"""T6B pass 2: migration manifest, ledger, migrator runner (offline / fakes only)."""
from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from deploy.postgres import migrate as migrate_mod
from deploy.postgres.migration_manifest import (
    MIGRATION_ADVISORY_LOCK_KEY,
    LedgerRow,
    MigrationManifestError,
    load_manifest,
    manifest_prefix_entries,
    plan_actions,
    reconcile_ledger,
    sha256_bytes,
    sha256_file,
)
from deploy.postgres.migrate import MigrationRunResult, main, redact_dsn, run_migrations, safe_error_message

_ROOT = Path(__file__).resolve().parents[1]
_MANIFEST = _ROOT / "deploy" / "postgres" / "migrations.manifest"
_MIG_DIR = _ROOT / "migrations" / "postgresql"


def test_manifest_order_matches_greenfield() -> None:
    entries = load_manifest(_MANIFEST, _MIG_DIR)
    names = [e.filename for e in entries]
    assert names == [
        "002_tenant_schema_prepare.sql",
        "003_tenant_rls_enable.sql",
        "004_tenant_trace_pk_finalize.sql",
    ]


def test_manifest_checksum_deterministic() -> None:
    path = _MIG_DIR / "002_tenant_schema_prepare.sql"
    data = path.read_bytes()
    assert sha256_file(path) == sha256_bytes(data)
    assert sha256_bytes(data) == hashlib.sha256(data).hexdigest()


def test_manifest_duplicate_line(tmp_path: Path) -> None:
    manifest = tmp_path / "m.manifest"
    manifest.write_text("002_tenant_schema_prepare.sql\n002_tenant_schema_prepare.sql\n", encoding="utf-8")
    with pytest.raises(MigrationManifestError) as exc:
        load_manifest(manifest, _MIG_DIR)
    assert exc.value.code == "manifest_duplicate"


def test_manifest_missing_file(tmp_path: Path) -> None:
    manifest = tmp_path / "m.manifest"
    manifest.write_text("999_missing.sql\n", encoding="utf-8")
    with pytest.raises(MigrationManifestError) as exc:
        load_manifest(manifest, _MIG_DIR)
    assert exc.value.code == "manifest_missing_file"


def test_manifest_path_traversal_rejected(tmp_path: Path) -> None:
    manifest = tmp_path / "m.manifest"
    manifest.write_text("../002_tenant_schema_prepare.sql\n", encoding="utf-8")
    with pytest.raises(MigrationManifestError) as exc:
        load_manifest(manifest, _MIG_DIR)
    assert exc.value.code == "manifest_unsafe_path"


def test_plan_skip_when_same_checksum() -> None:
    entries = load_manifest(_MANIFEST, _MIG_DIR)
    first = entries[0]
    ledger = {first.filename: LedgerRow(first.filename, first.checksum)}
    planned = plan_actions(entries, ledger)
    assert planned[0][1] == "skip"
    assert planned[1][1] == "apply"


def test_plan_checksum_mismatch_fails() -> None:
    entries = load_manifest(_MANIFEST, _MIG_DIR)
    first = entries[0]
    ledger = {first.filename: LedgerRow(first.filename, "0" * 64)}
    with pytest.raises(MigrationManifestError) as exc:
        plan_actions(entries, ledger)
    assert exc.value.code == "checksum_mismatch"


def test_ledger_unknown_migration_fails() -> None:
    manifest_names = frozenset({"002_tenant_schema_prepare.sql"})
    with pytest.raises(MigrationManifestError) as exc:
        reconcile_ledger(manifest_names, [LedgerRow("001_tenant_preflight.sql", "abc")])
    assert exc.value.code == "ledger_unknown_migration"


def test_dry_run_no_database_writes() -> None:
    connect = MagicMock()
    result = run_migrations(dsn="", dry_run=True, connect_fn=connect)
    connect.assert_not_called()
    assert result.ok is True
    assert result.dry_run is True
    assert len(result.steps) == 3


def test_dry_run_through_prefix_only() -> None:
    result = run_migrations(
        dsn="",
        dry_run=True,
        through="002_tenant_schema_prepare.sql",
    )
    assert result.ok is True
    assert [s.filename for s in result.steps] == ["002_tenant_schema_prepare.sql"]
    assert result.steps[0].status == "would_apply"


def test_through_invalid_fail_closed_before_connect() -> None:
    connect = MagicMock()
    result = run_migrations(
        dsn="postgresql://migrator@localhost/db",
        dry_run=False,
        through="999_not_in_manifest.sql",
        connect_fn=connect,
    )
    connect.assert_not_called()
    assert result.ok is False
    assert result.error_code == "through_target_invalid"


