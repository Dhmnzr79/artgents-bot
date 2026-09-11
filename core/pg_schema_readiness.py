"""Read-only PostgreSQL schema readiness checks (no DDL)."""
from __future__ import annotations

import re
from typing import Any

_REQUIRED_TABLES: tuple[str, ...] = ("bot_events", "leads", "v5_turn_traces")

_TENANT_TABLES_CLIENT_ID: tuple[str, ...] = _REQUIRED_TABLES

_V5_REQUIRED_COLUMNS: frozenset[str] = frozenset(
    {
        "turn_id",
        "ts",
        "client_id",
        "gate_traces",
        "retrieval_candidates",
        "errors",
        "safety_net_used",
        "resolver_bypassed_env",
    }
)

_T4B_CHECK_CONSTRAINTS: frozenset[str] = frozenset(
    {
        "bot_events_client_id_format",
        "leads_client_id_format",
        "v5_turn_traces_client_id_format",
        "v5_turn_traces_turn_id_nonempty",
    }
)

_COMPOSITE_UNIQUE_INDEX = "v5_turn_traces_client_turn_uidx"
_EXPECTED_INDEX_COLUMNS = ("client_id", "turn_id")
_EXPECTED_PK_COLUMNS = ("client_id", "turn_id")
_TENANT_POLICY_NAME = "tenant_isolation"
_EXPECTED_TENANT_EXPR = (
    "client_id = nullif(current_setting('app.current_tenant', true), '')"
)
_RUNTIME_DML_PRIVS = ("SELECT", "INSERT", "UPDATE", "DELETE")
_RUNTIME_FORBIDDEN_TABLE_PRIVS = ("TRUNCATE", "REFERENCES", "TRIGGER")
_RUNTIME_SEQUENCES = ("bot_events_id_seq", "leads_id_seq")
_LEDGER_SCHEMA = "bot_migration"
_LEDGER_TABLE = "bot_migration.schema_migrations"
_LEDGER_FORBIDDEN_SCHEMA_PRIVS = ("USAGE", "CREATE")
_LEDGER_FORBIDDEN_TABLE_PRIVS = (
    "SELECT",
    "INSERT",
    "UPDATE",
    "DELETE",
    "TRUNCATE",
    "REFERENCES",
    "TRIGGER",
)


def _strip_redundant_outer_parens(expr: str) -> str:
    inner = expr.strip()
    while len(inner) >= 2 and inner[0] == "(" and inner[-1] == ")":
        candidate = inner[1:-1].strip()
        if candidate.count("(") != candidate.count(")"):
            break
        inner = candidate
    return inner


def _normalize_policy_expr(expr: str | None) -> str:
    if not expr:
        return ""
    s = expr.strip().lower()
    s = re.sub(r"::\s*text\b", "", s)
    s = _strip_redundant_outer_parens(s)
    return re.sub(r"\s+", " ", s)


def _normalize_check_expr(definition: str) -> str:
    raw = (definition or "").strip()
    m = re.match(r"^CHECK\s*\((.*)\)\s*$", raw, flags=re.IGNORECASE | re.DOTALL)
    inner = m.group(1).strip() if m else raw
    inner = _strip_redundant_outer_parens(inner)
    return re.sub(r"\s+", " ", inner).lower()


def _policy_roles_public(roles_text: str) -> bool:
    raw = (roles_text or "").strip().lower()
    if not raw:
        return False
    tokens = re.findall(r"[a-z_][a-z0-9_]*", raw)
    return tokens == ["public"]


