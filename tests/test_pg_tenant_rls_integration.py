"""PostgreSQL RLS integration suite (requires disposable BOT_TEST_PG_DSN).

Prerequisites on the test database:
- Migrations 002, 003, and 004 applied.
- Runtime connection uses a non-owner role (not SUPERUSER / BYPASSRLS).

Without BOT_TEST_PG_DSN the module collects tests but skips them at runtime.
"""
from __future__ import annotations

import os
import uuid
from contextlib import contextmanager
from urllib.parse import urlparse

import pytest

from core.pg_schema_readiness import check_pg_schema_ready
from core.pg_tenant_context import APP_CURRENT_TENANT_GUC, tenant_transaction

_TEST_DSN = (os.getenv("BOT_TEST_PG_DSN") or "").strip()
_RUNTIME_DSN = (os.getenv("BOT_PG_DSN") or "").strip()
_MARKER_PREFIX = "t4b-int-"
_EXPECTED_V5_PK_COLUMNS = ("client_id", "turn_id")


def _db_name(dsn: str) -> str:
    path = urlparse(dsn).path or ""
    return path.lstrip("/").split("?")[0]


def _host_ok(dsn: str) -> bool:
    host = (urlparse(dsn).hostname or "").lower()
    return host in {"localhost", "127.0.0.1"}


def _dsn_allowed(dsn: str) -> bool:
    if not dsn or dsn == _RUNTIME_DSN:
        return False
    if "bot_pgdata" in dsn.lower():
        return False
    if not _host_ok(dsn):
        return False
    name = _db_name(dsn).lower()
    return "test" in name


_SKIP_REASON = (
    "Requires BOT_TEST_PG_DSN (local DB name contains 'test', not BOT_PG_DSN) "
    "with migrations 002+003+004 applied and a runtime non-owner role"
)


def _new_marker() -> str:
    return f"{_MARKER_PREFIX}{uuid.uuid4().hex}"


def _guc_is_cleared_sql() -> str:
    return f"SELECT NULLIF(current_setting(%s, true), '') IS NULL"


def _assert_guc_cleared(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(_guc_is_cleared_sql(), (APP_CURRENT_TENANT_GUC,))
        assert cur.fetchone()[0] is True


def _v5_primary_key_columns(conn) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT a.attname
            FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            JOIN unnest(c.conkey) WITH ORDINALITY AS ck(attnum, ordinality) ON true
            JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ck.attnum
            WHERE n.nspname = 'public'
              AND t.relname = 'v5_turn_traces'
              AND c.contype = 'p'
            ORDER BY ck.ordinality
            """
        )
        return [str(row[0]) for row in cur.fetchall()]


def _runtime_owns_observability_tables(conn) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM pg_tables
            WHERE schemaname = 'public'
              AND tablename IN ('bot_events', 'leads', 'v5_turn_traces')
              AND tableowner = current_user
            LIMIT 1
            """
        )
        return cur.fetchone() is not None


def _assert_integration_db_ready(conn) -> None:
    ready, reason = check_pg_schema_ready(conn)
    if not ready:
        pytest.skip(f"schema not ready: {reason}")
    pk_cols = _v5_primary_key_columns(conn)
    if pk_cols != list(_EXPECTED_V5_PK_COLUMNS):
        pytest.skip(
            "migration 004 not applied: public.v5_turn_traces PRIMARY KEY "
            f"columns are {pk_cols!r}, expected {list(_EXPECTED_V5_PK_COLUMNS)!r}"
        )
    if _runtime_owns_observability_tables(conn):
        pytest.skip(
            "runtime role must not own public.bot_events, public.leads, or "
            "public.v5_turn_traces (apply roles_template.sql)"
        )


def _cleanup_marker(conn, tenant: str, marker: str) -> None:
    with tenant_transaction(conn, tenant):
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM public.bot_events WHERE request_id = %s",
                (marker,),
            )
            cur.execute(
                "DELETE FROM public.v5_turn_traces WHERE turn_id = %s",
                (marker,),
            )
            cur.execute(
                "DELETE FROM public.leads WHERE request_id = %s",
                (marker,),
            )


