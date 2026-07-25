"""Offline tests for A9R2c patient-scope planner live harness (no LLM)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from contracts.planner_attempt import PlannerAttempt
from core.turn_frame_from_raw import build_turn_frame_from_raw
from evals.v5 import a9r2b_patient_scope_live_contract as a9r2b_contract
from evals.v5 import a9r2c_patient_scope_live_contract as contract
from evals.v5.a9r2_patient_scope_live_contract import assert_frozen_a9r2_live_artifacts_unchanged
from evals.v5.a9r2_patient_scope_live_harness import prepare_live_run, run_planner_harness
from evals.v5.a9r2_patient_scope_live_scoring import evaluate_proposed_gates

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
    prefix = "a9r2c_patient_scope_live"
    return {
        "attempt_marker": tmp_path / f"{prefix}_attempt.json",
        "call_ledger": tmp_path / f"{prefix}_call_ledger.jsonl",
        "raw": tmp_path / f"{prefix}_raw.json",
        "result": tmp_path / f"{prefix}_result.json",
        "manifest": tmp_path / f"{prefix}_manifest.json",
        "manual_review": tmp_path / f"{prefix}_manual_review.json",
    }


def test_live_case_budget_and_model() -> None:
    matrix = contract.load_frozen_matrix_v3()
    calls = contract.iter_live_planner_calls(matrix)
    assert len({call["case_id"] for call in calls}) == 16
    assert len(calls) == 17
    assert contract.OWNER_APPROVED_PLANNER_MODEL == "qwen3.7-plus"


def test_true_composite_gate_structure() -> None:
    summary = {
        "wrong_non_unknown_axis_count": 0,
        "material_false_positive_axis_count": 0,
        "correction_success_rate": 1.0,
        "positive_axis_recall": 0.9,
        "true_composite_exact_turn_rate": 0.9,
        "malformed_projection_count": 0,
        "transport_provider_error_count": 0,
        "planner_calls": 17,
        "retry_count": 0,
    }
    gates = evaluate_proposed_gates(summary, gates=contract.PROPOSED_GATES)
    assert gates["all_passed"] is True
    assert "true_composite_exact_turn_rate" in gates


def test_harness_offline_perfect_run_writes_artifacts(artifact_paths: dict[str, Path]) -> None:
    matrix = contract.load_frozen_matrix_v3()
    responses = {
        call["question"]: {
            "topic": call["topic"],
            "patient_scope": {
                "extent": call["expected_scope"].get("extent", "unknown"),
                "jaw": call["expected_scope"].get("jaw", "unknown"),
                "stage": call["expected_scope"].get("stage", "unknown"),
                "modifiers": list(call["expected_scope"].get("modifiers") or []),
            },
        }
        for call in contract.iter_live_planner_calls(matrix)
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
    result = json.loads(artifact_paths["result"].read_text(encoding="utf-8"))
    assert result["summary"]["true_composite_exact_turn_rate"] == 1.0
    assert result["summary"]["composite_eligible_turns"] == 17


def test_cli_dry_run() -> None:
    from evals.v5.run_a9r2c_patient_scope_live import main

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
    assert marker["planner_model"] == "qwen3.7-plus"


def test_frozen_prior_live_artifacts_unchanged() -> None:
    assert_frozen_a9r2_live_artifacts_unchanged()
    a9r2b_contract.assert_frozen_a9r2b_live_artifacts_unchanged()
