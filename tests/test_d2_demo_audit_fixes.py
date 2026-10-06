"""Final demo audit: policy action survives assembly; details retain selectors."""
import json
import pytest

from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from session import mem_get, session_client_scope
from tests.test_d2_http_contract import FakeProvider, http_env, post, post_sse
from tests.test_d2_document_click_task_http import _body
from tests.test_d2_sim2_dialogues import raw, price, explanation


def detail(brand=None, **extra):
    return {'kind': 'price_detail', 'request_id': 'r1',
            'target': {'type': 'service', 'id': 'all_on_4'},
            'price_detail_aspect': 'stages', **({'brand_id': brand} if brand else {}), **extra}


def saved(db, sid='cp6a'):
    with D2DialogueStore(db) as store:
        return store.read_latest_completion(SessionKey(client_id='demo', sid=sid))


def ctas(body):
    return [b for b in body['ui']['buttons'] if b['action_kind'] == 'cta']


@pytest.mark.parametrize('transport', ['json', 'sse'])
@pytest.mark.parametrize('kind', ['price', 'policy', 'mixed'])
def test_child_refusal_has_no_booking_action_and_forged_click_cannot_start_lead(http_env, transport, kind):
    client, db, use, _ = http_env
    child_price = price('caries', 'service', age_group='child', context='current_care')
    policy = {'kind': 'clinic_policy', 'request_id': 'r1',
              'policy_ids': ['no_pediatric_dentistry'], 'age_group': 'child', 'context': 'current_care'}
    blocks = [policy if kind == 'policy' else child_price]
    if kind == 'mixed':
        blocks.append(explanation('Расскажем о клинике.', request_id='r2'))
    fake = use(FakeProvider(raw(*blocks)))
    send = post if transport == 'json' else post_sse
    body = _body(send(client, q='Сколько стоит лечение ребёнку?'), transport)
    assert 'только со взрослыми' in body['answer']
    assert not ctas(body)
    assert saved(db).response.resolved.d2_price_block is None
    assert saved(db).response.resolved.textual_cta_block is None
    assert _body(send(client, q='Сколько стоит лечение ребёнку?'), transport) == body
    rejected = send(client, q='', request_id='forged', ref='button:default_consult', ui_revision=body['revision'])
    if transport == 'json':
        assert rejected.status_code != 200
    else:
        from tests.test_d2_http_contract import sse_events
        assert 'error' in dict(sse_events(rejected))
    with session_client_scope('demo'):
        assert mem_get('cp6a')['lead_intent'] not in {'collecting_name', 'collecting_phone'}
    assert len(fake.inputs) == 1
    fake.raw = raw(price('caries', 'service', age_group='adult'))
    adult = _body(send(client, request_id='adult', q='А лечение для взрослого?'), transport)
    assert ctas(adult) and saved(db).response.resolved.d2_price_block is not None


@pytest.mark.parametrize('transport', ['json', 'sse'])
def test_payment_policy_does_not_forbid_paid_adult_booking(http_env, transport):
    client, _, use, _ = http_env
    use(FakeProvider(raw({'kind':'clinic_policy', 'request_id':'r1', 'policy_ids':['no_oms']})))
    body = _body((post if transport == 'json' else post_sse)(client, q='Работаете по ОМС?'), transport)
    assert ctas(body)


@pytest.mark.parametrize('transport', ['json', 'sse'])
@pytest.mark.parametrize('history', [None, 'all', 'implantium'])
def test_explicit_brand_details_override_previous_set_and_keep_next_context(http_env, transport, history):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(detail('nobel_biocare'))))
    send = post if transport == 'json' else post_sse
    if history:
        fake.raw = raw(price('all_on_4', 'service', **({'brand_id':history} if history != 'all' else {})))
        _body(send(client, request_id='price', q='Сколько стоит All-on-4?'), transport)
        fake.raw = raw(detail('nobel_biocare'))
    args = dict(request_id='details', q='Какие этапы оплаты All-on-4 Nobel?')
    body = _body(send(client, **args), transport)
    rows = saved(db).response.resolved.d2_price_detail_block.rows
    assert [r.offer_id for r in rows] == ['all_on_4.jaw.nobel']
    assert '256' in body['answer'] and '171' in body['answer']
    assert 'Implantium' not in body['answer'] and 'Impro' not in body['answer']
    calls = len(fake.inputs)
    assert _body(send(client, **args), transport) == body
    assert len(fake.inputs) == calls
    fake.raw = raw(explanation('О сроках лечения.'))
    _body(send(client, request_id='next', q='А сроки лечения?'), transport)
    assert fake.inputs[-1].context.ordinary.discussion_scope.brand_id == 'nobel_biocare'


