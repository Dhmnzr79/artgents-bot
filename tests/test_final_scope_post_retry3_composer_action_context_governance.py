"""PRE-CODE checker for FINAL_SCOPE_POST_RETRY3_COMPOSER_ACTION_CONTEXT governance."""

from __future__ import annotations

import json
from pathlib import Path

from evals.v5.final_scope_widget_e2e_live_contract import FROZEN_TURNS_HASH, sha256_file_hex
from evals.v5.final_scope_widget_e2e_retry3_live_contract import (
    FROZEN_RETRY3_LIVE_ARTIFACT_SHA256,
    FROZEN_RETRY3_LIVE_STDOUT_SIZE,
    LIVE_ATTEMPT_MARKER_PATH,
    LIVE_CALL_LEDGER_PATH,
    LIVE_STDOUT_LOG_PATH,
    assert_frozen_preflight_abort_artifacts_unchanged,
    assert_frozen_retry1_live_artifacts_unchanged,
    assert_frozen_retry2_live_artifacts_unchanged,
    assert_frozen_retry3_live_artifacts_unchanged,
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
    / "FINAL_SCOPE_WIDGET_E2E_RETRY3_MANUAL_REVIEW_AUDIT.md"
)
POST_RETRY3_SEAM_AUDIT_PATH = (
    _REPO_ROOT
    / "docs"
    / "evidence"
    / "final_scope"
    / "FINAL_SCOPE_POST_RETRY3_COMPOSER_ACTION_CONTEXT_SEAM_AUDIT.md"
)

CORRECTED_RETRY3_LEDGER_ROLE_COUNTS = {
    "ingress": 5,
    "planner": 5,
    "medical_boundary": 8,
    "composer": 8,
    "semantic_verifier": 8,
}
CORRECTED_RETRY3_LEDGER_TOTAL = 34


def test_manual_review_audit_exists() -> None:
    assert MANUAL_REVIEW_AUDIT_PATH.is_file()
    text = MANUAL_REVIEW_AUDIT_PATH.read_text(encoding="utf-8")
    assert "341c1eb" in text
    assert "AUTOMATED_PASS" in text
    assert "Owner manual verdict" in text or "owner manual" in text.lower()
    assert "**FAIL**" in text
    assert "T2" in text and "T6" in text and "T7" in text
    assert "price:None" in text
    assert "продолжить" in text
    assert "c3f4fe0cab32ac0a4e94c3b140f10f415036c6f34cffc8463975be47920e66d8" in text


def test_post_retry3_seam_audit_exists() -> None:
    assert POST_RETRY3_SEAM_AUDIT_PATH.is_file()
    text = POST_RETRY3_SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    assert "TargetComposerActionContext" in text
    assert "user_message" in text
    assert "продолжить" in text
    assert "broad_family_price" in text
    assert "price:None" in text
    assert "AM-1" in text and "AM-11" in text
    assert "A9_PATIENT_SCOPE_AUTHORITY" in text


def test_frozen_retry3_live_artifacts_unchanged() -> None:
    assert_frozen_retry3_live_artifacts_unchanged()


def test_retry3_attempt_marker_role_counts_match_completed_ledger() -> None:
    marker = json.loads(LIVE_ATTEMPT_MARKER_PATH.read_text(encoding="utf-8"))
    assert marker["status"] == "attempt_completed"
    assert marker["completed_provider_calls"] == CORRECTED_RETRY3_LEDGER_TOTAL
    assert marker["role_counts"] == CORRECTED_RETRY3_LEDGER_ROLE_COUNTS


def test_retry3_stdout_size_pinned() -> None:
    assert LIVE_STDOUT_LOG_PATH.is_file()
    assert LIVE_STDOUT_LOG_PATH.stat().st_size == FROZEN_RETRY3_LIVE_STDOUT_SIZE
    assert sha256_file_hex(LIVE_STDOUT_LOG_PATH) == (
        FROZEN_RETRY3_LIVE_ARTIFACT_SHA256[
            "evals/v5/artifacts/final_scope_widget_e2e_retry3_live_stdout.log"
        ]
    )


def test_retry3_ledger_sha_pinned() -> None:
    assert LIVE_CALL_LEDGER_PATH.is_file()
    assert sha256_file_hex(LIVE_CALL_LEDGER_PATH) == (
        FROZEN_RETRY3_LIVE_ARTIFACT_SHA256[
            "evals/v5/artifacts/final_scope_widget_e2e_retry3_call_ledger.jsonl"
        ]
    )


def test_frozen_widget_e2e_turn_matrix_unchanged() -> None:
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH


def test_frozen_neighbor_suites_unchanged() -> None:
    assert_frozen_preflight_abort_artifacts_unchanged()
    assert_frozen_retry1_live_artifacts_unchanged()
    assert_frozen_retry2_live_artifacts_unchanged()
    assert_frozen_s62_live_artifacts_unchanged()
    assert_frozen_s63_live_artifacts_unchanged()
    assert_frozen_suite_unchanged()
