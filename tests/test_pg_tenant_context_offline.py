"""Offline tests for PostgreSQL tenant transaction helper."""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from core.pg_tenant_context import (
    APP_CURRENT_TENANT_GUC,
    InvalidPgTenantError,
    tenant_transaction,
    validate_trusted_pg_tenant,
)


@pytest.mark.parametrize(
    "client_id",
    [None, "", "  ", " demo", "default", "_template", "../x", "unknown-clinic-xyz"],
)
def test_validate_trusted_pg_tenant_rejects_invalid(client_id) -> None:
    with pytest.raises(InvalidPgTenantError):
        validate_trusted_pg_tenant(client_id)


def test_validate_trusted_pg_tenant_accepts_demo() -> None:
    assert validate_trusted_pg_tenant("demo") == "demo"


def test_tenant_transaction_sets_local_guc_before_yield() -> None:
    executed: list[tuple] = []
    tx_entered = False

    class _Cur:
        def execute(self, sql, params=None):
            executed.append((sql, params))

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    @contextmanager
    def _transaction():
        nonlocal tx_entered
        tx_entered = True
        yield

    conn = MagicMock()
    conn.transaction = _transaction
    conn.cursor.return_value = _Cur()

    with tenant_transaction(conn, "demo") as tenant:
        assert tenant == "demo"
        assert tx_entered
        assert executed
        sql, params = executed[0]
        assert "set_config" in sql
        assert params == (APP_CURRENT_TENANT_GUC, "demo")
        assert "true" in sql.lower()


def test_tenant_transaction_rolls_back_on_error() -> None:
    exit_exc_types: list[type[BaseException]] = []

    @contextmanager
    def _transaction():
        try:
            yield
        except Exception as exc:
            exit_exc_types.append(type(exc))
            raise

    class _Cur:
        def execute(self, *_a, **_k):
            return None

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    conn = MagicMock()
    conn.transaction = _transaction
    conn.cursor.return_value = _Cur()

    with pytest.raises(RuntimeError):
        with tenant_transaction(conn, "demo"):
            raise RuntimeError("boom")

    assert exit_exc_types == [RuntimeError]
