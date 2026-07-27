"""Product runtime entry point for target FullContext responses (S61)."""

from __future__ import annotations

from dataclasses import dataclass

from contracts.target_turn_frame_dispatch import (
    TargetTurnFrameBoundMaterializeResponse,
    TargetTurnFrameBoundTerminalResponse,
)
from contracts.turn_frame import TurnFrame
from contracts.ui_scope_action import UiScopeAction
from contracts.ui_stage_action import UiStageAction
from core.target_composer_action_context import (
    bind_pending_ui_actions_for_composer,
    reset_pending_ui_actions_for_composer,
)
from core.target_boundary_enforced_fullcontext_response import (
    run_target_offline_boundary_enforced_fullcontext_response,
)
from core.target_composer_executor import TargetComposerBackend
from core.target_medical_boundary import (
    TargetMedicalBoundaryBackend,
    execute_target_medical_boundary_classification,
    normalize_boundary_for_pipeline,
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
from core.target_effective_scope import resolve_effective_scope
from core.target_patient_scope_projection import project_patient_scope_from_turn_frame
from core.target_runtime_session import (
    read_target_runtime_session,
    sync_session_patient_facts_topic,
    write_target_runtime_session_after_materialized,
)
from core.target_runtime_followup_nav import TargetRuntimeFollowupItem
from core.target_presentation_decision import TargetPresentationCadenceState
from core.target_pipeline_observability import (
    emit_target_pipeline_failure_from_exception,
)
from core.target_presentation_turn_projection import (
    marketing_scenarios_from_turn_frame,
    provisional_spec_from_turn_frame,
    resolve_target_semantic_context,
)
from core.target_runtime_strategy import resolve_target_runtime_strategy_context
from core.target_strategy_context import strategy_match_from_effective_scope
from core.target_runtime_turn_frame_hydration import (
    hydrate_target_runtime_turn_frame_from_session,
)
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
from core.target_structured_answer import (
    materialize_structured_contact_turn_response,
    resolve_structured_answer_capability,
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


def _current_ui_scope_action_from_request() -> UiScopeAction | None:
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


def _current_ui_stage_action_from_request() -> UiStageAction | None:
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


def _publish_effective_scope(scope) -> None:
    try:
        from flask import request

        request.ctx["effective_scope"] = scope.model_dump()
    except Exception:
        pass


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
    turn_frame = hydrate_target_runtime_turn_frame_from_session(
        turn_frame,
        user_message=user_message,
        session_state=session_state,
        allowed_service_ids=frozenset(context.bundle.services.keys()),
    )

    sync_session_patient_facts_topic(sid, current_topic=turn_frame.topic)
    session_state = read_target_runtime_session(sid)
    projected_turn_scope = project_patient_scope_from_turn_frame(turn_frame)
    effective_scope = resolve_effective_scope(
        current_ui_action=_current_ui_scope_action_from_request(),
        current_ui_stage_action=_current_ui_stage_action_from_request(),
        session_facts=session_state.patient_facts,
        current_topic=turn_frame.topic,
        session_turn_count=session_state.session_turn_count,
        projected_turn_scope=projected_turn_scope,
    )
    _publish_effective_scope(effective_scope)

    structured_capability = resolve_structured_answer_capability(turn_frame)
    if structured_capability is not None and structured_capability.kind == "clinic_contact":
        try:
            result = materialize_structured_contact_turn_response(
                client_id=client_id,
                turn_frame=turn_frame,
                contact_fields=structured_capability.contact_fields,
                allowed_topics=context.allowed_topics,
            )
        except Exception as exc:
            stage, code, value = emit_target_pipeline_failure_from_exception(exc)
            return TargetRuntimeTurnOutcome(
                widget=materialize_target_error_payload(
                    client_id=client_id,
                    sid=sid,
                    error_code=code,
                    pipeline_stage=stage,
                    pipeline_value=value,
                ),
                pipeline_result=None,
                turn_frame=turn_frame,
            )
        presentation_cadence = TargetPresentationCadenceState(
            shown_video_ids=frozenset(session_state.shown_video_ids),
            shown_content_followup_refs=frozenset(session_state.shown_content_followup_refs),
            shown_price_followup_refs=frozenset(session_state.shown_price_followup_refs),
            situation_offered=session_state.situation_offered,
        )
        widget = widget_payload_from_runtime_result(
            client_id=client_id,
            sid=sid,
            context=context,
            result=result,
            turn_frame=turn_frame,
            cadence=presentation_cadence,
            allow_situation=not turn_frame.needs_clarification,
        )
        if widget.kind == "materialized":
            selection = result.session_selection or TargetMaterializedSessionSelection((), (), ())
            followups = _followups_from_widget(widget)
            write_target_runtime_session_after_materialized(
                sid,
                turn_frame=turn_frame,
                verified=result.verified,
                prior=session_state,
                current_selection=selection,
                followups=followups,
                effective_scope=effective_scope,
                presentation_cadence_update=widget.presentation_cadence_update,
            )
        return TargetRuntimeTurnOutcome(
            widget=widget,
            pipeline_result=result,
            turn_frame=turn_frame,
        )

    try:
        boundary = execute_target_medical_boundary_classification(
            user_message,
            backend=boundary_backend,
            min_confidence_none=0.80,
            min_confidence_medical_handoff=0.70,
        )
        boundary = normalize_boundary_for_pipeline(boundary)
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

    catalog_strategy = resolve_target_runtime_strategy_context(
        context.bundle,
        service_id=turn_frame.service_id,
    )
    strategy_context = strategy_match_from_effective_scope(
        effective_scope,
        service_family=catalog_strategy.family,
    )

    ui_action_tokens = bind_pending_ui_actions_for_composer(
        scope_action=_current_ui_scope_action_from_request(),
        stage_action=_current_ui_stage_action_from_request(),
    )
    presentation_cadence = TargetPresentationCadenceState(
        shown_video_ids=frozenset(session_state.shown_video_ids),
        shown_content_followup_refs=frozenset(session_state.shown_content_followup_refs),
        shown_price_followup_refs=frozenset(session_state.shown_price_followup_refs),
        situation_offered=session_state.situation_offered,
    )
    provisional_spec = provisional_spec_from_turn_frame(
        turn_frame,
        allowed_topics=context.allowed_topics,
        tone_key="commercial_warm",
    )
    semantic_context = resolve_target_semantic_context(turn_frame, provisional_spec)
    marketing_scenarios = marketing_scenarios_from_turn_frame(turn_frame)
    allow_situation = not turn_frame.needs_clarification
    try:
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
                semantic_context=semantic_context,
                today=runtime_today(),
                md_root=context.md_root,
                cached_full_context=context.cached_full_context,
                include_initial_block=False,
                include_consultation_close=context.include_consultation_close,
                include_cta=context.cta_capability,
                user_message=user_message,
                tone=context.tone,
                composer_backend=composer_backend,
                semantic_backend=semantic_backend,
                marketing_scenarios=marketing_scenarios,
                shown_fact_ids=session_state.shown_fact_ids,
                shown_amplifier_refs=session_state.shown_amplifier_refs,
                shown_consultation_value_refs=session_state.shown_consultation_value_refs,
                effective_scope=effective_scope,
                client_id=client_id,
            )
        except TargetResponseVerificationError as exc:
            emit_target_pipeline_failure_from_exception(exc)
            return TargetRuntimeTurnOutcome(
                widget=materialize_target_error_payload(
                    client_id=client_id,
                    sid=sid,
                    error_code=exc.code,
                    pipeline_stage="verifier",
                    pipeline_value=exc.value,
                ),
                pipeline_result=None,
                turn_frame=turn_frame,
            )
        except Exception as exc:
            stage, code, value = emit_target_pipeline_failure_from_exception(exc)
            return TargetRuntimeTurnOutcome(
                widget=materialize_target_error_payload(
                    client_id=client_id,
                    sid=sid,
                    error_code=code,
                    pipeline_stage=stage,
                    pipeline_value=value,
                ),
                pipeline_result=None,
                turn_frame=turn_frame,
            )
    finally:
        reset_pending_ui_actions_for_composer(ui_action_tokens)

    widget = widget_payload_from_runtime_result(
        client_id=client_id,
        sid=sid,
        context=context,
        result=result,
        turn_frame=turn_frame,
        cadence=presentation_cadence,
        allow_situation=allow_situation,
    )

    presentation_update = None
    if widget.kind == "materialized":
        presentation_update = widget.presentation_cadence_update

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
            effective_scope=effective_scope,
            presentation_cadence_update=presentation_update,
        )

    return TargetRuntimeTurnOutcome(
        widget=widget,
        pipeline_result=result,
        turn_frame=turn_frame,
    )
