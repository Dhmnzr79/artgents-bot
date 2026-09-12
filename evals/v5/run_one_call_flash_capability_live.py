"""CLI for ONE_CALL Flash capability LIVE eval (Stage 3B governance)."""

from __future__ import annotations

import argparse
import sys

from evals.v5.one_call_flash_capability_contract import (
    LIVE_AUTHORIZED_ATTEMPT_ID,
    PROPOSED_LIVE_ATTEMPT_ID,
)
from evals.v5.one_call_flash_capability_live_runner import (
    CapabilityLiveGovernanceError,
    run_live_attempt,
    run_preflight_blocked,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="ONE_CALL Flash capability LIVE eval (owner-gated, max 6 calls)",
    )
    parser.add_argument(
        "--attempt-id",
        required=True,
        help="Explicit attempt id; must match LIVE_AUTHORIZED_ATTEMPT_ID when gate open",
    )
    parser.add_argument(
        "--wall-timeout-seconds",
        type=float,
        default=60.0,
        help="Per-case child wall timeout (default 60)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    attempt_id = args.attempt_id.strip()
    if not attempt_id:
        print("attempt_id_required", file=sys.stderr)
        return 2

    if LIVE_AUTHORIZED_ATTEMPT_ID is None:
        summary = run_preflight_blocked(attempt_id)
        print(summary)
        return 3

    try:
        result = run_live_attempt(
            attempt_id,
            wall_timeout_seconds=args.wall_timeout_seconds,
        )
        print(result)
        return 0
    except CapabilityLiveGovernanceError as exc:
        print(f"governance_error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
