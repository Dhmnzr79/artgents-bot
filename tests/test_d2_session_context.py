from __future__ import annotations

from datetime import UTC, datetime, timedelta
import pytest
from pydantic import ValidationError

from contracts.d2_session_context import (
    DEFAULT_D2_SESSION_IDLE_TTL_SECONDS,
    D2EnvelopeSessionBinding,
    D2SessionActivity,
    D2SessionContextError,
    D2SessionTtlPolicy,
)
from contracts.one_call_envelope import OneCallEnvelope, OneCallEnvelopeReferences
from contracts.request_understanding import (
    RequestTreatmentSituation,
    RequestUnderstanding,
    RequestUnderstandingRequest,
    RequestUnderstandingSubject,
)
from contracts.response_plan import FrozenPriceOfferRow, SessionKey
from contracts.response_plan_session import (
    HistoricalPriceOffersSnapshot,
    PersistedActiveService,
    PersistedActiveTopic,
    PersistedShownCommercialIds,
    PersistedShownOptionsSnapshot,
    PersistedSituationState,
    ResponsePlanSessionContractError,
    ResponsePlanSessionState,
    SESSION_SCHEMA_VERSION,
    SessionDialoguePair,
    empty_session_snapshot,
)
from core.d2_session_context import (
    bind_d1r_envelope_to_d2_context,
    project_d2_session_context,
    seed_d2_plan_focus,
)


NOW = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)


def _key(*, client_id: str = "demo", sid: str = "s1") -> SessionKey:
    return SessionKey(client_id=client_id, sid=sid)


def _snapshot() -> object:
    key = _key()
    state = ResponsePlanSessionState(
        schema_version=SESSION_SCHEMA_VERSION,
        session_key=key,
        revision=7,
        last_committed_turn_index=99,
        dialogue_pairs=(
            SessionDialoguePair(
                patient_text="Сколько стоит?",
                assistant_text="От 100 000 ₽",
                committed_at_turn=99,
            ),
        ),
        active_service=PersistedActiveService(
            service_id="all_on_4", provenance="explicit_current", set_at_turn=1
        ),
        active_topic=PersistedActiveTopic(
            topic_id="implantation", provenance="explicit_current", set_at_turn=1
        ),
        situation_state=PersistedSituationState(
            session_key=key,
            topic_id="implantation",
            extent="full_arch",
            jaw="upper",
            stage="unknown",
            modifiers=(),
            set_at_turn=1,
            situation_owner_id="owner-implant-1",
            tooth_count=4,
        ),
        shown_options_snapshot=PersistedShownOptionsSnapshot(
            session_key=key,
            topic_id="implantation",
            service_ids=("all_on_4",),
            shown_at_turn=1,
        ),
        historical_price_offers=HistoricalPriceOffersSnapshot(
            rows=(
                FrozenPriceOfferRow(
                    source_client_id="demo",
                    offer_id="offer-a",
                    service_id="all_on_4",
                    offer_label="All-on-4",
                    amount=100_000,
                    currency="RUB",
                    billing_unit="service",
                ),
            ),
            shown_at_turn=1,
        ),
        accumulated_shown_ids=PersistedShownCommercialIds(promo_fact_ids=("promo-a",)),
        terminal_state="clarify",
        clarify_pending=True,
    )
    return empty_session_snapshot(key).model_copy(
        update={"state": state, "exists_in_store": True}
    )


def _activity(*, at: datetime, key: SessionKey | None = None) -> D2SessionActivity:
    return D2SessionActivity(session_key=key or _key(), last_user_turn_at=at)


def _envelope(
    *requests: RequestUnderstandingRequest,
    patient_text: str = "Исходный текст не является semantic input.",
) -> OneCallEnvelope:
    subject_ids = {request.subject_id for request in requests if request.subject_id is not None}
    subjects = tuple(
        RequestUnderstandingSubject(subject_id=subject_id, relation="self", age_group="adult")
        for subject_id in sorted(subject_ids)
    )
    return OneCallEnvelope(
        route="ANSWER",
        service_id=None,
        extent=None,
        jaw=None,
        stage=None,
        scenario="none",
        commercial_intent="none",
        promotion_scope="none",
        clarify_axis=None,
        clarify_service_options=None,
        patient_text=patient_text,
        service_reference_status="none",
        requested_service_id=None,
        references=OneCallEnvelopeReferences(direct_fact_ids=()),
        request_understanding=RequestUnderstanding(subjects=subjects, requests=requests),
    )


