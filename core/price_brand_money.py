"""Brand filter consumption + budget anchor on implant price path (BRAND_FILTER_ON)."""
from __future__ import annotations

import re
from typing import Any, Literal

from contracts.ask_orchestration import AskOrchestrationResult
from contracts.price_offer import PriceOffer
from core.client_config_loader import (
    brand_money_budget_anchor_fact_ids,
    brand_money_budget_anchor_service_id,
)
from core.patient_scope_cues import IMPLANT_PRICE_RX
from core.price_offers import (
    build_price_answer_for_lookup,
    format_rub,
    get_price_offers,
    has_budget_signal,
    literal_brand_in_query,
    min_offer_total,
)
from core.pricebook_loader import load_pricebook_service, resolve_fact_refs
from logging_setup import get_logger, log_json

logger = get_logger("bot")

BrandMoneyPath = Literal["explicit_brand", "budget_anchor", "budget_fallback"]

_DEFAULT_BUDGET_ANCHOR_FACT_IDS = (
    "installment_12",
    "tax_deduction",
    "implant_same_day_discount",
    "free_implant_consult",
)


def brand_filter_enabled() -> bool:
    from config import BRAND_FILTER_ON

    return bool(BRAND_FILTER_ON)


def resolve_brand_filter(q: str, *, client_id: str | None) -> tuple[str | None, str | None]:
    """Explicit brand/group only when literally named in the patient query."""
    return literal_brand_in_query(q, client_id=client_id)


def has_price_question(q: str, *, brand: str | None = None) -> bool:
    from core.patient_scope_cues import has_price_intent

    text = (q or "").strip()
    if not text:
        return False
    if has_budget_signal(text) or has_price_intent(text):
        return True
    if brand and re.search(r"\bсколько\b", text, re.I | re.U):
        return True
    return bool(re.search(r"\bсколько\b", text, re.I | re.U) and IMPLANT_PRICE_RX.search(text))


def _implant_context_service_ids(client_id: str | None) -> frozenset[str]:
    from core.pricebook_loader import list_pricebook_service_ids
    from core.turn_planner_llm import _implantation_tagged_service_ids

    ids = set(_implantation_tagged_service_ids(client_id))
    for service_id in list_pricebook_service_ids(client_id):
        entry = load_pricebook_service(client_id, service_id)
        if not entry:
            continue
        tags = {str(t or "").strip().lower() for t in (entry.tags or [])}
        if "budget_anchor" in tags or "implantation" in tags:
            ids.add(service_id)
    return frozenset(ids)


def is_implant_price_context(
    q: str,
    price_route: dict[str, Any] | None = None,
    *,
    brand: str | None = None,
    brand_group: str | None = None,
    client_id: str | None = None,
) -> bool:
    if brand or brand_group:
        return True
    text = (q or "").strip()
    if IMPLANT_PRICE_RX.search(text):
        return True
    implant_ids = _implant_context_service_ids(client_id)
    if price_route:
        sid = str(price_route.get("matched_service_id") or "").strip()
        if sid in implant_ids:
            return True
        service = price_route.get("service") if isinstance(price_route.get("service"), dict) else {}
        topic = str(service.get("catalog_topic") or "").strip().lower()
        if topic == "implantation":
            return True
    return False


def classify_brand_money_path(
    q: str,
    price_route: dict[str, Any] | None = None,
    *,
    client_id: str | None = None,
) -> BrandMoneyPath | None:
    if not brand_filter_enabled():
        return None
    literal_brand, literal_group = resolve_brand_filter(q, client_id=client_id)
    literal_explicit = bool(literal_brand or literal_group)
    budget = has_budget_signal(q)
    implant = is_implant_price_context(
        q,
        price_route,
        brand=literal_brand,
        brand_group=literal_group,
        client_id=client_id,
    )
    if budget and implant and not literal_explicit:
        return "budget_anchor"
    if literal_explicit and implant and has_price_question(q, brand=literal_brand):
        return "explicit_brand"
    if budget and not implant:
        return "budget_fallback"
    return None


