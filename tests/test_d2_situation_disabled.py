"""Situation intake is dormant; ordinary Q&A and authorized leads stay active."""
from copy import deepcopy
import json

import pytest

from session import mem_get, session_client_scope, set_situation_pending, set_situation_note
from tests.test_d2_http_contract import FakeProvider, http_env, post, post_sse, sse_events
from tests.test_d2_document_click_task_http import _body
from tests.test_d2_sim2_dialogues import raw, explanation
from lead_interrupt import LEAD_PENDING_ANSWER_REF, LEAD_RESUME_REF
from core.d2_live_provider import build_d2_d1r_messages


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
    fake = use(FakeProvider(raw({'kind': 'booking', 'request_id': 'r1', 'age_group': 'adult'})))
    send = post if transport == 'json' else post_sse
    if active:
        _body(send(client, request_id='book', q='Хочу записаться'), transport)
        _body(send(client, request_id='name', q='Анна'), transport)
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
@pytest.mark.parametrize('slot', ['ordinary', 'name', 'phone'])
def test_historical_situation_flag_cannot_route_current_turn(http_env, transport, slot):
    client, _, use, _ = http_env
    fake = use(FakeProvider(raw({'kind': 'booking', 'request_id': 'r1', 'age_group': 'adult'})))
    send = post if transport == 'json' else post_sse
    if slot != 'ordinary':
        _body(send(client, request_id='book', q='Хочу записаться'), transport)
        if slot == 'phone':
            _body(send(client, request_id='name', q='Анна'), transport)
    with session_client_scope('demo'):
        set_situation_pending('cp6a', True)
        set_situation_note('cp6a', 'Старая заметка')
    fake.raw = raw(explanation('Пояснение по материалам клиники.'))
    question = 'Как проходит лечение? +79991234567' if slot == 'ordinary' else 'Александр' if slot == 'name' else '+79991234567'
    count = len(fake.inputs)
    args = dict(request_id='current', q=question)
    body = _body(send(client, **args), transport)
    assert _body(send(client, **args), transport) == body
    with session_client_scope('demo'):
        state = mem_get('cp6a')
        assert state['situation_pending'] is True
        assert state['situation_note'] == ('' if slot == 'phone' else 'Старая заметка')
        if slot == 'ordinary':
            assert state['lead_intent'] not in {'collecting_name', 'collecting_phone'}
            assert body['answer'] == 'Пояснение по материалам клиники.'
        elif slot == 'name':
            assert state['lead_intent'] == 'collecting_phone'
            assert state['profile']['name'] == 'Александр'
        else:
            assert 'заявка никуда не ушла' in body['answer']
    assert len(fake.inputs) == count + (1 if slot == 'ordinary' else 0)
    if slot == 'ordinary':
        prompt = json.dumps(build_d2_d1r_messages(fake.inputs[-1]), ensure_ascii=False)
        assert '79991234567' not in prompt
        assert 'Старая заметка' not in prompt


@pytest.mark.parametrize('transport', ['json', 'sse'])
def test_existing_booking_cta_still_requires_published_ui(http_env, transport):
    client, _, use, _ = http_env
    fake = use(FakeProvider(raw(explanation('Пояснение по материалам клиники.'))))
    send = post if transport == 'json' else post_sse
    answer = _body(send(client, request_id='answer', q='Как проходит лечение?'), transport)
    button = next(b for b in answer['ui']['buttons'] if b['action_kind'] == 'cta')
    rejected(send(client, request_id='forged', q='', ref='button:nonexistent',
                  ui_revision=answer['revision']), transport)
    with session_client_scope('demo'):
        assert mem_get('cp6a')['lead_intent'] != 'collecting_name'
    _body(send(client, request_id='click', q='', ref='button:' + button['button_id'],
               ui_revision=answer['revision']), transport)
    with session_client_scope('demo'):
        assert mem_get('cp6a')['lead_intent'] == 'collecting_name'
    assert len(fake.inputs) == 1


@pytest.mark.parametrize('transport', ['json', 'sse'])
def test_historical_situation_flag_does_not_interrupt_lead_pause(http_env, transport):
    client, _, use, _ = http_env
    fake = use(FakeProvider(raw({'kind': 'booking', 'request_id': 'r1', 'age_group': 'adult'})))
    send = post if transport == 'json' else post_sse
    _body(send(client, request_id='book', q='Хочу записаться'), transport)
    _body(send(client, request_id='name', q='Анна'), transport)
    pending = _body(send(client, request_id='question', q='Как проходит лечение?'), transport)
    fake.raw = raw(explanation('Пояснение по материалам клиники.'))
    paused = _body(send(client, request_id='answer', q='', ref=LEAD_PENDING_ANSWER_REF,
                        ui_revision=pending['revision']), transport)
    with session_client_scope('demo'):
        set_situation_pending('cp6a', True)
        before = deepcopy(mem_get('cp6a'))
        assert before['lead_intent'] == 'paused'
    resumed = _body(send(client, request_id='resume', q='', ref=LEAD_RESUME_REF,
                         ui_revision=paused['revision']), transport)
    with session_client_scope('demo'):
        state = mem_get('cp6a')
        assert state['lead_intent'] == 'collecting_phone'
        assert state['profile']['name'] == 'Анна'
        assert state['situation_pending'] is True
    assert {q['reply_id'] for q in resumed['ui']['quick_replies']} == {'lead:cancel'}
    assert len(fake.inputs) == 2
