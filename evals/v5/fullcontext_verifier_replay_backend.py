"""Eval-only backends for S52 verifier-only replay (no live LLM in scope)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from core.target_composer_executor import TargetComposerInvocation
from core.target_response_verifier import (
    TargetSemanticAssessment,
    TargetSemanticIssue,
    TargetSemanticVerifierInvocation,
)

class FullContextVerifierReplayTransportError(RuntimeError):
    """Eval transport failure before structured payload reaches S46 pipeline."""

    def __init__(self, code: str, value: object) -> None:
        self.code = code
        self.value = value
        super().__init__(f"{code}: {value!r}")


class FullContextVerifierReplayLiveNotConfiguredError(FullContextVerifierReplayTransportError):
    """Live delegate was not injected; eval refuses to call LLM implicitly."""


@dataclass(frozen=True, slots=True)
class FullContextVerifierReplayComposerCapture:
    invocation: TargetComposerInvocation
    raw_backend_payload: object


@dataclass(frozen=True, slots=True)
class FullContextVerifierReplaySemanticCapture:
    invocation: TargetSemanticVerifierInvocation
    raw_backend_payload: object


class FrozenCandidateComposerBackend:
    """Returns one frozen candidate text per case; never calls a Composer provider."""

    def __init__(self, candidate_text: str) -> None:
        self.candidate_text = candidate_text
        self.invocation_count = 0
        self.provider_call_count = 0
        self.captures: list[FullContextVerifierReplayComposerCapture] = []

    def generate(self, invocation: TargetComposerInvocation, /) -> object:
        self.invocation_count += 1
        if self.invocation_count > 1:
            raise FullContextVerifierReplayTransportError(
                "fullcontext_verifier_replay_composer_retry_forbidden",
                self.invocation_count,
            )
        self.captures.append(
            FullContextVerifierReplayComposerCapture(
                invocation=invocation,
                raw_backend_payload=self.candidate_text,
            )
        )
        return self.candidate_text


class IssueBasedFakeSemanticBackend:
    """Deterministic issue-based semantic backend for offline replay tests."""

    def __init__(
        self,
        *,
        assessment: TargetSemanticAssessment | None = None,
        assessment_for_case: Callable[[str, str], TargetSemanticAssessment] | None = None,
        case_id: str = "",
    ) -> None:
        self._assessment = assessment
        self._assessment_for_case = assessment_for_case
        self._case_id = case_id
        self.invocation_count = 0
        self.provider_call_count = 0
        self.captures: list[FullContextVerifierReplaySemanticCapture] = []

    def assess(self, invocation: TargetSemanticVerifierInvocation, /) -> object:
        self.invocation_count += 1
        if self.invocation_count > 1:
            raise FullContextVerifierReplayTransportError(
                "fullcontext_verifier_replay_semantic_retry_forbidden",
                self.invocation_count,
            )
        if self._assessment_for_case is not None:
            assessment = self._assessment_for_case(self._case_id, invocation.candidate_text)
        else:
            assessment = self._assessment or TargetSemanticAssessment()
        self.captures.append(
            FullContextVerifierReplaySemanticCapture(
                invocation=invocation,
                raw_backend_payload=assessment,
            )
        )
        return assessment


def owner_label_fake_assessment(case_id: str, candidate_text: str) -> TargetSemanticAssessment:
    from evals.v5.fullcontext_verifier_replay_contract import EXPECTED_BLOCK_CASE_IDS

    if case_id not in EXPECTED_BLOCK_CASE_IDS:
        return TargetSemanticAssessment()
    span_by_case = {
        "fc_medical_03": "гормональные изменения",
        "fc_missing_01": "компенсированном диабете",
        "fc_missing_02": "аутоиммунным",
    }
    span = span_by_case[case_id]
    if span not in candidate_text:
        raise FullContextVerifierReplayTransportError(
            "fullcontext_verifier_replay_fake_span_missing",
            (case_id, span),
        )
    return TargetSemanticAssessment(
        issues=(
            TargetSemanticIssue(
                kind="material_external_medical_claim",
                offending_span=span,
            ),
        )
    )


class FullContextVerifierReplaySemanticAdapter:
    """Requires explicit delegate; never calls LLM by itself."""

    def __init__(self, delegate: object | None = None) -> None:
        self._delegate = delegate
        self.invocation_count = 0
        self.provider_call_count = 0

    def assess(self, invocation: TargetSemanticVerifierInvocation, /) -> object:
        if self._delegate is None:
            raise FullContextVerifierReplayLiveNotConfiguredError(
                "fullcontext_verifier_replay_live_not_configured",
                "semantic",
            )
        self.invocation_count += 1
        if self.invocation_count > 1:
            raise FullContextVerifierReplayTransportError(
                "fullcontext_verifier_replay_semantic_retry_forbidden",
                self.invocation_count,
            )
        self.provider_call_count += 1
        assess = getattr(self._delegate, "assess")
        return assess(invocation)


def assert_backend_module_has_no_provider_imports() -> None:
    import ast

    path = Path(__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    forbidden = {
        "openai",
        "anthropic",
        "dashscope",
    }
    overlap = imported & forbidden
    if overlap:
        raise RuntimeError(f"forbidden provider imports present: {sorted(overlap)}")
