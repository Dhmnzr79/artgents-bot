"""PRE-CODE checker for FINAL_PRICE_AND_SERVICE_COVERAGE governance."""

from __future__ import annotations

from pathlib import Path

from evals.v5.final_scope_widget_e2e_live_contract import FROZEN_TURNS_HASH, sha256_file_hex
from evals.v5.final_scope_widget_e2e_retry4_live_contract import (
    assert_frozen_retry4_live_artifacts_unchanged,
)
from tests.test_ac3_scope_price_flow_offline import test_w1b_snapshot_checksums_unchanged
from tests.test_final_scope_widget_e2e_closeout_implementation import (
    test_frozen_retry4_artifacts_unchanged_after_closeout,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]

SEAM_AUDIT_PATH = (
    _REPO_ROOT
    / "docs"
    / "evidence"
    / "price_service"
    / "FINAL_PRICE_AND_SERVICE_COVERAGE_SEAM_AUDIT.md"
)
ARCH_PATH = _REPO_ROOT / "docs" / "PRICE_SERVICE_ARCHITECTURE.md"
TASK_PATH = _REPO_ROOT / "TASK.md"
GOVERNANCE_BASELINE_HEAD = "696f77d"


def test_seam_audit_exists_and_covers_four_situations() -> None:
    assert SEAM_AUDIT_PATH.is_file()
    text = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    assert GOVERNANCE_BASELINE_HEAD in text
    assert "696f77d" in text
    assert "no_public_price" in text
    assert "service_not_offered" in text
    assert "family-level" in text.lower() or "family level" in text.lower()
    assert "family_prices.json" in text
    assert "applies_to_service_ids" in text
    assert "Mode A" in text or "scope-specific" in text
    assert "Mode B" in text or "family-only" in text
    assert "precedence" in text.lower()
    assert "Acceptance matrix" in text or "acceptance matrix" in text.lower()


def test_task_governance_section_and_acceptance_matrix() -> None:
    text = TASK_PATH.read_text(encoding="utf-8")
    assert "FINAL_PRICE_AND_SERVICE_COVERAGE" in text
    assert GOVERNANCE_BASELINE_HEAD in text
    assert "PRE-CODE" in text
    assert "test_final_price_and_service_coverage_governance.py" in text
    for case_id in ("A.", "B.", "C.", "D.", "E.", "F.", "G.", "H.", "I.", "J.", "K.", "L."):
        assert case_id in text or f"| {case_id[0]} |" in text
    assert "family_prices.json" in text
    assert "NO LIVE" in text
    assert "NO LLM" in text
    assert "Retry5" in text or "RETRY5" in text.upper()


def test_canonical_architecture_doc_referenced() -> None:
    assert ARCH_PATH.is_file()
    arch = ARCH_PATH.read_text(encoding="utf-8")
    assert "no_public_price" in arch
    seam = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    assert "PRICE_SERVICE_ARCHITECTURE.md" in seam


def test_frozen_artifact_guards() -> None:
    test_frozen_retry4_artifacts_unchanged_after_closeout()
    test_w1b_snapshot_checksums_unchanged()
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH
    assert_frozen_retry4_live_artifacts_unchanged()


def test_implementation_artifacts_present_post_phase2() -> None:
    impl_test = _REPO_ROOT / "tests" / "test_final_price_and_service_coverage_implementation.py"
    family_resolution = _REPO_ROOT / "core" / "target_family_price_resolution.py"
    assert impl_test.is_file(), "implementation tests must exist after Phase 2"
    assert family_resolution.is_file(), "family price resolution module must exist after Phase 2"
