"""PERF-1: production-safe execution context for the /ask/stream background worker.

Generalizes the existing `core/target_composer_action_context.py` pattern
(`ContextVar` + `bind_...() -> tokens` / `reset_...(tokens)` in `finally`) for the
values a worker thread needs: `client_id`, the status-event sink used by
`core/turn_timing.py`'s `stage_start` hook, and the non-lossy Composer text sink.

Governance (docs/evidence/performance/FINAL_EARLY_SSE_STATUS_STREAMING_SEAM_AUDIT.md,
"Worker execution context: production-safe design"):

- Never `app.test_request_context()` (testing utility).
- Never `flask.copy_current_request_context` (shares the same `request.ctx` dict by
  reference — `RequestContext.copy()` passes `request=self.request`).
- The worker pushes its own **independent** `RequestContext` via
  `app.request_context(environ)` (Flask's real production entry point) built from a
  hand-built minimal environ — no `werkzeug.test`/`EnvironBuilder`, no reuse of the
  original request's real environ, cookies, or body stream.
"""

from __future__ import annotations

import io
import os
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Callable, Iterator

from session import bind_client_id

StatusEmitter = Callable[[str, str], None]
TextEmitter = Callable[[str], None]

_client_id_var: ContextVar[str | None] = ContextVar(
    "perf1_worker_client_id", default=None
)
_status_sink_var: ContextVar[StatusEmitter | None] = ContextVar(
    "perf1_worker_status_sink", default=None
)
_text_sink_var: ContextVar[TextEmitter | None] = ContextVar(
    "composer_text_stream_sink", default=None
)


def current_worker_client_id() -> str | None:
    return _client_id_var.get()


def current_status_sink() -> StatusEmitter | None:
    """Read by core/turn_timing.py's stage_start hook. None outside a worker context."""
    return _status_sink_var.get()


def current_text_sink() -> TextEmitter | None:
    """Return the current SSE answer-delta sink, or ``None`` on blocking paths."""
    return _text_sink_var.get()


def bind_text_sink(emitter: TextEmitter | None) -> Token:
    return _text_sink_var.set(emitter)


def reset_text_sink(token: Token) -> None:
    _text_sink_var.reset(token)


def _minimal_environ(*, path: str) -> dict[str, object]:
    """Hand-built minimal WSGI environ (PEP 3333) — no werkzeug.test/EnvironBuilder,
    no reuse of the live request's environ, headers, cookies, or body."""
    return {
        "REQUEST_METHOD": "POST",
        "SCRIPT_NAME": "",
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "SERVER_NAME": "localhost",
        "SERVER_PORT": "0",
        "SERVER_PROTOCOL": "HTTP/1.1",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "http",
        "wsgi.input": io.BytesIO(b""),
        "wsgi.errors": io.BytesIO(),
        "wsgi.multithread": True,
        "wsgi.multiprocess": False,
        "wsgi.run_once": False,
    }


@contextmanager
def worker_execution_context(
    app,
    *,
    request_id: str,
    sid: str,
    client_id: str,
    turn_t0_monotonic: float,
    status_emit: StatusEmitter | None,
    text_emit: TextEmitter | None = None,
    path: str = "/ask/stream",
) -> Iterator[None]:
    """Independent request context + explicit bindings for one PERF-1 worker turn.

    Never shares `request.ctx` with the request-handling (generator) thread. Binds
    and resets, in one `finally` that runs on every exit path: the `client_id`
    ContextVar, `session.py`'s thread-local client-pack binding, and the
    status-event-sink ContextVar. PERF-0 stage marks land in this context's own
    fresh `turn_timing` bucket (via the normal `request.ctx["turn_timing"]` path),
    scoped only to this worker's run.
    """

    from flask import request as flask_request

    req_ctx = app.request_context(_minimal_environ(path=path))
    req_ctx.push()
    client_token = _client_id_var.set(client_id)
    sink_token = _status_sink_var.set(status_emit)
    text_sink_token = bind_text_sink(text_emit)
    try:
        flask_request.ctx = {
            "request_id": request_id,
            "sid": sid,
            "session_id": sid,
            "client_id": client_id,
            "app_version": os.getenv("APP_VERSION", "dev"),
            "env": os.getenv("APP_ENV", "local"),
            "path": path,
            "method": "POST",
            "turn_t0_monotonic": turn_t0_monotonic,
        }
        # Explicit, not relied upon implicitly from deep inside unmodified pipeline
        # code — matches session.py's existing thread-local contract exactly (this
        # call is idempotent: bind_client_id no-ops if the sid's stored client_id
        # already matches, so it never double-writes).
        bind_client_id(sid, client_id)
        yield
    finally:
        reset_text_sink(text_sink_token)
        _status_sink_var.reset(sink_token)
        _client_id_var.reset(client_token)
        req_ctx.pop()


def new_request_id() -> str:
    return str(uuid.uuid4())


def monotonic_now() -> float:
    return time.monotonic()
