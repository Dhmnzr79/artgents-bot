"""No tenant fallback, public local access, auth bypass or mutations."""
import pytest

@pytest.fixture
def admin_app(monkeypatch):
    import admin_dashboard.app as mod
    monkeypatch.setattr(mod,'APP_ENV','local')
    monkeypatch.setattr(mod,'ADMIN_TOKEN','synthetic-admin-token')
    monkeypatch.setattr(mod,'admin_client_options',lambda:[{'client_id':'demo','label':'Demo'}])
    return mod.app.test_client(),mod

@pytest.mark.parametrize('query',['','?client_id=','?client_id=not-a-real-clinic-pack','?client_id=nikadent','?client_id=../demo'])
def test_missing_disabled_unknown_client_fail_closed(admin_app,query,monkeypatch):
    client,mod=admin_app
    monkeypatch.setattr(mod.repository,'overview',lambda *_:pytest.fail('unauthorized storage read'))
    assert client.get('/api/overview'+query).status_code==400

@pytest.mark.parametrize('base,remote,origin',[
    ('http://attacker.invalid','127.0.0.1',None),('http://localhost','192.0.2.7',None),
    ('http://localhost','127.0.0.1','https://attacker.invalid')])
def test_local_access_and_dns_rebinding_blocked(admin_app,base,remote,origin):
    response=admin_app[0].get('/api/clients',base_url=base,environ_overrides={'REMOTE_ADDR':remote},headers={'Origin':origin}if origin else{})
    assert response.status_code==403

@pytest.mark.parametrize('environment',['prod','production'])
def test_prod_requires_token_for_assets_and_home(admin_app,environment):
    client,mod=admin_app;mod.APP_ENV=environment
    for path in ('/','/api/clients','/static/dashboard.js'):
        assert client.get(path).status_code==404
        assert client.get(path,headers={'X-Admin-Dashboard-Token':'wrong'}).status_code==404
        response=client.get(path,headers={'X-Admin-Dashboard-Token':mod.ADMIN_TOKEN})
        assert response.status_code==200 and 'no-store'in response.headers['Cache-Control']
        assert 'frame-ancestors'in response.headers['Content-Security-Policy']

def test_missing_token_and_unknown_environment_fail_closed(admin_app):
    client,mod=admin_app;mod.APP_ENV,mod.ADMIN_TOKEN='prod',''
    assert client.get('/api/clients').status_code==503
    mod.APP_ENV='staging';assert client.get('/api/clients').status_code==503

@pytest.mark.parametrize('method,path',[('POST','/api/dialogs/synthetic/purge'),('DELETE','/api/dialogs/synthetic'),('POST','/api/leads')])
def test_no_mutation_routes(admin_app,method,path):
    response=admin_app[0].open(path,method=method)
    assert response.status_code in(404,405)and 'no-store'in response.headers['Cache-Control']

@pytest.mark.parametrize('query',['limit=0','limit=101','limit=x','cursor=-1','cursor=9223372036854775808'])
def test_pagination_is_bounded(admin_app,query):
    assert admin_app[0].get('/api/dialogs?client_id=demo&'+query).status_code==400
