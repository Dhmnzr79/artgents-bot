"""Isolated one-call Composer executor with injected backend."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from contracts.response_plan_composer import (
    AdaptedComposerDecision,
    ComposerAdapterError,
    ComposerParserError,
    adapt_composer_envelope_to_decision,
    parse_response_plan_composer_json,
)
from contracts.response_plan_composer_input import (
    ComposerInputContext,
    ComposerInputError,
    validate_composer_input_context,
)
from core.response_plan_composer_input import (
    ComposerDecisionInvocation,
    build_composer_decision_invocation,
)

ComposerExecutorErrorCode = Literal[
    "composer_bypass_forbidden",
    "composer_backend_exception",
    "composer_backend_non_string_output",
]


class ComposerExecutorError(ValueError):
    """Typed executor boundary error."""

    def __init__(self, code: ComposerExecutorErrorCode, detail: object = None) -> None:
        self.code = code
        self.detail = detail
        message = code if detail is None else f"{code}: {detail!r}"
        super().__init__(message)


class ComposerOutputError(ValueError):
    """Typed model output error preserving parser diagnostics."""

    def __init__(self, code: str, detail: object = None) -> None:
        self.code = code
        self.detail = detail
        message = code if detail is None else f"{code}: {detail!r}"
        super().__init__(message)


class ComposerDecisionBackend(Protocol):
    def generate(self, invocation: ComposerDecisionInvocation, /) -> str: ...


@dataclass(frozen=True, slots=True)
class ComposerDecisionExecutionResult:
    adapted_decision: AdaptedComposerDecision
    invocation: ComposerDecisionInvocation
    provider_call_count: int
    source_corpus_sha256: str
    model_corpus_sha256: str


def execute_composer_decision(
    input_context: ComposerInputContext,
    backend: ComposerDecisionBackend,
) -> ComposerDecisionExecutionResult:
    """Validate input, invoke backend exactly once, parse and adapt model output."""

    try:
        validate_composer_input_context(input_context)
    except ComposerInputError as exc:
        if exc.code == "composer_input_bypass_forbidden":
            raise ComposerExecutorError("composer_bypass_forbidden", exc.detail) from exc
        raise

    invocation = build_composer_decision_invocation(input_context)
    provider_call_count = 0

    try:
        raw_output = backend.generate(invocation)
        provider_call_count = 1
    except ComposerExecutorError:
        raise
    except Exception as exc:
        raise ComposerExecutorError("composer_backend_exception", type(exc).__name__) from exc

    if not isinstance(raw_output, str):
        raise ComposerExecutorError(
            "composer_backend_non_string_output",
            type(raw_output).__name__,
        )

    try:
        parsed = parse_response_plan_composer_json(raw_output)
        adapted = adapt_composer_envelope_to_decision(
            parsed,
            input_context.decision_authority,
        )
    except ComposerParserError as exc:
        raise ComposerOutputError(exc.code, exc.detail) from exc
    except ComposerAdapterError as exc:
        raise ComposerOutputError(exc.code, exc.detail) from exc

    return ComposerDecisionExecutionResult(
        adapted_decision=adapted,
        invocation=invocation,
        provider_call_count=provider_call_count,
        source_corpus_sha256=invocation.source_corpus_sha256,
        model_corpus_sha256=invocation.model_corpus_sha256,
    )
