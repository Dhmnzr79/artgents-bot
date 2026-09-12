"""Eval-only live LLM delegates for S47 FullContext response eval (not product/runtime)."""

from __future__ import annotations

import json
import os

from config import QWEN_PLUS_MODEL
from core.target_composer_executor import TargetComposerInvocation
from core.target_response_verifier import (
    TARGET_SEMANTIC_ISSUE_KINDS,
    TargetSemanticAssessment,
    TargetSemanticIssue,
    TargetSemanticVerifierInvocation,
)
from evals.v5.fullcontext_response_eval_backend import (
    FullContextResponseEvalComposerCapture,
    FullContextResponseEvalSemanticCapture,
    FullContextResponseEvalTransportError,
)
from llm import LLM_REQUEST_TIMEOUT_SEC, chat_completions_create, log_llm_error, log_llm_usage
from logging_setup import get_logger

logger = get_logger("fullcontext_response_eval")

_COMPOSER_USER_TEMPLATE = (
    "Compose the patient-facing answer using the inputs below.\n\n"
    "CACHED_FULL_CONTEXT:\n{cached_full_context}\n\n"
    "RESPONSE_DIRECTIVES_JSON:\n{response_directives_json}\n\n"
    "PRIMARY_EVIDENCE_JSON:\n{primary_evidence_json}\n\n"
    "USER_MESSAGE:\n{user_message}"
)

_VERIFIER_USER_TEMPLATE = (
    "Assess the candidate answer using the inputs below.\n\n"
    "CACHED_FULL_CONTEXT:\n{cached_full_context}\n\n"
    "RESPONSE_SPEC_JSON:\n{response_spec_json}\n\n"
    "PRIMARY_EVIDENCE_JSON:\n{primary_evidence_json}\n\n"
    "CANDIDATE_TEXT:\n{candidate_text}\n\n"
    "Return JSON only: "
    '{{"issues":[{{"kind":"<unsupported_clinic_claim|personal_medical_conclusion|'
    "material_external_medical_claim|minor_external_detail>\","
    '"offending_span":"<exact substring from candidate>"}}]}}'
)

_ISSUE_KINDS = tuple(sorted(TARGET_SEMANTIC_ISSUE_KINDS))


def serialize_composer_invocation_for_sdk(
    invocation: TargetComposerInvocation,
) -> dict[str, str]:
    payload = {
        "system_policy": invocation.system_policy,
        "cached_full_context": invocation.cached_full_context,
        "response_directives_json": invocation.response_directives_json,
        "primary_evidence_json": invocation.primary_evidence_json,
        "user_message": invocation.user_message,
    }
    return json.loads(json.dumps(payload, ensure_ascii=False))


def serialize_verifier_invocation_for_sdk(
    invocation: TargetSemanticVerifierInvocation,
) -> dict[str, str]:
    payload = {
        "system_policy": invocation.system_policy,
        "cached_full_context": invocation.cached_full_context,
        "response_spec_json": invocation.response_spec_json,
        "primary_evidence_json": invocation.primary_evidence_json,
        "candidate_text": invocation.candidate_text,
    }
    return json.loads(json.dumps(payload, ensure_ascii=False))


def build_composer_sdk_messages(
    invocation: TargetComposerInvocation,
) -> list[dict[str, str]]:
    serialized = serialize_composer_invocation_for_sdk(invocation)
    return [
        {"role": "system", "content": serialized["system_policy"]},
        {
            "role": "user",
            "content": _COMPOSER_USER_TEMPLATE.format(
                cached_full_context=serialized["cached_full_context"],
                response_directives_json=serialized["response_directives_json"],
                primary_evidence_json=serialized["primary_evidence_json"],
                user_message=serialized["user_message"],
            ),
        },
    ]


def build_verifier_sdk_messages(
    invocation: TargetSemanticVerifierInvocation,
) -> list[dict[str, str]]:
    serialized = serialize_verifier_invocation_for_sdk(invocation)
    return [
        {"role": "system", "content": serialized["system_policy"]},
        {
            "role": "user",
            "content": _VERIFIER_USER_TEMPLATE.format(
                cached_full_context=serialized["cached_full_context"],
                response_spec_json=serialized["response_spec_json"],
                primary_evidence_json=serialized["primary_evidence_json"],
                candidate_text=serialized["candidate_text"],
            ),
        },
    ]


def _serialize_usage(usage: object) -> object:
    if usage is None:
        return None
    if hasattr(usage, "model_dump"):
        return usage.model_dump()
    if hasattr(usage, "to_dict"):
        return usage.to_dict()
    return {
        key: getattr(usage, key)
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        if hasattr(usage, key)
    }


def fullcontext_response_eval_live_model() -> str:
    return (
        (os.getenv("FULLCONTEXT_RESPONSE_EVAL_LLM_MODEL") or "").strip()
        or QWEN_PLUS_MODEL
    )


