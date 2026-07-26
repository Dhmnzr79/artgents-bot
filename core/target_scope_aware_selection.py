"""Compose scope-aware selection from AC1 scope + S15/S23/S24 (AC2, offline only)."""

from __future__ import annotations

from contracts.doctor_schema import TargetDoctorCatalog
from contracts.effective_scope import EffectiveScope
from contracts.response_schema import ResponseSchemaBundle, TargetOffer
from contracts.target_scope_aware_selection import (
    SelectionKind,
    TargetPriceAnchor,
    TargetScopeAwareSelectionResult,
)
from contracts.target_service_applicability import SelectionPatientContext
from core.response_strategy import resolve_target_strategy
from core.service_data_context import build_service_data_context
from core.target_brand_offer_projection import project_target_service_brand_offers
from core.target_offer_projection import project_target_service_offers
from core.target_service_applicability import filter_applicable_services
from core.target_family_price_resolution import (
    PROTOCOL_PRICE_UNCONFIRMED_PREFIX,
    build_family_only_broad_selection,
    list_family_prices_for_topic,
)
from core.target_offer_price_reachability import (
    assess_broad_extent_coverages,
    merge_stage_reachable_offers_by_service,
)
from core.target_explicit_service_price_lookup import (
    lookup_patient_context_from_effective_scope,
)
from core.target_strategy_context import (
    selection_patient_context_from_inputs,
    strategy_match_for_explicit_service_price_lookup,
    strategy_match_from_effective_scope,
)

_BROAD_ANCHOR_EXTENTS = ("one_tooth", "full_arch", "few_teeth")


def _project_offers_for_service(
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    *,
    service_id: str,
    strategy_context,
    selected_option_id: str | None,
    selected_brand_id: str | None,
    explicit_offer_id: str | None,
    effective_scope: EffectiveScope | None = None,
    explicit_service_price_lookup: bool = False,
) -> tuple[TargetOffer, ...]:
    context = build_service_data_context(bundle, doctor_catalog, service_id)
    projection_strategy = strategy_context
    if explicit_service_price_lookup and effective_scope is not None:
        projection_strategy = strategy_match_for_explicit_service_price_lookup(
            effective_scope,
            service_family=strategy_context.family,
        )
    if selected_brand_id:
        brand_projection = project_target_service_brand_offers(
            context,
            bundle.brands,
            bundle.strategy,
            projection_strategy,
            selected_brand_id=selected_brand_id,
            selected_option_id=selected_option_id,
            explicit_offer_id=explicit_offer_id,
        )
        return brand_projection.offers
    projection = project_target_service_offers(
        context,
        bundle.strategy,
        projection_strategy,
        selected_option_id=selected_option_id,
        explicit_offer_id=explicit_offer_id,
        effective_scope=effective_scope,
        explicit_service_price_lookup=explicit_service_price_lookup,
    )
    return projection.offers


