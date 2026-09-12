"""CLI for ONE_CALL Stage 3C Speed Gate LIVE eval (owner-gated)."""

from __future__ import annotations

import argparse
import sys

from evals.v5.one_call_stage3c_speed_gate_contract import (
    LIVE_AUTHORIZED_ATTEMPT_ID,
    PROPOSED_LIVE_ATTEMPT_ID,
)
from evals.v5.one_call_stage3c_speed_gate_live_runner import (
    SpeedGateLiveGovernanceError,
    run_live_attempt,
    run_preflight_blocked,
    validate_expected_live_head,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="ONE_CALL Stage 3C Speed Gate LIVE eval (owner-gated)",
    )
    parser.add_argument(
        "--attempt-id",
        required=True,
        help="Explicit attempt id; must match LIVE_AUTHORIZED_ATTEMPT_ID when gate open",
    )
    parser.add_argument(
        "--expected-head",
        default=None,
        help="Owner-authorized exact LIVE code HEAD (40-char lowercase hex); required when gate open",
    )
    parser.add_argument(
        "--attempt-wall-timeout-seconds",
        type=float,
        default=600.0,
        help="Absolute measurement wall timeout (default 600)",
    )
    parser.add_argument(
        "--worker-startup-timeout-seconds",
        type=float,
        default=60.0,
        help="Worker bootstrap timeout before worker_ready (default 60)",
    )
    parser.add_argument(
        "--turn-timeout-seconds",
        type=float,
        default=120.0,
        help="Per-turn IPC timeout after turn_start (default 120)",
    )
    parser.add_argument(
        "--wall-timeout-seconds",
        type=float,
        default=None,
        help="Deprecated alias for --attempt-wall-timeout-seconds",
    )
    parser.add_argument(
        "--fake-transport",
        action="store_true",
        help="Eval-only: use fake provider transport (still requires open gate)",
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

    if args.expected_head is None:
        print("expected_head_required", file=sys.stderr)
        return 2

    try:
        expected_live_head = validate_expected_live_head(args.expected_head)
        result = run_live_attempt(
            attempt_id,
            expected_live_head=expected_live_head,
            worker_startup_timeout_seconds=args.worker_startup_timeout_seconds,
            turn_timeout_seconds=args.turn_timeout_seconds,
            attempt_wall_timeout_seconds=(
                args.wall_timeout_seconds
                if args.wall_timeout_seconds is not None
                else args.attempt_wall_timeout_seconds
            ),
            use_fake_transport=args.fake_transport,
        )
        print(result)
        return 0
    except SpeedGateLiveGovernanceError as exc:
        print(f"governance_error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
