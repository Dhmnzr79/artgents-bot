"""Product runtime LLM backends for target FullContext path (S61)."""

from __future__ import annotations

import json
import os

from config import QWEN_PLUS_MODEL
from core.target_composer_executor import TargetComposerInvocation
from core.target_composer_json_stream import TargetComposerJsonStream
from core.target_medical_boundary import (
    TARGET_MEDICAL_BOUNDARY_SYSTEM_POLICY,
    TargetMedicalBoundaryInvocation,
)
from core.target_response_verifier import (
    TARGET_SEMANTIC_ISSUE_KINDS,
    TargetSemanticAssessment,
    TargetSemanticIssue,
    TargetSemanticVerifierInvocation,
)
from core.target_runtime_llm_messages import (
    build_boundary_sdk_messages,
    build_composer_sdk_messages,
    build_verifier_sdk_messages,
    parse_verifier_assessment_payload,
)
from llm import LLM_REQUEST_TIMEOUT_SEC, chat_completions_create, log_llm_error, log_llm_usage
from logging_setup import get_logger, log_llm_stream_usage

logger = get_logger("target_runtime")


class TargetRuntimeBackendTransportError(RuntimeError):
    """Typed transport failure for target runtime provider backends."""

    def __init__(self, code: str, value: object) -> None:
        self.code = code
        self.value = value
        super().__init__(f"{code}: {value!r}")


def target_fullcontext_composer_model() -> str:
    return (
        (os.getenv("TARGET_FULLCONTEXT_COMPOSER_MODEL") or "").strip()
        or (os.getenv("FULLCONTEXT_RESPONSE_EVAL_LLM_MODEL") or "").strip()
        or QWEN_PLUS_MODEL
    )


def target_fullcontext_verifier_model() -> str:
    return (
        (os.getenv("TARGET_FULLCONTEXT_VERIFIER_MODEL") or "").strip()
        or (os.getenv("FULLCONTEXT_RESPONSE_EVAL_LLM_MODEL") or "").strip()
        or QWEN_PLUS_MODEL
    )


def target_fullcontext_boundary_model() -> str:
    return (
        (os.getenv("TARGET_FULLCONTEXT_BOUNDARY_MODEL") or "").strip()
        or (os.getenv("MEDICAL_BOUNDARY_EVAL_LLM_MODEL") or "").strip()
        or QWEN_PLUS_MODEL
    )


class TargetRuntimeLiveComposerBackend:
    """One-shot live composer backend for target runtime (lazy network on generate)."""

    supports_deterministic_commercial_answer = True
    supports_versioned_answer_cache = True

    def __init__(self, *, model: str | None = None) -> None:
        self.model = model or target_fullcontext_composer_model()
        self.call_count = 0

    def generate(self, invocation: TargetComposerInvocation, /) -> object:
        self.call_count += 1
        if self.call_count > 1:
            raise TargetRuntimeBackendTransportError(
                "target_runtime_composer_retry_forbidden",
                self.call_count,
            )
        try:
            response = chat_completions_create(
                model=self.model,
                temperature=0,
                max_completion_tokens=1024,
                response_format={"type": "json_object"},
                timeout=LLM_REQUEST_TIMEOUT_SEC,
                messages=build_composer_sdk_messages(invocation),
            )
            log_llm_usage(
                logger,
                response,
                call_type="target_fullcontext_runtime_composer",
                model=self.model,
            )
            raw_text = (response.choices[0].message.content or "").strip()
            if not raw_text:
                raise ValueError("composer_empty_output")
            return raw_text
        except TargetRuntimeBackendTransportError:
            raise
        except Exception as exc:
            log_llm_error(
                logger,
                call_type="target_fullcontext_runtime_composer",
                model=self.model,
                err=str(exc)[:300],
            )
            raise TargetRuntimeBackendTransportError(
                "target_runtime_composer_provider_failed",
                type(exc).__name__,
            ) from exc

    def generate_stream(self, invocation: TargetComposerInvocation, on_delta, /) -> object:
        """Stream only the decoded ``answer`` field; retain strict JSON for parsing."""

        self.call_count += 1
        if self.call_count > 1:
            raise TargetRuntimeBackendTransportError(
                "target_runtime_composer_retry_forbidden",
                self.call_count,
            )
        parser = TargetComposerJsonStream()
        usage = None
        try:
            stream = chat_completions_create(
                model=self.model,
                temperature=0,
                max_completion_tokens=1024,
                response_format={"type": "json_object"},
                timeout=LLM_REQUEST_TIMEOUT_SEC,
                messages=build_composer_sdk_messages(invocation),
                stream=True,
                stream_options={"include_usage": True},
            )
            for chunk in stream:
                if getattr(chunk, "usage", None) is not None:
                    usage = chunk.usage
                choices = getattr(chunk, "choices", None) or ()
                if not choices:
                    continue
                raw_delta = getattr(getattr(choices[0], "delta", None), "content", None)
                if not raw_delta:
                    continue
                answer_delta = parser.ingest(str(raw_delta))
                if answer_delta:
                    on_delta(answer_delta)
            log_llm_stream_usage(
                logger,
                usage,
                call_type="target_fullcontext_runtime_composer",
                model=self.model,
            )
            if not parser.raw_json.strip():
                raise ValueError("composer_empty_output")
            return parser.raw_json
        except TargetRuntimeBackendTransportError:
            raise
        except Exception as exc:
            log_llm_error(
                logger,
                call_type="target_fullcontext_runtime_composer",
                model=self.model,
                err=str(exc)[:300],
            )
            raise TargetRuntimeBackendTransportError(
                "target_runtime_composer_provider_failed",
                type(exc).__name__,
            ) from exc


