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
    D2PartDeferredBlock,
    D2PartFailureBlock,
    D2FrozenPriceBlock,
    D2FrozenPriceRow,
    D2PriceScopeDecision,
    D2PriceScopeChoice,
    D2ResolvedRequestPart,
    D2TreatmentSituationDecision,
    FactRole,
    FrozenPriceOfferRow,
    InformationSourceBlock,
    PreComposerPlan,
    PricePlan,
    RouteModePair,
    RequiredOfferConditionBlock,
    RequiredOfferConditionOfferEntry,
    ResponseCaps,
    ServiceOptionEntry,
    ServiceOptionsBlock,
    AuthoredServiceAlternativeBlock,
    ServiceValueCandidate,
    TextualCtaCandidate,
    UiButtonCandidate,
    UiPlanCandidates,
    UiQuickReplyCandidate,
    UiVideoCandidate,
    UiWidgetCandidate,
    all_allowed_route_mode_pairs,
)
from contracts.one_call_envelope import OneCallEnvelope
from contracts.d2_session_context import D2PlanFocusSeed
from contracts.request_understanding import RequestUnderstanding, RequestUnderstandingRequest
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
    D2PartFailureAuthority,
    D2PublishedOfferTerms,
    OfferConditionEvidence,
    PriceLookupMode,
    ResponsePlanMaterializationSources,
    SelectedOfferTrace,
)
from core.target_offer_extent_applicability import offer_applies_to_extent
from contracts.response_plan_post_composer import PostComposerSelectionPlan, ResponseSituationDelta
from contracts.response_schema import (
    ResponseSchemaBundle,
    TargetCommercialFact,
    TargetFixedPrice,
    TargetFromPrice,
    TargetNoPublicPrice,
    TargetOffer,
    TargetRangePrice,
    TargetService,
    TargetStrategyMatch,
)
from contracts.response_schema_refs import ResponseSchemaExternalIndex
from core.response_plan_authored_alternative_policy import unambiguous_topic_for_service_ids
from core.d2_content_realization import (
    D2ContentRealization,
    realize_d2_content,
    realize_d2_unattributed_content,
)
from core.d2_commercial_plan import resolve_d2_commercial_plan
from core.response_plan_condition_evidence import materialization_price_scope_label
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
from core.target_offer_projection import project_target_service_offers
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

    authored_block = _materialize_authored_service_alternative(selection, bundle, client_id)
    service_options = None if authored_block is not None else _materialize_service_options(
        selection, bundle, client_id
    )
    if price_plan.kind != "none" and service_options is not None:
        raise MaterializationContractError("service_options_forbidden_with_price")
    if price_plan.kind != "none" and authored_block is not None:
        raise MaterializationContractError("authored_alternative_forbidden_with_price")

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
        authored_service_alternative_block=authored_block,
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


