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
    build_broad_family_price_commerce_result,
    build_scoped_family_price_commerce_result,
    build_payment_stages_display_block,
    build_precomposer_multi_offer_commerce,
    build_precomposer_single_offer_commerce,
    PAYMENT_STAGES_UNAVAILABLE_TEXT,
    resolve_payment_stages_offers_for_turn,
    resolve_payment_stages_target_offers,
    _strip_route_metadata,
)
from core.one_call_price_text import (
    apply_model_prose_policy_for_code_owned_monetary_surface,
    assemble_price_turn_visible_text,
    dedupe_price_line_from_patient_text,
    displayed_offers_show_numeric_price,
    enrich_price_line_with_mandatory_conditions,
    is_ambiguous_no_public_price_selection,
    is_no_public_price_price_turn,
    record_monetary_prose_filter_meta,
    resolve_pure_code_owned_monetary_request,
    should_fully_suppress_model_prose_for_code_owned_surface,
)
from contracts.sales_one_plus_semantic import SalesOnePlusSemanticFrame
from core.sales_one_plus_semantic_authority import (
    presentation_active_service_id,
    presentation_commercial_intent,
    presentation_promotion_scope,
)
from core.sales_fast_strict_evidence import effective_scope_from_semantic_frame
from core.one_call_payment_stages_policy import (
    governed_payment_stages_ui_ref,
    payment_stages_materialization_allowed,
)
from core.sales_fast_broad_family_price import (
    BROAD_FAMILY_PRICE_NEUTRAL_INTRO,
    SCOPED_FAMILY_PRICE_NEUTRAL_INTRO,
    is_broad_family_price_overview_turn,
    is_scoped_family_price_overview_turn,
)
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
    del bound_package, commerce_result, commercial_intent, direct_eligible_texts
    return _strip_route_metadata(patient_text).strip()


def _displayed_offers_for_turn(
    *,
    precomposer_selected_offer: PrecomposerSelectedOfferResult | None,
    commerce_result: AuthoritativeCommerceResult | None,
) -> tuple:
    from contracts.response_schema import TargetOffer

    if precomposer_selected_offer is not None:
        if (
            precomposer_selected_offer.availability == "selected"
            and precomposer_selected_offer.offer is not None
        ):
            return (precomposer_selected_offer.offer,)
        if precomposer_selected_offer.availability == "multiple":
            return tuple(precomposer_selected_offer.offers)
    if commerce_result is not None:
        if commerce_result.selected_exact_offer is not None:
            return (commerce_result.selected_exact_offer,)
        if commerce_result.ordered_offers:
            return tuple(commerce_result.ordered_offers)
    return ()


def _current_nav_ref() -> str | None:
    try:
        from flask import has_request_context, request

        if has_request_context():
            ref = str(request.ctx.get("nav_ref") or "").strip()
            return ref or None
    except Exception:
        pass
    return None


def _ctx_typed_action(raw: object, model: type) -> object | None:
    if not isinstance(raw, dict):
        return None
    try:
        return model.model_validate(raw)
    except Exception:
        return None


def _current_ui_scope_action() -> object | None:
    try:
        from flask import has_request_context, request
        from contracts.ui_scope_action import UiScopeAction

        if has_request_context():
            return _ctx_typed_action(request.ctx.get("current_ui_scope_action"), UiScopeAction)
    except Exception:
        pass
    return None


def _current_ui_stage_action() -> object | None:
    try:
        from flask import has_request_context, request
        from contracts.ui_stage_action import UiStageAction

        if has_request_context():
            return _ctx_typed_action(request.ctx.get("current_ui_stage_action"), UiStageAction)
    except Exception:
        pass
    return None


def _presentation_effective_scope(semantic: object) -> object:
    return effective_scope_from_semantic_frame(
        semantic,
        current_ui_action=_current_ui_scope_action(),
        current_ui_stage_action=_current_ui_stage_action(),
    )


def _current_ui_service_action() -> object | None:
    try:
        from flask import has_request_context, request
        from contracts.ui_service_action import UiServiceAction

        if has_request_context():
            return _ctx_typed_action(request.ctx.get("current_ui_service_action"), UiServiceAction)
    except Exception:
        pass
    return None


