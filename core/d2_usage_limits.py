"""Tenant-owned, durable resource admission. No dialogue or semantic decisions."""
from hashlib import sha256
from pathlib import Path
from typing import Annotated
import re
import time
import uuid

import yaml
from pydantic import BaseModel, ConfigDict, Field, StrictInt

PositiveInt = Annotated[StrictInt, Field(gt=0)]


class ClientUsageLimits(BaseModel):
    model_config = ConfigDict(extra="forbid")
    visitor_messages_per_minute: PositiveInt
    ip_messages_per_minute: PositiveInt
    visitor_ai_questions_per_day: PositiveInt
    tenant_model_calls_per_day: PositiveInt
    message_max_chars: PositiveInt
    request_max_bytes: PositiveInt
    visitor_leads_per_hour: PositiveInt


def limits_from_features(features):
    if "usage_limits" not in features:
        return None
    return ClientUsageLimits.model_validate(features["usage_limits"])


def load_usage_limits(client_id, *, clients_root=None):
    if clients_root is None:
        from core.client_config_loader import load_features
        return limits_from_features(load_features(client_id))
    raw = yaml.safe_load((Path(clients_root) / client_id / "features.yaml").read_text(encoding="utf-8")) or {}
    return limits_from_features(raw)


class ClientUsageLimitReached(RuntimeError):
    def __init__(self, code, retry_after=60):
        self.code, self.retry_after = code, max(1, int(retry_after))
        super().__init__(code)


def visitor_bucket(visitor_id, peer_ip):
    # A browser token is a best-effort bucket, never an authenticated identity.
    if visitor_id is not None and (
        not isinstance(visitor_id, str)
        or not re.fullmatch(r"[a-fA-F0-9-]{32,36}", visitor_id)
    ):
        raise ValueError("visitor_id_invalid")
    return sha256(("visitor:" + visitor_id if visitor_id else "peer:" + (peer_ip or "unknown")).encode()).hexdigest()


class ClientUsageAdmission:
    def __init__(self, connection, *, limits, client_id, sid, request_id, visitor_id, peer_ip, clock=None):
        self.db, self.limits, self.client = connection, limits, client_id
        self.sid, self.request = sid, request_id
        self.visitor = visitor_bucket(visitor_id, peer_ip)
        self.peer = sha256((peer_ip or "unknown").encode()).hexdigest()
        self.clock = clock or time.time
        self.db.execute("""CREATE TABLE IF NOT EXISTS d2_usage_event (
            client_id TEXT NOT NULL, kind TEXT NOT NULL, sid TEXT NOT NULL,
            request_id TEXT NOT NULL, event_id TEXT NOT NULL, visitor_hash TEXT NOT NULL,
            peer_hash TEXT NOT NULL, admitted_at REAL NOT NULL,
            PRIMARY KEY(client_id,kind,sid,request_id,event_id))""")
        self.db.execute("CREATE INDEX IF NOT EXISTS d2_usage_time ON d2_usage_event(client_id,kind,admitted_at)")
        self.db.execute("CREATE INDEX IF NOT EXISTS d2_usage_visitor ON d2_usage_event(client_id,kind,visitor_hash,admitted_at)")
        self.db.execute("CREATE INDEX IF NOT EXISTS d2_usage_peer ON d2_usage_event(client_id,kind,peer_hash,admitted_at)")
        self.db.commit()

    def _seen(self, kind):
        # Keep request deduplication durable, including failed request retries.
        row = self.db.execute("SELECT visitor_hash FROM d2_usage_event WHERE client_id=? AND kind=? AND sid=? AND request_id=? LIMIT 1",
                              (self.client, kind, self.sid, self.request)).fetchone()
        if row and row[0] != self.visitor:
            raise ValueError("usage_request_visitor_mismatch")
        return row is not None

    def _check(self, kind, window, maximum, code, now, bucket=None):
        clause, args = "", []
        if bucket:
            column, value = bucket
            clause, args = " AND " + column + "=?", [value]
        count, oldest = self.db.execute(
            "SELECT COUNT(*),MIN(admitted_at) FROM d2_usage_event WHERE client_id=? AND kind=? AND admitted_at>?" + clause,
            [self.client, kind, now-window, *args]).fetchone()
        if count >= maximum:
            raise ClientUsageLimitReached(code, oldest + window - now + 1)

    def _insert(self, kind, now, event=""):
        self.db.execute("INSERT INTO d2_usage_event VALUES(?,?,?,?,?,?,?,?)",
                        (self.client, kind, self.sid, self.request, event, self.visitor, self.peer, now))

    def message(self):
        now = self.clock()
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            self._seen("message")  # Validate the bucket binding on failed retries.
            self._check("message", 60, self.limits.visitor_messages_per_minute, "visitor_rate_limit", now, ("visitor_hash", self.visitor))
            self._check("message", 60, self.limits.ip_messages_per_minute, "ip_rate_limit", now, ("peer_hash", self.peer))
            # Completed replay bypasses this method at the dialogue owner.
            # A retry after a failed turn is fresh ingress and must be throttled.
            self._insert("message", now, uuid.uuid4().hex)

    def model(self):
        now = self.clock()
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            seen = self._seen("question")
            if not seen:
                self._check("question", 86400, self.limits.visitor_ai_questions_per_day, "visitor_ai_limit", now, ("visitor_hash", self.visitor))
            self._check("model", 86400, self.limits.tenant_model_calls_per_day, "tenant_ai_limit", now)
            if not seen:
                self._insert("question", now)
            self._insert("model", now, uuid.uuid4().hex)

    def lead(self):
        now = self.clock()
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            # An already attempted effect must never send a second email.
            if self._seen("lead"):
                raise ClientUsageLimitReached("lead_already_attempted", 3600)
            self._check("lead", 3600, self.limits.visitor_leads_per_hour, "visitor_lead_limit", now, ("visitor_hash", self.visitor))
            self._insert("lead", now)
