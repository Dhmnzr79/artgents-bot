from __future__ import annotations

import pytest

from contracts.turn_plan import TurnPlan
from session import (
    get_pending_clarify,
    mem_add_user,
    mem_reset,
    set_pending_clarify,
)


def test_clarify_reask_once_then_clears(monkeypatch):
    from orchestration.ask_turn import _pending_clarify_turn_result

    sid = "clarify-reask-once"
    mem_reset(sid)
    set_pending_clarify(
        sid,
        question="Уточню: свой зуб или имплант?",
        option_service_ids=["zirconia_crowns", "implant_supported_prosthetics"],
    )
    monkeypatch.setattr("orchestration.ask_turn.CLARIFY_STATE_ON", True)

    first = _pending_clarify_turn_result(
        q="да",
        sid=sid,
        client_id="demo",
        intent="content",
        decision_frame=None,
    )

    assert first is not None
    assert (first.service_payload or {})["meta"]["clarify"]["reask_count"] == 1
    assert int((get_pending_clarify(sid) or {}).get("reask_count") or 0) == 1

    second = _pending_clarify_turn_result(
        q="да",
        sid=sid,
        client_id="demo",
        intent="content",
        decision_frame=None,
    )

    assert second is None
    assert get_pending_clarify(sid) is None


def test_clarify_stale_age_clears(monkeypatch):
    from orchestration.ask_turn import _pending_clarify_turn_result

    sid = "clarify-stale"
    mem_reset(sid)
    set_pending_clarify(
        sid,
        question="Уточню: свой зуб или имплант?",
        option_service_ids=["zirconia_crowns", "implant_supported_prosthetics"],
    )
    for idx in range(3):
        mem_add_user(sid, f"turn {idx}")
    monkeypatch.setattr("orchestration.ask_turn.CLARIFY_STATE_ON", True)

    result = _pending_clarify_turn_result(
        q="да",
        sid=sid,
        client_id="demo",
        intent="content",
        decision_frame=None,
    )

    assert result is None
    assert get_pending_clarify(sid) is None


def test_clarify_topic_switch_clears(monkeypatch):
    from core.turn_planner_llm import publish_turn_plan
    from orchestration.ask_turn import _pending_clarify_turn_result

    sid = "clarify-topic-switch"
    mem_reset(sid)
    set_pending_clarify(
        sid,
        question="Уточню: свой зуб или имплант?",
        option_service_ids=["zirconia_crowns", "implant_supported_prosthetics"],
    )
    monkeypatch.setattr("orchestration.ask_turn.CLARIFY_STATE_ON", True)
    app = pytest.importorskip("flask").Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        publish_turn_plan(
            TurnPlan(
                route="price_lookup",
                aspects=["price"],
                service_id="veneers",
                followup_of=None,
                needs_clarify=False,
            )
        )
        result = _pending_clarify_turn_result(
            q="а виниры сколько?",
            sid=sid,
            client_id="demo",
            intent="price_lookup",
            decision_frame=None,
        )

    assert result is None
    assert get_pending_clarify(sid) is None


def test_clarify_selected_option_clears(monkeypatch):
    from core.turn_planner_llm import publish_turn_plan
    from orchestration.ask_turn import _pending_clarify_turn_result

    sid = "clarify-selected-option"
    mem_reset(sid)
    set_pending_clarify(
        sid,
        question="Уточню: свой зуб или имплант?",
        option_service_ids=["zirconia_crowns", "implant_supported_prosthetics"],
    )
    monkeypatch.setattr("orchestration.ask_turn.CLARIFY_STATE_ON", True)
    app = pytest.importorskip("flask").Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        publish_turn_plan(
            TurnPlan(
                route="price_lookup",
                aspects=["price"],
                service_id="implant_supported_prosthetics",
                followup_of=None,
                needs_clarify=False,
            )
        )
        result = _pending_clarify_turn_result(
            q="на имплант",
            sid=sid,
            client_id="demo",
            intent="price_lookup",
            decision_frame=None,
        )

    assert result is None
    assert get_pending_clarify(sid) is None


