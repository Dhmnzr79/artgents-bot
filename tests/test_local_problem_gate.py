from __future__ import annotations

import pytest
from pydantic import ValidationError

from contracts.local_problem_gate import LocalProblemGateResult
from core.local_problem_gate import LocalProblemGateError, decide_local_problem_gate


@pytest.mark.parametrize(
    ("text", "reason_code"),
    [
        ("Сейчас сильно болит зуб", "current_symptom"),
        ("Кровоточит и опухло после лечения", "current_symptom"),
        ("Хочу пожаловаться", "complaint_or_management"),
        ("Дайте директора", "complaint_or_management"),
        ("Хочу оставить негативный отзыв", "complaint_or_management"),
        ("Какой у меня диагноз?", "diagnosis_request"),
        ("Посмотрите по фото и скажите, что с зубом", "diagnosis_request"),
        ("Что принимать и какая дозировка?", "personal_treatment_request"),
        ("Что лучше мне — имплант или мост?", "personal_treatment_request"),
        ("Имплант шатается и десна не заживает", "current_symptom"),
        ("Как оставить отзыв о клинике?", "complaint_or_management"),
        ("После операции появилось воспаление, подскажите порядок действий", "post_procedure_complication"),
    ],
)
def test_explicit_problem_cases_route_to_admin(text: str, reason_code: str) -> None:
    result = decide_local_problem_gate(text)

    assert result.decision == "admin"
    assert result.reason_code == reason_code


@pytest.mark.parametrize(
    "text",
    [
        "Как тяжёлые хронические заболевания влияют на возможность имплантации?",
        "Как подбирают лечение при сложных противопоказаниях к имплантации?",
        "Какие бывают противопоказания к имплантации?",
        "Как хронические заболевания учитывают перед имплантацией?",
        "Боюсь, что будет больно",
        "Боюсь, что имплант не приживется",
        "Сколько стоит имплантация?",
        "Есть ли парковка?",
        "Как вы стерилизуете инструменты?",
        "Какая температура стерилизации инструментов?",
        "Болит ли устанавливать имплант?",
        "Боюсь, что имплант будет шататься",
        "Чем имплант отличается от моста?",
        "Где почитать отзывы?",
        "А если потом будет непросто?",
        "",
    ],
)
def test_commercial_facts_future_fears_and_general_medical_faq_pass(text: str) -> None:
    result = decide_local_problem_gate(text)

    assert result.decision == "pass"
    assert result.reason_code == "no_high_precision_match"


def test_obvious_text_noise_is_spam() -> None:
    result = decide_local_problem_gate("!!!!!")

    assert result.decision == "spam"
    assert result.reason_code == "obvious_text_noise"


@pytest.mark.parametrize(
    "text",
    ["У меня болит зуб", "После имплантации болит десна"],
)
def test_explicit_current_pain_remains_admin(text: str) -> None:
    assert decide_local_problem_gate(text).decision == "admin"


def test_contract_is_strict_and_does_not_contain_raw_text() -> None:
    with pytest.raises(ValidationError, match="local_problem_gate_result_inconsistent"):
        LocalProblemGateResult(decision="pass", reason_code="current_symptom")
    with pytest.raises(LocalProblemGateError, match="local_problem_gate_text_invalid"):
        decide_local_problem_gate(None)  # type: ignore[arg-type]