def _request(
    *,
    request_id: str = "r1",
    topic_id: str | None = None,
    service_id: str | None = None,
    continuity: str | None = None,
    reset: bool = False,
) -> RequestUnderstandingRequest:
    situation = None
    subject_id = None
    if continuity is not None:
        subject_id = "s1" if continuity == "same" else None
        situation = RequestTreatmentSituation(
            scope_commitment="reset" if reset else "reported",
            extent="unknown" if reset else "one_tooth",
            jaw="unknown" if reset else "upper",
            continuity=continuity,  # type: ignore[arg-type]
        )
    return RequestUnderstandingRequest(
        request_id=request_id,
        kind="price",
        subject_id=subject_id,
        context="current_care",
        service_id=service_id,
        topic_id=topic_id,
        situation=situation,
    )


def _fresh_projection():
    return project_d2_session_context(
        _snapshot(),  # type: ignore[arg-type]
        expected_session_key=_key(),
        activity=_activity(at=NOW - timedelta(seconds=1)),
        policy=D2SessionTtlPolicy(),
        now=NOW,
    )


def _expired_projection():
    return project_d2_session_context(
        _snapshot(),  # type: ignore[arg-type]
        expected_session_key=_key(),
        activity=_activity(at=NOW - timedelta(seconds=1800)),
        policy=D2SessionTtlPolicy(),
        now=NOW,
    )


def test_default_ttl_is_30_minutes_and_is_injected() -> None:
    assert D2SessionTtlPolicy().idle_ttl_seconds == DEFAULT_D2_SESSION_IDLE_TTL_SECONDS == 1800


@pytest.mark.parametrize("value", [True, 1.0, "1800", 0, -1])
def test_ttl_policy_rejects_non_positive_or_non_strict_duration(value: object) -> None:
    with pytest.raises(ValidationError):
        D2SessionTtlPolicy(idle_ttl_seconds=value)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("elapsed", "expected"),
    [
        (timedelta(seconds=1799, microseconds=999999), "fresh"),
        (timedelta(seconds=1800), "expired"),
        (timedelta(seconds=1800, microseconds=1), "expired"),
    ],
)
def test_ttl_boundary_is_inclusive_at_expiry(elapsed: timedelta, expected: str) -> None:
    snapshot = _snapshot()
    projection = project_d2_session_context(
        snapshot,  # type: ignore[arg-type]
        expected_session_key=_key(),
        activity=_activity(at=NOW - elapsed),
        policy=D2SessionTtlPolicy(),
        now=NOW,
    )
    assert projection.freshness == expected


def test_fresh_context_keeps_typed_ordinary_state_without_interpreting_text() -> None:
    snapshot = _snapshot()
    projection = project_d2_session_context(
        snapshot,  # type: ignore[arg-type]
        expected_session_key=_key(),
        activity=_activity(at=NOW - timedelta(seconds=1)),
        policy=D2SessionTtlPolicy(),
        now=NOW,
    )
    assert projection.freshness == "fresh"
    assert projection.ordinary.active_service is not None
    assert projection.ordinary.active_service.service_id == "all_on_4"
    assert projection.ordinary.active_topic is not None
    assert projection.ordinary.situation_state is not None
    assert projection.ordinary.situation_state.situation_owner_id == "owner-implant-1"
    assert projection.ordinary.situation_state.tooth_count == 4
    assert projection.ordinary.shown_options_snapshot is not None
    assert projection.ordinary.historical_price_offers is not None
    assert projection.ordinary.dialogue_pairs == snapshot.state.dialogue_pairs  # type: ignore[union-attr]
    assert projection.ordinary.clarify_pending is True


