"""One D2 catalog/price projection for dental and medical packs; offline only."""
from copy import deepcopy
import json
import logging
from pathlib import Path
import shutil

import pytest
from pydantic import ValidationError

from contracts.response_plan import SessionKey
from contracts.response_plan_materialization import MaterializationContractError, MaterializationOwnershipError
from contracts.response_schema import TargetService, TargetFixedPrice
from core.d2_price_offer import build_d2_price_offer_row
from core.d2_published_offer_terms import build_d2_published_offer_terms
from core.d2_tenant_snapshot import build_d2_model_view, load_d2_tenant_snapshot
from core.d2_dialogue_store import D2DialogueStore
from scripts.validate_client_pack import validate_client_pack
from tests.test_d2_http_contract import http_env, post, post_sse
from tests.test_d2_document_click_task_http import _body
from core.d2_live_provider import D2HttpProvider
from tests.test_d2_native_price_runtime import Transport, message

ROOT = Path(__file__).resolve().parents[1]
MEDICAL = ROOT / 'clients/demo_medical'


def snapshot(cid='demo_medical', root=ROOT / 'clients'):
    return load_d2_tenant_snapshot(cid, clients_root=root)


def project(snap, offer):
    return build_d2_price_offer_row(offer, bundle=snap.bundle, client_id=snap.client_id,
        terms=build_d2_published_offer_terms(offer=offer, source_client_id=snap.client_id))


@pytest.mark.parametrize('cid,count', [('demo',33),('nikadent',26),('demo_medical',45),('_template',1)])
def test_current_catalog_and_validator_share_pack_without_legacy_files(cid, count):
    snap = snapshot(cid)
    view = build_d2_model_view(snap)
    assert len(snap.bundle.offers) == count
    assert len(view.published_terms) == count
    assert validate_client_pack(ROOT / 'clients' / cid) == []


@pytest.mark.parametrize('offer_id', sorted(path.stem for path in (MEDICAL/'target_response/pricebook/services').glob('*.json')))
def test_every_medical_offer_preserves_canonical_price_scope_and_details(offer_id):
    snap = snapshot()
    offer = next(item for item in snap.bundle.offers if item.offer_id == offer_id)
    before = deepcopy(snap.bundle.model_dump())
    row = project(snap, offer)
    assert row.offer_id == offer.offer_id and row.service_id == offer.service_id
    assert row.mode == offer.price.mode
    assert row.includes == tuple(offer.package.includes)
    assert row.excludes == tuple(offer.package.excludes)
    assert len(row.stages) == len(offer.payment_stages or ())
    if row.mode == 'no_public_price':
        assert row.price_display_text == offer.price.approved_text
    else:
        assert row.billing_unit == offer.price.billing_unit
        assert row.scope_text == offer.package.label.split(';',1)[0].strip()
        for field in ('amount','min_amount','max_amount'):
            assert getattr(row,field) == getattr(offer.price,field,None)
    for condition in (offer.required_conditions_metadata.conditions if offer.required_conditions_metadata else ()):
        assert condition.display_text in row.condition_texts or condition.display_text == row.scope_text
    assert snap.bundle.model_dump() == before


@pytest.mark.parametrize('mode,price_data,text', [
    ('fixed',{'amount':4100},'4\u00a0100'),
    ('from',{'min_amount':4100},'от 4\u00a0100'),
    ('range',{'min_amount':4100,'max_amount':6200},'4\u00a0100–6\u00a0200'),
])
def test_new_family_and_unit_use_authored_scope_without_legacy_dictionary(mode,price_data,text):
    snap = snapshot()
    payload = snap.bundle.model_dump()
    payload['services']['ent_consultation']['family'] = 'new_clinic_specialty'
    offer = next(item for item in payload['offers'] if item['offer_id']=='ent_consultation.primary')
    offer['price'] = dict(mode=mode,currency='RUB',billing_unit='new_clinic_unit',**price_data)
    offer['package']['label'] = 'за выбранный комплекс'
    offer['package']['price_scope_label'] = 'в рамках одного визита'
    bundle = type(snap.bundle).model_validate(payload)
    authored = next(item for item in bundle.offers if item.offer_id == offer['offer_id'])
    terms = build_d2_published_offer_terms(offer=authored,source_client_id=snap.client_id)
    assert 'в рамках одного визита' in terms.condition_texts
    row = build_d2_price_offer_row(authored,bundle=bundle,client_id=snap.client_id,terms=terms)
    assert row.billing_unit == 'new_clinic_unit'
    assert row.scope_text == 'за выбранный комплекс' and text in row.price_display_text


@pytest.mark.parametrize('value',['', '   ', None, 42])
def test_open_taxonomy_still_rejects_invalid_identifiers(value):
    with pytest.raises(ValidationError):
        TargetService(name='Visit',family=value,selection={'mode':'direct'})
    with pytest.raises(ValidationError):
        TargetFixedPrice(mode='fixed',amount=100,currency='RUB',billing_unit=value)


