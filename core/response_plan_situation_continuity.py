"""Pure situation continuity merge for post-Composer selection."""

from __future__ import annotations

from dataclasses import dataclass

from contracts.effective_scope import EffectiveScope, ScopeAxisProvenance
from contracts.response_plan import SessionKey
from contracts.response_plan_composer import (
    AdaptedComposerDecision,
    ComposerPatientSituation,
    SituationExtent,
    SituationJaw,
    SituationModifier,
    SituationStage,
)
from contracts.response_plan_post_composer import (
    PostComposerDiagnostic,
    PostComposerSituationError,
    ResponseSituationDelta,
    ResponseSituationState,
    ResponseScopeKind,
    SituationContinuityPolicy,
)
from contracts.response_schema import ResponseSchemaBundle
from contracts.target_service_content_topic import parse_service_catalog_content_topic


@dataclass(frozen=True, slots=True)
class ReferenceTopicResolution:
    reference_service_id: str | None
    resolved_topic_id: str | None
    response_scope: ResponseScopeKind
    diagnostics: tuple[PostComposerDiagnostic, ...]
    active_session_reference_rejected: bool = False


def post_composer_reference_resolution_rejected(ref_topic: ReferenceTopicResolution) -> bool:
    return ref_topic.active_session_reference_rejected


@dataclass(frozen=True, slots=True)
class SituationMergeResult:
    effective_scope: EffectiveScope
    situation_delta: ResponseSituationDelta
    merged_state: ResponseSituationState | None
    diagnostics: tuple[PostComposerDiagnostic, ...]


def _is_terminal_route(decision: AdaptedComposerDecision) -> bool:
    route = decision.decision.route
    mode = decision.decision.mode
    if route == "ANSWER" and mode == "contacts":
        return True
    if route == "ADMIN" and mode in ("standard", "medical_terminal"):
        return True
    return False


def _axis_known_extent(extent: SituationExtent) -> bool:
    return extent != "unknown"


def _axis_known_jaw(jaw: SituationJaw) -> bool:
    return jaw != "unknown"


def _axis_known_stage(stage: SituationStage) -> bool:
    return stage != "unknown"


def _has_known_situation_axes(situation: ComposerPatientSituation) -> bool:
    return (
        _axis_known_extent(situation.extent)
        or _axis_known_jaw(situation.jaw)
        or _axis_known_stage(situation.stage)
        or bool(situation.modifiers)
    )


def _reported_context_from_modifiers(
    modifiers: tuple[SituationModifier, ...],
) -> str | None:
    if "reported_bone_deficit" in modifiers:
        return "reported_bone_deficit"
    return None


def _validate_prior_state(
    *,
    session_key: SessionKey,
    source_client_id: str,
    prior_state: ResponseSituationState | None,
) -> None:
    if prior_state is None:
        return
    if prior_state.session_key != session_key:
        raise PostComposerSituationError("situation_session_key_mismatch")
    if prior_state.session_key.client_id != source_client_id:
        raise PostComposerSituationError("situation_client_mismatch")


