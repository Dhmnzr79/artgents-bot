"""Load and render structured price offers (PRODUCT_WORK_PLAN stage 3)."""
from __future__ import annotations

import json
import os
import re
import threading
from typing import Any

from pydantic import ValidationError

from config import PRICE_CONCERN_RE, PRICE_LOOKUP_RE
from contracts.price_brand_aliases import PriceBrandAliasesFile
from contracts.price_offer import PriceOffer, PriceOfferUnit, PriceOffersFile
from contracts.pricebook import PricebookServiceEntry
from core.client_runtime import client_pack_dir
from core.patient_scope_cues import (
    ALL_ON_4_ONLY_RX as _ALL_ON_4_ONLY_RX,
    ALL_ON_6_ONLY_RX as _ALL_ON_6_ONLY_RX,
    ALL_ON_6_RX as _ALL_ON_6_RX,
    CROWN_INCLUSION_RX as _CROWN_INCLUSION_RX,
    FULL_ARCH_RX as _FULL_ARCH_RX,
    IMPLANT_PRICE_RX as _IMPLANT_PRICE_RX,
    JAW_EXPLICIT_RX as _JAW_EXPLICIT_RX,
    JAW_RESTORATION_RX as _JAW_RESTORATION_RX,
    ONE_STAGE_PRICE_RX as _ONE_STAGE_PRICE_RX,
    ONE_TOOTH_EXPLICIT_RX as _ONE_TOOTH_EXPLICIT_RX,
    UPPER_JAW_RX as _UPPER_JAW_RX,
)
from core.pricebook_loader import (
    load_pricebook_service,
    offers_from_service_entry,
)

_UNIT_BY_SERVICE: dict[str, PriceOfferUnit] = {
    "classic": "one_tooth",
    "one_stage": "one_tooth",
    "all_on_4": "jaw",
    "all_on_6": "jaw",
}

_CACHE_LOCK = threading.Lock()
_CACHE: dict[str, list[PriceOffer]] = {}
_CACHE_MTIME: dict[str, float] = {}
_ALIAS_CACHE: dict[str, list[tuple[str, str]]] = {}
_ALIAS_MTIME: dict[str, float] = {}


def format_rub(amount: int) -> str:
    return f"{int(amount):,}".replace(",", " ") + " ₽"


def _brand_filter_on() -> bool:
    from config import BRAND_FILTER_ON

    return bool(BRAND_FILTER_ON)


def price_offers_path(client_id: str | None) -> str:
    return os.path.join(client_pack_dir(client_id), "price_offers.json")


def price_brand_aliases_path(client_id: str | None) -> str:
    return os.path.join(client_pack_dir(client_id), "price_brand_aliases.json")


def load_price_offers(client_id: str | None, *, force_reload: bool = False) -> list[PriceOffer]:
    path = price_offers_path(client_id)
    try:
        mtime = os.path.getmtime(path) if os.path.isfile(path) else 0.0
    except OSError:
        mtime = 0.0
    pack_key = path
    with _CACHE_LOCK:
        if not force_reload and _CACHE.get(pack_key) is not None and _CACHE_MTIME.get(pack_key) == mtime:
            return list(_CACHE[pack_key])
    if not os.path.isfile(path):
        with _CACHE_LOCK:
            _CACHE[pack_key] = []
            _CACHE_MTIME[pack_key] = mtime
        return []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh) or {}
        parsed = PriceOffersFile.model_validate(raw)
        offers = list(parsed.offers)
    except (OSError, json.JSONDecodeError, ValidationError, ValueError):
        offers = []
    with _CACHE_LOCK:
        _CACHE[pack_key] = offers
        _CACHE_MTIME[pack_key] = mtime
    return list(offers)


