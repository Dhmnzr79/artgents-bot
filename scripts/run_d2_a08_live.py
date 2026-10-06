"""Explicitly authorized CP3 live runner; never an HTTP or widget entry point."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.d2_live_a08_harness import run_cp3_a08_live
from core.d2_live_provider import CP3_MAX_PROVIDER_CALLS, D2Cp3LiveProvider


AUTHORIZATION_TOKEN = "CP3_LIVE_A08_TWO_CALLS"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorize", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--clients-root", default=Path("clients"), type=Path)
    args = parser.parse_args()
    if args.authorize != AUTHORIZATION_TOKEN:
        raise SystemExit("explicit CP3 authorization token required")
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    result = run_cp3_a08_live(
        clients_root=args.clients_root.resolve(),
        database_path=output_dir / "cp3-a08.sqlite",
        provider=D2Cp3LiveProvider(max_calls=CP3_MAX_PROVIDER_CALLS),
    )
    (output_dir / "cp3-a08-summary.json").write_text(
        json.dumps(result.as_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result.as_dict(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
