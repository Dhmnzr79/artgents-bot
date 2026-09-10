"""Tests for manual session purge."""
from __future__ import annotations

from pathlib import Path

import pytest

import config
from pg_retention import purge_session_observability
from session import mem_add_user, mem_get, session_client_scope


def test_purge_session_empty_args() -> None:
    stats = purge_session_observability("", sid="", client_id="demo")
    assert stats["found"] is False
    assert stats["bot_events_deleted"] == 0


def test_purge_session_traces_sql_includes_client_id(monkeypatch: pytest.MonkeyPatch) -> None:
    executed: list[tuple[str, tuple]] = []

    class _Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def execute(self, sql, params=None):
            executed.append((str(sql).strip(), tuple(params or ())))
            return self

        def fetchone(self):
            return (1,)

        @property
        def rowcount(self):
            return 1

    class _Conn:
        def cursor(self):
            return _Cursor()

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    monkeypatch.setattr("psycopg.connect", lambda *_a, **_k: _Conn())
    monkeypatch.setattr("session.mem_reset", lambda *_a, **_k: None)

    purge_session_observability(
        "postgresql://example",
        sid="sid-1",
        client_id="nikadent",
    )

    trace_deletes = [
        (sql, params)
        for sql, params in executed
        if "DELETE FROM v5_turn_traces" in sql
    ]
    assert len(trace_deletes) == 1
    sql, params = trace_deletes[0]
    assert "client_id=%s" in sql
    assert params == ("sid-1", "nikadent")


def test_purge_shared_sid_only_removes_target_tenant(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same sid across clinics: purge must scope PG deletes and SQLite reset by client_id."""
    shared_sid = "shared-sid"
    monkeypatch.setattr(config, "ALLOWED_CLIENTS", frozenset({"demo", "nikadent"}))

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    def _sqlite_path(client_id: str | None) -> str:
        pack = (client_id or "demo").strip() or "demo"
        return str((sessions_dir / f"{pack}.db").resolve())

    monkeypatch.setattr("session.sqlite_path_for_client", _sqlite_path)
    monkeypatch.setattr("core.client_runtime.sqlite_path_for_client", _sqlite_path)

    with session_client_scope("demo"):
        mem_add_user(shared_sid, "demo-turn")
    with session_client_scope("nikadent"):
        mem_add_user(shared_sid, "nikadent-turn")

    bot_events = [
        ("shared-sid", "demo", "llm_usage"),
        ("shared-sid", "demo", "turn_complete"),
        ("shared-sid", "nikadent", "turn_complete"),
    ]
    traces = [
        ("shared-sid", "demo", "demo-trace"),
        ("shared-sid", "nikadent", "nikadent-trace"),
    ]
    leads = [
        ("shared-sid", "demo"),
        ("shared-sid", "nikadent"),
    ]

    class _Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def execute(self, sql, params=None):
            self._last_sql = str(sql)
            self._last_params = tuple(params or ())
            return self

        def fetchone(self):
            sql = getattr(self, "_last_sql", "")
            params = getattr(self, "_last_params", ())
            if "FROM bot_events" in sql and "SELECT 1" in sql:
                sid, cid = params
                if any(row[0] == sid and row[1] == cid for row in bot_events):
                    return (1,)
            if "FROM leads" in sql and "SELECT 1" in sql:
                sid, cid = params
                if any(row[0] == sid and row[1] == cid for row in leads):
                    return (1,)
            return None

        @property
        def rowcount(self):
            sql = getattr(self, "_last_sql", "")
            params = getattr(self, "_last_params", ())
            if "DELETE FROM bot_events" in sql:
                sid, cid = params[0], params[1]
                before = len(bot_events)
                bot_events[:] = [r for r in bot_events if not (r[0] == sid and r[1] == cid and r[2] != "llm_usage")]
                return before - len(bot_events)
            if "DELETE FROM v5_turn_traces" in sql:
                sid, cid = params
                before = len(traces)
                traces[:] = [r for r in traces if not (r[0] == sid and r[1] == cid)]
                return before - len(traces)
            if "DELETE FROM leads" in sql:
                sid, cid = params
                before = len(leads)
                leads[:] = [r for r in leads if not (r[0] == sid and r[1] == cid)]
                return before - len(leads)
            return 0

    class _Conn:
        def cursor(self):
            return _Cursor()

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    monkeypatch.setattr("psycopg.connect", lambda *_a, **_k: _Conn())

    stats = purge_session_observability(
        "postgresql://example",
        sid=shared_sid,
        client_id="nikadent",
    )
    assert stats["found"] is True
    assert stats["sqlite_cleared"] is True
    assert ("shared-sid", "demo", "llm_usage") in bot_events
    assert ("shared-sid", "demo", "turn_complete") in bot_events
    assert ("shared-sid", "nikadent", "turn_complete") not in bot_events
    assert ("shared-sid", "demo", "demo-trace") in traces
    assert ("shared-sid", "nikadent", "nikadent-trace") not in traces
    assert ("shared-sid", "demo") in leads
    assert ("shared-sid", "nikadent") not in leads

    with session_client_scope("demo"):
        demo_hist = [str(item.get("content") or "") for item in mem_get(shared_sid).get("hist") or []]
    with session_client_scope("nikadent"):
        nika_hist = [str(item.get("content") or "") for item in mem_get(shared_sid).get("hist") or []]

    assert "demo-turn" in demo_hist
    assert "nikadent-turn" not in nika_hist
