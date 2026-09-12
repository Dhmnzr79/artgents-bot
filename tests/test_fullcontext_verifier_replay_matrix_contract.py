from __future__ import annotations

import json
from collections import Counter

import pytest

from evals.v5.fullcontext_verifier_replay_contract import (
    AUTOMATED_ACCEPTANCE_GATES,
    BLAST_RADIUS_GROUPS,
    EXPECTED_BLOCK_CASE_IDS,
    EXPECTED_BLOCK_CASE_IDS_V2,
    FROZEN_SOURCE_RESULT_SHA256,
    MATERIALIZABLE_CASE_IDS,
    MODEL_RECOMMENDATION,
    REPLAY_MATRIX_HASH,
    REPLAY_MATRIX_PATH,
    REPLAY_MATRIX_V2_HASH,
    REPLAY_MATRIX_V2_PATH,
    TERMINAL_CONTROL_CASE_ID,
    V2_CHANGED_CASE_IDS,
    HarnessConfigError,
    load_candidate_text,
    load_replay_matrix,
    load_replay_matrix_v2,
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
    assert MODEL_RECOMMENDATION["status"] == "owner_approved"
    assert AUTOMATED_ACCEPTANCE_GATES["status"] == "owner_approved"
    assert MODEL_RECOMMENDATION["expected_verifier_provider_calls_materializable"] == 19
    assert AUTOMATED_ACCEPTANCE_GATES["composer_provider_call_count_max"] == 0


def test_terminal_control_case_id_pinned() -> None:
    spec = load_replay_matrix()
    assert spec["terminal_control_case_id"] == TERMINAL_CONTROL_CASE_ID


def test_replay_matrix_hash_constant_documented() -> None:
    assert REPLAY_MATRIX_HASH == "a273a58d96b00a76fd22b4d6fc9b97791df4f6d1"


def test_replay_matrix_v2_hash_and_counts() -> None:
    spec = load_replay_matrix_v2()
    assert spec["parent_replay_matrix_git_blob_hash"] == REPLAY_MATRIX_HASH
    assert REPLAY_MATRIX_V2_HASH == "009977fca3a3e2a37b5c865f74c55c49c00de669"
    decisions = Counter(case["expected_decision"] for case in spec["cases"])
    assert decisions["pass"] == 14
    assert decisions["block"] == 5
    block_ids = {case["case_id"] for case in spec["cases"] if case["expected_decision"] == "block"}
    assert block_ids == EXPECTED_BLOCK_CASE_IDS_V2


def test_replay_matrix_v2_delta_only_boundary_cases() -> None:
    v1 = load_replay_matrix()
    v2 = load_replay_matrix_v2()
    v1_by = {case["case_id"]: case for case in v1["cases"]}
    v2_by = {case["case_id"]: case for case in v2["cases"]}
    changed = [case_id for case_id in v1_by if v1_by[case_id] != v2_by[case_id]]
    assert set(changed) == V2_CHANGED_CASE_IDS
    for case_id in v1_by:
        if case_id in V2_CHANGED_CASE_IDS:
            continue
        assert v1_by[case_id] == v2_by[case_id]


def test_replay_matrix_v2_path_pinned() -> None:
    assert REPLAY_MATRIX_V2_PATH.name == "fullcontext_verifier_replay_matrix_v2.json"


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
