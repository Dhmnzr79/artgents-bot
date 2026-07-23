"""Product runtime entry point for target FullContext responses (S61)."""

from __future__ import annotations

from dataclasses import dataclass

from contracts.target_turn_frame_dispatch import (
    TargetTurnFrameBoundMaterializeResponse,
    TargetTurnFrameBoundTerminalResponse,
)
from contracts.turn_frame import TurnFrame
from core.target_boundary_enforced_fullcontext_response import (
    run_target_offline_boundary_enforced_fullcontext_response,
)
from core.target_composer_executor import TargetComposerBackend
from core.target_medical_boundary import (
    TargetMedicalBoundaryBackend,
    execute_target_medical_boundary_classification,
)
from core.target_response_verifier import (
    TargetResponseVerificationError,
    TargetSemanticVerifierBackend,
)
from core.target_runtime_client_context import (
    TargetRuntimeClientContextError,
    load_target_runtime_client_context,
    runtime_today,
)
from core.target_runtime_session import (
    read_target_runtime_session,
    write_target_runtime_session_after_materialized,
)
from core.target_runtime_followup_nav import TargetRuntimeFollowupItem
from core.target_runtime_strategy import resolve_target_runtime_strategy_context
from core.target_runtime_turn_frame_bridge import (
    TargetRuntimeTurnFrameError,
    load_runtime_turn_frame,
)
from core.target_session_selection import TargetMaterializedSessionSelection
from core.target_runtime_widget import (
    TargetRuntimeWidgetPayload,
    materialize_target_error_payload,
    widget_payload_from_runtime_result,
)


@dataclass(frozen=True, slots=True)
class TargetRuntimeTurnOutcome:
    widget: TargetRuntimeWidgetPayload
    pipeline_result: object | None
    turn_frame: TurnFrame | None


def _followups_from_widget(widget: TargetRuntimeWidgetPayload) -> tuple[TargetRuntimeFollowupItem, ...]:
    payload = widget.payload
    quick = payload.get("quick_replies") if isinstance(payload.get("quick_replies"), list) else []
    items: list[TargetRuntimeFollowupItem] = []
    for entry in quick:
        if not isinstance(entry, dict):
            continue
        ref = str(entry.get("ref") or "").strip()
        label = str(entry.get("label") or "").strip()
        if ref:
            items.append(TargetRuntimeFollowupItem(ref=ref, label=label))
    return tuple(items)


def run_target_fullcontext_runtime_turn(
    *,
    client_id: str,
    sid: str,
    user_message: str,
    composer_backend: TargetComposerBackend,
    semantic_backend: TargetSemanticVerifierBackend,
    boundary_backend: TargetMedicalBoundaryBackend,
    brand_term: str | None = None,
) -> TargetRuntimeTurnOutcome:
    """Run one target-only FullContext turn via existing S46 pipeline."""

    try:
        context = load_target_runtime_client_context(client_id)
    except TargetRuntimeClientContextError as exc:
        return TargetRuntimeTurnOutcome(
            widget=materialize_target_error_payload(
                client_id=client_id,
                sid=sid,
                error_code=exc.code,
            ),
            pipeline_result=None,
            turn_frame=None,
        )

    try:
        turn_frame = load_runtime_turn_frame()
    except TargetRuntimeTurnFrameError as exc:
        return TargetRuntimeTurnOutcome(
            widget=materialize_target_error_payload(
                client_id=client_id,
                sid=sid,
                error_code=exc.code,
            ),
            pipeline_result=None,
            turn_frame=None,
        )

    session_state = read_target_runtime_session(sid)
    try:
        boundary = execute_target_medical_boundary_classification(
            user_message,
            backend=boundary_backend,
            min_confidence_none=0.80,
            min_confidence_medical_handoff=0.70,
        )
    except Exception as exc:
        return TargetRuntimeTurnOutcome(
            widget=materialize_target_error_payload(
                client_id=client_id,
                sid=sid,
                error_code=f"target_runtime_boundary_failed:{type(exc).__name__}",
            ),
            pipeline_result=None,
            turn_frame=turn_frame,
        )

    strategy_context = resolve_target_runtime_strategy_context(
        context.bundle,
        service_id=turn_frame.service_id,
    )

    try:
        result = run_target_offline_boundary_enforced_fullcontext_response(
            turn_frame,
            boundary,
            context.bundle,
            context.doctor_catalog,
            context.external_index,
            context.consultation_values,
            tone_key="commercial_warm",
            allowed_topics=context.allowed_topics,
            forbidden_topics=("diagnosis", "personal_eligibility"),
            required_fact_ids=(),
            allow_marketing_facts=True,
            allow_consultation_close=True,
            allow_cta=True,
            min_topic_confidence=0.5,
            min_service_confidence=0.0,
            min_intent_confidence=0.0,
            brand_term=brand_term,
            strategy_context=strategy_context,
            semantic_context=context.semantic_context,
            today=runtime_today(),
            md_root=context.md_root,
            cached_full_context=context.cached_full_context,
            include_initial_block=context.include_initial_block,
            include_consultation_close=context.include_consultation_close,
            include_cta=context.cta_capability,
            user_message=user_message,
            tone=context.tone,
            composer_backend=composer_backend,
            semantic_backend=semantic_backend,
            marketing_scenarios=(),
            shown_fact_ids=session_state.shown_fact_ids,
            shown_amplifier_refs=session_state.shown_amplifier_refs,
            shown_consultation_value_refs=session_state.shown_consultation_value_refs,
        )
    except TargetResponseVerificationError as exc:
        return TargetRuntimeTurnOutcome(
            widget=materialize_target_error_payload(
                client_id=client_id,
                sid=sid,
                error_code=exc.code,
            ),
            pipeline_result=None,
            turn_frame=turn_frame,
        )
    except Exception as exc:
        return TargetRuntimeTurnOutcome(
            widget=materialize_target_error_payload(
                client_id=client_id,
                sid=sid,
                error_code=f"target_runtime_pipeline_failed:{type(exc).__name__}",
            ),
            pipeline_result=None,
            turn_frame=turn_frame,
        )

    widget = widget_payload_from_runtime_result(
        client_id=client_id,
        sid=sid,
        context=context,
        result=result,
        turn_frame=turn_frame,
    )

    if isinstance(result, TargetTurnFrameBoundMaterializeResponse):
        selection = result.session_selection or TargetMaterializedSessionSelection((), (), ())
        followups = _followups_from_widget(widget)
        write_target_runtime_session_after_materialized(
            sid,
            turn_frame=turn_frame,
            verified=result.verified,
            prior=session_state,
            current_selection=selection,
            followups=followups,
        )

    return TargetRuntimeTurnOutcome(
        widget=widget,
        pipeline_result=result,
        turn_frame=turn_frame,
    )
