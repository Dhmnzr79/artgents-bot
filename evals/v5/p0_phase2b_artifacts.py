"""Lightweight artifact helpers for P0 Phase 2B (no Flask/LLM imports)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from evals.v5.p0_phase2b_contract import (
    CANDIDATE_MODEL_ID,
    CONTROL_MODEL_ID,
    MEASUREMENT_ID,
    REQUIRED_BASELINE_COMMIT,
    build_call_plan,
)

_REPO = Path(__file__).resolve().parents[2]
_ARTIFACTS = _REPO / "evals" / "v5" / "artifacts" / "p0_phase2b_qwen38_streaming"


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=_REPO, text=True).strip()


def git_dirty_tracked() -> list[str]:
    out = subprocess.check_output(["git", "diff", "--name-only", "HEAD"], cwd=_REPO, text=True)
    return [line.strip().replace("\\", "/") for line in out.splitlines() if line.strip()]


def persist_artifact(name: str, payload: dict[str, Any]) -> Path:
    _ARTIFACTS.mkdir(parents=True, exist_ok=True)
    path = _ARTIFACTS / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def baseline_report() -> dict[str, Any]:
    dirty = git_dirty_tracked()
    head = git_head()
    return {
        "measurement_id": MEASUREMENT_ID,
        "head": head,
        "required_baseline_commit": REQUIRED_BASELINE_COMMIT,
        "baseline_commit_is_head": head == REQUIRED_BASELINE_COMMIT,
        "dirty_tracked_paths": dirty,
        "dirty_out_of_scope_note": (
            "Tracked dirty paths are deploy/postgres/g8 WIP — excluded from Phase 2B product scope."
        ),
        "control_model": CONTROL_MODEL_ID,
        "candidate_model": CANDIDATE_MODEL_ID,
        "planned_calls": len(build_call_plan(include_canary=True, repeat_pass=True)),
    }
