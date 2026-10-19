"""Private, read-only administration of the current D2 bot."""
from datetime import datetime, timedelta, timezone
import hmac
import ipaddress
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv(Path(__file__).resolve().parents[1] / '.env')

from admin_dashboard import repository
from core.client_config_loader import admin_client_options

APP_ENV = (os.getenv('APP_ENV') or 'local').strip().lower()
ADMIN_TOKEN = (os.getenv('ADMIN_DASHBOARD_TOKEN') or '').strip()
PORT = int(os.getenv('ADMIN_DASHBOARD_PORT', '9100'))
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 1024


def _overview_period_bounds(raw=None):
    key = raw if raw in {'today', 'week', 'month'} else 'today'
    days = {'today': 1, 'week': 7, 'month': 30}[key]
    now = datetime.now(timezone.utc)
    end = datetime(now.year, now.month, now.day, tzinfo=timezone.utc) + timedelta(days=1)
    return end - timedelta(days=days), end, key, {'today': 'сегодня', 'week': '7 дней', 'month': '30 дней'}[key]


def _loopback(value):
    try:
        return value == 'localhost' or ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


@app.before_request
def _guard():
    if APP_ENV == 'local':
        host = urlsplit('http://' + request.host).hostname or ''
        if not _loopback(request.remote_addr or '') or not _loopback(host):
            return jsonify(error='local_access_only'), 403
        origin = request.headers.get('Origin')
        if origin and origin != request.host_url.rstrip('/'):
            return jsonify(error='origin_forbidden'), 403
    elif APP_ENV in {'prod', 'production'}:
        if not ADMIN_TOKEN:
            return jsonify(error='dashboard_token_not_set'), 503
        token = request.headers.get('X-Admin-Dashboard-Token', '')
        if not hmac.compare_digest(token.encode(), ADMIN_TOKEN.encode()):
            return jsonify(error='not_found'), 404
    else:
        return jsonify(error='dashboard_environment_invalid'), 503


@app.after_request
def _private_headers(response):
    response.headers.update({
        'Cache-Control': 'no-store, private', 'Pragma': 'no-cache', 'Expires': '0',
        'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer',
        'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'",
    })
    return response


def _client():
    cid = request.args.get('client_id', '')
    if cid not in {item['client_id'] for item in admin_client_options()}:
        raise ValueError('unknown_client')
    return cid


def _paging():
    limit = int(request.args.get('limit', '20'))
    cursor = request.args.get('cursor')
    cursor = int(cursor) if cursor is not None else None
    if not 1 <= limit <= 100 or (cursor is not None and not 1 <= cursor <= 2**63 - 1):
        raise ValueError('pagination_invalid')
    return limit, cursor


@app.errorhandler(ValueError)
def _bad_request(_exc):
    return jsonify(error='invalid_request'), 400


@app.errorhandler(repository.StorageUnavailable)
def _storage_error(_exc):
    return jsonify(error='d2_storage_unavailable'), 503


@app.get('/')
def home():
    return render_template('index.html', app_env=APP_ENV)


@app.get('/api/health')
def api_health():
    clients = admin_client_options()
    storage = {item['client_id']: repository.health(item['client_id']) for item in clients}
    return jsonify(ok=True, architecture='D2', read_only=True, storage=storage)


@app.get('/api/clients')
def api_clients():
    return jsonify(items=admin_client_options())


@app.get('/api/overview')
def api_overview():
    cid = _client()
    start, end, period, label = _overview_period_bounds(request.args.get('period'))
    return jsonify(client_id=cid, period=period, period_label=label,
                   **repository.overview(cid, start.isoformat(), end.isoformat()))


@app.get('/api/dialogs')
def api_dialogs():
    cid = _client()
    limit, cursor = _paging()
    return jsonify(client_id=cid, **repository.dialogs(cid, limit, cursor))


@app.get('/api/dialogs/<session_id>/thread')
def api_thread(session_id):
    cid = _client()
    if not re.fullmatch('[a-f0-9]{64}', session_id):
        raise ValueError('session_id_invalid')
    limit, cursor = _paging()
    result = repository.thread(cid, session_id, limit, cursor)
    if result is None:
        return jsonify(error='not_found'), 404
    return jsonify(client_id=cid, **result)


@app.get('/api/leads')
def api_leads():
    cid = _client()
    limit, cursor = _paging()
    return jsonify(client_id=cid, **repository.leads(cid, limit, cursor))


@app.get('/api/costs')
def api_costs():
    cid = _client()
    start, end, *_ = _overview_period_bounds(request.args.get('period'))
    return jsonify(client_id=cid, **repository.costs(cid, start.isoformat(), end.isoformat()))


@app.get('/api/funnel')
def api_funnel():
    cid = _client()
    start, end, *_ = _overview_period_bounds(request.args.get('period'))
    return jsonify(client_id=cid, **repository.funnel(cid, start.isoformat(), end.isoformat()))


@app.get('/api/events')
@app.get('/api/problems')
def api_observations():
    cid = _client()
    limit, cursor = _paging()
    start, end, *_ = _overview_period_bounds(request.args.get('period'))
    return jsonify(client_id=cid, **repository.observations(cid, start.isoformat(), end.isoformat(),
                   limit, cursor, failures_only=request.path == '/api/problems'))


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=PORT, debug=False, use_reloader=False)
