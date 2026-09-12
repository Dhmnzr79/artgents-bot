"""A9 patient-scope projection types (A9R1, offline/unwired)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from contracts.target_service_applicability import PatientStage, ReportedContext
from contracts.ui_scope_action import ScopeExtent

NATIVE_PATIENT_SCOPE_PROVENANCE_PREFIX = "turn_plan.raw.patient_scope"

ProjectedExtent = ScopeExtent | Literal["unknown"]
ProjectedJaw = Literal["unknown", "upper", "lower", "both"]
ProjectedStage = PatientStage | Literal["unknown"]


@dataclass(frozen=True, slots=True)
class ProjectedScopeAxis:
    """One projected axis from TurnFrame.patient_scope field metadata."""

    value: str | None
    provenance: str
    usable: bool


@dataclass(frozen=True, slots=True)
class ProjectedPatientScope:
    """Native planner patient_scope projection; not merged with session/UI."""

    extent: ProjectedScopeAxis
    jaw: ProjectedScopeAxis
    stage: ProjectedScopeAxis
    reported_context: ProjectedScopeAxis

    @property
    def has_usable_axis(self) -> bool:
        return any(
            axis.usable
            for axis in (
                self.extent,
                self.jaw,
                self.stage,
                self.reported_context,
            )
        )
