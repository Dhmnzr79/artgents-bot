from __future__ import annotations

import json
from collections import Counter

import pytest

from evals.v5.medical_boundary_eval_contract import (
    FROZEN_MATRIX_HASH,
    MATRIX_PATH,
    PROPOSED_ACCEPTANCE_THRESHOLDS,
    PROPOSED_THRESHOLD_KEYS,
    REQUIRED_CASE_KINDS,
    HarnessConfigError,
    load_frozen_matrix,
    validate_frozen_matrix_hash,
)


def test_frozen_matrix_hash_matches() -> None:
    validate_frozen_matrix_hash(path=MATRIX_PATH)


def test_matrix_has_required_case_kinds_and_expected_labels() -> None:
    spec = load_frozen_matrix()
    kinds = {case["case_kind"] for case in spec["cases"]}
    assert kinds == REQUIRED_CASE_KINDS
    assert len(spec["cases"]) == 26
    for case in spec["cases"]:
        assert case["expected_label"] in {"none", "medical_handoff"}


def test_matrix_forbids_observed_fields_in_source_file() -> None:
    raw = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    for case in raw["cases"]:
        assert "observed_label" not in case
        assert "pass" not in case


def test_proposed_thresholds_pending_owner_approval() -> None:
    spec = load_frozen_matrix()
    thresholds = spec["proposed_acceptance_thresholds"]
    assert thresholds["status"] == "pending_owner_approval"
    for key in PROPOSED_THRESHOLD_KEYS:
        assert thresholds[key] == PROPOSED_ACCEPTANCE_THRESHOLDS[key]
    assert thresholds["dangerous_false_none_count_max"] == 0


def test_matrix_case_kind_distribution_is_compact() -> None:
    spec = load_frozen_matrix()
    counts = Counter(case["case_kind"] for case in spec["cases"])
    assert counts["informational_commercial"] == 3
    assert counts["price_payment_doctors_services"] == 4
    assert counts["personal_eligibility"] == 4
    assert counts["symptoms_complications"] == 4
    assert counts["diagnosis_treatment_choice"] == 3
    assert counts["borderline_general_vs_personal"] == 4
    assert counts["short_typo_noise"] == 2
    assert counts["prompt_injection"] == 2


def test_matrix_hash_constant_documented() -> None:
    assert FROZEN_MATRIX_HASH == "aabfd0e6dac95aa7130f3c2596b3730004bcfe75"


def test_tampered_matrix_hash_rejected(tmp_path) -> None:
    tampered = tmp_path / "matrix.json"
    tampered.write_text('{"schema_version": 1}', encoding="utf-8")
    with pytest.raises(HarnessConfigError, match="hash mismatch"):
        load_frozen_matrix(path=tampered)
