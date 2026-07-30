"""Implementation acceptance matrix for FINAL_PARALLEL_INGRESS_PLANNER_LATENCY / PERF-4.

Covers the 30-scenario matrix from the seam audit / TASK.md with FAKE classify_ingress and
plan_turn_attempt only -- no network, no real provider call, no repo artifact. Ingress and
Planner are exercised through the real `run_pre_resolver_turn` / `run_planner_turn` /
`core.planner_compute_executor` wiring; only the two underlying LLM-call functions are faked.

Deviation from the Phase 2 allowlist, recorded here and in TASK.md: `ingress_gate.py` gained a
minimal, additive, backward-compatible `on_llm_path` hook on `classify_ingress` (default `None`,
zero behavior change for any existing caller). This was required because forking Planner's
speculative compute by independently re-running Ingress's own deterministic pre-checks (the
original approach) diverges from whatever a test's `classify_ingress` fake decides, and was
observed to leak a real, live provider call into pre-existing offline tests that fake
`classify_ingress` directly (e.g. `test_ingress_stage_completed_deterministic_no_llm`). The hook
ties the fork decision to the exact real moment `classify_ingress` is about to call its own LLM
path, so a caller that replaces `classify_ingress` wholesale automatically never triggers the
fork either -- eliminating the bug class by construction instead of patching individual tests.
"""

from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import Future

import pytest
from flask import Flask, request

import app as app_module
import core.planner_compute_executor as executor_module
import ingress_gate as ingress_gate_module
import orchestration.pre_resolver_turn as pre_resolver_module
import orchestration.planner_turn as planner_turn_module
from contracts.ask_orchestration import AskOrchestrationResult
from contracts.ingress_route import IngressRouteResult
from contracts.planner_attempt import PlannerAttempt
from core.planner_compute_executor import (
    PlannerSpeculationHandle,
    discard_planner_speculation,
    join_planner_speculation,
    try_submit_planner_speculation,
)

# PERF-4 ships with PLANNER_SPECULATION_CAPACITY defaulting to 0 (inert -- see
# core/planner_compute_executor.py's module docstring: real activation is a separate,
# later owner step, mirroring PERF-3's two-gate pattern). This test file explicitly
# activates a working capacity for its own scope only, via the autouse fixture below,
# so it can exercise the real fork/join/executor mechanism deliberately.
PLANNER_SPECULATION_CAPACITY = 4
from core.turn_planner_llm import TURN_PLANNER_LLM_MODEL, _SYSTEM as PLANNER_SYSTEM_PROMPT
from ingress_gate import INGRESS_CLASSIFY_MODEL, _INGRESS_SYSTEM as INGRESS_SYSTEM_PROMPT
from orchestration.context import AskTurnContext
from orchestration.planner_turn import run_planner_turn
from session import mem_reset

_NOT_AVAILABLE = PlannerAttempt(frame=None, status="not_available")


# --------------------------------------------------------------------------------------------
# Fakes -- no network, no real provider call anywhere in this file
# --------------------------------------------------------------------------------------------


def _fake_normal_ingress_via_llm(*, delay: float = 0.0):
    """Mimics classify_ingress()'s real control flow for the LLM path: calls on_llm_path
    exactly once, then returns route=normal, source='llm'."""

    def _classify(question, *, client_id, sid, skip=False, on_llm_path=None):
        if on_llm_path is not None:
            on_llm_path()
        if delay:
            time.sleep(delay)
        return IngressRouteResult(
            route="normal",
            confidence=0.9,
            reason="fake_llm_normal",
            policy_key=None,
            requested_service=None,
            source="llm",
            is_urgent=False,
        )

    return _classify


def _fake_reject_ingress_via_llm(*, delay: float = 0.0):
    def _classify(question, *, client_id, sid, skip=False, on_llm_path=None):
        if on_llm_path is not None:
            on_llm_path()
        if delay:
            time.sleep(delay)
        return IngressRouteResult(
            route="hard_stop_non_target",
            confidence=0.9,
            reason="fake_llm_reject",
            policy_key=None,
            requested_service=None,
            source="llm",
            is_urgent=False,
        )

    return _classify


def _fake_deterministic_ingress(route: str = "normal"):
    """Mimics a rule/deterministic hit: never calls on_llm_path."""

    def _classify(question, *, client_id, sid, skip=False, on_llm_path=None):
        return IngressRouteResult(
            route=route,
            confidence=1.0,
            reason="rule_match",
            policy_key=None,
            requested_service=None,
            source="rule",
            is_urgent=False,
        )

    return _classify


