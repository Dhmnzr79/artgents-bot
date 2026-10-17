"""Public catalog is complete, tenant-bound and independent of dialogue state."""
import json
import shutil
from datetime import date
from pathlib import Path

import pytest
from core.d2_tenant_snapshot import load_d2_tenant_snapshot
from core.widget_catalog import build_widget_catalog
from core.d2_price_offer import d2_catalog_price_summary
from tests.d2_ci_http import http_env,send
from tests.test_d2_native_price_runtime import Transport,message
from core.d2_live_provider import D2HttpProvider

ROOT=Path(__file__).resolve().parents[1]


def admit_medical(http_env,monkeypatch):
    import config
    shutil.copytree(ROOT/'clients/demo_medical',http_env[3]/'clients/demo_medical')
    monkeypatch.setattr(config,'ALLOWED_CLIENTS',frozenset({'demo','nikadent','demo_medical'}))


@pytest.mark.parametrize('tenant,sections,count',[('demo',5,22),('nikadent',5,27),('demo_medical',10,21)])
def test_catalog_actual_endpoint_is_read_only_and_complete(http_env,monkeypatch,tenant,sections,count):
    if tenant=='demo_medical':admit_medical(http_env,monkeypatch)
    client,db,_,_=http_env
    response=client.get('/api/widget-catalog',query_string={'client_id':tenant})
    assert response.status_code==200
    data=response.get_json()
    assert data['client_id']==tenant and len(data['catalog_version'])==64
    assert len(data['sections'])==sections and len(data['services'])==count
    assert not db.exists()
    refs=[s for section in data['sections'] for s in section['service_ids']]
    assert len(refs)==len(set(refs))==count
    serialized=json.dumps(data,ensure_ascii=False)
    assert 'price_select:' not in serialized and 'ui_revision' not in serialized
    assert 'lead_config' not in serialized and 'recipients' not in serialized
    assert set(refs)=={s['service_id'] for s in data['services']}
    assert data['label'] and all(section['subtitle'] for section in data['sections'])
    authored=json.loads((ROOT/'clients'/tenant/'target_response/widget_catalog.json').read_text(encoding='utf-8'))
    assert {s['service_id']:s['subtitle'] for s in data['services']}==authored['service_subtitles']


def test_catalog_exact_price_and_offer_promo_scope(http_env,monkeypatch):
    admit_medical(http_env,monkeypatch)
    data=http_env[0].get('/api/widget-catalog?client_id=demo_medical').get_json()
    service=next(s for s in data['services'] if s['service_id']=='laser_hair_removal')
    assert service['price']['presentation']=='options'
    rows=service['price']['rows']
    assert [(r['offer_id'],r['amount']) for r in rows]==[
        ('laser_hair_removal.underarms',1900),('laser_hair_removal.legs',4500),('laser_hair_removal.three_zones',7900)]
    special='Только пакет «Три зоны»'
    assert special in json.dumps(service['details']['laser_hair_removal.three_zones'],ensure_ascii=False)
    assert special not in json.dumps(service['details']['laser_hair_removal.underarms'],ensure_ascii=False)
    assert service['price_summary_text']=='от 1\u00a0900\u00a0₽'


@pytest.mark.parametrize('prices,expected',[
    ([],None),
    ([('no_public_price',None,None)],None),
    ([('fixed',35000,None)],'35\u00a0000\u00a0₽'),
    ([('from',35000,None)],'от 35\u00a0000\u00a0₽'),
    ([('range',35000,45000)],'35\u00a0000–45\u00a0000\u00a0₽'),
    ([('fixed',35000,None),('no_public_price',None,None)],'35\u00a0000\u00a0₽'),
    ([('fixed',85000,None),('fixed',76200,None),('fixed',101200,None)],'от 76\u00a0200\u00a0₽'),
    ([('fixed',5000,None),('range',2900,4000),('from',3100,None)],'от 2\u00a0900\u00a0₽'),
    ([('fixed',0,None),('fixed',100,None)],'от 0\u00a0₽'),
])
def test_catalog_price_summary_uses_public_lower_bounds(prices,expected):
    from core.d2_price_offer import build_d2_price_offer_row
    from core.d2_published_offer_terms import build_d2_published_offer_terms
    snapshot=load_d2_tenant_snapshot('demo',clients_root=ROOT/'clients')
    base=next(offer for offer in snapshot.bundle.offers if offer.offer_id=='classic.one_tooth.implantium')
    rows=[]
    for mode,amount,maximum in prices:
        value=dict(mode=mode)
        if mode=='no_public_price':value['approved_text']='Стоимость уточнит администратор'
        else:
            value.update(currency='RUB',billing_unit='implant')
            value['amount' if mode=='fixed' else 'min_amount']=amount
            if mode=='range':value['max_amount']=maximum
        offer=type(base).model_validate({**base.model_dump(mode='json'),'price':value})
        bundle=snapshot.bundle.model_copy(update={'offers':(offer,)})
        rows.append(build_d2_price_offer_row(offer,bundle=bundle,client_id='demo',terms=build_d2_published_offer_terms(offer=offer,source_client_id='demo')))
    assert d2_catalog_price_summary(tuple(rows))==expected


def test_missing_offer_services_remain_visible_without_synthetic_offer(http_env):
    data=http_env[0].get('/api/widget-catalog?client_id=nikadent').get_json()
    unpriced={s['service_id'] for s in data['services'] if s['price'] is None}
    assert unpriced=={'pulpitis','tooth_restoration','teeth_cleaning','periodontitis','ceramic_inlays'}
    assert all(s['details']=={} for s in data['services'] if s['service_id'] in unpriced)
    assert data['unpriced_text']=='Стоимость уточнит администратор'


