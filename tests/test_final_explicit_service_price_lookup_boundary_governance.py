"""PRE-CODE checker for FINAL_EXPLICIT_SERVICE_PRICE_LOOKUP_BOUNDARY governance."""

from __future__ import annotations

from pathlib import Path

from evals.v5.final_scope_widget_e2e_live_contract import FROZEN_TURNS_HASH, sha256_file_hex
from evals.v5.final_scope_widget_e2e_retry4_live_contract import (
    assert_frozen_retry4_live_artifacts_unchanged,
)
from tests.test_ac3_scope_price_flow_offline import test_w1b_snapshot_checksums_unchanged
from tests.test_final_price_scope_coverage_nav_implementation import (
    test_frozen_pins_unchanged as test_pscn_frozen_pins_unchanged,
)
from tests.test_final_scope_widget_e2e_closeout_implementation import (
    test_frozen_retry4_artifacts_unchanged_after_closeout,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]

SEAM_AUDIT_PATH = (
    _REPO_ROOT
    / "docs"
    / "evidence"
    / "price_service"
    / "FINAL_EXPLICIT_SERVICE_PRICE_LOOKUP_BOUNDARY_SEAM_AUDIT.md"
)
ARCH_PATH = _REPO_ROOT / "docs" / "PRICE_SERVICE_ARCHITECTURE.md"
TASK_PATH = _REPO_ROOT / "TASK.md"
GOVERNANCE_BASELINE_HEAD = "19297fc"


def test_seam_audit_exists_and_covers_lookup_applicability_gap() -> None:
    assert SEAM_AUDIT_PATH.is_file()
    text = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    assert GOVERNANCE_BASELINE_HEAD in text
    assert "one_stage" in text
    assert "full_arch" in text
    assert "lookup" in text.lower()
    assert "applicability" in text.lower()
    assert "target_fullcontext_error" in text
    assert "filter_applicable_services" in text
    assert "project_target_service_offers" in text
    assert "extent_axis" in text or "provenance" in text.lower()
    assert "session" in text.lower()
    assert "data_gap" in text
    assert "Acceptance matrix" in text or "acceptance matrix" in text.lower()


def test_task_governance_section_and_acceptance_matrix() -> None:
    text = TASK_PATH.read_text(encoding="utf-8")
    assert "FINAL_EXPLICIT_SERVICE_PRICE_LOOKUP_BOUNDARY" in text
    assert GOVERNANCE_BASELINE_HEAD in text
    assert "PRE-CODE" in text
    assert "test_final_explicit_service_price_lookup_boundary_governance.py" in text
    assert "explicit service price lookup" in text.lower() or "explicit_service_price_lookup" in text
    assert "lookup" in text.lower() and "applicability" in text.lower()
    for n in range(1, 19):
        assert f"| {n} |" in text
    assert "cross-turn" in text.lower() or "Cross-turn" in text
    assert "NO LIVE" in text
    assert "NO LLM" in text
    assert "one_stage" in text and "hardcode" in text.lower()


def test_canonical_architecture_doc_referenced() -> None:
    assert ARCH_PATH.is_file()
    seam = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    assert "PRICE_SERVICE_ARCHITECTURE.md" in seam


def test_frozen_artifact_guards() -> None:
    test_frozen_retry4_artifacts_unchanged_after_closeout()
    test_w1b_snapshot_checksums_unchanged()
    test_pscn_frozen_pins_unchanged()
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH
    assert_frozen_retry4_live_artifacts_unchanged()


def test_implementation_artifacts_present_post_phase2() -> None:
    impl_test = (
        _REPO_ROOT
        / "tests"
        / "test_final_explicit_service_price_lookup_boundary_implementation.py"
    )
    sparse_test = (
        _REPO_ROOT
        / "tests"
        / "test_final_explicit_service_price_lookup_boundary_sparse_fixtures.py"
    )
    matrix_test = (
        _REPO_ROOT
        / "tests"
        / "test_final_explicit_service_price_lookup_boundary_cross_turn_matrix.py"
    )
    boundary = _REPO_ROOT / "core" / "target_explicit_service_price_lookup.py"
    assert impl_test.is_file(), "implementation tests must exist after Phase 2"
    assert sparse_test.is_file(), "sparse fixtures must exist after Phase 2"
    assert matrix_test.is_file(), "cross-turn matrix must exist after Phase 2"
    assert boundary.is_file(), "boundary module must exist after Phase 2"