def resolve_d2_envelope_response(
    envelope: OneCallEnvelope,
    sources: ResponsePlanMaterializationSources,
    *,
    as_of: date,
    d2_plan_focus_seed: D2PlanFocusSeed | None = None,
    common_route_direct_service_only: bool = False,
    common_route_content_lookup: bool = False,
) -> MaterializedResponseOutcome:
    """Resolve the D2 lower plan from an already validated D1R envelope.

    This boundary deliberately accepts the parsed D1R object, never a second model
    payload. It is isolated until S3 wires it to HTTP/SSE.
    """

    if envelope.route != "ANSWER":
        raise MaterializationContractError("d2_envelope_route_unsupported")
    understanding = envelope.request_understanding
    if understanding is None or not understanding.requests:
        raise MaterializationContractError("d2_request_understanding_required")

    price_parts = tuple(item for item in understanding.requests if item.kind == "price")
    content_parts = tuple(item for item in understanding.requests if item.kind == "content")
    direct_promotion = envelope.commercial_intent == "promotion"
    direct_fact = (
        envelope.commercial_intent == "payment"
        and bool(envelope.references.direct_fact_ids)
    )
    # The same multi-document presentation applies to comparisons and to
    # independent questions. Neither borrows one document's secondary UI.
    multiple_content_parts = len(content_parts) > 1
    ready_comparison = (
        len(content_parts) == 1
        and content_parts[0].content_ref is not None
        and content_parts[0].content_ref.startswith("comparison__")
    )
    auto_promo = (
        common_route_content_lookup
        and not direct_promotion
        and not direct_fact
        and not multiple_content_parts
        and not ready_comparison
        and not price_parts
    )
    # A direct commercial fact is an exact addition, not a replacement for
    # ordinary FullContext prose in the same turn. Promotions remain code-only.
    code_owned_null_content = direct_promotion
    unsupported = tuple(
        item.request_id
        for item in understanding.requests
        if item.kind not in {"price", "content"}
    )
    if unsupported:
        raise MaterializationContractError("d2_request_kind_unsupported")
    if not price_parts and not content_parts:
        raise MaterializationContractError("d2_price_or_content_part_required")
    if direct_promotion and envelope.promotion_scope not in {"general", "service", "shown"}:
        raise MaterializationContractError("d2_promotion_scope_invalid")

    client_id = sources.material_authority.source_client_id
    if client_id != sources.session_key.client_id:
        raise MaterializationOwnershipError("materialization_client_mismatch")

    treatment_situation = _d2_treatment_situation(
        understanding, client_id=client_id, sources=sources
    )

    # Resolve content first. Wrong/missing refs soft-fail as part gaps (D2-078);
    # foreign tenant material remains fatal and must not hide behind price recovery.
    # FullContext prose is the ordinary answer path.  A content_ref remains
    # useful provenance for source UI, but it does not decide whether the user
    # asked an informational question or whether the prose may be published.
    allow_missing_content_ref = True
    information_blocks, content_realizations = _d2_information_blocks(
        content_parts=content_parts,
        client_id=client_id,
        sources=sources,
        allow_missing_content_ref=allow_missing_content_ref,
        code_owned_null_content=code_owned_null_content,
    )
    content_part_scopes = tuple(
        _d2_content_scope(
            part,
            client_id=client_id,
            sources=sources,
            allow_missing_content_ref=allow_missing_content_ref,
            allow_missing_content_authority=(
                content_realizations[part.request_id].outcome == "unavailable"
                and content_realizations[part.request_id].reason == "d2_content_source_missing"
            ),
        )
        for part in content_parts
    )

    price_block: D2FrozenPriceBlock | None = None
    failure_blocks: list[D2PartFailureBlock] = []
    deferred_blocks: list[D2PartDeferredBlock] = []
    price_failure_reason: str | None = None
    price_scopes_by_id: dict[str, tuple[tuple[str, ...], str, str | None]] = {}
    if price_parts:
        price_part = price_parts[0]
        for part in price_parts:
            price_scope = _d2_price_scope(part, client_id=client_id, sources=sources)
            _d2_validate_price_scope_ownership(
                price_scope[0], bundle=sources.material_authority.bundle
            )
            price_scopes_by_id[part.request_id] = price_scope
        service_ids, response_scope, selected_topic_id = price_scopes_by_id[price_part.request_id]
        deferred_blocks.extend(
            D2PartDeferredBlock(
                request_id=part.request_id,
                source_client_id=client_id,
            )
            for part in price_parts[1:]
        )
        applied_extent = _d2_applied_extent(price_part, treatment_situation, sources)
        if applied_extent is None:
            applied_extent = _d2_same_topic_applied_extent(
                price_part,
                price_parts=price_parts,
                d2_plan_focus_seed=d2_plan_focus_seed,
                sources=sources,
            )
        if applied_extent is None:
            applied_extent = _d2_cross_topic_applied_extent(
                price_part,
                price_parts=price_parts,
                d2_plan_focus_seed=d2_plan_focus_seed,
                sources=sources,
            )
        try:
            direct_service_order = ()
            if common_route_direct_service_only and price_part.service_id is not None:
                direct_service_order = _d2_direct_service_ordered_offer_ids(
                    service_ids=service_ids,
                    client_id=client_id,
                    sources=sources,
                )
            direction_order = next(
                (
                    item.ordered_offer_ids
                    for item in sources.d2_directions
                    if price_part.service_id is None and item.topic_id == selected_topic_id
                ),
                (),
            )
            price_block, trace = _d2_price_block(
                bundle=sources.material_authority.bundle,
                client_id=client_id,
                service_ids=service_ids,
                published_terms=sources.d2_published_terms_by_offer,
                brand_id=price_part.brand_id,
                applied_extent=applied_extent,
                ordered_offer_ids=direct_service_order or direction_order,
                direct_service_only=False,
                authored_order_only=bool(direct_service_order),
            )
        except MaterializationContractError as error:
            price_failure_reason = str(error)
            if price_failure_reason not in {
                "d2_no_price_candidates",
                "d2_no_scope_price_candidates",
            }:
                raise
            failure_blocks.append(
                _d2_part_failure_block(
                    request_id=price_part.request_id,
                    reason=price_failure_reason,
                    client_id=client_id,
                    sources=sources,
                )
            )
            trace = MaterializationTrace(
                price_lookup_mode="catalog_reference",
                considered_offers=(),
                selected_offers=(),
                price_candidate_service_ids=service_ids,
            )
            scope_decision = None
            volume_choices = ()
        else:
            scope_decision, volume_choices = _d2_price_scope_decision(
                part=price_part,
                client_id=client_id,
                sources=sources,
                service_ids=service_ids,
                applied_extent=applied_extent,
                selected_offer_ids=tuple(row.offer_id for row in price_block.rows),
            )
    else:
        first = content_parts[0]
        first_realization = content_realizations[first.request_id]
        service_ids, response_scope, selected_topic_id = _d2_content_scope(
            first,
            client_id=client_id,
            sources=sources,
            allow_missing_content_ref=allow_missing_content_ref,
            allow_missing_content_authority=(
                first_realization.outcome == "unavailable"
                and first_realization.reason == "d2_content_source_missing"
            ),
        )
        trace = MaterializationTrace(
            price_lookup_mode=None,
            considered_offers=(),
            selected_offers=(),
        )
        scope_decision = None
        volume_choices = ()
    part_identities = []
    def _scope_identity(scope: str, service_id: str | None, topic_id: str | None) -> tuple[str, str | None]:
        if service_id is not None:
            return ("service", service_id)
        if topic_id is not None:
            return ("topic", topic_id)
        return (scope, None)
    if price_parts:
        part_identities.append(_scope_identity(response_scope, price_part.service_id, selected_topic_id))
    part_identities.extend(_scope_identity(scope, part.service_id, topic) for part, (_, scope, topic) in zip(content_parts, content_part_scopes))
    plan_scope = response_scope if len(set(part_identities)) == 1 else "mixed"
    request_parts = []
    content_scopes_by_id = {part.request_id: scope for part, scope in zip(content_parts, content_part_scopes)}
    for part in understanding.requests:
        if part.kind == "price":
            _, part_scope, part_topic_id = price_scopes_by_id[part.request_id]
            request_parts.append(D2ResolvedRequestPart(
                request_id=part.request_id,
                kind="price",
                status=(
                    "unavailable" if price_failure_reason is not None else "answered"
                ) if part.request_id == price_part.request_id else "deferred",
                failure_reason=(
                    price_failure_reason if part.request_id == price_part.request_id else None
                ),
                subject_id=part.subject_id,
                scope=part_scope,
                service_id=part.service_id,
                topic_id=part_topic_id,
            ))
        elif part.kind == "content":
            _, scope, topic = content_scopes_by_id[part.request_id]
            realization = content_realizations[part.request_id]
            if realization.outcome == "unavailable":
                assert realization.reason is not None
                failure_blocks.append(
                    _d2_content_failure_block(
                        request_id=part.request_id,
                        reason=realization.reason,
                        client_id=client_id,
                    )
                )
            request_parts.append(D2ResolvedRequestPart(
                request_id=part.request_id,
                kind="content",
                status=realization.outcome,
                failure_reason=realization.reason,
                subject_id=part.subject_id,
                scope=scope,
                service_id=part.service_id,
                topic_id=topic,
                content_ref=part.content_ref,
                content_section_refs=realization.section_refs,
                content_publication=realization.publication,
                snapshot_fingerprint=(
                    sources.d2_snapshot_fingerprint
                    if realization.outcome != "unavailable" else None
                ),
            ))
    frozen_failure_blocks = tuple(failure_blocks)
    frozen_deferred_blocks = tuple(deferred_blocks)
    source_content_ref = None
    if (
        content_parts
        and content_parts[0].content_ref is not None
        and content_realizations[content_parts[0].request_id].outcome != "unavailable"
    ):
        source_content_ref = content_parts[0].content_ref
    elif direct_fact:
        source_content_ref = _d2_direct_fact_source_ref(
            envelope.references.direct_fact_ids,
            sources,
        )
    source_ui, source_ui_diagnostics = _d2_source_ui(
        content_ref=source_content_ref,
        sources=sources,
    )
    ui_candidates = _d2_select_ui(
        source_ui=source_ui,
        sources=sources,
        suppress_secondary=(
            bool(price_parts)
            or direct_promotion
            or multiple_content_parts
        ),
    )
    if volume_choices:
        ui_candidates = ui_candidates.model_copy(
            update={"quick_replies": (*ui_candidates.quick_replies, *(item.candidate for item in volume_choices))}
        )
    unavailable_count = sum(part.status == "unavailable" for part in request_parts)
    deferred_count = sum(part.status == "deferred" for part in request_parts)
    result_status = (
        "complete" if not unavailable_count and not deferred_count and not any(part.status == "recovered" for part in request_parts)
        else "failed" if unavailable_count == len(request_parts)
        else "degraded"
    )
    if price_parts:
        commercial_service_id = (
            None if price_block is None and price_parts[0].brand_id is not None
            else price_parts[0].service_id
        )
    elif direct_promotion and envelope.promotion_scope == "general":
        commercial_service_id = None
    elif direct_promotion or auto_promo:
        commercial_service_id = content_parts[0].service_id
    else:
        commercial_service_id = None
    offer_ids = tuple(row.offer_id for row in price_block.rows) if price_block is not None else ()
    active_promo_ids = frozenset(
        fact.id
        for fact in sources.material_authority.bundle.facts.values()
        if fact_active_as_of(fact, as_of)
    )
    commercial = resolve_d2_commercial_plan(
        authority=sources.d2_commercial,
        service_id=commercial_service_id,
        include_packages=price_block is not None and not direct_promotion and not direct_fact,
        shown_promo_fact_ids=sources.shown_promo_fact_ids,
        offer_ids=offer_ids,
        promo_form="full" if direct_promotion else "short",
        promotion_scope=envelope.promotion_scope if direct_promotion else "service",
        skip_shown=not direct_promotion,
        max_promo=4 if direct_promotion else 2,
        active_promo_ids=active_promo_ids,
    )
    requested_fact_ids = envelope.references.direct_fact_ids if direct_fact else ()
    commercial_facts = _d2_requested_fact_candidates(
        requested_fact_ids,
        sources=sources,
        client_id=client_id,
        as_of=as_of,
    )
    plan = PreComposerPlan(
        session_key=sources.session_key,
        context_strategy=sources.context_strategy,
        route_authority=ComposerSelectedRouteAuthority(
            allowed_route_modes=(RouteModePair(route="ANSWER", mode="standard"),),
            terminal_candidates=(),
        ),
        response_scope=plan_scope,
        selected_service_id=service_ids[0] if plan_scope == "service" else None,
        active_session_service_id=None,
        selected_topic_id=selected_topic_id if plan_scope != "mixed" else None,
        price_plan=PricePlan(kind="none"),
        d2_price_block=price_block,
        d2_treatment_situation=treatment_situation,
        d2_price_scope_decision=scope_decision,
        d2_request_parts=tuple(request_parts),
        d2_part_failure_blocks=frozen_failure_blocks,
        d2_part_deferred_blocks=frozen_deferred_blocks,
        d2_result_status=result_status,
        textual_cta_candidate=(
            _materialize_textual_cta(sources)
            if (
                price_block is not None
                or any(
                    part.status == "answered" and part.kind == "content"
                    for part in request_parts
                )
            )
            else None
        ),
        ui_candidates=ui_candidates,
        transport_kind=sources.transport_kind,
        d2_commercial_owned=True,
        d2_commercial_promo_blocks=commercial.promo_blocks,
        d2_price_booster_block=commercial.price_booster_block,
        d2_also_list_block=commercial.also_list_block,
        d2_compatibility_blocks=commercial.compatibility_blocks,
        commercial_facts=commercial_facts,
    )
    if direct_promotion and not commercial.promo_blocks:
        raise MaterializationContractError("d2_promotion_no_eligible_facts")
    composer_result = ComposerResult(
        route="ANSWER",
        mode="standard",
        patient_text=None,
        requested_fact_ids=requested_fact_ids,
        information_blocks=information_blocks,
        d2_part_failure_blocks=frozen_failure_blocks,
        d2_part_deferred_blocks=frozen_deferred_blocks,
        visible_price_block=price_block is not None,
        code_owned_answer=(
            (direct_promotion and bool(commercial.promo_blocks))
            or (direct_fact and bool(requested_fact_ids))
        ),
    )
    resolved = resolve_response_plan(plan, composer_result)
    finalized_trace = replace(trace, finalized_offers=_build_finalized_offer_trace(resolved))
    return MaterializedResponseOutcome(
        resolved=resolved,
        rendered_text=render_response_text(resolved),
        ui_projection=project_response_ui(resolved),
        materialization_diagnostics=source_ui_diagnostics,
        selection_diagnostics=(),
        adapter_diagnostics=(),
        situation_delta=ResponseSituationDelta(action="keep"),
        trace=finalized_trace,
    )


