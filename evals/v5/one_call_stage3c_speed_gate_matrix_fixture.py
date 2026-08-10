"""Frozen Stage 2 snapshot rows for Stage 3C matrix (eval-only, no tests.* imports)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FrozenStage2Snapshot:
    case_id: str
    user_message: str
    expected_decision: str
    execution_layer: str
    critical_required_all: tuple[str, ...] = ()
    noncritical_review_any: tuple[tuple[str, ...], ...] = ()
    forbidden_terms: tuple[str, ...] = ()
    forbidden_price_tokens: tuple[str, ...] = ()


# Pinned subset of tests/fixtures/one_call_stage2_cases.json referenced by Stage 3C matrix.
FROZEN_STAGE2_SNAPSHOTS: dict[str, FrozenStage2Snapshot] = {
    "m01": FrozenStage2Snapshot(
        case_id="m01",
        user_message="Есть ли парковка?",
        expected_decision="answer",
        execution_layer="model",
        critical_required_all=("парков", "2", "бесплат"),
    ),
    "p03": FrozenStage2Snapshot(
        case_id="p03",
        user_message="Сколько стоит классический имплант за один зуб?",
        expected_decision="answer",
        execution_layer="model",
        critical_required_all=("76",),
        noncritical_review_any=(("зуб",), ("рассроч", "бесплатн")),
        forbidden_terms=("примерно", "от 76200"),
    ),
    "p04": FrozenStage2Snapshot(
        case_id="p04",
        user_message="Сколько будет All-on-4 на обе челюсти?",
        expected_decision="answer",
        execution_layer="model",
        noncritical_review_any=(("консультац", "уточн"),),
        forbidden_terms=("умнож", "итого"),
        forbidden_price_tokens=("636000",),
    ),
    "f01": FrozenStage2Snapshot(
        case_id="f01",
        user_message="Боюсь боли при имплантации",
        expected_decision="answer",
        execution_layer="model",
        critical_required_all=(),
        noncritical_review_any=(("консультац",), ("боль", "анестез")),
    ),
    "a01": FrozenStage2Snapshot(
        case_id="a01",
        user_message="Как тяжёлые хронические заболевания влияют на возможность имплантации?",
        expected_decision="admin",
        execution_layer="local",
    ),
    "a02": FrozenStage2Snapshot(
        case_id="a02",
        user_message="После операции появилось воспаление, подскажите порядок действий",
        expected_decision="admin",
        execution_layer="local",
    ),
    "a03": FrozenStage2Snapshot(
        case_id="a03",
        user_message="Как подбирают лечение при сложных противопоказаниях к имплантации?",
        expected_decision="admin",
        execution_layer="local",
    ),
}


def snapshot_by_id(case_id: str) -> FrozenStage2Snapshot:
    try:
        return FROZEN_STAGE2_SNAPSHOTS[case_id]
    except KeyError as exc:
        raise KeyError(case_id) from exc
