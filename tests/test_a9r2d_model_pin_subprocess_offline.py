"""Subprocess tests for patient-scope planner model-pin wiring."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_python(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(_REPO_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )


def test_stale_config_import_blocks_model_pin_preflight() -> None:
    repo = str(_REPO_ROOT).replace("\\", "\\\\")
    script = f"""
import os, sys
sys.path.insert(0, r"{repo}")
os.environ["TURN_PLANNER_LLM_MODEL"] = "qwen3.6-flash"
import config
os.environ["TURN_PLANNER_LLM_MODEL"] = "qwen3.7-plus"
from evals.v5.patient_scope_live_model_pin import (
    PlannerModelPinError,
    assert_planner_model_pin_before_marker,
)
try:
    assert_planner_model_pin_before_marker("qwen3.7-plus")
except PlannerModelPinError:
    raise SystemExit(0)
raise SystemExit(1)
"""
    proc = _run_python(script)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_env_before_import_configures_plus() -> None:
    repo = str(_REPO_ROOT).replace("\\", "\\\\")
    script = f"""
import os, sys
sys.path.insert(0, r"{repo}")
os.environ["TURN_PLANNER_LLM_MODEL"] = "qwen3.7-plus"
from evals.v5.patient_scope_live_model_pin import assert_planner_model_pin_before_marker
provenance = assert_planner_model_pin_before_marker("qwen3.7-plus")
import config
assert config.TURN_PLANNER_LLM_MODEL == "qwen3.7-plus"
assert provenance["configured_model"] == "qwen3.7-plus"
raise SystemExit(0)
"""
    proc = _run_python(script)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_a9r2d_dry_run_blocks_live_and_declares_pin() -> None:
    proc = subprocess.run(
        [sys.executable, "evals/v5/run_a9r2d_patient_scope_live.py", "--dry-run"],
        cwd=str(_REPO_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert '"live_blocked": true' in proc.stdout
    assert '"requires_planner_model_pin": true' in proc.stdout
    assert '"owner_requested_model": "qwen3.7-plus"' in proc.stdout


def test_a9r2c_incident_status_constants() -> None:
    from evals.v5 import a9r2c_patient_scope_live_contract as contract

    assert contract.OFFICIAL_A9R2C_STATUS == "A9R2C_NOT_VALID_FOR_PLUS"
    assert contract.A9R2C_PLUS_VALIDATION is False
    assert contract.A9R2C_INCIDENT_PROVIDER_CALLS == 17
    assert contract.A9R2C_RERUN_BLOCKED is True
    contract.assert_frozen_a9r2c_live_artifacts_unchanged()
