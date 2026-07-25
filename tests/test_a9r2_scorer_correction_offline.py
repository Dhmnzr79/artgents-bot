"""Offline tests for A9R2 post-live scorer correction (Checkpoint A)."""

from __future__ import annotations

import json

import pytest

from contracts.turn_frame import TurnFrame
from core.turn_frame_from_raw import build_turn_frame_from_raw
from evals.v5.a9r2_patient_scope_live_contract import (
    FROZEN_A9R2_LIVE_ARTIFACT_SHA256,
    LIVE_RAW_ARTIFACT_PATH,
    LIVE_RESULT_ARTIFACT_PATH,
    OFFICIAL_A9R2_LIVE_VERDICT,
    OFFICIAL_A9R2_STATUS,
    assert_frozen_a9r2_live_artifacts_unchanged,
    iter_live_planner_calls,
    load_frozen_matrix_v2,
    sha256_file_hex,
)
from evals.v5.a9r2_patient_scope_live_diagnostic_recompute import (
    recompute_frozen_a9r2_live_diagnostic,
    write_diagnostic_recompute_artifact,
)
from evals.v5.a9r2_patient_scope_live_scoring import (
    is_scope_scoring_transport_error,
    patient_scope_axes_strict_valid,
    score_planner_call,
)

_ALLOWED_TOPICS = frozenset({"implantation", "prosthetics"})
_ALLOWED_SERVICES = frozenset({"all_on_4", "classic"})


def _frame_from_raw(raw_turn_plan: dict) -> TurnFrame:
    return TurnFrame.model_validate(raw_turn_plan)


def test_frozen_live_artifact_sha256_pins() -> None:
    assert_frozen_a9r2_live_artifacts_unchanged()
    for name, expected in FROZEN_A9R2_LIVE_ARTIFACT_SHA256.items():
        path = LIVE_RAW_ARTIFACT_PATH.parent / name
        assert sha256_file_hex(path) == expected


def test_partial_with_invalid_topic_is_not_transport_error() -> None:
    raw = json.loads(LIVE_RAW_ARTIFACT_PATH.read_text(encoding="utf-8"))
    entry = next(
        row for row in raw["calls"]
        if row["call_id"] == "a9r_ambiguous_01_contradictory_extent"
    )
    frame = _frame_from_raw(entry["raw_turn_plan"])
    assert patient_scope_axes_strict_valid(frame)
    assert is_scope_scoring_transport_error(planner_status="partial", frame=frame) is False


def test_partial_correction_turn2_is_not_transport_and_scores_exact() -> None:
    raw = json.loads(LIVE_RAW_ARTIFACT_PATH.read_text(encoding="utf-8"))
    matrix = load_frozen_matrix_v2()
    call_spec = next(
        call for call in iter_live_planner_calls(matrix)
        if call["call_id"].endswith(":turn2")
    )
    entry = next(
        row for row in raw["calls"]
        if row["call_id"] == call_spec["call_id"]
    )
    frame = _frame_from_raw(entry["raw_turn_plan"])
    score = score_planner_call(
        frame=frame,
        planner_status=str(entry["planner_status"]),
        call_spec=call_spec,
        prior_session=None,
        session_turn_count=2,
    )
    assert score["transport_provider_error"] is False
    assert score["composite_turn_exact"] is True
    assert score["correction_success"] is True
    assert score["observed_axes"]["extent"] == "one_tooth"


def test_ambiguous_01_all_unknown_scores_exact() -> None:
    raw = json.loads(LIVE_RAW_ARTIFACT_PATH.read_text(encoding="utf-8"))
    matrix = load_frozen_matrix_v2()
    call_spec = next(
        call for call in iter_live_planner_calls(matrix)
        if call["case_id"] == "a9r_ambiguous_01_contradictory_extent"
    )
    entry = next(
        row for row in raw["calls"]
        if row["call_id"] == call_spec["call_id"]
    )
    frame = _frame_from_raw(entry["raw_turn_plan"])
    score = score_planner_call(
        frame=frame,
        planner_status=str(entry["planner_status"]),
        call_spec=call_spec,
    )
    assert score["transport_provider_error"] is False
    assert score["composite_turn_exact"] is True
    assert score["false_positive_axis_count"] == 0
    assert all(value in (None, "unknown") for value in score["observed_axes"].values())


def test_diagnostic_recompute_preserves_official_fail() -> None:
    official = json.loads(LIVE_RESULT_ARTIFACT_PATH.read_text(encoding="utf-8"))
    payload = recompute_frozen_a9r2_live_diagnostic()
    assert official["automated_verdict"] == OFFICIAL_A9R2_LIVE_VERDICT == "AUTOMATED_FAIL"
    assert payload["official_status"] == OFFICIAL_A9R2_STATUS == "A9R2_NOT_PASSED"
    assert payload["no_retroactive_pass"] is True
    assert payload["diagnostic_automated_verdict"] == "AUTOMATED_FAIL"


def test_diagnostic_recompute_corrected_metrics() -> None:
    payload = recompute_frozen_a9r2_live_diagnostic()
    summary = payload["corrected_summary"]
    assert summary["transport_provider_error_count"] == 0
    assert summary["correction_success_rate"] == 1.0
    assert summary["correction_turns"] == 1
    assert payload["remaining_negative_ambiguous_false_positives"]
    assert len(payload["remaining_negative_ambiguous_false_positives"]) == 3


def test_write_diagnostic_recompute_artifact(tmp_path) -> None:
    out = tmp_path / "diag.json"
    payload = write_diagnostic_recompute_artifact(out)
    assert out.exists()
    assert payload["measurement_id"] == "a9r2_patient_scope_live_diagnostic_recompute"


def test_degraded_status_remains_transport_error() -> None:
    assert is_scope_scoring_transport_error(planner_status="degraded", frame=None) is True


def test_invalid_patient_scope_extent_is_transport_error() -> None:
    frame = build_turn_frame_from_raw(
        {
            "route": "content",
            "aspects": ["price"],
            "topic": "implantation",
            "topic_confidence": 0.9,
            "patient_scope": {
                "extent": "several",
                "jaw": "unknown",
                "stage": "unknown",
                "modifiers": [],
            },
        },
        allowed_topics=_ALLOWED_TOPICS,
        allowed_service_ids=_ALLOWED_SERVICES,
    )
    assert patient_scope_axes_strict_valid(frame) is False
    assert is_scope_scoring_transport_error(planner_status="ok", frame=frame) is True
