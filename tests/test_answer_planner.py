from __future__ import annotations

from core.answer_planner import detect_aspects


def test_detect_aspects_price_and_payment():
    aspects = detect_aspects("Сколько стоит имплант и есть ли рассрочка?")
    assert "price" in aspects
    assert "payment" in aspects


def test_detect_aspects_warranty_for_service_question():
    aspects = detect_aspects("А вы делаете all-on-4 и какие гарантии на нее?")
    assert "warranty" in aspects


def test_detect_aspects_overview_for_deictic_followup():
    aspects = detect_aspects("а это?")
    assert aspects == ["overview"]
