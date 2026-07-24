"""C2b offline: one planner call, zero resolver calls."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from flask import Flask, request

from contracts.planner_attempt import PlannerAttempt
from contracts.turn_frame import TurnFrame
from core.turn_frame_from_raw import build_turn_frame_from_raw
from orchestration.planner_turn import run_planner_turn


def _frame() -> TurnFrame:
    return build_turn_frame_from_raw(
        {
            "route": "content",
            "aspects": ["price"],
            "primary_aspect": "price",
            "service_id": "all_on_4",
            "topic": "implantation",
            "topic_confidence": 0.9,
        },
        allowed_topics=frozenset({"implantation"}),
        allowed_service_ids=frozenset({"all_on_4"}),
    )


def test_planner_turn_one_call_zero_resolver(monkeypatch: pytest.MonkeyPatch) -> None:
    planner_calls = 0
    resolver = MagicMock()
    frame = _frame()

    def _plan(*_a, **_k):
        nonlocal planner_calls
        planner_calls += 1
        return PlannerAttempt(frame=frame, status="ok")

    monkeypatch.setattr("orchestration.planner_turn.plan_turn_attempt", _plan)
    monkeypatch.setattr("resolver.resolve_with_fallback", resolver)

    app = Flask(__name__)
    with app.test_request_context("/"):
        request.ctx = {}
        outcome = run_planner_turn(
            q="сколько стоит all-on-4?",
            sid="c2b-spy",
            client_id="demo",
            st={"hist": []},
            enqueue_resolver_trace=lambda **_kwargs: None,
        )
        assert planner_calls == 1
        resolver.assert_not_called()
        assert request.ctx["resolver_used"] is False
        assert request.ctx["turn_planner_used"] is True
        assert outcome.intent in {"content", "price_lookup"}


def test_partial_frame_no_resolver(monkeypatch: pytest.MonkeyPatch) -> None:
    frame = build_turn_frame_from_raw(
        {"route": "content", "aspects": [], "topic": "doctors", "topic_confidence": 0.95},
        allowed_topics=frozenset({"doctors"}),
    )
    resolver = MagicMock()
    monkeypatch.setattr(
        "orchestration.planner_turn.plan_turn_attempt",
        lambda *_a, **_k: PlannerAttempt(frame=frame, status="partial"),
    )
    monkeypatch.setattr("resolver.resolve_with_fallback", resolver)

    app = Flask(__name__)
    with app.test_request_context("/"):
        request.ctx = {}
        run_planner_turn(
            q="кто делает?",
            sid="c2b-partial",
            client_id="demo",
            st={},
            enqueue_resolver_trace=lambda **_kwargs: None,
        )
        resolver.assert_not_called()
        assert request.ctx["turn_planner_used"] is True
        assert request.ctx["resolver_used"] is False


def test_not_available_fail_closed_no_resolver(monkeypatch: pytest.MonkeyPatch) -> None:
    resolver = MagicMock()
    monkeypatch.setattr(
        "orchestration.planner_turn.plan_turn_attempt",
        lambda *_a, **_k: PlannerAttempt(frame=None, status="not_available"),
    )
    monkeypatch.setattr("resolver.resolve_with_fallback", resolver)

    app = Flask(__name__)
    with app.test_request_context("/"):
        request.ctx = {}
        run_planner_turn(
            q="test",
            sid="c2b-na",
            client_id="demo",
            st={},
            enqueue_resolver_trace=lambda **_kwargs: None,
        )
        resolver.assert_not_called()
        assert request.ctx["turn_planner_used"] is False
        assert request.ctx["resolver_used"] is False
