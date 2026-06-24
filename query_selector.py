"""Chunk selection orchestration for /ask retrieval path."""
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from config import (
    COMMERCIAL_INFO_RE,
    CONSULTATION_QUERY_RE,
    KT_EXPLICIT_RE,
    LOW_SCORE_THRESHOLD,
    QUERY_REWRITE_ON,
    DEFAULT_CLIENT_ID,
    PRICE_CONCERN_RE,
    PRICE_LOOKUP_RE,
    PRICE_SERVICE_MATCH_STRONG,
)
from core.candidate_builder import (
    apply_metadata_candidate_boosts,
    chunk_ref_short,
    effective_scope_topic_for_retrieval,
    finalize_selection_selected_by,
    infer_selected_source,
    merge_alias_into_candidate_pool,
    metadata_context_from_decision,
    resolve_alias_for_turn,
)
from core.catalog_match import resolve_catalog_match
from core.client_config_loader import resolve_pack_client_id
from core.follow_up_rewrite import follow_up_turn_meta, get_follow_up_turn_ctx
from core.retrieval_rerank import maybe_rerank_top
from core.routing_loader import THRESHOLDS
from core.price_offers import (
    is_crown_inclusion_content_query,
    is_generic_implant_price_query,
    is_one_stage_price_query,
    resolve_implant_group_overview,
    should_offer_unit_clarify,
)
from core.pricebook_loader import load_pricebook_service
from core.turn_timing import timed_stage
from llm import classify_price_intent, rewrite_query_for_retrieval
from session import mem_get
from policy import (
    contacts_intent,
    continuation_only_phrase,
    pick_contacts_chunk,
    pick_prices_chunk,
    price_intent,
    session_has_continuation_context,
)
from retriever import (
    broad_query_detect,
    chunk_info,
    is_point_literal_query,
    merge_retrieval_candidates,
    normalize_retrieval_query,
    prefer_overview_if_broad,
    retrieve,
)