def test_expired_or_missing_activity_hides_all_ordinary_context_but_retains_nonrepeat_state() -> None:
    snapshot = _snapshot()
    for activity, expected in (
        (_activity(at=NOW - timedelta(seconds=1800)), "expired"),
        (None, "unknown"),
    ):
        projection = project_d2_session_context(
            snapshot,  # type: ignore[arg-type]
            expected_session_key=_key(),
            activity=activity,
            policy=D2SessionTtlPolicy(),
            now=NOW,
        )
        assert projection.freshness == expected
        assert projection.ordinary.dialogue_pairs == ()
        assert projection.ordinary.active_service is None
        assert projection.ordinary.active_topic is None
        assert projection.ordinary.situation_state is None
        assert projection.ordinary.shown_options_snapshot is None
        assert projection.ordinary.historical_price_offers is None
        assert projection.ordinary.clarify_pending is False
        assert projection.retained_terminal_state == "clarify"
        assert projection.retained_shown_ids.promo_fact_ids == ("promo-a",)


def test_many_turns_do_not_expire_a_fresh_idle_record() -> None:
    snapshot = _snapshot()
    projection = project_d2_session_context(
        snapshot,  # type: ignore[arg-type]
        expected_session_key=_key(),
        activity=_activity(at=NOW - timedelta(seconds=1)),
        policy=D2SessionTtlPolicy(idle_ttl_seconds=2),
        now=NOW,
    )
    assert snapshot.state.last_committed_turn_index == 99  # type: ignore[union-attr]
    assert projection.freshness == "fresh"


def test_custom_ttl_changes_expiry_without_reading_turn_age() -> None:
    projection = project_d2_session_context(
        _snapshot(),  # type: ignore[arg-type]
        expected_session_key=_key(),
        activity=_activity(at=NOW - timedelta(seconds=2)),
        policy=D2SessionTtlPolicy(idle_ttl_seconds=2),
        now=NOW,
    )
    assert projection.freshness == "expired"


def test_text_changes_do_not_change_ttl_result_or_semantic_metadata() -> None:
    snapshot = _snapshot()
    changed_pair = snapshot.state.dialogue_pairs[0].model_copy(  # type: ignore[union-attr]
        update={
            "patient_text": "Совершенно другой текст?!",
            "assistant_text": "И другой ответ",
        }
    )
    changed_state = snapshot.state.model_copy(  # type: ignore[union-attr]
        update={"dialogue_pairs": (changed_pair,)}
    )
    changed_snapshot = snapshot.model_copy(update={"state": changed_state})  # type: ignore[union-attr]
    kwargs = {
        "expected_session_key": _key(),
        "activity": _activity(at=NOW - timedelta(seconds=10)),
        "policy": D2SessionTtlPolicy(),
        "now": NOW,
    }
    original = project_d2_session_context(snapshot, **kwargs)  # type: ignore[arg-type]
    changed = project_d2_session_context(changed_snapshot, **kwargs)
    assert original.freshness == changed.freshness == "fresh"
    assert original.ordinary.active_service == changed.ordinary.active_service
    assert original.ordinary.active_topic == changed.ordinary.active_topic
    assert original.ordinary.situation_state == changed.ordinary.situation_state


@pytest.mark.parametrize(
    ("activity_key", "expected"),
    [(_key(client_id="other"), "activity_session_key_mismatch"), (_key(sid="other"), "activity_session_key_mismatch")],
)
def test_activity_must_match_tenant_and_sid(activity_key: SessionKey, expected: str) -> None:
    with pytest.raises(D2SessionContextError, match=expected):
        project_d2_session_context(
            _snapshot(),  # type: ignore[arg-type]
            expected_session_key=_key(),
            activity=_activity(at=NOW, key=activity_key),
            policy=D2SessionTtlPolicy(),
            now=NOW,
        )


def test_snapshot_must_match_tenant_and_sid() -> None:
    with pytest.raises(D2SessionContextError, match="snapshot_session_key_mismatch"):
        project_d2_session_context(
            _snapshot(),  # type: ignore[arg-type]
            expected_session_key=_key(sid="other"),
            activity=_activity(at=NOW),
            policy=D2SessionTtlPolicy(),
            now=NOW,
        )


def test_invalid_naive_and_future_timestamps_fail_closed() -> None:
    with pytest.raises(ValidationError):
        D2SessionActivity(session_key=_key(), last_user_turn_at="not-a-timestamp")  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="last_user_turn_at_timezone_required"):
        _activity(at=datetime(2026, 9, 18, 12, 0))
    with pytest.raises(D2SessionContextError, match="last_user_turn_at_in_future"):
        project_d2_session_context(
            _snapshot(),  # type: ignore[arg-type]
            expected_session_key=_key(),
            activity=_activity(at=NOW + timedelta(microseconds=1)),
            policy=D2SessionTtlPolicy(),
            now=NOW,
        )