def _scoped_selection(
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    *,
    effective_scope: EffectiveScope,
    topic: str,
    patient: SelectionPatientContext,
    strategy_context,
    explicit_service_id: str | None,
    explicit_offer_id: str | None,
    selected_option_id: str | None,
    selected_brand_id: str | None,
    explicit_service_price_lookup: bool = False,
) -> TargetScopeAwareSelectionResult:
    applicable = filter_applicable_services(
        bundle,
        topic=topic,
        strategy_context=strategy_context,
        patient=patient,
        explicit_service_id=explicit_service_id,
        explicit_service_price_lookup=explicit_service_price_lookup,
    )
    if not applicable:
        return TargetScopeAwareSelectionResult(
            topic=topic,
            effective_scope=effective_scope,
            kind="scoped_shortlist",
            strategy_context=strategy_context,
            matched_rule_id=None,
            service_ids=(),
            offers_by_service_id={},
            exclusions=("no_applicable_services",),
        )

    resolution = resolve_target_strategy(
        bundle.strategy,
        strategy_context,
        service_ids=tuple(item.service_id for item in applicable),
        explicit_service_id=explicit_service_id,
    )
    offers_by_service: dict[str, tuple[TargetOffer, ...]] = {}
    exclusions: list[str] = []
    for service_id in resolution.service_ids:
        entry = next(item for item in applicable if item.service_id == service_id)
        option_pin = selected_option_id
        if option_pin is None and len(entry.eligible_option_ids) == 1:
            option_pin = entry.eligible_option_ids[0]
        offers = _project_offers_for_service(
            bundle,
            doctor_catalog,
            service_id=service_id,
            strategy_context=strategy_context,
            selected_option_id=option_pin,
            selected_brand_id=selected_brand_id,
            explicit_offer_id=explicit_offer_id if service_id == explicit_service_id else None,
            effective_scope=effective_scope,
            explicit_service_price_lookup=explicit_service_price_lookup,
        )
        if offers:
            offers_by_service[service_id] = offers
        else:
            exclusions.append(f"no_public_or_missing_offers:{service_id}")

    if not offers_by_service:
        exclusions.append("no_applicable_offers")
    elif (
        explicit_service_id is not None
        and explicit_service_id not in offers_by_service
        and explicit_service_id in bundle.services
        and bundle.services[explicit_service_id].active
        and list_family_prices_for_topic(bundle, topic)
    ):
        exclusions.append(f"{PROTOCOL_PRICE_UNCONFIRMED_PREFIX}{explicit_service_id}")

    return TargetScopeAwareSelectionResult(
        topic=topic,
        effective_scope=effective_scope,
        kind="scoped_shortlist",
        strategy_context=strategy_context,
        matched_rule_id=resolution.matched_rule_id,
        service_ids=resolution.service_ids,
        offers_by_service_id=offers_by_service,
        exclusions=tuple(exclusions),
        price_confirmed_extents=(
            (patient.extent,)  # type: ignore[return-value]
            if offers_by_service and patient.extent is not None
            else ()
        ),
        price_navigable_extents=(
            (patient.extent,)  # type: ignore[return-value]
            if offers_by_service and patient.extent is not None
            else ()
        ),
    )


def _broad_anchor_selection(
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    *,
    effective_scope: EffectiveScope,
    topic: str,
    base_patient: SelectionPatientContext,
    strategy_context,
    stage,
    jaw,
    reported_context,
) -> TargetScopeAwareSelectionResult:
    anchors: list[TargetPriceAnchor] = []
    anchor_service_ids: list[str] = []
    exclusions: list[str] = []

    for extent in _BROAD_ANCHOR_EXTENTS:
        scoped_scope = effective_scope.model_copy(update={"extent": extent})
        patient = SelectionPatientContext(
            extent=extent,
            stage=base_patient.stage,
            jaw=base_patient.jaw,
            reported_context=base_patient.reported_context,
        )
        scoped_strategy = strategy_match_from_effective_scope(
            scoped_scope,
            stage=stage,
            jaw=jaw,
            reported_context=reported_context,
        )
        applicable = filter_applicable_services(
            bundle,
            topic=topic,
            strategy_context=scoped_strategy,
            patient=patient,
        )
        if not applicable:
            exclusions.append(f"no_anchor_applicable:{extent}")
            continue
        resolution = resolve_target_strategy(
            bundle.strategy,
            scoped_strategy,
            service_ids=tuple(item.service_id for item in applicable),
        )
        if not resolution.service_ids:
            exclusions.append(f"no_anchor_ranked:{extent}")
            continue
        anchor_offer = None
        anchor_service_id = None
        for top_service_id in resolution.service_ids:
            offers = _project_offers_for_service(
                bundle,
                doctor_catalog,
                service_id=top_service_id,
                strategy_context=scoped_strategy,
                selected_option_id=None,
                selected_brand_id=None,
                explicit_offer_id=None,
            )
            if offers and offers[0].price.mode in {"fixed", "from", "range"}:
                anchor_offer = offers[0]
                anchor_service_id = top_service_id
                break
        if anchor_offer is None:
            exclusions.append(f"no_anchor_offers:{extent}")
            continue
        anchors.append(
            TargetPriceAnchor(
                extent=extent,
                service_id=anchor_service_id,
                offer_id=anchor_offer.offer_id,
            )
        )
        anchor_service_ids.append(anchor_service_id)

    coverages = assess_broad_extent_coverages(
        bundle,
        doctor_catalog,
        effective_scope=effective_scope,
        topic=topic,
        base_patient=base_patient,
        anchor_extents=_BROAD_ANCHOR_EXTENTS,
        stage=stage,
        jaw=jaw,
        reported_context=reported_context,
    )
    price_navigable_extents = tuple(
        coverage.extent for coverage in coverages if coverage.navigable
    )
    stage_offers_by_service = merge_stage_reachable_offers_by_service(coverages)
    stage_service_ids = tuple(stage_offers_by_service.keys())

    if not anchors:
        family_records = list_family_prices_for_topic(bundle, topic)
        if family_records:
            return build_family_only_broad_selection(
                bundle,
                family_price=family_records[0],
                topic=topic,
                effective_scope=effective_scope,
                strategy_context=strategy_context,
                matched_rule_id=None,
            )

    return TargetScopeAwareSelectionResult(
        topic=topic,
        effective_scope=effective_scope,
        kind="broad_anchors",
        strategy_context=strategy_context,
        matched_rule_id=None,
        service_ids=tuple(dict.fromkeys((*anchor_service_ids, *stage_service_ids))),
        offers_by_service_id=stage_offers_by_service,
        anchors=tuple(anchors),
        exclusions=tuple(exclusions),
        price_confirmed_extents=tuple(anchor.extent for anchor in anchors),
        price_navigable_extents=price_navigable_extents,
    )