def _pending_price_clarify_active() -> bool:
    try:
        from flask import has_request_context, request
        from core.pending_price_clarify import (
            is_pending_price_clarify_fresh,
            read_pending_price_clarify,
        )
        from session import mem_get

        if not has_request_context():
            return False
        sid = str(request.ctx.get("sid") or "").strip()
        if not sid:
            return False
        pending = read_pending_price_clarify(mem_get(sid))
        if pending is None:
            return False
        session_turn_count = int(mem_get(sid).get("session_turn_count") or 0)
        return is_pending_price_clarify_fresh(
            pending,
            session_turn_count=session_turn_count,
        )
    except Exception:
        return False


def _resolve_pure_code_owned_monetary_request(user_message: str, nav_ref: str | None) -> bool:
    return resolve_pure_code_owned_monetary_request(
        user_message,
        nav_ref=nav_ref,
        current_ui_scope_action=_current_ui_scope_action(),
        current_ui_service_action=_current_ui_service_action(),
        pending_price_clarify_active=_pending_price_clarify_active(),
    )


def _presentation_mode_for_turn(
    *,
    precomposer_selected_offer: PrecomposerSelectedOfferResult | None,
    broad_family_price_turn: bool,
    scoped_family_price_turn: bool,
) -> str:
    if broad_family_price_turn or scoped_family_price_turn:
        return "broad"
    if precomposer_selected_offer is None:
        return "none"
    if precomposer_selected_offer.availability == "selected":
        return "exact"
    if precomposer_selected_offer.availability == "multiple":
        return "multiple"
    return "none"


def _presentation_session_state() -> object:
    from core.target_runtime_session import TargetRuntimeSessionState

    try:
        from flask import has_request_context, request
        from core.target_runtime_session import read_target_runtime_session

        if has_request_context():
            sid = str(request.ctx.get("sid") or "").strip()
            if sid:
                return read_target_runtime_session(sid)
    except Exception:
        pass

    return TargetRuntimeSessionState(
        last_service_id=None,
        last_topic=None,
        last_primary_aspect=None,
        service_focus_set_at_turn=None,
        session_turn_count=0,
        shown_fact_ids=(),
        shown_amplifier_refs=(),
        shown_consultation_value_refs=(),
        shown_service_value_ids=(),
        shown_video_ids=(),
        shown_content_followup_refs=(),
        shown_price_followup_refs=(),
        situation_offered=False,
        last_rendered_promo_fact_id=None,
        rendered_promo_fact_ids=(),
        last_turn_rendered_promo_fact_ids=(),
        followups=(),
    )


def _append_payment_stages_if_requested(
    text: str,
    *,
    semantic: SalesOnePlusSemanticFrame,
    user_message: str,
    displayed_offers: tuple,
    commerce_result: AuthoritativeCommerceResult | None,
    precomposer_selected_offer: PrecomposerSelectedOfferResult | None,
    selected_brand_id: str | None,
    bundle: TargetRuntimeClientContext,
    nav_ref: str | None = None,
) -> str:
    if not payment_stages_materialization_allowed(
        semantic=semantic,
        user_message=user_message,
        nav_ref=nav_ref,
    ):
        return text

    selected_exact_offer = None
    if commerce_result is not None and commerce_result.selected_exact_offer is not None:
        selected_exact_offer = commerce_result.selected_exact_offer
    elif (
        precomposer_selected_offer is not None
        and precomposer_selected_offer.availability == "selected"
        and precomposer_selected_offer.offer is not None
    ):
        selected_exact_offer = precomposer_selected_offer.offer

    session_state = _presentation_session_state()
    target_offers = resolve_payment_stages_offers_for_turn(
        bundle=bundle.bundle,
        nav_ref=nav_ref,
        session_state=session_state,
        displayed_offers=tuple(displayed_offers),
        selected_exact_offer=selected_exact_offer,
        selected_brand_id=selected_brand_id,
        followups=session_state.followups,
    )
    if not target_offers:
        if governed_payment_stages_ui_ref(nav_ref):
            return text.strip() or PAYMENT_STAGES_UNAVAILABLE_TEXT
        if (
            semantic.commercial_intent == "payment_stages"
            and selected_exact_offer is not None
        ):
            return PAYMENT_STAGES_UNAVAILABLE_TEXT
        return text

    block = build_payment_stages_display_block(
        target_offers,
        bundle=bundle.bundle,
    )
    if not block:
        if governed_payment_stages_ui_ref(nav_ref):
            return text.strip() or PAYMENT_STAGES_UNAVAILABLE_TEXT
        if (
            semantic.commercial_intent == "payment_stages"
            and selected_exact_offer is not None
        ):
            return PAYMENT_STAGES_UNAVAILABLE_TEXT
        return text
    if block in text:
        return text
    separator = "\n\n" if text.strip() else ""
    return f"{text.rstrip()}{separator}{block}"


