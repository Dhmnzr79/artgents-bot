"""Brand filter money-path — BRAND_FILTER_ON gate (planner brand + budget anchor)."""
from __future__ import annotations

import uuid

import pytest

from contracts.turn_plan import TurnPlan
from core.price_brand_money import (
    brand_filter_enabled,
    build_budget_anchor_brief,
    build_budget_anchor_card,
    build_budget_anchor_payload,
    classify_brand_money_path,
    resolve_brand_filter,
    try_brand_money_early,
    try_brand_money_orchestration,
)
from core.price_offers import build_price_answer_for_lookup as _build_price_lookup
from core.turn_planner_llm import publish_turn_plan, _validate_plan
from query_selector import select_price_service_route
from session import mem_reset


@pytest.fixture
def brand_on(monkeypatch):
    monkeypatch.setenv("BRAND_FILTER_ON", "1")
    monkeypatch.setattr("config.BRAND_FILTER_ON", True)


@pytest.fixture
def brand_off(monkeypatch):
    monkeypatch.setenv("BRAND_FILTER_ON", "0")
    monkeypatch.setattr("config.BRAND_FILTER_ON", False)


def _publish_brand_filter(*, brand: str | None = None, brand_group: str | None = None) -> None:
    bf: dict[str, str | None] | None = None
    if brand or brand_group:
        bf = {"brand": brand, "brand_group": brand_group}
    publish_turn_plan(
        TurnPlan(
            route="price_lookup",
            aspects=["price"],
            service_id="classic",
            followup_of=None,
            needs_clarify=False,
            brand_filter=bf,
        )
    )


def _flask_ctx():
    app = pytest.importorskip("flask").Flask(__name__)
    return app.test_request_context("/")


def test_brand_on_flag():
    assert brand_filter_enabled() is False  # default in test env unless fixture


def test_korean_implants_live_phrase(brand_on):
    q = "сколько стоят корейские импланты?"
    route = select_price_service_route(q, client_id="demo", intent_override="price_lookup")
    with _flask_ctx():
        from flask import request

        request.ctx = {}
        _publish_brand_filter(brand_group="korean")
        assert classify_brand_money_path(q, route, client_id="demo") == "explicit_brand"
        answer, meta = _build_price_lookup(
            client_id="demo",
            service_id="classic",
            q=q,
        )
    assert answer is not None
    assert "76 200" in answer
    assert meta["price_offer_ids"] == ["classic.one_tooth.implantium"]


def test_korean_literal_without_planner(brand_on):
    q = "корейские импланты сколько стоят?"
    route = select_price_service_route(q, client_id="demo", intent_override="price_lookup")
    with _flask_ctx():
        from flask import request

        request.ctx = {}
        assert classify_brand_money_path(q, route, client_id="demo") == "explicit_brand"
        result = try_brand_money_orchestration(
            q=q,
            sid="kr-lit",
            client_id="demo",
            price_route=route,
            decision_frame=None,
        )
    assert result is not None
    meta = (result.service_payload or {}).get("meta") or {}
    assert meta.get("brand_money_path") == "explicit_brand"
    assert meta.get("price_offer_ids") == ["classic.one_tooth.implantium"]


def test_budget_phrase_wins_over_planner_korean_inference(brand_on):
    q = "какие импланты подешевле?"
    route = select_price_service_route(q, client_id="demo")
    with _flask_ctx():
        from flask import request

        request.ctx = {}
        _publish_brand_filter(brand_group="korean")
        assert classify_brand_money_path(q, route, client_id="demo") == "budget_anchor"
        result = try_brand_money_early(q=q, sid="budget-planner", client_id="demo", decision_frame=None)
    assert result is not None
    assert result.service_route == "price_brand_budget_anchor"
    meta = (result.service_payload or {}).get("meta") or {}
    ids = meta.get("price_offer_ids") or []
    assert len(ids) == 2
    assert "76200" in str(meta.get("composer_brief") or "").replace(" ", "") or "76 200" in str(
        meta.get("composer_brief") or ""
    )
    assert "85200" in str(meta.get("composer_brief") or "").replace(" ", "") or "85 200" in str(
        meta.get("composer_brief") or ""
    )


