from __future__ import annotations

import pytest

from contracts.answer_plan import AnswerPlan
from contracts.decision_frame import DecisionFrame, DecisionFrameConfidence
from contracts.source_route_result import SourceRouteResult
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


def test_composer_uses_turn_plan_service_without_service_selector(monkeypatch):
    from core.turn_planner_llm import publish_turn_plan
    from orchestration.composer_flow import try_composer_overlay

    app = pytest.importorskip("flask").Flask(__name__)
    monkeypatch.setattr("orchestration.composer_flow.COMPOSER_ON", True)
    monkeypatch.setattr("orchestration.composer_flow.FULLCTX_ON", True)
    monkeypatch.setattr("orchestration.composer_flow.SERVICE_SELECT_LLM_ON", True)
    monkeypatch.setattr("orchestration.composer_flow.publish_answer_packet", lambda _p: None)
    monkeypatch.setattr(
        "orchestration.composer_flow.classify_service",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("selector skipped")),
    )
    monkeypatch.setattr(
        "orchestration.composer_flow.generate_answer_from_packet_fullctx",
        lambda *a, **k: ("composed", {"composer_used": True}),
    )
    monkeypatch.setattr(
        "orchestration.composer_flow._composer_should_defer_jaw_scope_price",
        lambda _q: False,
    )

    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        publish_turn_plan(
            TurnPlan(
                route="price_lookup",
                aspects=["price"],
                service_id="tooth_extraction",
                followup_of=None,
                needs_clarify=False,
            )
        )
        result = try_composer_overlay(
            q="Больно ли удалять зуб и сколько это стоит?",
            sid="turn-plan-composer",
            client_id="demo",
            intent="price_lookup",
            plan=AnswerPlan(
                aspects=["price"],
                primary_aspect="price",
                service_id="pulpitis",
                topic="treatment",
            ),
            sr=SourceRouteResult(
                source="catalog_md",
                service_id="pulpitis",
                ref="treatment__service__pulpitis.md#korotko",
                match_score=1.0,
                match_method="catalog_containment",
            ),
            decision=_decision(None),
            decision_frame={},
        )

    assert result is not None
    assert result.matched_service_id == "tooth_extraction"


def test_composer_defers_when_turn_plan_price_service_is_null(monkeypatch):
    from core.turn_planner_llm import publish_turn_plan
    from orchestration.composer_flow import try_composer_overlay

    app = pytest.importorskip("flask").Flask(__name__)
    monkeypatch.setattr("orchestration.composer_flow.COMPOSER_ON", True)
    monkeypatch.setattr("orchestration.composer_flow.FULLCTX_ON", True)
    monkeypatch.setattr("orchestration.composer_flow.SERVICE_SELECT_LLM_ON", True)
    monkeypatch.setattr(
        "orchestration.composer_flow.classify_service",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("selector skipped")),
    )
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        publish_turn_plan(
            TurnPlan(
                route="price_lookup",
                aspects=["price"],
                service_id=None,
                followup_of=None,
                needs_clarify=True,
            )
        )
        result = try_composer_overlay(
            q="Сколько стоит имплантация?",
            sid="turn-plan-composer-null",
            client_id="demo",
            intent="price_lookup",
            plan=AnswerPlan(aspects=["price"], primary_aspect="price", service_id=None),
            sr=SourceRouteResult(
                source="none",
                service_id=None,
                ref=None,
                match_score=0.0,
                match_method="none",
            ),
            decision=_decision(None),
            decision_frame={},
        )

    assert result is None


def _composer_env(monkeypatch):
    monkeypatch.setattr("orchestration.composer_flow.COMPOSER_ON", True)
    monkeypatch.setattr("orchestration.composer_flow.FULLCTX_ON", True)
    monkeypatch.setattr("orchestration.composer_flow.SERVICE_SELECT_LLM_ON", True)
    monkeypatch.setattr("orchestration.composer_flow.publish_answer_packet", lambda _p: None)
    monkeypatch.setattr(
        "orchestration.composer_flow.classify_service",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("selector skipped")),
    )
    monkeypatch.setattr(
        "orchestration.composer_flow.generate_answer_from_packet_fullctx",
        lambda *a, **k: ("composed", {"composer_used": True}),
    )
    monkeypatch.setattr(
        "orchestration.composer_flow._composer_should_defer_jaw_scope_price",
        lambda _q: False,
    )


def test_composer_plan_null_service_is_final_no_fuzzy_fallback(monkeypatch):
    """Plan svc=None on non-price aspect: composer proceeds with service=None,
    fuzzy sr.service_id (all_on_4-style bias) must NOT leak into the packet."""
    from core.turn_planner_llm import publish_turn_plan
    from orchestration.composer_flow import try_composer_overlay

    app = pytest.importorskip("flask").Flask(__name__)
    _composer_env(monkeypatch)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        publish_turn_plan(
            TurnPlan(
                route="content",
                aspects=["payment"],
                service_id=None,
                followup_of=None,
                needs_clarify=False,
            )
        )
        result = try_composer_overlay(
            q="Есть рассрочка на имплантацию?",
            sid="turn-plan-null-final",
            client_id="demo",
            intent="content",
            plan=AnswerPlan(aspects=["payment"], primary_aspect="payment", service_id="all_on_4"),
            sr=SourceRouteResult(
                source="catalog_md",
                service_id="all_on_4",
                ref="implantation__service__all_on_4.md#korotko",
                match_score=0.9,
                match_method="catalog_containment",
            ),
            decision=_decision("all_on_4"),
            decision_frame={},
        )

    assert result is not None
    assert result.matched_service_id is None


def test_composer_included_without_service_proceeds(monkeypatch):
    """Plan svc=None + aspect included: answer comes from KB, no defer to price."""
    from core.turn_planner_llm import publish_turn_plan
    from orchestration.composer_flow import try_composer_overlay

    app = pytest.importorskip("flask").Flask(__name__)
    _composer_env(monkeypatch)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        publish_turn_plan(
            TurnPlan(
                route="content",
                aspects=["included"],
                service_id=None,
                followup_of=None,
                needs_clarify=True,
            )
        )
        result = try_composer_overlay(
            q="Коронка входит в цену импланта?",
            sid="turn-plan-included",
            client_id="demo",
            intent="content",
            plan=AnswerPlan(aspects=["included"], primary_aspect="included", service_id=None),
            sr=SourceRouteResult(
                source="none", service_id=None, ref=None, match_score=0.0, match_method="none"
            ),
            decision=_decision(None),
            decision_frame={},
        )

    assert result is not None


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