def resolve_budget_anchor_service_id(client_id: str | None) -> str | None:
    configured = brand_money_budget_anchor_service_id(client_id)
    if configured and load_pricebook_service(client_id, configured):
        return configured
    from core.pricebook_loader import list_pricebook_service_ids

    for service_id in list_pricebook_service_ids(client_id):
        entry = load_pricebook_service(client_id, service_id)
        if not entry or not entry.variants:
            continue
        tags = {str(t or "").strip().lower() for t in (entry.tags or [])}
        if "budget_anchor" in tags:
            return service_id
    for service_id in list_pricebook_service_ids(client_id):
        entry = load_pricebook_service(client_id, service_id)
        if not entry or not entry.variants:
            continue
        tags = {str(t or "").strip().lower() for t in (entry.tags or [])}
        if "implantation" in tags:
            return service_id
    return None


def _budget_anchor_unit(client_id: str | None, service_id: str) -> str | None:
    entry = load_pricebook_service(client_id, service_id)
    if not entry:
        return None
    return str(entry.default_unit or "").strip() or None


def _pick_budget_anchor_pair(offers: list[PriceOffer]) -> tuple[PriceOffer | None, PriceOffer | None]:
    if not offers:
        return None, None
    affordable = min(offers, key=lambda o: o.total)
    recommended = next((o for o in offers if o.recommended), None)
    if recommended is not None and recommended.offer_id == affordable.offer_id:
        recommended = None
    if recommended is None:
        others = sorted(
            (o for o in offers if o.offer_id != affordable.offer_id),
            key=lambda o: o.total,
        )
        recommended = others[0] if others else None
    return affordable, recommended


def _build_budget_anchor_content(
    *,
    client_id: str | None,
) -> tuple[list[str], list[str], list[str], dict[str, Any]]:
    service_id = resolve_budget_anchor_service_id(client_id)
    if not service_id:
        return [], [], [], {"brand_money_path": "budget_anchor"}
    unit = _budget_anchor_unit(client_id, service_id)
    offers = get_price_offers(client_id, service_id, unit=unit)  # type: ignore[arg-type]
    affordable, anchor = _pick_budget_anchor_pair(offers)
    card_lines: list[str] = []
    pinned_lines: list[str] = []
    meta: dict[str, Any] = {
        "brand_money_path": "budget_anchor",
        "matched_service_id": service_id,
    }
    if affordable:
        label = str(affordable.brand_label or affordable.brand or service_id).strip()
        card_lines.append(f"Доступный вариант: {label} — {format_rub(affordable.total)}.")
        pinned_lines.append(f"{label} — {format_rub(affordable.total)}.")
        meta.setdefault("price_offer_ids", []).append(affordable.offer_id)
    if anchor:
        label = str(anchor.brand_label or anchor.brand or service_id).strip()
        card_lines.append(f"Рекомендуемый баланс: {label} — {format_rub(anchor.total)}.")
        pinned_lines.append(f"{label} — {format_rub(anchor.total)}.")
        meta.setdefault("price_offer_ids", []).append(anchor.offer_id)
    fact_ids = brand_money_budget_anchor_fact_ids(client_id) or _DEFAULT_BUDGET_ANCHOR_FACT_IDS
    facts = resolve_fact_refs(client_id, list(fact_ids), usable_in="price_answer")
    fact_lines: list[str] = []
    for fact in facts:
        body = str(fact.text_fact or "").strip()
        if body:
            fact_lines.append(body)
    meta["pricebook_applied"] = True
    return card_lines, pinned_lines, fact_lines, meta


def build_budget_anchor_card(*, client_id: str | None) -> tuple[str, dict[str, Any]]:
    card_lines, _pinned_lines, fact_lines, meta = _build_budget_anchor_content(client_id=client_id)
    card = "\n".join(card_lines + fact_lines).strip()
    meta["composer_brief"] = card
    return card, meta


def build_budget_anchor_pinned_source(*, client_id: str | None) -> tuple[str, dict[str, Any]]:
    _card_lines, pinned_lines, fact_lines, meta = _build_budget_anchor_content(client_id=client_id)
    pinned = "\n".join(pinned_lines + fact_lines).strip()
    return pinned, meta


