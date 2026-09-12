"""G8 disposable PostgreSQL integration (real connections; CI G8 job only — no skips)."""

from __future__ import annotations

import os
import uuid
from contextlib import contextmanager
from urllib.parse import urlparse

import psycopg
import psycopg.errors
import pytest

from core.pg_schema_readiness import check_pg_schema_ready
from core.pg_tenant_context import (
    APP_CURRENT_TENANT_GUC,
    InvalidPgTenantError,
    tenant_transaction,
)
from deploy.postgres.g8_disposable_constants import G8_INTEGRATION_SCENARIO_IDS

_MARKER_PREFIX = "g8-int-"
_INSUFFICIENT_PRIVILEGE = "42501"


def _require_g8_active() -> None:
    if os.getenv("G8_QUALIFICATION_ACTIVE") != "1":
        pytest.fail("G8_QUALIFICATION_ACTIVE=1 required (run via g8_qualification_runner)")


def _runtime_dsn() -> str:
    dsn = (os.getenv("BOT_PG_DSN") or "").strip()
    if not dsn:
        pytest.fail("BOT_PG_DSN missing")
    return dsn


def _migrator_dsn() -> str:
    dsn = (os.getenv("BOT_MIGRATOR_PG_DSN") or "").strip()
    if not dsn:
        pytest.fail("BOT_MIGRATOR_PG_DSN missing")
    return dsn


def _new_marker() -> str:
    return f"{_MARKER_PREFIX}{uuid.uuid4().hex}"


def _guc_cleared(conn) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT NULLIF(current_setting(%s, true), '') IS NULL",
            (APP_CURRENT_TENANT_GUC,),
        )
        return bool(cur.fetchone()[0])


