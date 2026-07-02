from __future__ import annotations

import json

import pytest

from contracts.turn_plan import TurnPlan
from core.turn_planner_llm import _validate_plan, plan_turn


def _mock_llm(monkeypatch, payload):
    captured: dict = {}

    def _fake(**kwargs):
        captured.update(kwargs)

        class _Msg:
            content = json.dumps(payload)

        class _Choice:
            message = _Msg()

        class _Resp:
            choices = [_Choice()]

        return _Resp()

    monkeypatch.setattr("core.turn_planner_llm.chat_completions_create", _fake)
    return captured


def test_validate_turn_plan_rejects_unknown_service_id():
    with pytest.raises(ValueError):
        _validate_plan(
            {
                "route": "price_lookup",
                "aspects": ["price"],
                "service_id": "not_in_catalog",
                "followup_of": None,
                "needs_clarify": False,
                "patient_situation": None,
                "brand_filter": None,
            },
            allowed_service_ids=frozenset({"classic"}),
            allowed_brand_groups=frozenset({"korean"}),
            allowed_brands=frozenset({"implantium"}),
        )


def test_plan_turn_composite_question_returns_aspects(monkeypatch):
    monkeypatch.setattr("core.turn_planner_llm.build_compact_service_catalog", lambda _cid: [
        {"service_id": "all_on_4", "title": "All-on-4", "about": "вся челюсть на 4 имплантах"},
        {"service_id": "classic", "title": "Классическая имплантация", "about": "один зуб"},
    ])
    monkeypatch.setattr(
        "core.turn_planner_llm._allowed_pricebook_filters",
        lambda _cid: (frozenset({"korean"}), frozenset({"implantium"})),
    )
    _mock_llm(
        monkeypatch,
        {
            "route": "price_lookup",
            "aspects": ["price", "pain", "duration"],
            "service_id": "all_on_4",
            "followup_of": None,
            "needs_clarify": False,
            "patient_situation": None,
            "brand_filter": None,
        },
    )

    plan = plan_turn("Сколько стоит all-on-4, это больно и долго ли заживает?", "tp-1", "demo")

    assert isinstance(plan, TurnPlan)
    assert plan.route == "price_lookup"
    assert set(plan.aspects) == {"price", "pain", "duration"}
    assert plan.service_id == "all_on_4"


def test_plan_turn_followup_price_uses_history(monkeypatch):
    from session import mem_add_bot, mem_add_user, mem_reset

    sid = "turn-planner-followup"
    mem_reset(sid)
    mem_add_user(sid, "Делаете all-on-4?")
    mem_add_bot(sid, "Да, выполняем протокол All-on-4.")

    monkeypatch.setattr("core.turn_planner_llm.build_compact_service_catalog", lambda _cid: [
        {"service_id": "all_on_4", "title": "All-on-4", "about": "вся челюсть на 4 имплантах"},
        {"service_id": "veneers", "title": "Виниры", "about": "эстетическая реставрация"},
    ])
    monkeypatch.setattr(
        "core.turn_planner_llm._allowed_pricebook_filters",
        lambda _cid: (frozenset(), frozenset()),
    )
    captured = _mock_llm(
        monkeypatch,
        {
            "route": "price_lookup",
            "aspects": ["price"],
            "service_id": "all_on_4",
            "followup_of": "all_on_4",
            "needs_clarify": False,
            "patient_situation": None,
            "brand_filter": None,
        },
    )

    plan = plan_turn("а сколько стоит?", sid, "demo")

    assert plan is not None
    assert plan.followup_of == "all_on_4"
    assert plan.service_id == "all_on_4"
    user = captured["messages"][1]["content"]
    assert "Контекст диалога" in user
    assert "не источник фактов" in user
    assert "all-on-4" in user.lower()
    assert user.count("а сколько стоит?") == 1


def test_plan_turn_topic_switch_after_focus_splits_followup_and_service(monkeypatch):
    from session import mem_add_bot, mem_add_user, mem_reset

    sid = "turn-planner-topic-switch"
    mem_reset(sid)
    mem_add_user(sid, "Расскажите про All-on-4")
    mem_add_bot(sid, "All-on-4 помогает восстановить зубной ряд на одной челюсти.")

    monkeypatch.setattr("core.turn_planner_llm.build_compact_service_catalog", lambda _cid: [
        {"service_id": "all_on_4", "title": "All-on-4", "about": "вся челюсть"},
        {"service_id": "veneers", "title": "Виниры", "about": "эстетика улыбки"},
    ])
    monkeypatch.setattr(
        "core.turn_planner_llm._allowed_pricebook_filters",
        lambda _cid: (frozenset(), frozenset()),
    )
    _mock_llm(
        monkeypatch,
        {
            "route": "price_lookup",
            "aspects": ["price"],
            "service_id": "veneers",
            "followup_of": None,
            "needs_clarify": False,
            "patient_situation": None,
            "brand_filter": None,
        },
    )

    plan = plan_turn("а виниры сколько?", sid, "demo")

    assert plan is not None
    assert plan.followup_of is None
    assert plan.service_id == "veneers"


def test_plan_turn_bad_json_fail_open(monkeypatch):
    monkeypatch.setattr("core.turn_planner_llm.build_compact_service_catalog", lambda _cid: [
        {"service_id": "classic", "title": "Классическая имплантация", "about": "один зуб"},
    ])
    monkeypatch.setattr(
        "core.turn_planner_llm._allowed_pricebook_filters",
        lambda _cid: (frozenset(), frozenset()),
    )

    def _bad(**_kwargs):
        class _Msg:
            content = "not json"

        class _Choice:
            message = _Msg()

        class _Resp:
            choices = [_Choice()]

        return _Resp()

    monkeypatch.setattr("core.turn_planner_llm.chat_completions_create", _bad)

    assert plan_turn("сколько стоит имплантация", "tp-bad", "demo") is None


def test_plan_turn_validates_brand_filter(monkeypatch):
    monkeypatch.setattr("core.turn_planner_llm.build_compact_service_catalog", lambda _cid: [
        {"service_id": "classic", "title": "Классическая имплантация", "about": "один зуб"},
    ])
    monkeypatch.setattr(
        "core.turn_planner_llm._allowed_pricebook_filters",
        lambda _cid: (frozenset({"korean"}), frozenset({"implantium"})),
    )
    _mock_llm(
        monkeypatch,
        {
            "route": "price_lookup",
            "aspects": ["price"],
            "service_id": "classic",
            "followup_of": None,
            "needs_clarify": False,
            "patient_situation": None,
            "brand_filter": {"brand_group": "korean", "brand": None},
        },
    )

    plan = plan_turn("сколько стоят корейские импланты", "tp-brand", "demo")

    assert plan is not None
    assert plan.brand_filter is not None
    assert plan.brand_filter.brand_group == "korean"
