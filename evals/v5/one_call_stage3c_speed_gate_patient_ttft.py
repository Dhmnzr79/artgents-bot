"""Patient-visible TTFT from production /ask/stream SSE (Stage 3C)."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, Literal

PatientTextKind = Literal["text_delta", "ui_answer", "none"]
FirstVisibleEventType = Literal["text_delta", "ui", "none"]

_CONTROL_MARKER_PREFIXES = ("@ANSWER", "@ADMIN", "@ANS")
_JSON_ENVELOPE_START = re.compile(r"^\s*[\{\"]")
_STATUS_EVENT = "event: status"
_TYPING_EVENT = "event: typing"
_TEXT_DELTA_EVENT = "event: text_delta"
_UI_EVENT = "event: ui"
_DONE_EVENT = "event: done"

MonotonicClock = Callable[[], float]
ANSWER_EXCERPT_MAX = 2000


@dataclass(frozen=True, slots=True)
class PatientVisibleTiming:
    patient_ttft_ms: int | None
    total_ms: int
    patient_text_kind: PatientTextKind
    widget_payload_ready: bool
    first_visible_excerpt: str | None
    first_visible_event_type: FirstVisibleEventType
    ttft_measurement_valid: bool
    sse_event_count: int


@dataclass(slots=True)
class SseEvent:
    event: str
    data: str
    arrival_monotonic: float


@dataclass(slots=True)
class IncrementalSseDecoder:
    """Buffer SSE bytes/strings; emit complete events as chunks arrive."""

    _buffer: str = ""

    def feed(self, chunk: str, arrival_monotonic: float) -> list[SseEvent]:
        self._buffer += chunk
        events: list[SseEvent] = []
        while "\n\n" in self._buffer:
            block, self._buffer = self._buffer.split("\n\n", 1)
            parsed = _parse_sse_block(block)
            if parsed is not None:
                events.append(
                    SseEvent(
                        event=parsed[0],
                        data=parsed[1],
                        arrival_monotonic=arrival_monotonic,
                    )
                )
        return events


def _parse_sse_block(block: str) -> tuple[str, str] | None:
    event_name = ""
    data_lines: list[str] = []
    for line in block.splitlines():
        if line.startswith("event:"):
            event_name = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].strip())
    if not event_name and not data_lines:
        return None
    return event_name, "\n".join(data_lines)


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


def _decode_text_delta_payload(data: str) -> str | None:
    payload_raw = data.strip()
    if not payload_raw:
        return None
    try:
        payload = json.loads(payload_raw)
    except json.JSONDecodeError:
        # Legacy plain-text delta lines in tests.
        if _is_control_or_service_text(payload_raw):
            return None
        return payload_raw
    if not isinstance(payload, dict):
        return None
    delta = payload.get("delta")
    if not isinstance(delta, str):
        return None
    if not delta.strip() or _is_control_or_service_text(delta):
        return None
    return delta


def _decode_ui_answer(data: str) -> str | None:
    payload_raw = data.strip()
    if not payload_raw:
        return None
    try:
        payload = json.loads(payload_raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    answer = payload.get("answer")
    if isinstance(answer, str) and answer.strip() and not _is_control_or_service_text(answer):
        return answer
    return None


def _bounded_excerpt(text: str | None, limit: int = ANSWER_EXCERPT_MAX) -> str | None:
    if not text:
        return None
    return text[:limit]


def measure_patient_visible_timing_from_events(
    events: list[SseEvent],
    *,
    request_started_monotonic: float,
    completed_monotonic: float,
    streaming_measurement: bool = True,
) -> PatientVisibleTiming:
    total_ms = max(0, int((completed_monotonic - request_started_monotonic) * 1000))
    first_kind: PatientTextKind = "none"
    first_event_type: FirstVisibleEventType = "none"
    first_excerpt: str | None = None
    first_visible_at: float | None = None
    widget_ready = any(evt.event == "done" for evt in events) and any(
        evt.event == "ui" for evt in events
    )

    for evt in events:
        if evt.event in {"status", "typing"}:
            continue
        if evt.event == "text_delta":
            delta = _decode_text_delta_payload(evt.data)
            if delta is None:
                continue
            first_kind = "text_delta"
            first_event_type = "text_delta"
            first_excerpt = delta[:64]
            first_visible_at = evt.arrival_monotonic
            break
        if evt.event == "ui":
            answer = _decode_ui_answer(evt.data)
            if answer is None:
                continue
            first_kind = "ui_answer"
            first_event_type = "ui"
            first_excerpt = answer[:64]
            first_visible_at = evt.arrival_monotonic
            break

    patient_ttft_ms: int | None = None
    ttft_measurement_valid = streaming_measurement
    if first_visible_at is not None and streaming_measurement:
        patient_ttft_ms = max(
            0,
            int((first_visible_at - request_started_monotonic) * 1000),
        )
    elif not streaming_measurement:
        ttft_measurement_valid = False

    return PatientVisibleTiming(
        patient_ttft_ms=patient_ttft_ms,
        total_ms=total_ms,
        patient_text_kind=first_kind,
        widget_payload_ready=widget_ready,
        first_visible_excerpt=first_excerpt,
        first_visible_event_type=first_event_type,
        ttft_measurement_valid=ttft_measurement_valid,
        sse_event_count=len(events),
    )


def measure_streaming_patient_timing(
    chunks: Iterable[str],
    *,
    request_started_monotonic: float,
    chunk_arrival_monotonic: Iterable[float] | None = None,
    monotonic_clock: MonotonicClock = time.monotonic,
    completed_monotonic: float | None = None,
) -> PatientVisibleTiming:
    decoder = IncrementalSseDecoder()
    events: list[SseEvent] = []
    arrivals = list(chunk_arrival_monotonic or [])
    for index, chunk in enumerate(chunks):
        arrival = arrivals[index] if index < len(arrivals) else monotonic_clock()
        events.extend(decoder.feed(chunk, arrival))
    completed = completed_monotonic if completed_monotonic is not None else (
        arrivals[-1] if arrivals else monotonic_clock()
    )
    return measure_patient_visible_timing_from_events(
        events,
        request_started_monotonic=request_started_monotonic,
        completed_monotonic=completed,
        streaming_measurement=True,
    )


def measure_patient_visible_timing(
    *,
    stream_text: str,
    request_started_monotonic: float,
    first_visible_monotonic: float | None = None,
    completed_monotonic: float | None = None,
) -> PatientVisibleTiming:
    """Parse a complete SSE body without post-hoc timing reconstruction."""

    completed = completed_monotonic or time.monotonic()
    decoder = IncrementalSseDecoder()
    events = decoder.feed(stream_text, request_started_monotonic)
    timing = measure_patient_visible_timing_from_events(
        events,
        request_started_monotonic=request_started_monotonic,
        completed_monotonic=completed,
        streaming_measurement=False,
    )
    if first_visible_monotonic is not None and timing.first_visible_event_type != "none":
        patient_ttft_ms = max(
            0,
            int((first_visible_monotonic - request_started_monotonic) * 1000),
        )
        return PatientVisibleTiming(
            patient_ttft_ms=patient_ttft_ms,
            total_ms=timing.total_ms,
            patient_text_kind=timing.patient_text_kind,
            widget_payload_ready=timing.widget_payload_ready,
            first_visible_excerpt=timing.first_visible_excerpt,
            first_visible_event_type=timing.first_visible_event_type,
            ttft_measurement_valid=True,
            sse_event_count=timing.sse_event_count,
        )
    return timing


def _extract_ui_payload(stream_text: str) -> dict[str, object] | None:
    decoder = IncrementalSseDecoder()
    events = decoder.feed(stream_text, 0.0)
    for evt in events:
        if evt.event != "ui":
            continue
        payload_raw = evt.data.strip()
        if not payload_raw:
            continue
        try:
            parsed = json.loads(payload_raw)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def execute_stream_turn(
    client: Any,
    *,
    sid: str,
    client_id: str,
    body: dict[str, object],
    monotonic_clock: MonotonicClock = time.monotonic,
) -> dict[str, object]:
    started = monotonic_clock()
    response = client.post(
        "/ask/stream",
        json={**body, "sid": sid, "client_id": client_id},
        buffered=False,
    )
    decoder = IncrementalSseDecoder()
    events: list[SseEvent] = []
    for chunk in response.response:
        text = chunk.decode("utf-8") if isinstance(chunk, bytes) else str(chunk)
        arrival = monotonic_clock()
        events.extend(decoder.feed(text, arrival))
    completed = monotonic_clock()
    stream_text = "".join(
        f"event: {evt.event}\ndata: {evt.data}\n\n" for evt in events
    )
    timing = measure_patient_visible_timing_from_events(
        events,
        request_started_monotonic=started,
        completed_monotonic=completed,
        streaming_measurement=True,
    )
    ui_payload = _extract_ui_payload(stream_text)
    answer_text = str((ui_payload or {}).get("answer") or "")
    return {
        "status_code": response.status_code,
        "stream_text": stream_text,
        "ui_payload": ui_payload,
        "answer_text": answer_text,
        "answer_excerpt": _bounded_excerpt(answer_text),
        "meta": (ui_payload or {}).get("meta") if isinstance((ui_payload or {}).get("meta"), dict) else {},
        "patient_ttft_ms": timing.patient_ttft_ms,
        "total_ms": timing.total_ms,
        "patient_text_kind": timing.patient_text_kind,
        "widget_payload_ready": timing.widget_payload_ready,
        "first_visible_excerpt": timing.first_visible_excerpt,
        "first_visible_event_type": timing.first_visible_event_type,
        "ttft_measurement_valid": timing.ttft_measurement_valid,
        "sse_event_count": timing.sse_event_count,
    }
