"""PRE-CODE / COMPLETION checker for FINAL_SCOPE_WIDGET_E2E_RETRY2 pre-live."""

from __future__ import annotations

from pathlib import Path

from evals.v5.final_scope_widget_e2e_live_contract import (
    FROZEN_TURNS_HASH,
    MAX_HTTP_TURNS,
    MAX_PROVIDER_CALLS,
    OWNER_APPROVED_PLANNER_MODEL,
    RETRY_COUNT_MAX,
    sha256_file_hex,
)
from evals.v5.final_scope_widget_e2e_retry1_live_contract import (
    LIVE_ATTEMPT_MARKER_PATH as RETRY1_ATTEMPT_MARKER_PATH,
    LIVE_RAW_ARTIFACT_PATH as RETRY1_RAW_ARTIFACT_PATH,
)
from evals.v5.final_scope_widget_e2e_retry2_live_contract import (
    DEFAULT_LIVE_ARTIFACT_PATHS,
    LIVE_ATTEMPT_MARKER_PATH,
    MEASUREMENT_ID,
    PARENT_MEASUREMENT_ID,
    VERIFIED_FORENSIC_RETRY1_STDOUT_PATH,
    VERIFIED_FORENSIC_RETRY1_STDOUT_SHA256,
    VERIFIED_FORENSIC_RETRY1_STDOUT_SIZE,
    assert_frozen_preflight_abort_artifacts_unchanged,
    assert_frozen_retry1_live_artifacts_unchanged,
    assert_frozen_s62_live_artifacts_unchanged,
    assert_frozen_s63_live_artifacts_unchanged,
    assert_frozen_suite_unchanged,
    assert_retry2_live_artifacts_absent,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]

SEAM_AUDIT_PATH = (
    _REPO_ROOT
    / "docs"
    / "evidence"
    / "final_scope"
    / "FINAL_SCOPE_WIDGET_E2E_RETRY2_SEAM_AUDIT.md"
)


def test_seam_audit_exists() -> None:
    assert SEAM_AUDIT_PATH.is_file()
    text = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    assert "retry2" in text
    assert "c670b96" in text
    assert "POST_RETRY1" in text or "product correction" in text.lower()


def test_frozen_retry1_live_artifacts_unchanged() -> None:
    assert_frozen_retry1_live_artifacts_unchanged()


def test_frozen_widget_e2e_turn_matrix_unchanged() -> None:
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH


def test_frozen_neighbor_suites_unchanged() -> None:
    assert_frozen_preflight_abort_artifacts_unchanged()
    assert_frozen_s62_live_artifacts_unchanged()
    assert_frozen_s63_live_artifacts_unchanged()
    assert_frozen_suite_unchanged()


def test_retry2_namespace_isolated_from_retry1() -> None:
    assert MEASUREMENT_ID == "final_scope_widget_e2e_retry2"
    assert PARENT_MEASUREMENT_ID == "final_scope_widget_e2e_retry1"
    assert RETRY1_ATTEMPT_MARKER_PATH != LIVE_ATTEMPT_MARKER_PATH
    assert RETRY1_RAW_ARTIFACT_PATH not in DEFAULT_LIVE_ARTIFACT_PATHS
    assert all("retry2" in str(path) for path in DEFAULT_LIVE_ARTIFACT_PATHS)
    assert RETRY1_ATTEMPT_MARKER_PATH.is_file()
    assert RETRY1_RAW_ARTIFACT_PATH.is_file()


def test_retry2_live_artifacts_absent_pre_live() -> None:
    assert_retry2_live_artifacts_absent()


def test_retry2_budget_and_authority_constants() -> None:
    assert MAX_PROVIDER_CALLS == 40
    assert MAX_HTTP_TURNS == 8
    assert RETRY_COUNT_MAX == 0
    assert OWNER_APPROVED_PLANNER_MODEL == "qwen3.7-plus"


def test_forensic_retry1_stdout_verified_and_removed() -> None:
    """UTF-16 forensic duplicate verified at RETRY2 checkpoint; must not remain on disk."""
    assert not VERIFIED_FORENSIC_RETRY1_STDOUT_PATH.exists()
    assert VERIFIED_FORENSIC_RETRY1_STDOUT_SHA256 == (
        "d3e3f159e37e94e0f04b6e1e30a6a7675a2c093c9121f72d78248813c9c3f946"
    )
    assert VERIFIED_FORENSIC_RETRY1_STDOUT_SIZE == 634_914
