"""Admin /api/health reflects schema readiness."""
from __future__ import annotations

import importlib
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def admin_mod():
    return importlib.import_module("admin_dashboard.app")


def test_api_health_schema_unavailable_returns_503(admin_mod, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(admin_mod, "BOT_PG_DSN", "postgresql://u:p@localhost:5432/bot_events_test")
    monkeypatch.setattr(admin_mod, "psycopg", MagicMock())
    conn = MagicMock()
    admin_mod.psycopg.connect.return_value = conn
    monkeypatch.setattr(admin_mod, "check_pg_schema_ready", lambda _c: (False, "missing_table:public.bot_events"))

    client = admin_mod.app.test_client()
    resp = client.get("/api/health")
    assert resp.status_code == 503
    body = resp.get_json()
    assert body.get("postgres") == "db_schema_unavailable"
    conn.close.assert_called_once()
