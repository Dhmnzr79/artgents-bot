"""Pure inactivity-TTL projection for the isolated D2 session contract."""

from __future__ import annotations

from datetime import datetime, timedelta

from contracts.d2_session_context import (
    D2CrossTopicSituationCarry,
    D2EnvelopeSessionBinding,
    D2OrdinarySessionContext,
    D2PlanFocusSeed,
    D2SessionActivity,
    D2SessionContextError,
    D2SessionContextProjection,
    D2SessionTtlPolicy,
)
from contracts.one_call_envelope import OneCallEnvelope
from contracts.request_understanding import RequestUnderstandingRequest
from contracts.response_plan import SessionKey
from contracts.response_plan_session import ResponsePlanSessionSnapshot


def project_d2_session_context(
    snapshot: ResponsePlanSessionSnapshot,
    *,
    expected_session_key: SessionKey,
    activity: D2SessionActivity | None,
    policy: D2SessionTtlPolicy,
    now: datetime,
) -> D2SessionContextProjection:
    """Return an immutable TTL-gated view without examining dialogue text.

    ``activity`` is intentionally supplied rather than read or updated here.
    A missing record is fail-closed for ordinary context.  Semantic continuation
    (including ambiguity and patient/topic changes) is intentionally outside
    this helper.
    """

    _require_aware("now", now)
    source = snapshot.state
    if source.session_key != expected_session_key:
        raise D2SessionContextError("snapshot_session_key_mismatch")
    if activity is None:
        return _projection(
            snapshot,
            freshness="unknown",
            last_user_turn_at=None,
            ordinary=D2OrdinarySessionContext(),
        )
    if activity.session_key != expected_session_key:
        raise D2SessionContextError("activity_session_key_mismatch")

    last_user_turn_at = activity.last_user_turn_at
    _require_aware("last_user_turn_at", last_user_turn_at)
    elapsed = now - last_user_turn_at
    if elapsed.total_seconds() < 0:
        raise D2SessionContextError("last_user_turn_at_in_future")

    if elapsed >= timedelta(seconds=policy.idle_ttl_seconds):
        return _projection(
            snapshot,
            freshness="expired",
            last_user_turn_at=last_user_turn_at,
            ordinary=D2OrdinarySessionContext(),
        )
    return _projection(
        snapshot,
        freshness="fresh",
        last_user_turn_at=last_user_turn_at,
        ordinary=D2OrdinarySessionContext(
            dialogue_pairs=source.dialogue_pairs,
            active_service=source.active_service,
            active_topic=source.active_topic,
            situation_state=source.situation_state,
            shown_options_snapshot=source.shown_options_snapshot,
            historical_price_offers=source.historical_price_offers,
            clarify_pending=source.clarify_pending,
        ),
    )


def bind_d1r_envelope_to_d2_context(
    envelope: OneCallEnvelope,
    projection: D2SessionContextProjection,
) -> D2EnvelopeSessionBinding:
    """Classify one parsed D1R envelope using only fresh typed session refs.

    C10 freshness merely permits reading ordinary state.  It never chooses a
    semantic outcome: an explicit typed topic is still a new topic after TTL
    expiry, while an absent or conflicting focus fails closed as ambiguous.
    Dialogue text, turn counters, and service-to-topic inference are outside
    this pure binding.
    """

    requests = (
        envelope.request_understanding.requests
        if envelope.request_understanding is not None
        else ()
    )
    topic_ids = {request.topic_id for request in requests if request.topic_id is not None}
    if len(topic_ids) > 1:
        return _binding(projection, outcome="ambiguous_focus")

    ordinary = (
        projection.ordinary
        if projection.freshness == "fresh"
        else D2OrdinarySessionContext()
    )
    explicit_topic_id = next(iter(topic_ids), None)
    if explicit_topic_id is not None:
        return _bind_explicit_topic(
            projection,
            ordinary=ordinary,
            requests=requests,
            explicit_topic_id=explicit_topic_id,
        )

    service_ids = {request.service_id for request in requests if request.service_id is not None}
    if len(service_ids) != 1:
        return _binding(projection, outcome="ambiguous_focus")
    return _bind_exact_service(
        projection,
        ordinary=ordinary,
        service_id=next(iter(service_ids)),
    )


