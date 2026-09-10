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
def test_conversational_peredumal_cancel_does_not_use_gray_llm(q: str) -> None:
    decision = classify_lead_active_turn(
        q,
        st=_st(),
        sid="s1",
        client_id="demo",
    )
    assert decision.kind == "meta_cancel"


def test_ya_ne_budu_pending_not_gray(monkeypatch: pytest.MonkeyPatch) -> None:
    decision = classify_lead_active_turn("я не буду", st=_st())
    assert decision.kind == "pending_interrupt"


def test_cancel_text_during_name_collection() -> None:
    decision = classify_lead_active_turn("не хочу записываться", st=_st())
    assert decision.kind == "meta_cancel"
    assert parse_lead_cancel("не хочу записываться")


def test_meta_pause_text_during_name_collection() -> None:
    decision = classify_lead_active_turn("задать вопрос", st=_st())
    assert decision.kind == "meta_pause"
    assert parse_lead_meta_pause("задать вопрос")


def test_pain_concern_on_name_step_is_pending_not_provider() -> None:
    decision = classify_lead_active_turn("Я боюсь боли", st=_st())
    assert decision.kind == "pending_interrupt"


def test_tooth_pain_on_name_step_is_pending() -> None:
    decision = classify_lead_active_turn("У меня болит зуб", st=_st())
    assert decision.kind == "pending_interrupt"


def test_price_question_on_name_step_is_pending() -> None:
    decision = classify_lead_active_turn("Сколько стоит имплант?", st=_st())
    assert decision.kind == "pending_interrupt"


def test_contacts_question_on_name_step_is_pending() -> None:
    decision = classify_lead_active_turn("А какой адрес?", st=_st())
    assert decision.kind == "pending_interrupt"


def test_content_heuristics_still_apply_outside_pii_slots() -> None:
    decision = classify_lead_active_turn(
        "Сколько стоит имплант?",
        st={"lead_intent": "confirming_name", "lead_flow_active": True},
    )
    assert decision.kind == "content"
    assert decision.content_hint == "price"


def test_valid_name_is_slot() -> None:
    decision = classify_lead_active_turn("Мария", st=_st())
    assert decision.kind == "slot"
    assert decision.slot_value == "Мария"


def test_rare_unknown_short_name_is_slot() -> None:
    decision = classify_lead_active_turn("Маолывр", st=_st())
    assert decision.kind == "slot"
    assert decision.slot_value == "Маолывр"


def test_ambiguous_dali_is_slot_not_pending() -> None:
    decision = classify_lead_active_turn("Дали", st=_st())
    assert decision.kind == "slot"
    assert decision.slot_value == "Дали"


@pytest.mark.parametrize(
    "q",
    [
        "Привет",
        "Шатается имплант",
        "А сколько стоит All-on-4?",
        "Когда можно записаться?",
    ],
)
def test_obvious_non_name_on_name_step_is_pending(q: str) -> None:
    decision = classify_lead_active_turn(q, st=_st())
    assert decision.kind == "pending_interrupt"


def test_ya_anna_is_slot() -> None:
    decision = classify_lead_active_turn("я Анна", st=_st())
    assert decision.kind == "slot"
    assert decision.slot_value == "Анна"


def test_invalid_name_on_name_step_is_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    decision = classify_lead_active_turn("12345", st=_st())
    assert decision.kind == "pending_interrupt"


def test_defer_phrase_exits_lead() -> None:
    decision = classify_lead_active_turn("надо подумать", st=_st())
    assert decision.kind == "defer"
    assert parse_lead_defer("надо подумать")


def test_pause_ref_is_meta_pause() -> None:
    decision = classify_lead_active_turn("", ref=LEAD_PAUSE_REF, st=_st())
    assert decision.kind == "meta_pause"
