"""C2a runtime TurnFrame contract — offline tests."""

from __future__ import annotations

import pytest
from flask import Flask, request

from contracts.planner_attempt import PlannerAttempt
from contracts.turn_frame import TurnFrame
from core.runtime_turn_frame import (
    RUNTIME_FRAME_STATUS_DEGRADED,
    RUNTIME_FRAME_STATUS_NOT_AVAILABLE,
    RUNTIME_FRAME_STATUS_OK,
    RUNTIME_FRAME_STATUS_PARTIAL,
    get_runtime_turn_frame_status,
    load_runtime_turn_frame_snapshot,
    publish_planner_attempt_frame,
)
from core.target_runtime_turn_frame_bridge import (
    TargetRuntimeTurnFrameError,
    load_runtime_turn_frame,
)
from core.turn_frame_from_raw import build_turn_frame_from_raw


def _frame(**overrides: object) -> TurnFrame:
    raw: dict[str, object] = {
        "route": "content",
        "aspects": ["price"],
        "primary_aspect": "price",
        "service_id": "all_on_4",
        "topic": "implantation",
        "topic_confidence": 0.9,
    }
    raw.update(overrides)
    if overrides.get("aspects") == []:
        raw.pop("primary_aspect", None)
    return build_turn_frame_from_raw(
        raw,
        allowed_topics=frozenset({"implantation"}),
        allowed_service_ids=frozenset({"all_on_4"}),
    )


@pytest.fixture
def flask_ctx():
    app = Flask(__name__)
    with app.test_request_context():
        request.ctx = {}
        yield


def test_publish_ok_frame(flask_ctx) -> None:
    frame = _frame()
    out = publish_planner_attempt_frame(
        attempt=PlannerAttempt(frame=frame, status="ok")
    )
    assert out is frame
    assert get_runtime_turn_frame_status() == RUNTIME_FRAME_STATUS_OK
    snapshot = load_runtime_turn_frame_snapshot()
    assert isinstance(snapshot, dict)
    assert snapshot["service_id"] == "all_on_4"
    assert request.ctx["turn_frame_shadow_status"] == RUNTIME_FRAME_STATUS_OK
    assert request.ctx["turn_frame_shadow"]["service_id"] == "all_on_4"


def test_publish_partial_frame_usable_by_bridge(flask_ctx) -> None:
    frame = _frame(aspects=[])
    publish_planner_attempt_frame(
        attempt=PlannerAttempt(frame=frame, status="partial")
    )
    assert get_runtime_turn_frame_status() == RUNTIME_FRAME_STATUS_PARTIAL
    loaded = load_runtime_turn_frame()
    assert loaded.service_id == "all_on_4"


def test_not_available_fail_closed(flask_ctx) -> None:
    publish_planner_attempt_frame(
        attempt=PlannerAttempt(frame=None, status="not_available")
    )
    assert get_runtime_turn_frame_status() == RUNTIME_FRAME_STATUS_NOT_AVAILABLE
    assert load_runtime_turn_frame_snapshot() is None
    with pytest.raises(TargetRuntimeTurnFrameError):
        load_runtime_turn_frame()


def test_degraded_fail_closed(flask_ctx) -> None:
    publish_planner_attempt_frame(
        attempt=PlannerAttempt(frame=None, status="degraded")
    )
    assert get_runtime_turn_frame_status() == RUNTIME_FRAME_STATUS_DEGRADED
    with pytest.raises(TargetRuntimeTurnFrameError):
        load_runtime_turn_frame()


def test_runtime_keys_in_metadata_first_turn_details(flask_ctx) -> None:
    from core.metadata_first_observability import metadata_first_turn_details

    frame = _frame(aspects=[])
    publish_planner_attempt_frame(
        attempt=PlannerAttempt(frame=frame, status="partial")
    )
    details = metadata_first_turn_details()
    assert details["runtime_turn_frame_status"] == RUNTIME_FRAME_STATUS_PARTIAL
    assert details["runtime_turn_frame"]["service_id"] == "all_on_4"
    assert details["turn_frame_shadow_status"] == RUNTIME_FRAME_STATUS_PARTIAL
