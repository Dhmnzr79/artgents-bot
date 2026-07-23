"""Price scope router — unit + route integration tests."""

from __future__ import annotations

import pytest

from core.clinic_policies_loader import find_service_alternative
from core.price_scope import detect_price_scope
from contracts.patient_situation import PatientSituationResult
from price_query_cases import (
    FULL_JAW_CASES,
    GENERIC_CASES,
    JAW_FORBIDDEN,
    ONE_TOOTH_CASES,
    SPECIFIC_CASES,
    UPPER_JAW_CASES,
)
from query_selector import select_price_service_route


@pytest.fixture(autouse=True)
def _no_patient_situation_llm(monkeypatch):
    """Price router tests are deterministic — no patient_situation LLM."""
    empty_situation = PatientSituationResult(
        kind="unknown",
        confidence=0.0,
        source="rule_based",
        patient_scope="unknown",
    )
    monkeypatch.setattr(
        "query_selector._patient_situation_for_turn",
        lambda *a, **k: (empty_situation, False),
    )


@pytest.mark.parametrize("question", ONE_TOOTH_CASES)
def test_detect_one_tooth_scope(question: str):
    scope = detect_price_scope(question, client_id="demo")
    assert scope.kind == "one_tooth"
    assert scope.group_id is None
    assert JAW_FORBIDDEN <= scope.blocked_service_ids


@pytest.mark.parametrize("question", ONE_TOOTH_CASES)
def test_one_tooth_routes_not_all_on_4(question: str):
    route = select_price_service_route(question, client_id="demo", sid="scope-test")
    assert route.get("mode") == "matched"
    assert route.get("matched_service_id") in {"classic", "one_stage"}
    assert route.get("matched_service_id") not in JAW_FORBIDDEN


@pytest.mark.parametrize("question", GENERIC_CASES)
def test_generic_implantation_group_overview(question: str):
    scope = detect_price_scope(question, client_id="demo")
    assert scope.kind == "generic_implantation"
    assert scope.group_id == "implantation"
    route = select_price_service_route(question, client_id="demo", sid="scope-generic")
    assert route.get("mode") == "group_overview"
    assert route.get("group_id") == "implantation"


@pytest.mark.parametrize("question", FULL_JAW_CASES)
def test_full_jaw_scope_and_overview(question: str):
    scope = detect_price_scope(question, client_id="demo")
    assert scope.kind == "full_jaw"
    assert scope.group_id == "full_jaw"
    route = select_price_service_route(question, client_id="demo", sid="scope-jaw")
    assert route.get("mode") == "group_overview"
    assert route.get("group_id") == "full_jaw"


@pytest.mark.parametrize("question", UPPER_JAW_CASES)
def test_upper_jaw_scope(question: str):
    scope = detect_price_scope(question, client_id="demo")
    assert scope.kind == "upper_jaw"
    assert scope.group_id == "upper_jaw"
    route = select_price_service_route(question, client_id="demo", sid="scope-upper")
    assert route.get("mode") == "group_overview"
    assert route.get("group_id") == "upper_jaw"


@pytest.mark.parametrize("question,service_id", SPECIFIC_CASES)
def test_specific_protocol_scope(question: str, service_id: str):
    scope = detect_price_scope(question, client_id="demo")
    assert scope.kind == "specific_protocol"
    assert scope.protocol_service_id == service_id
    route = select_price_service_route(question, client_id="demo", sid=f"scope-{service_id}")
    assert route.get("mode") == "matched"
    assert route.get("matched_service_id") == service_id


def test_prosthetic_stage_scope():
    question = "У меня уже стоит имплант, сколько стоит коронка?"
    scope = detect_price_scope(question, client_id="demo")
    assert scope.kind == "prosthetic_stage"
    assert scope.protocol_service_id == "implant_supported_prosthetics"
    route = select_price_service_route(question, client_id="demo", sid="scope-crown")
    assert route.get("matched_service_id") == "implant_supported_prosthetics"
    assert route.get("matched_service_id") not in {"classic", "all_on_4"}


def test_ct_price_unscoped():
    scope = detect_price_scope("Сколько стоит КТ?", client_id="demo")
    assert scope.kind == "none"
    route = select_price_service_route("Сколько стоит КТ?", client_id="demo", sid="scope-ct")
    assert route.get("mode") == "matched"
    assert route.get("matched_service_id") == "tomography"


def test_incident_one_missing_tooth_not_all_on_4():
    q = "А сколько будет стоить имплантация если нет одного зуба?"
    route = select_price_service_route(q, client_id="demo", sid="incident-one-tooth")
    assert route.get("matched_service_id") == "classic"
    body_sid = "incident-one-tooth"
    # price should be one-tooth range, not jaw 318k — checked via service id
    assert route.get("matched_service_id") != "all_on_4"


def test_basal_implantation_price_service_alternative_defer():
    q = "Сколько стоит базальная имплантация?"
    assert find_service_alternative(q, "demo") is not None
    route = select_price_service_route(
        q, client_id="demo", sid="svc-alt-basal", intent_override="price_lookup"
    )
    assert route.get("mode") == "clarify"
    assert route.get("fallback_reason") == "service_not_offered"
    assert route.get("mode") != "group_overview"


def test_generic_implantation_stays_group_overview_d1():
    q = "Сколько стоит имплантация?"
    assert find_service_alternative(q, "demo") is None
    route = select_price_service_route(
        q, client_id="demo", sid="svc-alt-generic", intent_override="price_lookup"
    )
    assert route.get("mode") == "group_overview"
    assert route.get("group_id") == "implantation"


def test_classic_implantation_not_service_alternative():
    q = "Сколько стоит классическая имплантация?"
    assert find_service_alternative(q, "demo") is None
    route = select_price_service_route(
        q, client_id="demo", sid="svc-alt-classic", intent_override="price_lookup"
    )
    assert route.get("mode") != "clarify" or route.get("fallback_reason") != "service_not_offered"
    assert route.get("matched_service_id") == "classic"
