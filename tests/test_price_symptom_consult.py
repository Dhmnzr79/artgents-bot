"""Price symptom consult gate — flag, routing, payload."""
from __future__ import annotations

import uuid

import pytest

from core.price_symptom_consult import should_gate_price_to_consult
from query_selector import select_price_service_route
from session import mem_reset, set_last_subject
from ux_builder import build_price_symptom_consult_payload


@pytest.fixture
def gate_on(monkeypatch):
    monkeypatch.setenv("PRICE_SYMPTOM_CONSULT_ON", "1")
    monkeypatch.setattr(
        "core.price_symptom_consult.price_symptom_consult_enabled",
        lambda _cid: True,
    )


@pytest.fixture
def gate_off(monkeypatch):
    monkeypatch.setenv("PRICE_SYMPTOM_CONSULT_ON", "0")
    monkeypatch.setattr(
        "core.price_symptom_consult.price_symptom_consult_enabled",
        lambda _cid: False,
    )


def test_gate_off_preserves_legacy_clarify(gate_off):
    sid = f"psc-off-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    route = select_price_service_route(
        "шатается зуб, сколько стоит?",
        client_id="demo",
        sid=sid,
    )
    assert route.get("mode") in {"clarify", "matched"}
    assert not should_gate_price_to_consult(
        q="шатается зуб, сколько стоит?",
        sid=sid,
        client_id="demo",
        price_route=route,
    )


def test_gate_on_symptom_price_consult(gate_on):
    sid = f"psc-on-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    route = select_price_service_route(
        "шатается зуб, сколько стоит?",
        client_id="demo",
        sid=sid,
    )
    assert should_gate_price_to_consult(
        q="шатается зуб, сколько стоит?",
        sid=sid,
        client_id="demo",
        price_route=route,
    )


def test_gate_on_explicit_treatment_price_not_gated(gate_on):
    sid = f"psc-treat-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    route = select_price_service_route(
        "болит зуб, сколько лечение?",
        client_id="demo",
        sid=sid,
    )
    assert not should_gate_price_to_consult(
        q="болит зуб, сколько лечение?",
        sid=sid,
        client_id="demo",
        price_route=route,
    )


def test_gate_on_explicit_extraction_not_gated(gate_on):
    sid = f"psc-ext-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    route = select_price_service_route(
        "шатается зуб, сколько удаление?",
        client_id="demo",
        sid=sid,
    )
    assert not should_gate_price_to_consult(
        q="шатается зуб, сколько удаление?",
        sid=sid,
        client_id="demo",
        price_route=route,
    )


def test_gate_on_session_focus_not_gated(gate_on):
    sid = f"psc-focus-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    set_last_subject(
        sid,
        service_id="all_on_4",
        topic="implantation",
        label="All-on-4",
    )
    route = select_price_service_route(
        "а сколько стоит?",
        client_id="demo",
        sid=sid,
    )
    assert route.get("mode") == "matched"
    assert not should_gate_price_to_consult(
        q="а сколько стоит?",
        sid=sid,
        client_id="demo",
        price_route=route,
    )


def test_price_lookup_fallback_returns_consult_payload(gate_on):
    from core.price_symptom_consult import try_price_symptom_consult_orchestration

    result = try_price_symptom_consult_orchestration(
        q="болит зуб, сколько стоит?",
        sid="psc-fb",
        client_id="demo",
        decision_frame=None,
        price_route={"mode": "clarify", "intent": "price_lookup"},
    )
    assert result is not None
    assert result.kind == "service_reply"
    assert result.service_route == "price_symptom_consult"
    payload = result.service_payload or {}
    assert "осмотр" in (payload.get("answer") or "").lower()
    assert payload.get("meta", {}).get("answer_path") == "price_symptom_consult"
    quick = payload.get("quick_replies") or []
    assert len(quick) == 2
    labels = [str(x.get("label") or "") for x in quick]
    assert any("консультац" in lb.lower() for lb in labels)


def test_consult_payload_pinned_no_diagnosis():
    payload = build_price_symptom_consult_payload(sid="s1", client_id="demo")
    answer = (payload.get("answer") or "").lower()
    for forbidden in ("кариес", "пульпит", "пародонтит", "диагноз", "лечить"):
        assert forbidden not in answer
