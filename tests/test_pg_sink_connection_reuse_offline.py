"""Offline orchestration: separate transactions and set_config per pg_sink item."""
from __future__ import annotations

from contextlib import contextmanager

import pytest

import pg_sink
from core.pg_tenant_context import APP_CURRENT_TENANT_GUC


class _RecordingConn:
    def __init__(self) -> None:
        self.tx_starts = 0
        self.set_config_calls: list[tuple] = []

    @contextmanager
    def transaction(self):
        self.tx_starts += 1
        yield

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False

    def execute(self, sql, params=None):
        if sql and "set_config" in sql:
            self.set_config_calls.append(tuple(params or ()))


def test_sequential_items_use_separate_transactions_and_set_config(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _RecordingConn()
    monkeypatch.setattr(pg_sink, "_insert_bot_event", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("fail")))

    with pytest.raises(RuntimeError):
        pg_sink._process_queue_item(conn, "bot_event", {"client_id": "demo", "event_type": "x"})

    monkeypatch.setattr(pg_sink, "_insert_bot_event", lambda *_a, **_k: None)
    pg_sink._process_queue_item(conn, "bot_event", {"client_id": "nikadent", "event_type": "y"})

    assert conn.tx_starts == 2
    assert len(conn.set_config_calls) == 2
    assert conn.set_config_calls[0][0] == APP_CURRENT_TENANT_GUC
    assert conn.set_config_calls[0][1] == "demo"
    assert conn.set_config_calls[1][1] == "nikadent"
