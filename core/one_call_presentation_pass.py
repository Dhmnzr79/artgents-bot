"""Single local post-Flash presentation pass (Stage 5.1)."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from contracts.exact_sales_resolution import ExactSalesResolution
from contracts.one_call_presentation_result import (
    OneCallPresentationResult,
    PresentationCadenceDelta,
    PresentationQuickReply,
    PresentationRenderedIds,
    PresentationSessionDelta,
)
from contracts.precomposer_selected_offer import PrecomposerSelectedOfferResult, ResolvedPriceText
from contracts.response_schema import TargetStrategyMatch
from contracts.service_reference import AvailabilityStatus
from contracts.turn_frame import TurnFrame
from core.one_call_direct_commercial import (
    DirectCommercialMaterialization,
    append_direct_commercial_without_duplicates,
    materialize_direct_commercial,
)
from core.sales_fast_authoritative_commerce import (
    AuthoritativeCommerceResult,
    apply_authoritative_commerce_to_patient_text,
    build_authoritative_commerce_result,
    build_precomposer_multi_offer_commerce,
    build_precomposer_single_offer_commerce,
    collect_planned_render_commercial_allowlist,
    gate_commerce_result_by_intent,
    sanitize_model_text_for_authoritative_marketing,
)
from core.one_call_price_text import assemble_price_turn_visible_text
from contracts.sales_one_plus_semantic import SalesOnePlusSemanticFrame
from core.sales_one_plus_semantic_authority import (
    presentation_active_service_id,
    presentation_commercial_intent,
    presentation_promotion_scope,
)
from core.sales_fast_strict_evidence import effective_scope_from_semantic_frame
from core.service_availability_presentation import (
    AvailabilityOverlay,
    build_alternative_price_lines,
    build_alternative_secondary_slots,
    build_availability_overlay,
    load_authored_alternatives,
    resolve_family_price_context_with_disclaimer,
    resolve_price_coverage_kind,
)
from core.service_value_selection import service_value_text_for_ref
from core.target_marketing_selector import (
    OptionalMarketingApplicationError,
    TargetMarketingSelectionError,
    fact_ids_present_in_text,
    select_stage51_marketing,
)
from core.target_response_evidence import (
    TargetResponseEvidencePackageError,
    merge_marketing_selection_into_materials,
)
from core.target_presentation_decision import (
    TargetPresentationCadenceState,
    TargetPresentationCadenceUpdate,
    TargetPresentationDecision,
    decide_target_presentation,
)
from core.target_presentation_turn_projection import (
    resolve_target_semantic_context,
    should_include_automatic_marketing_block,
)
from core.target_generic_fullcontext_content import (
    is_generic_fullcontext_content_spec,
)
from core.target_response_materialization_plan import (
    TargetResponseMaterializationPlanError,
    build_target_response_materialization_plan,
)
from core.target_response_policy import select_target_response_length_profile
from core.target_scope_aware_price_package import is_scope_aware_price_spec
from core.target_structured_service_availability import is_structured_service_availability_spec
from core.target_response_verifier import TargetVerifiedComposedResponse
from core.target_runtime_client_context import TargetRuntimeClientContext
from core.target_spec_offline_response_package import TargetSpecBoundOfflineResponsePackage
from core.target_verified_primary_content_cta_projection import (
    project_verified_primary_content_cta,
)
from core.target_verified_response_pipeline import _used_content_refs_from_package
from core.target_composer_request import (
    TargetComposerRequestError,
    materialize_target_composer_request,
)
from core.target_scoped_response_evidence import TargetScopedResponseEvidenceError
from core.sales_fast_presentation import (
    AUTOMATIC_AMPLIFIER_LIST_HEADER,
    build_direct_promotion_patient_text,
    supplement_sales_fast_patient_text_with_marketing,
)

_FAIL_CLOSED_TEXT: dict[str, str] = {
    "promotion_shown_without_session_promo": (
        "В этом диалоге ещё не была показана акция, о которой можно ответить повторно. "
        "Могу рассказать, какие акции сейчас действуют в клинике."
    ),
    "promotion_shown_promo_no_longer_eligible": (
        "Ранее показанная акция сейчас недоступна или уже не действует. "
        "Могу перечислить актуальные акции клиники."
    ),
    "promotion_service_without_authoritative_service_id": (
        "Чтобы ответить об акции на конкретную услугу, нужно уточнить услугу."
    ),
    "promotion_no_eligible_facts": (
        "Сейчас в материалах клиники нет подходящей акции для этого запроса. "
        "Могу рассказать об услугах клиники или перечислить общие акции."
    ),
    "promotion_shown_ambiguous": (
        "В прошлом ответе было несколько акций. Уточните, пожалуйста, "
        "о какой именно акции вы спрашиваете."
    ),
}


def _fail_closed_text(reason: str) -> str:
    return _FAIL_CLOSED_TEXT.get(
        reason,
        "Сейчас не могу надёжно ответить по этому вопросу об акции. "
        "Администратор клиники поможет уточнить детали.",
    )


def _price_marketing_suffix_without_service_value(
    *,
    bound_package: TargetSpecBoundOfflineResponsePackage,
    bundle: TargetRuntimeClientContext,
) -> str:
    facts_by_id = {
        fact.id: fact for fact in bound_package.package.materials.commercial_facts
    }
    selection = bound_package.package.materials.marketing_selection
    text = ""
    amplifier_ref_set = frozenset(selection.amplifier_refs)

    for ref in selection.selected_refs:
        if not ref.startswith("fact:") or ref in amplifier_ref_set:
            continue
        fact_id = ref.removeprefix("fact:")
        fact = facts_by_id.get(fact_id)
        if fact is None:
            continue
        fact_text = str(fact.text_fact).strip()
        if not fact_text or fact_text in text:
            continue
        separator = "\n\n" if text.strip() else ""
        text = f"{text.rstrip()}{separator}{fact_text}"

    bullet_lines: list[str] = []
    for ref in selection.amplifier_refs:
        if not ref.startswith("fact:"):
            continue
        fact_id = ref.removeprefix("fact:")
        fact = facts_by_id.get(fact_id)
        if fact is None:
            fact = bundle.bundle.facts.get(fact_id)
        if fact is None:
            continue
        fact_text = str(fact.text_fact).strip()
        if not fact_text or fact_text in text:
            continue
        bullet_lines.append(fact_text)

    if bullet_lines:
        list_block = AUTOMATIC_AMPLIFIER_LIST_HEADER + "\n" + "\n".join(
            f"- {line}" for line in bullet_lines
        )
        separator = "\n\n" if text.strip() else ""
        text = f"{text.rstrip()}{separator}{list_block}"
    return text


def _precomposer_multi_unsafe_block_legacy(
    *,
    precomposer_selected_offer: PrecomposerSelectedOfferResult | None,
    original_commercial_intent: str,
    resolved_price_text: ResolvedPriceText | None,
) -> bool:
    if original_commercial_intent != "price":
        return False
    if precomposer_selected_offer is None:
        return False
    if precomposer_selected_offer.diagnostic is not None:
        return True
    if precomposer_selected_offer.availability == "multiple":
        if resolved_price_text is None or resolved_price_text.owner != "canonical_multi":
            return True
    return False


def _informational_evidence_fact_kinds() -> frozenset[str]:
    return frozenset({"warranty"})


def _planned_render_fact_allowlists(
    bound_package: TargetSpecBoundOfflineResponsePackage,
    patient_text: str,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    facts_by_id = {
        fact.id: fact for fact in bound_package.package.materials.commercial_facts
    }
    commercial_texts: list[str] = []
    planned_informational: list[str] = []
    present_informational: list[str] = []
    informational_kinds = _informational_evidence_fact_kinds()
    selection = bound_package.package.materials.marketing_selection
    ref_groups: tuple[tuple[tuple[str, ...], bool], ...] = (
        (tuple(selection.selected_refs), False),
        (tuple(selection.amplifier_refs), True),
    )
    for refs, amplifiers_only in ref_groups:
        for ref in refs:
            if not ref.startswith("fact:"):
                continue
            fact = facts_by_id.get(ref.removeprefix("fact:"))
            if fact is None:
                continue
            fact_kind = str(fact.kind)
            if amplifiers_only and fact_kind not in informational_kinds:
                continue
            fact_text = str(fact.text_fact).strip()
            if not fact_text:
                continue
            if fact_text in patient_text:
                if fact_kind in informational_kinds:
                    present_informational.append(fact_text)
                continue
            if amplifiers_only:
                continue
            if fact_kind == "promo":
                commercial_texts.append(fact_text)
            elif fact_kind in informational_kinds:
                planned_informational.append(fact_text)
    return (
        tuple(commercial_texts),
        tuple(planned_informational),
        tuple(present_informational),
    )


def _sanitize_patient_text_for_render(
    *,
    patient_text: str,
    bound_package: TargetSpecBoundOfflineResponsePackage,
    commerce_result: AuthoritativeCommerceResult | None,
    commercial_intent: str,
    direct_eligible_texts: tuple[str, ...] = (),
) -> str:
    commercial_texts, _, _ = _planned_render_fact_allowlists(
        bound_package,
        patient_text,
    )
    all_planned = commercial_texts + direct_eligible_texts
    allowed_amounts, allowed_percents = collect_planned_render_commercial_allowlist(
        planned_commercial_fact_texts=all_planned,
        commerce=commerce_result,
        commercial_intent=commercial_intent,
    )
    return sanitize_model_text_for_authoritative_marketing(
        patient_text,
        allowed_amounts=allowed_amounts,
        allowed_percents=allowed_percents,
    )


_OPTIONAL_MARKETING_APPLICATION_ERRORS = (
    OptionalMarketingApplicationError,
    TargetResponseEvidencePackageError,
    TargetResponseMaterializationPlanError,
    TypeError,
    KeyError,
)


def _optional_marketing_failure_is_tolerable(
    commercial_intent: str,
    *,
    required_promotion_satisfied: bool,
) -> bool:
    """Return True when a marketing failure may be skipped without losing the main answer."""

    if commercial_intent != "promotion":
        return True
    return required_promotion_satisfied


def _apply_stage51_marketing(
    bound_package: TargetSpecBoundOfflineResponsePackage,
    *,
    context: TargetRuntimeClientContext,
    semantic: SalesOnePlusSemanticFrame,
    turn_frame: TurnFrame,
    shown_fact_ids: tuple[str, ...],
    shown_amplifier_refs: tuple[str, ...],
    shown_service_value_ids: tuple[str, ...] = (),
    last_rendered_promo_fact_id: str | None,
    last_turn_rendered_promo_fact_ids: tuple[str, ...] = (),
    patient_text: str = "",
    extra_present_fact_ids: tuple[str, ...] = (),
    today: date,
    include_automatic_block: bool = True,
    required_promotion_satisfied: bool = False,
) -> tuple[TargetSpecBoundOfflineResponsePackage, str | None]:
    commercial_intent = presentation_commercial_intent(semantic)
    semantic_context = resolve_target_semantic_context(
        turn_frame,
        bound_package.spec,
    )
    present_fact_ids = tuple(
        dict.fromkeys(
            [
                *fact_ids_present_in_text(patient_text, context.bundle),
                *extra_present_fact_ids,
            ]
        )
    )
    try:
        outcome = select_stage51_marketing(
            context.bundle,
            context.doctor_catalog,
            context.external_index,
            route=semantic.route,
            commercial_intent=presentation_commercial_intent(semantic),
            promotion_scope=presentation_promotion_scope(semantic),
            semantic_context=semantic_context,
            service_id=presentation_active_service_id(semantic),
            today=today,
            marketing_scenarios=tuple(turn_frame.marketing_scenarios),
            shown_fact_ids=shown_fact_ids,
            shown_amplifier_refs=shown_amplifier_refs,
            last_rendered_promo_fact_id=last_rendered_promo_fact_id,
            last_turn_rendered_promo_fact_ids=last_turn_rendered_promo_fact_ids,
            turn_topic=turn_frame.topic,
            shown_service_value_ids=shown_service_value_ids,
            present_fact_ids=present_fact_ids,
            include_automatic_block=include_automatic_block,
        )
    except TargetMarketingSelectionError:
        if not _optional_marketing_failure_is_tolerable(
            commercial_intent,
            required_promotion_satisfied=required_promotion_satisfied,
        ):
            raise
        return bound_package, None
    if outcome.fail_closed_reason is not None:
        return bound_package, outcome.fail_closed_reason
    if outcome.selection is None:
        return bound_package, None
    try:
        merged_materials = merge_marketing_selection_into_materials(
            bound_package.package.materials,
            context.bundle,
            outcome.selection,
        )
        spec = bound_package.spec
        canonical_plan = build_target_response_materialization_plan(
            merged_materials,
            required_components=spec.required_components,
            allow_missing_content=is_structured_service_availability_spec(spec),
            requested_components=spec.required_components,
            response_stage=spec.response_stage,
            is_generic_fullcontext=is_generic_fullcontext_content_spec(spec),
            is_scope_aware_price=is_scope_aware_price_spec(spec),
            is_structured_service_availability=is_structured_service_availability_spec(spec),
        )
        package = replace(
            bound_package.package,
            materials=merged_materials,
            plan=canonical_plan,
        )
        return replace(
            bound_package,
            package=package,
            selected_cta_key=outcome.selection.cta_key if bound_package.spec.allow_cta else None,
        ), None
    except _OPTIONAL_MARKETING_APPLICATION_ERRORS:
        if not _optional_marketing_failure_is_tolerable(
            commercial_intent,
            required_promotion_satisfied=required_promotion_satisfied,
        ):
            raise
        return bound_package, None


def _build_verified(
    *,
    bound_package: TargetSpecBoundOfflineResponsePackage,
    context: TargetRuntimeClientContext,
    turn_frame: TurnFrame,
    patient_text: str,
    user_message: str,
) -> TargetVerifiedComposedResponse:
    package_primary = bound_package.package.plan.primary_content_ref
    try:
        request = materialize_target_composer_request(
            bound_package,
            context.bundle,
            context.doctor_catalog,
            context.consultation_values,
            user_message=user_message,
            md_root=context.md_root,
            client_id=context.client_id,
            response_length_profile=select_target_response_length_profile(
                bound_package.spec,
                aspects=tuple(turn_frame.aspects),
                aspects_valid=turn_frame.field_meta.aspects.status == "valid",
                marketing_scenarios=tuple(turn_frame.marketing_scenarios),
                needs_clarification=turn_frame.needs_clarification,
            ),
        )
        package_used = _used_content_refs_from_package(bound_package, request)
    except (TargetScopedResponseEvidenceError, TargetComposerRequestError) as exc:
        from core import turn_timing

        turn_timing.set_flag("post_composer_evidence_degraded", True)
        turn_timing.set_flag("post_composer_evidence_error_code", exc.code)
        package_used = ()
    verified = TargetVerifiedComposedResponse(
        text=patient_text,
        spec=bound_package.spec,
        selected_followups=bound_package.package.selected_followups,
        selected_cta_key=bound_package.selected_cta_key,
        navigation_followups=bound_package.package.navigation_followups,
        primary_content_ref=package_primary,
        used_content_refs=package_used,
    )
    return project_verified_primary_content_cta(
        verified,
        client_id=context.client_id,
        md_root=context.md_root,
    )


def _rendered_fact_ids_from_text(
    *,
    bound_package: TargetSpecBoundOfflineResponsePackage,
    rendered_text: str,
) -> tuple[str, ...]:
    facts_by_id = {fact.id: fact for fact in bound_package.package.materials.commercial_facts}
    selected_ids = tuple(
        ref.removeprefix("fact:")
        for ref in bound_package.package.materials.marketing_selection.selected_refs
        if ref.startswith("fact:")
    )
    return tuple(
        fact_id
        for fact_id in selected_ids
        if (fact := facts_by_id.get(fact_id)) is not None
        and str(fact.text_fact).strip() in rendered_text
    )


def _promo_fact_ids(
    *,
    bound_package: TargetSpecBoundOfflineResponsePackage,
    rendered_fact_ids: tuple[str, ...],
    bundle: ResponseSchemaBundle,
) -> tuple[str, ...]:
    promo_kinds = frozenset({"promo"})
    promo_ids: list[str] = []
    for fact_id in rendered_fact_ids:
        fact = bundle.facts.get(fact_id)
        if fact is not None and str(fact.kind) in promo_kinds:
            promo_ids.append(fact_id)
    return tuple(dict.fromkeys(promo_ids))


def _presentation_quick_replies(
    decision: TargetPresentationDecision,
) -> tuple[PresentationQuickReply, ...]:
    return tuple(
        PresentationQuickReply(label=str(item["label"]), ref=str(item["ref"]))
        for item in decision.quick_replies
    )


def _secondary_slots(
    decision: TargetPresentationDecision,
) -> tuple[PresentationQuickReply, ...]:
    if decision.channel != "content":
        return ()
    return _presentation_quick_replies(decision)


def _merge_availability_patient_text(
    *,
    availability_status: AvailabilityStatus,
    overlay: AvailabilityOverlay | None,
    patient_text: str = "",
    alternative_price_lines: tuple[str, ...] = (),
    family_price_context: str | None = None,
) -> str:
    if availability_status == "unresolved":
        if overlay is not None and overlay.unresolved_text:
            return overlay.unresolved_text.strip()
        return (
            "Не вижу такой услуги в перечне клиники. "
            "Возможно, она называется иначе — уточните название."
        )

    if availability_status == "known_not_offered":
        parts: list[str] = []
        if overlay is not None:
            if overlay.not_offered_text:
                parts.append(overlay.not_offered_text.strip())
            for alt_text in overlay.alternative_texts:
                token = alt_text.strip()
                if token:
                    parts.append(token)
        for line in alternative_price_lines:
            token = line.strip()
            if token:
                parts.append(token)
        return "\n\n".join(parts)

    parts: list[str] = []
    body = str(patient_text or "").strip()
    if body:
        parts.append(body)
    if family_price_context:
        parts.append(family_price_context.strip())
    return "\n\n".join(parts)


def _availability_blocks_commerce(availability_status: AvailabilityStatus) -> bool:
    return availability_status in {"known_not_offered", "unresolved"}


def build_one_call_presentation_result(
    *,
    bound_package: TargetSpecBoundOfflineResponsePackage,
    context: TargetRuntimeClientContext,
    turn_frame: TurnFrame,
    semantic: SalesOnePlusSemanticFrame,
    patient_text: str,
    user_message: str,
    cadence: TargetPresentationCadenceState,
    allow_situation: bool,
    resolution: ExactSalesResolution,
    strategy_context: TargetStrategyMatch,
    shown_fact_ids: tuple[str, ...],
    shown_amplifier_refs: tuple[str, ...],
    shown_consultation_value_refs: tuple[str, ...] = (),
    shown_service_value_ids: tuple[str, ...] = (),
    last_rendered_promo_fact_id: str | None = None,
    last_turn_rendered_promo_fact_ids: tuple[str, ...] = (),
    today: date,
    precomposer_selected_offer: PrecomposerSelectedOfferResult | None = None,
    resolved_price_text: ResolvedPriceText | None = None,
) -> OneCallPresentationResult:
    """Run exactly one presentation pass for sales-fast widget materialization."""

    commercial_intent = presentation_commercial_intent(semantic)
    promotion_scope = presentation_promotion_scope(semantic)
    original_commercial_intent = semantic.commercial_intent
    price_intent_requested = original_commercial_intent == "price"
    if turn_frame.needs_clarification:
        commercial_intent = "none"

    availability_status = semantic.availability_status
    requested_service_id = semantic.requested_service_id
    authored_alternatives = ()
    alternative_secondary_slots: tuple[PresentationQuickReply, ...] = ()
    alternative_price_lines: tuple[str, ...] = ()
    family_price_context: str | None = None
    price_coverage_kind = "none"
    availability_overlay: AvailabilityOverlay | None = None

    if availability_status == "known_not_offered" and requested_service_id:
        authored_alternatives = load_authored_alternatives(
            context.client_id,
            requested_service_id=requested_service_id,
            bundle=context.bundle,
        )
        availability_overlay = build_availability_overlay(
            client_id=context.client_id,
            availability_status=availability_status,
            requested_service_id=requested_service_id,
            bundle=context.bundle,
        )
        if authored_alternatives:
            alt_ids = authored_alternatives[0].alternative_service_ids
            alternative_secondary_slots = build_alternative_secondary_slots(
                context.bundle,
                alternative_service_ids=alt_ids,
            )
            if price_intent_requested:
                alternative_price_lines = build_alternative_price_lines(
                    context.bundle,
                    alternative_service_ids=alt_ids,
                    doctor_catalog=context.doctor_catalog,
                    strategy_context=strategy_context,
                )
        commercial_intent = "none"
    elif availability_status == "unresolved":
        availability_overlay = build_availability_overlay(
            client_id=context.client_id,
            availability_status=availability_status,
            requested_service_id=requested_service_id,
            bundle=context.bundle,
        )
        commercial_intent = "none"
    else:
        active_service = presentation_active_service_id(semantic)
        if active_service:
            price_coverage_kind = resolve_price_coverage_kind(
                context.bundle,
                service_id=active_service,
                doctor_catalog=context.doctor_catalog,
                strategy_context=strategy_context,
            )
            if price_coverage_kind == "family_context":
                if original_commercial_intent == "price":
                    family_price_context = resolve_family_price_context_with_disclaimer(
                        context.bundle,
                        active_service,
                    )
                    commercial_intent = "none"

    skip_marketing = _availability_blocks_commerce(availability_status)
    direct_materialization: DirectCommercialMaterialization | None = None
    direct_request_present = bool(semantic.direct_fact_ids)
    if direct_request_present and not skip_marketing:
        direct_materialization = materialize_direct_commercial(
            bundle=context.bundle,
            direct_fact_ids=semantic.direct_fact_ids,
            authoritative_service_id=presentation_active_service_id(semantic),
            today=today,
        )
    direct_commercial_text = (
        direct_materialization.rendered_text if direct_materialization is not None else ""
    )
    direct_eligible_texts = (
        direct_materialization.eligible_texts if direct_materialization is not None else ()
    )
    bound_with_marketing = bound_package
    fail_reason = None
    include_automatic_block = (
        not skip_marketing
        and should_include_automatic_marketing_block(
            turn_frame,
            bound_package.spec,
            price_coverage_kind=price_coverage_kind,
        )
    )
    extra_present_fact_ids: tuple[str, ...] = ()
    if direct_request_present and direct_materialization is not None:
        eligible_texts = frozenset(direct_materialization.eligible_texts)
        extra_present_fact_ids = tuple(
            fact_id
            for fact_id in semantic.direct_fact_ids
            if (fact := context.bundle.facts.get(fact_id)) is not None
            and str(fact.text_fact).strip() in eligible_texts
        )
    if not skip_marketing:
        required_promotion_satisfied = (
            original_commercial_intent == "promotion"
            and bool(semantic.direct_fact_ids)
            and bool(direct_commercial_text.strip())
        )
        bound_with_marketing, fail_reason = _apply_stage51_marketing(
            bound_package,
            context=context,
            semantic=semantic,
            turn_frame=turn_frame,
            shown_fact_ids=shown_fact_ids,
            shown_amplifier_refs=shown_amplifier_refs,
            shown_service_value_ids=shown_service_value_ids,
            last_rendered_promo_fact_id=last_rendered_promo_fact_id,
            last_turn_rendered_promo_fact_ids=last_turn_rendered_promo_fact_ids,
            patient_text=patient_text,
            extra_present_fact_ids=extra_present_fact_ids,
            today=today,
            include_automatic_block=include_automatic_block,
            required_promotion_satisfied=required_promotion_satisfied,
        )
    show_family_price_surface = (
        price_coverage_kind == "family_context"
        and original_commercial_intent == "price"
    )
    presentation_bound = bound_with_marketing
    if (
        show_family_price_surface
        and not _availability_blocks_commerce(availability_status)
        and fail_reason is None
    ):
        from core.sales_fast_strict_evidence import assemble_stage51b_availability_bound_package

        effective_scope = effective_scope_from_semantic_frame(
            semantic,
            current_ui_action=None,
            current_ui_stage_action=None,
        )
        presentation_bound = assemble_stage51b_availability_bound_package(
            turn_frame=turn_frame,
            bundle=context.bundle,
            doctor_catalog=context.doctor_catalog,
            external_index=context.external_index,
            consultation_values=context.consultation_values,
            strategy_context=strategy_context,
            effective_scope=effective_scope,
            allowed_topics=context.allowed_topics,
            today=today,
            md_root=context.md_root,
            client_id=context.client_id,
        )
    if fail_reason is not None and not semantic.direct_fact_ids:
        safe_text = _fail_closed_text(fail_reason)
        empty_decision = TargetPresentationDecision(
            quick_replies=(),
            video=None,
            situation={"show": False, "mode": "normal"},
            dropped=(),
            cadence_update=TargetPresentationCadenceUpdate(),
            channel="none",
        )
        return OneCallPresentationResult(
            status="fail_closed",
            reason_code=fail_reason,
            final_patient_text=safe_text,
            authoritative_commerce=None,
            rendered_marketing_fact_ids=(),
            rendered_promo_fact_ids=(),
            rendered_amplifier_refs=(),
            selected_cta_key=None,
            quick_replies=(),
            secondary_content_slots=(),
            video=None,
            situation={"show": False, "mode": "normal"},
            presentation_channel="none",
            rendered_ids=PresentationRenderedIds(
                marketing_fact_ids=(),
                promo_fact_ids=(),
                amplifier_refs=(),
                followup_refs=(),
                video_id=None,
                situation_shown=False,
            ),
            pending_session_delta=None,
        )

    commerce_result: AuthoritativeCommerceResult | None = None
    precomposer_price_turn = (
        resolved_price_text is not None
        and resolved_price_text.line.strip()
        and original_commercial_intent == "price"
        and precomposer_selected_offer is not None
        and precomposer_selected_offer.availability == "selected"
        and precomposer_selected_offer.offer is not None
    )
    precomposer_multi_price_turn = (
        resolved_price_text is not None
        and resolved_price_text.line.strip()
        and resolved_price_text.owner == "canonical_multi"
        and original_commercial_intent == "price"
        and precomposer_selected_offer is not None
        and precomposer_selected_offer.availability == "multiple"
        and 2 <= len(precomposer_selected_offer.offers) <= 3
    )
    block_legacy_authoritative_commerce = _precomposer_multi_unsafe_block_legacy(
        precomposer_selected_offer=precomposer_selected_offer,
        original_commercial_intent=original_commercial_intent,
        resolved_price_text=resolved_price_text,
    )
    if (
        not turn_frame.needs_clarification
        and not _availability_blocks_commerce(availability_status)
        and price_coverage_kind != "family_context"
    ):
        if precomposer_price_turn:
            commerce_result = build_precomposer_single_offer_commerce(
                precomposer_selected_offer.offer,  # type: ignore[union-attr]
                bundle=context.bundle,
            )
        elif precomposer_multi_price_turn:
            commerce_result = build_precomposer_multi_offer_commerce(
                precomposer_selected_offer.offers,  # type: ignore[union-attr]
                service_id=str(precomposer_selected_offer.service_id),
            )
        elif not block_legacy_authoritative_commerce:
            commerce_result = gate_commerce_result_by_intent(
                build_authoritative_commerce_result(
                    bound_package=bound_with_marketing,
                    resolution=resolution,
                    bundle=context.bundle,
                    strategy_context=strategy_context,
                ),
                commercial_intent=commercial_intent,
            )

    if _availability_blocks_commerce(availability_status):
        final_patient_text = _merge_availability_patient_text(
            availability_status=availability_status,
            overlay=availability_overlay,
            alternative_price_lines=alternative_price_lines,
        )
    else:
        if turn_frame.needs_clarification:
            supplemented_text = patient_text
        elif commercial_intent == "promotion":
            if semantic.direct_fact_ids:
                base_text = _sanitize_patient_text_for_render(
                    patient_text=patient_text,
                    bound_package=presentation_bound,
                    commerce_result=commerce_result,
                    commercial_intent=commercial_intent,
                    direct_eligible_texts=direct_eligible_texts,
                )
                promo_text = build_direct_promotion_patient_text(bound_with_marketing)
                supplemented_text = base_text
                if promo_text.strip():
                    supplemented_text = supplement_sales_fast_patient_text_with_marketing(
                        patient_text=supplemented_text,
                        bound_package=presentation_bound,
                        bundle=context.bundle,
                    )
                if direct_commercial_text.strip():
                    supplemented_text = append_direct_commercial_without_duplicates(
                        supplemented_text,
                        direct_commercial_text,
                    )
                if not supplemented_text.strip() and not direct_commercial_text.strip():
                    safe_text = _fail_closed_text("promotion_no_eligible_facts")
                    return OneCallPresentationResult(
                        status="fail_closed",
                        reason_code="promotion_no_eligible_facts",
                        final_patient_text=safe_text,
                        authoritative_commerce=None,
                        rendered_marketing_fact_ids=(),
                        rendered_promo_fact_ids=(),
                        rendered_amplifier_refs=(),
                        selected_cta_key=None,
                        quick_replies=(),
                        secondary_content_slots=(),
                        video=None,
                        situation={"show": False, "mode": "normal"},
                        presentation_channel="none",
                        rendered_ids=PresentationRenderedIds(
                            marketing_fact_ids=(),
                            promo_fact_ids=(),
                            amplifier_refs=(),
                            followup_refs=(),
                            video_id=None,
                            situation_shown=False,
                        ),
                        pending_session_delta=None,
                        offer_fact_refs=(),
                    )
            else:
                promo_text = build_direct_promotion_patient_text(bound_with_marketing)
                if not promo_text.strip():
                    safe_text = _fail_closed_text("promotion_no_eligible_facts")
                    return OneCallPresentationResult(
                        status="fail_closed",
                        reason_code="promotion_no_eligible_facts",
                        final_patient_text=safe_text,
                        authoritative_commerce=None,
                        rendered_marketing_fact_ids=(),
                        rendered_promo_fact_ids=(),
                        rendered_amplifier_refs=(),
                        selected_cta_key=None,
                        quick_replies=(),
                        secondary_content_slots=(),
                        video=None,
                        situation={"show": False, "mode": "normal"},
                        presentation_channel="none",
                        rendered_ids=PresentationRenderedIds(
                            marketing_fact_ids=(),
                            promo_fact_ids=(),
                            amplifier_refs=(),
                            followup_refs=(),
                            video_id=None,
                            situation_shown=False,
                        ),
                        pending_session_delta=None,
                        offer_fact_refs=(),
                    )
                supplemented_text = promo_text
        else:
            if (
                (precomposer_price_turn or precomposer_multi_price_turn)
                and resolved_price_text is not None
            ):
                if precomposer_multi_price_turn:
                    marketing_only = _price_marketing_suffix_without_service_value(
                        bound_package=presentation_bound,
                        bundle=context,
                    )
                else:
                    marketing_only = supplement_sales_fast_patient_text_with_marketing(
                        patient_text="",
                        bound_package=presentation_bound,
                        bundle=context.bundle,
                    )
                supplemented_text = assemble_price_turn_visible_text(
                    price_line=resolved_price_text.line,
                    patient_text=patient_text,
                    marketing_suffix=marketing_only,
                )
            else:
                base_text = _sanitize_patient_text_for_render(
                    patient_text=patient_text,
                    bound_package=presentation_bound,
                    commerce_result=commerce_result,
                    commercial_intent=commercial_intent,
                    direct_eligible_texts=direct_eligible_texts,
                )
                supplemented_text = supplement_sales_fast_patient_text_with_marketing(
                    patient_text=base_text,
                    bound_package=presentation_bound,
                    bundle=context.bundle,
                )
            if direct_commercial_text.strip():
                supplemented_text = append_direct_commercial_without_duplicates(
                    supplemented_text,
                    direct_commercial_text,
                )
        final_patient_text = supplemented_text
        if (
            commerce_result is not None
            and not precomposer_price_turn
            and not precomposer_multi_price_turn
            and not block_legacy_authoritative_commerce
        ):
            final_patient_text = apply_authoritative_commerce_to_patient_text(
                supplemented_text,
                commerce_result,
            )
        final_patient_text = _merge_availability_patient_text(
            availability_status=availability_status,
            overlay=None,
            patient_text=final_patient_text,
            family_price_context=family_price_context
            if show_family_price_surface
            else None,
        )

    verified = _build_verified(
        bound_package=presentation_bound,
        context=context,
        turn_frame=turn_frame,
        patient_text=final_patient_text,
        user_message=user_message,
    )
    presentation = decide_target_presentation(
        client_id=context.client_id,
        md_root=context.md_root,
        spec=verified.spec,
        navigation_followups=verified.navigation_followups,
        selected_followups=verified.selected_followups,
        primary_content_ref=verified.primary_content_ref,
        cadence=cadence,
        allow_situation=allow_situation and not _availability_blocks_commerce(availability_status),
        alternative_secondary_override=alternative_secondary_slots or None,
    )

    rendered_fact_ids = _rendered_fact_ids_from_text(
        bound_package=bound_with_marketing,
        rendered_text=final_patient_text,
    )
    if direct_materialization is not None and semantic.direct_fact_ids:
        for fact_id in semantic.direct_fact_ids:
            fact = context.bundle.facts.get(fact_id)
            if fact is None:
                continue
            if str(fact.text_fact).strip() in final_patient_text:
                rendered_fact_ids = tuple(dict.fromkeys((*rendered_fact_ids, fact_id)))
    rendered_promo_ids = _promo_fact_ids(
        bound_package=bound_with_marketing,
        rendered_fact_ids=rendered_fact_ids,
        bundle=context.bundle,
    )
    facts_by_id = {f.id: f for f in bound_with_marketing.package.materials.commercial_facts}
    doctors_by_id = {d.doctor_id: d for d in bound_with_marketing.package.materials.doctors}
    used_refs = frozenset(str(r).strip() for r in verified.used_content_refs)
    proven_amplifiers: list[str] = []
    for ref in bound_with_marketing.package.materials.marketing_selection.amplifier_refs:
        if ref.startswith("fact:"):
            fact_id = ref.removeprefix("fact:")
            fact = facts_by_id.get(fact_id)
            if fact is not None and str(fact.text_fact).strip() in final_patient_text:
                proven_amplifiers.append(ref)
        elif ref.startswith("kb:"):
            doc = ref.removeprefix("kb:").split("#", 1)[0]
            if doc in used_refs:
                proven_amplifiers.append(ref)
        elif ref.startswith("doctor:"):
            doctor = doctors_by_id.get(ref.removeprefix("doctor:"))
            if doctor is not None and (
                doctor.profile_ref.removeprefix("kb:").split("#", 1)[0] in used_refs
                or doctor.name.casefold() in final_patient_text.casefold()
            ):
                proven_amplifiers.append(ref)
    rendered_amplifier_refs = tuple(proven_amplifiers)

    followup_refs = tuple(qr.ref for qr in _presentation_quick_replies(presentation))
    video_id = None
    if presentation.video is not None:
        video_id = str(presentation.video.get("video_key") or presentation.video.get("id") or "").strip() or None
    situation_shown = bool(presentation.situation.get("show"))

    last_promo = rendered_promo_ids[0] if len(rendered_promo_ids) == 1 else None
    last_turn_promo_ids = rendered_promo_ids
    offer_fact_refs_tuple = tuple(
        ref
        for ref in bound_with_marketing.package.materials.marketing_selection.selected_refs
        if ref.startswith("fact:")
    )
    cadence_delta = PresentationCadenceDelta(
        shown_video_ids=presentation.cadence_update.shown_video_ids,
        shown_content_followup_refs=presentation.cadence_update.shown_content_followup_refs,
        shown_price_followup_refs=presentation.cadence_update.shown_price_followup_refs,
        situation_offered=presentation.cadence_update.situation_offered,
    )
    service_value_selection = (
        bound_with_marketing.package.materials.marketing_selection.service_value_ref
    )
    rendered_service_value_ids: tuple[str, ...] = ()
    if service_value_selection and service_value_selection.startswith("fact:"):
        fact_id = service_value_selection.removeprefix("fact:")
        sv_text = service_value_text_for_ref(context.bundle, service_value_selection)
        if sv_text and sv_text in final_patient_text:
            rendered_service_value_ids = (fact_id,)
    session_delta = PresentationSessionDelta(
        shown_fact_ids=rendered_fact_ids,
        shown_amplifier_refs=tuple(proven_amplifiers),
        shown_consultation_value_refs=shown_consultation_value_refs,
        shown_service_value_ids=rendered_service_value_ids,
        last_rendered_promo_fact_id=last_promo,
        rendered_promo_fact_ids=rendered_promo_ids,
        last_turn_rendered_promo_fact_ids=last_turn_promo_ids,
        cadence_update=cadence_delta,
    )

    return OneCallPresentationResult(
        status="ok",
        reason_code=None,
        final_patient_text=final_patient_text,
        authoritative_commerce=commerce_result,
        rendered_marketing_fact_ids=rendered_fact_ids,
        rendered_promo_fact_ids=rendered_promo_ids,
        rendered_amplifier_refs=tuple(proven_amplifiers),
        selected_cta_key=verified.selected_cta_key,
        quick_replies=_presentation_quick_replies(presentation),
        secondary_content_slots=(
            alternative_secondary_slots
            if alternative_secondary_slots
            else _secondary_slots(presentation)
        ),
        video=None if alternative_secondary_slots else presentation.video,
        situation={"show": False, "mode": "normal"}
        if alternative_secondary_slots
        else dict(presentation.situation),
        presentation_channel="content" if alternative_secondary_slots else presentation.channel,
        rendered_ids=PresentationRenderedIds(
            marketing_fact_ids=rendered_fact_ids,
            promo_fact_ids=rendered_promo_ids,
            amplifier_refs=tuple(proven_amplifiers),
            followup_refs=followup_refs,
            video_id=video_id if not alternative_secondary_slots else None,
            situation_shown=situation_shown if not alternative_secondary_slots else False,
        ),
        pending_session_delta=session_delta,
        verified_for_session=verified,
        offer_fact_refs=offer_fact_refs_tuple,
        availability_status=availability_status,
        requested_service_id=requested_service_id,
        authored_alternatives=authored_alternatives,
        price_coverage_kind=price_coverage_kind,
        family_price_context=family_price_context,
        alternative_price_lines=alternative_price_lines,
        rendered_alternative_service_ids=tuple(
            slot.ref.removeprefix("target:ui_service/")
            for slot in alternative_secondary_slots
        ),
        rendered_alternative_refs=tuple(slot.ref for slot in alternative_secondary_slots),
    )
