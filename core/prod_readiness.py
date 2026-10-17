"""Production readiness checks (read-only, no provider calls)."""
from __future__ import annotations

import os
from typing import Any

import config
from core.alibaba_openai_transport_policy import (
    AlibabaEndpointConfigurationError,
    validate_alibaba_chat_api_key,
    validate_alibaba_chat_base_url,
)
from core.client_config_loader import ExplicitPackClientIdError, require_explicit_pack_client_id
from core.d2_tenant_snapshot import (
    d2_clients_root, load_d2_tenant_snapshot, build_d2_model_view,
    validate_d2_authored_content_refs,
)

_FORBIDDEN_RUNTIME_CLIENT_IDS = frozenset({"default", "_template"})


def _invalid_allowed_client_id(client_id: str) -> str | None:
    cid = (client_id or "").strip()
    if not cid:
        return "allowed_client_id_empty"
    if cid in _FORBIDDEN_RUNTIME_CLIENT_IDS:
        return "allowed_client_id_forbidden"
    try:
        require_explicit_pack_client_id(cid)
    except ExplicitPackClientIdError:
        return "allowed_client_pack_missing"
    clients_root = d2_clients_root().resolve()
    pack_root = (clients_root / cid).resolve()
    if pack_root.parent != clients_root:
        return "allowed_client_pack_invalid"
    md_dir = pack_root / "md"
    if not os.path.isdir(md_dir):
        return "allowed_client_pack_missing"
    try:
        md_files = [
            name
            for name in os.listdir(md_dir)
            if name.lower().endswith(".md") and os.path.isfile(os.path.join(md_dir, name))
        ]
    except OSError:
        return "allowed_client_pack_invalid"
    if not md_files:
        return "allowed_client_pack_invalid"
    try:
        from core.d2_usage_limits import load_usage_limits
        load_usage_limits(cid, clients_root=clients_root)
    except (ValueError, OSError):
        return "allowed_client_usage_limits_invalid"
    try:
        snapshot = load_d2_tenant_snapshot(cid, clients_root=clients_root)
        build_d2_model_view(snapshot)
        if validate_d2_authored_content_refs(snapshot):
            return "allowed_client_pack_invalid"
    except Exception:
        return "allowed_client_pack_invalid"
    if not snapshot.bundle.services or not snapshot.bundle.offers:
        return "allowed_client_pack_invalid"
    return None


def evaluate_allowed_client_registry() -> list[str]:
    """Fail-closed registry checks for prod startup/readiness."""
    reasons: list[str] = []
    if not config.ALLOWED_CLIENTS:
        reasons.append("allowed_clients_empty")
        return reasons
    default_cid = (config.DEFAULT_CLIENT_ID or "").strip()
    if not default_cid or default_cid not in config.ALLOWED_CLIENTS:
        reasons.append("default_client_not_allowed")
    for cid in sorted(config.ALLOWED_CLIENTS):
        code = _invalid_allowed_client_id(cid)
        if code:
            reasons.append(f"{code}:{cid}")
    return reasons


def _evaluate_chat_transport() -> list[str]:
    reasons: list[str] = []
    try:
        validate_alibaba_chat_api_key(config.CHAT_API_KEY)
    except AlibabaEndpointConfigurationError as exc:
        reasons.append(str(exc.code))
    try:
        validate_alibaba_chat_base_url(config.CHAT_BASE_URL)
    except AlibabaEndpointConfigurationError as exc:
        reasons.append(str(exc.code))
    return reasons


def _evaluate_postgres_schema(dsn: str) -> list[str]:
    reasons: list[str] = []
    try:
        import psycopg
    except Exception:
        reasons.append("postgres_driver_unavailable")
        return reasons
    conn = None
    try:
        conn = psycopg.connect(dsn, autocommit=True, connect_timeout=3)
        from core.pg_schema_readiness import check_pg_schema_ready

        ready, reason = check_pg_schema_ready(conn)
        if not ready:
            reasons.append(f"postgres_schema_not_ready:{reason}")
    except Exception:
        reasons.append("postgres_unavailable")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
    return reasons


def evaluate_readiness(*, app_env: str | None = None) -> tuple[bool, dict[str, Any]]:
    """
    Return (ok, payload) for /health/ready.

    Prod: full fail-closed checks including PostgreSQL schema.
    Local/test: optional PG when BOT_PG_DSN unset; no provider/SMTP calls.
    """
    env = (app_env or config.APP_ENV or "local").strip().lower()
    checks: dict[str, Any] = {"app_env": env}

    if env != "prod":
        checks["postgres"] = "skipped"
        checks["chat_transport"] = "skipped"
        checks["client_registry"] = "skipped"
        return True, {"ok": True, "status": "ready", "checks": checks}

    reasons: list[str] = []
    reasons.extend(evaluate_allowed_client_registry())
    reasons.extend(_evaluate_chat_transport())

    dsn = (os.getenv("BOT_PG_DSN") or "").strip()
    if not dsn:
        reasons.append("bot_pg_dsn_missing")
    else:
        reasons.extend(_evaluate_postgres_schema(dsn))

    checks["reasons"] = reasons
    ok = not reasons
    checks["status"] = "ready" if ok else "not_ready"
    return ok, {"ok": ok, "status": checks["status"], "checks": checks}
