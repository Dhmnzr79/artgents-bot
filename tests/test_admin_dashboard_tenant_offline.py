"""Admin dashboard tenant resolution fail-closed for explicit unknown client."""
from __future__ import annotations

import importlib

import pytest


@pytest.fixture
def admin_app():
    mod = importlib.import_module("admin_dashboard.app")
    return mod.app, mod


def test_explicit_unknown_client_id_fail_closed(admin_app) -> None:
    app, mod = admin_app
    client = app.test_client()
    resp = client.get("/api/overview?client_id=not-a-real-clinic-pack")
    assert resp.status_code == 400
    assert resp.get_json().get("error") == "unknown_client"


def test_require_db_has_no_schema_bootstrap(admin_app) -> None:
    import inspect

    mod = admin_app[1]
    src = inspect.getsource(mod._require_db)
    assert "ensure_pg_schema" not in src
