"""Migration 002 must replace drifted CHECK constraints, not accept wrong semantics."""
from __future__ import annotations

from pathlib import Path

from core.pg_schema_readiness import _normalize_check_expr

_ROOT = Path(__file__).resolve().parents[1]
_SQL_002 = (_ROOT / "migrations" / "postgresql" / "002_tenant_schema_prepare.sql").read_text(
    encoding="utf-8"
)

_CLIENT_CHECK = (
    "client_id = btrim(client_id) AND length(client_id) > 0 "
    "AND client_id !~ '[./\\\\]' AND client_id NOT LIKE '%..%' "
    "AND client_id !~ '^[.-]' AND client_id ~ '^[a-z0-9][a-z0-9_-]*$' "
    "AND client_id NOT IN ('default', '_template')"
)


def test_normalize_check_expr_detects_semantic_drift() -> None:
    good = f"CHECK ({_CLIENT_CHECK})"
    bad = f"CHECK ({_CLIENT_CHECK} AND client_id <> 'evil')"
    assert _normalize_check_expr(good) == _normalize_check_expr(f"CHECK(({_CLIENT_CHECK}))")
    assert _normalize_check_expr(good) != _normalize_check_expr(bad)


def test_002_uses_ensure_t4b_with_drop_on_mismatch() -> None:
    assert "_ensure_t4b_check_constraint" in _SQL_002
    assert "DROP CONSTRAINT" in _SQL_002
    assert "_normalize_check_expr" in _SQL_002
    assert "_add_check_if_missing" not in _SQL_002
