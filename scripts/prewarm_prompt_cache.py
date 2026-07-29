#!/usr/bin/env python3
"""Owner-controlled provider prompt-cache prewarm CLI (PERF-3, Option B).

Manual, standalone operator tool. It is never imported by app.py, a request handler, a startup
hook, or the pytest import graph -- it runs only when an operator invokes it directly.

Default action is DRY-RUN: it loads the client pack, builds the real Composer/Verifier messages
via the production builders, computes each role's fingerprint, and prints only anonymized
scalar metadata (hashes, model, role, prefix length, token estimate, fingerprint, budget). It
makes ZERO provider calls, creates ZERO markers, and needs no attempt-id.

  python scripts/prewarm_prompt_cache.py --client-id demo

Live mode (--live) is HARD-BLOCKED in this phase. It requires an explicit --attempt-id and
expected model/fingerprint per role, runs the model-pin + fingerprint preflight (which aborts
before any marker/provider call), and then exits with a dedicated BLOCKED code -- still before
any marker write or provider call -- because real activation needs a SEPARATE owner LIVE/LLM
GO (the second rollout gate).

  python scripts/prewarm_prompt_cache.py --client-id demo --live \
      --attempt-id 2026-07-29-demo-01 \
      --expected-composer-model qwen3.7-plus --expected-verifier-model qwen3.7-plus \
      --expected-composer-fingerprint <hex> --expected-verifier-fingerprint <hex>

Exit codes: 0 dry-run OK · 2 usage error · 3 preflight mismatch (model-pin/fingerprint) ·
4 live blocked (separate owner LIVE/LLM GO required).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import ALLOWED_CLIENTS  # noqa: E402
from core.target_prompt_cache_prewarm import (  # noqa: E402
    LIVE_OUTCOME_BLOCKED,
    LIVE_OUTCOME_EXECUTED,
    LIVE_OUTCOME_FINGERPRINT_MISMATCH,
    LIVE_OUTCOME_MODEL_MISMATCH,
    LiveRequest,
    LiveRoleExpectation,
    build_dry_run_report,
    run_live,
)

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_PREFLIGHT_MISMATCH = 3
EXIT_LIVE_BLOCKED = 4


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="prewarm_prompt_cache",
        description="Owner-controlled provider prompt-cache prewarm (dry-run default; live hard-blocked).",
    )
    parser.add_argument("--client-id", required=True, help="Client pack id (must be allowlisted).")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Live mode (hard-blocked; requires a separate owner LIVE/LLM GO).",
    )
    parser.add_argument("--attempt-id", default=None, help="Explicit attempt id (required in --live).")
    parser.add_argument("--expected-composer-model", default=None)
    parser.add_argument("--expected-verifier-model", default=None)
    parser.add_argument("--expected-composer-fingerprint", default=None)
    parser.add_argument("--expected-verifier-fingerprint", default=None)
    return parser


def _run_dry_run(client_id: str) -> int:
    report = build_dry_run_report(client_id)
    print(f"[prewarm dry-run] client_id={report.client_id} budget={report.budget} retry={report.retry}")
    print("[prewarm dry-run] mode=dry-run provider_calls=0 markers=0 (no attempt-id required)")
    for role in report.roles:
        print(
            f"  role={role.role} model={role.model} "
            f"static_prefix_chars={role.static_prefix_chars} est_tokens~={role.estimated_tokens}"
        )
        print(f"    static_prefix_hash={role.static_prefix_hash}")
        print(f"    corpus_sha256={role.corpus_sha256}")
        print(f"    fingerprint={role.fingerprint}")
    return EXIT_OK


def _run_live(args: argparse.Namespace) -> int:
    missing = [
        name
        for name, value in (
            ("--attempt-id", args.attempt_id),
            ("--expected-composer-model", args.expected_composer_model),
            ("--expected-verifier-model", args.expected_verifier_model),
            ("--expected-composer-fingerprint", args.expected_composer_fingerprint),
            ("--expected-verifier-fingerprint", args.expected_verifier_fingerprint),
        )
        if not value
    ]
    if missing:
        print(f"[prewarm live] usage error: --live requires {', '.join(missing)}", file=sys.stderr)
        return EXIT_USAGE

    request = LiveRequest(
        attempt_id=args.attempt_id,
        client_id=args.client_id,
        expectations=(
            LiveRoleExpectation(
                role="composer",
                expected_model=args.expected_composer_model,
                expected_fingerprint=args.expected_composer_fingerprint,
            ),
            LiveRoleExpectation(
                role="verifier",
                expected_model=args.expected_verifier_model,
                expected_fingerprint=args.expected_verifier_fingerprint,
            ),
        ),
    )
    outcome = run_live(request)

    if outcome.kind == LIVE_OUTCOME_MODEL_MISMATCH:
        print(
            f"[prewarm live] ABORT before marker/call: model-pin mismatch for role={outcome.role} "
            f"expected={outcome.expected} configured={outcome.actual}",
            file=sys.stderr,
        )
        return EXIT_PREFLIGHT_MISMATCH
    if outcome.kind == LIVE_OUTCOME_FINGERPRINT_MISMATCH:
        print(
            f"[prewarm live] ABORT before marker/call: fingerprint mismatch for role={outcome.role} "
            f"expected={outcome.expected} computed={outcome.actual}",
            file=sys.stderr,
        )
        return EXIT_PREFLIGHT_MISMATCH
    if outcome.kind == LIVE_OUTCOME_BLOCKED:
        print(
            "[prewarm live] BLOCKED before any marker write or provider call: live activation "
            "requires a separate owner LIVE/LLM GO (two-gate rollout). 0 provider calls, 0 markers.",
            file=sys.stderr,
        )
        return EXIT_LIVE_BLOCKED
    if outcome.kind == LIVE_OUTCOME_EXECUTED:  # unreached in this phase
        attempt = outcome.attempt
        print(
            f"[prewarm live] attempt={attempt.attempt_id} status={attempt.status} "
            f"calls_started={attempt.calls_started} calls_completed={attempt.calls_completed}"
        )
        return EXIT_OK
    print(f"[prewarm live] unexpected outcome: {outcome.kind}", file=sys.stderr)
    return EXIT_USAGE


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.client_id not in ALLOWED_CLIENTS:
        print(
            f"[prewarm] usage error: client_id {args.client_id!r} not in ALLOWED_CLIENTS "
            f"({sorted(ALLOWED_CLIENTS)})",
            file=sys.stderr,
        )
        return EXIT_USAGE

    if args.live:
        return _run_live(args)
    return _run_dry_run(args.client_id)


if __name__ == "__main__":
    raise SystemExit(main())
