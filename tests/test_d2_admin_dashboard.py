"""Actual D2 HTTP -> receipts -> private read-only admin; no SMTP/provider network."""
from hashlib import sha256
import json
import sqlite3
from unittest.mock import Mock
from uuid import uuid4
import pytest
from core.d2_admin_metrics import identity_hash
from core.d2_live_provider import D2HttpProvider
from tests.d2_ci_http import http_env,send,click
from tests.test_d2_native_price_runtime import Transport,message,price
from tests.test_widget_booking_form import form_payload

@pytest.fixture
def admin_env(http_env,monkeypatch):
    bot,db,use,temp=http_env
    import admin_dashboard.app as mod
    monkeypatch.setattr(mod,'APP_ENV','local')
    monkeypatch.setattr(mod,'admin_client_options',lambda:[dict(client_id=c,label=c)for c in('demo','nikadent')])
    inherited_connect=sqlite3.connect
    def isolated_connect(database,*args,**kwargs):
        # Extend fixture ONLY for the exact temp database's read-only URI.
        if kwargs.get('uri'):
            assert str(database)==db.resolve().as_uri()+'?mode=ro'
            return sqlite3.dbapi2.connect(database,*args,**kwargs)
        return inherited_connect(database,*args,**kwargs)
    monkeypatch.setattr(sqlite3,'connect',isolated_connect)
    return bot,mod.app.test_client(),db,use,temp,mod

def test_saved_publication_privacy_ownership_no_writes(admin_env):
    bot,admin,db,use,_,mod=admin_env;sid=uuid4().hex
    wire=Transport(message('Сохранённый ответ. Личный контакт +79995556677, abc@example.org.'))
    use(D2HttpProvider(transport=wire))
    send(bot,sid=sid,q='Мой телефон +79998887766, other@example.org. Расскажите о клинике.')
    digest=sha256(db.read_bytes()).hexdigest()
    assert admin.get('/api/dialogs?client_id=demo').json['items'][0]['session_id']==identity_hash(sid)
    response=admin.get(f'/api/dialogs/{identity_hash(sid)}/thread?client_id=demo')
    assert response.status_code==200 and 'Сохранённый ответ'in response.json['items'][0]['answer']
    text=json.dumps(response.json,ensure_ascii=False)
    assert all(secret not in text for secret in('79995556677','79998887766','abc@example.org','other@example.org',sid,'consent_receipt','request_fingerprint'))
    assert admin.get(f'/api/dialogs/{identity_hash(sid)}/thread?client_id=nikadent').status_code==404
    assert sha256(db.read_bytes()).hexdigest()==digest and len(wire.calls)==1
    with mod.repository.reader('demo')as conn:
        with pytest.raises(sqlite3.OperationalError):conn.execute('DELETE FROM d2_dialogue')
    assert sha256(db.read_bytes()).hexdigest()==digest

def test_history_page_and_frozen_prices_without_catalog_recalculation(admin_env):
    bot,admin,_,use,temp,_=admin_env;sid=uuid4().hex
    wire=Transport(message(None,price()),message('<NO_TEXT>'),message('Последующее объяснение.'))
    use(D2HttpProvider(transport=wire));first=send(bot,sid=sid,request_id='prices')
    selected=click(bot,first,'price_select:classic.one_tooth.nobel',sid=sid,request_id='chosen')
    send(bot,sid=sid,request_id='last',q='Расскажите ещё.')
    path=temp/'clients/demo/target_response/pricebook/services/classic.one_tooth.nobel.json'
    content=json.loads(path.read_text(encoding='utf-8'));content['price']['amount']=1;path.write_text(json.dumps(content),encoding='utf-8')
    latest=admin.get(f'/api/dialogs/{identity_hash(sid)}/thread?client_id=demo&limit=1').json
    assert [x['revision']for x in latest['items']]==[3]and latest['next_cursor']
    older=admin.get(f'/api/dialogs/{identity_hash(sid)}/thread',query_string=dict(client_id='demo',limit=1,cursor=latest['next_cursor'])).json
    assert [x['revision']for x in older['items']]==[2]and '101'in older['items'][0]['answer']and '101'in selected['answer']
    assert len(wire.calls)==3

