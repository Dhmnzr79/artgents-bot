"""Deterministic protocol-choice guard: код не даёт планировщику решать имплант-протокол за пациента."""
from __future__ import annotations

import pytest

from contracts.turn_plan import TurnPlan
from core.turn_planner_llm import _apply_protocol_choice_guard


def _plan(service_id: str | None, followup_of: str | None = None) -> TurnPlan:
    return TurnPlan(
        route="content",
        aspects=["overview"],
        service_id=service_id,
        followup_of=followup_of,
        needs_clarify=False,
    )


@pytest.mark.parametrize(
    "q,svc",
    [
        ("Что входит в имплантацию под ключ?", "all_on_4"),
        ("Можно имплантацию во сне?", "all_on_4"),
        ("Коронка входит в цену импланта?", "implant_supported_prosthetics"),
        ("Есть рассрочка на имплантацию?", "one_stage"),
    ],
)
def test_guard_downgrades_unnamed_protocol(q: str, svc: str) -> None:
    out = _apply_protocol_choice_guard(_plan(svc), q=q, client_id="demo")
    assert out.service_id is None


@pytest.mark.parametrize(
    "q,svc",
    [
        ("Сколько стоит all-on-4?", "all_on_4"),
        ("Сколько стоит классическая имплантация?", "classic"),
        ("Синус-лифтинг входит в цену импланта?", "sinus_lift"),
        ("У меня уже стоит имплант, сколько стоит коронка?", "implant_supported_prosthetics"),
        ("Коронка на имплант — сколько стоит?", "implant_supported_prosthetics"),
    ],
)
def test_guard_keeps_named_or_cued_service(q: str, svc: str) -> None:
    out = _apply_protocol_choice_guard(_plan(svc), q=q, client_id="demo")
    assert out.service_id == svc


def test_guard_keeps_followup_context() -> None:
    out = _apply_protocol_choice_guard(
        _plan("all_on_4", followup_of="all_on_4"),
        q="а сколько стоит?",
        client_id="demo",
    )
    assert out.service_id == "all_on_4"


def test_guard_ignores_non_implant_services() -> None:
    out = _apply_protocol_choice_guard(_plan("veneers"), q="сколько стоят виниры?", client_id="demo")
    assert out.service_id == "veneers"