def _materialized_public_price_turn(
    *,
    has_code_price_line: bool,
    no_public_price_line_turn: bool,
    displayed_offers: tuple,
    broad_family_code_price_turn: bool,
    scoped_family_code_price_turn: bool,
) -> bool:
    if no_public_price_line_turn:
        return False
    if broad_family_code_price_turn or scoped_family_code_price_turn:
        return True
    if not has_code_price_line:
        return False
    if displayed_offers and displayed_offers_show_numeric_price(displayed_offers):
        return True
    return has_code_price_line and not displayed_offers


def _apply_model_prose_policy_for_code_price_turn(
    *,
    patient_body: str,
    user_message: str,
    has_monetary_surface: bool,
    materialized_public_price: bool,
    pure_code_owned_monetary_request: bool,
    nav_ref: str | None,
    no_public_price_line_turn: bool,
) -> str:
    filtered, removed, partial_answer = apply_model_prose_policy_for_code_owned_monetary_surface(
        patient_body,
        user_message=user_message,
        has_monetary_surface=has_monetary_surface,
        materialized_public_price=materialized_public_price,
        pure_code_owned_monetary_request=pure_code_owned_monetary_request,
        nav_ref=nav_ref,
        no_public_price_line_turn=no_public_price_line_turn,
    )
    record_monetary_prose_filter_meta(
        removed_paragraph_count=removed,
        fully_suppressed=should_fully_suppress_model_prose_for_code_owned_surface(
            pure_code_owned_monetary_request=pure_code_owned_monetary_request,
            has_monetary_surface=has_monetary_surface,
            materialized_public_price=materialized_public_price,
            nav_ref=nav_ref,
            no_public_price_line_turn=no_public_price_line_turn,
        ),
        partial_answer=partial_answer,
    )
    return filtered