def _d2_treatment_situation(
    understanding: RequestUnderstanding,
    *,
    client_id: str,
    sources: ResponsePlanMaterializationSources,
) -> D2TreatmentSituationDecision | None:
    owning_request = next((item for item in understanding.requests if item.situation is not None), None)
    if owning_request is None:
        return None
    situation = owning_request.situation
    assert situation is not None

    if owning_request.service_id is not None:
        if owning_request.service_id not in sources.material_authority.bundle.services:
            raise MaterializationOwnershipError("materialization_foreign_material")
    if owning_request.topic_id is not None:
        direction = next(
            (
                item
                for item in sources.d2_directions
                if item.topic_id == owning_request.topic_id and item.source_client_id == client_id
            ),
            None,
        )
        if direction is None:
            raise MaterializationOwnershipError("materialization_foreign_material")
        if owning_request.service_id is not None and owning_request.service_id not in direction.service_ids:
            raise MaterializationContractError("d2_treatment_service_topic_mismatch")

    subject = next(
        (item for item in understanding.subjects if item.subject_id == owning_request.subject_id),
        None,
    )
    return D2TreatmentSituationDecision(
        source_request_id=owning_request.request_id,
        subject_relation=subject.relation if subject is not None else None,
        subject_age_group=subject.age_group if subject is not None else None,
        service_id=owning_request.service_id,
        topic_id=owning_request.topic_id,
        scope_commitment=situation.scope_commitment,
        extent=situation.extent,
        tooth_count=situation.tooth_count,
        jaw=situation.jaw,
        continuity=situation.continuity,
    )


def _d2_applied_extent(
    part: RequestUnderstandingRequest,
    situation: D2TreatmentSituationDecision | None,
    sources: ResponsePlanMaterializationSources,
) -> str | None:
    del sources
    if (
        situation is None
        or situation.source_request_id != part.request_id
        or situation.scope_commitment not in {"reported", "correction", "hypothetical"}
        or situation.extent not in {"one_tooth", "few_teeth", "full_arch"}
    ):
        return None
    return situation.extent


