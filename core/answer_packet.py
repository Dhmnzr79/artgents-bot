"""Deterministic answer packet assembler (composer roadmap phase 2)."""

from __future__ import annotations

from typing import Any

from contracts.answer_packet import AnswerPacketSnapshot, PacketCard, PromoDecisionRecord
from contracts.answer_plan import AnswerPlan, AspectKind, PlanAppendKind
from contracts.pricebook import PricingFact
from core.answer_planner import payment_terms_ref, warranty_terms_ref
from core.marketing_loader import load_marketing_config
from core.marketing_policy import decide_promo_fact
from core.pricebook_loader import load_pricebook_service, resolve_fact_refs

_TOPIC_CONTENT_REF: dict[str, dict[AspectKind, str]] = {
    "implantation": {
        "pain": "implantation__faq__pain.md#korotko",
        "duration": "implantation__faq__duration.md#korotko",
    },
}


def _service_content_ref(
    aspect: AspectKind,
    *,
    topic: str | None,
    service_id: str | None,
    primary_chunk_ref: str | None,
    source_ref: str | None,
) -> str | None:
    if primary_chunk_ref and aspect in {"overview", "comparison"}:
        return primary_chunk_ref
    if source_ref and aspect == "overview":
        return source_ref
    topic_key = (topic or "implantation").strip().lower()
    topic_map = _TOPIC_CONTENT_REF.get(topic_key, {})
    if aspect in topic_map:
        return topic_map[aspect]
    if service_id and aspect == "overview":
        return f"{topic_key}__service__{service_id}.md#korotko"
    return None


def _promo_facts_for_service(
    client_id: str | None,
    service_id: str | None,
) -> list[PricingFact]:
    if not service_id:
        return []
    entry = load_pricebook_service(client_id, service_id)
    if not entry:
        return []
    facts = resolve_fact_refs(client_id, list(entry.fact_refs or []))
    return [f for f in facts if f.kind == "promo"]


def _promo_gate_aspect(plan: AnswerPlan, *, client_id: str | None) -> str:
    """Aspect passed to decide_promo_fact (marketing gate before LLM)."""
    blocked = set(load_marketing_config(client_id).blocked_aspects_for_promo or ())
    for aspect in plan.aspects:
        if aspect in blocked:
            return aspect
    primary = plan.primary_aspect
    if primary == "pain":
        return "pain"
    if primary in (None, "overview", "price", "payment") or "price" in plan.aspects:
        return "overview"
    return str(primary or "overview")


def _promo_cards(
    *,
    client_id: str | None,
    service_id: str | None,
    route: str | None,
    aspect: str | None,
) -> tuple[list[PacketCard], list[PromoDecisionRecord]]:
    cards: list[PacketCard] = []
    decisions: list[PromoDecisionRecord] = []
    aspect_eff = str(aspect or "overview").strip() or "overview"
    for fact in _promo_facts_for_service(client_id, service_id):
        decision = decide_promo_fact(
            client_id=client_id,
            fact=fact,
            service_id=service_id,
            route=route,
            aspect=aspect_eff,
        )
        decisions.append(
            PromoDecisionRecord(
                fact_id=fact.id,
                allowed=decision.allowed,
                reason=decision.reason,
                promo_key=decision.promo_key,
                aspect=aspect_eff,
            )
        )
        if decision.allowed:
            cards.append(
                PacketCard(
                    aspect=aspect_eff,  # type: ignore[arg-type]
                    kind="promo",
                    fact_id=fact.id,
                    promo_decision=decision.reason,
                    included_reason="promo_allowed",
                )
            )
    return cards, decisions


def _cta_card(*, client_id: str | None, service_id: str | None) -> PacketCard | None:
    if not service_id:
        return None
    svc_cfg = load_marketing_config(client_id).service(service_id)
    cta_key = str(svc_cfg.primary_cta_key or "").strip() if svc_cfg else ""
    if not cta_key:
        return None
    return PacketCard(
        kind="cta",
        cta_key=cta_key,
        included_reason="service_marketing",
    )


def _buttons_card(*, client_id: str | None, service_id: str | None) -> PacketCard | None:
    if not service_id:
        return None
    entry = load_pricebook_service(client_id, service_id)
    if not entry or not entry.followups:
        return None
    refs: list[str] = []
    for fu in entry.followups:
        ref = str(fu.ref or "").strip()
        if ref:
            refs.append(ref)
            continue
        aspect = str(fu.aspect or "").strip()
        if aspect:
            refs.append(f"price_aspect:{aspect}")
    if not refs:
        return None
    return PacketCard(
        kind="buttons",
        button_refs=refs,
        included_reason="pricebook_followups",
    )


