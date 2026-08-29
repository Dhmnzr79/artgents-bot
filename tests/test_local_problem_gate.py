from __future__ import annotations

import pytest
from pydantic import ValidationError

from contracts.local_problem_gate import LocalProblemGateResult
from core.local_problem_gate import LocalProblemGateError, decide_local_problem_gate


@pytest.mark.parametrize(
    "text",
    [
        "Сейчас сильно болит зуб",
        "Хочу пожаловаться",
        "Какой у меня диагноз?",
        "Что принимать и какая дозировка?",
        "Как оставить отзыв о клинике?",
        "Хочу оставить положительный отзыв",
        "Свяжите меня с врачом",
        "Боюсь, что будет больно",
        "Чем имплант отличается от моста?",
    ],
)
def test_meaningful_messages_pass_to_composer(text: str) -> None:
    result = decide_local_problem_gate(text)

    assert result.decision == "pass"
    assert result.reason_code == "no_high_precision_match"


def test_obvious_text_noise_is_spam() -> None:
    result = decide_local_problem_gate("!!!!!")

    assert result.decision == "spam"
    assert result.reason_code == "obvious_text_noise"


def test_contract_is_strict_and_does_not_contain_raw_text() -> None:
    with pytest.raises(ValidationError, match="local_problem_gate_result_inconsistent"):
        LocalProblemGateResult(decision="spam", reason_code="no_high_precision_match")
    with pytest.raises(LocalProblemGateError, match="local_problem_gate_text_invalid"):
        decide_local_problem_gate(None)  # type: ignore[arg-type]
