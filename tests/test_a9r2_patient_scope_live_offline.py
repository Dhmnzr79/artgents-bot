"""Offline tests for A9R2 patient-scope planner live harness (no LLM)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from contracts.planner_attempt import PlannerAttempt
from core.turn_frame_from_raw import build_turn_frame_from_raw
from evals.v5.a9r2_patient_scope_live_contract import (
    ATTEMPT_MARKER_EXISTS_CODE,
    LIVE_ATTEMPT_MARKER_PATH,
    LIVE_CALL_LEDGER_PATH,
    LIVE_MANIFEST_ARTIFACT_PATH,
    LIVE_MANUAL_REVIEW_ARTIFACT_PATH,
    LIVE_RAW_ARTIFACT_PATH,
    LIVE_RESULT_ARTIFACT_PATH,
    MAX_PLANNER_CALLS,
    assert_matrix_v1_frozen,
    iter_live_planner_calls,
    load_frozen_matrix_v2,
    load_attempt_marker,
)
from evals.v5.a9r2_patient_scope_live_harness import prepare_live_run, run_planner_harness
from evals.v5.a9r2_patient_scope_live_scoring import (
    evaluate_proposed_gates,
    score_axis,
    score_planner_call,
)
from evals.v5.fullcontext_response_eval_contract import (
    AttemptMarkerExistsError,
    HarnessConfigError,
)
from tests.test_a9r1_offline_harness import (
    test_a9_v1_v2_matrix_blobs_unchanged as _a9_shadow_blobs_unchanged,
)
from tests.test_ac3_scope_price_flow_offline import test_w1b_snapshot_checksums_unchanged

_ALLOWED_TOPICS = frozenset({"implantation", "prosthetics"})
_ALLOWED_SERVICES = frozenset({"all_on_4", "classic"})


def _frame_from_scope(scope: dict, *, topic: str = "implantation"):
    return build_turn_frame_from_raw(
        {
            "route": "content",
            "aspects": ["price"],
            "primary_aspect": "price",
            "service_id": None,
            "topic": topic,
            "topic_confidence": 0.9,
            "patient_scope": scope,
        },
        allowed_topics=_ALLOWED_TOPICS,
        allowed_service_ids=_ALLOWED_SERVICES,
    )


def _fake_planner_factory(responses: dict[str, dict]) -> callable:
    def _planner(question: str, sid: str | None, client_id: str | None) -> PlannerAttempt:
        scope = responses.get(question)
        if scope is None:
            return PlannerAttempt(frame=None, status="not_available")
        if scope.get("__transport_error__"):
            return PlannerAttempt(frame=None, status="degraded")
        frame = _frame_from_scope(scope["patient_scope"], topic=scope.get("topic", "implantation"))
        return PlannerAttempt(frame=frame, status="ok")

    return _planner


@pytest.fixture
def artifact_paths(tmp_path: Path) -> dict[str, Path]:
    return {
        "attempt_marker": tmp_path / "attempt.json",
        "call_ledger": tmp_path / "ledger.jsonl",
        "raw": tmp_path / "raw.json",
        "result": tmp_path / "result.json",
        "manifest": tmp_path / "manifest.json",
        "manual_review": tmp_path / "manual_review.json",
    }


def test_live_case_and_call_budget() -> None:
    matrix = load_frozen_matrix_v2()
    calls = iter_live_planner_calls(matrix)
    assert len({call["case_id"] for call in calls}) == 16
    assert len(calls) == MAX_PLANNER_CALLS == 17


def test_scoring_distinguishes_miss_vs_wrong() -> None:
    frame_miss = _frame_from_scope(
        {"extent": "unknown", "jaw": "unknown", "stage": "unknown", "modifiers": []}
    )
    miss = score_planner_call(
        frame=frame_miss,
        planner_status="ok",
        call_spec={
            "expected_scope": {
                "extent": "full_arch",
                "jaw": "unknown",
                "stage": "unknown",
                "modifiers": [],
            },
            "category": "extent_positive",
            "topic": "implantation",
        },
    )
    assert miss["axis_outcomes"]["extent"] == "missing_expected_positive_axis"
    assert miss["wrong_non_unknown_axis_count"] == 0

    frame_wrong = _frame_from_scope(
        {"extent": "one_tooth", "jaw": "unknown", "stage": "unknown", "modifiers": []}
    )
    wrong = score_planner_call(
        frame=frame_wrong,
        planner_status="ok",
        call_spec={
            "expected_scope": {
                "extent": "full_arch",
                "jaw": "unknown",
                "stage": "unknown",
                "modifiers": [],
            },
            "category": "extent_positive",
            "topic": "implantation",
        },
    )
    assert wrong["axis_outcomes"]["extent"] == "wrong_non_unknown_axis"
    assert wrong["wrong_non_unknown_axis_count"] == 1


def test_negative_all_on_4_false_positive_scored(artifact_paths: dict[str, Path]) -> None:
    outcome = score_axis(
        axis="extent",
        expected="unknown",
        observed={"value": "full_arch", "usable": True, "status": "valid"},
        category="no_scope_from_service",
    )
    assert outcome == "false_positive_axis"


def test_scalar_bridge_not_usable_in_live_projection() -> None:
    frame = build_turn_frame_from_raw(
        {
            "route": "content",
            "aspects": ["price"],
            "patient_situation": "one_tooth_missing",
            "topic": "implantation",
            "topic_confidence": 0.9,
        },
        allowed_topics=_ALLOWED_TOPICS,
        allowed_service_ids=_ALLOWED_SERVICES,
    )
    score = score_planner_call(
        frame=frame,
        planner_status="ok",
        call_spec={
            "expected_scope": {
                "extent": "unknown",
                "jaw": "unknown",
                "stage": "unknown",
                "modifiers": [],
            },
            "category": "ambiguous",
            "topic": "implantation",
        },
    )
    assert score["projected_usable"]["extent"] is False


def test_harness_offline_perfect_run_writes_artifacts(artifact_paths: dict[str, Path]) -> None:
    matrix = load_frozen_matrix_v2()
    responses: dict[str, dict] = {}
    for call in iter_live_planner_calls(matrix):
        responses[call["question"]] = {
            "topic": call["topic"],
            "patient_scope": {
                "extent": call["expected_scope"].get("extent", "unknown"),
                "jaw": call["expected_scope"].get("jaw", "unknown"),
                "stage": call["expected_scope"].get("stage", "unknown"),
                "modifiers": list(call["expected_scope"].get("modifiers") or []),
            },
        }

    payload = run_planner_harness(
        planner_fn=_fake_planner_factory(responses),
        attempt_marker_path=artifact_paths["attempt_marker"],
        call_ledger_path=artifact_paths["call_ledger"],
        raw_path=artifact_paths["raw"],
        result_path=artifact_paths["result"],
        manifest_path=artifact_paths["manifest"],
        manual_review_path=artifact_paths["manual_review"],
    )
    assert payload["automated_verdict"] == "AUTOMATED_PASS"
    assert payload["final_verdict"] == "PENDING_MANUAL_REVIEW"
    result = json.loads(artifact_paths["result"].read_text(encoding="utf-8"))
    assert result["authority_enabled"] is False
    assert all(path.exists() for path in artifact_paths.values())


def test_attempt_marker_blocks_second_run_without_override(artifact_paths: dict[str, Path]) -> None:
    matrix = load_frozen_matrix_v2()
    responses = {
        call["question"]: {
            "topic": call["topic"],
            "patient_scope": {
                "extent": "unknown",
                "jaw": "unknown",
                "stage": "unknown",
                "modifiers": [],
            },
        }
        for call in iter_live_planner_calls(matrix)
    }
    kwargs = {
        "planner_fn": _fake_planner_factory(responses),
        **{f"{key}_path": artifact_paths[key] for key in (
            "attempt_marker",
            "call_ledger",
            "raw",
            "result",
            "manifest",
            "manual_review",
        )},
    }
    run_planner_harness(**kwargs)
    with pytest.raises((AttemptMarkerExistsError, HarnessConfigError)):
        run_planner_harness(**kwargs)


def test_cli_live_entrypoint_exists() -> None:
    from evals.v5.run_a9r2_patient_scope_live import main

    assert callable(main)


def test_correction_and_natural_tooth_present_in_fake_run(artifact_paths: dict[str, Path]) -> None:
    matrix = load_frozen_matrix_v2()
    responses: dict[str, dict] = {}
    for call in iter_live_planner_calls(matrix):
        responses[call["question"]] = {
            "topic": call["topic"],
            "patient_scope": {
                "extent": call["expected_scope"].get("extent", "unknown"),
                "jaw": call["expected_scope"].get("jaw", "unknown"),
                "stage": call["expected_scope"].get("stage", "unknown"),
                "modifiers": list(call["expected_scope"].get("modifiers") or []),
            },
        }
    payload = run_planner_harness(
        planner_fn=_fake_planner_factory(responses),
        attempt_marker_path=artifact_paths["attempt_marker"],
        call_ledger_path=artifact_paths["call_ledger"],
        raw_path=artifact_paths["raw"],
        result_path=artifact_paths["result"],
        manifest_path=artifact_paths["manifest"],
        manual_review_path=artifact_paths["manual_review"],
    )
    result = json.loads(artifact_paths["result"].read_text(encoding="utf-8"))
    correction_rows = [
        row for row in result["call_results"] if "correction" in row["case_id"]
    ]
    assert correction_rows
    assert payload["summary"]["correction_success_rate"] == 1.0
    stage_row = next(
        row for row in result["call_results"]
        if row["case_id"] == "a9r_stage_02_natural_tooth_present"
    )
    assert stage_row["score"]["merged_stage"] == "natural_tooth_present"


def test_proposed_gates_structure() -> None:
    summary = {
        "wrong_non_unknown_axis_count": 0,
        "false_positive_axis_count": 0,
        "correction_success_rate": 1.0,
        "positive_axis_recall": 0.9,
        "composite_exact_turn_rate": 0.9,
        "malformed_projection_count": 0,
        "transport_provider_error_count": 0,
        "planner_calls": 17,
        "retry_count": 0,
    }
    gates = evaluate_proposed_gates(summary)
    assert gates["all_passed"] is True


def test_frozen_neighbor_artifacts_unchanged() -> None:
    assert_matrix_v1_frozen()
    _a9_shadow_blobs_unchanged()
    test_w1b_snapshot_checksums_unchanged()


def test_cli_dry_run() -> None:
    from evals.v5.run_a9r2_patient_scope_live import main

    assert main(["--dry-run"]) == 0


def test_attempt_marker_records_started_calls(artifact_paths: dict[str, Path]) -> None:
    prepare_live_run(attempt_marker_path=artifact_paths["attempt_marker"])
    marker = load_attempt_marker(artifact_paths["attempt_marker"])
    assert marker["provider_calls_started"] == 0
    assert marker["abort_blocks_retry_without_owner_approval"] is True