def test_nobel_conversational_without_planner(brand_on):
    q = "сколько нобель"
    route = select_price_service_route(q, client_id="demo", intent_override="price_lookup")
    with _flask_ctx():
        from flask import request

        request.ctx = {}
        brand, group = resolve_brand_filter(q, client_id="demo")
        assert brand == "Nobel Biocare"
        assert group is None
        result = try_brand_money_orchestration(
            q=q,
            sid="nobel-live",
            client_id="demo",
            price_route=route,
            decision_frame=None,
        )
    assert result is not None
    assert (result.service_payload or {}).get("meta", {}).get("brand_money_path") == "explicit_brand"
    assert "101 200" in (result.service_payload or {}).get("answer", "")


def test_nobel_with_implants_phrase(brand_on):
    q = "сколько стоят импланты нобель?"
    route = select_price_service_route(q, client_id="demo", intent_override="price_lookup")
    assert classify_brand_money_path(q, route, client_id="demo") == "explicit_brand"
    with _flask_ctx():
        from flask import request

        request.ctx = {}
        result = try_brand_money_early(
            q=q,
            sid="nobel-impl",
            client_id="demo",
            decision_frame=None,
        )
    assert result is not None
    meta = (result.service_payload or {}).get("meta") or {}
    assert meta.get("brand_money_path") == "explicit_brand"
    assert meta.get("price_offer_ids") == ["classic.one_tooth.nobel"]


@pytest.mark.parametrize(
    ("q", "expected_total"),
    [
        ("сколько impro", "85 200"),
        ("сколько стоит имплантиум", "76 200"),
    ],
)
def test_conversational_brand_aliases(brand_on, q, expected_total):
    route = select_price_service_route(q, client_id="demo", intent_override="price_lookup")
    assert classify_brand_money_path(q, route, client_id="demo") == "explicit_brand"
    with _flask_ctx():
        from flask import request

        request.ctx = {}
        result = try_brand_money_orchestration(
            q=q,
            sid=f"alias-{expected_total}",
            client_id="demo",
            price_route=route,
            decision_frame=None,
        )
    assert result is not None
    answer = (result.service_payload or {}).get("answer") or ""
    assert expected_total in answer


def test_cheap_implants_budget_anchor_two_brands(brand_on):
    q = "дешёвые импланты"
    route = select_price_service_route(q, client_id="demo", intent_override="price_lookup")
    assert classify_brand_money_path(q, route, client_id="demo") == "budget_anchor"
    card, meta = build_budget_anchor_card(client_id="demo")
    assert len(meta.get("price_offer_ids") or []) == 2
    assert "76 200" in card
    assert "85 200" in card


def test_which_implants_cheaper_budget_anchor_live_phrase(brand_on, monkeypatch):
    woven = (
        "Понимаю, что хочется найти более доступный вариант имплантации. "
        "Самый бюджетный вариант «один зуб» — Implantium за 76 200 ₽. "
        "Если важнее баланс качества и цены, Impro — 85 200 ₽. "
        "Доступна рассрочка от клиники до 12 месяцев, можно оформить налоговый вычет 13% "
        "от оплаченного лечения, при оплате в день обращения — скидка до 15% на имплантацию. "
        "Сейчас по этому протоколу можно пройти бесплатную консультацию имплантолога."
    )

    def _composer(*_args, **_kwargs):
        return woven, {"composer_used": True}

    monkeypatch.setattr("core.price_brand_money._generate_budget_anchor_answer", _composer)

    q = "какие импланты подешевле?"
    route = select_price_service_route(q, client_id="demo")
    assert route.get("intent") == "price_concern"
    assert classify_brand_money_path(q, route, client_id="demo") == "budget_anchor"
    with _flask_ctx():
        from flask import request

        request.ctx = {}
        result = try_brand_money_early(q=q, sid="budget-live", client_id="demo", decision_frame=None)
    assert result is not None
    assert result.service_route == "price_brand_budget_anchor"
    payload = result.service_payload or {}
    meta = payload.get("meta") or {}
    answer = str(payload.get("answer") or "")
    assert meta.get("brand_money_path") == "budget_anchor"
    assert meta.get("answer_path") == "composer"
    assert len(meta.get("price_offer_ids") or []) == 2
    assert "76 200" in answer
    assert "85 200" in answer
    assert not answer.strip().startswith("Доступный вариант:")
    assert not answer.strip().startswith("Рекомендуемый баланс:")
    gate = meta.get("numeric_fact_gate") or {}
    assert gate.get("action") in {None, "pass", "skipped"}
    brief = str(meta.get("composer_brief") or "")
    assert "76 200" in brief
    assert "85 200" in brief


