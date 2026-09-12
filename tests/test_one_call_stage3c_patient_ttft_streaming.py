"""Deterministic streaming patient TTFT tests (Stage 3C v2)."""

from __future__ import annotations

import json

import pytest

from evals.v5.one_call_stage3c_speed_gate_patient_ttft import (
    IncrementalSseDecoder,
    measure_patient_visible_timing,
    measure_patient_visible_timing_from_events,
    measure_streaming_patient_timing,
    SseEvent,
)


def test_status_then_delayed_text_delta_ttft_matches_delay() -> None:
    chunks = [
        "event: status\ndata: {\"message\":\"…\"}\n\n",
        "event: typing\ndata: {\"phase\":\"writing\"}\n\n",
    ]
    arrivals = [0.0, 0.05]
    chunks.append(f"event: text_delta\ndata: {json.dumps({'delta': 'Видимый'})}\n\n")
    arrivals.append(0.25)
    timing = measure_streaming_patient_timing(
        chunks,
        request_started_monotonic=0.0,
        chunk_arrival_monotonic=arrivals,
        completed_monotonic=0.5,
    )
    assert timing.ttft_measurement_valid
    assert timing.patient_ttft_ms == 250
    assert timing.patient_text_kind == "text_delta"


def test_text_delta_json_delta_extracted_not_envelope() -> None:
    payload = json.dumps({"delta": "Видимый текст"})
    stream = (
        "event: status\ndata: {}\n\n"
        f"event: text_delta\ndata: {payload}\n\n"
        "event: done\ndata: {}\n\n"
    )
    timing = measure_patient_visible_timing(
        stream_text=stream,
        request_started_monotonic=0.0,
        first_visible_monotonic=0.12,
        completed_monotonic=0.4,
    )
    assert timing.patient_text_kind == "text_delta"
    assert timing.first_visible_excerpt == "Видимый текст"[:64]
    assert timing.patient_ttft_ms == 120


def test_control_marker_delta_excluded() -> None:
    stream = (
        f"event: text_delta\ndata: {json.dumps({'delta': '@ANSWER'})}\n\n"
        f"event: text_delta\ndata: {json.dumps({'delta': 'Пациентский текст'})}\n\n"
    )
    timing = measure_patient_visible_timing(
        stream_text=stream,
        request_started_monotonic=0.0,
        first_visible_monotonic=0.2,
        completed_monotonic=0.3,
    )
    assert timing.patient_text_kind == "text_delta"
    assert timing.first_visible_excerpt == "Пациентский текст"[:64]


def test_sse_event_split_across_chunks() -> None:
    part1 = "event: text_delta\ndata: "
    part2 = json.dumps({"delta": "Разбитый"}) + "\n\n"
    timing = measure_streaming_patient_timing(
        [part1, part2],
        request_started_monotonic=0.0,
        chunk_arrival_monotonic=[0.1, 0.35],
        completed_monotonic=0.5,
    )
    assert timing.patient_ttft_ms == 350
    assert timing.patient_text_kind == "text_delta"


def test_multiple_events_in_one_chunk() -> None:
    chunk = (
        f"event: text_delta\ndata: {json.dumps({'delta': 'Первый'})}\n\n"
        f"event: text_delta\ndata: {json.dumps({'delta': 'Второй'})}\n\n"
    )
    timing = measure_streaming_patient_timing(
        [chunk],
        request_started_monotonic=0.0,
        chunk_arrival_monotonic=[0.18],
        completed_monotonic=0.4,
    )
    assert timing.patient_ttft_ms == 180
    assert timing.first_visible_excerpt == "Первый"[:64]


def test_ui_only_answer_ttft_near_total() -> None:
    ui_payload = json.dumps({"answer": "Ответ пациенту"})
    timing = measure_streaming_patient_timing(
        ["event: ui\ndata: " + ui_payload + "\n\nevent: done\ndata: {}\n\n"],
        request_started_monotonic=0.0,
        chunk_arrival_monotonic=[0.42],
        completed_monotonic=0.42,
    )
    assert timing.patient_text_kind == "ui_answer"
    assert timing.first_visible_event_type == "ui"
    assert timing.patient_ttft_ms == 420
    assert timing.total_ms == 420


def test_no_visible_text_ttft_null_invalid() -> None:
    timing = measure_streaming_patient_timing(
        ["event: status\ndata: {}\n\n", "event: done\ndata: {}\n\n"],
        request_started_monotonic=0.0,
        chunk_arrival_monotonic=[0.05, 0.2],
        completed_monotonic=0.2,
    )
    assert timing.patient_ttft_ms is None
    assert timing.patient_text_kind == "none"
    assert timing.ttft_measurement_valid


def test_buffered_static_parse_without_timestamps_invalid_ttft() -> None:
    stream = f"event: text_delta\ndata: {json.dumps({'delta': 'Текст'})}\n\n"
    timing = measure_patient_visible_timing(
        stream_text=stream,
        request_started_monotonic=0.0,
        completed_monotonic=1.0,
    )
    assert timing.patient_ttft_ms is None
    assert not timing.ttft_measurement_valid


def test_ui_ignored_after_text_delta() -> None:
    events = [
        SseEvent(
            event="text_delta",
            data=json.dumps({"delta": "Дельта"}),
            arrival_monotonic=0.15,
        ),
        SseEvent(
            event="ui",
            data=json.dumps({"answer": "Дельта полный"}),
            arrival_monotonic=0.4,
        ),
    ]
    timing = measure_patient_visible_timing_from_events(
        events,
        request_started_monotonic=0.0,
        completed_monotonic=0.5,
        streaming_measurement=True,
    )
    assert timing.patient_ttft_ms == 150
    assert timing.first_visible_event_type == "text_delta"


def test_incremental_decoder_preserves_partial_line() -> None:
    decoder = IncrementalSseDecoder()
    first = decoder.feed("event: text_", 0.1)
    assert first == []
    second = decoder.feed("delta\ndata: {}\n\n", 0.2)
    assert len(second) == 1
    assert second[0].event == "text_delta"
