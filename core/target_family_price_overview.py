"""Deterministic family price overview selection and assembly (W1)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from pathlib import Path

from contracts.doctor_schema import TargetDoctorCatalog
from contracts.response_schema import ResponseSchemaBundle, TargetOffer, TargetStrategyMatch
from contracts.response_schema_refs import ResponseSchemaExternalIndex
from contracts.service_consultation import ServiceConsultationValue
from contracts.target_family_price_overview import (
    FamilyPriceOverviewSelection,
    FamilyPriceOverviewServiceEntry,
)
from contracts.target_response_spec import TargetResponseSpec
from contracts.target_service_content_topic import service_catalog_content_topic_matches
from core.service_data_context import build_service_data_context
from core.target_marketing_selector import TargetMarketingSelection
from core.target_offer_projection import project_target_service_offers
from core.target_offline_response_assembly import TargetOfflineResponseMaterials
from core.target_offline_response_package import TargetOfflineResponsePackage
from core.target_response_followup_materializer import materialize_target_response_followups
from core.target_response_followup_policy import (
    TargetResponseFollowupSelection,
    select_target_response_followups,
)
from core.target_response_materialization_plan import build_target_response_materialization_plan

FAMILY_PRICE_OVERVIEW_MAX_SERVICES = 4

_ROLE_RANK = {
    "protocol": 0,
    "advanced_protocol": 1,
    "supporting": 2,
}


class TargetFamilyPriceOverviewError(ValueError):
    """Typed fail-closed family price overview failure."""

    def __init__(self, code: str, value: object) -> None:
        self.code = code
        self.value = value
        super().__init__(f"{code}: {value!r}")


def is_family_price_overview_spec(spec: TargetResponseSpec) -> bool:
    """True when spec declares a multi-service family price overview."""

    if type(spec) is not TargetResponseSpec:
        return False
    return (
        spec.response_mode == "answer"
        and spec.service_id is None
        and spec.family_price_overview_topic is not None
        and spec.required_components == ("price",)
        and spec.followup_source is None
        and not spec.allow_marketing_facts
        and not spec.allow_cta
    )


def _role_rank(roles: tuple[str, ...]) -> int:
    ranks = [_ROLE_RANK[role] for role in roles if role in _ROLE_RANK]
    return min(ranks) if ranks else 3


def _representative_offer(
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    service_id: str,
) -> TargetOffer | None:
    context = build_service_data_context(bundle, doctor_catalog, service_id)
    projection = project_target_service_offers(
        context,
        bundle.strategy,
        TargetStrategyMatch(family=None, extent=None),
    )
    if not projection.offers:
        return None
    return projection.offers[0]


def select_family_price_overview_services(
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    *,
    turn_topic: str,
    max_services: int = FAMILY_PRICE_OVERVIEW_MAX_SERVICES,
) -> FamilyPriceOverviewSelection:
    """Select priced services for one topic using catalog membership and deterministic order."""

    if type(turn_topic) is not str or not turn_topic.strip():
        raise TargetFamilyPriceOverviewError("family_overview_topic_invalid", turn_topic)
    topic = turn_topic.strip()

    candidates: list[FamilyPriceOverviewServiceEntry] = []
    for catalog_order, (service_id, service) in enumerate(bundle.services.items()):
        if not service.active:
            continue
        if not service_catalog_content_topic_matches(service.content_ref, topic):
            continue
        offer = _representative_offer(bundle, doctor_catalog, service_id)
        if offer is None:
            continue
        candidates.append(
            FamilyPriceOverviewServiceEntry(
                service_id=service_id,
                service_name=service.name,
                offer_id=offer.offer_id,
                catalog_order=catalog_order,
                role_rank=_role_rank(tuple(service.roles)),
            )
        )

    candidates.sort(key=lambda entry: (entry.role_rank, entry.catalog_order))
    limited = tuple(candidates[:max_services])
    return FamilyPriceOverviewSelection(turn_topic=topic, entries=limited)


def assemble_family_price_overview_materials(
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    selection: FamilyPriceOverviewSelection,
) -> TargetOfflineResponseMaterials:
    """Build price-only materials for a multi-service family overview."""

    offers: list[TargetOffer] = []
    for entry in selection.entries:
        offer = _representative_offer(bundle, doctor_catalog, entry.service_id)
        if offer is None or offer.offer_id != entry.offer_id:
            raise TargetFamilyPriceOverviewError(
                "family_overview_offer_mismatch",
                (entry.service_id, entry.offer_id),
            )
        offers.append(offer.model_copy(deep=True))

    return TargetOfflineResponseMaterials(
        service_id=None,
        service=None,
        selected_brand_id=None,
        brand=None,
        matched_rule_id=None,
        max_options=len(offers),
        offers=tuple(offers),
        doctors=(),
        selected_content_ref=None,
        marketing_selection=TargetMarketingSelection(
            applied_scenarios=(),
            selected_refs=(),
            amplifier_refs=(),
            cta_key="",
        ),
        commercial_facts=(),
        external_source_refs=(),
        consultation_close=None,
        marketing_slots_used=0,
        amplifier_slots_used=0,
        family_service_ids=selection.service_ids,
    )


def assemble_family_price_overview_package(
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    external_index: ResponseSchemaExternalIndex,
    consultation_values: Sequence[ServiceConsultationValue],
    *,
    selection: FamilyPriceOverviewSelection,
    md_root: Path,
) -> TargetOfflineResponsePackage:
    """Assemble S27-S30 package for family price overview (price-only, no follow-ups)."""

    _ = external_index, consultation_values
    materials = assemble_family_price_overview_materials(
        bundle,
        doctor_catalog,
        selection,
    )
    plan = build_target_response_materialization_plan(
        materials,
        required_components=("price",),
    )
    followup_candidates = materialize_target_response_followups(
        plan,
        materials,
        md_root=md_root,
    )
    selected_followups = select_target_response_followups(
        followup_candidates,
        source=None,
    )
    return TargetOfflineResponsePackage(
        materials=materials,
        plan=plan,
        followup_candidates=followup_candidates,
        selected_followups=selected_followups,
    )
