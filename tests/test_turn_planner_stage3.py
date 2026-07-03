from __future__ import annotations

import pytest

from contracts.turn_plan import TurnPlan


def test_patient_situation_uses_turn_plan_before_regex():
    from core.patient_situation_session import resolve_patient_situation_for_turn
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
                patient_situation="full_arch_missing",
            )
        )
        result, meta = resolve_patient_situation_for_turn(
            "что мне подойдет?",
            sid="turn-plan-patient-situation",
            client_id="demo",
        )

    assert result.kind == "full_arch_missing"
    assert result.patient_scope == "full_jaw"
    assert result.source == "llm_fallback"
    assert "turn_planner" in result.evidence
    assert meta["patient_situation_source"] == "turn_planner"


def test_price_fact_block_filters_by_turn_plan_brand_group():
    from core.answer_packet_materialize import render_price_fact_block
    from core.turn_planner_llm import publish_turn_plan

    app = pytest.importorskip("flask").Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        publish_turn_plan(
            TurnPlan(
                route="price_lookup",
                aspects=["price"],
                service_id="classic",
                followup_of=None,
                needs_clarify=False,
                brand_filter={"brand_group": "korean"},
            )
        )
        text = render_price_fact_block(client_id="demo", service_id="classic")

    assert text is not None
    assert "Implantium" in text
    assert "Impro" not in text
    assert "Nobel" not in text
    assert "76 200" in text


def test_price_answer_lookup_filters_by_turn_plan_brand_group():
    from core.price_offers import build_price_answer_for_lookup
    from core.turn_planner_llm import publish_turn_plan

    app = pytest.importorskip("flask").Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        publish_turn_plan(
            TurnPlan(
                route="price_lookup",
                aspects=["price"],
                service_id="classic",
                followup_of=None,
                needs_clarify=False,
                brand_filter={"brand_group": "korean"},
            )
        )
        answer, meta = build_price_answer_for_lookup(
            client_id="demo",
            service_id="classic",
            q="сколько стоят корейские импланты",
        )

    assert answer is not None
    assert "Implantium" in answer
    assert "76 200" in answer
    # T1: фильтр проверяем по структуре (какие офферы разрешены), а не по словам —
    # факты из базы (гарантия «на Impro и Nobel — пожизненная») остаются дословно.
    assert meta["price_offer_ids"] == ["classic.one_tooth.implantium"]
    assert meta["price_offer_brand_group_filter"] == "korean"
