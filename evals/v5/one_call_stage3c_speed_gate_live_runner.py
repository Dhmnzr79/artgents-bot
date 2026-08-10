"""LIVE runner skeleton for Stage 3C Speed Gate (dry-run first; gate default closed)."""

from __future__ import annotations

import multiprocessing
import os
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from evals.v5.one_call_stage3c_speed_gate_contract import (
    LIVE_AUTHORIZED_ATTEMPT_ID,
    PROPOSED_LIVE_ATTEMPT_ID,
    build_attempt_marker_payload,
)
from evals.v5.one_call_stage3c_speed_gate_harness import run_offline_dry_run
from evals.v5.one_call_stage3c_speed_gate_live_artifacts import (
    append_ledger_event,
    artifact_paths_for_attempt,
    create_attempt_marker_exclusive,
)
from evals.v5.one_call_stage3c_speed_gate_matrix import frozen_matrix_sha256


class SpeedGateLiveGovernanceError(RuntimeError):
    code: str

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def assert_live_governance(attempt_id: str) -> None:
    if LIVE_AUTHORIZED_ATTEMPT_ID is None:
        raise SpeedGateLiveGovernanceError("live_gate_closed", "stage3c_live_gate_closed")
    if LIVE_AUTHORIZED_ATTEMPT_ID != attempt_id:
        raise SpeedGateLiveGovernanceError(
            "attempt_id_mismatch",
            f"stage3c_attempt_id_mismatch:{attempt_id}",
        )


def run_dry_run_attempt(
    *,
    attempt_id: str = "stage3c_offline_dry_run",
    baseline_commit: str,
) -> dict[str, Any]:
    """Fake-transport dry-run; no network, no gate required."""

    paths = artifact_paths_for_attempt(attempt_id)
    if paths["attempt_json"].exists():
        raise RuntimeError(f"artifact already exists: {paths['attempt_json']}")

    matrix_sha = frozen_matrix_sha256()
    create_attempt_marker_exclusive(
        paths["attempt_json"],
        build_attempt_marker_payload(
            attempt_id=attempt_id,
            frozen_matrix_sha256=matrix_sha,
            baseline_commit=baseline_commit,
        ),
    )
    append_ledger_event(
        paths["calls_jsonl"],
        event="START",
        case_id="dry_run",
        attempt_id=attempt_id,
    )

    from pytest import MonkeyPatch

    with MonkeyPatch.context() as monkeypatch:
        result = run_offline_dry_run(
            monkeypatch,
            attempt_id=attempt_id,
            write_artifacts=False,
        )

    paths["raw_json"].write_text(
        __import__("json").dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    paths["result_json"].write_text(
        __import__("json").dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    append_ledger_event(
        paths["calls_jsonl"],
        event="FINISH",
        case_id="dry_run",
        attempt_id=attempt_id,
        extra={"verdict": result.get("speed_gate", {}).get("verdict")},
    )
    return result


def run_live_attempt(
    *,
    attempt_id: str,
    baseline_commit: str,
    wall_timeout_seconds: float = 600.0,
    use_fake_transport: bool = False,
) -> dict[str, Any]:
    if use_fake_transport:
        return run_dry_run_attempt(attempt_id=attempt_id, baseline_commit=baseline_commit)

    assert_live_governance(attempt_id)
    started = time.monotonic()
    if time.monotonic() - started > wall_timeout_seconds:
        raise TimeoutError("stage3c_wall_timeout")
    raise SpeedGateLiveGovernanceError(
        "live_not_implemented",
        "stage3c_live_requires_owner_gate_and_fake_dry_run_first",
    )
