"""PERF-4: dedicated bounded executor for Planner's speculative compute (Variant C).

Governance: docs/evidence/performance/FINAL_PARALLEL_INGRESS_PLANNER_LATENCY_SEAM_AUDIT.md,
TASK.md ("FINAL_PARALLEL_INGRESS_PLANNER_LATENCY / PERF-4").

Only `plan_turn_attempt` (the pure LLM call -- zero Flask/`request.ctx` dependency, confirmed
by the seam audit) ever runs on the worker thread here. Everything publish-shaped
(`publish_planner_attempt_frame`, the `request.ctx` writes, `record_decision_frame_ctx`,
`enqueue_resolver_trace`) stays in `orchestration/planner_turn.py`, in the main orchestration
thread, exactly as it already does -- this module never touches any of that.

This is a **separate, independently-bounded** pool -- never PERF-1's `_sse_worker_executor`
(`app.py`). `_orchestrate_ask_turn` already runs *inside* one of PERF-1's SSE worker threads for
`/ask/stream`; sharing a pool would let all of PERF-1's workers deadlock under load, each
blocked submitting a nested task to their own already-exhausted pool (seam audit S10).

The worker function (`_compute`) reads only an immutable `PlannerSpeculationSnapshot` built in
the main thread before submit -- never Flask `request`/`request.ctx`, never `session.py`'s
thread-local client-pack binding (`session._tls`, which silently falls back to the `"demo"`
pack if unset on the current thread -- a real cross-client hazard for a reused pool thread),
never anything that could change after submit.
"""

from __future__ import annotations

import os
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass

from contracts.planner_attempt import PlannerAttempt
from core.turn_planner_llm import plan_turn_attempt
from logging_setup import get_logger, log_json

logger = get_logger("bot")

# Bounded admission via an explicit Semaphore (non-blocking acquire), not the pool's own
# (effectively unbounded) internal work queue -- same pattern PERF-1 already uses for
# `_sse_worker_executor`/`_sse_worker_admission`, applied to a wholly separate pool.
#
# SAFE-BY-DEFAULT ROLLOUT: capacity defaults to 0 (inert). At capacity 0, admission
# always refuses (Semaphore(0).acquire(blocking=False) is always False), so
# try_submit_planner_speculation always returns None and every caller falls back to
# the synchronous path (plan_turn_attempt called directly, in-thread) -- byte-for-byte
# the same behavior as before PERF-4 existed. This mirrors PERF-3's two-gate pattern
# (implementation GO, then a SEPARATE owner LIVE/LLM GO before real activation): Phase 2
# ships the mechanism fully implemented and test-covered, but real concurrent-call
# activation in production requires a separate, explicit owner step -- setting
# PLANNER_SPECULATION_CAPACITY to a positive integer. This was deliberately chosen over
# auditing every existing test for an implicit "run_pre_resolver_turn alone never
# reaches Planner" assumption that PERF-4 breaks: several pre-existing tests were found
# relying on exactly that (see TASK.md's PERF-4 completion record) and a wide test
# suite this large cannot be exhaustively proven free of more.
PLANNER_SPECULATION_CAPACITY = max(0, int(os.getenv("PLANNER_SPECULATION_CAPACITY", "0")))
_planner_speculation_executor = ThreadPoolExecutor(
    max_workers=max(1, PLANNER_SPECULATION_CAPACITY), thread_name_prefix="planner-speculative"
)
_planner_speculation_admission = threading.Semaphore(PLANNER_SPECULATION_CAPACITY)

# Defense in depth only: plan_turn_attempt already carries its own LLM request timeout
# (LLM_REQUEST_TIMEOUT_SEC); this bounds the *join*, so a hung compute cannot block the
# main thread past what a synchronous plan_turn_attempt call would already be bounded to.
PLANNER_SPECULATION_JOIN_TIMEOUT_SEC = float(
    os.getenv("PLANNER_SPECULATION_JOIN_TIMEOUT_SEC", "25")
)


@dataclass(frozen=True, slots=True)
class PlannerSpeculationSnapshot:
    """Immutable inputs Planner's compute needs, captured in the main thread before submit.

    No `q`/answer/session content is ever included in this module's log events (only
    `client_id` + `request_id`, per the owner's explicit observability scope) -- this
    dataclass itself still carries `q`/`history` because the *compute* genuinely needs
    them; only the *events emitted about* the compute are restricted.
    """

    client_id: str
    sid: str
    q: str
    history: str
    request_id: str | None


@dataclass(frozen=True, slots=True)
class PlannerSpeculationHandle:
    """One speculatively-submitted Planner compute. Exactly one of
    `join_planner_speculation` / `discard_planner_speculation` is ever called per handle --
    never both. That mirrors the pre-existing sequential code's own control flow: either
    Ingress resolves the turn as normal and no earlier short-circuit fired (join/publish),
    or one of them did (discard) -- structurally exclusive, not a new state machine.
    """

    future: "Future[PlannerAttempt]"
    snapshot: PlannerSpeculationSnapshot


