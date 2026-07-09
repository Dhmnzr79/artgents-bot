"""Chunk selection orchestration for /ask retrieval path."""
import json
import os
import re
from typing import Any

from config import (
    COMMERCIAL_INFO_RE,
    CONSULTATION_QUERY_RE,
    KT_EXPLICIT_RE,
    DEFAULT_CLIENT_ID,
    PRICE_CONCERN_RE,
    PRICE_LOOKUP_RE,
    PRICE_SERVICE_MATCH_STRONG,
)
from core.catalog_match import resolve_catalog_match
from core.client_config_loader import resolve_pack_client_id
from core.routing_loader import THRESHOLDS
from core.price_scope import PriceScopeResult, detect_price_scope, scope_catalog_excludes, scope_implant_topic
from core.patient_situation import patient_situation_from_ctx
from core.patient_situation_routing import merge_price_scope
from core.patient_situation_session import resolve_patient_situation_for_turn
from core.price_offers import is_crown_inclusion_content_query, is_generic_implant_price_query
from core.price_followup import (
    is_vague_price_followup,
    is_weak_catalog_price_token_match,
    price_query_has_explicit_service_object,
)
from contracts.dialog_focus import DialogFocusDecision
from core.dialog_focus import dialog_focus_for_turn
from core.pricebook_loader import load_pricebook_service
from llm import classify_price_intent
from session import mem_get
from policy import (
    continuation_only_phrase,
    session_has_continuation_context,
)


def normalize_retrieval_query(q: str) -> str:
    """Legacy public normalizer kept for callers after embed retrieval removal."""
    text = (q or "").strip().lower().replace("ё", "е")
    text = re.sub(r"[^\w\s\-]", " ", text, flags=re.U)
    return re.sub(r"\s+", " ", text, flags=re.U).strip()

def _service_in_pricebook(
    client_id: str | None,
    service_id: str | None,
    price_key: str | None,
) -> bool:
    sid = (service_id or price_key or "").strip()
    if not sid:
        return False
    return load_pricebook_service(client_id, sid) is not None


def _patient_situation_for_turn(
    q: str,
    *,
    sid: str | None,
    client_id: str | None = None,
) -> tuple[Any, bool]:
    """Resolved patient situation for this turn + whether it was session-carried."""
    try:
        from flask import has_request_context, request
    except ImportError:
        has_request_context = lambda: False  # type: ignore[assignment,misc]
        request = None  # type: ignore[assignment]
    if has_request_context() and request is not None and hasattr(request, "ctx"):
        ctx_result = patient_situation_from_ctx()
        if ctx_result is not None:
            carried = bool(request.ctx.get("patient_situation_carried", False))
            return ctx_result, carried
    situation, meta = resolve_patient_situation_for_turn(q, sid=sid, client_id=client_id)
    return situation, bool(meta.get("patient_situation_carried"))


def _price_route_is_matched(route_source: str, price_ref: str | None) -> bool:
    if price_ref and route_source == "price_ref":
        return True
    return route_source in {"prices_json", "pricebook"}


def _resolve_price_lookup_route(
    *,
    route_source: str,
    price_ref: Any,
    price_item: dict | None,
    pricebook_available: bool = False,
    q: str = "",
    sid: str | None = None,
    client_id: str | None = None,
) -> tuple[str, str | None, str | None]:
    """price_ref → md; pricebook or prices.json; без авто-подстановки payment_terms."""
    if continuation_only_phrase(q) and not _service_from_session_context(sid, client_id):
        return route_source, None, None
    pref = str(price_ref or "").strip()
    if pref:
        rs = "price_ref" if route_source == "catalog" else route_source
        return rs, pref, None
    if price_item is not None:
        return "prices_json", None, None
    if pricebook_available:
        return "pricebook", None, None
    return route_source, None, "price_not_in_catalog"


def select_chunk_for_question(
    q: str,
    *,
    client_id: str | None,
    sid: str | None = None,
    scope_topic: str | None = None,
    decision: Any | None = None,
) -> dict:
    """Embed retrieval is removed in full-context 3.4; content uses composer."""
    _ = (q, client_id, sid, scope_topic, decision)
    return {
        "mode": "no_candidates",
        "debug_meta": {"retrieval_removed": True},
    }