def run_target_scope_aware_selection(
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    *,
    effective_scope: EffectiveScope,
    topic: str,
    explicit_service_id: str | None = None,
    explicit_offer_id: str | None = None,
    selected_option_id: str | None = None,
    selected_brand_id: str | None = None,
    stage: str | None = None,
    jaw: str | None = None,
    reported_context: str | None = None,
) -> TargetScopeAwareSelectionResult:
    """Pure offline scope-aware selection; not wired to runtime/widget."""

    patient = selection_patient_context_from_inputs(
        effective_scope,
        stage=stage,  # type: ignore[arg-type]
        jaw=jaw,  # type: ignore[arg-type]
        reported_context=reported_context,  # type: ignore[arg-type]
    )
    strategy_context = strategy_match_from_effective_scope(
        effective_scope,
        stage=stage,  # type: ignore[arg-type]
        jaw=jaw,  # type: ignore[arg-type]
        reported_context=reported_context,  # type: ignore[arg-type]
    )

    if explicit_service_id is not None:
        lookup_patient = lookup_patient_context_from_effective_scope(effective_scope)
        return _scoped_selection(
            bundle,
            doctor_catalog,
            effective_scope=effective_scope,
            topic=topic,
            patient=lookup_patient,
            strategy_context=strategy_context,
            explicit_service_id=explicit_service_id,
            explicit_offer_id=explicit_offer_id,
            selected_option_id=selected_option_id,
            selected_brand_id=selected_brand_id,
            explicit_service_price_lookup=True,
        )

    if effective_scope.extent == "unknown":
        return _broad_anchor_selection(
            bundle,
            doctor_catalog,
            effective_scope=effective_scope,
            topic=topic,
            base_patient=patient,
            strategy_context=strategy_context,
            stage=stage,
            jaw=jaw,
            reported_context=reported_context,
        )

    return _scoped_selection(
        bundle,
        doctor_catalog,
        effective_scope=effective_scope,
        topic=topic,
        patient=patient,
        strategy_context=strategy_context,
        explicit_service_id=None,
        explicit_offer_id=explicit_offer_id,
        selected_option_id=selected_option_id,
        selected_brand_id=selected_brand_id,
    )
