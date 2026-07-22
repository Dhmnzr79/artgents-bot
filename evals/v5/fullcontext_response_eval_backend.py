"""Eval-only backend adapters for S47 FullContext response eval (no live LLM in scope)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from core.target_composer_executor import TargetComposerBackend, TargetComposerInvocation
from core.target_response_verifier import (
    TargetSemanticVerification,
    TargetSemanticVerifierBackend,
    TargetSemanticVerifierInvocation,
)


class FullContextResponseEvalTransportError(RuntimeError):
    """Eval transport failure before structured payload reaches S46 pipeline."""

    def __init__(self, code: str, value: object) -> None:
        self.code = code
        self.value = value
        super().__init__(f"{code}: {value!r}")


class FullContextResponseEvalLiveNotConfiguredError(FullContextResponseEvalTransportError):
    """Live delegate was not injected; eval refuses to call LLM implicitly."""


@dataclass(frozen=True, slots=True)
class FullContextResponseEvalComposerCapture:
    invocation: TargetComposerInvocation
    raw_backend_payload: object


@dataclass(frozen=True, slots=True)
class FullContextResponseEvalSemanticCapture:
    invocation: TargetSemanticVerifierInvocation
    raw_backend_payload: object


class FullContextResponseEvalRecordingComposerBackend:
    """Fake composer backend: one generate call per case."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.call_count = 0
        self.captures: list[FullContextResponseEvalComposerCapture] = []

    def generate(self, invocation: TargetComposerInvocation, /) -> object:
        self.call_count += 1
        if self.call_count > 1:
            raise FullContextResponseEvalTransportError(
                "fullcontext_response_eval_composer_retry_forbidden",
                self.call_count,
            )
        self.captures.append(
            FullContextResponseEvalComposerCapture(
                invocation=invocation,
                raw_backend_payload=self.text,
            )
        )
        return self.text


class FullContextResponseEvalRecordingSemanticBackend:
    """Fake semantic backend: one assess call per case."""

    def __init__(
        self,
        assessment: TargetSemanticVerification | None = None,
    ) -> None:
        self.assessment = assessment or TargetSemanticVerification(
            general_grounding_ok=True,
            strict_commercial_grounding_ok=True,
            topic_scope_ok=True,
            medical_boundary_ok=True,
            selected_facts_ok=True,
        )
        self.call_count = 0
        self.captures: list[FullContextResponseEvalSemanticCapture] = []

    def assess(self, invocation: TargetSemanticVerifierInvocation, /) -> object:
        self.call_count += 1
        if self.call_count > 1:
            raise FullContextResponseEvalTransportError(
                "fullcontext_response_eval_semantic_retry_forbidden",
                self.call_count,
            )
        self.captures.append(
            FullContextResponseEvalSemanticCapture(
                invocation=invocation,
                raw_backend_payload=self.assessment,
            )
        )
        return self.assessment


class FullContextResponseEvalComposerAdapter:
    """Requires explicit delegate; never calls LLM by itself."""

    def __init__(self, delegate: TargetComposerBackend | None = None) -> None:
        self._delegate = delegate
        self.call_count = 0

    def generate(self, invocation: TargetComposerInvocation, /) -> object:
        if self._delegate is None:
            raise FullContextResponseEvalLiveNotConfiguredError(
                "fullcontext_response_eval_live_not_configured",
                "composer",
            )
        self.call_count += 1
        if self.call_count > 1:
            raise FullContextResponseEvalTransportError(
                "fullcontext_response_eval_composer_retry_forbidden",
                self.call_count,
            )
        return self._delegate.generate(invocation)


class FullContextResponseEvalSemanticAdapter:
    """Requires explicit delegate; never calls LLM by itself."""

    def __init__(self, delegate: TargetSemanticVerifierBackend | None = None) -> None:
        self._delegate = delegate
        self.call_count = 0

    def assess(self, invocation: TargetSemanticVerifierInvocation, /) -> object:
        if self._delegate is None:
            raise FullContextResponseEvalLiveNotConfiguredError(
                "fullcontext_response_eval_live_not_configured",
                "semantic",
            )
        self.call_count += 1
        if self.call_count > 1:
            raise FullContextResponseEvalTransportError(
                "fullcontext_response_eval_semantic_retry_forbidden",
                self.call_count,
            )
        return self._delegate.assess(invocation)
