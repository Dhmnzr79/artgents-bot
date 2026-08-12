# logging_setup.py
import atexit
import json
import logging
import os
import queue
import re
import sys
import threading
import time
import uuid
from datetime import datetime
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from pathlib import Path

from config import estimate_llm_usage_usd

_REPO_ROOT = Path(__file__).resolve().parent
_LOG_ROTATION_MAX_BYTES = int(os.getenv("BOT_LOG_MAX_BYTES", "10000000"))
_LOG_ROTATION_BACKUP_COUNT = int(os.getenv("BOT_LOG_BACKUP_COUNT", "5"))
_LOG_WRITER_MODE = "queue_listener"

_log_init_lock = threading.Lock()
_log_queue: queue.Queue | None = None
_log_listener: QueueListener | None = None
_loggers_with_queue: set[str] = set()
_logging_initialized = False
_startup_event_emitted = False

_LOG_RETENTION_DAYS = int(os.getenv("BOT_LOG_RETENTION_DAYS", "7"))
_LOG_PURGE_DONE = False
_LOG_NAME_RX = re.compile(r"\.(?:jsonl|log)(?:\.\d+)?$", re.IGNORECASE)

SENSITIVE_KEYS = ("api_key", "apikey", "token", "secret", "authorization", "password")
_USAGE_TOKEN_KEYS = frozenset({"prompt_tokens", "completion_tokens", "total_tokens", "cached_tokens"})
_PHONE_DIGIT_MIN = 10
_PHONE_DIGIT_MAX = 15
# Ловим номера в разных форматах: +7..., 8(...), с пробелами/скобками/дефисами.
_PHONE_TEXT_RX = re.compile(r"(?<!\d)(?:\+?\d[\d\-\s().]{8,}\d)(?!\d)")

BOT_EVENTS_SCHEMA_VERSION = int(os.getenv("BOT_EVENTS_SCHEMA_VERSION", "1"))


def resolve_log_paths(
    *,
    repo_root: Path | None = None,
    log_dir_env: str | None = None,
    log_file_env: str | None = None,
) -> tuple[str, str]:
    """Resolve absolute LOG_DIR and LOG_FILE independent of process CWD."""
    root = (repo_root or _REPO_ROOT).resolve()
    raw_dir = log_dir_env if log_dir_env is not None else os.getenv("BOT_LOG_DIR", "logs")
    raw_file = log_file_env if log_file_env is not None else os.getenv("BOT_LOG_FILE", "app.jsonl")

    file_path = Path(raw_file)
    if file_path.is_absolute():
        log_file = file_path.resolve()
        log_dir = log_file.parent
        return str(log_dir), str(log_file)

    dir_path = Path(raw_dir)
    if not dir_path.is_absolute():
        dir_path = (root / dir_path).resolve()
    else:
        dir_path = dir_path.resolve()

    resolved_file = (dir_path / file_path).resolve()
    try:
        resolved_file.relative_to(dir_path)
    except ValueError as exc:
        raise ValueError(
            f"BOT_LOG_FILE must resolve inside LOG_DIR ({dir_path}): {raw_file!r}"
        ) from exc
    return str(dir_path), str(resolved_file)


LOG_DIR, LOG_FILE = resolve_log_paths()


def log_rotation_max_bytes() -> int:
    return _LOG_ROTATION_MAX_BYTES


def log_rotation_backup_count() -> int:
    return _LOG_ROTATION_BACKUP_COUNT


def log_writer_mode() -> str:
    return _LOG_WRITER_MODE


def _mask_phone_like(value):
    s = str(value or "")
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) < _PHONE_DIGIT_MIN or len(digits) > _PHONE_DIGIT_MAX:
        return value
    if len(digits) >= 11:
        return f"+{digits[0]}******{digits[-2:]}"
    return "***"


def _mask_phone_in_text(value):
    s = str(value or "")
    return _PHONE_TEXT_RX.sub(lambda m: str(_mask_phone_like(m.group())), s)


def redact_text(value: str, *, max_len: int | None = None) -> str:
    """Явная редактирующая функция для payload до записи в любое хранилище."""
    out = _mask_phone_in_text(value or "")
    if max_len is not None and max_len > 0 and len(out) > max_len:
        return out[:max_len]
    return out


def _sanitize(d):
    if not isinstance(d, dict):
        return d
    clean = {}
    for k, v in d.items():
        kl = k.lower() if isinstance(k, str) else ""
        if isinstance(k, str) and kl not in _USAGE_TOKEN_KEYS and any(s in kl for s in SENSITIVE_KEYS):
            clean[k] = "***"
        elif isinstance(k, str) and ("phone" in kl or "tel" in kl):
            clean[k] = _mask_phone_like(v)
        elif isinstance(k, str) and "situation" in kl:
            txt = _mask_phone_in_text(v)
            clean[k] = (txt[:80] + "…") if len(txt) > 80 else txt
        elif isinstance(v, dict):
            clean[k] = _sanitize(v)
        elif isinstance(v, list):
            clean[k] = [
                _sanitize(x) if isinstance(x, dict) else (_mask_phone_in_text(x) if isinstance(x, str) else x)
                for x in v
            ]
        elif isinstance(v, str):
            clean[k] = _mask_phone_in_text(v)
        else:
            clean[k] = v
    return clean


