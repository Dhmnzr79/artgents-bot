"""PRE-CODE / COMPLETION checker for FINAL_SCOPE_WIDGET_E2E_RETRY4."""

from __future__ import annotations

import json
from pathlib import Path

from evals.v5.final_scope_widget_e2e_live_contract import FROZEN_TURNS_HASH, sha256_file_hex
from evals.v5.final_scope_widget_e2e_retry1_live_contract import (
    LIVE_ATTEMPT_MARKER_PATH as RETRY1_ATTEMPT_MARKER_PATH,
)
from evals.v5.final_scope_widget_e2e_retry2_live_contract import (
    LIVE_ATTEMPT_MARKER_PATH as RETRY2_ATTEMPT_MARKER_PATH,
)
from evals.v5.final_scope_widget_e2e_retry3_live_contract import (
    LIVE_ATTEMPT_MARKER_PATH as RETRY3_ATTEMPT_MARKER_PATH,
)
from evals.v5.final_scope_widget_e2e_retry4_live_contract import (
    DEFAULT_LIVE_ARTIFACT_PATHS,
    EXPECTED_FREE_TEXT_PLANNER_CALLS,
    FROZEN_RETRY4_LIVE_ARTIFACT_SHA256,
    FROZEN_RETRY4_LIVE_STDOUT_SIZE,
    LIVE_ATTEMPT_MARKER_PATH,
    LIVE_CALL_LEDGER_PATH,
    LIVE_STDOUT_LOG_PATH,
    MANUAL_REVIEW_RUBRIC,
    MAX_BOUNDARY_CALLS,
    MAX_COMPOSER_CALLS,
    MAX_HTTP_TURNS,
    MAX_INGRESS_CALLS,
    MAX_PLANNER_CALLS,
    MAX_PROVIDER_CALLS,
    MAX_VERIFIER_CALLS,
    MEASUREMENT_ID,
    PARENT_MEASUREMENT_ID,
    RETRY_COUNT_MAX,
    TYPED_UI_TURNS_NO_PLANNER,
    OWNER_APPROVED_PLANNER_MODEL,
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

CORRECTED_RETRY4_LEDGER_ROLE_COUNTS = {
    "ingress": 5,
    "planner": 5,
    "medical_boundary": 8,
    "composer": 8,
    "semantic_verifier": 8,
}
CORRECTED_RETRY4_LEDGER_TOTAL = 34

SEAM_AUDIT_PATH = (
    _REPO_ROOT
    / "docs"
    / "evidence"
    / "final_scope"
    / "FINAL_SCOPE_WIDGET_E2E_RETRY4_SEAM_AUDIT.md"
)


def test_seam_audit_exists() -> None:
    assert SEAM_AUDIT_PATH.is_file()
    text = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    assert "retry4" in text
    assert "6b67e35" in text
    assert "POST_RETRY3" in text or "Composer action context" in text
    assert "compact_overview" in text or "compact overview" in text
    assert "full_arch" in text
    assert "crown" in text.lower() or "корон" in text


def test_frozen_retry1_retry2_retry3_live_artifacts_unchanged() -> None:
    assert_frozen_retry1_live_artifacts_unchanged()
    assert_frozen_retry2_live_artifacts_unchanged()
    assert_frozen_retry3_live_artifacts_unchanged()


def test_frozen_widget_e2e_turn_matrix_unchanged() -> None:
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH


def test_frozen_neighbor_suites_unchanged() -> None:
    assert_frozen_preflight_abort_artifacts_unchanged()
    assert_frozen_s62_live_artifacts_unchanged()
    assert_frozen_s63_live_artifacts_unchanged()
    assert_frozen_suite_unchanged()


def test_retry4_namespace_isolated() -> None:
    assert MEASUREMENT_ID == "final_scope_widget_e2e_retry4"
    assert PARENT_MEASUREMENT_ID == "final_scope_widget_e2e_retry3"
    assert RETRY1_ATTEMPT_MARKER_PATH != LIVE_ATTEMPT_MARKER_PATH
    assert RETRY2_ATTEMPT_MARKER_PATH != LIVE_ATTEMPT_MARKER_PATH
    assert RETRY3_ATTEMPT_MARKER_PATH != LIVE_ATTEMPT_MARKER_PATH
    assert all("retry4" in str(path) for path in DEFAULT_LIVE_ARTIFACT_PATHS)
    assert RETRY1_ATTEMPT_MARKER_PATH.is_file()
    assert RETRY2_ATTEMPT_MARKER_PATH.is_file()
    assert RETRY3_ATTEMPT_MARKER_PATH.is_file()


def test_retry4_live_artifacts_present_post_live() -> None:
    assert_frozen_retry4_live_artifacts_unchanged()
    assert LIVE_ATTEMPT_MARKER_PATH.is_file()


def test_retry4_attempt_marker_role_counts_match_completed_ledger() -> None:
    marker = json.loads(LIVE_ATTEMPT_MARKER_PATH.read_text(encoding="utf-8"))
    assert marker["status"] == "attempt_completed"
    assert marker["completed_provider_calls"] == CORRECTED_RETRY4_LEDGER_TOTAL
    assert marker["role_counts"] == CORRECTED_RETRY4_LEDGER_ROLE_COUNTS
    assert marker["manual_review_rubric"] == {
        "1": "compact_overview",
        "2": "full_arch_prices",
        "6": "concise_stage_clarification",
        "7": "crown_price",
    }


def test_retry4_stdout_size_pinned() -> None:
    assert LIVE_STDOUT_LOG_PATH.is_file()
    assert LIVE_STDOUT_LOG_PATH.stat().st_size == FROZEN_RETRY4_LIVE_STDOUT_SIZE
    assert sha256_file_hex(LIVE_STDOUT_LOG_PATH) == (
        FROZEN_RETRY4_LIVE_ARTIFACT_SHA256[
            "evals/v5/artifacts/final_scope_widget_e2e_retry4_live_stdout.log"
        ]
    )


def test_retry4_ledger_sha_pinned() -> None:
    assert LIVE_CALL_LEDGER_PATH.is_file()
    assert sha256_file_hex(LIVE_CALL_LEDGER_PATH) == (
        FROZEN_RETRY4_LIVE_ARTIFACT_SHA256[
            "evals/v5/artifacts/final_scope_widget_e2e_retry4_call_ledger.jsonl"
        ]
    )


def test_retry4_budget_planner_and_manual_rubric() -> None:
    assert MAX_PROVIDER_CALLS == 34
    assert MAX_INGRESS_CALLS == 5
    assert MAX_PLANNER_CALLS == 5
    assert MAX_BOUNDARY_CALLS == 8
    assert MAX_COMPOSER_CALLS == 8
    assert MAX_VERIFIER_CALLS == 8
    assert MAX_HTTP_TURNS == 8
    assert RETRY_COUNT_MAX == 0
    assert OWNER_APPROVED_PLANNER_MODEL == "qwen3.7-plus"
    assert EXPECTED_FREE_TEXT_PLANNER_CALLS == 5
    assert TYPED_UI_TURNS_NO_PLANNER == frozenset({2, 6, 7})
    assert MANUAL_REVIEW_RUBRIC == {
        1: "compact_overview",
        2: "full_arch_prices",
        6: "concise_stage_clarification",
        7: "crown_price",
    }
    assert (
        MAX_INGRESS_CALLS
        + MAX_PLANNER_CALLS
        + MAX_BOUNDARY_CALLS
        + MAX_COMPOSER_CALLS
        + MAX_VERIFIER_CALLS
    ) == MAX_PROVIDER_CALLS
