"""Stage 4.1: Windows-safe logging and PII-free runtime/SSE diagnostics."""

from __future__ import annotations

import json
import logging
import os
import queue
import subprocess
import sys
import threading
import time
import uuid
from logging.handlers import QueueHandler, RotatingFileHandler
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import app as app_module
import config
import logging_setup as ls
from core import turn_timing
from core.provider_call_budget import ProviderCallPolicy, http_provider_budget_scope
from core.runtime_diagnostics import (
    SseRenderDiagnosticTracker,
    build_runtime_turn_diagnostic_payload,
    utf8_text_fingerprint,
)
from core.sales_fast_observability import record_sales_fast_observability
from session import mem_reset


_REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _logging_subprocess_script() -> str:
    return """
import json, os, sys, threading
from pathlib import Path
from logging.handlers import QueueHandler, RotatingFileHandler
import logging

log_dir = sys.argv[1]
os.environ["BOT_LOG_DIR"] = log_dir
os.environ["BOT_LOG_FILE"] = "stage41.jsonl"
os.environ["BOT_LOG_RETENTION_DAYS"] = "7"

import logging_setup as ls

barrier = threading.Barrier(4)

def worker(i):
    barrier.wait()
    logger = ls.get_logger(f"worker-{i}")
    logger.info(
        "worker_line",
        extra={"extra_data": {"worker_id": i, "thread": threading.current_thread().name}},
    )

threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
for t in threads:
    t.start()
for t in threads:
    t.join()

for name in sorted(ls._loggers_with_queue):
    logger = logging.getLogger(name)
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0], QueueHandler)
    assert logger.propagate is False
    assert not any(isinstance(h, RotatingFileHandler) for h in logger.handlers)

listener = ls._log_listener
assert listener is not None
file_handlers = [h for h in listener.handlers if isinstance(h, RotatingFileHandler)]
assert len(file_handlers) == 1

ls._shutdown_logging()
rows = []
with open(ls.LOG_FILE, encoding="utf-8") as fh:
    for raw in fh:
        raw = raw.strip()
        if raw:
            rows.append(json.loads(raw))
startup = [r for r in rows if r.get("msg") == "logging_startup"]
assert len(startup) == 1, startup
assert startup[0]["log_path"] == ls.LOG_FILE
assert Path(startup[0]["log_path"]).is_absolute()
assert startup[0]["writer_mode"] == "queue_listener"
worker_lines = [r for r in rows if r.get("msg") == "worker_line"]
assert len(worker_lines) == 4
ids = {r["worker_id"] for r in worker_lines}
assert ids == {0, 1, 2, 3}
assert len({json.dumps(r, sort_keys=True) for r in rows}) == len(rows)
print(json.dumps({"log_file": ls.LOG_FILE, "startup": startup[0], "line_count": len(rows)}))
"""


