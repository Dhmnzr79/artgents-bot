"""PERF-1 Phase 2 implementation acceptance matrix (early SSE status streaming).

Covers TASK.md § FINAL_EARLY_SSE_STATUS_STREAMING / PERF-1 acceptance rows 1-21.
No LIVE/LLM/network anywhere: Ingress/Planner/Boundary/Composer/Verifier are all
fake/stubbed, matching the pattern already established by the PERF-0 test suite.
"""

from __future__ import annotations

import json
import queue
import threading
import time
import uuid

import pytest
from flask import Flask, request

from contracts.planner_attempt import PlannerAttempt
from core.runtime_turn_frame import publish_planner_attempt_frame
from core.target_runtime_turn import run_target_fullcontext_runtime_turn
from core.target_sse_worker_context import (
    _status_sink_var,
    current_status_sink,
    current_worker_client_id,
    worker_execution_context,
)
from core.turn_frame_from_raw import build_turn_frame_from_raw
from orchestration.context import AskTurnContext
from orchestration.planner_turn import PlannerTurnOutcome
from session import mem_get, mem_reset
from tests.test_target_boundary_enforced_fullcontext_response import (
    PRICE_TEXT,
    RecordingComposerBackend,
    RecordingSemanticBackend,
)

_ALLOWED_TOPICS = frozenset({"implantation", "doctors", "clinic"})
_ALLOWED_SERVICES = frozenset({"all_on_4"})


# --- shared fixtures --------------------------------------------------------


class BackendPayload:
    def __init__(self, decision: str, confidence: float) -> None:
        self.decision = decision
        self.confidence = confidence


class RecordingBoundaryBackend:
    def __init__(self, payload: object, *, delay: float = 0.0) -> None:
        self.payload = payload
        self.delay = delay
        self.invocations: list[object] = []

    def classify(self, invocation: object, /) -> object:
        self.invocations.append(invocation)
        if self.delay:
            time.sleep(self.delay)
        return self.payload


class _FailingBoundaryBackend:
    """Backend failure is fail-closed internally (uncertain) -> terminal enforcement."""

    def classify(self, invocation: object, /) -> object:
        raise RuntimeError("boundary backend unavailable")


class _RaisingComposerBackend:
    def generate(self, invocation, /):
        raise RuntimeError("composer backend unavailable")


def _frame(**overrides: object):
    payload: dict[str, object] = {
        "route": "content",
        "aspects": ["price"],
        "primary_aspect": "price",
        "service_id": "all_on_4",
        "topic": "implantation",
        "topic_confidence": 0.9,
    }
    payload.update(overrides)
    return build_turn_frame_from_raw(
        payload,
        allowed_topics=_ALLOWED_TOPICS,
        allowed_service_ids=_ALLOWED_SERVICES,
    )


def _install_turn_frame(frame) -> None:
    publish_planner_attempt_frame(attempt=PlannerAttempt(frame=frame, status="ok"))


@pytest.fixture(autouse=True)
def _clear_cache():
    from core.target_runtime_client_context import clear_target_runtime_client_context_cache

    clear_target_runtime_client_context_cache()
    yield
    clear_target_runtime_client_context_cache()


def _fake_backends(*, boundary_delay: float = 0.0):
    return (
        RecordingComposerBackend(PRICE_TEXT),
        RecordingSemanticBackend(),
        RecordingBoundaryBackend(BackendPayload("none", 0.95), delay=boundary_delay),
    )


def _setup_http_fakes(monkeypatch: pytest.MonkeyPatch, app_module, *, boundary_delay: float = 0.0):
    import orchestration.target_fullcontext_turn as target_turn_module

    composer, semantic, boundary = _fake_backends(boundary_delay=boundary_delay)
    monkeypatch.setattr(
        target_turn_module, "_default_target_runtime_backends", lambda: (composer, semantic, boundary)
    )
    monkeypatch.setattr(app_module, "run_planner_turn", lambda **k: PlannerTurnOutcome("content", None))
    monkeypatch.setattr(
        "core.target_runtime_turn.load_runtime_turn_frame",
        lambda: _frame(primary_aspect="price", aspects=["price"]),
    )
    return composer, semantic, boundary