def _d2_same_topic_applied_extent(
    part: RequestUnderstandingRequest,
    *,
    price_parts: tuple[RequestUnderstandingRequest, ...],
    d2_plan_focus_seed: D2PlanFocusSeed | None,
    sources: ResponsePlanMaterializationSources,
) -> str | None:
    """Use only a fresh, typed same-topic situation from the D2 focus seed."""

    if (
        d2_plan_focus_seed is None
        or d2_plan_focus_seed.action != "resolve_topic"
        or d2_plan_focus_seed.source_session_key != sources.session_key
        or d2_plan_focus_seed.topic_id is None
    ):
        return None
    source = d2_plan_focus_seed.carried_situation
    situation = part.situation
    if (
        source is None
        or source.situation_owner_id is None
        or source.session_key != sources.session_key
        or part.service_id is not None
        or part.topic_id is None
        or part.topic_id != d2_plan_focus_seed.topic_id
        or part.topic_id != source.topic_id
        or {item.topic_id for item in price_parts} != {part.topic_id}
        or situation is None
        or situation.continuity != "same"
        or situation.scope_commitment == "reset"
        or source.extent not in {"one_tooth", "few_teeth", "full_arch"}
    ):
        return None
    return source.extent


def _d2_cross_topic_applied_extent(
    part: RequestUnderstandingRequest,
    *,
    price_parts: tuple[RequestUnderstandingRequest, ...],
    d2_plan_focus_seed: D2PlanFocusSeed | None,
    sources: ResponsePlanMaterializationSources,
) -> str | None:
    """Return a C14 candidate's source extent only for its exact destination.

    The seed is an already TTL-gated, typed C12/C14 projection.  This resolver
    does not revisit that projection or infer any semantic relation from text.
    A current request's own typed situation is handled first by
    ``_d2_applied_extent`` and is never replaced here.
    """

    if (
        d2_plan_focus_seed is None
        or d2_plan_focus_seed.action != "resolve_topic"
        or d2_plan_focus_seed.source_session_key != sources.session_key
        or d2_plan_focus_seed.topic_id is None
    ):
        return None
    carry = d2_plan_focus_seed.cross_topic_carry
    if (
        carry is None
        or part.service_id is not None
        or part.topic_id is None
        or part.subject_id is None
        or part.topic_id != d2_plan_focus_seed.topic_id
        or part.topic_id != carry.destination_topic_id
        or {item.topic_id for item in price_parts} != {part.topic_id}
    ):
        return None
    source = carry.source_situation
    situation = part.situation
    if (
        source.situation_owner_id is None
        or carry.situation_owner_id != source.situation_owner_id
        or source.session_key != sources.session_key
        or carry.destination_topic_id == source.topic_id
        or situation is None
        or situation.continuity != "same"
        or situation.scope_commitment == "reset"
        or source.extent not in {"one_tooth", "few_teeth", "full_arch"}
    ):
        return None
    return source.extent


def _d2_price_scope_decision(
    *,
    part: RequestUnderstandingRequest,
    client_id: str,
    sources: ResponsePlanMaterializationSources,
    service_ids: tuple[str, ...],
    applied_extent: str | None,
    selected_offer_ids: tuple[str, ...],
    ) -> tuple[D2PriceScopeDecision | None, tuple[D2PriceScopeChoice, ...]]:
    if part.service_id is not None or part.topic_id is None:
        return None, ()
    presentation = next(
        (item for item in sources.d2_direction_price_presentations if item.topic_id == part.topic_id),
        None,
    )
    if presentation is None or presentation.source_client_id != client_id:
        return None, ()
    brand = sources.material_authority.bundle.brands.brands.get(part.brand_id) if part.brand_id else None
    choices: tuple[D2PriceScopeChoice, ...] = ()
    situation = part.situation
    # Volume buttons come from clinic presentation (D2-028). Offer-set diversity
    # is not required: extents may share a price card and still need a choice.
    can_offer_choices = situation is None
    if applied_extent is None and can_offer_choices and presentation.volume_choices:
        choices = tuple(
            D2PriceScopeChoice(extent=item.extent, candidate=item.candidate)
            for item in presentation.volume_choices
        )
    return (
        D2PriceScopeDecision(
            source_request_id=part.request_id,
            topic_id=part.topic_id,
            applied_extent=applied_extent,
            reason="known_situation" if applied_extent is not None else "overview",
            selected_offer_ids=selected_offer_ids,
            introduction_text=(
                f"Вот опубликованные цены для {brand.canonical_name}."
                if brand is not None else presentation.introduction_text
            ),
            # Clarification copy only with volume buttons (D2-005/074). After
            # «Не знаю» choices are empty: keep orienting prices, do not re-ask.
            unknown_extent_text=presentation.unknown_extent_text if choices else None,
            volume_choices=choices,
        ),
        choices,
    )


def _d2_scope_offer_ids(
    *, service_ids: tuple[str, ...], extent: str, sources: ResponsePlanMaterializationSources
) -> tuple[str, ...]:
    ids: list[str] = []
    bundle = sources.material_authority.bundle
    for service_id in service_ids:
        service = bundle.services.get(service_id)
        if service is None or not service.active:
            continue
        context = build_service_data_context(bundle, TargetDoctorCatalog(doctors={}), service_id)
        options_by_id = {option.option_id: option for option in service.options}
        for offer in context.offers:
            if not offer.active:
                continue
            if offer.option_id is not None and options_by_id[offer.option_id].active is False:
                continue
            if _d2_offer_applies(offer, service, extent):
                ids.append(offer.offer_id)
    return tuple(ids)


def _d2_offer_applies(offer: TargetOffer, service: TargetService, extent: str) -> bool:
    if offer.applies_to_extents is None and not service.selection.extent:
        return False
    return offer_applies_to_extent(offer, service, extent)  # type: ignore[arg-type]


def _d2_typed_content_scope_from_part(
    part: RequestUnderstandingRequest,
    *,
    client_id: str,
    sources: ResponsePlanMaterializationSources,
) -> tuple[tuple[str, ...], str, str | None]:
    """Scope for a recoverable content gap — only typed IDs, never invented cards."""
    if part.service_id is not None:
        if part.service_id not in sources.material_authority.bundle.services:
            raise MaterializationOwnershipError("materialization_foreign_material")
        return (part.service_id,), "service", part.topic_id
    if part.topic_id is not None:
        for direction in sources.d2_directions:
            if direction.topic_id == part.topic_id and direction.source_client_id == client_id:
                return direction.service_ids, "topic", part.topic_id
        return (), "topic", part.topic_id
    return (), "clinic", None