@pytest.mark.parametrize('fault',['foreign_offer','altered_price','foreign_terms','wrong_terms_offer','forged_terms','inactive_option'])
def test_shared_projection_rejects_noncanonical_or_foreign_inputs(fault):
    snap = snapshot()
    offer = next(item for item in snap.bundle.offers if item.offer_id=='ent_consultation.primary')
    terms = build_d2_published_offer_terms(offer=offer,source_client_id=snap.client_id)
    bundle = snap.bundle
    if fault == 'foreign_offer':
        offer = snapshot('demo').bundle.offers[0]
    elif fault == 'altered_price':
        offer = offer.model_copy(update={'price':offer.price.model_copy(update={'amount':1})})
    elif fault == 'foreign_terms':
        terms = terms.model_copy(update={'source_client_id':'another_clinic'})
    elif fault == 'wrong_terms_offer':
        terms = terms.model_copy(update={'offer_id':'ent_consultation.repeat'})
    elif fault == 'forged_terms':
        terms = terms.model_copy(update={'package_label':'all treatment included'})
    else:
        bundle = deepcopy(bundle)
        next(item for item in bundle.services[offer.service_id].options if item.option_id==offer.option_id).active = False
    with pytest.raises((MaterializationContractError,MaterializationOwnershipError)):
        build_d2_price_offer_row(offer,bundle=bundle,client_id=snap.client_id,terms=terms)


@pytest.mark.parametrize('fault',['tenant','commercial_ref','service_doc','fact_anchor','invalid_commercial'])
def test_validator_checks_current_d2_graph(tmp_path,fault):
    pack = tmp_path/'demo_medical'
    shutil.copytree(MEDICAL,pack)
    target = pack/'target_response'
    path = target/'d2_commercial.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    if fault == 'tenant':
        data['client_id'] = 'another_clinic'
    elif fault == 'commercial_ref':
        data['service_profiles'][0]['price_booster_id'] = 'missing'
    elif fault == 'service_doc':
        path = target/'service_catalog.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data['ent_consultation']['content_ref'] = '../another_clinic/private.md'
    elif fault == 'fact_anchor':
        path = target/'pricebook/facts.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        next(iter(data.values()))['detail_ref'] = 'clinic__info__about.md#missing'
    if fault == 'invalid_commercial':
        path.write_text('{broken',encoding='utf-8')
    else:
        path.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    assert validate_client_pack(pack)


def test_legacy_yaml_neither_required_nor_a_d2_authority(tmp_path):
    pack = tmp_path/'demo_medical'
    shutil.copytree(MEDICAL,pack)
    before = snapshot(root=tmp_path)
    for name in ['marketing.yaml','clinic_strategy.yaml']:
        (pack/'target_response'/name).write_text('invalid: [',encoding='utf-8')
    after = snapshot(root=tmp_path)
    assert before.fingerprint == after.fingerprint
    assert build_d2_model_view(before) == build_d2_model_view(after)
    assert validate_client_pack(pack) == []


@pytest.mark.parametrize('transport',['json','sse'])
@pytest.mark.parametrize('service',['ent_consultation','biorevitalization','ultrasound_lifting','botulinum_therapy'])
def test_medical_prices_use_actual_http_frozen_path_and_replay_without_new_registry(http_env,monkeypatch,transport,service):
    client, db, use, tmp = http_env
    shutil.copytree(MEDICAL,tmp/'clients/demo_medical')
    import config
    monkeypatch.setattr(config,'ALLOWED_CLIENTS',frozenset({'demo','nikadent','demo_medical'}))
    wire = Transport(
        message(None, {'target':{'type':'service','id':service}}),
        message('<NO_TEXT>'),
        message('Подготовку обсудит врач.'),
    )
    use(D2HttpProvider(transport=wire))
    send = post if transport=='json' else post_sse
    args = dict(client_id='demo_medical',sid='medical',request_id='price',q='Какая стоимость услуги?')
    response = send(client,**args)
    assert response.status_code == 200
    body = _body(response,transport)
    snap = snapshot(root=tmp/'clients')
    with D2DialogueStore(db) as store:
        result = store.read_latest_completion(SessionKey(client_id='demo_medical',sid='medical')).response.resolved
        rows = result.d2_price_block.rows
        # Stage 1 preserves the current selected-first card behavior. The next
        # UX stage will expose the variant list before opening its details.
        expected = {o.offer_id for o in snap.bundle.offers if o.service_id==service}
        assert len(rows) == 1 and rows[0].offer_id in expected
        assert {action.offer_id for action in result.ui_plan.price_select_actions} == expected
        for row in rows:
            offer = next(o for o in snap.bundle.offers if o.offer_id==row.offer_id)
            assert row == project(snap,offer)
        assert store.read(SessionKey(client_id='demo',sid='medical')) is None
    assert _body(send(client,**args),transport) == body and len(wire.calls) == 2
    follow = send(client,client_id='demo_medical',sid='medical',request_id='next',q='А как подготовиться?')
    assert follow.status_code == 200
    history = wire.calls[-1]['messages'][1]['content']
    assert service in history and 'demo_medical' in history and len(wire.calls) == 3
    context = json.loads(history.split('=== D2_SESSION_CONTEXT ===\n')[1].split('\n\n===')[0])
    assert context['ordinary']['discussion_scope']['target']['id'] == service


