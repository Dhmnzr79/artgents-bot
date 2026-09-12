"""Rolling retention for observability data (variant A: per-session last activity)."""
from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timedelta, timezone

from core.client_config_loader import list_trusted_tenant_ids
from core.pg_tenant_context import (
    InvalidPgTenantError,
    tenant_transaction,
    validate_trusted_pg_tenant,
)

_RETENTION_HOURS = int(os.getenv("BOT_OBSERVABILITY_RETENTION_HOURS", "24"))
_INTERVAL_SEC = int(os.getenv("BOT_OBSERVABILITY_RETENTION_INTERVAL_SEC", "3600"))
_WORKER_STARTED = False
_WORKER_LOCK = threading.Lock()
_LOGGER = None


def retention_hours() -> int:
    return max(0, _RETENTION_HOURS)


def _log(level: str, msg: str, **fields) -> None:
    logger = _LOGGER
    if logger is None:
        return
    try:
        from logging_setup import log_json

        log_json(logger, msg, **fields)
    except Exception:
        try:
            getattr(logger, level, logger.info)(f"{msg} {fields}")
        except Exception:
            pass


def _purge_session_pg(
    conn,
    *,
    tenant: str,
    sid_clean: str,
    keep_llm_usage: bool,
) -> dict[str, int | bool]:
    stats: dict[str, int | bool] = {
        "found": False,
        "bot_events_deleted": 0,
        "traces_deleted": 0,
        "leads_deleted": 0,
    }
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM bot_events WHERE sid=%s AND client_id=%s LIMIT 1",
            (sid_clean, tenant),
        )
        if not cur.fetchone():
            cur.execute(
                "SELECT 1 FROM leads WHERE sid=%s AND client_id=%s LIMIT 1",
                (sid_clean, tenant),
            )
            if not cur.fetchone():
                return stats
        stats["found"] = True

        if keep_llm_usage:
            cur.execute(
                """
                DELETE FROM bot_events
                WHERE sid=%s AND client_id=%s AND event_type <> 'llm_usage'
                """,
                (sid_clean, tenant),
            )
        else:
            cur.execute(
                "DELETE FROM bot_events WHERE sid=%s AND client_id=%s",
                (sid_clean, tenant),
            )
        stats["bot_events_deleted"] = int(cur.rowcount or 0)
        cur.execute(
            "DELETE FROM v5_turn_traces WHERE sid=%s AND client_id=%s",
            (sid_clean, tenant),
        )
        stats["traces_deleted"] = int(cur.rowcount or 0)
        cur.execute(
            "DELETE FROM leads WHERE sid=%s AND client_id=%s",
            (sid_clean, tenant),
        )
        stats["leads_deleted"] = int(cur.rowcount or 0)
    return stats


def purge_session_observability(
    dsn: str,
    *,
    sid: str,
    client_id: str,
    keep_llm_usage: bool = True,
) -> dict[str, int | bool]:
    """Delete one sid from PG (+ SQLite). Keeps llm_usage rows when keep_llm_usage=True."""
    sid_clean = (sid or "").strip()
    stats: dict[str, int | bool] = {
        "found": False,
        "bot_events_deleted": 0,
        "traces_deleted": 0,
        "leads_deleted": 0,
        "sqlite_cleared": False,
    }
    if not sid_clean or not (dsn or "").strip():
        return stats

    try:
        tenant = validate_trusted_pg_tenant(client_id)
    except InvalidPgTenantError:
        return stats

    import psycopg

    try:
        with psycopg.connect(dsn.strip(), autocommit=True) as conn:
            with tenant_transaction(conn, tenant):
                row_stats = _purge_session_pg(
                    conn,
                    tenant=tenant,
                    sid_clean=sid_clean,
                    keep_llm_usage=keep_llm_usage,
                )
    except Exception as e:
        _log("warning", "observability_purge_pg_failed", err=str(e)[:200])
        return stats

    stats["found"] = bool(row_stats.get("found"))
    stats["bot_events_deleted"] = int(row_stats.get("bot_events_deleted") or 0)
    stats["traces_deleted"] = int(row_stats.get("traces_deleted") or 0)
    stats["leads_deleted"] = int(row_stats.get("leads_deleted") or 0)

    from session import mem_reset

    try:
        mem_reset(sid_clean, client_id=tenant)
        stats["sqlite_cleared"] = True
    except Exception as e:
        _log("warning", "observability_purge_sqlite_failed", sid=sid_clean, err=str(e)[:200])

    return stats


