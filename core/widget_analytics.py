"""Best-effort, text-free page funnel. Owns no dialogue or delivery decisions."""
from collections import OrderedDict
from contextlib import closing
from datetime import datetime, timedelta, timezone
import os
import re
import sqlite3
from threading import Lock
from time import monotonic
from uuid import UUID
from urllib.parse import urlsplit

from core.client_config_loader import load_widget_presentation_v1
from core.d2_admin_metrics import identity_hash
from core.d2_storage import dialogue_store_path

KINDS = ('opened', 'question', 'form', 'submit')
_buckets = OrderedDict()
_lock = Lock()


def analytics_path(client_id):
    return dialogue_store_path(client_id).with_name('widget_analytics.sqlite')


def admit(client_id, peer):
    """Bound anonymous endpoint traffic without consuming dialogue/lead quotas."""
    key = (client_id, identity_hash(peer or 'unknown'))
    now = monotonic()
    with _lock:
        start, count = _buckets.pop(key, (now, 0))
        if now - start >= 60:
            start, count = now, 0
        _buckets[key] = (start, count + 1)
        while len(_buckets) > 4096:
            _buckets.popitem(last=False)
        return count < 120


def _uuid(value):
    if not isinstance(value, str) or len(value) > 36:
        raise ValueError('invalid_event')
    return str(UUID(value))


def event_values(client_id, data, origin):
    if not isinstance(data, dict) or set(data) - {'client_id', 'view_id', 'kind', 'path', 'sid', 'request_id'}:
        raise ValueError('invalid_event')
    kind = data.get('kind')
    if kind not in KINDS:
        raise ValueError('invalid_event')
    view = _uuid(data.get('view_id'))
    path = data.get('path')
    if not isinstance(path, str) or len(path) > 1024:
        raise ValueError('invalid_event')
    # Only configured public routes can enter storage, never arbitrary URL data.
    path = path.split('?', 1)[0].split('#', 1)[0].rstrip('/') or '/'
    presentation = load_widget_presentation_v1(client_id)
    routes = {'/'} | {p.rstrip('/') or '/' for menu in presentation.get('pageMenus', []) for p in menu['paths']}
    path = path if path in routes else '(other)'
    domain = urlsplit(origin).hostname
    if not domain or len(domain) > 253 or not re.fullmatch(r'[a-zA-Z0-9.:-]+', domain):
        raise ValueError('invalid_event')
    sid = request_id = None
    if kind == 'submit':
        _uuid(data.get('sid'))
        _uuid(data.get('request_id'))
        sid, request_id = data['sid'], data['request_id']
    elif 'sid' in data or 'request_id' in data:
        raise ValueError('invalid_event')
    return dict(view_hash=identity_hash(view), kind=kind, domain=domain.lower(), path=path,
                sid_hash=identity_hash(sid) if sid else None,
                request_hash=identity_hash(request_id) if request_id else None)


def record(client_id, values):
    """Failure must never change the widget or create a canonical D2 database."""
    if os.getenv('D2_ADMIN_METRICS_ENABLED', '1') != '1':
        return
    try:
        path = analytics_path(client_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(path, timeout=.05)) as conn, conn:
            conn.execute('BEGIN IMMEDIATE')
            conn.execute('''CREATE TABLE IF NOT EXISTS widget_event (
                client_id TEXT NOT NULL, view_hash TEXT NOT NULL, kind TEXT NOT NULL,
                domain TEXT NOT NULL, path TEXT NOT NULL, observed_at TEXT NOT NULL,
                sid_hash TEXT, request_hash TEXT NOT NULL,
                PRIMARY KEY(client_id,view_hash,kind,request_hash))''')
            conn.execute('CREATE INDEX IF NOT EXISTS widget_event_time ON widget_event(client_id,observed_at)')
            first = conn.execute('SELECT domain,path FROM widget_event WHERE client_id=? AND view_hash=? LIMIT 1',
                                 (client_id, values['view_hash'])).fetchone()
            conn.execute('INSERT OR IGNORE INTO widget_event VALUES (?,?,?,?,?,?,?,?)',
                (client_id, values['view_hash'], values['kind'], first[0] if first else values['domain'], first[1] if first else values['path'],
                 datetime.now(timezone.utc).isoformat(), values['sid_hash'], values['request_hash'] or ''))
            cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
            conn.execute('DELETE FROM widget_event WHERE client_id=? AND observed_at<?', (client_id, cutoff))
    except Exception:
        pass
