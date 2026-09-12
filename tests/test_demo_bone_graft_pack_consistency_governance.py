"""PRE-CODE checker for DEMO_BONE_GRAFT_PACK_CONSISTENCY governance (Phase 1 only)."""

from __future__ import annotations

import re
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
    / "client_pack"
    / "DEMO_BONE_GRAFT_PACK_CONSISTENCY_SEAM_AUDIT.md"
)
TASK_PATH = _REPO_ROOT / "TASK.md"
GOVERNANCE_BASELINE_HEAD = "18e4d47"
PRIOR_COMPLETION_BASE = "204da81"

WIDE_TEST_PATHS = [
    "tests/test_final_client_pack_data_convergence_b_governance.py",
    "tests/test_final_client_pack_data_convergence_governance.py",
    "tests/test_final_client_pack_data_convergence_reader_cutover.py",
    "tests/test_final_client_pack_data_convergence_sparse_pack.py",
    "tests/test_validate_client_pack.py",
    "tests/test_client_pack_template_scaffold.py",
    "tests/test_turn_planner_llm.py",
    "tests/test_turn_planner_wiring.py",
    "tests/test_catalog_match.py",
    "tests/test_follow_up_rewrite.py",
    "tests/test_dialog_focus_baseline.py",
    "tests/test_dialog_focus_contract.py",
    "tests/test_demo_doctor_catalog.py",
    "tests/test_demo_doctor_template.py",
    "tests/test_demo_target_service_catalog.py",
    "tests/test_demo_target_price_offers.py",
    "tests/test_demo_target_marketing_policy.py",
    "tests/test_demo_target_marketing_migration_audit.py",
    "tests/test_response_schema_loader.py",
    "tests/test_target_scope_aware_selection_offline.py",
    "tests/test_final_price_and_service_coverage_implementation.py",
    "tests/test_final_price_scope_coverage_nav_implementation.py",
    "tests/test_final_explicit_service_price_lookup_boundary_implementation.py",
    "tests/test_c2_import_firewall_offline.py",
    "tests/test_price_ref_routing.py",
    "tests/test_content_linter.py",
]

FAILURE_TESTS = [
    "test_demo_doctor_catalog",
    "test_demo_doctor_template",
    "test_demo_target_service_catalog",
    "test_demo_target_price_offers",
    "test_demo_target_marketing_policy",
    "test_demo_target_marketing_migration_audit",
]


def test_seam_audit_exists_and_classifies_six_failures() -> None:
    assert SEAM_AUDIT_PATH.is_file()
    text = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    assert GOVERNANCE_BASELINE_HEAD in text
    assert PRIOR_COMPLETION_BASE in text
    for test_name in FAILURE_TESTS:
        assert test_name in text
    for label in (
        "actual demo-data gap",
        "architectural hardcode",
        "historical fixture",
        "stale test",
    ):
        assert label in text.lower()
    assert "bone_graft" in text
    assert "no_public_price" in text
    assert "doctors__doctor__orlov" in text
    assert "doctors__doctor__volkov" in text
    assert "NO PRODUCT" in text.upper() or "no product code" in text.lower()
    assert "NO LIVE" in text


def test_task_governance_section_and_acceptance_matrix() -> None:
    text = TASK_PATH.read_text(encoding="utf-8")
    assert "DEMO_BONE_GRAFT_PACK_CONSISTENCY" in text
    assert GOVERNANCE_BASELINE_HEAD in text
    assert "PRE-CODE" in text
    assert "test_demo_bone_graft_pack_consistency_governance.py" in text
    assert "bone_graft" in text
    assert "no_public_price" in text
    section = text.split("# TASK — DEMO_BONE_GRAFT_PACK_CONSISTENCY (governance)")[-1]
    task_tail = section
    wide_block = task_tail.split("```powershell", 1)[-1].split("```", 1)[0]
    assert "test_turn_plan_protocol_guard.py" not in wide_block
    for n in range(1, 15):
        assert f"| {n} |" in section
    assert "NO LIVE" in section
    assert "NO LLM" in section


def test_owner_sign_off_table_and_doctor_mapping() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    task = TASK_PATH.read_text(encoding="utf-8")
    combined = audit + "\n" + task
    assert "Owner sign-off" in combined or "owner sign-off" in combined.lower()
    assert "PENDING" in combined
    assert "doctors__doctor__orlov" in combined
    assert "doctors__doctor__volkov" in combined
    assert "kuznetsov" in combined.lower()
    assert "Кто делает костную пластику" in combined or "bone graft doctors" in combined.lower()


def test_corrected_wide_command_paths_exist() -> None:
    task_tail = TASK_PATH.read_text(encoding="utf-8").split(
        "# TASK — DEMO_BONE_GRAFT_PACK_CONSISTENCY (governance)"
    )[-1]
    missing = [path for path in WIDE_TEST_PATHS if not (_REPO_ROOT / path).is_file()]
    assert not missing, f"missing wide paths: {missing}"
    wide_block = task_tail.split("```powershell", 1)[-1].split("```", 1)[0]
    assert "test_turn_plan_protocol_guard.py" not in wide_block
    for path in WIDE_TEST_PATHS:
        assert path in task_tail


def test_prior_milestone_post_push_verdict_recorded() -> None:
    text = TASK_PATH.read_text(encoding="utf-8")
    section = text.split("DEMO_BONE_GRAFT_PACK_CONSISTENCY")[0]
    assert PRIOR_COMPLETION_BASE in section
    assert "18e4d47" in section
    assert "24/24" in section or "24 passed" in section.lower()


def test_normative_no_fictitious_price_promo_doctor() -> None:
    audit = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    task = TASK_PATH.read_text(encoding="utf-8")
    combined = re.sub(r"\*+", "", audit + "\n" + task).lower()
    required = (
        "no_public_price",
        "no fictitious",
        "fictitious",
        "bone_graft-specific promotion",
        "sinus_lift",
        "42000",
        "68000",
        "unit_labels",
        "demo_legacy_marketing",
        "facts.json",
        "tomography",
    )
    for phrase in required:
        assert phrase in combined, phrase


def test_frozen_artifact_guards() -> None:
    test_frozen_retry4_artifacts_unchanged_after_closeout()
    test_w1b_snapshot_checksums_unchanged()
    test_pscn_frozen_pins_unchanged()
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH
    assert_frozen_retry4_live_artifacts_unchanged()