def _d2_content_scope(
    part: RequestUnderstandingRequest,
    *,
    client_id: str,
    sources: ResponsePlanMaterializationSources,
    allow_missing_content_ref: bool = False,
    allow_missing_content_authority: bool = False,
) -> tuple[tuple[str, ...], str, str | None]:
    if part.content_ref is None:
        if not allow_missing_content_ref:
            raise MaterializationContractError("d2_content_ref_required")
        return _d2_typed_content_scope_from_part(
            part, client_id=client_id, sources=sources
        )
    if allow_missing_content_authority:
        # Recoverable content gap: never invent cards; scope only from typed IDs.
        return _d2_typed_content_scope_from_part(
            part, client_id=client_id, sources=sources
        )
    authority = next(
        (item for item in sources.d2_authored_content if item.content_ref == part.content_ref),
        None,
    )
    if authority is None or authority.source_client_id != client_id:
        raise MaterializationOwnershipError("materialization_foreign_material")
    if part.service_id is not None:
        if part.service_id not in sources.material_authority.bundle.services:
            raise MaterializationContractError("d2_content_service_mismatch")
        if part.service_id not in authority.allowed_service_ids:
            raise MaterializationContractError("d2_content_service_mismatch")
        return (part.service_id,), "service", part.topic_id
    if part.topic_id is not None:
        for direction in sources.d2_directions:
            if direction.topic_id == part.topic_id and direction.source_client_id == client_id:
                return direction.service_ids, "topic", part.topic_id
        if not authority.allowed_service_ids:
            return (), "topic", part.topic_id
    if not authority.allowed_service_ids:
        return (), "clinic", None
    raise MaterializationContractError("d2_content_scope_required")


def _d2_price_scope(
    part: RequestUnderstandingRequest,
    *,
    client_id: str,
    sources: ResponsePlanMaterializationSources,
) -> tuple[tuple[str, ...], str, str | None]:
    if part.service_id is not None:
        return (part.service_id,), "service", part.topic_id
    if part.topic_id is None:
        raise MaterializationContractError("d2_price_scope_required")
    if part.brand_id is not None and part.topic_id == "implantation":
        bundle = sources.material_authority.bundle
        service_ids = tuple(dict.fromkeys(
            offer.service_id for offer in bundle.offers
            if offer.active and offer.brand_id == part.brand_id
            and offer.service_id in bundle.services
            and bundle.services[offer.service_id].active
            and bundle.services[offer.service_id].family == "implantology"
        ))
        if service_ids:
            return service_ids, "topic", part.topic_id
    for direction in sources.d2_directions:
        if direction.topic_id == part.topic_id and direction.source_client_id == client_id:
            return direction.service_ids, "topic", direction.topic_id
    raise MaterializationOwnershipError("materialization_foreign_material")


def _d2_validate_price_scope_ownership(
    service_ids: tuple[str, ...],
    *,
    bundle: ResponseSchemaBundle,
) -> None:
    """Validate every deferred price reference without looking up its offers."""
    if not service_ids or any(service_id not in bundle.services for service_id in service_ids):
        raise MaterializationOwnershipError("materialization_foreign_material")


def _d2_direct_service_ordered_offer_ids(
    *,
    service_ids: tuple[str, ...],
    client_id: str,
    sources: ResponsePlanMaterializationSources,
) -> tuple[str, ...]:
    """Return the sole tenant-authored offer order for one exact D2 service."""
    if len(service_ids) != 1:
        raise MaterializationContractError("d2_direct_service_scope_invalid")
    service_id = service_ids[0]
    directions = tuple(
        item
        for item in sources.d2_directions
        if item.source_client_id == client_id and service_id in item.service_ids
    )
    if len(directions) != 1:
        raise MaterializationContractError("d2_no_price_candidates")
    offers_by_id = {
        offer.offer_id: offer for offer in sources.material_authority.bundle.offers
    }
    ordered_offer_ids = tuple(
        offer_id
        for offer_id in directions[0].ordered_offer_ids
        if (offer := offers_by_id.get(offer_id)) is not None and offer.service_id == service_id
    )
    if not ordered_offer_ids:
        raise MaterializationContractError("d2_no_price_candidates")
    return ordered_offer_ids


