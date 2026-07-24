from __future__ import annotations

import pytest

from contracts.dialog_focus import DialogFocusDecision
from contracts.source_route_result import SourceRouteResult
from core.answer_planner import build_answer_plan, detect_aspects
from session import mem_reset
from tests.test_s61_correction_target_runtime import _seed_target_runtime_state


def test_detect_aspects_price_and_payment():
    aspects = detect_aspects("Сколько стоит имплант и есть ли рассрочка?")
    assert "price" in aspects
    assert "payment" in aspects


def test_build_answer_plan_composite_append():
    plan = build_answer_plan(
        q="Сколько стоит classic с коронкой и можно ли в рассрочку?",
        sid="t1",
        client_id="demo",
        intent="content",
        decision=None,
        source_route=None,
    )
    assert "price" in plan.aspects
    assert "payment" in plan.aspects
    assert "payment_terms" in plan.append


def test_build_answer_plan_adds_warranty_append_for_service_question():
    plan = build_answer_plan(
        q="А вы делаете all-on-4 и какие гарантии на нее?",
        sid="t_all_on_4_warranty",
        client_id="demo",
        intent="content",
        decision=None,
        source_route=SourceRouteResult(
            source="catalog_md",
            service_id="all_on_4",
            ref="implantation__service__all_on_4.md#korotko",
            match_score=1.0,
            match_method="catalog_containment",
        ),
    )
    assert "warranty" in plan.aspects
    assert "warranty_terms" in plan.append
    assert plan.service_id == "all_on_4"


def test_primary_aspect_only_from_current_question():
    plan = build_answer_plan(
        q="а это?",
        sid="t_no_carry",
        client_id="demo",
        intent="content",
        decision=None,
        source_route=None,
    )
    assert plan.aspects == ["overview"]
    assert plan.primary_aspect is None
    assert plan.append == []


def test_follow_up_payment_uses_target_runtime_state():
    sid = "t_follow_payment"
    mem_reset(sid)
    _seed_target_runtime_state(
        sid,
        last_service_id="classic",
        last_topic="implantation",
        service_focus_set_at_turn=0,
    )
    plan = build_answer_plan(
        q="рассрочка?",
        sid=sid,
        client_id="demo",
        intent="content",
        decision=None,
        source_route=None,
    )
    assert plan.service_id == "classic"
    assert "payment" in plan.aspects
    assert "payment_terms" in plan.append
    assert "price_offer" not in plan.append


def test_planner_uses_dialog_focus_for_attribute_without_session_subject():
    app = pytest.importorskip("flask").Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {
            "dialog_focus_decision": DialogFocusDecision(
                focus_service_id="classic",
                focus_topic="implantation",
                focus_label="Классическая имплантация",
                focus_turn_age=0,
                attribute="warranty",
                explicit_topic_change=False,
                resolved_service_id="classic",
                source="target_runtime_state",
                used_llm=False,
                confidence=0.8,
                reason="test",
            ).model_dump()
        }
        plan = build_answer_plan(
            q="Гарантия какая?",
            sid="planner-dialog-focus",
            client_id="demo",
            intent="content",
            decision=None,
            source_route=None,
        )
    assert plan.service_id == "classic"
    assert "warranty" in plan.aspects
    assert "dialog_focus" in plan.plan_reason
