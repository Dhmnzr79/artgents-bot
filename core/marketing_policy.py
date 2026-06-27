"""Deterministic gates for marketing ingredients selected by runtime code."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from contracts.pricebook import PricingFact
from core.marketing_loader import MarketingPromo, load_marketing_config


@dataclass(frozen=True)
class PromoFactDecision:
    fact_id: str
    allowed: bool
    reason: str
    promo_key: str | None = None


def _date_active(active_until: str | None, *, today: date | None = None) -> bool:
    until = str(active_until or "").strip()
    if not until:
        return True
    try:
        end = datetime.strptime(until[:10], "%Y-%m-%d").date()
    except ValueError:
        return True
    return (today or date.today()) <= end


def _matches_any_or_empty(allowed: tuple[str, ...], value: str | None) -> bool:
    if not allowed:
        return True
    needle = str(value or "").strip()
    return needle in allowed


def _promo_rule_for_fact(client_id: str | None, fact: PricingFact) -> tuple[str, MarketingPromo] | None:
    cfg = load_marketing_config(client_id)
    for key, promo in (cfg.promos or {}).items():
        if str(promo.fact_ref or "").strip() == fact.id:
            return key, promo
    direct = (cfg.promos or {}).get(fact.id)
    if direct is not None:
        return fact.id, direct
    return None


def decide_promo_fact(
    *,
    client_id: str | None,
    fact: PricingFact,
    service_id: str | None,
    route: str | None,
    aspect: str | None = None,
    today: date | None = None,
) -> PromoFactDecision:
    if fact.kind != "promo":
        return PromoFactDecision(fact_id=fact.id, allowed=True, reason="not_promo")

    match = _promo_rule_for_fact(client_id, fact)
    if match is None:
        return PromoFactDecision(fact_id=fact.id, allowed=False, reason="promo_not_configured")
    promo_key, promo = match
    if not promo.active:
        return PromoFactDecision(fact_id=fact.id, allowed=False, reason="promo_inactive", promo_key=promo_key)
    if not _date_active(promo.active_until, today=today):
        return PromoFactDecision(fact_id=fact.id, allowed=False, reason="promo_expired", promo_key=promo_key)
    if not _date_active(fact.active_until, today=today):
        return PromoFactDecision(fact_id=fact.id, allowed=False, reason="fact_expired", promo_key=promo_key)
    if not _matches_any_or_empty(promo.allowed_service_ids, service_id):
        return PromoFactDecision(fact_id=fact.id, allowed=False, reason="service_not_allowed", promo_key=promo_key)
    if not _matches_any_or_empty(promo.allowed_routes, route):
        return PromoFactDecision(fact_id=fact.id, allowed=False, reason="route_not_allowed", promo_key=promo_key)

    aspect_eff = str(aspect or "overview").strip()
    blocked = set(load_marketing_config(client_id).blocked_aspects_for_promo or ()) | set(promo.blocked_aspects)
    if aspect_eff and aspect_eff in blocked:
        return PromoFactDecision(fact_id=fact.id, allowed=False, reason="aspect_blocked", promo_key=promo_key)
    if promo.allowed_aspects and aspect_eff not in promo.allowed_aspects:
        return PromoFactDecision(fact_id=fact.id, allowed=False, reason="aspect_not_allowed", promo_key=promo_key)
    return PromoFactDecision(fact_id=fact.id, allowed=True, reason="allowed", promo_key=promo_key)


def filter_promo_facts(
    *,
    client_id: str | None,
    facts: list[PricingFact],
    service_id: str | None,
    route: str | None,
    aspect: str | None = None,
    today: date | None = None,
) -> tuple[list[PricingFact], list[PromoFactDecision]]:
    kept: list[PricingFact] = []
    decisions: list[PromoFactDecision] = []
    for fact in facts:
        decision = decide_promo_fact(
            client_id=client_id,
            fact=fact,
            service_id=service_id,
            route=route,
            aspect=aspect,
            today=today,
        )
        if fact.kind == "promo":
            decisions.append(decision)
        if decision.allowed:
            kept.append(fact)
    return kept, decisions
