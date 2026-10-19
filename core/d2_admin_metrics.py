"""Owner-approved, text-free technical observations; never a dialogue decision.

SID/request IDs are hashed, because caller-supplied IDs may themselves contain PII.
Failures here cannot fail a bot request. No transcript, prompt or exception text.
"""
from contextvars import ContextVar
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from functools import wraps
import logging
import os
import re
import sqlite3
from time import monotonic
from uuid import uuid4

from core.d2_storage import dialogue_store_path
from core.d2_costing import cache_split, cost_snapshot, token_count

_current = ContextVar('d2_admin_observation', default=None)
_warned = False

# Nullable additions belong only to this technical ledger. Old rows stay unknown.
DETAIL_COLUMNS = {
    'cached_prompt_tokens': 'INTEGER', 'uncached_prompt_tokens': 'INTEGER',
    'provider_started_at': 'TEXT', 'pricing_basis': 'TEXT',
    'rate_cached_usd_per_1m': 'REAL', 'rate_uncached_usd_per_1m': 'REAL',
    'rate_completion_usd_per_1m': 'REAL',
}


def identity_hash(value: str) -> str:
    return sha256(value.encode('utf-8', errors='surrogatepass')).hexdigest()


def _best_effort(fn):
    @wraps(fn)
    def guarded(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception:
            return None
    return guarded


def _write(client_id, values):
    global _warned
    if os.getenv('D2_ADMIN_METRICS_ENABLED', '1') != '1':
        return
    try:
        path = dialogue_store_path(client_id)
        if not path.is_file():
            return
        with closing(sqlite3.connect(path, timeout=.05)) as conn, conn:
            conn.execute('BEGIN IMMEDIATE')
            conn.execute('''CREATE TABLE IF NOT EXISTS d2_admin_observation (
                client_id TEXT NOT NULL, event_id TEXT NOT NULL, sid_hash TEXT NOT NULL,
                request_hash TEXT NOT NULL, observed_at TEXT NOT NULL, kind TEXT NOT NULL,
                outcome TEXT NOT NULL, model TEXT, prompt_tokens INTEGER, completion_tokens INTEGER,
                duration_ms INTEGER NOT NULL, estimated_usd REAL,
                PRIMARY KEY(client_id,event_id))''')
            columns = {row[1] for row in conn.execute('PRAGMA table_info(d2_admin_observation)')}
            for name, sql_type in DETAIL_COLUMNS.items():
                if name not in columns:
                    conn.execute(f'ALTER TABLE d2_admin_observation ADD COLUMN {name} {sql_type}')
            conn.execute('CREATE INDEX IF NOT EXISTS d2_admin_observation_time ON d2_admin_observation(client_id,observed_at)')
            conn.execute('CREATE INDEX IF NOT EXISTS d2_admin_observation_request ON d2_admin_observation(client_id,request_hash)')
            record = {'client_id': client_id, **values}
            conn.execute('INSERT OR IGNORE INTO d2_admin_observation (' + ','.join(record)
                         + ') VALUES (' + ','.join('?' for _ in record) + ')', tuple(record.values()))
            days = max(1, int(os.getenv('D2_ADMIN_METRICS_RETENTION_DAYS', '30')))
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            conn.execute('DELETE FROM d2_admin_observation WHERE client_id=? AND observed_at<?', (client_id, cutoff))
    except Exception:
        if not _warned:
            _warned = True
            logging.getLogger('bot').warning('d2_admin_metrics_unavailable')


@dataclass
class RequestObservation:
    client_id: str
    sid_hash: str
    request_hash: str
    attempt: str = field(default_factory=lambda: uuid4().hex)
    started: float = field(default_factory=monotonic)
    calls: int = 0
    outcome: str = 'failed'

    def __enter__(self):
        self._token = _current.set(self)
        return self

    def complete(self, replay=False):
        self.outcome = 'replayed' if replay else 'completed'

    @_best_effort
    def __exit__(self, *_exc):
        _current.reset(self._token)
        _write(self.client_id, dict(event_id=self.attempt, sid_hash=self.sid_hash,
            request_hash=self.request_hash, observed_at=datetime.now(timezone.utc).isoformat(),
            kind='request', outcome=self.outcome,
            duration_ms=max(0, int((monotonic() - self.started) * 1000))))


def observe_request(client_id, sid, request_id):
    return RequestObservation(client_id, identity_hash(sid), identity_hash(request_id))


@_best_effort
def provider_started(model):
    observation = _current.get()
    if observation is None:
        return None
    observation.calls += 1
    safe_model = model if isinstance(model, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,149}', model) else None
    return observation, observation.calls, monotonic(), safe_model, datetime.now(timezone.utc)


@_best_effort
def provider_finished(observation, response=None):
    if observation is None:
        return
    owner, index, started, model, started_at = observation
    usage = getattr(response, 'usage', None)
    prompt, completion = token_count(usage, 'prompt_tokens'), token_count(usage, 'completion_tokens')
    cached, uncached = cache_split(usage, prompt)
    _write(owner.client_id, dict(event_id=f'{owner.attempt}:{index}', sid_hash=owner.sid_hash,
        request_hash=owner.request_hash, observed_at=datetime.now(timezone.utc).isoformat(),
        kind='provider', outcome='returned' if response is not None else 'failed', model=model,
        prompt_tokens=prompt, completion_tokens=completion, cached_prompt_tokens=cached,
        uncached_prompt_tokens=uncached, provider_started_at=started_at.isoformat(),
        duration_ms=max(0, int((monotonic() - started) * 1000)),
        **cost_snapshot(model, started_at, cached, uncached, completion)))