def build_budget_anchor_brief(*, client_id: str | None) -> str:
    pinned, _meta = build_budget_anchor_pinned_source(client_id=client_id)
    return (
        "Задача: написать ОДИН связный тёплый ответ пациенту на бюджетный вопрос про импланты.\n"
        "Арка (в этом порядке): услышать бюджет → назвать доступный вариант честно → "
        "заякорить рекомендованным балансом → платёжные смягчители → бесплатная консультация имплантолога.\n"
        "Пиши связной прозой, без нумерованных списков и без ярлыков "
        "«Доступный вариант:», «Рекомендуемый баланс:».\n"
        "Цифры и факты в блоке ниже пришпилены — воспроизведи суммы, проценты и сроки ДОСЛОВНО, "
        "не округляй и не придумывай новые.\n"
        "Не сравнивай разные масштабы лечения и не уводи в птеригоидные/скуловые протоколы.\n"
        "Приглашений и CTA не добавляй — их добавит интерфейс.\n\n"
        "ДОСЛОВНО — пришпиленные факты (все суммы и условия из этого блока):\n"
        f"{pinned}"
    )


def _generate_budget_anchor_answer(*args, **kwargs):
    from llm import generate_answer_from_packet_fullctx

    return generate_answer_from_packet_fullctx(*args, **kwargs)


def compose_budget_anchor_answer(
    *,
    client_id: str | None,
    patient_q: str,
    brief: str,
    session_id: str | None,
) -> tuple[str | None, dict[str, Any]]:
    q = (patient_q or "").strip()
    if not q or not (brief or "").strip():
        return None, {}
    meta = {
        "client_id": client_id,
        "composer_surface": "brand_budget_anchor",
    }
    try:
        from llm import LLM_FALLBACK_ANSWER

        answer, profile = _generate_budget_anchor_answer(
            q,
            brief,
            ["price"],
            [],
            meta,
            session_id or "",
        )
    except Exception as exc:
        log_json(
            logger,
            "budget_anchor_composer_failed",
            client_id=client_id,
            sid=session_id,
            err=str(exc)[:300],
        )
        return None, {}
    if not isinstance(profile, dict) or not profile.get("composer_used"):
        log_json(
            logger,
            "budget_anchor_composer_fail_open",
            client_id=client_id,
            sid=session_id,
            reason="composer_not_used",
        )
        return None, profile if isinstance(profile, dict) else {}
    if not (answer or "").strip() or answer == LLM_FALLBACK_ANSWER:
        return None, profile
    return str(answer).strip(), profile


def _cheapest_offer(client_id: str | None, service_id: str) -> tuple[str, int] | None:
    entry = load_pricebook_service(client_id, service_id)
    if not entry:
        return None
    unit = entry.default_unit
    offers = get_price_offers(client_id, service_id, unit=unit)
    if offers:
        cheapest = min(offers, key=lambda o: o.total)
        label = str(cheapest.brand_label or cheapest.brand or service_id).strip()
        return label, int(cheapest.total)
    if entry.price_model == "simple" and entry.price is not None:
        label = str(entry.display_name or service_id).strip()
        return label, int(entry.price.value)
    total = min_offer_total(client_id, service_id, unit=unit)
    if total is not None:
        label = str(entry.display_name or service_id).strip()
        return label, int(total)
    return None


def _fallback_anchor_for_query(
    q: str,
    *,
    client_id: str | None,
    matched_service_id: str | None,
) -> tuple[str, int, str] | None:
    text = (q or "").strip().lower()
    anchor_sid = resolve_budget_anchor_service_id(client_id)
    hints: tuple[tuple[re.Pattern[str], str | None], ...] = (
        (re.compile(r"съ[её]мн\w*|частичн\w+\s+протез|полн\w+\s+протез", re.I | re.U), "removable_dentures"),
        (re.compile(r"мост|коронк", re.I | re.U), "zirconia_crowns"),
        (re.compile(r"бюгел", re.I | re.U), "clasp_dentures"),
        (re.compile(r"имплант", re.I | re.U), anchor_sid),
    )
    candidates: list[str] = []
    for rx, sid in hints:
        if sid and rx.search(text):
            candidates.append(sid)
    matched = str(matched_service_id or "").strip()
    if matched and matched not in candidates:
        candidates.append(matched)
    if not candidates:
        return None
    best: tuple[str, int, str] | None = None
    for sid in candidates:
        if not sid:
            continue
        row = _cheapest_offer(client_id, sid)
        if row is None:
            continue
        label, total = row
        if best is None or total < best[1]:
            best = (sid, total, label)
    return best


