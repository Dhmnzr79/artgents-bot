"""Current JSON/SSE quota integration with mocked provider; no network."""
import sqlite3
import time
import pytest
from core.d2_demo_limits import reserve_demo_call, demo_usage_path
from core.d2_live_provider import D2HttpProvider
from tests.test_d2_http_contract import http_env, post, post_sse, sse_events
from tests.test_d2_native_price_runtime import Transport, message, price
from tests.test_d2_price_cards import cards
from tests.d2_ci_http import send

VISITOR = "11111111-1111-1111-1111-111111111111"


def seed(count):
    for i in range(count):
        reserve_demo_call(sid="seed", request_id=str(i), visitor_id=VISITOR,
                          peer_ip="seed", client_id="demo", now=time.time())


def wire(monkeypatch, *replies, fail=False):
    import core.d2_http_adapter as adapter
    transport = Transport(*(replies or (message("Ответ по материалам клиники."),)))
    if fail: transport.replies = [RuntimeError("offline failure")]
    monkeypatch.setattr(adapter, "D2HttpProvider", lambda **kwargs: D2HttpProvider(transport=transport, **kwargs))
    return transport.calls


def denied(result, transport, code):
    if transport == "json":
        assert result.status_code == 429
        assert result.get_json() == {"error": code}
    else:
        events = dict(sse_events(result))
        assert events['error'] == {'error': code}
        assert 'ui' not in events and 'done' not in events


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_thirtieth_question_replay_free_catalog_click_and_new_sid_blocked(http_env, monkeypatch, transport):
    client, db, _, _ = http_env
    seed(29)
    calls = wire(monkeypatch, message(None, price(volume={'extent':'one_tooth'})), message('<NO_TEXT>'))
    args = dict(sid="test", request_id="last", visitor_id=VISITOR, q="Сколько стоит имплантация?")
    first = send(client, transport, **args)
    assert cards(first)[0]['price']['rows'][0]['amount'] == 76200
    assert send(client, transport, **args) == first
    assert len(calls) == 2
    result = (post if transport == 'json' else post_sse)(client, sid="new", request_id="denied", visitor_id=VISITOR, q="Какие гарантии?")
    denied(result, transport, "demo_visitor_limit")
    ref = 'price_select:classic.one_tooth.nobel'
    assert ref in {r['reply_id'] for r in first['ui']['quick_replies']}
    chosen = send(client, transport, sid="test", request_id="click", visitor_id=VISITOR,
                  q="", ref=ref, ui_revision=first['revision'])
    assert cards(chosen)[0]['price']['rows'][0]['amount'] == 101200
    assert len(calls) == 2
    with sqlite3.connect(demo_usage_path()) as conn:
        assert conn.execute('SELECT COUNT(*) FROM demo_usage_attempt').fetchone()[0] == 31
    with sqlite3.connect(db) as conn:
        assert not conn.execute("SELECT 1 FROM d2_turn_request WHERE request_id='denied'").fetchone()


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_failed_attempt_charged_and_dialogue_rollback(http_env, monkeypatch, transport):
    client, db, _, _ = http_env
    calls = wire(monkeypatch, fail=True)
    result = (post if transport == 'json' else post_sse)(client, request_id="failed", visitor_id=VISITOR)
    if transport == 'json': assert result.status_code == 503
    else: assert dict(sse_events(result))['error']['error'] == 'd2_turn_failed'
    assert len(calls) == 1
    with sqlite3.connect(demo_usage_path()) as conn:
        assert conn.execute('SELECT COUNT(*) FROM demo_usage_attempt').fetchone()[0] == 1
    with sqlite3.connect(db) as conn:
        assert not conn.execute("SELECT 1 FROM d2_turn_request WHERE request_id='failed'").fetchone()


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_shared_global_budget_blocks_before_provider(http_env, monkeypatch, transport):
    client, _, _, _ = http_env
    seed(1)
    with sqlite3.connect(demo_usage_path()) as conn:
        row = conn.execute('SELECT * FROM demo_usage_attempt').fetchone()
        other = ('demo_medical', *row[1:])
        conn.executemany('INSERT INTO demo_usage_attempt VALUES(?,?,?,?,?,?)', [other] * 3999)
    calls = wire(monkeypatch)
    denied((post if transport == 'json' else post_sse)(client, sid='fresh', request_id='blocked', visitor_id=VISITOR), transport, 'demo_daily_limit')
    assert calls == []


def test_demo_storage_path_is_independent_of_request_tenant(monkeypatch, tmp_path):
    import core.d2_demo_limits as limits
    monkeypatch.setattr(limits, 'dialogue_store_path', lambda tenant: tmp_path / tenant / 'dialogue.sqlite')
    for tenant in ('demo', 'demo_medical'):
        reserve_demo_call(client_id=tenant, sid=tenant, request_id='q', visitor_id=VISITOR, peer_ip='ip')
    assert not (tmp_path / 'demo_medical').exists()
    with sqlite3.connect(demo_usage_path()) as conn:
        assert conn.execute('SELECT COUNT(*) FROM demo_usage_attempt').fetchone()[0] == 2


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_limit_preserves_private_form_and_lead_submission(http_env, monkeypatch, transport):
    from copy import deepcopy
    from session import mem_get, session_client_scope
    from tests.test_d2_text_reply import response, action
    from tests.test_widget_booking_form import form_payload
    client, _, _, _ = http_env
    calls = wire(monkeypatch, message(response(actions=[action('start_booking', age_group='adult')])))
    opened = send(client, transport, request_id='book', visitor_id=VISITOR, q='Хочу записаться')
    assert opened['ui']['booking_form'] is True
    payload = form_payload(client, tenant='demo', sid='cp6a', name='Анна')
    seed(29)
    with session_client_scope('demo'):
        before = deepcopy(mem_get('cp6a'))
    denied((post if transport == 'json' else post_sse)(client, request_id='blocked', visitor_id=VISITOR, q='Какая цена?'), transport, 'demo_visitor_limit')
    with session_client_scope('demo'):
        assert mem_get('cp6a') == before
    submitted = client.post('/lead', json=payload)
    assert submitted.status_code == 200 and submitted.get_json()['status'] == 'demo_stub'
    assert client.post('/lead', json=payload).get_json() == submitted.get_json()
    assert len(calls) == 1


def test_non_demo_admission_is_unchanged(http_env, monkeypatch):
    client, _, _, _ = http_env
    seed(30)
    calls = wire(monkeypatch)
    result = send(client, client_id='nikadent', sid='other', request_id='other', visitor_id=VISITOR, q='Расскажите о клинике')
    assert result['client_id'] == 'nikadent' and len(calls) == 1
    with sqlite3.connect(demo_usage_path()) as conn:
        assert conn.execute('SELECT COUNT(*) FROM demo_usage_attempt').fetchone()[0] == 30