def _d2_price_block(
    *,
    bundle: ResponseSchemaBundle,
    client_id: str,
    service_ids: tuple[str, ...],
    published_terms: dict[str, D2PublishedOfferTerms],
    brand_id: str | None = None,
    applied_extent: str | None = None,
    ordered_offer_ids: tuple[str, ...] = (),
    direct_service_only: bool = False,
    authored_order_only: bool = False,
) -> tuple[D2FrozenPriceBlock, MaterializationTrace]:
    if brand_id is not None and brand_id not in bundle.brands.brands:
        raise MaterializationContractError("d2_no_price_candidates")
    offers: list[TargetOffer] = []
    if direct_service_only:
        # A direct D2 service-price request has no authored direction ordering.
        # Keep this narrow: it is materializable only when the tenant publishes
        # one active offer for that service, so no legacy strategy selector is
        # needed to choose or rank alternatives.
        if len(service_ids) != 1:
            raise MaterializationContractError("d2_direct_service_scope_invalid")
        service = bundle.services.get(service_ids[0])
        if service is None or not service.active:
            raise MaterializationOwnershipError("materialization_foreign_material")
        options_by_id = {option.option_id: option for option in service.options}
        offers = [
            offer
            for offer in bundle.offers
            if offer.service_id == service_ids[0]
            and (brand_id is None or offer.brand_id == brand_id)
            and offer.active
            and (
                offer.option_id is None
                or (offer.option_id in options_by_id and options_by_id[offer.option_id].active)
            )
            and (applied_extent is None or _d2_offer_applies(offer, service, applied_extent))
        ]
        if not offers:
            # Recoverable empty catalog for this service (C02 / D2-065): keep
            # independent content parts alive instead of hard-failing the turn.
            raise MaterializationContractError("d2_no_price_candidates")
        if len(offers) != 1:
            raise MaterializationContractError("d2_direct_service_offer_selection_unsupported")
    elif ordered_offer_ids and (authored_order_only or brand_id is None):
        # An exact D2 service with several prices may only use the tenant's
        # explicit order.  In particular, no catalog/strategy fallback may
        # introduce a fourth card or a card absent from that order.
        by_id = {offer.offer_id: offer for offer in bundle.offers}
        for offer_id in ordered_offer_ids:
            offer = by_id.get(offer_id)
            if offer is None or offer.service_id not in service_ids or not offer.active:
                raise MaterializationOwnershipError("d2_direction_offer_unavailable")
            service = bundle.services.get(offer.service_id)
            if service is None or not service.active or (offer.option_id is not None and not any(
                option.option_id == offer.option_id and option.active for option in service.options
            )):
                raise MaterializationOwnershipError("d2_direction_service_unavailable")
            if brand_id is not None and offer.brand_id != brand_id:
                continue
            if applied_extent is None or _d2_offer_applies(offer, service, applied_extent):
                offers.append(offer)
        if not offers and applied_extent is not None and not authored_order_only:
            # Generic direction overviews may keep their existing typed-extent
            # behaviour. Exact-service selection above remains order-only.
            for offer in bundle.offers:
                if not offer.active or offer.service_id not in service_ids:
                    continue
                service = bundle.services.get(offer.service_id)
                if service is None or not service.active:
                    continue
                if offer.option_id is not None and not any(
                    option.option_id == offer.option_id and option.active for option in service.options
                ):
                    continue
                if _d2_offer_applies(offer, service, applied_extent):
                    offers.append(offer)
        offers = offers[:3]
    elif brand_id is not None:
        candidates: list[TargetOffer] = []
        for service_id in service_ids:
            service = bundle.services.get(service_id)
            if service is None or not service.active:
                continue
            active_options = {item.option_id for item in service.options if item.active}
            candidates.extend(
                offer for offer in bundle.offers
                if offer.service_id == service_id and offer.brand_id == brand_id and offer.active
                and (offer.option_id is None or offer.option_id in active_options)
                and (applied_extent is None or _d2_offer_applies(offer, service, applied_extent))
            )
        authored_rank = {offer_id: index for index, offer_id in enumerate(ordered_offer_ids)}
        service_rank = {
            offer.service_id: min(
                (authored_rank[item.offer_id] for item in bundle.offers
                 if item.service_id == offer.service_id and item.offer_id in authored_rank),
                default=len(authored_rank),
            )
            for offer in candidates
        }
        candidates.sort(key=lambda offer: service_rank[offer.service_id])
        if applied_extent is None:
            # Unknown volume: one published example per scale is enough.
            seen_scales: set[str] = set()
            for offer in candidates:
                scale = next(iter(offer.applies_to_extents or ()), offer.service_id)
                if scale not in seen_scales:
                    offers.append(offer)
                    seen_scales.add(scale)
            offers = offers[:3]
        else:
            offers = candidates[:3]
    for service_id in (() if ordered_offer_ids or direct_service_only or brand_id is not None else service_ids):
        if service_id not in bundle.services:
            raise MaterializationOwnershipError("materialization_foreign_material")
        context = build_service_data_context(bundle, TargetDoctorCatalog(doctors={}), service_id)
        candidate_context = context
        if applied_extent is not None:
            candidate_context = replace(
                context,
                offers=tuple(
                    offer for offer in context.offers
                    if _d2_offer_applies(offer, context.service, applied_extent)
                ),
            )
        projection = project_target_service_offers(
            candidate_context,
            bundle.strategy,
            TargetStrategyMatch(family=context.service.family),
        )
        for offer in projection.offers:
            offers.append(offer)
            if len(offers) >= 3:
                break
        if len(offers) >= 3:
            break
    if not offers:
        raise MaterializationContractError(
            "d2_no_scope_price_candidates" if applied_extent is not None else "d2_no_price_candidates"
        )
    rows = tuple(
        _d2_frozen_price_row(
            offer,
            client_id=client_id,
            terms=_d2_terms_for_offer(offer, client_id=client_id, published_terms=published_terms),
        )
        for offer in offers
    )
    trace = MaterializationTrace(
        price_lookup_mode="catalog_reference",
        considered_offers=(),
        selected_offers=tuple(
            SelectedOfferTrace(
                offer_id=offer.offer_id,
                service_id=offer.service_id,
                amount=offer.price.amount if isinstance(offer.price, TargetFixedPrice) else None,
                currency=offer.price.currency if isinstance(offer.price, TargetFixedPrice) else None,
                billing_unit=offer.price.billing_unit if isinstance(offer.price, TargetFixedPrice) else None,
            )
            for offer in offers
        ),
        price_candidate_service_ids=service_ids,
    )
    return D2FrozenPriceBlock(source_client_id=client_id, rows=rows), trace


def _d2_part_failure_block(
    *,
    request_id: str,
    reason: str,
    client_id: str,
    sources: ResponsePlanMaterializationSources,
) -> D2PartFailureBlock:
    authority: D2PartFailureAuthority | None = next(
        (item for item in sources.d2_part_failures if item.reason == reason),
        None,
    )
    if authority is None or authority.source_client_id != client_id:
        raise MaterializationContractError("d2_part_failure_authority_missing")
    return D2PartFailureBlock(
        request_id=request_id,
        source_client_id=client_id,
        message_id=authority.message_id,
        reason=authority.reason,
        display_text=authority.display_text,
    )


def _d2_content_failure_block(
    *,
    request_id: str,
    reason: str,
    client_id: str,
) -> D2PartFailureBlock:
    """Freeze the neutral code-owned message for a rejected prose block."""
    if reason not in {
        "d2_model_prose_empty",
        "d2_model_prose_money",
        "d2_model_prose_link",
        "d2_content_source_missing",
    }:
        raise MaterializationContractError("d2_content_failure_reason_invalid")
    return D2PartFailureBlock(
        request_id=request_id,
        source_client_id=client_id,
        message_id="d2-content-unavailable",
        reason=reason,  # type: ignore[arg-type]
        display_text="К сожалению, у меня пока недостаточно информации по этому вопросу",
    )


