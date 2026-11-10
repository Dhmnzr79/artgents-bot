"""One durable shared admission owner for both public demos."""
from contextlib import closing
from hashlib import sha256
import sqlite3
import time

from config import RATE_LIMIT_MAX_PER_IP, RATE_LIMIT_WINDOW_SEC
from core.d2_storage import dialogue_store_path
from core.d2_usage_limits import visitor_bucket

DEMO_CLIENTS = frozenset({"demo", "demo_medical"})
DEMO_DAILY_CALLS = 4000
DEMO_VISITOR_QUESTIONS = 30


class D2DemoLimitReached(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def demo_usage_path():
    # Always anchored to demo, never the requesting tenant's directory.
    return dialogue_store_path("demo").with_name("demo_usage.sqlite")


def reserve_demo_call(**kwargs):
    path = demo_usage_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path, timeout=5)) as connection:
        admit_demo_call(connection, **kwargs)


def admit_demo_call(connection, *, sid, request_id, visitor_id, peer_ip,
                    client_id="demo", now=None):
    """Charge each attempted call, but one question per tenant/SID/request ID.

    Failures remain charged. Completed dialogue replay never calls this owner.
    Browser IDs are best effort; absent IDs use a hashed peer address.
    """
    if client_id not in DEMO_CLIENTS or not sid or not request_id:
        raise ValueError("demo_admission_identity_invalid")
    stamp = time.time() if now is None else now
    visitor = visitor_bucket(visitor_id, peer_ip)
    peer = sha256((peer_ip or "unknown").encode()).hexdigest()
    connection.execute("""CREATE TABLE IF NOT EXISTS demo_usage_attempt (
        client_id TEXT NOT NULL, sid TEXT NOT NULL, request_id TEXT NOT NULL,
        visitor_hash TEXT NOT NULL, peer_hash TEXT NOT NULL, admitted_at REAL NOT NULL)""")
    connection.execute("CREATE INDEX IF NOT EXISTS demo_usage_time ON demo_usage_attempt(admitted_at)")
    connection.execute("CREATE INDEX IF NOT EXISTS demo_usage_question ON demo_usage_attempt(client_id,sid,request_id)")
    connection.execute("CREATE INDEX IF NOT EXISTS demo_usage_visitor ON demo_usage_attempt(visitor_hash,admitted_at)")
    connection.execute("CREATE INDEX IF NOT EXISTS demo_usage_peer ON demo_usage_attempt(peer_hash,admitted_at)")
    connection.commit()
    identity = (client_id, sid, request_id)
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        seen = connection.execute(
            "SELECT visitor_hash, MAX(admitted_at) FROM demo_usage_attempt WHERE client_id=? AND sid=? AND request_id=? GROUP BY visitor_hash",
            identity).fetchall()
        if any(row[0] != visitor for row in seen):
            raise ValueError("usage_request_visitor_mismatch")
        already_question = any(row[1] > stamp - 86400 for row in seen)
        if not already_question:
            questions = connection.execute("""SELECT COUNT(*) FROM (
                SELECT client_id,sid,request_id FROM demo_usage_attempt
                WHERE visitor_hash=? AND admitted_at>?
                GROUP BY client_id,sid,request_id)""", (visitor, stamp - 86400)).fetchone()[0]
            if questions >= DEMO_VISITOR_QUESTIONS:
                raise D2DemoLimitReached("demo_visitor_limit")
        for code, maximum, clause, args in (
            ("demo_ip_limit", RATE_LIMIT_MAX_PER_IP, "peer_hash=? AND admitted_at>?", (peer, stamp - RATE_LIMIT_WINDOW_SEC)),
            ("demo_daily_limit", DEMO_DAILY_CALLS, "admitted_at>?", (stamp - 86400,)),
        ):
            count = connection.execute("SELECT COUNT(*) FROM demo_usage_attempt WHERE " + clause, args).fetchone()[0]
            if count >= maximum:
                raise D2DemoLimitReached(code)
        connection.execute("INSERT INTO demo_usage_attempt VALUES(?,?,?,?,?,?)",
                           (*identity, visitor, peer, stamp))
