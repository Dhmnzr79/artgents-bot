"""COMPLETION checker for FINAL_TEST_SUITE_CONVERGENCE TSC-B implementation."""

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
INVENTORY_PATH = _REPO_ROOT / "docs" / "evidence" / "testing" / "final_test_failure_inventory.json"
TASK_PATH = _REPO_ROOT / "TASK.md"
TSC_B_INVENTORY_COUNT = 50
TSC_A_INVENTORY_COUNT = 38
TSC_A_HEAD = "d9e69f9"


def _load_inventory() -> dict:
    return json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))


def test_task_documents_tsc_b_complete_and_tsc_c_not_started() -> None:
    section = TASK_PATH.read_text(encoding="utf-8").split("# TASK — FINAL_TEST_SUITE_CONVERGENCE (governance)")[-1]
    assert "TSC-B" in section and "COMPLETE" in section
    assert "TSC-C" in section and "NOT STARTED" in section
    tsc_c_block = section.split("### TSC-C", 1)[1].split("### TSC-D", 1)[0]
    assert "COMPLETE" not in tsc_c_block


def test_tsc_b_inventory_nodeids_green() -> None:
    nodeids = [
        e["nodeid"]
        for e in _load_inventory()["entries"]
        if e["checkpoint"] == "TSC-B"
    ]
    assert len(nodeids) == TSC_B_INVENTORY_COUNT
    proc = subprocess.run(
        ["python", "-m", "pytest", *nodeids, "-q"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_tsc_a_inventory_still_green() -> None:
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


def test_no_skip_xfail_markers_in_tsc_b_allowlist_files() -> None:
    files = sorted(
        {
            path
            for entry in _load_inventory()["entries"]
            if entry["checkpoint"] == "TSC-B"
            for path in entry["files"]
            if path.startswith("tests/") and path.endswith(".py")
        }
    )
    for rel in files:
        text = (_REPO_ROOT / rel).read_text(encoding="utf-8")
        assert "pytest.mark.skip" not in text, rel
        assert "pytest.mark.xfail" not in text, rel


def test_invalid_pack_http_and_runtime_fail_closed() -> None:
    proc = subprocess.run(
        [
            "python",
            "-m",
            "pytest",
            "tests/test_s61_target_fullcontext_runtime.py::test_invalid_pack_fail_closed",
            "tests/test_s61_target_fullcontext_runtime.py::test_invalid_pack_http_ask_and_stream_fail_closed",
            "-q",
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_frozen_pins_unchanged() -> None:
    test_w1b_snapshot_checksums_unchanged()
    test_pscn_frozen_pins_unchanged()
    test_frozen_retry4_artifacts_unchanged_after_closeout()
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH
    assert_frozen_retry4_live_artifacts_unchanged()


def test_acceptance_commands_green() -> None:
    proc = subprocess.run(
        [
            "python",
            "-m",
            "pytest",
            "tests/test_planner_attempt_contract.py",
            "tests/test_c2d_loader_canonical_offline.py",
            "tests/test_target_cached_full_context.py",
            "-q",
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_governance_baseline_heads_documented() -> None:
    text = TASK_PATH.read_text(encoding="utf-8")
    section = text.split("# TASK — FINAL_TEST_SUITE_CONVERGENCE (governance)")[-1]
    assert "1980ab7" in text
    assert TSC_A_HEAD in section
