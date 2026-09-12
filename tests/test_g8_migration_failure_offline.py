"""G8 safe migration failure diagnostics (offline)."""

from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout
from unittest.mock import MagicMock

import pytest

from deploy.postgres import migrate as migrate_mod
from deploy.postgres.g8_disposable import _fetch_ledger_schema_migrations_oid
from deploy.postgres.g8_qualification_runner import (
    G8MigrationFailure,
    _migration_failure_from_result,
    _print_g8_failure,
)
from deploy.postgres.migrate import MigrationRunResult, run_migrations, safe_sqlstate_from_exception
from deploy.postgres.migration_manifest import load_manifest

_ROOT = migrate_mod._REPO_ROOT
_MANIFEST = _ROOT / "deploy" / "postgres" / "migrations.manifest"
_MIG_DIR = _ROOT / "migrations" / "postgresql"


class _SqlstateError(Exception):
    def __init__(self, sqlstate: str) -> None:
        self.sqlstate = sqlstate
        super().__init__("sensitive-sql-error")


def test_safe_sqlstate_accepts_valid_five_char_code() -> None:
    assert safe_sqlstate_from_exception(_SqlstateError("42601")) == "42601"


def test_safe_sqlstate_rejects_invalid_or_dangerous_values() -> None:
    assert safe_sqlstate_from_exception(_SqlstateError("4260")) is None
    assert safe_sqlstate_from_exception(_SqlstateError("password leak")) is None
    assert safe_sqlstate_from_exception(Exception("no sqlstate")) is None


def test_migration_sql_failed_records_filename_and_sqlstate() -> None:
    entries = load_manifest(_MANIFEST, _MIG_DIR)
    target = entries[0].filename

    class _Cur:
        def __init__(self) -> None:
            self._lock_calls = 0

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def execute(self, sql, params=None):
            if "INSERT INTO bot_migration" in sql:
                raise AssertionError("ledger insert must not run on SQL failure")

        def fetchone(self):
            self._lock_calls += 1
            if self._lock_calls == 1:
                return (True,)
            return None

        def fetchall(self):
            return []

    conn = MagicMock()
    conn.cursor.return_value = _Cur()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            migrate_mod,
            "_execute_migration_sql",
            lambda _c, _sql: (_ for _ in ()).throw(_SqlstateError("42601")),
        )
        result = run_migrations(
            dsn="postgresql://migrator:secret@localhost/db",
            dry_run=False,
            connect_fn=lambda *_a, **_k: conn,
        )
    assert result.ok is False
    assert result.error_code == "migration_sql_failed"
    assert result.failed_filename == target
    assert result.sqlstate == "42601"


def test_migration_connect_failed_records_safe_sqlstate_only() -> None:
    def _connect_fail(*_a, **_k):
        raise _SqlstateError("08001")

    result = run_migrations(
        dsn="postgresql://migrator@localhost/db",
        dry_run=False,
        connect_fn=_connect_fail,
    )
    assert result.error_code == "migration_connect_failed"
    assert result.sqlstate == "08001"
    assert result.failed_filename is None


def test_g8_migration_failure_prints_safe_fields(capsys: pytest.CaptureFixture[str]) -> None:
    exc = G8MigrationFailure(
        code="migration_sql_failed",
        migration="002_tenant_schema_prepare.sql",
        sqlstate="42601",
    )
    _print_g8_failure("migrate_primary", exc)
    out = capsys.readouterr().out.strip()
    assert out == (
        "g8_qualification=failed stage=migrate_primary "
        "detail=G8MigrationFailure code=migration_sql_failed "
        "migration=002_tenant_schema_prepare.sql sqlstate=42601"
    )
    assert "secret" not in out
    assert "postgresql://" not in out


def test_g8_migration_failure_from_result_preserves_codes() -> None:
    result = MigrationRunResult(
        ok=False,
        dry_run=False,
        steps=[],
        error_code="migration_sql_failed",
        failed_filename="003_tenant_rls_enable.sql",
        sqlstate="42501",
    )
    exc = _migration_failure_from_result(result)
    assert exc.code == "migration_sql_failed"
    assert exc.migration == "003_tenant_rls_enable.sql"
    assert exc.sqlstate == "42501"


def test_fetch_ledger_schema_migrations_oid_requires_exactly_one_row() -> None:
    class _Cur:
        def __init__(self, rows: list[tuple[int]]) -> None:
            self._rows = rows

        def execute(self, sql, params=None):
            self._sql = sql

        def fetchall(self):
            return self._rows

    with pytest.raises(RuntimeError, match="ledger_relation_oid_invalid"):
        _fetch_ledger_schema_migrations_oid(_Cur([]))
    with pytest.raises(RuntimeError, match="ledger_relation_oid_invalid"):
        _fetch_ledger_schema_migrations_oid(_Cur([(1,), (2,)]))
    assert _fetch_ledger_schema_migrations_oid(_Cur([(4242,)])) == 4242


def test_g8_failure_stdout_never_leaks_dsn_or_password() -> None:
    dsn = "postgresql://bot_runtime:super_secret@127.0.0.1:5432/g8_qual_primary"
    exc = Exception(f"connect failed for {dsn} password=super_secret")
    buf = io.StringIO()
    with redirect_stdout(buf):
        _print_g8_failure("migrate_primary", exc)
    out = buf.getvalue()
    assert "super_secret" not in out
    assert "postgresql://" not in out
    assert "password" not in out.lower()
