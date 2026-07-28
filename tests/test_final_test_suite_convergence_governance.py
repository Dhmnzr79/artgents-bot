"""Governance checker for FINAL_TEST_SUITE_CONVERGENCE (Phase 1 + TSC-A closeout)."""

from __future__ import annotations

import json
import subprocess
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
    / "testing"
    / "FINAL_TEST_SUITE_CONVERGENCE_SEAM_AUDIT.md"
)
ARCHITECTURE_PATH = _REPO_ROOT / "docs" / "TEST_SUITE_ARCHITECTURE.md"
INVENTORY_PATH = _REPO_ROOT / "docs" / "evidence" / "testing" / "final_test_failure_inventory.json"
DELTA_PATH = _REPO_ROOT / "drafts" / "wide_two_head_delta_classification.json"
DELTA_AUDIT_PATH = _REPO_ROOT / "drafts" / "EXACT_WIDE_TWO_HEAD_DELTA_AUDIT.md"
TASK_PATH = _REPO_ROOT / "TASK.md"
GOVERNANCE_BASELINE_HEAD = "1980ab7"
TSC_A_HEAD = "d9e69f9"
MILESTONE = "FINAL_TEST_SUITE_CONVERGENCE"
TSC_A_INVENTORY_COUNT = 38
EXPECTED_CURRENT_FAILURES = 185
EXPECTED_FAIL_BOTH = 178


def _load_inventory() -> dict:
    return json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))


def test_seam_audit_exists_and_covers_convergence() -> None:
    assert SEAM_AUDIT_PATH.is_file()
    text = SEAM_AUDIT_PATH.read_text(encoding="utf-8")
    assert GOVERNANCE_BASELINE_HEAD in text
    for phrase in (
        "current_safe_offline",
        "historical_frozen_contracts",
        "live_owner_gated",
        "TSC-A",
        "TSC-B",
        "TSC-C",
        "TSC-D",
        "54→55",
        "638→661",
        "rate-limit",
        "_IP_RATE_BUCKETS",
        "marketing_scenarios",
        "185",
        "NO LIVE",
        "NO product changes",
    ):
        assert phrase in text, phrase
    for section in (
        "## 1. Mutable demo-pack guards",
        "## 2. Rate-limit pollution",
        "## 3. Frozen / shadow / preservation",
        "## Implementation checkpoints",
        "## Forbidden solutions",
    ):
        assert section in text, section


def test_architecture_doc_exists() -> None:
    assert ARCHITECTURE_PATH.is_file()
    text = ARCHITECTURE_PATH.read_text(encoding="utf-8")
    for phrase in (
        "current_safe_offline",
        "historical_frozen_contracts",
        "live_owner_gated",
        "testpaths",
        "docs/artifacts",
    ):
        assert phrase in text, phrase


def test_inventory_covers_all_current_failures() -> None:
    inventory = _load_inventory()
    assert inventory["failure_count"] == EXPECTED_CURRENT_FAILURES
    assert len(inventory["entries"]) == EXPECTED_CURRENT_FAILURES
    nodeids = {e["nodeid"] for e in inventory["entries"]}
    assert len(nodeids) == EXPECTED_CURRENT_FAILURES


def test_inventory_counts_match_delta_audit() -> None:
    inventory = _load_inventory()
    delta = json.loads(DELTA_PATH.read_text(encoding="utf-8"))
    assert inventory["totals"]["current"]["failed"] == delta["totals"]["current"]["failed"]
    assert inventory["delta_bucket_sizes"]["FAIL_BOTH"] == delta["bucket_sizes"]["FAIL_BOTH"]
    assert inventory["delta_bucket_sizes"]["PASS_BASELINE_FAIL_CURRENT"] == delta["bucket_sizes"][
        "PASS_BASELINE_FAIL_CURRENT"
    ]
    fail_both_inv = sum(1 for e in inventory["entries"] if e["delta_status"] == "FAIL_BOTH")
    assert fail_both_inv == EXPECTED_FAIL_BOTH


def test_every_nodeid_has_action_and_checkpoint() -> None:
    allowed_actions = {
        "KEEP_AS_IS",
        "UPDATE_ASSERTION",
        "FIX_TEST_ISOLATION",
        "FIX_HISTORICAL_CONTRACT",
        "DELETE_ORPHAN_TEST",
        "PRODUCT_BUG_FUTURE",
    }
    allowed_checkpoints = {"TSC-A", "TSC-B", "TSC-C", "TSC-D"}
    for entry in _load_inventory()["entries"]:
        assert entry["action"] in allowed_actions, entry["nodeid"]
        assert entry["checkpoint"] in allowed_checkpoints, entry["nodeid"]
        assert entry["bucket"] in {
            "current_safe_offline",
            "historical_frozen_contracts",
            "live_owner_gated",
        }
        assert entry["files"], entry["nodeid"]