def load_brand_alias_rules(client_id: str | None, *, force_reload: bool = False) -> list[tuple[str, str]]:
    """Return (alias_phrase, canonical_brand) sorted longest alias first."""
    path = price_brand_aliases_path(client_id)
    try:
        mtime = os.path.getmtime(path) if os.path.isfile(path) else 0.0
    except OSError:
        mtime = 0.0
    with _CACHE_LOCK:
        if not force_reload and _ALIAS_CACHE.get(path) is not None and _ALIAS_MTIME.get(path) == mtime:
            return list(_ALIAS_CACHE[path])
    rules: list[tuple[str, str]] = []
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                raw = json.load(fh) or {}
            parsed = PriceBrandAliasesFile.model_validate(raw)
            for alias, brand in parsed.brand_aliases.items():
                a = str(alias or "").strip().lower()
                b = str(brand or "").strip()
                if a and b:
                    rules.append((a, b))
        except (OSError, json.JSONDecodeError, ValidationError, ValueError):
            rules = []
    rules.sort(key=lambda x: len(x[0]), reverse=True)
    with _CACHE_LOCK:
        _ALIAS_CACHE[path] = rules
        _ALIAS_MTIME[path] = mtime
    return list(rules)


def default_unit_for_service(service_id: str | None) -> PriceOfferUnit | None:
    sid = (service_id or "").strip()
    return _UNIT_BY_SERVICE.get(sid)


def detect_brand_in_query(q: str, *, client_id: str | None = None) -> str | None:
    text = (q or "").lower()
    if not text:
        return None
    for alias, brand in load_brand_alias_rules(client_id):
        if alias in text:
            return brand
    return None


_BRAND_GROUP_QUERY_RX: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"корейск", re.I | re.U), "korean"),
    (re.compile(r"немецк|герман", re.I | re.U), "german"),
    (re.compile(r"швейцар", re.I | re.U), "swiss"),
)


def literal_brand_group_in_query(q: str) -> str | None:
    text = (q or "").strip()
    if not text:
        return None
    for rx, group in _BRAND_GROUP_QUERY_RX:
        if rx.search(text):
            return group
    return None


def literal_brand_in_query(q: str, *, client_id: str | None = None) -> tuple[str | None, str | None]:
    """Brand/group only when literally named in patient text (aliases + geo groups)."""
    brand = detect_brand_in_query(q, client_id=client_id)
    brand_group = literal_brand_group_in_query(q)
    return brand, brand_group


def has_literal_brand_in_query(q: str, *, client_id: str | None = None) -> bool:
    brand, group = literal_brand_in_query(q, client_id=client_id)
    return bool(brand or group)


BUDGET_SIGNAL_RE = re.compile(
    r"(?:"
    r"деш[её]в\w*|"
    r"подеш[её]в\w*|"
    r"бюджет\w*|"
    r"попроще\s+по\s+цен\w*|"
    r"сам\w+\s+доступн\w*|"
    r"доступн\w+\s+имплант"
    r")",
    re.I | re.U,
)


def has_budget_signal(q: str) -> bool:
    text = (q or "").strip()
    if not text:
        return False
    return bool(PRICE_CONCERN_RE.search(text) or BUDGET_SIGNAL_RE.search(text))


def canonical_brand_name(raw: str, *, client_id: str | None = None) -> str | None:
    """Map conversational alias or partial brand token to canonical pricebook brand."""
    text = (raw or "").strip().lower()
    if not text:
        return None
    for alias, brand in load_brand_alias_rules(client_id):
        if alias == text:
            return brand
    for alias, brand in load_brand_alias_rules(client_id):
        if brand.lower() == text:
            return brand
    return detect_brand_in_query(text, client_id=client_id)


def is_generic_implant_price_query(q: str) -> bool:
    text = (q or "").strip()
    if not text or not PRICE_LOOKUP_RE.search(text):
        return False
    if not _IMPLANT_PRICE_RX.search(text):
        return False
    if re.search(r"протез|протезирован|коронк|абатмент", text, re.I | re.U):
        return False
    if _JAW_EXPLICIT_RX.search(text) or _ONE_TOOTH_EXPLICIT_RX.search(text):
        return False
    return True


def _jaw_scope_price_query_common(text: str) -> bool:
    if not text or not PRICE_LOOKUP_RE.search(text):
        return False
    if _ONE_TOOTH_EXPLICIT_RX.search(text):
        return False
    if re.search(r"протез|протезирован|коронк|абатмент", text, re.I | re.U):
        return False
    if _ALL_ON_4_ONLY_RX.search(text) and not _ALL_ON_6_ONLY_RX.search(text):
        return False
    if _ALL_ON_6_ONLY_RX.search(text) and not _ALL_ON_4_ONLY_RX.search(text):
        return False
    has_jaw = bool(
        _JAW_EXPLICIT_RX.search(text) or _UPPER_JAW_RX.search(text) or _FULL_ARCH_RX.search(text)
    )
    has_signal = bool(
        _IMPLANT_PRICE_RX.search(text)
        or _JAW_RESTORATION_RX.search(text)
        or _UPPER_JAW_RX.search(text)
        or _FULL_ARCH_RX.search(text)
    )
    return has_jaw and has_signal


