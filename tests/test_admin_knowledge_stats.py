"""Tenant knowledge sizing uses actual prompt serialization, never paid calls."""
from pathlib import Path
import shutil
import pytest


def test_current_pack_recomputed_without_provider_or_private_data(tmp_path, monkeypatch):
    import admin_dashboard.knowledge_stats as mod
    import llm
    monkeypatch.setattr(llm.chat_client.chat.completions, 'create',
                        lambda **_: pytest.fail('provider call forbidden'))
    root=tmp_path/'clients'
    shutil.copytree(Path('clients/demo'), root/'demo')
    monkeypatch.setattr(mod, 'd2_clients_root', lambda: root)
    first=mod.knowledge_stats('demo')
    assert first['documents'] == len(list((root/'demo/md').rglob('*.md')))
    assert first['services'] >= first['active_services'] > 0
    assert first['offers'] >= first['active_offers'] > 0
    assert first['total_chars'] == first['system_chars'] + first['tool_chars']
    assert first['system_chars'] == first['corpus_chars'] + first['other_system_chars']
    assert first['md_bytes'] > first['md_chars']
    assert all(isinstance(v,int) for v in first.values())
    doc=next((root/'demo/md').glob('*.md'))
    with doc.open('a',encoding='utf-8') as f:f.write('\nНовый факт для проверки.')
    second=mod.knowledge_stats('demo')
    assert second['total_chars'] > first['total_chars']
    assert second['pack_bytes'] > first['pack_bytes']
    assert second['documents'] == first['documents']


def test_knowledge_endpoint_tenant_and_auth(monkeypatch):
    import admin_dashboard.app as appmod
    import admin_dashboard.knowledge_stats as stats
    monkeypatch.setattr(appmod,'APP_ENV','local')
    monkeypatch.setattr(appmod,'admin_client_options',lambda:[dict(client_id='demo',label='Demo')])
    calls=[]
    monkeypatch.setattr(stats,'knowledge_stats',lambda cid:calls.append(cid) or dict(documents=12))
    client=appmod.app.test_client()
    for cid in ('','nikadent','../demo'):
        assert client.get('/api/knowledge',query_string={'client_id':cid}).status_code==400
    assert calls==[]
    response=client.get('/api/knowledge?client_id=demo')
    assert response.json==dict(client_id='demo',documents=12)
    assert 'no-store' in response.headers['Cache-Control']
    monkeypatch.setattr(appmod,'APP_ENV','prod')
    monkeypatch.setattr(appmod,'ADMIN_TOKEN','test-private')
    assert client.get('/api/knowledge?client_id=demo').status_code==404
    assert calls==['demo']


def test_missing_pack_safe_error(monkeypatch,tmp_path):
    import admin_dashboard.knowledge_stats as mod
    from admin_dashboard.repository import StorageUnavailable
    monkeypatch.setattr(mod,'d2_clients_root',lambda:tmp_path)
    with pytest.raises(StorageUnavailable,match='knowledge_stats_unavailable'):
        mod.knowledge_stats('demo')
