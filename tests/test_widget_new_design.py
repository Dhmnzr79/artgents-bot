"""Theme presentation contracts and real UI behavior, with offline HTTP fixtures only."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from contracts.widget_config import validate_widget_presentation_document, WidgetConfigValidationError
from tests.d2_ci_http import http_env, send, click
from tests.test_nikadent_price_authority_offline import native, request
from tests.test_widget_catalog import admit_medical
from tests.test_d2_price_cards_browser import RUNNER

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('tenant,design,brand', [
    ('demo', 'aura', '#0C2FE0'), ('demo_medical', 'orbit', '#196E76'), ('nikadent', 'orbit', '#762E94'),
])
def test_client_design_and_authored_icons(tenant, design, brand):
    from core.client_config_loader import load_widget_presentation_v1, merge_widget_brand_presentation
    presentation = load_widget_presentation_v1(tenant)
    assert presentation['design'] == design
    assert presentation['onlineLabel'] == 'сейчас онлайн'
    assert all(item['iconKey'] for item in presentation['starterPrompts'])
    public = merge_widget_brand_presentation(tenant, presentation)
    assert public['theme']['brand'].upper() == brand.upper()


@pytest.mark.parametrize('field,value', [('design', 'other'), ('iconKey', 'invented')])
def test_unknown_presentation_values_rejected(field, value):
    raw = json.loads((ROOT / 'clients/demo/widget_config.json').read_text(encoding='utf-8'))
    if field == 'design': raw[field] = value
    else: raw['starterPrompts'][0][field] = value
    with pytest.raises(WidgetConfigValidationError):
        validate_widget_presentation_document(raw, client_id='demo')


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows Chrome offline UI proof')
def test_three_themes_mobile_layout_and_clear_private_context(http_env, monkeypatch, tmp_path):
    admit_medical(http_env, monkeypatch)
    client = http_env[0]
    fixtures = []
    for tenant in ['demo', 'demo_medical', 'nikadent']:
        fixtures.append(dict(
            config=client.get('/api/widget-config', query_string={'client_id': tenant}).get_json(),
            catalog=client.get('/api/widget-catalog', query_string={'client_id': tenant}).get_json(),
            definition=client.get('/api/booking-form', query_string={'client_id': tenant}).get_json(),
        ))
    # Current native HTTP receipts and the actions actually published at each revision.
    # The old FakeProvider browser fixtures no longer publish authorised refs.
    for fixture in fixtures:
        tenant = fixture['config']['clientId']
        if tenant == 'demo_medical': continue
        topic = 'implantation' if tenant == 'demo' else 'prosthetics'
        sid = 'new-design-' + tenant
        wire = native(http_env[2], request(topic, topic=True))
        initial = send(client, client_id=tenant, sid=sid, request_id='initial', q='Сколько стоит лечение?')
        responses = {'initial': initial}
        previous = initial
        for extent in ['one_tooth', 'full_arch', 'unknown']:
            ref = f'volume:{topic}:{extent}'
            responses[ref] = click(client, previous, ref, request_id=extent, client_id=tenant, sid=sid)
            previous = responses[ref]
        assert len(wire.calls) == 2
        fixture['dialogue'] = responses
    payload = tmp_path / 'design-fixtures.json'
    payload.write_text(json.dumps(fixtures, ensure_ascii=False), encoding='utf-8')
    runner = RUNNER.split('  await page.evaluate(async fixtures => {', 1)[0]
    runner += (ROOT / 'tests/js/widget_new_design_harness.mjs').read_text(encoding='utf-8')
    result = subprocess.run(['node', '--input-type=module', '-'], input=runner, cwd=ROOT,
        env={**os.environ, 'CARDS_PAYLOADS': str(payload)}, text=True, encoding='utf-8',
        capture_output=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"tenants":3' in result.stdout
    assert '"provider":0' in result.stdout
