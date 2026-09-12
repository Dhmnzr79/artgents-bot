#!/usr/bin/env python3
"""Offline migration bundle fingerprint for G4/G5 production receipts (server-only)."""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

_ALGORITHM_VERSION = 1
_SAFE_FILENAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*\.sql$")
_FINGERPRINT_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class MigrationBundleFingerprintError(ValueError):
    """Fail-closed bundle validation error."""


def _parse_manifest_lines(text: str) -> list[str]:
    names: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        names.append(stripped)
    return names


def compute_migration_bundle_fingerprint(manifest_path: Path, migrations_dir: Path) -> str:
    if not manifest_path.is_file():
        raise MigrationBundleFingerprintError("manifest missing")
    raw_names = _parse_manifest_lines(manifest_path.read_text(encoding="utf-8"))
    if not raw_names:
        raise MigrationBundleFingerprintError("manifest empty")
    seen: set[str] = set()
    migrations_root = migrations_dir.resolve()
    if not migrations_root.is_dir():
        raise MigrationBundleFingerprintError("migrations directory missing")

    hasher = hashlib.sha256()
    hasher.update(f"algorithm_version={_ALGORITHM_VERSION}\n".encode("utf-8"))

    for name in raw_names:
        if name in seen:
            raise MigrationBundleFingerprintError(f"duplicate manifest entry: {name}")
        seen.add(name)
        if not _SAFE_FILENAME.match(name):
            raise MigrationBundleFingerprintError(f"unsafe manifest filename: {name}")
        if ".." in name or "/" in name or "\\" in name:
            raise MigrationBundleFingerprintError(f"unsafe manifest path: {name}")
        sql_path = (migrations_root / name).resolve()
        try:
            sql_path.relative_to(migrations_root)
        except ValueError as exc:
            raise MigrationBundleFingerprintError(f"manifest escapes migrations dir: {name}") from exc
        if not sql_path.is_file():
            raise MigrationBundleFingerprintError(f"missing sql file: {name}")
        if sql_path.is_symlink():
            raise MigrationBundleFingerprintError(f"sql file must not be symlink: {name}")
        content = sql_path.read_bytes()
        hasher.update(name.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(content)
        hasher.update(b"\n")

    return f"sha256:{hasher.hexdigest()}"


def validate_fingerprint_format(value: str) -> None:
    if not _FINGERPRINT_RE.fullmatch(value or ""):
        raise MigrationBundleFingerprintError("invalid fingerprint format")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compute migration bundle fingerprint")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--migrations-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        fp = compute_migration_bundle_fingerprint(args.manifest, args.migrations_dir)
        validate_fingerprint_format(fp)
    except MigrationBundleFingerprintError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(fp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
