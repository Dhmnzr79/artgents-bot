"""Assemble price answers from PriceBook v2 (deterministic blocks + fact_refs)."""
from __future__ import annotations

from typing import Any, Literal

from contracts.price_offer import PriceOffer
from contracts.pricebook import (
    AnswerBlockKind,
    PriceAnswerPlan,
    PricebookServiceEntry,
    PricingFact,
    PriceScenario,
)
from core.price_offers import (
    format_rub,
    render_offer_includes_only,
    render_offer_stages_only,
    render_price_offers_append,
    variants_are_brand_based,
)
from core.marketing_policy import filter_promo_facts
from core.pricebook_loader import load_pricebook_service, resolve_fact_refs

AspectKind = Literal["includes", "excludes", "stages", "overview"]


def _format_simple_price(entry: PricebookServiceEntry) -> str | None:
    price = entry.price
    if not price:
        return None
    prefix = "от " if price.price_type == "from" else ""
    line = f"{prefix}**{format_rub(price.value)}**"
    if price.note:
        line += f". {price.note.strip()}"
    return line


def _render_strict_facts(facts: list[PricingFact]) -> str | None:
    strict = [f.text_fact.strip() for f in facts if f.render_mode == "strict" and f.text_fact.strip()]
    if not strict:
        return None
    return "\n".join(f"- {t}" for t in strict)


def _render_natural_facts(facts: list[PricingFact]) -> str | None:
    """Natural facts as prose (no bullet); LLM paraphrase deferred to stage 5."""
    natural = [f.text_fact.strip() for f in facts if f.render_mode == "natural" and f.text_fact.strip()]
    if not natural:
        return None
    return "\n\n".join(natural)


def _complex_intro(entry: PricebookServiceEntry) -> str:
    custom = str(entry.intro_text or "").strip()
    if custom:
        return custom
    name = entry.display_name.strip()
    if entry.service_id in {"all_on_4", "all_on_6"} or entry.default_unit == "jaw":
        return (
            f"{name} считают за одну челюсть: в пакет входит восстановление зубного ряда "
            f"на {'4' if entry.service_id == 'all_on_4' else '6' if entry.service_id == 'all_on_6' else 'нескольких'} имплантах."
        )
    return (
        f"Классическая имплантация одного зуба «под ключ» — цена зависит от системы имплантов. "
        f"Ниже ориентиры по брендам."
        if entry.service_id == "classic"
        else f"Стоимость «{name}» зависит от выбранной системы имплантов."
    )


def _template_intro(
    entry: PricebookServiceEntry,
    *,
    scenario: PriceScenario,
    aspect: AspectKind | None = None,
) -> str | None:
    if scenario == "overview" or aspect:
        return None
    if entry.price_model == "simple":
        return f"По услуге «{entry.display_name}»:"
    return _complex_intro(entry)


def _template_closer(entry: PricebookServiceEntry, *, aspect: AspectKind | None = None) -> str | None:
    if aspect:
        return None
    _ = entry
    # Price answers should not add a consult closer by default; configured facts/CTA handle next steps.
    return None


def plan_for_service(
    entry: PricebookServiceEntry,
    *,
    scenario: PriceScenario | None = None,
    aspect: AspectKind | None = None,
) -> PriceAnswerPlan:
    if aspect in ("stages", "includes", "excludes"):
        blocks: list[AnswerBlockKind] = ["stages"] if aspect == "stages" else ["includes"]
        return PriceAnswerPlan(
            scenario="aspect_followup",
            service_id=entry.service_id,
            unit=entry.default_unit,
            aspect=aspect if aspect != "excludes" else "excludes",
            blocks=blocks,
            fact_refs=[],
            followups=list(entry.followups),
        )
    if scenario:
        sc = scenario
    elif entry.price_model == "simple":
        sc = "simple_with_followup" if entry.followups else "simple"
    else:
        sc = "complex"
    blocks = ["intro"]
    if entry.price_model == "simple":
        blocks.extend(["price_line", "fact_refs", "closer", "followups"])
    else:
        blocks.extend(["price_table", "fact_refs", "closer", "followups"])
    return PriceAnswerPlan(
        scenario=sc,
        service_id=entry.service_id,
        unit=entry.default_unit,
        blocks=blocks,
        fact_refs=list(entry.fact_refs),
        followups=list(entry.followups),
        llm_intro=False,
        llm_closer=False,
    )


