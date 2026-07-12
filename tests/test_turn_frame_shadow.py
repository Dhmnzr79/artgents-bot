from __future__ import annotations

import inspect
from unittest.mock import patch

import pytest

from contracts.decision_frame import DecisionFrame, DecisionFrameConfidence
from contracts.turn_plan import TurnPlan
from core.turn_frame_adapter import build_turn_frame_from_legacy
from core.turn_frame_shadow import (
    SHADOW_REASON_BUILD_FAILED,
    SHADOW_REASON_TURN_PLAN_MISSING,
    SHADOW_STATUS_DEGRADED,
    SHADOW_STATUS_NOT_AVAILABLE,
    SHADOW_STATUS_OK,
    mark_turn_frame_shadow_not_available,
    record_turn_frame_shadow,
)
from orchestration.resolver_turn import run_resolver_turn


def _decision(**overrides) -> DecisionFrame:
    payload = {
        "route_intent": "price_lookup",
        "service_topic": "implantation",
        "service_id": "all_on_4",
        "query_mode": "specific",
        "confidence": {
            "intent": 0.9,
            "topic": 0.85,
            "service": 0.9,
            "query_mode": 0.85,
        },
        "needs_clarification": False,
    }
    payload.update(overrides)
    return DecisionFrame.model_validate(payload)


def _turn_plan(**overrides) -> TurnPlan:
    payload = {
        "route": "price_lookup",
        "aspects": ["price"],
        "service_id": "all_on_4",
        "followup_of": "all_on_4",
        "needs_clarify": False,
    }
    payload.update(overrides)
    return TurnPlan.model_validate(payload)


def test_record_turn_frame_shadow_ok_writes_dump_and_status() -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    turn_plan = _turn_plan()
    decision = _decision()
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {"turn_frame_shadow_reason": "stale"}
        frame = record_turn_frame_shadow(turn_plan=turn_plan, decision_frame=decision)

        assert frame is not None
        assert request.ctx["turn_frame_shadow_status"] == SHADOW_STATUS_OK
        assert request.ctx["turn_frame_shadow"] == frame.model_dump()
        assert "turn_frame_shadow_reason" not in request.ctx


def test_record_turn_frame_shadow_snapshot_has_field_meta_from_adapter() -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    turn_plan = _turn_plan()
    decision = _decision()
    expected = build_turn_frame_from_legacy(turn_plan=turn_plan, decision_frame=decision)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        record_turn_frame_shadow(turn_plan=turn_plan, decision_frame=decision)

        snapshot = request.ctx["turn_frame_shadow"]
        assert snapshot == expected.model_dump()
        assert snapshot["field_meta"]["emotion"]["provenance"] == "default"
        assert snapshot["field_meta"]["intent"]["provenance"] == "decision_frame.route_intent"


def test_mark_turn_frame_shadow_not_available() -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {"turn_frame_shadow": {"intent": "content"}}
        mark_turn_frame_shadow_not_available()

        assert request.ctx["turn_frame_shadow_status"] == SHADOW_STATUS_NOT_AVAILABLE
        assert request.ctx["turn_frame_shadow_reason"] == SHADOW_REASON_TURN_PLAN_MISSING
        assert "turn_frame_shadow" not in request.ctx


def test_record_turn_frame_shadow_degraded_isolates_builder_failure(monkeypatch) -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    turn_plan = _turn_plan()
    decision = _decision()

    def _boom(**_kwargs):
        raise RuntimeError("secret builder failure with user text")

    monkeypatch.setattr("core.turn_frame_shadow.build_turn_frame_from_legacy", _boom)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        frame = record_turn_frame_shadow(turn_plan=turn_plan, decision_frame=decision)

        assert frame is None
        assert request.ctx["turn_frame_shadow_status"] == SHADOW_STATUS_DEGRADED
        assert request.ctx["turn_frame_shadow_reason"] == SHADOW_REASON_BUILD_FAILED
        assert "turn_frame_shadow" not in request.ctx