def test_pending_clarify_yields_to_real_question(monkeypatch):
    """Новый содержательный вопрос при pending («а больно ли?») отвечается, а не переспрашивается."""
    import pytest as _pytest
    from contracts.turn_plan import TurnPlan
    from core.turn_planner_llm import publish_turn_plan
    from orchestration.ask_turn import _pending_clarify_turn_result
    from session import get_pending_clarify, mem_reset, set_pending_clarify

    monkeypatch.setattr("orchestration.ask_turn.CLARIFY_STATE_ON", True)
    app = _pytest.importorskip("flask").Flask(__name__)
    sid = "clarify-real-question"
    mem_reset(sid)
    set_pending_clarify(
        sid,
        question="Про какую коронку речь?",
        option_service_ids=["zirconia_crowns", "implant_supported_prosthetics"],
    )
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        publish_turn_plan(
            TurnPlan(route="content", aspects=["pain"], service_id=None, needs_clarify=False)
        )
        result = _pending_clarify_turn_result(
            q="а больно ли ставить?",
            sid=sid,
            client_id="demo",
            intent="content",
            decision_frame=None,
        )

    assert result is None
    assert get_pending_clarify(sid) is None


def test_fullctx_parse_non_json_degrades_to_raw():
    """Не-JSON от модели показывается как текст, а не роняет ход в заглушку."""
    from llm import _parse_packet_composer_fullctx_json
    import json as _json
    import pytest as _pytest

    with _pytest.raises(_json.JSONDecodeError):
        _parse_packet_composer_fullctx_json("просто текст без JSON", client_id="demo")


def test_composer_price_defer_yields_to_clarify(monkeypatch):
    """needs_clarify + нет группового ответа (коронка) → композер получает ход и может спросить."""
    import pytest as _pytest
    from contracts.answer_plan import AnswerPlan
    from contracts.source_route_result import SourceRouteResult
    from contracts.turn_plan import TurnPlan
    from core.turn_planner_llm import publish_turn_plan
    from orchestration.composer_flow import try_composer_overlay

    app = _pytest.importorskip("flask").Flask(__name__)
    monkeypatch.setattr("orchestration.composer_flow.COMPOSER_ON", True)
    monkeypatch.setattr("orchestration.composer_flow.FULLCTX_ON", True)
    monkeypatch.setattr("orchestration.composer_flow.CLARIFY_STATE_ON", True)
    monkeypatch.setattr("orchestration.composer_flow.publish_answer_packet", lambda _p: None)
    monkeypatch.setattr(
        "orchestration.composer_flow._defer_group_price_via_price_route",
        lambda **_k: False,
    )
    monkeypatch.setattr(
        "orchestration.composer_flow._composer_should_defer_jaw_scope_price",
        lambda _q: False,
    )
    monkeypatch.setattr(
        "orchestration.composer_flow.generate_answer_from_packet_fullctx",
        lambda *a, **k: ("Про какую коронку речь?", {"composer_used": True, "clarify": {
            "question": "Про какую коронку речь?",
            "option_service_ids": ["zirconia_crowns", "implant_supported_prosthetics"],
        }}),
    )
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        publish_turn_plan(
            TurnPlan(route="price_lookup", aspects=["price"], service_id=None, needs_clarify=True)
        )
        result = try_composer_overlay(
            q="Сколько стоит коронка?",
            sid="clarify-defer-yield",
            client_id="demo",
            intent="price_lookup",
            plan=AnswerPlan(aspects=["price"], primary_aspect="price", service_id=None),
            sr=SourceRouteResult(source="none", service_id=None, ref=None, match_score=0.0, match_method="none"),
            decision=None,
            decision_frame={},
        )

    assert result is not None