def _append_suppressed(
    cards: list[PacketCard],
    *,
    apply_meta: dict[str, Any] | None,
    suppressed_append: list[PlanAppendKind],
) -> None:
    if not isinstance(apply_meta, dict):
        return
    applied = {str(x).strip() for x in (apply_meta.get("applied") or []) if str(x).strip()}
    suppressed = {str(x).strip() for x in (apply_meta.get("suppressed") or []) if str(x).strip()}
    for card in cards:
        append_key = _card_append_kind(card)
        if append_key and append_key in applied:
            card.included_reason = "apply_applied"
        if append_key and append_key in suppressed:
            card.suppressed_reason = "apply_suppressed"


def _card_append_kind(card: PacketCard) -> str | None:
    if card.kind == "price":
        return "price_offer"
    if card.kind == "payment":
        return "payment_terms"
    if card.kind == "warranty":
        return "warranty_terms"
    return None


def assemble_answer_packet(
    plan: AnswerPlan,
    *,
    client_id: str | None,
    route: str | None = None,
    service_id: str | None = None,
    source_ref: str | None = None,
    primary_chunk_ref: str | None = None,
    apply_meta: dict[str, Any] | None = None,
) -> AnswerPacketSnapshot:
    """Build allowed packet cards from plan + marketing/pricebook rules (no LLM)."""
    svc = (service_id or plan.service_id or "").strip() or None
    cards: list[PacketCard] = []
    handled_aspects: set[AspectKind] = set()

    for aspect in plan.aspects:
        if aspect == "price" and svc:
            cards.append(
                PacketCard(
                    aspect="price",
                    kind="price",
                    fact_id=svc,
                    included_reason="plan_append:price_offer"
                    if "price_offer" in plan.append
                    else "aspect_price",
                )
            )
            handled_aspects.add("price")
            continue
        if aspect == "payment":
            cards.append(
                PacketCard(
                    aspect="payment",
                    kind="payment",
                    source_ref=payment_terms_ref(),
                    included_reason="plan_append:payment_terms"
                    if "payment_terms" in plan.append
                    else "aspect_payment",
                )
            )
            handled_aspects.add("payment")
            continue
        if aspect == "warranty":
            cards.append(
                PacketCard(
                    aspect="warranty",
                    kind="warranty",
                    source_ref=warranty_terms_ref(),
                    included_reason="plan_append:warranty_terms"
                    if "warranty_terms" in plan.append
                    else "aspect_warranty",
                )
            )
            handled_aspects.add("warranty")
            continue
        if aspect in handled_aspects:
            continue
        ref = _service_content_ref(
            aspect,
            topic=plan.topic,
            service_id=svc,
            primary_chunk_ref=primary_chunk_ref,
            source_ref=source_ref,
        )
        cards.append(
            PacketCard(
                aspect=aspect,
                kind="content",
                source_ref=ref,
                included_reason="aspect_detected",
            )
        )
        handled_aspects.add(aspect)

    promo_aspect = _promo_gate_aspect(plan, client_id=client_id)
    promo_cards, promo_decisions = _promo_cards(
        client_id=client_id,
        service_id=svc,
        route=route,
        aspect=promo_aspect,
    )
    cards.extend(promo_cards)

    cta = _cta_card(client_id=client_id, service_id=svc)
    if cta is not None:
        cards.append(cta)
    buttons = _buttons_card(client_id=client_id, service_id=svc)
    if buttons is not None:
        cards.append(buttons)

    suppressed = list(plan.suppressed_append)
    if isinstance(apply_meta, dict):
        for append_kind in apply_meta.get("suppressed") or []:
            ak = str(append_kind).strip()
            if ak and ak not in suppressed:
                suppressed.append(ak)  # type: ignore[arg-type]

    _append_suppressed(cards, apply_meta=apply_meta, suppressed_append=suppressed)

    stage = "assembled" if apply_meta else "assembled"
    return AnswerPacketSnapshot(
        cards=cards,
        service_id=svc,
        topic=plan.topic,
        primary_aspect=plan.primary_aspect,
        plan_reason=plan.plan_reason,
        snapshot_stage=stage,
        suppressed_append=suppressed,
        promo_decisions=promo_decisions,
    )
