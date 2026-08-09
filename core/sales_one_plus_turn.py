"""Pure, non-activated one-Plus candidate orchestration."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Protocol

from contracts.exact_sales_resolution import ExactSalesResolution
from contracts.local_problem_gate import LocalProblemGateResult
from contracts.sales_one_plus import (
    SalesOnePlusInvocation,
    SalesOnePlusResult,
    SalesOnePlusStrictFact,
)
from contracts.target_cached_full_context import TargetCachedFullContext
from core import turn_timing
from core.local_problem_gate import decide_local_problem_gate
from core.sales_one_plus_protocol import (
    SALES_ONE_PLUS_SYSTEM_POLICY,
    SalesOnePlusProtocolError,
    build_sales_one_plus_user_prompt,
    parse_sales_one_plus_output,
)
from core.sales_one_plus_stream import SalesOnePlusStreamParser


RawDeltaCallback = Callable[[str], None]
PatientDeltaCallback = Callable[[str], None]


class SalesOnePlusBackend(Protocol):
    def generate(self, invocation: SalesOnePlusInvocation, /) -> object: ...


class SalesOnePlusStreamingBackend(Protocol):
    def generate_stream(
        self,
        invocation: SalesOnePlusInvocation,
        on_raw_delta: RawDeltaCallback,
        /,
    ) -> None: ...


class _ConsumerCallbackError(Exception):
    """Keep consumer cancellation distinct from provider/protocol failures."""

    def __init__(self, cause: Exception) -> None:
        self.cause = cause
        super().__init__(type(cause).__name__)


def _require_static_handoff(text: object) -> str:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("sales_one_plus_static_admin_handoff_empty")
    return text


def _make_invocation(
    *,
    user_message: str,
    cached_full_context: TargetCachedFullContext,
    exact_sales_resolution: ExactSalesResolution,
    current_strict_facts: Sequence[SalesOnePlusStrictFact],
    sales_context: Mapping[str, object] | None,
) -> SalesOnePlusInvocation:
    corpus = cached_full_context.model_corpus_text
    strict_facts = tuple(current_strict_facts)
    context = dict(sales_context or {})
    return SalesOnePlusInvocation(
        system_prompt=SALES_ONE_PLUS_SYSTEM_POLICY,
        user_prompt=build_sales_one_plus_user_prompt(
            model_corpus_text=corpus,
            exact_sales_resolution=exact_sales_resolution,
            current_strict_facts=strict_facts,
            sales_context=context,
            user_message=user_message,
        ),
        model_corpus_text=corpus,
        user_message=user_message,
        exact_sales_resolution=exact_sales_resolution,
        current_strict_facts=strict_facts,
        sales_context=context,
    )


def _result_from_local_gate(
    gate: LocalProblemGateResult,
    *,
    static_handoff: str,
) -> SalesOnePlusResult | None:
    if gate.decision == "spam":
        return SalesOnePlusResult(
            decision="spam",
            source="local_gate",
            reason=gate.reason_code,
        )
    if gate.decision == "admin":
        return SalesOnePlusResult(
            decision="admin",
            source="local_gate",
            reason=gate.reason_code,
            handoff_text=static_handoff,
        )
    return None


def _local_terminal_result(
    *,
    user_message: str,
    static_handoff: str,
    local_gate_result: LocalProblemGateResult | None = None,
) -> SalesOnePlusResult | None:
    if local_gate_result is not None:
        return _result_from_local_gate(local_gate_result, static_handoff=static_handoff)
    turn_timing.stage_start("sales_fast_local_gate")
    local = decide_local_problem_gate(user_message)
    turn_timing.stage_end("sales_fast_local_gate", status="completed", reason=local.decision)
    return _result_from_local_gate(local, static_handoff=static_handoff)


def _admin_result(
    *,
    source: str,
    reason: str,
    static_handoff: str,
) -> SalesOnePlusResult:
    return SalesOnePlusResult(
        decision="admin",
        source=source,
        reason=reason,
        handoff_text=static_handoff,
    )


def run_sales_one_plus_candidate(
    *,
    user_message: str,
    cached_full_context: TargetCachedFullContext,
    exact_sales_resolution: ExactSalesResolution,
    current_strict_facts: Sequence[SalesOnePlusStrictFact] = (),
    sales_context: Mapping[str, object] | None = None,
    static_admin_handoff_text: str,
    backend: SalesOnePlusBackend,
    local_gate_result: LocalProblemGateResult | None = None,
) -> SalesOnePlusResult:
    """Make exactly one blocking backend call after a local pass."""

    static_handoff = _require_static_handoff(static_admin_handoff_text)
    local_result = _local_terminal_result(
        user_message=user_message,
        static_handoff=static_handoff,
        local_gate_result=local_gate_result,
    )
    if local_result is not None:
        return local_result

    invocation = _make_invocation(
        user_message=user_message,
        cached_full_context=cached_full_context,
        exact_sales_resolution=exact_sales_resolution,
        current_strict_facts=current_strict_facts,
        sales_context=sales_context,
    )
    try:
        raw = backend.generate(invocation)
    except Exception:
        return _admin_result(
            source="backend",
            reason="backend_failed",
            static_handoff=static_handoff,
        )
    try:
        decision, text = parse_sales_one_plus_output(raw)
    except SalesOnePlusProtocolError as exc:
        return _admin_result(
            source="protocol",
            reason=exc.code,
            static_handoff=static_handoff,
        )
    if decision == "admin":
        return _admin_result(
            source="model",
            reason="model_admin",
            static_handoff=static_handoff,
        )
    return SalesOnePlusResult(
        decision="answer",
        source="model",
        reason="model_answer",
        patient_text=text,
    )


def run_sales_one_plus_candidate_stream(
    *,
    user_message: str,
    cached_full_context: TargetCachedFullContext,
    exact_sales_resolution: ExactSalesResolution,
    current_strict_facts: Sequence[SalesOnePlusStrictFact] = (),
    sales_context: Mapping[str, object] | None = None,
    static_admin_handoff_text: str,
    backend: SalesOnePlusStreamingBackend,
    on_delta: PatientDeltaCallback,
    local_gate_result: LocalProblemGateResult | None = None,
) -> SalesOnePlusResult:
    """Stream answer body after its marker using one backend call and no retry."""

    static_handoff = _require_static_handoff(static_admin_handoff_text)
    local_result = _local_terminal_result(
        user_message=user_message,
        static_handoff=static_handoff,
        local_gate_result=local_gate_result,
    )
    if local_result is not None:
        return local_result

    def emit_patient_delta(delta: str) -> None:
        try:
            on_delta(delta)
        except Exception as exc:
            raise _ConsumerCallbackError(exc) from exc

    parser = SalesOnePlusStreamParser(emit_patient_delta)
    invocation = _make_invocation(
        user_message=user_message,
        cached_full_context=cached_full_context,
        exact_sales_resolution=exact_sales_resolution,
        current_strict_facts=current_strict_facts,
        sales_context=sales_context,
    )
    try:
        backend.generate_stream(invocation, parser.ingest)
        decision, text = parser.finalize()
    except _ConsumerCallbackError as exc:
        raise exc.cause
    except SalesOnePlusProtocolError as exc:
        if parser.answer_text:
            return SalesOnePlusResult(
                decision="answer",
                source="backend",
                reason=exc.code,
                patient_text=parser.answer_text,
                interrupted=True,
            )
        return _admin_result(
            source="protocol",
            reason=exc.code,
            static_handoff=static_handoff,
        )
    except Exception:
        if parser.answer_text:
            return SalesOnePlusResult(
                decision="answer",
                source="backend",
                reason="stream_interrupted",
                patient_text=parser.answer_text,
                interrupted=True,
            )
        return _admin_result(
            source="backend",
            reason="backend_failed",
            static_handoff=static_handoff,
        )

    if decision == "admin":
        return _admin_result(
            source="model",
            reason="model_admin",
            static_handoff=static_handoff,
        )
    return SalesOnePlusResult(
        decision="answer",
        source="model",
        reason="model_answer",
        patient_text=text,
    )
