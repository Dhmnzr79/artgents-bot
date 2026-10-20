"""Technical observation cannot alter replies, privacy or model call count."""
import json
import sqlite3
from types import SimpleNamespace as NS
import pytest
from core import d2_admin_metrics as metrics
from core import d2_diagnostics as diagnostics
from core.d2_dialogue_store import D2DialogueStore

@pytest.fixture
def db(tmp_path,monkeypatch):
    path=tmp_path/'metrics.sqlite';monkeypatch.setenv('D2_DIALOGUE_DB_PATH',str(path))
    for key,value in dict(D2_ADMIN_METRICS_ENABLED='1',BOT_LLM_USD_PER_1M_PROMPT='1',BOT_LLM_USD_PER_1M_COMPLETION='2').items():monkeypatch.setenv(key,value)
    with D2DialogueStore(path):pass
    return path

def rows(db):
    with sqlite3.connect(db)as conn:
        conn.row_factory=sqlite3.Row
        return [dict(r)for r in conn.execute('SELECT * FROM d2_admin_observation')]

def test_tokens_estimate_hashes_without_private_strings(db):
    private='PRIVATE_PATIENT +79991234567 private@example.org';response=NS(usage=NS(prompt_tokens=1000,completion_tokens=100,prompt_cache_hit_tokens=0,prompt_cache_miss_tokens=1000));calls=[]
    def transport(**kwargs):calls.append(kwargs);return response
    with metrics.observe_request('demo',private,private)as observation:
        assert diagnostics.call_provider(transport,model='synthetic-model')is response
        observation.complete()
    saved=rows(db);assert len(calls)==1 and len(saved)==2
    assert private not in json.dumps(saved)and '79991234567'not in json.dumps(saved)
    usage=next(row for row in saved if row['kind']=='provider')
    assert usage['prompt_tokens']==1000 and usage['completion_tokens']==100 and usage['estimated_usd']==.0012
    assert metrics._current.get()is None

def test_missing_usage_and_rates_are_unknown(db,monkeypatch):
    monkeypatch.setenv('BOT_LLM_USD_PER_1M_PROMPT','0');monkeypatch.setenv('BOT_LLM_USD_PER_1M_COMPLETION','0')
    with metrics.observe_request('demo','s','r')as observation:
        diagnostics.call_provider(lambda **_:NS(),model='model');observation.complete()
    usage=next(row for row in rows(db)if row['kind']=='provider')
    assert usage['prompt_tokens']is None and usage['completion_tokens']is None and usage['estimated_usd']is None

def test_replay_does_not_invent_calls(db):
    with metrics.observe_request('demo','s','r')as observation:
        diagnostics.call_provider(lambda **_:NS(),model='model');diagnostics.call_provider(lambda **_:NS(),model='model');observation.complete()
    with metrics.observe_request('demo','s','r')as observation:observation.complete(replay=True)
    assert sum(row['kind']=='provider'for row in rows(db))==2
    assert sum(row['outcome']=='replayed'for row in rows(db))==1

def test_provider_error_preserved_without_exception_text(db):
    original=TimeoutError('PRIVATE_FAILURE with credentials')
    def fail(**_):raise original
    with pytest.raises(TimeoutError)as captured:
        with metrics.observe_request('demo','s','r'):diagnostics.call_provider(fail,model='model')
    assert captured.value is original and 'PRIVATE_FAILURE'not in json.dumps(rows(db))
    assert all(row['outcome']=='failed'for row in rows(db))and metrics._current.get()is None

def test_observer_failure_never_fails_transport(db,monkeypatch):
    def fail(*_args,**_kwargs):raise RuntimeError('observer broken')
    monkeypatch.setattr(metrics,'_write',fail);reply=NS()
    with metrics.observe_request('demo','s','r')as observation:
        assert diagnostics.call_provider(lambda **_:reply,model='model')is reply
        observation.complete()
    assert metrics._current.get()is None

def test_busy_storage_does_not_fail_answer(db):
    with sqlite3.connect(db)as writer:
        writer.execute('BEGIN EXCLUSIVE')
        with metrics.observe_request('demo','s','r')as observation:
            assert diagnostics.call_provider(lambda **_:'same reply',model='model')=='same reply';observation.complete()
        writer.rollback()
    assert metrics._current.get()is None

def test_disabled_metrics_do_not_create_table(db,monkeypatch):
    monkeypatch.setenv('D2_ADMIN_METRICS_ENABLED','0')
    with metrics.observe_request('demo','s','r')as observation:diagnostics.call_provider(lambda **_:NS(),model='model');observation.complete()
    with sqlite3.connect(db)as conn:assert conn.execute("SELECT 1 FROM sqlite_master WHERE name='d2_admin_observation'").fetchone()is None


def test_observation_connections_are_closed_after_each_write(db,monkeypatch):
    connect=sqlite3.connect;opened=[]
    def tracked(*args,**kwargs):
        conn=connect(*args,**kwargs);opened.append(conn);return conn
    monkeypatch.setattr(metrics.sqlite3,'connect',tracked)
    with metrics.observe_request('demo','s','r')as observation:
        diagnostics.call_provider(lambda **_:NS(),model='model');observation.complete()
    assert len(opened)==2
    for conn in opened:
        with pytest.raises(sqlite3.ProgrammingError):conn.execute('SELECT 1')


def test_additive_telemetry_upgrade_preserves_old_observation_and_canonical_tables(db):
    with sqlite3.connect(db)as conn:
        conn.execute('''CREATE TABLE d2_admin_observation (
            client_id TEXT,event_id TEXT,sid_hash TEXT,request_hash TEXT,observed_at TEXT,
            kind TEXT,outcome TEXT,model TEXT,prompt_tokens INTEGER,completion_tokens INTEGER,
            duration_ms INTEGER,estimated_usd REAL,PRIMARY KEY(client_id,event_id))''')
        conn.execute("INSERT INTO d2_admin_observation VALUES('demo','old','s','r','2999-01-01','provider','returned','old-model',1000,100,1,.0012)")
        before=conn.execute("SELECT name,sql FROM sqlite_master WHERE name IN ('d2_dialogue','d2_turn_request') ORDER BY name").fetchall()
    with metrics.observe_request('demo','s','new')as observation:
        diagnostics.call_provider(lambda **_:NS(usage=dict(prompt_tokens=1000,completion_tokens=100,
            prompt_tokens_details={'cached_tokens':900})),model='model');observation.complete()
    old=next(row for row in rows(db)if row['event_id']=='old')
    assert old['estimated_usd']==.0012 and old['cached_prompt_tokens']is None and old['pricing_basis']is None
    new=next(row for row in rows(db)if row['kind']=='provider'and row['event_id']!='old')
    assert new['cached_prompt_tokens']==900 and new['uncached_prompt_tokens']==100
    with sqlite3.connect(db)as conn:
        assert conn.execute("SELECT name,sql FROM sqlite_master WHERE name IN ('d2_dialogue','d2_turn_request') ORDER BY name").fetchall()==before
