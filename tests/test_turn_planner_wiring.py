from __future__ import annotations

import pytest

from contracts.decision_frame import DecisionFrame, DecisionFrameConfidence
from contracts.turn_plan import TurnPlan


def _decision(service_id: str | None = "all_on_4") -> DecisionFrame:
    return DecisionFrame(
        route_intent="price_lookup",
        service_topic="implantation",
        service_id=service_id,
        query_mode="specific",
        confidence=DecisionFrameConfidence(
            intent=0.9,
            topic=0.85,
            service=0.9 if service_id else 0.0,
            query_mode=0.85,
        ),
        needs_clarification=False,
    )


def test_turn_plan_to_decision_frame_is_resolver_compatible():
    from core.turn_planner_llm import turn_plan_to_decision_frame

    plan = TurnPlan(
        route="price_lookup",
        aspects=["price"],
        service_id="all_on_4",
        followup_of="all_on_4",
        needs_clarify=False,
    )

    decision = turn_plan_to_decision_frame(plan, client_id="demo")

    assert decision.route_intent == "price_lookup"
    assert decision.service_topic == "implantation"
    assert decision.service_id == "all_on_4"
    assert decision.query_mode == "specific"
    assert decision.needs_clarification is False


def test_answer_plan_uses_turn_plan_aspects_and_service():
    from core.answer_planner import build_answer_plan
    from core.turn_planner_llm import publish_turn_plan

    app = pytest.importorskip("flask").Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        publish_turn_plan(
            TurnPlan(
                route="content",
                aspects=["payment", "warranty"],
                service_id="all_on_4",
                followup_of=None,
                needs_clarify=False,
            )
        )
        plan = build_answer_plan(
            q="а условия?",
            sid="turn-plan-answer-plan",
            client_id="demo",
            intent="content",
            decision=_decision("all_on_4"),
            source_route=None,
        )

    assert plan.aspects == ["payment", "warranty"]
    assert plan.service_id == "all_on_4"
    assert "payment_terms" in plan.append
    assert "warranty_terms" in plan.append
    assert "turn_planner" in plan.plan_reason


def test_dialog_focus_from_turn_plan_skips_gray_llm(monkeypatch):
    from core.dialog_focus import record_dialog_focus_ctx
    from core.turn_planner_llm import publish_turn_plan
    from session import mem_reset, set_last_subject

    app = pytest.importorskip("flask").Flask(__name__)
    sid = "turn-plan-focus"
    mem_reset(sid)
    set_last_subject(
        sid,
        service_id="all_on_4",
        topic="implantation",
        label="All-on-4",
    )

    def _raise_gray(*_a, **_k):
        raise AssertionError("dialog focus gray-zone LLM must not run under turn planner")

    monkeypatch.setattr("core.dialog_focus_llm.classify_dialog_focus_gray_zone", _raise_gray)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        publish_turn_plan(
            TurnPlan(
                route="price_lookup",
                aspects=["price"],
                service_id="all_on_4",
                followup_of="all_on_4",
                needs_clarify=False,
            )
        )
        focus = record_dialog_focus_ctx(
            "а сколько стоит?",
            sid=sid,
            client_id="demo",
            decision=_decision("all_on_4"),
        )

    assert focus.focus_service_id == "all_on_4"
    assert focus.resolved_service_id == "all_on_4"
    assert focus.attribute == "price"
    assert focus.used_llm is False
    assert focus.source == "last_subject"


def test_detect_aspects_appends_comparison_to_turn_plan():
    from core.answer_planner import detect_aspects
    from core.turn_planner_llm import publish_turn_plan

    app = pytest.importorskip("flask").Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        publish_turn_plan(
            TurnPlan(
                route="content",
                aspects=["overview"],
                service_id="classic",
                followup_of=None,
                needs_clarify=False,
            )
        )
        aspects = detect_aspects(
            "Что лучше — имплант или мост?",
            decision=None,
        )

    assert "comparison" in aspects


def test_detect_aspects_anchors_pain_for_sedation():
    """«во сне»/седация/наркоз — словарь обезболивания; ярлык pain блокирует промо."""
    from core.answer_planner import detect_aspects
    from core.turn_planner_llm import publish_turn_plan

    app = pytest.importorskip("flask").Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        publish_turn_plan(
            TurnPlan(
                route="content",
                aspects=["overview"],
                service_id=None,
                followup_of=None,
                needs_clarify=False,
            )
        )
        aspects = detect_aspects("Можно имплантацию во сне?", decision=None)

    assert "pain" in aspects
