"""Price symptom consult gate — flag, routing, payload."""
from __future__ import annotations

import uuid

import pytest

from contracts.patient_situation import PatientSituationCues, PatientSituationResult
from core.price_symptom_consult import (
    should_defer_price_strict_service,
    should_gate_price_to_consult,
    try_price_strict_service_defer,
    try_price_symptom_consult_orchestration,
)
from core.pricebook_loader import load_pricebook_service
from query_selector import select_price_service_route
from session import mem_add_user, mem_reset, set_last_patient_situation, set_last_subject
from ux_builder import build_price_symptom_consult_payload


@pytest.fixture
def strict_on(monkeypatch):
    monkeypatch.setenv("PRICE_STRICT_SERVICE_ON", "1")
    monkeypatch.setattr("config.PRICE_STRICT_SERVICE_ON", True)


@pytest.fixture
def no_patient_situation_llm(monkeypatch):
    """Vague-price carry tests: fresh detect unknown, carry from session snapshot."""
    unknown = PatientSituationResult(
        kind="unknown",
        confidence=0.0,
        source="rule_based",
        patient_scope="unknown",
    )
    monkeypatch.setattr(
        "core.patient_situation.detect_patient_situation",
        lambda *a, **k: unknown,
    )


def _persist_one_tooth_situation(sid: str, *, turn1: str) -> None:
    situation = PatientSituationResult(
        kind="one_tooth_missing",
        confidence=0.95,
        source="rule_based",
        evidence=["нет одного зуба"],
        patient_scope="one_tooth",
        problem="missing_teeth",
        extent="one_tooth",
        cues=PatientSituationCues(quantity="one"),
    )
    set_last_patient_situation(sid, situation.model_dump())
    mem_add_user(sid, turn1)


def _persist_full_jaw_situation(sid: str, *, turn1: str) -> None:
    situation = PatientSituationResult(
        kind="full_arch_missing",
        confidence=0.95,
        source="rule_based",
        evidence=["нет зубов"],
        patient_scope="full_jaw",
        problem="missing_teeth",
        extent="full_arch",
        cues=PatientSituationCues(quantity="all"),
    )
    set_last_patient_situation(sid, situation.model_dump())
    mem_add_user(sid, turn1)


@pytest.fixture
def gate_on(monkeypatch):
    monkeypatch.setenv("PRICE_SYMPTOM_CONSULT_ON", "1")
    monkeypatch.setattr(
        "core.price_symptom_consult.price_symptom_consult_enabled",
        lambda _cid: True,
    )


@pytest.fixture
def money_gates_on(gate_on, strict_on):
    """Both price defer gates enabled — live default path."""
    return None


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


def test_strict_ps03_vague_price_after_one_tooth_situation_not_deferred(
    money_gates_on, no_patient_situation_llm
):
    sid = f"psc-ps03-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    turn1 = "У меня нет одного зуба, что лучше?"
    _persist_one_tooth_situation(sid, turn1=turn1)
    q = "А сколько стоит?"
    route = select_price_service_route(q, client_id="demo", sid=sid)
    assert route.get("mode") == "matched"
    assert route.get("matched_service_id") == "classic"
    assert not should_gate_price_to_consult(
        q=q, sid=sid, client_id="demo", price_route=route
    )
    assert try_price_symptom_consult_orchestration(
        q=q, sid=sid, client_id="demo", decision_frame=None, price_route=route
    ) is None
    assert not should_defer_price_strict_service(
        q=q, sid=sid, client_id="demo", price_route=route
    )
    assert try_price_strict_service_defer(
        q=q, sid=sid, client_id="demo", decision_frame=None, price_route=route
    ) is None
    pb = load_pricebook_service("demo", "classic")
    assert pb is not None
    assert pb.default_unit == "one_tooth"


def test_money_gates_symptom_price_without_situation_stays_consult(
    money_gates_on, no_patient_situation_llm
):
    sid = f"psc-symptom-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    # «зуб болит, сколько?» не матчит PRICE regex; каноническая форма symptom-price:
    q = "болит зуб, сколько стоит?"
    route = select_price_service_route(q, client_id="demo", sid=sid)
    assert should_gate_price_to_consult(
        q=q, sid=sid, client_id="demo", price_route=route
    )
    result = try_price_symptom_consult_orchestration(
        q=q, sid=sid, client_id="demo", decision_frame=None, price_route=route
    )
    assert result is not None
    assert result.service_route == "price_symptom_consult"


def test_strict_h2_fluoridation_without_situation_defers(money_gates_on, no_patient_situation_llm):
    sid = f"psc-h2-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    q = "сколько стоит фторирование зубов?"
    route = select_price_service_route(
        q, client_id="demo", sid=sid, intent_override="price_lookup"
    )
    assert should_defer_price_strict_service(
        q=q, sid=sid, client_id="demo", price_route=route
    )
    result = try_price_strict_service_defer(
        q=q, sid=sid, client_id="demo", decision_frame=None, price_route=route
    )
    assert result is not None
    assert result.service_route == "price_strict_service_defer"


def test_strict_h3_braces_policy_alternative_defers(money_gates_on, no_patient_situation_llm):
    sid = f"psc-h3-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    q = "сколько стоит установка брекетов?"
    route = select_price_service_route(
        q, client_id="demo", sid=sid, intent_override="price_lookup"
    )
    assert should_defer_price_strict_service(
        q=q, sid=sid, client_id="demo", price_route=route
    )
    result = try_price_strict_service_defer(
        q=q, sid=sid, client_id="demo", decision_frame=None, price_route=route
    )
    assert result is not None
    answer = (result.service_payload or {}).get("answer") or ""
    assert "брекет" in answer.lower()
    assert "элайнер" in answer.lower()


def test_strict_ps05_full_jaw_vague_price_not_regressed(money_gates_on, no_patient_situation_llm):
    sid = f"psc-ps05-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    turn1 = "Что делать, если нет зубов вообще?"
    _persist_full_jaw_situation(sid, turn1=turn1)
    q = "А что по ценам?"
    route = select_price_service_route(q, client_id="demo", sid=sid)
    assert route.get("mode") == "group_overview"
    assert route.get("group_id") == "full_jaw"
    assert not should_gate_price_to_consult(
        q=q, sid=sid, client_id="demo", price_route=route
    )
    assert not should_defer_price_strict_service(
        q=q, sid=sid, client_id="demo", price_route=route
    )
