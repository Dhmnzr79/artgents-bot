"""CLI for FINAL scope/widget E2E retry1 live runtime eval."""

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

from evals.v5.fullcontext_response_eval_contract import HarnessConfigError
from evals.v5.final_scope_widget_e2e_retry1_live_contract import (
    ATTEMPT_MARKER_EXISTS_CODE,
    DEFAULT_LIVE_ARTIFACT_PATHS,
    LIVE_ATTEMPT_MARKER_PATH,
    MAX_HTTP_TURNS,
    MAX_PROVIDER_CALLS,
    MEASUREMENT_ID,
    OWNER_APPROVED_PLANNER_MODEL,
    assert_frozen_preflight_abort_artifacts_unchanged,
    assert_frozen_suite_unchanged,
)
from evals.v5.final_scope_widget_e2e_retry1_live_harness import (
    _assert_frozen_neighbors,
    configure_process_env,
    prepare_retry1_live_run,
    run_http_harness,
    run_non_network_preflight,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=MEASUREMENT_ID)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate frozen suite, authority env, post-S69 seams, and artifact guards only",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Point to pytest offline harness (no network)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run one owner-approved FINAL scope/widget retry1 live attempt",
    )
    parser.add_argument(
        "--owner-override-attempt-marker",
        action="store_true",
        help="Allow live prep when retry1 attempt marker exists (owner approval only)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        configure_process_env()
        assert_frozen_preflight_abort_artifacts_unchanged()
        assert_frozen_suite_unchanged()
    except HarnessConfigError as error:
        print(f"CONFIG_ERROR: {error}", file=sys.stderr)
        return 2

    if args.dry_run:
        try:
            run_non_network_preflight(
                attempt_marker_path=LIVE_ATTEMPT_MARKER_PATH,
                artifact_paths=DEFAULT_LIVE_ARTIFACT_PATHS,
                assert_frozen_neighbors=_assert_frozen_neighbors,
            )
        except HarnessConfigError as error:
            print(f"CONFIG_ERROR: {error}", file=sys.stderr)
            return 2
        payload = {
            "measurement_id": MEASUREMENT_ID,
            "artifact_paths": [str(path) for path in DEFAULT_LIVE_ARTIFACT_PATHS],
            "attempt_marker": str(LIVE_ATTEMPT_MARKER_PATH),
            "max_http_turns": MAX_HTTP_TURNS,
            "max_provider_calls": MAX_PROVIDER_CALLS,
            "planner_model": OWNER_APPROVED_PLANNER_MODEL,
            "a9_patient_scope_authority": "1",
            "live_blocked": True,
            "dry_run": True,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if args.offline:
        print(
            "Use pytest tests/test_final_scope_widget_e2e_retry1_live_harness.py for offline harness",
            file=sys.stderr,
        )
        return 0

    if args.live:
        try:
            payload = run_http_harness(
                live=True,
                monkeypatch=None,
                owner_override_attempt_marker=args.owner_override_attempt_marker,
            )
        except Exception as error:
            if ATTEMPT_MARKER_EXISTS_CODE in str(error):
                print(ATTEMPT_MARKER_EXISTS_CODE, file=sys.stderr)
                return 3
            print(f"LIVE_ABORT: {type(error).__name__}: {error}", file=sys.stderr)
            return 5
        summary = payload["summary"]
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        automated = summary.get("automated_verdict")
        print(f"AUTOMATED_VERDICT: {automated}", file=sys.stderr)
        print(f"FINAL_VERDICT: {summary.get('final_verdict')}", file=sys.stderr)
        print("RERUN_BLOCKED", file=sys.stderr)
        print("MANUAL_REVIEW_REQUIRED", file=sys.stderr)
        return 0 if automated == "AUTOMATED_PASS" else 4

    print("LIVE_NOT_CONFIGURED: use --live, --offline, or --dry-run", file=sys.stderr)
    return 4


if __name__ == "__main__":
    raise SystemExit(main())
