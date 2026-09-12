"""Gunicorn runtime settings (process model validation, no network)."""
from __future__ import annotations

_DEFAULT_THREADS = 8
_MIN_THREADS = 2
_MAX_THREADS = 16


def parse_gunicorn_threads(raw: str | None = None) -> int:
    """Validate GUNICORN_THREADS for single-process gthread workers."""
    value = (raw if raw is not None else "").strip() or str(_DEFAULT_THREADS)
    if not value.isdigit():
        raise ValueError("gunicorn_threads_invalid")
    threads = int(value)
    if threads < _MIN_THREADS or threads > _MAX_THREADS:
        raise ValueError("gunicorn_threads_out_of_range")
    return threads
