from __future__ import annotations

import json
from collections import Counter

import pytest

from evals.v5.fullcontext_response_eval_contract import (
    ACCEPTANCE_THRESHOLDS,
    FROZEN_MATRIX_HASH,
    MATRIX_PATH,
    REQUIRED_CASE_KINDS,
    THRESHOLDS_STATUS,
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


def test_proposed_thresholds_frozen_before_first_live() -> None:
    spec = load_frozen_matrix()
    thresholds = spec["proposed_acceptance_thresholds"]
    assert thresholds["status"] == THRESHOLDS_STATUS
    assert thresholds["outcome_match_rate_min"] == ACCEPTANCE_THRESHOLDS["outcome_match_rate_min"]


def test_pain_case_is_medical_handoff_without_service_id() -> None:
    spec = load_frozen_matrix()
    case = next(item for item in spec["cases"] if item["case_id"] == "fc_pain_01")
    assert case["case_kind"] == "pain_reassurance"
    assert case["expected_outcome"] == "materialize_verified"
    assert case["expected_response_mode"] == "medical_handoff"
    assert case["turn_frame_raw"]["service_id"] is None
    assert "implantation__faq__pain.md" in case["audit_source_refs"]


def test_terminal_case_is_boundary_uncertain() -> None:
    spec = load_frozen_matrix()
    case = next(item for item in spec["cases"] if item["case_id"] == "fc_terminal_01")
    assert case["expected_outcome"] == "terminal_boundary_uncertain"
    assert case["boundary_result"]["decision"] == "uncertain"


def test_missing_base_cases_have_two_entries() -> None:
    spec = load_frozen_matrix()
    missing = [case for case in spec["cases"] if case["case_kind"] == "missing_base"]
    assert len(missing) == 2


def test_matrix_hash_constant_documented() -> None:
    assert FROZEN_MATRIX_HASH == "79baaa077bc5dcc0b7ecef4d0f5081d400e58f69"


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