def _fake_planner_compute(*, delay: float = 0.0, raises: bool = False, calls: list | None = None):
    def _plan(q, sid, client_id, *, history_override=None):
        if calls is not None:
            calls.append((q, sid, client_id, history_override))
        if delay:
            time.sleep(delay)
        if raises:
            raise RuntimeError("fake_planner_boom")
        return _NOT_AVAILABLE

    return _plan


def _ctx_kwargs(sid: str, client_id: str = "demo"):
    return dict(
        resolve_client_id=lambda *a, **k: client_id,
        bind_chat_ctx=lambda *a, **k: None,
        resolve_ip=lambda: "127.0.0.1",
        client_txt=lambda cid: {},
        service_payload=lambda **k: {},
        get_last_content_ui_payload=lambda sid: None,
    )


def _run_pre_resolver(data: dict, *, sid: str, request_id: str = "test-req-id"):
    """Runs the real run_pre_resolver_turn inside a minimal, independent Flask request
    context -- mirrors the existing PERF-0 test pattern for this exact function."""
    flask_app = Flask(__name__)
    with flask_app.test_request_context():
        request.ctx = {}
        request.ctx["turn_t0_monotonic"] = time.monotonic()
        request.ctx["request_id"] = request_id
        result = pre_resolver_module.run_pre_resolver_turn(data, **_ctx_kwargs(sid))
        bucket = dict(request.ctx.get("turn_timing") or {})
    return result, bucket


def _run_pre_resolver_then_planner(
    data: dict, *, sid: str, client_id: str = "demo", request_id: str = "test-req-id"
):
    """Mirrors app.py's _orchestrate_ask_turn sequencing: pre-resolver, then (if it
    reached AskTurnContext) run_planner_turn -- all inside one Flask request context, on
    this one (main) thread, exactly like production."""
    flask_app = Flask(__name__)
    with flask_app.test_request_context():
        request.ctx = {}
        request.ctx["turn_t0_monotonic"] = time.monotonic()
        request.ctx["request_id"] = request_id
        pre = pre_resolver_module.run_pre_resolver_turn(data, **_ctx_kwargs(sid, client_id))
        outcome = None
        if not isinstance(pre, AskOrchestrationResult):
            outcome = run_planner_turn(
                q=pre.q,
                sid=pre.sid,
                client_id=pre.client_id,
                st=pre.st,
                enqueue_resolver_trace=lambda **k: None,
                speculative_handle=pre.planner_speculation,
            )
        bucket = dict(request.ctx.get("turn_timing") or {})
    return pre, outcome, bucket


def _data(q: str, sid: str) -> dict:
    return {"q": q, "sid": sid, "client_id": "demo"}


def _sid(tag: str) -> str:
    s = f"perf4-{tag}-{uuid.uuid4().hex[:8]}"
    mem_reset(s)
    return s


@pytest.fixture(autouse=True)
def _fake_planner_by_default(monkeypatch):
    """Safety net for this whole file: plan_turn_attempt is faked (instant, no
    network) by default in every test, on BOTH the speculative-compute path
    (core.planner_compute_executor's own imported reference) and the synchronous
    fallback path (orchestration.planner_turn's separately-imported reference) --
    these are two distinct module-level bindings of the same function. Individual
    tests override either via their own monkeypatch.setattr(...) when they need a
    specific delay/exception/call-recording fake -- but no test in this file can ever
    reach the real network even if it forgets to patch explicitly."""
    monkeypatch.setattr(executor_module, "plan_turn_attempt", _fake_planner_compute())
    monkeypatch.setattr(planner_turn_module, "plan_turn_attempt", _fake_planner_compute())
    # Production default is capacity=0 (inert -- see core/planner_compute_executor.py).
    # This file explicitly activates a real, working, bounded capacity for its own
    # scope only, so it can exercise the actual fork/join/executor mechanism.
    monkeypatch.setattr(
        executor_module, "_planner_speculation_admission", threading.Semaphore(PLANNER_SPECULATION_CAPACITY)
    )
    yield
    # Drain: wait for the admission semaphore to return to full capacity before the
    # next test starts, so a slow fake's still-in-flight background task (started
    # under this test's patch) can never bleed capacity into the next test.
    deadline = time.monotonic() + 5.0
    while (
        executor_module._planner_speculation_admission._value < PLANNER_SPECULATION_CAPACITY
        and time.monotonic() < deadline
    ):
        time.sleep(0.02)


