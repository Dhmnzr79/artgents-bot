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


def _strip_redundant_outer_parens(expr: str) -> str:
    inner = expr.strip()
    while len(inner) >= 2 and inner[0] == "(" and inner[-1] == ")":
        candidate = inner[1:-1].strip()
        if candidate.count("(") != candidate.count(")"):
            break
        inner = candidate
    return inner


def _normalize_check_expr(definition: str) -> str:
    raw = (definition or "").strip()
    m = re.match(r"^CHECK\s*\((.*)\)\s*$", raw, flags=re.IGNORECASE | re.DOTALL)
    inner = m.group(1).strip() if m else raw
    inner = _strip_redundant_outer_parens(inner)
    return re.sub(r"\s+", " ", inner).lower()


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

    return True, "ok"
