from __future__ import annotations

import pytest

from contracts.turn_plan import TurnPlan


def _publish_turn_plan_ctx(plan: TurnPlan) -> None:
    from flask import request

    request.ctx["turn_plan"] = plan.model_dump()


@pytest.fixture
def brand_on(monkeypatch):
    monkeypatch.setenv("BRAND_FILTER_ON", "1")
    monkeypatch.setattr("config.BRAND_FILTER_ON", True)


def test_patient_situation_uses_turn_plan_before_regex():
    from core.patient_situation_session import resolve_patient_situation_for_turn

    app = pytest.importorskip("flask").Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        _publish_turn_plan_ctx(
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


def test_price_answer_lookup_filters_by_turn_plan_brand_group(brand_on):
    from core.price_offers import build_price_answer_for_lookup

    app = pytest.importorskip("flask").Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {}
        _publish_turn_plan_ctx(
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
    assert meta["price_offer_ids"] == ["classic.one_tooth.implantium"]
    assert meta["price_offer_brand_group_filter"] == "korean"
