"""CLI for Stage 5.3 offline multiclient matrix harness."""

from __future__ import annotations

import argparse
import json
import sys

from evals.v5.stage53.one_call_stage53_harness import run_offline_matrix
from evals.v5.stage53.one_call_stage53_matrix import (
    assert_frozen_matrix_unchanged,
    assert_matrix_arithmetic,
    build_matrix_document,
    frozen_matrix_sha256,
    matrix_json_path,
    write_frozen_matrix_json,
)


def _write_matrix_command() -> int:
    path = write_frozen_matrix_json()
    sha = frozen_matrix_sha256()
    print(f"matrix_written={path}")
    print(f"matrix_sha256={sha}")
    return 0


def _freeze_sha_command() -> int:
    sha = frozen_matrix_sha256()
    print(sha)
    return 0


def _verify_command() -> int:
    assert_frozen_matrix_unchanged()
    assert_matrix_arithmetic()
    print("matrix_ok")
    return 0


def _run_offline_command() -> int:
    import pytest

    monkeypatch = pytest.MonkeyPatch()
    with monkeypatch.context():
        result = run_offline_matrix(monkeypatch)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("pass") else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage 5.3 offline multiclient harness")
    parser.add_argument(
        "command",
        choices=("write-matrix", "freeze-sha", "verify", "run-offline"),
        help="Harness command",
    )
    args = parser.parse_args(argv)

    if args.command == "write-matrix":
        return _write_matrix_command()
    if args.command == "freeze-sha":
        return _freeze_sha_command()
    if args.command == "verify":
        return _verify_command()
    if args.command == "run-offline":
        return _run_offline_command()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
