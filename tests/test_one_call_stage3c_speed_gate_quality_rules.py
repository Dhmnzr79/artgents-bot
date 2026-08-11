"""Stage 3C quality scorer rule tests."""

from __future__ import annotations

from evals.v5.one_call_stage3c_speed_gate_quality_rules import (
    matches_forbidden_computed_total,
    matches_forbidden_term,
)


def test_itogo_consultation_phrase_passes() -> None:
    answer = "Итоговая сумма уточняется после консультации с администратором."
    assert not matches_forbidden_term("итого", answer)


def test_itogo_total_line_fails() -> None:
    answer = "Итого 636 000 ₽ за обе челюсти."
    assert matches_forbidden_term("итого", answer)


def test_computed_total_phrase_fails() -> None:
    answer = "Общая стоимость составит 636 000 ₽."
    assert matches_forbidden_computed_total(answer)


def test_multiplication_marker_fails() -> None:
    answer = "318 000 × 2 = 636 000 ₽"
    assert matches_forbidden_term("умнож", answer)