def test_budget_anchor_composer_fail_open_to_card(brand_on, monkeypatch):
    def _composer(*_args, **_kwargs):
        return None, {"composer_used": False}

    monkeypatch.setattr("core.price_brand_money._generate_budget_anchor_answer", _composer)

    payload = build_budget_anchor_payload(
        sid="fail-open",
        client_id="demo",
        q="какие импланты подешевле?",
        price_route={"intent": "price_concern", "match_score": 0.9},
    )
    answer = str(payload.get("answer") or "")
    meta = payload.get("meta") or {}
    assert meta.get("composer_fail_open") is True
    assert "76 200" in answer
    assert "85 200" in answer
    assert len(meta.get("price_offer_ids") or []) == 2


def test_budget_anchor_brief_has_no_list_labels(brand_on):
    brief = build_budget_anchor_brief(client_id="demo")
    pinned_section = brief.split("ДОСЛОВНО")[-1] if "ДОСЛОВНО" in brief else brief
    assert "Доступный вариант:" not in pinned_section
    assert "Рекомендуемый баланс:" not in pinned_section
    assert "76 200" in brief
    assert "85 200" in brief




def test_budget_anchor_card_from_pricebook_not_literals(brand_on):
    card, meta = build_budget_anchor_card(client_id="demo")
    ids = meta.get("price_offer_ids") or []
    assert len(ids) == 2
    assert meta.get("matched_service_id") == "classic"
    assert "76 200" in card
    assert "85 200" in card
    brief = build_budget_anchor_brief(client_id="demo")
    assert "Implantium" in brief or "76 200" in brief


def test_flag_off_preserves_unfiltered_lookup(brand_off):
    with _flask_ctx():
        from flask import request

        request.ctx = {}
        _publish_brand_filter(brand_group="korean")
        answer, meta = _build_price_lookup(
            client_id="demo",
            service_id="classic",
            q="сколько стоят корейские импланты?",
        )
    assert answer is not None
    assert len(meta.get("price_offer_ids") or []) == 3


def test_flag_off_orchestration_is_noop(brand_off):
    route = {"matched_service_id": "classic", "intent": "price_lookup", "mode": "matched"}
    with _flask_ctx():
        from flask import request

        request.ctx = {}
        _publish_brand_filter(brand_group="korean")
        assert try_brand_money_orchestration(
            q="сколько стоят корейские импланты?",
            sid="off",
            client_id="demo",
            price_route=route,
            decision_frame=None,
        ) is None


def test_planner_validates_conversational_nobel_alias(brand_on):
    allowed_groups = frozenset({"korean", "german", "swiss"})
    allowed_brands = frozenset({"nobel biocare", "impro", "implantium"})
    plan = _validate_plan(
        {
            "route": "price_lookup",
            "aspects": ["price"],
            "service_id": "classic",
            "followup_of": None,
            "needs_clarify": False,
            "brand_filter": {"brand": "нобель", "brand_group": None},
        },
        allowed_service_ids=frozenset({"classic"}),
        allowed_brand_groups=allowed_groups,
        allowed_brands=allowed_brands,
        client_id="demo",
    )
    assert plan is not None
    assert plan.brand_filter is not None
    assert plan.brand_filter.brand == "Nobel Biocare"