def is_full_jaw_implant_price_query(q: str) -> bool:
    """Jaw-scope implant price without a single protocol — → manifest group full_jaw."""
    text = (q or "").strip()
    if not _jaw_scope_price_query_common(text):
        return False
    return not _UPPER_JAW_RX.search(text)


def is_upper_jaw_restoration_price_query(q: str) -> bool:
    """Upper jaw full-arch price — compare All-on-4 vs All-on-6 (manifest group upper_jaw)."""
    text = (q or "").strip()
    if not _jaw_scope_price_query_common(text):
        return False
    return bool(_UPPER_JAW_RX.search(text))


def is_crown_inclusion_content_query(q: str) -> bool:
    """Crown in/out of turnkey price — FAQ content, not zirconia price lookup."""
    text = (q or "").strip()
    if not text or not _CROWN_INCLUSION_RX.search(text):
        return False
    if PRICE_LOOKUP_RE.search(text) and re.search(r"сколько|цена|стоим|стоит", text, re.I | re.U):
        if re.search(r"уже\s+стоит\s+имплант|коронк\w*\s+на\s+имплант", text, re.I | re.U):
            return False
        if re.search(r"обычн\w*|на\s+зуб\b|сво[ийё]\w*\s+зуб", text, re.I | re.U):
            return False
    return True


def is_one_stage_price_query(q: str) -> bool:
    text = (q or "").strip()
    if not text:
        return False
    if not (PRICE_LOOKUP_RE.search(text) or re.search(r"сколько|цена|стоим|стоит", text, re.I | re.U)):
        return False
    return bool(_ONE_STAGE_PRICE_RX.search(text))


def resolve_implant_group_overview(q: str) -> str | None:
    from core.price_scope import detect_price_scope

    return detect_price_scope(q).group_id


def should_offer_unit_clarify(q: str, match: dict[str, Any]) -> bool:
    """Generic implant price → group overview from manifest (legacy name kept)."""
    _ = match
    return resolve_implant_group_overview(q) is not None


def build_unit_clarify_answer(client_id: str | None, *, group_id: str = "implantation") -> str | None:
    from core.price_group_overview import build_group_overview_answer

    answer, _, _ = build_group_overview_answer(client_id, group_id=group_id)
    return answer


def unit_clarify_quick_replies(
    client_id: str | None = None,
    *,
    group_id: str = "implantation",
) -> list[dict[str, str]]:
    from core.price_group_overview import group_overview_quick_replies

    return group_overview_quick_replies(client_id, group_id=group_id)


def get_price_offers(
    client_id: str | None,
    service_id: str,
    *,
    unit: PriceOfferUnit | None = None,
    brand: str | None = None,
    brand_group: str | None = None,
) -> list[PriceOffer]:
    sid = (service_id or "").strip()
    if not sid:
        return []
    unit_eff = unit or default_unit_for_service(sid)
    entry = load_pricebook_service(client_id, sid)
    if entry is not None:
        pool = offers_from_service_entry(entry) if entry.variants else []
    else:
        pool = [o for o in load_price_offers(client_id) if o.service_id == sid]
    out: list[PriceOffer] = []
    for offer in pool:
        if unit_eff and offer.unit != unit_eff:
            continue
        if brand and offer.brand.strip().lower() != str(brand).strip().lower():
            continue
        if brand_group:
            variant = next((v for v in (entry.variants if entry else []) if v.offer_id == offer.offer_id), None)
            if variant and str(variant.brand_group or "").strip().lower() != str(brand_group).strip().lower():
                continue
        out.append(offer)
    out.sort(key=lambda o: (not o.recommended, o.total, o.brand))
    return out


def min_offer_total(
    client_id: str | None,
    service_id: str,
    *,
    unit: PriceOfferUnit | None = None,
) -> int | None:
    offers = get_price_offers(client_id, service_id, unit=unit)
    if not offers:
        return None
    return min(o.total for o in offers)


