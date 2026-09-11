"""Offline tests for pg_schema_readiness (negative catalog shapes)."""
from __future__ import annotations

from unittest.mock import MagicMock

from core.pg_schema_readiness import _normalize_policy_expr, check_pg_schema_ready

_TENANT_QUAL = (
    "(client_id = NULLIF(current_setting('app.current_tenant'::text, true), ''::text))"
)


class _CatalogCursor:
    def __init__(self, handler):
        self._handler = handler
        self._sql = ""
        self._params = None

    def execute(self, sql, params=None, **_k):
        self._sql = sql
        self._params = params

    def fetchone(self):
        return self._handler.fetchone(self._sql, self._params)

    def fetchall(self):
        return self._handler.fetchall(self._sql, self._params)

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


def _policy_rows():
    return [
        (table, "tenant_isolation", "PERMISSIVE", "ALL", "{public}", _TENANT_QUAL, _TENANT_QUAL)
        for table in ("bot_events", "leads", "v5_turn_traces")
    ]


class _HappyHandler:
    def fetchone(self, sql: str, params=None):
        if "indisunique" in sql:
            return (True, ["client_id", "turn_id"])
        if "information_schema.tables" in sql:
            return (1,)
        if "is_nullable" in sql:
            return ("NO",)
        if "pg_roles" in sql and "current_user" in sql and "pg_auth_members" not in sql:
            return (False, False, False, False, False, "bot_runtime")
        if "has_schema_privilege" in sql:
            if params and len(params) >= 2:
                schema = str(params[0])
                priv = str(params[1]).upper()
            elif params and len(params) == 1:
                schema = str(params[0])
                priv = "USAGE" if "'USAGE'" in sql else "CREATE"
            else:
                schema = "public" if "'public'" in sql else "bot_migration"
                priv = "USAGE" if "'USAGE'" in sql else "CREATE"
            if schema == "public" and priv == "USAGE":
                return (True,)
            if schema == "public" and priv == "CREATE":
                return (False,)
            if schema == "bot_migration" or "'bot_migration'" in sql:
                return (False,)
        if "has_table_privilege" in sql:
            if params and len(params) >= 2:
                priv = str(params[1]).upper()
            elif "'SELECT'" in sql:
                priv = "SELECT"
            elif "'INSERT'" in sql:
                priv = "INSERT"
            elif "'UPDATE'" in sql:
                priv = "UPDATE"
            elif "'DELETE'" in sql:
                priv = "DELETE"
            elif "'TRUNCATE'" in sql:
                priv = "TRUNCATE"
            elif "'REFERENCES'" in sql:
                priv = "REFERENCES"
            elif "'TRIGGER'" in sql:
                priv = "TRIGGER"
            else:
                priv = ""
            if params and "schema_migrations" in str(params[0]):
                return (False,)
            if priv in {"TRUNCATE", "REFERENCES", "TRIGGER"}:
                return (False,)
            if priv:
                return (True,)
        if "has_sequence_privilege" in sql:
            if params and len(params) >= 2 and str(params[1]).upper() == "UPDATE":
                return (False,)
            return (True,)
        if "contype = 'p'" in sql:
            return (["client_id", "turn_id"],)
        return None

    def fetchall(self, sql: str, params=None):
        if "v5_turn_traces" in sql and "column_name" in sql:
            return [
                ("turn_id",),
                ("ts",),
                ("client_id",),
                ("gate_traces",),
                ("retrieval_candidates",),
                ("errors",),
                ("safety_net_used",),
                ("resolver_bypassed_env",),
            ]
        if "pg_constraint" in sql and "contype = 'c'" in sql:
            return [
                ("bot_events_client_id_format", True),
                ("leads_client_id_format", True),
                ("v5_turn_traces_client_id_format", True),
                ("v5_turn_traces_turn_id_nonempty", True),
            ]
        if "pg_tables" in sql and "tableowner" in sql:
            return [
                ("bot_events", "bot_migrator"),
                ("leads", "bot_migrator"),
                ("v5_turn_traces", "bot_migrator"),
            ]
        if "relrowsecurity" in sql:
            return [
                ("bot_events", True, True),
                ("leads", True, True),
                ("v5_turn_traces", True, True),
            ]
        if "pg_policies" in sql:
            return _policy_rows()
        if "pg_auth_members" in sql:
            return []
        return []


