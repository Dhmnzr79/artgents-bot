"""Demo admission on actual HTTP provider with offline transport only."""
from tests.d2_ci_http import bind_copied_tenant
import sqlite3
import shutil
from copy import deepcopy
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from core.d2_demo_limits import admit_demo_call, D2DemoLimitReached
from core.d2_live_provider import D2HttpProvider
from tests.test_d2_http_contract import http_env, post, post_sse, sse_events
from tests.test_d2_native_price_runtime import Transport, message, price
from tests.test_d2_text_reply import response, action
from tests.test_d2_price_cards import cards
from tests.test_widget_booking_form import form_payload


def wire(monkeypatch, *replies, fail=False):
    import core.d2_http_adapter as adapter
    transport = Transport(*(replies or (message('Объяснение по материалам клиники.'),)))
    if fail:
        transport.replies = [RuntimeError('offline transport failure')]
    monkeypatch.setattr(adapter, 'D2HttpProvider', lambda **kwargs: D2HttpProvider(transport=transport, **kwargs))
    return transport.calls


def _body(response, transport):
    assert response.status_code == 200, response.get_data(as_text=True)
    if transport == 'json':
        body = response.get_json()
    else:
        events = dict(sse_events(response))
        assert 'error' not in events and 'done' in events, events
        body = events['ui']
    assert body['revision'] > 0 and isinstance(body['ui'], dict)
    return body


def seed(db, *, sid='other', count=1, peer='seed', stamp=None):
    with sqlite3.connect(db) as conn:
        admit_demo_call(conn, sid=sid, peer_ip=peer, now=time.time() if stamp is None else stamp)
        conn.executemany('INSERT INTO d2_demo_model_attempt (sid,peer_hash,admitted_at,client_id) VALUES(?,?,?,?)', [(sid, 'seed', time.time() if stamp is None else stamp, 'demo')] * (count-1))


def limit(response, transport, code):
    if transport == 'json':
        assert response.status_code == 429
        assert response.get_json() == {'error': code}
    else:
        events = dict(sse_events(response))
        assert events['error'] == {'error': code}
        assert 'ui' not in events and 'done' not in events


@pytest.mark.parametrize('transport', ['json', 'sse'])
def test_session_limit_replay_free_click_and_explicit_new_sid(http_env, monkeypatch, transport):
    client, db, _, _ = http_env
    native = price(volume={'extent': 'one_tooth'})
    calls = wire(monkeypatch, message(None, native), message(None, native))
    seed(db, sid='cp6a', count=29)
    send = post if transport == 'json' else post_sse
    args = dict(request_id='thirtieth', q='Сколько стоит имплантация?')
    first = _body(send(client, **args), transport)
    row = cards(first)[0]['price']['rows'][0]
    assert row['offer_id'] == 'classic.one_tooth.implantium'
    assert row['amount'] == 76200
    assert len(calls) == 1  # A successful card consumes only its actual first call.
    assert _body(send(client, **args), transport) == first
    limit(send(client, request_id='thirty-first', q='А сроки?'), transport, 'demo_session_limit')
    with sqlite3.connect(db) as conn:
        assert conn.execute('SELECT COUNT(*) FROM d2_demo_model_attempt').fetchone()[0] == 30
        assert not conn.execute("SELECT 1 FROM d2_turn_request WHERE request_id='thirty-first'").fetchone()
    ref = 'price_select:classic.one_tooth.nobel'
    assert ref in {q['reply_id'] for q in first['ui']['quick_replies']}
    clicked = _body(send(client, request_id='free', q='', ref=ref, ui_revision=first['revision']), transport)
    selected = cards(clicked)[0]['price']['rows'][0]
    assert selected['offer_id'] == 'classic.one_tooth.nobel'
    assert selected['amount'] == 101200
    assert len(calls) == 1
    fresh = _body(send(client, sid='new-sid', request_id='new', q='Сколько стоит имплантация?'), transport)
    assert fresh['sid'] == 'new-sid' and len(calls) == 2
    assert cards(fresh)[0]['price']['rows'][0]['offer_id'] == 'classic.one_tooth.implantium'



@pytest.mark.parametrize('transport', ['json', 'sse'])
@pytest.mark.parametrize('kind', ['daily', 'ip'])
def test_shared_limit_before_transport_and_other_tenant_unchanged(http_env, monkeypatch, transport, kind):
    client, db, _, tmp = http_env
    shutil.copytree(tmp / 'clients/demo', tmp / 'clients/secondary')
    bind_copied_tenant(tmp / 'clients/secondary', 'secondary')
    import config
    monkeypatch.setattr(config, 'ALLOWED_CLIENTS', frozenset({'demo', 'secondary'}))
    calls = wire(monkeypatch)
    import core.d2_demo_limits as quota
    if kind == 'daily':
        seed(db, count=400)
    else:
        monkeypatch.setattr(quota, 'RATE_LIMIT_MAX_PER_IP', 1)
        seed(db, peer='127.0.0.1')
    send = post if transport == 'json' else post_sse
    limit(send(client, sid='fresh', request_id='blocked', q='Как проходит лечение?'), transport, 'demo_'+kind+'_limit')
    assert calls == []
    other = _body(send(client, client_id='secondary', sid='fresh', request_id='other', q='Как проходит лечение?'), transport)
    assert other['client_id'] == 'secondary' and len(calls) == 1
    with sqlite3.connect(db) as conn:
        assert not conn.execute("SELECT 1 FROM d2_turn_request WHERE request_id='blocked'").fetchone()


