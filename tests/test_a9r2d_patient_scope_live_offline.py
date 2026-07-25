"""Offline tests for A9R2d patient-scope planner live harness (no LLM)."""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path

import pytest

from contracts.planner_attempt import PlannerAttempt
from core.turn_frame_from_raw import build_turn_frame_from_raw
from evals.v5 import a9r2b_patient_scope_live_contract as a9r2b_contract
from evals.v5 import a9r2c_patient_scope_live_contract as a9r2c_contract
from evals.v5 import a9r2d_patient_scope_live_contract as contract
from evals.v5.a9r2_patient_scope_live_contract import assert_frozen_a9r2_live_artifacts_unchanged
from evals.v5.a9r2_patient_scope_live_harness import prepare_live_run, run_planner_harness
from evals.v5.fullcontext_response_eval_contract import HarnessConfigError
from evals.v5.patient_scope_live_model_pin import PROVIDER_MODEL_MISMATCH_CODE
from tests.test_a9r1_offline_harness import (
    test_a9_v1_v2_matrix_blobs_unchanged as _a9_shadow_blobs_unchanged,
)
from tests.test_ac3_scope_price_flow_offline import test_w1b_snapshot_checksums_unchanged
from tests.test_patient_scope_a9r_matrix_v2_contract import test_a9r_v2_matrix_blob_frozen

_ALLOWED_TOPICS = frozenset({"implantation", "prosthetics"})
_ALLOWED_SERVICES = frozenset({"all_on_4", "classic"})


@pytest.fixture(autouse=True)
def _pin_plus_model_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TURN_PLANNER_LLM_MODEL", "qwen3.7-plus")
    import config

    importlib.reload(config)


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
    prefix = "a9r2d_patient_scope_live"
    return {
        "attempt_marker": tmp_path / f"{prefix}_attempt.json",
        "call_ledger": tmp_path / f"{prefix}_call_ledger.jsonl",
        "raw": tmp_path / f"{prefix}_raw.json",
        "result": tmp_path / f"{prefix}_result.json",
        "manifest": tmp_path / f"{prefix}_manifest.json",
        "manual_review": tmp_path / f"{prefix}_manual_review.json",
    }


def test_namespace_isolated_from_a9r2c() -> None:
    assert contract.MEASUREMENT_ID == "a9r2d_patient_scope_live"
    assert contract.REQUIRES_PLANNER_MODEL_PIN is True
    assert contract.LIVE_ATTEMPT_MARKER_PATH.name.startswith("a9r2d_")
    assert contract.LIVE_ATTEMPT_MARKER_PATH != a9r2c_contract.LIVE_ATTEMPT_MARKER_PATH


def test_attempt_marker_includes_model_provenance(artifact_paths: dict[str, Path]) -> None:
    prepare_live_run(
        contract=contract,
        attempt_marker_path=artifact_paths["attempt_marker"],
        call_ledger_path=artifact_paths["call_ledger"],
        raw_path=artifact_paths["raw"],
        result_path=artifact_paths["result"],
        manifest_path=artifact_paths["manifest"],
        manual_review_path=artifact_paths["manual_review"],
    )
    marker = json.loads(artifact_paths["attempt_marker"].read_text(encoding="utf-8"))
    assert marker["owner_requested_model"] == "qwen3.7-plus"
    assert marker["model_provenance"]["configured_model"] == "qwen3.7-plus"
    assert marker["provider_calls_started"] == 0


def test_harness_writes_model_provenance_not_declared_only(
    artifact_paths: dict[str, Path],
) -> None:
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
    run_planner_harness(
        planner_fn=_fake_planner_factory(responses),
        contract=contract,
        attempt_marker_path=artifact_paths["attempt_marker"],
        call_ledger_path=artifact_paths["call_ledger"],
        raw_path=artifact_paths["raw"],
        result_path=artifact_paths["result"],
        manifest_path=artifact_paths["manifest"],
        manual_review_path=artifact_paths["manual_review"],
    )
    manifest = json.loads(artifact_paths["manifest"].read_text(encoding="utf-8"))
    assert "planner_model" not in manifest
    assert manifest["model_provenance"]["owner_requested_model"] == "qwen3.7-plus"
    assert manifest["model_provenance"]["configured_model"] == "qwen3.7-plus"
    assert manifest["planner_calls"] == 17


def test_model_mismatch_aborts_after_first_observed_response(
    artifact_paths: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    matrix = contract.load_frozen_matrix_v3()
    first_call = contract.iter_live_planner_calls(matrix)[0]

    def _planner(question: str, sid: str | None, client_id: str | None) -> PlannerAttempt:
        scope = {
            "extent": first_call["expected_scope"].get("extent", "unknown"),
            "jaw": first_call["expected_scope"].get("jaw", "unknown"),
            "stage": first_call["expected_scope"].get("stage", "unknown"),
            "modifiers": [],
        }
        return PlannerAttempt(frame=_frame_from_scope(scope, topic=first_call["topic"]), status="ok")

    def _tracking_wrapper(fn, observed_models):
        def wrapped(q: str, sid: str | None, client_id: str | None) -> PlannerAttempt:
            observed_models.append("qwen3.6-flash")
            return fn(q, sid, client_id)

        return wrapped

    monkeypatch.setattr(
        "evals.v5.patient_scope_live_model_pin.make_model_tracked_planner",
        _tracking_wrapper,
    )

    with pytest.raises(HarnessConfigError):
        run_planner_harness(
            planner_fn=_planner,
            contract=contract,
            attempt_marker_path=artifact_paths["attempt_marker"],
            call_ledger_path=artifact_paths["call_ledger"],
            raw_path=artifact_paths["raw"],
            result_path=artifact_paths["result"],
            manifest_path=artifact_paths["manifest"],
            manual_review_path=artifact_paths["manual_review"],
        )

    result = json.loads(artifact_paths["result"].read_text(encoding="utf-8"))
    manifest = json.loads(artifact_paths["manifest"].read_text(encoding="utf-8"))
    assert result["abort_reason"] == PROVIDER_MODEL_MISMATCH_CODE
    assert manifest["abort_reason"] == PROVIDER_MODEL_MISMATCH_CODE
    assert result["summary"]["planner_calls"] == 1
    assert len(json.loads(artifact_paths["raw"].read_text(encoding="utf-8"))["calls"]) == 1


def test_cli_dry_run() -> None:
    from evals.v5.run_a9r2d_patient_scope_live import main

    assert main(["--dry-run"]) == 0


def test_frozen_neighbor_artifacts_unchanged() -> None:
    test_a9r_v2_matrix_blob_frozen()
    assert_frozen_a9r2_live_artifacts_unchanged()
    a9r2b_contract.assert_frozen_a9r2b_live_artifacts_unchanged()
    a9r2c_contract.assert_frozen_a9r2c_live_artifacts_unchanged()
    _a9_shadow_blobs_unchanged()
    test_w1b_snapshot_checksums_unchanged()
