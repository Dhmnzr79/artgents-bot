"""Offline tests for A9R2b post-live composite metric correction."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.v5 import a9r2b_patient_scope_live_contract as contract
from evals.v5.a9r2b_patient_scope_live_diagnostic_recompute import (
    recompute_frozen_a9r2b_live_diagnostic,
    write_diagnostic_recompute_artifact,
)
from evals.v5.a9r2_patient_scope_live_scoring import aggregate_call_results


def test_frozen_a9r2b_official_inflated_composite_preserved() -> None:
    contract.assert_frozen_a9r2b_live_artifacts_unchanged()
    official = json.loads(contract.LIVE_RESULT_ARTIFACT_PATH.read_text(encoding="utf-8"))
    summary = official["summary"]
    assert summary["composite_exact_turns"] == 11
    assert summary["composite_scored_turns"] == 12
    assert summary["composite_exact_turn_rate"] == pytest.approx(11 / 12)
    assert official["automated_verdict"] == contract.OFFICIAL_A9R2B_LIVE_VERDICT


def test_corrected_true_composite_rate_on_frozen_raw() -> None:
    payload = recompute_frozen_a9r2b_live_diagnostic()
    corrected = payload["corrected_summary"]
    assert corrected["composite_exact_turns"] == 11
    assert corrected["composite_eligible_turns"] == 17
    assert payload["corrected_true_composite_exact_turn_rate"] == pytest.approx(11 / 17)
    assert corrected["true_composite_exact_turn_rate"] == pytest.approx(11 / 17)
    assert payload["official_inflated_composite_scored_turns"] == 12
    assert payload["no_retroactive_pass"] is True
    assert payload["official_live_verdict_unchanged"] is True
    assert payload["diagnostic_automated_verdict"] == "AUTOMATED_FAIL"


def test_corrected_per_axis_material_diagnostic() -> None:
    payload = recompute_frozen_a9r2b_live_diagnostic()
    diag = payload["corrected_material_per_axis_diagnostic"]
    assert diag["extent"] == {"correct": 8, "miss": 1, "false_positive": 1, "wrong": 0}
    assert diag["jaw"] == {"correct": 3, "miss": 0, "false_positive": 1, "wrong": 0}
    assert diag["stage"] == {"correct": 2, "miss": 0, "false_positive": 3, "wrong": 0}


def test_composite_denominator_includes_exact_all_unknown_negative_turns() -> None:
    payload = recompute_frozen_a9r2b_live_diagnostic()
    neg_exact = [
        row
        for row in payload["call_results"]
        if row.get("category") in ("no_scope_from_service", "no_stage_inference", "ambiguous")
        and row["score"].get("composite_turn_exact")
    ]
    assert len(neg_exact) >= 5
    assert payload["corrected_composite_eligible_turns"] == 17


def test_regression_against_denominator_inflation() -> None:
    """Eligible turns must not drop exact all-unknown negative cases from denominator."""

    payload = recompute_frozen_a9r2b_live_diagnostic()
    corrected = payload["corrected_summary"]
    inflated_denominator = 12
    corrected_denominator = corrected["composite_eligible_turns"]
    assert corrected_denominator > inflated_denominator
    inflated_rate = corrected["composite_exact_turns"] / inflated_denominator
    corrected_rate = corrected["true_composite_exact_turn_rate"]
    assert inflated_rate == pytest.approx(11 / 12)
    assert corrected_rate == pytest.approx(11 / 17)
    assert corrected_rate < inflated_rate


def test_write_diagnostic_recompute_artifact(tmp_path: Path) -> None:
    out = tmp_path / "diag.json"
    payload = write_diagnostic_recompute_artifact(out)
    assert out.exists()
    assert payload["measurement_id"] == "a9r2b_patient_scope_live_diagnostic_recompute"


def test_aggregate_call_results_eligibility_matches_numerator() -> None:
    call_results = [
        {
            "category": "ambiguous",
            "score": {
                "transport_provider_error": False,
                "composite_turn_exact": True,
                "axis_outcomes": {
                    "extent": "not_applicable",
                    "jaw": "not_applicable",
                    "stage": "not_applicable",
                    "reported_context": "not_applicable",
                },
            },
        },
        {
            "category": "extent_positive",
            "score": {
                "transport_provider_error": True,
                "composite_turn_exact": False,
                "axis_outcomes": {},
            },
        },
    ]
    summary = aggregate_call_results(call_results)
    assert summary["composite_exact_turns"] == 1
    assert summary["composite_eligible_turns"] == 1
    assert summary["true_composite_exact_turn_rate"] == 1.0
