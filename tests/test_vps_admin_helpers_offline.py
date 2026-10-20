"""Read-only audit output never contains inspected secrets; no SSH/Docker calls."""
import json
from pathlib import Path
import re
import pytest

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def audit_module():
    text=(ROOT/'scripts/audit_vps_admin.ps1').read_text(encoding='utf-8')
    source=re.search(r"\$auditCode = @'\r?\n(.*?)\r?\n'@",text,re.S).group(1)
    namespace={'__name__':'offline_audit'}
    exec(compile(source,'readonly_vps_audit','exec'),namespace)
    return namespace


def test_inspection_reports_only_allowlisted_metadata(audit_module):
    secret='PRIVATE_CREDENTIAL_MUST_NEVER_APPEAR'
    data={'Config':{'Env':[f'ADMIN_DASHBOARD_TOKEN={secret}',f'CHAT_API_KEY={secret}',
        f'SMTP_PASSWORD={secret}',f'CADDY_ADMIN_BASIC_AUTH_HASH={secret}',
        'CADDY_ADMIN_BASIC_AUTH_USER=owner','APP_ENV=prod','ALLOWED_CLIENTS=demo,nikadent'],
        'Labels':{'org.opencontainers.image.revision':'a'*40}},
        'State':{'Running':True,'Health':{'Status':'healthy'}},
        'HostConfig':{'PortBindings':{'9100/tcp':[{'HostIp':'127.0.0.1','HostPort':'9100'}]}},
        'Mounts':[{'Destination':'/app/data','Type':'volume','Name':'bot_data','RW':False}]}
    calls=[]
    def fake_run(args):
        calls.append(args)
        return 'abc123\n'if args[1]=='ps'else json.dumps([data])
    audit_module['run']=fake_run
    admin=audit_module['service_info']('admin');caddy=audit_module['service_info']('caddy')
    assert secret not in json.dumps([admin,caddy])
    assert admin['internal_token_present']and admin['production_mode']
    assert admin['allowed_clients']==['demo','nikadent']
    assert admin['data_mounts'][0]['writable']is False
    assert caddy['admin_login']=='owner'and caddy['password_hash_present']
    assert admin['published_ports']['9100/tcp'][0]['address']=='127.0.0.1'
    assert all(args[:2]in (['docker','ps'],['docker','inspect'])for args in calls)


@pytest.mark.parametrize('ids',['','abc\ndef\n'])
def test_ambiguous_service_never_picks_an_arbitrary_container(audit_module,ids):
    def fake_run(args):
        assert args[1]=='ps'
        return ids
    audit_module['run']=fake_run
    assert audit_module['service_info']('admin')=={'running_containers':len(ids.split())}


def test_errors_are_sanitized_without_docker_stderr(audit_module):
    def fail(_args):raise RuntimeError('PRIVATE_DOCKER_ERROR_WITH_CREDENTIALS')
    audit_module['run']=fail
    audit_module['file_info']=lambda _path:{'exists':False}
    audit_module['http_status']=lambda:401
    report=audit_module['audit']()
    assert 'PRIVATE_DOCKER_ERROR'not in json.dumps(report)
    assert report['read_only']and report['unauthenticated_admin_http_status']==401
    assert all(item=={'inspection':'unavailable'}for item in report['services'].values())


@pytest.mark.parametrize('address,expected',[('::','::'),('0.0.0.0','0.0.0.0'),('','all_interfaces')])
def test_public_bindings_remain_visible(audit_module,address,expected):
    assert audit_module['safe_address'](address)==expected
