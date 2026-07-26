"""PRE-CODE checker for FINAL_SCOPE_WIDGET_E2E_CLOSEOUT governance."""

from __future__ import annotations

import json
from pathlib import Path

from evals.v5.final_scope_widget_e2e_live_contract import FROZEN_TURNS_HASH, sha256_file_hex
from evals.v5.final_scope_widget_e2e_retry4_live_contract import (
    FROZEN_RETRY4_LIVE_ARTIFACT_SHA256,
    LIVE_ATTEMPT_MARKER_PATH,
    LIVE_MANIFEST_ARTIFACT_PATH,
    LIVE_RAW_ARTIFACT_PATH,
    LIVE_RESULT_ARTIFACT_PATH,
    MANUAL_REVIEW_RUBRIC,
    assert_frozen_preflight_abort_artifacts_unchanged,
    assert_frozen_retry1_live_artifacts_unchanged,
    assert_frozen_retry2_live_artifacts_unchanged,
    assert_frozen_retry3_live_artifacts_unchanged,
    assert_frozen_retry4_live_artifacts_unchanged,
    assert_frozen_s62_live_artifacts_unchanged,
    assert_frozen_s63_live_artifacts_unchanged,
    assert_frozen_suite_unchanged,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]

MANUAL_REVIEW_AUDIT_PATH = (
    _REPO_ROOT
    / "docs"
    / "evidence"
    / "final_scope"
    / "FINAL_SCOPE_WIDGET_E2E_RETRY4_MANUAL_REVIEW_AUDIT.md"
)
CLOSEOUT_SEAM_AUDIT_PATH = (
    _REPO_ROOT
    / "docs"
    / "evidence"
    / "final_scope"
    / "FINAL_SCOPE_WIDGET_E2E_CLOSEOUT_SEAM_AUDIT.md"
)
TASK_PATH = _REPO_ROOT / "TASK.md"

FROZEN_RETRY4_RESULT_SHA256 = (
    "8778278802f4f4f474cfe8dbb4118f684208a1605aec5cc40b5b3bf003207a03"
)
FROZEN_RETRY4_MANIFEST_SHA256 = (
    "46f5ea55537e3514dd8b40d44f37d08f60a4324646aabbecc74d444acc1fba90"
)
GOVERNANCE_BASELINE_HEAD = "5ff9893"


def test_manual_review_audit_owner_pass_captured() -> None:
    assert MANUAL_REVIEW_AUDIT_PATH.is_file()
    text = MANUAL_REVIEW_AUDIT_PATH.read_text(encoding="utf-8")
    assert GOVERNANCE_BASELINE_HEAD in text
    assert "AUTOMATED_PASS" in text
    assert "Owner manual verdict" in text or "owner manual" in text.lower()
    assert "**PASS**" in text
    assert "8/8" in text
    assert "PENDING_MANUAL_REVIEW" in text
    assert FROZEN_RETRY4_RESULT_SHA256 in text
    assert FROZEN_RETRY4_MANIFEST_SHA256 in text
    assert FROZEN_TURNS_HASH in text
    assert "3459868df40d47c841ad2ef4eacb38a69be7bb73b42694af30279940dfabc0df" in text
    assert "compact_overview" in text
    assert "full_arch_prices" in text
    assert "concise_stage_clarification" in text
    assert "crown_price" in text
    assert "704" in text
    assert "WinError 32" in text


def test_closeout_seam_audit_exists() -> None:
    assert CLOSEOUT_SEAM_AUDIT_PATH.is_file()
    text = CLOSEOUT_SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    assert "A9_PATIENT_SCOPE_AUTHORITY" in text
    assert "unconditional" in text.lower()
    assert "qwen3.7-plus" in text
    assert "reported_context" in text
    assert "typed UI" in text or "typed ui" in text.lower()
    assert "materialized" in text
    assert "AC1" in text and "AC3" in text
    for rule in (
        "one_tooth",
        "few_teeth",
        "full_arch",
        "natural_tooth_present",
        "implant_placed",
        "All-on-4",
        "/ask/stream",
    ):
        assert rule in text


def test_task_closeout_governance_section() -> None:
    text = TASK_PATH.read_text(encoding="utf-8")
    assert "FINAL_SCOPE_WIDGET_E2E_CLOSEOUT" in text
    assert GOVERNANCE_BASELINE_HEAD in text
    assert "NO LIVE" in text
    assert "NO Retry5" in text
    assert "test_final_scope_widget_e2e_closeout_governance.py" in text


def test_frozen_retry4_result_stays_pending_manual_review_capture() -> None:
    payload = json.loads(LIVE_RESULT_ARTIFACT_PATH.read_text(encoding="utf-8"))
    assert payload["summary"]["automated_verdict"] == "AUTOMATED_PASS"
    assert payload["summary"]["final_verdict"] == "PENDING_MANUAL_REVIEW"
    assert sha256_file_hex(LIVE_RESULT_ARTIFACT_PATH) == FROZEN_RETRY4_RESULT_SHA256
    assert sha256_file_hex(LIVE_RAW_ARTIFACT_PATH) == FROZEN_RETRY4_RESULT_SHA256
    assert sha256_file_hex(LIVE_MANIFEST_ARTIFACT_PATH) == FROZEN_RETRY4_MANIFEST_SHA256


def test_frozen_retry4_live_artifacts_unchanged() -> None:
    assert_frozen_retry4_live_artifacts_unchanged()
    assert LIVE_ATTEMPT_MARKER_PATH.is_file()


def test_frozen_widget_matrix_and_neighbor_suites_unchanged() -> None:
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH
    assert_frozen_preflight_abort_artifacts_unchanged()
    assert_frozen_retry1_live_artifacts_unchanged()
    assert_frozen_retry2_live_artifacts_unchanged()
    assert_frozen_retry3_live_artifacts_unchanged()
    assert_frozen_s62_live_artifacts_unchanged()
    assert_frozen_s63_live_artifacts_unchanged()
    assert_frozen_suite_unchanged()


def test_a9_flag_still_present_until_closeout_implementation() -> None:
    config_text = (_REPO_ROOT / "config.py").read_text(encoding="utf-8")
    assert "A9_PATIENT_SCOPE_AUTHORITY" in config_text
    assert MANUAL_REVIEW_RUBRIC[1] == "compact_overview"
    assert (
        FROZEN_RETRY4_LIVE_ARTIFACT_SHA256[
            "evals/v5/artifacts/final_scope_widget_e2e_retry4_result.json"
        ]
        == FROZEN_RETRY4_RESULT_SHA256
    )
