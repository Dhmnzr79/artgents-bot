from __future__ import annotations

import json
from collections import Counter

import pytest

from evals.v5.fullcontext_verifier_replay_contract import (
    AUTOMATED_ACCEPTANCE_GATES,
    BLAST_RADIUS_GROUPS,
    EXPECTED_BLOCK_CASE_IDS,
    FROZEN_SOURCE_RESULT_SHA256,
    MATERIALIZABLE_CASE_IDS,
    MODEL_RECOMMENDATION,
    REPLAY_MATRIX_HASH,
    REPLAY_MATRIX_PATH,
    TERMINAL_CONTROL_CASE_ID,
    HarnessConfigError,
    load_candidate_text,
    load_replay_matrix,
    validate_frozen_source_pins,
    validate_replay_matrix_hash,
)


def test_frozen_source_and_replay_matrix_hashes() -> None:
    validate_frozen_source_pins()
    validate_replay_matrix_hash(path=REPLAY_MATRIX_PATH)


def test_replay_matrix_has_nineteen_materializable_cases() -> None:
    spec = load_replay_matrix()
    case_ids = [case["case_id"] for case in spec["cases"]]
    assert len(case_ids) == 19
    assert len(set(case_ids)) == 19
    assert tuple(sorted(case_ids)) == tuple(sorted(MATERIALIZABLE_CASE_IDS))


def test_replay_matrix_pass_block_counts() -> None:
    spec = load_replay_matrix()
    decisions = Counter(case["expected_decision"] for case in spec["cases"])
    assert decisions["pass"] == 16
    assert decisions["block"] == 3
    block_ids = {case["case_id"] for case in spec["cases"] if case["expected_decision"] == "block"}
    assert block_ids == EXPECTED_BLOCK_CASE_IDS


def test_replay_matrix_case_schema_fields() -> None:
    spec = load_replay_matrix()
    required = {
        "case_id",
        "source_matrix_v2_case_id",
        "source_result_sha256",
        "candidate_text_sha256",
        "expected_decision",
        "required_blocking_issue_kinds",
        "allowed_nonblocking_issue_kinds",
        "blast_radius_group",
        "rationale",
        "audit_source_refs",
    }
    for case in spec["cases"]:
        assert set(case.keys()) == required
        assert case["source_result_sha256"] == FROZEN_SOURCE_RESULT_SHA256


def test_candidate_text_sha_matches_frozen_result() -> None:
    spec = load_replay_matrix()
    for case in spec["cases"]:
        text = load_candidate_text(case_id=case["case_id"], replay_case=case)
        assert text.strip()


def test_blast_radius_groups_cover_mass_selling_cases() -> None:
    spec = load_replay_matrix()
    groups = {case["blast_radius_group"] for case in spec["cases"]}
    for group in BLAST_RADIUS_GROUPS:
        assert group in groups, group


def test_model_and_gates_pending_owner_approval() -> None:
    spec = load_replay_matrix()
    assert spec["model_recommendation"]["status"] == "pending_owner_approval"
    assert spec["proposed_automated_acceptance_gates"]["status"] == "pending_owner_approval"
    assert MODEL_RECOMMENDATION["expected_verifier_provider_calls_materializable"] == 19
    assert AUTOMATED_ACCEPTANCE_GATES["composer_provider_call_count_max"] == 0


def test_terminal_control_case_id_pinned() -> None:
    spec = load_replay_matrix()
    assert spec["terminal_control_case_id"] == TERMINAL_CONTROL_CASE_ID


def test_replay_matrix_hash_constant_documented() -> None:
    assert REPLAY_MATRIX_HASH == "a273a58d96b00a76fd22b4d6fc9b97791df4f6d1"


def test_duplicate_case_id_rejected(tmp_path) -> None:
    spec = load_replay_matrix()
    broken = json.loads(json.dumps(spec))
    broken["cases"].append(dict(broken["cases"][0]))
    path = tmp_path / "broken.json"
    path.write_text(json.dumps(broken, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(HarnessConfigError, match="duplicate case_id"):
        load_replay_matrix(path=path)


def test_unknown_case_id_in_matrix_rejected(tmp_path) -> None:
    spec = load_replay_matrix()
    broken = json.loads(json.dumps(spec))
    broken["cases"][0]["case_id"] = "fc_unknown_99"
    broken["cases"][0]["source_matrix_v2_case_id"] = "fc_unknown_99"
    path = tmp_path / "broken.json"
    path.write_text(json.dumps(broken, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(HarnessConfigError, match="case_id set mismatch"):
        load_replay_matrix(path=path)