@pytest.mark.parametrize('delivery,expected',[('email','sent'),('email_failed','unknown'),('email_smtp_not_configured','failed')])
def test_form_receipt_without_private_fields_or_resend(admin_env,monkeypatch,delivery,expected):
    bot,admin,db,_,_,_=admin_env;sender=Mock(return_value=delivery)
    monkeypatch.setattr('lead_service._resolve_delivery_status',sender)
    body=form_payload(bot);bot.post('/lead',json=body);before=db.read_bytes()
    response=admin.get('/api/leads?client_id=nikadent')
    assert response.status_code==200 and response.json['items'][0]['status']==expected
    serialized=json.dumps(response.json,ensure_ascii=False)
    assert all(secret not in serialized for secret in(body['name'],body['phone'],body['wish'],'consent_receipt'))
    overview=admin.get('/api/overview?client_id=nikadent').json
    assert overview[expected]==1 and overview['forms']==1
    assert db.read_bytes()==before and sender.call_count==1

def test_demo_stub_is_not_sent_and_historical_cost_unknown(admin_env):
    bot,admin,_,_,_,_=admin_env;bot.post('/lead',json=form_payload(bot,tenant='demo'))
    data=admin.get('/api/overview?client_id=demo').json
    assert data['demo_stub']==1 and data['sent']==0
    assert admin.get('/api/costs?client_id=demo').json['estimated_usd']is None

def test_owner_tampering_fails_closed(admin_env):
    bot,admin,db,use,_,_=admin_env;use(D2HttpProvider(transport=Transport(message('Only demo'))));sid=uuid4().hex;send(bot,sid=sid)
    with sqlite3.connect(db)as conn:
        conn.execute("UPDATE d2_turn_request SET payload=json_set(payload,'$.context.session_key.client_id','nikadent') WHERE client_id='demo'")
    response=admin.get(f'/api/dialogs/{identity_hash(sid)}/thread?client_id=demo')
    assert response.status_code==503 and response.json=={'error':'d2_storage_unavailable'}

def test_real_adapter_usage_replay_and_failed_request_observation(admin_env,monkeypatch):
    from types import SimpleNamespace as NS
    bot,admin,_,use,_,_=admin_env
    monkeypatch.setenv('CHAT_BASE_URL','https://provider.invalid')
    monkeypatch.setenv('BOT_LLM_USD_PER_1M_PROMPT','1')
    monkeypatch.setenv('BOT_LLM_USD_PER_1M_COMPLETION','2')
    reply=message('Ответ с метриками.');reply.usage=NS(prompt_tokens=1000,completion_tokens=100,prompt_cache_hit_tokens=0,prompt_cache_miss_tokens=1000)
    wire=Transport(reply,TimeoutError('PRIVATE_PROVIDER_ERROR'))
    use(D2HttpProvider(transport=wire))
    sid=uuid4().hex
    first=send(bot,sid=sid,request_id='first',q='Расскажите о клинике')
    assert send(bot,sid=sid,request_id='first',q='Расскажите о клинике')==first
    costs=admin.get('/api/costs?client_id=demo').json
    assert costs['items'][0]['calls']==1 and costs['estimated_usd']==.0012
    response=bot.post('/ask',json=dict(client_id='demo',sid=sid,request_id='second',q='Следующий вопрос'))
    assert response.status_code>=400
    errors=admin.get('/api/problems?client_id=demo').json
    assert errors['available'] and errors['items']
    assert 'PRIVATE_PROVIDER_ERROR'not in json.dumps(errors)
    assert len(wire.calls)==2


