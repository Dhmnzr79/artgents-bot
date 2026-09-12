"""Pure production adapter between typed FullContext authorities and response-plan path."""

from __future__ import annotations

from typing import TYPE_CHECKING

from contracts.response_plan import (
    CanonicalMultiPriceCandidate,
    CanonicalSinglePriceCandidate,
    CodeOwnedTerminalCandidate,
    CommercialFactCandidate,
    ComposerSelectedRouteAuthority,
    DeterministicBypassRouteAuthority,
    FactApplicability,
    FactRole,
    FrozenPriceOfferRow,
    PreComposerPlan,
    PricePlan,
    RequiredOfferConditionBlock,
    ResponseCaps,
    ResponseScope,
    RouteModePair,
    ServiceValueCandidate,
    TextualCtaCandidate,
    UiButtonCandidate,
    UiPlanCandidates,
    UiQuickReplyCandidate,
    UiVideoCandidate,
    UiWidgetCandidate,
    all_allowed_route_mode_pairs,
)
from contracts.response_plan_adapter import (
    ResponsePlanAdapterComposerRouteAuthority,
    ResponsePlanAdapterDeterministicRouteAuthority,
    ResponsePlanAdapterError,
    ResponsePlanAdapterMaterialAuthority,
    ResponsePlanAdapterSources,
    ResponsePlanAdapterTerminalAuthority,
)
from contracts.response_schema import BillingUnit, TargetCommercialFact, TargetFixedPrice, TargetOffer
from contracts.target_response_spec import TargetResponseSpec
from contracts.turn_frame import TurnFrame
from core.target_client_ui_nav import TargetNavigationFollowup
from core.target_offline_response_assembly import TargetOfflineResponseMaterials
from core.target_response_followup_policy import TargetResponseFollowupSelection
from core.target_response_materialization_plan import TargetResponseMaterializationPlan

if TYPE_CHECKING:
    from core.target_response_followup_materializer import TargetContentFollowup, TargetPriceFollowup

_EXPLICIT_ONLY_FACT_IDS: frozenset[str] = frozenset({"implant_warranty", "clinic_warranty"})
_INVALID_TOPIC_IDS: frozenset[str] = frozenset({"unknown", "none", "null", "n/a", "na"})
_CURRENCY_SYMBOLS: dict[str, str] = {"RUB": "₽"}
_BILLING_UNIT_PHRASES: dict[BillingUnit, str] = {
    "tooth": "за один зуб",
    "implant": "за один имплант",
    "tooth_package": "за лечение одного зуба под ключ",
    "jaw": "за одну челюсть",
    "both_jaws": "за обе челюсти",
    "procedure": "за одну процедуру",
    "unit": "за одну единицу",
    "course": "за курс лечения",
}
_COMPOSER_TERMINAL_PAIRS: frozenset[tuple[str, str]] = frozenset(
    {
        ("ANSWER", "contacts"),
        ("ADMIN", "standard"),
        ("ADMIN", "medical_terminal"),
    }
)
_EMPTY_UI = UiPlanCandidates()


def build_pre_composer_plan(sources: ResponsePlanAdapterSources) -> PreComposerPlan:
    """Map typed runtime authorities into an isolated PreComposerPlan."""

    session_client_id = sources.session_key.client_id
    _assert_client_lane(session_client_id, sources)

    scope, selected_service_id, selected_topic_id, active_session_service_id = _resolve_scope(
        sources.turn_frame,
        sources.allowed_topic_ids,
        sources.session_state.last_service_id,
    )

    route_authority = sources.route_authority
    if isinstance(route_authority, ResponsePlanAdapterDeterministicRouteAuthority):
        return _build_deterministic_bypass_plan(
            sources,
            session_client_id=session_client_id,
            route_authority=route_authority,
            scope=scope,
            selected_service_id=selected_service_id,
            selected_topic_id=selected_topic_id,
            active_session_service_id=active_session_service_id,
        )

    return _build_composer_selected_plan(
        sources,
        session_client_id=session_client_id,
        scope=scope,
        selected_service_id=selected_service_id,
        selected_topic_id=selected_topic_id,
        active_session_service_id=active_session_service_id,
    )


def billing_unit_phrase(billing_unit: str) -> str:
    phrase = _BILLING_UNIT_PHRASES.get(billing_unit)  # type: ignore[arg-type]
    if phrase is None:
        raise ResponsePlanAdapterError("adapter_price_metadata_incomplete", billing_unit)
    return phrase