def _safe_client_id(client_id: str | None) -> str:
    return resolve_pack_client_id(client_id)


def _client_json_path(client_id: str | None, file_name: str) -> str:
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "clients", _safe_client_id(client_id), file_name)


def _read_json_dict(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else {}
    except OSError:
        return {}
    except json.JSONDecodeError:
        return {}


def commercial_info_query(q: str) -> bool:
    return bool(COMMERCIAL_INFO_RE.search(q or ""))


def consultation_info_query(q: str) -> bool:
    return bool(CONSULTATION_QUERY_RE.search(q or ""))


def _lookup_intent_by_rules(q: str) -> str:
    q0 = (q or "").strip()
    if not q0:
        return "other"
    if continuation_only_phrase(q0):
        return "other"
    if is_crown_inclusion_content_query(q0):
        return "other"
    if PRICE_CONCERN_RE.search(q0):
        return "price_concern"
    if PRICE_LOOKUP_RE.search(q0):
        return "price_lookup"
    if consultation_info_query(q0) or commercial_info_query(q0):
        return "other"
    return "other"


def price_rules_hint(q: str) -> str | None:
    """Deterministic price intent from regex rules (runs before Resolver output)."""
    v = _lookup_intent_by_rules(q)
    if v == "price_concern":
        return "price_concern"
    if v == "price_lookup":
        return "price_lookup"
    return None


def catalog_service_session_context(sid: str | None, client_id: str | None) -> dict | None:
    """Public wrapper for `_service_from_session_context` (A3 session fallback)."""
    return _service_from_session_context(sid, client_id)


def classify_price_route_intent(q: str, *, client_id: str | None, sid: str | None) -> str:
    rule_intent = _lookup_intent_by_rules(q)
    if rule_intent != "other":
        return rule_intent
    return classify_price_intent(q, client_id=client_id, sid=sid or "")


def match_service_from_catalog(
    q: str,
    *,
    client_id: str | None,
    exclude_service_ids: frozenset[str] | None = None,
    service_topic: str | None = None,
    topic_confidence: float = 0.0,
) -> dict:
    catalog = _read_json_dict(_client_json_path(client_id, "service_catalog.json"))
    return resolve_catalog_match(
        q,
        catalog,
        exclude_service_ids=exclude_service_ids,
        service_topic=service_topic,
        topic_confidence=topic_confidence,
        strong_match_min=float(PRICE_SERVICE_MATCH_STRONG),
    )


def match_catalog_for_implant_group_overview(q: str, *, client_id: str | None) -> dict:
    """Generic implant price overview: prefer implant services; no typo-only containment."""
    q0 = (q or "").strip()
    exclude: frozenset[str] = frozenset()
    if not KT_EXPLICIT_RE.search(q0):
        exclude = frozenset({"tomography"})
    m = match_service_from_catalog(
        q0,
        client_id=client_id,
        exclude_service_ids=exclude,
        service_topic="implantation",
        topic_confidence=0.9,
    )
    return {**m, "containment_eligible": False}


def compute_retrieval_scope_with_conflict_guard(
    *,
    scope_topic_candidate: str | None,
    q: str,
    client_id: str | None,
    decision: Any | None = None,
) -> tuple[str | None, str]:
    """Legacy no-op after embed retrieval removal."""
    raw = (scope_topic_candidate or "").strip().lower()
    if not raw or raw == "unknown":
        return None, "none"

    q0 = (q or "").strip()
    match = match_service_from_catalog(q0, client_id=client_id)
    if match.get("containment_eligible"):
        return None, "catalog_match"
    _ = decision
    return raw, "none"


def _service_from_session_context(sid: str | None, client_id: str | None) -> dict | None:
    """Ищет услугу в каталоге по current_doc_id или last_catalog_service_id из сессии.

    Возвращает dict {service_id, service, price_key, price_ref, price_item} или None.
    Используется как fallback когда пользователь спрашивает цену без названия услуги,
    но до этого уже смотрел конкретную услугу.
    """
    if not sid:
        return None
    st = mem_get(sid)
    catalog = _read_json_dict(_client_json_path(client_id, "service_catalog.json"))
    if not isinstance(catalog, dict):
        return None

    def _make_result(service_id: str, entry: dict, context_doc_id: str | None) -> dict:
        price_key = entry.get("price_key")
        price_ref = entry.get("price_ref")
        pb_avail = _service_in_pricebook(client_id, service_id, price_key)
        price_item = None
        if not pb_avail:
            prices = _read_json_dict(_client_json_path(client_id, "prices.json"))
            price_item = prices.get(price_key) if isinstance(prices, dict) and price_key else None
        return {
            "service_id": str(service_id),
            "service": entry,
            "price_key": price_key,
            "price_ref": price_ref,
            "price_item": price_item if isinstance(price_item, dict) else None,
            "pricebook_available": pb_avail,
            "context_doc_id": context_doc_id,
        }

    # Попытка 1: last_subject (диалоговый фокус; приоритет над устаревшим catalog id)
    sub = st.get("last_subject")
    age = int(st.get("subject_turn_age") or 0)
    if isinstance(sub, dict) and age <= int(THRESHOLDS.follow_up.max_subject_turn_age):
        sub_sid = (sub.get("service_id") or "").strip()
        if sub_sid and sub_sid in catalog:
            entry = catalog[sub_sid]
            if isinstance(entry, dict) and bool(entry.get("active", True)):
                return _make_result(sub_sid, entry, None)

    # Попытка 2: по current_doc_id (сервисы с md_entry_ref)
    current_doc_id = (st.get("current_doc_id") or "").strip()
    if current_doc_id:
        doc_norm = current_doc_id.removesuffix(".md")
        for service_id, entry in catalog.items():
            if not isinstance(entry, dict) or not bool(entry.get("active", True)):
                continue
            md_ref = (entry.get("md_entry_ref") or "").strip()
            if not md_ref:
                continue
            if md_ref.removesuffix(".md") == doc_norm:
                return _make_result(service_id, entry, current_doc_id)

    # Попытка 3: по last_catalog_service_id (сервисы без md_entry_ref, напр. КТ, отбеливание)
    last_svc_id = (st.get("last_catalog_service_id") or "").strip()
    if last_svc_id and last_svc_id in catalog:
        entry = catalog[last_svc_id]
        if isinstance(entry, dict) and bool(entry.get("active", True)):
            return _make_result(last_svc_id, entry, None)

    return None


def price_session_ctx_matches_catalog_leader(match: dict[str, Any], ctx: dict[str, Any]) -> bool:
    """Если каталог нашёл лучшего кандидата по service_id — session fallback допустим только при том же id.

    Иначе пользователь явно назвал другую услугу (даже при низком match score), и подставлять
    last_catalog_service_id нельзя (виниры → импланты).
    """
    mid = (match.get("matched_service_id") or "").strip()
    if not mid:
        return True
    return mid == (ctx.get("service_id") or "").strip()


def _price_query_names_explicit_service(q: str) -> bool:
    """В ценовом вопросе есть название услуги, а не только «а сколько стоит»."""
    return price_query_has_explicit_service_object(q)


def price_lookup_allows_session_context(q: str, match: dict[str, Any], ctx: dict[str, Any]) -> bool:
    """Session fallback для цены: тот же service_id в каталоге или короткое продолжение без нового объекта."""
    if is_vague_price_followup(q) and is_weak_catalog_price_token_match(match, q):
        return True
    if not price_session_ctx_matches_catalog_leader(match, ctx):
        return False
    if not (match.get("matched_service_id") or "").strip() and _price_query_names_explicit_service(q):
        return False
    return True


def _dialog_focus_for_price_route(
    q: str,
    *,
    sid: str | None,
    client_id: str | None,
) -> DialogFocusDecision | None:
    return dialog_focus_for_turn(q, sid=sid, client_id=client_id)


def _dialog_focus_price_intent(focus: DialogFocusDecision | None) -> bool:
    return bool(focus and focus.attribute == "price")


def _dialog_focus_allows_price_session_context(
    focus: DialogFocusDecision | None,
    ctx: dict[str, Any],
) -> bool:
    if not _dialog_focus_price_intent(focus) or not focus:
        return False
    if focus.explicit_topic_change:
        return False
    resolved = (focus.resolved_service_id or focus.focus_service_id or "").strip()
    if not resolved:
        return False
    return resolved == str(ctx.get("service_id") or "").strip()


def _try_price_session_route(
    q: str,
    match: dict[str, Any],
    ctx: dict[str, Any],
    *,
    intent: str,
    sid: str | None,
    client_id: str | None,
    fallback_reason_default: str = "context_session",
    dialog_focus: DialogFocusDecision | None = None,
) -> dict | None:
    legacy_allowed = price_lookup_allows_session_context(q, match, ctx)
    focus_allowed = _dialog_focus_allows_price_session_context(dialog_focus, ctx)
    if not (legacy_allowed or focus_allowed):
        return None
    if focus_allowed and not legacy_allowed:
        fallback_reason_default = "dialog_focus"
    pi = ctx.get("price_item")
    pr = ctx.get("price_ref")
    rs = "catalog"
    rs, pr2, fb = _resolve_price_lookup_route(
        route_source=rs,
        price_ref=pr,
        price_item=pi,
        pricebook_available=bool(ctx.get("pricebook_available")),
        q=q,
        sid=sid,
        client_id=client_id,
    )
    fb_final = fb or fallback_reason_default
    base = {
        "intent": intent,
        "route_source": rs,
        "matched_service_id": ctx["service_id"],
        "service": ctx["service"],
        "match_score": 1.0,
        "is_confident": True,
        "price_key": ctx.get("price_key"),
        "price_ref": pr2,
        "price_item": pi,
        "context_doc_id": ctx.get("context_doc_id"),
        "fallback_reason": fb_final,
    }
    if _price_route_is_matched(rs, pr2):
        return {"mode": "matched", **base}
    return {
        "mode": "unavailable",
        "fallback_reason": fb_final or "price_not_in_catalog",
        **base,
    }


def select_price_service_route(
    q: str, *, client_id: str | None, sid: str | None = None, intent_override: str | None = None
) -> dict:
    dialog_focus = _dialog_focus_for_price_route(q, sid=sid, client_id=client_id)
    if intent_override in ("price_lookup", "price_concern"):
        intent = intent_override
    else:
        intent = classify_price_route_intent(q, client_id=client_id, sid=sid)
    if intent == "other" and _dialog_focus_price_intent(dialog_focus):
        intent = "price_lookup"
    if intent == "other":
        return {"mode": "other", "intent": intent}
    if is_crown_inclusion_content_query(q):
        return {"mode": "other", "intent": "other"}

    scope = (
        detect_price_scope(q, client_id=client_id)
        if intent == "price_lookup"
        else PriceScopeResult.none()
    )
    if intent == "price_lookup":
        situation, vague_carry = _patient_situation_for_turn(q, sid=sid, client_id=client_id)
        scope = merge_price_scope(
            scope,
            situation,
            client_id=client_id,
            vague_price_carry=vague_carry,
        )
    exclude_ids = scope_catalog_excludes(scope)
    topic_hint = scope_implant_topic(scope)
    match: dict | None = None

    if intent == "price_lookup" and scope.protocol_service_id:
        catalog = _read_json_dict(_client_json_path(client_id, "service_catalog.json"))
        proto = catalog.get(scope.protocol_service_id)
        if isinstance(proto, dict):
            match = {
                "matched_service_id": scope.protocol_service_id,
                "service": proto,
                "match_score": 1.0,
                "is_confident": True,
            }

    if match is None:
        match = match_service_from_catalog(
            q,
            client_id=client_id,
            exclude_service_ids=exclude_ids if exclude_ids else None,
            service_topic=topic_hint,
            topic_confidence=0.9 if topic_hint else 0.0,
        )

    group_id = scope.group_id if intent == "price_lookup" else None
    if intent == "price_lookup" and group_id and client_id:
        from core.clinic_policies_loader import find_service_alternative

        if find_service_alternative(q, client_id):
            return {
                "mode": "clarify",
                "intent": intent,
                "fallback_reason": "service_not_offered",
                **match,
            }
    if intent == "price_lookup" and group_id:
        overview_match = (
            match_catalog_for_implant_group_overview(q, client_id=client_id)
            if group_id == "implantation"
            else match
        )
        return {
            "mode": "group_overview",
            "group_id": group_id,
            "intent": intent,
            **overview_match,
        }
    if intent == "price_lookup" and is_vague_price_followup(q):
        scope_resolved_vague_price = bool(
            scope.protocol_service_id
            and (match.get("matched_service_id") or "") == scope.protocol_service_id
            and match.get("is_confident")
        )
        if not scope_resolved_vague_price:
            ctx = _service_from_session_context(sid, client_id)
            if ctx:
                session_route = _try_price_session_route(
                    q,
                    match,
                    ctx,
                    intent=intent,
                    sid=sid,
                    client_id=client_id,
                    dialog_focus=dialog_focus,
                )
                if session_route:
                    return session_route
            if is_weak_catalog_price_token_match(match, q) or (
                match.get("is_confident") and not price_query_has_explicit_service_object(q)
            ):
                return {
                    "mode": "clarify",
                    "intent": intent,
                    "fallback_reason": "price_clarify_no_context",
                    **match,
                }
    if not match.get("matched_service_id"):
        if intent == "price_lookup" and is_generic_implant_price_query(q):
            return {
                "mode": "group_overview",
                "group_id": "implantation",
                "intent": intent,
                **match_catalog_for_implant_group_overview(q, client_id=client_id),
            }
        ctx = _service_from_session_context(sid, client_id)
        if ctx and intent == "price_lookup" and (
            price_lookup_allows_session_context(q, match, ctx)
            or _dialog_focus_allows_price_session_context(dialog_focus, ctx)
        ):
            session_route = _try_price_session_route(
                q,
                match,
                ctx,
                intent=intent,
                sid=sid,
                client_id=client_id,
                dialog_focus=dialog_focus,
            )
            if session_route:
                return session_route
        if continuation_only_phrase(q) and not session_has_continuation_context(
            mem_get(sid) if sid else {}
        ):
            return {
                "mode": "clarify",
                "intent": intent,
                "fallback_reason": "continuation_no_context",
                **match,
            }
        return {
            "mode": "clarify",
            "intent": intent,
            "fallback_reason": "service_not_found",
            **match,
        }
    if not match.get("is_confident"):
        ctx = _service_from_session_context(sid, client_id)
        if ctx and intent == "price_lookup" and (
            price_lookup_allows_session_context(q, match, ctx)
            or _dialog_focus_allows_price_session_context(dialog_focus, ctx)
        ):
            session_route = _try_price_session_route(
                q,
                match,
                ctx,
                intent=intent,
                sid=sid,
                client_id=client_id,
                dialog_focus=dialog_focus,
            )
            if session_route:
                return session_route
        if continuation_only_phrase(q) and not session_has_continuation_context(
            mem_get(sid) if sid else {}
        ):
            return {
                "mode": "clarify",
                "intent": intent,
                "fallback_reason": "continuation_no_context",
                **match,
            }
        return {
            "mode": "clarify",
            "intent": intent,
            "fallback_reason": "low_match_score",
            **match,
        }
    prices = _read_json_dict(_client_json_path(client_id, "prices.json"))
    service = match.get("service") or {}
    price_ref = service.get("price_ref")
    price_key = service.get("price_key")
    matched_sid = str(match.get("matched_service_id") or "")
    pb_avail = _service_in_pricebook(client_id, matched_sid, price_key)
    price_item = None
    if not pb_avail:
        price_item = prices.get(price_key) if isinstance(prices, dict) and price_key else None
    route_source = "catalog"
    if intent == "price_concern":
        route_source = "catalog"
    fallback_reason: str | None = None
    if intent == "price_lookup":
        route_source, price_ref, fallback_reason = _resolve_price_lookup_route(
            route_source=route_source,
            price_ref=price_ref,
            price_item=price_item if isinstance(price_item, dict) else None,
            pricebook_available=pb_avail,
            q=q,
            sid=sid,
            client_id=client_id,
        )
        if continuation_only_phrase(q) and not price_ref and price_item is None and not pb_avail:
            return {
                "mode": "clarify",
                "intent": intent,
                "fallback_reason": "continuation_no_context",
                **match,
            }
        if fallback_reason == "price_not_in_catalog":
            return {
                "mode": "unavailable",
                "intent": intent,
                "fallback_reason": fallback_reason,
                **match,
            }
    return {
        "mode": "matched",
        "intent": intent,
        "route_source": route_source,
        "price_key": price_key,
        "price_ref": price_ref,
        "price_item": price_item if isinstance(price_item, dict) else None,
        "fallback_reason": fallback_reason,
        **match,
    }


def build_price_route_for_service_id(
    service_id: str,
    *,
    client_id: str | None,
    sid: str | None = None,
    q: str = "",
) -> dict | None:
    """Deterministic price route for widget ref `price:{service_id}` (catalog match score = 1)."""
    sid_clean = (service_id or "").strip()
    if not sid_clean:
        return None
    catalog = _read_json_dict(_client_json_path(client_id, "service_catalog.json"))
    if not isinstance(catalog, dict):
        return None
    entry = catalog.get(sid_clean)
    if not isinstance(entry, dict) or not bool(entry.get("active", True)):
        return None
    prices = _read_json_dict(_client_json_path(client_id, "prices.json"))
    price_key = entry.get("price_key")
    price_ref = entry.get("price_ref")
    pb_avail = _service_in_pricebook(client_id, sid_clean, price_key)
    price_item = None
    if not pb_avail:
        price_item = prices.get(price_key) if isinstance(prices, dict) and price_key else None
    q_eff = (q or "").strip() or f"Сколько стоит {entry.get('title') or sid_clean}?"
    route_source = "catalog"
    route_source, price_ref, fallback_reason = _resolve_price_lookup_route(
        route_source=route_source,
        price_ref=price_ref,
        price_item=price_item if isinstance(price_item, dict) else None,
        pricebook_available=pb_avail,
        q=q_eff,
        sid=sid,
        client_id=client_id,
    )
    return {
        "mode": "matched",
        "intent": "price_lookup",
        "route_source": route_source,
        "matched_service_id": sid_clean,
        "service": entry,
        "match_score": 1.0,
        "is_confident": True,
        "price_key": price_key,
        "price_ref": price_ref,
        "price_item": price_item if isinstance(price_item, dict) else None,
        "fallback_reason": fallback_reason or "price_ref_click",
    }


def select_catalog_content_route(q: str, *, client_id: str | None) -> dict:
    # DEPRECATED — replaced by source_routing.route_source (A3 catalog branches); see DEPRECATED.md, removed in PR #2.1
    """Информационный маршрут по service_catalog (без ценового интента).

    Гибрид:
    - если сервис уверенно распознан и у него есть MD-страница (md_entry_ref),
      сначала пробуем route в конкретный md (md_first);
    - если MD нет, но есть facts, отвечаем facts-карточкой;
    - иначе mode=none и дальше общий retrieval.
    """
    match = match_service_from_catalog(q, client_id=client_id)
    if not match.get("matched_service_id") or not match.get("is_confident"):
        return {"mode": "none"}
    service = match.get("service") or {}
    md_raw = service.get("md_entry_ref")
    if isinstance(md_raw, str) and md_raw.strip():
        return {
            "mode": "md_first",
            "matched_service_id": match.get("matched_service_id"),
            "match_score": match.get("match_score"),
            "service": service,
            "md_entry_ref": md_raw.strip(),
        }
    facts = [str(x).strip() for x in (service.get("facts") or []) if str(x).strip()]
    if not facts:
        return {"mode": "none"}
    return {
        "mode": "facts",
        "matched_service_id": match.get("matched_service_id"),
        "match_score": match.get("match_score"),
        "service": service,
    }
