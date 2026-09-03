"""Top-level post-Composer selection orchestration."""

from __future__ import annotations

from datetime import date

from contracts.response_plan import SessionKey
from contracts.response_plan_composer import AdaptedComposerDecision
from contracts.response_plan_dialogue_context import (
    ShownOptionsFreshnessPolicy,
    ShownServiceOptionsSnapshot,
    require_non_negative_int,
)
from contracts.response_plan_post_composer import (
    PostComposerDiagnostic,
    PostComposerMaterialAuthority,
    PostComposerOwnershipError,
    PostComposerSelectionPlan,
    ResponseScopeKind,
    ResponseSituationState,
    SituationContinuityPolicy,
)
from core.response_plan_composer_authority import collect_allowed_topic_ids
from core.response_plan_dialogue_context import (
    snapshot_topic_allowed_for_decision,
    validate_shown_options_snapshot,
)
from core.response_plan_fact_projection import resolve_requested_fact_candidates
from core.response_plan_service_selection import (
    adapter_reference_rejection,
    resolve_service_selection,
)
from core.response_plan_situation_continuity import (
    merge_situation_continuity,
    post_composer_reference_resolution_rejected,
    resolve_reference_service_and_topic,
)


def _is_terminal_route(adapted: AdaptedComposerDecision) -> bool:
    route = adapted.decision.route
    mode = adapted.decision.mode
    if route == "ANSWER" and mode == "contacts":
        return True
    if route == "ADMIN" and mode in ("standard", "medical_terminal"):
        return True
    return False


def _is_clarify_route(adapted: AdaptedComposerDecision) -> bool:
    return adapted.decision.route == "CLARIFY" and adapted.decision.mode == "standard"


def _response_scope_for_resolution(
    *,
    reference_service_id: str | None,
    resolved_topic_id: str | None,
) -> ResponseScopeKind:
    if reference_service_id is not None:
        return "service"
    if resolved_topic_id is not None:
        return "topic"
    return "clinic"


def _empty_selection_plan(
    *,
    session_key: SessionKey,
    material: PostComposerMaterialAuthority,
    adapted: AdaptedComposerDecision,
    resolved_topic_id: str | None,
    response_scope: str,
    reference_service_id: str | None,
    effective_scope,
    situation_delta,
    diagnostics,
) -> PostComposerSelectionPlan:
    return PostComposerSelectionPlan(
        session_key=session_key,
        source_client_id=material.source_client_id,
        decision=adapted.decision,
        resolved_topic_id=resolved_topic_id,
        response_scope=response_scope,  # type: ignore[arg-type]
        reference_service_id=reference_service_id,
        reference_service_status="none"
        if reference_service_id is None
        else "unknown",
        effective_scope=effective_scope,
        ranked_service_ids=(),
        visible_service_option_ids=(),
        price_candidate_service_ids=(),
        comparison_service_ids=(),
        selection_basis="none",
        selection_intent="none",
        requested_fact_candidates=(),
        situation_delta=situation_delta,
        adapter_diagnostics=adapted.diagnostics,
        diagnostics=tuple(diagnostics),
    )