def build_budget_fallback_payload(
    *,
    sid: str,
    client_id: str | None,
    q: str,
    price_route: dict[str, Any] | None,
) -> dict[str, Any]:
    matched = str((price_route or {}).get("matched_service_id") or "").strip() or None
    anchor = _fallback_anchor_for_query(q, client_id=client_id, matched_service_id=matched)
    if anchor:
        service_id, total, label = anchor
        price_line = f"Ориентир по стоимости — от {format_rub(total)} ({label})."
        meta_service = service_id
        offer_ids: list[str] = []
    else:
        price_line = (
            "Точную стоимость врач назовёт на консультации — после осмотра по вашей ситуации."
        )
        meta_service = matched
        offer_ids = []
    answer = (
        "Понимаю, что важен бюджет. "
        f"{price_line} "
        "На бесплатной консультации врач посмотрит ситуацию и назовёт точную сумму по вашему случаю."
    )
    meta: dict[str, Any] = {
        "sid": sid,
        "client_id": client_id,
        "intent": str((price_route or {}).get("intent") or "price_concern"),
        "matched_service_id": meta_service,
        "route_source": "brand_budget_fallback",
        "brand_money_path": "budget_fallback",
        "fallback_reason": "budget_cross_scope",
        "followups": [],
        "ui_source_family": "price_navigation",
        "answer_path": "brand_budget_fallback",
    }
    if offer_ids:
        meta["price_offer_ids"] = offer_ids
    if anchor:
        meta["pricebook_simple_value"] = anchor[1]
    return {
        "answer": answer,
        "quick_replies": [],
        "cta": None,
        "video": None,
        "situation": {"show": False, "mode": "normal"},
        "offer": None,
        "meta": meta,
    }


def _explicit_brand_service_id(price_route: dict[str, Any] | None, *, client_id: str | None) -> str:
    anchor = resolve_budget_anchor_service_id(client_id)
    if anchor:
        return anchor
    return str((price_route or {}).get("matched_service_id") or "").strip()


def build_explicit_brand_payload(
    *,
    sid: str,
    client_id: str | None,
    q: str,
    price_route: dict[str, Any] | None,
) -> dict[str, Any] | None:
    from core.price_answer_assembler import assemble_price_answer

    literal_brand, literal_group = resolve_brand_filter(q, client_id=client_id)
    service_id = _explicit_brand_service_id(price_route, client_id=client_id)
    entry = load_pricebook_service(client_id, service_id)
    if not entry:
        return None
    unit = entry.default_unit
    offers = get_price_offers(
        client_id,
        service_id,
        unit=unit,
        brand=literal_brand,
        brand_group=literal_group,
    )
    if (literal_brand or literal_group) and not offers and entry.price_model == "complex":
        offers = get_price_offers(client_id, service_id, unit=unit)
    answer, offer_meta = assemble_price_answer(
        client_id=client_id,
        service_id=service_id,
        offers=offers,
        entry=entry,
        aspect=None,
    )
    if not answer:
        return None
    service = (price_route or {}).get("service") if isinstance((price_route or {}).get("service"), dict) else {}
    meta = {
        "sid": sid,
        "client_id": client_id,
        "intent": str((price_route or {}).get("intent") or "price_lookup"),
        "matched_service_id": service_id,
        "match_score": round(float((price_route or {}).get("match_score") or 0.0), 4),
        "route_source": "brand_filter",
        "brand_money_path": "explicit_brand",
        "price_key": service.get("price_key"),
        "price_ref": service.get("price_ref"),
        "fallback_reason": None,
        "followups": [],
        "ui_source_family": "price_navigation",
        "answer_path": "brand_filter",
        "price_offer_brand_filter": literal_brand,
        "price_offer_brand_group_filter": literal_group,
    }
    meta.update(offer_meta)
    return {
        "answer": answer,
        "quick_replies": [],
        "cta": None,
        "video": None,
        "situation": {"show": False, "mode": "normal"},
        "offer": None,
        "meta": meta,
    }


