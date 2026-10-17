"""Private form uses one sender/receipt, without contact messages or dialogue writes."""
import json
from unittest.mock import Mock
import pytest

from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from core.d2_live_provider import D2HttpProvider
from tests.d2_ci_http import http_env,send,click
from tests.test_d2_native_price_runtime import Transport,message,price
from tests.test_d2_price_cards import cards


def form_payload(client, *, tenant='nikadent',sid='form',request_id='submit',**changes):
    definition=client.get('/api/booking-form',query_string={'client_id':tenant}).get_json()
    payload=dict(client_id=tenant,sid=sid,request_id=request_id,name='Тестовое Имя Формы',phone='+79991234567',wish='Позвонить вечером',
                 consent=dict(accepted=True,definition_fingerprint=definition['definition_fingerprint']))
    payload.update(changes);return payload


@pytest.mark.parametrize('tenant',['demo','nikadent'])
def test_submit_replay_and_private_payload_not_in_store(http_env,monkeypatch,tenant):
    client,db,_,_=http_env
    delivery=Mock(return_value='email');monkeypatch.setattr('lead_service._resolve_delivery_status',delivery)
    payload=form_payload(client,tenant=tenant)
    response=client.post('/lead',json=payload)
    assert response.status_code==200
    body=response.get_json();assert body['ok'] and body['status']==('demo_stub' if tenant=='demo' else 'sent')
    assert client.post('/lead',json=payload).get_json()==body
    assert delivery.call_count==(0 if tenant=='demo' else 1)
    if tenant=='nikadent':
        assert delivery.call_args.kwargs['name']==payload['name']
        assert delivery.call_args.kwargs['phone']==payload['phone']
    with D2DialogueStore(db) as store:
        assert store.read(SessionKey(client_id=tenant,sid=payload['sid'])) is None
        assert store.read_latest_completion(SessionKey(client_id=tenant,sid=payload['sid'])) is None
        rows=store._connection.execute('SELECT payload FROM d2_turn_request').fetchall()
        encoded=json.dumps(rows,ensure_ascii=False)
        assert all(value not in encoded for value in [payload['name'],payload['phone'],payload['wish']])
        receipt=json.loads(rows[0][0]);assert receipt['accepted'] is True
        assert bool(receipt['consent_receipt'])==(tenant=='nikadent')
    changed={**payload,'name':'Другое имя'}
    assert client.post('/lead',json=changed).status_code==409
    assert delivery.call_count==(0 if tenant=='demo' else 1)


@pytest.mark.parametrize('tenant',['demo','nikadent'])
def test_no_checkbox_no_effect_and_fields_remain_retryable(http_env,monkeypatch,tenant):
    client,_,_,_=http_env
    sender=Mock(return_value='email');monkeypatch.setattr('lead_service._resolve_delivery_status',sender)
    payload=form_payload(client,tenant=tenant);payload['consent']['accepted']=False
    response=client.post('/lead',json=payload)
    assert response.status_code==400 and response.get_json()['error_code']=='lead_consent_required'
    assert not sender.called
    payload['consent']['accepted']=True
    assert client.post('/lead',json=payload).get_json()['ok']


@pytest.mark.parametrize('fault',['definition','missing_definition','accepted_type','bad_phone','extra_price','foreign_offer','stale_catalog'])
def test_invalid_private_submission_never_dispatches(http_env,monkeypatch,fault):
    client,_,_,_=http_env
    sender=Mock(return_value='email');monkeypatch.setattr('lead_service._resolve_delivery_status',sender)
    payload=form_payload(client)
    if fault=='definition':payload['consent']['definition_fingerprint']='0'*64
    elif fault=='missing_definition':payload['consent']['definition_fingerprint']=None
    elif fault=='accepted_type':payload['consent']['accepted']='yes'
    elif fault=='bad_phone':payload['phone']='123'
    elif fault=='extra_price':payload['amount']=1
    else:
        data=client.get('/api/widget-catalog?client_id=nikadent').get_json()
        payload['selection']=dict(service_id='caries',offer_id='classic.one_tooth.nobel',catalog_version=data['catalog_version'])
        if fault=='stale_catalog':payload['selection'].update(offer_id='caries.default',catalog_version='0'*64)
    response=client.post('/lead',json=payload)
    assert response.status_code==400 and not sender.called
    assert payload['name'] not in response.get_data(as_text=True)


