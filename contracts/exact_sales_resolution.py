"""Typed, offline result for deterministic exact sales facts.

This contract deliberately represents only already-authoritative inputs.  It is
not a classifier, a treatment selector, or a price calculator.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from contracts.answer_plan import AspectKind
from contracts.target_service_applicability import PatientStage
from contracts.ui_scope_action import ScopeExtent

ExactSalesAuthority = Literal[
    "governed_ui",
    "exact_turn",
    "valid_session",
    "unknown",
]
ExactSalesFieldName = Literal["service_id", "aspect", "extent", "jaw", "stage"]
ExactSalesJaw = Literal["upper", "lower", "both"]


@dataclass(frozen=True, slots=True)
class ExactSalesFieldAuthority:
    """Source that was allowed to set one resolver field."""

    authority: ExactSalesAuthority
    provenance: str


@dataclass(frozen=True, slots=True)
class ExactSalesConflict:
    """Visible precedence conflict; the resolver never silently merges values."""

    field: ExactSalesFieldName
    selected_value: str | None
    selected_authority: ExactSalesAuthority
    rejected_value: str | None
    rejected_authority: ExactSalesAuthority


@dataclass(frozen=True, slots=True)
class ExactSalesResolution:
    """Exact sales facts plus source for every exposed axis.

    ``jaw="both"`` is an accepted scope fact only.  This type intentionally
    carries no offer, amount, billing unit, or inferred service choice.
    """

    service_id: str | None
    aspect: AspectKind | None
    extent: ScopeExtent | None
    jaw: ExactSalesJaw | None
    stage: PatientStage | None
    service_id_authority: ExactSalesFieldAuthority
    aspect_authority: ExactSalesFieldAuthority
    extent_authority: ExactSalesFieldAuthority
    jaw_authority: ExactSalesFieldAuthority
    stage_authority: ExactSalesFieldAuthority
    conflicts: tuple[ExactSalesConflict, ...] = ()
