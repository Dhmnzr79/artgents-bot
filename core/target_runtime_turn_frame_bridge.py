"""Runtime TurnFrame bridge from planner ctx (S61 / C2a native contract)."""

from __future__ import annotations

from typing import NoReturn

from contracts.turn_frame import TurnFrame
from core.runtime_turn_frame import (
    RUNTIME_FRAME_STATUS_DEGRADED,
    RUNTIME_FRAME_STATUS_NOT_AVAILABLE,
    RUNTIME_FRAME_STATUS_OK,
    RUNTIME_FRAME_STATUS_PARTIAL,
    get_runtime_turn_frame_status,
    load_runtime_turn_frame_snapshot,
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
    """Return the planner-built TurnFrame stored on the request ctx."""

    status = get_runtime_turn_frame_status()
    if status in {RUNTIME_FRAME_STATUS_NOT_AVAILABLE, RUNTIME_FRAME_STATUS_DEGRADED}:
        _fail("target_runtime_turn_frame_unavailable", status)
    if status not in {RUNTIME_FRAME_STATUS_OK, RUNTIME_FRAME_STATUS_PARTIAL}:
        _fail("target_runtime_turn_frame_unavailable", status)
    snapshot = load_runtime_turn_frame_snapshot()
    if snapshot is None:
        _fail("target_runtime_turn_frame_missing", status)
    try:
        return TurnFrame.model_validate(snapshot)
    except Exception as exc:
        _fail("target_runtime_turn_frame_invalid", type(exc).__name__)