def _d2_frozen_price_row(
    offer: TargetOffer,
    *,
    client_id: str,
    terms: D2PublishedOfferTerms,
) -> D2FrozenPriceRow:
    price = offer.price
    unit = ""
    if isinstance(price, TargetFixedPrice):
        body = f"{_format_d2_amount(price.amount)} {_d2_currency(price.currency)}"
        unit = billing_unit_phrase(price.billing_unit)
        mode = "fixed"
    elif isinstance(price, TargetFromPrice):
        body = f"от {_format_d2_amount(price.min_amount)} {_d2_currency(price.currency)}"
        unit = billing_unit_phrase(price.billing_unit)
        mode = "from"
    elif isinstance(price, TargetRangePrice):
        body = (
            f"{_format_d2_amount(price.min_amount)}–{_format_d2_amount(price.max_amount)} "
            f"{_d2_currency(price.currency)}"
        )
        unit = billing_unit_phrase(price.billing_unit)
        mode = "range"
    elif isinstance(price, TargetNoPublicPrice):
        return D2FrozenPriceRow(
            source_client_id=client_id,
            offer_id=offer.offer_id,
            service_id=offer.service_id,
            mode="no_public_price",
            display_text=price.approved_text,
            approved_text=price.approved_text,
            condition_texts=tuple(item for item in (terms.package_label, *terms.condition_texts) if item != price.approved_text),
        )
    else:  # pragma: no cover - TargetPrice is a discriminated union.
        raise MaterializationContractError("d2_price_mode_invalid")
    return D2FrozenPriceRow(
        source_client_id=client_id,
        offer_id=offer.offer_id,
        service_id=offer.service_id,
        mode=mode,
        display_text=f"{body} {unit} — {terms.package_label}",
        amount=price.amount if isinstance(price, TargetFixedPrice) else None,
        min_amount=(
            price.min_amount
            if isinstance(price, (TargetFromPrice, TargetRangePrice))
            else None
        ),
        max_amount=price.max_amount if isinstance(price, TargetRangePrice) else None,
        currency=price.currency,
        billing_unit=price.billing_unit,
        condition_texts=terms.condition_texts,
    )


def _d2_terms_for_offer(
    offer: TargetOffer,
    *,
    client_id: str,
    published_terms: dict[str, D2PublishedOfferTerms],
) -> D2PublishedOfferTerms:
    terms = published_terms.get(offer.offer_id)
    if terms is None:
        raise MaterializationContractError("d2_published_terms_required")
    if terms.source_client_id != client_id:
        raise MaterializationOwnershipError("materialization_foreign_material")
    return terms


def _format_d2_amount(amount: int) -> str:
    return f"{amount:,}".replace(",", " ")


def _d2_currency(currency: str) -> str:
    if currency == "RUB":
        return "₽"
    return currency


def _d2_condition_texts(evidence: OfferConditionEvidence) -> tuple[str, ...]:
    texts: list[str] = []
    for block in evidence.conditions:
        if block.entries:
            texts.extend(entry.display_text for entry in block.entries)
        elif block.display_text is not None:
            texts.append(block.display_text)
    return tuple(texts)


def _d2_direct_fact_source_ref(
    fact_ids: tuple[str, ...],
    sources: ResponsePlanMaterializationSources,
) -> str | None:
    available = {item.content_ref for item in sources.d2_source_ui}
    for fact_id in fact_ids:
        fact = sources.material_authority.bundle.facts.get(fact_id)
        detail = getattr(fact, "detail_ref", None) if fact is not None else None
        if not isinstance(detail, str) or not detail.strip():
            continue
        content_ref = detail.split("#", 1)[0].strip()
        if content_ref in available:
            return content_ref
    return None


def _d2_requested_fact_candidates(
    fact_ids: tuple[str, ...],
    *,
    sources: ResponsePlanMaterializationSources,
    client_id: str,
    as_of: date,
) -> tuple:
    if not fact_ids:
        return ()
    bundle = sources.material_authority.bundle
    candidates = []
    for fact_id in fact_ids:
        fact = bundle.facts.get(fact_id)
        if fact is None or not fact_active_as_of(fact, as_of):
            continue
        candidates.append(
            project_commercial_fact_candidate(
                bundle,
                fact,
                source_client_id=client_id,
                allowed_roles=("requested_fact",),
            )
        )
    return tuple(candidates)


def _d2_information_blocks(
    *,
    content_parts: tuple[RequestUnderstandingRequest, ...],
    client_id: str,
    sources: ResponsePlanMaterializationSources,
    allow_missing_content_ref: bool = False,
    code_owned_null_content: bool = False,
) -> tuple[tuple[InformationSourceBlock, ...], dict[str, D2ContentRealization]]:
    by_ref = {item.content_ref: item for item in sources.d2_authored_content}
    blocks: list[InformationSourceBlock] = []
    realizations: dict[str, D2ContentRealization] = {}
    for part in content_parts:
        if part.content_ref is None:
            if code_owned_null_content:
                realizations[part.request_id] = D2ContentRealization(
                    outcome="answered",
                    publication=None,
                    display_text=None,
                    section_refs=(),
                )
            elif not (part.content_text or "").strip():
                # No prose and no optional provenance is still a real gap.
                realizations[part.request_id] = D2ContentRealization(
                    outcome="unavailable",
                    publication=None,
                    display_text=None,
                    section_refs=(),
                    reason="d2_content_source_missing",
                )
            else:
                realization = realize_d2_unattributed_content(part)
                realizations[part.request_id] = realization
                if realization.outcome != "unavailable":
                    assert realization.display_text is not None
                    blocks.append(InformationSourceBlock(
                        request_id=part.request_id,
                        source_client_id=client_id,
                        content_ref=None,
                        display_text=realization.display_text,
                        source_section_refs=(),
                        publication="model_prose",
                        snapshot_fingerprint=sources.d2_snapshot_fingerprint,
                        replacement_reason=None,
                    ))
            continue
        authority = by_ref.get(part.content_ref)
        if authority is None:
            # Wrong model ref for this tenant snapshot — recoverable gap (D2-078).
            realizations[part.request_id] = D2ContentRealization(
                outcome="unavailable",
                publication=None,
                display_text=None,
                section_refs=(),
                reason="d2_content_source_missing",
            )
            continue
        if authority.source_client_id != client_id:
            raise MaterializationOwnershipError("materialization_foreign_material")
        section_by_ref = {section.section_ref: section for section in authority.sections}
        if any(ref not in section_by_ref for ref in part.content_section_refs):
            realizations[part.request_id] = D2ContentRealization(
                outcome="unavailable",
                publication=None,
                display_text=None,
                section_refs=(),
                reason="d2_content_source_missing",
            )
            continue
        if part.service_id is not None and part.service_id not in authority.allowed_service_ids:
            realizations[part.request_id] = D2ContentRealization(
                outcome="unavailable",
                publication=None,
                display_text=None,
                section_refs=(),
                reason="d2_content_source_missing",
            )
            continue
        if part.topic_id is not None and authority.allowed_service_ids:
            content_topics = {
                item.topic_id
                for item in sources.d2_directions
                if item.source_client_id == client_id
                and set(authority.allowed_service_ids).intersection(item.service_ids)
            }
            if content_topics and part.topic_id not in content_topics:
                realizations[part.request_id] = D2ContentRealization(
                    outcome="unavailable",
                    publication=None,
                    display_text=None,
                    section_refs=(),
                    reason="d2_content_source_missing",
                )
                continue
        part_service_ids, _, part_topic_id = _d2_content_scope(
            part,
            client_id=client_id,
            sources=sources,
            allow_missing_content_ref=allow_missing_content_ref,
        )
        if authority.allowed_service_ids and not set(part_service_ids).intersection(authority.allowed_service_ids):
            raise MaterializationOwnershipError("materialization_foreign_material")
        if part.service_id is not None and part.service_id not in part_service_ids:
            realizations[part.request_id] = D2ContentRealization(
                outcome="unavailable",
                publication=None,
                display_text=None,
                section_refs=(),
                reason="d2_content_source_missing",
            )
            continue
        if part.topic_id is not None and part.topic_id != part_topic_id:
            realizations[part.request_id] = D2ContentRealization(
                outcome="unavailable",
                publication=None,
                display_text=None,
                section_refs=(),
                reason="d2_content_source_missing",
            )
            continue
        realization = realize_d2_content(part, authority)
        realizations[part.request_id] = realization
        if realization.outcome == "unavailable":
            continue
        assert realization.display_text is not None
        assert realization.publication is not None
        blocks.append(
            InformationSourceBlock(
                request_id=part.request_id,
                source_client_id=client_id,
                content_ref=authority.content_ref,
                display_text=realization.display_text,
                source_section_refs=realization.section_refs,
                publication=realization.publication,
                snapshot_fingerprint=sources.d2_snapshot_fingerprint,
                replacement_reason=realization.reason,
            )
        )
    return tuple(blocks), realizations


