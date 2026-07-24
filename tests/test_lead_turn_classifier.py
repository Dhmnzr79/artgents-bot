"""Tests for lead active-turn classifier (intent before slot)."""
from __future__ import annotations

import pytest

from contracts.lead_turn import LeadTurnDecision
from core.lead_turn_classifier import classify_lead_active_turn
from lead_interrupt import LEAD_PAUSE_REF, parse_lead_cancel, parse_lead_defer, parse_lead_meta_pause


def _st(*, lead_intent: str = "collecting_name") -> dict:
    return {"lead_intent": lead_intent, "lead_flow_active": True}


def test_cancel_ne_hochu() -> None:
    decision = classify_lead_active_turn("Не хочу", st=_st())
    assert decision.kind == "meta_cancel"
    assert parse_lead_cancel("Не хочу")


def test_obvious_peredumal_is_deterministic_cancel() -> None:
    decision = classify_lead_active_turn("передумал", st=_st())
    assert decision.kind == "meta_cancel"
    assert parse_lead_cancel("передумал")


def test_conversational_cancel_is_deterministic() -> None:
    assert parse_lead_cancel("Я передумал")
    assert parse_lead_cancel("Не, я передумал")
    assert not parse_lead_cancel("я не буду")


@pytest.mark.parametrize("q", ["Я передумал", "Не, я передумал"])
def test_conversational_peredumal_cancel_does_not_use_gray_llm(
    monkeypatch: pytest.MonkeyPatch,
    q: str,
) -> None:
    monkeypatch.setattr(
        "core.lead_turn_classifier.classify_lead_turn_gray_zone",
        lambda *a, **k: pytest.fail("gray LLM must not be called for explicit cancel"),
    )
    decision = classify_lead_active_turn(
        q,
        st=_st(),
        sid="s1",
        client_id="demo",
    )
    assert decision.kind == "meta_cancel"


def test_ya_ne_budu_gray_zone_cancel(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_gray(q: str, **kwargs):
        if "не буду" in q.lower():
            return LeadTurnDecision(kind="meta_cancel", confidence=0.9)
        return None

    monkeypatch.setattr(
        "core.lead_turn_classifier.classify_lead_turn_gray_zone",
        _fake_gray,
    )
    decision = classify_lead_active_turn("я не буду", st=_st(), sid="s1", client_id="demo")
    assert decision.kind == "meta_cancel"
    assert decision.kind != "slot"


def test_cancel_text_during_name_collection() -> None:
    decision = classify_lead_active_turn("не хочу записываться", st=_st())
    assert decision.kind == "meta_cancel"
    assert parse_lead_cancel("не хочу записываться")


def test_meta_pause_text_during_name_collection() -> None:
    decision = classify_lead_active_turn("задать вопрос", st=_st())
    assert decision.kind == "meta_pause"
    assert parse_lead_meta_pause("задать вопрос")


def test_pain_concern_is_content_not_slot() -> None:
    decision = classify_lead_active_turn("Я боюсь боли", st=_st())
    assert decision.kind == "content"
    assert decision.content_hint == "pain"


def test_tooth_pain_is_content_before_slot() -> None:
    decision = classify_lead_active_turn("У меня болит зуб", st=_st())
    assert decision.kind == "content"
    assert decision.content_hint == "pain"


def test_price_question_is_content() -> None:
    decision = classify_lead_active_turn("Сколько стоит имплант?", st=_st())
    assert decision.kind == "content"
    assert decision.content_hint == "price"


def test_contacts_question_is_content() -> None:
    decision = classify_lead_active_turn("А какой адрес?", st=_st())
    assert decision.kind == "content"
    assert decision.content_hint == "contacts"


def test_valid_name_is_slot() -> None:
    decision = classify_lead_active_turn("Мария", st=_st())
    assert decision.kind == "slot"
    assert decision.slot_value == "Мария"


def test_ya_anna_is_slot() -> None:
    decision = classify_lead_active_turn("я Анна", st=_st())
    assert decision.kind == "slot"
    assert decision.slot_value == "Анна"


def test_invalid_name_is_unclear_not_slot_first(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "core.lead_turn_classifier.classify_lead_turn_gray_zone",
        lambda *a, **k: None,
    )
    decision = classify_lead_active_turn("12345", st=_st(), sid="s1", client_id="demo")
    assert decision.kind == "unclear"


def test_defer_phrase_exits_lead() -> None:
    decision = classify_lead_active_turn("надо подумать", st=_st())
    assert decision.kind == "defer"
    assert parse_lead_defer("надо подумать")


def test_pause_ref_is_meta_pause() -> None:
    decision = classify_lead_active_turn("", ref=LEAD_PAUSE_REF, st=_st())
    assert decision.kind == "meta_pause"
