"""Effective patient scope merge contract (AC1 + A9R1 axis model)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from contracts.ui_scope_action import ScopeExtent
from contracts.target_service_applicability import PatientStage, ReportedContext

EffectiveScopeSource = Literal[
    "ui_action",
    "ui_stage_action",
    "a9_turn",
    "composer_decision",
    "session",
    "unknown",
]
EffectiveScopeJaw = Literal["unknown", "upper", "lower", "both"]
ScopeAxisSource = Literal[
    "ui_action",
    "ui_stage_action",
    "a9_turn",
    "composer_decision",
    "session",
    "unknown",
]


class ScopeAxisProvenance(BaseModel):
    """Per-axis source attribution for partial merge (A9R1)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: ScopeAxisSource = "unknown"
    provenance: str = Field(default="unknown", min_length=1)


class EffectiveScope(BaseModel):
    """Merged scope for product runtime; does not select treatment or service."""

    model_config = ConfigDict(extra="forbid")

    extent: ScopeExtent | Literal["unknown"] = "unknown"
    jaw: EffectiveScopeJaw = "unknown"
    stage: PatientStage | None = None
    reported_context: ReportedContext | None = None
    topic: str | None = None
    source: EffectiveScopeSource = "unknown"
    provenance: str = Field(default="unknown", min_length=1)
    extent_axis: ScopeAxisProvenance = Field(default_factory=ScopeAxisProvenance)
    jaw_axis: ScopeAxisProvenance = Field(default_factory=ScopeAxisProvenance)
    stage_axis: ScopeAxisProvenance = Field(default_factory=ScopeAxisProvenance)
    reported_context_axis: ScopeAxisProvenance = Field(
        default_factory=ScopeAxisProvenance
    )
