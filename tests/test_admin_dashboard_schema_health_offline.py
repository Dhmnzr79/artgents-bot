"""D2 readiness is read-only and fails closed on invalid storage."""
import sqlite3
import pytest

@pytest.fixture
def admin_mod(monkeypatch):
    import admin_dashboard.app as mod
    monkeypatch.setattr(mod, 'APP_ENV', 'local')
    monkeypatch.setattr(mod, 'admin_client_options', lambda: [{'client_id':'demo','label':'Demo'}])
    return mod

def test_missing_database_is_empty_without_creating_it(admin_mod, tmp_path, monkeypatch):
    path=tmp_path/'absent.sqlite'
    monkeypatch.setenv('D2_DIALOGUE_DB_PATH',str(path))
    result=admin_mod.app.test_client().get('/api/health')
    assert result.status_code==200
    assert result.json['storage']['demo']=={'state':'empty','read_only':True,'metrics':False}
    assert not path.exists()

@pytest.mark.parametrize('corrupt',[True,False])
def test_invalid_database_fails_without_bootstrap(admin_mod,tmp_path,monkeypatch,corrupt):
    path=tmp_path/'bad.sqlite'
    if corrupt:path.write_bytes(b'not a database')
    else:
        with sqlite3.connect(path)as conn:conn.execute('CREATE TABLE unrelated(value TEXT)')
    before=path.read_bytes();monkeypatch.setenv('D2_DIALOGUE_DB_PATH',str(path))
    result=admin_mod.app.test_client().get('/api/health')
    assert result.status_code==503 and result.json=={'error':'d2_storage_unavailable'}
    assert path.read_bytes()==before


@pytest.mark.parametrize('table',['d2_dialogue','d2_turn_request','d2_admin_observation'])
def test_expected_table_name_with_wrong_columns_is_not_ready(admin_mod,tmp_path,monkeypatch,table):
    from core.d2_dialogue_store import D2DialogueStore
    path=tmp_path/'wrong-columns.sqlite'
    with D2DialogueStore(path):pass
    with sqlite3.connect(path)as conn:
        if table!='d2_admin_observation':conn.execute(f'DROP TABLE {table}')
        conn.execute(f'CREATE TABLE {table}(unrelated TEXT)')
    before=path.read_bytes();monkeypatch.setenv('D2_DIALOGUE_DB_PATH',str(path))
    result=admin_mod.app.test_client().get('/api/health')
    assert result.status_code==503 and result.json=={'error':'d2_storage_unavailable'}
    assert path.read_bytes()==before
