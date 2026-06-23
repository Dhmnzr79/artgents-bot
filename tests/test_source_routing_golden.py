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


def test_implantation_what_is_routes_to_methods_overview() -> None:
    sr = route_source(
        "Что такое имплантация зубов?",
        sid="t",
        client_id="demo",
        decision=_frame(mode="overview"),
        app_intent="content",
    )
    assert sr.source == "catalog_md"
    assert "methods_overview" in (sr.ref or "")


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


def test_treatment_sequence_routes_to_steps() -> None:
    sr = route_source(
        "Что сначала: КТ, удаление, лечение дёсен или имплантация?",
        sid="t4",
        client_id="demo",
        decision=_frame(mode="process"),
        app_intent="content",
    )
    assert sr.source == "catalog_md"
    assert "implantation__info__steps" in (sr.ref or "")


def test_permanent_crown_why_wait_routes_to_tooth_one_day() -> None:
    sr = route_source(
        "Почему нельзя сразу поставить постоянную коронку?",
        sid="t5",
        client_id="demo",
        decision=_frame(topic="prosthetics", mode="process"),
        app_intent="content",
    )
    assert sr.source == "catalog_md"
    assert "tooth_one_day" in (sr.ref or "")
