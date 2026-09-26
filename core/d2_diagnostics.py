"""Best-effort, text-free observation of the existing D2 HTTP path.

Attempt-local only: no session/store fields, request IDs or transport changes.
SSE binds the context only during next/close, never across a yielded chunk.
"""
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
from hashlib import sha256
from pathlib import Path
from time import monotonic
from uuid import uuid4


_current = ContextVar("d2_diagnostic_attempt", default=None)
_STAGES = {
    "ingress": "app.py", "transport": "app.py", "stream_done": "app.py",
    "request": "core/d2_http_adapter.py", "store_open": "core/d2_http_adapter.py",
    "payload": "core/d2_http_adapter.py", "rollback": "core/d2_http_adapter.py",
    "store_close": "core/d2_http_adapter.py",
    "reserve": "core/d2_dialogue.py", "snapshot": "core/d2_dialogue.py",
    "state_read": "core/d2_dialogue.py", "binding": "core/d2_dialogue.py",
    "provider": "core/d2_dialogue.py", "parse": "core/d2_dialogue.py",
    "materialize": "core/d2_dialogue.py", "gate": "core/d2_dialogue.py",
    "state_build": "core/d2_dialogue.py", "commit": "core/d2_dialogue.py",
    "effect": "core/d2_dialogue.py", "prompt": "core/d2_live_provider.py",
    "provider_transport": "core/d2_live_provider.py",
    "provider_response": "core/d2_live_provider.py",
}
# Exact membership only; never stringify exceptions or export their arguments.
_REASONS = frozenset({
    "d2_experiment_content_not_resolved", "d2_experiment_price_not_resolved",
    "d2_experiment_tenant_changed", "d2_content_scope_required",
    "d2_no_price_candidates", "d2_content_source_missing",
    "d2_unauthorized_ui_action", "d2_stale_ui_action",
    "d2_stale_or_unsupported_ref", "d2_ui_revision_required",
    "d2_ui_action_requires_empty_question", "d2_request_id_required",
    "d2_unsupported_request_fields", "d2_request_field_invalid",
    "d2_question_invalid", "d2_provider_input_privacy_only",
    "d2_http_response_choices_missing", "d2_http_response_content_missing",
    "d2_prompt_fullcontext_empty",
})
_PROSE_REVIEW_REASONS = frozenset({
    "d2_model_prose_money", "d2_model_prose_link",
})
_SOURCE_FILES = (
    "app.py", "core/d2_diagnostics.py", "core/d2_http_adapter.py",
    "core/d2_dialogue.py", "core/d2_live_provider.py",
)


