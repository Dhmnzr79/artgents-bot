"""Retrieval 2.0 — LLM rerank gate + fail-open execution (H3).

Trigger thresholds: ``core/routing.yaml`` → ``rerank`` (+ ``retrieval.low_score_threshold`` for min).
"""
from __future__ import annotations

import json
import time
from typing import Any

from config import RERANK_MODEL
from core.routing_loader import THRESHOLDS
from llm import chat_completions_create
from logging_setup import get_logger, log_json, log_llm_usage
from retriever import chunk_info

logger = get_logger("bot")


def _top_score(candidates: list[dict]) -> float:
    if not candidates:
        return 0.0
    return float(candidates[0].get("_score") or 0.0)


def _score_gap(candidates: list[dict]) -> float:
    if len(candidates) < 2:
        return 1.0
    return abs(
        float(candidates[0].get("_score") or 0.0) - float(candidates[1].get("_score") or 0.0)
    )


def _alias_backed(ch: dict) -> bool:
    return "alias" in list(ch.get("_pool_sources") or [])


def alias_pack_signal_strong(alias_decision: str) -> bool:
    """Pack alias tier strong enough to defer to pool over LLM rerank."""
    tier = str(alias_decision or "").strip().lower()
    return tier in ("exact", "near_exact", "embed_high")


def strong_alias_blocks_rerank(
    candidates: list[dict],
    *,
    alias_strong: bool,
    alias_decision: str = "",
) -> bool:
    """Skip LLM rerank when a strong pack alias sits in the ambiguous top band."""
    rr = THRESHOLDS.rerank
    if not bool(rr.skip_on_strong_alias_in_pool):
        return False
    if not alias_strong and not alias_pack_signal_strong(alias_decision):
        return False
    if not candidates:
        return False
    gap_max = float(rr.score_gap_max)
    top_k = int(rr.top_k)
    top_sc = float(candidates[0].get("_score") or 0.0)
    band = [
        c
        for c in candidates[:top_k]
        if abs(float(c.get("_score") or 0.0) - top_sc) <= gap_max + 1e-9
    ]
    return any(_alias_backed(c) for c in band)


def pool_top_when_alias_rerank_skipped(candidates: list[dict]) -> dict:
    """Prefer alias-backed pool row on score tie (H1 sort keeps pre-semantic leader)."""
    if not candidates:
        raise ValueError("pool_top_when_alias_rerank_skipped requires candidates")
    top_k = int(THRESHOLDS.rerank.top_k)
    top_sc = float(candidates[0].get("_score") or 0.0)
    eps = 1e-4
    ties = [
        c
        for c in candidates[:top_k]
        if abs(float(c.get("_score") or 0.0) - top_sc) <= eps
    ]
    alias_ties = [c for c in ties if _alias_backed(c)]
    if alias_ties:
        return alias_ties[0]
    return candidates[0]


def evaluate_rerank_trigger(
    candidates: list[dict],
    *,
    point_literal: bool,
    alias_strong: bool = False,
    alias_decision: str = "",
) -> tuple[bool, str]:
    """Return (should_rerank, rerank_trigger_reason). Does not call LLM."""
    rr = THRESHOLDS.rerank
    if not bool(rr.enabled):
        return False, "disabled"
    if len(candidates) < int(rr.min_candidates):
        return False, "too_few_candidates"
    if point_literal:
        return False, "point_literal_query"
    top = _top_score(candidates)
    low = float(THRESHOLDS.retrieval.low_score_threshold)
    if top < low:
        return False, "below_score_min"
    if top >= float(rr.score_max):
        return False, "above_score_max"
    if _score_gap(candidates) >= float(rr.score_gap_max):
        return False, "gap_too_wide"
    if strong_alias_blocks_rerank(
        candidates, alias_strong=alias_strong, alias_decision=alias_decision
    ):
        return False, "strong_alias_in_pool"
    return True, "triggered"