def test_record_turn_frame_shadow_degraded_emits_structured_event_without_leaks(
    monkeypatch,
) -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    turn_plan = _turn_plan()
    decision = _decision()
    captured: list[dict] = []

    def _capture(_logger, event_name, *, status=None, details=None, **_kwargs):
        captured.append(
            {
                "event_name": event_name,
                "status": status,
                "details": details or {},
            }
        )

    monkeypatch.setattr(
        "core.turn_frame_shadow.build_turn_frame_from_legacy",
        lambda **_kwargs: (_ for _ in ()).throw(ValueError("leaked exception detail")),
    )
    monkeypatch.setattr("core.turn_frame_shadow.emit_bot_event", _capture)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        record_turn_frame_shadow(turn_plan=turn_plan, decision_frame=decision)

    assert len(captured) == 1
    event = captured[0]
    assert event["event_name"] == "turn_frame_shadow"
    assert event["status"] == SHADOW_STATUS_DEGRADED
    assert event["details"]["turn_frame_shadow_status"] == SHADOW_STATUS_DEGRADED
    assert event["details"]["turn_frame_shadow_reason"] == SHADOW_REASON_BUILD_FAILED
    payload = str(event)
    assert "leaked exception detail" not in payload


def test_shadow_recorder_signatures_exclude_question_like_params() -> None:
    forbidden = {"question", "answer", "history", "payload", "q"}
    for fn in (record_turn_frame_shadow, mark_turn_frame_shadow_not_available):
        params = set(inspect.signature(fn).parameters)
        assert params.isdisjoint(forbidden)


def test_run_resolver_turn_planner_success_records_shadow(monkeypatch) -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    turn_plan = _turn_plan()
    monkeypatch.setattr("orchestration.resolver_turn.TURN_PLANNER_ON", True)
    monkeypatch.setattr("core.turn_planner_llm.plan_turn", lambda *_a, **_k: turn_plan)
    monkeypatch.setattr("core.turn_planner_llm.publish_turn_plan", lambda _p: None)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        run_resolver_turn(
            q="сколько стоит all-on-4?",
            sid="shadow-success",
            client_id="demo",
            st={},
            enqueue_resolver_trace=lambda **_k: None,
        )

        assert request.ctx["turn_frame_shadow_status"] == SHADOW_STATUS_OK
        assert isinstance(request.ctx.get("turn_frame_shadow"), dict)
        assert request.ctx["turn_frame_shadow"]["service_id"] == "all_on_4"


def test_run_resolver_turn_does_not_replace_decision_or_intent(monkeypatch) -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    from core.turn_planner_llm import turn_plan_to_decision_frame

    turn_plan = _turn_plan()
    expected_decision = turn_plan_to_decision_frame(turn_plan, client_id="demo")
    monkeypatch.setattr("orchestration.resolver_turn.TURN_PLANNER_ON", True)
    monkeypatch.setattr("core.turn_planner_llm.plan_turn", lambda *_a, **_k: turn_plan)
    monkeypatch.setattr("core.turn_planner_llm.publish_turn_plan", lambda _p: None)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        outcome = run_resolver_turn(
            q="сколько стоит?",
            sid="shadow-no-replace",
            client_id="demo",
            st={},
            enqueue_resolver_trace=lambda **_k: None,
        )

        assert outcome.decision.model_dump() == expected_decision.model_dump()
        assert outcome.intent == "price_lookup"
        assert isinstance(request.ctx.get("turn_frame_shadow"), dict)