def check_pg_schema_ready(conn: Any) -> tuple[bool, str]:
    """
    Verify tenant observability schema exists and matches T4B phase-002 expectations.

    Does not query tenant-owned row data (no RLS tenant context required).
    """
    with conn.cursor() as cur:
        for table in _REQUIRED_TABLES:
            cur.execute(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = %s
                """,
                (table,),
            )
            if not cur.fetchone():
                return False, f"missing_table:public.{table}"

        for table in _TENANT_TABLES_CLIENT_ID:
            cur.execute(
                """
                SELECT is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = %s
                  AND column_name = 'client_id'
                """,
                (table,),
            )
            row = cur.fetchone()
            if not row:
                return False, f"missing_column:public.{table}.client_id"
            if str(row[0]).upper() != "NO":
                return False, f"nullable_client_id:public.{table}"

        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'v5_turn_traces'
            """
        )
        v5_cols = {str(row[0]) for row in cur.fetchall()}
        missing = sorted(_V5_REQUIRED_COLUMNS - v5_cols)
        if missing:
            return False, f"v5_turn_traces_missing_columns:{','.join(missing)}"

        cur.execute(
            """
            SELECT c.conname, c.convalidated
            FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE n.nspname = 'public'
              AND t.relname = ANY(%s)
              AND c.contype = 'c'
              AND c.conname = ANY(%s)
            """,
            (list(_REQUIRED_TABLES), list(_T4B_CHECK_CONSTRAINTS)),
        )
        found = {str(row[0]): bool(row[1]) for row in cur.fetchall()}
        for name in sorted(_T4B_CHECK_CONSTRAINTS):
            if name not in found:
                return False, f"missing_constraint:{name}"
            if not found[name]:
                return False, f"unvalidated_constraint:{name}"

        cur.execute(
            """
            SELECT i.indisunique,
                   array_agg(a.attname ORDER BY u.ord) AS columns
            FROM pg_class ic
            JOIN pg_index i ON i.indexrelid = ic.oid
            JOIN pg_class tc ON tc.oid = i.indrelid
            JOIN pg_namespace n ON n.oid = tc.relnamespace
            JOIN unnest(i.indkey) WITH ORDINALITY AS u(attnum, ord) ON true
            JOIN pg_attribute a ON a.attrelid = tc.oid AND a.attnum = u.attnum
            WHERE n.nspname = 'public'
              AND tc.relname = 'v5_turn_traces'
              AND ic.relname = %s
            GROUP BY i.indisunique
            """,
            (_COMPOSITE_UNIQUE_INDEX,),
        )
        idx_row = cur.fetchone()
        if not idx_row:
            return False, f"missing_index:public.{_COMPOSITE_UNIQUE_INDEX}"
        if not bool(idx_row[0]):
            return False, f"index_not_unique:public.{_COMPOSITE_UNIQUE_INDEX}"
        cols = tuple(str(c) for c in (idx_row[1] or []))
        if cols != _EXPECTED_INDEX_COLUMNS:
            return False, f"index_wrong_columns:public.{_COMPOSITE_UNIQUE_INDEX}:{cols}"

        ready, reason = _check_runtime_role_security(cur)
        if not ready:
            return False, reason

    return True, "ok"


