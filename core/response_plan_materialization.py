"""Post-Composer selection materialization into PreComposerPlan (RESPONSE-MATERIALIZATION-1)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import date

from contracts.doctor_schema import TargetDoctorCatalog
from contracts.response_plan import (
    CanonicalMultiPriceCandidate,
    CanonicalSinglePriceCandidate,
    CommercialFactCandidate,
    ComposerResult,
    ComposerSelectedRouteAuthority,
    FactRole,
    FrozenPriceOfferRow,
    PreComposerPlan,
    PricePlan,
    RequiredOfferConditionBlock,
    RequiredOfferConditionOfferEntry,
    ResponseCaps,
    ServiceOptionEntry,
    ServiceOptionsBlock,
    ServiceValueCandidate,
    TextualCtaCandidate,
    UiButtonCandidate,
    UiPlanCandidates,
    UiWidgetCandidate,
    all_allowed_route_mode_pairs,
)
from contracts.response_plan_composer import AdaptedComposerDecision
from contracts.response_plan_materialization import (
    ConsideredOfferTrace,
    FinalizedOfferTrace,
    MaterializationContractError,
    MaterializationDiagnostic,
    MaterializationOwnershipError,
    MaterializationTrace,
    MaterializedPreComposerPayload,
    MaterializedResponseOutcome,
    OfferConditionEvidence,
    PriceLookupMode,
    ResponsePlanMaterializationSources,
    SelectedOfferTrace,
)
from contracts.response_plan_post_composer import PostComposerSelectionPlan
from contracts.response_schema import ResponseSchemaBundle, TargetCommercialFact, TargetFixedPrice, TargetOffer, TargetService
from contracts.response_schema_refs import ResponseSchemaExternalIndex
from core.response_plan_fact_projection import (
    fact_active_as_of,
    fact_explicit_only,
    project_commercial_fact_candidate,
)
from core.response_plan_production_adapter import (
    billing_unit_phrase,
    format_frozen_price_row_display,
    format_multi_price_display_from_rows,
)
from core.response_plan_resolver import resolve_response_plan
from core.response_text_renderer import render_response_text
from core.response_strategy import resolve_target_strategy
from core.response_ui_projection import project_response_ui
from core.service_data_context import ServiceDataContext, build_service_data_context
from core.service_value_selection import resolve_service_value_ref
from core.target_marketing_selector import (
    TargetMarketingSelectionError,
    select_target_marketing,
)
from core.target_offer_extent_applicability import filter_offers_for_extent
from core.target_strategy_context import (
    strategy_match_for_explicit_service_price_lookup,
    strategy_match_from_effective_scope,
)

_COMPOSER_TERMINAL_PAIRS: frozenset[tuple[str, str]] = frozenset(
    {
        ("ANSWER", "contacts"),
        ("ADMIN", "standard"),
        ("ADMIN", "medical_terminal"),
    }
)
_CONDITION_ID_ORDER: tuple[str, ...] = (
    "per_jaw",
    "per_tooth",
    "package_includes",
    "mandatory_exclusion",
    "ct_separate",
    "bone_grafting_separate",
)
_EMPTY_EXTERNAL_INDEX = ResponseSchemaExternalIndex(kb_refs=(), doctor_refs=())


def materialize_pre_composer_payload(
    selection: PostComposerSelectionPlan,
    adapted: AdaptedComposerDecision,
    sources: ResponsePlanMaterializationSources,
    *,
    as_of: date,
) -> MaterializedPreComposerPayload:
    """Materialize typed PreComposerPlan + ComposerResult from post-Composer selection."""

    _validate_ownership(selection, sources)
    _validate_adapted_matches_selection(selection, adapted)
    _validate_condition_evidence_bundle(
        sources.material_authority.bundle,
        sources.material_authority.source_client_id,
        sources.condition_evidence_by_offer,
    )

    decision = selection.decision
    route = decision.route
    mode = decision.mode

    if route in {"ADMIN", "CLARIFY"} or (route == "ANSWER" and mode == "contacts"):
        return _materialize_terminal_payload(selection, sources)

    composer_result = _composer_result_from_decision(decision)
    diagnostics: list[MaterializationDiagnostic] = []
    bundle = sources.material_authority.bundle
    client_id = sources.material_authority.source_client_id

    price_lookup_mode = _price_lookup_mode(selection)
    price_plan, price_trace, price_diag = _materialize_price_plan(
        selection,
        bundle,
        client_id,
        price_lookup_mode,
        sources.condition_evidence_by_offer,
    )
    diagnostics.extend(price_diag)

    service_options = _materialize_service_options(selection, bundle, client_id)
    if price_plan.kind != "none" and service_options is not None:
        raise MaterializationContractError("service_options_forbidden_with_price")

    required_conditions = _materialize_required_conditions(
        price_plan,
        price_trace.selected_offers,
        sources.condition_evidence_by_offer,
        bundle,
        client_id,
    )

    promo_ids, amplifier_ids, service_value, marketing_diag = _materialize_optional_marketing(
        selection,
        bundle,
        sources,
        as_of=as_of,
        response_scope=selection.response_scope,
        selected_service_id=_selected_service_id(selection),
        client_id=client_id,
    )
    diagnostics.extend(marketing_diag)
    commercial_facts = _materialize_commercial_facts(
        selection,
        bundle,
        client_id,
        promo_ids,
        amplifier_ids,
        as_of=as_of,
    )

    textual_cta = _materialize_textual_cta(sources)
    ui_candidates = _materialize_ui_candidates(sources)
    terminal_candidates = _materialize_terminal_candidates(sources)

    scope = selection.response_scope
    selected_service_id = _selected_service_id(selection)
    selected_topic_id = selection.resolved_topic_id if scope != "clinic" else None

    plan = PreComposerPlan(
        session_key=selection.session_key,
        context_strategy=sources.context_strategy,
        route_authority=ComposerSelectedRouteAuthority(
            allowed_route_modes=all_allowed_route_mode_pairs(),
            terminal_candidates=terminal_candidates,
        ),
        response_scope=scope,
        selected_service_id=selected_service_id,
        active_session_service_id=None,
        selected_topic_id=selected_topic_id,
        price_plan=price_plan,
        required_offer_conditions=required_conditions,
        commercial_facts=commercial_facts,
        promo_candidate_ids=promo_ids,
        automatic_amplifier_candidate_ids=amplifier_ids,
        service_value_candidate=service_value,
        textual_cta_candidate=textual_cta,
        normal_caps=ResponseCaps(),
        price_caps=ResponseCaps(max_service_value=0, max_promo=2, max_automatic_amplifiers=4),
        ui_candidates=ui_candidates,
        transport_kind=sources.transport_kind,
        service_options_block=service_options,
    )

    trace = MaterializationTrace(
        price_lookup_mode=price_lookup_mode,
        considered_offers=price_trace.considered_offers,
        selected_offers=price_trace.selected_offers,
        finalized_offers=(),
        visible_service_option_ids=selection.visible_service_option_ids,
        price_candidate_service_ids=selection.price_candidate_service_ids,
    )

    return MaterializedPreComposerPayload(
        plan=plan,
        composer_result=composer_result,
        materialization_diagnostics=tuple(diagnostics),
        selection_diagnostics=selection.diagnostics,
        adapter_diagnostics=selection.adapter_diagnostics,
        situation_delta=selection.situation_delta,
        trace=trace,
    )


def resolve_materialized_response(
    selection: PostComposerSelectionPlan,
    adapted: AdaptedComposerDecision,
    sources: ResponsePlanMaterializationSources,
    *,
    as_of: date,
) -> MaterializedResponseOutcome:
    """Run materialization → resolver → renderer → UI projection."""

    payload = materialize_pre_composer_payload(
        selection,
        adapted,
        sources,
        as_of=as_of,
    )
    resolved = resolve_response_plan(payload.plan, payload.composer_result)
    finalized_offers = _build_finalized_offer_trace(resolved)
    trace = replace(payload.trace, finalized_offers=finalized_offers)
    return MaterializedResponseOutcome(
        resolved=resolved,
        rendered_text=render_response_text(resolved),
        ui_projection=project_response_ui(resolved),
        materialization_diagnostics=payload.materialization_diagnostics,
        selection_diagnostics=payload.selection_diagnostics,
        adapter_diagnostics=payload.adapter_diagnostics,
        situation_delta=payload.situation_delta,
        trace=trace,
    )


def _validate_ownership(
    selection: PostComposerSelectionPlan,
    sources: ResponsePlanMaterializationSources,
) -> None:
    if selection.session_key != sources.session_key:
        raise MaterializationOwnershipError("materialization_session_key_mismatch")
    if selection.source_client_id != sources.material_authority.source_client_id:
        raise MaterializationOwnershipError("materialization_client_mismatch")


def _validate_adapted_matches_selection(
    selection: PostComposerSelectionPlan,
    adapted: AdaptedComposerDecision,
) -> None:
    if selection.decision != adapted.decision:
        raise MaterializationContractError("materialization_adapted_decision_mismatch")
    if tuple(selection.adapter_diagnostics) != tuple(adapted.diagnostics):
        raise MaterializationContractError("materialization_adapted_diagnostics_mismatch")


def _validate_condition_evidence_bundle(
    bundle: ResponseSchemaBundle,
    client_id: str,
    condition_evidence: dict[str, OfferConditionEvidence],
) -> None:
    offers_by_id = {offer.offer_id: offer for offer in bundle.offers}
    for key, evidence in condition_evidence.items():
        if key != evidence.offer_id:
            raise MaterializationOwnershipError("materialization_condition_key_mismatch")
        if evidence.source_client_id != client_id:
            raise MaterializationOwnershipError("materialization_condition_client_mismatch")
        offer = offers_by_id.get(evidence.offer_id)
        if offer is None:
            raise MaterializationOwnershipError("materialization_condition_offer_foreign")
        service = bundle.services.get(offer.service_id)
        if service is None or service is not bundle.services.get(offer.service_id):
            raise MaterializationOwnershipError("materialization_condition_service_foreign")


def _selected_service_id(selection: PostComposerSelectionPlan) -> str | None:
    if selection.response_scope == "service":
        return selection.reference_service_id
    return None


def _price_lookup_mode(selection: PostComposerSelectionPlan) -> PriceLookupMode | None:
    if not selection.price_candidate_service_ids:
        return None
    if selection.selection_basis == "referenced_service":
        return "catalog_reference"
    return "situation_selection"


def _price_requested(selection: PostComposerSelectionPlan) -> bool:
    return "price" in selection.decision.requested_aspect_ids


def _materialize_price_plan(
    selection: PostComposerSelectionPlan,
    bundle: ResponseSchemaBundle,
    client_id: str,
    lookup_mode: PriceLookupMode | None,
    condition_evidence: dict[str, OfferConditionEvidence],
) -> tuple[PricePlan, MaterializationTrace, list[MaterializationDiagnostic]]:
    empty_trace = MaterializationTrace(
        lookup_mode,
        (),
        (),
        (),
        selection.visible_service_option_ids,
        selection.price_candidate_service_ids,
    )
    if not _price_requested(selection) or lookup_mode is None:
        return PricePlan(kind="none"), empty_trace, []

    diagnostics: list[MaterializationDiagnostic] = []
    considered: list[ConsideredOfferTrace] = []
    selected_offers: list[TargetOffer] = []
    service_ranked: dict[str, tuple[TargetOffer, ...]] = {}

    for service_id in selection.price_candidate_service_ids:
        if service_id not in bundle.services:
            diagnostics.append(
                MaterializationDiagnostic(
                    code="materialization_foreign_material",
                    detail=service_id,
                )
            )
            continue
        service = bundle.services[service_id]
        if not service.active:
            continue
        context = build_service_data_context(
            bundle, TargetDoctorCatalog(doctors={}), service_id
        )
        ranked, service_considered, service_diag = _materializable_offers_for_service(
            context,
            bundle,
            selection.effective_scope,
            lookup_mode,
            condition_evidence,
            client_id,
        )
        considered.extend(service_considered)
        diagnostics.extend(service_diag)
        if ranked:
            service_ranked[service_id] = ranked

    if not service_ranked:
        if _price_requested(selection):
            diagnostics.append(
                MaterializationDiagnostic(code="materialization_no_price_candidates")
            )
        trace = MaterializationTrace(
            lookup_mode,
            tuple(considered),
            (),
            (),
            selection.visible_service_option_ids,
            selection.price_candidate_service_ids,
        )
        return PricePlan(kind="none"), trace, diagnostics

    candidate_service_ids = [
        service_id
        for service_id in selection.price_candidate_service_ids
        if service_id in service_ranked
    ]
    if len(candidate_service_ids) == 1:
        only_service_id = candidate_service_ids[0]
        selected_offers = list(service_ranked[only_service_id][:3])
    else:
        for service_id in candidate_service_ids:
            ranked = service_ranked[service_id]
            selected_offers.append(ranked[0])
            if len(selected_offers) >= 3:
                selected_offers = selected_offers[:3]
                break

    trace_selected = tuple(
        SelectedOfferTrace(
            offer_id=offer.offer_id,
            service_id=offer.service_id,
            amount=_fixed_price(offer).amount if _is_fixed(offer) else None,
            currency=_fixed_price(offer).currency if _is_fixed(offer) else None,
            billing_unit=_fixed_price(offer).billing_unit if _is_fixed(offer) else None,
        )
        for offer in selected_offers
    )

    trace = MaterializationTrace(
        lookup_mode,
        tuple(considered),
        trace_selected,
        (),
        selection.visible_service_option_ids,
        selection.price_candidate_service_ids,
    )

    if len(selected_offers) == 1:
        offer = selected_offers[0]
        fixed = _fixed_price(offer)
        billing_unit_phrase(fixed.billing_unit)
        offer_rows = _build_frozen_price_rows(bundle, (offer,), client_id)
        return (
            PricePlan(
                kind="single",
                single=CanonicalSinglePriceCandidate(
                    source_client_id=client_id,
                    offer_id=offer.offer_id,
                    display_text=format_frozen_price_row_display(
                    offer_rows[0],
                    package_label=offer.package.label,
                ),
                    amount=fixed.amount,
                    currency=fixed.currency,
                    billing_unit=fixed.billing_unit,
                ),
                offer_rows=offer_rows,
            ),
            trace,
            diagnostics,
        )

    billing_units = {_fixed_price(offer).billing_unit for offer in selected_offers}
    currencies = {_fixed_price(offer).currency for offer in selected_offers}
    if len(billing_units) != 1 or len(currencies) != 1:
        diagnostics.append(
            MaterializationDiagnostic(
                code="materialization_price_unit_incompatible",
                detail=(billing_units, currencies),
            )
        )
        return PricePlan(kind="none"), trace, diagnostics

    offer_rows = _build_frozen_price_rows(bundle, tuple(selected_offers), client_id)
    return (
        PricePlan(
            kind="multi",
            multi=CanonicalMultiPriceCandidate(
                source_client_id=client_id,
                offer_ids=tuple(offer.offer_id for offer in selected_offers),
                display_text=format_multi_price_display_from_rows(
                    offer_rows,
                    tuple(offer.package.label for offer in selected_offers),
                ),
            ),
            offer_rows=offer_rows,
        ),
        trace,
        diagnostics,
    )


def _offer_option_exclusion(
    offer: TargetOffer,
    service,
) -> str | None:
    if offer.option_id is None:
        return None
    options_by_id = {option.option_id: option for option in service.options}
    option = options_by_id.get(offer.option_id)
    if option is None:
        return "invalid_service_option"
    if option.active is False:
        return "inactive_service_option"
    return None


def _materializable_offers_for_service(
    context: ServiceDataContext,
    bundle: ResponseSchemaBundle,
    effective_scope,
    lookup_mode: PriceLookupMode,
    condition_evidence: dict[str, OfferConditionEvidence],
    client_id: str,
) -> tuple[tuple[TargetOffer, ...], list[ConsideredOfferTrace], list[MaterializationDiagnostic]]:
    diagnostics: list[MaterializationDiagnostic] = []
    considered: list[ConsideredOfferTrace] = []
    eligible: list[TargetOffer] = []

    if lookup_mode == "catalog_reference":
        strategy_match = strategy_match_for_explicit_service_price_lookup(
            effective_scope,
            service_family=context.service.family,
        )
    else:
        strategy_match = strategy_match_from_effective_scope(
            effective_scope,
            service_family=context.service.family,
        )

    active_offers: list[TargetOffer] = []
    for offer in context.offers:
        if not offer.active:
            considered.append(
                ConsideredOfferTrace(offer.offer_id, context.service_id, True, "inactive_offer")
            )
            continue
        option_exclusion = _offer_option_exclusion(offer, context.service)
        if option_exclusion is not None:
            considered.append(
                ConsideredOfferTrace(
                    offer.offer_id,
                    context.service_id,
                    True,
                    option_exclusion,  # type: ignore[arg-type]
                )
            )
            continue
        active_offers.append(offer)

    if lookup_mode == "situation_selection" and strategy_match.extent is not None:
        active_offers = list(
            filter_offers_for_extent(
                tuple(active_offers),
                context.service,
                strategy_match.extent,  # type: ignore[arg-type]
            )
        )

    for offer in active_offers:
        if not _is_fixed(offer):
            considered.append(
                ConsideredOfferTrace(
                    offer.offer_id,
                    context.service_id,
                    True,
                    "unsupported_price_mode",
                )
            )
            diagnostics.append(
                MaterializationDiagnostic(
                    code="materialization_unsupported_price_mode",
                    detail=offer.offer_id,
                )
            )
            continue
        evidence = condition_evidence.get(offer.offer_id)
        if evidence is None or evidence.completeness == "unknown":
            considered.append(
                ConsideredOfferTrace(
                    offer.offer_id,
                    context.service_id,
                    True,
                    "conditions_unknown",
                )
            )
            diagnostics.append(
                MaterializationDiagnostic(
                    code="materialization_price_conditions_unknown",
                    detail=offer.offer_id,
                )
            )
            continue
        if evidence.completeness == "incomplete":
            considered.append(
                ConsideredOfferTrace(
                    offer.offer_id,
                    context.service_id,
                    True,
                    "conditions_incomplete",
                )
            )
            diagnostics.append(
                MaterializationDiagnostic(
                    code="materialization_price_conditions_incomplete",
                    detail=offer.offer_id,
                )
            )
            continue
        considered.append(ConsideredOfferTrace(offer.offer_id, context.service_id, False, None))
        eligible.append(offer)

    if not eligible:
        return (), considered, diagnostics

    resolution = resolve_target_strategy(
        bundle.strategy,
        strategy_match,
        offer_ids=tuple(offer.offer_id for offer in eligible),
    )
    eligible_by_id = {offer.offer_id: offer for offer in eligible}
    ranked = tuple(eligible_by_id[offer_id] for offer_id in resolution.offer_ids if offer_id in eligible_by_id)
    cap = min(resolution.max_options, 3)
    return ranked[:cap], considered, diagnostics


def _titlecase_service_alias(alias: str) -> str:
    parts = alias.split("-")
    if not parts:
        return alias
    first = parts[0]
    titled_first = first[:1].upper() + first[1:] if first else first
    return "-".join([titled_first, *parts[1:]])


def _patient_facing_service_label(service: TargetService) -> str:
    name = str(service.name).strip()
    for alias in service.aliases:
        alias_text = str(alias).strip()
        if not alias_text:
            continue
        if alias_text.casefold() in name.casefold():
            return _titlecase_service_alias(alias_text)
    return name


def _offer_variant_label(bundle: ResponseSchemaBundle, offer: TargetOffer) -> str | None:
    if offer.brand_id:
        brand = bundle.brands.brands.get(offer.brand_id)
        if brand is not None and str(brand.canonical_name).strip():
            return str(brand.canonical_name).strip()
    if offer.option_id:
        service = bundle.services.get(offer.service_id)
        if service is not None:
            for option in service.options:
                if option.option_id == offer.option_id:
                    label = str(option.name).strip()
                    if label:
                        return label
    return None


def _offer_distinguishing_label(bundle: ResponseSchemaBundle, offer: TargetOffer) -> str:
    service = bundle.services.get(offer.service_id)
    if service is None:
        return offer.offer_id
    base = _patient_facing_service_label(service)
    variant = _offer_variant_label(bundle, offer)
    if variant:
        return f"{base} {variant}"
    return base


def _build_frozen_price_rows(
    bundle: ResponseSchemaBundle,
    offers: tuple[TargetOffer, ...],
    client_id: str,
) -> tuple[FrozenPriceOfferRow, ...]:
    rows: list[FrozenPriceOfferRow] = []
    for offer in offers:
        fixed = _fixed_price(offer)
        rows.append(
            FrozenPriceOfferRow(
                source_client_id=client_id,
                offer_id=offer.offer_id,
                service_id=offer.service_id,
                offer_label=_offer_distinguishing_label(bundle, offer),
                amount=fixed.amount,
                currency=fixed.currency,
                billing_unit=fixed.billing_unit,
                option_id=offer.option_id,
                brand_id=offer.brand_id,
            )
        )
    return tuple(rows)


def _materialize_required_conditions(
    price_plan: PricePlan,
    selected_traces: tuple[SelectedOfferTrace, ...],
    condition_evidence: dict[str, OfferConditionEvidence],
    bundle: ResponseSchemaBundle,
    client_id: str,
) -> tuple[RequiredOfferConditionBlock, ...]:
    if price_plan.kind == "none":
        return ()
    offers_by_id = {offer.offer_id: offer for offer in bundle.offers}
    label_by_offer = {row.offer_id: row.offer_label for row in price_plan.offer_rows}
    ordered_offer_ids = [trace.offer_id for trace in selected_traces]
    grouped: dict[str, list[RequiredOfferConditionOfferEntry]] = {}
    for offer_id in ordered_offer_ids:
        evidence = condition_evidence.get(offer_id)
        if evidence is None or not evidence.conditions:
            continue
        offer = offers_by_id.get(offer_id)
        if offer is None:
            raise MaterializationOwnershipError("materialization_condition_offer_foreign")
        offer_label = label_by_offer.get(offer_id) or _offer_distinguishing_label(bundle, offer)
        for block in evidence.conditions:
            if block.source_client_id != client_id:
                raise MaterializationOwnershipError("materialization_condition_block_client_mismatch")
            if block.display_text and block.entries:
                raise MaterializationContractError("materialization_condition_ambiguous_form")
            if block.entries:
                for entry in block.entries:
                    if entry.offer_id != offer_id:
                        raise MaterializationOwnershipError("materialization_condition_entry_offer_mismatch")
                    grouped.setdefault(block.condition_id, []).append(
                        RequiredOfferConditionOfferEntry(
                            offer_id=offer_id,
                            display_text=entry.display_text,
                            offer_label=offer_label,
                        )
                    )
            elif block.display_text:
                grouped.setdefault(block.condition_id, []).append(
                    RequiredOfferConditionOfferEntry(
                        offer_id=offer_id,
                        display_text=block.display_text,
                        offer_label=offer_label,
                    )
                )
    blocks: list[RequiredOfferConditionBlock] = []
    for condition_id in _CONDITION_ID_ORDER:
        entries = grouped.get(condition_id)
        if not entries:
            continue
        blocks.append(
            RequiredOfferConditionBlock(
                source_client_id=client_id,
                condition_id=condition_id,  # type: ignore[arg-type]
                completeness="complete",
                entries=tuple(entries),
            )
        )
    return tuple(blocks)


def _materialize_service_options(
    selection: PostComposerSelectionPlan,
    bundle: ResponseSchemaBundle,
    client_id: str,
) -> ServiceOptionsBlock | None:
    if _price_requested(selection):
        return None
    if not selection.visible_service_option_ids:
        return None
    options: list[ServiceOptionEntry] = []
    for service_id in selection.visible_service_option_ids:
        service = bundle.services.get(service_id)
        if service is None or not service.active:
            continue
        options.append(
            ServiceOptionEntry(
                service_id=service_id,
                display_name=service.name,
            )
        )
    if not options:
        return None
    return ServiceOptionsBlock(
        source_client_id=client_id,
        strategy_reference=_strategy_reference(bundle),
        options=tuple(options),
    )


def _strategy_reference(bundle: ResponseSchemaBundle) -> str:
    payload = bundle.strategy.model_dump(mode="json")
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]
    return f"strategy:v{bundle.strategy.version}:{digest}"


def _materialize_commercial_facts(
    selection: PostComposerSelectionPlan,
    bundle: ResponseSchemaBundle,
    client_id: str,
    promo_ids: tuple[str, ...],
    amplifier_ids: tuple[str, ...],
    *,
    as_of: date,
) -> tuple[CommercialFactCandidate, ...]:
    by_id: dict[str, CommercialFactCandidate] = {}
    for fact in selection.requested_fact_candidates:
        if fact.source_client_id != client_id:
            raise MaterializationOwnershipError("materialization_fact_client_mismatch")
        _merge_commercial_fact_candidate(by_id, fact)

    for fact_id in dict.fromkeys((*promo_ids, *amplifier_ids)):
        fact = bundle.facts.get(fact_id)
        if fact is None or not fact_active_as_of(fact, as_of):
            continue
        candidate = project_commercial_fact_candidate(
            bundle,
            fact,
            source_client_id=client_id,
            allowed_roles=_marketing_fact_roles(fact, promo_ids, amplifier_ids),
        )
        _merge_commercial_fact_candidate(by_id, candidate)
    return tuple(by_id.values())


def _marketing_fact_roles(
    fact: TargetCommercialFact,
    promo_ids: tuple[str, ...],
    amplifier_ids: tuple[str, ...],
) -> tuple[FactRole, ...]:
    if fact_explicit_only(fact):
        return ("requested_fact",)
    roles: list[FactRole] = ["requested_fact"]
    if fact.id in promo_ids:
        roles.append("promo")
    if fact.id in amplifier_ids:
        roles.append("automatic_amplifier")
    return tuple(dict.fromkeys(roles))


def _merge_commercial_fact_candidate(
    by_id: dict[str, CommercialFactCandidate],
    candidate: CommercialFactCandidate,
) -> None:
    existing = by_id.get(candidate.fact_id)
    if existing is None:
        by_id[candidate.fact_id] = candidate
        return
    if (
        existing.display_text != candidate.display_text
        or existing.source_client_id != candidate.source_client_id
        or existing.explicit_only != candidate.explicit_only
        or existing.applicability != candidate.applicability
        or existing.allowed_topic_ids != candidate.allowed_topic_ids
        or existing.allowed_service_ids != candidate.allowed_service_ids
        or existing.requires_implant_scope != candidate.requires_implant_scope
        or existing.requested_display_policy != candidate.requested_display_policy
    ):
        raise MaterializationContractError("materialization_fact_conflict")
    merged_roles = tuple(dict.fromkeys((*existing.allowed_roles, *candidate.allowed_roles)))
    by_id[candidate.fact_id] = existing.model_copy(update={"allowed_roles": merged_roles})


def _derive_marketing_semantic_context(selection: PostComposerSelectionPlan) -> str:
    if _price_requested(selection):
        return "price"
    if selection.resolved_topic_id == "doctors":
        return "doctors"
    return "service"


def _materialize_optional_marketing(
    selection: PostComposerSelectionPlan,
    bundle: ResponseSchemaBundle,
    sources: ResponsePlanMaterializationSources,
    *,
    as_of: date,
    response_scope: str,
    selected_service_id: str | None,
    client_id: str,
) -> tuple[tuple[str, ...], tuple[str, ...], ServiceValueCandidate | None, list[MaterializationDiagnostic]]:
    diagnostics: list[MaterializationDiagnostic] = []
    if selection.decision.route != "ANSWER" or selection.decision.mode != "standard":
        return (), (), None, diagnostics

    semantic_context = _derive_marketing_semantic_context(selection)
    service_id = selected_service_id if response_scope == "service" else None
    if response_scope in {"topic", "clinic"}:
        service_id = None

    try:
        marketing = select_target_marketing(
            bundle,
            TargetDoctorCatalog(doctors={}),
            _EMPTY_EXTERNAL_INDEX,
            semantic_context=semantic_context,
            service_id=service_id,
            today=as_of,
            include_initial_block=True,
            shown_fact_ids=sources.shown_promo_fact_ids,
            shown_amplifier_refs=tuple(f"fact:{fact_id}" for fact_id in sources.shown_amplifier_fact_ids),
            turn_topic=selection.resolved_topic_id,
        )
    except TargetMarketingSelectionError as exc:
        diagnostics.append(
            MaterializationDiagnostic(
                code="materialization_optional_unavailable",
                detail=exc.code,
            )
        )
        return (), (), None, diagnostics

    promo_ids: list[str] = []
    for ref in marketing.selected_refs:
        if not ref.startswith("fact:"):
            diagnostics.append(
                MaterializationDiagnostic(
                    code="materialization_optional_unavailable",
                    detail=ref,
                )
            )
            continue
        fact_id = ref.removeprefix("fact:")
        fact = bundle.facts.get(fact_id)
        if fact is None or not fact_active_as_of(fact, as_of):
            diagnostics.append(
                MaterializationDiagnostic(
                    code="materialization_optional_unavailable",
                    detail=fact_id,
                )
            )
            continue
        if fact_explicit_only(fact):
            continue
        promo_ids.append(fact_id)

    amplifier_ids: list[str] = []
    for ref in marketing.amplifier_refs:
        if not ref.startswith("fact:"):
            diagnostics.append(
                MaterializationDiagnostic(
                    code="materialization_optional_unavailable",
                    detail=ref,
                )
            )
            continue
        fact_id = ref.removeprefix("fact:")
        fact = bundle.facts.get(fact_id)
        if fact is None or not fact_active_as_of(fact, as_of):
            diagnostics.append(
                MaterializationDiagnostic(
                    code="materialization_optional_unavailable",
                    detail=fact_id,
                )
            )
            continue
        if fact_explicit_only(fact):
            continue
        amplifier_ids.append(fact_id)

    service_value: ServiceValueCandidate | None = None
    if response_scope == "service" and selected_service_id is not None:
        sv_ref = resolve_service_value_ref(
            bundle,
            service_id=selected_service_id,
            shown_service_value_ids=frozenset(sources.shown_service_value_ids),
        )
        if sv_ref is not None:
            fact_id = sv_ref.removeprefix("fact:")
            fact = bundle.facts.get(fact_id)
            if fact is None or not fact_active_as_of(fact, as_of):
                diagnostics.append(
                    MaterializationDiagnostic(
                        code="materialization_optional_unavailable",
                        detail=fact_id,
                    )
                )
            else:
                service_value = ServiceValueCandidate(
                    fact_id=fact_id,
                    display_text=fact.text_fact,
                    source_client_id=client_id,
                )

    return tuple(dict.fromkeys(promo_ids)), tuple(dict.fromkeys(amplifier_ids)), service_value, diagnostics


def _materialize_textual_cta(
    sources: ResponsePlanMaterializationSources,
) -> TextualCtaCandidate | None:
    authority = sources.textual_cta_authority
    if authority is None:
        return None
    return TextualCtaCandidate(
        source_client_id=authority.source_client_id,
        text=authority.text,
    )


def _materialize_ui_candidates(sources: ResponsePlanMaterializationSources) -> UiPlanCandidates:
    authority = sources.ui_authority
    if authority is None:
        return UiPlanCandidates()
    buttons = tuple(
        UiButtonCandidate(
            source_client_id=authority.source_client_id,
            button_id=item.button_id,
            label=item.label,
            action_kind=item.action_kind,
        )
        for item in authority.buttons
    )
    widget = None
    if authority.widget is not None:
        widget = UiWidgetCandidate(
            source_client_id=authority.source_client_id,
            widget_offer_id=authority.widget.widget_offer_id,
        )
    return UiPlanCandidates(buttons=buttons, widget=widget)


def _materialize_terminal_candidates(
    sources: ResponsePlanMaterializationSources,
) -> tuple:
    from contracts.response_plan import CodeOwnedTerminalCandidate

    client_id = sources.material_authority.source_client_id
    candidates: list[CodeOwnedTerminalCandidate] = []
    seen: set[tuple[str, str]] = set()
    for authority in sources.terminal_authorities:
        pair = (authority.route, authority.mode)
        if pair not in _COMPOSER_TERMINAL_PAIRS:
            raise MaterializationContractError("materialization_terminal_invalid")
        if pair in seen:
            raise MaterializationContractError("materialization_terminal_duplicate")
        if authority.source_client_id != client_id:
            raise MaterializationOwnershipError("materialization_terminal_client_mismatch")
        candidates.append(
            CodeOwnedTerminalCandidate(
                source_client_id=authority.source_client_id,
                route=authority.route,
                mode=authority.mode,
                authority=authority.authority,
                display_text=authority.display_text,
                canonical_contact=authority.canonical_contact,
            )
        )
        seen.add(pair)
    for required_pair in _COMPOSER_TERMINAL_PAIRS:
        if required_pair not in seen:
            raise MaterializationContractError("materialization_terminal_missing")
    return tuple(candidates)


def _materialize_terminal_payload(
    selection: PostComposerSelectionPlan,
    sources: ResponsePlanMaterializationSources,
) -> MaterializedPreComposerPayload:
    composer_result = _composer_result_from_decision(selection.decision)
    terminal_candidates = _materialize_terminal_candidates(sources)
    plan = PreComposerPlan(
        session_key=selection.session_key,
        context_strategy=sources.context_strategy,
        route_authority=ComposerSelectedRouteAuthority(
            allowed_route_modes=all_allowed_route_mode_pairs(),
            terminal_candidates=terminal_candidates,
        ),
        response_scope=selection.response_scope,
        selected_service_id=_selected_service_id(selection),
        active_session_service_id=None,
        selected_topic_id=selection.resolved_topic_id if selection.response_scope != "clinic" else None,
        price_plan=PricePlan(kind="none"),
        commercial_facts=(),
        ui_candidates=UiPlanCandidates(),
        transport_kind=sources.transport_kind,
    )
    return MaterializedPreComposerPayload(
        plan=plan,
        composer_result=composer_result,
        materialization_diagnostics=(),
        selection_diagnostics=selection.diagnostics,
        adapter_diagnostics=selection.adapter_diagnostics,
        situation_delta=selection.situation_delta,
        trace=MaterializationTrace(None, (), (), ()),
    )


def _composer_result_from_decision(decision) -> ComposerResult:
    return ComposerResult(
        route=decision.route,
        mode=decision.mode,
        patient_text=decision.patient_text,
        requested_fact_ids=decision.requested_fact_ids,
    )


def _build_finalized_offer_trace(resolved) -> tuple[FinalizedOfferTrace, ...]:
    if resolved.price_block is None:
        return ()
    rows = resolved.price_block.offer_rows
    if not rows:
        return ()
    return tuple(
        FinalizedOfferTrace(
            offer_id=row.offer_id,
            service_id=row.service_id,
            source_client_id=row.source_client_id,
            amount=row.amount,
            currency=row.currency,
            billing_unit=row.billing_unit,
            offer_label=row.offer_label,
        )
        for row in rows
    )


def _is_fixed(offer: TargetOffer) -> bool:
    return isinstance(offer.price, TargetFixedPrice)


def _fixed_price(offer: TargetOffer) -> TargetFixedPrice:
    assert isinstance(offer.price, TargetFixedPrice)
    return offer.price