def _service_in_pricebook(
    client_id: str | None,
    service_id: str | None,
    price_key: str | None,
) -> bool:
    sid = (service_id or price_key or "").strip()
    if not sid:
        return False
    return load_pricebook_service(client_id, sid) is not None


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
    """Return selection result for /ask.

    mode:
      - no_candidates
      - low_score
      - chunk
    """
    q_user = (q or "").strip()

    fu_ctx = get_follow_up_turn_ctx(q_user, sid=sid, client_id=client_id)
    follow_up_mode = bool(fu_ctx and fu_ctx.follow_up_mode)

    # Интенты и алиасы — только по исходному вопросу пациента (не по rewrite).
    q_policy = normalize_retrieval_query(q_user) or q_user

    meta_ctx = metadata_context_from_decision(decision, q=q_policy)
    eff_scope = effective_scope_topic_for_retrieval(
        scope_topic, meta_ctx, follow_up_mode=follow_up_mode
    )

    tel_p: dict[str, Any] = {}
    tel_s: dict[str, Any] = {}
    with timed_stage("retrieval_block_ms"):
        if follow_up_mode and fu_ctx is not None:
            q_rewrite_eff = fu_ctx.rewritten_query
            primary = retrieve(
                q_rewrite_eff,
                topk=8,
                client_id=client_id,
                scope_topic=eff_scope,
                telemetry=tel_p,
            )
        else:
            with ThreadPoolExecutor(max_workers=2) as pool:
                primary_future = pool.submit(
                    retrieve,
                    q_user,
                    topk=8,
                    client_id=client_id,
                    scope_topic=eff_scope,
                    telemetry=tel_p,
                )
                rewrite_future = None
                if sid and QUERY_REWRITE_ON:
                    rewrite_future = pool.submit(
                        rewrite_query_for_retrieval,
                        sid,
                        q_user,
                        client_id=client_id,
                    )
                primary = primary_future.result()
                q_rewrite_eff = (
                    rewrite_future.result() if rewrite_future is not None else q_user
                )

    nu = (normalize_retrieval_query(q_user) or q_user).strip().lower()
    nr = (normalize_retrieval_query(q_rewrite_eff) or q_rewrite_eff).strip().lower()

    nr_meta = normalize_retrieval_query(q_rewrite_eff) or q_rewrite_eff
    base_meta = {
        "query_user_raw": q_user[:200],
        "query_rewrite_effective": q_rewrite_eff[:200],
        "query_normalized_user": q_policy[:200],
        "query_normalized_rewrite": nr_meta[:200],
        "rewrite_applied": bool(q_rewrite_eff.strip().lower() != q_user.strip().lower()),
        **follow_up_turn_meta(fu_ctx),
    }
    secondary: list = []
    if nr != nu:
        secondary = retrieve(
            q_rewrite_eff,
            topk=8,
            client_id=client_id,
            silent=True,
            scope_topic=eff_scope,
            telemetry=tel_s,
        )
    widen_fb = bool(tel_p.get("scope_widen_fallback")) or bool(tel_s.get("scope_widen_fallback"))

    # Defaults so early returns (e.g. no_candidates) can call _dm() before alias resolution runs.
    alias_leader: dict | None = None
    alias_score = 0.0
    alias_diag: dict[str, Any] = {}
    boost_tel: dict[str, Any] = {}

    def _dm(extra: dict) -> dict:
        tel = {
            k: v
            for k, v in alias_diag.items()
            if k.startswith("alias_") or k.startswith("old_")
        }
        return {
            **base_meta,
            **boost_tel,
            **extra,
            **tel,
            "scope_widen_fallback": widen_fb,
            "retrieval_scope_topic_effective": eff_scope,
        }

    def _selection_telemetry(chunk: dict | None, *, selected_by: str, **extra: Any) -> dict[str, Any]:
        sb = finalize_selection_selected_by(chunk, selected_by=selected_by)
        out = {
            "selected_by": sb,
            "selected_source": infer_selected_source(chunk, selected_by=selected_by),
            "pool_winner_ref": chunk_ref_short(chunk) if isinstance(chunk, dict) else None,
            **extra,
        }
        if "alias_fallback_used" not in out:
            out["alias_fallback_used"] = sb == "soft_alias_assist" or out.get("selected_source") == "alias_fallback"
        return out

    cands = merge_retrieval_candidates(primary, secondary)[:8]
    cands = prefer_overview_if_broad(cands, broad_query_detect(q_policy))
    top_semantic_raw: float | None = None
    if cands:
        top_semantic_raw = float(cands[0].get("_score") or 0.0)
        cands, boost_tel = apply_metadata_candidate_boosts(
            cands, ctx=meta_ctx, client_id=client_id
        )
        boost_tel["top_semantic_raw"] = round(top_semantic_raw, 4)
    if not cands:
        return {
            "mode": "no_candidates",
            "debug_meta": _dm({"top_score": None, **boost_tel}),
        }

    is_contacts = contacts_intent(q_policy)
    is_price = price_intent(q_policy)
    alias_leader, alias_score, alias_diag = resolve_alias_for_turn(
        q_policy,
        ctx=meta_ctx,
        client_id=client_id,
        top_semantic_score=top_semantic_raw,
        follow_up_mode=follow_up_mode,
    )
    cands, pool_tel = merge_alias_into_candidate_pool(
        cands,
        alias_leader=alias_leader,
        alias_score=alias_score,
    )
    boost_tel.update(pool_tel)

    tier = str(alias_diag.get("alias_decision") or "")
    sim_raw = float(alias_diag.get("alias_similarity") or 0.0)
    ath = THRESHOLDS.alias
    alias_strong = bool(
        alias_leader
        and alias_score >= float(ath.strong_effective_min)
        and (
            tier in ("exact", "near_exact")
            or (
                tier == "embed_high"
                and sim_raw >= float(ath.embedding_strong_cosine_min)
            )
            or (
                tier == "rescue"
                and sim_raw >= float(ath.embedding_strong_cosine_min)
            )
        )
    )

    top_score = float(cands[0].get("_score") or 0.0)
    allow_low = alias_strong or (is_contacts and pick_contacts_chunk(cands)) or (
        is_price and pick_prices_chunk(cands)
    )
    if top_score < LOW_SCORE_THRESHOLD and not allow_low:
        if alias_leader and alias_score >= float(THRESHOLDS.alias.soft_assist_min):
            soft = dict(alias_leader)
            soft["_alias_score"] = round(alias_score, 4)
            soft["_score"] = round(float(alias_score), 4)
            soft["_pool_sources"] = ["alias"]
            return {
                "mode": "chunk",
                "chunk": soft,
                "rerank_applied": False,
                "debug_meta": _dm(
                    _selection_telemetry(
                        soft,
                        selected_by="soft_alias_assist",
                        alias_fallback_used=True,
                        top_score=round(top_score, 4),
                        threshold=LOW_SCORE_THRESHOLD,
                        alias_score=round(float(alias_score or 0.0), 4),
                        is_contacts=bool(is_contacts),
                        is_price=bool(is_price),
                    )
                ),
            }
        top_cinfo = chunk_info(cands[0], cands[0].get("_score")) if cands else None
        return {
            "mode": "low_score",
            "debug_meta": _dm(
                {
                    "top_score": round(top_score, 4),
                    "threshold": LOW_SCORE_THRESHOLD,
                    "alias_score": round(float(alias_score or 0.0), 4),
                    "is_contacts": bool(is_contacts),
                    "is_price": bool(is_price),
                    "top_candidate": top_cinfo,
                }
            ),
        }

    if is_contacts:
        picked = pick_contacts_chunk(cands)
        if picked is not None:
            return {
                "mode": "chunk",
                "chunk": picked,
                "rerank_applied": False,
                "debug_meta": _dm(
                    _selection_telemetry(
                        picked,
                        selected_by="contacts",
                        top_score=round(top_score, 4),
                        alias_score=round(float(alias_score or 0.0), 4),
                    )
                ),
            }

    if is_price:
        picked = pick_prices_chunk(cands)
        if picked is not None:
            return {
                "mode": "chunk",
                "chunk": picked,
                "rerank_applied": False,
                "debug_meta": _dm(
                    _selection_telemetry(
                        picked,
                        selected_by="price",
                        top_score=round(top_score, 4),
                        alias_score=round(float(alias_score or 0.0), 4),
                    )
                ),
            }

    top = cands[0]
    score_gap = (
        abs(float(cands[0].get("_score") or 0.0) - float(cands[1].get("_score") or 0.0))
        if len(cands) >= 2
        else 1.0
    )
    top, rerank_tel = maybe_rerank_top(
        q_user,
        cands,
        point_literal=is_point_literal_query(q_policy),
        alias_strong=alias_strong,
        alias_decision=tier,
    )
    rerank_applied = bool(rerank_tel.get("rerank_applied"))

    return {
        "mode": "chunk",
        "chunk": top,
        "rerank_applied": rerank_applied,
        "debug_meta": _dm(
            _selection_telemetry(
                top,
                selected_by="semantic",
                top_score=round(top_score, 4),
                score_gap=round(float(score_gap), 4),
                alias_score=round(float(alias_score or 0.0), 4),
                **rerank_tel,
            )
        ),
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
    """Вернуть эффективный topic scope для retrieval и причину гарда.

    Порядок: containment catalog (как в A3) блокирует scope; затем сильный alias.
    ``guard_reason``: ``catalog_match`` | ``alias_hit`` | ``none``.
    """
    raw = (scope_topic_candidate or "").strip().lower()
    if not raw or raw == "unknown":
        return None, "none"

    q0 = (q or "").strip()
    match = match_service_from_catalog(q0, client_id=client_id)
    if match.get("containment_eligible"):
        return None, "catalog_match"

    q_pol = normalize_retrieval_query(q0) or q0
    meta_ctx = metadata_context_from_decision(decision, q=q_pol)
    _leader, alias_sc, _alias_diag = resolve_alias_for_turn(
        q_pol,
        ctx=meta_ctx,
        client_id=client_id,
        top_semantic_score=None,
    )
    alias_val = float(alias_sc or 0.0)
    if alias_val >= float(THRESHOLDS.alias.scope_guard_min):
        return None, "alias_hit"

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

    # Попытка 1: по current_doc_id (сервисы с md_entry_ref)
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

    # Попытка 2: по last_catalog_service_id (сервисы без md_entry_ref, напр. КТ, отбеливание)
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
    if continuation_only_phrase(q):
        return False
    qn = re.sub(r"\s+", " ", (q or "").strip(), flags=re.U)
    stripped = PRICE_LOOKUP_RE.sub("", qn).strip()
    stripped = re.sub(r"^(?:а|и|ну)\s+", "", stripped, flags=re.I | re.U).strip()
    stripped = re.sub(r"^[\s?.!,;:—\-]+", "", stripped).strip()
    tokens = [t for t in re.findall(r"[0-9a-zа-яё]{3,}", stripped, flags=re.I | re.U)]
    return bool(tokens)


def price_lookup_allows_session_context(q: str, match: dict[str, Any], ctx: dict[str, Any]) -> bool:
    """Session fallback для цены: тот же service_id в каталоге или короткое продолжение без нового объекта."""
    if not price_session_ctx_matches_catalog_leader(match, ctx):
        return False
    if not (match.get("matched_service_id") or "").strip() and _price_query_names_explicit_service(q):
        return False
    return True


def select_price_service_route(
    q: str, *, client_id: str | None, sid: str | None = None, intent_override: str | None = None
) -> dict:
    if intent_override in ("price_lookup", "price_concern"):
        intent = intent_override
    else:
        intent = classify_price_route_intent(q, client_id=client_id, sid=sid)
    if intent == "other":
        return {"mode": "other", "intent": intent}
    if is_crown_inclusion_content_query(q):
        return {"mode": "other", "intent": "other"}
    match = match_service_from_catalog(q, client_id=client_id)
    if intent == "price_lookup" and is_one_stage_price_query(q):
        catalog = _read_json_dict(_client_json_path(client_id, "service_catalog.json"))
        one_stage_svc = catalog.get("one_stage") if isinstance(catalog.get("one_stage"), dict) else None
        if one_stage_svc:
            match = {
                "matched_service_id": "one_stage",
                "service": one_stage_svc,
                "match_score": 1.0,
                "is_confident": True,
            }
    group_id = resolve_implant_group_overview(q) if intent == "price_lookup" else None
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
    if not match.get("matched_service_id"):
        if intent == "price_lookup" and is_generic_implant_price_query(q):
            return {
                "mode": "group_overview",
                "group_id": "implantation",
                "intent": intent,
                **match_catalog_for_implant_group_overview(q, client_id=client_id),
            }
        ctx = _service_from_session_context(sid, client_id)
        if ctx and intent == "price_lookup" and price_lookup_allows_session_context(q, match, ctx):
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
            fb_final = fb or "context_session"
            if _price_route_is_matched(rs, pr2):
                return {
                    "mode": "matched",
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
            return {
                "mode": "unavailable",
                "intent": intent,
                "fallback_reason": fb_final or "price_not_in_catalog",
                "matched_service_id": ctx.get("service_id"),
                "service": ctx.get("service"),
                "match_score": 1.0,
                "is_confident": True,
            }
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
        if ctx and intent == "price_lookup" and price_lookup_allows_session_context(q, match, ctx):
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
            fb_final = fb or "context_session"
            if _price_route_is_matched(rs, pr2):
                return {
                    "mode": "matched",
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
            return {
                "mode": "unavailable",
                "intent": intent,
                "fallback_reason": fb_final or "price_not_in_catalog",
                "matched_service_id": ctx.get("service_id"),
                "service": ctx.get("service"),
                "match_score": 1.0,
                "is_confident": True,
            }
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