def test_ready_happy_path_minimal_catalog() -> None:
    conn = MagicMock()
    conn.cursor.return_value = _CatalogCursor(_HappyHandler())
    ok, reason = check_pg_schema_ready(conn)
    assert ok is True
    assert reason == "ok"


def test_normalize_policy_expr_accepts_pg_text_casts() -> None:
    raw = "(client_id = NULLIF(current_setting('app.current_tenant'::text, true), ''::text))"
    assert _normalize_policy_expr(raw) == (
        "client_id = nullif(current_setting('app.current_tenant', true), '')"
    )


def test_fails_when_index_not_unique() -> None:
    class _H(_HappyHandler):
        def fetchone(self, sql: str, params=None):
            if "indisunique" in sql:
                return (False, ["client_id", "turn_id"])
            return super().fetchone(sql, params)

    conn = MagicMock()
    conn.cursor.return_value = _CatalogCursor(_H())
    ok, reason = check_pg_schema_ready(conn)
    assert ok is False
    assert reason.startswith("index_not_unique:")


def test_fails_when_runtime_superuser() -> None:
    class _H(_HappyHandler):
        def fetchone(self, sql: str, params=None):
            if "pg_roles" in sql and "pg_auth_members" not in sql:
                return (True, False, False, False, False, "bot_runtime")
            return super().fetchone(sql, params)

    conn = MagicMock()
    conn.cursor.return_value = _CatalogCursor(_H())
    ok, reason = check_pg_schema_ready(conn)
    assert ok is False
    assert reason == "runtime_role_superuser"


def test_fails_when_policy_using_true() -> None:
    class _H(_HappyHandler):
        def fetchall(self, sql: str, params=None):
            if "pg_policies" in sql:
                return [
                    ("bot_events", "tenant_isolation", "PERMISSIVE", "ALL", "{public}", "true", _TENANT_QUAL),
                    ("leads", "tenant_isolation", "PERMISSIVE", "ALL", "{public}", _TENANT_QUAL, _TENANT_QUAL),
                    ("v5_turn_traces", "tenant_isolation", "PERMISSIVE", "ALL", "{public}", _TENANT_QUAL, _TENANT_QUAL),
                ]
            return super().fetchall(sql, params)

    conn = MagicMock()
    conn.cursor.return_value = _CatalogCursor(_H())
    ok, reason = check_pg_schema_ready(conn)
    assert ok is False
    assert reason == "policy_using_not_tenant_expr:public.bot_events"


def test_fails_when_policy_with_check_true() -> None:
    class _H(_HappyHandler):
        def fetchall(self, sql: str, params=None):
            if "pg_policies" in sql:
                return [
                    ("bot_events", "tenant_isolation", "PERMISSIVE", "ALL", "{public}", _TENANT_QUAL, "true"),
                    ("leads", "tenant_isolation", "PERMISSIVE", "ALL", "{public}", _TENANT_QUAL, _TENANT_QUAL),
                    ("v5_turn_traces", "tenant_isolation", "PERMISSIVE", "ALL", "{public}", _TENANT_QUAL, _TENANT_QUAL),
                ]
            return super().fetchall(sql, params)

    conn = MagicMock()
    conn.cursor.return_value = _CatalogCursor(_H())
    ok, reason = check_pg_schema_ready(conn)
    assert ok is False
    assert reason == "policy_with_check_not_tenant_expr:public.bot_events"


