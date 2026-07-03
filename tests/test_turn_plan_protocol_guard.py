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


def test_guard_keeps_session_focus_service() -> None:
    """Follow-up без followup_of от модели: фокус сессии — детерминированное подтверждение."""
    from session import mem_reset, set_last_subject

    sid = "guard-session-focus"
    mem_reset(sid)
    set_last_subject(sid, service_id="classic", topic="implantation", label="Классическая")
    out = _apply_protocol_choice_guard(
        _plan("classic"), q="а кто делает?", client_id="demo", sid=sid
    )
    assert out.service_id == "classic"


def test_guard_downgrades_when_focus_differs() -> None:
    from session import mem_reset, set_last_subject

    sid = "guard-session-focus-differs"
    mem_reset(sid)
    set_last_subject(sid, service_id="veneers", topic="prosthetics", label="Виниры")
    out = _apply_protocol_choice_guard(
        _plan("all_on_4"), q="есть рассрочка на имплантацию?", client_id="demo", sid=sid
    )
    assert out.service_id is None


def test_focus_enrichment_resolves_vague_followup() -> None:
    from core.turn_planner_llm import _apply_focus_followup_enrichment
    from session import mem_reset, set_last_subject

    sid = "enrich-vague-doc"
    mem_reset(sid)
    set_last_subject(sid, service_id="classic", topic="implantation", label="Классическая")
    out = _apply_focus_followup_enrichment(_plan(None), q="а кто делает?", sid=sid)
    assert out.service_id == "classic"
    assert out.followup_of == "classic"


def test_focus_enrichment_skips_topic_change() -> None:
    from core.turn_planner_llm import _apply_focus_followup_enrichment
    from session import mem_reset, set_last_subject

    sid = "enrich-topic-change"
    mem_reset(sid)
    set_last_subject(sid, service_id="classic", topic="implantation", label="Классическая")
    out = _apply_focus_followup_enrichment(
        _plan(None), q="а виниры сколько стоят?", sid=sid
    )
    assert out.service_id is None
    assert out.followup_of is None
