"""Source routing guards for Core Golden §2.1 (implantation content)."""
from __future__ import annotations

from contracts.decision_frame import DecisionFrame
from source_routing import route_source


def _frame(*, topic: str = "implantation", mode: str = "process") -> DecisionFrame:
    return DecisionFrame(
        route_intent="content",
        service_topic=topic,
        service_id=None,
        query_mode=mode,
        confidence={"intent": 0.9, "topic": 0.9, "service": 0.0, "query_mode": 0.9},
        needs_clarification=False,
    )


def test_implantation_without_kt_does_not_use_tomography_facts() -> None:
    sr = route_source(
        "Что такое имплантация зубов?",
        sid="t2",
        client_id="demo",
        decision=_frame(mode="overview"),
        app_intent="content",
    )
    assert sr.service_id != "tomography"


def test_kt_before_implantation_may_use_tomography_facts() -> None:
    sr = route_source(
        "Нужна ли КТ перед имплантацией?",
        sid="t3",
        client_id="demo",
        decision=_frame(),
        app_intent="content",
    )
    assert sr.source == "catalog_facts"
    assert sr.service_id == "tomography"


def test_treatment_order_must_not_route_tomography_catalog_facts() -> None:
    """Golden #14: «КТ» в списке этапов ≠ запрос про услугу tomography."""
    sr = route_source(
        "Что сначала: КТ, удаление, лечение дёсен или имплантация?",
        sid="t14",
        client_id="demo",
        decision=_frame(mode="process"),
        app_intent="content",
    )
    assert not (sr.source == "catalog_facts" and sr.service_id == "tomography")


def test_implant_doctors_question_routes_doctor_not_catalog_facts() -> None:
    """Smoke #10: staff intent must win over tomography catalog false-positive."""
    sr = route_source(
        "Кто у вас занимается имплантацией?",
        sid="t10",
        client_id="demo",
        decision=_frame(topic="doctors", mode="specific"),
        app_intent="content",
    )
    assert sr.source == "doctor"
    assert sr.match_method == "doctors_lookup"