class TargetRuntimeLiveSemanticBackend:
    """One-shot live semantic verifier backend for target runtime."""

    def __init__(self, *, model: str | None = None) -> None:
        self.model = model or target_fullcontext_verifier_model()
        self.call_count = 0

    def assess(self, invocation: TargetSemanticVerifierInvocation, /) -> object:
        self.call_count += 1
        if self.call_count > 1:
            raise TargetRuntimeBackendTransportError(
                "target_runtime_verifier_retry_forbidden",
                self.call_count,
            )
        try:
            response = chat_completions_create(
                model=self.model,
                temperature=0,
                max_completion_tokens=512,
                response_format={"type": "json_object"},
                timeout=LLM_REQUEST_TIMEOUT_SEC,
                messages=build_verifier_sdk_messages(invocation),
            )
            log_llm_usage(
                logger,
                response,
                call_type="target_fullcontext_runtime_verifier",
                model=self.model,
            )
            raw_text = (response.choices[0].message.content or "").strip()
            payload = json.loads(raw_text)
            parsed = parse_verifier_assessment_payload(payload)
            issues: list[TargetSemanticIssue] = []
            for item in parsed["issues"]:
                if not isinstance(item, dict):
                    raise ValueError("semantic_issue_not_object")
                kind = item["kind"]
                span = item["offending_span"]
                if type(kind) is not str or kind not in TARGET_SEMANTIC_ISSUE_KINDS:
                    raise ValueError("semantic_issue_kind_invalid")
                if type(span) is not str or not span.strip():
                    raise ValueError("semantic_issue_span_invalid")
                issues.append(TargetSemanticIssue(kind=kind, offending_span=span.strip()))  # type: ignore[arg-type]
            return TargetSemanticAssessment(issues=tuple(issues))
        except TargetRuntimeBackendTransportError:
            raise
        except Exception as exc:
            log_llm_error(
                logger,
                call_type="target_fullcontext_runtime_verifier",
                model=self.model,
                err=str(exc)[:300],
            )
            raise TargetRuntimeBackendTransportError(
                "target_runtime_verifier_provider_failed",
                type(exc).__name__,
            ) from exc


class TargetRuntimeLiveMedicalBoundaryBackend:
    """One-shot live medical boundary backend for target runtime."""

    def __init__(self, *, model: str | None = None) -> None:
        self.model = model or target_fullcontext_boundary_model()
        self.call_count = 0

    def classify(self, invocation: TargetMedicalBoundaryInvocation, /) -> object:
        self.call_count += 1
        if self.call_count > 1:
            raise TargetRuntimeBackendTransportError(
                "target_runtime_boundary_retry_forbidden",
                self.call_count,
            )
        try:
            response = chat_completions_create(
                model=self.model,
                temperature=0,
                max_completion_tokens=64,
                response_format={"type": "json_object"},
                timeout=LLM_REQUEST_TIMEOUT_SEC,
                messages=build_boundary_sdk_messages(
                    system_policy=TARGET_MEDICAL_BOUNDARY_SYSTEM_POLICY,
                    user_message=invocation.user_message,
                ),
            )
            log_llm_usage(
                logger,
                response,
                call_type="target_fullcontext_runtime_boundary",
                model=self.model,
            )
            raw_text = (response.choices[0].message.content or "").strip()
            payload = json.loads(raw_text)
            if not isinstance(payload, dict):
                raise ValueError("boundary_not_object")
            if set(payload.keys()) != {"decision", "confidence"}:
                raise ValueError("boundary_extra_fields")
            return payload
        except TargetRuntimeBackendTransportError:
            raise
        except Exception as exc:
            log_llm_error(
                logger,
                call_type="target_fullcontext_runtime_boundary",
                model=self.model,
                err=str(exc)[:300],
            )
            raise TargetRuntimeBackendTransportError(
                "target_runtime_boundary_provider_failed",
                type(exc).__name__,
            ) from exc
