"""Explicit named-service price lookup vs patient applicability (offline only)."""

from __future__ import annotations

from contracts.effective_scope import EffectiveScope, ScopeAxisSource
from contracts.response_schema import TargetOffer, TargetService
from contracts.target_service_applicability import (
    PatientJaw,
    PatientStage,
    ReportedContext,
    SelectionPatientContext,
)
from contracts.ui_scope_action import ScopeExtent
from core.target_offer_extent_applicability import (
    offer_applies_to_extent,
    resolve_offer_applies_to_extents,
)

_CURRENT_TURN_AXIS_SOURCES: frozenset[ScopeAxisSource] = frozenset(
    {"ui_action", "ui_stage_action", "a9_turn"}
)


def _axis_from_scope(
    effective_scope: EffectiveScope,
    field: str,
) -> tuple[object | None, ScopeAxisSource]:
    axis = getattr(effective_scope, f"{field}_axis")
    source = axis.source
    if source == "session":
        return None, source
    if source in _CURRENT_TURN_AXIS_SOURCES:
        return getattr(effective_scope, field), source
    if source == "unknown":
        return None, source
    return getattr(effective_scope, field), source


def lookup_patient_context_from_effective_scope(
    effective_scope: EffectiveScope,
) -> SelectionPatientContext:
    """Patient axes for catalog lookup: inherited session axes stripped."""

    extent_value, _ = _axis_from_scope(effective_scope, "extent")
    if extent_value in (None, "unknown"):
        extent: ScopeExtent | str = "unknown"
    else:
        extent = extent_value  # type: ignore[assignment]

    stage_value, _ = _axis_from_scope(effective_scope, "stage")
    stage = stage_value if isinstance(stage_value, str) else None  # type: ignore[assignment]

    jaw_value, _ = _axis_from_scope(effective_scope, "jaw")
    jaw: PatientJaw | None = None
    if jaw_value in ("upper", "lower"):
        jaw = jaw_value  # type: ignore[assignment]

    reported_value, _ = _axis_from_scope(effective_scope, "reported_context")
    reported_context = (
        reported_value if reported_value == "reported_bone_deficit" else None
    )

    return SelectionPatientContext(
        extent=extent,  # type: ignore[arg-type]
        stage=stage,
        jaw=jaw,
        reported_context=reported_context,  # type: ignore[arg-type]
    )


def lookup_extent_for_offer_filter(
    effective_scope: EffectiveScope,
) -> ScopeExtent | None:
    patient = lookup_patient_context_from_effective_scope(effective_scope)
    if patient.extent == "unknown":
        return None
    return patient.extent  # type: ignore[return-value]


def explicit_lookup_applicability_patient(
    effective_scope: EffectiveScope,
) -> SelectionPatientContext:
    """Applicability gate for explicit named-service price lookup."""

    return lookup_patient_context_from_effective_scope(effective_scope)


def explicit_lookup_offer_extent_conflicts(
    service: TargetService,
    offers: tuple[TargetOffer, ...],
    effective_scope: EffectiveScope,
) -> bool:
    """True when current-turn extent excludes every authored public offer."""

    lookup_extent = lookup_extent_for_offer_filter(effective_scope)
    if lookup_extent is None:
        return False
    if not offers:
        return True
    return not any(
        offer_applies_to_extent(offer, service, lookup_extent) for offer in offers
    )


def explicit_lookup_service_selection_conflicts(
    service: TargetService,
    effective_scope: EffectiveScope,
) -> bool:
    """True when current-turn extent cannot match any authored offer extent."""

    lookup_extent = lookup_extent_for_offer_filter(effective_scope)
    if lookup_extent is None:
        return False
    authored_extents: set[ScopeExtent] = set()
    selection = service.selection
    if selection.extent:
        authored_extents.update(selection.extent)  # type: ignore[arg-type]
    for offer in service.options:
        if offer.selection and offer.selection.extent:
            authored_extents.update(offer.selection.extent)  # type: ignore[arg-type]
    if authored_extents and lookup_extent not in authored_extents:
        return True
    if not authored_extents:
        return False
    return False


def filter_offers_for_explicit_lookup(
    offers: tuple[TargetOffer, ...],
    service: TargetService,
    effective_scope: EffectiveScope,
) -> tuple[TargetOffer, ...]:
    lookup_extent = lookup_extent_for_offer_filter(effective_scope)
    if lookup_extent is None:
        return offers
    return tuple(
        offer
        for offer in offers
        if offer_applies_to_extent(offer, service, lookup_extent)
    )


def authored_offer_extents_union(
    service: TargetService,
    offers: tuple[TargetOffer, ...],
) -> tuple[ScopeExtent, ...]:
    extents: list[ScopeExtent] = []
    seen: set[ScopeExtent] = set()
    for offer in offers:
        for extent in resolve_offer_applies_to_extents(offer, service):
            if extent not in seen:
                seen.add(extent)
                extents.append(extent)
    return tuple(extents)
