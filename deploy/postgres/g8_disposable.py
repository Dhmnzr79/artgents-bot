"""G8 disposable PostgreSQL bootstrap, DSN builders, and readiness helpers."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from deploy.postgres.g8_disposable_constants import (
    G8_BOOTSTRAP_PASSWORD,
    G8_BOOTSTRAP_USER,
    G8_MIGRATOR_PASSWORD,
    G8_MIGRATOR_ROLE,
    G8_PG_HOST,
    G8_PG_PORT,
    G8_PRIMARY_DATABASE,
    G8_RESTORE_DATABASE,
    G8_RUNTIME_PASSWORD,
    G8_RUNTIME_ROLE,
    PG_ISREADY_INTERVAL_SEC,
    PG_ISREADY_TIMEOUT_SEC,
    POSTGRES_IMAGE_PIN,
)
from deploy.postgres.g8_docker_pg import pg_isready_host_fallback, pg_isready_in_container

_GRANTS_SQL = Path(__file__).resolve().parent / "g8_disposable_grants_post_migrate.sql"


def build_dsn(
    *,
    user: str,
    password: str,
    database: str,
    host: str = G8_PG_HOST,
    port: int = G8_PG_PORT,
) -> str:
    return (
        f"postgresql://{quote_plus(user)}:{quote_plus(password)}"
        f"@{host}:{port}/{quote_plus(database)}"
    )


def bootstrap_superuser_dsn(database: str = G8_PRIMARY_DATABASE) -> str:
    return build_dsn(
        user=G8_BOOTSTRAP_USER,
        password=G8_BOOTSTRAP_PASSWORD,
        database=database,
    )


def migrator_dsn(database: str = G8_PRIMARY_DATABASE) -> str:
    return build_dsn(
        user=G8_MIGRATOR_ROLE,
        password=G8_MIGRATOR_PASSWORD,
        database=database,
    )


def runtime_dsn(database: str = G8_PRIMARY_DATABASE) -> str:
    return build_dsn(
        user=G8_RUNTIME_ROLE,
        password=G8_RUNTIME_PASSWORD,
        database=database,
    )


def wait_for_postgres_ready(
    *,
    user: str = G8_BOOTSTRAP_USER,
    database: str = G8_PRIMARY_DATABASE,
    host: str = G8_PG_HOST,
    port: int = G8_PG_PORT,
    timeout_sec: int = PG_ISREADY_TIMEOUT_SEC,
    interval_sec: float = PG_ISREADY_INTERVAL_SEC,
) -> None:
    deadline = time.monotonic() + timeout_sec
    use_docker = bool((os.getenv("G8_POSTGRES_CONTAINER_ID") or "").strip())
    while time.monotonic() < deadline:
        if use_docker:
            ready = pg_isready_in_container(user=user, database=database)
        else:
            ready = pg_isready_host_fallback(
                user=user,
                database=database,
                host=host,
                port=port,
                env_password=G8_BOOTSTRAP_PASSWORD,
            )
        if ready:
            return
        time.sleep(interval_sec)
    raise RuntimeError("postgres_not_ready")


def _ensure_login_role(cur: Any, role: str, password: str) -> None:
    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
    if cur.fetchone():
        return
    cur.execute(
        f"""
        CREATE ROLE {role} LOGIN PASSWORD %s
          NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOREPLICATION
        """,
        (password,),
    )


def _grant_database_bootstrap_privileges(cur: Any, database: str) -> None:
    cur.execute(f"REVOKE CREATE ON DATABASE {database} FROM PUBLIC, {G8_RUNTIME_ROLE}")
    cur.execute(f"GRANT CREATE ON DATABASE {database} TO {G8_MIGRATOR_ROLE}")
    cur.execute(
        f"GRANT CONNECT ON DATABASE {database} TO {G8_MIGRATOR_ROLE}, {G8_RUNTIME_ROLE}"
    )


def _exec_bootstrap_roles(conn: Any) -> None:
    with conn.cursor() as cur:
        _ensure_login_role(cur, G8_MIGRATOR_ROLE, G8_MIGRATOR_PASSWORD)
        _ensure_login_role(cur, G8_RUNTIME_ROLE, G8_RUNTIME_PASSWORD)
        cur.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
        cur.execute(f"GRANT USAGE, CREATE ON SCHEMA public TO {G8_MIGRATOR_ROLE}")
        cur.execute(f"GRANT USAGE ON SCHEMA public TO {G8_RUNTIME_ROLE}")
        cur.execute(f"REVOKE CREATE ON SCHEMA public FROM {G8_RUNTIME_ROLE}")
        _grant_database_bootstrap_privileges(cur, G8_PRIMARY_DATABASE)


def bootstrap_disposable_primary(conn: Any) -> None:
    _exec_bootstrap_roles(conn)


def prepare_restore_database_schema(conn: Any) -> None:
    """Pre-restore grants on empty g8_qual_restored (connected to that database)."""
    with conn.cursor() as cur:
        cur.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
        cur.execute(f"GRANT USAGE, CREATE ON SCHEMA public TO {G8_MIGRATOR_ROLE}")
        cur.execute(f"GRANT USAGE ON SCHEMA public TO {G8_RUNTIME_ROLE}")
        cur.execute(f"REVOKE CREATE ON SCHEMA public FROM {G8_RUNTIME_ROLE}")


def apply_post_migrate_grants(conn: Any) -> None:
    sql = _GRANTS_SQL.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)


def create_restore_database(conn: Any) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (G8_RESTORE_DATABASE,),
        )
        if cur.fetchone():
            raise RuntimeError("restore_database_already_exists")
        cur.execute(f'CREATE DATABASE "{G8_RESTORE_DATABASE}"')
        _grant_database_bootstrap_privileges(cur, G8_RESTORE_DATABASE)


def drop_restore_database_if_exists(conn: Any) -> None:
    old_autocommit = conn.autocommit
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = %s AND pid <> pg_backend_pid()
                """,
                (G8_RESTORE_DATABASE,),
            )
            cur.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (G8_RESTORE_DATABASE,),
            )
            if cur.fetchone():
                cur.execute(f'DROP DATABASE "{G8_RESTORE_DATABASE}"')
    finally:
        conn.autocommit = old_autocommit


