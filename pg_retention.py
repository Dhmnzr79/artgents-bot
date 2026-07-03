"""Rolling retention for observability data (variant A: per-session last activity)."""
from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timedelta, timezone

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


def purge_session_observability(
    dsn: str,
    *,
    sid: str,
    client_id: str,
    keep_llm_usage: bool = True,
) -> dict[str, int | bool]:
    """Delete one sid from PG (+ SQLite). Keeps llm_usage rows when keep_llm_usage=True."""
    sid_clean = (sid or "").strip()
    cid = (client_id or "").strip()
    stats: dict[str, int | bool] = {
        "found": False,
        "bot_events_deleted": 0,
        "traces_deleted": 0,
        "leads_deleted": 0,
        "sqlite_cleared": False,
    }
    if not sid_clean or not cid or not (dsn or "").strip():
        return stats

    import psycopg

    with psycopg.connect(dsn.strip(), autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM bot_events WHERE sid=%s AND client_id=%s LIMIT 1",
                (sid_clean, cid),
            )
            if not cur.fetchone():
                cur.execute(
                    "SELECT 1 FROM leads WHERE sid=%s AND client_id=%s LIMIT 1",
                    (sid_clean, cid),
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
                    (sid_clean, cid),
                )
            else:
                cur.execute(
                    "DELETE FROM bot_events WHERE sid=%s AND client_id=%s",
                    (sid_clean, cid),
                )
            stats["bot_events_deleted"] = int(cur.rowcount or 0)
            cur.execute("DELETE FROM v5_turn_traces WHERE sid=%s", (sid_clean,))
            stats["traces_deleted"] = int(cur.rowcount or 0)
            cur.execute(
                "DELETE FROM leads WHERE sid=%s AND client_id=%s",
                (sid_clean, cid),
            )
            stats["leads_deleted"] = int(cur.rowcount or 0)

    from session import bind_session_client, mem_reset

    try:
        bind_session_client(cid)
        mem_reset(sid_clean)
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

    with psycopg.connect(dsn.strip(), autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sid, client_id
                FROM bot_events
                WHERE sid IS NOT NULL
                GROUP BY sid, client_id
                HAVING max(occurred_at) < %s
                """,
                (cutoff,),
            )
            expired = [(str(sid), str(client_id or "")) for sid, client_id in cur.fetchall() if sid]
        if not expired:
            return stats

        sids = [row[0] for row in expired]
        stats["sids_purged"] = len(sids)

        for sid, client_id in expired:
            row_stats = purge_session_observability(
                dsn,
                sid=sid,
                client_id=client_id or "",
                keep_llm_usage=True,
            )
            stats["bot_events_deleted"] += int(row_stats.get("bot_events_deleted") or 0)
            stats["traces_deleted"] += int(row_stats.get("traces_deleted") or 0)
            stats["leads_deleted"] += int(row_stats.get("leads_deleted") or 0)

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
