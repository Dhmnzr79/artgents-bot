from __future__ import annotations

import json
from collections import Counter

import pytest

from evals.v5.fullcontext_response_eval_contract import (
    AUTOMATED_ACCEPTANCE_THRESHOLDS,
    AUTOMATED_THRESHOLDS_STATUS,
    CASE_SPECIFIC_RUBRIC_IDS,
    FINAL_ACCEPTANCE_GATES,
    FINAL_GATES_STATUS,
    FROZEN_MATRIX_HASH,
    GLOBAL_RUBRIC_IDS,
    MATRIX_PATH,
    MODEL_RECOMMENDATION,
    REQUIRED_CASE_KINDS,
    HarnessConfigError,
    load_frozen_matrix,
    validate_frozen_matrix_hash,
)


def test_frozen_matrix_hash_matches() -> None:
    validate_frozen_matrix_hash(path=MATRIX_PATH)


def test_matrix_has_twenty_cases_and_required_kinds() -> None:
    spec = load_frozen_matrix()
    assert len(spec["cases"]) == 20
    kinds = {case["case_kind"] for case in spec["cases"]}
    assert kinds == REQUIRED_CASE_KINDS


def test_matrix_forbids_observed_fields_in_source_file() -> None:
    raw = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    for case in raw["cases"]:
        assert "observed_outcome" not in case
        assert "pass" not in case
        assert "manual_review_rubric" not in case


def test_manual_review_contract_present() -> None:
    spec = load_frozen_matrix()
    contract = spec["manual_review_contract"]
    global_ids = [item["id"] for item in contract["global_rubric"]]
    assert tuple(global_ids) == GLOBAL_RUBRIC_IDS
    assert set(contract["case_specific_rubric_profiles"].keys()) == set(
        CASE_SPECIFIC_RUBRIC_IDS.keys()
    )


def test_proposed_automated_thresholds_frozen_before_first_live() -> None:
    spec = load_frozen_matrix()
    thresholds = spec["proposed_automated_acceptance_thresholds"]
    assert thresholds["status"] == AUTOMATED_THRESHOLDS_STATUS
    assert thresholds["outcome_match_rate_min"] == AUTOMATED_ACCEPTANCE_THRESHOLDS[
        "outcome_match_rate_min"
    ]


def test_proposed_final_gates_pending_owner_approval() -> None:
    spec = load_frozen_matrix()
    gates = spec["proposed_final_acceptance_gates"]
    assert gates["status"] == FINAL_GATES_STATUS
    assert gates["manual_answer_quality_pass_rate_min"] == FINAL_ACCEPTANCE_GATES[
        "manual_answer_quality_pass_rate_min"
    ]


def test_model_recommendation_pending_owner_approval() -> None:
    spec = load_frozen_matrix()
    recommendation = spec["model_recommendation"]
    assert recommendation["status"] == MODEL_RECOMMENDATION["status"]
    assert recommendation["composer_model"] == "qwen3.7-plus"
    assert recommendation["expected_llm_calls_materializable"] == 38


def test_pain_case_is_medical_handoff_without_service_id() -> None:
    spec = load_frozen_matrix()
    case = next(item for item in spec["cases"] if item["case_id"] == "fc_pain_01")
    assert case["case_kind"] == "pain_reassurance"
    assert case["case_specific_rubric_profile"] == "pain_reassurance"
    assert case["expected_outcome"] == "materialize_verified"
    assert case["expected_response_mode"] == "medical_handoff"
    assert case["turn_frame_raw"]["service_id"] is None
    assert "implantation__faq__pain.md" in case["audit_source_refs"]


def test_terminal_case_is_boundary_uncertain() -> None:
    spec = load_frozen_matrix()
    case = next(item for item in spec["cases"] if item["case_id"] == "fc_terminal_01")
    assert case["expected_outcome"] == "terminal_boundary_uncertain"
    assert case["case_specific_rubric_profile"] is None
    assert case["boundary_result"]["decision"] == "uncertain"


def test_missing_base_cases_have_two_entries() -> None:
    spec = load_frozen_matrix()
    missing = [case for case in spec["cases"] if case["case_kind"] == "missing_base"]
    assert len(missing) == 2
    assert all(case["case_specific_rubric_profile"] == "missing_base" for case in missing)


def test_matrix_hash_constant_documented() -> None:
    assert FROZEN_MATRIX_HASH == "c0b2b4cd364b2013cfbe68651eaf43e8bdb3626c"


def test_tampered_matrix_hash_rejected(tmp_path) -> None:
    tampered = tmp_path / "matrix.json"
    tampered.write_text('{"schema_version": 1}', encoding="utf-8")
    with pytest.raises(HarnessConfigError, match="hash mismatch"):
        load_frozen_matrix(path=tampered)


def test_case_kind_distribution() -> None:
    spec = load_frozen_matrix()
    counts = Counter(case["case_kind"] for case in spec["cases"])
    assert counts["general_information"] == 3
    assert counts["structured_commercial_price"] == 2
    assert counts["known_medical_topic"] == 3
    assert counts["medical_boundary_personal"] == 2
    assert counts["terminal_uncertain"] == 1
