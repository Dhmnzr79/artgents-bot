"""CLI for A9R2 patient-scope planner live eval."""

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

from evals.v5.a9r2_patient_scope_live_contract import (  # noqa: E402
    ATTEMPT_MARKER_EXISTS_CODE,
    DEFAULT_LIVE_ARTIFACT_PATHS,
    LIVE_ATTEMPT_MARKER_PATH,
    MEASUREMENT_ID,
    assert_attempt_marker_absent,
    assert_live_artifacts_absent,
    assert_matrix_v1_frozen,
    assert_matrix_v2_frozen,
    iter_live_planner_calls,
    load_frozen_matrix_v2,
)
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
    assert_matrix_v1_frozen()
    assert_matrix_v2_frozen()
    matrix = load_frozen_matrix_v2()
    return iter_live_planner_calls(matrix)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=MEASUREMENT_ID)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate frozen matrices and live-case budget only (no LLM)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run one owner-approved A9R2 live planner attempt",
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
            "measurement_id": MEASUREMENT_ID,
            "matrix_v2_blob": "6a9cc6f7a964d0ab3ead79e5dd2cf0a64d743f57",
            "live_case_count": 16,
            "planner_call_budget": 17,
            "retry_count_max": 0,
            "artifact_paths": [str(path) for path in DEFAULT_LIVE_ARTIFACT_PATHS],
            "attempt_marker": str(LIVE_ATTEMPT_MARKER_PATH),
            "dry_run": True,
            "live_blocked": not args.live,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    try:
        assert_attempt_marker_absent(
            LIVE_ATTEMPT_MARKER_PATH,
            owner_override=args.owner_override_attempt_marker,
        )
        assert_live_artifacts_absent()
    except (AttemptMarkerExistsError, LiveArtifactExistsError) as error:
        print(f"PREFLIGHT_BLOCKED: {error}", file=sys.stderr)
        return 4

    configure_live_env()
    from core.turn_planner_llm import plan_turn_attempt

    try:
        payload = run_planner_harness(
            planner_fn=plan_turn_attempt,
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
