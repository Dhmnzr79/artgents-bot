"""Offline replay of frozen Stage 3C v2 LIVE artifact."""

from __future__ import annotations

import json
from pathlib import Path

from evals.v5.one_call_stage3c_speed_gate_harness import replay_speed_gate_interpretation

_REPO = Path(__file__).resolve().parents[1]
_V2_RESULT = (
    _REPO / "evals/v5/artifacts/one_call_stage3c_speed_gate_v2_2026-08-11-01/result.json"
)


def test_v2_artifact_replay_latency_passes_absolute_gate() -> None:
    result = json.loads(_V2_RESULT.read_text(encoding="utf-8"))
    replay = replay_speed_gate_interpretation(result)
    corrected = replay["corrected_speed_gate"]
    assert corrected["checks"]["new_total_p50_pass"]
    assert corrected["checks"]["new_case_total_pass"]
    assert corrected["checks"]["new_ttft_p95_pass"]


def test_v2_artifact_replay_s04_quality_passes_after_scorer_fix() -> None:
    result = json.loads(_V2_RESULT.read_text(encoding="utf-8"))
    replay = replay_speed_gate_interpretation(result)
    s04 = replay["corrected_quality_by_case"]["s04_both_jaws"]
    assert s04["pass"]
    assert not any(item.startswith("forbidden_term:итого") for item in s04["critical_failures"])


def test_v2_artifact_replay_s03_still_documents_historical_defect() -> None:
    result = json.loads(_V2_RESULT.read_text(encoding="utf-8"))
    replay = replay_speed_gate_interpretation(result)
    s03 = replay["corrected_quality_by_case"]["s03_exact_price"]
    assert not s03["pass"]
    assert any("missing_critical:76" in item for item in s03["critical_failures"])