def format_single_price_display(offer: TargetOffer) -> str:
    fixed = _require_fixed_price(offer)
    amount = _format_amount(fixed.amount)
    symbol = _currency_symbol(fixed.currency)
    unit_phrase = billing_unit_phrase(fixed.billing_unit)
    return f"{amount} {symbol} {unit_phrase} — {offer.package.label}"


def format_frozen_price_row_display(
    row: FrozenPriceOfferRow,
    *,
    package_label: str | None = None,
) -> str:
    amount = _format_amount(row.amount)
    symbol = _currency_symbol(row.currency)
    unit_phrase = billing_unit_phrase(row.billing_unit)
    package = (package_label or "").strip()
    if package:
        return f"{amount} {symbol} {unit_phrase} — {row.offer_label}: {package}"
    return f"{amount} {symbol} {unit_phrase} — {row.offer_label}"


def format_multi_price_display_from_rows(
    rows: tuple[FrozenPriceOfferRow, ...],
    package_labels: tuple[str | None, ...] | None = None,
) -> str:
    labels = package_labels if package_labels is not None else (None,) * len(rows)
    if len(labels) != len(rows):
        raise ResponsePlanAdapterError("adapter_price_row_label_mismatch", len(labels))
    lines = [
        format_frozen_price_row_display(row, package_label=package_label)
        for row, package_label in zip(rows, labels, strict=True)
    ]
    return "\n".join(lines)


def format_multi_price_display(offers: tuple[TargetOffer, ...]) -> str:
    lines = [format_single_price_display(offer) for offer in offers]
    return "\n".join(lines)


def _build_composer_selected_plan(
    sources: ResponsePlanAdapterSources,
    *,
    session_client_id: str,
    scope: ResponseScope,
    selected_service_id: str | None,
    selected_topic_id: str | None,
    active_session_service_id: str | None,
) -> PreComposerPlan:
    authority = sources.material_authority
    if authority is None:
        raise ResponsePlanAdapterError("adapter_material_authority_required", "composer_selected")
    material_client_id = authority.source_client_id
    if material_client_id != session_client_id:
        raise ResponsePlanAdapterError(
            "adapter_client_mismatch",
            ("material", material_client_id, session_client_id),
        )
    _validate_package_coherence(authority)
    bound_package = authority.bound_package
    spec = bound_package.spec
    materials = bound_package.package.materials
    materialization_plan = bound_package.package.plan
    selected_followups = bound_package.package.selected_followups
    _validate_spec_turn_alignment(sources.turn_frame, spec)

    price_plan = _build_price_plan(spec, materials, materialization_plan, material_client_id)
    required_conditions = _build_required_conditions(sources, price_plan, session_client_id)
    commercial_facts, promo_ids, amplifier_ids = _build_commercial_facts(
        materials,
        material_client_id,
    )
    service_value = _build_service_value_candidate(
        materials,
        material_client_id,
        response_scope=scope,
    )
    textual_cta = _build_textual_cta(sources, session_client_id, bound_package.selected_cta_key)
    ui_candidates = _build_material_ui_candidates(
        sources,
        material_client_id,
        bound_package,
        selected_followups,
    )
    terminal_candidates = _build_terminal_candidates(sources, session_client_id)

    return PreComposerPlan(
        session_key=sources.session_key,
        context_strategy=sources.context_strategy,
        route_authority=ComposerSelectedRouteAuthority(
            allowed_route_modes=all_allowed_route_mode_pairs(),
            terminal_candidates=terminal_candidates,
        ),
        response_scope=scope,
        selected_service_id=selected_service_id,
        active_session_service_id=active_session_service_id,
        selected_topic_id=selected_topic_id,
        history_turn_count=sources.session_state.history_turn_count,
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
    )