def test_projection_does_not_mutate_snapshot_or_activity() -> None:
    snapshot = _snapshot()
    activity = _activity(at=NOW - timedelta(seconds=1800))
    before_snapshot = snapshot.model_dump(mode="json")  # type: ignore[union-attr]
    before_activity = activity.model_dump(mode="json")
    projection = project_d2_session_context(
        snapshot,  # type: ignore[arg-type]
        expected_session_key=_key(),
        activity=activity,
        policy=D2SessionTtlPolicy(),
        now=NOW,
    )
    assert projection.freshness == "expired"
    assert snapshot.model_dump(mode="json") == before_snapshot  # type: ignore[union-attr]
    assert activity.model_dump(mode="json") == before_activity


def test_fresh_exact_typed_topic_with_same_situation_carries_only_typed_state() -> None:
    projection = _fresh_projection()
    binding = bind_d1r_envelope_to_d2_context(
        _envelope(_request(topic_id="implantation", continuity="same")), projection
    )
    assert binding.outcome == "clear_continuation"
    assert binding.resolved_topic_id == "implantation"
    assert binding.carried_situation == projection.ordinary.situation_state
    assert binding.source_session_key == _key()
    assert binding.source_revision == 7
    assert binding.source_turn_index == 99


@pytest.mark.parametrize("projection_factory", [_fresh_projection, _expired_projection])
def test_explicit_new_typed_topic_is_not_decided_by_ttl(projection_factory) -> None:
    binding = bind_d1r_envelope_to_d2_context(
        _envelope(_request(topic_id="prosthetics", continuity="same")), projection_factory()
    )
    assert binding.outcome == "explicit_new_topic"
    assert binding.resolved_topic_id == "prosthetics"
    assert binding.carried_situation is None


def test_fresh_explicit_same_situation_can_offer_typed_cross_topic_candidate() -> None:
    binding = bind_d1r_envelope_to_d2_context(
        _envelope(_request(topic_id="prosthetics", continuity="same")), _fresh_projection()
    )
    seed = seed_d2_plan_focus(binding)
    assert binding.outcome == "explicit_new_topic"
    assert binding.cross_topic_carry is not None
    assert binding.cross_topic_carry.situation_owner_id == "owner-implant-1"
    assert binding.cross_topic_carry.source_situation.topic_id == "implantation"
    assert binding.cross_topic_carry.source_situation.tooth_count == 4
    assert binding.cross_topic_carry.destination_topic_id == "prosthetics"
    assert seed.topic_id == "prosthetics"
    assert seed.cross_topic_carry == binding.cross_topic_carry


@pytest.mark.parametrize(
    "projection_update, continuity, reset",
    [
        ({"situation_state": _snapshot().state.situation_state.model_copy(update={"situation_owner_id": None})}, "same", False),  # type: ignore[union-attr]
        ({"shown_options_snapshot": _snapshot().state.shown_options_snapshot.model_copy(update={"topic_id": "prosthetics"})}, "same", False),  # type: ignore[union-attr]
        ({}, "new", False),
        ({}, "unknown", False),
        ({}, "same", True),
    ],
)
def test_cross_topic_candidate_fails_closed_without_all_typed_guards(
    projection_update: dict[str, object], continuity: str, reset: bool
) -> None:
    snapshot = _snapshot()
    state = snapshot.state.model_copy(update=projection_update)  # type: ignore[union-attr]
    projection = project_d2_session_context(
        snapshot.model_copy(update={"state": state}),  # type: ignore[union-attr]
        expected_session_key=_key(),
        activity=_activity(at=NOW - timedelta(seconds=1)),
        policy=D2SessionTtlPolicy(),
        now=NOW,
    )
    binding = bind_d1r_envelope_to_d2_context(
        _envelope(_request(topic_id="prosthetics", continuity=continuity, reset=reset)),
        projection,
    )
    assert binding.outcome in {"explicit_new_topic", "ambiguous_focus"}
    assert binding.cross_topic_carry is None