def _stub_pre_resolver(monkeypatch: pytest.MonkeyPatch, app_module, *, q: str, sid: str) -> None:
    ctx = AskTurnContext(
        q=q, sid=sid, client_id="demo", ref="", data={"q": q, "sid": sid, "client_id": "demo"}, st={}
    )
    monkeypatch.setattr(app_module, "run_pre_resolver_turn", lambda *a, **k: ctx)


def _read_sse_events(resp) -> list[tuple[float, str, dict]]:
    """(elapsed_seconds_since_first_chunk, event_name, data_dict), using real
    wall-clock arrival times from the lazily-iterated WSGI iterable (never
    resp.data, which would force full buffering and destroy timing)."""
    t0 = time.monotonic()
    buffer = ""
    events: list[tuple[float, str, dict]] = []
    current_event: str | None = None
    for chunk in resp.response:
        elapsed = time.monotonic() - t0
        buffer += chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.rstrip("\r")
            if line.startswith("event: "):
                current_event = line[len("event: "):].strip()
            elif line.startswith("data: "):
                raw = line[len("data: "):]
                try:
                    data = json.loads(raw) if raw.strip() else {}
                except Exception:
                    data = {}
                if current_event:
                    events.append((elapsed, current_event, data))
                current_event = None
    return events


def _post_stream(client, *, q: str, sid: str):
    return client.post("/ask/stream", json={"q": q, "sid": sid, "client_id": "demo"})


# --- Rows 1/2: first event before a delayed stage completes ----------------


def test_first_sse_event_before_delayed_boundary_and_measurable_pause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app as app_module

    sid = f"perf1-delay-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _setup_http_fakes(monkeypatch, app_module, boundary_delay=0.4)
    _stub_pre_resolver(monkeypatch, app_module, q="Сколько стоит All-on-4?", sid=sid)

    client = app_module.app.test_client()
    resp = _post_stream(client, q="Сколько стоит All-on-4?", sid=sid)
    assert resp.status_code == 200
    events = _read_sse_events(resp)

    assert events, "expected at least one SSE event"
    first_elapsed, first_event, first_data = events[0]
    assert first_event == "status"
    assert first_elapsed < 0.3, f"first server event too slow: {first_elapsed:.3f}s"

    ui_events = [e for e in events if e[1] == "ui"]
    assert len(ui_events) == 1
    ui_elapsed = ui_events[0][0]
    # measurable pause: the delayed boundary (0.4s) must show up as real elapsed time
    assert ui_elapsed - first_elapsed > 0.2, (first_elapsed, ui_elapsed)


# --- Row 3: generic FullContext status order ---------------------------


def test_generic_fullcontext_status_order_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    sid = f"perf1-order-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _setup_http_fakes(monkeypatch, app_module)
    _stub_pre_resolver(monkeypatch, app_module, q="Сколько стоит All-on-4?", sid=sid)

    client = app_module.app.test_client()
    resp = _post_stream(client, q="Сколько стоит All-on-4?", sid=sid)
    events = _read_sse_events(resp)

    status_messages = [data.get("message") for _, name, data in events if name == "status"]
    valid_phrases = {
        "Проверяю вопрос",
        "Ищу информацию в материалах клиники",
        "Готовлю ответ",
    }
    assert status_messages, "expected at least the initial status"
    for msg in status_messages:
        assert msg in valid_phrases, msg
    # no immediate duplicate
    for a, b in zip(status_messages, status_messages[1:]):
        assert a != b
    # exactly one ui, one done, done last
    kinds = [name for _, name, _ in events]
    assert kinds.count("ui") == 1
    assert kinds.count("done") == 1
    assert kinds[-1] == "done"


# --- Rows 4/5: structured contacts / service availability skip status ------


