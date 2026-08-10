"""CLI: Stage 3C Speed Gate offline fake dry-run."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from evals.v5.one_call_stage3c_speed_gate_harness import assert_offline_gate_closed, run_offline_dry_run
from evals.v5.one_call_stage3c_speed_gate_live_runner import run_dry_run_attempt


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _git_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=_repo_root(),
        text=True,
    ).strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ONE_CALL Stage 3C Speed Gate dry-run")
    parser.add_argument(
        "--attempt-id",
        default="stage3c_offline_dry_run",
        help="Artifact subdirectory name for offline dry-run output",
    )
    parser.add_argument(
        "--with-artifacts",
        action="store_true",
        help="Write attempt marker + ledger + raw/result under evals/v5/artifacts/",
    )
    args = parser.parse_args(argv)

    try:
        assert_offline_gate_closed()
    except Exception as exc:
        print({"error": str(exc), "exit_code": 3})
        return 3

    if args.with_artifacts:
        payload = run_dry_run_attempt(attempt_id=args.attempt_id, observed_live_head=_git_head())
    else:
        from pytest import MonkeyPatch

        with MonkeyPatch.context() as monkeypatch:
            payload = run_offline_dry_run(
                monkeypatch,
                attempt_id=args.attempt_id,
                write_artifacts=True,
            )

    print(
        {
            "attempt_id": args.attempt_id,
            "verdict": payload.get("speed_gate", {}).get("verdict"),
            "speed_pass": payload.get("speed_gate", {}).get("speed_pass"),
            "frozen_matrix_sha256": payload.get("frozen_matrix_sha256"),
            "old_peak_calls": payload.get("call_plan", {}).get("observed_old_peak_per_case"),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
