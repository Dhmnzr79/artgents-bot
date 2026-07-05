from __future__ import annotations

import pytest

from contracts.turn_plan import TurnPlan
from core.price_scope import detect_price_scope
from core.price_scope_planner import price_scope_from_plan


def _plan(
    *,
    service_id: str | None = None,
    patient_situation: str | None = None,
    route: str = "price_lookup",
) -> TurnPlan:
    return TurnPlan(
        route=route,
        aspects=["price"],
        service_id=service_id,
        patient_situation=patient_situation,
        needs_clarify=False,
    )


ONE_TOOTH_CASES = [
    (
        "А сколько будет стоить имплантация если нет одного зуба?",
        _plan(patient_situation="one_tooth_missing"),
    ),
    (
        "Сколько стоит имплантация если нет одного зуба?",
        _plan(patient_situation="one_tooth_missing"),
    ),
    (
        "Нет одного зуба, сколько стоит имплант?",
        _plan(patient_situation="one_tooth_missing"),
    ),
    (
        "Сколько стоит восстановить один зуб имплантом?",
        _plan(patient_situation="one_tooth_missing"),
    ),
    (
        "Сколько стоит поставить один имплант?",
        _plan(patient_situation="one_tooth_missing"),
    ),
]

GENERIC_CASES = [
    ("Сколько стоит имплантация?", _plan(patient_situation="generic_implant_interest")),
    ("Сколько стоит имплантация зуба?", _plan(patient_situation="generic_implant_interest")),
]

FULL_JAW_CASES = [
    (
        "Сколько стоит имплантация всей челюсти?",
        _plan(patient_situation="full_arch_missing"),
    ),
    (
        "Сколько стоит вставить все зубы под ключ?",
        _plan(patient_situation="full_arch_missing"),
    ),
    (
        "Сколько стоит восстановить всю челюсть?",
        _plan(patient_situation="full_arch_missing"),
    ),
]

SPECIFIC_CASES = [
    ("Сколько стоит All-on-4?", _plan(service_id="all_on_4")),
    ("Сколько стоит All-on-6?", _plan(service_id="all_on_6")),
    ("Сколько стоит скуловая имплантация?", _plan(service_id="zygomatic_implants")),
    ("Сколько стоят птеригоидные импланты?", _plan(service_id="pterygoid_implants")),
    (
        "Удалить зуб и сразу поставить имплант — сколько стоит?",
        _plan(service_id="one_stage", patient_situation="extraction_then_implant"),
    ),
]

PARITY_CASES = (
    ONE_TOOTH_CASES
    + GENERIC_CASES
    + FULL_JAW_CASES
    + [
        (
            "Сколько стоит имплантация всей верхней челюсти?",
            _plan(patient_situation="upper_jaw_missing_or_complex"),
        )
    ]
    + SPECIFIC_CASES
    + [
        (
            "У меня уже стоит имплант, сколько стоит коронка?",
            _plan(
                service_id="implant_supported_prosthetics",
                patient_situation="existing_implant_prosthetic_stage",
            ),
        ),
        ("Сколько стоит КТ?", _plan(service_id="tomography")),
    ]
)


@pytest.mark.parametrize("query,plan", PARITY_CASES)
def test_price_scope_from_plan_matches_regex_scope(query: str, plan: TurnPlan):
    expected = detect_price_scope(query, client_id="demo")
    actual = price_scope_from_plan(plan, "demo")

    assert actual.kind == expected.kind
    assert actual.group_id == expected.group_id
    assert actual.protocol_service_id == expected.protocol_service_id
    assert actual.blocked_service_ids == expected.blocked_service_ids