def _assert_connection_alive(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT 1")
        assert cur.fetchone()[0] == 1


def _expect_sqlstate(conn, sql: str, *, sqlstate: str, params=()) -> None:
    with pytest.raises(psycopg.Error) as exc_info:
        with conn.cursor() as cur:
            cur.execute(sql, params)
    assert exc_info.value.sqlstate == sqlstate
    _assert_connection_alive(conn)


def _cleanup_marker(conn, tenant: str, marker: str) -> None:
    with tenant_transaction(conn, tenant):
        with conn.cursor() as cur:
            cur.execute("DELETE FROM public.bot_events WHERE request_id = %s", (marker,))
            cur.execute("DELETE FROM public.v5_turn_traces WHERE turn_id = %s", (marker,))
            cur.execute("DELETE FROM public.leads WHERE request_id = %s", (marker,))


@contextmanager
def _marker_scope(conn, marker: str):
    try:
        yield marker
    finally:
        for tenant in ("demo", "nikadent"):
            _cleanup_marker(conn, tenant, marker)


def _seed_bot_event(conn, tenant: str, marker: str, sid: str | None = None) -> int:
    sid_val = sid or f"sid-{marker[:8]}"
    with tenant_transaction(conn, tenant):
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.bot_events (
                  occurred_at, kind, event_type, schema_version,
                  request_id, sid, client_id, details
                )
                VALUES (now(), 'bot_event', %s, 1, %s, %s, %s, '{}'::jsonb)
                RETURNING id
                """,
                (marker, marker, sid_val, tenant),
            )
            return int(cur.fetchone()[0])


@pytest.fixture(scope="module")
def g8_runtime_conn():
    _require_g8_active()
    with psycopg.connect(_runtime_dsn(), autocommit=True) as conn:
        ready, reason = check_pg_schema_ready(conn)
        if not ready:
            pytest.fail(f"schema_not_ready:{reason}")
        yield conn


class TestG8DisposablePrimary:
    def test_scenario_01_tenant_a_writes(self, g8_runtime_conn) -> None:
        marker = _new_marker()
        with _marker_scope(g8_runtime_conn, marker):
            row_id = _seed_bot_event(g8_runtime_conn, "demo", marker)
            assert row_id > 0

    def test_scenario_02_tenant_b_writes(self, g8_runtime_conn) -> None:
        marker = _new_marker()
        with _marker_scope(g8_runtime_conn, marker):
            row_id = _seed_bot_event(g8_runtime_conn, "nikadent", marker)
            assert row_id > 0

    def test_scenario_03_tenant_a_cannot_read_b(self, g8_runtime_conn) -> None:
        marker = _new_marker()
        with _marker_scope(g8_runtime_conn, marker):
            row_id = _seed_bot_event(g8_runtime_conn, "nikadent", marker)
            with tenant_transaction(g8_runtime_conn, "demo"):
                with g8_runtime_conn.cursor() as cur:
                    cur.execute("SELECT count(*) FROM public.bot_events WHERE id=%s", (row_id,))
                    assert cur.fetchone()[0] == 0

    def test_scenario_04_tenant_b_cannot_read_a(self, g8_runtime_conn) -> None:
        marker = _new_marker()
        with _marker_scope(g8_runtime_conn, marker):
            row_id = _seed_bot_event(g8_runtime_conn, "demo", marker)
            with tenant_transaction(g8_runtime_conn, "nikadent"):
                with g8_runtime_conn.cursor() as cur:
                    cur.execute("SELECT count(*) FROM public.bot_events WHERE id=%s", (row_id,))
                    assert cur.fetchone()[0] == 0

    def test_scenario_05_runtime_without_tenant_reads_zero(self, g8_runtime_conn) -> None:
        marker = _new_marker()
        with _marker_scope(g8_runtime_conn, marker):
            _seed_bot_event(g8_runtime_conn, "demo", marker)
            with g8_runtime_conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FROM public.bot_events WHERE request_id=%s",
                    (marker,),
                )
                assert cur.fetchone()[0] == 0

    def test_scenario_06_tenant_context_substitution_blocked(self, g8_runtime_conn) -> None:
        marker = _new_marker()
        with _marker_scope(g8_runtime_conn, marker):
            with tenant_transaction(g8_runtime_conn, "demo"):
                with pytest.raises(psycopg.Error) as exc_info:
                    with g8_runtime_conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO public.bot_events (
                              occurred_at, kind, event_type, schema_version,
                              client_id, request_id, details
                            ) VALUES (now(), 'bot_event', %s, 1, %s, %s, '{}'::jsonb)
                            """,
                            (marker, "nikadent", marker),
                        )
                assert exc_info.value.sqlstate == _INSUFFICIENT_PRIVILEGE
            _assert_connection_alive(g8_runtime_conn)

    def test_scenario_07_connection_reuse_clears_tenant_context(self, g8_runtime_conn) -> None:
        marker_a = _new_marker()
        marker_b = _new_marker()
        with _marker_scope(g8_runtime_conn, marker_a):
            with _marker_scope(g8_runtime_conn, marker_b):
                _seed_bot_event(g8_runtime_conn, "demo", marker_a)
                assert _guc_cleared(g8_runtime_conn)
                row_b = _seed_bot_event(g8_runtime_conn, "nikadent", marker_b)
                with tenant_transaction(g8_runtime_conn, "nikadent"):
                    with g8_runtime_conn.cursor() as cur:
                        cur.execute(
                            "SELECT count(*) FROM public.bot_events WHERE request_id=%s",
                            (marker_a,),
                        )
                        assert cur.fetchone()[0] == 0
                        cur.execute("SELECT count(*) FROM public.bot_events WHERE id=%s", (row_b,))
                        assert cur.fetchone()[0] == 1

    def test_scenario_08_rollback_clears_tenant_context(self, g8_runtime_conn) -> None:
        marker = _new_marker()
        with _marker_scope(g8_runtime_conn, marker):
            with pytest.raises(RuntimeError):
                with tenant_transaction(g8_runtime_conn, "demo"):
                    raise RuntimeError("g8-rollback-test")
            assert _guc_cleared(g8_runtime_conn)
            _assert_connection_alive(g8_runtime_conn)

    def test_scenario_09_runtime_cannot_disable_rls(self, g8_runtime_conn) -> None:
        _expect_sqlstate(
            g8_runtime_conn,
            "ALTER TABLE public.bot_events DISABLE ROW LEVEL SECURITY",
            sqlstate=_INSUFFICIENT_PRIVILEGE,
        )

    def test_scenario_10_runtime_cannot_execute_ddl(self, g8_runtime_conn) -> None:
        _expect_sqlstate(
            g8_runtime_conn,
            "CREATE TABLE public.g8_forbidden (id int)",
            sqlstate=_INSUFFICIENT_PRIVILEGE,
        )

    def test_scenario_11_runtime_cannot_read_migration_ledger(self, g8_runtime_conn) -> None:
        _expect_sqlstate(
            g8_runtime_conn,
            "SELECT count(*) FROM bot_migration.schema_migrations",
            sqlstate=_INSUFFICIENT_PRIVILEGE,
        )

    def test_scenario_12_migrator_can_apply_migration(self) -> None:
        _require_g8_active()
        with psycopg.connect(_migrator_dsn(), autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "CREATE TABLE public.g8_migrator_ddl_probe (id int PRIMARY KEY)"
                )
                cur.execute("DROP TABLE public.g8_migrator_ddl_probe")

    def test_scenario_13_retention_limited_to_current_tenant(self, g8_runtime_conn) -> None:
        from pg_retention import purge_session_observability

        marker_demo = _new_marker()
        marker_nika = _new_marker()
        sid = f"g8-ret-{uuid.uuid4().hex[:6]}"
        with _marker_scope(g8_runtime_conn, marker_demo):
            with _marker_scope(g8_runtime_conn, marker_nika):
                _seed_bot_event(g8_runtime_conn, "demo", marker_demo, sid=sid)
                _seed_bot_event(g8_runtime_conn, "nikadent", marker_nika, sid=sid)
                stats = purge_session_observability(
                    _runtime_dsn(), sid=sid, client_id="demo"
                )
                assert stats["found"] is True
                assert int(stats["bot_events_deleted"]) >= 1
                with tenant_transaction(g8_runtime_conn, "demo"):
                    with g8_runtime_conn.cursor() as cur:
                        cur.execute(
                            "SELECT count(*) FROM public.bot_events WHERE request_id=%s",
                            (marker_demo,),
                        )
                        assert cur.fetchone()[0] == 0
                with tenant_transaction(g8_runtime_conn, "nikadent"):
                    with g8_runtime_conn.cursor() as cur:
                        cur.execute(
                            "SELECT count(*) FROM public.bot_events WHERE request_id=%s",
                            (marker_nika,),
                        )
                        assert cur.fetchone()[0] == 1

    def test_scenario_14_invalid_unknown_tenant_fail_closed(self) -> None:
        _require_g8_active()
        with pytest.raises(InvalidPgTenantError):
            with psycopg.connect(_runtime_dsn(), autocommit=True) as conn:
                with tenant_transaction(conn, "not_a_real_tenant_pack"):
                    pass


