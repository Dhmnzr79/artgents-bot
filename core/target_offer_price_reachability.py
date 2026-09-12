"""Deterministic one-hop price reachability for scope navigation (offline only)."""

from __future__ import annotations

from dataclasses import dataclass

from contracts.doctor_schema import TargetDoctorCatalog
from contracts.effective_scope import EffectiveScope
from contracts.response_schema import ResponseSchemaBundle, TargetOffer
from contracts.target_service_applicability import SelectionPatientContext
from contracts.ui_scope_action import ScopeExtent
from core.target_response_stage import discover_stage_clarification_stages

_CONFIRMED_PRICE_MODES = frozenset({"fixed", "from", "range", "no_public_price"})


@dataclass(frozen=True, slots=True)
class ExtentPriceCoverage:
    extent: ScopeExtent
    immediate: bool
    navigable: bool
    stage_reachable_offers: tuple[TargetOffer, ...] = ()


def offers_have_confirmed_price(offers: tuple[TargetOffer, ...]) -> bool:
    return any(offer.price.mode in _CONFIRMED_PRICE_MODES for offer in offers)


def _confirmed_offers_from_selection(selection) -> tuple[TargetOffer, ...]:
    collected: list[TargetOffer] = []
    for service_offers in selection.offers_by_service_id.values():
        for offer in service_offers:
            if offer.price.mode in _CONFIRMED_PRICE_MODES:
                collected.append(offer)
    return tuple(collected)


def _trial_selection(
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    *,
    effective_scope: EffectiveScope,
    topic: str,
    patient: SelectionPatientContext,
    stage: str | None,
    jaw: str | None,
    reported_context: str | None,
):
    from core.target_scope_aware_selection import run_target_scope_aware_selection

    return run_target_scope_aware_selection(
        bundle,
        doctor_catalog,
        effective_scope=effective_scope,
        topic=topic,
        stage=stage,  # type: ignore[arg-type]
        jaw=jaw,  # type: ignore[arg-type]
        reported_context=reported_context,  # type: ignore[arg-type]
    )


def assess_extent_price_coverage(
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    *,
    effective_scope: EffectiveScope,
    topic: str,
    extent: ScopeExtent,
    base_patient: SelectionPatientContext,
    stage: str | None,
    jaw: str | None,
    reported_context: str | None,
) -> ExtentPriceCoverage:
    scoped_scope = effective_scope.model_copy(update={"extent": extent})
    patient = SelectionPatientContext(
        extent=extent,
        stage=base_patient.stage,
        jaw=base_patient.jaw,
        reported_context=base_patient.reported_context,
    )
    immediate_selection = _trial_selection(
        bundle,
        doctor_catalog,
        effective_scope=scoped_scope,
        topic=topic,
        patient=patient,
        stage=stage,
        jaw=jaw,
        reported_context=reported_context,
    )
    immediate_offers = _confirmed_offers_from_selection(immediate_selection)
    if immediate_offers:
        return ExtentPriceCoverage(
            extent=extent,
            immediate=True,
            navigable=True,
            stage_reachable_offers=(),
        )

    stage_patient = SelectionPatientContext(
        extent=extent,
        stage=None,
        jaw=base_patient.jaw,
        reported_context=base_patient.reported_context,
    )
    stage_candidates = discover_stage_clarification_stages(
        bundle,
        topic=topic,
        patient=stage_patient,
    )
    stage_offers: list[TargetOffer] = []
    seen_offer_ids: set[str] = set()
    for trial_stage in stage_candidates:
        trial_selection = _trial_selection(
            bundle,
            doctor_catalog,
            effective_scope=scoped_scope,
            topic=topic,
            patient=SelectionPatientContext(
                extent=extent,
                stage=trial_stage,
                jaw=base_patient.jaw,
                reported_context=base_patient.reported_context,
            ),
            stage=trial_stage,
            jaw=jaw,
            reported_context=reported_context,
        )
        for offer in _confirmed_offers_from_selection(trial_selection):
            if offer.offer_id in seen_offer_ids:
                continue
            stage_offers.append(offer)
            seen_offer_ids.add(offer.offer_id)

    navigable = bool(stage_offers)
    return ExtentPriceCoverage(
        extent=extent,
        immediate=False,
        navigable=navigable,
        stage_reachable_offers=tuple(stage_offers),
    )


def assess_broad_extent_coverages(
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    *,
    effective_scope: EffectiveScope,
    topic: str,
    base_patient: SelectionPatientContext,
    anchor_extents: tuple[ScopeExtent, ...],
    stage: str | None,
    jaw: str | None,
    reported_context: str | None,
) -> tuple[ExtentPriceCoverage, ...]:
    return tuple(
        assess_extent_price_coverage(
            bundle,
            doctor_catalog,
            effective_scope=effective_scope,
            topic=topic,
            extent=extent,
            base_patient=base_patient,
            stage=stage,
            jaw=jaw,
            reported_context=reported_context,
        )
        for extent in anchor_extents
    )


def merge_stage_reachable_offers_by_service(
    coverages: tuple[ExtentPriceCoverage, ...],
) -> dict[str, tuple[TargetOffer, ...]]:
    by_service: dict[str, list[TargetOffer]] = {}
    seen_offer_ids: set[str] = set()
    for coverage in coverages:
        if coverage.immediate:
            continue
        for offer in coverage.stage_reachable_offers:
            if offer.offer_id in seen_offer_ids:
                continue
            by_service.setdefault(offer.service_id, []).append(offer)
            seen_offer_ids.add(offer.offer_id)
    return {service_id: tuple(offers) for service_id, offers in by_service.items()}
