from __future__ import annotations

import uuid

import pytest

import core.price_group_overview as price_group_overview
from core.price_group_overview import build_group_overview_answer
from query_selector import select_price_service_route


def test_select_price_route_group_overview_for_generic_implant():
    route = select_price_service_route("Сколько стоит имплантация?", client_id="demo", sid="t1")
    assert route.get("mode") == "group_overview"
    assert route.get("group_id") == "implantation"


def test_select_price_route_group_overview_for_typo():
    route = select_price_service_route("Сколько стоит импланатция?", client_id="demo", sid="t2")
    assert route.get("mode") == "group_overview"


def test_group_overview_even_when_catalog_matches_classic():
    route = select_price_service_route("Сколько стоит имплантация?", client_id="demo", sid="t3")
    assert route.get("mode") == "group_overview"
    assert route.get("matched_service_id") != "tomography"
    assert route.get("containment_eligible") is False


@pytest.mark.parametrize("question", ["Сколько стоит имплантация?", "Сколько стоит импланатция?"])
def test_group_overview_answer_shape(question):
    answer, quick, meta = build_group_overview_answer("demo")
    assert answer
    assert "86 500" in answer
    assert "протокол" in answer.lower()
    assert len(quick) >= 3
    assert meta.get("pricebook_group_id") == "implantation"


