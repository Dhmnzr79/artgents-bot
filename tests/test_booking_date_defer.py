"""Booking date defer gate — no slot confirmation without schedule."""
from __future__ import annotations

import re
import uuid

import pytest

from core.booking_date_defer import (
    extract_booking_datetime_preference,
    looks_like_booking_datetime_signal,
    should_defer_booking_date_at_entry,
    should_defer_booking_date_confirmation,
)
from core.lead_turn_classifier import classify_lead_active_turn
from flow_handlers import handle_flows
from lead_interrupt import detect_lead_interrupt
from session import get_lead_preferred_datetime, mem_get, mem_reset, set_lead_intent


@pytest.fixture
def gate_on(monkeypatch):
    monkeypatch.setenv("BOOKING_DATE_DEFER_ON", "1")
    monkeypatch.setattr(
        "core.booking_date_defer.booking_date_defer_enabled",
        lambda _cid: True,
    )


@pytest.fixture
def gate_off(monkeypatch):
    monkeypatch.setenv("BOOKING_DATE_DEFER_ON", "0")
    monkeypatch.setattr(
        "core.booking_date_defer.booking_date_defer_enabled",
        lambda _cid: False,
    )


_FORBIDDEN_REPLY_RX = re.compile(
    r"(?:"
    r"записал[аи]"
    r"|принял[аи]?"
    r"|зафиксировал[аи]"
    r"|меняю\s+дат"
    r"|подтвердит"
    r"|согласован"
    r"|заброниров"
    r"|свободн"
    r"|жд[её]м\s+вас"
    r"|\d"
    r")",
    re.I | re.U,
)


def _assert_neutral_defer_answer(answer: str, *, expect_name: bool = True) -> None:
    low = answer.lower()
    assert "администратор" in low
    assert not _FORBIDDEN_REPLY_RX.search(answer), answer
    if expect_name:
        assert "как к вам" in low or "обращаться" in low


def _service_payload(answer, sid, client_id, **kwargs):
    meta = {"sid": sid, "client_id": client_id}
    if kwargs.get("lead_flow"):
        meta["lead_flow"] = True
    if kwargs.get("lead_step"):
        meta["lead_step"] = kwargs["lead_step"]
    return {
        "answer": answer,
        "quick_replies": list(kwargs.get("quick_replies") or []),
        "meta": meta,
    }


def _txt() -> dict:
    return {
        "lead_name_prompt": "Как к вам можно обращаться?",
        "lead_booking_date_defer": (
            "Пожелание по дате передам администратору. "
            "Удобные дату и время он уточнит с вами при звонке."
        ),
        "lead_booking_date_defer_phone": (
            "Оставьте, пожалуйста, номер телефона для звонка администратора."
        ),
    }


@pytest.mark.parametrize(
    "q",
    [
        "можно на 10 июля?",
        "на 11?",
        "а на 11 можно?",
        "давайте завтра",
        "в среду",
        "15.08",
        "передумал, а на 11?",
    ],
)
def test_mid_lead_date_variants_neutral_stub(gate_on, q: str):
    sid = f"bdd-mid-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    set_lead_intent(sid, "collecting_name")

    result = handle_flows(
        data={},
        st=mem_get(sid),
        sid=sid,
        q=q,
        client_id="demo",
        txt=_txt(),
        service_payload=_service_payload,
        get_last_content_ui_payload=lambda _sid: None,
        get_topic_state=lambda _sid, _doc: {},
    )

    assert result is not None
    answer = (result.get("payload") or {}).get("answer") or ""
    _assert_neutral_defer_answer(answer)
    assert mem_get(sid).get("lead_intent") == "collecting_name"
    assert get_lead_preferred_datetime(sid)


def test_entry_with_date_neutral_stub(gate_on):
    sid = f"bdd-entry-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)

    result = handle_flows(
        data={},
        st=mem_get(sid),
        sid=sid,
        q="Можно на 15 января записаться?",
        client_id="demo",
        txt=_txt(),
        service_payload=_service_payload,
        get_last_content_ui_payload=lambda _sid: None,
        get_topic_state=lambda _sid, _doc: {},
    )

    assert result is not None
    answer = (result.get("payload") or {}).get("answer") or ""
    _assert_neutral_defer_answer(answer)
    assert "подберём удобную дату" not in answer.lower()
    assert mem_get(sid).get("lead_intent") == "collecting_name"


def test_classifier_bare_day_before_gray_zone(gate_on):
    decision = classify_lead_active_turn(
        "а на 11 можно?",
        st={"lead_intent": "collecting_name"},
        client_id="demo",
        sid="s-bare-11",
    )
    assert decision.kind == "booking_date"
    assert detect_lead_interrupt("а на 11 можно?", resume_step="collecting_name") == "generic"


@pytest.mark.parametrize(
    "q",
    [
        "Мария",
        "Майя",
        "+79161234567",
        "а больно ли?",
        "сколько имплант?",
    ],
)
def test_negatives_not_booking_date_signal(gate_on, q: str):
    assert not looks_like_booking_datetime_signal(q, in_lead_flow=True)
    assert not should_defer_booking_date_at_entry(q=q, client_id="demo")


def test_extract_preference_internal_only(gate_on):
    assert extract_booking_datetime_preference("можно на 10 июля?") == "10 июля"
    assert extract_booking_datetime_preference("на 11?") == "на 11"
    assert extract_booking_datetime_preference("завтра в 18:00") == "завтра, 18:00"
    assert extract_booking_datetime_preference("сколько стоит имплант?") is None


@pytest.mark.parametrize("q", ["Я передумал", "Не, я передумал"])
def test_cancel_phrase_is_not_a_booking_date_signal(gate_on, q: str):
    assert not looks_like_booking_datetime_signal(q, in_lead_flow=True)
    assert not looks_like_booking_datetime_signal(
        q,
        in_lead_flow=True,
        has_prior_preference=True,
    )


def test_date_change_with_new_date_remains_booking_date(gate_on):
    decision = classify_lead_active_turn(
        "передумал, а на 11?",
        st={"lead_intent": "collecting_name"},
        client_id="demo",
        sid="s-date-change",
    )
    assert decision.kind == "booking_date"


@pytest.mark.parametrize(
    "q",
    ["другой день", "поменяйте дату", "а раньше можно", "на другую"],
)
def test_explicit_date_change_phrases_remain_booking_date(gate_on, q: str):
    assert looks_like_booking_datetime_signal(q, in_lead_flow=True)
    decision = classify_lead_active_turn(
        q,
        st={"lead_intent": "collecting_name"},
        client_id="demo",
        sid="s-explicit-date-change",
    )
    assert decision.kind == "booking_date"


def test_classifier_gate_off_preserves_content_interrupt(gate_off):
    decision = classify_lead_active_turn(
        "а можно на 24 июля?",
        st={"lead_intent": "collecting_name"},
        client_id="demo",
    )
    assert decision.kind == "content"
    assert decision.content_hint == "generic"


def test_mid_lead_date_question_gate_off_old_interrupt(gate_off):
    sid = f"bdd-off-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    set_lead_intent(sid, "collecting_name")

    result = handle_flows(
        data={},
        st=mem_get(sid),
        sid=sid,
        q="а можно на 24 июля?",
        client_id="demo",
        txt=_txt(),
        service_payload=_service_payload,
        get_last_content_ui_payload=lambda _sid: None,
        get_topic_state=lambda _sid, _doc: {},
    )

    assert result is None