def _quiet(fn):
    @wraps(fn)
    def safe(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception:
            return None
    return safe


@dataclass
class _Attempt:
    trace: str = field(default_factory=lambda: uuid4().hex)
    started: float = field(default_factory=monotonic)
    stage: str = "ingress"
    commit: str = "unknown"
    replay: bool = False
    provider_attempts: int = 0
    failed: bool = False
    streaming: bool = False
    done_emitted: bool = False
    finished: bool = False


def _write(fields):
    from logging_setup import get_logger, log_json_no_context
    log_json_no_context(get_logger("bot"), "d2_diagnostic", **fields)


@_quiet
def _event(attempt, event, *, reason="none", duration_ms=None):
    if attempt is None:
        return
    fields = dict(
        event=event, attempt_trace_id=attempt.trace, stage=attempt.stage,
        code_site=_STAGES[attempt.stage], reason=reason,
        commit_state=attempt.commit, replay=attempt.replay,
        provider_attempts=attempt.provider_attempts,
    )
    if duration_ms is not None:
        fields["duration_ms"] = duration_ms
    _write(fields)


@_quiet
def startup():
    # Snapshot of these five source files on disk at startup, NOT a guarantee
    # about all imported code, a clean checkout, or later edits on disk.
    root = Path(__file__).resolve().parents[1]
    digest = sha256()
    for name in _SOURCE_FILES:
        digest.update(name.encode() + b"\0" + (root / name).read_bytes() + b"\0")
    _write(dict(event="source_snapshot", commit="unknown",
                source_scope="rec1_five_files_on_disk_at_startup",
                source_files_sha256=digest.hexdigest()))


@_quiet
def _begin():
    attempt = _Attempt()
    _event(attempt, "attempt_started")
    return attempt


class _Bound:
    def __init__(self, attempt):
        self.attempt = attempt
        self.token = None

    @_quiet
    def __enter__(self):
        self.token = _current.set(self.attempt)

    @_quiet
    def __exit__(self, *_exc):
        if self.token is not None:
            _current.reset(self.token)


@_quiet
def stage(name):
    attempt = _current.get()
    if attempt is not None and name in _STAGES:
        attempt.stage = name
        _event(attempt, "stage_started")


@_quiet
def prose_review_signal(reason):
    """Best-effort observation, not a turn failure or a prose verdict."""
    if reason in _PROSE_REVIEW_REASONS:
        _event(_current.get(), "prose_review_signal", reason=reason)


@_quiet
def failure(exc):
    attempt = _current.get()
    if attempt is None or attempt.failed:
        return
    attempt.failed = True
    reason = "unknown"
    if isinstance(exc, TimeoutError):
        reason = "provider_timeout" if attempt.stage == "provider_transport" else "timeout"
    elif isinstance(exc, ValueError):
        reason = "invalid_envelope" if attempt.stage == "parse" else "invalid_value"
    # Only an exact built-in string from the closed vocabulary may escape.
    args = exc.args
    if args and type(args[0]) is str and args[0] in _REASONS:
        reason = args[0]
    _event(attempt, "failure", reason=reason)


@_quiet
def committed():
    attempt = _current.get()
    if attempt is not None:
        attempt.commit = "confirmed"
        _event(attempt, "commit_confirmed")


@_quiet
def replayed():
    attempt = _current.get()
    if attempt is not None:
        attempt.replay = True
        attempt.commit = "confirmed"
        _event(attempt, "replay")


@_quiet
def completion_not_found():
    attempt = _current.get()
    if attempt is not None:
        _event(attempt, "completion_not_found")


@_quiet
def _finish(attempt, event):
    if attempt is not None and not attempt.finished:
        attempt.finished = True
        _event(attempt, event, duration_ms=max(0, int((monotonic() - attempt.started) * 1000)))


def http_attempt(fn):
    @wraps(fn)
    def observed(*args, **kwargs):
        attempt = _begin()
        with _Bound(attempt):
            try:
                result = fn(*args, **kwargs)
            except BaseException as exc:
                failure(exc)
                _finish(attempt, "http_raised")
                raise
            _http_returned(attempt, result)
            return result
    return observed


@_quiet
def _http_returned(attempt, result):
    if attempt is None or attempt.streaming:
        return
    status = result[1] if isinstance(result, tuple) else getattr(result, "status_code", 200)
    # A returned Response is not proof that the client received it.
    _finish(attempt, "http_rejected" if type(status) is int and status >= 400 else "http_returned")


class _Stream:
    def __init__(self, iterator, attempt):
        self.iterator, self.attempt = iterator, attempt
        self.closed = False

    def __iter__(self):
        return self

    def __next__(self):
        with _Bound(self.attempt):
            try:
                chunk = next(self.iterator)
            except StopIteration:
                _finish(self.attempt, "stream_exhausted")
                raise
            except BaseException as exc:
                failure(exc)
                _finish(self.attempt, "stream_raised")
                raise
            _chunk_emitted(self.attempt)
        return chunk

    def close(self):
        if self.closed:
            return
        self.closed = True
        with _Bound(self.attempt):
            try:
                self.iterator.close()
            except BaseException as exc:
                failure(exc)
                raise
            finally:
                _closed(self.attempt)


@_quiet
def _chunk_emitted(attempt):
    if attempt is not None and attempt.stage == "stream_done":
        attempt.done_emitted = True
        _event(attempt, "stream_done_emitted")


@_quiet
def _closed(attempt):
    _finish(attempt, "stream_closed_after_done" if attempt is not None and attempt.done_emitted
            else "stream_disconnected")


@_quiet
def _stream_attempt():
    attempt = _current.get()
    if attempt is not None:
        attempt.streaming = True
    return attempt


def stream(iterator):
    return _Stream(iterator, _stream_attempt())


@_quiet
def _provider_started():
    attempt = _current.get()
    if attempt is not None:
        attempt.provider_attempts += 1
    stage("provider_transport")
    return attempt, monotonic()


@_quiet
def _provider_finished(observation):
    if observation is not None:
        attempt, started = observation
        _event(attempt, "provider_finished", duration_ms=max(0, int((monotonic() - started) * 1000)))


def call_provider(transport, **kwargs):
    """Count this existing transport invocation, not hidden SDK network retries."""
    observation = _provider_started()
    try:
        return transport(**kwargs)
    except BaseException as exc:
        failure(exc)
        raise
    finally:
        _provider_finished(observation)
