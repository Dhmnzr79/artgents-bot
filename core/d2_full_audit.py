"""Opt-in local transcript for debugging D2 turns, never a product event log.

The file contains patient text and model output. It is deliberately separate
from the redacted application log and is disabled in production.
"""

from __future__ import annotations

import json
import os
import re
import threading
import traceback
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_REPO_ROOT = Path(__file__).resolve().parents[1]
_TRACE_ID: ContextVar[str | None] = ContextVar("d2_full_audit_trace_id", default=None)
_WRITE_LOCK = threading.Lock()
_CREDENTIAL_KEY = re.compile(r"(?i)(?:api[_-]?key|access[_-]?token|authorization|password|secret)")
_SECRET_PATTERNS = (
    re.compile(r"(?i)\bBearer\s+\S+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(
        r'(?i)((?:\\?")?(?:api[_-]?key|access[_-]?token|authorization|password|secret)'
        r'(?:\\?")?\s*[:=]\s*(?:\\?")?)([^"\\\s,}\]]+)'
    ),
)


def full_audit_enabled() -> bool:
    return (
        os.getenv("D2_FULL_AUDIT_LOG") == "1"
        and (os.getenv("APP_ENV") or "local").strip().lower() not in {"prod", "production"}
    )


def full_audit_path() -> Path:
    configured = Path(os.getenv("BOT_LOG_DIR") or "logs")
    log_dir = configured if configured.is_absolute() else _REPO_ROOT / configured
    return log_dir / "d2_full_audit.jsonl"


class full_audit_trace:
    """Set the trace without contextlib changing frozen exception objects."""

    def __init__(self, trace_id: str) -> None:
        self.trace_id = trace_id
        self.token = None

    def __enter__(self) -> None:
        self.token = _TRACE_ID.set(self.trace_id)

    def __exit__(self, _exc_type, _exc, _tb) -> bool:
        _TRACE_ID.reset(self.token)
        return False


def _json_value(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (tuple, set, frozenset)):
        return list(value)
    return str(value)


def _scrub_credentials(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    if isinstance(value, dict):
        return {
            str(key): ("[REDACTED_CREDENTIAL]" if _CREDENTIAL_KEY.search(str(key))
                       else _scrub_credentials(item))
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_scrub_credentials(item) for item in value]
    if isinstance(value, str):
        return _redact_secrets(value)
    return value


def _redact_secrets(serialized: str) -> str:
    result = serialized
    for pattern in _SECRET_PATTERNS[:2]:
        result = pattern.sub("[REDACTED_CREDENTIAL]", result)
    result = _SECRET_PATTERNS[2].sub(r"\1[REDACTED_CREDENTIAL]", result)
    return result


def full_audit(event: str, *, trace_id: str | None = None, **fields: Any) -> None:
    """Append one complete local D2 event when explicitly enabled.

    Never pass environment variables, credentials, cookies or HTTP headers.
    Logging failure is reported by type only and cannot fail a user turn.
    """
    if not full_audit_enabled():
        return
    effective_trace = trace_id or _TRACE_ID.get()
    if effective_trace is None:
        return
    try:
        row = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "trace_id": effective_trace,
            "event": event,
            **fields,
        }
        line = json.dumps(_scrub_credentials(row), ensure_ascii=False, default=_json_value)
        path = full_audit_path()
        with _WRITE_LOCK:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as stream:
                stream.write(line + "\n")
    except Exception as exc:
        from logging_setup import get_logger, log_json_no_context

        log_json_no_context(get_logger("bot"), "d2_full_audit_write_failed",
                            trace_id=effective_trace, error_type=type(exc).__name__)


def full_audit_exception(stage: str, exc: Exception, *, trace_id: str | None = None) -> None:
    full_audit(
        "exception", trace_id=trace_id, stage=stage,
        exception_type=type(exc).__name__,
        traceback="".join(traceback.format_exception(exc)),
    )