def assemble_price_answer(
    *,
    client_id: str | None,
    service_id: str,
    offers: list[PriceOffer],
    entry: PricebookServiceEntry | None = None,
    plan: PriceAnswerPlan | None = None,
    aspect: AspectKind | None = None,
) -> tuple[str | None, dict[str, Any]]:
    """Build price answer from PriceBook entry + filtered offers."""
    entry = entry or load_pricebook_service(client_id, service_id)
    if not entry:
        return None, {}

    plan = plan or plan_for_service(entry, aspect=aspect)
    parts: list[str] = []
    meta: dict[str, Any] = {
        "pricebook_applied": True,
        "pricebook_service_id": service_id,
        "pricebook_scenario": plan.scenario,
    }
    if aspect:
        meta["pricebook_aspect"] = aspect

    if plan.scenario == "aspect_followup" and offers:
        if aspect == "stages":
            block = render_offer_stages_only(offers)
            if block:
                parts.append(block)
        elif aspect in ("includes", "excludes"):
            block = render_offer_includes_only(offers)
            if block:
                parts.append(block)
        if not parts:
            return None, {}
        meta.update(
            {
                "price_offers_applied": True,
                "price_offer_service_id": service_id,
                "price_offer_ids": [o.offer_id for o in offers],
            }
        )
        return "\n\n".join(parts), meta

    intro = _template_intro(entry, scenario=plan.scenario, aspect=aspect)
    if intro and "intro" in plan.blocks:
        parts.append(intro)

    if "price_line" in plan.blocks and entry.price_model == "simple":
        price_line = _format_simple_price(entry)
        if price_line:
            parts.append(price_line)
            meta["pricebook_simple_value"] = entry.price.value if entry.price else None

    if "price_table" in plan.blocks and offers:
        compact = entry.price_model == "complex"
        brand_based = variants_are_brand_based(entry)
        table_heading = (
            ("**По брендам:**" if brand_based else "**Варианты:**") if compact else None
        )
        append = render_price_offers_append(
            offers,
            compact=compact,
            heading=table_heading,
            brand_based=brand_based,
        )
        if append:
            parts.append(append)

    facts = resolve_fact_refs(client_id, list(entry.fact_refs), usable_in="price_answer")
    facts, promo_decisions = filter_promo_facts(
        client_id=client_id,
        facts=facts,
        service_id=service_id,
        route="price_lookup",
        aspect=aspect or "overview",
    )
    if promo_decisions:
        applied = [d.fact_id for d in promo_decisions if d.allowed]
        suppressed = {d.fact_id: d.reason for d in promo_decisions if not d.allowed}
        if applied:
            meta["marketing_promos_applied"] = applied
        if suppressed:
            meta["marketing_promos_suppressed"] = suppressed
    if "fact_refs" in plan.blocks and facts:
        strict_block = _render_strict_facts(facts)
        natural_block = _render_natural_facts(facts)
        fact_parts: list[str] = []
        if strict_block:
            fact_parts.append(strict_block)
            meta["pricebook_strict_facts"] = [f.id for f in facts if f.render_mode == "strict"]
        if natural_block:
            fact_parts.append(natural_block)
            meta["pricebook_natural_facts"] = [f.id for f in facts if f.render_mode == "natural"]
        if fact_parts:
            parts.append("\n\n".join(fact_parts))

    closer = _template_closer(entry, aspect=aspect)
    if closer and "closer" in plan.blocks:
        parts.append(closer)

    if not parts:
        return None, {}

    answer = "\n\n".join(p for p in parts if p and p.strip())

    if offers:
        meta.update(
            {
                "price_offers_applied": True,
                "price_offer_service_id": service_id,
                "price_offer_ids": [o.offer_id for o in offers],
            }
        )
    return answer, meta


