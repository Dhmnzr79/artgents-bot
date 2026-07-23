"""CLI for S62 target FullContext HTTP live runtime eval."""

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
from evals.v5.s62_target_runtime_live_contract import (
    ATTEMPT_MARKER_EXISTS_CODE,
    DEFAULT_LIVE_ARTIFACT_PATHS,
    LIVE_ATTEMPT_MARKER_PATH,
    MEASUREMENT_ID,
    assert_frozen_suite_unchanged,
)
from evals.v5.s62_target_runtime_live_harness import prepare_live_run, run_http_harness


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=MEASUREMENT_ID)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate frozen suite and artifact guards only",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run HTTP harness with fake provider transport (no network)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run one owner-approved S62 live attempt",
    )
    parser.add_argument(
        "--owner-override-attempt-marker",
        action="store_true",
        help="Allow live prep when attempt marker exists (owner approval only)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        assert_frozen_suite_unchanged()
    except HarnessConfigError as error:
        print(f"CONFIG_ERROR: {error}", file=sys.stderr)
        return 2

    if args.dry_run:
        payload = {
            "measurement_id": MEASUREMENT_ID,
            "artifact_paths": [str(path) for path in DEFAULT_LIVE_ARTIFACT_PATHS],
            "attempt_marker": str(LIVE_ATTEMPT_MARKER_PATH),
            "dry_run": True,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if args.offline:
        print("Use pytest tests/test_s62_target_runtime_live_harness.py for offline harness", file=sys.stderr)
        return 0

    if args.live:
        try:
            payload = run_http_harness(live=True, monkeypatch=None)
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
        return 0 if automated == "AUTOMATED_PASS" else 4

    print("LIVE_NOT_CONFIGURED: use --live, --offline, or --dry-run", file=sys.stderr)
    return 4


if __name__ == "__main__":
    raise SystemExit(main())
