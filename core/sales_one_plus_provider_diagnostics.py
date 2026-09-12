"""Safe provider error diagnostics for sales-fast One Call."""

from __future__ import annotations

import time
from typing import Any, Literal

from logging_setup import get_logger, log_json

ProviderErrorCategory = Literal[
    "timeout",
    "rate_limit",
    "provider_4xx",
    "provider_5xx",
    "connection",
    "stream_interrupted",
    "unknown",
]

_SENSITIVE_MARKERS = (
    "authorization",
    "api-key",
    "apikey",
    "bearer",
    "system",
    "user",
    "messages",
    "prompt",
)


def _http_status_from_exception(exc: BaseException) -> int | None:
    for attr in ("status_code", "http_status", "status"):
        value = getattr(exc, attr, None)
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                continue
    response = getattr(exc, "response", None)
    if response is not None:
        status = getattr(response, "status_code", None)
        if status is not None:
            try:
                return int(status)
            except (TypeError, ValueError):
                return None
    return None


def _provider_request_id_from_exception(exc: BaseException) -> str | None:
    for attr in ("request_id", "x_request_id"):
        value = getattr(exc, attr, None)
        if value:
            return str(value)[:128]
    response = getattr(exc, "response", None)
    if response is not None:
        headers = getattr(response, "headers", None)
        if isinstance(headers, dict):
            for key in ("x-request-id", "request-id", "x-dashscope-request-id"):
                if headers.get(key):
                    return str(headers.get(key))[:128]
    return None


def categorize_provider_exception(
    exc: BaseException,
    *,
    stream_interrupted: bool = False,
) -> ProviderErrorCategory:
    if stream_interrupted:
        return "stream_interrupted"
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    if "timeout" in name or "timeout" in text or "timed out" in text:
        return "timeout"
    if "ratelimit" in name or "rate limit" in text or "429" in text:
        return "rate_limit"
    status = _http_status_from_exception(exc)
    if status == 429:
        return "rate_limit"
    if status is not None and 400 <= status < 500:
        return "provider_4xx"
    if status is not None and status >= 500:
        return "provider_5xx"
    if any(token in name for token in ("connection", "connect", "network")):
        return "connection"
    if any(token in text for token in ("connection", "connect", "network", "refused")):
        return "connection"
    return "unknown"


def _safe_error_message(exc: BaseException) -> str:
    message = f"{type(exc).__name__}: {exc}"
    lowered = message.lower()
    if any(marker in lowered for marker in _SENSITIVE_MARKERS):
        return type(exc).__name__
    return message[:300]


def log_sales_one_plus_provider_error(
    *,
    exc: BaseException,
    requested_model: str,
    configured_timeout_sec: float,
    elapsed_ms: int,
    stream: bool,
    received_first_stream_chunk: bool,
    stream_interrupted: bool = False,
) -> ProviderErrorCategory:
    category = categorize_provider_exception(
        exc,
        stream_interrupted=stream_interrupted,
    )
    log_json(
        get_logger("bot"),
        "sales_one_plus_provider_error",
        exception_class=type(exc).__name__,
        category=category,
        http_status=_http_status_from_exception(exc),
        provider_request_id=_provider_request_id_from_exception(exc),
        elapsed_ms=elapsed_ms,
        configured_timeout_sec=configured_timeout_sec,
        requested_model=requested_model,
        stream=stream,
        received_first_stream_chunk=received_first_stream_chunk,
        error_message=_safe_error_message(exc),
    )
    return category


def monotonic_elapsed_ms(started: float) -> int:
    return max(0, int((time.monotonic() - started) * 1000))