def hide_navigated_quick_replies(
    quick: list[dict[str, str]],
    *,
    active_ref: str | None = None,
    exclude_refs: set[str] | None = None,
) -> list[dict[str, str]]:
    """Drop buttons for the ref just opened and for refs already used in session."""
    active = (active_ref or "").strip().lower()
    excluded = {str(r).strip().lower() for r in (exclude_refs or set()) if str(r).strip()}
    out: list[dict[str, str]] = []
    for item in quick:
        ref = str(item.get("ref") or "").strip()
        if not ref:
            continue
        rl = ref.lower()
        if active and rl == active:
            continue
        if rl in excluded:
            continue
        out.append(item)
    return out


def fact_followups_to_quick_replies(
    client_id: str | None,
    fact_refs: list[str],
    *,
    usable_in: str = "price_answer",
    service_id: str | None = None,
    route: str | None = "price_lookup",
    aspect: str | None = None,
) -> list[dict[str, str]]:
    """Buttons from facts.json (detail_ref + followup_label)."""
    facts = resolve_fact_refs(client_id, fact_refs, usable_in=usable_in)
    facts, _ = filter_promo_facts(
        client_id=client_id,
        facts=facts,
        service_id=service_id,
        route=route,
        aspect=aspect or "overview",
    )
    out: list[dict[str, str]] = []
    for fact in facts:
        label = str(fact.followup_label or "").strip()
        ref = str(fact.detail_ref or "").strip()
        if label and ref:
            out.append({"label": label, "ref": ref})
    return out


def merge_price_quick_replies(
    entry: PricebookServiceEntry,
    client_id: str | None,
    *,
    active_aspect: str | None = None,
    active_ref: str | None = None,
    exclude_refs: set[str] | None = None,
) -> list[dict[str, str]]:
    """Service followups + fact-derived buttons; dedupe by ref."""
    seen: set[str] = set()
    merged: list[dict[str, str]] = []
    for item in (
        followups_to_quick_replies(entry, active_aspect=active_aspect)
        + fact_followups_to_quick_replies(
            client_id,
            list(entry.fact_refs),
            service_id=entry.service_id,
            route="price_lookup",
            aspect=active_aspect or "overview",
        )
    ):
        ref = str(item.get("ref") or "").strip()
        if not ref or ref in seen:
            continue
        seen.add(ref)
        merged.append(item)
    return hide_navigated_quick_replies(
        merged,
        active_ref=active_ref,
        exclude_refs=exclude_refs,
    )


def followups_to_quick_replies(
    entry: PricebookServiceEntry,
    *,
    active_aspect: str | None = None,
) -> list[dict[str, str]]:
    """Map pricebook followups to widget quick_replies.

    When ``active_aspect`` is set (S7 detail view), skip the button for the aspect
    already shown — e.g. no «Оплата по этапам» on the stages screen.
    """
    active = (active_aspect or "").strip().lower()
    out: list[dict[str, str]] = []
    for fu in entry.followups:
        label = str(fu.label or "").strip()
        if not label:
            continue
        if fu.action == "price_aspect" and fu.aspect:
            aspect = str(fu.aspect).strip().lower()
            if active and aspect == active:
                continue
            ref = str(fu.detail_ref or "").strip() or f"price:{entry.service_id}/{fu.aspect}"
            out.append({"label": label, "ref": ref})
        elif fu.action == "price_service" and fu.service_id:
            out.append({"label": label, "ref": f"price:{fu.service_id}"})
        elif fu.action == "md_ref" and fu.ref:
            out.append({"label": label, "ref": fu.ref})
        elif fu.action == "price_group" and fu.group_id:
            out.append({"label": label, "ref": f"price:{fu.group_id}/overview"})
    return out