def _unit_heading(unit: PriceOfferUnit) -> str:
    if unit == "one_tooth":
        return "под ключ, один зуб"
    if unit == "one_implant":
        return "один имплант"
    if unit == "one_site":
        return "одна зона"
    if unit == "jaw":
        return "под ключ, одна челюсть"
    if unit == "full_mouth":
        return "обе челюсти"
    return "под ключ"


def _append_bullet_section(lines: list[str], heading: str, items: list[str]) -> None:
    if not items:
        return
    lines.append("")
    lines.append(f"**{heading}:**")
    for item in items:
        t = str(item or "").strip()
        if t:
            lines.append(f"- {t}")


def variants_are_brand_based(entry: PricebookServiceEntry) -> bool:
    """True when variant rows represent implant brands (not procedure options)."""
    if not entry.variants:
        return False
    return any(v.brand_group for v in entry.variants)


def _recommended_offer_suffix(*, brand_based: bool) -> str:
    if brand_based:
        return " — часто рекомендуем как баланс цены и надёжности"
    return " — рекомендуемый вариант"


def _render_offer_detail_lines(
    offer: PriceOffer,
    *,
    compact: bool,
    brand_based: bool = True,
) -> list[str]:
    suffix = _recommended_offer_suffix(brand_based=brand_based) if offer.recommended else ""
    lines = [f"- **{offer.brand_label}** — **{format_rub(offer.total)}**{suffix}"]
    if compact:
        return lines
    _append_bullet_section(lines, "Входит", list(offer.includes))
    _append_bullet_section(lines, "Не входит", list(offer.excludes))
    if offer.payment_stages:
        lines.append("")
        lines.append("**Оплата по этапам:**")
        for stage in offer.payment_stages:
            lines.append(f"- {stage.name} — **{format_rub(stage.amount)}**")
    return lines


def render_price_offers_append(
    offers: list[PriceOffer],
    *,
    compact: bool = False,
    heading: str | None = None,
    brand_based: bool = True,
) -> str | None:
    if not offers:
        return None
    lines: list[str] = []
    if heading:
        lines.append(heading)
    elif not compact:
        unit = offers[0].unit
        lines.append(f"**Точные цены** ({_unit_heading(unit)}):")

    if len(offers) == 1 and not compact:
        lines.extend(_render_offer_detail_lines(offers[0], compact=False, brand_based=brand_based))
        return "\n".join(lines)

    for offer in offers:
        line = f"- {offer.brand_label} — **{format_rub(offer.total)}**"
        if offer.recommended:
            line += _recommended_offer_suffix(brand_based=brand_based)
        lines.append(line)

    if compact:
        return "\n".join(lines)

    stage_offer = next((o for o in offers if o.recommended), offers[0])
    if stage_offer.payment_stages:
        lines.append("")
        lines.append(f"**Оплата по этапам** (пример {stage_offer.brand_label}):")
        for stage in stage_offer.payment_stages:
            lines.append(f"- {stage.name} — **{format_rub(stage.amount)}**")

    _append_bullet_section(lines, f"Входит (пример {stage_offer.brand_label})", list(stage_offer.includes))
    _append_bullet_section(lines, "Не входит", list(stage_offer.excludes))

    return "\n".join(lines)


def _recommended_offer(offers: list[PriceOffer]) -> PriceOffer | None:
    if not offers:
        return None
    return next((o for o in offers if o.recommended), offers[0])


def render_offer_stages_only(offers: list[PriceOffer]) -> str | None:
    offer = _recommended_offer(offers)
    if not offer or not offer.payment_stages:
        return None
    lines = [f"**Оплата по этапам** ({offer.brand_label}):"]
    for stage in offer.payment_stages:
        lines.append(f"- {stage.name} — **{format_rub(stage.amount)}**")
    return "\n".join(lines)


def render_offer_includes_only(offers: list[PriceOffer]) -> str | None:
    offer = _recommended_offer(offers)
    if not offer:
        return None
    lines: list[str] = []
    _append_bullet_section(lines, "Входит", list(offer.includes))
    _append_bullet_section(lines, "Не входит", list(offer.excludes))
    return "\n".join(lines).strip() or None