def resolve_reference_service_and_topic(
    adapted: AdaptedComposerDecision,
    bundle: ResponseSchemaBundle,
    *,
    active_session_service_id: str | None,
    allowed_topic_ids: frozenset[str],
) -> ReferenceTopicResolution:
    decision = adapted.decision
    diagnostics: list[PostComposerDiagnostic] = []

    reference_service_id: str | None = None
    active_session_reference_rejected = False
    if decision.service_reference_kind == "explicit_current":
        reference_service_id = decision.explicit_service_id
    elif decision.service_reference_kind == "active_session":
        reference_service_id = active_session_service_id
        if reference_service_id is None:
            active_session_reference_rejected = True
            diagnostics.append(
                PostComposerDiagnostic(
                    code="post_composer_active_service_unavailable",
                )
            )

    service_topic: str | None = None
    if reference_service_id is not None:
        service = bundle.services.get(reference_service_id)
        if service is None or not service.active:
            diagnostics.append(
                PostComposerDiagnostic(
                    code="post_composer_active_service_unavailable",
                    detail=reference_service_id,
                )
            )
        else:
            service_topic = parse_service_catalog_content_topic(service.content_ref)

    decision_topic = decision.topic_id
    if decision_topic is not None and decision_topic not in allowed_topic_ids:
        diagnostics.append(
            PostComposerDiagnostic(
                code="post_composer_topic_unavailable",
                detail=decision_topic,
            )
        )
        decision_topic = None

    resolved_topic_id: str | None = None
    if decision_topic is not None:
        resolved_topic_id = decision_topic
    elif service_topic is not None:
        resolved_topic_id = service_topic

    if (
        decision_topic is not None
        and service_topic is not None
        and decision_topic != service_topic
    ):
        diagnostics.append(
            PostComposerDiagnostic(
                code="post_composer_topic_unavailable",
                detail={
                    "decision_topic": decision_topic,
                    "service_topic": service_topic,
                },
            )
        )
        resolved_topic_id = service_topic

    if reference_service_id is not None and resolved_topic_id is not None:
        response_scope: ResponseScopeKind = "service"
    elif resolved_topic_id is not None:
        response_scope = "topic"
    else:
        response_scope = "clinic"

    return ReferenceTopicResolution(
        reference_service_id=reference_service_id,
        resolved_topic_id=resolved_topic_id,
        response_scope=response_scope,
        diagnostics=tuple(diagnostics),
        active_session_reference_rejected=active_session_reference_rejected,
    )


def _session_eligible(
    *,
    prior_state: ResponseSituationState | None,
    resolved_topic_id: str | None,
    current_turn_index: int,
    policy: SituationContinuityPolicy,
) -> tuple[bool, PostComposerDiagnostic | None]:
    if prior_state is None:
        return False, None
    if resolved_topic_id is None:
        return False, None
    if prior_state.topic_id != resolved_topic_id:
        return False, PostComposerDiagnostic(
            code="situation_session_topic_changed",
            detail=prior_state.topic_id,
        )
    age = current_turn_index - prior_state.set_at_turn
    if age < 0:
        raise PostComposerSituationError("situation_turn_index_negative")
    if age > policy.max_age_turns:
        return False, PostComposerDiagnostic(code="situation_session_stale")
    return True, None


def _merge_axis_extent(
    current: SituationExtent,
    session: SituationExtent,
) -> tuple[SituationExtent, str]:
    if _axis_known_extent(current):
        return current, "composer_decision"
    if session != "unknown":
        return session, "session"
    return "unknown", "unknown"


def _merge_axis_jaw(current: SituationJaw, session: SituationJaw) -> tuple[SituationJaw, str]:
    if _axis_known_jaw(current):
        return current, "composer_decision"
    if session != "unknown":
        return session, "session"
    return "unknown", "unknown"


def _merge_axis_stage(
    current: SituationStage,
    session: SituationStage,
) -> tuple[SituationStage, str]:
    if _axis_known_stage(current):
        return current, "composer_decision"
    if session != "unknown":
        return session, "session"
    return "unknown", "unknown"


