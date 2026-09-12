"""Selection applicability contracts (AC2)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from contracts.response_schema import TargetService
from contracts.ui_scope_action import ScopeExtent

PatientStage = Literal["natural_tooth_present", "extraction_context", "implant_placed"]
PatientJaw = Literal["upper", "lower"]
ReportedContext = Literal["reported_bone_deficit"]


@dataclass(frozen=True, slots=True)
class SelectionPatientContext:
    """Known patient axes for service_catalog.selection matching."""

    extent: ScopeExtent | Literal["unknown"] = "unknown"
    stage: PatientStage | None = None
    jaw: PatientJaw | None = None
    reported_context: ReportedContext | None = None


@dataclass(frozen=True, slots=True)
class TargetApplicableService:
    service_id: str
    service: TargetService
    eligible_option_ids: tuple[str, ...]
