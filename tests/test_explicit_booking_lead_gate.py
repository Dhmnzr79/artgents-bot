"""Pre-Resolver lead gate: regex-only explicit booking (plan A)."""

from __future__ import annotations

from policy import booking_intent, explicit_booking_intent


def test_explicit_booking_matches_record_phrases():
    assert explicit_booking_intent("Хочу записаться") is True
    assert explicit_booking_intent("Можно записаться сегодня?") is True
    assert explicit_booking_intent("Очень болит зуб, срочно запишите меня пожалуйста") is True


def test_explicit_booking_rejects_content_intent_without_record_phrase():
    assert explicit_booking_intent("Я хочу удалить зуб и поставить имплант") is False
    assert explicit_booking_intent("Болит зуб, можете принять сегодня?") is False
    assert explicit_booking_intent("Хочу проконсультироваться по имплантации") is False


def test_booking_intent_llm_not_used_for_explicit_gate(monkeypatch):
    """explicit_booking_intent never calls LLM; booking_intent may (policy/CTA)."""

    def _boom(*_a, **_kw):
        raise AssertionError("LLM must not run for explicit_booking_intent")

    monkeypatch.setattr("policy.classify_booking_wants_appointment", _boom)
    assert explicit_booking_intent("Я хочу удалить зуб и поставить имплант") is False