def purge_expired_observability(dsn: str, *, retention_hours: int | None = None) -> dict[str, int]:
    """Delete PG rows and SQLite sessions idle longer than retention window."""
    hours = retention_hours() if retention_hours is None else max(0, int(retention_hours))
    if hours <= 0 or not (dsn or "").strip():
        return {"sids_purged": 0, "bot_events_deleted": 0, "traces_deleted": 0, "leads_deleted": 0}

    import psycopg

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    stats = {
        "sids_purged": 0,
        "bot_events_deleted": 0,
        "traces_deleted": 0,
        "leads_deleted": 0,
    }

    tenants = list_trusted_tenant_ids()
    if not tenants:
        return stats

    try:
        with psycopg.connect(dsn.strip(), autocommit=True) as conn:
            for tenant in tenants:
                expired_sids: list[str] = []
                with tenant_transaction(conn, tenant):
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            SELECT sid
                            FROM bot_events
                            WHERE client_id = %s AND sid IS NOT NULL
                            GROUP BY sid
                            HAVING max(occurred_at) < %s
                            """,
                            (tenant, cutoff),
                        )
                        expired_sids = [str(row[0]) for row in cur.fetchall() if row and row[0]]

                for sid_clean in expired_sids:
                    with tenant_transaction(conn, tenant):
                        row_stats = _purge_session_pg(
                            conn,
                            tenant=tenant,
                            sid_clean=sid_clean,
                            keep_llm_usage=True,
                        )
                    stats["sids_purged"] += 1
                    stats["bot_events_deleted"] += int(row_stats.get("bot_events_deleted") or 0)
                    stats["traces_deleted"] += int(row_stats.get("traces_deleted") or 0)
                    stats["leads_deleted"] += int(row_stats.get("leads_deleted") or 0)
                    try:
                        from session import mem_reset

                        mem_reset(sid_clean, client_id=tenant)
                    except Exception as e:
                        _log(
                            "warning",
                            "observability_purge_sqlite_failed",
                            sid=sid_clean,
                            err=str(e)[:200],
                        )
    except Exception as e:
        _log("warning", "observability_retention_failed", err=str(e)[:300])

    return stats


def start_observability_retention_worker(logger, dsn: str | None = None) -> bool:
    """Background rolling purge (daemon thread). No-op when retention_hours=0."""
    global _WORKER_STARTED, _LOGGER
    hours = retention_hours()
    pg_dsn = (dsn or os.getenv("BOT_PG_DSN") or "").strip()
    if hours <= 0 or not pg_dsn:
        return False

    _LOGGER = logger
    with _WORKER_LOCK:
        if _WORKER_STARTED:
            return True
        _WORKER_STARTED = True

    def _loop() -> None:
        while True:
            try:
                stats = purge_expired_observability(pg_dsn, retention_hours=hours)
                if stats.get("sids_purged"):
                    _log("info", "observability_retention_purge", **stats, retention_hours=hours)
            except Exception as e:
                _log("warning", "observability_retention_failed", err=str(e)[:300])
            time.sleep(max(60, _INTERVAL_SEC))

    t = threading.Thread(target=_loop, name="observability-retention", daemon=True)
    t.start()
    _log("info", "observability_retention_started", retention_hours=hours, interval_sec=_INTERVAL_SEC)
    return True
