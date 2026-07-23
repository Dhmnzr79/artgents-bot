from __future__ import annotations

import json

import pytest

from core.target_response_verifier import TargetSemanticAssessment, TargetSemanticIssue
from evals.v5.fullcontext_response_eval_contract import derive_semantic_reject_flags
from evals.v5.fullcontext_verifier_replay_contract import (
    EXPECTED_BLOCK_CASE_IDS_V2,
    FROZEN_S53_ARTIFACT_SHA256,
    FROZEN_S53_LIVE_RESULT_SHA256,
    LIVE_RESULT_ARTIFACT_PATH,
    REPLAY_MATRIX_HASH,
    REPLAY_MATRIX_V2_HASH,
    V2_CHANGED_CASE_IDS,
    HarnessConfigError,
    build_manual_review_seed,
    extract_replay_semantic_issues,
    load_replay_matrix,
    load_replay_matrix_v2,
    recompute_frozen_s53_diagnostics,
    score_replay_case,
    sha256_file_hex,
    validate_frozen_s53_artifacts,
)
from evals.v5.run_fullcontext_verifier_replay import main as run_replay_main
import evals.v5.run_fullcontext_verifier_replay as replay_runner


def _frozen_live_payload(case_id: str) -> dict[str, object]:
    payload = json.loads(LIVE_RESULT_ARTIFACT_PATH.read_text(encoding="utf-8"))
    return next(row for row in payload["case_results"] if row["case_id"] == case_id)


def test_frozen_s53_artifact_sha_pins() -> None:
    validate_frozen_s53_artifacts()
    for name, expected in FROZEN_S53_ARTIFACT_SHA256.items():
        path = LIVE_RESULT_ARTIFACT_PATH.parent / name
        assert sha256_file_hex(path) == expected


def test_extract_replay_semantic_issues_reads_live_assessment_shape() -> None:
    row = _frozen_live_payload("fc_medical_03")
    issues = extract_replay_semantic_issues(row["semantic_raw_payload"])
    assert len(issues) == 1
    assert issues[0]["kind"] == "material_external_medical_claim"


def test_fc_medical_03_recompute_block_kind_match() -> None:
    row = _frozen_live_payload("fc_medical_03")
    replay_case = next(
        case for case in load_replay_matrix()["cases"] if case["case_id"] == "fc_medical_03"
    )
    score = score_replay_case(
        replay_case=replay_case,
        observed_decision=row["observed_decision"],
        semantic_payload=row["semantic_raw_payload"],
    )
    assert score.decision_match is True
    assert score.missed_block is False
    assert score.blocking_kind_match is True


def test_fc_missing_02_recompute_block_kind_match() -> None:
    row = _frozen_live_payload("fc_missing_02")
    replay_case = next(
        case for case in load_replay_matrix()["cases"] if case["case_id"] == "fc_missing_02"
    )
    score = score_replay_case(
        replay_case=replay_case,
        observed_decision=row["observed_decision"],
        semantic_payload=row["semantic_raw_payload"],
    )
    assert score.decision_match is True
    assert score.missed_block is False
    assert score.blocking_kind_match is True


def test_manual_review_seed_matches_automated_scorer() -> None:
    payload = json.loads(LIVE_RESULT_ARTIFACT_PATH.read_text(encoding="utf-8"))
    replay_spec = load_replay_matrix()
    seed = build_manual_review_seed(
        case_results=list(payload["case_results"]),
        result_sha256=FROZEN_S53_LIVE_RESULT_SHA256,
        replay_spec=replay_spec,
    )
    for case in seed["cases"]:
        if case["review_status"] == "not_applicable":
            continue
        row = next(r for r in payload["case_results"] if r["case_id"] == case["case_id"])
        replay_case = next(c for c in replay_spec["cases"] if c["case_id"] == case["case_id"])
        score = score_replay_case(
            replay_case=replay_case,
            observed_decision=row["observed_decision"],
            semantic_payload=row["semantic_raw_payload"],
        )
        assert case["decision_match"] == score.decision_match
        assert case["blocking_kind_match"] == score.blocking_kind_match
        assert case["semantic_issues"] == extract_replay_semantic_issues(row["semantic_raw_payload"])


def test_malformed_replay_semantic_payload_fail_closed() -> None:
    with pytest.raises(HarnessConfigError, match="extra top-level keys"):
        extract_replay_semantic_issues({"model": "x", "assessment": {"issues": []}, "usage": {}, "extra": 1})
    with pytest.raises(HarnessConfigError, match="shape not recognized"):
        extract_replay_semantic_issues({"nested": {"issues": []}})


def test_dataclass_and_flat_issue_shapes_supported() -> None:
    assessment = TargetSemanticAssessment(
        issues=(TargetSemanticIssue(kind="minor_external_detail", offending_span="имплант"),)
    )
    assert extract_replay_semantic_issues(assessment)[0]["kind"] == "minor_external_detail"
    assert extract_replay_semantic_issues(
        {"issues": [{"kind": "minor_external_detail", "offending_span": "имплант"}]}
    )[0]["kind"] == "minor_external_detail"


