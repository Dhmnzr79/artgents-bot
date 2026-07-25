"""Offline tests for A9R2b patient-scope planner live harness (no LLM)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from contracts.planner_attempt import PlannerAttempt
from core.turn_frame_from_raw import build_turn_frame_from_raw
from core.turn_planner_llm import _PATIENT_SCOPE_PROMPT
from evals.v5 import a9r2_patient_scope_live_contract as a9r2_contract
from evals.v5 import a9r2b_patient_scope_live_contract as contract
from evals.v5.a9r2_patient_scope_live_harness import prepare_live_run, run_planner_harness
from evals.v5.a9r2_patient_scope_live_scoring import (
    evaluate_proposed_gates,
    is_scope_scoring_transport_error,
    patient_scope_axes_strict_valid,
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
from tests.test_patient_scope_a9r_matrix_v2_contract import test_a9r_v2_matrix_blob_frozen

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
        frame = _frame_from_scope(scope["patient_scope"], topic=scope.get("topic", "implantation"))
        return PlannerAttempt(frame=frame, status="ok")

    return _planner


@pytest.fixture
def artifact_paths(tmp_path: Path) -> dict[str, Path]:
    prefix = "a9r2b_patient_scope_live"
    return {
        "attempt_marker": tmp_path / f"{prefix}_attempt.json",
        "call_ledger": tmp_path / f"{prefix}_call_ledger.jsonl",
        "raw": tmp_path / f"{prefix}_raw.json",
        "result": tmp_path / f"{prefix}_result.json",
        "manifest": tmp_path / f"{prefix}_manifest.json",
        "manual_review": tmp_path / f"{prefix}_manual_review.json",
    }


def test_live_case_and_call_budget() -> None:
    matrix = contract.load_frozen_matrix_v3()
    calls = contract.iter_live_planner_calls(matrix)
    assert len({call["case_id"] for call in calls}) == 16
    assert len(calls) == contract.MAX_PLANNER_CALLS == 17


def test_stage_02_v3_expects_one_tooth_extent() -> None:
    matrix = contract.load_frozen_matrix_v3()
    call = next(
        call for call in contract.iter_live_planner_calls(matrix)
        if call["case_id"] == "a9r_stage_02_natural_tooth_present"
    )
    assert call["expected_scope"]["extent"] == "one_tooth"
    assert call["expected_scope"]["stage"] == "natural_tooth_present"


def test_calibrated_prompt_present_in_planner_backend() -> None:
    for snippet in (
        "названия услуги или протокола",
        "All-on-4",
        "natural_tooth_present",
        "missing teeth",
    ):
        assert snippet in _PATIENT_SCOPE_PROMPT


def test_partial_valid_patient_scope_not_transport() -> None:
    frame = build_turn_frame_from_raw(
        {
            "route": "content",
            "aspects": ["overview"],
            "topic": None,
            "topic_confidence": 0.0,
            "patient_scope": {
                "extent": "unknown",
                "jaw": "unknown",
                "stage": "unknown",
                "modifiers": [],
            },
        },
        allowed_topics=_ALLOWED_TOPICS,
        allowed_service_ids=_ALLOWED_SERVICES,
    )
    assert patient_scope_axes_strict_valid(frame)
    assert is_scope_scoring_transport_error(planner_status="partial", frame=frame) is False


def test_no_service_name_inference_all_on_4() -> None:
    matrix = contract.load_frozen_matrix_v3()
    call = next(
        call for call in contract.iter_live_planner_calls(matrix)
        if call["case_id"] == "a9r_negative_02_all_on_4_price"
    )
    frame = _frame_from_scope(
        {"extent": "unknown", "jaw": "unknown", "stage": "unknown", "modifiers": []},
        topic=call["topic"],
    )
    score = score_planner_call(frame=frame, planner_status="ok", call_spec=call)
    assert score["composite_turn_exact"] is True
    assert score["material_false_positive_axis_count"] == 0


def test_explicit_implant_placed_stage_extracted() -> None:
    matrix = contract.load_frozen_matrix_v3()
    call = next(
        call for call in contract.iter_live_planner_calls(matrix)
        if call["case_id"] == "a9r_stage_01_implant_placed"
    )
    frame = _frame_from_scope(
        {"extent": "unknown", "jaw": "unknown", "stage": "implant_placed", "modifiers": []},
        topic="prosthetics",
    )
    score = score_planner_call(frame=frame, planner_status="ok", call_spec=call)
    assert score["axis_outcomes"]["stage"] == "correct_expected_axis"


def test_ambiguous_conflict_stays_unknown() -> None:
    matrix = contract.load_frozen_matrix_v3()
    call = next(
        call for call in contract.iter_live_planner_calls(matrix)
        if call["case_id"] == "a9r_ambiguous_01_contradictory_extent"
    )
    frame = _frame_from_scope(
        {"extent": "unknown", "jaw": "unknown", "stage": "unknown", "modifiers": []}
    )
    score = score_planner_call(frame=frame, planner_status="partial", call_spec=call)
    assert score["composite_turn_exact"] is True


def test_material_fp_gate_structure() -> None:
    summary = {
        "wrong_non_unknown_axis_count": 0,
        "material_false_positive_axis_count": 0,
        "correction_success_rate": 1.0,
        "positive_axis_recall": 0.9,
        "composite_exact_turn_rate": 0.9,
        "malformed_projection_count": 0,
        "transport_provider_error_count": 0,
        "planner_calls": 17,
        "retry_count": 0,
    }
    gates = evaluate_proposed_gates(summary, gates=contract.PROPOSED_GATES)
    assert gates["all_passed"] is True


def test_harness_offline_perfect_run_writes_artifacts(artifact_paths: dict[str, Path]) -> None:
    matrix = contract.load_frozen_matrix_v3()
    responses: dict[str, dict] = {}
    for call in contract.iter_live_planner_calls(matrix):
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
        contract=contract,
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


def test_attempt_marker_blocks_second_run(artifact_paths: dict[str, Path]) -> None:
    matrix = contract.load_frozen_matrix_v3()
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
        for call in contract.iter_live_planner_calls(matrix)
    }
    kwargs = {
        "planner_fn": _fake_planner_factory(responses),
        "contract": contract,
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


def test_cli_dry_run() -> None:
    from evals.v5.run_a9r2b_patient_scope_live import main

    assert main(["--dry-run"]) == 0


def test_attempt_marker_before_provider_call(artifact_paths: dict[str, Path]) -> None:
    prepare_live_run(
        contract=contract,
        attempt_marker_path=artifact_paths["attempt_marker"],
        call_ledger_path=artifact_paths["call_ledger"],
        raw_path=artifact_paths["raw"],
        result_path=artifact_paths["result"],
        manifest_path=artifact_paths["manifest"],
        manual_review_path=artifact_paths["manual_review"],
    )
    marker = contract.load_attempt_marker(artifact_paths["attempt_marker"])
    assert marker["provider_calls_started"] == 0
    assert marker["abort_blocks_retry_without_owner_approval"] is True


def test_frozen_neighbor_artifacts_unchanged() -> None:
    test_a9r_v2_matrix_blob_frozen()
    a9r2_contract.assert_frozen_a9r2_live_artifacts_unchanged()
    _a9_shadow_blobs_unchanged()
    test_w1b_snapshot_checksums_unchanged()