def _check_runtime_role_security(cur: Any) -> tuple[bool, str]:
    cur.execute(
        """
        SELECT r.rolsuper,
               r.rolbypassrls,
               r.rolcreatedb,
               r.rolcreaterole,
               r.rolreplication,
               r.rolname
        FROM pg_roles r
        WHERE r.rolname = current_user
        """
    )
    role_row = cur.fetchone()
    if not role_row:
        return False, "runtime_role_unknown"
    if bool(role_row[0]):
        return False, "runtime_role_superuser"
    if bool(role_row[1]):
        return False, "runtime_role_bypassrls"
    if bool(role_row[2]):
        return False, "runtime_role_createdb"
    if bool(role_row[3]):
        return False, "runtime_role_createrole"
    if bool(role_row[4]):
        return False, "runtime_role_replication"
    runtime_name = str(role_row[5])

    cur.execute(
        """
        SELECT r.rolname
        FROM pg_auth_members m
        JOIN pg_roles r ON r.oid = m.roleid
        JOIN pg_roles u ON u.oid = m.member
        WHERE u.rolname = current_user
          AND r.rolname <> current_user
        """
    )
    if cur.fetchall():
        return False, "runtime_role_extra_membership"

    cur.execute(
        """
        SELECT tablename, tableowner
        FROM pg_tables
        WHERE schemaname = 'public'
          AND tablename = ANY(%s)
        """,
        (list(_REQUIRED_TABLES),),
    )
    owners = {str(row[0]): str(row[1]) for row in cur.fetchall()}
    for table in _REQUIRED_TABLES:
        owner = owners.get(table)
        if not owner:
            return False, f"missing_table_owner:public.{table}"
        if owner == runtime_name:
            return False, f"runtime_role_owns_table:public.{table}"

    cur.execute(
        """
        SELECT c.relname,
               c.relrowsecurity,
               c.relforcerowsecurity
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relname = ANY(%s)
          AND c.relkind = 'r'
        """,
        (list(_REQUIRED_TABLES),),
    )
    rls_flags = {str(row[0]): (bool(row[1]), bool(row[2])) for row in cur.fetchall()}
    for table in _REQUIRED_TABLES:
        flags = rls_flags.get(table)
        if not flags:
            return False, f"missing_rls_catalog:public.{table}"
        if not flags[0]:
            return False, f"rls_not_enabled:public.{table}"
        if not flags[1]:
            return False, f"rls_not_forced:public.{table}"

    cur.execute(
        """
        SELECT tablename, policyname, permissive, cmd, roles::text, qual, with_check
        FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = ANY(%s)
        ORDER BY tablename, policyname
        """,
        (list(_REQUIRED_TABLES),),
    )
    policies_by_table: dict[str, list[tuple[str, str, str, str, str, str]]] = {}
    for row in cur.fetchall():
        table = str(row[0])
        policies_by_table.setdefault(table, []).append(
            (
                str(row[1]),
                str(row[2]),
                str(row[3]),
                str(row[4]),
                str(row[5] or ""),
                str(row[6] or ""),
            )
        )

    for table in _REQUIRED_TABLES:
        rows = policies_by_table.get(table, [])
        if len(rows) != 1:
            return False, f"policy_count_invalid:public.{table}:{len(rows)}"
        name, permissive, cmd, roles, qual, with_check = rows[0]
        if name != _TENANT_POLICY_NAME:
            return False, f"policy_name_invalid:public.{table}:{name}"
        if permissive.strip().upper() != "PERMISSIVE":
            return False, f"policy_permissive_invalid:public.{table}:{permissive}"
        if cmd.strip().upper() != "ALL":
            return False, f"policy_cmd_invalid:public.{table}:{cmd}"
        if not _policy_roles_public(roles):
            return False, f"policy_roles_invalid:public.{table}"
        using_norm = _normalize_policy_expr(qual)
        check_norm = _normalize_policy_expr(with_check)
        if using_norm == "true":
            return False, f"policy_using_not_tenant_expr:public.{table}"
        if check_norm == "true":
            return False, f"policy_with_check_not_tenant_expr:public.{table}"
        if using_norm != _EXPECTED_TENANT_EXPR:
            return False, f"policy_using_mismatch:public.{table}"
        if check_norm != _EXPECTED_TENANT_EXPR:
            return False, f"policy_with_check_mismatch:public.{table}"

    cur.execute(
        """
        SELECT array_agg(a.attname ORDER BY u.ordinality) AS columns
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        JOIN unnest(c.conkey) WITH ORDINALITY AS u(attnum, ordinality) ON true
        JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = u.attnum
        WHERE n.nspname = 'public'
          AND t.relname = 'v5_turn_traces'
          AND c.contype = 'p'
        GROUP BY c.oid
        """
    )
    pk_row = cur.fetchone()
    if not pk_row:
        return False, "missing_primary_key:public.v5_turn_traces"
    pk_cols = tuple(str(c) for c in (pk_row[0] or []))
    if pk_cols != _EXPECTED_PK_COLUMNS:
        return False, f"primary_key_wrong_columns:public.v5_turn_traces:{pk_cols}"

    cur.execute("SELECT has_schema_privilege(current_user, 'public', 'USAGE')")
    usage_row = cur.fetchone()
    if not usage_row or not bool(usage_row[0]):
        return False, "runtime_schema_usage_missing"

    cur.execute("SELECT has_schema_privilege(current_user, 'public', 'CREATE')")
    create_priv = cur.fetchone()
    if create_priv and bool(create_priv[0]):
        return False, "runtime_schema_create_granted"

    for table in _REQUIRED_TABLES:
        qualified = f"public.{table}"
        for priv in _RUNTIME_DML_PRIVS:
            cur.execute(
                "SELECT has_table_privilege(current_user, %s, %s)",
                (qualified, priv),
            )
            row = cur.fetchone()
            if not row or not bool(row[0]):
                return False, f"runtime_table_priv_missing:public.{table}:{priv.lower()}"
        for priv in _RUNTIME_FORBIDDEN_TABLE_PRIVS:
            cur.execute(
                "SELECT has_table_privilege(current_user, %s, %s)",
                (qualified, priv),
            )
            row = cur.fetchone()
            if row and bool(row[0]):
                return False, f"runtime_table_priv_forbidden:public.{table}:{priv.lower()}"

    for seq in _RUNTIME_SEQUENCES:
        qualified = f"public.{seq}"
        for priv in ("USAGE", "SELECT"):
            cur.execute(
                "SELECT has_sequence_privilege(current_user, %s, %s)",
                (qualified, priv),
            )
            row = cur.fetchone()
            if not row or not bool(row[0]):
                return False, f"runtime_sequence_priv_missing:public.{seq}:{priv.lower()}"
        cur.execute(
            "SELECT has_sequence_privilege(current_user, %s, %s)",
            (qualified, "UPDATE"),
        )
        upd_row = cur.fetchone()
        if upd_row and bool(upd_row[0]):
            return False, f"runtime_sequence_priv_forbidden:public.{seq}:update"

    for priv in _LEDGER_FORBIDDEN_SCHEMA_PRIVS:
        cur.execute(
            "SELECT has_schema_privilege(current_user, %s, %s)",
            (_LEDGER_SCHEMA, priv),
        )
        row = cur.fetchone()
        if row and bool(row[0]):
            return False, f"runtime_ledger_schema_forbidden:{priv.lower()}"

    for priv in _LEDGER_FORBIDDEN_TABLE_PRIVS:
        cur.execute(
            "SELECT has_table_privilege(current_user, %s, %s)",
            (_LEDGER_TABLE, priv),
        )
        row = cur.fetchone()
        if row and bool(row[0]):
            return False, f"runtime_ledger_table_forbidden:{priv.lower()}"

    return True, "ok"
