"""Static checks for PostgreSQL tenant migration SQL (offline)."""
from __future__ import annotations

from pathlib import Path

import pytest

import admin_dashboard.app as admin_app
import pg_sink

_ROOT = Path(__file__).resolve().parents[1]
_MIG = _ROOT / "migrations" / "postgresql"

_CLIENT_CHECK_SNIPPET = "client_id = btrim(client_id)"
_TURN_ID_CHECK = "v5_turn_traces_turn_id_nonempty"


def _read(name: str) -> str:
    return (_MIG / name).read_text(encoding="utf-8")


def test_002_brownfield_adds_format_checks_for_all_tables() -> None:
    sql = _read("002_tenant_schema_prepare.sql")
    assert "_ensure_t4b_check_constraint" in sql
    for table in ("bot_events", "leads", "v5_turn_traces"):
        assert f"'public', '{table}'" in sql
    assert sql.count(_CLIENT_CHECK_SNIPPET) >= 3


def test_002_rejects_name_only_constraint_helper() -> None:
    sql = _read("002_tenant_schema_prepare.sql")
    assert "_add_check_if_missing" not in sql
    assert "DROP CONSTRAINT" in sql


def test_002_greenfield_and_brownfield_client_id_checks_aligned() -> None:
    sql = _read("002_tenant_schema_prepare.sql")
    assert "CONSTRAINT bot_events_client_id_format CHECK" in sql
    assert "CONSTRAINT leads_client_id_format CHECK" in sql
    assert "CONSTRAINT v5_turn_traces_client_id_format CHECK" in sql
    assert "bot_events_client_id_format" in sql
    assert "leads_client_id_format" in sql
    assert "v5_turn_traces_client_id_format" in sql


def test_002_turn_id_nonblank_greenfield_and_brownfield() -> None:
    sql = _read("002_tenant_schema_prepare.sql")
    assert _TURN_ID_CHECK in sql
    assert "btrim(turn_id) = ''" in sql


def test_migrations_use_public_schema_qualified_tables() -> None:
    sql2 = _read("002_tenant_schema_prepare.sql")
    sql3 = _read("003_tenant_rls_enable.sql")
    sql4 = _read("004_tenant_trace_pk_finalize.sql")
    for sql in (sql2, sql3):
        assert "public.bot_events" in sql
        assert "public.leads" in sql
        assert "public.v5_turn_traces" in sql
    assert "public.v5_turn_traces" in sql4


def test_003_enables_force_rls_and_policies_have_using_and_check() -> None:
    sql = _read("003_tenant_rls_enable.sql")
    assert "FORCE ROW LEVEL SECURITY" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert sql.count("USING (") >= 3
    assert sql.count("WITH CHECK (") >= 3


def test_004_requires_composite_unique_before_pk_swap() -> None:
    sql = _read("004_tenant_trace_pk_finalize.sql")
    assert "v5_turn_traces_client_turn_uidx" in sql
    assert "PRIMARY KEY (client_id, turn_id)" in sql


def test_migrations_do_not_demo_backfill() -> None:
    for path in _MIG.glob("*.sql"):
        low = path.read_text(encoding="utf-8").lower()
        assert "set client_id = 'demo'" not in low
        assert "client_id='demo'" not in low


def test_runtime_ddl_removed_from_worker_and_admin() -> None:
    import inspect

    assert "_ensure_tables" not in inspect.getsource(pg_sink._worker)
    assert "ensure_pg_schema" not in inspect.getsource(admin_app._require_db)
