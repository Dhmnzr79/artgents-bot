from __future__ import annotations

from core.claim_gate import detect_forbidden_claims


def test_detect_forbidden_claims_positive_cases():
    cases = [
        "Операция пройдёт безболезненно при правильной анестезии.",
        "Мы гарантируем результат лечения.",
        "Имплант приживётся на 100%.",
        "Процедура полностью безопасна для всех пациентов.",
        "После осмотра боли совсем не будет.",
        "Вам не будет больно во время вмешательства.",
        "Гарантированный результат после установки.",
        "Стопроцентное приживление импланта.",
    ]
    for text in cases:
        assert detect_forbidden_claims(text), f"expected hit: {text!r}"


def test_detect_forbidden_claims_negative_hedged_cases():
    safe = [
        "Приживаемость обычно высокая, но зависит от состояния кости.",
        "Во время операции боли обычно не чувствуют благодаря анестезии.",
        "Максимум ощущений — лёгкий дискомфорт после процедуры.",
        "Вид анестезии подбирают индивидуально на консультации.",
        "Точнее скажет врач на осмотре после диагностики.",
        "Обычно дискомфорт минимальный, ощущения индивидуальны.",
    ]
    for text in safe:
        assert detect_forbidden_claims(text) == [], f"false positive: {text!r}"


def test_detect_forbidden_claims_fail_open_on_bad_input():
    assert detect_forbidden_claims("") == []