@pytest.mark.parametrize('transport', ['json', 'sse'])
def test_failed_provider_attempt_is_charged_and_reservation_released(http_env, monkeypatch, transport):
    client, db, _, _ = http_env
    calls = wire(monkeypatch, fail=True)
    response = (post if transport == 'json' else post_sse)(client, request_id='failed', q='Как проходит лечение?')
    if transport == 'json':
        assert response.status_code == 503
    else:
        assert dict(sse_events(response))['error']['error'] == 'd2_turn_failed'
    assert len(calls) == 1
    with sqlite3.connect(db) as conn:
        assert conn.execute('SELECT COUNT(*) FROM d2_demo_model_attempt').fetchone()[0] == 1
        assert not conn.execute("SELECT 1 FROM d2_turn_request WHERE request_id='failed'").fetchone()


def test_counters_persist_and_rolling_window_and_concurrency(tmp_path):
    path=tmp_path/'quota.sqlite'
    with sqlite3.connect(path) as conn:
        for i in range(29): admit_demo_call(conn, sid='same', peer_ip='ip', now=0)
    def try_one(i):
        with sqlite3.connect(path) as conn:
            try: admit_demo_call(conn, sid='same', peer_ip='ip', now=90000)
            except D2DemoLimitReached as exc: return exc.code
            return 'admitted'
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(try_one, [1,2])) == ['admitted','demo_session_limit']
    with sqlite3.connect(path) as conn:
        admit_demo_call(conn, sid='fresh', peer_ip='ip', now=90000)
        assert conn.execute('SELECT COUNT(*) FROM d2_demo_model_attempt').fetchone()[0] == 31
        assert 'ip' not in [r[0] for r in conn.execute('SELECT peer_hash FROM d2_demo_model_attempt')]


def test_daily_and_ip_windows_expire_without_resetting_session(tmp_path, monkeypatch):
    import core.d2_demo_limits as quota
    path = tmp_path/'windows.sqlite'
    seed(path, count=400, stamp=0)
    with sqlite3.connect(path) as conn:
        with pytest.raises(D2DemoLimitReached, match='demo_daily_limit'):
            admit_demo_call(conn, sid='fresh', peer_ip='new', now=86399)
        admit_demo_call(conn, sid='fresh', peer_ip='new', now=86400)
        monkeypatch.setattr(quota, 'RATE_LIMIT_MAX_PER_IP', 1)
        with pytest.raises(D2DemoLimitReached, match='demo_ip_limit'):
            admit_demo_call(conn, sid='another', peer_ip='new', now=86459)
        admit_demo_call(conn, sid='another', peer_ip='new', now=86460)


@pytest.mark.parametrize('transport', ['json', 'sse'])
def test_quota_denial_preserves_private_form_and_new_sid_is_independent(http_env, monkeypatch, transport):
    from session import mem_get, session_client_scope
    client, db, _, _ = http_env
    calls = wire(monkeypatch, message(response(actions=[action('start_booking', age_group='adult')])),
                 message(response(actions=[action('start_booking', age_group='adult')])))
    send = post if transport == 'json' else post_sse
    opened = _body(send(client, request_id='book', q='Хочу записаться'), transport)
    assert opened['ui']['booking_form'] is True
    payload = form_payload(client, tenant='demo', sid='cp6a', name='Анна')
    seed(db, sid='cp6a', count=29)
    with session_client_scope('demo'):
        before = deepcopy(mem_get('cp6a'))
        assert before['lead_intent'] == 'none'
    limit(send(client, request_id='blocked', q='Сколько стоит имплантация?'), transport, 'demo_session_limit')
    with session_client_scope('demo'):
        assert mem_get('cp6a') == before
    assert len(calls) == 1
    submitted = client.post('/lead', json=payload)
    assert submitted.status_code == 200 and submitted.get_json()['status'] == 'demo_stub'
    assert client.post('/lead', json=payload).get_json() == submitted.get_json()
    fresh = _body(send(client, sid='new', request_id='fresh-book', q='Хочу записаться'), transport)
    assert fresh['ui']['booking_form'] is True
    with session_client_scope('demo'):
        assert mem_get('cp6a') == before
        assert mem_get('new')['lead_intent'] == 'none'
        assert not mem_get('new')['profile'].get('name')
    assert len(calls) == 2
