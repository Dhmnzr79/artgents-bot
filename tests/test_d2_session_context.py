from __future__ import annotations

from datetime import UTC, datetime, timedelta
import pytest
from pydantic import ValidationError

from contracts.d2_session_context import (
    DEFAULT_D2_SESSION_IDLE_TTL_SECONDS,
    D2SessionActivity,
    D2SessionContextError,
    D2SessionTtlPolicy,
)
from contracts.response_plan import FrozenPriceOfferRow, SessionKey
from contracts.response_plan_session import (
    HistoricalPriceOffersSnapshot,
    PersistedActiveService,
    PersistedActiveTopic,
    PersistedShownCommercialIds,
    PersistedShownOptionsSnapshot,
    PersistedSituationState,
    ResponsePlanSessionState,
    SESSION_SCHEMA_VERSION,
    SessionDialoguePair,
    empty_session_snapshot,
)
from core.d2_session_context import project_d2_session_context


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
