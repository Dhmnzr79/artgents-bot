"""Metadata-First v1: soft score boosts on retrieval candidates."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.routing_loader import THRESHOLDS
from retriever import chunk_doc_type, load_corpus_if_needed


@dataclass(frozen=True)
class MetadataRetrievalContext:
    query_mode: str | None
    service_topic: str | None
    service_topic_confidence: float = 0.0
    query_aspects: tuple[str, ...] = ()


def metadata_context_from_decision(
    decision: Any | None,
    *,
    q: str | None = None,
) -> MetadataRetrievalContext | None:
    if decision is None:
        return None
    if isinstance(decision, dict):
        qm = decision.get("query_mode")
        st = decision.get("service_topic")
        conf = decision.get("confidence") or {}
        topic_conf = (
            float(conf.get("topic", 0.0))
            if isinstance(conf, dict)
            else float(getattr(conf, "topic", 0.0) or 0.0)
        )
    else:
        qm = getattr(decision, "query_mode", None)
        st = getattr(decision, "service_topic", None)
        conf = getattr(decision, "confidence", None)
        topic_conf = float(getattr(conf, "topic", 0.0) or 0.0) if conf is not None else 0.0
    qm = str(qm or "").strip().lower() or None
    st = str(st or "").strip().lower() or None
    if st in ("", "unknown"):
        st = None
    if not qm and not st and not (q or "").strip():
        return None

    aspects: tuple[str, ...] = ()
    if (q or "").strip():
        from core.answer_planner import detect_aspects

        detected = detect_aspects(q or "", decision=decision)
        aspects = tuple(a for a in detected if a)

    return MetadataRetrievalContext(
        query_mode=qm,
        service_topic=st,
        service_topic_confidence=topic_conf,
        query_aspects=aspects,
    )


def effective_scope_topic_for_retrieval(
    scope_topic: str | None,
    ctx: MetadataRetrievalContext | None,
    *,
    follow_up_mode: bool = False,
) -> str | None:
    """Comparison queries: no hard topic scope (prefer doc_type via boosts)."""
    if follow_up_mode:
        return None
    if ctx and str(ctx.query_mode or "").strip().lower() == "comparison":
        return None
    return scope_topic


def _chunk_topic(ch: dict) -> str | None:
    t = ch.get("topic")
    if t is not None and str(t).strip():
        return str(t).strip().lower()
    return None


def _topic_confidence_ok(ctx: MetadataRetrievalContext) -> bool:
    return float(ctx.service_topic_confidence or 0.0) >= float(
        THRESHOLDS.retrieval.scope_topic_min_confidence
    )


def _comparison_retrieval_state(
    ctx: MetadataRetrievalContext | None,
    *,
    client_id: str | None,
    corpus: list[dict] | None = None,
) -> tuple[bool, bool]:
    """Return (comparison_docs_for_topic, exclude_comparison_from_pool)."""
    if ctx is None or str(ctx.query_mode or "").strip().lower() != "comparison":
        return False, False
    st = ctx.service_topic
    topic_conf_ok = _topic_confidence_ok(ctx)
    comparison_available = False
    if st and topic_conf_ok:
        corpus_rows = corpus if corpus is not None else load_corpus_if_needed(client_id)
        comparison_available = _corpus_has_comparison_for_topic(
            corpus_rows, client_id=client_id, service_topic=st
        )
    exclude = (
        bool(THRESHOLDS.metadata_first.comparison_miss_exclude_comparison)
        and not comparison_available
    )
    return comparison_available, exclude


def _corpus_has_comparison_for_topic(
    corpus: list[dict],
    *,
    client_id: str | None,
    service_topic: str,
) -> bool:
    """True if pack has at least one comparison doc for this service_topic."""
    want_topic = service_topic.strip().lower()
    if not want_topic or want_topic == "unknown":
        return False
    for row in corpus:
        if not isinstance(row, dict):
            continue
        row_cid = row.get("client_id")
        if client_id and row_cid and row_cid != client_id:
            continue
        dt = chunk_doc_type(row)
        if not dt or str(dt).strip().lower() != "comparison":
            continue
        topic_l = _chunk_topic(row)
        if topic_l == want_topic:
            return True
    return False


def _chunk_aspect(ch: dict) -> str | None:
    a = ch.get("aspect")
    if a is not None and str(a).strip():
        return str(a).strip().lower()
    return None


def apply_metadata_candidate_boosts(
    candidates: list[dict],
    *,
    ctx: MetadataRetrievalContext | None,
    client_id: str | None,
    corpus: list[dict] | None = None,
) -> tuple[list[dict], dict[str, Any]]:
    """Re-rank retrieval candidates with soft metadata boosts; fail-open."""
    tel: dict[str, Any] = {
        "candidate_pool_before": len(candidates),
        "metadata_boost_applied": False,
        "comparison_prefer": False,
        "fallback_used": False,
    }
    if not candidates or ctx is None:
        tel["candidate_pool_after"] = len(candidates)
        return candidates, tel

    mf = THRESHOLDS.metadata_first
    corpus_rows = corpus if corpus is not None else load_corpus_if_needed(client_id)
    qm = str(ctx.query_mode or "").strip().lower()
    st = ctx.service_topic
    topic_conf_ok = _topic_confidence_ok(ctx)

    comparison_available, exclude_comparison = _comparison_retrieval_state(
        ctx, client_id=client_id, corpus=corpus_rows
    )
    if qm == "comparison":
        tel["comparison_docs_for_topic"] = comparison_available
        if not comparison_available:
            tel["fallback_used"] = True

    boosted: list[dict] = []
    for ch in candidates:
        if not isinstance(ch, dict):
            continue
        row = dict(ch)
        base = float(row.get("_score") or 0.0)
        bonus = 0.0
        dt = chunk_doc_type(row)
        dt_l = str(dt or "").strip().lower()
        topic_l = _chunk_topic(row)

        if (
            qm == "comparison"
            and comparison_available
            and dt_l == "comparison"
            and st
            and topic_conf_ok
            and topic_l == st
        ):
            bonus += float(mf.comparison_doc_type_boost)
            tel["comparison_prefer"] = True

        if st and topic_conf_ok and topic_l == st:
            bonus += float(mf.service_topic_match_boost)

        chunk_aspect = _chunk_aspect(row)
        if chunk_aspect and ctx.query_aspects and chunk_aspect in ctx.query_aspects:
            bonus += float(mf.aspect_match_boost)

        if bonus > 0:
            row["_score"] = base + bonus
            row["_metadata_boost"] = round(bonus, 4)
            tel["metadata_boost_applied"] = True
        boosted.append(row)

    boosted.sort(key=lambda c: float(c.get("_score") or 0.0), reverse=True)

    if exclude_comparison:
        before = len(boosted)
        boosted = [
            ch
            for ch in boosted
            if str(chunk_doc_type(ch) or "").strip().lower() != "comparison"
        ]
        excluded = before - len(boosted)
        if excluded:
            tel["comparison_miss_excluded"] = True
            tel["comparison_excluded_count"] = excluded

    tel["candidate_pool_after"] = len(boosted)
    return boosted, tel


def filter_alias_leader_on_comparison_miss(
    alias_leader: dict | None,
    *,
    ctx: MetadataRetrievalContext | None,
    client_id: str | None,
    corpus: list[dict] | None = None,
) -> tuple[dict | None, bool]:
    """Drop alias leader when it is a comparison doc on comparison-topic miss."""
    if not isinstance(alias_leader, dict):
        return alias_leader, False
    _, exclude_comparison = _comparison_retrieval_state(
        ctx, client_id=client_id, corpus=corpus
    )
    if not exclude_comparison:
        return alias_leader, False
    if str(chunk_doc_type(alias_leader) or "").strip().lower() != "comparison":
        return alias_leader, False
    return None, True


def filter_alias_leader_on_topic_mismatch(
    alias_leader: dict | None,
    *,
    ctx: MetadataRetrievalContext | None,
    alias_diag: dict[str, Any] | None,
    follow_up_mode: bool = False,
) -> tuple[dict | None, bool]:
    """Drop non-exact alias when chunk topic conflicts with confident resolver service_topic."""
    if follow_up_mode:
        return alias_leader, False
    if not bool(THRESHOLDS.metadata_first.alias_topic_guard_enabled):
        return alias_leader, False
    if not isinstance(alias_leader, dict) or ctx is None:
        return alias_leader, False
    st = ctx.service_topic
    if not st or not _topic_confidence_ok(ctx):
        return alias_leader, False
    tier = str((alias_diag or {}).get("alias_decision") or "").strip().lower()
    if tier in ("exact", "near_exact"):
        return alias_leader, False
    chunk_topic = _chunk_topic(alias_leader)
    if not chunk_topic or chunk_topic == st.strip().lower():
        return alias_leader, False
    return None, True


def resolve_alias_for_turn(
    q: str,
    *,
    ctx: MetadataRetrievalContext | None,
    client_id: str | None,
    top_semantic_score: float | None = None,
    corpus: list[dict] | None = None,
    follow_up_mode: bool = False,
) -> tuple[dict | None, float, dict[str, Any]]:
    """Single runtime alias entry: corpus leader → metadata guards → cap vs semantic top.

    Used by chunk selection, content arbiter alias candidate, and scope conflict guard.
    """
    from retriever import corpus_alias_leader

    alias_leader, alias_score, alias_diag = corpus_alias_leader(q, client_id=client_id)
    tel: dict[str, Any] = dict(alias_diag)

    alias_leader, comp_rej = filter_alias_leader_on_comparison_miss(
        alias_leader, ctx=ctx, client_id=client_id, corpus=corpus
    )
    if comp_rej:
        alias_score = 0.0
        tel["comparison_miss_alias_rejected"] = True

    topic_got: str | None = _chunk_topic(alias_leader) if isinstance(alias_leader, dict) else None
    alias_leader, topic_rej = filter_alias_leader_on_topic_mismatch(
        alias_leader, ctx=ctx, alias_diag=tel, follow_up_mode=follow_up_mode
    )
    if topic_rej:
        alias_score = 0.0
        tel["alias_topic_guard_rejected"] = True
        tel["alias_topic_guard_want"] = ctx.service_topic if ctx else None
        tel["alias_topic_guard_got"] = topic_got

    alias_score, alias_capped = cap_alias_score_vs_semantic(
        float(alias_score or 0.0), top_semantic_score
    )
    if alias_capped:
        tel["alias_boost_capped"] = True

    tel["alias_hit"] = bool(alias_leader)
    tel["alias_boost"] = round(float(alias_score or 0.0), 4)
    return alias_leader, alias_score, tel


def cap_alias_score_vs_semantic(
    alias_score: float,
    top_semantic_score: float | None,
) -> tuple[float, bool]:
    """Alias cannot exceed top semantic by more than metadata_first.alias_boost_max_delta."""
    if top_semantic_score is None:
        return alias_score, False
    cap = float(THRESHOLDS.metadata_first.alias_boost_max_delta)
    top = float(top_semantic_score)
    if alias_score <= top + cap:
        return alias_score, False
    return top + cap, True
