"""Single Caddy hop: actual HTTP endpoints, offline provider and quota."""
from pathlib import Path
import os

import pytest
from flask import Flask, request
from werkzeug.middleware.proxy_fix import ProxyFix

from tests.test_d2_http_contract import http_env, sse_events
from tests.test_d2_demo_limits import wire


@pytest.mark.parametrize('route', ['/ask', '/ask/stream'])
@pytest.mark.parametrize('trusted', [False, True])
def test_client_ip_quota_through_single_proxy(http_env, monkeypatch, route, trusted):
    client, _, _, _ = http_env
    import app
    import core.d2_demo_limits as quota
    original = app.app.wsgi_app
    # App import is shared: explicitly exercise both startup configurations.
    while isinstance(original, ProxyFix):
        original = original.app
    middleware = ProxyFix(original, x_for=1, x_proto=0, x_host=0,
                          x_port=0, x_prefix=0) if trusted else original
    monkeypatch.setattr(app.app, 'wsgi_app', middleware)
    monkeypatch.setattr(quota, 'RATE_LIMIT_MAX_PER_IP', 1)
    calls = wire(monkeypatch)

    def send(sid, ip):
        return client.post(route, json={'sid': sid, 'request_id': sid,
            'client_id': 'demo', 'q': 'Как проходит лечение?'},
            headers={'X-Forwarded-For': ip},
            environ_overrides={'REMOTE_ADDR': '172.20.0.2'}, buffered=True)

    def blocked(response):
        if route == '/ask':
            return response.status_code == 429 and response.get_json() == {'error': 'demo_ip_limit'}
        return dict(sse_events(response)).get('error') == {'error': 'demo_ip_limit'}

    assert not blocked(send('first', '203.0.113.10'))
    # Distinct clients no longer share the Caddy IP bucket when enabled.
    assert blocked(send('second', '203.0.113.11')) is (not trusted)
    # A new session does not bypass the same visitor's IP bucket.
    assert blocked(send('third', '203.0.113.10'))
    assert len(calls) == (2 if trusted else 1)


def test_deployment_enables_only_ip_trust_and_overwrites_client_header():
    root = Path(__file__).resolve().parents[1]
    source = (root / 'app.py').read_text(encoding='utf-8')
    assert 'os.getenv("BOT_TRUST_CADDY_IP", "0") == "1"' in source
    assert 'x_for=1, x_proto=0, x_host=0, x_port=0, x_prefix=0' in source
    compose = (root / 'deploy/production/compose.yml').read_text(encoding='utf-8')
    assert 'BOT_TRUST_CADDY_IP: "1"' in compose.split('  bot:', 1)[1].split('  admin:', 1)[0]
    caddy = (root / 'deploy/production/Caddyfile').read_text(encoding='utf-8')
    assert caddy.count('header_up X-Forwarded-For {http.request.remote.host}') == 2


@pytest.mark.parametrize('enabled', ['0', '1'])
def test_actual_startup_switch_and_only_last_ip_is_trusted(monkeypatch, enabled):
    monkeypatch.setenv('BOT_TRUST_CADDY_IP', enabled)
    root = Path(__file__).resolve().parents[1]
    source = (root / 'app.py').read_text(encoding='utf-8')
    startup = source.split('app = Flask(', 1)[1].split('logger =', 1)[0]
    namespace = {'Flask': Flask, '__name__': __name__, 'os': os, 'ProxyFix': ProxyFix}
    exec('app = Flask(' + startup, namespace)
    test_app = namespace['app']
    @test_app.get('/')
    def address():
        return {'ip': request.remote_addr, 'host': request.host, 'scheme': request.scheme}
    response = test_app.test_client().get('/', headers={
        'X-Forwarded-For': '198.51.100.99, 203.0.113.10',
        'X-Forwarded-Host': 'forged.example', 'X-Forwarded-Proto': 'https'},
        environ_overrides={'REMOTE_ADDR': '172.20.0.2'})
    assert response.get_json() == {
        'ip': '203.0.113.10' if enabled == '1' else '172.20.0.2',
        'host': 'localhost', 'scheme': 'http'}