def seed_d2_plan_focus(binding: D2EnvelopeSessionBinding) -> D2PlanFocusSeed:
    """Project a C11 result into one resolver-neutral, typed focus seed.

    C10 freshness and all D1R semantic interpretation have already happened
    upstream.  This helper neither revisits them nor infers a topic from a
    service.  A usable resolved topic is the sole condition for ``resolve``;
    every incomplete but structurally valid binding asks for clarification.
    """

    _validate_binding_for_plan_focus(binding)
    if binding.outcome == "ambiguous_focus" or binding.resolved_topic_id is None:
        return _plan_focus_seed(binding, action="clarify_focus")
    if binding.outcome == "explicit_new_topic":
        return _plan_focus_seed(
            binding,
            action="resolve_topic",
            topic_id=binding.resolved_topic_id,
            cross_topic_carry=binding.cross_topic_carry,
        )
    return _plan_focus_seed(
        binding,
        action="resolve_topic",
        topic_id=binding.resolved_topic_id,
        carried_situation=binding.carried_situation,
    )


def _validate_binding_for_plan_focus(binding: D2EnvelopeSessionBinding) -> None:
    if binding.outcome == "ambiguous_focus":
        if binding.resolved_topic_id is not None or binding.carried_situation is not None:
            raise D2SessionContextError("ambiguous_binding_has_focus")
        return
    if binding.outcome == "explicit_new_topic":
        if binding.resolved_topic_id is None or binding.carried_situation is not None:
            raise D2SessionContextError("explicit_new_binding_invalid")
        return
    if binding.outcome != "clear_continuation":
        raise D2SessionContextError("binding_outcome_invalid")
    if (
        binding.carried_situation is not None
        and binding.resolved_topic_id != binding.carried_situation.topic_id
    ):
        raise D2SessionContextError("clear_binding_situation_topic_mismatch")


def _plan_focus_seed(
    binding: D2EnvelopeSessionBinding,
    *,
    action: str,
    topic_id: str | None = None,
    carried_situation=None,
    cross_topic_carry=None,
) -> D2PlanFocusSeed:
    return D2PlanFocusSeed(
        source_session_key=binding.source_session_key,
        source_revision=binding.source_revision,
        source_turn_index=binding.source_turn_index,
        action=action,  # type: ignore[arg-type]
        topic_id=topic_id,
        carried_situation=carried_situation,
        cross_topic_carry=cross_topic_carry,
    )


def _bind_explicit_topic(
    projection: D2SessionContextProjection,
    *,
    ordinary: D2OrdinarySessionContext,
    requests: tuple[RequestUnderstandingRequest, ...],
    explicit_topic_id: str,
) -> D2EnvelopeSessionBinding:
    stored_topic_ids = {
        value
        for value in (
            ordinary.active_topic.topic_id if ordinary.active_topic is not None else None,
            ordinary.situation_state.topic_id if ordinary.situation_state is not None else None,
            (
                ordinary.shown_options_snapshot.topic_id
                if ordinary.shown_options_snapshot is not None
                else None
            ),
        )
        if value is not None
    }
    if not stored_topic_ids or explicit_topic_id not in stored_topic_ids:
        return _binding(
            projection,
            outcome="explicit_new_topic",
            resolved_topic_id=explicit_topic_id,
            cross_topic_carry=_cross_topic_carry_candidate(
                ordinary=ordinary,
                requests=requests,
                destination_topic_id=explicit_topic_id,
            ),
        )
    if stored_topic_ids != {explicit_topic_id}:
        return _binding(projection, outcome="ambiguous_focus")
    return _binding(
        projection,
        outcome="clear_continuation",
        resolved_topic_id=explicit_topic_id,
        carried_situation=_same_typed_situation(
            requests,
            ordinary=ordinary,
            resolved_topic_id=explicit_topic_id,
        ),
    )