def test_group_overview_living_flag_off_keeps_static_answer(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise AssertionError("composer must not be called when flag is off")

    monkeypatch.setattr(price_group_overview, "LIVING_OVERVIEW_ON", False)
    monkeypatch.setattr(price_group_overview, "_generate_living_overview_answer", _boom)

    answer, quick, meta = build_group_overview_answer(
        "demo",
        patient_q="Сколько стоит имплантация?",
        session_id="living-off",
    )

    assert answer
    assert answer.startswith("Стоимость имплантации зависит от выбранного протокола.")
    assert answer.endswith("Выберите протокол ниже или уточните вопрос.")
    assert ["price:classic", "price:one_stage", "price:all_on_4"] == [
        r["ref"] for r in quick[:3]
    ]
    assert "76 200" in answer
    assert "86 500" in answer
    assert "318 000" in answer
    assert meta.get("pricebook_group_id") == "implantation"


def test_group_overview_living_intro_keeps_prices_and_buttons(monkeypatch):
    calls = {}

    def _composer(user_q, knowledge_base, aspects, deterministic_cards, meta, session_id):
        calls["user_q"] = user_q
        calls["knowledge_base"] = knowledge_base
        calls["aspects"] = aspects
        calls["deterministic_cards"] = deterministic_cards
        calls["meta"] = meta
        calls["session_id"] = session_id
        return (
            "Понимаю, хочется сразу сориентироваться по имплантации.\n\n"
            "Ниже оставила варианты, можно выбрать подходящий или уточнить вопрос.",
            {"composer_used": True},
        )

    monkeypatch.setattr(price_group_overview, "LIVING_OVERVIEW_ON", True)
    monkeypatch.setattr(price_group_overview, "_generate_living_overview_answer", _composer)

    static_answer, static_quick, _ = build_group_overview_answer("demo")
    answer, quick, meta = build_group_overview_answer(
        "demo",
        patient_q="Сколько примерно стоит имплантация?",
        session_id="living-on",
    )

    assert answer
    assert answer.startswith("Понимаю, хочется сразу сориентироваться по имплантации.")
    assert answer.endswith("Ниже оставила варианты, можно выбрать подходящий или уточнить вопрос.")
    assert "Стоимость имплантации зависит от выбранного протокола." not in answer
    expected_prices = ["76 200", "86 500", "318 000", "398 000", "42 000"]
    for expected in expected_prices:
        assert expected in answer
    assert [answer.index(expected) for expected in expected_prices] == sorted(
        answer.index(expected) for expected in expected_prices
    )
    assert [static_answer.index(expected) for expected in expected_prices] == sorted(
        static_answer.index(expected) for expected in expected_prices
    )
    assert quick == static_quick
    assert meta.get("pricebook_group_id") == "implantation"
    assert calls["user_q"] == "Сколько примерно стоит имплантация?"
    assert "Детерминированная карточка цен" in calls["knowledge_base"]
    assert calls["aspects"] == ["price"]
    assert calls["deterministic_cards"] == []
    assert calls["meta"]["composer_surface"] == "living_overview_frame"
    assert calls["session_id"] == "living-on"


def test_group_overview_living_composer_exception_fail_opens(monkeypatch):
    def _composer(*_args, **_kwargs):
        raise RuntimeError("composer unavailable")

    monkeypatch.setattr(price_group_overview, "LIVING_OVERVIEW_ON", True)
    monkeypatch.setattr(price_group_overview, "_generate_living_overview_answer", _composer)

    answer, quick, meta = build_group_overview_answer(
        "demo",
        patient_q="Сколько стоит имплантация?",
        session_id="living-error",
    )

    assert answer
    assert answer.startswith("Стоимость имплантации зависит от выбранного протокола.")
    assert answer.endswith("Выберите протокол ниже или уточните вопрос.")
    assert [r["ref"] for r in quick[:3]] == ["price:classic", "price:one_stage", "price:all_on_4"]
    assert "318 000" in answer
    assert meta.get("pricebook_group_id") == "implantation"


def test_select_price_route_full_jaw_overview():
    route = select_price_service_route(
        "Сколько стоит имплантация на челюсть?",
        client_id="demo",
        sid="t4",
    )
    assert route.get("mode") == "group_overview"
    assert route.get("group_id") == "full_jaw"


def test_full_jaw_overview_answer_shape():
    answer, quick, meta = build_group_overview_answer("demo", group_id="full_jaw")
    assert answer
    assert "318 000" in answer
    assert "398 000" in answer
    assert "All-on-4" in answer
    assert "76 200" not in answer
    assert "за челюсть" in answer
    assert meta.get("pricebook_group_id") == "full_jaw"
    assert len(quick) == 2
    refs = [r["ref"] for r in quick]
    assert refs == ["price:all_on_4", "price:all_on_6"]


def test_upper_jaw_overview_answer_shape():
    answer, quick, meta = build_group_overview_answer("demo", group_id="upper_jaw")
    assert answer
    assert "318 000" in answer
    assert "398 000" in answer
    assert "верхней челюсти" in answer.lower()
    assert "6 опор" in answer
    assert "за челюсть" in answer
    assert meta.get("pricebook_group_id") == "upper_jaw"
    assert len(quick) == 2


def test_select_price_route_upper_jaw_overview():
    route = select_price_service_route(
        "сколько стоит вся верхняя челюсть",
        client_id="demo",
        sid="t5",
    )
    assert route.get("mode") == "group_overview"
    assert route.get("group_id") == "upper_jaw"


def test_e2e_generic_implant_overview(monkeypatch):
    monkeypatch.setenv("E2E_USE_TEST_CLIENT", "1")
    from app import app

    client = app.test_client()
    sid = f"test-implant-overview-{uuid.uuid4().hex[:12]}"
    resp = client.post(
        "/ask",
        json={"q": "Сколько стоит имплантация?", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    meta = body.get("meta") or {}
    assert meta.get("price_status") == "group_overview"
    assert meta.get("fallback_reason") == "price_implant_overview"
    answer = body.get("answer") or ""
    assert "318 000" in answer
    refs = [r.get("ref") for r in body.get("quick_replies") or []]
    assert "price:classic" in refs
    assert "price:all_on_4" in refs


def test_e2e_full_jaw_implant_overview(monkeypatch):
    monkeypatch.setenv("E2E_USE_TEST_CLIENT", "1")
    from app import app

    client = app.test_client()
    sid = f"test-full-jaw-overview-{uuid.uuid4().hex[:12]}"
    resp = client.post(
        "/ask",
        json={"q": "Сколько стоит имплантация на челюсть?", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    meta = body.get("meta") or {}
    assert meta.get("price_status") == "group_overview"
    assert meta.get("pricebook_group_id") == "full_jaw"
    refs = [r.get("ref") for r in body.get("quick_replies") or []]
    assert refs == ["price:all_on_4", "price:all_on_6"]
    assert "price:classic" not in refs