def _d2_source_ui(
    *,
    content_ref: str | None,
    sources: ResponsePlanMaterializationSources,
) -> tuple[UiPlanCandidates, tuple[MaterializationDiagnostic, ...]]:
    if content_ref is None:
        return UiPlanCandidates(), ()
    authority = next(
        (item for item in sources.d2_source_ui if item.content_ref == content_ref),
        None,
    )
    if authority is None:
        return UiPlanCandidates(source_content_ref=content_ref), ()
    shown_refs = set(sources.shown_d2_secondary_ref_ids)
    diagnostics: list[MaterializationDiagnostic] = []
    valid_reply_ids: set[str] = set()
    valid_quick_replies = []
    for item in authority.quick_replies:
        if item.source_client_id != authority.source_client_id:
            diagnostics.append(
                MaterializationDiagnostic(
                    code="materialization_optional_unavailable",
                    detail=("d2_source_ui_quick_reply_client_mismatch", item.reply_id),
                )
            )
            continue
        if item.reply_id in valid_reply_ids:
            diagnostics.append(
                MaterializationDiagnostic(
                    code="materialization_optional_unavailable",
                    detail=("d2_source_ui_quick_reply_duplicate", item.reply_id),
                )
            )
            continue
        valid_reply_ids.add(item.reply_id)
        valid_quick_replies.append(item)

    video = authority.video
    if video is not None and video.source_client_id != authority.source_client_id:
        diagnostics.append(
            MaterializationDiagnostic(
                code="materialization_optional_unavailable",
                detail=("d2_source_ui_video_client_mismatch", video.video_id),
            )
        )
        video = None
    elif video is not None and video.video_id in valid_reply_ids:
        diagnostics.append(
            MaterializationDiagnostic(
                code="materialization_optional_unavailable",
                detail=("d2_source_ui_secondary_ref_duplicate", video.video_id),
            )
        )
        video = None
    elif video is not None and video.video_id in shown_refs:
        video = None

    remaining_secondary_slots = 2 - int(video is not None)
    quick_replies = tuple(
        item
        for item in valid_quick_replies
        if item.reply_id not in shown_refs
    )[:remaining_secondary_slots]
    cta = authority.cta
    if cta is not None and cta.source_client_id != authority.source_client_id:
        diagnostics.append(
            MaterializationDiagnostic(
                code="materialization_optional_unavailable",
                detail=("d2_source_ui_cta_client_mismatch", cta.button_id),
            )
        )
        cta = None
    elif cta is not None and cta.action_kind != "cta":
        diagnostics.append(
            MaterializationDiagnostic(
                code="materialization_optional_unavailable",
                detail=("d2_source_ui_cta_kind_invalid", cta.button_id),
            )
        )
        cta = None
    return (
        UiPlanCandidates(
            quick_replies=quick_replies,
            buttons=(cta,) if cta is not None else (),
            video=video,
            source_content_ref=content_ref,
        ),
        tuple(diagnostics),
    )


def _d2_select_ui(
    *,
    source_ui: UiPlanCandidates,
    sources: ResponsePlanMaterializationSources,
    suppress_secondary: bool,
) -> UiPlanCandidates:
    source_cta = next(
        (item for item in source_ui.buttons if item.action_kind == "cta"),
        None,
    )
    global_ui = _materialize_ui_candidates(sources)
    global_cta = next(
        (item for item in global_ui.buttons if item.action_kind == "cta"),
        None,
    )
    selected_cta = source_cta or global_cta
    return UiPlanCandidates(
        quick_replies=() if suppress_secondary else source_ui.quick_replies,
        buttons=(selected_cta,) if selected_cta is not None else (),
        video=None if suppress_secondary else source_ui.video,
        source_content_ref=source_ui.source_content_ref,
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
                    package_label=materialization_price_scope_label(offer),
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
                    tuple(materialization_price_scope_label(offer) for offer in selected_offers),
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


def _materialize_authored_service_alternative(
    selection: PostComposerSelectionPlan,
    bundle: ResponseSchemaBundle,
    client_id: str,
) -> AuthoredServiceAlternativeBlock | None:
    approved_text = selection.authored_alternative_approved_text
    unavailable_text = selection.authored_alternative_unavailable_text
    if not approved_text and not unavailable_text:
        return None
    if selection.reference_service_id is None:
        raise MaterializationContractError("authored_alternative_requires_reference_service")
    option_ids = selection.visible_service_option_ids
    options: list[ServiceOptionEntry] = []
    for service_id in option_ids:
        service = bundle.services.get(service_id)
        if service is None or not service.active:
            raise MaterializationContractError("authored_alternative_bundle_inconsistent")
        options.append(
            ServiceOptionEntry(
                service_id=service_id,
                display_name=service.name,
            )
        )
    return AuthoredServiceAlternativeBlock(
        source_client_id=client_id,
        requested_service_id=selection.reference_service_id,
        approved_text=(approved_text or unavailable_text or "").strip(),
        options=tuple(options),
        options_unambiguous_topic_id=unambiguous_topic_for_service_ids(bundle, option_ids),
    )


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
