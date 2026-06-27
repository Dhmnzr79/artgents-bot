"""Metadata-First v1 + Retrieval 2.0 pool telemetry (request.ctx + bot_event details)."""
from __future__ import annotations

import os
from typing import Any

from flask import request

from retriever import chunk_doc_type

# Retrieval 2.0 H1–H3.1: unified pool + rerank observability slice.
RETRIEVAL_POOL_CTX_KEYS: tuple[str, ...] = (
    "pool_sources",
    "alias_in_pool",
    "alias_pool_merged",
    "alias_fallback_used",
    "alias_channel_suppressed",
    "selected_source",
    "pool_winner_ref",
    "rerank_trigger_reason",
    "rerank_applied",
    "rerank_fallback_used",
    "rerank_fallback_reason",
)

_METADATA_FIRST_TURN_KEYS: tuple[str, ...] = (
    "route_intent",
    "query_mode",
    "service_topic",
    "candidate_pool_before",
    "candidate_pool_after",
    "selected_doc_id",
    "selected_doc_type",
    "alias_hit",
    "alias_boost",
    "fallback_used",
    "comparison_prefer",
    "comparison_docs_for_topic",
    "metadata_boost_applied",
    "comparison_miss_excluded",
    "comparison_excluded_count",
    "alias_topic_guard_rejected",
    "retrieval_scope_guard_reason",
    "retrieval_scope_topic_candidate",
    "patient_situation_kind",
    "patient_situation_confidence",
    "patient_scope",
    "patient_next_best_action",
    "patient_situation_evidence",
    "patient_situation_source",
    "patient_situation_should_clarify",
    "patient_situation_clarify_question",
    "patient_situation_clarification_reason",
    "patient_situation_carried",
    "patient_situation_carry_age",
    "patient_options_overview_used",
    "patient_options_situation_kind",
    "patient_options_service_ids",
    "patient_options_source",
    "patient_options_skipped",
    "patient_options_strategy",
    *RETRIEVAL_POOL_CTX_KEYS,
)

_MERGE_DEBUG_META_KEYS: tuple[str, ...] = (
    "candidate_pool_before",
    "candidate_pool_after",
    "metadata_boost_applied",
    "comparison_prefer",
    "comparison_docs_for_topic",
    "fallback_used",
    "comparison_miss_excluded",
    "comparison_excluded_count",
    "comparison_miss_alias_rejected",
    "alias_topic_guard_rejected",
    "retrieval_scope_topic_effective",
    "alias_boost_capped",
    "alias_hit",
    "alias_boost",
    *RETRIEVAL_POOL_CTX_KEYS,
)


def should_expose_metadata_first_in_response() -> bool:
    """Test hook: attach telemetry to /ask meta only when E2E_USE_TEST_CLIENT=1."""
    return (os.getenv("E2E_USE_TEST_CLIENT") or "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def retrieval_pool_turn_details(ctx: dict[str, Any] | None = None) -> dict[str, Any]:
    """Retrieval 2.0 pool slice for events / eval (H4)."""
    if ctx is None:
        if not hasattr(request, "ctx"):
            return {}
        ctx = request.ctx
    return {k: ctx[k] for k in RETRIEVAL_POOL_CTX_KEYS if k in ctx}


def metadata_first_turn_details() -> dict[str, Any]:
    """Subset for turn_complete / retrieval events."""
    if not hasattr(request, "ctx"):
        return {}
    ctx = request.ctx
    out = {k: ctx[k] for k in _METADATA_FIRST_TURN_KEYS if k in ctx}
    pool = retrieval_pool_turn_details(ctx)
    if pool:
        out["retrieval_pool"] = pool
    return out


def metadata_first_response_meta() -> dict[str, Any]:
    """Subset of ctx fields for eval runner (`meta.metadata_first`)."""
    return metadata_first_turn_details()


def record_decision_frame_ctx(decision: Any | None) -> None:
    """§7: resolver axes on the turn."""
    if decision is None or not hasattr(request, "ctx"):
        return
    if isinstance(decision, dict):
        ri = str(decision.get("route_intent") or "").strip().lower()
        qm = str(decision.get("query_mode") or "").strip().lower()
        st = str(decision.get("service_topic") or "").strip().lower()
    else:
        ri = str(getattr(decision, "route_intent", None) or "").strip().lower()
        qm = str(getattr(decision, "query_mode", None) or "").strip().lower()
        st = str(getattr(decision, "service_topic", None) or "").strip().lower()
    request.ctx["route_intent"] = ri or None
    request.ctx["query_mode"] = qm or None
    request.ctx["service_topic"] = st if st and st != "unknown" else None


def merge_retrieval_debug_meta(debug_meta: dict[str, Any] | None) -> None:
    if not isinstance(debug_meta, dict) or not hasattr(request, "ctx"):
        return
    for key in _MERGE_DEBUG_META_KEYS:
        if key in debug_meta:
            request.ctx[key] = debug_meta[key]


def record_selection_metadata(
    *,
    selected_doc_id: str | None,
    selected_chunk: dict | None,
    selected_route: str | None = None,
) -> None:
    if not hasattr(request, "ctx"):
        return
    if selected_doc_id:
        request.ctx["selected_doc_id"] = selected_doc_id
    if selected_route:
        request.ctx["selected_route"] = selected_route
    if isinstance(selected_chunk, dict):
        dt = chunk_doc_type(selected_chunk)
        if dt:
            request.ctx["selected_doc_type"] = str(dt).strip().lower()
        topic = selected_chunk.get("topic")
        if topic:
            request.ctx["selected_topic"] = str(topic).strip().lower()
