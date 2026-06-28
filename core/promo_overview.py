"""Direct promo/discount answers from PriceBook facts + marketing rules."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

from contracts.pricebook import PricingFact
from core.marketing_loader import MarketingPromo, load_marketing_config
from core.pricebook_loader import load_pricebook_service, load_pricing_facts

_PROMO_QUERY_RE = re.compile(
    r"\b(акци\w*|скидк\w*|спецпредлож\w*|промокод\w*)\b",
    re.IGNORECASE,
)
_DISCOUNT_QUERY_RE = re.compile(r"\b(скидк\w*|промокод\w*)\b|%", re.IGNORECASE)
_DISCOUNT_FACT_RE = re.compile(r"\b(скидк\w*|промокод\w*)\b|%", re.IGNORECASE)


@dataclass(frozen=True)
class PromoOverviewItem:
    fact: PricingFact
    promo_key: str
    allowed_service_ids: tuple[str, ...]


def is_direct_promo_question(q: str | None) -> bool:
    text = (q or "").strip().lower().replace("ё", "е")
    if not text:
        return False
    return bool(_PROMO_QUERY_RE.search(text))


def _date_active(active_until: str | None, *, today: date | None = None) -> bool:
    raw = str(active_until or "").strip()
    if not raw:
        return True
    try:
        end = datetime.strptime(raw[:10], "%Y-%m-%d").date()
    except ValueError:
        return True
    return (today or date.today()) <= end


def _route_allowed(rule: MarketingPromo, route: str) -> bool:
    return not rule.allowed_routes or route in rule.allowed_routes


def _service_allowed(rule: MarketingPromo, service_id: str | None) -> bool:
    if not service_id:
        return True
    return not rule.allowed_service_ids or service_id in rule.allowed_service_ids


def _fact_usable_for_promo_overview(fact: PricingFact) -> bool:
    usable = set(fact.usable_in or [])
    return bool(usable & {"price_answer", "commercial_answer"})


def _is_discount_fact(fact: PricingFact) -> bool:
    return bool(_DISCOUNT_FACT_RE.search((fact.text_fact or "").lower().replace("ё", "е")))


def _service_from_question(q: str, *, client_id: str | None) -> str | None:
    try:
        from query_selector import match_service_from_catalog
    except Exception:
        return None
    match = match_service_from_catalog(q, client_id=client_id)
    sid = str(match.get("matched_service_id") or "").strip()
    if sid and bool(match.get("is_confident")):
        return sid
    return None


def active_promo_overview_items(
    *,
    client_id: str | None,
    q: str | None = None,
    service_id: str | None = None,
    route: str = "promo_overview",
    today: date | None = None,
) -> list[PromoOverviewItem]:
    cfg = load_marketing_config(client_id)
    facts_file = load_pricing_facts(client_id)
    if not facts_file:
        return []

    service_eff = service_id or _service_from_question(q or "", client_id=client_id)
    discount_only = bool(_DISCOUNT_QUERY_RE.search((q or "").lower().replace("ё", "е")))
    out: list[PromoOverviewItem] = []

    for promo_key, rule in (cfg.promo_rules or {}).items():
        if not rule.active:
            continue
        if not _route_allowed(rule, route):
            continue
        if not _service_allowed(rule, service_eff):
            continue
        if not _date_active(rule.active_until, today=today):
            continue

        fact_id = str(rule.fact_ref or promo_key).strip()
        fact = facts_file.facts.get(fact_id)
        if not fact or fact.kind != "promo":
            continue
        if not _date_active(fact.active_until, today=today):
            continue
        if not _fact_usable_for_promo_overview(fact):
            continue
        if discount_only and not _is_discount_fact(fact):
            continue
        out.append(
            PromoOverviewItem(
                fact=fact,
                promo_key=promo_key,
                allowed_service_ids=tuple(rule.allowed_service_ids or ()),
            )
        )
    return out


def _service_label(client_id: str | None, service_id: str) -> str:
    entry = load_pricebook_service(client_id, service_id)
    if entry and entry.display_name:
        return entry.display_name
    return service_id.replace("_", " ")


def _quick_replies_for_items(
    client_id: str | None,
    items: list[PromoOverviewItem],
    *,
    service_id: str | None,
    limit: int = 4,
) -> list[dict[str, str]]:
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for item in items:
        services = [service_id] if service_id else list(item.allowed_service_ids)
        if not service_id and len(services) > 2:
            continue
        for sid in services:
            sid_eff = str(sid or "").strip()
            if not sid_eff or sid_eff in seen:
                continue
            seen.add(sid_eff)
            out.append({"label": f"Стоимость: {_service_label(client_id, sid_eff)}", "ref": f"price:{sid_eff}"})
            if len(out) >= limit:
                return out
    return out


def build_promo_overview_payload(
    *,
    sid: str,
    client_id: str | None,
    q: str,
) -> dict | None:
    if not is_direct_promo_question(q):
        return None

    service_id = _service_from_question(q, client_id=client_id)
    items = active_promo_overview_items(client_id=client_id, q=q, service_id=service_id)
    service_title = _service_label(client_id, service_id) if service_id else ""

    if not items:
        answer = (
            f"По услуге «{service_title}» сейчас не вижу активных акций в базе."
            if service_id
            else "Сейчас не вижу активных акций в базе. Если интересует конкретная услуга, напишите ее название — проверю точнее."
        )
        applied: list[str] = []
    else:
        lines = "\n".join(f"- {item.fact.text_fact.strip()}" for item in items if item.fact.text_fact.strip())
        if service_id:
            answer = f"По услуге «{service_title}» сейчас есть такие условия:\n\n{lines}"
        else:
            answer = f"Сейчас активны такие предложения:\n\n{lines}"
        applied = [item.fact.id for item in items]

    quick = _quick_replies_for_items(client_id, items, service_id=service_id)
    return {
        "answer": answer,
        "quick_replies": quick,
        "cta": None,
        "video": None,
        "situation": {"show": False, "mode": "normal"},
        "offer": None,
        "meta": {
            "sid": sid,
            "client_id": client_id,
            "intent": "promo_overview",
            "service_route": "promo_overview",
            "route_source": "marketing",
            "matched_service_id": service_id,
            "marketing_promos_applied": applied,
            "followups": [],
            "ui_source_family": "price_navigation",
        },
    }
