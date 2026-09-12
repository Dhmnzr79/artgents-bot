"""Native runtime TurnFrame publisher/loader for product path (C2a)."""

from __future__ import annotations

from typing import Any

from flask import request

from contracts.planner_attempt import PlannerAttempt
from contracts.turn_frame import TurnFrame
from logging_setup import emit_bot_event, get_logger

logger = get_logger("bot")

RUNTIME_FRAME_STATUS_OK = "ok"
RUNTIME_FRAME_STATUS_PARTIAL = "partial"
RUNTIME_FRAME_STATUS_NOT_AVAILABLE = "not_available"
RUNTIME_FRAME_STATUS_DEGRADED = "degraded"

RUNTIME_FRAME_REASON_TURN_PLAN_MISSING = "turn_plan_missing"
RUNTIME_FRAME_REASON_BUILD_FAILED = "turn_frame_build_failed"

_CTX_FRAME = "runtime_turn_frame"
_CTX_STATUS = "runtime_turn_frame_status"
_CTX_REASON = "runtime_turn_frame_reason"

# A9 / historical eval contracts read shadow-named telemetry in response meta.
_CTX_SHADOW_ALIAS = "turn_frame_shadow"
_CTX_SHADOW_STATUS_ALIAS = "turn_frame_shadow_status"
_CTX_SHADOW_REASON_ALIAS = "turn_frame_shadow_reason"


def _ctx() -> dict[str, Any] | None:
    if not hasattr(request, "ctx"):
        return None
    return request.ctx


def _mirror_shadow_telemetry_aliases(
    ctx: dict[str, Any],
    *,
    status: str,
    snapshot: dict[str, object] | None,
    reason: str | None = None,
) -> None:
    ctx[_CTX_SHADOW_STATUS_ALIAS] = status
    if snapshot is not None:
        ctx[_CTX_SHADOW_ALIAS] = snapshot
    else:
        ctx.pop(_CTX_SHADOW_ALIAS, None)
    if reason:
        ctx[_CTX_SHADOW_REASON_ALIAS] = reason
    else:
        ctx.pop(_CTX_SHADOW_REASON_ALIAS, None)


def mark_runtime_turn_frame_not_available() -> None:
    ctx = _ctx()
    if ctx is None:
        return
    ctx[_CTX_STATUS] = RUNTIME_FRAME_STATUS_NOT_AVAILABLE
    ctx[_CTX_REASON] = RUNTIME_FRAME_REASON_TURN_PLAN_MISSING
    ctx.pop(_CTX_FRAME, None)
    _mirror_shadow_telemetry_aliases(
        ctx,
        status=RUNTIME_FRAME_STATUS_NOT_AVAILABLE,
        snapshot=None,
        reason=RUNTIME_FRAME_REASON_TURN_PLAN_MISSING,
    )


def _mark_runtime_turn_frame_degraded(ctx: dict[str, Any]) -> None:
    ctx[_CTX_STATUS] = RUNTIME_FRAME_STATUS_DEGRADED
    ctx[_CTX_REASON] = RUNTIME_FRAME_REASON_BUILD_FAILED
    ctx.pop(_CTX_FRAME, None)
    _mirror_shadow_telemetry_aliases(
        ctx,
        status=RUNTIME_FRAME_STATUS_DEGRADED,
        snapshot=None,
        reason=RUNTIME_FRAME_REASON_BUILD_FAILED,
    )
    try:
        emit_bot_event(
            logger,
            "runtime_turn_frame",
            status=RUNTIME_FRAME_STATUS_DEGRADED,
            details={
                "runtime_turn_frame_status": RUNTIME_FRAME_STATUS_DEGRADED,
                "runtime_turn_frame_reason": RUNTIME_FRAME_REASON_BUILD_FAILED,
                "turn_frame_shadow_status": RUNTIME_FRAME_STATUS_DEGRADED,
                "turn_frame_shadow_reason": RUNTIME_FRAME_REASON_BUILD_FAILED,
            },
        )
    except Exception:
        pass


def publish_planner_attempt_frame(*, attempt: PlannerAttempt) -> TurnFrame | None:
    """Store planner-built TurnFrame on request ctx (primary product contract)."""
    ctx = _ctx()
    if ctx is None:
        return None

    status = attempt.status
    if status == RUNTIME_FRAME_STATUS_NOT_AVAILABLE:
        mark_runtime_turn_frame_not_available()
        return None
    if status == RUNTIME_FRAME_STATUS_DEGRADED:
        _mark_runtime_turn_frame_degraded(ctx)
        return None

    frame = attempt.frame
    if frame is None:
        _mark_runtime_turn_frame_degraded(ctx)
        return None
    return _publish_runtime_turn_frame_snapshot(
        ctx,
        frame=frame,
        status=status,
        typed_ui=False,
    )


def publish_typed_ui_turn_frame(frame: TurnFrame) -> TurnFrame | None:
    """Store governed UI-built TurnFrame on request ctx without planner involvement."""

    ctx = _ctx()
    if ctx is None:
        return None
    return _publish_runtime_turn_frame_snapshot(
        ctx,
        frame=frame,
        status=RUNTIME_FRAME_STATUS_OK,
        typed_ui=True,
    )


def _publish_runtime_turn_frame_snapshot(
    ctx: dict[str, Any],
    *,
    frame: TurnFrame,
    status: str,
    typed_ui: bool,
) -> TurnFrame | None:
    try:
        snapshot = frame.model_dump()
    except Exception:
        _mark_runtime_turn_frame_degraded(ctx)
        return None

    ctx[_CTX_FRAME] = snapshot
    ctx[_CTX_STATUS] = status
    ctx.pop(_CTX_REASON, None)
    ctx["typed_ui_turn_frame_used"] = typed_ui
    ctx["turn_planner_used"] = not typed_ui
    _mirror_shadow_telemetry_aliases(ctx, status=status, snapshot=snapshot, reason=None)
    if typed_ui:
        try:
            emit_bot_event(
                logger,
                "typed_ui_turn_frame_used",
                status=RUNTIME_FRAME_STATUS_OK,
                details={
                    "runtime_turn_frame_status": status,
                    "typed_ui_turn_frame_used": True,
                    "topic": frame.topic,
                    "intent": frame.intent,
                    "needs_clarification": frame.needs_clarification,
                },
            )
        except Exception:
            pass
    return frame


def get_runtime_turn_frame_status() -> str | None:
    ctx = _ctx()
    if ctx is None:
        return None
    status = ctx.get(_CTX_STATUS)
    return str(status) if status is not None else None


def load_runtime_turn_frame_snapshot() -> dict[str, object] | None:
    ctx = _ctx()
    if ctx is None:
        return None
    snapshot = ctx.get(_CTX_FRAME)
    if not isinstance(snapshot, dict):
        return None
    return snapshot