def test_canonical_selection_reaches_delivery_without_client_titles_or_prices(http_env,monkeypatch):
    client,_,_,_=http_env
    sender=Mock(return_value='email');monkeypatch.setattr('lead_service._resolve_delivery_status',sender)
    catalog=client.get('/api/widget-catalog?client_id=nikadent').get_json()
    payload=form_payload(client,selection=dict(service_id='removable_dentures',offer_id='removable_dentures.jaw.nylon',catalog_version=catalog['catalog_version']))
    assert client.post('/lead',json=payload).get_json()['ok']
    selection=sender.call_args.kwargs['selection']
    assert selection['service_id']=='removable_dentures' and selection['offer_id']=='removable_dentures.jaw.nylon'
    assert 'нейлон' in selection['variant_name']


def test_form_does_not_replace_dialogue_or_invalidate_price_buttons(http_env,monkeypatch):
    client,db,use,_=http_env
    wire=Transport(message(None,price()),message('<NO_TEXT>'));use(D2HttpProvider(transport=wire))
    body=send(client,request_id='price')
    key=SessionKey(client_id='demo',sid='cp6a')
    with D2DialogueStore(db)as store:before=store.read(key);completion=store.read_latest_completion(key)
    form=form_payload(client,tenant='demo',sid='cp6a')
    assert client.post('/lead',json=form).get_json()['ok']
    with D2DialogueStore(db)as store:assert store.read(key)==before;assert store.read_latest_completion(key)==completion
    chosen=click(client,body,'price_select:classic.one_tooth.nobel',request_id='select')
    assert cards(chosen)[0]['price']['rows'][0]['offer_id']=='classic.one_tooth.nobel'
    assert len(wire.calls)==2


@pytest.mark.parametrize('delivery',['email_failed','email_smtp_not_configured'])
def test_failed_or_unknown_delivery_is_durable_and_never_resent(http_env,monkeypatch,delivery):
    client,_,_,_=http_env
    sender=Mock(return_value=delivery);monkeypatch.setattr('lead_service._resolve_delivery_status',sender)
    payload=form_payload(client)
    first=client.post('/lead',json=payload).get_json()
    assert not first['ok'] and first['status']==('unknown' if delivery=='email_failed' else 'failed')
    assert client.post('/lead',json=payload).get_json()==first and sender.call_count==1


def test_crash_after_pending_receipt_does_not_authorize_resend(http_env,monkeypatch):
    client,_,_,_=http_env
    class ProcessCrash(BaseException):pass
    sender=Mock(side_effect=ProcessCrash());monkeypatch.setattr('core.d2_booking_form.handle_lead',sender)
    payload=form_payload(client)
    with pytest.raises(ProcessCrash):client.post('/lead',json=payload)
    replay=client.post('/lead',json=payload).get_json()
    assert replay['status']=='pending' and not replay['ok'] and sender.call_count==1


def test_existing_three_leads_per_hour_limit_and_replay(http_env,monkeypatch):
    client,_,_,_=http_env
    sender=Mock(return_value='email');monkeypatch.setattr('lead_service._resolve_delivery_status',sender)
    for index in range(3):
        payload=form_payload(client,request_id=f'send{index}')
        assert client.post('/lead',json=payload).get_json()['ok']
        assert client.post('/lead',json=payload).get_json()['ok']
    assert client.post('/lead',json=form_payload(client,request_id='fourth')).status_code==429
    assert sender.call_count==3


@pytest.mark.parametrize('transport',['json','sse'])
def test_booking_intent_offers_form_and_does_not_collect_slots(http_env,transport):
    from session import session_client_scope,mem_get
    client,_,use,_=http_env
    raw='\n<D2_META>\n'+json.dumps({'actions':[{'name':'start_booking','arguments':{'age_group':'adult'}}]})+'\n</D2_META>'
    wire=Transport(message(raw),message('Отвечаю на обычный вопрос.'));use(D2HttpProvider(transport=wire))
    body=send(client,transport,q='Хочу записаться')
    assert body['ui']['booking_form'] and body['ui']['lead_consent'] is None
    assert not any(r['reply_id'].startswith('lead:') for r in body['ui']['quick_replies'])
    with session_client_scope('demo'):assert mem_get('cp6a').get('lead_intent')=='none'
    send(client,transport,request_id='next',q='А где вы находитесь?')
    assert len(wire.calls)==2


def test_mixed_price_and_booking_keeps_variant_actions(http_env):
    client,_,use,_=http_env
    raw='\n<D2_META>\n'+json.dumps({'actions':[{'name':'start_booking','arguments':{'age_group':'adult'}}]})+'\n</D2_META>'
    wire=Transport(message(raw,price()),message('<NO_TEXT>'));use(D2HttpProvider(transport=wire))
    body=send(client)
    assert body['ui']['booking_form'] and cards(body)[0]['price']['presentation']=='options'
    chosen=click(client,body,'price_select:classic.one_tooth.nobel',request_id='choose')
    assert cards(chosen)[0]['price']['rows'][0]['offer_id']=='classic.one_tooth.nobel' and len(wire.calls)==2