# --------------------------------------------------------------------------------------------
# 1-2: accepted normal turn, call counts, wall-time overlap
# --------------------------------------------------------------------------------------------


def test_1_normal_accepted_ingress_and_planner_each_called_once(monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr(
        pre_resolver_module, "classify_ingress", _fake_normal_ingress_via_llm()
    )
    monkeypatch.setattr(
        executor_module, "plan_turn_attempt", _fake_planner_compute(calls=calls)
    )
    sid = _sid("normal")
    pre, outcome, _bucket = _run_pre_resolver_then_planner(_data("Что такое имплантация?", sid), sid=sid)
    assert not isinstance(pre, AskOrchestrationResult)
    assert outcome is not None
    assert len(calls) == 1


def test_2_artificial_delays_prove_wall_time_is_max_not_sum(monkeypatch) -> None:
    ingress_delay = 0.25
    planner_delay = 0.35
    monkeypatch.setattr(
        pre_resolver_module, "classify_ingress", _fake_normal_ingress_via_llm(delay=ingress_delay)
    )
    monkeypatch.setattr(
        executor_module, "plan_turn_attempt", _fake_planner_compute(delay=planner_delay)
    )
    sid = _sid("overlap")
    t0 = time.monotonic()
    pre, outcome, _bucket = _run_pre_resolver_then_planner(_data("Что такое костная пластика?", sid), sid=sid)
    elapsed = time.monotonic() - t0
    assert outcome is not None
    # Sequential would be >= 0.60s; overlapped should sit close to max(0.25, 0.35) = 0.35s.
    assert elapsed < (ingress_delay + planner_delay) - 0.1, elapsed
    assert elapsed < planner_delay + 0.35, elapsed  # generous upper bound, not sum


# --------------------------------------------------------------------------------------------
# 3-4: publish exactly once, in the main thread
# --------------------------------------------------------------------------------------------


def test_3_planner_result_published_exactly_once(monkeypatch) -> None:
    publish_calls: list = []
    monkeypatch.setattr(pre_resolver_module, "classify_ingress", _fake_normal_ingress_via_llm())
    monkeypatch.setattr(executor_module, "plan_turn_attempt", _fake_planner_compute())
    monkeypatch.setattr(
        planner_turn_module,
        "publish_planner_attempt_frame",
        lambda **k: publish_calls.append(k),
    )
    sid = _sid("publish-once")
    _run_pre_resolver_then_planner(_data("Сколько стоит коронка?", sid), sid=sid)
    assert len(publish_calls) == 1


def test_4_planner_publish_happens_on_main_thread(monkeypatch) -> None:
    main_thread_id = threading.get_ident()
    publish_thread_ids: list = []
    monkeypatch.setattr(pre_resolver_module, "classify_ingress", _fake_normal_ingress_via_llm())
    monkeypatch.setattr(executor_module, "plan_turn_attempt", _fake_planner_compute())
    monkeypatch.setattr(
        planner_turn_module,
        "publish_planner_attempt_frame",
        lambda **k: publish_thread_ids.append(threading.get_ident()),
    )
    sid = _sid("publish-thread")
    _run_pre_resolver_then_planner(_data("Есть ли рассрочка?", sid), sid=sid)
    assert publish_thread_ids == [main_thread_id]


# --------------------------------------------------------------------------------------------
# 5-7: worker isolation -- no Flask context, no thread-local session, immutable snapshot
# --------------------------------------------------------------------------------------------


def test_5_worker_never_touches_flask_request_context(monkeypatch) -> None:
    from flask import has_request_context

    observed: list = []

    def _plan(q, sid, client_id, *, history_override=None):
        observed.append(has_request_context())
        return _NOT_AVAILABLE

    monkeypatch.setattr(pre_resolver_module, "classify_ingress", _fake_normal_ingress_via_llm())
    monkeypatch.setattr(executor_module, "plan_turn_attempt", _plan)
    sid = _sid("no-flask-ctx")
    _run_pre_resolver_then_planner(_data("Какие гарантии на имплант?", sid), sid=sid)
    assert observed == [False]


def test_6_history_read_exactly_once_from_main_thread_never_in_worker(monkeypatch) -> None:
    history_calls: list = []

    def _fake_history(sid, **kwargs):
        history_calls.append(threading.get_ident())
        return "prior turn context"

    monkeypatch.setattr(pre_resolver_module, "recent_dialog_history", _fake_history)
    monkeypatch.setattr(pre_resolver_module, "classify_ingress", _fake_normal_ingress_via_llm())

    received_history: list = []

    def _plan(q, sid, client_id, *, history_override=None):
        received_history.append(history_override)
        return _NOT_AVAILABLE

    monkeypatch.setattr(executor_module, "plan_turn_attempt", _plan)
    sid = _sid("history-once")
    _run_pre_resolver_then_planner(_data("Больно ли ставить имплант?", sid), sid=sid)
    assert history_calls == [threading.get_ident()]  # called once, from this (main) thread
    assert received_history == ["prior turn context"]


def test_7_session_history_passed_as_immutable_snapshot(monkeypatch) -> None:
    monkeypatch.setattr(pre_resolver_module, "recent_dialog_history", lambda sid, **k: "snap-A")
    monkeypatch.setattr(pre_resolver_module, "classify_ingress", _fake_normal_ingress_via_llm())
    received: list = []
    monkeypatch.setattr(
        executor_module,
        "plan_turn_attempt",
        lambda q, sid, client_id, *, history_override=None: (
            received.append(history_override) or _NOT_AVAILABLE
        ),
    )
    sid = _sid("snapshot")
    _run_pre_resolver_then_planner(_data("А сколько стоит имплантация зуба?", sid), sid=sid)
    assert received == ["snap-A"]


# --------------------------------------------------------------------------------------------
# 8-9: deterministic Ingress hit never forks Planner
# --------------------------------------------------------------------------------------------


def test_8_deterministic_ingress_normal_no_speculative_planner(monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr(pre_resolver_module, "classify_ingress", _fake_deterministic_ingress("normal"))
    monkeypatch.setattr(planner_turn_module, "plan_turn_attempt", _fake_planner_compute(calls=calls))
    sid = _sid("det-normal")
    pre, _outcome, _bucket = _run_pre_resolver_then_planner(_data("Выпал зуб, что делать?", sid), sid=sid)
    assert not isinstance(pre, AskOrchestrationResult)
    assert pre.planner_speculation is None
    # Planner still runs (sequentially) after a deterministic Ingress hit -- just never
    # via the speculative fork.
    assert len(calls) == 1


def test_9_deterministic_ingress_reject_planner_zero_calls(monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr(
        pre_resolver_module, "classify_ingress", _fake_deterministic_ingress("hard_stop_non_target")
    )
    monkeypatch.setattr(executor_module, "plan_turn_attempt", _fake_planner_compute(calls=calls))
    sid = _sid("det-reject")
    pre, outcome, _bucket = _run_pre_resolver_then_planner(_data("реклама казино", sid), sid=sid)
    assert isinstance(pre, AskOrchestrationResult)
    assert outcome is None
    assert len(calls) == 0


# --------------------------------------------------------------------------------------------
# 10-11: LLM-path Ingress normal uses parallel Planner; reject discards it
# --------------------------------------------------------------------------------------------


def test_10_ingress_llm_normal_uses_parallel_planner(monkeypatch) -> None:
    monkeypatch.setattr(pre_resolver_module, "classify_ingress", _fake_normal_ingress_via_llm())
    monkeypatch.setattr(executor_module, "plan_turn_attempt", _fake_planner_compute())
    sid = _sid("llm-normal")
    pre, outcome, _bucket = _run_pre_resolver_then_planner(_data("Что такое остеоинтеграция?", sid), sid=sid)
    assert not isinstance(pre, AskOrchestrationResult)
    assert isinstance(pre.planner_speculation, PlannerSpeculationHandle)
    assert outcome is not None


def test_11_ingress_llm_reject_planner_never_published(monkeypatch) -> None:
    publish_calls: list = []
    monkeypatch.setattr(pre_resolver_module, "classify_ingress", _fake_reject_ingress_via_llm())
    monkeypatch.setattr(executor_module, "plan_turn_attempt", _fake_planner_compute())
    monkeypatch.setattr(
        planner_turn_module, "publish_planner_attempt_frame", lambda **k: publish_calls.append(k)
    )
    sid = _sid("llm-reject")
    pre, outcome, _bucket = _run_pre_resolver_then_planner(_data("иди в интернете поищи", sid), sid=sid)
    assert isinstance(pre, AskOrchestrationResult)
    assert outcome is None
    assert publish_calls == []


# --------------------------------------------------------------------------------------------
# 12-14: discard/cancellation lifecycle
# --------------------------------------------------------------------------------------------


def test_12_reject_does_not_wait_for_slow_running_planner(monkeypatch) -> None:
    monkeypatch.setattr(pre_resolver_module, "classify_ingress", _fake_reject_ingress_via_llm())
    monkeypatch.setattr(executor_module, "plan_turn_attempt", _fake_planner_compute(delay=0.6))
    sid = _sid("reject-fast")
    t0 = time.monotonic()
    pre, _bucket = _run_pre_resolver(_data("спам спам спам", sid), sid=sid)
    elapsed = time.monotonic() - t0
    assert isinstance(pre, AskOrchestrationResult)
    assert elapsed < 0.3, elapsed  # must not block on the still-running 0.6s compute


def test_13_cancelled_future_releases_admission_capacity() -> None:
    handle = try_submit_planner_speculation(
        client_id="demo", sid="s1", q="q", history="", request_id="r1"
    )
    assert handle is not None
    discard_planner_speculation(handle)  # not yet started -> cancel() succeeds
    # Capacity must be free again: submitting PLANNER_SPECULATION_CAPACITY more should
    # all succeed without overload.
    fresh = [
        try_submit_planner_speculation(
            client_id="demo", sid=f"s{i}", q="q", history="", request_id=None
        )
        for i in range(PLANNER_SPECULATION_CAPACITY)
    ]
    try:
        assert all(h is not None for h in fresh)
    finally:
        for h in fresh:
            discard_planner_speculation(h)


def test_14_discarded_finished_future_leaves_no_unobserved_exception(monkeypatch) -> None:
    monkeypatch.setattr(
        executor_module, "plan_turn_attempt", _fake_planner_compute(raises=True)
    )
    handle = try_submit_planner_speculation(
        client_id="demo", sid="s1", q="q", history="", request_id="r1"
    )
    assert handle is not None
    time.sleep(0.05)  # let the worker actually start (so cancel() will fail below)
    discard_planner_speculation(handle)
    deadline = time.monotonic() + 2.0
    while not handle.future.done() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert handle.future.done()
    # future.exception() must not raise / must not be "never retrieved" -- _compute
    # already swallows the RuntimeError and returns a degraded PlannerAttempt, so the
    # future itself completed successfully (no exception stored at all).
    assert handle.future.exception() is None


# --------------------------------------------------------------------------------------------
# 15: lite -> full ingress retry forks Planner at most once
# --------------------------------------------------------------------------------------------


def test_15_ingress_retry_forks_planner_compute_exactly_once(monkeypatch) -> None:
    calls: list = []

    def _classify_with_internal_retry(question, *, client_id, sid, skip=False, on_llm_path=None):
        if on_llm_path is not None:
            on_llm_path()  # classify_ingress calls this once, before its (possibly
            # multi-request) LLM path -- an internal lite->full retry never calls it again.
        return IngressRouteResult(
            route="normal",
            confidence=0.9,
            reason="fake_llm_after_retry",
            policy_key=None,
            requested_service=None,
            source="llm",
            is_urgent=False,
        )

    monkeypatch.setattr(pre_resolver_module, "classify_ingress", _classify_with_internal_retry)
    monkeypatch.setattr(executor_module, "plan_turn_attempt", _fake_planner_compute(calls=calls))
    sid = _sid("retry-once")
    _run_pre_resolver_then_planner(_data("Делаете ли брекеты?", sid), sid=sid)
    assert len(calls) == 1


# --------------------------------------------------------------------------------------------
# 16: Planner compute exception preserves the existing fallback contract
# --------------------------------------------------------------------------------------------


def test_16_planner_compute_exception_preserves_fallback_contract(monkeypatch) -> None:
    monkeypatch.setattr(pre_resolver_module, "classify_ingress", _fake_normal_ingress_via_llm())
    monkeypatch.setattr(executor_module, "plan_turn_attempt", _fake_planner_compute(raises=True))
    handle = try_submit_planner_speculation(
        client_id="demo", sid="s1", q="q", history="", request_id="r1"
    )
    assert handle is not None
    attempt = join_planner_speculation(handle)
    assert attempt.status == "not_available"
    assert attempt.frame is None


# --------------------------------------------------------------------------------------------
# 17-18: executor overload fallback (Variant D)
# --------------------------------------------------------------------------------------------


def test_17_overload_plus_ingress_normal_runs_sequential_planner_once(monkeypatch) -> None:
    monkeypatch.setattr(executor_module._planner_speculation_admission, "acquire", lambda blocking=False: False)
    calls: list = []
    monkeypatch.setattr(pre_resolver_module, "classify_ingress", _fake_normal_ingress_via_llm())
    monkeypatch.setattr(planner_turn_module, "plan_turn_attempt", _fake_planner_compute(calls=calls))
    sid = _sid("overload-normal")
    pre, outcome, _bucket = _run_pre_resolver_then_planner(_data("Как ухаживать после имплантации?", sid), sid=sid)
    assert not isinstance(pre, AskOrchestrationResult)
    assert pre.planner_speculation is None
    assert outcome is not None
    assert len(calls) == 1


def test_18_overload_plus_ingress_reject_planner_zero_calls(monkeypatch) -> None:
    monkeypatch.setattr(executor_module._planner_speculation_admission, "acquire", lambda blocking=False: False)
    calls: list = []
    monkeypatch.setattr(pre_resolver_module, "classify_ingress", _fake_reject_ingress_via_llm())
    monkeypatch.setattr(executor_module, "plan_turn_attempt", _fake_planner_compute(calls=calls))
    sid = _sid("overload-reject")
    pre, _bucket = _run_pre_resolver(_data("оффтоп мусор", sid), sid=sid)
    assert isinstance(pre, AskOrchestrationResult)
    assert len(calls) == 0


# --------------------------------------------------------------------------------------------
# 19-20: no nested deadlock; bounded concurrency
# --------------------------------------------------------------------------------------------


def test_19_planner_executor_is_a_separate_pool_from_sse_worker_executor() -> None:
    assert executor_module._planner_speculation_executor is not app_module._sse_worker_executor


def test_19b_fork_join_completes_from_within_a_size_one_worker_pool(monkeypatch) -> None:
    """Simulates running the fork/join code from inside a PERF-1-style single-worker
    pool: if the Planner-compute executor were the same object, this would deadlock at
    capacity. Since it is a separate pool, this must complete quickly."""
    from concurrent.futures import ThreadPoolExecutor

    monkeypatch.setattr(pre_resolver_module, "classify_ingress", _fake_normal_ingress_via_llm())
    monkeypatch.setattr(executor_module, "plan_turn_attempt", _fake_planner_compute())
    sid = _sid("nested")

    outer_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="fake-sse-worker")
    try:
        future = outer_pool.submit(
            lambda: _run_pre_resolver_then_planner(_data("Какие импланты вы ставите?", sid), sid=sid)
        )
        pre, outcome, _bucket = future.result(timeout=5.0)
    finally:
        outer_pool.shutdown(wait=True)
    assert not isinstance(pre, AskOrchestrationResult)
    assert outcome is not None


def test_20_concurrent_submissions_stay_within_bounded_capacity(monkeypatch) -> None:
    in_flight = {"count": 0, "max": 0}
    lock = threading.Lock()

    def _plan(q, sid, client_id, *, history_override=None):
        with lock:
            in_flight["count"] += 1
            in_flight["max"] = max(in_flight["max"], in_flight["count"])
        time.sleep(0.15)
        with lock:
            in_flight["count"] -= 1
        return _NOT_AVAILABLE

    monkeypatch.setattr(executor_module, "plan_turn_attempt", _plan)
    handles = [
        try_submit_planner_speculation(
            client_id="demo", sid=f"s{i}", q="q", history="", request_id=None
        )
        for i in range(PLANNER_SPECULATION_CAPACITY + 4)
    ]
    try:
        started = sum(1 for h in handles if h is not None)
        assert started <= PLANNER_SPECULATION_CAPACITY
        for h in handles:
            if h is not None:
                join_planner_speculation(h)
        assert in_flight["max"] <= PLANNER_SPECULATION_CAPACITY
    finally:
        for h in handles:
            discard_planner_speculation(h)


# --------------------------------------------------------------------------------------------
# 21-22: /ask and /ask/stream parity
# --------------------------------------------------------------------------------------------


def test_21_and_22_ask_and_ask_stream_produce_same_ui_payload(monkeypatch) -> None:
    import orchestration.target_fullcontext_turn as target_turn_module
    from contracts.ask_orchestration import AskOrchestrationResult as _AOR

    q = "Сколько стоит консультация?"

    def _fake_orchestrate_ask_turn(data):
        return _AOR(
            kind="service_reply",
            q=data.get("q") or "",
            sid=data.get("sid") or "",
            client_id="demo",
            service_payload={"answer": "тестовый ответ", "meta": {}},
            service_doc_id=None,
            service_track_user=False,
            service_route="content",
            http_status=200,
        )

    monkeypatch.setattr(app_module, "_orchestrate_ask_turn", _fake_orchestrate_ask_turn)
    client = app_module.app.test_client()
    results = {}
    for endpoint in ("/ask", "/ask/stream"):
        sid = _sid(f"parity-{endpoint.replace('/', '_')}")
        resp = client.post(endpoint, json={"q": q, "sid": sid, "client_id": "demo"})
        assert resp.status_code == 200
        if endpoint == "/ask":
            results[endpoint] = resp.get_json()
        else:
            body = resp.get_data(as_text=True)
            ui_line = next(
                line for line in body.splitlines() if line.startswith("data: ") and "тестовый" in line
            )
            import json as _json

            results[endpoint] = _json.loads(ui_line[len("data: "):])
    assert results["/ask"]["answer"] == results["/ask/stream"]["answer"]


# --------------------------------------------------------------------------------------------
# 23-26: typed UI / contacts / availability / lead-situation-reset-ref short-circuits
# --------------------------------------------------------------------------------------------


def test_23_typed_ui_ref_click_never_starts_speculative_planner(monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr(executor_module, "plan_turn_attempt", _fake_planner_compute(calls=calls))
    sid = _sid("typed-ui")
    pre, bucket = _run_pre_resolver(
        {"q": "", "sid": sid, "client_id": "demo", "ref": "price:all_on_4"}, sid=sid
    )
    # ingress_skip=True on any ref click -> the fork point is never reached.
    assert len(calls) == 0
    if not isinstance(pre, AskOrchestrationResult):
        assert pre.planner_speculation is None


def test_23b_app_discards_speculation_when_typed_outcome_present(monkeypatch) -> None:
    discarded: list = []
    monkeypatch.setattr(app_module, "discard_planner_speculation", lambda h: discarded.append(h))
    monkeypatch.setattr(app_module, "run_pre_resolver_turn", lambda *a, **k: AskTurnContext(
        q="продолжить", sid="s1", client_id="demo", ref="scope:x", data={}, st={},
        planner_speculation=None,
    ))
    monkeypatch.setattr(app_module, "try_run_typed_ui_planner_turn", lambda **k: object())
    called_planner: list = []
    monkeypatch.setattr(app_module, "run_planner_turn", lambda **k: called_planner.append(k))
    monkeypatch.setattr(
        app_module,
        "orchestrate_target_fullcontext_turn",
        lambda **k: AskOrchestrationResult(kind="service_reply", q="", sid="s1", client_id="demo",
                                            service_payload={"answer": "", "meta": {}}),
    )
    app_module._orchestrate_ask_turn({"q": "продолжить", "sid": "s1", "client_id": "demo"})
    assert len(discarded) == 1
    assert called_planner == []


def test_24_contacts_ref_click_never_starts_speculative_planner(monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr(executor_module, "plan_turn_attempt", _fake_planner_compute(calls=calls))
    sid = _sid("contacts")
    _run_pre_resolver({"q": "", "sid": sid, "client_id": "demo", "ref": "contacts:phone"}, sid=sid)
    assert len(calls) == 0


def test_25_service_availability_ref_click_never_starts_speculative_planner(monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr(executor_module, "plan_turn_attempt", _fake_planner_compute(calls=calls))
    sid = _sid("availability")
    _run_pre_resolver(
        {"q": "", "sid": sid, "client_id": "demo", "ref": "service_availability:veneers"}, sid=sid
    )
    assert len(calls) == 0


def test_26_lead_situation_reset_never_start_speculative_planner(monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr(executor_module, "plan_turn_attempt", _fake_planner_compute(calls=calls))

    sid_reset = _sid("reset")
    _run_pre_resolver({"q": "/reset", "sid": sid_reset, "client_id": "demo"}, sid=sid_reset)
    assert len(calls) == 0

    monkeypatch.setattr(pre_resolver_module, "is_lead_context", lambda st: True)
    sid_lead = _sid("lead")
    _run_pre_resolver({"q": "меня зовут Иван", "sid": sid_lead, "client_id": "demo"}, sid=sid_lead)
    assert len(calls) == 0


# --------------------------------------------------------------------------------------------
# 27-28: prompts/models/schema unchanged; accepted-normal call count unchanged
# --------------------------------------------------------------------------------------------


def test_27_planner_and_ingress_prompts_models_unchanged() -> None:
    assert TURN_PLANNER_LLM_MODEL
    assert INGRESS_CLASSIFY_MODEL
    assert "route: content | price_lookup | price_concern | unknown." in PLANNER_SYSTEM_PROMPT
    assert "route=normal" in INGRESS_SYSTEM_PROMPT
    assert "route=hard_stop_non_target" in INGRESS_SYSTEM_PROMPT


def test_28_accepted_normal_turn_understanding_layer_call_count_is_two(monkeypatch) -> None:
    ingress_calls: list = []
    planner_calls: list = []

    def _classify(question, *, client_id, sid, skip=False, on_llm_path=None):
        ingress_calls.append(1)
        if on_llm_path is not None:
            on_llm_path()
        return IngressRouteResult(
            route="normal", confidence=0.9, reason="ok", policy_key=None,
            requested_service=None, source="llm", is_urgent=False,
        )

    monkeypatch.setattr(pre_resolver_module, "classify_ingress", _classify)
    monkeypatch.setattr(executor_module, "plan_turn_attempt", _fake_planner_compute(calls=planner_calls))
    sid = _sid("call-count")
    _run_pre_resolver_then_planner(_data("Какая гарантия на коронки?", sid), sid=sid)
    assert len(ingress_calls) == 1
    assert len(planner_calls) == 1


# --------------------------------------------------------------------------------------------
# 29: PERF-0 trace shows genuine overlap
# --------------------------------------------------------------------------------------------


def test_29_perf0_trace_shows_ingress_planner_overlap(monkeypatch) -> None:
    monkeypatch.setattr(
        pre_resolver_module, "classify_ingress", _fake_normal_ingress_via_llm(delay=0.2)
    )
    monkeypatch.setattr(executor_module, "plan_turn_attempt", _fake_planner_compute(delay=0.1))
    sid = _sid("perf0-overlap")
    _pre, _outcome, bucket = _run_pre_resolver_then_planner(_data("Что такое синус-лифтинг?", sid), sid=sid)
    marks = bucket.get("marks") or {}
    assert "planner_start" in marks and "ingress_end" in marks and "ingress_start" in marks
    # Planner started before Ingress finished -- genuine overlap, not sequential.
    assert marks["planner_start"] < marks["ingress_end"]
    assert marks["planner_start"] >= marks["ingress_start"]


# --------------------------------------------------------------------------------------------
# 30: structured logs contain no PII
# --------------------------------------------------------------------------------------------


def test_30_speculation_events_contain_no_pii(monkeypatch) -> None:
    logged: list = []

    def _spy_log_json(logger, message, **fields):
        logged.append((message, fields))

    monkeypatch.setattr(executor_module, "log_json", _spy_log_json)
    monkeypatch.setattr(pre_resolver_module, "classify_ingress", _fake_normal_ingress_via_llm())
    monkeypatch.setattr(executor_module, "plan_turn_attempt", _fake_planner_compute())
    sid = "s-real-looking-session-id-should-never-appear"
    q = "Мой телефон +7 900 123-45-67, перезвоните"
    _run_pre_resolver_then_planner(_data(q, sid), sid=sid)
    speculation_events = [(m, f) for m, f in logged if m.startswith("planner_speculation") or m.startswith("planner_parallel") or m.startswith("planner_compute")]
    assert speculation_events
    forbidden_keys = {"q", "answer", "sid", "contacts", "phone"}
    for _message, fields in speculation_events:
        assert not (forbidden_keys & set(fields.keys()))
        for value in fields.values():
            if isinstance(value, str):
                assert q not in value
                assert sid not in value
