"""Offline real HTTP, read-only report and browser-module telemetry boundaries."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
from unittest.mock import Mock
from uuid import uuid4

import pytest

from core import widget_analytics as analytics
from core.d2_admin_metrics import identity_hash
from tests.d2_ci_http import http_env
from tests.test_widget_booking_form import form_payload

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = 'http://127.0.0.1:9001'


@pytest.fixture
def environment(http_env, monkeypatch):
    bot, db, _, temp = http_env
    import admin_dashboard.app as admin
    monkeypatch.setattr(admin, 'APP_ENV', 'local')
    monkeypatch.setattr(admin, 'admin_client_options', lambda: [dict(client_id=c, label=c) for c in ('demo','nikadent','demo_medical')])
    monkeypatch.setenv('D2_ADMIN_METRICS_ENABLED', '1')
    analytics._buckets.clear()
    inherited = sqlite3.connect
    def connect(database, *args, **kwargs):
        if kwargs.get('uri'):
            assert str(database) in {p.resolve().as_uri()+'?mode=ro' for p in (db, analytics.analytics_path('demo'))}
            return sqlite3.dbapi2.connect(database, *args, **kwargs)
        return inherited(database, *args, **kwargs)
    monkeypatch.setattr(sqlite3, 'connect', connect)
    return bot, admin.app.test_client(), db, temp


def event(bot, *, kind='opened', view=None, tenant='demo', path='/', **ids):
    body=dict(client_id=tenant, view_id=view or str(uuid4()), kind=kind, path=path, **ids)
    return bot.post('/api/widget-events?client_id='+tenant, json=body, headers={'Origin': ORIGIN})


def report(admin, tenant='demo'):
    response=admin.get('/api/funnel', query_string=dict(client_id=tenant, period='today'))
    assert response.status_code==200, response.json
    return response.json


def test_empty_is_read_only_and_does_not_bootstrap(environment):
    _, admin, db, _=environment
    assert report(admin)==dict(client_id='demo', available=False, items=[], truncated=False)
    assert not db.exists() and not analytics.analytics_path('demo').exists()
    assert admin.get('/api/funnel?client_id=foreign').status_code==400


def test_page_dedup_without_dialogue_and_no_private_url(environment):
    bot, admin, db, _=environment; view=str(uuid4())
    for _ in range(3):
        assert event(bot,view=view,path='/?phone=79991234567#private').status_code==204
    assert event(bot,view=view,kind='question',path='/other-page').status_code==204
    assert event(bot,path='/patients/private@example.org/79991234567').status_code==204
    data=report(admin); assert data['totals']['opened']==2 and data['totals']['question']==1
    root=next(x for x in data['items'] if x['path']=='/')
    assert root['question']==1 and root['domain']=='127.0.0.1'
    assert {x['path'] for x in data['items']}=={'/','(other)'}
    assert not db.exists()
    with closing(sqlite3.connect(analytics.analytics_path('demo'))) as conn:
        saved=str(conn.execute('SELECT * FROM widget_event').fetchall())
    assert all(secret not in saved for secret in ('79991234567','private@example.org',view,'?phone'))
    assert report(admin,'nikadent')['items']==[]


@pytest.mark.parametrize('delivery,expected',[('email','sent'),('email_failed','unknown'),('email_smtp_not_configured','failed')])
def test_delivery_only_canonical_receipt_and_retry_dedup(environment,monkeypatch,delivery,expected):
    bot,admin,db,_=environment;view=str(uuid4());sid=str(uuid4());request_id=str(uuid4())
    sender=Mock(return_value=delivery);monkeypatch.setattr('lead_service._resolve_delivery_status',sender)
    for kind in ('opened','form','submit'):
        assert event(bot,kind=kind,view=view,tenant='nikadent',**(dict(sid=sid,request_id=request_id) if kind=='submit' else {})).status_code==204
    assert report(admin,'nikadent')['totals']['accepted']==0
    body=form_payload(bot,sid=sid,request_id=request_id)
    assert bot.post('/lead',json=body).status_code==200
    assert bot.post('/lead',json=body).status_code==200
    assert event(bot,kind='submit',view=view,tenant='nikadent',sid=sid,request_id=request_id).status_code==204
    before=db.read_bytes();side=analytics.analytics_path('nikadent').read_bytes()
    data=report(admin,'nikadent');assert data['totals']['accepted']==1 and data['totals'][expected]==1
    assert data['totals']['sent']==int(expected=='sent') and data['totals']['submit']==1
    assert all(secret not in json.dumps(data,ensure_ascii=False) for secret in (body['name'],body['phone'],body['wish'],sid,request_id))
    assert db.read_bytes()==before and analytics.analytics_path('nikadent').read_bytes()==side
    assert sender.call_count==1 and report(admin)['totals']['accepted']==0


def test_new_success_after_rejected_attempt_and_demo_separate(environment):
    bot,admin,_,_=environment;view=str(uuid4());sid=str(uuid4());first=str(uuid4());second=str(uuid4())
    assert event(bot,kind='submit',view=view,sid=sid,request_id=first).status_code==204
    invalid=form_payload(bot,tenant='demo',sid=sid,request_id=first,phone='123')
    assert bot.post('/lead',json=invalid).status_code==400
    valid=form_payload(bot,tenant='demo',sid=sid,request_id=second)
    assert event(bot,kind='submit',view=view,sid=sid,request_id=second).status_code==204
    assert bot.post('/lead',json=valid).json['status']=='demo_stub'
    data=report(admin)['totals']
    assert data['submit']==data['accepted']==data['demo_stub']==1 and data['sent']==0


@pytest.mark.parametrize('patch',[{'kind':'sent'},{'q':'private'},{'phone':'79991234567'},{'view_id':'private'},
    {'sid':'private'}, {'kind':'submit','sid':'private','request_id':str(uuid4())}, {'path':'a'*1025}, {'kind':[]}, {'view_id':None}, {'client_id':{}}, {'client_id':None}])
def test_closed_event_input(environment,patch):
    bot,_,_,_=environment
    body=dict(client_id='demo',kind='opened',view_id=str(uuid4()),path='/');body.update(patch)
    response=bot.post('/api/widget-events',json=body,headers={'Origin':ORIGIN})
    assert response.status_code==400 and response.headers['Cache-Control']=='no-store'
    assert not analytics.analytics_path('demo').exists()


def test_origin_cors_tenant_body_limit_and_rate(environment,monkeypatch):
    bot,_,_,_=environment
    body=dict(client_id='demo',kind='opened',view_id=str(uuid4()),path='/')
    assert bot.post('/api/widget-events',json=body).status_code==403
    assert bot.post('/api/widget-events',json=body,headers={'Origin':'https://evil.invalid'}).status_code==403
    assert event(bot,tenant='foreign').status_code==403
    allowed=bot.options('/api/widget-events?client_id=demo',headers={'Origin':ORIGIN,'Access-Control-Request-Method':'POST'})
    assert allowed.status_code==204 and allowed.headers['Access-Control-Allow-Origin']==ORIGIN
    assert bot.options('/api/widget-events?client_id=demo',headers={'Origin':'https://evil.invalid'}).status_code==403
    oversized=bot.post('/api/widget-events',data='{"client_id":"demo","path":"'+'a'*3000+'"}',content_type='application/json',headers={'Origin':ORIGIN})
    assert oversized.status_code==413
    analytics._buckets.clear()
    for _ in range(120):assert analytics.admit('demo','peer')
    assert not analytics.admit('demo','peer') and analytics.admit('nikadent','peer')
    monkeypatch.setattr(analytics,'monotonic',lambda:10**12)
    assert analytics.admit('demo','peer')
    for n in range(4100):analytics.admit('demo',str(n))
    assert len(analytics._buckets)==4096
    monkeypatch.setattr(analytics,'admit',lambda *_:False)
    assert event(bot).status_code==429


def test_disabled_busy_and_retention_do_not_touch_canonical(environment,monkeypatch):
    bot,_,db,_=environment
    monkeypatch.setenv('D2_ADMIN_METRICS_ENABLED','0');assert event(bot).status_code==204
    path=analytics.analytics_path('demo');assert not path.exists() and not db.exists()
    monkeypatch.setenv('D2_ADMIN_METRICS_ENABLED','1');assert event(bot).status_code==204
    with closing(sqlite3.connect(path)) as conn,conn:
        conn.execute('UPDATE widget_event SET observed_at=?',((datetime.now(timezone.utc)-timedelta(days=31)).isoformat(),))
    assert event(bot).status_code==204
    with closing(sqlite3.connect(path)) as conn:
        assert conn.execute('SELECT count(*) FROM widget_event').fetchone()[0]==1
        conn.execute('BEGIN EXCLUSIVE')
        assert event(bot).status_code==204
        conn.rollback()
    assert not db.exists()


def test_known_paths_period_and_connection_closure(environment,monkeypatch):
    bot,admin,_,_=environment
    monkeypatch.setattr(analytics,'load_widget_presentation_v1',lambda _:dict(pageMenus=[dict(paths=['/clinic/'])]))
    assert event(bot,path='/clinic/?utm_source=private#secret').status_code==204
    assert report(admin)['items'][0]['path']=='/clinic'
    path=analytics.analytics_path('demo')
    with closing(sqlite3.connect(path)) as conn,conn:
        conn.execute('UPDATE widget_event SET observed_at=?',((datetime.now(timezone.utc)-timedelta(days=2)).isoformat(),))
    assert report(admin)['items']==[]
    assert admin.get('/api/funnel?client_id=demo&period=week').json['totals']['opened']==1
    connect=sqlite3.connect;opened=[]
    def tracked(*args,**kwargs):
        conn=connect(*args,**kwargs);opened.append(conn);return conn
    monkeypatch.setattr(sqlite3,'connect',tracked)
    assert event(bot).status_code==204;report(admin)
    for conn in opened:
        with pytest.raises(sqlite3.ProgrammingError):conn.execute('SELECT 1')


def test_actual_javascript_observer_and_form_handler_offline():
    node=shutil.which('node') or r'C:\Program Files\nodejs\node.exe'
    result=subprocess.run([node,str(ROOT/'tests/js/widget_analytics_test.mjs')],cwd=ROOT,capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stdout+result.stderr


def test_medical_and_dental_are_separate(environment,http_env,monkeypatch):
    from tests.test_widget_catalog import admit_medical
    admit_medical(http_env,monkeypatch)
    bot,admin,_,_=environment
    for tenant,count in [('demo',1),('demo_medical',2),('nikadent',3)]:
        for _ in range(count):assert event(bot,tenant=tenant).status_code==204
    for tenant,count in [('demo',1),('demo_medical',2),('nikadent',3)]:
        assert report(admin,tenant)['totals']['opened']==count


def test_report_cap_is_explicit(environment):
    bot,admin,_,_=environment
    assert event(bot).status_code==204
    now=datetime.now(timezone.utc).isoformat()
    with closing(sqlite3.connect(analytics.analytics_path('demo'))) as conn,conn:
        conn.executemany('INSERT INTO widget_event VALUES (?,?,?,?,?,?,?,?)',
            [('demo',identity_hash(str(n)),'opened','127.0.0.1','/',now,None,'') for n in range(50001)])
    data=report(admin)
    assert data['truncated'] is True and data['totals']['opened']==50000
