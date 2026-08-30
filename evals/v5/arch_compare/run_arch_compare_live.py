"""CLI entrypoint for architecture comparison LIVE prep (fake default, LIVE gated)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _bootstrap() -> Path:
    repo_root = _REPO_ROOT
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)
    return repo_root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Architecture compare LIVE prep runner (fake default).")
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--live", action="store_true", help="Request LIVE mode (requires authorization).")
    parser.add_argument(
        "--authorization-json",
        help="Path to external authorization manifest (required for --live).",
    )
    parser.add_argument(
        "--artifacts-root",
        default=None,
        help="Artifact output root (defaults to evals/v5/artifacts/arch_compare_live_prep).",
    )
    args = parser.parse_args(argv)

    repo_root = _bootstrap()
    from evals.v5.arch_compare.arch_compare_live_guard import (
        ArchCompareLiveGuardError,
        authorization_manifest_from_dict,
        build_guard_context,
        validate_run_mode,
    )
    from evals.v5.arch_compare.arch_compare_live_report import persist_live_prep_artifacts
    from evals.v5.arch_compare.arch_compare_live_runner import run_arch_compare_fake_full_path

    authorization = None
    if args.authorization_json:
        authorization = authorization_manifest_from_dict(
            json.loads(Path(args.authorization_json).read_text(encoding="utf-8"))
        )

    artifacts_root = (
        Path(args.artifacts_root)
        if args.artifacts_root
        else repo_root / "evals" / "v5" / "artifacts" / "arch_compare_live_prep"
    )
    artifact_dir = artifacts_root / args.attempt_id

    guard_context = build_guard_context(
        repo_root=repo_root,
        attempt_id=args.attempt_id,
        live_requested=args.live,
        authorization=authorization,
        artifact_dir=artifact_dir,
        transport_kind="fake",
    )

    try:
        mode = validate_run_mode(guard_context)
    except ArchCompareLiveGuardError as exc:
        print(f"GUARD_REJECT:{exc.code}:{exc}", file=sys.stderr)
        return 2

    if mode == "live":
        print("LIVE mode is gated and not enabled in prep checkpoint.", file=sys.stderr)
        return 2

    result = run_arch_compare_fake_full_path(attempt_id=args.attempt_id, guard_context=guard_context)
    paths = persist_live_prep_artifacts(
        artifacts_root=artifacts_root,
        attempt_id=args.attempt_id,
        run_result=result,
        stdout_log=f"mode=fake attempt_id={args.attempt_id}\n",
    )
    print(json.dumps({"artifact_dir": str(paths["dir"]), "mode": result["mode"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
