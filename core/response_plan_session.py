"""Read/prepare/commit bridge for typed response-plan session continuity."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from contracts.response_plan import FinalizedCommercialIds, ResolvedResponsePlan, ResponseUIProjection, SessionKey
from contracts.response_plan_composer import ComposerDecision
from contracts.response_plan_composer_input import (
    MAX_COMPOSER_HISTORY_TURNS,
    ComposerConfirmedShownOptions,
    ComposerDialogueTurn,
    ComposerSessionContext,
)
from contracts.response_plan_dialogue_context import ShownOptionsFreshnessPolicy
from contracts.response_plan_post_composer import (
    PostComposerSelectionPlan,
    ResponseSituationDelta,
    ResponseSituationState,
    SituationContinuityPolicy,
)
from contracts.response_schema import ResponseSchemaBundle
from contracts.response_plan_session import (
    HistoricalPriceOffersSnapshot,
    PersistedActiveService,
    PersistedActiveTopic,
    PersistedShownCommercialIds,
    PersistedShownOptionsSnapshot,
    PersistedSituationState,
    PreparedSessionUpdate,
    ResponsePlanSessionContractError,
    ResponsePlanSessionOwnershipError,
    ResponsePlanSessionReceiptMismatch,
    ResponsePlanSessionSnapshot,
    ResponsePlanSessionState,
    SessionCommitResult,
    SessionCompletionReceipt,
    SessionContinuityPolicy,
    SessionDialoguePair,
    SessionSnapshotIdentity,
    TurnPipelineOutcome,
    TurnRequestBinding,
    attach_update_fingerprint,
    compute_update_fingerprint,
)
from core.response_plan_dialogue_context import (
    ValidatedShownOptionsSnapshot,
    build_price_offer_shown_snapshot,
    snapshot_topic_allowed_for_decision,
    validate_shown_options_snapshot,
)
from core.response_text_renderer import render_response_text
from core.response_ui_projection import project_response_ui

if TYPE_CHECKING:
    from core.response_plan_session_store import ResponsePlanSessionStore

_TERMINAL_ROUTES = frozenset({"ADMIN", "CONTACTS"})


@dataclass(frozen=True, slots=True)
class SessionFreshnessDiagnostic:
    lane: str
    detail: object = None


@dataclass(frozen=True, slots=True)
class TurnReadBundle:
    recent_dialogue: tuple[ComposerDialogueTurn, ...]
    composer_session_context: ComposerSessionContext
    confirmed_shown_options: ComposerConfirmedShownOptions | None
    validated_shown_options: ValidatedShownOptionsSnapshot | None
    active_session_service_id: str | None
    prior_situation_state: ResponseSituationState | None
    accumulated_shown_ids: PersistedShownCommercialIds
    history_turn_count: int
    freshness_diagnostics: tuple[SessionFreshnessDiagnostic, ...]


def serialize_prior_patient_situation(state: ResponseSituationState) -> str:
    payload = {
        "topic_id": state.topic_id,
        "extent": state.extent,
        "jaw": state.jaw,
        "stage": state.stage,
        "modifiers": list(state.modifiers),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _age(current_turn_index: int, set_at_turn: int) -> int:
    if set_at_turn > current_turn_index:
        raise ResponsePlanSessionContractError("future_set_at_turn")
    return current_turn_index - set_at_turn


def _is_stale(*, current_turn_index: int, set_at_turn: int, max_age_turns: int) -> bool:
    return _age(current_turn_index, set_at_turn) > max_age_turns


def _dialogue_messages_from_pairs(
    pairs: tuple[SessionDialoguePair, ...],
) -> tuple[ComposerDialogueTurn, ...]:
    turns: list[ComposerDialogueTurn] = []
    for pair in pairs:
        turns.append(ComposerDialogueTurn(role="patient", text=pair.patient_text))
        turns.append(ComposerDialogueTurn(role="assistant", text=pair.assistant_text))
    if len(turns) > MAX_COMPOSER_HISTORY_TURNS:
        turns = turns[-MAX_COMPOSER_HISTORY_TURNS:]
    return tuple(turns)


def _trim_pairs(
    pairs: tuple[SessionDialoguePair, ...],
    *,
    history_pair_limit: int,
) -> tuple[SessionDialoguePair, ...]:
    if len(pairs) <= history_pair_limit:
        return pairs
    return pairs[-history_pair_limit:]


def _situation_lane(
    snapshot: ResponsePlanSessionSnapshot,
    policy: SessionContinuityPolicy,
) -> tuple[ResponseSituationState | None, str, str, str | None, tuple[SessionFreshnessDiagnostic, ...]]:
    current_turn_index = snapshot.current_turn_index
    diagnostics: list[SessionFreshnessDiagnostic] = []
    state = snapshot.state.situation_state
    if state is None:
        return None, "none", "absent", None, ()
    runtime = state.to_runtime()
    if _is_stale(
        current_turn_index=current_turn_index,
        set_at_turn=state.set_at_turn,
        max_age_turns=policy.situation_max_age_turns,
    ):
        diagnostics.append(SessionFreshnessDiagnostic("situation", "stale"))
        return None, "none", "absent", None, tuple(diagnostics)
    return runtime, "session_active", "current", serialize_prior_patient_situation(runtime), ()


def _active_service_lane(
    snapshot: ResponsePlanSessionSnapshot,
    policy: SessionContinuityPolicy,
) -> tuple[str | None, str | None, str, str, tuple[SessionFreshnessDiagnostic, ...]]:
    current_turn_index = snapshot.current_turn_index
    diagnostics: list[SessionFreshnessDiagnostic] = []
    active = snapshot.state.active_service
    if active is None:
        return None, None, "none", "absent", ()
    if _is_stale(
        current_turn_index=current_turn_index,
        set_at_turn=active.set_at_turn,
        max_age_turns=policy.active_service_max_age_turns,
    ):
        diagnostics.append(SessionFreshnessDiagnostic("active_service", active.service_id))
        return None, None, "none", "absent", tuple(diagnostics)
    provenance = "patient_explicit" if active.provenance == "explicit_current" else "session_active"
    return active.service_id, active.service_id, provenance, "current", tuple(diagnostics)


def _active_topic_lane(
    snapshot: ResponsePlanSessionSnapshot,
    policy: SessionContinuityPolicy,
) -> tuple[str | None, str, str, tuple[SessionFreshnessDiagnostic, ...]]:
    current_turn_index = snapshot.current_turn_index
    diagnostics: list[SessionFreshnessDiagnostic] = []
    topic = snapshot.state.active_topic
    if topic is None:
        return None, "none", "absent", ()
    if _is_stale(
        current_turn_index=current_turn_index,
        set_at_turn=topic.set_at_turn,
        max_age_turns=policy.active_topic_max_age_turns,
    ):
        diagnostics.append(SessionFreshnessDiagnostic("active_topic", topic.topic_id))
        return None, "none", "absent", tuple(diagnostics)
    provenance = (
        "patient_explicit"
        if topic.provenance in {"explicit_current", "explicit_topic"}
        else "session_active"
    )
    return topic.topic_id, provenance, "current", tuple(diagnostics)


def _confirmed_shown_options(
    snapshot: ResponsePlanSessionSnapshot,
    policy: SessionContinuityPolicy,
    *,
    source_client_id: str,
    bundle: ResponseSchemaBundle,
) -> tuple[
    ComposerConfirmedShownOptions | None,
    ValidatedShownOptionsSnapshot | None,
    tuple[SessionFreshnessDiagnostic, ...],
]:
    shown = snapshot.state.shown_options_snapshot
    if shown is None:
        return None, None, ()
    validated, diagnostics = validate_shown_options_snapshot(
        shown.to_runtime(),
        session_key=snapshot.state.session_key,
        source_client_id=source_client_id,
        current_turn_index=snapshot.current_turn_index,
        policy=shown_options_freshness_policy(policy),
        bundle=bundle,
    )
    freshness_diag: list[SessionFreshnessDiagnostic] = []
    for diagnostic in diagnostics:
        if diagnostic.code == "shown_options_snapshot_stale":
            freshness_diag.append(SessionFreshnessDiagnostic("shown_options", shown.topic_id))
    if validated is None:
        return None, None, tuple(freshness_diag)
    return (
        ComposerConfirmedShownOptions(
            snapshot=shown.to_runtime(),
            freshness_policy=ShownOptionsFreshnessPolicy(
                max_age_turns=policy.shown_options_max_age_turns
            ),
            current_turn_index=snapshot.current_turn_index,
        ),
        validated,
        tuple(freshness_diag),
    )


def resolve_topic_restoration_shown_snapshot(
    prior: ResponsePlanSessionState,
    *,
    validated_shown: ValidatedShownOptionsSnapshot | None,
    selection: PostComposerSelectionPlan,
) -> PersistedShownOptionsSnapshot | None:
    if prior.active_topic is not None:
        return None
    if selection.decision.option_reference_kind != "shown_options":
        return None
    if validated_shown is None:
        return None
    resolved_topic_id, _, snapshot_usable = snapshot_topic_allowed_for_decision(
        validated_shown,
        decision_topic_id=selection.resolved_topic_id,
    )
    if not snapshot_usable:
        return None
    if resolved_topic_id is None:
        return None
    if validated_shown.snapshot.topic_id != resolved_topic_id:
        return None
    return PersistedShownOptionsSnapshot.from_runtime(validated_shown.snapshot)


def resolve_topic_restoration_shown_snapshot_for_state(
    prior: ResponsePlanSessionState,
    *,
    policy: SessionContinuityPolicy,
    source_client_id: str,
    bundle: ResponseSchemaBundle,
    current_turn_index: int,
    selection: PostComposerSelectionPlan,
) -> PersistedShownOptionsSnapshot | None:
    shown = prior.shown_options_snapshot
    if shown is None:
        return None
    validated, _ = validate_shown_options_snapshot(
        shown.to_runtime(),
        session_key=prior.session_key,
        source_client_id=source_client_id,
        current_turn_index=current_turn_index,
        policy=shown_options_freshness_policy(policy),
        bundle=bundle,
    )
    return resolve_topic_restoration_shown_snapshot(
        prior,
        validated_shown=validated,
        selection=selection,
    )


def build_turn_read_bundle(
    snapshot: ResponsePlanSessionSnapshot,
    *,
    policy: SessionContinuityPolicy,
    source_client_id: str,
    bundle: ResponseSchemaBundle,
) -> TurnReadBundle:
    if snapshot.state.session_key.client_id != source_client_id:
        raise ResponsePlanSessionContractError("read_bundle_client_mismatch")

    recent_dialogue = _dialogue_messages_from_pairs(snapshot.state.dialogue_pairs)
    prior_state, situation_provenance, situation_freshness, prior_text, situation_diag = (
        _situation_lane(snapshot, policy)
    )
    (
        authority_service_id,
        model_service_id,
        service_provenance,
        service_freshness,
        service_diag,
    ) = _active_service_lane(snapshot, policy)
    topic_id, topic_provenance, topic_freshness, topic_diag = _active_topic_lane(snapshot, policy)
    confirmed, validated_shown, shown_diag = _confirmed_shown_options(
        snapshot,
        policy,
        source_client_id=source_client_id,
        bundle=bundle,
    )

    session_context = ComposerSessionContext(
        session_key=snapshot.state.session_key,
        source_client_id=source_client_id,
        active_service_id=model_service_id,
        active_service_provenance=service_provenance,  # type: ignore[arg-type]
        active_service_freshness=service_freshness,  # type: ignore[arg-type]
        active_topic_id=topic_id,
        active_topic_provenance=topic_provenance,  # type: ignore[arg-type]
        active_topic_freshness=topic_freshness,  # type: ignore[arg-type]
        prior_patient_situation=prior_text,
        situation_provenance=situation_provenance,  # type: ignore[arg-type]
        situation_freshness=situation_freshness,  # type: ignore[arg-type]
    )
    diagnostics = situation_diag + service_diag + topic_diag + shown_diag
    return TurnReadBundle(
        recent_dialogue=recent_dialogue,
        composer_session_context=session_context,
        confirmed_shown_options=confirmed,
        validated_shown_options=validated_shown,
        active_session_service_id=authority_service_id,
        prior_situation_state=prior_state,
        accumulated_shown_ids=snapshot.state.accumulated_shown_ids,
        history_turn_count=len(recent_dialogue),
        freshness_diagnostics=diagnostics,
    )


def create_turn_request_binding(
    snapshot: ResponsePlanSessionSnapshot,
    *,
    request_id: str,
    patient_message: str,
) -> TurnRequestBinding:
    return TurnRequestBinding(
        session_key=snapshot.state.session_key,
        request_id=request_id,
        expected_revision=snapshot.state.revision,
        current_turn_index=snapshot.current_turn_index,
        patient_message=patient_message,
        snapshot_identity=SessionSnapshotIdentity.from_snapshot(snapshot),
    )


def _merge_id_tuple(left: tuple[str, ...], right: tuple[str, ...]) -> tuple[str, ...]:
    seen = set(left)
    merged = list(left)
    for item in right:
        if item not in seen:
            merged.append(item)
            seen.add(item)
    return tuple(merged)


def _merge_accumulated_shown_ids(
    prior: PersistedShownCommercialIds,
    finalized: FinalizedCommercialIds,
) -> PersistedShownCommercialIds:
    return PersistedShownCommercialIds(
        requested_fact_ids=_merge_id_tuple(prior.requested_fact_ids, finalized.requested_fact_ids),
        promo_fact_ids=_merge_id_tuple(prior.promo_fact_ids, finalized.promo_fact_ids),
        amplifier_fact_ids=_merge_id_tuple(
            prior.amplifier_fact_ids, finalized.amplifier_fact_ids
        ),
        service_value_ids=_merge_id_tuple(prior.service_value_ids, finalized.service_value_ids),
        price_offer_ids=_merge_id_tuple(prior.price_offer_ids, finalized.price_offer_ids),
        required_offer_condition_ids=_merge_id_tuple(
            prior.required_offer_condition_ids, finalized.required_offer_condition_ids
        ),
        shown_service_option_ids=_merge_id_tuple(
            prior.shown_service_option_ids, finalized.shown_service_option_ids
        ),
    )


def _topic_compatible(
    *,
    prior_topic: str | None,
    resolved_topic: str | None,
) -> bool:
    if prior_topic is None:
        return True
    if resolved_topic is None:
        return False
    return prior_topic == resolved_topic


def _compute_active_service(
    prior: PersistedActiveService | None,
    *,
    session_delta_service_id: str | None,
    decision: ComposerDecision,
    current_turn_index: int,
) -> PersistedActiveService | None:
    if session_delta_service_id is None:
        return None
    if decision.service_reference_kind == "explicit_current":
        if decision.explicit_service_id == session_delta_service_id:
            return PersistedActiveService(
                service_id=session_delta_service_id,
                provenance="explicit_current",
                set_at_turn=current_turn_index,
            )
        return None
    if decision.service_reference_kind == "active_session":
        if prior is not None and prior.service_id == session_delta_service_id:
            return PersistedActiveService(
                service_id=session_delta_service_id,
                provenance="active_session",
                set_at_turn=prior.set_at_turn,
            )
        return None
    if prior is not None and prior.service_id == session_delta_service_id:
        return prior
    return None


def _compute_active_topic(
    prior: PersistedActiveTopic | None,
    *,
    session_delta_topic_id: str | None,
    decision: ComposerDecision,
    resolved_topic_id: str | None,
    active_service: PersistedActiveService | None,
    current_turn_index: int,
    confirmed_shown_options_snapshot: PersistedShownOptionsSnapshot | None = None,
) -> PersistedActiveTopic | None:
    topic_id = session_delta_topic_id
    if topic_id is None:
        return None
    if decision.service_reference_kind == "explicit_current" and active_service is not None:
        if (
            active_service.provenance == "explicit_current"
            and active_service.set_at_turn == current_turn_index
        ):
            return PersistedActiveTopic(
                topic_id=topic_id,
                provenance="explicit_current",
                set_at_turn=current_turn_index,
            )
    if (
        decision.topic_id is not None
        and resolved_topic_id is not None
        and decision.topic_id == resolved_topic_id
    ):
        return PersistedActiveTopic(
            topic_id=topic_id,
            provenance="explicit_topic",
            set_at_turn=current_turn_index,
        )
    if (
        prior is None
        and decision.option_reference_kind == "shown_options"
        and confirmed_shown_options_snapshot is not None
        and confirmed_shown_options_snapshot.topic_id == topic_id
        and resolved_topic_id == topic_id
    ):
        return PersistedActiveTopic(
            topic_id=topic_id,
            provenance="shown_options",
            set_at_turn=confirmed_shown_options_snapshot.shown_at_turn,
        )
    if prior is not None and prior.topic_id == topic_id:
        return prior
    return None


def _situation_from_delta(
    prior: PersistedSituationState | None,
    *,
    selection: PostComposerSelectionPlan,
) -> PersistedSituationState | None:
    delta = selection.situation_delta
    if delta.action == "keep":
        return prior
    if delta.action == "clear":
        return None
    if delta.state is None:
        raise ResponsePlanSessionContractError("situation_upsert_missing_state")
    return PersistedSituationState.from_runtime(delta.state)


def _shown_options_from_resolved(
    prior: PersistedShownOptionsSnapshot | None,
    *,
    resolved: ResolvedResponsePlan,
    selection: PostComposerSelectionPlan,
    session_key: SessionKey,
    current_turn_index: int,
) -> PersistedShownOptionsSnapshot | None:
    route = selection.decision.route
    if route in _TERMINAL_ROUTES:
        return None
    if resolved.authored_service_alternative_block is not None and resolved.authored_service_alternative_block.options:
        block = resolved.authored_service_alternative_block
        service_ids = tuple(item.service_id for item in block.options)
        topic_id = block.options_unambiguous_topic_id
        if topic_id is None:
            return None
        return PersistedShownOptionsSnapshot(
            session_key=session_key,
            topic_id=topic_id,
            service_ids=service_ids,
            shown_at_turn=current_turn_index,
            provenance="finalized_plan_service_options",
        )
    if resolved.service_options_block is not None:
        service_ids = tuple(item.service_id for item in resolved.service_options_block.options)
        topic_id = selection.resolved_topic_id
        if topic_id is None:
            return None
        return PersistedShownOptionsSnapshot(
            session_key=session_key,
            topic_id=topic_id,
            service_ids=service_ids,
            shown_at_turn=current_turn_index,
            provenance="finalized_plan_service_options",
        )
    if resolved.price_block is not None and resolved.price_block.offer_rows:
        topic_id = selection.resolved_topic_id
        if topic_id is None:
            return prior
        runtime = build_price_offer_shown_snapshot(
            session_key,
            topic_id=topic_id,
            rows=resolved.price_block.offer_rows,
            shown_at_turn=current_turn_index,
        )
        return PersistedShownOptionsSnapshot.from_runtime(runtime)
    if prior is not None and not _topic_compatible(
        prior_topic=prior.topic_id,
        resolved_topic=selection.resolved_topic_id,
    ):
        return None
    return prior


def _historical_price_from_resolved(
    prior: HistoricalPriceOffersSnapshot | None,
    *,
    resolved: ResolvedResponsePlan,
    selection: PostComposerSelectionPlan,
    current_turn_index: int,
) -> HistoricalPriceOffersSnapshot | None:
    if resolved.price_block is None or not resolved.price_block.offer_rows:
        return prior
    return HistoricalPriceOffersSnapshot(
        rows=resolved.price_block.offer_rows,
        shown_at_turn=current_turn_index,
        topic_id=selection.resolved_topic_id,
    )


def apply_session_state_transition(
    prior: ResponsePlanSessionState,
    *,
    policy: SessionContinuityPolicy,
    binding: TurnRequestBinding,
    rendered_text: str,
    selection: PostComposerSelectionPlan,
    resolved: ResolvedResponsePlan,
    topic_restoration_shown_snapshot: PersistedShownOptionsSnapshot | None = None,
) -> ResponsePlanSessionState:
    if prior.session_key != binding.session_key:
        raise ResponsePlanSessionContractError("transition_session_key_mismatch")
    if binding.snapshot_identity.session_key != prior.session_key:
        raise ResponsePlanSessionContractError("transition_snapshot_identity_mismatch")
    if binding.snapshot_identity.revision != prior.revision:
        raise ResponsePlanSessionContractError("transition_snapshot_revision_mismatch")
    if binding.current_turn_index != prior.last_committed_turn_index + 1:
        raise ResponsePlanSessionContractError("transition_turn_index_mismatch")

    current_turn_index = binding.current_turn_index
    active_service = _compute_active_service(
        prior.active_service,
        session_delta_service_id=resolved.session_delta.active_service_id,
        decision=selection.decision,
        current_turn_index=current_turn_index,
    )
    active_topic = _compute_active_topic(
        prior.active_topic,
        session_delta_topic_id=resolved.session_delta.active_topic_id,
        decision=selection.decision,
        resolved_topic_id=selection.resolved_topic_id,
        active_service=active_service,
        current_turn_index=current_turn_index,
        confirmed_shown_options_snapshot=topic_restoration_shown_snapshot,
    )
    situation = _situation_from_delta(prior.situation_state, selection=selection)
    shown_options = _shown_options_from_resolved(
        prior.shown_options_snapshot,
        resolved=resolved,
        selection=selection,
        session_key=binding.session_key,
        current_turn_index=current_turn_index,
    )
    historical_price = _historical_price_from_resolved(
        prior.historical_price_offers,
        resolved=resolved,
        selection=selection,
        current_turn_index=current_turn_index,
    )
    accumulated = _merge_accumulated_shown_ids(
        prior.accumulated_shown_ids,
        resolved.finalized_commercial_ids,
    )
    new_pairs = _trim_pairs(
        (
            *prior.dialogue_pairs,
            SessionDialoguePair(
                patient_text=binding.patient_message,
                assistant_text=rendered_text,
                committed_at_turn=current_turn_index,
            ),
        ),
        history_pair_limit=policy.history_pair_limit,
    )
    return ResponsePlanSessionState(
        schema_version=prior.schema_version,
        session_key=prior.session_key,
        revision=prior.revision + 1,
        last_committed_turn_index=current_turn_index,
        dialogue_pairs=new_pairs,
        active_service=active_service,
        active_topic=active_topic,
        situation_state=situation,
        shown_options_snapshot=shown_options,
        historical_price_offers=historical_price,
        accumulated_shown_ids=accumulated,
        terminal_state=resolved.session_delta.terminal_state,
        clarify_pending=resolved.session_delta.clarify_pending,
    )


def validate_prepared_response_coherence(
    *,
    selection: PostComposerSelectionPlan,
    resolved: ResolvedResponsePlan,
    rendered_text: str,
    ui_projection: ResponseUIProjection,
    situation_delta: ResponseSituationDelta,
) -> None:
    """Pure selection ↔ frozen-response checks before delivery or commit."""
    decision = selection.decision
    if decision.route != resolved.route:
        raise ResponsePlanSessionContractError("prepared_route_mismatch")
    if decision.mode != resolved.mode:
        raise ResponsePlanSessionContractError("prepared_mode_mismatch")
    if decision.patient_text != resolved.patient_text:
        raise ResponsePlanSessionContractError("prepared_patient_text_mismatch")
    if selection.response_scope != resolved.response_scope:
        raise ResponsePlanSessionContractError("prepared_response_scope_mismatch")
    if situation_delta != selection.situation_delta:
        raise ResponsePlanSessionContractError("prepared_situation_delta_mismatch")
    if selection.reference_service_id is not None and resolved.response_scope == "service":
        if resolved.session_delta.active_service_id != selection.reference_service_id:
            raise ResponsePlanSessionContractError("prepared_reference_service_mismatch")
    if resolved.price_block is not None and resolved.price_block.offer_rows:
        allowed_services = set(selection.price_candidate_service_ids)
        for row in resolved.price_block.offer_rows:
            if row.service_id not in allowed_services:
                raise ResponsePlanSessionContractError("prepared_price_row_service_mismatch")
    if render_response_text(resolved) != rendered_text:
        raise ResponsePlanSessionContractError("prepared_rendered_text_mismatch")
    if project_response_ui(resolved) != ui_projection:
        raise ResponsePlanSessionContractError("prepared_ui_projection_mismatch")


def validate_topic_restoration_shown_snapshot_binding(
    *,
    source_state: ResponsePlanSessionState,
    request_binding: TurnRequestBinding,
    topic_restoration_shown_snapshot: PersistedShownOptionsSnapshot | None,
) -> None:
    """Pure source-binding check for non-null topic restoration basis."""
    if topic_restoration_shown_snapshot is None:
        return
    session_key = request_binding.session_key
    if topic_restoration_shown_snapshot.session_key != session_key:
        raise ResponsePlanSessionContractError("topic_restoration_source_session_mismatch")
    if source_state.session_key != session_key:
        raise ResponsePlanSessionContractError("topic_restoration_source_session_mismatch")
    prior_shown = source_state.shown_options_snapshot
    if prior_shown is None:
        raise ResponsePlanSessionContractError("topic_restoration_source_snapshot_missing")
    if topic_restoration_shown_snapshot != prior_shown:
        raise ResponsePlanSessionContractError("topic_restoration_source_snapshot_mismatch")


def validate_prepared_update_intrinsic(
    prepared: PreparedSessionUpdate,
    receipt: SessionCompletionReceipt,
) -> str:
    """State-independent prepared/receipt checks. Returns recalculated fingerprint."""
    if prepared.request_binding.session_key != receipt.session_key:
        raise ResponsePlanSessionOwnershipError("receipt_session_key_mismatch")
    if prepared.request_binding.request_id != receipt.request_id:
        raise ResponsePlanSessionReceiptMismatch("receipt_request_id_mismatch")
    recalculated = compute_update_fingerprint(prepared)
    if recalculated != receipt.update_fingerprint:
        raise ResponsePlanSessionReceiptMismatch("receipt_fingerprint_mismatch")
    if recalculated != prepared.update_fingerprint:
        raise ResponsePlanSessionContractError("prepared_fingerprint_invalid")
    if prepared.ui_projection.transport_kind != receipt.transport_kind:
        raise ResponsePlanSessionReceiptMismatch("receipt_transport_kind_mismatch")
    if prepared.resolved_plan.transport_kind != receipt.transport_kind:
        raise ResponsePlanSessionReceiptMismatch("resolved_transport_kind_mismatch")
    validate_prepared_response_coherence(
        selection=prepared.selection,
        resolved=prepared.resolved_plan,
        rendered_text=prepared.rendered_text,
        ui_projection=prepared.ui_projection,
        situation_delta=prepared.selection.situation_delta,
    )
    return recalculated


def validate_prepared_session_update(
    prepared: PreparedSessionUpdate,
    *,
    source_state: ResponsePlanSessionState,
    policy: SessionContinuityPolicy,
) -> None:
    if prepared.request_binding.expected_revision != source_state.revision:
        raise ResponsePlanSessionContractError("prepared_source_revision_mismatch")
    if prepared.request_binding.snapshot_identity.revision != source_state.revision:
        raise ResponsePlanSessionContractError("prepared_snapshot_identity_mismatch")
    validate_topic_restoration_shown_snapshot_binding(
        source_state=source_state,
        request_binding=prepared.request_binding,
        topic_restoration_shown_snapshot=prepared.topic_restoration_shown_snapshot,
    )
    expected = apply_session_state_transition(
        source_state,
        policy=policy,
        binding=prepared.request_binding,
        rendered_text=prepared.rendered_text,
        selection=prepared.selection,
        resolved=prepared.resolved_plan,
        topic_restoration_shown_snapshot=prepared.topic_restoration_shown_snapshot,
    )
    if expected != prepared.proposed_state:
        raise ResponsePlanSessionContractError("proposed_state_transition_mismatch")


def validate_bound_pipeline_outcome(
    *,
    snapshot: ResponsePlanSessionSnapshot,
    expected_binding: TurnRequestBinding,
    pipeline: TurnPipelineOutcome,
) -> None:
    if expected_binding != pipeline.request_binding:
        raise ResponsePlanSessionContractError("pipeline_binding_mismatch")
    if SessionSnapshotIdentity.from_snapshot(snapshot) != expected_binding.snapshot_identity:
        raise ResponsePlanSessionContractError("pipeline_snapshot_identity_mismatch")
    if expected_binding.session_key != snapshot.state.session_key:
        raise ResponsePlanSessionContractError("pipeline_snapshot_session_mismatch")
    if expected_binding.current_turn_index != snapshot.current_turn_index:
        raise ResponsePlanSessionContractError("pipeline_turn_index_mismatch")


def prepare_session_update(
    snapshot: ResponsePlanSessionSnapshot,
    *,
    policy: SessionContinuityPolicy,
    pipeline: TurnPipelineOutcome,
    expected_binding: TurnRequestBinding,
    topic_restoration_shown_snapshot: PersistedShownOptionsSnapshot | None = None,
) -> PreparedSessionUpdate:
    validate_bound_pipeline_outcome(
        snapshot=snapshot,
        expected_binding=expected_binding,
        pipeline=pipeline,
    )
    binding = expected_binding
    if binding.session_key != snapshot.state.session_key:
        raise ResponsePlanSessionContractError("prepare_snapshot_session_mismatch")
    if binding.current_turn_index != snapshot.current_turn_index:
        raise ResponsePlanSessionContractError("prepare_turn_index_mismatch")
    if SessionSnapshotIdentity.from_snapshot(snapshot) != binding.snapshot_identity:
        raise ResponsePlanSessionContractError("prepare_snapshot_identity_mismatch")

    selection = pipeline.selection
    validate_topic_restoration_shown_snapshot_binding(
        source_state=snapshot.state,
        request_binding=binding,
        topic_restoration_shown_snapshot=topic_restoration_shown_snapshot,
    )
    validate_prepared_response_coherence(
        selection=selection,
        resolved=pipeline.materialized.resolved,
        rendered_text=pipeline.rendered_text,
        ui_projection=pipeline.ui_projection,
        situation_delta=pipeline.materialized.situation_delta,
    )
    proposed = apply_session_state_transition(
        snapshot.state,
        policy=policy,
        binding=binding,
        rendered_text=pipeline.rendered_text,
        selection=selection,
        resolved=pipeline.materialized.resolved,
        topic_restoration_shown_snapshot=topic_restoration_shown_snapshot,
    )
    prepared = PreparedSessionUpdate(
        request_binding=binding,
        patient_message=binding.patient_message,
        rendered_text=pipeline.rendered_text,
        proposed_state=proposed,
        resolved_plan=pipeline.materialized.resolved,
        ui_projection=pipeline.ui_projection,
        selection=selection,
        topic_restoration_shown_snapshot=topic_restoration_shown_snapshot,
        update_fingerprint="",
    )
    return attach_update_fingerprint(prepared)


def commit_session_update(
    store: ResponsePlanSessionStore,
    prepared: PreparedSessionUpdate,
    receipt: SessionCompletionReceipt,
    *,
    policy: SessionContinuityPolicy,
    source_state: ResponsePlanSessionState,
) -> SessionCommitResult:
    return store.commit(prepared, receipt, policy=policy, source_state=source_state)


def situation_continuity_policy(policy: SessionContinuityPolicy) -> SituationContinuityPolicy:
    return SituationContinuityPolicy(max_age_turns=policy.situation_max_age_turns)


def shown_options_freshness_policy(policy: SessionContinuityPolicy) -> ShownOptionsFreshnessPolicy:
    return ShownOptionsFreshnessPolicy(max_age_turns=policy.shown_options_max_age_turns)
