from __future__ import annotations

from contracts.effective_scope import EffectiveScope
from contracts.response_schema import TargetStrategyMatch
from core.target_strategy_context import (
    selection_patient_context_from_inputs,
    strategy_match_from_effective_scope,
)


def _scope(*, extent: str = "unknown", topic: str = "implantation") -> EffectiveScope:
    return EffectiveScope(
        extent=extent,  # type: ignore[arg-type]
        topic=topic,
        source="ui_action",
        provenance="test",
    )


def test_strategy_match_maps_known_extent() -> None:
    match = strategy_match_from_effective_scope(_scope(extent="one_tooth"))
    assert match.extent == "one_tooth"
    assert match.stage is None


def test_strategy_match_unknown_extent_is_unset() -> None:
    match = strategy_match_from_effective_scope(_scope(extent="unknown"))
    assert match.extent is None


def test_selection_patient_context_unknown_extent() -> None:
    patient = selection_patient_context_from_inputs(
        _scope(extent="unknown"),
        stage="extraction_context",
    )
    assert patient.extent == "unknown"
    assert patient.stage == "extraction_context"


def test_strategy_match_passes_context_axes() -> None:
    match = strategy_match_from_effective_scope(
        _scope(extent="full_arch"),
        jaw="upper",
        reported_context="reported_bone_deficit",
    )
    assert match == TargetStrategyMatch(
        extent="full_arch",
        jaw="upper",
        reported_context="reported_bone_deficit",
    )