def test_fails_when_extra_policy_on_table() -> None:
    class _H(_HappyHandler):
        def fetchall(self, sql: str, params=None):
            if "pg_policies" in sql:
                rows = _policy_rows()
                rows.append(
                    (
                        "bot_events",
                        "extra_open",
                        "PERMISSIVE",
                        "ALL",
                        "{public}",
                        _TENANT_QUAL,
                        _TENANT_QUAL,
                    )
                )
                return rows
            return super().fetchall(sql, params)

    conn = MagicMock()
    conn.cursor.return_value = _CatalogCursor(_H())
    ok, reason = check_pg_schema_ready(conn)
    assert ok is False
    assert reason.startswith("policy_count_invalid:public.bot_events:")


def test_fails_when_policy_wrong_guc() -> None:
    class _H(_HappyHandler):
        def fetchall(self, sql: str, params=None):
            if "pg_policies" in sql:
                bad = "(client_id = NULLIF(current_setting('app.wrong_tenant', true), ''))"
                return [
                    (table, "tenant_isolation", "PERMISSIVE", "ALL", "{public}", bad, bad)
                    for table in ("bot_events", "leads", "v5_turn_traces")
                ]
            return super().fetchall(sql, params)

    conn = MagicMock()
    conn.cursor.return_value = _CatalogCursor(_H())
    ok, reason = check_pg_schema_ready(conn)
    assert ok is False
    assert reason == "policy_using_mismatch:public.bot_events"


def test_fails_when_policy_wrong_role() -> None:
    class _H(_HappyHandler):
        def fetchall(self, sql: str, params=None):
            if "pg_policies" in sql:
                return [
                    ("bot_events", "tenant_isolation", "PERMISSIVE", "ALL", "{bot_runtime}", _TENANT_QUAL, _TENANT_QUAL),
                    ("leads", "tenant_isolation", "PERMISSIVE", "ALL", "{public}", _TENANT_QUAL, _TENANT_QUAL),
                    ("v5_turn_traces", "tenant_isolation", "PERMISSIVE", "ALL", "{public}", _TENANT_QUAL, _TENANT_QUAL),
                ]
            return super().fetchall(sql, params)

    conn = MagicMock()
    conn.cursor.return_value = _CatalogCursor(_H())
    ok, reason = check_pg_schema_ready(conn)
    assert ok is False
    assert reason == "policy_roles_invalid:public.bot_events"


def test_fails_when_policy_wrong_cmd() -> None:
    class _H(_HappyHandler):
        def fetchall(self, sql: str, params=None):
            if "pg_policies" in sql:
                return [
                    ("bot_events", "tenant_isolation", "PERMISSIVE", "SELECT", "{public}", _TENANT_QUAL, _TENANT_QUAL),
                    ("leads", "tenant_isolation", "PERMISSIVE", "ALL", "{public}", _TENANT_QUAL, _TENANT_QUAL),
                    ("v5_turn_traces", "tenant_isolation", "PERMISSIVE", "ALL", "{public}", _TENANT_QUAL, _TENANT_QUAL),
                ]
            return super().fetchall(sql, params)

    conn = MagicMock()
    conn.cursor.return_value = _CatalogCursor(_H())
    ok, reason = check_pg_schema_ready(conn)
    assert ok is False
    assert reason == "policy_cmd_invalid:public.bot_events:SELECT"


def test_fails_when_runtime_has_extra_role_membership() -> None:
    class _H(_HappyHandler):
        def fetchall(self, sql: str, params=None):
            if "pg_auth_members" in sql:
                return [("pg_read_all_data",)]
            return super().fetchall(sql, params)

    conn = MagicMock()
    conn.cursor.return_value = _CatalogCursor(_H())
    ok, reason = check_pg_schema_ready(conn)
    assert ok is False
    assert reason == "runtime_role_extra_membership"


def test_fails_when_runtime_has_schema_create() -> None:
    class _H(_HappyHandler):
        def fetchone(self, sql: str, params=None):
            if "has_schema_privilege" in sql and "'CREATE'" in sql:
                return (True,)
            return super().fetchone(sql, params)

    conn = MagicMock()
    conn.cursor.return_value = _CatalogCursor(_H())
    ok, reason = check_pg_schema_ready(conn)
    assert ok is False
    assert reason == "runtime_schema_create_granted"


