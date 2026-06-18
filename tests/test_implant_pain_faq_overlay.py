"""Implant pain/fear FAQ overlay (pre-A3, like contacts)."""
from __future__ import annotations

from policy import implant_pain_faq_intent, pick_implant_pain_faq_chunk


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


def test_pick_implant_pain_faq_chunk() -> None:
    cands = [
        {"file": "implantation__service__classic.md", "h3_id": "korotko"},
        {"file": "implantation__faq__pain.md", "h3_id": "korotko"},
    ]
    picked = pick_implant_pain_faq_chunk(cands)
    assert picked is not None
    assert picked["file"] == "implantation__faq__pain.md"
