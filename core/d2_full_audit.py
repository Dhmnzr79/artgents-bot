"""Opt-in, PII-inclusive local transcript of the current D2 HTTP attempt.

Never use this as an application event log. It is disabled by default and in
production; the separate REC-1 diagnostic channel remains text-free.
"""

from __future__ import annotations

import json
import os
import re
import threading
import traceback
from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core import d2_diagnostics


_ROOT = Path(__file__).resolve().parents[1]
_WRITE_LOCK = threading.Lock()
_CREDENTIAL_LABEL = r"(?:api[_-]?key|[a-z0-9_-]*token|authorization|password|secret)"
_CREDENTIAL_KEY = re.compile(rf"(?i){_CREDENTIAL_LABEL}\b")
_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(?:Bearer|Basic)\s+\S+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(
        rf'(?i)(\b{_CREDENTIAL_LABEL}\b\s*[:=]\s*)[^\r\n,}}\]]+'
    ),
)


def full_audit_enabled() -> bool:
    return (
        os.getenv("D2_FULL_AUDIT_LOG") == "1"
        and (os.getenv("APP_ENV") or "local").strip().lower() not in {"prod", "production"}
    )


def full_audit_path() -> Path:
    configured = Path(os.getenv("BOT_LOG_DIR") or "logs")
    log_dir = configured if configured.is_absolute() else _ROOT / configured
    return log_dir / "d2_full_audit.jsonl"


def _redact_secrets(value: str) -> str:
    # Raw HTTP bodies and some provider payloads are JSON encoded *inside* a
    # string. Scrub their keys structurally before applying plain-text rules.
    if _CREDENTIAL_KEY.search(value) and value.lstrip().startswith(("{", "[")):
        try:
            return json.dumps(_serialize(json.loads(value)), ensure_ascii=False)
        except (TypeError, ValueError):
            pass
    result = value
    for pattern in _SECRET_PATTERNS[:2]:
        result = pattern.sub("[REDACTED_CREDENTIAL]", result)
    return _SECRET_PATTERNS[2].sub(r"\1[REDACTED_CREDENTIAL]", result)


def _serialize(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _serialize(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {
            str(key): (
                "[REDACTED_CREDENTIAL]" if _CREDENTIAL_KEY.search(str(key))
                else _serialize(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_serialize(item) for item in value]
    if isinstance(value, str):
        return _redact_secrets(value)
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return _redact_secrets(str(value))


def full_audit(event: str, *, trace_id: str | None = None, **fields: Any) -> None:
    """Write one event; failure is never allowed to change the bot turn."""
    if not full_audit_enabled():
        return
    try:
        effective_trace = trace_id or d2_diagnostics.current_trace_id()
        if effective_trace is None:
            return
        row = _serialize({
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "trace_id": effective_trace,
            "event": event,
            **fields,
        })
        line = json.dumps(row, ensure_ascii=False, allow_nan=False)
        path = full_audit_path()
        with _WRITE_LOCK:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as stream:
                stream.write(line + "\n")
    except Exception as exc:
        try:
            from logging_setup import get_logger, log_json_no_context
            log_json_no_context(
                get_logger("bot"), "d2_full_audit_write_failed",
                error_type=type(exc).__name__,
            )
        except Exception:
            pass


def full_audit_exception(stage: str, exc: BaseException) -> None:
    if not full_audit_enabled():
        return
    try:
        formatted = "".join(traceback.format_exception(exc))
    except Exception:
        formatted = "[traceback_unavailable]"
    full_audit(
        "exception", stage=stage, exception_type=type(exc).__name__,
        traceback=formatted,
    )
