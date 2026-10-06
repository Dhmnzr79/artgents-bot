"""Demo-only admission of billable attempts; no dialogue or model decisions."""
from hashlib import sha256
import time

from config import RATE_LIMIT_MAX_PER_IP, RATE_LIMIT_WINDOW_SEC


class D2DemoLimitReached(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def admit_demo_call(connection, *, sid, peer_ip, now=None):
    """Reserve an attempt atomically, before network; failures still cost quota.

    Stored in the demo's existing SQLite file, persistent across process restarts.
    IP is the captured peer address, never an untrusted forwarded header.
    """
    stamp = time.time() if now is None else now
    peer = sha256((peer_ip or "unknown").encode()).hexdigest()
    connection.execute(
        "CREATE TABLE IF NOT EXISTS d2_demo_model_attempt "
        "(sid TEXT NOT NULL, peer_hash TEXT NOT NULL, admitted_at REAL NOT NULL)"
    )
    connection.execute("CREATE INDEX IF NOT EXISTS d2_demo_attempt_sid ON d2_demo_model_attempt(sid)")
    connection.execute("CREATE INDEX IF NOT EXISTS d2_demo_attempt_time ON d2_demo_model_attempt(admitted_at)")
    connection.execute("CREATE INDEX IF NOT EXISTS d2_demo_attempt_peer ON d2_demo_model_attempt(peer_hash, admitted_at)")
    connection.commit()
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        checks = (
            ("demo_session_limit", 10, "sid=?", (sid,)),
            ("demo_ip_limit", RATE_LIMIT_MAX_PER_IP,
             "peer_hash=? AND admitted_at>?", (peer, stamp - RATE_LIMIT_WINDOW_SEC)),
            ("demo_daily_limit", 200, "admitted_at>?", (stamp - 86400,)),
        )
        for code, limit, clause, args in checks:
            count = connection.execute(
                "SELECT COUNT(*) FROM d2_demo_model_attempt WHERE " + clause, args,
            ).fetchone()[0]
            if count >= limit:
                raise D2DemoLimitReached(code)
        connection.execute(
            "INSERT INTO d2_demo_model_attempt(sid,peer_hash,admitted_at) VALUES(?,?,?)",
            (sid, peer, stamp),
        )
