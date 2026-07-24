"""Effective patient scope merge contract (AC1)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from contracts.ui_scope_action import ScopeExtent
from contracts.target_service_applicability import PatientStage

EffectiveScopeSource = Literal["ui_action", "ui_stage_action", "session", "unknown"]


class EffectiveScope(BaseModel):
    """Merged scope for product runtime; does not select treatment or service."""

    model_config = ConfigDict(extra="forbid")

    extent: ScopeExtent | Literal["unknown"] = "unknown"
    stage: PatientStage | None = None
    topic: str | None = None
    source: EffectiveScopeSource = "unknown"
    provenance: str = Field(default="unknown", min_length=1)
