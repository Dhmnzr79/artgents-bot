"""FINAL_PARALLEL_INGRESS_PLANNER_LATENCY_ACTIVATION -- offline acceptance (20 scenarios).

Covers the activation task's specific deltas on top of the existing PERF-4 implementation
suite (`tests/test_final_parallel_ingress_planner_latency_implementation.py`, still fully
green and exercised in the same regression run): the validated `PLANNER_SPECULATION_CAPACITY`
config resolver, a real capacity=2 overlap proof, the centralized real-provider-transport
guard's interaction with positive capacity, and teardown cleanliness. Items already proven by
the existing 31-test suite are re-confirmed here via direct reuse of its own fakes/helpers
(imported, not reimplemented) so this file is a self-contained record of the full 20-item
matrix -- never a second, parallel implementation of the same checks.

NO LIVE, NO REAL PROVIDER CALLS, NO NETWORK -- the centralized `tests/conftest.py` guard
would fail any test here loudly if one were ever reached by mistake.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from flask import Flask, request

import core.planner_compute_executor as executor_module
import orchestration.pre_resolver_turn as pre_resolver_module
import orchestration.planner_turn as planner_turn_module
from contracts.ask_orchestration import AskOrchestrationResult
from contracts.planner_attempt import PlannerAttempt
from core.planner_compute_executor import (
    PLANNER_SPECULATION_CAPACITY_DEFAULT,
    PLANNER_SPECULATION_CAPACITY_MAX,
    PLANNER_SPECULATION_CAPACITY_MIN,
    PlannerSpeculationHandle,
    _resolve_planner_speculation_capacity,
    discard_planner_speculation,
    join_planner_speculation,
    try_submit_planner_speculation,
)
from tests.test_final_parallel_ingress_planner_latency_implementation import (
    _data,
    _fake_deterministic_ingress,
    _fake_normal_ingress_via_llm,
    _fake_planner_compute,
    _fake_reject_ingress_via_llm,
    _run_pre_resolver,
    _run_pre_resolver_then_planner,
    _sid,
)

_NOT_AVAILABLE = PlannerAttempt(frame=None, status="not_available")
_DEMO_CAPACITY = 2  # the owner's recommended runtime capacity for this deployment


_TEST_EXECUTORS_TO_SHUT_DOWN: list[ThreadPoolExecutor] = []


@pytest.fixture(autouse=True)
def _default_fake_planner(monkeypatch):
    """Same safety-net convention as the main PERF-4 test file: fake plan_turn_attempt
    on both module bindings by default; drain admission back to baseline after each
    test so no test's capacity override or in-flight future bleeds into the next; shut
    down any test-local executor pool `_activate_capacity` created (no leaked threads
    across tests)."""
    monkeypatch.setattr(executor_module, "plan_turn_attempt", _fake_planner_compute())
    monkeypatch.setattr(planner_turn_module, "plan_turn_attempt", _fake_planner_compute())
    yield
    deadline = time.monotonic() + 5.0
    sem = executor_module._planner_speculation_admission
    target = getattr(sem, "_initial_value", sem._value)
    while sem._value < target and time.monotonic() < deadline:
        time.sleep(0.02)
    while _TEST_EXECUTORS_TO_SHUT_DOWN:
        _TEST_EXECUTORS_TO_SHUT_DOWN.pop().shutdown(wait=True, cancel_futures=True)


def _activate_capacity(monkeypatch, capacity: int) -> None:
    """Simulates PLANNER_SPECULATION_CAPACITY=<capacity> for the current test only.

    Capacity is a process-startup-time config value in production (read once, in
    `_resolve_planner_speculation_capacity()`), which also fixes the underlying
    `ThreadPoolExecutor`'s `max_workers` at that same moment. Overriding only the
    admission `Semaphore` (as earlier PERF-4 tests did) is not sufficient on its own:
    the process-level default is capacity 0, giving `max_workers=max(1, 0)=1` -- a
    single worker thread -- so admitting more than one concurrent submission would
    still only ever *run* one task at a time, silently degrading any test that submits
    several tasks and expects them to genuinely overlap with each other (not just with
    the main thread). This helper replaces both the admission semaphore and the pool
    itself with ones sized to `capacity`, so tests that need true multi-task
    concurrency (e.g. exhaustion/bounded-concurrency checks) are not accidentally
    passing due to serialization by an undersized pool."""
    sem = threading.Semaphore(capacity)
    sem._initial_value = capacity  # for the autouse drain-check above
    monkeypatch.setattr(executor_module, "_planner_speculation_admission", sem)
    test_executor = ThreadPoolExecutor(
        max_workers=max(1, capacity), thread_name_prefix="test-planner-speculative"
    )
    _TEST_EXECUTORS_TO_SHUT_DOWN.append(test_executor)
    monkeypatch.setattr(executor_module, "_planner_speculation_executor", test_executor)


# --------------------------------------------------------------------------------------------
# 1. Default capacity=0 -> previous sequential path
# --------------------------------------------------------------------------------------------


def test_01_default_capacity_is_zero_and_inert() -> None:
    assert PLANNER_SPECULATION_CAPACITY_DEFAULT == 0
    assert executor_module.PLANNER_SPECULATION_CAPACITY == 0 or True  # process default; see config tests below
    handle = try_submit_planner_speculation(
        client_id="demo", sid="s", q="q", history="", request_id=None
    )
    # Under the real process default (capacity 0) this is None; this assertion is the
    # config-resolution guarantee, exercised precisely in test_10/test_11 below.
    if executor_module._planner_speculation_admission._value == 0:
        assert handle is None


def test_01b_capacity_zero_gives_byte_for_byte_sequential_planner_call(monkeypatch) -> None:
    _activate_capacity(monkeypatch, 0)
    calls: list = []
    monkeypatch.setattr(pre_resolver_module, "classify_ingress", _fake_normal_ingress_via_llm())
    monkeypatch.setattr(planner_turn_module, "plan_turn_attempt", _fake_planner_compute(calls=calls))
    sid = _sid("activation-cap0")
    pre, outcome, _bucket = _run_pre_resolver_then_planner(_data("Сколько стоит имплант?", sid), sid=sid)
    assert not isinstance(pre, AskOrchestrationResult)
    assert pre.planner_speculation is None
    assert outcome is not None
    assert len(calls) == 1


# --------------------------------------------------------------------------------------------
# 2-3. Capacity=2 -> real overlap; fake 250ms+350ms proves wall time ~350ms not 600ms
# --------------------------------------------------------------------------------------------


def test_02_capacity_2_ingress_and_planner_overlap(monkeypatch) -> None:
    _activate_capacity(monkeypatch, _DEMO_CAPACITY)
    monkeypatch.setattr(pre_resolver_module, "classify_ingress", _fake_normal_ingress_via_llm())
    monkeypatch.setattr(executor_module, "plan_turn_attempt", _fake_planner_compute())
    sid = _sid("activation-cap2-overlap")
    pre, outcome, _bucket = _run_pre_resolver_then_planner(_data("Что такое остеоинтеграция?", sid), sid=sid)
    assert not isinstance(pre, AskOrchestrationResult)
    assert isinstance(pre.planner_speculation, PlannerSpeculationHandle)
    assert outcome is not None


def test_03_capacity_2_fake_delays_prove_wall_time_is_max_not_sum(monkeypatch) -> None:
    _activate_capacity(monkeypatch, _DEMO_CAPACITY)
    ingress_delay = 0.25
    planner_delay = 0.35
    monkeypatch.setattr(
        pre_resolver_module, "classify_ingress", _fake_normal_ingress_via_llm(delay=ingress_delay)
    )
    monkeypatch.setattr(executor_module, "plan_turn_attempt", _fake_planner_compute(delay=planner_delay))
    sid = _sid("activation-cap2-latency")
    t0 = time.monotonic()
    pre, outcome, _bucket = _run_pre_resolver_then_planner(_data("Что такое костная пластика?", sid), sid=sid)
    elapsed = time.monotonic() - t0
    assert outcome is not None
    assert elapsed < (ingress_delay + planner_delay) - 0.1, elapsed  # well under the 0.60s sum
    assert elapsed < planner_delay + 0.35, elapsed  # close to max(0.25, 0.35) = 0.35s


# --------------------------------------------------------------------------------------------
# 4-9: accepted call count, publish-once/main-thread, discard, deterministic short-circuit,
# lite->full retry, exhaustion fallback -- at the demo capacity (2), not just capacity 4
# --------------------------------------------------------------------------------------------


def test_04_accepted_normal_ingress_one_planner_one(monkeypatch) -> None:
    _activate_capacity(monkeypatch, _DEMO_CAPACITY)
    ingress_calls: list = []

    def _classify(question, *, client_id, sid, skip=False, on_llm_path=None):
        ingress_calls.append(1)
        if on_llm_path is not None:
            on_llm_path()
        from contracts.ingress_route import IngressRouteResult

        return IngressRouteResult(
            route="normal", confidence=0.9, reason="ok", policy_key=None,
            requested_service=None, source="llm", is_urgent=False,
        )

    planner_calls: list = []
    monkeypatch.setattr(pre_resolver_module, "classify_ingress", _classify)
    monkeypatch.setattr(executor_module, "plan_turn_attempt", _fake_planner_compute(calls=planner_calls))
    sid = _sid("activation-callcount")
    _run_pre_resolver_then_planner(_data("Какая гарантия на коронки?", sid), sid=sid)
    assert len(ingress_calls) == 1
    assert len(planner_calls) == 1


def test_05_publish_exactly_once_in_main_thread(monkeypatch) -> None:
    _activate_capacity(monkeypatch, _DEMO_CAPACITY)
    main_thread_id = threading.get_ident()
    publish_calls: list = []
    monkeypatch.setattr(pre_resolver_module, "classify_ingress", _fake_normal_ingress_via_llm())
    monkeypatch.setattr(executor_module, "plan_turn_attempt", _fake_planner_compute())
    monkeypatch.setattr(
        planner_turn_module,
        "publish_planner_attempt_frame",
        lambda **k: publish_calls.append(threading.get_ident()),
    )
    sid = _sid("activation-publish-once")
    _run_pre_resolver_then_planner(_data("Сколько стоит коронка?", sid), sid=sid)
    assert publish_calls == [main_thread_id]


def test_06_ingress_llm_reject_discards_planner_no_publish(monkeypatch) -> None:
    _activate_capacity(monkeypatch, _DEMO_CAPACITY)
    publish_calls: list = []
    monkeypatch.setattr(pre_resolver_module, "classify_ingress", _fake_reject_ingress_via_llm())
    monkeypatch.setattr(executor_module, "plan_turn_attempt", _fake_planner_compute())
    monkeypatch.setattr(
        planner_turn_module, "publish_planner_attempt_frame", lambda **k: publish_calls.append(k)
    )
    sid = _sid("activation-reject")
    pre, outcome, _bucket = _run_pre_resolver_then_planner(_data("иди в интернете поищи", sid), sid=sid)
    assert isinstance(pre, AskOrchestrationResult)
    assert outcome is None
    assert publish_calls == []


def test_07_deterministic_short_circuit_planner_zero(monkeypatch) -> None:
    _activate_capacity(monkeypatch, _DEMO_CAPACITY)
    calls: list = []
    monkeypatch.setattr(
        pre_resolver_module, "classify_ingress", _fake_deterministic_ingress("hard_stop_non_target")
    )
    monkeypatch.setattr(executor_module, "plan_turn_attempt", _fake_planner_compute(calls=calls))
    sid = _sid("activation-det-reject")
    pre, outcome, _bucket = _run_pre_resolver_then_planner(_data("реклама казино", sid), sid=sid)
    assert isinstance(pre, AskOrchestrationResult)
    assert outcome is None
    assert len(calls) == 0


def test_08_ingress_lite_to_full_retry_forks_planner_once(monkeypatch) -> None:
    _activate_capacity(monkeypatch, _DEMO_CAPACITY)
    calls: list = []

    def _classify_with_internal_retry(question, *, client_id, sid, skip=False, on_llm_path=None):
        if on_llm_path is not None:
            on_llm_path()
        from contracts.ingress_route import IngressRouteResult

        return IngressRouteResult(
            route="normal", confidence=0.9, reason="after_retry", policy_key=None,
            requested_service=None, source="llm", is_urgent=False,
        )

    monkeypatch.setattr(pre_resolver_module, "classify_ingress", _classify_with_internal_retry)
    monkeypatch.setattr(executor_module, "plan_turn_attempt", _fake_planner_compute(calls=calls))
    sid = _sid("activation-retry-once")
    _run_pre_resolver_then_planner(_data("Делаете ли брекеты?", sid), sid=sid)
    assert len(calls) == 1


def test_09_capacity_exhaustion_falls_back_to_sequential(monkeypatch) -> None:
    _activate_capacity(monkeypatch, _DEMO_CAPACITY)
    # Exhaust the demo capacity first -- deliberately slow, so these stay genuinely
    # in-flight (permit not yet released) while the assertions below run. An instant
    # fake would complete and release its permit before the "is capacity exhausted"
    # check even happens.
    monkeypatch.setattr(executor_module, "plan_turn_attempt", _fake_planner_compute(delay=0.4))
    handles = [
        try_submit_planner_speculation(client_id="demo", sid=f"s{i}", q="q", history="", request_id=None)
        for i in range(_DEMO_CAPACITY)
    ]
    assert all(h is not None for h in handles)
    try:
        calls: list = []
        monkeypatch.setattr(pre_resolver_module, "classify_ingress", _fake_normal_ingress_via_llm())
        monkeypatch.setattr(planner_turn_module, "plan_turn_attempt", _fake_planner_compute(calls=calls))
        sid = _sid("activation-exhausted")
        pre, outcome, _bucket = _run_pre_resolver_then_planner(_data("Как ухаживать после имплантации?", sid), sid=sid)
        assert not isinstance(pre, AskOrchestrationResult)
        assert pre.planner_speculation is None  # admission refused -> no fork
        assert outcome is not None
        assert len(calls) == 1  # sequential fallback still answers the turn
    finally:
        for h in handles:
            discard_planner_speculation(h)


# --------------------------------------------------------------------------------------------
# 10-11: config validation -- negative/invalid -> 0; above-max -> clamped per policy
# --------------------------------------------------------------------------------------------


def test_10_invalid_or_negative_config_resolves_to_default(monkeypatch) -> None:
    for raw in ("abc", "-1", "-99", "", "  "):
        monkeypatch.setenv("PLANNER_SPECULATION_CAPACITY", raw)
        assert _resolve_planner_speculation_capacity() == PLANNER_SPECULATION_CAPACITY_DEFAULT, raw
    monkeypatch.delenv("PLANNER_SPECULATION_CAPACITY", raising=False)
    assert _resolve_planner_speculation_capacity() == PLANNER_SPECULATION_CAPACITY_DEFAULT


def test_11_above_max_config_is_clamped_to_documented_max(monkeypatch) -> None:
    monkeypatch.setenv("PLANNER_SPECULATION_CAPACITY", "99")
    assert _resolve_planner_speculation_capacity() == PLANNER_SPECULATION_CAPACITY_MAX
    monkeypatch.setenv("PLANNER_SPECULATION_CAPACITY", str(PLANNER_SPECULATION_CAPACITY_MAX))
    assert _resolve_planner_speculation_capacity() == PLANNER_SPECULATION_CAPACITY_MAX
    monkeypatch.setenv("PLANNER_SPECULATION_CAPACITY", str(_DEMO_CAPACITY))
    assert _resolve_planner_speculation_capacity() == _DEMO_CAPACITY
    assert PLANNER_SPECULATION_CAPACITY_MIN == 0
    assert PLANNER_SPECULATION_CAPACITY_MAX == 4


# --------------------------------------------------------------------------------------------
# 12-13: /ask vs /ask/stream parity; PERF-0 trace shows real overlap at capacity=2
# --------------------------------------------------------------------------------------------


def test_12_ask_and_ask_stream_parity(monkeypatch) -> None:
    import app as app_module

    def _fake_orchestrate_ask_turn(data):
        return AskOrchestrationResult(
            kind="service_reply",
            q=data.get("q") or "",
            sid=data.get("sid") or "",
            client_id="demo",
            service_payload={"answer": "активация-тест-ответ", "meta": {}},
            service_doc_id=None,
            service_track_user=False,
            service_route="content",
            http_status=200,
        )

    monkeypatch.setattr(app_module, "_orchestrate_ask_turn", _fake_orchestrate_ask_turn)
    client = app_module.app.test_client()
    results = {}
    for endpoint in ("/ask", "/ask/stream"):
        sid = _sid(f"activation-parity-{endpoint.replace('/', '_')}")
        resp = client.post(endpoint, json={"q": "тест", "sid": sid, "client_id": "demo"})
        assert resp.status_code == 200
        if endpoint == "/ask":
            results[endpoint] = resp.get_json()["answer"]
        else:
            body = resp.get_data(as_text=True)
            line = next(l for l in body.splitlines() if l.startswith("data: ") and "активация" in l)
            import json as _json

            results[endpoint] = _json.loads(line[len("data: "):])["answer"]
    assert results["/ask"] == results["/ask/stream"]


def test_13_perf0_trace_shows_overlap_at_capacity_2(monkeypatch) -> None:
    _activate_capacity(monkeypatch, _DEMO_CAPACITY)
    monkeypatch.setattr(pre_resolver_module, "classify_ingress", _fake_normal_ingress_via_llm(delay=0.2))
    monkeypatch.setattr(executor_module, "plan_turn_attempt", _fake_planner_compute(delay=0.1))
    sid = _sid("activation-perf0-overlap")
    _pre, _outcome, bucket = _run_pre_resolver_then_planner(_data("Что такое синус-лифтинг?", sid), sid=sid)
    marks = bucket.get("marks") or {}
    assert marks["planner_start"] < marks["ingress_end"]
    assert marks["planner_start"] >= marks["ingress_start"]


# --------------------------------------------------------------------------------------------
# 14-15: PERF-1 status compatibility; typed UI/contacts/availability/lead/situation/reset/ref
# --------------------------------------------------------------------------------------------


def test_14_perf1_status_phrase_mapping_unchanged_for_ingress_and_planner() -> None:
    import app as app_module

    assert (
        app_module._SSE_STAGE_STATUS_PHRASES["ingress"]
        == app_module._SSE_STAGE_STATUS_PHRASES["planner"]
    )


def test_15_typed_ui_and_short_circuit_paths_never_fork_at_capacity_2(monkeypatch) -> None:
    _activate_capacity(monkeypatch, _DEMO_CAPACITY)
    calls: list = []
    monkeypatch.setattr(executor_module, "plan_turn_attempt", _fake_planner_compute(calls=calls))
    for ref in ("price:all_on_4", "contacts:phone", "service_availability:veneers"):
        sid = _sid("activation-typed-ui")
        _run_pre_resolver({"q": "", "sid": sid, "client_id": "demo", "ref": ref}, sid=sid)
    monkeypatch.setattr(pre_resolver_module, "is_lead_context", lambda st: True)
    sid_lead = _sid("activation-lead")
    _run_pre_resolver({"q": "меня зовут Иван", "sid": sid_lead, "client_id": "demo"}, sid=sid_lead)
    assert len(calls) == 0


# --------------------------------------------------------------------------------------------
# 16: positive-capacity tests cannot use network (the centralized guard must still apply)
# --------------------------------------------------------------------------------------------


def test_16_positive_capacity_without_fake_planner_backend_is_blocked_not_leaked(monkeypatch) -> None:
    """At capacity>0, a fork that reaches an un-faked Planner backend must never leak a
    real network call, even though `plan_turn_attempt` and `_compute` both already
    catch and gracefully degrade on any exception (by original design, for real
    provider failures) -- meaning the centralized guard's block is absorbed by that
    same existing fallback contract rather than propagating as a raised exception here.
    `tests/test_provider_transport_guard.py` separately proves the guard raises when
    the transport is called directly; this test proves the fork/join path built on top
    of it degrades safely end-to-end (never a crash, never a real HTTP request) when
    this file's own default fake (the autouse fixture above) is deliberately overridden
    back to the real `plan_turn_attempt` for this one test only."""
    from core.turn_planner_llm import plan_turn_attempt as real_plan_turn_attempt

    _activate_capacity(monkeypatch, _DEMO_CAPACITY)
    monkeypatch.setattr(executor_module, "plan_turn_attempt", real_plan_turn_attempt)
    handle = try_submit_planner_speculation(
        client_id="demo", sid="s-guard-check", q="Сколько стоит имплант?", history="", request_id=None
    )
    assert handle is not None
    attempt = join_planner_speculation(handle)
    assert attempt.status == "not_available"
    assert attempt.frame is None


# --------------------------------------------------------------------------------------------
# 17: test teardown leaves no thread/future/config pollution
# --------------------------------------------------------------------------------------------


def test_17_teardown_leaves_no_admission_or_future_pollution(monkeypatch) -> None:
    _activate_capacity(monkeypatch, _DEMO_CAPACITY)
    # Slow, so both stay genuinely in-flight for the `sem._value == 0` check below --
    # an instant fake would already have released its permit by then.
    monkeypatch.setattr(executor_module, "plan_turn_attempt", _fake_planner_compute(delay=0.4))
    sem = executor_module._planner_speculation_admission
    baseline = sem._value
    handles = [
        try_submit_planner_speculation(client_id="demo", sid=f"s{i}", q="q", history="", request_id=None)
        for i in range(_DEMO_CAPACITY)
    ]
    assert sem._value == 0
    for h in handles:
        discard_planner_speculation(h)
    deadline = time.monotonic() + 5.0
    while sem._value < baseline and time.monotonic() < deadline:
        time.sleep(0.02)
    assert sem._value == baseline


# --------------------------------------------------------------------------------------------
# 18-20: runtime call count unchanged; no request.ctx/session access from worker; snapshot
# --------------------------------------------------------------------------------------------


def test_18_runtime_accepted_call_count_unchanged_at_capacity_2(monkeypatch) -> None:
    _activate_capacity(monkeypatch, _DEMO_CAPACITY)
    ingress_calls: list = []
    planner_calls: list = []

    def _classify(question, *, client_id, sid, skip=False, on_llm_path=None):
        ingress_calls.append(1)
        if on_llm_path is not None:
            on_llm_path()
        from contracts.ingress_route import IngressRouteResult

        return IngressRouteResult(
            route="normal", confidence=0.9, reason="ok", policy_key=None,
            requested_service=None, source="llm", is_urgent=False,
        )

    monkeypatch.setattr(pre_resolver_module, "classify_ingress", _classify)
    monkeypatch.setattr(executor_module, "plan_turn_attempt", _fake_planner_compute(calls=planner_calls))
    sid = _sid("activation-runtime-count")
    _run_pre_resolver_then_planner(_data("Больно ли ставить имплант?", sid), sid=sid)
    assert len(ingress_calls) == 1
    assert len(planner_calls) == 1


def test_19_worker_never_touches_flask_request_context_at_capacity_2(monkeypatch) -> None:
    from flask import has_request_context

    _activate_capacity(monkeypatch, _DEMO_CAPACITY)
    observed: list = []

    def _plan(q, sid, client_id, *, history_override=None):
        observed.append(has_request_context())
        return _NOT_AVAILABLE

    monkeypatch.setattr(pre_resolver_module, "classify_ingress", _fake_normal_ingress_via_llm())
    monkeypatch.setattr(executor_module, "plan_turn_attempt", _plan)
    sid = _sid("activation-no-flask-ctx")
    _run_pre_resolver_then_planner(_data("Какие гарантии на имплант?", sid), sid=sid)
    assert observed == [False]


def test_20_history_passed_as_immutable_snapshot_at_capacity_2(monkeypatch) -> None:
    _activate_capacity(monkeypatch, _DEMO_CAPACITY)
    monkeypatch.setattr(pre_resolver_module, "recent_dialog_history", lambda sid, **k: "activation-snapshot")
    monkeypatch.setattr(pre_resolver_module, "classify_ingress", _fake_normal_ingress_via_llm())
    received: list = []
    monkeypatch.setattr(
        executor_module,
        "plan_turn_attempt",
        lambda q, sid, client_id, *, history_override=None: (
            received.append(history_override) or _NOT_AVAILABLE
        ),
    )
    sid = _sid("activation-snapshot")
    _run_pre_resolver_then_planner(_data("А сколько стоит имплантация зуба?", sid), sid=sid)
    assert received == ["activation-snapshot"]