def build_budget_anchor_payload(
    *,
    sid: str,
    client_id: str | None,
    q: str,
    price_route: dict[str, Any] | None,
) -> dict[str, Any]:
    from core.numeric_fact_gate import apply_numeric_fact_gate

    card, card_meta = build_budget_anchor_card(client_id=client_id)
    brief = build_budget_anchor_brief(client_id=client_id)
    pinned, _pinned_meta = build_budget_anchor_pinned_source(client_id=client_id)
    service_id = str(card_meta.get("matched_service_id") or resolve_budget_anchor_service_id(client_id) or "")
    meta: dict[str, Any] = {
        "sid": sid,
        "client_id": client_id,
        "intent": str((price_route or {}).get("intent") or "price_concern"),
        "matched_service_id": service_id or None,
        "match_score": round(float((price_route or {}).get("match_score") or 0.0), 4),
        "route_source": "brand_budget_anchor",
        "brand_money_path": "budget_anchor",
        "fallback_reason": None,
        "followups": [],
        "ui_source_family": "price_navigation",
        "answer_path": "brand_budget_anchor",
        "composer_brief": brief,
    }
    meta.update(card_meta)

    composed, composer_profile = compose_budget_anchor_answer(
        client_id=client_id,
        patient_q=q,
        brief=brief,
        session_id=sid,
    )
    if composed:
        answer = composed
        meta["answer_path"] = "composer"
        meta["composer_used"] = True
        if isinstance(composer_profile, dict):
            meta.update({k: v for k, v in composer_profile.items() if k not in meta})
    else:
        answer = card
        meta["composer_fail_open"] = True

    gate_result = apply_numeric_fact_gate(
        answer=answer,
        route="price_concern",
        meta=meta,
        client_id=client_id,
        allowed_source_text=pinned or card,
    )
    answer = gate_result.answer
    gate_meta = gate_result.meta_dict()
    if gate_meta:
        meta.update(gate_meta)

    return {
        "answer": answer,
        "quick_replies": [],
        "cta": None,
        "video": None,
        "situation": {"show": False, "mode": "normal"},
        "offer": None,
        "meta": meta,
    }


def try_brand_money_orchestration(
    *,
    q: str,
    sid: str,
    client_id: str,
    price_route: dict[str, Any] | None,
    decision_frame: dict[str, Any] | None,
) -> AskOrchestrationResult | None:
    if not brand_filter_enabled():
        return None
    path = classify_brand_money_path(q, price_route, client_id=client_id)
    if path is None:
        return None
    try:
        if path == "explicit_brand":
            payload = build_explicit_brand_payload(
                sid=sid,
                client_id=client_id,
                q=q,
                price_route=price_route,
            )
            if payload is None:
                return None
            service_route = "price_lookup"
        elif path == "budget_anchor":
            payload = build_budget_anchor_payload(
                sid=sid,
                client_id=client_id,
                q=q,
                price_route=price_route,
            )
            service_route = "price_brand_budget_anchor"
        else:
            payload = build_budget_fallback_payload(
                sid=sid,
                client_id=client_id,
                q=q,
                price_route=price_route,
            )
            service_route = "price_brand_budget_fallback"
    except Exception as exc:
        log_json(
            logger,
            "brand_money_fail_open",
            client_id=client_id,
            sid=sid,
            path=path,
            err=str(exc)[:300],
        )
        return None
    log_json(
        logger,
        "brand_money_route",
        client_id=client_id,
        sid=sid,
        path=path,
        matched_service_id=(payload.get("meta") or {}).get("matched_service_id"),
    )
    return AskOrchestrationResult(
        kind="service_reply",
        q=q,
        sid=sid,
        client_id=client_id,
        service_payload=payload,
        service_doc_id=None,
        service_track_user=True,
        service_route=service_route,
        decision_frame=decision_frame,
        price_offer_meta={
            k: v
            for k, v in (payload.get("meta") or {}).items()
            if k.startswith("price_offer") or k in {"pricebook_applied", "pricebook_simple_value"}
        }
        or None,
    )


def try_brand_money_early(
    *,
    q: str,
    sid: str,
    client_id: str,
    decision_frame: dict[str, Any] | None,
) -> AskOrchestrationResult | None:
    """Resolve catalog price route and intercept before composer / concern_ref."""
    if not brand_filter_enabled():
        return None
    try:
        from query_selector import select_price_service_route

        price_route = select_price_service_route(q, client_id=client_id, sid=sid)
        return try_brand_money_orchestration(
            q=q,
            sid=sid,
            client_id=client_id,
            price_route=price_route,
            decision_frame=decision_frame,
        )
    except Exception as exc:
        log_json(
            logger,
            "brand_money_early_fail_open",
            client_id=client_id,
            sid=sid,
            err=str(exc)[:300],
        )
        return None
