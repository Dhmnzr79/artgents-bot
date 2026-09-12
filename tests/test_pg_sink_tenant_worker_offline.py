"""Offline tests for pg_sink tenant worker transactions and UPSERT targets."""
from __future__ import annotations

import inspect

import pytest

import pg_sink


def test_upsert_sql_uses_client_id_turn_id_conflict() -> None:
    src = inspect.getsource(pg_sink._insert_v5_turn_trace)
    assert "ON CONFLICT (client_id, turn_id)" in src
    src2 = inspect.getsource(pg_sink._upsert_v5_verifier_shadow)
    assert "ON CONFLICT (client_id, turn_id)" in src2


def test_worker_source_has_no_runtime_ensure_tables() -> None:
    src = inspect.getsource(pg_sink._worker)
    assert "_ensure_tables" not in src


def test_process_queue_item_uses_tenant_transaction(monkeypatch: pytest.MonkeyPatch) -> None:
    import pytest

    calls: list[str] = []

    class _Ctx:
        def __enter__(self):
            calls.append("txn")
            return "demo"

        def __exit__(self, *_a):
            return False

    monkeypatch.setattr(pg_sink, "tenant_transaction", lambda _c, _id: _Ctx())
    monkeypatch.setattr(pg_sink, "_insert_bot_event", lambda *_a, **_k: calls.append("insert"))

    conn = object()
    pg_sink._process_queue_item(conn, "bot_event", {"client_id": "demo", "event_type": "x"})
    assert calls == ["txn", "insert"]
