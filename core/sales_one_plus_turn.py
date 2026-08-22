"""Pure, non-activated one-Plus candidate orchestration."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Literal, Protocol

from contracts.exact_sales_resolution import ExactSalesResolution
from contracts.local_problem_gate import LocalProblemGateResult
from contracts.one_call_client_pack_identity import ClientPackIdentityKey
from contracts.one_call_envelope import OneCallEnvelope
from contracts.sales_one_plus import (
    SalesOnePlusInvocation,
    SalesOnePlusResult,
    SalesOnePlusStrictFact,
)
from contracts.target_cached_full_context import TargetCachedFullContext
from core import turn_timing
from core.local_problem_gate import decide_local_problem_gate
from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.one_call_commercial_fact_catalog import CommercialFactCatalogSnapshot
from core.one_call_envelope_protocol import (
    OneCallEnvelopeProtocolError,
    parse_production_envelope_json,
)
from core.one_call_prefix_cache import get_or_build_stable_prefix
from core.sales_one_plus_protocol import build_sales_one_plus_dynamic_suffix
from core.sales_one_plus_stream import SalesOnePlusStreamParser
from core.service_reference_catalog import ServiceReferenceCatalogSnapshot


RawDeltaCallback = Callable[[str], None]
PatientDeltaCallback = Callable[[str], None]
ModelRouteDecision = Literal["answer", "admin", "clarify"]


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
    pack_identity: ClientPackIdentityKey,
    active_service_catalog: ActiveServiceCatalogSnapshot,
    service_reference_catalog: ServiceReferenceCatalogSnapshot,
    commercial_fact_catalog: CommercialFactCatalogSnapshot,
) -> SalesOnePlusInvocation:
    corpus = cached_full_context.model_corpus_text
    strict_facts = tuple(current_strict_facts)
    context = dict(sales_context or {})
    prefix_bundle, local_hit = get_or_build_stable_prefix(
        identity=pack_identity,
        cached_full_context=cached_full_context,
        active_service_catalog=active_service_catalog,
        service_reference_catalog=service_reference_catalog,
        commercial_fact_catalog=commercial_fact_catalog,
    )
    dynamic_suffix = build_sales_one_plus_dynamic_suffix(
        exact_sales_resolution=exact_sales_resolution,
        current_strict_facts=strict_facts,
        sales_context=context,
        user_message=user_message,
    )
    return SalesOnePlusInvocation(
        system_prompt=prefix_bundle.stable_prefix,
        user_prompt=dynamic_suffix,
        model_corpus_text=corpus,
        user_message=user_message,
        exact_sales_resolution=exact_sales_resolution,
        current_strict_facts=strict_facts,
        sales_context=context,
        pack_identity=pack_identity,
        local_prefix_cache_hit=local_hit,
        prefix_build_ms=prefix_bundle.build_ms if not local_hit else 0,
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
    envelope: OneCallEnvelope | None = None,
) -> SalesOnePlusResult:
    return SalesOnePlusResult(
        decision="admin",
        source=source,
        reason=reason,
        handoff_text=static_handoff,
        envelope=envelope,
    )


def _model_result_from_envelope(envelope: OneCallEnvelope) -> SalesOnePlusResult:
    if envelope.route == "ADMIN":
        raise ValueError("admin_envelope_requires_static_handoff")
    if envelope.route == "CLARIFY":
        return SalesOnePlusResult(
            decision="clarify",
            source="model",
            reason="model_clarify",
            patient_text=envelope.patient_text,
            envelope=envelope,
        )
    return SalesOnePlusResult(
        decision="answer",
        source="model",
        reason="model_answer",
        patient_text=envelope.patient_text,
        envelope=envelope,
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
    pack_identity: ClientPackIdentityKey,
    active_service_catalog: ActiveServiceCatalogSnapshot,
    service_reference_catalog: ServiceReferenceCatalogSnapshot,
    commercial_fact_catalog: CommercialFactCatalogSnapshot,
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
        pack_identity=pack_identity,
        active_service_catalog=active_service_catalog,
        service_reference_catalog=service_reference_catalog,
        commercial_fact_catalog=commercial_fact_catalog,
    )
    try:
        raw = backend.generate(invocation)
    except Exception:
        return _admin_result(
            source="backend",
            reason="backend_failed",
            static_handoff=static_handoff,
        )
    envelope = parse_production_envelope_json(
        raw,
        active_service_catalog=active_service_catalog,
        service_reference_catalog=service_reference_catalog,
        commercial_fact_catalog=commercial_fact_catalog,
    )
    if envelope.route == "ADMIN":
        return _admin_result(
            source="model",
            reason="model_admin",
            static_handoff=static_handoff,
            envelope=envelope,
        )
    return _model_result_from_envelope(envelope)


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
    pack_identity: ClientPackIdentityKey,
    active_service_catalog: ActiveServiceCatalogSnapshot,
    service_reference_catalog: ServiceReferenceCatalogSnapshot,
    commercial_fact_catalog: CommercialFactCatalogSnapshot,
) -> SalesOnePlusResult:
    """Buffer provider JSON fully, validate once, then emit patient_text only."""

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

    parser = SalesOnePlusStreamParser(
        emit_patient_delta,
        active_service_catalog=active_service_catalog,
        service_reference_catalog=service_reference_catalog,
        commercial_fact_catalog=commercial_fact_catalog,
    )
    invocation = _make_invocation(
        user_message=user_message,
        cached_full_context=cached_full_context,
        exact_sales_resolution=exact_sales_resolution,
        current_strict_facts=current_strict_facts,
        sales_context=sales_context,
        pack_identity=pack_identity,
        active_service_catalog=active_service_catalog,
        service_reference_catalog=service_reference_catalog,
        commercial_fact_catalog=commercial_fact_catalog,
    )
    try:
        backend.generate_stream(invocation, parser.ingest)
        envelope = parser.finalize()
    except _ConsumerCallbackError as exc:
        raise exc.cause
    except OneCallEnvelopeProtocolError:
        raise
    except Exception:
        reason = "stream_interrupted" if parser.has_partial_content else "backend_failed"
        return _admin_result(
            source="backend",
            reason=reason,
            static_handoff=static_handoff,
        )

    if envelope.route == "ADMIN":
        return _admin_result(
            source="model",
            reason="model_admin",
            static_handoff=static_handoff,
            envelope=envelope,
        )
    return _model_result_from_envelope(envelope)
