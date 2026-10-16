"""Only authored first-entry context reaches the first ordinary model call."""
import json
import shutil
from pathlib import Path
import pytest
from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from core.d2_live_provider import D2HttpProvider
from core.d2_tenant_snapshot import load_d2_tenant_snapshot
from tests.d2_ci_http import http_env,send
from tests.test_d2_native_price_runtime import Transport,message
from tests.test_d2_http_contract import post

ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('transport',['json','sse'])
def test_entry_page_frozen_and_never_overwrites_continuation(http_env,transport):
    client,db,use,_=http_env
    wire=Transport(message('Расскажу о вариантах.'),message('Продолжение темы.'));use(D2HttpProvider(transport=wire))
    send(client,transport,request_id='first',q='Какие варианты?',entry_page_path='/all-on-4/')
    prompt=wire.calls[0]['messages'][1]['content']
    assert 'ENTRY_PAGE_CONTEXT' in prompt and 'implantation' in prompt
    with D2DialogueStore(db)as store:
        entry=store.read(SessionKey(client_id='demo',sid='cp6a')).entry_page_context
    assert entry.topic_id=='implantation' and entry.path=='/all-on-4'
    send(client,transport,request_id='second',q='Подробнее',entry_page_path='/koronki-i-nesemnoe-protezirovanie/')
    assert 'ENTRY_PAGE_CONTEXT' not in wire.calls[1]['messages'][1]['content']
    with D2DialogueStore(db)as store:assert store.read(SessionKey(client_id='demo',sid='cp6a')).entry_page_context==entry


@pytest.mark.parametrize('path',['/unconfigured-page','/'])
def test_general_entry_does_not_invent_topic(http_env,path):
    client,db,use,_=http_env
    wire=Transport(message('Здравствуйте!'));use(D2HttpProvider(transport=wire))
    send(client,entry_page_path=path)
    assert 'ENTRY_PAGE_CONTEXT' not in wire.calls[0]['messages'][1]['content']
    with D2DialogueStore(db)as store:assert store.read(SessionKey(client_id='demo',sid='cp6a')).entry_page_context is None


@pytest.mark.parametrize('path',['https://foreign.example/x','/a?name=secret','/a#secret','//foreign/x',12])
def test_arbitrary_url_topic_and_query_not_accepted(http_env,path):
    client,_,use,_=http_env;wire=Transport();use(D2HttpProvider(transport=wire))
    assert post(client,entry_page_path=path).status_code==400
    assert wire.calls==[]
    assert post(client,entry_topic_id='implantation').status_code==400


def test_authored_unknown_topic_fails_snapshot_validation(tmp_path):
    shutil.copytree(ROOT/'clients/demo',tmp_path/'demo')
    path=tmp_path/'demo/widget_config.json';data=json.loads(path.read_text(encoding='utf-8'));data['pageMenus'][0]['topicId']='foreign_topic'
    path.write_text(json.dumps(data),encoding='utf-8')
    with pytest.raises(ValueError,match='widget_page_topic_invalid'):
        load_d2_tenant_snapshot('demo',clients_root=tmp_path)
