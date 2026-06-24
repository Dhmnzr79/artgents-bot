from __future__ import annotations

import json
import os
from typing import Any

from flask import request

from core.client_config_loader import load_ui_bundle, ui_menu_to_payload
from logging_setup import emit_bot_event, get_logger
from core.metadata_first_observability import (
    merge_retrieval_debug_meta,
    metadata_first_turn_details,
    record_decision_frame_ctx,
    record_selection_metadata,
)
from core.routing_loader import THRESHOLDS
from query_selector import compute_retrieval_scope_with_conflict_guard
from retriever import chunk_info
from ux_builder import format_price_answer_from_item

logger = get_logger("bot")


def decision_dump(decision) -> dict[str, Any] | None:
    return decision.model_dump() if decision is not None else None


def get_last_content_ui_payload_compat(sid: str) -> dict | None:
    import session as session_mod

    fn = getattr(session_mod, "get_last_content_ui_payload", None)
    if callable(fn):
        return fn(sid)
    return None


def with_default_anchor(md_entry_ref: str) -> str:
    ref = (md_entry_ref or "").strip()
    if not ref:
        return ""
    return ref if "#" in ref else f"{ref}#korotko"


def load_prices_for_client(client_id: str | None) -> dict:
    from core.client_runtime import client_pack_dir

    p = os.path.join(client_pack_dir(client_id), "prices.json")
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def service_price_line_for_content(service: dict, client_id: str | None) -> str | None:
    if not isinstance(service, dict):
        return None
    if str(service.get("price_display") or "").strip().lower() != "always":
        return None
    price_key = str(service.get("price_key") or "").strip()
    if not price_key:
        return None
    title = str(service.get("title") or price_key).strip()

    from core.pricebook_loader import load_pricebook_service
    from core.price_offers import format_rub

    entry = load_pricebook_service(client_id, price_key)
    if entry is not None:
        if entry.price_model == "simple" and entry.price is not None:
            return format_price_answer_from_item(
                {
                    "name": entry.display_name,
                    "price_type": entry.price.price_type,
                    "value": entry.price.value,
                    "currency": entry.price.currency,
                    "note": entry.price.note,
                },
                title_fallback=title,
            )
        if entry.variants:
            min_total = min(v.total for v in entry.variants)
            label = str(entry.display_name or title).strip()
            return f"{label} — от {format_rub(min_total)}."

    prices = load_prices_for_client(client_id)
    price_item = prices.get(price_key) if isinstance(prices, dict) else None
    if not isinstance(price_item, dict):
        return None
    return format_price_answer_from_item(price_item, title_fallback=title)


def apply_content_retrieval_scope_ctx(
    scope_topic_candidate: str | None,
    q: str,
    client_id: str,
    decision: Any | None = None,
) -> str | None:
    eff, gr = compute_retrieval_scope_with_conflict_guard(
        scope_topic_candidate=scope_topic_candidate,
        q=q,
        client_id=client_id,
        decision=decision,
    )
    if (
        bool(THRESHOLDS.metadata_first.soft_scope_enabled)
        and gr == "none"
        and eff is not None
    ):
        request.ctx["retrieval_scope_topic"] = None
        request.ctx["retrieval_scope_guard_reason"] = "metadata_first_soft"
        request.ctx["retrieval_scope_topic_candidate"] = eff
        return None
    request.ctx["retrieval_scope_topic"] = eff
    request.ctx["retrieval_scope_guard_reason"] = gr
    if eff is not None:
        request.ctx["retrieval_scope_topic_candidate"] = eff
    return eff


def apply_metadata_first_after_content_route(
    *,
    decision: Any,
    retrieval_debug_meta: dict | None,
    selected_doc_id: str | None,
    selected_chunk: dict | None,
    selected_route: str | None,
    alias_candidate: dict | None,
) -> None:
    """Merge §7 telemetry into request.ctx after content arbiter / retrieval."""
    from arbiter import canonical_ref, ref_from_chunk

    record_decision_frame_ctx(decision)
    dbg = dict(retrieval_debug_meta) if isinstance(retrieval_debug_meta, dict) else {}
    if isinstance(alias_candidate, dict) and hasattr(request, "ctx"):
        leader = alias_candidate.get("leader_chunk") or alias_candidate.get("leader")
        score = alias_candidate.get("alias_score")
        request.ctx["alias_hit"] = bool(leader)
        if score is not None:
            request.ctx["alias_boost"] = round(float(score), 4)
    if isinstance(selected_chunk, dict) and isinstance(alias_candidate, dict):
        pool_ref = str(dbg.get("pool_winner_ref") or "").strip()
        sel_ref = ref_from_chunk(selected_chunk) or ""
        alias_ch = alias_candidate.get("leader_chunk")
        alias_ref = ref_from_chunk(alias_ch) if isinstance(alias_ch, dict) else ""
        if (
            not dbg.get("alias_fallback_used")
            and pool_ref
            and sel_ref
            and alias_ref
            and canonical_ref(sel_ref) == canonical_ref(alias_ref)
            and canonical_ref(sel_ref) != canonical_ref(pool_ref)
        ):
            dbg["alias_fallback_used"] = True
            dbg["selected_source"] = "alias_fallback"
    merge_retrieval_debug_meta(dbg)
    record_selection_metadata(
        selected_doc_id=selected_doc_id,
        selected_chunk=selected_chunk,
        selected_route=selected_route,
    )


def guided_menu_payload(sid: str, client_id: str | None) -> dict:
    ui = load_ui_bundle(client_id)
    return ui_menu_to_payload(ui.guided_menu, sid=sid, client_id=client_id)


def ru_doctor_count_word(n: int) -> str:
    n_abs = abs(int(n))
    n10 = n_abs % 10
    n100 = n_abs % 100
    if n10 == 1 and n100 != 11:
        return "врач"
    if n10 in (2, 3, 4) and n100 not in (12, 13, 14):
        return "врача"
    return "врачей"


def slim_content_arbiter_details(details: dict) -> dict:
    if not isinstance(details, dict):
        return {}
    out = dict(details)
    cands = out.get("candidates")
    if isinstance(cands, dict):
        c2 = dict(cands)
        ret = c2.get("retrieval_candidate")
        if isinstance(ret, dict):
            r2 = dict(ret)
            r2.pop("chunk", None)
            c2["retrieval_candidate"] = r2
        alias_c = c2.get("alias_candidate")
        if isinstance(alias_c, dict):
            a2 = dict(alias_c)
            leader = a2.get("leader")
            if isinstance(leader, dict):
                leader2 = dict(leader)
                leader2.pop("text", None)
                a2["leader"] = leader2
            a2.pop("leader_chunk", None)
            c2["alias_candidate"] = a2
        out["candidates"] = c2
    return out


def log_selection(
    *,
    q: str,
    chosen_chunk: dict,
    chosen_score,
    original_top_score,
    rerank_applied: bool,
) -> None:
    chosen = chunk_info(chosen_chunk, chosen_score)
    from logging_setup import log_json

    log_json(
        logger,
        "selection",
        question=q[:200],
        original_top_score=(
            round(float(original_top_score), 4) if original_top_score is not None else None
        ),
        rerank_applied=bool(rerank_applied),
        chosen=chosen,
    )
    emit_bot_event(
        logger,
        "retrieval_selected",
        status="chunk",
        details={
            "question_preview": (q or "")[:200],
            "original_top_score": (
                round(float(original_top_score), 4) if original_top_score is not None else None
            ),
            "rerank_applied": bool(rerank_applied),
            "chosen": chosen,
        },
    )
