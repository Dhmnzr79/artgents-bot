"""PRE-CODE checker for FINAL_PRICE_SCOPE_COVERAGE_NAV governance."""

from __future__ import annotations

from pathlib import Path

from evals.v5.final_scope_widget_e2e_live_contract import FROZEN_TURNS_HASH, sha256_file_hex
from evals.v5.final_scope_widget_e2e_retry4_live_contract import (
    assert_frozen_retry4_live_artifacts_unchanged,
)
from tests.test_ac3_scope_price_flow_offline import test_w1b_snapshot_checksums_unchanged
from tests.test_final_price_and_service_coverage_implementation import (
    test_frozen_pins_unchanged as test_fps_frozen_pins_unchanged,
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
    / "FINAL_PRICE_SCOPE_COVERAGE_NAV_SEAM_AUDIT.md"
)
ARCH_PATH = _REPO_ROOT / "docs" / "PRICE_SERVICE_ARCHITECTURE.md"
TASK_PATH = _REPO_ROOT / "TASK.md"
GOVERNANCE_BASELINE_HEAD = "f5c5c96"


def test_seam_audit_exists_and_covers_scope_nav_gap() -> None:
    assert SEAM_AUDIT_PATH.is_file()
    text = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    assert GOVERNANCE_BASELINE_HEAD in text
    assert "few_teeth" in text
    assert "applies_to_extents" in text
    assert "service applicability" in text.lower() or "service-level" in text.lower()
    assert "offer" in text.lower()
    assert "materialize_scope_nav_followups" in text
    assert "family_only_broad" in text
    assert "Acceptance matrix" in text or "acceptance matrix" in text.lower()
    assert "data_gap" in text


def test_task_governance_section_and_acceptance_matrix() -> None:
    text = TASK_PATH.read_text(encoding="utf-8")
    assert "FINAL_PRICE_SCOPE_COVERAGE_NAV" in text
    assert GOVERNANCE_BASELINE_HEAD in text
    assert "PRE-CODE" in text
    assert "test_final_price_scope_coverage_nav_governance.py" in text
    assert "applies_to_extents" in text
    for case_id in ("A.", "B.", "C.", "D.", "E.", "F.", "G.", "H.", "I.", "J."):
        assert case_id in text or f"| {case_id[0]} |" in text
    assert "NO LIVE" in text
    assert "NO LLM" in text


def test_canonical_architecture_doc_referenced() -> None:
    assert ARCH_PATH.is_file()
    arch = ARCH_PATH.read_text(encoding="utf-8")
    assert "few_teeth" in arch
    seam = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    assert "PRICE_SERVICE_ARCHITECTURE.md" in seam


def test_frozen_artifact_guards() -> None:
    test_frozen_retry4_artifacts_unchanged_after_closeout()
    test_w1b_snapshot_checksums_unchanged()
    test_fps_frozen_pins_unchanged()
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH
    assert_frozen_retry4_live_artifacts_unchanged()


def test_implementation_artifacts_present_post_phase2() -> None:
    impl_test = _REPO_ROOT / "tests" / "test_final_price_scope_coverage_nav_implementation.py"
    extent_module = _REPO_ROOT / "core" / "target_offer_extent_applicability.py"
    assert impl_test.is_file(), "implementation tests must exist after Phase 2"
    assert extent_module.is_file(), "extent applicability module must exist after Phase 2"
