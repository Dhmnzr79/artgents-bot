"""CLI for A9R2c patient-scope planner live eval."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

_EVAL_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _EVAL_DIR.parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from evals.v5 import a9r2c_patient_scope_live_contract as contract  # noqa: E402
from evals.v5.a9r2_patient_scope_live_harness import (  # noqa: E402
    configure_live_env,
    run_planner_harness,
)
from evals.v5.fullcontext_response_eval_contract import (  # noqa: E402
    AttemptMarkerExistsError,
    HarnessConfigError,
    LiveArtifactExistsError,
)


def _preflight(*, owner_override_attempt_marker: bool) -> list[dict]:
    contract.assert_matrix_v1_frozen()
    contract.assert_matrix_v2_frozen()
    contract.assert_matrix_v3_frozen()
    matrix = contract.load_frozen_matrix_v3()
    return contract.iter_live_planner_calls(matrix)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=contract.MEASUREMENT_ID)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate frozen matrices and live-case budget only (no LLM)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run one owner-approved A9R2c live planner attempt",
    )
    parser.add_argument(
        "--owner-override-attempt-marker",
        action="store_true",
        help="Allow prep when attempt marker exists with zero started calls",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        calls = _preflight(owner_override_attempt_marker=args.owner_override_attempt_marker)
    except HarnessConfigError as error:
        print(f"CONFIG_ERROR: {error}", file=sys.stderr)
        return 2

    if args.dry_run or (not args.live):
        payload = {
            "measurement_id": contract.MEASUREMENT_ID,
            "matrix_v3_blob": contract.MATRIX_V3_BLOB,
            "planner_model": contract.OWNER_APPROVED_PLANNER_MODEL,
            "live_case_count": contract.LIVE_CASE_COUNT,
            "planner_call_budget": contract.MAX_PLANNER_CALLS,
            "retry_count_max": contract.RETRY_COUNT_MAX,
            "artifact_paths": [str(path) for path in contract.DEFAULT_LIVE_ARTIFACT_PATHS],
            "attempt_marker": str(contract.LIVE_ATTEMPT_MARKER_PATH),
            "dry_run": True,
            "live_blocked": not args.live,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    try:
        contract.assert_attempt_marker_absent(
            contract.LIVE_ATTEMPT_MARKER_PATH,
            owner_override=args.owner_override_attempt_marker,
        )
        contract.assert_live_artifacts_absent()
    except (AttemptMarkerExistsError, LiveArtifactExistsError) as error:
        print(f"PREFLIGHT_BLOCKED: {error}", file=sys.stderr)
        return 4

    configure_live_env(contract=contract)
    from core.turn_planner_llm import plan_turn_attempt

    try:
        payload = run_planner_harness(
            planner_fn=plan_turn_attempt,
            contract=contract,
            owner_override_attempt_marker=args.owner_override_attempt_marker,
            record_dialog_history=True,
        )
    except HarnessConfigError as error:
        print(f"LIVE_ABORTED: {error}", file=sys.stderr)
        return 5

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["automated_verdict"] == "AUTOMATED_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
