"""Patient-visible TTFT from production /ask/stream SSE (Stage 3C)."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any, Literal

PatientTextKind = Literal["text_delta", "ui_answer", "none"]

_CONTROL_MARKER_PREFIXES = ("@ANSWER", "@ADMIN", "@ANS")
_JSON_ENVELOPE_START = re.compile(r"^\s*[\{\"]")
_STATUS_EVENT = "event: status"
_TYPING_EVENT = "event: typing"
_TEXT_DELTA_EVENT = "event: text_delta"
_UI_EVENT = "event: ui"
_DONE_EVENT = "event: done"


@dataclass(frozen=True, slots=True)
class PatientVisibleTiming:
    patient_ttft_ms: int | None
    total_ms: int
    patient_text_kind: PatientTextKind
    widget_payload_ready: bool
    first_visible_excerpt: str | None


def _is_control_or_service_text(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    upper = stripped.upper()
    for prefix in _CONTROL_MARKER_PREFIXES:
        if upper.startswith(prefix):
            return True
    if _JSON_ENVELOPE_START.match(stripped):
        return True
    return False


def _extract_ui_answer(event_block: str) -> str | None:
    for line in event_block.splitlines():
        if line.startswith("data:"):
            payload_raw = line[5:].strip()
            if not payload_raw:
                continue
            try:
                payload = json.loads(payload_raw)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                answer = payload.get("answer")
                if isinstance(answer, str) and answer.strip():
                    return answer
    return None


def measure_patient_visible_timing(
    *,
    stream_text: str,
    request_started_monotonic: float,
    first_visible_monotonic: float | None = None,
    completed_monotonic: float | None = None,
) -> PatientVisibleTiming:
    """First patient-visible text excludes control markers, JSON envelopes, status, typing."""

    completed = completed_monotonic or time.monotonic()
    total_ms = max(0, int((completed - request_started_monotonic) * 1000))

    first_kind: PatientTextKind = "none"
    first_excerpt: str | None = None
    first_visible_at = first_visible_monotonic
    widget_ready = _DONE_EVENT in stream_text and _UI_EVENT in stream_text

    if first_visible_at is None:
        blocks = stream_text.split("\n\n")
        cursor = request_started_monotonic
        for block in blocks:
            if _STATUS_EVENT in block or _TYPING_EVENT in block:
                continue
            if _TEXT_DELTA_EVENT in block:
                for line in block.splitlines():
                    if not line.startswith("data:"):
                        continue
                    delta = line[5:].strip()
                    if not delta or _is_control_or_service_text(delta):
                        continue
                    first_kind = "text_delta"
                    first_excerpt = delta[:64]
                    first_visible_at = cursor
                    break
                if first_visible_at is not None:
                    break
            if _UI_EVENT in block:
                answer = _extract_ui_answer(block)
                if answer and not _is_control_or_service_text(answer):
                    first_kind = "ui_answer"
                    first_excerpt = answer[:64]
                    first_visible_at = cursor
                    break
            cursor += 0.001

    patient_ttft_ms: int | None = None
    if first_visible_at is not None:
        patient_ttft_ms = max(0, int((first_visible_at - request_started_monotonic) * 1000))
    if first_kind == "ui_answer" and patient_ttft_ms is not None and patient_ttft_ms <= 5:
        # Blocking test client: ui-only answers arrive when the HTTP response completes.
        patient_ttft_ms = total_ms

    return PatientVisibleTiming(
        patient_ttft_ms=patient_ttft_ms,
        total_ms=total_ms,
        patient_text_kind=first_kind,
        widget_payload_ready=widget_ready,
        first_visible_excerpt=first_excerpt,
    )


def execute_stream_turn(
    client: Any,
    *,
    sid: str,
    client_id: str,
    body: dict[str, object],
) -> dict[str, object]:
    started = time.monotonic()
    response = client.post(
        "/ask/stream",
        json={**body, "sid": sid, "client_id": client_id},
    )
    stream_text = response.get_data(as_text=True)
    completed = time.monotonic()
    timing = measure_patient_visible_timing(
        stream_text=stream_text,
        request_started_monotonic=started,
        completed_monotonic=completed,
    )
    ui_payload: dict[str, object] | None = None
    for block in stream_text.split("\n\n"):
        if _UI_EVENT not in block:
            continue
        for line in block.splitlines():
            if line.startswith("data:"):
                try:
                    parsed = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    ui_payload = parsed
                    break
    return {
        "status_code": response.status_code,
        "stream_text": stream_text,
        "ui_payload": ui_payload,
        "answer_text": str((ui_payload or {}).get("answer") or ""),
        "meta": (ui_payload or {}).get("meta") if isinstance((ui_payload or {}).get("meta"), dict) else {},
        "patient_ttft_ms": timing.patient_ttft_ms,
        "total_ms": timing.total_ms,
        "patient_text_kind": timing.patient_text_kind,
        "widget_payload_ready": timing.widget_payload_ready,
        "first_visible_excerpt": timing.first_visible_excerpt,
    }