def test_manifest_prefix_entries_contract() -> None:
    entries = load_manifest(_MANIFEST, _MIG_DIR)
    prefix = manifest_prefix_entries(entries, "003_tenant_rls_enable.sql")
    assert [e.filename for e in prefix] == [
        "002_tenant_schema_prepare.sql",
        "003_tenant_rls_enable.sql",
    ]


def test_cli_dry_run_through() -> None:
    code = main(["--dry-run", "--through", "002_tenant_schema_prepare.sql"])
    assert code == 0


def test_checksum_mismatch_not_connect_failed() -> None:
    entries = load_manifest(_MANIFEST, _MIG_DIR)
    bad = LedgerRow(entries[0].filename, "0" * 64)

    class _Cur:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def execute(self, sql, params=None):
            pass

        def fetchone(self):
            return (True,)

        def fetchall(self):
            return [(bad.filename, bad.checksum)]

    conn = MagicMock()
    conn.cursor.return_value = _Cur()
    result = run_migrations(
        dsn="postgresql://migrator@localhost/db",
        dry_run=False,
        connect_fn=lambda *_a, **_k: conn,
    )
    assert result.error_code == "checksum_mismatch"
    assert result.error_code != "migration_connect_failed"


def test_ledger_unknown_migration_error_code() -> None:
    class _Cur:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def execute(self, sql, params=None):
            pass

        def fetchone(self):
            return (True,)

        def fetchall(self):
            return [("001_tenant_preflight.sql", "abc")]

    conn = MagicMock()
    conn.cursor.return_value = _Cur()
    result = run_migrations(
        dsn="postgresql://migrator@localhost/db",
        dry_run=False,
        connect_fn=lambda *_a, **_k: conn,
    )
    assert result.error_code == "ledger_unknown_migration"


def test_through_002_applies_only_first_migration() -> None:
    inserts: list[str] = []

    class _Cur:
        def __init__(self) -> None:
            self._last_sql = ""
            self._last_checksum: str | None = None
            self._expect_checksum_read = False

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def execute(self, sql, params=None):
            self._last_sql = sql
            if params and "INSERT INTO" in sql:
                inserts.append(str(params[0]))
                self._last_checksum = str(params[1])
            if "SELECT checksum FROM" in sql:
                self._expect_checksum_read = True

        def fetchone(self):
            if "pg_try_advisory_lock" in self._last_sql:
                return (True,)
            if self._expect_checksum_read:
                self._expect_checksum_read = False
                return (self._last_checksum,)
            return None

        def fetchall(self):
            return []

    conn = MagicMock()
    conn.cursor.return_value = _Cur()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(migrate_mod, "_execute_migration_sql", lambda _c, _s: None)
        result = run_migrations(
            dsn="postgresql://migrator@localhost/db",
            dry_run=False,
            through="002_tenant_schema_prepare.sql",
            connect_fn=lambda *_a, **_k: conn,
        )
    assert result.ok is True
    assert inserts == ["002_tenant_schema_prepare.sql"]


def test_failure_does_not_record_applied() -> None:
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
            lambda _c, _sql: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        result = run_migrations(
            dsn="postgresql://migrator:secret@localhost/db",
            dry_run=False,
            connect_fn=lambda *_a, **_k: conn,
        )
    assert result.ok is False
    assert result.error_code == "migration_sql_failed"


def test_safe_error_output_redacts_dsn() -> None:
    msg = safe_error_message(Exception("connect failed postgresql://user:sekret@host/db"))
    assert "sekret" not in msg
    assert redact_dsn("postgresql://user:sekret@host/db") == "postgresql://user:***@host/db"


def test_advisory_lock_contract_constant() -> None:
    assert isinstance(MIGRATION_ADVISORY_LOCK_KEY, int)
    assert MIGRATION_ADVISORY_LOCK_KEY > 0


def test_concurrent_runner_busy_lock() -> None:
    class _Cur:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def execute(self, sql, params=None):
            self._last = sql

        def fetchone(self):
            return (False,)

        def fetchall(self):
            return []

    conn = MagicMock()
    conn.cursor.return_value = _Cur()
    result = run_migrations(
        dsn="postgresql://migrator@localhost/bot_test",
        dry_run=False,
        connect_fn=lambda *_a, **_k: conn,
    )
    assert result.ok is False
    assert result.error_code == "advisory_lock_busy"


