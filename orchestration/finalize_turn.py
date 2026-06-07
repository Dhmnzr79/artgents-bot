from __future__ import annotations

import time
from typing import Any

from flask import request

from core.turn_timing import summary_for_turn_complete
from core.metadata_first_observability import (
    metadata_first_response_meta,
    metadata_first_turn_details,
    should_expose_metadata_first_in_response,
)
from core.observability_pii import (
    observability_bot_text,
    observability_turn_preview,
    observability_user_texts,
)
from logging_setup import emit_bot_event, get_logger
from session import get_topic_state, mem_get, record_last_bot_payload

logger = get_logger("bot")


def verifier_trace_flat(v: Any) -> dict[str, Any]:
    """Поля A7 для bot_event details (без лишних ключей)."""
    if not isinstance(v, dict):
        return {}
    return {k: val for k, val in v.items() if str(k).startswith("verifier_")}


def infer_route_from_payload(payload: dict) -> str:
    """Telemetry route для PG/JSONL (не smoke contract)."""
    meta = payload.get("meta") or {}
    if meta.get("error") == "rate_limited":
        return "rate_limited"
    if bool(meta.get("low_score")):
        return "low_score_fallback"
    if bool(meta.get("situation_collect")):
        return "situation_collect"
    if bool(meta.get("lead_flow")):
        return "lead_flow"
    ingress_route = str(meta.get("ingress_route") or "").strip().lower()
    if ingress_route and ingress_route != "normal":
        return f"ingress_{ingress_route}"
    if bool(meta.get("handoff_filter")):
        return "handoff_filter"
    intent = str(meta.get("intent") or "").strip().lower()
    if intent == "catalog_facts":
        return "catalog_facts"
    if intent == "offtopic":
        return "offtopic"
    return "retrieval_chunk"


def finalize_ask(
    payload: dict,
    sid: str,
    q: str,
    *,
    doc_id: str | None = None,
    turn_meta: dict | None = None,
    route: str | None = None,
) -> dict:
    record_last_bot_payload(sid, payload)
    st = mem_get(sid)
    meta = payload.setdefault("meta", {})
    session_turn_count = int(st.get("session_turn_count") or 0)
    if doc_id:
        tstate = get_topic_state(sid, doc_id)
        meta["turn_count"] = int(tstate.get("doc_turn_count") or 0)
    else:
        meta["turn_count"] = session_turn_count
    meta["session_turn_count"] = session_turn_count

    if should_expose_metadata_first_in_response():
        mf = metadata_first_response_meta()
        if mf:
            meta["metadata_first"] = mf

    effective_route = str(route or request.ctx.get("route") or infer_route_from_payload(payload))
    request.ctx["route"] = effective_route
    pmeta = payload.get("meta") or {}
    answer_text = str(payload.get("answer") or "")
    user_text_redacted, user_preview_redacted, pii_withheld = observability_user_texts(
        q or "",
        route=effective_route,
        meta=pmeta,
    )
    bot_text_redacted = observability_bot_text(
        answer_text,
        route=effective_route,
        meta=pmeta,
    )
    if turn_meta and turn_meta.get("interaction") == "user_message":
        safe_turn_meta = dict(turn_meta)
        safe_turn_meta["preview"] = observability_turn_preview(
            q or "",
            route=effective_route,
            meta=pmeta,
        )
        if pii_withheld:
            safe_turn_meta["pii_withheld"] = True
        emit_bot_event(logger, "user_turn_completed", status="ok", details=safe_turn_meta)
    emit_bot_event(
        logger,
        "bot_reply_completed",
        status="ok",
        details={
            "answer_chars": len(answer_text),
            "doc_id": doc_id or pmeta.get("doc_id"),
            "low_score": bool(pmeta.get("low_score")),
            "handoff_filter": bool(pmeta.get("handoff_filter")),
            "lead_flow": bool(pmeta.get("lead_flow")),
            "intent": pmeta.get("intent"),
            "meta_error": pmeta.get("error"),
            "route": effective_route,
            "resolver_used": bool(request.ctx.get("resolver_used")),
            "safety_net_used": bool(request.ctx.get("safety_net_used")),
            **verifier_trace_flat(request.ctx.get("verifier_turn")),
        },
    )
    if turn_meta and turn_meta.get("interaction") == "user_message":
        t0 = request.ctx.get("turn_t0_monotonic")
        lat_ms = None
        if isinstance(t0, (int, float)):
            lat_ms = max(0, int((time.monotonic() - float(t0)) * 1000))
        emit_bot_event(
            logger,
            "turn_complete",
            status="ok",
            details={
                "turn_number": int(meta.get("session_turn_count") or 0),
                "user_text_redacted": user_text_redacted,
                "user_preview_redacted": user_preview_redacted,
                "bot_text_redacted": bot_text_redacted,
                "intent": pmeta.get("intent"),
                "doc_id": doc_id or pmeta.get("doc_id"),
                "route": effective_route,
                "low_score": bool(pmeta.get("low_score")),
                "lead_flow": bool(pmeta.get("lead_flow")),
                "situation_collect": bool(pmeta.get("situation_collect")),
                "lead_step": pmeta.get("lead_step"),
                "handoff_filter": bool(pmeta.get("handoff_filter")),
                "pii_withheld": pii_withheld,
                "answer_chars": len(answer_text),
                "latency_ms": lat_ms,
                "fallback_reason": pmeta.get("fallback_reason"),
                "resolver_used": bool(request.ctx.get("resolver_used")),
                "safety_net_used": bool(request.ctx.get("safety_net_used")),
                "retrieval_scope_topic": request.ctx.get("retrieval_scope_topic"),
                "retrieval_scope_guard_reason": str(
                    request.ctx.get("retrieval_scope_guard_reason") or "none"
                ),
                "retrieval_scope_widen_fallback": bool(
                    request.ctx.get("retrieval_scope_widen_fallback")
                ),
                **metadata_first_turn_details(),
                "legacy_intent": request.ctx.get("legacy_intent"),
                "effective_intent": str(request.ctx.get("effective_intent") or ""),
                "source_route_decision": request.ctx.get("source_route_decision"),
                **verifier_trace_flat(request.ctx.get("verifier_turn")),
                **summary_for_turn_complete(),
            },
        )
    cta = payload.get("cta")
    if isinstance(cta, dict) and (cta.get("action") or cta.get("text")):
        emit_bot_event(
            logger,
            "cta_shown",
            details={
                "action": str(cta.get("action") or ""),
                "text_preview": str(cta.get("text") or "")[:120],
            },
        )
    return payload