def test_fails_when_runtime_missing_table_delete() -> None:
    class _H(_HappyHandler):
        def fetchone(self, sql: str, params=None):
            if "has_table_privilege" in sql and params and params[1] == "DELETE":
                return (False,)
            return super().fetchone(sql, params)

    conn = MagicMock()
    conn.cursor.return_value = _CatalogCursor(_H())
    ok, reason = check_pg_schema_ready(conn)
    assert ok is False
    assert "runtime_table_priv_missing" in reason


def test_fails_when_runtime_has_truncate() -> None:
    class _H(_HappyHandler):
        def fetchone(self, sql: str, params=None):
            if "has_table_privilege" in sql and params and params[1] == "TRUNCATE":
                return (True,)
            return super().fetchone(sql, params)

    conn = MagicMock()
    conn.cursor.return_value = _CatalogCursor(_H())
    ok, reason = check_pg_schema_ready(conn)
    assert ok is False
    assert "runtime_table_priv_forbidden" in reason


def test_fails_when_runtime_can_read_ledger() -> None:
    class _H(_HappyHandler):
        def fetchone(self, sql: str, params=None):
            target = str(params[0]) if params else sql
            if "has_table_privilege" in sql and "schema_migrations" in target:
                return (True,)
            return super().fetchone(sql, params)

    conn = MagicMock()
    conn.cursor.return_value = _CatalogCursor(_H())
    ok, reason = check_pg_schema_ready(conn)
    assert ok is False
    assert reason == "runtime_ledger_table_forbidden:select"


def test_fails_when_policy_restrictive() -> None:
    class _H(_HappyHandler):
        def fetchall(self, sql: str, params=None):
            if "pg_policies" in sql:
                return [
                    (
                        "bot_events",
                        "tenant_isolation",
                        "RESTRICTIVE",
                        "ALL",
                        "{public}",
                        _TENANT_QUAL,
                        _TENANT_QUAL,
                    ),
                    *_policy_rows()[1:],
                ]
            return super().fetchall(sql, params)

    conn = MagicMock()
    conn.cursor.return_value = _CatalogCursor(_H())
    ok, reason = check_pg_schema_ready(conn)
    assert ok is False
    assert reason == "policy_permissive_invalid:public.bot_events:RESTRICTIVE"


def test_fails_when_runtime_ledger_insert_granted() -> None:
    class _H(_HappyHandler):
        def fetchone(self, sql: str, params=None):
            if "has_table_privilege" in sql and params and params[1] == "INSERT":
                if params and "schema_migrations" in str(params[0]):
                    return (True,)
            return super().fetchone(sql, params)

    conn = MagicMock()
    conn.cursor.return_value = _CatalogCursor(_H())
    ok, reason = check_pg_schema_ready(conn)
    assert ok is False
    assert reason == "runtime_ledger_table_forbidden:insert"


def test_fails_when_runtime_ledger_schema_create_granted() -> None:
    class _H(_HappyHandler):
        def fetchone(self, sql: str, params=None):
            if "has_schema_privilege" in sql and params and params[0] == "bot_migration":
                if str(params[1]).upper() == "CREATE":
                    return (True,)
            return super().fetchone(sql, params)

    conn = MagicMock()
    conn.cursor.return_value = _CatalogCursor(_H())
    ok, reason = check_pg_schema_ready(conn)
    assert ok is False
    assert reason == "runtime_ledger_schema_forbidden:create"


def test_fails_when_runtime_sequence_update_granted() -> None:
    class _H(_HappyHandler):
        def fetchone(self, sql: str, params=None):
            if "has_sequence_privilege" in sql and params and params[1] == "UPDATE":
                return (True,)
            return super().fetchone(sql, params)

    conn = MagicMock()
    conn.cursor.return_value = _CatalogCursor(_H())
    ok, reason = check_pg_schema_ready(conn)
    assert ok is False
    assert reason == "runtime_sequence_priv_forbidden:public.bot_events_id_seq:update"
