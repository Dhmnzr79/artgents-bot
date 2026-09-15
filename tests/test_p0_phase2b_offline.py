"""Offline contract tests for P0 Phase 2B streaming measurement harness."""

from __future__ import annotations

import json

from evals.v5.p0_phase2b_contract import (
    CANDIDATE_MODEL_ID,
    CONTROL_MODEL_ID,
    MAX_LIVE_PROVIDER_CALLS,
    assert_call_plan_within_budget,
    build_call_plan,
)
from evals.v5.p0_phase2b_stream_probe import PatientTextStreamProbe
def _answer_envelope(patient_text: str) -> str:
    return (
        '{"route":"ANSWER","patient_text":'
        + json.dumps(patient_text, ensure_ascii=False)
        + ',"commercial_intent":"general","clarify_axis":null,"clarify_service_options":null,'
        '"references":{"used_doc_ids":[],"follow_up_doc_ids":[]}}'
    )


def test_call_plan_within_budget() -> None:
    plan = build_call_plan(include_canary=True, repeat_pass=True)
    assert len(plan) <= MAX_LIVE_PROVIDER_CALLS
    assert_call_plan_within_budget(plan)
    models = {row[0] for row in plan}
    assert models == {CONTROL_MODEL_ID, CANDIDATE_MODEL_ID}


def test_probe_detects_patient_text_chunks() -> None:
    payload = _answer_envelope("Первый фрагмент и второй фрагмент ответа")
    mid = len(payload) // 3
    probe = PatientTextStreamProbe()
    probe.feed(payload[:mid], 0.1)
    probe.feed(payload[mid : mid * 2], 0.2)
    probe.feed(payload[mid * 2 :], 0.35)
    assert probe.patient_text_value_start_at == 0.1 or probe.patient_text_value_start_at == 0.2
    assert probe.streamed_patient_text == "Первый фрагмент и второй фрагмент ответа"
    assert probe.patient_text_chunk_count >= 2
    assert probe.two_plus_value_chunks


def test_probe_matches_envelope_across_splits() -> None:
    text = 'Ответ с "кавычками" и символом'
    payload = _answer_envelope(text)
    for split in (1, 5, 17, len(payload) - 1):
        probe = PatientTextStreamProbe()
        probe.feed(payload[:split], 0.0)
        probe.feed(payload[split:], 0.05)
        assert probe.streamed_patient_text == text


def test_models_are_distinct_snapshots() -> None:
    assert CONTROL_MODEL_ID != CANDIDATE_MODEL_ID
    assert "qwen3.8" in CANDIDATE_MODEL_ID
