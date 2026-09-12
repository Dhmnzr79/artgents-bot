#!/usr/bin/env python3
"""G8 disposable PostgreSQL qualification orchestrator (CI / local Docker only)."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from deploy.postgres import migrate as migrate_mod
from deploy.postgres.g8_disposable import (
    apply_post_migrate_grants,
    assert_migrator_role_catalog,
    assert_runtime_role_catalog,
    bootstrap_disposable_primary,
    bootstrap_superuser_dsn,
    create_restore_database,
    drop_restore_database_if_exists,
    migrator_dsn,
    prepare_restore_database_schema,
    runtime_dsn,
    wait_for_postgres_ready,
)
from deploy.postgres.g8_disposable_constants import (
    G8_AFTER_RESTORE_TEST_COUNT,
    G8_BOOTSTRAP_PASSWORD,
    G8_BOOTSTRAP_USER,
    G8_PRIMARY_DATABASE,
    G8_PRIMARY_SCENARIO_COUNT,
    G8_RESTORE_DATABASE,
)
from deploy.postgres.g8_docker_pg import (
    pg_dump_custom_to_file,
    pg_restore_into_database,
    pg_restore_list_archive,
    validated_postgres_container_id,
)
from deploy.postgres.g8_junit import assert_junit_exact_passed
from deploy.postgres.migration_manifest import load_manifest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MANIFEST = _REPO_ROOT / "deploy" / "postgres" / "migrations.manifest"
_MIGRATIONS_DIR = _REPO_ROOT / "migrations" / "postgresql"
_G7_HELPER = _REPO_ROOT / "deploy" / "production" / "server" / "backup_postgres_g7.py"
_INTEGRATION_PRIMARY = (
    "tests/test_g8_postgres_qualification_integration.py::TestG8DisposablePrimary"
)
_INTEGRATION_RESTORE = (
    "tests/test_g8_postgres_qualification_integration.py::TestG8DisposableAfterRestore"
)


def _load_g7():
    spec = importlib.util.spec_from_file_location("backup_postgres_g7", _G7_HELPER)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _qualify_roles(database: str) -> None:
    import psycopg

    with psycopg.connect(runtime_dsn(database), autocommit=True) as conn:
        assert_runtime_role_catalog(conn)
    with psycopg.connect(migrator_dsn(database), autocommit=True) as conn:
        assert_migrator_role_catalog(conn)


def _seed_restore_sentinels() -> None:
    import psycopg

    from core.pg_tenant_context import tenant_transaction

    demo_marker = f"g8-restore-demo-{uuid.uuid4().hex[:12]}"
    nika_marker = f"g8-restore-nika-{uuid.uuid4().hex[:12]}"
    os.environ["G8_SENTINEL_MARKER_DEMO"] = demo_marker
    os.environ["G8_SENTINEL_MARKER_NIKA"] = nika_marker
    os.environ["G8_RESTORE_DATABASE"] = G8_RESTORE_DATABASE
    with psycopg.connect(runtime_dsn(G8_PRIMARY_DATABASE), autocommit=True) as conn:
        with tenant_transaction(conn, "demo"):
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.bot_events (
                      occurred_at, kind, event_type, schema_version,
                      request_id, sid, client_id, details
                    )
                    VALUES (now(), 'bot_event', %s, 1, %s, %s, %s, '{}'::jsonb)
                    """,
                    (demo_marker, demo_marker, f"sid-{demo_marker[:8]}", "demo"),
                )
        with tenant_transaction(conn, "nikadent"):
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.bot_events (
                      occurred_at, kind, event_type, schema_version,
                      request_id, sid, client_id, details
                    )
                    VALUES (now(), 'bot_event', %s, 1, %s, %s, %s, '{}'::jsonb)
                    """,
                    (nika_marker, nika_marker, f"sid-{nika_marker[:8]}", "nikadent"),
                )


def _run_migrations_twice() -> None:
    os.environ["BOT_MIGRATOR_PG_DSN"] = migrator_dsn()
    first = migrate_mod.run_migrations(dsn=os.environ["BOT_MIGRATOR_PG_DSN"], dry_run=False)
    if not first.ok:
        raise RuntimeError(f"migration_first_run_failed:{first.error_code}")
    second = migrate_mod.run_migrations(dsn=os.environ["BOT_MIGRATOR_PG_DSN"], dry_run=False)
    if not second.ok:
        raise RuntimeError(f"migration_second_run_failed:{second.error_code}")
    if any(step.status != "skipped" for step in second.steps):
        raise RuntimeError("migration_idempotency_failed:not_all_skipped")


def _verify_ledger(database: str) -> None:
    import psycopg

    entries = load_manifest(_MANIFEST, _MIGRATIONS_DIR)
    expected = {e.filename: e.checksum for e in entries}
    with psycopg.connect(migrator_dsn(database), autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT filename, checksum FROM bot_migration.schema_migrations ORDER BY filename"
            )
            rows = {str(r[0]): str(r[1]) for r in cur.fetchall()}
    if rows != expected:
        raise RuntimeError("migration_ledger_mismatch")


def _set_runtime_env(database: str) -> None:
    os.environ["G8_QUALIFICATION_ACTIVE"] = "1"
    os.environ["BOT_PG_DSN"] = runtime_dsn(database)
    os.environ["BOT_MIGRATOR_PG_DSN"] = migrator_dsn(database)
    os.environ["G8_PRIMARY_DATABASE"] = G8_PRIMARY_DATABASE
    os.environ["G8_ACTIVE_DATABASE"] = database


def _pytest_strict(node_id: str, junit_path: Path, expected_passed: int) -> None:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "--tb=short",
            "-q",
            f"--junitxml={junit_path}",
            node_id,
        ],
        cwd=_REPO_ROOT,
        env=env,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"pytest_exit_nonzero:{node_id}")
    assert_junit_exact_passed(junit_path, expected_passed=expected_passed)


def _make_g7_backup_layout(work_dir: Path) -> tuple[Path, Path, Path]:
    parent = work_dir / "backups"
    archive_root = parent / "postgres"
    receipt_root = parent / "receipts"
    parent.mkdir(mode=0o700)
    archive_root.mkdir(mode=0o700)
    receipt_root.mkdir(mode=0o700)
    return parent, archive_root, receipt_root


def _backup_restore_drill(g7_mod, work_dir: Path) -> tuple[Path, Path]:
    validated_postgres_container_id()
    backups_parent, archive_root, receipt_root = _make_g7_backup_layout(work_dir)

    now = datetime.now(timezone.utc)
    created_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    file_ts = g7_mod.created_at_to_filename_timestamp(created_at)
    backup_id, unique_suffix = g7_mod.generate_backup_identity()
    stem = f"pgbackup-scheduled-{file_ts}-{unique_suffix}"
    archive = archive_root / f"{stem}.pgdump.custom"
    receipt = receipt_root / f"{stem}.receipt.json"

    pg_dump_custom_to_file(
        user=G8_BOOTSTRAP_USER,
        database=G8_PRIMARY_DATABASE,
        archive_path=archive,
    )
    pg_restore_list_archive(archive)

    archive_sha = g7_mod.sha256_file(archive)
    payload = g7_mod.build_receipt_payload(
        reason="scheduled",
        source_sha=None,
        created_at=created_at,
        archive_path=str(archive),
        archive_sha256=archive_sha,
        archive_size_bytes=archive.stat().st_size,
        database_name=G8_PRIMARY_DATABASE,
        backup_id=backup_id,
    )
    g7_mod.write_receipt_atomic(receipt, payload)
    g7_mod.verify_receipt_file(
        receipt,
        archive_root=archive_root,
        receipt_root=receipt_root,
        backups_parent=backups_parent,
        enforce_root_metadata=False,
    )

    import psycopg

    with psycopg.connect(bootstrap_superuser_dsn(G8_PRIMARY_DATABASE), autocommit=True) as conn:
        drop_restore_database_if_exists(conn)
        create_restore_database(conn)

    with psycopg.connect(bootstrap_superuser_dsn(G8_RESTORE_DATABASE), autocommit=True) as conn:
        prepare_restore_database_schema(conn)

    pg_restore_into_database(
        user=G8_BOOTSTRAP_USER,
        database=G8_RESTORE_DATABASE,
        archive_path=archive,
        role="bot_migrator",
    )

    with psycopg.connect(bootstrap_superuser_dsn(G8_RESTORE_DATABASE), autocommit=True) as conn:
        apply_post_migrate_grants(conn)

    return archive, receipt


def _cleanup_work_dir(work_dir: Path) -> None:
    if work_dir.is_dir():
        shutil.rmtree(work_dir, ignore_errors=True)


def _try_drop_restored_db() -> None:
    import psycopg

    try:
        with psycopg.connect(bootstrap_superuser_dsn(G8_PRIMARY_DATABASE), autocommit=True) as conn:
            drop_restore_database_if_exists(conn)
    except Exception:
        pass


def main() -> int:
    os.environ.setdefault("G8_BOOTSTRAP_USER", G8_BOOTSTRAP_USER)
    os.environ.setdefault("G8_BOOTSTRAP_PASSWORD", G8_BOOTSTRAP_PASSWORD)

    g7_mod = _load_g7()
    work_dir = Path(tempfile.mkdtemp(prefix="g8-qual-"))
    junit_primary = work_dir / "junit-primary.xml"
    junit_restore = work_dir / "junit-restore.xml"
    archive_path: Path | None = None
    receipt_path: Path | None = None
    failed: BaseException | None = None
    exit_code = 0
    try:
        wait_for_postgres_ready()
        import psycopg

        with psycopg.connect(bootstrap_superuser_dsn(G8_PRIMARY_DATABASE), autocommit=True) as conn:
            bootstrap_disposable_primary(conn)

        _run_migrations_twice()

        with psycopg.connect(bootstrap_superuser_dsn(G8_PRIMARY_DATABASE), autocommit=True) as conn:
            apply_post_migrate_grants(conn)

        _verify_ledger(G8_PRIMARY_DATABASE)
        _qualify_roles(G8_PRIMARY_DATABASE)
        _set_runtime_env(G8_PRIMARY_DATABASE)
        _pytest_strict(_INTEGRATION_PRIMARY, junit_primary, G8_PRIMARY_SCENARIO_COUNT)

        _seed_restore_sentinels()
        archive_path, receipt_path = _backup_restore_drill(g7_mod, work_dir)
        _verify_ledger(G8_RESTORE_DATABASE)
        _qualify_roles(G8_RESTORE_DATABASE)
        _set_runtime_env(G8_RESTORE_DATABASE)
        _pytest_strict(_INTEGRATION_RESTORE, junit_restore, G8_AFTER_RESTORE_TEST_COUNT)
        print("g8_qualification=ok")
    except BaseException as exc:
        failed = exc
        print(f"g8_qualification=failed detail={exc.__class__.__name__}")
        exit_code = 1
    finally:
        for path in (archive_path, receipt_path):
            if path is not None:
                path.unlink(missing_ok=True)
        _cleanup_work_dir(work_dir)
        _try_drop_restored_db()

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