@pytest.mark.parametrize('env',['local','prod'])
@pytest.mark.parametrize('fault',['invalid_commercial','service_ref','fact_ref'])
def test_startup_and_registry_use_configured_root_and_current_loader(tmp_path,monkeypatch,env,fault):
    import config
    import core.startup_check as startup
    from core.prod_readiness import evaluate_allowed_client_registry
    shutil.copytree(MEDICAL,tmp_path/'demo_medical')
    monkeypatch.setenv('D2_CLIENTS_ROOT',str(tmp_path))
    monkeypatch.setattr(config,'ALLOWED_CLIENTS',frozenset({'demo_medical'}))
    monkeypatch.setattr(config,'DEFAULT_CLIENT_ID','demo_medical')
    monkeypatch.setattr(startup,'ALLOWED_CLIENTS',config.ALLOWED_CLIENTS)
    monkeypatch.setattr(startup,'APP_ENV',env)
    assert evaluate_allowed_client_registry() == []
    startup.run_startup_check(logging.getLogger('test'))
    target = tmp_path/'demo_medical/target_response'
    if fault == 'invalid_commercial':
        (target/'d2_commercial.json').write_text('{broken',encoding='utf-8')
    else:
        path = target/('service_catalog.json' if fault=='service_ref' else 'pricebook/facts.json')
        data = json.loads(path.read_text(encoding='utf-8'))
        if fault=='service_ref':
            data['ent_consultation']['content_ref'] = 'missing.md'
        else:
            next(iter(data.values()))['detail_ref'] = 'missing.md#missing'
        path.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    assert evaluate_allowed_client_registry() == ['allowed_client_pack_invalid:demo_medical']
    with pytest.raises(SystemExit):
        startup.run_startup_check(logging.getLogger('test'))


@pytest.mark.parametrize('tenant',['default','_template','../demo_medical','missing'])
def test_registry_still_rejects_forbidden_escaping_and_missing_packs(tmp_path,monkeypatch,tenant):
    import config
    from core.prod_readiness import evaluate_allowed_client_registry
    monkeypatch.setenv('D2_CLIENTS_ROOT',str(tmp_path))
    monkeypatch.setattr(config,'ALLOWED_CLIENTS',frozenset({tenant}))
    monkeypatch.setattr(config,'DEFAULT_CLIENT_ID',tenant)
    assert evaluate_allowed_client_registry()


@pytest.mark.parametrize('topic', ['implantation','restoration','prosthetics'])
@pytest.mark.parametrize('count', [1,3])
@pytest.mark.parametrize('transport', ['json','sse'])
def test_dental_extent_and_count_still_filter_without_price_multiplication(http_env,topic,count,transport):
    client,db,use,_ = http_env
    volume = {'extent':'one_tooth' if count==1 else 'few_teeth','tooth_count':count,'jaw':'unknown'}
    wire = Transport(message(None, {'target':{'type':'topic','id':topic},'volume':volume}),message('<NO_TEXT>'))
    use(D2HttpProvider(transport=wire))
    send = post if transport=='json' else post_sse
    body = _body(send(client,q='Стоимость восстановления зубов?'),transport)
    with D2DialogueStore(db) as store:
        result = store.read_latest_completion(SessionKey(client_id='demo',sid='cp6a')).response.resolved
        expected = {
            ('implantation',1): ('classic.one_tooth.implantium','one_stage.one_tooth.implantium'),
            ('implantation',3): ('classic.one_tooth.implantium','one_stage.one_tooth.implantium'),
            ('restoration',1): ('classic.one_tooth.implantium','zirconia_crowns.default'),
            ('restoration',3): ('classic.one_tooth.implantium','removable_dentures.jaw.partial','zirconia_crowns.default'),
            ('prosthetics',1): ('zirconia_crowns.default','implant_supported_prosthetics.default'),
            ('prosthetics',3): ('zirconia_crowns.default','removable_dentures.jaw.partial','clasp_dentures.default'),
        }[topic,count]
        assert tuple(row.offer_id for row in result.d2_price_block.rows) == expected
        baseline_prices = {
            'classic.one_tooth.implantium':'76\u00a0200\u00a0₽',
            'one_stage.one_tooth.implantium':'86\u00a0500\u00a0₽',
            'zirconia_crowns.default':'от 25\u00a0000\u00a0₽',
            'implant_supported_prosthetics.default':'от 31\u00a0000\u00a0₽',
            'removable_dentures.jaw.partial':'45\u00a0000\u00a0₽',
            'clasp_dentures.default':'от 85\u00a0000\u00a0₽',
        }
        # Recorded independently against clean origin/main f762949 using the
        # same native tool/volume inputs, rather than an obsolete JSON helper.
        assert tuple(row.price_display_text for row in result.d2_price_block.rows) == tuple(baseline_prices[offer_id] for offer_id in expected)
        assert result.d2_request_parts[0].discussion_scope.volume.tooth_count == count
    assert '228 600' not in body['answer'].replace('\u00a0',' ')
    assert len(wire.calls) == 2
