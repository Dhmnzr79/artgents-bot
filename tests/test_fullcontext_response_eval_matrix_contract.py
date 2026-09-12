from __future__ import annotations

import json
import subprocess
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
    V2_MATRIX_HASH,
    V2_MATRIX_PATH,
    V2_PARENT_MATRIX_HASH,
    V2_SUITE_ID,
    HarnessConfigError,
    assert_v1_v2_matrix_delta,
    load_frozen_matrix,
    load_v2_matrix,
    validate_frozen_matrix_hash,
    validate_v2_matrix_hash,
)

BASELINE_MATRIX_REF = "dcd8862:evals/v5/demo/fullcontext_response_eval_matrix.json"
FC_BOUNDARY_03_PERSONAL_MESSAGE = "Что лучше именно в моём случае — имплант или мост?"


def _baseline_user_messages() -> dict[str, str]:
    raw = subprocess.check_output(
        ["git", "show", BASELINE_MATRIX_REF],
        text=True,
        encoding="utf-8",
    )
    spec = json.loads(raw)
    return {case["case_id"]: case["user_message"] for case in spec["cases"]}


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
    assert FROZEN_MATRIX_HASH == "14b1cbd4c3a8d906e0b19adb10ffaa60849803b3"


def test_fc_boundary_03_personal_treatment_choice_question() -> None:
    spec = load_frozen_matrix()
    case = next(item for item in spec["cases"] if item["case_id"] == "fc_boundary_03")
    assert case["case_kind"] == "medical_boundary_treatment_choice"
    assert case["user_message"] == FC_BOUNDARY_03_PERSONAL_MESSAGE
    assert case["expected_response_mode"] == "medical_handoff"
    assert case["case_specific_rubric_profile"] == "medical"


def test_nineteen_other_user_messages_unchanged_from_dcd8862() -> None:
    baseline = _baseline_user_messages()
    spec = load_frozen_matrix()
    assert len(spec["cases"]) == 20
    for case in spec["cases"]:
        case_id = case["case_id"]
        if case_id == "fc_boundary_03":
            continue
        assert case["user_message"] == baseline[case_id], case_id


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


def test_v2_matrix_hash_matches() -> None:
    validate_v2_matrix_hash(path=V2_MATRIX_PATH)


def test_v2_matrix_hash_constant_documented() -> None:
    assert V2_MATRIX_HASH == "615714c519a92a75e23c2f15bbaa01a0f88a4d95"
    assert V2_PARENT_MATRIX_HASH == FROZEN_MATRIX_HASH


def test_v2_matrix_has_twenty_cases_and_required_kinds() -> None:
    spec = load_v2_matrix()
    assert spec["suite_id"] == V2_SUITE_ID
    assert len(spec["cases"]) == 20
    kinds = {case["case_kind"] for case in spec["cases"]}
    assert kinds == REQUIRED_CASE_KINDS


def test_v2_user_messages_match_v1() -> None:
    v1 = load_frozen_matrix()
    v2 = load_v2_matrix()
    assert {case["case_id"]: case["user_message"] for case in v1["cases"]} == {
        case["case_id"]: case["user_message"] for case in v2["cases"]
    }


def test_v2_delta_is_fc_boundary_02_allowed_topics_only() -> None:
    assert_v1_v2_matrix_delta()


def test_fc_boundary_02_v2_adds_treatment_without_changing_safety() -> None:
    v1 = next(case for case in load_frozen_matrix()["cases"] if case["case_id"] == "fc_boundary_02")
    v2 = next(case for case in load_v2_matrix()["cases"] if case["case_id"] == "fc_boundary_02")
    assert v1["policy_envelope"]["allowed_topics"] == ["implantation", "doctors"]
    assert v2["policy_envelope"]["allowed_topics"] == ["implantation", "doctors", "treatment"]
    assert v1["medical_safety"] == v2["medical_safety"]
    assert v1["forbidden_claims"] == v2["forbidden_claims"]
    assert v1["user_message"] == v2["user_message"]


def test_s47_matrix_file_unchanged() -> None:
    validate_frozen_matrix_hash(path=MATRIX_PATH)
    assert FROZEN_MATRIX_HASH == "14b1cbd4c3a8d906e0b19adb10ffaa60849803b3"