def test_structured_contact_emits_no_boundary_composer_verifier_status() -> None:
    received: list[str] = []

    def _sink(stage_name: str, _event: str) -> None:
        received.append(stage_name)

    frame = _frame(
        aspects=["contact_phone"],
        primary_aspect="contact_phone",
        service_id=None,
        topic="clinic",
    )
    composer, semantic, boundary = _fake_backends()
    sid = f"perf1-contact-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    app = Flask(__name__)
    with app.test_request_context():
        request.ctx = {}
        token = _status_sink_var.set(_sink)
        try:
            _install_turn_frame(frame)
            outcome = run_target_fullcontext_runtime_turn(
                client_id="demo",
                sid=sid,
                user_message="Какой у вас телефон?",
                composer_backend=composer,
                semantic_backend=semantic,
                boundary_backend=boundary,
            )
        finally:
            _status_sink_var.reset(token)
    assert outcome.widget.kind == "materialized"
    assert "boundary" not in received
    assert "composer" not in received
    assert "verifier_deterministic" not in received
    assert "verifier_semantic" not in received


def test_structured_service_availability_emits_no_skipped_status() -> None:
    received: list[str] = []

    def _sink(stage_name: str, _event: str) -> None:
        received.append(stage_name)

    frame = _frame(
        aspects=["service_availability"],
        primary_aspect="service_availability",
        service_id="all_on_4",
        topic="clinic",
    )
    composer, semantic, boundary = _fake_backends()
    sid = f"perf1-avail-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    app = Flask(__name__)
    with app.test_request_context():
        request.ctx = {}
        token = _status_sink_var.set(_sink)
        try:
            _install_turn_frame(frame)
            run_target_fullcontext_runtime_turn(
                client_id="demo",
                sid=sid,
                user_message="Делаете ли вы All-on-4?",
                composer_backend=composer,
                semantic_backend=semantic,
                boundary_backend=boundary,
            )
        finally:
            _status_sink_var.reset(token)
    assert "boundary" not in received
    assert "composer" not in received
    assert "verifier_deterministic" not in received
    assert "verifier_semantic" not in received


# --- Row 6: typed UI click shows no Planner status --------------------------


def test_typed_ui_click_emits_no_planner_status() -> None:
    from contracts.ui_scope_action import UiScopeAction
    from orchestration.typed_ui_planner_turn import try_run_typed_ui_planner_turn

    received: list[str] = []

    def _sink(stage_name: str, _event: str) -> None:
        received.append(stage_name)

    app = Flask(__name__)
    with app.test_request_context():
        request.ctx = {}
        request.ctx["current_ui_scope_action"] = UiScopeAction(
            ref="scope:implantation:few_teeth",
            topic="implantation",
            extent="few_teeth",
        ).model_dump()
        token = _status_sink_var.set(_sink)
        try:
            outcome = try_run_typed_ui_planner_turn(
                sid="perf1-typed-ui",
                client_id="demo",
                enqueue_resolver_trace=lambda **k: None,
            )
        finally:
            _status_sink_var.reset(token)
    assert outcome is not None
    assert "planner" not in received


# --- Row 7: terminal / fallback ends with exactly one ui + one done --------


