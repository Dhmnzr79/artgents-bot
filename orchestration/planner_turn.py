"""Planner turn — one LLM call, native TurnFrame only (C2b)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from flask import request

from config import COMPARISON_QUERY_RE
from core.metadata_first_observability import record_decision_frame_ctx
from core.planner_compute_executor import (
    PlannerSpeculationHandle,
    join_planner_speculation,
)
from core.runtime_turn_frame import (
    RUNTIME_FRAME_STATUS_PARTIAL,
    RUNTIME_FRAME_STATUS_OK,
    get_runtime_turn_frame_status,
    publish_planner_attempt_frame,
)
from core.routing_loader import THRESHOLDS
from core.turn_planner_llm import plan_turn_attempt
from core import turn_timing
from logging_setup import get_logger, log_json
from core.target_query_cues import commercial_info_query, consultation_info_query

logger = get_logger("bot")


@dataclass(frozen=True)
class PlannerTurnOutcome:
    intent: str
    scope_topic_candidate: str | None


def _intent_from_attempt(*, q: str, attempt) -> str:
    if attempt.status not in {RUNTIME_FRAME_STATUS_OK, RUNTIME_FRAME_STATUS_PARTIAL}:
        return "content"
    frame = attempt.frame
    if frame is None:
        return "content"
    ri = str(frame.intent or "").strip().lower()
    if consultation_info_query(q) or commercial_info_query(q):
        return "content"
    if ri in ("price_lookup", "price_concern"):
        return ri
    return "content"


def _scope_topic_candidate_from_attempt(attempt) -> str | None:
    frame = attempt.frame
    if frame is None:
        return None
    topic = str(frame.topic or "").strip().lower()
    if not topic or topic == "unknown":
        return None
    confidence = float(frame.field_meta.topic.confidence or 0.0)
    if confidence < float(THRESHOLDS.retrieval.scope_topic_min_confidence):
        return None
    return topic


def run_planner_turn(
    *,
    q: str,
    sid: str,
    client_id: str,
    st: dict,
    enqueue_resolver_trace: Callable[..., None],
    speculative_handle: "PlannerSpeculationHandle | None" = None,
) -> PlannerTurnOutcome:
    """Single planner call → runtime TurnFrame; no resolver fallback.

    PERF-4 (Variant C): when `speculative_handle` is given, Planner's compute already
    ran (or is still running) concurrently with Ingress's own LLM call, submitted by
    `orchestration/pre_resolver_turn.py` via `core/planner_compute_executor.py`. This
    function only ever *joins* that result and *publishes* it — the join/publish split
    is exactly the seam the governance audit identified: everything below this point
    (`publish_planner_attempt_frame`, the `request.ctx` writes, `record_decision_frame_ctx`,
    `enqueue_resolver_trace`) is unchanged, runs in this same main orchestration thread,
    exactly once, regardless of whether the attempt came from a speculative join or the
    synchronous fallback call. `turn_timing.stage_start("planner")` for the speculative
    path already happened in `pre_resolver_turn.py` at fork time (so the recorded stage
    duration reflects when the compute actually began, honestly overlapping Ingress's
    own span) — only `stage_end` happens here for that path."""
    _ = st
    if speculative_handle is not None:
        attempt = join_planner_speculation(speculative_handle)
        turn_timing.stage_end("planner", status="completed")
        log_json(
            logger,
            "planner_speculation_published",
            client_id=client_id,
            request_id=request.ctx.get("request_id"),
        )
    else:
        turn_timing.stage_start("planner")
        attempt = plan_turn_attempt(q, sid, client_id)
        turn_timing.stage_end("planner", status="completed")
    publish_planner_attempt_frame(attempt=attempt)
    status = get_runtime_turn_frame_status()
    request.ctx["turn_planner_used"] = status in {
        RUNTIME_FRAME_STATUS_OK,
        RUNTIME_FRAME_STATUS_PARTIAL,
    }
    request.ctx["resolver_used"] = False
    request.ctx["safety_net_used"] = False
    if not request.ctx["turn_planner_used"]:
        log_json(
            logger,
            "turn_planner_no_usable_frame",
            sid=sid,
            client_id=client_id,
            runtime_status=status,
        )
    intent = _intent_from_attempt(q=q, attempt=attempt)
    request.ctx["effective_intent"] = str(intent)
    record_decision_frame_ctx(None)
    enqueue_resolver_trace(
        decision=None,
        safety_net_used=[],
        resolver_bypassed_env=False,
    )
    if COMPARISON_QUERY_RE.search(q or "") and attempt.frame is not None:
        _ = attempt.frame
    scope_topic_candidate = _scope_topic_candidate_from_attempt(attempt)
    return PlannerTurnOutcome(intent=intent, scope_topic_candidate=scope_topic_candidate)