def test_g8_integration_scenario_registry_complete() -> None:
    """Offline-safe: primary class exposes every mandated scenario id."""
    import inspect

    methods = {
        name
        for name, _ in inspect.getmembers(TestG8DisposablePrimary, predicate=inspect.isfunction)
        if name.startswith("test_scenario_")
    }
    expected = {f"test_{sid}" for sid in G8_INTEGRATION_SCENARIO_IDS}
    assert methods == expected


class TestG8DisposableAfterRestore:
    def test_restore_schema_readiness(self, g8_runtime_conn) -> None:
        _require_g8_active()
        db = urlparse(_runtime_dsn()).path.lstrip("/")
        expected = (os.getenv("G8_RESTORE_DATABASE") or "g8_qual_restored").strip()
        assert db == expected
        ready, reason = check_pg_schema_ready(g8_runtime_conn)
        assert ready, reason

    def test_restore_grants_target_restored_database(self, g8_runtime_conn) -> None:
        _require_g8_active()
        active = (os.getenv("G8_ACTIVE_DATABASE") or "").strip()
        assert active == (os.getenv("G8_RESTORE_DATABASE") or "g8_qual_restored").strip()
        with g8_runtime_conn.cursor() as cur:
            cur.execute("SELECT current_database()")
            assert cur.fetchone()[0] == active
            cur.execute(
                "SELECT has_schema_privilege(current_user, 'public', 'CREATE')"
            )
            assert cur.fetchone()[0] is False

    def test_restore_migration_ledger_matches_manifest(self) -> None:
        _require_g8_active()
        from pathlib import Path

        from deploy.postgres.migration_manifest import load_manifest

        root = Path(__file__).resolve().parents[1]
        manifest = root / "deploy" / "postgres" / "migrations.manifest"
        mig_dir = root / "migrations" / "postgresql"
        expected = {e.filename: e.checksum for e in load_manifest(manifest, mig_dir)}
        with psycopg.connect(_migrator_dsn(), autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT filename, checksum FROM bot_migration.schema_migrations ORDER BY filename"
                )
                rows = {str(r[0]): str(r[1]) for r in cur.fetchall()}
        assert rows == expected

    def test_restore_sentinel_row_counts(self, g8_runtime_conn) -> None:
        demo_marker = (os.getenv("G8_SENTINEL_MARKER_DEMO") or "").strip()
        nika_marker = (os.getenv("G8_SENTINEL_MARKER_NIKA") or "").strip()
        if not demo_marker or not nika_marker:
            pytest.fail("restore_sentinel_markers_missing")
        with tenant_transaction(g8_runtime_conn, "demo"):
            with g8_runtime_conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FROM public.bot_events WHERE request_id=%s",
                    (demo_marker,),
                )
                assert cur.fetchone()[0] == 1
        with tenant_transaction(g8_runtime_conn, "nikadent"):
            with g8_runtime_conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FROM public.bot_events WHERE request_id=%s",
                    (nika_marker,),
                )
                assert cur.fetchone()[0] == 1

    def test_restore_tenant_isolation(self, g8_runtime_conn) -> None:
        demo_marker = (os.getenv("G8_SENTINEL_MARKER_DEMO") or "").strip()
        if not demo_marker:
            pytest.fail("restore_sentinel_markers_missing")
        with tenant_transaction(g8_runtime_conn, "nikadent"):
            with g8_runtime_conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FROM public.bot_events WHERE request_id=%s",
                    (demo_marker,),
                )
                assert cur.fetchone()[0] == 0

    def test_restore_no_tenant_context_reads_zero(self, g8_runtime_conn) -> None:
        demo_marker = (os.getenv("G8_SENTINEL_MARKER_DEMO") or "").strip()
        if not demo_marker:
            pytest.fail("restore_sentinel_markers_missing")
        with g8_runtime_conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM public.bot_events WHERE request_id=%s",
                (demo_marker,),
            )
            assert cur.fetchone()[0] == 0