def merge_situation_continuity(
    adapted: AdaptedComposerDecision,
    *,
    session_key: SessionKey,
    source_client_id: str,
    resolved_topic_id: str | None,
    response_scope: ResponseScopeKind,
    prior_state: ResponseSituationState | None,
    current_turn_index: int,
    policy: SituationContinuityPolicy,
) -> SituationMergeResult:
    _validate_prior_state(
        session_key=session_key,
        source_client_id=source_client_id,
        prior_state=prior_state,
    )
    if current_turn_index < 0:
        raise PostComposerSituationError("situation_turn_index_negative")

    current = adapted.decision.patient_situation
    diagnostics: list[PostComposerDiagnostic] = []

    session_eligible, stale_diag = _session_eligible(
        prior_state=prior_state,
        resolved_topic_id=resolved_topic_id,
        current_turn_index=current_turn_index,
        policy=policy,
    )
    if stale_diag is not None:
        diagnostics.append(stale_diag)

    session_state = prior_state if session_eligible else None

    if response_scope == "clinic" and resolved_topic_id is None:
        session_state = None

    session_extent: SituationExtent = (
        session_state.extent if session_state is not None else "unknown"
    )
    session_jaw: SituationJaw = session_state.jaw if session_state is not None else "unknown"
    session_stage: SituationStage = (
        session_state.stage if session_state is not None else "unknown"
    )
    session_modifiers: tuple[SituationModifier, ...] = (
        session_state.modifiers if session_state is not None else ()
    )

    merged_extent, extent_source = _merge_axis_extent(current.extent, session_extent)
    merged_jaw, jaw_source = _merge_axis_jaw(current.jaw, session_jaw)
    merged_stage, stage_source = _merge_axis_stage(current.stage, session_stage)
    merged_modifiers = current.modifiers if current.modifiers else session_modifiers

    reported_context = _reported_context_from_modifiers(merged_modifiers)

    effective_scope = EffectiveScope(
        extent=merged_extent if merged_extent != "unknown" else "unknown",
        jaw=merged_jaw if merged_jaw != "unknown" else "unknown",
        stage=merged_stage if merged_stage != "unknown" else None,
        reported_context=reported_context,  # type: ignore[arg-type]
        topic=resolved_topic_id,
        source="composer_decision" if _has_known_situation_axes(current) else "session"
        if session_state is not None
        else "unknown",
        provenance="post_composer",
        extent_axis=ScopeAxisProvenance(source=extent_source, provenance="post_composer"),  # type: ignore[arg-type]
        jaw_axis=ScopeAxisProvenance(source=jaw_source, provenance="post_composer"),  # type: ignore[arg-type]
        stage_axis=ScopeAxisProvenance(source=stage_source, provenance="post_composer"),  # type: ignore[arg-type]
        reported_context_axis=ScopeAxisProvenance(
            source="composer_decision" if current.modifiers else "session"
            if session_state is not None and session_modifiers
            else "unknown",
            provenance="post_composer",
        ),
    )

    current_has_known = _has_known_situation_axes(current)
    topic_changed = (
        prior_state is not None
        and resolved_topic_id is not None
        and prior_state.topic_id != resolved_topic_id
    )

    merged_state: ResponseSituationState | None = None
    if resolved_topic_id is not None and (
        current_has_known
        or session_state is not None
        or merged_extent != "unknown"
        or merged_jaw != "unknown"
        or merged_stage != "unknown"
        or merged_modifiers
    ):
        set_at_turn = (
            current_turn_index
            if current_has_known
            else prior_state.set_at_turn
            if prior_state is not None and session_eligible
            else current_turn_index
        )
        merged_state = ResponseSituationState(
            session_key=session_key,
            topic_id=resolved_topic_id,
            extent=merged_extent,
            jaw=merged_jaw,
            stage=merged_stage,
            modifiers=merged_modifiers,
            set_at_turn=set_at_turn,
        )

    if _is_terminal_route(adapted):
        if current_has_known and merged_state is not None:
            situation_delta = ResponseSituationDelta(action="upsert", state=merged_state)
        else:
            situation_delta = ResponseSituationDelta(action="keep")
        return SituationMergeResult(
            effective_scope=effective_scope,
            situation_delta=situation_delta,
            merged_state=merged_state,
            diagnostics=tuple(diagnostics),
        )

    if topic_changed and not current_has_known:
        situation_delta = ResponseSituationDelta(action="clear")
    elif current_has_known and merged_state is not None:
        situation_delta = ResponseSituationDelta(action="upsert", state=merged_state)
    elif (
        prior_state is not None
        and session_eligible
        and merged_state is not None
        and merged_state == prior_state
    ):
        situation_delta = ResponseSituationDelta(action="keep")
    elif current_has_known and merged_state is not None:
        situation_delta = ResponseSituationDelta(action="upsert", state=merged_state)
    else:
        situation_delta = ResponseSituationDelta(action="keep")

    return SituationMergeResult(
        effective_scope=effective_scope,
        situation_delta=situation_delta,
        merged_state=merged_state,
        diagnostics=tuple(diagnostics),
    )