def _compute(snapshot: PlannerSpeculationSnapshot) -> PlannerAttempt:
    """Runs on the worker thread. `plan_turn_attempt` already degrades its own LLM-call
    failures internally (returns `PlannerAttempt(frame=None, status="not_available")`,
    never raises) -- this try/except only guards a truly unexpected bug elsewhere in the
    call chain, so the future itself never raises and `join_planner_speculation` never
    needs to special-case an exception from a *known* failure mode."""
    try:
        return plan_turn_attempt(
            snapshot.q,
            snapshot.sid,
            snapshot.client_id,
            history_override=snapshot.history,
        )
    except Exception as exc:  # noqa: BLE001 -- record class only, never message/content
        log_json(
            logger,
            "planner_compute_exception",
            client_id=snapshot.client_id,
            request_id=snapshot.request_id,
            error_class=type(exc).__name__,
        )
        return PlannerAttempt(frame=None, status="not_available")


def _release_admission(_future: "Future[PlannerAttempt]") -> None:
    """Done-callback: fires exactly once per future, on success, exception, or
    cancellation alike -- the single place capacity is released, regardless of whether
    the caller ends up joining or discarding."""
    _planner_speculation_admission.release()


def try_submit_planner_speculation(
    *,
    client_id: str,
    sid: str,
    q: str,
    history: str,
    request_id: str | None,
) -> PlannerSpeculationHandle | None:
    """Non-blocking. Returns `None` (no speculation started) under admission overload or
    a submit failure -- the caller must then run `plan_turn_attempt` synchronously itself
    (the existing, unchanged sequential path -- Variant D fallback), never a user-visible
    error and never an unbounded wait."""

    if not _planner_speculation_admission.acquire(blocking=False):
        log_json(
            logger,
            "planner_parallel_overload_sequential",
            client_id=client_id,
            request_id=request_id,
        )
        return None

    snapshot = PlannerSpeculationSnapshot(
        client_id=client_id, sid=sid, q=q, history=history, request_id=request_id
    )
    try:
        future = _planner_speculation_executor.submit(_compute, snapshot)
    except Exception:
        _planner_speculation_admission.release()
        log_json(
            logger,
            "planner_parallel_overload_sequential",
            client_id=client_id,
            request_id=request_id,
            reason="submit_failed",
        )
        return None

    future.add_done_callback(_release_admission)
    log_json(
        logger,
        "planner_speculation_submitted",
        client_id=client_id,
        request_id=request_id,
    )
    return PlannerSpeculationHandle(future=future, snapshot=snapshot)


def join_planner_speculation(
    handle: PlannerSpeculationHandle,
    *,
    timeout: float = PLANNER_SPECULATION_JOIN_TIMEOUT_SEC,
) -> PlannerAttempt:
    """Main-thread-only. Blocks, bounded by `timeout`, for the speculative compute's
    result. Never raises -- `_compute` already degrades internally, and this adds one
    more layer of defense (a join timeout, or any other executor-level failure) so the
    existing Planner fallback contract (`frame=None, status="not_available"`) is
    preserved end-to-end no matter what goes wrong. Publishing the returned attempt is
    the caller's responsibility (`orchestration/planner_turn.py`), not this module's."""
    try:
        return handle.future.result(timeout=timeout)
    except Exception as exc:
        log_json(
            logger,
            "planner_compute_exception",
            client_id=handle.snapshot.client_id,
            request_id=handle.snapshot.request_id,
            error_class=type(exc).__name__,
        )
        return PlannerAttempt(frame=None, status="not_available")


def _on_discarded_done(
    _future: "Future[PlannerAttempt]", *, client_id: str, request_id: str | None
) -> None:
    log_json(
        logger,
        "planner_speculation_discarded",
        client_id=client_id,
        request_id=request_id,
    )


def discard_planner_speculation(handle: PlannerSpeculationHandle | None) -> None:
    """Ingress rejected the turn, or another pre-Planner short-circuit fired first
    (lead-flow, anti-spam, ref-clarify, empty q, typed UI). Never waits on a running or
    already-finished compute; best-effort cancels one that has not started yet. Whatever
    the compute returns is never read, never published, never used for any product
    decision -- this function only observes that it finished (so no exception is ever
    left silently unobserved) and emits an anonymized outcome event."""
    if handle is None:
        return
    if handle.future.cancel():
        log_json(
            logger,
            "planner_speculation_cancelled",
            client_id=handle.snapshot.client_id,
            request_id=handle.snapshot.request_id,
        )
        return
    handle.future.add_done_callback(
        lambda f: _on_discarded_done(
            f,
            client_id=handle.snapshot.client_id,
            request_id=handle.snapshot.request_id,
        )
    )
