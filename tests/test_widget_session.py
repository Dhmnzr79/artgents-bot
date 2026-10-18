"""History remount reads own frozen public completions, independent of form/TTL."""
import json
from datetime import timedelta
from uuid import uuid4
from unittest.mock import Mock
import pytest
from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from core.d2_live_provider import D2HttpProvider
from tests.d2_ci_http import http_env,send,click
from tests.test_d2_native_price_runtime import Transport,message,price
from tests.test_widget_booking_form import form_payload


def history(client,sid,tenant='demo',**fields):
    return client.post('/api/widget-session',json=dict(client_id=tenant,sid=sid,**fields))


def test_full_public_history_larger_than_model_window_and_private_submit(http_env,monkeypatch):
    client,db,use,_=http_env;sid=uuid4().hex
    wire=Transport(*(message(f'Ответ номер {i}.') for i in range(5)));use(D2HttpProvider(transport=wire))
    for index in range(5):send(client,sid=sid,request_id=f'r{index}',q=f'Вопрос номер {index}')
    key=SessionKey(client_id='demo',sid=sid)
    with D2DialogueStore(db)as store:before=store.read(key);assert len(before.state.dialogue_pairs)<=3
    assert client.post('/lead',json=form_payload(client,tenant='demo',sid=sid)).get_json()['ok']
    result=history(client,sid)
    assert result.status_code==200 and result.headers['Cache-Control']=='no-store'
    data=result.get_json();assert len(data['entries'])==5
    assert [e['patient_text'] for e in data['entries']]==[f'Вопрос номер {i}' for i in range(5)]
    assert data['current']['revision']==5 and data['actions_current']
    assert 'Тестовое Имя Формы' not in result.get_data(as_text=True) and '79991234567' not in result.get_data(as_text=True)
    with D2DialogueStore(db)as store:assert store.read(key)==before
    assert len(wire.calls)==5


def test_saved_price_click_and_no_rematerialization(http_env):
    client,db,use,tmp=http_env;sid=uuid4().hex
    wire=Transport(message(None,price()),message('<NO_TEXT>'));use(D2HttpProvider(transport=wire))
    first=send(client,sid=sid,request_id='first')
    selected=click(client,first,'price_select:classic.one_tooth.nobel',sid=sid,request_id='select')
    # An unrelated current catalog edit must not rewrite a saved publication.
    path=tmp/'clients/demo/target_response/pricebook/services/classic.one_tooth.nobel.json'
    data=json.loads(path.read_text(encoding='utf-8'));data['price']['amount']=1;path.write_text(json.dumps(data),encoding='utf-8')
    restored=history(client,sid).get_json()
    assert restored['entries'][-1]['selected_ref']=='price_select:classic.one_tooth.nobel'
    assert restored['entries'][-1]['source_revision']==first['revision']
    assert restored['current']['ui']==selected['ui']
    assert '101' in restored['current']['answer']
    assert len(wire.calls)==2


def test_expired_history_does_not_refresh_ttl_or_authorize_actions(http_env):
    client,db,use,_=http_env;sid=uuid4().hex
    wire=Transport(message('Ответ.'));use(D2HttpProvider(transport=wire));send(client,sid=sid)
    key=SessionKey(client_id='demo',sid=sid)
    with D2DialogueStore(db)as store:
        record=store.read(key);record=record.model_copy(update={'activity':record.activity.model_copy(update={'last_user_turn_at':record.activity.last_user_turn_at-timedelta(days=10)})})
        with store._connection:store._connection.execute('UPDATE d2_dialogue SET payload=? WHERE client_id=? AND sid=?',(record.model_dump_json(),'demo',sid))
    data=history(client,sid).get_json();assert len(data['entries'])==1 and not data['actions_current']
    with D2DialogueStore(db)as store:assert store.read(key)==record


def test_restore_masks_free_prose_phone_and_email_but_preserves_prices(http_env):
    client,_,use,_=http_env;sid=uuid4().hex
    wire=Transport(message('Личный номер +79995556677 и abc@example.org.'));use(D2HttpProvider(transport=wire));send(client,sid=sid)
    data=history(client,sid).get_json()
    serialized=json.dumps(data)
    assert '79995556677' not in serialized and 'abc@example.org' not in serialized


def test_other_tenant_empty_unknown_sid_and_strict_sid(http_env):
    client,_,use,_=http_env;sid=uuid4().hex
    wire=Transport(message('Только этой клинике.'));use(D2HttpProvider(transport=wire));send(client,sid=sid)
    assert history(client,sid,tenant='nikadent').get_json()['entries']==[]
    assert history(client,uuid4().hex).get_json()['entries']==[]
    assert history(client,'predictable').status_code==400
    assert history(client,sid,tenant='unknown').status_code==403


def test_corrupt_receipt_is_an_error_without_new_session_or_cleanup(http_env):
    client,db,use,_=http_env;sid=uuid4().hex
    wire=Transport(message('Сохранённый ответ.'));use(D2HttpProvider(transport=wire));send(client,sid=sid)
    with D2DialogueStore(db)as store:
        with store._connection:store._connection.execute("UPDATE d2_turn_request SET payload='{}' WHERE client_id=? AND sid=?",('demo',sid))
    assert history(client,sid).status_code==400
    with D2DialogueStore(db)as store:assert store._connection.execute('SELECT payload FROM d2_turn_request').fetchone()[0]=='{}'
    assert len(wire.calls)==1