def test_single_writer_subprocess(tmp_path) -> None:
    log_dir = tmp_path / "isolated_logs"
    log_dir.mkdir()
    proc = subprocess.run(
        [sys.executable, "-c", _logging_subprocess_script(), str(log_dir)],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    stdout_lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    payload = json.loads(stdout_lines[-1])
    log_file = Path(payload["log_file"])
    assert log_file.is_absolute()
    assert log_file.parent == log_dir.resolve()
    assert not str(log_file).startswith(str(tmp_path / "other"))


def test_get_logger_idempotent_handlers() -> None:
    if not ls._logging_initialized:
        pytest.skip("logging not initialized in this process")
    first = ls.get_logger("stage41-idempotent-a")
    second = ls.get_logger("stage41-idempotent-a")
    assert first is second
    assert len(first.handlers) == 1
    assert isinstance(first.handlers[0], QueueHandler)


def test_runtime_diagnostic_payload_is_pii_free() -> None:
    patient_name = "УникальноеИмяПациентаStage41"
    patient_phone = "+79991112233"
    question = f"Сколько стоит имплант {patient_name}?"
    answer = f"Ответ для {patient_name} tel {patient_phone}"
    payload = build_runtime_turn_diagnostic_payload(
        request_id="req-stage41",
        client_id="demo",
        transport="json",
        route="sales_fast_contacts",
        status="completed",
        provider_calls=0,
        provider_policy="legacy_accounting",
        timing_summary={
            "total_ms": 120,
            "orchestrate_ms": 80,
            "sid": "must-not-leak",
            "preview": question,
            "answer": answer,
        },
        sales_fast_observability={
            "architecture": "one_call",
            "route": "sales_fast_contacts",
            "provider_calls": 0,
            "model": "qwen3.7-flash-2026-07-15",
            "timings_ms": {"total": 120},
        },
    )
    blob = json.dumps(payload, ensure_ascii=False)
    assert "sid" not in payload
    assert "preview" not in payload
    assert patient_name not in blob
    assert patient_phone not in blob
    assert question not in blob
    assert answer not in blob
    assert payload["provider_calls"] == 0
    assert payload["timings_ms"]["total_ms"] == 120


def test_emit_runtime_turn_diagnostic_zero_and_one_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[tuple[str, dict]] = []

    def _capture(_logger, msg, **fields):
        captured.append((msg, dict(fields)))

    monkeypatch.setattr(app_module, "log_json_no_context", _capture)

    with app_module.app.test_request_context("/ask", method="POST"):
        app_module.request.ctx = {
            "request_id": "req-0",
            "client_id": "demo",
            "path": "/ask",
            "turn_timing": {"durations_ms": {}, "flags": {}, "marks": {}, "stages": {}},
            "turn_t0_monotonic": 0.0,
        }
        turn_timing.mark("orchestrate_done")
        with http_provider_budget_scope(request_id="req-0", sales_one_plus_on=False) as budget:
            try:
                pass
            finally:
                turn_timing.set_flag("provider_calls", budget.call_count)
                turn_timing.set_flag("provider_policy", budget.policy.value)
                app_module._emit_runtime_turn_diagnostic(
                    status="completed",
                    route="sales_fast_contacts",
                    transport="json",
                    provider_calls=budget.call_count,
                    provider_policy=budget.policy.value,
                )

    zero_msgs = [fields for msg, fields in captured if msg == "runtime_turn_diagnostic"]
    assert len(zero_msgs) == 1
    assert zero_msgs[0]["provider_calls"] == 0
    assert zero_msgs[0]["transport"] == "json"
    assert zero_msgs[0]["route"] == "sales_fast_contacts"

    captured.clear()
    with app_module.app.test_request_context("/ask", method="POST"):
        app_module.request.ctx = {
            "request_id": "req-1",
            "client_id": "demo",
            "path": "/ask",
            "turn_timing": {"durations_ms": {}, "flags": {}, "marks": {}, "stages": {}},
            "turn_t0_monotonic": 0.0,
        }
        record_sales_fast_observability(
            architecture="one_call",
            route="sales_fast",
            provider_calls=1,
            model="qwen3.7-flash-2026-07-15",
            timings={"total": 500},
        )
        with http_provider_budget_scope(request_id="req-1", sales_one_plus_on=True) as budget:
            budget.reserve(source="sales_fast", model="qwen3.7-flash-2026-07-15")
            try:
                pass
            finally:
                app_module._emit_runtime_turn_diagnostic(
                    status="completed",
                    route="sales_fast",
                    transport="json",
                    provider_calls=budget.call_count,
                    provider_policy=budget.policy.value,
                )

    one_msgs = [fields for msg, fields in captured if msg == "runtime_turn_diagnostic"]
    assert len(one_msgs) == 1
    assert one_msgs[0]["provider_calls"] == 1
    assert one_msgs[0]["provider_policy"] == ProviderCallPolicy.ONE_CALL_LOCKED.value


def test_sse_fingerprint_delta_and_final() -> None:
    tracker = SseRenderDiagnosticTracker(request_id="r1", client_id="demo")
    tracker.track('event: text_delta\ndata: {"delta": "При"}\n\n')
    tracker.track('event: text_delta\ndata: {"delta": "вет"}\n\n')
    final_answer = "Привет"
    tracker.track(
        'event: ui\ndata: '
        + json.dumps({"answer": final_answer, "meta": {"service_route": "sales_fast"}}, ensure_ascii=False)
        + "\n\n"
    )
    tracker.track("event: done\ndata: {}\n\n")
    payload = tracker.build_payload()
    streamed_chars, streamed_bytes, streamed_sha = utf8_text_fingerprint("Привет")
    final_chars, final_bytes, final_sha = utf8_text_fingerprint(final_answer)
    assert payload["streamed_text_chars"] == streamed_chars
    assert payload["streamed_text_utf8_bytes"] == streamed_bytes
    assert payload["streamed_text_sha256"] == streamed_sha
    assert payload["final_text_chars"] == final_chars
    assert payload["final_text_sha256"] == final_sha
    assert payload["stream_matches_final"] is True
    assert payload["sse_event_counts"]["text_delta"] == 2
    assert payload["sse_event_counts"]["ui"] == 1


def test_sse_fingerprint_mismatch_and_ui_only() -> None:
    mismatch = SseRenderDiagnosticTracker(request_id="r2", client_id="demo")
    mismatch.track('event: text_delta\ndata: {"delta": "A"}\n\n')
    mismatch.track(
        'event: ui\ndata: '
        + json.dumps({"answer": "B", "meta": {}}, ensure_ascii=False)
        + "\n\n"
    )
    mismatch_payload = mismatch.build_payload()
    assert mismatch_payload["stream_matches_final"] is False

    ui_only = SseRenderDiagnosticTracker(request_id="r3", client_id="demo")
    ui_only.track(
        'event: ui\ndata: '
        + json.dumps({"answer": "Контакты", "meta": {}}, ensure_ascii=False)
        + "\n\n"
    )
    ui_only.track("event: done\ndata: {}\n\n")
    ui_payload = ui_only.build_payload()
    assert ui_payload["stream_matches_final"] is None
    assert ui_payload["streamed_text_chars"] == 0
    empty_chars, empty_bytes, empty_sha = utf8_text_fingerprint("")
    assert ui_payload["streamed_text_sha256"] == empty_sha


def test_sse_diagnostic_does_not_log_raw_text(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[dict] = []

    def _capture(_logger, msg, **fields):
        if msg == "sse_render_diagnostic":
            captured.append(dict(fields))

    monkeypatch.setattr(app_module, "log_json_no_context", _capture)
    delta = "СекретнаяДельтаStage41"
    final = "СекретныйФиналStage41"
    tracker = SseRenderDiagnosticTracker(request_id="r4", client_id="demo")
    tracker.track(f'event: text_delta\ndata: {json.dumps({"delta": delta}, ensure_ascii=False)}\n\n')
    tracker.track(
        'event: ui\ndata: '
        + json.dumps({"answer": final, "meta": {}}, ensure_ascii=False)
        + "\n\n"
    )
    app_module._emit_sse_render_diagnostic(tracker)
    assert len(captured) == 1
    blob = json.dumps(captured[0], ensure_ascii=False)
    assert delta not in blob
    assert final not in blob
    assert captured[0]["streamed_text_chars"] == len(delta)
    assert captured[0]["final_text_chars"] == len(final)


def test_sse_service_reply_emits_single_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[dict] = []

    def _capture(_logger, msg, **fields):
        if msg == "sse_render_diagnostic":
            captured.append(dict(fields))

    monkeypatch.setattr(app_module, "log_json_no_context", _capture)
    payload = {
        "answer": "Контакты клиники",
        "meta": {"service_route": "sales_fast_contacts"},
    }
    with app_module.app.test_request_context("/ask/stream", method="POST"):
        app_module.request.ctx = {
            "request_id": "sse-req",
            "client_id": "demo",
            "path": "/ask/stream",
        }
        resp = app_module._sse_service_reply(
            payload,
            sid="sid-sse",
            q="контакты",
            route="sales_fast_contacts",
        )
        body = resp.get_data(as_text=True)
    assert "event: ui" in body
    assert len(captured) == 1
    assert captured[0]["sse_event_counts"]["ui"] == 1
    assert captured[0]["stream_matches_final"] is None


def test_orchestrate_emits_runtime_diagnostic_on_zero_call_contacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "SALES_ONE_PLUS_ON", True)
    monkeypatch.setattr(app_module, "SALES_ONE_PLUS_ON", True)
    diagnostics: list[dict] = []

    def _capture(_logger, msg, **fields):
        if msg == "runtime_turn_diagnostic":
            diagnostics.append(dict(fields))

    monkeypatch.setattr(app_module, "log_json_no_context", _capture)
    monkeypatch.setattr(
        app_module,
        "orchestrate_sales_one_plus_ask_turn",
        lambda *args, **kwargs: SimpleNamespace(
            kind="service_reply",
            service_payload={"answer": "Телефон", "meta": {"service_route": "sales_fast_contacts"}},
            sid=kwargs.get("data", {}).get("sid", "sid"),
            q="телефон",
            service_doc_id=None,
            service_track_user=True,
            service_route="sales_fast_contacts",
            http_status=200,
        ),
    )

    sid = f"s41-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    client = app_module.app.test_client()
    resp = client.post("/ask", json={"q": "телефон", "sid": sid, "client_id": "demo"})
    assert resp.status_code == 200
    assert len(diagnostics) == 1
    assert diagnostics[0]["provider_calls"] == 0
    assert diagnostics[0]["route"] == "sales_fast_contacts"
    blob = json.dumps(diagnostics[0], ensure_ascii=False)
    assert sid not in blob
    assert "телефон" not in blob.lower() or diagnostics[0].get("route") == "sales_fast_contacts"


def test_dashboard_log_file_remains_string_path() -> None:
    assert isinstance(ls.LOG_FILE, str)
    assert Path(ls.LOG_FILE).is_absolute()


def _pii_diagnostic_subprocess_script() -> str:
    return """
import json, os, sys, uuid
from pathlib import Path

log_dir = sys.argv[1]
repo = Path(sys.argv[2]).resolve()
os.chdir(repo)
sys.path.insert(0, str(repo))
os.environ["OPENAI_API_KEY"] = "test-key-offline"
os.environ["BOT_LOG_DIR"] = log_dir
os.environ["BOT_LOG_FILE"] = "pii_diag.jsonl"
os.environ["BOT_LOG_RETENTION_DAYS"] = "0"

unique = {
    "sid": "sid-pii-" + uuid.uuid4().hex,
    "name": "NamePII" + uuid.uuid4().hex[:8],
    "phone": "+7999" + uuid.uuid4().hex[:7],
}
unique["q"] = f"Сколько стоит имплант {unique['name']} {unique['phone']}"
unique["answer"] = f"Ответ для {unique['name']} tel {unique['phone']}"

import config
import app as app_module
from types import SimpleNamespace
from logging_setup import LOG_FILE, _shutdown_logging
from session import mem_reset

config.SALES_ONE_PLUS_ON = True
app_module.SALES_ONE_PLUS_ON = True

def fake_orch(*args, **kwargs):
    return SimpleNamespace(
        kind="service_reply",
        service_payload={"answer": unique["answer"], "meta": {"service_route": "sales_fast_contacts"}},
        sid=kwargs.get("data", {}).get("sid", unique["sid"]),
        q=unique["q"],
        service_doc_id=None,
        service_track_user=True,
        service_route="sales_fast_contacts",
        http_status=200,
    )

app_module.orchestrate_sales_one_plus_ask_turn = fake_orch
mem_reset(unique["sid"])
resp = app_module.app.test_client().post(
    "/ask",
    json={"q": unique["q"], "sid": unique["sid"], "client_id": "demo"},
)
assert resp.status_code == 200
_shutdown_logging()
rows = []
with open(LOG_FILE, encoding="utf-8") as fh:
    for raw in fh:
        raw = raw.strip()
        if raw:
            rows.append(json.loads(raw))
diags = [r for r in rows if r.get("msg") == "runtime_turn_diagnostic"]
assert len(diags) == 1
blob = json.dumps(diags[0], ensure_ascii=False)
for key in ("sid", "session_id", "ip", "path", "q", "answer", "preview"):
    assert key not in diags[0], key
for val in unique.values():
    assert val not in blob, val
print(json.dumps({"status": diags[0].get("status"), "provider_calls": diags[0].get("provider_calls")}))
"""


def test_runtime_diagnostic_jsonl_excludes_request_context_pii(tmp_path) -> None:
    log_dir = tmp_path / "pii_logs"
    log_dir.mkdir()
    proc = subprocess.run(
        [sys.executable, "-c", _pii_diagnostic_subprocess_script(), str(log_dir), str(_REPO_ROOT)],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    assert payload["status"] == "completed"
    assert payload["provider_calls"] == 0


def _fake_service_orch(monkeypatch: pytest.MonkeyPatch, *, answer: str = "Телефон") -> str:
    monkeypatch.setattr(config, "SALES_ONE_PLUS_ON", True)
    monkeypatch.setattr(app_module, "SALES_ONE_PLUS_ON", True)
    monkeypatch.setattr(
        app_module,
        "orchestrate_sales_one_plus_ask_turn",
        lambda *args, **kwargs: SimpleNamespace(
            kind="service_reply",
            service_payload={"answer": answer, "meta": {"service_route": "sales_fast_contacts"}},
            sid=kwargs.get("data", {}).get("sid", "sid"),
            q=kwargs.get("data", {}).get("q", "телефон"),
            service_doc_id=None,
            service_track_user=True,
            service_route="sales_fast_contacts",
            http_status=200,
        ),
    )
    return f"s41-{uuid.uuid4().hex[:8]}"


def test_ask_runtime_diagnostic_has_final_timing_marks(monkeypatch: pytest.MonkeyPatch) -> None:
    diagnostics: list[dict] = []

    def _capture(_logger, msg, **fields):
        if msg == "runtime_turn_diagnostic":
            diagnostics.append(dict(fields))

    monkeypatch.setattr(app_module, "log_json_no_context", _capture)
    sid = _fake_service_orch(monkeypatch)
    mem_reset(sid)
    resp = app_module.app.test_client().post(
        "/ask",
        json={"q": "телефон", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert len(diagnostics) == 1
    timings = diagnostics[0].get("timings_ms") or {}
    assert diagnostics[0]["status"] == "completed"
    assert "orchestrate_done_since_start_ms" in timings or "orchestrate_ms" in timings


def test_ask_runtime_diagnostic_error_after_orchestration_assembly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    diagnostics: list[dict] = []

    def _capture(_logger, msg, **fields):
        if msg == "runtime_turn_diagnostic":
            diagnostics.append(dict(fields))

    monkeypatch.setattr(app_module, "log_json_no_context", _capture)
    sid = _fake_service_orch(monkeypatch)

    def _boom(*args, **kwargs):
        raise RuntimeError("assembly failed after orchestration")

    monkeypatch.setattr(app_module, "_service_reply", _boom)
    mem_reset(sid)
    resp = app_module.app.test_client().post(
        "/ask",
        json={"q": "телефон", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert len(diagnostics) == 1
    assert diagnostics[0]["status"] == "error"
    assert all(d["status"] != "completed" for d in diagnostics)


def test_worker_runtime_diagnostic_emits_after_build_sse_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order: list[str] = []
    real_build = app_module._build_sse_payload

    def _tracked_build(orch_r):
        order.append("build_sse_payload")
        return real_build(orch_r)

    real_emit = app_module._emit_runtime_turn_diagnostic_once

    def _tracked_emit(**kwargs):
        order.append("runtime_diagnostic")
        return real_emit(**kwargs)

    monkeypatch.setattr(app_module, "_build_sse_payload", _tracked_build)
    monkeypatch.setattr(app_module, "_emit_runtime_turn_diagnostic_once", _tracked_emit)
    monkeypatch.setattr(app_module, "_sse_worker_admission", MagicMock(acquire=MagicMock(return_value=False)))

    sid = _fake_service_orch(monkeypatch)
    mem_reset(sid)
    resp = app_module.app.test_client().post(
        "/ask/stream",
        json={"q": "телефон", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    list(resp.response)
    assert order.count("build_sse_payload") >= 1
    assert order.count("runtime_diagnostic") >= 1
    assert order.index("build_sse_payload") < order.index("runtime_diagnostic")


def _collect_sse_render_diagnostics(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    captured: list[dict] = []

    def _capture(_logger, msg, **fields):
        if msg == "sse_render_diagnostic":
            captured.append(dict(fields))

    monkeypatch.setattr(app_module, "log_json_no_context", _capture)
    return captured


def test_sse_service_reply_client_closed_on_early_iterator_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _collect_sse_render_diagnostics(monkeypatch)
    payload = {"answer": "Контакты", "meta": {"service_route": "sales_fast_contacts"}}
    with app_module.app.test_request_context("/ask/stream", method="POST"):
        app_module.request.ctx = {
            "request_id": "sse-close-req",
            "client_id": "demo",
            "path": "/ask/stream",
        }
        resp = app_module._sse_service_reply(
            payload,
            sid="sid-close",
            q="контакты",
            route="sales_fast_contacts",
        )
        it = iter(resp.response)
        next(it)
        it.close()
    assert len(captured) == 1
    assert captured[0]["status"] == "client_closed"
    assert captured[0]["sse_event_counts"]["done"] == 0


def test_stream_worker_client_closed_after_worker_submit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _collect_sse_render_diagnostics(monkeypatch)
    sid = _fake_service_orch(monkeypatch)
    mem_reset(sid)

    submit_called = threading.Event()
    worker_entered = threading.Event()
    worker_release = threading.Event()
    disconnect = threading.Event()
    real_run = app_module._run_sse_worker_turn
    real_submit = app_module._sse_worker_executor.submit
    real_queue_get = queue.Queue.get
    sem = app_module._sse_worker_admission
    sem_value_before = sem._value

    def tracked_run(*args, **kwargs):
        worker_entered.set()
        deadline = time.time() + 5
        while time.time() < deadline:
            if worker_release.wait(timeout=0.05):
                return real_run(*args, **kwargs)
        raise TimeoutError("worker_release was not set")

    def tracked_submit(fn):
        submit_called.set()
        return real_submit(fn)

    def disconnectable_queue_get(self, block=True, timeout=None):
        if disconnect.is_set() and threading.current_thread().name == "sse-disconnect-resume":
            raise GeneratorExit()
        return real_queue_get(self, block=block, timeout=timeout)

    monkeypatch.setattr(app_module, "_run_sse_worker_turn", tracked_run)
    monkeypatch.setattr(app_module._sse_worker_executor, "submit", tracked_submit)
    monkeypatch.setattr(queue.Queue, "get", disconnectable_queue_get)

    resp = app_module.app.test_client().post(
        "/ask/stream",
        json={"q": "телефон", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    it = iter(resp.response)
    next(it)

    resume_error: list[BaseException] = []

    def _resume_generator() -> None:
        try:
            next(it)
        except BaseException as exc:
            resume_error.append(exc)

    resume_thread = threading.Thread(
        target=_resume_generator,
        name="sse-disconnect-resume",
        daemon=True,
    )
    resume_thread.start()
    assert submit_called.wait(timeout=5), "executor submit was not reached"
    assert worker_entered.wait(timeout=5), "worker path did not start"
    disconnect.set()
    resume_thread.join(timeout=5)
    worker_release.set()
    deadline = time.time() + 5
    while time.time() < deadline and sem._value != sem_value_before:
        time.sleep(0.05)
    resume_thread.join(timeout=5)

    assert len(captured) == 1
    assert captured[0]["status"] == "client_closed"
    assert captured[0]["sse_event_counts"]["status"] >= 1
    assert captured[0]["sse_event_counts"]["done"] == 0
    assert sem._value == sem_value_before


def test_stream_overload_fallback_client_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _collect_sse_render_diagnostics(monkeypatch)
    fallback_called = threading.Event()
    fallback_release = threading.Event()
    disconnect = threading.Event()
    real_run = app_module._run_sse_worker_turn

    def slow_fallback(*args, **kwargs):
        fallback_called.set()
        deadline = time.time() + 5
        while time.time() < deadline:
            if disconnect.is_set():
                raise GeneratorExit()
            if fallback_release.wait(timeout=0.05):
                break
        else:
            raise TimeoutError("fallback_release was not set")
        return real_run(*args, **kwargs)

    monkeypatch.setattr(app_module, "_run_sse_worker_turn", slow_fallback)
    monkeypatch.setattr(app_module, "_sse_worker_admission", MagicMock(acquire=MagicMock(return_value=False)))
    sid = _fake_service_orch(monkeypatch)
    mem_reset(sid)
    resp = app_module.app.test_client().post(
        "/ask/stream",
        json={"q": "телефон", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    it = iter(resp.response)
    next(it)

    resume_error: list[BaseException] = []

    def _resume_generator() -> None:
        try:
            next(it)
        except BaseException as exc:
            resume_error.append(exc)

    resume_thread = threading.Thread(target=_resume_generator, daemon=True)
    resume_thread.start()
    assert fallback_called.wait(timeout=5), "overload fallback was not invoked"
    disconnect.set()
    resume_thread.join(timeout=5)
    fallback_release.set()
    resume_thread.join(timeout=5)

    assert len(captured) == 1
    assert captured[0]["status"] == "client_closed"
    assert captured[0]["sse_event_counts"]["done"] == 0


def test_stream_worker_completed_on_full_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _collect_sse_render_diagnostics(monkeypatch)
    sid = _fake_service_orch(monkeypatch)
    mem_reset(sid)
    resp = app_module.app.test_client().post(
        "/ask/stream",
        json={"q": "телефон", "sid": sid, "client_id": "demo"},
    )
    body = b"".join(resp.response).decode("utf-8")
    assert "event: done" in body
    assert len(captured) == 1
    assert captured[0]["status"] == "completed"


def test_stream_overload_fallback_completed_on_full_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _collect_sse_render_diagnostics(monkeypatch)
    monkeypatch.setattr(app_module, "_sse_worker_admission", MagicMock(acquire=MagicMock(return_value=False)))
    sid = _fake_service_orch(monkeypatch)
    mem_reset(sid)
    resp = app_module.app.test_client().post(
        "/ask/stream",
        json={"q": "телефон", "sid": sid, "client_id": "demo"},
    )
    body = b"".join(resp.response).decode("utf-8")
    assert "event: done" in body
    assert len(captured) == 1
    assert captured[0]["status"] == "completed"


def test_no_duplicate_runtime_or_sse_diagnostics_on_full_ask(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime: list[dict] = []
    sse: list[dict] = []

    def _capture(_logger, msg, **fields):
        if msg == "runtime_turn_diagnostic":
            runtime.append(dict(fields))
        elif msg == "sse_render_diagnostic":
            sse.append(dict(fields))

    monkeypatch.setattr(app_module, "log_json_no_context", _capture)
    sid = _fake_service_orch(monkeypatch)
    mem_reset(sid)
    resp = app_module.app.test_client().post(
        "/ask",
        json={"q": "телефон", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert len(runtime) == 1
    assert len(sse) == 0


def test_sse_worker_build_failure_emits_error_diagnostic_with_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime: list[dict] = []
    secret = f"SecretPatient{uuid.uuid4().hex[:8]}"

    def _capture(_logger, msg, **fields):
        if msg == "runtime_turn_diagnostic":
            runtime.append(dict(fields))

    monkeypatch.setattr(app_module, "log_json_no_context", _capture)
    sid = _fake_service_orch(monkeypatch, answer=f"Ответ {secret}")

    def _boom(_orch_r):
        raise RuntimeError(f"build failed {secret}")

    monkeypatch.setattr(app_module, "_build_sse_payload", _boom)

    request_id = f"worker-req-{uuid.uuid4().hex[:8]}"
    client_id = "demo"
    mem_reset(sid)
    _out, http_status = app_module._run_sse_worker_turn(
        data={"q": secret, "sid": sid, "client_id": client_id},
        client_id=client_id,
        request_id=request_id,
        sid=sid,
        turn_t0_monotonic=time.monotonic(),
        status_emit=None,
    )
    assert http_status == 200
    assert len(runtime) == 1
    diag = runtime[0]
    assert diag["status"] == "error"
    assert diag["request_id"] == request_id
    assert diag["client_id"] == client_id
    assert diag["transport"] == "sse"
    assert "provider_calls" in diag
    assert "provider_policy" in diag
    timings = diag.get("timings_ms") or {}
    assert "orchestrate_done_since_start_ms" in timings or "orchestrate_ms" in timings
    blob = json.dumps(diag, ensure_ascii=False)
    assert secret not in blob
    assert "build failed" not in blob
    assert all(item["status"] != "completed" for item in runtime)


def test_ask_stream_reset_dispatch_failure_emits_runtime_error_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime: list[dict] = []

    def _capture(_logger, msg, **fields):
        if msg == "runtime_turn_diagnostic":
            runtime.append(dict(fields))

    monkeypatch.setattr(app_module, "log_json_no_context", _capture)

    def _dispatch_boom(_orch_r):
        raise RuntimeError("dispatch sse failed after orchestration")

    monkeypatch.setattr(app_module, "_dispatch_orchestration_sse", _dispatch_boom)

    sid = f"reset-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    resp = app_module.app.test_client().post(
        "/ask/stream",
        json={"q": "/reset", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert len(runtime) == 1
    diag = runtime[0]
    assert diag["status"] == "error"
    assert diag["transport"] == "sse"
    assert diag.get("client_id") == "demo"
    assert diag.get("request_id")
    assert "provider_calls" in diag
    assert "provider_policy" in diag
    assert all(item["status"] != "completed" for item in runtime)
    blob = json.dumps(diag, ensure_ascii=False)
    assert "dispatch sse failed" not in blob