@pytest.mark.parametrize('transport', ['json', 'sse'])
def test_unfiltered_details_and_verified_click_keep_all_displayed_offers(http_env, transport):
    client, db, use, tmp = http_env
    config = tmp/'clients/demo/target_response/d2_commercial.json'
    catalog = json.loads(config.read_text(encoding='utf-8'))
    catalog['service_profiles'].append({'service_id':'all_on_4', 'price_detail_ids':['includes','stages']})
    config.write_text(json.dumps(catalog, ensure_ascii=False), encoding='utf-8')
    fake = use(FakeProvider(raw(detail())))
    send = post if transport == 'json' else post_sse
    _body(send(client, request_id='direct', q='Этапы оплаты All-on-4?'), transport)
    expected = {'all_on_4.jaw.impro','all_on_4.jaw.implantium','all_on_4.jaw.nobel'}
    assert {r.offer_id for r in saved(db).response.resolved.d2_price_detail_block.rows} == expected
    fake.raw = raw(price('all_on_4', 'service'))
    priced = _body(send(client, sid='click-sid', request_id='price', q='Сколько стоит All-on-4?'), transport)
    calls = len(fake.inputs)
    args = dict(sid='click-sid', request_id='click', q='', ref='price_detail:stages', ui_revision=priced['revision'])
    clicked = _body(send(client, **args), transport)
    assert {r.offer_id for r in saved(db, 'click-sid').response.resolved.d2_price_detail_block.rows} == expected
    assert len(fake.inputs) == calls
    assert _body(send(client, **args), transport) == clicked
    assert 'Этапы оплаты' not in [q['label'] for q in clicked['ui']['quick_replies']]


@pytest.mark.parametrize('transport', ['json', 'sse'])
def test_missing_brand_offers_publish_gap_not_other_brands(http_env, transport):
    client, db, use, tmp = http_env
    path = tmp/'clients/demo/target_response/pricebook/services/all_on_4.jaw.nobel.json'
    offer = json.loads(path.read_text(encoding='utf-8'))
    offer['active'] = False
    path.write_text(json.dumps(offer, ensure_ascii=False), encoding='utf-8')
    config = tmp/'clients/demo/target_response/d2_direction_prices.json'
    catalog = json.loads(config.read_text(encoding='utf-8'))
    for direction in catalog['directions']:
        direction['offer_ids'] = [i for i in direction['offer_ids'] if i != 'all_on_4.jaw.nobel']
    config.write_text(json.dumps(catalog, ensure_ascii=False), encoding='utf-8')
    use(FakeProvider(raw(detail('nobel_biocare'))))
    body = _body((post if transport == 'json' else post_sse)(client, q='Этапы оплаты All-on-4 Nobel?'), transport)
    assert 'детали не указаны' in body['answer']
    assert saved(db).response.resolved.d2_price_detail_block is None


@pytest.mark.parametrize('transport', ['json', 'sse'])
def test_explicit_offer_cannot_conflict_with_brand(http_env, transport):
    client, _, use, _ = http_env
    use(FakeProvider(raw(detail('nobel_biocare', price_detail_offer_id='all_on_4.jaw.impro'))))
    response = (post if transport == 'json' else post_sse)(client, q='Этапы Nobel?')
    if transport == 'json':
        assert response.status_code != 200
    else:
        from tests.test_d2_http_contract import sse_events
        assert 'error' in dict(sse_events(response))


@pytest.mark.parametrize('extent', ['full_arch', 'one_tooth'])
def test_detail_uses_same_extent_applicability_as_price(http_env, extent):
    client, db, use, _ = http_env
    use(FakeProvider(raw(detail('nobel_biocare', volume={'extent':extent}))))
    body = _body(post(client, q='Этапы оплаты выбранного объёма Nobel?'), 'json')
    block = saved(db).response.resolved.d2_price_detail_block
    if extent == 'full_arch':
        assert [r.offer_id for r in block.rows] == ['all_on_4.jaw.nobel']
    else:
        assert block is None and 'детали не указаны' in body['answer']