def test_run_resolver_turn_planner_missing_marks_not_available_before_resolver(monkeypatch) -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    resolver_calls: list[str] = []
    fallback_decision = _decision(route_intent="content", query_mode="overview")

    def _resolve_with_fallback(**_kwargs):
        resolver_calls.append("called")
        return fallback_decision, [], "content"

    monkeypatch.setattr("orchestration.resolver_turn.TURN_PLANNER_ON", True)
    monkeypatch.setattr("core.turn_planner_llm.plan_turn", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "orchestration.resolver_turn.resolve_with_fallback",
        _resolve_with_fallback,
    )
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        run_resolver_turn(
            q="сколько стоит?",
            sid="shadow-missing-plan",
            client_id="demo",
            st={"hist": []},
            enqueue_resolver_trace=lambda **_k: None,
        )

        assert request.ctx["turn_frame_shadow_status"] == SHADOW_STATUS_NOT_AVAILABLE
        assert request.ctx["turn_frame_shadow_reason"] == SHADOW_REASON_TURN_PLAN_MISSING
        assert "turn_frame_shadow" not in request.ctx
        assert resolver_calls == ["called"]


def test_run_resolver_turn_comparison_override_reflected_in_shadow(monkeypatch) -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    from core.turn_planner_llm import turn_plan_to_decision_frame

    turn_plan = _turn_plan(route="content", aspects=["overview"])
    pre_override_decision = turn_plan_to_decision_frame(turn_plan, client_id="demo")
    assert pre_override_decision.query_mode != "comparison"

    comparison_question = "что лучше all-on-4 или 6?"
    expected_shadow = build_turn_frame_from_legacy(
        turn_plan=turn_plan,
        decision_frame=pre_override_decision.model_copy(update={"query_mode": "comparison"}),
    )

    monkeypatch.setattr("orchestration.resolver_turn.TURN_PLANNER_ON", True)
    monkeypatch.setattr("core.turn_planner_llm.plan_turn", lambda *_a, **_k: turn_plan)
    monkeypatch.setattr("core.turn_planner_llm.publish_turn_plan", lambda _p: None)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        outcome = run_resolver_turn(
            q=comparison_question,
            sid="shadow-comparison-override",
            client_id="demo",
            st={},
            enqueue_resolver_trace=lambda **_k: None,
        )

        assert outcome.decision.query_mode == "comparison"
        assert request.ctx["turn_frame_shadow_status"] == SHADOW_STATUS_OK
        assert request.ctx["turn_frame_shadow"] == expected_shadow.model_dump()
        assert request.ctx["turn_frame_shadow"]["specificity"] == "general"


def test_record_turn_frame_shadow_degraded_on_model_dump_failure(monkeypatch) -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    turn_plan = _turn_plan()
    decision = _decision()

    class _FrameWithBadDump:
        def model_dump(self):
            raise RuntimeError("serialization exploded with secret")

    monkeypatch.setattr(
        "core.turn_frame_shadow.build_turn_frame_from_legacy",
        lambda **_kwargs: _FrameWithBadDump(),
    )
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        frame = record_turn_frame_shadow(turn_plan=turn_plan, decision_frame=decision)

        assert frame is None
        assert request.ctx["turn_frame_shadow_status"] == SHADOW_STATUS_DEGRADED
        assert request.ctx["turn_frame_shadow_reason"] == SHADOW_REASON_BUILD_FAILED
        assert "turn_frame_shadow" not in request.ctx
        assert "serialization exploded" not in str(request.ctx)


def test_record_turn_frame_shadow_degraded_survives_emit_bot_event_failure(monkeypatch) -> None:
    app = pytest.importorskip("flask").Flask(__name__)
    turn_plan = _turn_plan()
    decision = _decision()

    monkeypatch.setattr(
        "core.turn_frame_shadow.build_turn_frame_from_legacy",
        lambda **_kwargs: (_ for _ in ()).throw(ValueError("builder failed")),
    )

    def _emit_boom(*_args, **_kwargs):
        raise RuntimeError("telemetry sink unavailable")

    monkeypatch.setattr("core.turn_frame_shadow.emit_bot_event", _emit_boom)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        frame = record_turn_frame_shadow(turn_plan=turn_plan, decision_frame=decision)

        assert frame is None
        assert request.ctx["turn_frame_shadow_status"] == SHADOW_STATUS_DEGRADED
        assert request.ctx["turn_frame_shadow_reason"] == SHADOW_REASON_BUILD_FAILED
        assert "turn_frame_shadow" not in request.ctx