def _bind_exact_service(
    projection: D2SessionContextProjection,
    *,
    ordinary: D2OrdinarySessionContext,
    service_id: str,
) -> D2EnvelopeSessionBinding:
    resolved_topics: set[str] = set()
    matched = False
    if ordinary.active_service is not None and ordinary.active_service.service_id == service_id:
        matched = True
        if ordinary.active_topic is not None:
            resolved_topics.add(ordinary.active_topic.topic_id)
    if (
        ordinary.shown_options_snapshot is not None
        and service_id in ordinary.shown_options_snapshot.service_ids
    ):
        matched = True
        resolved_topics.add(ordinary.shown_options_snapshot.topic_id)
    if not matched or len(resolved_topics) > 1:
        return _binding(projection, outcome="ambiguous_focus")
    return _binding(
        projection,
        outcome="clear_continuation",
        resolved_topic_id=next(iter(resolved_topics), None),
    )


def _same_typed_situation(
    requests: tuple[RequestUnderstandingRequest, ...],
    *,
    ordinary: D2OrdinarySessionContext,
    resolved_topic_id: str,
):
    if ordinary.situation_state is None or ordinary.situation_state.topic_id != resolved_topic_id:
        return None
    for request in requests:
        if (
            request.topic_id == resolved_topic_id
            and request.situation is not None
            and request.situation.continuity == "same"
        ):
            return ordinary.situation_state
    return None


def _cross_topic_carry_candidate(
    *,
    ordinary: D2OrdinarySessionContext,
    requests: tuple[RequestUnderstandingRequest, ...],
    destination_topic_id: str,
) -> D2CrossTopicSituationCarry | None:
    source = ordinary.situation_state
    if (
        source is None
        or source.situation_owner_id is None
        or ordinary.active_topic is None
        or ordinary.shown_options_snapshot is None
        or ordinary.active_topic.topic_id != source.topic_id
        or ordinary.shown_options_snapshot.topic_id != source.topic_id
    ):
        return None
    for request in requests:
        if (
            request.topic_id == destination_topic_id
            and request.subject_id is not None
            and request.situation is not None
            and request.situation.continuity == "same"
            and request.situation.scope_commitment != "reset"
        ):
            return D2CrossTopicSituationCarry(
                situation_owner_id=source.situation_owner_id,
                source_situation=source,
                destination_topic_id=destination_topic_id,
            )
    return None


def _binding(
    projection: D2SessionContextProjection,
    *,
    outcome: str,
    resolved_topic_id: str | None = None,
    carried_situation=None,
    cross_topic_carry=None,
) -> D2EnvelopeSessionBinding:
    return D2EnvelopeSessionBinding(
        source_session_key=projection.session_key,
        source_revision=projection.source_revision,
        source_turn_index=projection.source_turn_index,
        outcome=outcome,  # type: ignore[arg-type]
        resolved_topic_id=resolved_topic_id,
        carried_situation=carried_situation,
        cross_topic_carry=cross_topic_carry,
    )


def _projection(
    snapshot: ResponsePlanSessionSnapshot,
    *,
    freshness: str,
    last_user_turn_at: datetime | None,
    ordinary: D2OrdinarySessionContext,
) -> D2SessionContextProjection:
    source = snapshot.state
    return D2SessionContextProjection(
        session_key=source.session_key,
        source_revision=source.revision,
        source_turn_index=source.last_committed_turn_index,
        freshness=freshness,  # type: ignore[arg-type]
        last_user_turn_at=last_user_turn_at,
        ordinary=ordinary,
        retained_terminal_state=source.terminal_state,
        retained_shown_ids=source.accumulated_shown_ids,
    )


def _require_aware(field: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise D2SessionContextError(f"{field}_timezone_required")
