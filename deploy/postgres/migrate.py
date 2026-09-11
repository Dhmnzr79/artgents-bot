#!/usr/bin/env python3
"""PostgreSQL tenant migration runner (migrator DSN only; no runtime DDL)."""
from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from deploy.postgres.migration_manifest import (
    MIGRATION_ADVISORY_LOCK_KEY,
    LedgerRow,
    ManifestEntry,
    MigrationManifestError,
    checksum_prefix,
    ledger_qualified_table,
    ledger_schema_ddl,
    load_manifest,
    manifest_prefix_entries,
    plan_actions,
    reconcile_ledger,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_MANIFEST = Path(__file__).resolve().parent / "migrations.manifest"
_DEFAULT_MIGRATIONS_DIR = _REPO_ROOT / "migrations" / "postgresql"

_DSN_SECRET_RE = re.compile(
    r"(postgresql(?:\+psycopg)?://)([^:@/]+)(?::([^@/]*))?@",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class MigrationStepResult:
    filename: str
    status: str
    checksum_prefix: str


@dataclass(frozen=True)
class MigrationRunResult:
    ok: bool
    dry_run: bool
    steps: list[MigrationStepResult]
    error_code: str | None = None


def redact_dsn(dsn: str) -> str:
    if not dsn:
        return ""
    return _DSN_SECRET_RE.sub(r"\1\2:***@", dsn)


def safe_error_message(exc: BaseException) -> str:
    text = str(exc) or exc.__class__.__name__
    text = _DSN_SECRET_RE.sub(r"\1\2:***@", text)
    if "password" in text.lower():
        return exc.__class__.__name__
    return text[:500]


def _require_migrator_dsn() -> str:
    dsn = (os.getenv("BOT_MIGRATOR_PG_DSN") or "").strip()
    if not dsn:
        raise MigrationManifestError("migrator_dsn_missing")
    return dsn


def _fetch_ledger(conn: Any) -> list[LedgerRow]:
    table = ledger_qualified_table()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT filename, checksum FROM {table} ORDER BY filename")
            return [LedgerRow(filename=str(r[0]), checksum=str(r[1])) for r in cur.fetchall()]
    except Exception:
        raise MigrationManifestError("ledger_read_failed") from None


def _ensure_ledger_schema(conn: Any) -> None:
    try:
        with conn.cursor() as cur:
            cur.execute(ledger_schema_ddl())
    except Exception:
        raise MigrationManifestError("ledger_setup_failed") from None


def _try_advisory_lock(conn: Any) -> bool:
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(%s)", (MIGRATION_ADVISORY_LOCK_KEY,))
            row = cur.fetchone()
        return bool(row and row[0])
    except Exception:
        raise MigrationManifestError("advisory_lock_failed") from None


def _execute_migration_sql(conn: Any, sql_text: str) -> None:
    """Execute migration file as-is (files contain their own BEGIN/COMMIT)."""
    with conn.cursor() as cur:
        cur.execute(sql_text)


def _record_applied(conn: Any, entry: ManifestEntry) -> None:
    table = ledger_qualified_table()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {table} (filename, checksum)
                VALUES (%s, %s)
                ON CONFLICT (filename) DO NOTHING
                """,
                (entry.filename, entry.checksum),
            )
            cur.execute(
                f"SELECT checksum FROM {table} WHERE filename = %s",
                (entry.filename,),
            )
            row = cur.fetchone()
    except Exception:
        raise MigrationManifestError("ledger_write_failed", entry.filename) from None
    if not row or str(row[0]) != entry.checksum:
        raise MigrationManifestError("ledger_write_failed", entry.filename)


def _execution_scope(
    entries: list[ManifestEntry],
    through: str | None,
) -> frozenset[str]:
    if through is None:
        return frozenset(e.filename for e in entries)
    prefix = manifest_prefix_entries(entries, through)
    return frozenset(e.filename for e in prefix)


def run_migrations(
    *,
    dsn: str,
    manifest_path: Path = _DEFAULT_MANIFEST,
    migrations_dir: Path = _DEFAULT_MIGRATIONS_DIR,
    dry_run: bool = False,
    through: str | None = None,
    connect_fn: Any | None = None,
) -> MigrationRunResult:
    steps: list[MigrationStepResult] = []
    try:
        entries = load_manifest(manifest_path, migrations_dir)
        manifest_names = frozenset(e.filename for e in entries)
        run_scope = _execution_scope(entries, through)
    except MigrationManifestError as exc:
        return MigrationRunResult(
            ok=False,
            dry_run=dry_run,
            steps=steps,
            error_code=exc.code,
        )

    try:
        planned = plan_actions(entries, {})
    except MigrationManifestError as exc:
        return MigrationRunResult(
            ok=False,
            dry_run=dry_run,
            steps=steps,
            error_code=exc.code,
        )

    if dry_run:
        for entry, action in planned:
            if entry.filename not in run_scope:
                continue
            status = "would_skip" if action == "skip" else "would_apply"
            steps.append(
                MigrationStepResult(
                    filename=entry.filename,
                    status=status,
                    checksum_prefix=checksum_prefix(entry.checksum),
                )
            )
        return MigrationRunResult(ok=True, dry_run=True, steps=steps)

    conn = None
    try:
        connect = connect_fn
        if connect is None:
            import psycopg

            connect = psycopg.connect
        conn = connect(dsn, autocommit=True, connect_timeout=10)
    except Exception:
        return MigrationRunResult(
            ok=False,
            dry_run=False,
            steps=steps,
            error_code="migration_connect_failed",
        )

    try:
        if not _try_advisory_lock(conn):
            return MigrationRunResult(
                ok=False,
                dry_run=False,
                steps=steps,
                error_code="advisory_lock_busy",
            )
        _ensure_ledger_schema(conn)
        ledger_rows = _fetch_ledger(conn)
        reconcile_ledger(manifest_names, ledger_rows)
        ledger_by_name = {r.filename: r for r in ledger_rows}
        planned = plan_actions(entries, ledger_by_name)

        for entry, action in planned:
            if entry.filename not in run_scope:
                continue
            prefix = checksum_prefix(entry.checksum)
            if action == "skip":
                steps.append(
                    MigrationStepResult(
                        filename=entry.filename,
                        status="skipped",
                        checksum_prefix=prefix,
                    )
                )
                continue
            try:
                sql_text = entry.path.read_text(encoding="utf-8")
            except OSError:
                return MigrationRunResult(
                    ok=False,
                    dry_run=False,
                    steps=steps,
                    error_code="migration_file_read_failed",
                )
            try:
                _execute_migration_sql(conn, sql_text)
            except Exception:
                return MigrationRunResult(
                    ok=False,
                    dry_run=False,
                    steps=steps,
                    error_code="migration_sql_failed",
                )
            try:
                _record_applied(conn, entry)
            except MigrationManifestError as exc:
                return MigrationRunResult(
                    ok=False,
                    dry_run=False,
                    steps=steps,
                    error_code=exc.code,
                )
            steps.append(
                MigrationStepResult(
                    filename=entry.filename,
                    status="applied",
                    checksum_prefix=prefix,
                )
            )
        return MigrationRunResult(ok=True, dry_run=False, steps=steps)
    except MigrationManifestError as exc:
        return MigrationRunResult(
            ok=False,
            dry_run=False,
            steps=steps,
            error_code=exc.code,
        )
    except Exception:
        return MigrationRunResult(
            ok=False,
            dry_run=False,
            steps=steps,
            error_code="migration_runtime_failed",
        )
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply tenant PostgreSQL migrations (migrator only).")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate manifest and checksums without connecting or writing.",
    )
    parser.add_argument(
        "--through",
        metavar="FILENAME",
        default=None,
        help="Apply only manifest prefix through this exact migration filename.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=_DEFAULT_MANIFEST,
        help="Path to migrations.manifest",
    )
    args = parser.parse_args(argv)

    if args.dry_run:
        result = run_migrations(
            dsn="",
            dry_run=True,
            manifest_path=args.manifest,
            through=args.through,
        )
    else:
        try:
            dsn = _require_migrator_dsn()
        except MigrationManifestError as exc:
            print(f"error={exc.code}")
            return 2
        result = run_migrations(
            dsn=dsn,
            dry_run=False,
            manifest_path=args.manifest,
            through=args.through,
        )

    for step in result.steps:
        print(f"{step.filename}\t{step.status}\t{step.checksum_prefix}")
    if result.error_code:
        print(f"error={result.error_code}")
        return 1
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