def resolve_post_composer_selection(
    *,
    session_key: SessionKey,
    adapted: AdaptedComposerDecision,
    material: PostComposerMaterialAuthority,
    active_session_service_id: str | None,
    prior_situation_state: ResponseSituationState | None,
    current_turn_index: int,
    policy: SituationContinuityPolicy,
    shown_options_policy: ShownOptionsFreshnessPolicy | None = None,
    as_of: date,
    shown_options_snapshot: ShownServiceOptionsSnapshot | None = None,
) -> PostComposerSelectionPlan:
    if session_key.client_id != material.source_client_id:
        raise PostComposerOwnershipError("post_composer_client_mismatch")

    require_non_negative_int("current_turn_index", current_turn_index)

    shown_policy = shown_options_policy or ShownOptionsFreshnessPolicy(
        max_age_turns=policy.max_age_turns
    )
    validated_shown, shown_diag = validate_shown_options_snapshot(
        shown_options_snapshot,
        session_key=session_key,
        source_client_id=material.source_client_id,
        current_turn_index=current_turn_index,
        policy=shown_policy,
        bundle=material.bundle,
    )

    allowed_topics = frozenset(collect_allowed_topic_ids(material))
    reference_rejected, _ = adapter_reference_rejection(adapted.diagnostics)

    ref_topic = resolve_reference_service_and_topic(
        adapted,
        material.bundle,
        active_session_service_id=active_session_service_id,
        allowed_topic_ids=allowed_topics,
    )
    reference_blocked = reference_rejected or post_composer_reference_resolution_rejected(
        ref_topic
    )

    resolved_topic_id = ref_topic.resolved_topic_id
    topic_diag: list = list(shown_diag)
    snapshot_selection_usable = validated_shown is not None
    if adapted.decision.option_reference_kind == "shown_options":
        resolved_topic_id, topic_from_snapshot_diag, snapshot_selection_usable = (
            snapshot_topic_allowed_for_decision(
                validated_shown,
                decision_topic_id=resolved_topic_id,
            )
        )
        topic_diag.extend(topic_from_snapshot_diag)
        if validated_shown is None and resolved_topic_id is None:
            topic_diag.append(
                PostComposerDiagnostic(code="shown_options_snapshot_unavailable")
            )

    response_scope = _response_scope_for_resolution(
        reference_service_id=ref_topic.reference_service_id,
        resolved_topic_id=resolved_topic_id,
    )

    selection_validated_shown = validated_shown if snapshot_selection_usable else None

    diagnostics = list(ref_topic.diagnostics)
    diagnostics.extend(topic_diag)

    situation = merge_situation_continuity(
        adapted,
        session_key=session_key,
        source_client_id=material.source_client_id,
        resolved_topic_id=resolved_topic_id,
        response_scope=response_scope,
        prior_state=prior_situation_state,
        current_turn_index=current_turn_index,
        policy=policy,
    )
    diagnostics.extend(situation.diagnostics)

    decision = adapted.decision

    if _is_terminal_route(adapted) or _is_clarify_route(adapted):
        return _empty_selection_plan(
            session_key=session_key,
            material=material,
            adapted=adapted,
            resolved_topic_id=resolved_topic_id,
            response_scope=response_scope,
            reference_service_id=ref_topic.reference_service_id,
            effective_scope=situation.effective_scope,
            situation_delta=situation.situation_delta,
            diagnostics=diagnostics,
        )

    service_selection = resolve_service_selection(
        material.bundle,
        effective_scope=situation.effective_scope,
        resolved_topic_id=resolved_topic_id,
        reference_service_id=ref_topic.reference_service_id,
        reference_rejected=reference_blocked,
        option_reference_kind=decision.option_reference_kind,
        validated_shown=selection_validated_shown,
        requested_aspect_ids=decision.requested_aspect_ids,
    )
    diagnostics.extend(service_selection.diagnostics)

    fact_candidates, fact_diagnostics = resolve_requested_fact_candidates(
        material.bundle,
        source_client_id=material.source_client_id,
        requested_fact_ids=decision.requested_fact_ids,
        response_scope=response_scope,
        resolved_topic_id=resolved_topic_id,
        reference_service_id=ref_topic.reference_service_id,
        effective_scope=situation.effective_scope,
        as_of=as_of,
    )
    diagnostics.extend(fact_diagnostics)

    return PostComposerSelectionPlan(
        session_key=session_key,
        source_client_id=material.source_client_id,
        decision=decision,
        resolved_topic_id=resolved_topic_id,
        response_scope=response_scope,
        reference_service_id=ref_topic.reference_service_id,
        reference_service_status=service_selection.reference_service_status,
        effective_scope=situation.effective_scope,
        ranked_service_ids=service_selection.ranked_service_ids,
        visible_service_option_ids=service_selection.visible_service_option_ids,
        price_candidate_service_ids=service_selection.price_candidate_service_ids,
        comparison_service_ids=service_selection.comparison_service_ids,
        selection_basis=service_selection.selection_basis,
        selection_intent=service_selection.selection_intent,
        requested_fact_candidates=fact_candidates,
        situation_delta=situation.situation_delta,
        adapter_diagnostics=adapted.diagnostics,
        diagnostics=tuple(diagnostics),
    )
