"""Offline tests for pg_schema_readiness (negative catalog shapes)."""
from __future__ import annotations

from unittest.mock import MagicMock

from core.pg_schema_readiness import check_pg_schema_ready


class _CatalogCursor:
    def __init__(self, handler):
        self._handler = handler
        self._sql = ""

    def execute(self, sql, *_a, **_k):
        self._sql = sql

    def fetchone(self):
        return self._handler.fetchone(self._sql)

    def fetchall(self):
        return self._handler.fetchall(self._sql)

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


class _HappyHandler:
    def fetchone(self, sql: str):
        if "indisunique" in sql:
            return (True, ["client_id", "turn_id"])
        if "information_schema.tables" in sql:
            return (1,)
        if "is_nullable" in sql:
            return ("NO",)
        return None

    def fetchall(self, sql: str):
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
        if "pg_constraint" in sql:
            return [
                ("bot_events_client_id_format", True),
                ("leads_client_id_format", True),
                ("v5_turn_traces_client_id_format", True),
                ("v5_turn_traces_turn_id_nonempty", True),
            ]
        return []


def test_ready_happy_path_minimal_catalog() -> None:
    conn = MagicMock()
    conn.cursor.return_value = _CatalogCursor(_HappyHandler())
    ok, reason = check_pg_schema_ready(conn)
    assert ok is True
    assert reason == "ok"


def test_fails_when_index_not_unique() -> None:
    class _H(_HappyHandler):
        def fetchone(self, sql: str):
            if "indisunique" in sql:
                return (False, ["client_id", "turn_id"])
            return super().fetchone(sql)

    conn = MagicMock()
    conn.cursor.return_value = _CatalogCursor(_H())
    ok, reason = check_pg_schema_ready(conn)
    assert ok is False
    assert reason.startswith("index_not_unique:")


def test_fails_when_index_wrong_column_order() -> None:
    class _H(_HappyHandler):
        def fetchone(self, sql: str):
            if "indisunique" in sql:
                return (True, ["turn_id", "client_id"])
            return super().fetchone(sql)

    conn = MagicMock()
    conn.cursor.return_value = _CatalogCursor(_H())
    ok, reason = check_pg_schema_ready(conn)
    assert ok is False
    assert reason.startswith("index_wrong_columns:")


def test_fails_when_client_id_nullable() -> None:
    class _H(_HappyHandler):
        def fetchone(self, sql: str):
            if "is_nullable" in sql:
                return ("YES",)
            return super().fetchone(sql)

    conn = MagicMock()
    conn.cursor.return_value = _CatalogCursor(_H())
    ok, reason = check_pg_schema_ready(conn)
    assert ok is False
    assert "nullable_client_id" in reason


def test_fails_when_constraint_unvalidated() -> None:
    class _H(_HappyHandler):
        def fetchall(self, sql: str):
            if "pg_constraint" in sql:
                return [("bot_events_client_id_format", False)]
            return super().fetchall(sql)

    conn = MagicMock()
    conn.cursor.return_value = _CatalogCursor(_H())
    ok, reason = check_pg_schema_ready(conn)
    assert ok is False
    assert reason.startswith("unvalidated_constraint:")
