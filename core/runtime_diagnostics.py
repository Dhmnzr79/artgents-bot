"""PII-free runtime and SSE render diagnostics (ONE_CALL Stage 4.1)."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

_TIMING_MS_SUFFIX = "_ms"
_TIMING_SINCE_SUFFIX = "_since_start_ms"

_RUNTIME_TIMING_SCALAR_KEYS = frozenset(
    {
        "total_ms",
        "orchestrate_ms",
        "first_server_event_since_start_ms",
        "request_complete_since_start_ms",
        "orchestrate_done_since_start_ms",
    }
)

_SALES_FAST_OBS_SCALAR_KEYS = frozenset(
    {
        "architecture",
        "route",
        "provider_calls",
        "model",
        "failure_kind",
        "backend_invocations",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "cached_tokens",
        "cache_hit",
        "cache_key_sha256",
        "prefix_sha256",
        "client_pack_version",
        "local_prefix_cache_hit",
        "provider_cache_hit",
        "client_pack_hash",
        "prompt_contract_version",
        "requested_model",
        "observed_model",
        "provider_model_verified",
    }
)

_SALES_FAST_OBS_TIMING_KEYS = frozenset(
    {"local_gate", "resolver", "provider", "presentation", "sales_fast", "total"}
)

_FORBIDDEN_DIAGNOSTIC_KEYS = frozenset(
    {
        "sid",
        "session_id",
        "ip",
        "q",
        "question",
        "answer",
        "preview",
        "user_text",
        "bot_text",
        "delta",
        "patient_text",
        "error",
        "exception",
        "question_preview",
        "user_preview_redacted",
        "user_text_redacted",
        "bot_text_redacted",
    }
)

_SSE_EVENT_RX = re.compile(r"^event:\s*(\w+)", re.MULTILINE)
_SSE_DATA_RX = re.compile(r"^data:\s*(.+)$", re.MULTILINE)


def utf8_text_fingerprint(text: str) -> tuple[int, int, str]:
    """Return (char_count, utf8_byte_count, sha256_hex) for UTF-8 text."""
    normalized = text or ""
    encoded = normalized.encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    return len(normalized), len(encoded), digest


def _safe_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def extract_safe_timing_fields(summary: dict[str, Any] | None) -> dict[str, int]:
    if not isinstance(summary, dict):
        return {}
    out: dict[str, int] = {}
    for key, value in summary.items():
        if key == "stages":
            continue
        if key in _RUNTIME_TIMING_SCALAR_KEYS or key.endswith(_TIMING_MS_SUFFIX):
            parsed = _safe_int(value)
            if parsed is not None:
                out[key] = parsed
        elif key.endswith(_TIMING_SINCE_SUFFIX):
            parsed = _safe_int(value)
            if parsed is not None:
                out[key] = parsed
    return out


def extract_safe_sales_fast_observability(flag_value: object) -> dict[str, Any]:
    if not isinstance(flag_value, dict):
        return {}
    out: dict[str, Any] = {}
    for key in _SALES_FAST_OBS_SCALAR_KEYS:
        value = flag_value.get(key)
        if value is None:
            continue
        if key in {"provider_calls", "backend_invocations", "prompt_tokens", "completion_tokens", "total_tokens", "cached_tokens"}:
            parsed = _safe_int(value)
            if parsed is not None:
                out[key] = parsed
        elif key == "cache_hit":
            out[key] = bool(value)
        elif key in {"local_prefix_cache_hit", "provider_cache_hit", "provider_model_verified"}:
            out[key] = bool(value)
        elif isinstance(value, str):
            out[key] = value
    timings = flag_value.get("timings_ms")
    if isinstance(timings, dict):
        safe_timings: dict[str, int] = {}
        for key in _SALES_FAST_OBS_TIMING_KEYS:
            parsed = _safe_int(timings.get(key))
            if parsed is not None:
                safe_timings[key] = parsed
        if safe_timings:
            out["timings_ms"] = safe_timings
    return out


def build_runtime_turn_diagnostic_payload(
    *,
    request_id: str | None,
    client_id: str | None,
    transport: str,
    route: str | None,
    status: str,
    provider_calls: int,
    provider_policy: str | None,
    timing_summary: dict[str, Any] | None,
    sales_fast_observability: object | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "event": "runtime_turn_diagnostic",
        "request_id": request_id,
        "client_id": client_id,
        "transport": transport,
        "route": route,
        "status": status,
        "provider_calls": int(provider_calls),
        "provider_policy": provider_policy,
    }
    timings = extract_safe_timing_fields(timing_summary)
    if timings:
        payload["timings_ms"] = timings
    obs = extract_safe_sales_fast_observability(sales_fast_observability)
    if obs:
        payload["sales_fast"] = obs
    return _drop_forbidden_keys(payload)


def _drop_forbidden_keys(payload: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in payload.items() if k not in _FORBIDDEN_DIAGNOSTIC_KEYS}


def _parse_sse_block(block: str) -> tuple[str | None, dict[str, Any] | None]:
    event_match = _SSE_EVENT_RX.search(block or "")
    data_match = _SSE_DATA_RX.search(block or "")
    event_type = event_match.group(1) if event_match else None
    data_obj: dict[str, Any] | None = None
    if data_match:
        raw = data_match.group(1).strip()
        if raw:
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                data_obj = parsed
    return event_type, data_obj


@dataclass
class SseRenderDiagnosticTracker:
    request_id: str | None
    client_id: str | None
    route: str | None = None
    status: str = "completed"
    counts: dict[str, int] = field(
        default_factory=lambda: {
            "status": 0,
            "typing": 0,
            "text_delta": 0,
            "ui": 0,
            "done": 0,
        }
    )
    streamed_parts: list[str] = field(default_factory=list)
    final_text: str | None = None
    emitted: bool = False

    def track(self, block: str) -> str:
        event_type, data_obj = _parse_sse_block(block)
        if event_type in self.counts:
            self.counts[event_type] += 1
        if event_type == "text_delta" and isinstance(data_obj, dict):
            delta = data_obj.get("delta")
            if isinstance(delta, str) and delta:
                self.streamed_parts.append(delta)
        elif event_type == "ui" and isinstance(data_obj, dict):
            answer = data_obj.get("answer")
            if isinstance(answer, str):
                self.final_text = answer
            meta = data_obj.get("meta")
            if isinstance(meta, dict):
                service_route = meta.get("service_route")
                if isinstance(service_route, str) and service_route.strip():
                    self.route = service_route.strip()
        return block

    def build_payload(self) -> dict[str, Any]:
        streamed_text = "".join(self.streamed_parts)
        final_text = self.final_text or ""
        streamed_chars, streamed_bytes, streamed_sha = utf8_text_fingerprint(streamed_text)
        final_chars, final_bytes, final_sha = utf8_text_fingerprint(final_text)
        if self.counts.get("text_delta", 0) == 0:
            stream_matches_final = None
        else:
            stream_matches_final = streamed_text == final_text
        return {
            "event": "sse_render_diagnostic",
            "request_id": self.request_id,
            "client_id": self.client_id,
            "route": self.route,
            "status": self.status,
            "sse_event_counts": dict(self.counts),
            "streamed_text_chars": streamed_chars,
            "streamed_text_utf8_bytes": streamed_bytes,
            "streamed_text_sha256": streamed_sha,
            "final_text_chars": final_chars,
            "final_text_utf8_bytes": final_bytes,
            "final_text_sha256": final_sha,
            "stream_matches_final": stream_matches_final,
        }