def test_success_applies_and_records_ledger() -> None:
    entries = load_manifest(_MANIFEST, _MIG_DIR)
    inserts: list[tuple[str, str]] = []

    class _Cur:
        def __init__(self) -> None:
            self._last_checksum: str | None = None
            self._last_sql = ""
            self._expect_checksum_read = False

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def execute(self, sql, params=None):
            self._last_sql = sql
            if params and "INSERT INTO" in sql:
                inserts.append((params[0], params[1]))
                self._last_checksum = str(params[1])
            if "SELECT checksum FROM" in sql:
                self._expect_checksum_read = True

        def fetchone(self):
            if "pg_try_advisory_lock" in self._last_sql:
                return (True,)
            if self._expect_checksum_read:
                self._expect_checksum_read = False
                return (self._last_checksum,)
            return None

        def fetchall(self):
            return []

    conn = MagicMock()
    conn.cursor.return_value = _Cur()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(migrate_mod, "_execute_migration_sql", lambda _c, _s: None)
        result = run_migrations(
            dsn="postgresql://migrator@localhost/bot_test",
            dry_run=False,
            connect_fn=lambda *_a, **_k: conn,
        )
    assert result.ok is True
    assert len(inserts) == 3
    assert inserts[0][0] == entries[0].filename


def test_static_roles_template_no_password() -> None:
    text = (_MIG_DIR / "roles_template.sql").read_text(encoding="utf-8").lower()
    assert "password 'bot" not in text
    assert "grant all on" not in text
    assert "nobypassrls" in text
    assert "revoke create" in text


def test_schema_readiness_does_not_select_tenant_rows() -> None:
    text = (_ROOT / "core" / "pg_schema_readiness.py").read_text(encoding="utf-8").lower()
    assert "from public.bot_events" not in text
    assert "from public.leads" not in text
    assert "from public.v5_turn_traces" not in text


def test_manifest_excludes_001() -> None:
    names = [e.filename for e in load_manifest(_MANIFEST, _MIG_DIR)]
    assert "001_tenant_preflight.sql" not in names


def _fake_conn(lock_ok: bool = True) -> MagicMock:
    class _Cur:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def execute(self, sql, params=None):
            if "pg_try_advisory_lock" in sql and not lock_ok:
                raise RuntimeError("lock query failed")

        def fetchone(self):
            return (True,)

        def fetchall(self):
            return []

    conn = MagicMock()
    conn.cursor.return_value = _Cur()
    return conn


def test_advisory_lock_execute_failure_returns_code() -> None:
    conn = _fake_conn(lock_ok=False)
    result = run_migrations(
        dsn="postgresql://migrator@localhost/db",
        dry_run=False,
        connect_fn=lambda *_a, **_k: conn,
    )
    assert result.ok is False
    assert result.error_code == "advisory_lock_failed"


def test_migration_file_read_failure_code(monkeypatch: pytest.MonkeyPatch) -> None:
    from dataclasses import replace

    conn = _fake_conn()
    entries = load_manifest(_MANIFEST, _MIG_DIR)

    class _BadPath:
        def read_text(self, encoding: str = "utf-8") -> str:
            raise OSError("nope")

    bad_entries = [replace(entries[0], path=_BadPath())] + entries[1:]

    def _load(*_a, **_k):
        return bad_entries

    monkeypatch.setattr(migrate_mod, "load_manifest", _load)
    result = run_migrations(
        dsn="postgresql://migrator@localhost/db",
        dry_run=False,
        connect_fn=lambda *_a, **_k: conn,
    )
    assert result.error_code == "migration_file_read_failed"


def test_unexpected_post_connect_failure_code(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _fake_conn()

    def _boom(_conn):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(migrate_mod, "_ensure_ledger_schema", _boom)
    result = run_migrations(
        dsn="postgresql://migrator@localhost/db",
        dry_run=False,
        connect_fn=lambda *_a, **_k: conn,
    )
    assert result.error_code == "migration_runtime_failed"


def test_cli_prints_safe_error_code_only(capsys, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_MIGRATOR_PG_DSN", "postgresql://migrator:secret@localhost/db")
    conn = _fake_conn(lock_ok=False)
    monkeypatch.setattr(
        migrate_mod,
        "run_migrations",
        lambda **_kw: MigrationRunResult(
            ok=False,
            dry_run=False,
            steps=[],
            error_code="advisory_lock_failed",
        ),
    )
    code = main([])
    captured = capsys.readouterr().out
    assert code != 0
    assert "error=advisory_lock_failed" in captured
    assert "secret" not in captured
    assert "postgresql://" not in captured
