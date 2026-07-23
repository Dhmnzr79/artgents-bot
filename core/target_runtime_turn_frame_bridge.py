"""Runtime TurnFrame bridge from planner shadow ctx (S61)."""

from __future__ import annotations

from typing import NoReturn

from contracts.turn_frame import TurnFrame
from core.turn_frame_shadow import (
    SHADOW_STATUS_DEGRADED,
    SHADOW_STATUS_NOT_AVAILABLE,
    SHADOW_STATUS_OK,
    SHADOW_STATUS_PARTIAL,
    get_turn_frame_shadow_snapshot,
    get_turn_frame_shadow_status,
)


class TargetRuntimeTurnFrameError(ValueError):
    """Typed fail-closed TurnFrame availability failure for target mode."""

    def __init__(self, code: str, value: object) -> None:
        self.code = code
        self.value = value
        super().__init__(f"{code}: {value!r}")


def _fail(code: str, value: object) -> NoReturn:
    raise TargetRuntimeTurnFrameError(code, value)


def load_runtime_turn_frame() -> TurnFrame:
    """Return the planner-built TurnFrame already stored on the request ctx."""

    status = get_turn_frame_shadow_status()
    if status in {SHADOW_STATUS_NOT_AVAILABLE, SHADOW_STATUS_DEGRADED}:
        _fail("target_runtime_turn_frame_unavailable", status)
    if status not in {SHADOW_STATUS_OK, SHADOW_STATUS_PARTIAL}:
        _fail("target_runtime_turn_frame_unavailable", status)
    snapshot = get_turn_frame_shadow_snapshot()
    if snapshot is None:
        _fail("target_runtime_turn_frame_missing", status)
    try:
        return TurnFrame.model_validate(snapshot)
    except Exception as exc:
        _fail("target_runtime_turn_frame_invalid", type(exc).__name__)
