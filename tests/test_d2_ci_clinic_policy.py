"""Clinic policy authority on current D2, never the retired D1 envelope."""
import pytest
import yaml

from tests.d2_ci_http import FakeProvider, http_env, send, click, raw, explanation
from session import session_client_scope, mem_get


@pytest.mark.parametrize('transport', ['json', 'sse'])
@pytest.mark.parametrize('policy_id', ['no_oms', 'no_dms', 'no_pediatric_dentistry'])
def test_policy_answer_uses_tenant_rule_and_remembers_effect(http_env, transport, policy_id):
    client, _, use, tmp = http_env
    fake = use(FakeProvider(raw({'kind':'clinic_policy','request_id':'r1','policy_ids':[policy_id]})))
    rules = yaml.safe_load((tmp/'clients/demo/clinic_policies.yaml').read_text(encoding='utf-8'))['policies']
    body = send(client, transport, request_id='policy', q='Вопрос о правилах клиники')
    assert rules[policy_id]['answer'].strip() in body['answer']
    other = 'no_oms' if policy_id != 'no_oms' else 'no_pediatric_dentistry'
    assert rules[other]['answer'].strip() not in body['answer']
    assert send(client, transport, request_id='policy', q='Вопрос о правилах клиники') == body
    assert len(fake.inputs) == 1
    if policy_id == 'no_pediatric_dentistry':
        assert not any(b['action_kind'] == 'cta' for b in body['ui']['buttons'])
        with session_client_scope('demo'):
            assert mem_get('cp6a')['lead_intent'] == 'none'
    fake.raw = raw(explanation('Продолжаем разговор.'))
    send(client, transport, request_id='next', q='Расскажите ещё')
    assert policy_id in fake.inputs[-1].context.ordinary.dialogue_pairs[-1].policy_ids
    assert len(fake.inputs) == 2


@pytest.mark.parametrize('transport', ['json', 'sse'])
def test_oms_information_does_not_forbid_paid_consultation(http_env, transport):
    client, _, use, _ = http_env
    fake = use(FakeProvider(raw({'kind':'clinic_policy','request_id':'r1','policy_ids':['no_oms']})))
    body = send(client, transport, request_id='oms', q='Работаете по ОМС?')
    button = next(b for b in body['ui']['buttons'] if b['action_kind'] == 'cta')
    click(client, body, 'button:'+button['button_id'], request_id='book', transport=transport)
    with session_client_scope('demo'):
        assert mem_get('cp6a')['lead_intent'] == 'collecting_name'
    assert len(fake.inputs) == 1


@pytest.mark.parametrize('transport', ['json', 'sse'])
def test_unoffered_braces_uses_approved_alternative_not_model_claim(http_env, transport):
    client, _, use, tmp = http_env
    fake = use(FakeProvider(raw(explanation('Брекеты доступны за один рубль.',
        target={'type':'service','id':'braces'}))))
    rules = yaml.safe_load((tmp/'clients/demo/clinic_policies.yaml').read_text(encoding='utf-8'))
    approved = next(r['approved_text'] for r in rules['service_alternatives'] if r.get('requested_service_id') == 'braces')
    body = send(client, transport, q='Устанавливаете брекеты?')
    assert approved.strip() in body['answer']
    assert 'элайнеры' in body['answer'].lower()
    assert 'один рубль' not in body['answer'] and 'Брекеты доступны' not in body['answer']
    assert len(fake.inputs) == 1
