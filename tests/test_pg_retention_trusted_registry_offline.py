"""Retention must use full trusted tenant registry (not admin-only list)."""
from __future__ import annotations

import inspect

from core.client_config_loader import list_admin_client_ids, list_trusted_tenant_ids
import pg_retention


def test_list_trusted_tenant_ids_includes_demo() -> None:
    ids = list_trusted_tenant_ids()
    assert "demo" in ids


def test_trusted_registry_is_superset_of_admin_when_both_exist() -> None:
    trusted = set(list_trusted_tenant_ids())
    admin = set(list_admin_client_ids())
    assert admin.issubset(trusted)


def test_purge_expired_uses_trusted_registry_not_global_select() -> None:
    src = inspect.getsource(pg_retention.purge_expired_observability)
    assert "list_trusted_tenant_ids" in src
    assert "GROUP BY sid, client_id" not in src
    assert "list_admin_client_ids" not in src


def test_purge_session_uses_tenant_transaction() -> None:
    src = inspect.getsource(pg_retention.purge_session_observability)
    assert "tenant_transaction" in src
    assert "validate_trusted_pg_tenant" in src


def test_retention_registry_is_not_limited_to_admin_clients() -> None:
    trusted = set(list_trusted_tenant_ids())
    admin = set(list_admin_client_ids())
    assert admin.issubset(trusted)