@contextmanager
def _marker_scope(conn, marker: str):
    errors: list[BaseException] = []
    try:
        yield marker
    finally:
        for tenant in ("demo", "nikadent"):
            try:
                _cleanup_marker(conn, tenant, marker)
            except BaseException as exc:
                errors.append(exc)
        if errors:
            raise AssertionError(
                f"cleanup failed for marker {marker!r} ({len(errors)} error(s)): {errors!r}"
            ) from errors[0]


def _seed_bot_event(conn, tenant: str, marker: str, sid: str | None = None) -> int:
    sid_val = sid or f"sid-{marker[:12]}"
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


def _insert_bot_event_in_open_transaction(
    conn, tenant: str, marker: str, sid: str | None = None
) -> int:
    """Insert within the caller's active tenant_transaction (no nested tenant_transaction)."""
    sid_val = sid or f"sid-{marker[:12]}"
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


def _seed_v5_trace(conn, tenant: str, marker: str) -> None:
    with tenant_transaction(conn, tenant):
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.v5_turn_traces (
                  turn_id, ts, sid, client_id, request_id,
                  gate_traces, retrieval_candidates, errors
                )
                VALUES (%s, now(), %s, %s, %s, '[]'::jsonb, '[]'::jsonb, '[]'::jsonb)
                ON CONFLICT (client_id, turn_id) DO UPDATE SET ts = EXCLUDED.ts
                """,
                (marker, f"sid-{marker[:8]}", tenant, marker),
            )


@pytest.fixture(scope="module")
def pg_integration_conn():
    if not _TEST_DSN or not _dsn_allowed(_TEST_DSN):
        pytest.skip(_SKIP_REASON)
    import psycopg

    with psycopg.connect(_TEST_DSN, autocommit=True) as conn:
        _assert_integration_db_ready(conn)
    with psycopg.connect(_TEST_DSN, autocommit=True) as conn:
        yield conn


INTEGRATION_SCENARIO_COUNT = 14


@pytest.mark.skipif(not _TEST_DSN or not _dsn_allowed(_TEST_DSN), reason=_SKIP_REASON)
class TestPgTenantRlsIntegration:
    def test_tenant_a_reads_only_a(self, pg_integration_conn) -> None:
        marker = _new_marker()
        with _marker_scope(pg_integration_conn, marker):
            row_id = _seed_bot_event(pg_integration_conn, "demo", marker)
            with tenant_transaction(pg_integration_conn, "demo"):
                with pg_integration_conn.cursor() as cur:
                    cur.execute("SELECT count(*) FROM public.bot_events WHERE id=%s", (row_id,))
                    assert cur.fetchone()[0] == 1
            with tenant_transaction(pg_integration_conn, "nikadent"):
                with pg_integration_conn.cursor() as cur:
                    cur.execute("SELECT count(*) FROM public.bot_events WHERE id=%s", (row_id,))
                    assert cur.fetchone()[0] == 0

    def test_cross_tenant_update_blocked(self, pg_integration_conn) -> None:
        marker = _new_marker()
        with _marker_scope(pg_integration_conn, marker):
            row_id = _seed_bot_event(pg_integration_conn, "demo", marker)
            with tenant_transaction(pg_integration_conn, "nikadent"):
                with pg_integration_conn.cursor() as cur:
                    cur.execute(
                        "UPDATE public.bot_events SET event_type='hijack' WHERE id=%s",
                        (row_id,),
                    )
                    assert cur.rowcount == 0
            with tenant_transaction(pg_integration_conn, "demo"):
                with pg_integration_conn.cursor() as cur:
                    cur.execute(
                        "SELECT event_type FROM public.bot_events WHERE id=%s",
                        (row_id,),
                    )
                    assert cur.fetchone()[0] == marker

    def test_cross_tenant_delete_blocked(self, pg_integration_conn) -> None:
        marker = _new_marker()
        with _marker_scope(pg_integration_conn, marker):
            row_id = _seed_bot_event(pg_integration_conn, "demo", marker)
            with tenant_transaction(pg_integration_conn, "nikadent"):
                with pg_integration_conn.cursor() as cur:
                    cur.execute("DELETE FROM public.bot_events WHERE id=%s", (row_id,))
                    assert cur.rowcount == 0
            with tenant_transaction(pg_integration_conn, "demo"):
                with pg_integration_conn.cursor() as cur:
                    cur.execute("SELECT count(*) FROM public.bot_events WHERE id=%s", (row_id,))
                    assert cur.fetchone()[0] == 1

    def test_cross_tenant_insert_blocked(self, pg_integration_conn) -> None:
        marker = _new_marker()
        with _marker_scope(pg_integration_conn, marker):
            with pytest.raises(Exception):
                with tenant_transaction(pg_integration_conn, "demo"):
                    with pg_integration_conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO public.bot_events (
                              occurred_at, kind, event_type, schema_version,
                              client_id, request_id, details
                            ) VALUES (now(), 'bot_event', %s, 1, %s, %s, '{}'::jsonb)
                            """,
                            (marker, "nikadent", marker),
                        )

    def test_unset_tenant_reads_zero(self, pg_integration_conn) -> None:
        marker = _new_marker()
        with _marker_scope(pg_integration_conn, marker):
            _seed_bot_event(pg_integration_conn, "demo", marker)
            with pg_integration_conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FROM public.bot_events WHERE request_id=%s",
                    (marker,),
                )
                assert cur.fetchone()[0] == 0

    def test_blank_tenant_reads_zero(self, pg_integration_conn) -> None:
        marker = _new_marker()
        with _marker_scope(pg_integration_conn, marker):
            _seed_bot_event(pg_integration_conn, "demo", marker)
            with pg_integration_conn.transaction():
                with pg_integration_conn.cursor() as cur:
                    cur.execute("SELECT set_config(%s, %s, true)", (APP_CURRENT_TENANT_GUC, ""))
                    cur.execute(
                        "SELECT count(*) FROM public.bot_events WHERE request_id=%s",
                        (marker,),
                    )
                    assert cur.fetchone()[0] == 0

    def test_rollback_clears_transaction_local_guc(self, pg_integration_conn) -> None:
        marker = _new_marker()
        with _marker_scope(pg_integration_conn, marker):
            _seed_bot_event(pg_integration_conn, "demo", marker)
            with pytest.raises(RuntimeError):
                with tenant_transaction(pg_integration_conn, "demo"):
                    raise RuntimeError("rollback-guc-test")
            _assert_guc_cleared(pg_integration_conn)
            with pg_integration_conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FROM public.bot_events WHERE request_id=%s",
                    (marker,),
                )
                assert cur.fetchone()[0] == 0

    def test_same_connection_a_error_then_b(self, pg_integration_conn) -> None:
        marker_a = _new_marker()
        marker_b = _new_marker()
        with _marker_scope(pg_integration_conn, marker_a):
            with _marker_scope(pg_integration_conn, marker_b):
                with pytest.raises(RuntimeError):
                    with tenant_transaction(pg_integration_conn, "demo"):
                        _insert_bot_event_in_open_transaction(
                            pg_integration_conn, "demo", marker_a
                        )
                        raise RuntimeError("fail-after-seed")
                _assert_guc_cleared(pg_integration_conn)
                with tenant_transaction(pg_integration_conn, "demo"):
                    with pg_integration_conn.cursor() as cur:
                        cur.execute(
                            "SELECT count(*) FROM public.bot_events WHERE request_id=%s",
                            (marker_a,),
                        )
                        assert cur.fetchone()[0] == 0
                row_b = _seed_bot_event(pg_integration_conn, "nikadent", marker_b)
                with tenant_transaction(pg_integration_conn, "nikadent"):
                    with pg_integration_conn.cursor() as cur:
                        cur.execute("SELECT count(*) FROM public.bot_events WHERE id=%s", (row_b,))
                        assert cur.fetchone()[0] == 1

    def test_v5_upsert_does_not_touch_other_tenant(self, pg_integration_conn) -> None:
        marker = _new_marker()
        with _marker_scope(pg_integration_conn, marker):
            _seed_v5_trace(pg_integration_conn, "demo", marker)
            _seed_v5_trace(pg_integration_conn, "nikadent", marker)
            with tenant_transaction(pg_integration_conn, "demo"):
                with pg_integration_conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO public.v5_turn_traces (
                          turn_id, ts, sid, client_id, request_id,
                          gate_traces, retrieval_candidates, errors, verifier_verdict
                        )
                        VALUES (%s, now(), 'sid-u', 'demo', %s, '[]'::jsonb, '[]'::jsonb, '[]'::jsonb, '{"ok":true}'::jsonb)
                        ON CONFLICT (client_id, turn_id) DO UPDATE SET verifier_verdict = EXCLUDED.verifier_verdict
                        """,
                        (marker, marker),
                    )
            with tenant_transaction(pg_integration_conn, "nikadent"):
                with pg_integration_conn.cursor() as cur:
                    cur.execute(
                        "SELECT verifier_verdict FROM public.v5_turn_traces WHERE turn_id=%s",
                        (marker,),
                    )
                    assert cur.fetchone()[0] is None

    def test_same_sid_isolated_between_tenants(self, pg_integration_conn) -> None:
        marker_demo = _new_marker()
        marker_nika = _new_marker()
        shared_sid = f"shared-{uuid.uuid4().hex[:6]}"
        with _marker_scope(pg_integration_conn, marker_demo):
            with _marker_scope(pg_integration_conn, marker_nika):
                _seed_bot_event(pg_integration_conn, "demo", marker_demo, sid=shared_sid)
                _seed_bot_event(pg_integration_conn, "nikadent", marker_nika, sid=shared_sid)
                with tenant_transaction(pg_integration_conn, "demo"):
                    with pg_integration_conn.cursor() as cur:
                        cur.execute(
                            "SELECT count(*) FROM public.bot_events WHERE sid=%s",
                            (shared_sid,),
                        )
                        assert cur.fetchone()[0] == 1

    def test_retention_demo_does_not_delete_nikadent(self, pg_integration_conn) -> None:
        from pg_retention import purge_session_observability

        marker_demo = _new_marker()
        marker_nika = _new_marker()
        sid = f"ret-{uuid.uuid4().hex[:6]}"
        with _marker_scope(pg_integration_conn, marker_demo):
            with _marker_scope(pg_integration_conn, marker_nika):
                _seed_bot_event(pg_integration_conn, "demo", marker_demo, sid=sid)
                _seed_bot_event(pg_integration_conn, "nikadent", marker_nika, sid=sid)
                purge_session_observability(_TEST_DSN, sid=sid, client_id="demo")
                with tenant_transaction(pg_integration_conn, "nikadent"):
                    with pg_integration_conn.cursor() as cur:
                        cur.execute(
                            "SELECT count(*) FROM public.bot_events WHERE request_id=%s",
                            (marker_nika,),
                        )
                        assert cur.fetchone()[0] == 1

    def test_force_rls_enabled_on_all_tables(self, pg_integration_conn) -> None:
        with pg_integration_conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.relname, c.relforcerowsecurity
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public'
                  AND c.relname IN ('bot_events', 'leads', 'v5_turn_traces')
                ORDER BY c.relname
                """
            )
            rows = cur.fetchall()
            assert len(rows) == 3
            assert all(bool(r[1]) for r in rows)

    def test_runtime_not_owner_of_all_tables(self, pg_integration_conn) -> None:
        with pg_integration_conn.cursor() as cur:
            cur.execute(
                """
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public'
                  AND tablename IN ('bot_events', 'leads', 'v5_turn_traces')
                  AND tableowner = current_user
                """
            )
            assert cur.fetchall() == []

    def test_runtime_nosuperuser_nobypassrls(self, pg_integration_conn) -> None:
        with pg_integration_conn.cursor() as cur:
            cur.execute(
                "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
            )
            row = cur.fetchone()
            assert row == (False, False)
