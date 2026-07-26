"""PRE-CODE / COMPLETION checker for FINAL_SCOPE_WIDGET_E2E_RETRY3 pre-live."""

from __future__ import annotations

from pathlib import Path

from evals.v5.final_scope_widget_e2e_live_contract import FROZEN_TURNS_HASH, sha256_file_hex
from evals.v5.final_scope_widget_e2e_retry1_live_contract import (
    LIVE_ATTEMPT_MARKER_PATH as RETRY1_ATTEMPT_MARKER_PATH,
)
from evals.v5.final_scope_widget_e2e_retry2_live_contract import (
    LIVE_ATTEMPT_MARKER_PATH as RETRY2_ATTEMPT_MARKER_PATH,
)
from evals.v5.final_scope_widget_e2e_retry3_live_contract import (
    DEFAULT_LIVE_ARTIFACT_PATHS,
    EXPECTED_FREE_TEXT_PLANNER_CALLS,
    LIVE_ATTEMPT_MARKER_PATH,
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
    assert_frozen_s62_live_artifacts_unchanged,
    assert_frozen_s63_live_artifacts_unchanged,
    assert_frozen_suite_unchanged,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]

SEAM_AUDIT_PATH = (
    _REPO_ROOT
    / "docs"
    / "evidence"
    / "final_scope"
    / "FINAL_SCOPE_WIDGET_E2E_RETRY3_SEAM_AUDIT.md"
)


def test_seam_audit_exists() -> None:
    assert SEAM_AUDIT_PATH.is_file()
    text = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    assert "retry3" in text
    assert "b4b47bc" in text
    assert "TYPED_UI" in text or "typed UI" in text


def test_frozen_retry1_and_retry2_live_artifacts_unchanged() -> None:
    assert_frozen_retry1_live_artifacts_unchanged()
    assert_frozen_retry2_live_artifacts_unchanged()


def test_frozen_widget_e2e_turn_matrix_unchanged() -> None:
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH


def test_frozen_neighbor_suites_unchanged() -> None:
    assert_frozen_preflight_abort_artifacts_unchanged()
    assert_frozen_s62_live_artifacts_unchanged()
    assert_frozen_s63_live_artifacts_unchanged()
    assert_frozen_suite_unchanged()


def test_retry3_namespace_isolated() -> None:
    assert MEASUREMENT_ID == "final_scope_widget_e2e_retry3"
    assert PARENT_MEASUREMENT_ID == "final_scope_widget_e2e_retry2"
    assert RETRY1_ATTEMPT_MARKER_PATH != LIVE_ATTEMPT_MARKER_PATH
    assert RETRY2_ATTEMPT_MARKER_PATH != LIVE_ATTEMPT_MARKER_PATH
    assert all("retry3" in str(path) for path in DEFAULT_LIVE_ARTIFACT_PATHS)
    assert RETRY1_ATTEMPT_MARKER_PATH.is_file()
    assert RETRY2_ATTEMPT_MARKER_PATH.is_file()


def test_retry3_live_artifacts_present_post_live() -> None:
    assert_frozen_retry3_live_artifacts_unchanged()
    assert LIVE_ATTEMPT_MARKER_PATH.is_file()


def test_retry3_budget_and_planner_expectations() -> None:
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
    assert (
        MAX_INGRESS_CALLS
        + MAX_PLANNER_CALLS
        + MAX_BOUNDARY_CALLS
        + MAX_COMPOSER_CALLS
        + MAX_VERIFIER_CALLS
    ) == MAX_PROVIDER_CALLS
