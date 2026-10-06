"""Demo admission on actual HTTP provider with offline transport only."""
import sqlite3
from types import SimpleNamespace
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from core.d2_demo_limits import admit_demo_call, D2DemoLimitReached
from core.d2_live_provider import D2HttpProvider
from tests.test_d2_http_contract import http_env, post, post_sse, sse_events
from tests.test_d2_document_click_task_http import _body
from tests.test_d2_sim2_dialogues import raw, price, explanation


def wire(monkeypatch, payload=None, fail=False):
    import core.d2_http_adapter as adapter
    calls = []
    def transport(**kwargs):
        calls.append(kwargs)
        if fail:
            raise RuntimeError('offline transport failure')
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=payload or raw(explanation('Объяснение по материалам клиники.'))))], model='offline', usage=None)
    monkeypatch.setattr(adapter, 'D2HttpProvider', lambda **kwargs: D2HttpProvider(transport=transport, **kwargs))
    return calls


def seed(db, *, sid='other', count=1, peer='seed', stamp=None):
    with sqlite3.connect(db) as conn:
        admit_demo_call(conn, sid=sid, peer_ip=peer, now=time.time() if stamp is None else stamp)
        conn.executemany('INSERT INTO d2_demo_model_attempt VALUES(?,?,?)', [(sid, 'seed', time.time() if stamp is None else stamp)] * (count-1))


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
    calls = wire(monkeypatch, raw(price()))
    seed(db, sid='cp6a', count=9)
    send = post if transport == 'json' else post_sse
    first = _body(send(client, request_id='tenth', q='Сколько стоит имплантация?'), transport)
    assert len(calls) == 1
    assert _body(send(client, request_id='tenth', q='Сколько стоит имплантация?'), transport) == first
    limit(send(client, request_id='eleventh', q='А сроки?'), transport, 'demo_session_limit')
    with sqlite3.connect(db) as conn:
        assert conn.execute('SELECT COUNT(*) FROM d2_demo_model_attempt').fetchone()[0] == 10
        assert not conn.execute("SELECT 1 FROM d2_turn_request WHERE request_id='eleventh'").fetchone()
    clicked = _body(send(client, request_id='free', q='', ref='volume:implantation:one_tooth', ui_revision=first['revision']), transport)
    assert '76 200' in clicked['answer'].replace('\u00a0',' ')
    assert len(calls) == 1
    fresh = _body(send(client, sid='new-sid', request_id='new', q='Сколько стоит имплантация?'), transport)
    assert fresh['sid'] == 'new-sid' and len(calls) == 2


@pytest.mark.parametrize('transport', ['json', 'sse'])
@pytest.mark.parametrize('kind', ['daily', 'ip'])
def test_shared_limit_before_transport_and_other_tenant_unchanged(http_env, monkeypatch, transport, kind):
    client, db, _, _ = http_env
    calls = wire(monkeypatch)
    import core.d2_demo_limits as quota
    if kind == 'daily':
        seed(db, count=200)
    else:
        monkeypatch.setattr(quota, 'RATE_LIMIT_MAX_PER_IP', 1)
        seed(db, peer='127.0.0.1')
    send = post if transport == 'json' else post_sse
    limit(send(client, sid='fresh', request_id='blocked', q='Как проходит лечение?'), transport, 'demo_'+kind+'_limit')
    assert calls == []
    other = _body(send(client, client_id='nikadent', sid='fresh', request_id='other', q='Как проходит лечение?'), transport)
    assert other['client_id'] == 'nikadent' and len(calls) == 1
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
        for i in range(9): admit_demo_call(conn, sid='same', peer_ip='ip', now=0)
    def try_one(i):
        with sqlite3.connect(path) as conn:
            try: admit_demo_call(conn, sid='same', peer_ip='ip', now=90000)
            except D2DemoLimitReached as exc: return exc.code
            return 'admitted'
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(try_one, [1,2])) == ['admitted','demo_session_limit']
    with sqlite3.connect(path) as conn:
        admit_demo_call(conn, sid='fresh', peer_ip='ip', now=90000)
        assert conn.execute('SELECT COUNT(*) FROM d2_demo_model_attempt').fetchone()[0] == 11
        assert 'ip' not in [r[0] for r in conn.execute('SELECT peer_hash FROM d2_demo_model_attempt')]


def test_daily_and_ip_windows_expire_without_resetting_session(tmp_path, monkeypatch):
    import core.d2_demo_limits as quota
    path = tmp_path/'windows.sqlite'
    seed(path, count=200, stamp=0)
    with sqlite3.connect(path) as conn:
        with pytest.raises(D2DemoLimitReached, match='demo_daily_limit'):
            admit_demo_call(conn, sid='fresh', peer_ip='new', now=86399)
        admit_demo_call(conn, sid='fresh', peer_ip='new', now=86400)
        monkeypatch.setattr(quota, 'RATE_LIMIT_MAX_PER_IP', 1)
        with pytest.raises(D2DemoLimitReached, match='demo_ip_limit'):
            admit_demo_call(conn, sid='another', peer_ip='new', now=86459)
        admit_demo_call(conn, sid='another', peer_ip='new', now=86460)


@pytest.mark.parametrize('transport', ['json', 'sse'])
def test_quota_denial_preserves_named_lead_and_new_sid_does_not_inherit_it(http_env, monkeypatch, transport):
    from lead_interrupt import LEAD_PENDING_ANSWER_REF
    from session import mem_get, session_client_scope
    client, db, _, _ = http_env
    calls = wire(monkeypatch, raw({'kind': 'booking', 'request_id': 'r1', 'age_group': 'adult'}))
    send = post if transport == 'json' else post_sse
    _body(send(client, request_id='book', q='Хочу записаться'), transport)
    _body(send(client, request_id='name', q='Анна'), transport)
    pending = _body(send(client, request_id='question', q='Сколько стоит имплантация?'), transport)
    seed(db, sid='cp6a', count=9)
    with session_client_scope('demo'):
        before = mem_get('cp6a')
        assert before['profile']['name'] == 'Анна'
    limit(send(client, request_id='blocked', q='', ref=LEAD_PENDING_ANSWER_REF,
               ui_revision=pending['revision']), transport, 'demo_session_limit')
    with session_client_scope('demo'):
        assert mem_get('cp6a') == before
    assert len(calls) == 1
    _body(send(client, sid='new', request_id='fresh-book', q='Хочу записаться'), transport)
    with session_client_scope('demo'):
        assert mem_get('cp6a') == before
        assert not mem_get('new')['profile'].get('name')