def build_price_answer_for_lookup(
    *,
    client_id: str | None,
    service_id: str,
    q: str,
    aspect: str | None = None,
) -> tuple[str | None, dict[str, Any]]:
    """PriceBook v2 answer when service entry exists; else legacy append-only."""
    from core.price_answer_assembler import assemble_price_answer
    from core.pricebook_loader import load_pricebook_service

    sid = (service_id or "").strip()
    entry = load_pricebook_service(client_id, sid)
    if not entry:
        return build_price_append_for_lookup(client_id=client_id, service_id=sid, q=q)

    brand = detect_brand_in_query(q, client_id=client_id)
    planner_brand = None
    planner_brand_group = None
    if _brand_filter_on():
        try:
            literal_brand, literal_group = literal_brand_in_query(q, client_id=client_id)
            if has_budget_signal(q) and not (literal_brand or literal_group):
                planner_brand = None
                planner_brand_group = None
            else:
                from core.turn_planner_llm import turn_plan_brand_filter_from_ctx

                planner_brand, planner_brand_group = turn_plan_brand_filter_from_ctx()
                if literal_brand or literal_group:
                    planner_brand = literal_brand or planner_brand
                    planner_brand_group = literal_group or planner_brand_group
        except Exception:
            pass
    brand = planner_brand or brand
    unit = entry.default_unit or default_unit_for_service(sid)
    offers = get_price_offers(
        client_id,
        sid,
        unit=unit,
        brand=brand,
        brand_group=planner_brand_group,
    )
    if (brand or planner_brand_group) and not offers and entry.price_model == "complex":
        offers = get_price_offers(client_id, sid, unit=unit)

    aspect_norm = (aspect or "").strip().lower() or None
    answer, meta = assemble_price_answer(
        client_id=client_id,
        service_id=sid,
        offers=offers,
        entry=entry,
        aspect=aspect_norm,  # type: ignore[arg-type]
    )
    if answer:
        meta.setdefault("price_offer_unit", unit)
        meta.setdefault("price_offer_brand_filter", brand)
        meta.setdefault("price_offer_brand_group_filter", planner_brand_group)
        return answer, meta
    return build_price_append_for_lookup(client_id=client_id, service_id=sid, q=q)


def build_price_append_for_lookup(
    *,
    client_id: str | None,
    service_id: str,
    q: str,
) -> tuple[str | None, dict[str, Any]]:
    brand = detect_brand_in_query(q, client_id=client_id)
    planner_brand = None
    planner_brand_group = None
    if _brand_filter_on():
        try:
            literal_brand, literal_group = literal_brand_in_query(q, client_id=client_id)
            if has_budget_signal(q) and not (literal_brand or literal_group):
                planner_brand = None
                planner_brand_group = None
            else:
                from core.turn_planner_llm import turn_plan_brand_filter_from_ctx

                planner_brand, planner_brand_group = turn_plan_brand_filter_from_ctx()
                if literal_brand or literal_group:
                    planner_brand = literal_brand or planner_brand
                    planner_brand_group = literal_group or planner_brand_group
        except Exception:
            pass
    brand = planner_brand or brand
    unit = default_unit_for_service(service_id)
    offers = get_price_offers(
        client_id,
        service_id,
        unit=unit,
        brand=brand,
        brand_group=planner_brand_group,
    )
    if (brand or planner_brand_group) and not offers:
        offers = get_price_offers(client_id, service_id, unit=unit)
    append = render_price_offers_append(offers)
    if not append:
        return None, {}
    meta = {
        "price_offers_applied": True,
        "price_offer_service_id": service_id,
        "price_offer_unit": unit,
        "price_offer_brand_filter": brand,
        "price_offer_brand_group_filter": planner_brand_group,
        "price_offer_ids": [o.offer_id for o in offers],
    }
    return append, meta


_PRICE_APPEND_LLM_HINT = (
    "\n\nЕсли в ответе будет блок «Точные цены», «Входит», «Не входит» или «Оплата по этапам» "
    "(дополнение после твоего текста), итоговые суммы, этапы и состав пакета для пациента бери "
    "**только** из того блока, не из текста источника."
)


def price_append_llm_hint() -> str:
    return _PRICE_APPEND_LLM_HINT
