"""Implant pain/fear intent helpers (policy / lead_interrupt). Overlay removed in E5 — routing via facet_arbitration."""
from __future__ import annotations

from policy import implant_pain_faq_intent


def test_implant_pain_faq_intent_positive() -> None:
    assert implant_pain_faq_intent("Больно ли ставить имплант?")
    assert implant_pain_faq_intent("Страшно ли делать имплантацию")
    assert implant_pain_faq_intent("Боюсь имплантации")
    assert implant_pain_faq_intent("Какая анестезия при имплантации?")


def test_implant_pain_faq_intent_negative() -> None:
    assert not implant_pain_faq_intent("Расскажите про классическую имплантацию")
    assert not implant_pain_faq_intent("Сколько стоит имплант?")
    assert not implant_pain_faq_intent("Почему импланты такие дорогие?")
    assert not implant_pain_faq_intent("Больно ли лечить кариес?")
