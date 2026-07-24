from __future__ import annotations

from typing import Literal

from contracts.effective_scope import EffectiveScope
from contracts.response_schema import TargetStrategyMatch
from contracts.target_service_applicability import (
    PatientJaw,
    PatientStage,
    ReportedContext,
    SelectionPatientContext,
)


def _selection_jaw_from_effective_scope(
    effective_scope: EffectiveScope,
    *,
    jaw: PatientJaw | None,
) -> PatientJaw | None:
    if jaw is not None:
        return jaw
    if effective_scope.jaw in ("upper", "lower"):
        return effective_scope.jaw  # type: ignore[return-value]
    return None


def selection_patient_context_from_inputs(
    effective_scope: EffectiveScope,
    *,
    stage: PatientStage | None = None,
    jaw: PatientJaw | None = None,
    reported_context: ReportedContext | None = None,
) -> SelectionPatientContext:
    extent = effective_scope.extent
    return SelectionPatientContext(
        extent=extent,
        stage=stage if stage is not None else effective_scope.stage,
        jaw=_selection_jaw_from_effective_scope(effective_scope, jaw=jaw),
        reported_context=(
            reported_context
            if reported_context is not None
            else effective_scope.reported_context
        ),
    )


def strategy_match_from_effective_scope(
    effective_scope: EffectiveScope,
    *,
    service_family: str | None = None,
    stage: PatientStage | None = None,
    jaw: PatientJaw | None = None,
    reported_context: ReportedContext | None = None,
) -> TargetStrategyMatch:
    """Map AC1 scope to strategy match key; unknown axes stay unset (fail-closed downstream)."""

    extent = None
    if effective_scope.extent != "unknown":
        extent = effective_scope.extent
    return TargetStrategyMatch(
        family=service_family,
        extent=extent,
        stage=stage if stage is not None else effective_scope.stage,
        jaw=_selection_jaw_from_effective_scope(effective_scope, jaw=jaw),
        reported_context=(
            reported_context
            if reported_context is not None
            else effective_scope.reported_context
        ),
    )