def _has_code_owned_monetary_surface(
    *,
    has_code_price_line: bool,
    broad_family_code_price_turn: bool,
    scoped_family_code_price_turn: bool,
    payment_stages_requested: bool,
) -> bool:
    return bool(
        has_code_price_line
        or broad_family_code_price_turn
        or scoped_family_code_price_turn
        or payment_stages_requested
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
    """Dormant legacy helper — do not use for active session provenance.

    Active presentation records only explicitly code-owned fact IDs with
    provenance, not substring matches in final patient text.
    """

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

    skip_marketing = True
    bound_with_marketing = bound_package
    fail_reason = None
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

        effective_scope = _presentation_effective_scope(semantic)
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
    effective_scope = _presentation_effective_scope(semantic)
    nav_ref = _current_nav_ref()
    payment_stages_requested = payment_stages_materialization_allowed(
        semantic=semantic,
        user_message=user_message,
        nav_ref=nav_ref,
    )
    precomposer_price_turn = (
        resolved_price_text is not None
        and resolved_price_text.line.strip()
        and original_commercial_intent == "price"
        and precomposer_selected_offer is not None
        and precomposer_selected_offer.availability == "selected"
        and precomposer_selected_offer.offer is not None
    )
    ambiguous_no_public_price_turn = (
        original_commercial_intent == "price"
        and resolved_price_text is not None
        and resolved_price_text.line.strip()
        and precomposer_selected_offer is not None
        and is_ambiguous_no_public_price_selection(precomposer_selected_offer)
    )
    no_public_price_line_turn = is_no_public_price_price_turn(
        commercial_intent=original_commercial_intent,
        selection=precomposer_selected_offer,
        resolved_price_text=resolved_price_text,
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
    broad_family_price_turn = is_broad_family_price_overview_turn(
        bound_package=bound_with_marketing,
        semantic=semantic,
        turn_frame=turn_frame,
        effective_scope=effective_scope,
        user_message=user_message,
    )
    scoped_family_price_turn = is_scoped_family_price_overview_turn(
        bound_package=bound_with_marketing,
        semantic=semantic,
        turn_frame=turn_frame,
        user_message=user_message,
    )
    if (
        not _availability_blocks_commerce(availability_status)
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
                bundle=context.bundle,
                strategy_context=strategy_context,
            )
        elif broad_family_price_turn:
            broad_scope = _presentation_effective_scope(semantic)
            commerce_result = build_broad_family_price_commerce_result(
                bound_package=bound_with_marketing,
                bundle=context.bundle,
                doctor_catalog=context.doctor_catalog,
                effective_scope=broad_scope,
            )
        elif scoped_family_price_turn:
            scoped_scope = _presentation_effective_scope(semantic)
            commerce_result = build_scoped_family_price_commerce_result(
                bound_package=bound_with_marketing,
                bundle=context.bundle,
                doctor_catalog=context.doctor_catalog,
                effective_scope=scoped_scope,
            )

    patient_body = _sanitize_patient_text_for_render(
        patient_text=patient_text,
        bound_package=presentation_bound,
        commerce_result=commerce_result,
        commercial_intent=commercial_intent,
    )
    displayed_offers = _displayed_offers_for_turn(
        precomposer_selected_offer=precomposer_selected_offer,
        commerce_result=commerce_result,
    )
    broad_family_code_price_turn = (
        broad_family_price_turn
        and commerce_result is not None
        and bool(commerce_result.patient_price_block)
    )
    scoped_family_code_price_turn = (
        scoped_family_price_turn
        and commerce_result is not None
        and bool(commerce_result.patient_price_block)
    )
    has_code_price_line = (
        original_commercial_intent == "price"
        and resolved_price_text is not None
        and resolved_price_text.line.strip()
        and resolved_price_text.owner != "none"
    )
    materialized_public_price = _materialized_public_price_turn(
        has_code_price_line=has_code_price_line,
        no_public_price_line_turn=no_public_price_line_turn,
        displayed_offers=displayed_offers,
        broad_family_code_price_turn=broad_family_code_price_turn,
        scoped_family_code_price_turn=scoped_family_code_price_turn,
    )
    has_code_owned_monetary_surface = _has_code_owned_monetary_surface(
        has_code_price_line=has_code_price_line,
        broad_family_code_price_turn=broad_family_code_price_turn,
        scoped_family_code_price_turn=scoped_family_code_price_turn,
        payment_stages_requested=payment_stages_requested,
    )
    pure_code_owned_monetary_request = _resolve_pure_code_owned_monetary_request(
        user_message,
        nav_ref,
    )
    if has_code_owned_monetary_surface:
        patient_body = _apply_model_prose_policy_for_code_price_turn(
            patient_body=patient_body,
            user_message=user_message,
            has_monetary_surface=True,
            materialized_public_price=materialized_public_price,
            pure_code_owned_monetary_request=pure_code_owned_monetary_request,
            nav_ref=nav_ref,
            no_public_price_line_turn=no_public_price_line_turn,
        )
    if _availability_blocks_commerce(availability_status):
        final_patient_text = _merge_availability_patient_text(
            availability_status=availability_status,
            overlay=availability_overlay,
            alternative_price_lines=alternative_price_lines,
        )
    else:
        price_line: str | None = None
        if scoped_family_code_price_turn:
            supplemented_text = apply_authoritative_commerce_to_patient_text(
                SCOPED_FAMILY_PRICE_NEUTRAL_INTRO,
                commerce_result,
            )
        elif turn_frame.needs_clarification and broad_family_code_price_turn:
            supplemented_text = apply_authoritative_commerce_to_patient_text(
                BROAD_FAMILY_PRICE_NEUTRAL_INTRO,
                commerce_result,
            )
        elif (
            (precomposer_price_turn or precomposer_multi_price_turn or ambiguous_no_public_price_turn)
            and resolved_price_text is not None
        ):
            price_line = resolved_price_text.line
            if displayed_offers:
                price_line = enrich_price_line_with_mandatory_conditions(
                    price_line,
                    displayed_offers,
                )
            patient_body = dedupe_price_line_from_patient_text(patient_body, price_line)
            supplemented_text = assemble_price_turn_visible_text(
                price_line=price_line,
                patient_text=patient_body,
                marketing_suffix="",
            )
        elif commerce_result is not None and commerce_result.patient_price_block:
            supplemented_text = apply_authoritative_commerce_to_patient_text(
                patient_body,
                commerce_result,
            )
        elif turn_frame.needs_clarification:
            supplemented_text = patient_body
        else:
            supplemented_text = patient_body
        final_patient_text = supplemented_text
        selected_brand_id = str(
            bound_with_marketing.package.materials.selected_brand_id or ""
        ).strip() or None
        final_patient_text = _append_payment_stages_if_requested(
            final_patient_text,
            semantic=semantic,
            user_message=user_message,
            displayed_offers=displayed_offers,
            commerce_result=commerce_result,
            precomposer_selected_offer=precomposer_selected_offer,
            selected_brand_id=selected_brand_id,
            bundle=context,
            nav_ref=nav_ref,
        )
        final_patient_text = _merge_availability_patient_text(
            availability_status=availability_status,
            overlay=None,
            patient_text=final_patient_text,
            family_price_context=family_price_context
            if show_family_price_surface
            else None,
        )
        if (
            payment_stages_requested
            and pure_code_owned_monetary_request
            and not str(final_patient_text or "").strip()
        ):
            final_patient_text = PAYMENT_STAGES_UNAVAILABLE_TEXT

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
        used_content_refs=verified.used_content_refs,
        cadence=cadence,
        allow_situation=allow_situation and not _availability_blocks_commerce(availability_status),
        scenario=semantic.scenario,
        topic=turn_frame.topic,
        alternative_secondary_override=alternative_secondary_slots or None,
    )

    code_owned_rendered_fact_ids: tuple[str, ...] = ()
    rendered_fact_ids = code_owned_rendered_fact_ids
    rendered_promo_ids = _promo_fact_ids(
        bound_package=bound_with_marketing,
        rendered_fact_ids=rendered_fact_ids,
        bundle=context.bundle,
    )
    facts_by_id = {f.id: f for f in bound_with_marketing.package.materials.commercial_facts}
    doctors_by_id = {d.doctor_id: d for d in bound_with_marketing.package.materials.doctors}
    used_refs = frozenset(str(r).strip() for r in verified.used_content_refs)
    proven_amplifiers: list[str] = []
    rendered_amplifier_refs: tuple[str, ...] = ()

    followup_refs = tuple(qr.ref for qr in _presentation_quick_replies(presentation))
    video_id = None
    if presentation.video is not None:
        video_id = str(
            presentation.video.get("key")
            or presentation.video.get("video_key")
            or presentation.video.get("id")
            or ""
        ).strip() or None
    situation_shown = bool(presentation.situation.get("show"))

    last_promo = rendered_promo_ids[0] if len(rendered_promo_ids) == 1 else None
    last_turn_promo_ids = rendered_promo_ids
    offer_fact_refs_tuple: tuple[str, ...] = ()
    cadence_delta = PresentationCadenceDelta(
        shown_video_ids=presentation.cadence_update.shown_video_ids,
        shown_content_followup_refs=presentation.cadence_update.shown_content_followup_refs,
        shown_price_followup_refs=presentation.cadence_update.shown_price_followup_refs,
        situation_offered=presentation.cadence_update.situation_offered,
    )
    session_delta = PresentationSessionDelta(
        shown_fact_ids=rendered_fact_ids,
        shown_amplifier_refs=rendered_amplifier_refs,
        shown_consultation_value_refs=(),
        shown_service_value_ids=(),
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
        rendered_amplifier_refs=rendered_amplifier_refs,
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
