"""Situation intake is dormant; ordinary Q&A and authorized leads stay active."""
from copy import deepcopy
import json

import pytest

from session import mem_get, session_client_scope, set_situation_pending, set_situation_note
from tests.test_d2_http_contract import FakeProvider, http_env, post, post_sse, sse_events
from lead_interrupt import LEAD_PENDING_ANSWER_REF, LEAD_RESUME_REF
from core.d2_live_provider import build_d2_d1r_messages
from tests.test_widget_booking_form import form_payload


def booking_reply():
    return '\n<D2_META>\n' + json.dumps({'actions': [
        {'name': 'start_booking', 'arguments': {'age_group': 'adult'}}
    ]}) + '\n</D2_META>'


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


def assert_lead_step(step):
    with session_client_scope('demo'):
        assert mem_get('cp6a')['lead_intent'] == step


def rejected(response, transport):
    if transport == 'json':
        assert response.status_code == 400
        assert response.get_json() == {'error': 'd2_invalid_turn'}
    else:
        events = dict(sse_events(response))
        assert events['error'] == {'error': 'd2_invalid_turn'}
        assert 'ui' not in events and 'done' not in events


@pytest.mark.parametrize('transport', ['json', 'sse'])
@pytest.mark.parametrize('action', ['start', 'back'])
@pytest.mark.parametrize('active', [False, True])
def test_obsolete_command_cannot_change_lead_or_call_model(http_env, transport, action, active):
    client, db, use, _ = http_env
    fake = use(FakeProvider(booking_reply()))
    send = post if transport == 'json' else post_sse
    if active:
        booking = _body(send(client, request_id='book', q='Хочу записаться'), transport)
        assert booking['ui']['booking_form'] is True
        assert_lead_step('none')
    with session_client_scope('demo'):
        before = deepcopy(mem_get('cp6a'))
    count = len(fake.inputs)
    rejected(send(client, request_id='obsolete', q='', situation_action=action), transport)
    with session_client_scope('demo'):
        assert mem_get('cp6a') == before
    assert len(fake.inputs) == count
    if not active:
        assert not db.exists()


@pytest.mark.parametrize('transport', ['json', 'sse'])
@pytest.mark.parametrize('slot', ['ordinary', 'form_open', 'form_submitted'])
def test_historical_situation_flag_cannot_route_current_turn(http_env, transport, slot):
    client, _, use, _ = http_env
    fake = use(FakeProvider(booking_reply()))
    send = post if transport == 'json' else post_sse
    if slot != 'ordinary':
        opened = _body(send(client, request_id='book', q='Хочу записаться'), transport)
        assert opened['ui']['booking_form'] is True
        assert_lead_step('none')
        if slot == 'form_submitted':
            payload = form_payload(client, tenant='demo', sid='cp6a')
            submitted = client.post('/lead', json=payload)
            assert submitted.status_code == 200 and submitted.get_json()['status'] == 'demo_stub'
    with session_client_scope('demo'):
        set_situation_pending('cp6a', True)
        set_situation_note('cp6a', 'Старая заметка')
    fake.raw = 'Пояснение по материалам клиники.'
    count = len(fake.inputs)
    args = dict(request_id='current', q='Как проходит лечение? +79991234567')
    body = _body(send(client, **args), transport)
    assert _body(send(client, **args), transport) == body
    assert body['answer'] == fake.raw
    with session_client_scope('demo'):
        state = mem_get('cp6a')
        assert state['situation_pending'] is True
        assert state['situation_note'] == 'Старая заметка'
        assert state['lead_intent'] == 'none'
        assert not state['profile'].get('name') and not state['profile'].get('phone')
    assert len(fake.inputs) == count + 1
    prompt = json.dumps(build_d2_d1r_messages(fake.inputs[-1]), ensure_ascii=False)
    assert '79991234567' not in prompt and 'Старая заметка' not in prompt
    assert 'Тестовое Имя Формы' not in prompt and 'Позвонить вечером' not in prompt


@pytest.mark.parametrize('transport', ['json', 'sse'])
def test_existing_booking_cta_still_requires_published_ui(http_env, transport):
    client, _, use, _ = http_env
    fake = use(FakeProvider('Пояснение по материалам клиники.'))
    send = post if transport == 'json' else post_sse
    answer = _body(send(client, request_id='answer', q='Как проходит лечение?'), transport)
    button = next(b for b in answer['ui']['buttons'] if b['action_kind'] == 'cta')
    rejected(send(client, request_id='forged', q='', ref='button:nonexistent',
                  ui_revision=answer['revision']), transport)
    with session_client_scope('demo'):
        assert mem_get('cp6a')['lead_intent'] != 'collecting_name'
    opened = _body(send(client, request_id='click', q='', ref='button:' + button['button_id'],
               ui_revision=answer['revision']), transport)
    with session_client_scope('demo'):
        assert mem_get('cp6a')['lead_intent'] == 'none'
    assert opened['ui']['booking_form'] is True
    assert not opened['ui']['quick_replies']
    assert len(fake.inputs) == 1


@pytest.mark.parametrize('transport', ['json', 'sse'])
def test_historical_situation_flag_does_not_restore_retired_lead_commands(http_env, transport):
    client, _, use, _ = http_env
    fake = use(FakeProvider(booking_reply()))
    send = post if transport == 'json' else post_sse
    opened = _body(send(client, request_id='book', q='Хочу записаться'), transport)
    assert opened['ui']['booking_form'] is True
    assert_lead_step('none')
    with session_client_scope('demo'):
        set_situation_pending('cp6a', True)
        before = deepcopy(mem_get('cp6a'))
    for index, ref in enumerate((LEAD_PENDING_ANSWER_REF, LEAD_RESUME_REF)):
        rejected(send(client, request_id=f'old-{index}', q='', ref=ref,
                      ui_revision=opened['revision']), transport)
        with session_client_scope('demo'):
            assert mem_get('cp6a') == before
    fake.raw = 'Пояснение по материалам клиники.'
    answered = _body(send(client, request_id='question', q='Как проходит лечение?'), transport)
    assert answered['answer'] == fake.raw and len(fake.inputs) == 2
    with session_client_scope('demo'):
        assert mem_get('cp6a')['lead_intent'] == 'none'
        assert mem_get('cp6a')['situation_pending'] is True
