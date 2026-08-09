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
from core.sales_fast_observability import collect_sales_fast_timings_ms, record_sales_fast_observability
from core.sales_fast_presentation import (
    materialize_sales_fast_admin_payload,
    materialize_sales_fast_answer_payload,
    materialize_sales_fast_spam_payload,
    materialize_sales_fast_terminal_from_dispatch,
    sales_fast_session_selection,
    static_sales_fast_admin_handoff,
)
from core.sales_fast_strict_evidence import (
    assemble_sales_fast_bound_package,
    strict_facts_and_sales_context,
)
from core.sales_fast_turn_frame import (
    build_sales_fast_turn_frame,
    project_sales_fast_scope_from_message,
)
from core.sales_one_plus_turn import (
    run_sales_one_plus_candidate,
    run_sales_one_plus_candidate_stream,
)
from core.target_client_data import match_service_from_target_catalog
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
from core.target_strategy_context import strategy_match_from_effective_scope
from core.target_spec_offline_response_package import TargetSpecBoundOfflineResponsePackage


PatientDeltaCallback = Callable[[str], None]


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


def _exact_service_term(user_message: str, client_id: str) -> str | None:
    match = match_service_from_target_catalog(user_message, client_id=client_id)
    term = str(
        match.get("matched_phrase")
        or match.get("matched_service_term")
        or match.get("matched_label")
        or ""
    ).strip()
    return term or None


def _resolve_sales_context(
    *,
    context: TargetRuntimeClientContext,
    sid: str,
    user_message: str,
) -> tuple[ExactSalesResolution, object, TargetPresentationCadenceState]:
    session_state = read_target_runtime_session(sid)
    current_ui_scope_action = _current_ui_scope_action()
    current_ui_stage_action = _current_ui_stage_action()
    projected_turn_scope = project_sales_fast_scope_from_message(user_message)
    from contracts.answer_plan import AspectKind
    from core.answer_planner import detect_aspects_regex

    aspects = detect_aspects_regex(user_message)
    exact_aspect: AspectKind | None = aspects[0] if aspects else None
    resolution = resolve_exact_sales_inputs(
        ExactSalesResolverInputs(
            services=context.bundle.services,
            current_topic=None,
            session_turn_count=session_state.session_turn_count,
            current_ui_scope_action=current_ui_scope_action,
            current_ui_stage_action=current_ui_stage_action,
            exact_service_term=_exact_service_term(user_message, context.client_id),
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
    return resolution, session_state, cadence


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
    resolution, session_state, cadence = _resolve_sales_context(
        context=context,
        sid=sid,
        user_message=user_message,
    )
    projected_turn_scope = project_sales_fast_scope_from_message(user_message)
    turn_frame = build_sales_fast_turn_frame(
        resolution=resolution,
        user_message=user_message,
        client_id=client_id,
        bundle=context.bundle,
    )
    effective_scope = resolve_effective_scope(
        current_ui_action=_current_ui_scope_action(),
        current_ui_stage_action=_current_ui_stage_action(),
        session_facts=session_state.patient_facts,
        current_topic=turn_frame.topic,
        session_turn_count=session_state.session_turn_count,
        projected_turn_scope=projected_turn_scope,
    )
    strategy_context = strategy_match_from_effective_scope(
        effective_scope,
        service_family=resolve_target_runtime_strategy_context(
            context.bundle,
            service_id=turn_frame.service_id,
        ).family,
    )
    bound = assemble_sales_fast_bound_package(
        turn_frame=turn_frame,
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
        shown_fact_ids=session_state.shown_fact_ids,
        shown_amplifier_refs=session_state.shown_amplifier_refs,
        shown_consultation_value_refs=session_state.shown_consultation_value_refs,
    )
    turn_timing.stage_end("sales_fast_resolver", status="completed")
    if isinstance(bound, TargetTurnFrameBoundTerminalResponse):
        turn_timing.stage_end("sales_fast", status="completed", reason="terminal_dispatch")
        record_sales_fast_observability(
            architecture="new",
            route="terminal",
            provider_calls=0,
            model=None,
        )
        return SalesFastWidgetOutcome(
            widget=materialize_sales_fast_terminal_from_dispatch(
                terminal=bound,
                client_id=client_id,
                sid=sid,
            ),
            provider_calls=0,
            model_route="local",
        )

    strict_facts, sales_context = strict_facts_and_sales_context(
        bound_package=bound,
        resolution=resolution,
        bundle=context.bundle,
    )
    static_handoff = static_sales_fast_admin_handoff(client_id=client_id)
    turn_timing.stage_start("sales_fast_model")
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
            on_delta=on_delta,
            local_gate_result=local_gate,
        )
    backend_invocations = int(getattr(backend, "call_count", 0) or 0)
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
        bound=bound,
        context=context,
        turn_frame=turn_frame,
        user_message=user_message,
        sid=sid,
        cadence=cadence,
        client_id=client_id,
        effective_scope=effective_scope,
        session_state=session_state,
        provider_calls=provider_calls,
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
    )
    return outcome


def _materialize_result(
    *,
    result: SalesOnePlusResult,
    bound: TargetSpecBoundOfflineResponsePackage,
    context: TargetRuntimeClientContext,
    turn_frame: object,
    user_message: str,
    sid: str,
    cadence: TargetPresentationCadenceState,
    client_id: str,
    effective_scope: object,
    session_state: object,
    provider_calls: int,
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
    turn_timing.stage_start("sales_fast_presentation")
    widget = materialize_sales_fast_answer_payload(
        bound_package=bound,
        context=context,
        turn_frame=turn_frame,  # type: ignore[arg-type]
        patient_text=result.patient_text or "",
        user_message=user_message,
        sid=sid,
        cadence=cadence,
        allow_situation=True,
    )
    turn_timing.stage_end("sales_fast_presentation", status="completed")
    from contracts.turn_frame import TurnFrame

    if widget.kind == "materialized" and isinstance(turn_frame, TurnFrame):
        final_patient_text = str(widget.payload.get("answer") or "")
        verified = build_sales_fast_verified_for_session(
            bound_package=bound,
            context=context,
            turn_frame=turn_frame,  # type: ignore[arg-type]
            patient_text=final_patient_text,
            user_message=user_message,
        )
        selection = sales_fast_session_selection(
            bound_package=bound,
            patient_text=final_patient_text,
            used_content_refs=verified.used_content_refs,
        )
        write_target_runtime_session_after_materialized(
            sid,
            turn_frame=turn_frame,  # type: ignore[arg-type]
            verified=verified,
            prior=session_state,  # type: ignore[arg-type]
            current_selection=selection,
            followups=_followups_from_widget(widget),
            effective_scope=effective_scope,  # type: ignore[arg-type]
            presentation_cadence_update=widget.presentation_cadence_update,
        )
    return SalesFastWidgetOutcome(
        widget=widget,
        provider_calls=provider_calls,
        model_route="model",
        failure_kind=result.reason if result.interrupted else None,
    )


def build_sales_fast_verified_for_session(
    *,
    bound_package: TargetSpecBoundOfflineResponsePackage,
    context: TargetRuntimeClientContext,
    turn_frame: TurnFrame,
    patient_text: str,
    user_message: str,
):
    from core.sales_fast_presentation import build_sales_fast_verified_response

    return build_sales_fast_verified_response(
        bound_package=bound_package,
        context=context,
        turn_frame=turn_frame,
        patient_text=patient_text,
        user_message=user_message,
    )