def test_catalog_authored_groups_preserve_canonical_offers(http_env,monkeypatch):
    admit_medical(http_env,monkeypatch)
    data=http_env[0].get('/api/widget-catalog?client_id=demo_medical').get_json()
    service=next(s for s in data['services'] if s['service_id']=='laser_hair_removal')
    assert data['show_sections'] is True
    groups=service['offer_groups']
    assert [g['title'] for g in groups]==['Отдельные зоны','Комплекс']
    assert [ref for g in groups for ref in g['offer_ids']]==[r['offer_id'] for r in service['price']['rows']]


@pytest.mark.parametrize('fault',['unknown','foreign','duplicate','missing','inactive','inactive_option','unknown_service','empty'])
def test_catalog_groups_reject_noncanonical_members(tmp_path,fault):
    shutil.copytree(ROOT/'clients/demo',tmp_path/'demo')
    path=tmp_path/'demo/target_response/widget_catalog.json'
    data=json.loads(path.read_text(encoding='utf-8'))
    group=data['offer_groups']['classic'][0]
    if fault=='unknown':group['offer_ids'][0]='unknown.offer'
    elif fault=='foreign':group['offer_ids'][0]='all_on_4.jaw.implantium'
    elif fault=='duplicate':group['offer_ids'].append(group['offer_ids'][0])
    elif fault=='missing':group['offer_ids'].pop()
    elif fault=='empty':data['offer_groups']['classic']=[]
    elif fault=='unknown_service':data['offer_groups']['unknown_service']=data['offer_groups'].pop('classic')
    elif fault=='inactive':
        offer_path=tmp_path/'demo/target_response/pricebook/services/classic.one_tooth.implantium.json'
        offer=json.loads(offer_path.read_text(encoding='utf-8'));offer['active']=False
        offer_path.write_text(json.dumps(offer),encoding='utf-8')
    else:
        catalog_path=tmp_path/'demo/target_response/service_catalog.json'
        catalog=json.loads(catalog_path.read_text(encoding='utf-8'))
        catalog['classic']['options']=[{'option_id':'disabled','name':'Disabled','active':False}]
        catalog_path.write_text(json.dumps(catalog),encoding='utf-8')
        offer_path=tmp_path/'demo/target_response/pricebook/services/classic.one_tooth.implantium.json'
        offer=json.loads(offer_path.read_text(encoding='utf-8'));offer['option_id']='disabled'
        offer_path.write_text(json.dumps(offer),encoding='utf-8')
    path.write_text(json.dumps(data),encoding='utf-8')
    from contracts.widget_catalog import WidgetCatalogNavigation
    from core.response_schema_loader import load_response_schema_bundle
    with pytest.raises(ValueError,match='widget_catalog'):
        WidgetCatalogNavigation.model_validate(data).bind('demo',load_response_schema_bundle(tmp_path/'demo/target_response'))


@pytest.mark.parametrize('fault',['foreign','unknown','inactive','duplicate','missing'])
def test_catalog_manifest_invalid_refs_rejected(tmp_path,fault):
    shutil.copytree(ROOT/'clients/demo',tmp_path/'demo')
    path=tmp_path/'demo/target_response/widget_catalog.json';data=json.loads(path.read_text(encoding='utf-8'))
    if fault=='foreign':data['client_id']='nikadent'
    elif fault=='unknown':data['sections'][0]['service_ids'].append('foreign_service')
    elif fault=='inactive':data['sections'][0]['service_ids'].append('braces')
    elif fault=='duplicate':data['sections'][0]['service_ids'].append('caries')
    else:data['sections'][0]['service_ids'].pop()
    path.write_text(json.dumps(data),encoding='utf-8')
    with pytest.raises(ValueError):
        build_widget_catalog(load_d2_tenant_snapshot('demo',clients_root=tmp_path),as_of=date(2026,10,16))


def test_catalog_origin_guard_and_unknown_tenant(http_env):
    client=http_env[0]
    assert client.get('/api/widget-catalog?client_id=unknown').status_code==403
    assert client.get('/api/widget-catalog?client_id=demo',headers={'Origin':'https://foreign.example'}).status_code==403


@pytest.mark.parametrize('fault',['missing','unknown','blank'])
def test_catalog_service_subtitles_must_cover_authored_services(tmp_path,fault):
    shutil.copytree(ROOT/'clients/demo',tmp_path/'demo')
    path=tmp_path/'demo/target_response/widget_catalog.json'
    data=json.loads(path.read_text(encoding='utf-8'))
    if fault=='missing':data['service_subtitles'].pop('classic')
    elif fault=='unknown':data['service_subtitles']['unknown_service']='Подпись'
    else:data['service_subtitles']['classic']='   '
    path.write_text(json.dumps(data),encoding='utf-8')
    with pytest.raises(ValueError,match='widget_catalog_invalid'):
        load_d2_tenant_snapshot('demo',clients_root=tmp_path)


def test_reading_other_catalog_does_not_change_dialogue(http_env):
    from core.d2_dialogue_store import D2DialogueStore
    from contracts.response_plan import SessionKey
    client,db,use,_=http_env
    wire=Transport(message('Здравствуйте!'),message('Продолжение.'));use(D2HttpProvider(transport=wire))
    send(client,request_id='first')
    with D2DialogueStore(db) as store:before=store.read(SessionKey(client_id='demo',sid='cp6a'))
    assert client.get('/api/widget-catalog?client_id=nikadent').status_code==200
    assert client.get('/api/widget-catalog?client_id=demo').status_code==200
    with D2DialogueStore(db) as store:assert store.read(SessionKey(client_id='demo',sid='cp6a'))==before
    assert len(wire.calls)==1
