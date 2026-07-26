"""PRE-CODE checker for FINAL_PROSTHETICS_PRICE_NAV_REACHABILITY governance."""

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
    / "FINAL_PROSTHETICS_PRICE_NAV_REACHABILITY_SEAM_AUDIT.md"
)
ARCH_PATH = _REPO_ROOT / "docs" / "PRICE_SERVICE_ARCHITECTURE.md"
TASK_PATH = _REPO_ROOT / "TASK.md"
GOVERNANCE_BASELINE_HEAD = "2b5e90d"


def test_seam_audit_exists_and_covers_reachability_gap() -> None:
    assert SEAM_AUDIT_PATH.is_file()
    text = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    assert GOVERNANCE_BASELINE_HEAD in text
    assert "one_tooth" in text
    assert "navigable" in text.lower()
    assert "immediate" in text.lower()
    assert "offer_id" in text
    assert "inference" in text.lower()
    assert "discover_stage_clarification_stages" in text
    assert "UiStageAction" in text
    assert "25000" in text or "25 000" in text
    assert "31000" in text or "31 000" in text
    assert "few_teeth" in text
    assert "implantation" in text.lower()
    assert "Acceptance matrix" in text or "acceptance matrix" in text.lower()


def test_task_governance_section_and_acceptance_matrix() -> None:
    text = TASK_PATH.read_text(encoding="utf-8")
    assert "FINAL_PROSTHETICS_PRICE_NAV_REACHABILITY" in text
    assert GOVERNANCE_BASELINE_HEAD in text
    assert "PRE-CODE" in text
    assert "test_final_prosthetics_price_nav_reachability_governance.py" in text
    assert "price_navigable" in text.lower() or "navigable" in text.lower()
    assert "applies_to_extents" in text
    for n in range(1, 17):
        assert f"| {n} |" in text or f"{n}." in text
    assert "NO LIVE" in text
    assert "NO LLM" in text
    assert "offer_id" in text and "inference" in text.lower()


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


def test_implementation_module_present_post_code() -> None:
    impl_test = (
        _REPO_ROOT
        / "tests"
        / "test_final_prosthetics_price_nav_reachability_implementation.py"
    )
    reachability = _REPO_ROOT / "core" / "target_offer_price_reachability.py"
    assert impl_test.is_file(), "implementation tests must exist after PRE-CODE"
    assert reachability.is_file(), "reachability module must exist after PRE-CODE"
