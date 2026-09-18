"""Pure inactivity-TTL projection for the isolated D2 session contract."""

from __future__ import annotations

from datetime import datetime, timedelta

from contracts.d2_session_context import (
    D2OrdinarySessionContext,
    D2SessionActivity,
    D2SessionContextError,
    D2SessionContextProjection,
    D2SessionTtlPolicy,
)
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
