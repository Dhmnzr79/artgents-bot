from __future__ import annotations

import pytest


def test_resolver_turn_planner_failure_uses_safe_content_not_resolver(monkeypatch):
    """P0: planner failure must not fall through to resolve_with_fallback (T8 bug)."""
    from orchestration.resolver_turn import run_resolver_turn

    monkeypatch.setattr("config.TURN_PLANNER_ON", True)
    monkeypatch.setattr("orchestration.resolver_turn.TURN_PLANNER_ON", True)
    monkeypatch.setattr("orchestration.resolver_turn.is_resolver_bypassed_env", lambda: False)

    resolve_calls: list[str] = []

    def _boom_resolve(*_a, **_k):
        resolve_calls.append("resolve_with_fallback")
        raise AssertionError("resolver must not run when planner failed under TURN_PLANNER_ON")

    monkeypatch.setattr("orchestration.resolver_turn.resolve_with_fallback", _boom_resolve)
    monkeypatch.setattr("core.turn_planner_llm.plan_turn", lambda *_a, **_k: None)

    app = pytest.importorskip("flask").Flask(__name__)
    traces: list[object] = []

    def _trace(**kwargs):
        traces.append(kwargs)

    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        outcome = run_resolver_turn(
            q="Боюсь, что имплант не приживётся",
            sid="p0-safe-default",
            client_id="demo",
            st={"hist": []},
            enqueue_resolver_trace=_trace,
        )
        ctx_snapshot = dict(request.ctx)

    assert not resolve_calls
    assert outcome.intent == "content"
    assert outcome.decision is not None
    assert outcome.decision.route_intent == "content"
    assert ctx_snapshot.get("turn_planner_safe_default") is True
    assert ctx_snapshot.get("resolver_used") is False
    assert ctx_snapshot.get("turn_plan_emotion") == "none"
