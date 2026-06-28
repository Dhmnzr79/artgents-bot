"""Deterministic gates for marketing ingredients selected by runtime code."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from contracts.pricebook import PricingFact
from core.marketing_loader import MarketingPromo, load_marketing_config


@dataclass(frozen=True)
class PromoFactDecision:
    fact_id: str
    allowed: bool
    reason: str
    promo_key: str | None = None


@dataclass(frozen=True)
class DoctorConsultBridge:
    text: str
    reason: str
    service_id: str | None = None


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
    for key, promo in (cfg.promo_rules or {}).items():
        if str(promo.fact_ref or "").strip() == fact.id:
            return key, promo
    direct = (cfg.promo_rules or {}).get(fact.id)
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


def _doctor_name_from_meta(meta: dict[str, Any]) -> str | None:
    for key in ("name_short", "name_full"):
        value = str(meta.get(key) or "").strip()
        if value:
            return value
    return None


def _service_candidates_from_meta(meta: dict[str, Any]) -> list[str]:
    matched = str(meta.get("matched_service_id") or "").strip()
    if matched:
        return [matched]
    raw = meta.get("services")
    if isinstance(raw, str):
        one = raw.strip()
        return [one] if one else []
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    return []


def select_doctor_consult_bridge(
    *,
    client_id: str | None,
    meta: dict[str, Any],
) -> DoctorConsultBridge:
    """Pick one non-price consult reason for doctor answers."""
    cfg = load_marketing_config(client_id)
    candidates = _service_candidates_from_meta(meta)
    matched = str(meta.get("matched_service_id") or "").strip()
    allowed_candidates = candidates if matched or len(candidates) == 1 else []
    for service_id in allowed_candidates:
        svc_cfg = cfg.service(service_id)
        if svc_cfg and svc_cfg.consult_reasons:
            reason = svc_cfg.consult_reasons[0]
            return DoctorConsultBridge(
                text=f"На консультации врач сможет {reason}.",
                reason="service_consult_reason",
                service_id=service_id,
            )

    name = _doctor_name_from_meta(meta)
    if name:
        return DoctorConsultBridge(
            text=f"На консультации {name} уточнит вашу ситуацию и подскажет, какой план лечения подойдет именно вам.",
            reason="doctor_named_fallback",
        )
    return DoctorConsultBridge(
        text="На консультации врач уточнит вашу ситуацию и поможет выбрать специалиста и план лечения под вашу задачу.",
        reason="doctor_generic_fallback",
    )
