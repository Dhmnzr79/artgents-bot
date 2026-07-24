"""Historical TurnFrame shadow recorder (A9 eval contracts / offline tests only).

Product path must use ``core.runtime_turn_frame`` (C2a). Do not import this module
from active product code.
"""

from __future__ import annotations

from typing import Any

from flask import request

from contracts.decision_frame import DecisionFrame
from contracts.planner_attempt import PlannerAttempt
from contracts.turn_frame import TurnFrame
from contracts.turn_plan import TurnPlan
from core.turn_frame_adapter import build_turn_frame_from_legacy
from logging_setup import emit_bot_event, get_logger

logger = get_logger("bot")

SHADOW_STATUS_OK = "ok"
SHADOW_STATUS_PARTIAL = "partial"
SHADOW_STATUS_NOT_AVAILABLE = "not_available"
SHADOW_STATUS_DEGRADED = "degraded"

SHADOW_REASON_TURN_PLAN_MISSING = "turn_plan_missing"
SHADOW_REASON_BUILD_FAILED = "turn_frame_build_failed"

_CTX_SHADOW = "turn_frame_shadow"
_CTX_STATUS = "turn_frame_shadow_status"
_CTX_REASON = "turn_frame_shadow_reason"


def _ctx() -> dict[str, Any] | None:
    if not hasattr(request, "ctx"):
        return None
    return request.ctx


def mark_turn_frame_shadow_not_available() -> None:
    """Historical — delegates to runtime publisher (C2a)."""
    from core.runtime_turn_frame import mark_runtime_turn_frame_not_available

    mark_runtime_turn_frame_not_available()


def record_planner_attempt_shadow(
    *,
    attempt: PlannerAttempt,
) -> TurnFrame | None:
    """Historical API — delegates to native runtime publisher."""
    from core.runtime_turn_frame import publish_planner_attempt_frame

    return publish_planner_attempt_frame(attempt=attempt)


def record_turn_frame_shadow(
    *,
    turn_plan: TurnPlan,
    decision_frame: DecisionFrame,
) -> TurnFrame | None:
    """Build TurnFrame from legacy planner inputs (historical / unit tests only)."""
    ctx = _ctx()
    if ctx is None:
        return None
    try:
        frame = build_turn_frame_from_legacy(
            turn_plan=turn_plan,
            decision_frame=decision_frame,
        )
        snapshot = frame.model_dump()
    except Exception:
        ctx[_CTX_STATUS] = SHADOW_STATUS_DEGRADED
        ctx[_CTX_REASON] = SHADOW_REASON_BUILD_FAILED
        ctx.pop(_CTX_SHADOW, None)
        try:
            emit_bot_event(
                logger,
                "turn_frame_shadow",
                status=SHADOW_STATUS_DEGRADED,
                details={
                    "turn_frame_shadow_status": SHADOW_STATUS_DEGRADED,
                    "turn_frame_shadow_reason": SHADOW_REASON_BUILD_FAILED,
                },
            )
        except Exception:
            pass
        return None

    ctx[_CTX_SHADOW] = snapshot
    ctx[_CTX_STATUS] = SHADOW_STATUS_OK
    ctx.pop(_CTX_REASON, None)
    return frame


def get_turn_frame_shadow_status() -> str | None:
    ctx = _ctx()
    if ctx is None:
        return None
    status = ctx.get(_CTX_STATUS)
    return str(status) if status is not None else None


def get_turn_frame_shadow_snapshot() -> dict[str, object] | None:
    ctx = _ctx()
    if ctx is None:
        return None
    snapshot = ctx.get(_CTX_SHADOW)
    if not isinstance(snapshot, dict):
        return None
    return snapshot
