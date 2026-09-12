"""Scope-aware price package assembly (AC3)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import NoReturn

from contracts.doctor_schema import TargetDoctorCatalog
from contracts.effective_scope import EffectiveScope
from contracts.response_schema import ResponseSchemaBundle, TargetOffer, TargetStrategyMatch
from contracts.response_schema_refs import ResponseSchemaExternalIndex
from contracts.service_consultation import ServiceConsultationValue
from contracts.target_response_spec import TargetResponseSpec
from contracts.target_response_stage import (
    ResponseStage,
    is_nav_scope_stage,
    is_nav_stage_clarify,
    is_scope_aware_price_stage,
)
from core.target_client_ui_nav import (
    TargetNavigationFollowup,
    materialize_scope_nav_followups,
    materialize_stage_nav_followups,
)
from core.target_marketing_selector import TargetMarketingSelection, select_target_marketing
from core.target_offline_response_assembly import TargetOfflineResponseMaterials
from core.target_offline_response_package import TargetOfflineResponsePackage
from core.target_response_followup_materializer import (
    materialize_target_response_followups,
)
from core.target_response_followup_policy import (
    TargetResponseFollowupSelection,
    select_target_response_followups,
)
from core.target_response_materialization_plan import build_target_response_materialization_plan
from core.target_response_stage import (
    can_collapse_to_concrete_service,
    derive_response_stage,
    discover_stage_clarification_stages,
)
from core.target_family_price_resolution import (
    is_family_only_broad_mode,
    resolve_explicit_service_price_stage,
)
from core.target_scope_aware_selection import run_target_scope_aware_selection
from core.target_strategy_context import selection_patient_context_from_inputs


class TargetScopeAwarePricePackageError(ValueError):
    def __init__(self, code: str, value: object) -> None:
        self.code = code
        self.value = value
        super().__init__(f"{code}: {value!r}")


def _error(code: str, value: object) -> NoReturn:
    raise TargetScopeAwarePricePackageError(code, value)


def is_scope_aware_price_spec(spec: TargetResponseSpec) -> bool:
    return spec.scope_price_topic is not None or is_scope_aware_price_stage(
        spec.response_stage
    )


def _offer_sort_amount(offer: TargetOffer) -> int:
    price = offer.price
    if price.mode == "fixed" and price.amount is not None:
        return int(price.amount)
    if price.mode in {"from", "range"} and price.min_amount is not None:
        return int(price.min_amount)
    return 0


def _offers_from_selection(
    selection,
    *,
    bundle: ResponseSchemaBundle,
) -> tuple[TargetOffer, ...]:
    offers: list[TargetOffer] = []
    if selection.kind == "broad_anchors":
        offers_by_id = {offer.offer_id: offer for offer in bundle.offers}
        seen_offer_ids: set[str] = set()
        collected: list[TargetOffer] = []
        for service_offers in selection.offers_by_service_id.values():
            for offer in service_offers:
                if offer.offer_id in seen_offer_ids:
                    continue
                collected.append(offer.model_copy(deep=True))
                seen_offer_ids.add(offer.offer_id)
        for anchor in selection.anchors:
            if anchor.offer_id in seen_offer_ids:
                continue
            service_offers = selection.offers_by_service_id.get(anchor.service_id, ())
            if service_offers:
                match = next(
                    (offer for offer in service_offers if offer.offer_id == anchor.offer_id),
                    service_offers[0],
                )
                collected.append(match.model_copy(deep=True))
                seen_offer_ids.add(anchor.offer_id)
                continue
            matched = offers_by_id.get(anchor.offer_id)
            if matched is not None:
                collected.append(matched.model_copy(deep=True))
                seen_offer_ids.add(anchor.offer_id)
        if collected:
            return tuple(sorted(collected, key=_offer_sort_amount))
        return ()
    for service_id in selection.service_ids:
        offers.extend(selection.offers_by_service_id.get(service_id, ()))
    return tuple(offer.model_copy(deep=True) for offer in offers)


def _family_service_ids(selection) -> tuple[str, ...]:
    if selection.kind == "broad_anchors":
        if selection.service_ids:
            return selection.service_ids
        return tuple(anchor.service_id for anchor in selection.anchors)
    return selection.service_ids


def _build_materials(
    *,
    bundle: ResponseSchemaBundle,
    selection,
    strategy_context: TargetStrategyMatch,
    marketing_selection: TargetMarketingSelection,
    include_payment_stages: bool,
) -> TargetOfflineResponseMaterials:
    offers = _offers_from_selection(selection, bundle=bundle)
    if not offers:
        _error("scope_price_no_offers", selection.exclusions)
    service_ids = _family_service_ids(selection)
    if selection.kind == "broad_anchors":
        primary_service_id = None
        primary_service = None
    else:
        primary_service_id = service_ids[0] if len(service_ids) == 1 else None
        primary_service = (
            bundle.services[primary_service_id].model_copy(deep=True)
            if primary_service_id is not None
            else None
        )
    if not include_payment_stages:
        offers = tuple(
            offer.model_copy(
                update={"payment_stages": None},
                deep=True,
            )
            for offer in offers
        )
    return TargetOfflineResponseMaterials(
        service_id=primary_service_id,
        service=primary_service,
        selected_brand_id=None,
        brand=None,
        matched_rule_id=selection.matched_rule_id,
        max_options=len(offers),
        offers=offers,
        doctors=(),
        selected_content_ref=None,
        marketing_selection=marketing_selection,
        commercial_facts=(),
        external_source_refs=(),
        consultation_close=None,
        marketing_slots_used=len(marketing_selection.selected_refs),
        amplifier_slots_used=len(marketing_selection.amplifier_refs),
        family_service_ids=service_ids,
    )


def assemble_scope_aware_price_package(
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    external_index: ResponseSchemaExternalIndex,
    consultation_values: Sequence[ServiceConsultationValue],
    *,
    spec: TargetResponseSpec,
    effective_scope: EffectiveScope,
    strategy_context: TargetStrategyMatch,
    client_id: str,
    md_root: Path,
    semantic_context: str,
    today: date,
    include_initial_block: bool,
    include_cta: bool,
    marketing_scenarios: Sequence[str] = (),
    shown_fact_ids: Sequence[str] = (),
    shown_amplifier_refs: Sequence[str] = (),
    shown_consultation_value_refs: Sequence[str] = (),
    turn_topic: str | None = None,
) -> TargetOfflineResponsePackage:
    topic = spec.scope_price_topic
    if topic is None:
        _error("scope_price_topic_missing", spec.response_stage)
    patient = selection_patient_context_from_inputs(
        effective_scope,
        stage=effective_scope.stage,
    )
    selection = run_target_scope_aware_selection(
        bundle,
        doctor_catalog,
        effective_scope=effective_scope,
        topic=topic,
        explicit_service_id=spec.service_id,
    )
    stage = spec.response_stage or derive_response_stage(
        explicit_service_id=spec.service_id,
        effective_scope=effective_scope,
        topic=topic,
        bundle=bundle,
        selection=selection,
    )
    if spec.service_id is not None and stage == "concrete_service_price":
        protocol_stage = resolve_explicit_service_price_stage(
            bundle,
            explicit_service_id=spec.service_id,
            topic=topic,
            selection=selection,
        )
        if protocol_stage is not None:
            stage = protocol_stage  # type: ignore[assignment]
    family_only_broad = is_family_only_broad_mode(selection)
    navigation: tuple[TargetNavigationFollowup, ...] = ()
    followup_source = spec.followup_source
    marketing_selection = TargetMarketingSelection(
        applied_scenarios=(),
        selected_refs=(),
        amplifier_refs=(),
        cta_key="",
    )
    include_payment_stages = stage in {"scoped_family_price", "concrete_service_price"}

    if stage == "stage_clarify":
        stages = discover_stage_clarification_stages(
            bundle,
            topic=topic,
            patient=patient,
        )
        if not stages:
            _error("scope_price_stage_clarify_empty", topic)
        navigation = materialize_stage_nav_followups(
            client_id,
            topic=topic,
            stages=stages,
        )
        if not navigation:
            _error("scope_price_stage_nav_missing", stages)
        materials = TargetOfflineResponseMaterials(
            service_id=None,
            service=None,
            selected_brand_id=None,
            brand=None,
            matched_rule_id=None,
            max_options=0,
            offers=(),
            doctors=(),
            selected_content_ref=None,
            marketing_selection=marketing_selection,
            commercial_facts=(),
            external_source_refs=(),
            consultation_close=None,
            marketing_slots_used=0,
            amplifier_slots_used=0,
            family_service_ids=(),
        )
        followup_source = None
    elif stage == "data_gap":
        materials = TargetOfflineResponseMaterials(
            service_id=None,
            service=None,
            selected_brand_id=None,
            brand=None,
            matched_rule_id=None,
            max_options=0,
            offers=(),
            doctors=(),
            selected_content_ref=None,
            marketing_selection=marketing_selection,
            commercial_facts=(),
            external_source_refs=(),
            consultation_close=None,
            marketing_slots_used=0,
            amplifier_slots_used=0,
            family_service_ids=(),
        )
        navigation = ()
        followup_source = None
    elif is_nav_scope_stage(stage):
        if include_initial_block and spec.allow_marketing_facts:
            marketing_selection = select_target_marketing(
                bundle,
                doctor_catalog,
                external_index,
                semantic_context=topic,
                service_id=None,
                today=today,
                include_initial_block=True,
                marketing_scenarios=marketing_scenarios,
                shown_fact_ids=shown_fact_ids,
                shown_amplifier_refs=shown_amplifier_refs,
                turn_topic=turn_topic or topic,
            )
            if len(marketing_selection.selected_refs) > 1:
                marketing_selection = TargetMarketingSelection(
                    applied_scenarios=marketing_selection.applied_scenarios,
                    selected_refs=marketing_selection.selected_refs[:1],
                    amplifier_refs=marketing_selection.amplifier_refs,
                    cta_key=marketing_selection.cta_key,
                )
        materials = _build_materials(
            bundle=bundle,
            selection=selection,
            strategy_context=strategy_context,
            marketing_selection=marketing_selection,
            include_payment_stages=False,
        )
        navigation = (
            ()
            if family_only_broad
            else materialize_scope_nav_followups(
                client_id,
                topic=topic,
                confirmed_extents=selection.price_navigable_extents,
            )
        )
        followup_source = None
    elif stage == "concrete_service_price" and can_collapse_to_concrete_service(selection):
        service_id = selection.service_ids[0]
        materials = _build_materials(
            bundle=bundle,
            selection=selection,
            strategy_context=strategy_context,
            marketing_selection=marketing_selection,
            include_payment_stages=True,
        )
        followup_source = "price"
    else:
        materials = _build_materials(
            bundle=bundle,
            selection=selection,
            strategy_context=strategy_context,
            marketing_selection=marketing_selection,
            include_payment_stages=include_payment_stages,
        )
        followup_source = "price" if stage == "scoped_family_price" else None

    plan = build_target_response_materialization_plan(
        materials,
        required_components=spec.required_components,
    )
    followup_candidates = materialize_target_response_followups(
        plan,
        materials,
        md_root=md_root,
    )
    selected_followups = select_target_response_followups(
        followup_candidates,
        source=followup_source,
    )
    if is_nav_stage_clarify(stage):
        selected_followups = TargetResponseFollowupSelection(
            source=None,
            content=(),
            price=(),
        )
    return TargetOfflineResponsePackage(
        materials=materials,
        plan=plan,
        followup_candidates=followup_candidates,
        selected_followups=selected_followups,
        navigation_followups=navigation,
        response_stage=stage,
    )
