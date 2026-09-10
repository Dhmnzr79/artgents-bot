"""Transaction-local PostgreSQL tenant context for RLS-backed operations."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

APP_CURRENT_TENANT_GUC = "app.current_tenant"


class InvalidPgTenantError(ValueError):
    """Fail-closed: tenant is not trusted for PostgreSQL operations."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def validate_trusted_pg_tenant(client_id: str | None) -> str:
    """Canonical trusted tenant id (pack exists, strict segment rules, no fallback)."""
    from core.client_config_loader import (
        ExplicitPackClientIdError,
        require_existing_explicit_pack_client_id,
    )

    try:
        return require_existing_explicit_pack_client_id(client_id)
    except ExplicitPackClientIdError as exc:
        raise InvalidPgTenantError(exc.code) from exc


@contextmanager
def tenant_transaction(conn: Any, client_id: str | None) -> Iterator[str]:
    """
    Validate tenant, open a DB transaction, set transaction-local GUC, yield tenant.

    On any exception the transaction rolls back and the local GUC is discarded.
    """
    tenant = validate_trusted_pg_tenant(client_id)
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config(%s, %s, true)",
                (APP_CURRENT_TENANT_GUC, tenant),
            )
        yield tenant