def test_frozen_artifacts_not_in_update_assertion_allowlists() -> None:
    frozen_tokens = ("evals/v5/", "FROZEN_", "docs/evidence/")
    for entry in _load_inventory()["entries"]:
        if entry["action"] != "UPDATE_ASSERTION":
            continue
        if "frozen_pins_unchanged" in entry["nodeid"]:
            continue
        combined = " ".join(entry["files"]) + entry["nodeid"]
        for token in frozen_tokens:
            assert token not in combined, f"frozen path in UPDATE_ASSERTION: {entry['nodeid']}"


def test_no_new_skip_xfail_in_task_section() -> None:
    section = TASK_PATH.read_text(encoding="utf-8").split(f"# TASK — {MILESTONE} (governance)")[-1]
    section_lower = section.lower()
    assert "pytest.mark.skip" not in section_lower
    assert "pytest.mark.xfail" not in section_lower


def test_tsc_a_complete() -> None:
    conftest = _REPO_ROOT / "tests" / "conftest.py"
    assert conftest.is_file()
    text = conftest.read_text(encoding="utf-8")
    assert "_IP_RATE_BUCKETS" in text
    assert "clear()" in text
    section = TASK_PATH.read_text(encoding="utf-8").split(f"# TASK — {MILESTONE} (governance)")[-1]
    assert "TSC-A" in section
    assert "COMPLETE" in section
    assert TSC_A_HEAD in section
    assert "tests/conftest.py" in section


def test_tsc_b_not_started() -> None:
    section = TASK_PATH.read_text(encoding="utf-8").split(f"# TASK — {MILESTONE} (governance)")[-1]
    assert "TSC-B" in section
    assert "NOT STARTED" in section
    tsc_b_block = section.split("### TSC-B", 1)[1].split("### TSC-C", 1)[0]
    assert "COMPLETE" not in tsc_b_block
    proc = subprocess.run(
        ["git", "diff", "--name-only", f"{TSC_A_HEAD}..HEAD", "--", "tests/test_planner_attempt_contract.py"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_task_governance_section_and_checkpoints() -> None:
    text = TASK_PATH.read_text(encoding="utf-8")
    section = text.split(f"# TASK — {MILESTONE} (governance)")[-1]
    assert MILESTONE in text
    assert GOVERNANCE_BASELINE_HEAD in text
    assert TSC_A_HEAD in section
    assert "PRE-CODE" in text
    assert "test_final_test_suite_convergence_governance.py" in text
    assert "final_test_failure_inventory.json" in text
    for cp in ("TSC-A", "TSC-B", "TSC-C", "TSC-D"):
        assert cp in section
    assert "NO LIVE" in section
    assert "TSC-A" in section and "COMPLETE" in section
    assert "TSC-B" in section and "NOT STARTED" in section


def test_tsc_a_inventory_nodeids_green() -> None:
    nodeids = [
        e["nodeid"]
        for e in _load_inventory()["entries"]
        if e["checkpoint"] == "TSC-A"
    ]
    assert len(nodeids) == TSC_A_INVENTORY_COUNT
    proc = subprocess.run(
        ["python", "-m", "pytest", *nodeids, "-q"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_delta_artifacts_present() -> None:
    for path in (DELTA_PATH, DELTA_AUDIT_PATH):
        assert path.is_file(), path


def test_checkpoint_allowlists_documented_in_task() -> None:
    section = TASK_PATH.read_text(encoding="utf-8").split(f"# TASK — {MILESTONE} (governance)")[-1]
    for needle in (
        "tests/conftest.py",
        "test_turn_planner_llm.py",
        "test_patient_scope_shadow_eval_contract.py",
        "test_final_scope_widget_e2e_live_harness.py",
    ):
        assert needle in section, needle


def test_frozen_pins_unchanged() -> None:
    test_w1b_snapshot_checksums_unchanged()
    test_pscn_frozen_pins_unchanged()
    test_frozen_retry4_artifacts_unchanged_after_closeout()
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH
    assert_frozen_retry4_live_artifacts_unchanged()


def test_git_diff_check_clean() -> None:
    proc = subprocess.run(
        ["git", "diff", "--check"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_pack_drift_nodeids_classified_update_assertion() -> None:
    pack_nodeids = {
        "tests/test_target_cached_full_context.py::test_demo_corpus_document_count_and_doctors_inclusion",
        "tests/test_turn_planner_llm.py::test_current_demo_compact_reference_and_catalog_drift_guard",
    }
    by_id = {e["nodeid"]: e for e in _load_inventory()["entries"]}
    for nid in pack_nodeids:
        assert by_id[nid]["action"] == "UPDATE_ASSERTION"
        assert by_id[nid]["checkpoint"] == "TSC-A"


def test_rate_limit_nodeids_classified_isolation() -> None:
    by_id = {e["nodeid"]: e for e in _load_inventory()["entries"]}
    nid = "tests/test_s61_correction_target_runtime.py::test_unknown_ref_returns_clarify"
    assert by_id[nid]["action"] == "FIX_TEST_ISOLATION"
    assert by_id[nid]["checkpoint"] == "TSC-A"
