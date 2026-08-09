"""Build strict facts and sales context for the sales-fast one-call path."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from pathlib import Path

from contracts.doctor_schema import TargetDoctorCatalog
from contracts.effective_scope import EffectiveScope
from contracts.exact_sales_resolution import ExactSalesResolution
from contracts.response_schema import ResponseSchemaBundle, TargetOffer, TargetStrategyMatch
from contracts.sales_one_plus import SalesOnePlusStrictFact
from contracts.service_consultation import ServiceConsultationValue
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
        include_initial_block=include_initial_block,
        include_consultation_close=True,
        include_cta=True,
        marketing_scenarios=resolved_scenarios,
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
    if offers:
        primary = offers[0]
        sales_context["offer_id"] = primary.offer_id
        if primary.price.mode == "fixed" and primary.price.amount is not None:
            sales_context["amount"] = int(primary.price.amount)
            sales_context["currency"] = "RUB"
    if _needs_admin_quote(resolution, offers=offers):
        sales_context["needs_admin_quote"] = True
        sales_context["offer_id"] = None
        sales_context.pop("amount", None)
    return tuple(strict_facts), sales_context


def turn_frame_topic_hint(bound_package: TargetSpecBoundOfflineResponsePackage) -> str | None:
    topic = bound_package.spec.scope_price_topic or bound_package.spec.service_id
    return str(topic) if topic else None