def _parse_assessment_payload(payload: object) -> TargetSemanticAssessment:
    if not isinstance(payload, dict):
        raise ValueError("semantic_live_not_object")
    if set(payload.keys()) != {"issues"}:
        raise ValueError("semantic_live_field_mismatch")
    raw_issues = payload["issues"]
    if type(raw_issues) is not list:
        raise ValueError("semantic_live_issues_not_list")
    issues: list[TargetSemanticIssue] = []
    for item in raw_issues:
        if not isinstance(item, dict):
            raise ValueError("semantic_live_issue_not_object")
        if set(item.keys()) != {"kind", "offending_span"}:
            raise ValueError("semantic_live_issue_field_mismatch")
        kind = item["kind"]
        span = item["offending_span"]
        if type(kind) is not str or kind not in TARGET_SEMANTIC_ISSUE_KINDS:
            raise ValueError("semantic_live_issue_kind_invalid")
        if type(span) is not str or not span.strip():
            raise ValueError("semantic_live_issue_span_invalid")
        issues.append(TargetSemanticIssue(kind=kind, offending_span=span.strip()))  # type: ignore[arg-type]
    return TargetSemanticAssessment(issues=tuple(issues))


class FullContextResponseEvalLiveComposerBackend:
    """One-shot live composer backend for eval harness injection only."""

    def __init__(self, *, model: str | None = None) -> None:
        self.model = model or fullcontext_response_eval_live_model()
        self.call_count = 0
        self.captures: list[FullContextResponseEvalComposerCapture] = []

    def generate(self, invocation: TargetComposerInvocation, /) -> object:
        self.call_count += 1
        if self.call_count > 1:
            raise FullContextResponseEvalTransportError(
                "fullcontext_response_eval_composer_retry_forbidden",
                self.call_count,
            )
        try:
            response = chat_completions_create(
                model=self.model,
                temperature=0,
                max_completion_tokens=1024,
                timeout=LLM_REQUEST_TIMEOUT_SEC,
                messages=build_composer_sdk_messages(invocation),
            )
            log_llm_usage(
                logger,
                response,
                call_type="s47_fullcontext_response_live_composer",
                model=self.model,
            )
            raw_text = (response.choices[0].message.content or "").strip()
            if not raw_text:
                raise ValueError("composer_live_empty_output")
            self.captures.append(
                FullContextResponseEvalComposerCapture(
                    invocation=invocation,
                    raw_backend_payload={
                        "model": self.model,
                        "text": raw_text,
                        "usage": _serialize_usage(getattr(response, "usage", None)),
                    },
                )
            )
            return raw_text
        except FullContextResponseEvalTransportError:
            raise
        except Exception as exc:
            log_llm_error(
                logger,
                call_type="s47_fullcontext_response_live_composer",
                err=str(exc),
                model=self.model,
            )
            raise FullContextResponseEvalTransportError(
                "fullcontext_response_eval_live_composer_failure",
                exc,
            ) from exc


class FullContextResponseEvalLiveSemanticBackend:
    """One-shot live semantic verifier backend for eval harness injection only."""

    def __init__(self, *, model: str | None = None) -> None:
        self.model = model or fullcontext_response_eval_live_model()
        self.call_count = 0
        self.captures: list[FullContextResponseEvalSemanticCapture] = []

    def assess(self, invocation: TargetSemanticVerifierInvocation, /) -> object:
        self.call_count += 1
        if self.call_count > 1:
            raise FullContextResponseEvalTransportError(
                "fullcontext_response_eval_semantic_retry_forbidden",
                self.call_count,
            )
        try:
            response = chat_completions_create(
                model=self.model,
                temperature=0,
                max_completion_tokens=128,
                response_format={"type": "json_object"},
                timeout=LLM_REQUEST_TIMEOUT_SEC,
                messages=build_verifier_sdk_messages(invocation),
            )
            log_llm_usage(
                logger,
                response,
                call_type="s47_fullcontext_response_live_verifier",
                model=self.model,
            )
            raw_text = (response.choices[0].message.content or "").strip()
            payload = json.loads(raw_text)
            assessment = _parse_assessment_payload(payload)
            self.captures.append(
                FullContextResponseEvalSemanticCapture(
                    invocation=invocation,
                    raw_backend_payload={
                        "model": self.model,
                        "assessment": payload,
                        "usage": _serialize_usage(getattr(response, "usage", None)),
                    },
                )
            )
            return assessment
        except FullContextResponseEvalTransportError:
            raise
        except Exception as exc:
            log_llm_error(
                logger,
                call_type="s47_fullcontext_response_live_verifier",
                err=str(exc),
                model=self.model,
            )
            raise FullContextResponseEvalTransportError(
                "fullcontext_response_eval_live_verifier_failure",
                exc,
            ) from exc