class JsonLineFormatter(logging.Formatter):
    def format(self, record):
        base = {
            "ts": datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        extra = getattr(record, "extra_data", None)
        if isinstance(extra, dict):
            base.update(extra)
        return json.dumps(base, ensure_ascii=False)


def log_retention_days() -> int:
    """File log retention window; 0 disables time-based purge."""
    return max(0, _LOG_RETENTION_DAYS)


def _is_log_file_name(name: str) -> bool:
    return bool(_LOG_NAME_RX.search(name or ""))


def purge_old_log_files(*, logger: logging.Logger | None = None) -> list[str]:
    """Delete rotated/local log files older than BOT_LOG_RETENTION_DAYS (by mtime)."""
    days = log_retention_days()
    retention_dir = os.path.dirname(os.path.normpath(LOG_FILE))
    active_path = os.path.normpath(LOG_FILE)
    if days <= 0 or not os.path.isdir(retention_dir):
        return []
    cutoff = time.time() - days * 86400
    removed: list[str] = []
    for name in os.listdir(retention_dir):
        if not _is_log_file_name(name):
            continue
        path = os.path.join(retention_dir, name)
        if not os.path.isfile(path):
            continue
        if os.path.normpath(path) == active_path:
            continue
        try:
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
                removed.append(name)
        except OSError:
            continue
    if removed and logger is not None:
        log_json(logger, "log_retention_purge", retention_days=days, removed=removed)
    return removed


def _shutdown_logging() -> None:
    global _log_listener
    with _log_init_lock:
        listener = _log_listener
        _log_listener = None
    if listener is not None:
        listener.stop()


def _emit_logging_startup(logger: logging.Logger) -> None:
    global _startup_event_emitted
    if _startup_event_emitted:
        return
    log_json(
        logger,
        "logging_startup",
        log_path=LOG_FILE,
        writer_mode=_LOG_WRITER_MODE,
        pid=os.getpid(),
        max_bytes=_LOG_ROTATION_MAX_BYTES,
        backup_count=_LOG_ROTATION_BACKUP_COUNT,
        retention_days=log_retention_days(),
    )
    _startup_event_emitted = True


def _ensure_logging_initialized() -> None:
    global _logging_initialized, _log_queue, _log_listener, LOG_DIR, LOG_FILE
    if _logging_initialized:
        return
    with _log_init_lock:
        if _logging_initialized:
            return
        LOG_DIR, LOG_FILE = resolve_log_paths()
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

        _log_queue = queue.Queue(-1)
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=_LOG_ROTATION_MAX_BYTES,
            backupCount=_LOG_ROTATION_BACKUP_COUNT,
            encoding="utf-8",
        )
        fmt = JsonLineFormatter()
        file_handler.setFormatter(fmt)

        stream = sys.stdout
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
        console_handler = logging.StreamHandler(stream)
        console_handler.setFormatter(fmt)

        _log_listener = QueueListener(
            _log_queue,
            file_handler,
            console_handler,
            respect_handler_level=True,
        )
        _log_listener.start()
        atexit.register(_shutdown_logging)

        startup_logger = logging.getLogger("logging_startup")
        startup_logger.setLevel(logging.INFO)
        startup_logger.propagate = False
        if "logging_startup" not in _loggers_with_queue:
            startup_logger.addHandler(QueueHandler(_log_queue))
            _loggers_with_queue.add("logging_startup")
        _emit_logging_startup(startup_logger)
        _logging_initialized = True


def get_logger(name="bot"):
    global _LOG_PURGE_DONE
    _ensure_logging_initialized()
    with _log_init_lock:
        logger = logging.getLogger(name)
        if name in _loggers_with_queue:
            return logger
        logger.setLevel(logging.INFO)
        logger.propagate = False
        assert _log_queue is not None
        logger.addHandler(QueueHandler(_log_queue))
        _loggers_with_queue.add(name)
        if not _LOG_PURGE_DONE:
            _LOG_PURGE_DONE = True
            purge_old_log_files()
        return logger


def request_context_defaults() -> dict:
    """Поля HTTP-запроса для склейки пайплайна (без обязательного Flask вне контекста)."""
    try:
        from flask import has_request_context, request

        if has_request_context() and getattr(request, "ctx", None):
            ctx = request.ctx
            sid = ctx.get("sid")
            out = {
                "request_id": ctx.get("request_id"),
                "sid": sid,
                "session_id": sid,
                "client_id": ctx.get("client_id"),
                "path": ctx.get("path"),
            }
            return {k: v for k, v in out.items() if v is not None}
    except Exception:
        pass
    return {}


def make_request_context(cookie_sid=None):
    """Контекст запроса: request_id + sid из cookie до разбора body."""
    cookie = (cookie_sid or "").strip() or None
    return {
        "request_id": str(uuid.uuid4()),
        "sid": cookie,
        "session_id": cookie,
        "client_id": None,
        "app_version": os.getenv("APP_VERSION", "dev"),
        "env": os.getenv("APP_ENV", "local"),
    }