def _build_deterministic_bypass_plan(
    sources: ResponsePlanAdapterSources,
    *,
    session_client_id: str,
    route_authority: ResponsePlanAdapterDeterministicRouteAuthority,
    scope: ResponseScope,
    selected_service_id: str | None,
    selected_topic_id: str | None,
    active_session_service_id: str | None,
) -> PreComposerPlan:
    pair = (route_authority.route, route_authority.mode)
    if sources.material_authority is not None:
        raise ResponsePlanAdapterError("adapter_material_authority_forbidden", pair)
    terminal = _require_deterministic_terminal(sources, pair, session_client_id)
    return PreComposerPlan(
        session_key=sources.session_key,
        context_strategy=sources.context_strategy,
        route_authority=DeterministicBypassRouteAuthority(
            route_mode=RouteModePair(route=route_authority.route, mode=route_authority.mode),
            terminal_candidate=terminal,
        ),
        response_scope=scope,
        selected_service_id=selected_service_id,
        active_session_service_id=active_session_service_id,
        selected_topic_id=selected_topic_id,
        history_turn_count=sources.session_state.history_turn_count,
        price_plan=PricePlan(kind="none"),
        required_offer_conditions=(),
        commercial_facts=(),
        promo_candidate_ids=(),
        automatic_amplifier_candidate_ids=(),
        service_value_candidate=None,
        textual_cta_candidate=None,
        normal_caps=ResponseCaps(),
        price_caps=ResponseCaps(max_service_value=0, max_promo=2, max_automatic_amplifiers=4),
        ui_candidates=_build_non_material_ui_candidates(sources, session_client_id),
        transport_kind=sources.transport_kind,
    )


def _validate_package_coherence(authority: ResponsePlanAdapterMaterialAuthority) -> None:
    bound = authority.bound_package
    package = bound.package
    materials = package.materials
    plan = package.plan

    if plan.required_components != bound.spec.required_components:
        raise ResponsePlanAdapterError(
            "adapter_package_source_incoherent",
            ("required_components", plan.required_components, bound.spec.required_components),
        )
    if plan.service_id != materials.service_id:
        raise ResponsePlanAdapterError(
            "adapter_package_source_incoherent",
            ("service_id", plan.service_id, materials.service_id),
        )
    if plan.selected_brand_id != materials.selected_brand_id:
        raise ResponsePlanAdapterError(
            "adapter_package_source_incoherent",
            ("selected_brand_id", plan.selected_brand_id, materials.selected_brand_id),
        )
    _validate_offer_coherence(plan, materials)
    fact_ids = tuple(fact.id for fact in materials.commercial_facts)
    if fact_ids != plan.commercial_fact_ids:
        raise ResponsePlanAdapterError(
            "adapter_package_source_incoherent",
            ("commercial_fact_ids", fact_ids, plan.commercial_fact_ids),
        )


def _validate_offer_coherence(
    plan: TargetResponseMaterializationPlan,
    materials: TargetOfflineResponseMaterials,
) -> None:
    material_offer_ids = {offer.offer_id for offer in materials.offers}
    price_requested = "price" in plan.required_components
    if price_requested:
        if not plan.offer_ids:
            raise ResponsePlanAdapterError(
                "adapter_package_source_incoherent",
                ("price_offer_ids_empty", plan.offer_ids),
            )
        if len(plan.offer_ids) != len(set(plan.offer_ids)):
            raise ResponsePlanAdapterError(
                "adapter_package_source_incoherent",
                ("price_offer_ids_duplicate", plan.offer_ids),
            )
        for offer_id in plan.offer_ids:
            if offer_id not in material_offer_ids:
                raise ResponsePlanAdapterError(
                    "adapter_package_source_incoherent",
                    ("offer_id_foreign", offer_id),
                )
        return
    if plan.offer_ids:
        raise ResponsePlanAdapterError(
            "adapter_package_source_incoherent",
            ("non_price_offer_ids_forbidden", plan.offer_ids),
        )


def _offers_for_price_plan(
    materials: TargetOfflineResponseMaterials,
    plan: TargetResponseMaterializationPlan,
) -> tuple[TargetOffer, ...]:
    if "price" not in plan.required_components:
        return ()
    offer_index = {offer.offer_id: offer for offer in materials.offers}
    selected: list[TargetOffer] = []
    for offer_id in plan.offer_ids:
        offer = offer_index.get(offer_id)
        if offer is None:
            raise ResponsePlanAdapterError(
                "adapter_package_source_incoherent",
                ("offer_id_missing", offer_id),
            )
        selected.append(offer)
    return tuple(selected)


def _validate_spec_turn_alignment(frame: TurnFrame, spec: TargetResponseSpec) -> None:
    if spec.service_id is not None and frame.service_id is not None and spec.service_id != frame.service_id:
        raise ResponsePlanAdapterError(
            "adapter_spec_turn_conflict",
            (spec.service_id, frame.service_id),
        )


