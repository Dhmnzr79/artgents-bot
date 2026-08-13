"""Build strict facts and sales context for the sales-fast one-call path."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path

from contracts.doctor_schema import TargetDoctorCatalog
from contracts.effective_scope import EffectiveScope, ScopeAxisProvenance
from contracts.exact_sales_resolution import ExactSalesFieldAuthority, ExactSalesResolution
from contracts.response_schema import ResponseSchemaBundle, TargetOffer, TargetStrategyMatch
from contracts.sales_one_plus import SalesOnePlusStrictFact
from contracts.sales_one_plus_semantic import SalesOnePlusSemanticFrame, SemanticFieldProvenance
from contracts.service_consultation import ServiceConsultationValue
from contracts.ui_scope_action import UiScopeAction
from contracts.ui_stage_action import UiStageAction
from contracts.target_turn_frame_dispatch import TargetTurnFrameBoundTerminalResponse
from contracts.target_turn_frame_policy_envelope import TargetTurnFramePolicyEnvelope
from contracts.turn_frame import TurnFrame
from core.target_policy_bound_verified_response_pipeline import _assemble_bound_package
from core.target_presentation_turn_projection import (
    marketing_scenarios_from_turn_frame,
    resolve_bound_marketing_flags,
    resolve_target_semantic_context,
)
from core.target_response_policy import build_target_response_spec
from core.target_spec_offline_response_package import TargetSpecBoundOfflineResponsePackage
from core.target_turn_frame_dispatch import dispatch_target_turn_frame_response


def _rubles(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " ₽"


def _offer_price_text(offer: TargetOffer) -> str:
    price = offer.price
    if price.mode == "fixed" and price.amount is not None:
        value = _rubles(int(price.amount))
    elif price.mode == "from" and price.min_amount is not None:
        value = "от " + _rubles(int(price.min_amount))
    elif price.mode == "range" and price.min_amount is not None and price.max_amount is not None:
        value = f"{_rubles(int(price.min_amount))}–{_rubles(int(price.max_amount))}"
    elif price.mode == "no_public_price":
        return str(price.approved_text).strip()
    else:
        return ""
    package_label = str(offer.package.label or "").strip()
    if package_label:
        return f"{value} {package_label}"
    return value


def _authority_for_provenance(provenance: SemanticFieldProvenance) -> ExactSalesFieldAuthority:
    if provenance == "governed_ui":
        return ExactSalesFieldAuthority(authority="governed_ui", provenance="governed_ui")
    if provenance == "envelope":
        return ExactSalesFieldAuthority(authority="unknown", provenance="envelope")
    return ExactSalesFieldAuthority(authority="unknown", provenance="null")


def exact_sales_resolution_from_semantic_frame(
    semantic: SalesOnePlusSemanticFrame,
) -> ExactSalesResolution:
    """Post-envelope commerce resolution — envelope/governed UI only, no session/catalog fill."""

    aspect = None
    if semantic.commercial_intent == "price":
        aspect = "price"
    elif semantic.commercial_intent == "payment":
        aspect = "payment"
    elif semantic.commercial_intent == "included":
        aspect = "included"
    aspect_authority = ExactSalesFieldAuthority(authority="unknown", provenance="envelope")
    return ExactSalesResolution(
        service_id=semantic.service_id,
        aspect=aspect,
        extent=semantic.extent,  # type: ignore[arg-type]
        jaw=semantic.jaw,  # type: ignore[arg-type]
        stage=semantic.stage,  # type: ignore[arg-type]
        service_id_authority=_authority_for_provenance(semantic.service_id_provenance),
        aspect_authority=aspect_authority,
        extent_authority=_authority_for_provenance(semantic.extent_provenance),
        jaw_authority=_authority_for_provenance(semantic.jaw_provenance),
        stage_authority=_authority_for_provenance(semantic.stage_provenance),
    )


def effective_scope_from_semantic_frame(
    semantic: SalesOnePlusSemanticFrame,
    *,
    current_ui_action: UiScopeAction | None,
    current_ui_stage_action: UiStageAction | None,
) -> EffectiveScope:
    """Authoritative scope for post-envelope rebuild without stale session service focus."""

    if current_ui_action is not None or current_ui_stage_action is not None:
        from core.target_effective_scope import resolve_effective_scope

        return resolve_effective_scope(
            current_ui_action=current_ui_action,
            current_ui_stage_action=current_ui_stage_action,
            session_facts=None,
            current_topic=None,
            session_turn_count=0,
            projected_turn_scope=None,
        )

    envelope_provenance = ScopeAxisProvenance(source="unknown", provenance="envelope")
    return EffectiveScope(
        extent=semantic.extent or "unknown",  # type: ignore[arg-type]
        jaw=semantic.jaw or "unknown",  # type: ignore[arg-type]
        stage=semantic.stage,
        topic=None,
        source="unknown",
        provenance="semantic_authority",
        extent_axis=envelope_provenance if semantic.extent is not None else ScopeAxisProvenance(),
        jaw_axis=envelope_provenance if semantic.jaw is not None else ScopeAxisProvenance(),
        stage_axis=envelope_provenance if semantic.stage is not None else ScopeAxisProvenance(),
    )


def build_pre_flash_prompt_hints(
    *,
    resolution: ExactSalesResolution,
    catalog_service_hint: str | None,
    session_service_hint: str | None = None,
) -> tuple[tuple[SalesOnePlusStrictFact, ...], dict[str, object]]:
    """Neutral pre-model hints only — no exact commercial amounts or authoritative service_id."""

    hints: dict[str, object] = {}
    if resolution.aspect is not None:
        hints["aspect_hint"] = resolution.aspect
    if catalog_service_hint:
        hints["catalog_service_hint"] = catalog_service_hint
    if session_service_hint:
        hints["session_service_hint"] = session_service_hint
    if resolution.service_id_authority.authority == "governed_ui" and resolution.service_id:
        hints["governed_ui_service_id"] = resolution.service_id
    if resolution.extent_authority.authority == "governed_ui" and resolution.extent:
        hints["governed_ui_extent"] = resolution.extent
    if resolution.jaw_authority.authority == "governed_ui" and resolution.jaw:
        hints["governed_ui_jaw"] = resolution.jaw
    if resolution.stage_authority.authority == "governed_ui" and resolution.stage:
        hints["governed_ui_stage"] = resolution.stage
    if resolution.jaw == "both" or resolution.extent == "few_teeth":
        hints["ambiguous_scope_hint"] = True
    return (), hints


def _needs_admin_quote(
    resolution: ExactSalesResolution,
    *,
    offers: Sequence[TargetOffer],
) -> bool:
    if resolution.jaw == "both":
        return True
    if resolution.extent == "few_teeth":
        return True
    if resolution.aspect in {"price", "payment", "included"} and not offers:
        return True
    return False


def assemble_sales_fast_bound_package(
    *,
    turn_frame: TurnFrame,
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    external_index: object,
    consultation_values: Sequence[ServiceConsultationValue],
    strategy_context: TargetStrategyMatch,
    effective_scope: EffectiveScope,
    allowed_topics: tuple[str, ...],
    today: date,
    md_root: Path,
    client_id: str,
    shown_fact_ids: Sequence[str] = (),
    shown_amplifier_refs: Sequence[str] = (),
    shown_consultation_value_refs: Sequence[str] = (),
) -> TargetSpecBoundOfflineResponsePackage | TargetTurnFrameBoundTerminalResponse:
    envelope = TargetTurnFramePolicyEnvelope(
        boundary_decision="none",
        tone_key="commercial_warm",
        allowed_topics=allowed_topics,
        forbidden_topics=("diagnosis", "personal_eligibility"),
        allow_marketing_facts=True,
        allow_consultation_close=True,
        allow_cta=True,
        min_topic_confidence=0.0,
        min_service_confidence=0.0,
        min_intent_confidence=0.0,
    )
    dispatch = dispatch_target_turn_frame_response(
        turn_frame,
        envelope,
        effective_scope=effective_scope,
    )
    if dispatch.kind == "terminal":
        return TargetTurnFrameBoundTerminalResponse(kind="terminal", dispatch=dispatch)
    bound_spec = build_target_response_spec(dispatch.policy_request)
    semantic_context = resolve_target_semantic_context(turn_frame, bound_spec)
    scenario_intent = marketing_scenarios_from_turn_frame(turn_frame)
    include_initial_block, resolved_scenarios, brand_term = resolve_bound_marketing_flags(
        turn_frame,
        bound_spec,
        boundary_allows_marketing=True,
        brand_term=None,
        marketing_scenarios=scenario_intent,
    )
    return _assemble_bound_package(
        dispatch.policy_request,
        bundle,
        doctor_catalog,  # type: ignore[arg-type]
        external_index,  # type: ignore[arg-type]
        consultation_values,  # type: ignore[arg-type]
        brand_term=brand_term,
        strategy_context=strategy_context,
        semantic_context=semantic_context,
        today=today,
        md_root=md_root,
        include_initial_block=False,
        include_consultation_close=True,
        include_cta=True,
        marketing_scenarios=(),
        shown_fact_ids=shown_fact_ids,
        shown_amplifier_refs=shown_amplifier_refs,
        shown_consultation_value_refs=shown_consultation_value_refs,
        turn_topic=turn_frame.topic,
        effective_scope=effective_scope,
        client_id=client_id,
    )


def strict_facts_and_sales_context(
    *,
    bound_package: TargetSpecBoundOfflineResponsePackage,
    resolution: ExactSalesResolution,
    bundle: ResponseSchemaBundle,
    strategy_context: TargetStrategyMatch,
) -> tuple[tuple[SalesOnePlusStrictFact, ...], dict[str, object]]:
    materials = bound_package.package.materials
    strict_facts: list[SalesOnePlusStrictFact] = []
    for offer in materials.offers:
        price_text = _offer_price_text(offer)
        if not price_text:
            continue
        service = bundle.services.get(offer.service_id)
        service_name = service.name if service is not None else offer.service_id
        strict_facts.append(
            SalesOnePlusStrictFact(
                id=f"offer:{offer.offer_id}",
                kind="offer",
                text=f"Стоимость {service_name} — {price_text}.",
                must_preserve_exact=True,
            )
        )
        package_bits = str(offer.package.label or "").strip()
        if package_bits:
            strict_facts.append(
                SalesOnePlusStrictFact(
                    id=f"package:{offer.offer_id}",
                    kind="package",
                    text=package_bits,
                    must_preserve_exact=True,
                )
            )
    for fact in materials.commercial_facts:
        strict_facts.append(
            SalesOnePlusStrictFact(
                id=f"fact:{fact.id}",
                kind=str(fact.kind),
                text=str(fact.text_fact).strip(),
                must_preserve_exact=fact.render_mode == "strict",
            )
        )
    offers = materials.offers
    sales_context: dict[str, object] = {
        "topic": turn_frame_topic_hint(bound_package),
        "service_id": resolution.service_id,
    }
    from core.sales_fast_authoritative_commerce import build_authoritative_commerce_result

    explicit_offer_id = None
    if materials.selected_brand_id:
        brand = str(materials.selected_brand_id).strip().lower()
        for offer in offers:
            if str(offer.brand_id or "").strip().lower() == brand:
                explicit_offer_id = offer.offer_id
                break
    commerce = build_authoritative_commerce_result(
        bound_package=bound_package,
        resolution=resolution,
        bundle=bundle,
        strategy_context=strategy_context,
    )
    selected_exact = commerce.selected_exact_offer
    if selected_exact is not None and not commerce.needs_consultation_quote:
        sales_context["offer_id"] = selected_exact.offer_id
        if selected_exact.price.mode == "fixed" and selected_exact.price.amount is not None:
            sales_context["amount"] = int(selected_exact.price.amount)
            sales_context["currency"] = "RUB"
    elif commerce.presentation_mode in {"overview", "entry_from"}:
        sales_context["generic_price_mode"] = commerce.presentation_mode
        if commerce.entry_price_amount is not None:
            sales_context["entry_amount"] = int(commerce.entry_price_amount)
    if _needs_admin_quote(resolution, offers=offers):
        sales_context["needs_admin_quote"] = True
        sales_context["offer_id"] = None
        sales_context.pop("amount", None)
    return tuple(strict_facts), sales_context


def turn_frame_topic_hint(bound_package: TargetSpecBoundOfflineResponsePackage) -> str | None:
    topic = bound_package.spec.scope_price_topic or bound_package.spec.service_id
    return str(topic) if topic else None
