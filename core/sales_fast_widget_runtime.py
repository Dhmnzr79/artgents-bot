"""Sales-fast widget runtime: local gate → exact resolver → one call → presentation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from config import SALES_ONE_PLUS_FLASH_MODEL
from contracts.exact_sales_resolution import ExactSalesResolution
from contracts.local_problem_gate import LocalProblemGateResult
from contracts.sales_one_plus import SalesOnePlusResult
from contracts.target_turn_frame_dispatch import TargetTurnFrameBoundTerminalResponse
from contracts.turn_frame import TurnFrame
from contracts.ui_scope_action import UiScopeAction
from contracts.ui_stage_action import UiStageAction
from core import turn_timing
from core.exact_sales_resolver import ExactSalesResolverInputs, resolve_exact_sales_inputs
from core.local_problem_gate import decide_local_problem_gate
from core.provider_call_budget import current_provider_call_budget
from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.service_reference_catalog import ServiceReferenceCatalogSnapshot
from core.sales_fast_observability import collect_sales_fast_timings_ms, record_sales_fast_observability
from core.sales_fast_presentation import (
    materialize_sales_fast_admin_payload,
    materialize_sales_fast_answer_payload,
    materialize_sales_fast_error_payload,
    materialize_sales_fast_spam_payload,
    materialize_sales_fast_terminal_from_dispatch,
    sales_fast_session_selection,
    static_sales_fast_admin_handoff,
)
from core.one_call_presentation_pass import build_one_call_presentation_result
from core.sales_fast_strict_evidence import (
    assemble_sales_fast_bound_package,
    build_pre_flash_prompt_hints,
    effective_scope_from_semantic_frame,
    exact_sales_resolution_from_semantic_frame,
    resolve_sales_fast_bound_package,
)
from core.sales_fast_turn_frame import (
    build_provisional_turn_frame,
    build_turn_frame_from_semantic_frame,
    project_sales_fast_scope_from_message,
)
from core.sales_one_plus_semantic_authority import (
    SalesOnePlusSemanticConflictError,
    bind_semantic_frame,
    governed_ui_authority_from_resolution,
)
from core.sales_one_plus_turn import (
    run_sales_one_plus_candidate,
    run_sales_one_plus_candidate_stream,
)
from core.sales_fast_service_identity import (
    SalesFastServiceIdentity,
    resolve_catalog_service_identity,
    resolve_session_service_for_followup,
)
from core.target_effective_scope import resolve_effective_scope
from core.target_presentation_decision import TargetPresentationCadenceState
from core.target_runtime_client_context import (
    TargetRuntimeClientContext,
    load_target_runtime_client_context,
    runtime_today,
)
from core.target_runtime_session import (
    read_target_runtime_session,
    write_target_runtime_session_after_materialized,
)
from core.target_runtime_strategy import resolve_target_runtime_strategy_context
from core.target_runtime_turn import _followups_from_widget
from core.target_runtime_widget import TargetRuntimeWidgetPayload, materialize_target_error_payload
from core.target_service_resolver import TargetServiceResolutionError
from core.target_strategy_context import strategy_match_from_effective_scope
from core.target_spec_offline_response_package import TargetSpecBoundOfflineResponsePackage


PatientDeltaCallback = Callable[[str], None]

_TECHNICAL_ERROR_PATIENT_TEXT = (
    "Сейчас не удалось подготовить ответ. Пожалуйста, попробуйте повторить вопрос."
)
_TECHNICAL_SEMANTIC_CONFLICT_CODES = frozenset(
    {
        "semantic_catalog_envelope_conflict_service_id",
        "semantic_session_envelope_conflict_service_id",
    }
)


class SalesFastOneCallBackend(Protocol):
    def generate(self, invocation: object, /) -> object: ...


class SalesFastStreamingBackend(Protocol):
    def generate_stream(
        self,
        invocation: object,
        on_raw_delta: Callable[[str], None],
        /,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class SalesFastWidgetOutcome:
    widget: TargetRuntimeWidgetPayload
    provider_calls: int
    model_route: str
    failure_kind: str | None = None


def _current_ui_scope_action() -> UiScopeAction | None:
    try:
        from flask import request

        raw = request.ctx.get("current_ui_scope_action")
    except Exception:
        return None
    if not isinstance(raw, dict):
        return None
    try:
        return UiScopeAction.model_validate(raw)
    except Exception:
        return None


def _current_ui_stage_action() -> UiStageAction | None:
    try:
        from flask import request

        raw = request.ctx.get("current_ui_stage_action")
    except Exception:
        return None
    if not isinstance(raw, dict):
        return None
    try:
        return UiStageAction.model_validate(raw)
    except Exception:
        return None


def _is_governed_typed_ui_turn() -> bool:
    return _current_ui_scope_action() is not None or _current_ui_stage_action() is not None


def _run_local_problem_gate_first(user_message: str) -> LocalProblemGateResult | None:
    """Normative gate for free text; governed typed UI skips lexical gate."""

    if _is_governed_typed_ui_turn():
        turn_timing.stage_skipped("sales_fast_local_gate", reason="typed_ui")
        return None
    turn_timing.stage_start("sales_fast_local_gate")
    gate = decide_local_problem_gate(user_message)
    turn_timing.stage_end(
        "sales_fast_local_gate",
        status="completed",
        reason=gate.reason_code,
    )
    return gate


def _local_gate_terminal_outcome(
    gate: LocalProblemGateResult,
    *,
    client_id: str,
    sid: str,
) -> SalesFastWidgetOutcome | None:
    if gate.decision == "spam":
        return SalesFastWidgetOutcome(
            widget=materialize_sales_fast_spam_payload(client_id=client_id, sid=sid),
            provider_calls=0,
            model_route="local",
        )
    if gate.decision == "admin":
        handoff = static_sales_fast_admin_handoff(client_id=client_id)
        return SalesFastWidgetOutcome(
            widget=materialize_sales_fast_admin_payload(
                client_id=client_id,
                sid=sid,
                handoff_text=handoff,
            ),
            provider_calls=0,
            model_route="local",
        )
    return None


def sales_fast_widget_outcome_from_local_gate(
    gate: LocalProblemGateResult,
    *,
    client_id: str,
    sid: str,
) -> SalesFastWidgetOutcome | None:
    """Materialize spam/admin terminal widgets from a normative gate result."""

    return _local_gate_terminal_outcome(gate, client_id=client_id, sid=sid)


def _technical_error_outcome(
    *,
    client_id: str,
    sid: str,
    error_code: str,
    provider_calls: int,
) -> SalesFastWidgetOutcome:
    return SalesFastWidgetOutcome(
        widget=materialize_sales_fast_error_payload(
            client_id=client_id,
            sid=sid,
            error_code=error_code,
            patient_text=_TECHNICAL_ERROR_PATIENT_TEXT,
        ),
        provider_calls=provider_calls,
        model_route="error",
        failure_kind=error_code,
    )


def _resolve_sales_context(
    *,
    context: TargetRuntimeClientContext,
    sid: str,
    user_message: str,
) -> tuple[ExactSalesResolution, object, TargetPresentationCadenceState, SalesFastServiceIdentity]:
    session_state = read_target_runtime_session(sid)
    current_ui_scope_action = _current_ui_scope_action()
    current_ui_stage_action = _current_ui_stage_action()
    projected_turn_scope = project_sales_fast_scope_from_message(user_message)
    from contracts.answer_plan import AspectKind
    from core.answer_planner import detect_aspects_regex

    aspects = detect_aspects_regex(user_message)
    exact_aspect: AspectKind | None = aspects[0] if aspects else None
    service_identity = resolve_catalog_service_identity(user_message, context.bundle)
    resolution = resolve_exact_sales_inputs(
        ExactSalesResolverInputs(
            services=context.bundle.services,
            current_topic=None,
            session_turn_count=session_state.session_turn_count,
            current_ui_scope_action=current_ui_scope_action,
            current_ui_stage_action=current_ui_stage_action,
            exact_service_term=service_identity.explicit_service_term,
            exact_aspect=exact_aspect,
            projected_turn_scope=projected_turn_scope,
            session_facts=session_state.patient_facts,
        )
    )
    cadence = TargetPresentationCadenceState(
        shown_video_ids=frozenset(session_state.shown_video_ids),
        shown_content_followup_refs=frozenset(session_state.shown_content_followup_refs),
        shown_price_followup_refs=frozenset(session_state.shown_price_followup_refs),
        situation_offered=session_state.situation_offered,
    )
    return resolution, session_state, cadence, service_identity


def _maybe_pre_flash_terminal(
    *,
    turn_frame: TurnFrame,
    context: TargetRuntimeClientContext,
    session_state: object,
    client_id: str,
    sid: str,
    effective_scope: object,
    strategy_context: object,
) -> SalesFastWidgetOutcome | None:
    if not _is_governed_typed_ui_turn():
        return None
    bound = assemble_sales_fast_bound_package(
        turn_frame=turn_frame,
        bundle=context.bundle,
        doctor_catalog=context.doctor_catalog,
        external_index=context.external_index,
        consultation_values=context.consultation_values,
        strategy_context=strategy_context,  # type: ignore[arg-type]
        effective_scope=effective_scope,  # type: ignore[arg-type]
        allowed_topics=context.allowed_topics,
        today=runtime_today(),
        md_root=context.md_root,
        client_id=client_id,
        shown_fact_ids=session_state.shown_fact_ids,  # type: ignore[attr-defined]
        shown_amplifier_refs=session_state.shown_amplifier_refs,  # type: ignore[attr-defined]
        shown_consultation_value_refs=session_state.shown_consultation_value_refs,  # type: ignore[attr-defined]
    )
    if not isinstance(bound, TargetTurnFrameBoundTerminalResponse):
        return None
    return SalesFastWidgetOutcome(
        widget=materialize_sales_fast_terminal_from_dispatch(
            terminal=bound,
            client_id=client_id,
            sid=sid,
        ),
        provider_calls=0,
        model_route="local",
    )


def _rebuild_authoritative_context(
    *,
    result: SalesOnePlusResult,
    context: TargetRuntimeClientContext,
    user_message: str,
    client_id: str,
    session_state: object,
    active_service_catalog: ActiveServiceCatalogSnapshot,
    service_reference_catalog: ServiceReferenceCatalogSnapshot,
    resolution: ExactSalesResolution,
    service_identity: SalesFastServiceIdentity,
) -> tuple[
    TurnFrame,
    TargetSpecBoundOfflineResponsePackage | TargetTurnFrameBoundTerminalResponse,
    object,
    ExactSalesResolution,
    object,
    object,
]:
    if result.envelope is None:
        raise ValueError("authoritative_rebuild_requires_envelope")
    governed_ui = governed_ui_authority_from_resolution(resolution)
    session_service_id = resolve_session_service_for_followup(
        turn_frame=build_provisional_turn_frame(
            resolution=resolution,
            user_message=user_message,
            client_id=client_id,
            bundle=context.bundle,
        ),
        user_message=user_message,
        session_state=session_state,  # type: ignore[arg-type]
        allowed_service_ids=active_service_catalog.active_service_ids,
        explicit_service_id=service_identity.explicit_service_id,
        commercial_intent=result.envelope.commercial_intent,
    )
    bound_identity = service_identity.with_session_service(session_service_id)
    semantic = bind_semantic_frame(
        envelope=result.envelope,
        governed_ui=governed_ui,
        active_service_catalog=active_service_catalog,
        service_reference_catalog=service_reference_catalog,
        explicit_catalog_service_id=bound_identity.explicit_service_id,
        session_service_id=bound_identity.session_service_id,
    )
    turn_frame = build_turn_frame_from_semantic_frame(
        semantic=semantic,
        user_message=user_message,
        bundle=context.bundle,
    )
    effective_scope = effective_scope_from_semantic_frame(
        semantic,
        current_ui_action=_current_ui_scope_action(),
        current_ui_stage_action=_current_ui_stage_action(),
    )
    strategy_context = strategy_match_from_effective_scope(
        effective_scope,  # type: ignore[arg-type]
        service_family=resolve_target_runtime_strategy_context(
            context.bundle,
            service_id=turn_frame.service_id,
        ).family,
    )
    commerce_resolution = exact_sales_resolution_from_semantic_frame(semantic)
    bound = resolve_sales_fast_bound_package(
        turn_frame=turn_frame,
        semantic=semantic,
        bundle=context.bundle,
        doctor_catalog=context.doctor_catalog,
        external_index=context.external_index,
        consultation_values=context.consultation_values,
        strategy_context=strategy_context,
        effective_scope=effective_scope,
        allowed_topics=context.allowed_topics,
        today=runtime_today(),
        md_root=context.md_root,
        client_id=client_id,
        shown_fact_ids=session_state.shown_fact_ids,  # type: ignore[attr-defined]
        shown_amplifier_refs=session_state.shown_amplifier_refs,  # type: ignore[attr-defined]
        shown_consultation_value_refs=session_state.shown_consultation_value_refs,  # type: ignore[attr-defined]
    )
    return turn_frame, bound, effective_scope, commerce_resolution, strategy_context, semantic


def run_sales_fast_widget_turn(
    *,
    client_id: str,
    sid: str,
    user_message: str,
    backend: SalesFastOneCallBackend,
    on_delta: PatientDeltaCallback | None = None,
    local_gate_result: LocalProblemGateResult | None = None,
) -> SalesFastWidgetOutcome:
    turn_timing.stage_skipped("planner", reason="sales_fast_path")
    turn_timing.stage_skipped("boundary", reason="sales_fast_path")
    turn_timing.stage_skipped("composer", reason="sales_fast_path")
    turn_timing.stage_skipped("verifier_deterministic", reason="sales_fast_path")
    turn_timing.stage_skipped("verifier_semantic", reason="sales_fast_path")
    turn_timing.stage_start("sales_fast")
    if local_gate_result is not None:
        if local_gate_result.reason_code == "governed_typed_ui":
            turn_timing.stage_skipped("sales_fast_local_gate", reason="governed_typed_ui")
        else:
            turn_timing.stage_skipped("sales_fast_local_gate", reason="pre_orchestrated")
        local_gate = local_gate_result
    else:
        local_gate = _run_local_problem_gate_first(user_message)
    if local_gate is not None:
        early = _local_gate_terminal_outcome(
            local_gate,
            client_id=client_id,
            sid=sid,
        )
        if early is not None:
            turn_timing.stage_end("sales_fast", status="completed", reason=local_gate.reason_code)
            record_sales_fast_observability(
                architecture="new",
                route="local",
                provider_calls=0,
                model=None,
                timings=collect_sales_fast_timings_ms(),
            )
            return early
    try:
        context = load_target_runtime_client_context(client_id)
    except Exception as exc:
        turn_timing.stage_end("sales_fast", status="exception", reason=type(exc).__name__)
        record_sales_fast_observability(
            architecture="new",
            route="error",
            provider_calls=0,
            model=None,
            failure_kind="bootstrap_failed",
        )
        return SalesFastWidgetOutcome(
            widget=materialize_target_error_payload(
                client_id=client_id,
                sid=sid,
                error_code=f"sales_fast_bootstrap_failed:{type(exc).__name__}",
            ),
            provider_calls=0,
            model_route="error",
            failure_kind="bootstrap_failed",
        )

    turn_timing.stage_start("sales_fast_resolver")
    try:
        resolution, session_state, cadence, service_identity = _resolve_sales_context(
            context=context,
            sid=sid,
            user_message=user_message,
        )
    except TargetServiceResolutionError as exc:
        turn_timing.stage_end("sales_fast_resolver", status="exception", reason=exc.code)
        turn_timing.stage_end("sales_fast", status="exception", reason=exc.code)
        record_sales_fast_observability(
            architecture="new",
            route="error",
            provider_calls=0,
            model=None,
            failure_kind=exc.code,
        )
        return _technical_error_outcome(
            client_id=client_id,
            sid=sid,
            error_code=exc.code,
            provider_calls=0,
        )
    projected_turn_scope = project_sales_fast_scope_from_message(user_message)
    turn_frame = build_provisional_turn_frame(
        resolution=resolution,
        user_message=user_message,
        client_id=client_id,
        bundle=context.bundle,
    )
    effective_scope = resolve_effective_scope(
        current_ui_action=_current_ui_scope_action(),
        current_ui_stage_action=_current_ui_stage_action(),
        session_facts=session_state.patient_facts if _is_governed_typed_ui_turn() else None,
        current_topic=turn_frame.topic,
        session_turn_count=session_state.session_turn_count,
        projected_turn_scope=projected_turn_scope if _is_governed_typed_ui_turn() else None,
    )
    strategy_context = strategy_match_from_effective_scope(
        effective_scope,
        service_family=resolve_target_runtime_strategy_context(
            context.bundle,
            service_id=turn_frame.service_id,
        ).family,
    )
    pre_flash_terminal = _maybe_pre_flash_terminal(
        turn_frame=turn_frame,
        context=context,
        session_state=session_state,
        client_id=client_id,
        sid=sid,
        effective_scope=effective_scope,
        strategy_context=strategy_context,
    )
    if pre_flash_terminal is not None:
        turn_timing.stage_end("sales_fast_resolver", status="completed", reason="terminal_dispatch")
        turn_timing.stage_end("sales_fast", status="completed", reason="terminal_dispatch")
        record_sales_fast_observability(
            architecture="new",
            route="terminal",
            provider_calls=0,
            model=None,
        )
        return pre_flash_terminal
    turn_timing.stage_end("sales_fast_resolver", status="completed")
    strict_facts, sales_context = build_pre_flash_prompt_hints(
        resolution=resolution,
        catalog_service_hint=service_identity.explicit_service_term,
        session_service_hint=session_state.last_service_id,
    )
    static_handoff = static_sales_fast_admin_handoff(client_id=client_id)
    active_service_catalog = ActiveServiceCatalogSnapshot.from_bundle(context.bundle)
    service_reference_catalog = ServiceReferenceCatalogSnapshot.from_bundle(context.bundle)
    turn_timing.stage_start("sales_fast_model")
    stream_on_delta: PatientDeltaCallback | None
    if on_delta is None:
        stream_on_delta = None
    else:

        def _buffer_model_delta(_: str) -> None:
            return None

        stream_on_delta = _buffer_model_delta

    if on_delta is None:
        result = run_sales_one_plus_candidate(
            user_message=user_message,
            cached_full_context=context.cached_full_context,
            exact_sales_resolution=resolution,
            current_strict_facts=strict_facts,
            sales_context=sales_context,
            static_admin_handoff_text=static_handoff,
            backend=backend,  # type: ignore[arg-type]
            local_gate_result=local_gate,
            pack_identity=context.pack_identity,
            active_service_catalog=active_service_catalog,
            service_reference_catalog=service_reference_catalog,
        )
    else:
        result = run_sales_one_plus_candidate_stream(
            user_message=user_message,
            cached_full_context=context.cached_full_context,
            exact_sales_resolution=resolution,
            current_strict_facts=strict_facts,
            sales_context=sales_context,
            static_admin_handoff_text=static_handoff,
            backend=backend,  # type: ignore[arg-type]
            on_delta=stream_on_delta,
            local_gate_result=local_gate,
            pack_identity=context.pack_identity,
            active_service_catalog=active_service_catalog,
            service_reference_catalog=service_reference_catalog,
        )
    backend_invocations = int(getattr(backend, "call_count", 0) or 0)
    cache_obs = getattr(backend, "last_observability", None)
    budget = current_provider_call_budget()
    if budget is not None:
        provider_calls = int(budget.call_count)
    else:
        provider_calls = 0
    turn_timing.stage_end(
        "sales_fast_model",
        status="completed",
        llm_used=provider_calls > 0,
        reason=result.reason,
    )
    outcome = _materialize_result(
        result=result,
        context=context,
        turn_frame=turn_frame,
        user_message=user_message,
        sid=sid,
        cadence=cadence,
        client_id=client_id,
        session_state=session_state,
        provider_calls=provider_calls,
        resolution=resolution,
        active_service_catalog=active_service_catalog,
        service_reference_catalog=service_reference_catalog,
        service_identity=service_identity,
        on_patient_delta=on_delta,
    )
    turn_timing.stage_end("sales_fast", status="completed")
    record_sales_fast_observability(
        architecture="new",
        route=outcome.model_route,
        provider_calls=provider_calls,
        model=SALES_ONE_PLUS_FLASH_MODEL if provider_calls else None,
        failure_kind=outcome.failure_kind,
        timings=collect_sales_fast_timings_ms(),
        backend_invocations=backend_invocations,
        cache_observability=cache_obs,
    )
    return outcome


def _materialize_result(
    *,
    result: SalesOnePlusResult,
    context: TargetRuntimeClientContext,
    turn_frame: TurnFrame,
    user_message: str,
    sid: str,
    cadence: TargetPresentationCadenceState,
    client_id: str,
    session_state: object,
    provider_calls: int,
    resolution: ExactSalesResolution,
    active_service_catalog: ActiveServiceCatalogSnapshot,
    service_reference_catalog: ServiceReferenceCatalogSnapshot,
    service_identity: SalesFastServiceIdentity,
    on_patient_delta: PatientDeltaCallback | None = None,
) -> SalesFastWidgetOutcome:
    if result.decision == "spam":
        return SalesFastWidgetOutcome(
            widget=materialize_sales_fast_spam_payload(client_id=client_id, sid=sid),
            provider_calls=provider_calls,
            model_route="local",
        )
    if result.decision == "admin":
        handoff = result.handoff_text or static_sales_fast_admin_handoff(client_id=client_id)
        return SalesFastWidgetOutcome(
            widget=materialize_sales_fast_admin_payload(
                client_id=client_id,
                sid=sid,
                handoff_text=handoff,
            ),
            provider_calls=provider_calls,
            model_route="local" if result.source == "local_gate" else "model_admin",
            failure_kind=None if result.source == "local_gate" else result.reason,
        )
    try:
        (
            authoritative_turn_frame,
            bound,
            effective_scope,
            commerce_resolution,
            strategy_context,
            semantic,
        ) = _rebuild_authoritative_context(
            result=result,
            context=context,
            user_message=user_message,
            client_id=client_id,
            session_state=session_state,
            active_service_catalog=active_service_catalog,
            service_reference_catalog=service_reference_catalog,
            resolution=resolution,
            service_identity=service_identity,
        )
    except SalesOnePlusSemanticConflictError as exc:
        if exc.code in _TECHNICAL_SEMANTIC_CONFLICT_CODES:
            return _technical_error_outcome(
                client_id=client_id,
                sid=sid,
                error_code=exc.code,
                provider_calls=provider_calls,
            )
        handoff = static_sales_fast_admin_handoff(client_id=client_id)
        return SalesFastWidgetOutcome(
            widget=materialize_sales_fast_admin_payload(
                client_id=client_id,
                sid=sid,
                handoff_text=handoff,
            ),
            provider_calls=provider_calls,
            model_route="model_admin",
            failure_kind=exc.code,
        )
    except ValueError as exc:
        if str(exc) == "authoritative_rebuild_requires_envelope":
            return _technical_error_outcome(
                client_id=client_id,
                sid=sid,
                error_code="authoritative_rebuild_requires_envelope",
                provider_calls=provider_calls,
            )
        raise
    if isinstance(bound, TargetTurnFrameBoundTerminalResponse):
        terminal_route = "clarify" if result.decision == "clarify" else "local"
        return SalesFastWidgetOutcome(
            widget=materialize_sales_fast_terminal_from_dispatch(
                terminal=bound,
                client_id=client_id,
                sid=sid,
            ),
            provider_calls=provider_calls,
            model_route=terminal_route,
        )
    turn_timing.stage_start("sales_fast_presentation")
    presentation = build_one_call_presentation_result(
        bound_package=bound,
        context=context,
        turn_frame=authoritative_turn_frame,
        semantic=semantic,  # type: ignore[arg-type]
        patient_text=result.patient_text or "",
        user_message=user_message,
        cadence=cadence,
        allow_situation=True,
        resolution=commerce_resolution,
        strategy_context=strategy_context,  # type: ignore[arg-type]
        shown_fact_ids=session_state.shown_fact_ids,  # type: ignore[attr-defined]
        shown_amplifier_refs=session_state.shown_amplifier_refs,  # type: ignore[attr-defined]
        shown_consultation_value_refs=session_state.shown_consultation_value_refs,  # type: ignore[attr-defined]
        last_rendered_promo_fact_id=session_state.last_rendered_promo_fact_id,  # type: ignore[attr-defined]
        today=runtime_today(),
    )
    widget = materialize_sales_fast_answer_payload(
        bound_package=bound,
        context=context,
        turn_frame=authoritative_turn_frame,
        patient_text=result.patient_text or "",
        user_message=user_message,
        sid=sid,
        cadence=cadence,
        allow_situation=True,
        resolution=commerce_resolution,
        strategy_context=strategy_context,  # type: ignore[arg-type]
        presentation=presentation,
    )
    turn_timing.stage_end("sales_fast_presentation", status="completed")
    if (
        widget.kind == "materialized"
        and presentation.status == "ok"
        and presentation.verified_for_session is not None
    ):
        final_patient_text = str(widget.payload.get("answer") or "")
        from core.target_response_verifier import TargetVerifiedComposedResponse
        from core.target_session_selection import TargetMaterializedSessionSelection

        verified = presentation.verified_for_session
        if not isinstance(verified, TargetVerifiedComposedResponse):
            raise TypeError("presentation_verified_for_session_invalid")
        session_delta = presentation.pending_session_delta
        if session_delta is not None:
            selection = TargetMaterializedSessionSelection(
                shown_fact_ids=session_delta.shown_fact_ids,
                shown_amplifier_refs=session_delta.shown_amplifier_refs,
                shown_consultation_value_refs=session_delta.shown_consultation_value_refs,
                last_rendered_promo_fact_id=session_delta.last_rendered_promo_fact_id,
            )
        else:
            selection = sales_fast_session_selection(
                bound_package=bound,
                patient_text=final_patient_text,
                used_content_refs=verified.used_content_refs,
            )
        write_target_runtime_session_after_materialized(
            sid,
            turn_frame=authoritative_turn_frame,
            verified=verified,
            prior=session_state,  # type: ignore[arg-type]
            current_selection=selection,
            followups=_followups_from_widget(widget),
            effective_scope=effective_scope,  # type: ignore[arg-type]
            presentation_cadence_update=widget.presentation_cadence_update,
            availability_status=semantic.availability_status,
        )
    model_route = "clarify" if result.decision == "clarify" else "model"
    outcome = SalesFastWidgetOutcome(
        widget=widget,
        provider_calls=provider_calls,
        model_route=model_route,
        failure_kind=result.reason if result.interrupted else None,
    )
    if on_patient_delta is not None and widget.kind == "materialized":
        final_patient_text = str(widget.payload.get("answer") or "").strip()
        if final_patient_text:
            on_patient_delta(final_patient_text)
    return outcome