def test_cross_topic_candidate_is_ttl_and_raw_text_invariant() -> None:
    original = _envelope(_request(topic_id="prosthetics", continuity="same"))
    hostile = original.model_copy(update={"patient_text": "НЕ МЕНЯЕТ TYPED CARRY"})
    fresh = bind_d1r_envelope_to_d2_context(original, _fresh_projection())
    hostile_fresh = bind_d1r_envelope_to_d2_context(hostile, _fresh_projection())
    expired = bind_d1r_envelope_to_d2_context(original, _expired_projection())
    assert fresh.cross_topic_carry == hostile_fresh.cross_topic_carry
    assert expired.cross_topic_carry is None


def test_missing_or_multiple_typed_focus_fails_closed_as_ambiguous() -> None:
    projection = _fresh_projection()
    missing = bind_d1r_envelope_to_d2_context(_envelope(_request()), projection)
    multiple = bind_d1r_envelope_to_d2_context(
        _envelope(
            _request(request_id="r1", topic_id="implantation"),
            _request(request_id="r2", topic_id="prosthetics"),
        ),
        projection,
    )
    assert missing.outcome == "ambiguous_focus"
    assert multiple.outcome == "ambiguous_focus"
    assert missing.carried_situation is None
    assert multiple.carried_situation is None


def test_exact_active_service_or_shown_option_is_the_only_service_continuation() -> None:
    projection = _fresh_projection()
    active = bind_d1r_envelope_to_d2_context(
        _envelope(_request(service_id="all_on_4")), projection
    )
    non_exact = bind_d1r_envelope_to_d2_context(
        _envelope(_request(service_id="all-on-4")), projection
    )
    assert active.outcome == "clear_continuation"
    assert active.resolved_topic_id == "implantation"
    assert non_exact.outcome == "ambiguous_focus"


@pytest.mark.parametrize(
    ("continuity", "reset"),
    [("new", False), ("unknown", False), ("unknown", True)],
)
def test_non_same_or_reset_typed_situation_never_carries(continuity: str, reset: bool) -> None:
    binding = bind_d1r_envelope_to_d2_context(
        _envelope(_request(topic_id="implantation", continuity=continuity, reset=reset)),
        _fresh_projection(),
    )
    assert binding.outcome == "clear_continuation"
    assert binding.carried_situation is None


def test_raw_dialogue_and_envelope_text_cannot_change_typed_binding() -> None:
    snapshot = _snapshot()
    changed_pair = snapshot.state.dialogue_pairs[0].model_copy(  # type: ignore[union-attr]
        update={"patient_text": "HOSTILE_NEW_TOPIC", "assistant_text": "HOSTILE_REPLY"}
    )
    changed_snapshot = snapshot.model_copy(  # type: ignore[union-attr]
        update={"state": snapshot.state.model_copy(update={"dialogue_pairs": (changed_pair,)})}
    )
    kwargs = {
        "expected_session_key": _key(),
        "activity": _activity(at=NOW - timedelta(seconds=1)),
        "policy": D2SessionTtlPolicy(),
        "now": NOW,
    }
    envelope = _envelope(_request(topic_id="implantation", continuity="same"))
    changed_envelope = envelope.model_copy(update={"patient_text": "HOSTILE_PATIENT_TEXT"})
    original = bind_d1r_envelope_to_d2_context(
        envelope, project_d2_session_context(snapshot, **kwargs)  # type: ignore[arg-type]
    )
    changed = bind_d1r_envelope_to_d2_context(
        changed_envelope, project_d2_session_context(changed_snapshot, **kwargs)
    )
    assert original == changed


def test_binding_does_not_mutate_envelope_or_projection() -> None:
    envelope = _envelope(_request(topic_id="implantation", continuity="same"))
    projection = _fresh_projection()
    before_envelope = envelope.model_dump(mode="json")
    before_projection = projection.model_dump(mode="json")
    bind_d1r_envelope_to_d2_context(envelope, projection)
    assert envelope.model_dump(mode="json") == before_envelope
    assert projection.model_dump(mode="json") == before_projection


