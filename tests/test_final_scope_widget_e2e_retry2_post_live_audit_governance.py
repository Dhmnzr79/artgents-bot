"""PRE-CODE checker for FINAL_SCOPE_WIDGET_E2E_RETRY2_POST_LIVE_AUDIT governance."""

from __future__ import annotations

from pathlib import Path

from evals.v5.final_scope_widget_e2e_live_contract import FROZEN_TURNS_HASH, sha256_file_hex
from evals.v5.final_scope_widget_e2e_retry2_live_contract import (
    FROZEN_RETRY2_LIVE_ARTIFACT_SHA256,
    FROZEN_RETRY2_LIVE_STDOUT_SIZE,
    LIVE_ATTEMPT_MARKER_PATH,
    LIVE_CALL_LEDGER_PATH,
    LIVE_STDOUT_LOG_PATH,
    assert_frozen_preflight_abort_artifacts_unchanged,
    assert_frozen_retry1_live_artifacts_unchanged,
    assert_frozen_retry2_live_artifacts_unchanged,
    assert_frozen_s62_live_artifacts_unchanged,
    assert_frozen_s63_live_artifacts_unchanged,
    assert_frozen_suite_unchanged,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]

LIVE_ATTEMPT_AUDIT_PATH = (
    _REPO_ROOT
    / "docs"
    / "evidence"
    / "final_scope"
    / "FINAL_SCOPE_WIDGET_E2E_RETRY2_LIVE_ATTEMPT_AUDIT.md"
)
POST_LIVE_SEAM_AUDIT_PATH = (
    _REPO_ROOT
    / "docs"
    / "evidence"
    / "final_scope"
    / "FINAL_SCOPE_WIDGET_E2E_RETRY2_POST_LIVE_SEAM_AUDIT.md"
)

CORRECTED_LEDGER_ROLE_COUNTS = {
    "ingress": 4,
    "planner": 6,
    "medical_boundary": 6,
    "composer": 4,
    "semantic_verifier": 4,
}
CORRECTED_LEDGER_TOTAL = 24


def test_live_attempt_audit_exists() -> None:
    assert LIVE_ATTEMPT_AUDIT_PATH.is_file()
    text = LIVE_ATTEMPT_AUDIT_PATH.read_text(encoding="utf-8")
    assert "AUTOMATED_FAIL" in text
    assert "target_fullcontext_error" in text
    assert "deb0e00b0fccc0d3ab6f5e65a67caaacf90677231898e10dc3e9f3893e160671" in text
    assert "продолжить" in text
    assert "WinError 32" in text


def test_post_live_seam_audit_exists() -> None:
    assert POST_LIVE_SEAM_AUDIT_PATH.is_file()
    text = POST_LIVE_SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    assert "T2" in text and "T6" in text
    assert "UiScopeAction" in text
    assert "needs_clarification=false" in text
    assert "AC1" in text and "AC2" in text and "AC3" in text
    assert "partial planner" in text.lower() or "partial frame" in text.lower()


def test_frozen_retry2_live_artifacts_unchanged() -> None:
    assert_frozen_retry2_live_artifacts_unchanged()


def test_retry2_attempt_marker_role_counts_match_corrected_ledger() -> None:
    import json

    marker = json.loads(LIVE_ATTEMPT_MARKER_PATH.read_text(encoding="utf-8"))
    assert marker["status"] == "attempt_started"
    assert marker["started_provider_calls"] == CORRECTED_LEDGER_TOTAL
    assert marker["role_counts"] == CORRECTED_LEDGER_ROLE_COUNTS


def test_retry2_stdout_size_pinned() -> None:
    assert LIVE_STDOUT_LOG_PATH.is_file()
    assert LIVE_STDOUT_LOG_PATH.stat().st_size == FROZEN_RETRY2_LIVE_STDOUT_SIZE
    assert sha256_file_hex(LIVE_STDOUT_LOG_PATH) == (
        FROZEN_RETRY2_LIVE_ARTIFACT_SHA256[
            "evals/v5/artifacts/final_scope_widget_e2e_retry2_live_stdout.log"
        ]
    )


def test_retry2_ledger_sha_pinned() -> None:
    assert LIVE_CALL_LEDGER_PATH.is_file()
    assert sha256_file_hex(LIVE_CALL_LEDGER_PATH) == (
        FROZEN_RETRY2_LIVE_ARTIFACT_SHA256[
            "evals/v5/artifacts/final_scope_widget_e2e_retry2_call_ledger.jsonl"
        ]
    )


def test_frozen_widget_e2e_turn_matrix_unchanged() -> None:
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH


def test_frozen_neighbor_suites_unchanged() -> None:
    assert_frozen_preflight_abort_artifacts_unchanged()
    assert_frozen_retry1_live_artifacts_unchanged()
    assert_frozen_s62_live_artifacts_unchanged()
    assert_frozen_s63_live_artifacts_unchanged()
    assert_frozen_suite_unchanged()