def llm_rerank_candidates(q: str, cands: list[dict]) -> tuple[dict, dict[str, Any]]:
    """Flash rerank over top-k candidates; fail-open to ``cands[0]`` on any error."""
    tel: dict[str, Any] = {"rerank_fallback_used": False, "rerank_fallback_reason": None}
    if not cands:
        raise ValueError("llm_rerank_candidates requires at least one candidate")
    t0 = time.time()
    try:
        cand_infos = [chunk_info(ch, ch.get("_score")) for ch in cands]
    except Exception:
        cand_infos = [chunk_info(ch, None) for ch in cands]
    log_json(
        logger,
        "rerank",
        question=q[:200],
        candidates=cand_infos,
        model_used=RERANK_MODEL,
    )

    prompt = (
        "Выбери самый уместный фрагмент для ответа на вопрос пользователя. "
        'Верни только JSON-объект вида {"choice": 1}, где choice — номер 1, 2 или 3.'
    )

    def _cand_block(ch: dict) -> str:
        if not isinstance(ch, dict):
            return ""
        return (
            f"{(ch.get('h2') or '').strip()}\n"
            f"{(ch.get('h3') or '').strip()}\n"
            f"{(ch.get('text') or '')[:500]}"
        ).strip()

    msgs = [
        {
            "role": "system",
            "content": (
                "Ты помощник стоматологической клиники. Тебе нужно выбрать фрагмент "
                "из базы знаний, который наиболее точно отвечает на вопрос пациента. "
                'Отвечай только JSON-объектом вида {"choice": 1}, где choice — 1, 2 или 3.'
            ),
        },
        {
            "role": "user",
            "content": (
                f"{prompt}\n\nВопрос: {q}\n\n"
                f"1) {_cand_block(cands[0])}\n\n"
                f"2) {_cand_block(cands[1]) if len(cands) > 1 else ''}\n\n"
                f"3) {_cand_block(cands[2]) if len(cands) > 2 else ''}"
            ),
        },
    ]
    fallback_reason: str | None = None
    try:
        out = chat_completions_create(
            model=RERANK_MODEL,
            messages=msgs,
            temperature=0,
            response_format={"type": "json_object"},
        )
        log_llm_usage(logger, out, call_type="rerank", model=RERANK_MODEL)
        raw = (out.choices[0].message.content or "").strip()
        try:
            obj = json.loads(raw)
        except Exception:
            obj = None
            fallback_reason = "invalid_json"
        if not isinstance(obj, dict):
            fallback_reason = fallback_reason or "invalid_json_object"
            result = cands[0]
        else:
            choice = obj.get("choice")
            if not isinstance(choice, int):
                fallback_reason = "missing_or_nonint_choice"
                result = cands[0]
            else:
                idx = int(choice) - 1
                max_idx = min(len(cands), 3) - 1
                if 0 <= idx <= max_idx:
                    result = cands[idx]
                else:
                    fallback_reason = "choice_out_of_range"
                    result = cands[0]
    except Exception:
        fallback_reason = "api_error"
        result = cands[0]

    if fallback_reason:
        tel["rerank_fallback_used"] = True
        tel["rerank_fallback_reason"] = fallback_reason

    lat = int((time.time() - t0) * 1000)
    log_json(
        logger,
        "rerank_result",
        model_used=RERANK_MODEL,
        latency_ms=lat,
        fallback_reason=fallback_reason,
        chosen=chunk_info(
            result, result.get("_score") if isinstance(result, dict) else None
        ),
    )
    return result, tel


def maybe_rerank_top(
    q: str,
    candidates: list[dict],
    *,
    point_literal: bool,
    alias_strong: bool = False,
    alias_decision: str = "",
) -> tuple[dict, dict[str, Any]]:
    """Apply rerank when gate passes; otherwise return pool top with skip telemetry."""
    if not candidates:
        raise ValueError("maybe_rerank_top requires at least one candidate")
    should, reason = evaluate_rerank_trigger(
        candidates,
        point_literal=point_literal,
        alias_strong=alias_strong,
        alias_decision=alias_decision,
    )
    tel: dict[str, Any] = {
        "rerank_trigger_reason": reason,
        "rerank_applied": False,
        "rerank_fallback_used": False,
        "rerank_fallback_reason": None,
    }
    if not should:
        top = candidates[0]
        if reason == "strong_alias_in_pool":
            top = pool_top_when_alias_rerank_skipped(candidates)
        return top, tel
    top_k = int(THRESHOLDS.rerank.top_k)
    pool = candidates[:top_k]
    chosen, inner = llm_rerank_candidates(q, pool)
    tel["rerank_applied"] = True
    tel["rerank_fallback_used"] = bool(inner.get("rerank_fallback_used"))
    if inner.get("rerank_fallback_reason"):
        tel["rerank_fallback_reason"] = inner.get("rerank_fallback_reason")
    return chosen, tel