def test_plan_focus_seed_maps_each_c11_outcome_without_reinterpreting_ttl() -> None:
    clear = bind_d1r_envelope_to_d2_context(
        _envelope(_request(topic_id="implantation", continuity="same")), _fresh_projection()
    )
    ambiguous = bind_d1r_envelope_to_d2_context(_envelope(_request()), _fresh_projection())
    explicit_new = bind_d1r_envelope_to_d2_context(
        _envelope(_request(topic_id="prosthetics")), _expired_projection()
    )
    clear_seed = seed_d2_plan_focus(clear)
    ambiguous_seed = seed_d2_plan_focus(ambiguous)
    new_seed = seed_d2_plan_focus(explicit_new)
    assert (clear_seed.action, clear_seed.topic_id) == ("resolve_topic", "implantation")
    assert clear_seed.carried_situation == clear.carried_situation
    assert (ambiguous_seed.action, ambiguous_seed.topic_id) == ("clarify_focus", None)
    assert ambiguous_seed.carried_situation is None
    assert (new_seed.action, new_seed.topic_id) == ("resolve_topic", "prosthetics")
    assert new_seed.carried_situation is None
    assert new_seed.cross_topic_carry is None


def test_plan_focus_seed_requires_a_typed_topic_for_clear_service_only_binding() -> None:
    binding = D2EnvelopeSessionBinding(
        source_session_key=_key(),
        source_revision=7,
        source_turn_index=99,
        outcome="clear_continuation",
    )
    seed = seed_d2_plan_focus(binding)
    assert seed.action == "clarify_focus"
    assert seed.topic_id is None


@pytest.mark.parametrize(
    "binding",
    [
        D2EnvelopeSessionBinding(
            source_session_key=_key(),
            source_revision=7,
            source_turn_index=99,
            outcome="ambiguous_focus",
        ).model_copy(update={"resolved_topic_id": "implantation"}),
        D2EnvelopeSessionBinding(
            source_session_key=_key(),
            source_revision=7,
            source_turn_index=99,
            outcome="explicit_new_topic",
            resolved_topic_id="prosthetics",
        ).model_copy(update={"carried_situation": _snapshot().state.situation_state}),  # type: ignore[union-attr]
    ],
)
def test_plan_focus_seed_rejects_inconsistent_binding_fail_closed(
    binding: D2EnvelopeSessionBinding,
) -> None:
    with pytest.raises(D2SessionContextError):
        seed_d2_plan_focus(binding)


def test_plan_focus_seed_is_invariant_to_raw_text_and_immutable() -> None:
    original_envelope = _envelope(_request(topic_id="implantation", continuity="same"))
    hostile_envelope = original_envelope.model_copy(
        update={"patient_text": "Новый текст, который нельзя классифицировать"}
    )
    original_binding = bind_d1r_envelope_to_d2_context(original_envelope, _fresh_projection())
    hostile_binding = bind_d1r_envelope_to_d2_context(hostile_envelope, _fresh_projection())
    before_binding = original_binding.model_dump(mode="json")
    original_seed = seed_d2_plan_focus(original_binding)
    hostile_seed = seed_d2_plan_focus(hostile_binding)
    assert original_seed == hostile_seed
    assert original_binding.model_dump(mode="json") == before_binding


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("situation_owner_id", " owner-1", "situation_owner_id_padded"),
        ("situation_owner_id", 1, "situation_owner_id_not_string"),
        ("tooth_count", True, "situation_tooth_count_invalid_type"),
        ("tooth_count", 0, "situation_tooth_count_not_positive"),
        ("tooth_count", 2, "situation_tooth_count_extent_conflict"),
    ],
)
def test_c13_persisted_situation_validates_owner_and_tooth_count(
    field: str, value: object, error: str
) -> None:
    payload = _snapshot().state.situation_state.model_dump()  # type: ignore[union-attr]
    payload.update({"extent": "one_tooth", field: value})
    with pytest.raises(ValidationError, match=error):
        PersistedSituationState.model_validate(payload)


def test_c13_fields_are_opaque_in_c10_and_fail_closed_at_legacy_conversion() -> None:
    situation = _snapshot().state.situation_state  # type: ignore[union-attr]
    assert situation is not None
    fresh = _fresh_projection()
    assert fresh.ordinary.situation_state == situation
    with pytest.raises(
        ResponsePlanSessionContractError,
        match="persisted_situation_c13_fields_not_runtime_compatible",
    ):
        situation.to_runtime()

    legacy = situation.model_copy(
        update={"situation_owner_id": None, "tooth_count": None}
    ).to_runtime()
    restored = PersistedSituationState.from_runtime(legacy)
    assert restored.situation_owner_id is None
    assert restored.tooth_count is None