def assert_runtime_role_catalog(conn: Any) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, rolreplication
            FROM pg_roles WHERE rolname = current_user
            """
        )
        row = cur.fetchone()
        if row != (False, False, False, False, False):
            raise RuntimeError("runtime_role_flags_invalid")
        cur.execute(
            """
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public'
              AND tablename IN ('bot_events', 'leads', 'v5_turn_traces')
              AND tableowner = current_user
            """
        )
        if cur.fetchall():
            raise RuntimeError("runtime_must_not_own_tenant_tables")
        cur.execute(
            "SELECT has_schema_privilege(current_user, 'public', 'CREATE')"
        )
        if cur.fetchone()[0]:
            raise RuntimeError("runtime_public_create_forbidden")
        cur.execute(
            "SELECT has_schema_privilege(current_user, 'bot_migration', 'USAGE')"
        )
        if cur.fetchone()[0]:
            raise RuntimeError("runtime_bot_migration_usage_forbidden")
        cur.execute(
            "SELECT has_table_privilege(current_user, 'bot_migration.schema_migrations', 'SELECT')"
        )
        if cur.fetchone()[0]:
            raise RuntimeError("runtime_ledger_select_forbidden")
        cur.execute(
            "SELECT has_database_privilege(current_user, current_database(), 'CREATE')"
        )
        if cur.fetchone()[0]:
            raise RuntimeError("runtime_database_create_forbidden")


def assert_migrator_role_catalog(conn: Any) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, rolreplication
            FROM pg_roles WHERE rolname = current_user
            """
        )
        row = cur.fetchone()
        if row != (False, False, False, False, False):
            raise RuntimeError("migrator_role_flags_invalid")
        cur.execute(
            """
            SELECT count(*) FROM pg_tables
            WHERE schemaname = 'public'
              AND tablename IN ('bot_events', 'leads', 'v5_turn_traces')
              AND tableowner = current_user
            """
        )
        if int(cur.fetchone()[0]) != 3:
            raise RuntimeError("migrator_must_own_tenant_tables")
        cur.execute(
            "SELECT has_table_privilege(current_user, 'bot_migration.schema_migrations', 'INSERT')"
        )
        if not cur.fetchone()[0]:
            raise RuntimeError("migrator_ledger_insert_required")
        cur.execute(
            "SELECT has_database_privilege(current_user, current_database(), 'CREATE')"
        )
        if not cur.fetchone()[0]:
            raise RuntimeError("migrator_database_create_required")


def pinned_image_for_ci_service() -> str:
    return POSTGRES_IMAGE_PIN