def emit_bot_event(
    logger,
    event_name: str,
    *,
    status=None,
    details: dict | None = None,
    **overrides: object,
):
    """Продуктовое событие для дашборда и Postgres-импорта (единый контракт)."""
    row = {
        "kind": "bot_event",
        "schema_version": BOT_EVENTS_SCHEMA_VERSION,
        "event_type": event_name,
    }
    row["ts"] = datetime.utcnow().isoformat(timespec="milliseconds") + "Z"
    row.update(request_context_defaults())
    for k, v in overrides.items():
        if v is not None:
            row[k] = v
    if status is not None:
        row["status"] = status
    row["details"] = dict(details or {})
    try:
        from core.observability_pii import scrub_observability_details

        row["details"] = scrub_observability_details(row["details"])
    except Exception:
        pass
    safe_row = _sanitize(row)
    try:
        from core.client_config_loader import postgres_events_enabled
        from pg_sink import enqueue_bot_event

        cid = safe_row.get("client_id")
        if postgres_events_enabled(cid):
            enqueue_bot_event(safe_row)
    except Exception:
        pass
    logger.info("bot_event", extra={"extra_data": safe_row})


def log_json(logger, message, **fields):
    """Как раньше, плюс подстановка request_id / sid / client_id / path из Flask ctx."""
    inj = request_context_defaults()
    for k, v in inj.items():
        if k == "session_id":
            continue
        fields.setdefault(k, v)
    _write_log_json(logger, message, fields)


def log_json_no_context(logger, message, **fields):
    """Structured log without implicit Flask request-context fields."""
    _write_log_json(logger, message, fields)


def _write_log_json(logger, message, fields) -> None:
    safe = _sanitize(fields)
    logger.info(message, extra={"extra_data": safe})
    _forward_record_for_pytest_caplog(logger, message, safe)


def _forward_record_for_pytest_caplog(logger, message, extra_data) -> None:
    if "PYTEST_CURRENT_TEST" not in os.environ:
        return
    root = logging.getLogger()
    if not root.handlers:
        return
    record = logger.makeRecord(
        logger.name,
        logging.INFO,
        "(logging_setup)",
        0,
        message,
        (),
        None,
    )
    record.extra_data = extra_data
    for handler in root.handlers:
        module = getattr(handler.__class__, "__module__", "")
        if module.startswith("_pytest") or handler.__class__.__name__ == "LogCaptureHandler":
            handler.handle(record)


def _cached_tokens_from_usage_obj(u: object) -> int | None:
    details = getattr(u, "prompt_tokens_details", None)
    if details is None:
        return None
    ct = getattr(details, "cached_tokens", None)
    if ct is None and isinstance(details, dict):
        ct = details.get("cached_tokens")
    try:
        return int(ct) if ct is not None else None
    except (TypeError, ValueError):
        return None


def usage_dict_from_completion(resp) -> dict | None:
    u = getattr(resp, "usage", None)
    if u is None:
        return None
    pt = getattr(u, "prompt_tokens", None)
    ct = getattr(u, "completion_tokens", None)
    tt = getattr(u, "total_tokens", None)
    out = {
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "total_tokens": tt,
    }
    cached = _cached_tokens_from_usage_obj(u)
    if cached is not None:
        out["cached_tokens"] = int(cached)
    est = estimate_llm_usage_usd(prompt_tokens=pt, completion_tokens=ct)
    if est is not None:
        out["estimated_usd"] = est
    return out


def log_llm_usage(
    logger,
    resp,
    *,
    call_type: str,
    model: str | None = None,
    extra_details: dict | None = None,
):
    """После успешного chat.completions.create (non-stream)."""
    u = usage_dict_from_completion(resp)
    if not u:
        return
    det = {"call_type": call_type, "model": model or getattr(resp, "model", None)}
    if extra_details:
        det.update(extra_details)
    det.update(u)
    emit_bot_event(logger, "llm_usage", details=det)


def log_llm_stream_usage(
    logger,
    usage_obj,
    *,
    call_type: str,
    model: str | None,
    extra_details: dict | None = None,
):
    """После stream с include_usage (или финальный chunk.usage)."""
    if usage_obj is None:
        return
    pt = getattr(usage_obj, "prompt_tokens", None)
    ct = getattr(usage_obj, "completion_tokens", None)
    tt = getattr(usage_obj, "total_tokens", None)
    det = {
        "call_type": call_type,
        "model": model,
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "total_tokens": tt,
    }
    cached = _cached_tokens_from_usage_obj(usage_obj)
    if cached is not None:
        det["cached_tokens"] = int(cached)
    est = estimate_llm_usage_usd(prompt_tokens=pt, completion_tokens=ct)
    if est is not None:
        det["estimated_usd"] = est
    if extra_details:
        det.update(extra_details)
    emit_bot_event(logger, "llm_usage", details=det)


def log_llm_error(logger, *, call_type: str, err: str, model: str | None = None):
    emit_bot_event(
        logger,
        "llm_error",
        status="error",
        details={
            "call_type": call_type,
            "error": (err or "")[:500],
            "model": model,
        },
    )
