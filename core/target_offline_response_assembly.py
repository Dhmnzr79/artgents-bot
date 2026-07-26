"""First vertical target response-material assembly (S27, offline and unwired)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from contracts.doctor_schema import TargetDoctorCatalog
from contracts.effective_scope import EffectiveScope
from contracts.response_schema import (
    ResponseSchemaBundle,
    TargetBrand,
    TargetCommercialFact,
    TargetOffer,
    TargetService,
    TargetStrategyMatch,
)
from contracts.response_schema_refs import ResponseSchemaExternalIndex
from contracts.service_consultation import ServiceConsultationValue
from core.service_data_context import ServiceDoctorContext
from core.target_brand_offer_projection import project_target_service_brand_offers
from core.target_brand_resolver import resolve_target_brand_term
from core.target_marketing_selector import TargetMarketingSelection
from core.target_offer_projection import project_target_service_offers
from core.target_response_evidence import build_target_response_evidence_package
from core.target_service_resolver import resolve_target_service_term
from core.target_strategy_context import strategy_match_for_explicit_service_price_lookup


@dataclass(frozen=True, slots=True)
class TargetOfflineResponseMaterials:
    service_id: str | None
    service: TargetService | None
    selected_brand_id: str | None
    brand: TargetBrand | None
    matched_rule_id: str | None
    max_options: int
    offers: tuple[TargetOffer, ...]
    doctors: tuple[ServiceDoctorContext, ...]
    selected_content_ref: str | None
    marketing_selection: TargetMarketingSelection
    commercial_facts: tuple[TargetCommercialFact, ...]
    external_source_refs: tuple[str, ...]
    consultation_close: ServiceConsultationValue | None
    marketing_slots_used: int
    amplifier_slots_used: int
    family_service_ids: tuple[str, ...] = ()


class TargetOfflineResponseAssemblyError(ValueError):
    """Typed error for an unknown exact S27 service or brand term."""

    def __init__(self, code: str, value: object) -> None:
        self.code = code
        self.value = value
        super().__init__(f"{code}: {value!r}")


def assemble_target_offline_response_materials(
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    external_index: ResponseSchemaExternalIndex,
    consultation_values: Sequence[ServiceConsultationValue],
    *,
    service_term: str,
    brand_term: str | None,
    strategy_context: TargetStrategyMatch,
    semantic_context: str,
    today: date,
    include_initial_block: bool,
    include_consultation_close: bool,
    marketing_scenarios: Sequence[str] = (),
    shown_fact_ids: Sequence[str] = (),
    shown_amplifier_refs: Sequence[str] = (),
    shown_consultation_value_refs: Sequence[str] = (),
    effective_scope: EffectiveScope | None = None,
    explicit_service_price_lookup: bool = False,
) -> TargetOfflineResponseMaterials:
    """Compose existing target selectors into one final factual material boundary."""

    service_resolution = resolve_target_service_term(bundle.services, service_term)
    if service_resolution is None:
        raise TargetOfflineResponseAssemblyError(
            "offline_assembly_service_not_found", service_term
        )

    brand_resolution = None
    if brand_term is not None:
        brand_resolution = resolve_target_brand_term(bundle.brands, brand_term)
        if brand_resolution is None:
            raise TargetOfflineResponseAssemblyError(
                "offline_assembly_brand_not_found", brand_term
            )

    evidence = build_target_response_evidence_package(
        bundle,
        doctor_catalog,
        external_index,
        consultation_values,
        service_id=service_resolution.service_id,
        selected_content_ref=service_resolution.service.content_ref,
        semantic_context=semantic_context,
        today=today,
        include_initial_block=include_initial_block,
        include_consultation_close=include_consultation_close,
        marketing_scenarios=marketing_scenarios,
        shown_fact_ids=shown_fact_ids,
        shown_amplifier_refs=shown_amplifier_refs,
        shown_consultation_value_refs=shown_consultation_value_refs,
    )

    selected_brand_id: str | None = None
    brand: TargetBrand | None = None
    projection_strategy = strategy_context
    if explicit_service_price_lookup and effective_scope is not None:
        projection_strategy = strategy_match_for_explicit_service_price_lookup(
            effective_scope,
            service_family=strategy_context.family,
        )
    if brand_resolution is None:
        projection = project_target_service_offers(
            evidence.service_context,
            bundle.strategy,
            projection_strategy,
            explicit_service_price_lookup=explicit_service_price_lookup,
            effective_scope=effective_scope,
        )
    else:
        selected_brand_id = brand_resolution.brand_id
        brand_projection = project_target_service_brand_offers(
            evidence.service_context,
            bundle.brands,
            bundle.strategy,
            strategy_context,
            selected_brand_id=selected_brand_id,
        )
        projection = brand_projection
        brand = brand_projection.brand

    return TargetOfflineResponseMaterials(
        service_id=service_resolution.service_id,
        service=evidence.service_context.service,
        selected_brand_id=selected_brand_id,
        brand=brand,
        matched_rule_id=projection.matched_rule_id,
        max_options=projection.max_options,
        offers=projection.offers,
        doctors=evidence.service_context.doctors,
        selected_content_ref=evidence.selected_content_ref,
        marketing_selection=evidence.marketing_selection,
        commercial_facts=evidence.commercial_facts,
        external_source_refs=evidence.external_source_refs,
        consultation_close=evidence.consultation_close,
        marketing_slots_used=evidence.marketing_slots_used,
        amplifier_slots_used=evidence.amplifier_slots_used,
    )