def test_historical_five_boolean_derivation_unchanged() -> None:
    payload = {
        "model": "qwen3.7-plus",
        "assessment": {
            "issues": [{"kind": "personal_medical_conclusion", "offending_span": "вам нельзя"}]
        },
        "usage": {},
    }
    flags = derive_semantic_reject_flags(payload)
    assert flags["semantic_medical_boundary_rejected"] is True
    assert flags["semantic_general_grounding_rejected"] is False


def test_replay_matrix_v2_spec() -> None:
    spec = load_replay_matrix_v2()
    assert spec["parent_replay_matrix_git_blob_hash"] == REPLAY_MATRIX_HASH
    assert len(spec["cases"]) == 19
    pass_count = sum(1 for case in spec["cases"] if case["expected_decision"] == "pass")
    block_count = sum(1 for case in spec["cases"] if case["expected_decision"] == "block")
    assert pass_count == 14
    assert block_count == 5
    block_ids = {case["case_id"] for case in spec["cases"] if case["expected_decision"] == "block"}
    assert block_ids == EXPECTED_BLOCK_CASE_IDS_V2


def test_replay_matrix_v2_only_boundary_cases_changed() -> None:
    v1 = load_replay_matrix()
    v2 = load_replay_matrix_v2()
    v1_by = {case["case_id"]: case for case in v1["cases"]}
    v2_by = {case["case_id"]: case for case in v2["cases"]}
    changed = [
        case_id
        for case_id in v1_by
        if v1_by[case_id] != v2_by[case_id]
    ]
    assert set(changed) == V2_CHANGED_CASE_IDS


def test_replay_matrix_v2_hash_pinned() -> None:
    assert REPLAY_MATRIX_V2_HASH == "009977fca3a3e2a37b5c865f74c55c49c00de669"


def test_diagnostic_recompute_v1_labels_15_of_19() -> None:
    diag = recompute_frozen_s53_diagnostics(matrix_spec=load_replay_matrix())
    assert diag["decision_match_count"] == 15
    assert set(diag["false_block_case_ids"]) == {
        "fc_boundary_01",
        "fc_boundary_02",
        "fc_boundary_03",
    }
    assert diag["missed_block_case_ids"] == ["fc_missing_01"]


def test_diagnostic_recompute_v2_labels_17_of_19() -> None:
    diag = recompute_frozen_s53_diagnostics(matrix_spec=load_replay_matrix_v2())
    assert diag["decision_match_count"] == 17
    assert diag["false_block_case_ids"] == ["fc_boundary_01"]
    assert diag["missed_block_case_ids"] == ["fc_missing_01"]


def test_diagnostic_recompute_is_not_s53_pass() -> None:
    payload = json.loads(LIVE_RESULT_ARTIFACT_PATH.read_text(encoding="utf-8"))
    assert payload["summary"]["automated_verdict"]["verdict"] == "AUTOMATED_FAIL"
    assert payload["summary"]["final_verdict"] == "FAIL"


def test_cli_matrix_v2_dry_run(capsys, monkeypatch, tmp_path) -> None:
    paths = {
        "attempt": tmp_path / "attempt.json",
        "raw": tmp_path / "raw.json",
        "result": tmp_path / "result.json",
        "ledger": tmp_path / "ledger.jsonl",
        "manifest": tmp_path / "manifest.json",
        "manual": tmp_path / "manual.json",
    }
    artifact_paths = tuple(paths.values())
    monkeypatch.setattr(replay_runner, "LIVE_ATTEMPT_MARKER_PATH", paths["attempt"])
    monkeypatch.setattr(replay_runner, "DEFAULT_LIVE_ARTIFACT_PATHS", artifact_paths)
    assert run_replay_main(["--matrix-v2", "--dry-run"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["matrix_v2"] is True
    assert out["matrix_git_blob_hash"] == REPLAY_MATRIX_V2_HASH
    assert out["v2_live_status"] == "pending_owner_approval"


def test_cli_matrix_v2_live_blocked(capsys, monkeypatch, tmp_path) -> None:
    paths = {
        "attempt": tmp_path / "attempt.json",
        "raw": tmp_path / "raw.json",
        "result": tmp_path / "result.json",
        "ledger": tmp_path / "ledger.jsonl",
        "manifest": tmp_path / "manifest.json",
        "manual": tmp_path / "manual.json",
    }
    artifact_paths = tuple(paths.values())
    monkeypatch.setattr(replay_runner, "LIVE_ATTEMPT_MARKER_PATH", paths["attempt"])
    monkeypatch.setattr(replay_runner, "DEFAULT_LIVE_ARTIFACT_PATHS", artifact_paths)
    assert run_replay_main(["--matrix-v2", "--live"]) == 3
    assert "V2_LIVE_PENDING_OWNER_APPROVAL" in capsys.readouterr().err