def test_cached_usage_snapshot_totals_and_replay_without_charge(admin_env,monkeypatch):
    from datetime import datetime,timezone
    from types import SimpleNamespace as NS
    from core import d2_admin_metrics as metrics
    bot,admin,db,use,_,_=admin_env
    monkeypatch.setenv('CHAT_BASE_URL','https://api.deepseek.com')
    # Same current date for API filtering, deterministic peak hour for the tariff.
    fixed=datetime.now(timezone.utc).replace(hour=1,minute=0,second=0,microsecond=0)
    class Clock:
        @staticmethod
        def now(_tz):return fixed
    monkeypatch.setattr(metrics,'datetime',Clock)
    reply=message('Ответ с кэшем.');reply.usage=NS(prompt_tokens=10000,completion_tokens=1000,
        prompt_cache_hit_tokens=9000,prompt_cache_miss_tokens=1000)
    wire=Transport(reply);use(D2HttpProvider(model='deepseek-flash',transport=wire))
    sid=uuid4().hex;first=send(bot,sid=sid,request_id='cache',q='О клинике')
    assert send(bot,sid=sid,request_id='cache',q='О клинике')==first
    before=db.read_bytes()
    data=admin.get('/api/costs?client_id=demo').json;row=data['items'][0]
    assert (row['calls'],row['prompt_tokens'],row['cached_prompt_tokens'],row['uncached_prompt_tokens'],row['completion_tokens'])==(1,10000,9000,1000,1000)
    expected=.001554 if fixed.weekday()<5 else .000777
    assert data['estimated_usd']==pytest.approx(expected)and data['legacy_calls']==0 and data['unsplit_calls']==0
    monkeypatch.setenv('BOT_LLM_USD_PER_1M_PROMPT','999');monkeypatch.setenv('CHAT_BASE_URL','https://provider.invalid')
    assert admin.get('/api/costs?client_id=demo').json['estimated_usd']==data['estimated_usd']
    events=admin.get('/api/events?client_id=demo').json['items']
    provider=next(x for x in events if x['kind']=='provider')
    assert provider['pricing_basis'].startswith('deepseek-flash-2026-10-19/')
    assert provider['rate_cached_usd_per_1m']==(.006 if fixed.weekday()<5 else .003)
    assert admin.get('/api/costs?client_id=nikadent').json['items']==[]
    assert db.read_bytes()==before and len(wire.calls)==1


def test_old_ledger_is_read_only_and_old_amount_not_added_to_new_cost(admin_env):
    from datetime import datetime,timezone
    bot,admin,db,_,_,_=admin_env
    # Create only the previous telemetry schema; admin must not upgrade it.
    from core.d2_dialogue_store import D2DialogueStore
    with D2DialogueStore(db):pass
    with sqlite3.connect(db)as conn:
        conn.execute('''CREATE TABLE d2_admin_observation (
            client_id TEXT,event_id TEXT,sid_hash TEXT,request_hash TEXT,observed_at TEXT,
            kind TEXT,outcome TEXT,model TEXT,prompt_tokens INTEGER,completion_tokens INTEGER,
            duration_ms INTEGER,estimated_usd REAL,PRIMARY KEY(client_id,event_id))''')
        conn.execute('INSERT INTO d2_admin_observation VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
            ('demo','old','safe-s','safe-r',datetime.now(timezone.utc).isoformat(),'provider','returned','old-model',1000,100,1,.0012))
    before=db.read_bytes()
    data=admin.get('/api/costs?client_id=demo').json
    assert data['estimated_usd']is None and data['legacy_estimated_usd']==.0012 and data['legacy_calls']==1 and data['unsplit_calls']==1
    assert data['items'][0]['cached_prompt_tokens']is None
    events=admin.get('/api/events?client_id=demo&limit=1').json
    assert len(events['items'])==1 and events['items'][0]['pricing_basis']is None
    assert db.read_bytes()==before
