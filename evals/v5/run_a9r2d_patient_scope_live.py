"""CLI for A9R2d patient-scope planner live eval (model-pin wiring)."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence

_EVAL_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _EVAL_DIR.parents[1]
_INNER_RUNNER = _EVAL_DIR / "a9r2d_patient_scope_live_inner.py"


def _preflight_dry_run() -> dict:
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    from evals.v5 import a9r2d_patient_scope_live_contract as contract
    from evals.v5.fullcontext_response_eval_contract import HarnessConfigError

    contract.assert_matrix_v1_frozen()
    contract.assert_matrix_v2_frozen()
    contract.assert_matrix_v3_frozen()
    matrix = contract.load_frozen_matrix_v3()
    calls = contract.iter_live_planner_calls(matrix)
    if len(calls) != contract.MAX_PLANNER_CALLS:
        raise HarnessConfigError("planner call budget mismatch")
    return {
        "measurement_id": contract.MEASUREMENT_ID,
        "matrix_v3_blob": contract.MATRIX_V3_BLOB,
        "owner_requested_model": contract.OWNER_APPROVED_PLANNER_MODEL,
        "requires_planner_model_pin": contract.REQUIRES_PLANNER_MODEL_PIN,
        "live_case_count": contract.LIVE_CASE_COUNT,
        "planner_call_budget": contract.MAX_PLANNER_CALLS,
        "retry_count_max": contract.RETRY_COUNT_MAX,
        "artifact_paths": [str(path) for path in contract.DEFAULT_LIVE_ARTIFACT_PATHS],
        "attempt_marker": str(contract.LIVE_ATTEMPT_MARKER_PATH),
        "inner_runner": str(_INNER_RUNNER),
    }


def _run_live_subprocess() -> int:
    env = os.environ.copy()
    env["TURN_PLANNER_LLM_MODEL"] = "qwen3.7-plus"
    proc = subprocess.run(
        [sys.executable, str(_INNER_RUNNER)],
        cwd=str(_REPO_ROOT),
        env=env,
        check=False,
    )
    return int(proc.returncode)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="a9r2d_patient_scope_live")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument(
        "--owner-override-attempt-marker",
        action="store_true",
        help="disallowed for A9R2d",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.owner_override_attempt_marker:
        print("OWNER_OVERRIDE_FORBIDDEN", file=sys.stderr)
        return 3

    try:
        payload = _preflight_dry_run()
    except Exception as error:
        print(f"CONFIG_ERROR: {error}", file=sys.stderr)
        return 2

    if args.dry_run or (not args.live):
        payload["dry_run"] = True
        payload["live_blocked"] = not args.live
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    return _run_live_subprocess()


if __name__ == "__main__":
    raise SystemExit(main())
