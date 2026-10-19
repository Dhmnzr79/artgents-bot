# Read-only inventory; sudo password is entered directly in SSH's terminal.
# Never outputs production.env, password/hash/token values, contacts or dialogue text.
$ErrorActionPreference = "Stop"
$keyPath = Join-Path $env:USERPROFILE ".ssh\artgents_timeweb_ed25519"
if (-not (Test-Path -LiteralPath $keyPath -PathType Leaf)) { throw "SSH key not found: $keyPath" }
$null = Get-Command ssh -ErrorAction Stop
$auditCode = @'
import json
import ipaddress
import os
import re
import stat
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PROJECT = 'demo-bot-production'

def run(args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=15)
    if result.returncode:
        raise RuntimeError('read_command_failed')
    return result.stdout

def safe_name(value):
    return value if isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9_.@/-]{1,128}',value) else 'unknown'

def safe_sha(value):
    return value if isinstance(value,str) and re.fullmatch(r'[0-9a-f]{40}',value) else 'unknown'

def safe_address(value):
    if value=='':
        return 'all_interfaces'
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return 'unknown'

def service_info(service):
    ids = run(['docker','ps','-q','--filter',f'label=com.docker.compose.project={PROJECT}',
        '--filter',f'label=com.docker.compose.service={service}']).split()
    if len(ids) != 1:
        return {'running_containers':len(ids)}
    raw = json.loads(run(['docker','inspect',ids[0]]))[0]
    config = raw.get('Config',{})
    env = dict(item.split('=',1) for item in config.get('Env',[]) if '=' in item)
    state = raw.get('State',{})
    ports = raw.get('HostConfig',{}).get('PortBindings') or {}
    result = dict(running_containers=1, running=bool(state.get('Running')),
        health=safe_name(state.get('Health',{}).get('Status','not_configured')),
        source_sha=safe_sha(config.get('Labels',{}).get('org.opencontainers.image.revision')),
        published_ports={safe_name(key):[dict(address=safe_address(p.get('HostIp','')),
            port=safe_name(p.get('HostPort'))) for p in (values or [])] for key,values in ports.items()},
        data_mounts=[dict(destination=m['Destination'],type=safe_name(m.get('Type')),
            volume=safe_name(m.get('Name')),writable=bool(m.get('RW')))
            for m in raw.get('Mounts',[]) if m.get('Destination')=='/app/data'])
    if service=='admin':
        result['production_mode'] = env.get('APP_ENV') in ('prod','production')
        result['internal_token_present'] = bool(env.get('ADMIN_DASHBOARD_TOKEN'))
        result['allowed_clients'] = [safe_name(c.strip()) for c in env.get('ALLOWED_CLIENTS','').split(',') if c.strip()]
        result['postgres_credentials_present'] = bool(env.get('BOT_PG_DSN'))
    if service=='caddy':
        result['admin_login'] = safe_name(env.get('CADDY_ADMIN_BASIC_AUTH_USER'))
        result['password_hash_present'] = bool(env.get('CADDY_ADMIN_BASIC_AUTH_HASH'))
        result['internal_token_present'] = bool(env.get('ADMIN_DASHBOARD_TOKEN'))
    if service=='bot':
        # A literal model ID and booleans only, never provider/SMTP credentials.
        result['model'] = safe_name(env.get('DEFAULT_LLM_MODEL'))
        result['metrics_explicitly_disabled'] = env.get('D2_ADMIN_METRICS_ENABLED')=='0'
    return result

def file_info(path):
    item = Path(path)
    if not item.exists():
        return {'exists':False}
    info = item.stat()
    return {'exists':True,'root_owned':info.st_uid==0,'mode':oct(stat.S_IMODE(info.st_mode))}

def http_status():
    try:
        with urllib.request.urlopen('http://127.0.0.1:9100/', timeout=3) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except Exception:
        return 'unavailable'

def audit():
    report = {'checked_at':datetime.now(timezone.utc).isoformat(),'read_only':True,'services':{}}
    for name in ('bot','admin','caddy'):
        try:
            report['services'][name] = service_info(name)
        except Exception:
            report['services'][name] = {'inspection':'unavailable'}
    report['unauthenticated_admin_http_status'] = http_status()
    report['files'] = {path:file_info(path) for path in (
        '/etc/artgents/production.env','/opt/artgents/bin/deploy-production',
        '/opt/artgents/bin/backup-postgres','/opt/artgents/bin/backup-sqlite')}
    return report

def main():
    if os.geteuid()!=0:
        print('Read-only audit requires sudo; no configuration was changed.')
        return 1
    try:
        print(json.dumps(audit(),ensure_ascii=True,indent=2))
        return 0
    except Exception:
        print('Read-only audit incomplete; no configuration was changed.')
        return 1

if __name__=='__main__':
    raise SystemExit(main())
'@
$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($auditCode))
# Only generated Base64 is interpolated into a fixed remote command.
$remoteCommand = "sudo python3 -c 'import base64,sys;exec(base64.b64decode(sys.argv[1]))' $encoded"
Write-Host "Read-only VPS admin audit. No deploy, restart, email or model request."
Write-Host "Enter the Linux sudo password for deploy when SSH asks; it is not saved by this helper."
& ssh -t -o StrictHostKeyChecking=yes -o ConnectTimeout=10 -i $keyPath deploy@5.129.195.70 $remoteCommand
if ($LASTEXITCODE -ne 0) { throw "Read-only audit did not complete (SSH code $LASTEXITCODE)." }
