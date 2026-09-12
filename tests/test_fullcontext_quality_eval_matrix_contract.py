from __future__ import annotations

import json

import pytest

from evals.v5.fullcontext_quality_eval_contract import (
    CASE_KEYS,
    EXPECTED_LLM_CALLS,
    FROZEN_MATRIX_HASH,
    GLOBAL_RUBRIC_IDS,
    MATRIX_PATH,
    MEASUREMENT_ID,
    SUITE_ID,
    assert_frozen_prior_artifacts_unchanged,
    load_frozen_matrix,
    validate_frozen_matrix_hash,
    validate_matrix_spec,
)

EXPECTED_USER_MESSAGES = (
    "Что лучше именно в моём случае — имплант или мост?",
    "Можно ли ставить импланты при волчанке?",
    "Можно ли ставить импланты при диабете?",
    "Можно ли ставить имплант при беременности?",
    "Больно ли ставить имплант?",
    "Сколько стоит All-on-4?",
    "Кто делает имплантацию?",
    "Что такое All-on-4?",
    "Как можно оплатить All-on-4?",
)


def test_matrix_schema_case_ids_counts_and_frozen_hash() -> None:
    validate_frozen_matrix_hash(path=MATRIX_PATH)
    spec = load_frozen_matrix(path=MATRIX_PATH)
    assert spec["suite_id"] == SUITE_ID
    assert spec["schema_version"] == 1
    assert len(spec["cases"]) == 9
    assert len({case["case_id"] for case in spec["cases"]}) == 9
    assert spec["model_recommendation"]["expected_llm_calls_total"] == EXPECTED_LLM_CALLS
    assert spec["scoring_contract"]["literal_forbidden_hits_diagnostic_only"] is True


def test_all_nine_user_messages_and_case_keys() -> None:
    spec = load_frozen_matrix()
    messages = tuple(case["user_message"] for case in spec["cases"])
    assert messages == EXPECTED_USER_MESSAGES
    for case in spec["cases"]:
        assert set(case.keys()) == set(CASE_KEYS)
        assert case["expected_outcome"] == "materialize_verified"
        assert case["expected_primary_evidence_refs"] is not None
        assert case["critical_requirements"]


def test_global_rubric_ids_match_owner_spec() -> None:
    spec = load_frozen_matrix()
    rubric_ids = tuple(item["id"] for item in spec["manual_review_contract"]["global_rubric"])
    assert rubric_ids == GLOBAL_RUBRIC_IDS


def test_consult_case_expects_free_implant_consult_evidence() -> None:
    spec = load_frozen_matrix()
    case = next(item for item in spec["cases"] if item["case_id"] == "s57_consult_01")
    assert case["expected_primary_evidence_refs"] == ["fact:free_implant_consult"]
    assert case["policy_envelope"]["allow_consultation_close"] is True
    assert case["turn_frame_raw"]["service_id"] is None
    assert case["turn_frame_raw"]["topic"] == "implantation"


def test_frozen_prior_artifacts_byte_identical() -> None:
    assert_frozen_prior_artifacts_unchanged()


def test_validate_matrix_spec_rejects_wrong_case_count() -> None:
    spec = load_frozen_matrix()
    broken = dict(spec)
    broken["cases"] = spec["cases"][:8]
    with pytest.raises(Exception, match="exactly 9"):
        validate_matrix_spec(broken)


def test_measurement_and_suite_constants() -> None:
    assert MEASUREMENT_ID == "s57_fullcontext_quality_eval"
    assert FROZEN_MATRIX_HASH == "89616cbde59229e222d4c87f4e2abc06361aa05d"