def _resolve_scope(
    frame: TurnFrame,
    allowed_topic_ids: tuple[str, ...],
    last_service_id: str | None,
) -> tuple[ResponseScope, str | None, str | None, str | None]:
    active_session_service_id = _normalize_optional_id(last_service_id)
    if _normalize_optional_id(frame.service_id) is not None:
        return "service", frame.service_id, None, active_session_service_id
    topic_id = _valid_topic_id(frame.topic, allowed_topic_ids)
    if topic_id is not None:
        return "topic", None, topic_id, active_session_service_id
    return "clinic", None, None, active_session_service_id


def _valid_topic_id(topic: str | None, allowed_topic_ids: tuple[str, ...]) -> str | None:
    if topic is None or not topic.strip() or _is_invalid_topic_token(topic):
        return None
    normalized = topic.strip()
    if allowed_topic_ids and normalized not in allowed_topic_ids:
        return None
    return normalized


def _is_invalid_topic_token(topic: str) -> bool:
    token = topic.strip().lower()
    return token in _INVALID_TOPIC_IDS


def _normalize_optional_id(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized or normalized.lower() in _INVALID_TOPIC_IDS:
        return None
    return normalized


def _assert_client_lane(client_id: str, sources: ResponsePlanAdapterSources) -> None:
    if sources.condition_authority is not None and sources.condition_authority.source_client_id != client_id:
        raise ResponsePlanAdapterError(
            "adapter_client_mismatch",
            ("conditions", sources.condition_authority.source_client_id),
        )
    for authority in sources.terminal_authorities:
        if authority.source_client_id != client_id:
            raise ResponsePlanAdapterError(
                "adapter_client_mismatch",
                ("terminal", authority.source_client_id),
            )
        contact = authority.canonical_contact
        if contact is not None and contact.source_client_id != client_id:
            raise ResponsePlanAdapterError(
                "adapter_client_mismatch",
                ("terminal_contact", contact.source_client_id),
            )
    if sources.ui_authority is not None and sources.ui_authority.source_client_id != client_id:
        raise ResponsePlanAdapterError("adapter_client_mismatch", ("ui", sources.ui_authority.source_client_id))
    if (
        sources.textual_cta_authority is not None
        and sources.textual_cta_authority.source_client_id != client_id
    ):
        raise ResponsePlanAdapterError(
            "adapter_client_mismatch",
            ("textual_cta", sources.textual_cta_authority.source_client_id),
        )


def _terminal_from_authority(authority: ResponsePlanAdapterTerminalAuthority) -> CodeOwnedTerminalCandidate:
    return CodeOwnedTerminalCandidate(
        source_client_id=authority.source_client_id,
        route=authority.route,
        mode=authority.mode,
        authority=authority.authority,
        display_text=authority.display_text,
        canonical_contact=authority.canonical_contact,
    )


def _build_terminal_candidates(
    sources: ResponsePlanAdapterSources,
    client_id: str,
) -> tuple[CodeOwnedTerminalCandidate, ...]:
    candidates: list[CodeOwnedTerminalCandidate] = []
    seen: set[tuple[str, str]] = set()
    for authority in sources.terminal_authorities:
        pair = (authority.route, authority.mode)
        if pair not in _COMPOSER_TERMINAL_PAIRS:
            raise ResponsePlanAdapterError("adapter_terminal_authority_invalid", pair)
        if pair in seen:
            raise ResponsePlanAdapterError("adapter_terminal_authority_invalid", "duplicate")
        if authority.source_client_id != client_id:
            raise ResponsePlanAdapterError("adapter_client_mismatch", ("terminal", authority.source_client_id))
        candidates.append(_terminal_from_authority(authority))
        seen.add(pair)
    for required_pair in _COMPOSER_TERMINAL_PAIRS:
        if required_pair not in seen:
            raise ResponsePlanAdapterError("adapter_terminal_authority_invalid", required_pair)
    return tuple(candidates)


def _require_deterministic_terminal(
    sources: ResponsePlanAdapterSources,
    pair: tuple[str, str],
    client_id: str,
) -> CodeOwnedTerminalCandidate:
    matches = [
        authority
        for authority in sources.terminal_authorities
        if (authority.route, authority.mode) == pair
    ]
    if len(matches) != 1:
        raise ResponsePlanAdapterError("adapter_terminal_authority_invalid", pair)
    authority = matches[0]
    if authority.source_client_id != client_id:
        raise ResponsePlanAdapterError("adapter_client_mismatch", ("terminal", authority.source_client_id))
    return _terminal_from_authority(authority)


def _price_intent(spec: TargetResponseSpec) -> bool:
    return "price" in spec.required_components


def _build_price_plan(
    spec: TargetResponseSpec,
    materials: TargetOfflineResponseMaterials,
    materialization_plan: TargetResponseMaterializationPlan,
    material_client_id: str,
) -> PricePlan:
    if not _price_intent(spec):
        return PricePlan(kind="none")
    offers = _active_fixed_offers(_offers_for_price_plan(materials, materialization_plan))
    if not offers:
        raise ResponsePlanAdapterError("adapter_price_intent_without_offer")
    if len(offers) == 1:
        offer = offers[0]
        fixed = _require_fixed_price(offer)
        if not fixed.currency or not fixed.billing_unit or not offer.package.label:
            raise ResponsePlanAdapterError("adapter_price_metadata_incomplete", offer.offer_id)
        billing_unit_phrase(fixed.billing_unit)
        return PricePlan(
            kind="single",
            single=CanonicalSinglePriceCandidate(
                source_client_id=material_client_id,
                offer_id=offer.offer_id,
                display_text=format_single_price_display(offer),
                amount=fixed.amount,
                currency=fixed.currency,
                billing_unit=fixed.billing_unit,
            ),
        )
    if len(offers) > 3:
        raise ResponsePlanAdapterError("adapter_price_shape_unsupported", len(offers))
    billing_units = {
        offer.price.billing_unit for offer in offers if isinstance(offer.price, TargetFixedPrice)
    }
    currencies = {
        offer.price.currency for offer in offers if isinstance(offer.price, TargetFixedPrice)
    }
    if len(billing_units) != 1:
        raise ResponsePlanAdapterError("adapter_price_shape_unsupported", billing_units)
    if len(currencies) != 1:
        raise ResponsePlanAdapterError("adapter_price_shape_unsupported", currencies)
    return PricePlan(
        kind="multi",
        multi=CanonicalMultiPriceCandidate(
            source_client_id=material_client_id,
            offer_ids=tuple(offer.offer_id for offer in offers),
            display_text=format_multi_price_display(offers),
        ),
    )


def _active_fixed_offers(offers: tuple[TargetOffer, ...]) -> tuple[TargetOffer, ...]:
    selected: list[TargetOffer] = []
    for offer in offers:
        if not offer.active:
            continue
        if isinstance(offer.price, TargetFixedPrice):
            selected.append(offer)
            continue
        raise ResponsePlanAdapterError("adapter_price_shape_unsupported", offer.price.mode)
    return tuple(selected)


def _require_fixed_price(offer: TargetOffer) -> TargetFixedPrice:
    if not isinstance(offer.price, TargetFixedPrice):
        raise ResponsePlanAdapterError("adapter_price_shape_unsupported", offer.price.mode)
    return offer.price


def _build_required_conditions(
    sources: ResponsePlanAdapterSources,
    price_plan: PricePlan,
    client_id: str,
) -> tuple[RequiredOfferConditionBlock, ...]:
    if price_plan.kind == "none":
        return ()
    authority = sources.condition_authority
    if authority is None:
        return ()
    if authority.price_response_requires_conditions and not authority.required_conditions:
        raise ResponsePlanAdapterError("adapter_price_conditions_unavailable")
    for block in authority.required_conditions:
        if block.source_client_id != client_id:
            raise ResponsePlanAdapterError("adapter_client_mismatch", ("condition", block.source_client_id))
    return authority.required_conditions


def _build_commercial_facts(
    materials: TargetOfflineResponseMaterials,
    material_client_id: str,
) -> tuple[tuple[CommercialFactCandidate, ...], tuple[str, ...], tuple[str, ...]]:
    bundle_facts = {fact.id: fact for fact in materials.commercial_facts}
    promo_ids = _promo_fact_ids(materials)
    amplifier_ids = _amplifier_fact_ids(materials)
    candidates: list[CommercialFactCandidate] = []
    seen: set[str] = set()
    for fact in materials.commercial_facts:
        if not fact.active:
            raise ResponsePlanAdapterError("adapter_fact_source_missing", fact.id)
        if fact.id in seen:
            continue
        seen.add(fact.id)
        roles = _fact_allowed_roles(fact, promo_ids, amplifier_ids)
        if not roles:
            raise ResponsePlanAdapterError("adapter_fact_role_unsupported", fact.id)
        candidates.append(
            CommercialFactCandidate(
                fact_id=fact.id,
                display_text=fact.text_fact,
                explicit_only=fact.kind == "warranty",
                allowed_roles=roles,
                applicability=_fact_applicability(fact),
                allowed_topic_ids=tuple(fact.allowed_topics),
                allowed_service_ids=tuple(fact.allowed_service_ids),
                source_client_id=material_client_id,
                requires_implant_scope=fact.id == "implant_warranty",
            )
        )
    for fact_id in (*promo_ids, *amplifier_ids):
        if fact_id not in bundle_facts:
            raise ResponsePlanAdapterError("adapter_fact_source_missing", fact_id)
    return tuple(candidates), promo_ids, amplifier_ids


def _promo_fact_ids(materials: TargetOfflineResponseMaterials) -> tuple[str, ...]:
    refs = materials.marketing_selection.selected_refs
    return tuple(ref.removeprefix("fact:") for ref in refs if ref.startswith("fact:"))


def _amplifier_fact_ids(materials: TargetOfflineResponseMaterials) -> tuple[str, ...]:
    refs = materials.marketing_selection.amplifier_refs
    return tuple(ref.removeprefix("fact:") for ref in refs if ref.startswith("fact:"))


def _fact_allowed_roles(
    fact: TargetCommercialFact,
    promo_ids: tuple[str, ...],
    amplifier_ids: tuple[str, ...],
) -> tuple[FactRole, ...]:
    if fact.kind == "warranty":
        return ("requested_fact",)
    roles: list[FactRole] = ["requested_fact"]
    if fact.id in promo_ids:
        roles.append("promo")
    if fact.id in amplifier_ids:
        roles.append("automatic_amplifier")
    return tuple(dict.fromkeys(roles))


def _fact_applicability(fact: TargetCommercialFact) -> FactApplicability:
    if fact.allowed_service_ids:
        return "service_scoped"
    if fact.allowed_topics:
        return "topic_scoped"
    return "clinic_wide"


def _build_service_value_candidate(
    materials: TargetOfflineResponseMaterials,
    material_client_id: str,
    *,
    response_scope: ResponseScope,
) -> ServiceValueCandidate | None:
    if response_scope != "service":
        return None
    ref = materials.marketing_selection.service_value_ref
    if ref is None:
        return None
    fact_id = ref.removeprefix("fact:")
    bundle_index = {fact.id: fact for fact in materials.commercial_facts}
    source_fact = bundle_index.get(fact_id)
    if source_fact is None:
        raise ResponsePlanAdapterError("adapter_service_value_source_missing", ref)
    return ServiceValueCandidate(
        fact_id=fact_id,
        display_text=source_fact.text_fact,
        source_client_id=material_client_id,
    )


def _build_textual_cta(
    sources: ResponsePlanAdapterSources,
    client_id: str,
    selected_cta_key: str | None,
) -> TextualCtaCandidate | None:
    if selected_cta_key and sources.textual_cta_authority is None:
        return None
    authority = sources.textual_cta_authority
    if authority is None:
        return None
    if authority.source_client_id != client_id:
        raise ResponsePlanAdapterError("adapter_client_mismatch", ("textual_cta", authority.source_client_id))
    return TextualCtaCandidate(source_client_id=client_id, text=authority.text)


def _build_material_ui_candidates(
    sources: ResponsePlanAdapterSources,
    material_client_id: str,
    bound_package,
    selected_followups: TargetResponseFollowupSelection,
) -> UiPlanCandidates:
    quick_replies = _build_quick_replies(
        material_client_id,
        bound_package,
        selected_followups,
    )
    buttons, widget, video = _explicit_ui_blocks(sources, material_client_id)
    return UiPlanCandidates(
        quick_replies=quick_replies,
        buttons=buttons,
        widget=widget,
        video=video,
    )


def _build_non_material_ui_candidates(
    sources: ResponsePlanAdapterSources,
    client_id: str,
) -> UiPlanCandidates:
    buttons, widget, video = _explicit_ui_blocks(sources, client_id)
    if not buttons and widget is None and video is None:
        return _EMPTY_UI
    return UiPlanCandidates(quick_replies=(), buttons=buttons, widget=widget, video=video)


def _explicit_ui_blocks(
    sources: ResponsePlanAdapterSources,
    client_id: str,
) -> tuple[tuple[UiButtonCandidate, ...], UiWidgetCandidate | None, UiVideoCandidate | None]:
    buttons: list[UiButtonCandidate] = []
    widget: UiWidgetCandidate | None = None
    video: UiVideoCandidate | None = None
    ui = sources.ui_authority
    if ui is None:
        return (), None, None
    if ui.source_client_id != client_id:
        raise ResponsePlanAdapterError("adapter_client_mismatch", ("ui", ui.source_client_id))
    for button in ui.buttons:
        if button.source_client_id != client_id:
            raise ResponsePlanAdapterError("adapter_client_mismatch", ("button", button.source_client_id))
        buttons.append(
            UiButtonCandidate(
                source_client_id=client_id,
                button_id=button.button_id,
                label=button.label,
                action_kind=button.action_kind,
            )
        )
    if ui.widget is not None:
        if ui.widget.source_client_id != client_id:
            raise ResponsePlanAdapterError("adapter_client_mismatch", ("widget", ui.widget.source_client_id))
        widget = UiWidgetCandidate(
            source_client_id=client_id,
            widget_offer_id=ui.widget.widget_offer_id,
        )
    if ui.video is not None:
        if ui.video.source_client_id != client_id:
            raise ResponsePlanAdapterError("adapter_client_mismatch", ("video", ui.video.source_client_id))
        video = UiVideoCandidate(source_client_id=client_id, video_id=ui.video.video_id)
    return tuple(buttons), widget, video


def _build_quick_replies(
    material_client_id: str,
    bound_package,
    selected_followups: TargetResponseFollowupSelection,
) -> tuple[UiQuickReplyCandidate, ...]:
    seen: set[str] = set()
    items: list[UiQuickReplyCandidate] = []
    for followup in _content_followups(selected_followups):
        reply_id = followup.ref
        if reply_id in seen:
            continue
        seen.add(reply_id)
        items.append(
            UiQuickReplyCandidate(
                source_client_id=material_client_id,
                reply_id=reply_id,
                label=followup.label,
            )
        )
    for followup in _price_followups(selected_followups):
        reply_id = followup.ref
        if reply_id in seen:
            continue
        seen.add(reply_id)
        items.append(
            UiQuickReplyCandidate(
                source_client_id=material_client_id,
                reply_id=reply_id,
                label=followup.label,
            )
        )
    for nav in _navigation_followups(bound_package):
        reply_id = nav.ref
        if reply_id in seen:
            continue
        seen.add(reply_id)
        items.append(
            UiQuickReplyCandidate(
                source_client_id=material_client_id,
                reply_id=reply_id,
                label=nav.label,
            )
        )
    return tuple(items)


def _content_followups(selection: TargetResponseFollowupSelection) -> tuple[TargetContentFollowup, ...]:
    return selection.content if selection.source in {None, "content"} else ()


def _price_followups(selection: TargetResponseFollowupSelection) -> tuple[TargetPriceFollowup, ...]:
    return selection.price if selection.source in {None, "price"} else ()


def _navigation_followups(bound_package) -> tuple[TargetNavigationFollowup, ...]:
    return getattr(bound_package.package, "navigation_followups", ())


def _format_amount(amount: int) -> str:
    return f"{amount:,}".replace(",", " ")


def _currency_symbol(currency: str) -> str:
    return _CURRENCY_SYMBOLS.get(currency, currency)


def build_pre_composer_plan_from_materialization(
    selection,
    adapted,
    sources,
    *,
    as_of,
):
    """Post-Composer adapter entrypoint: selection + authorities → PreComposerPlan."""

    from datetime import date as date_type

    from core.response_plan_materialization import materialize_pre_composer_payload

    if not isinstance(as_of, date_type):
        raise ResponsePlanAdapterError("adapter_materialization_as_of_invalid", as_of)
    return materialize_pre_composer_payload(selection, adapted, sources, as_of=as_of).plan
