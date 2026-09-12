"""Retention must process trusted tenants even when admin.enabled is false."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone

import pytest

import pg_retention


def test_purge_expired_calls_tenant_transaction_for_non_admin_trusted_tenant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenants_touched: list[str] = []

    @contextmanager
    def _recording_tt(_conn, client_id):
        tenants_touched.append(client_id)
        yield client_id

    monkeypatch.setattr(pg_retention, "list_trusted_tenant_ids", lambda: ["nikadent"])
    monkeypatch.setattr("core.client_config_loader.admin_enabled", lambda _c: False)
    monkeypatch.setattr(pg_retention, "tenant_transaction", _recording_tt)

    class _Cur:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def execute(self, *_a, **_k):
            return self

        def fetchall(self):
            return []

    class _Conn:
        @contextmanager
        def transaction(self):
            yield

        def cursor(self):
            return _Cur()

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    monkeypatch.setattr("psycopg.connect", lambda *_a, **_k: _Conn())

    stats = pg_retention.purge_expired_observability(
        "postgresql://127.0.0.1:5432/bot_events_test",
        retention_hours=1,
    )
    assert stats["sids_purged"] == 0
    assert tenants_touched == ["nikadent"]
