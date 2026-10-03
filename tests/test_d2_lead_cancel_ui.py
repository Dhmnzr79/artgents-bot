"""Cancel is visible only once lead collection reaches the phone slot."""
import pytest
from lead_interrupt import LEAD_CANCEL_REF, LEAD_PENDING_ANSWER_REF, LEAD_RESUME_REF
from session import mem_get, session_client_scope
from tests.test_d2_document_click_task_http import _body
from tests.test_d2_http_contract import FakeProvider, http_env, post, post_sse
from tests.test_d2_sim2_dialogues import raw, price


@pytest.mark.parametrize('transport', ['json', 'sse'])
@pytest.mark.parametrize('pause', [False, True])
def test_cancel_only_at_phone(http_env, transport, pause):
    client, _, use, _ = http_env
    fake = use(FakeProvider(raw({'kind': 'booking', 'request_id': 'r1', 'age_group': 'adult'})))
    send = post if transport == 'json' else post_sse
    def call(**args):
        response = send(client, **args)
        assert response.status_code == 200, response.get_data(as_text=True)
        return _body(response, transport)
    def refs(body):
        return {q['reply_id'] for q in body['ui']['quick_replies']}
    first = call(request_id='book', q='Хочу записаться')
    assert refs(first) == set()
    assert call(request_id='book', q='Хочу записаться') == first
    assert len(fake.inputs) == 1
    with session_client_scope('demo'):
        assert mem_get('cp6a')['lead_intent'] == 'collecting_name'
    if pause:
        pending = call(request_id='question', q='Сколько стоит имплантация?')
        fake.raw = raw(price('classic', 'service'))
        args = dict(request_id='answer', q='', ref=LEAD_PENDING_ANSWER_REF, ui_revision=pending['revision'])
        answer = call(**args)
        assert refs(answer) == {LEAD_RESUME_REF}
        assert call(**args) == answer
        with session_client_scope('demo'):
            state = mem_get('cp6a')
            assert state['lead_intent'] == 'paused'
            assert state['lead_resume_step'] == 'collecting_name'
        resumed = call(request_id='resume', q='', ref=LEAD_RESUME_REF, ui_revision=answer['revision'])
        assert refs(resumed) == set()
    phone = call(request_id='name', q='Анна')
    assert refs(phone) == {LEAD_CANCEL_REF}
    with session_client_scope('demo'):
        assert mem_get('cp6a')['lead_intent'] == 'collecting_phone'
        assert mem_get('cp6a')['profile']['name'] == 'Анна'
    args = dict(request_id='cancel', q='', ref=LEAD_CANCEL_REF, ui_revision=phone['revision'])
    cancelled = call(**args)
    assert call(**args) == cancelled
    assert LEAD_CANCEL_REF not in refs(cancelled)
    with session_client_scope('demo'):
        assert mem_get('cp6a')['lead_intent'] not in {'collecting_name', 'collecting_phone', 'paused'}
    assert len(fake.inputs) == (2 if pause else 1)

@pytest.mark.parametrize('transport', ['json', 'sse'])
def test_situation_intake_name_has_no_cancel(http_env, transport):
    client, _, use, _ = http_env
    fake = use(FakeProvider(raw({'kind': 'booking', 'request_id': 'r1', 'age_group': 'adult'})))
    send = post if transport == 'json' else post_sse
    _body(send(client, request_id='start', q='', situation_action='start'), transport)
    name = _body(send(client, request_id='description', q='Хочу обсудить восстановление зуба'), transport)
    assert name['ui']['quick_replies'] == []
    with session_client_scope('demo'):
        assert mem_get('cp6a')['lead_intent'] == 'collecting_name'
    phone = _body(send(client, request_id='name', q='Анна'), transport)
    assert {q['reply_id'] for q in phone['ui']['quick_replies']} == {LEAD_CANCEL_REF}
    assert len(fake.inputs) == 0
