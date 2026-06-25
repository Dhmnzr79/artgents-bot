"""Price scope router — unit + route integration tests."""

from __future__ import annotations

import pytest

from core.price_scope import PriceScopeResult, detect_price_scope
from query_selector import select_price_service_route

ONE_TOOTH_CASES = [
    "А сколько будет стоить имплантация если нет одного зуба?",
    "Сколько стоит имплантация если нет одного зуба?",
    "Нет одного зуба, сколько стоит имплант?",
    "Сколько стоит восстановить один зуб имплантом?",
    "Сколько стоит поставить один имплант?",
]

GENERIC_CASES = [
    "Сколько стоит имплантация?",
    "Сколько стоит имплантация зуба?",
]

FULL_JAW_CASES = [
    "Сколько стоит имплантация всей челюсти?",
    "Сколько стоит вставить все зубы под ключ?",
    "Сколько стоит восстановить всю челюсть?",
]

SPECIFIC_CASES = [
    ("Сколько стоит All-on-4?", "all_on_4"),
    ("Сколько стоит All-on-6?", "all_on_6"),
    ("Сколько стоит скуловая имплантация?", "zygomatic_implants"),
    ("Сколько стоят птеригоидные импланты?", "pterygoid_implants"),
    (
        "Удалить зуб и сразу поставить имплант — сколько стоит?",
        "one_stage",
    ),
]

JAW_FORBIDDEN = frozenset({"all_on_4", "all_on_6", "zygomatic_implants"})


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


def test_upper_jaw_scope():
    question = "Сколько стоит имплантация всей верхней челюсти?"
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