def test_terminal_fallback_ends_with_one_ui_one_done(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module
    import orchestration.target_fullcontext_turn as target_turn_module

    sid = f"perf1-terminal-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    composer = RecordingComposerBackend(PRICE_TEXT)
    semantic = RecordingSemanticBackend()
    boundary = _FailingBoundaryBackend()
    monkeypatch.setattr(
        target_turn_module, "_default_target_runtime_backends", lambda: (composer, semantic, boundary)
    )
    monkeypatch.setattr(app_module, "run_planner_turn", lambda **k: PlannerTurnOutcome("content", None))
    monkeypatch.setattr(
        "core.target_runtime_turn.load_runtime_turn_frame", lambda: _frame()
    )
    _stub_pre_resolver(monkeypatch, app_module, q="Можно ли мне?", sid=sid)

    client = app_module.app.test_client()
    resp = _post_stream(client, q="Можно ли мне?", sid=sid)
    assert resp.status_code == 200
    events = _read_sse_events(resp)
    kinds = [name for _, name, _ in events]
    assert kinds.count("ui") == 1
    assert kinds.count("done") == 1
    assert kinds[-1] == "done"
    ui_payload = next(data for _, name, data in events if name == "ui")
    assert "консультац" in ui_payload["answer"].lower()


# --- Row 8: pipeline exception ends cleanly, no hang ------------------------


def test_pipeline_exception_ends_with_one_ui_one_done(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module
    import orchestration.target_fullcontext_turn as target_turn_module

    sid = f"perf1-exc-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    composer = _RaisingComposerBackend()
    semantic = RecordingSemanticBackend()
    boundary = RecordingBoundaryBackend(BackendPayload("none", 0.95))
    monkeypatch.setattr(
        target_turn_module, "_default_target_runtime_backends", lambda: (composer, semantic, boundary)
    )
    monkeypatch.setattr(app_module, "run_planner_turn", lambda **k: PlannerTurnOutcome("content", None))
    monkeypatch.setattr(
        "core.target_runtime_turn.load_runtime_turn_frame",
        lambda: _frame(primary_aspect="price", aspects=["price"]),
    )
    _stub_pre_resolver(monkeypatch, app_module, q="Сколько стоит All-on-4?", sid=sid)

    client = app_module.app.test_client()
    resp = _post_stream(client, q="Сколько стоит All-on-4?", sid=sid)
    assert resp.status_code == 200
    events = _read_sse_events(resp)
    kinds = [name for _, name, _ in events]
    assert kinds.count("ui") == 1
    assert kinds.count("done") == 1
    assert kinds[-1] == "done"
    ui_payload = next(data for _, name, data in events if name == "ui")
    assert "администратор" in ui_payload["answer"].lower()


# --- Row 9: /ask vs /ask/stream identical ui payload ------------------------


def test_ask_and_ask_stream_ui_payload_identical(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    results: dict[str, dict] = {}
    for endpoint in ("/ask", "/ask/stream"):
        composer, semantic, boundary = _setup_http_fakes(monkeypatch, app_module)
        sid = f"perf1-parity-{uuid.uuid4().hex[:8]}"
        mem_reset(sid)
        _stub_pre_resolver(monkeypatch, app_module, q="Сколько стоит All-on-4?", sid=sid)
        client = app_module.app.test_client()
        resp = client.post(
            endpoint, json={"q": "Сколько стоит All-on-4?", "sid": sid, "client_id": "demo"}
        )
        assert resp.status_code == 200
        if endpoint == "/ask":
            results[endpoint] = resp.get_json()
        else:
            events = _read_sse_events(resp)
            results[endpoint] = next(data for _, name, data in events if name == "ui")

    assert results["/ask"]["answer"] == results["/ask/stream"]["answer"]
    assert results["/ask"]["meta"]["service_route"] == results["/ask/stream"]["meta"]["service_route"]
    assert results["/ask"]["quick_replies"] == results["/ask/stream"]["quick_replies"]
    assert results["/ask"]["cta"] == results["/ask/stream"]["cta"]


# --- Row 10: done exactly once and last (multi-scenario check) -------------


def test_done_is_last_and_exactly_once_across_scenarios(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    for boundary_delay in (0.0, 0.15):
        _setup_http_fakes(monkeypatch, app_module, boundary_delay=boundary_delay)
        sid = f"perf1-done-{uuid.uuid4().hex[:8]}"
        mem_reset(sid)
        _stub_pre_resolver(monkeypatch, app_module, q="Сколько стоит All-on-4?", sid=sid)
        client = app_module.app.test_client()
        resp = _post_stream(client, q="Сколько стоит All-on-4?", sid=sid)
        events = _read_sse_events(resp)
        kinds = [name for _, name, _ in events]
        assert kinds.count("done") == 1
        assert kinds[-1] == "done"


# --- Row 11: exactly one session write -------------------------------------


def test_exactly_one_session_write_worker_path(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module
    import session as session_module

    sid = f"perf1-write-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _setup_http_fakes(monkeypatch, app_module)
    _stub_pre_resolver(monkeypatch, app_module, q="Сколько стоит All-on-4?", sid=sid)

    add_user_calls = []
    add_bot_calls = []
    real_add_user = session_module.mem_add_user
    real_add_bot = session_module.mem_add_bot

    def _spy_add_user(session_id, text):
        add_user_calls.append(session_id)
        return real_add_user(session_id, text)

    def _spy_add_bot(session_id, text):
        add_bot_calls.append(session_id)
        return real_add_bot(session_id, text)

    monkeypatch.setattr(app_module, "mem_add_user", _spy_add_user)
    monkeypatch.setattr(app_module, "mem_add_bot", _spy_add_bot)

    client = app_module.app.test_client()
    resp = _post_stream(client, q="Сколько стоит All-on-4?", sid=sid)
    assert resp.status_code == 200
    list(resp.response)  # drain fully

    assert add_user_calls.count(sid) == 1
    assert add_bot_calls.count(sid) == 1


# --- Row 12: disconnect does not cause a second turn or duplicate write ----


def test_disconnect_no_second_orchestration_or_duplicate_write(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    sid = f"perf1-disconnect-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    composer, semantic, boundary = _setup_http_fakes(monkeypatch, app_module, boundary_delay=0.2)
    _stub_pre_resolver(monkeypatch, app_module, q="Сколько стоит All-on-4?", sid=sid)

    admission_before = app_module._sse_worker_admission._value

    client = app_module.app.test_client()
    resp = _post_stream(client, q="Сколько стоит All-on-4?", sid=sid)
    assert resp.status_code == 200

    # Simulate a client disconnect after the turn has genuinely started:
    # the 1st next() only reaches the initial (pre-orchestration) yield —
    # generators are lazy up to their first `yield` — so pull a 2nd item too,
    # which forces execution past the admission check and worker submission,
    # then stop iterating and close the generator early (exactly like Werkzeug
    # does when the socket goes away mid-stream).
    it = iter(resp.response)
    next(it)
    next(it)
    close = getattr(resp.response, "close", None)
    if callable(close):
        close()

    # The worker keeps running in the background regardless of the abandoned
    # generator; wait for it to actually finish exactly once.
    deadline = time.monotonic() + 5.0
    while len(boundary.invocations) < 1 and time.monotonic() < deadline:
        time.sleep(0.02)
    # give the worker's own finally a moment to release admission
    deadline = time.monotonic() + 5.0
    while app_module._sse_worker_admission._value < admission_before and time.monotonic() < deadline:
        time.sleep(0.02)

    assert len(boundary.invocations) == 1, "orchestration must run exactly once"
    assert app_module._sse_worker_admission._value == admission_before, "admission capacity leaked"

    st = mem_get(sid)
    # exactly one user turn recorded (session_turn_count incremented once)
    assert int(st.get("session_turn_count") or 0) == 1


# --- Row 13: no PII in status events ----------------------------------------


def test_no_pii_in_status_events(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    sid = f"perf1-pii-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _setup_http_fakes(monkeypatch, app_module)
    q = "Я боюсь боли, мой телефон +79991234567, зовут Иван"
    _stub_pre_resolver(monkeypatch, app_module, q=q, sid=sid)

    client = app_module.app.test_client()
    resp = _post_stream(client, q=q, sid=sid)
    events = _read_sse_events(resp)
    status_blobs = [json.dumps(data, ensure_ascii=False) for _, name, data in events if name == "status"]
    combined = "\n".join(status_blobs)
    assert "боюсь боли" not in combined
    assert "+79991234567" not in combined
    assert "9991234567" not in combined
    assert "Иван" not in combined


# --- Row 14: PERF-0 stage marks preserved -----------------------------------


def test_perf0_stage_marks_preserved_in_worker_trace() -> None:
    app = Flask(__name__)
    composer, semantic, boundary = _fake_backends()
    sid = f"perf1-trace-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    bucket_ref: dict = {}
    with app.test_request_context():
        request.ctx = {}
        with worker_execution_context(
            app,
            request_id=str(uuid.uuid4()),
            sid=sid,
            client_id="demo",
            turn_t0_monotonic=time.monotonic(),
            status_emit=None,
        ):
            _install_turn_frame(_frame(primary_aspect="price", aspects=["price"]))
            run_target_fullcontext_runtime_turn(
                client_id="demo",
                sid=sid,
                user_message="Сколько стоит All-on-4?",
                composer_backend=composer,
                semantic_backend=semantic,
                boundary_backend=boundary,
            )
            bucket_ref.update(request.ctx.get("turn_timing") or {})
    stages = bucket_ref.get("stages") or {}
    for name in ("boundary", "composer", "verifier_deterministic", "verifier_semantic"):
        assert stages.get(name, {}).get("status") == "completed", (name, stages)


# --- Row 15: LLM call count identical to /ask -------------------------------


def test_llm_call_count_matches_ask(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    counts: dict[str, dict[str, int]] = {}
    for endpoint in ("/ask", "/ask/stream"):
        composer, semantic, boundary = _setup_http_fakes(monkeypatch, app_module)
        sid = f"perf1-count-{uuid.uuid4().hex[:8]}"
        mem_reset(sid)
        _stub_pre_resolver(monkeypatch, app_module, q="Сколько стоит All-on-4?", sid=sid)
        client = app_module.app.test_client()
        resp = client.post(
            endpoint, json={"q": "Сколько стоит All-on-4?", "sid": sid, "client_id": "demo"}
        )
        assert resp.status_code == 200
        list(resp.response)
        counts[endpoint] = {
            "composer": len(composer.invocations),
            "semantic": len(semantic.invocations),
            "boundary": len(boundary.invocations),
        }
    assert counts["/ask"] == counts["/ask/stream"] == {"composer": 1, "semantic": 1, "boundary": 1}


# --- Row 16: old client ignores unknown event ------------------------------


def test_old_client_still_gets_correct_typing_ui_done_subsequence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app as app_module

    sid = f"perf1-oldclient-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _setup_http_fakes(monkeypatch, app_module)
    _stub_pre_resolver(monkeypatch, app_module, q="Сколько стоит All-on-4?", sid=sid)

    client = app_module.app.test_client()
    resp = _post_stream(client, q="Сколько стоит All-on-4?", sid=sid)
    events = _read_sse_events(resp)
    # simulate an old client that only understands typing/ui/done
    known = {"typing", "ui", "done"}
    old_client_view = [(name, data) for _, name, data in events if name in known]
    kinds = [name for name, _ in old_client_view]
    assert kinds[-2:] == ["ui", "done"]
    assert kinds.count("ui") == 1
    assert kinds.count("done") == 1


# --- Rows 17/18: worker bindings reset in finally (normal + exception) -----


def test_worker_bindings_reset_on_normal_completion() -> None:
    app = Flask(__name__)
    sid = f"perf1-bind-ok-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    assert current_worker_client_id() is None
    assert current_status_sink() is None
    with app.test_request_context():
        request.ctx = {}
        with worker_execution_context(
            app,
            request_id=str(uuid.uuid4()),
            sid=sid,
            client_id="demo",
            turn_t0_monotonic=time.monotonic(),
            status_emit=lambda *a: None,
        ):
            assert current_worker_client_id() == "demo"
            assert current_status_sink() is not None
    assert current_worker_client_id() is None
    assert current_status_sink() is None


def test_worker_bindings_reset_on_exception() -> None:
    app = Flask(__name__)
    sid = f"perf1-bind-exc-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    with pytest.raises(RuntimeError):
        with app.test_request_context():
            request.ctx = {}
            with worker_execution_context(
                app,
                request_id=str(uuid.uuid4()),
                sid=sid,
                client_id="demo",
                turn_t0_monotonic=time.monotonic(),
                status_emit=lambda *a: None,
            ):
                assert current_worker_client_id() == "demo"
                raise RuntimeError("boom")
    assert current_worker_client_id() is None
    assert current_status_sink() is None


# --- Row 19: overload falls back to synchronous, exactly once --------------


def test_overload_admission_full_falls_back_to_synchronous_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app as app_module

    sid = f"perf1-overload-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    composer, semantic, boundary = _setup_http_fakes(monkeypatch, app_module)
    _stub_pre_resolver(monkeypatch, app_module, q="Сколько стоит All-on-4?", sid=sid)

    fake_admission = threading.Semaphore(1)
    fake_admission.acquire()  # pre-exhaust: capacity is 0 for this test
    monkeypatch.setattr(app_module, "_sse_worker_admission", fake_admission)

    submitted = []
    real_submit = app_module._sse_worker_executor.submit

    def _spy_submit(fn, *a, **k):
        submitted.append(fn)
        return real_submit(fn, *a, **k)

    monkeypatch.setattr(app_module._sse_worker_executor, "submit", _spy_submit)

    client = app_module.app.test_client()
    resp = _post_stream(client, q="Сколько стоит All-on-4?", sid=sid)
    assert resp.status_code == 200
    events = _read_sse_events(resp)
    kinds = [name for _, name, _ in events]

    assert kinds.count("ui") == 1
    assert kinds.count("done") == 1
    assert kinds[-1] == "done"
    assert submitted == [], "must not submit to the worker executor when admission is full"
    assert len(boundary.invocations) == 1, "orchestration must still run exactly once"


# --- Row 20: status queue overflow never loses the final result ------------


def test_status_queue_overflow_does_not_drop_or_block() -> None:
    import app as app_module

    q: "queue.Queue[str]" = queue.Queue(maxsize=1)
    emit = app_module._make_status_emitter(q, already_sent=None)
    emit("ingress", "start")  # fills the queue (capacity 1)
    assert q.qsize() == 1
    # A second, distinct phrase must not raise or block even though the queue is full.
    emit("boundary", "start")
    assert q.qsize() == 1  # dropped silently, lossy by design
    assert q.get_nowait() == "Проверяю вопрос"


def test_status_queue_overflow_http_still_delivers_final_ui(monkeypatch: pytest.MonkeyPatch) -> None:
    import app as app_module

    sid = f"perf1-qfull-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    monkeypatch.setattr(app_module, "_SSE_STATUS_QUEUE_MAXSIZE", 1)
    _setup_http_fakes(monkeypatch, app_module, boundary_delay=0.1)
    _stub_pre_resolver(monkeypatch, app_module, q="Сколько стоит All-on-4?", sid=sid)

    client = app_module.app.test_client()
    resp = _post_stream(client, q="Сколько стоит All-on-4?", sid=sid)
    events = _read_sse_events(resp)
    kinds = [name for _, name, _ in events]
    assert kinds.count("ui") == 1
    assert kinds.count("done") == 1
    ui_payload = next(data for _, name, data in events if name == "ui")
    assert ui_payload.get("answer")


# --- Row 21: generator and worker never share request.ctx ------------------


def test_generator_and_worker_have_distinct_request_ctx() -> None:
    app = Flask(__name__)
    sid = f"perf1-ctx-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    with app.test_request_context():
        request.ctx = {"marker": "generator"}
        outer_ctx_id = id(request.ctx)
        inner_ctx_id = None
        with worker_execution_context(
            app,
            request_id=str(uuid.uuid4()),
            sid=sid,
            client_id="demo",
            turn_t0_monotonic=time.monotonic(),
            status_emit=None,
        ):
            inner_ctx_id = id(request.ctx)
            assert request.ctx.get("marker") != "generator"
        assert request.ctx.get("marker") == "generator"
        assert request.ctx is not None
    assert inner_ctx_id is not None
    assert inner_ctx_id != outer_ctx_id
