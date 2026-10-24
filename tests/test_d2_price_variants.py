"""One native price path for all tenants: options, exact detail, frozen replay."""
import json
import shutil
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from contracts.response_plan import SessionKey
from contracts.response_schema import ResponseDataCatalog
from core.d2_dialogue_store import D2DialogueStore
from core.d2_live_provider import D2HttpProvider
from core.d2_tenant_snapshot import load_d2_tenant_snapshot, build_d2_model_view
from core.d2_commercial_plan import resolve_d2_commercial_plan
from core.d2_snapshot_sources import _commercial_authority
from tests.d2_ci_http import http_env, send, click
from tests.test_d2_http_contract import post
from tests.test_d2_native_price_runtime import Transport, message
from tests.test_d2_price_cards import cards

ROOT = Path(__file__).resolve().parents[1]


def medical(http_env, monkeypatch):
    _, _, _, tmp = http_env
    shutil.copytree(ROOT/'clients/demo_medical', tmp/'clients/demo_medical')
    import config
    monkeypatch.setattr(config, 'ALLOWED_CLIENTS', frozenset({'demo','demo_medical','nikadent'}))


def saved(db, tenant):
    with D2DialogueStore(db) as store:
        return store.read_latest_completion(SessionKey(client_id=tenant, sid='variants')).response.resolved


def native(use, service, *, needs_completion=False, **fields):
    replies = [message(None, {'target':{'type':'service','id':service}, **fields})]
    if needs_completion:
        replies.append(message('<NO_TEXT>'))
    wire = Transport(*replies, message('Подготовку обсудит врач.'))
    use(D2HttpProvider(transport=wire))
    return wire


@pytest.mark.parametrize('transport', ['json','sse'])
@pytest.mark.parametrize('tenant,service,expected,chosen', [
    ('demo','classic', {'classic.one_tooth.implantium','classic.one_tooth.impro','classic.one_tooth.nobel'}, 'classic.one_tooth.nobel'),
    ('demo_medical','ent_consultation', {'ent_consultation.primary','ent_consultation.repeat'}, 'ent_consultation.repeat'),
    ('nikadent','removable_dentures', {'removable_dentures.jaw.partial','removable_dentures.jaw.full','removable_dentures.jaw.acry_free','removable_dentures.jaw.nylon'}, 'removable_dentures.jaw.nylon'),
])
def test_options_click_replay_and_next_scope(http_env, monkeypatch, transport, tenant, service, expected, chosen):
    if tenant == 'demo_medical':
        medical(http_env, monkeypatch)
    client, db, use, _ = http_env
    wire = native(use, service)
    args = dict(client_id=tenant, sid='variants')
    body = send(client, transport, **args, request_id='list', q='Стоимость?')
    card = cards(body)[0]
    assert card['price']['presentation'] == 'options'
    assert {r['offer_id'] for r in card['price']['rows']} == expected
    assert {q['reply_id'].removeprefix('price_select:') for q in card['choices']} == expected
    assert saved(db, tenant).d2_request_parts[0].discussion_scope.brand_id is None
    assert not saved(db, tenant).d2_price_booster_block
    assert not saved(db, tenant).promo_blocks
    assert [r.model_dump(mode='json') for r in saved(db, tenant).d2_price_block.rows] == card['price']['rows']
    assert len(wire.calls) == 1
    # A fabricated offer ref is never allowed to select a row or call the model.
    rejected = post(client, **args, request_id='forged', q='',
                    ref='price_select:foreign.offer', ui_revision=body['revision'])
    assert rejected.status_code == 400
    assert saved(db, tenant).d2_price_block.presentation == 'options'
    detail = click(client, body, 'price_select:'+chosen, **args, transport=transport, request_id='click')
    assert cards(detail)[0]['price']['presentation'] == 'detail'
    assert [r['offer_id'] for r in cards(detail)[0]['price']['rows']] == [chosen]
    assert len(wire.calls) == 1
    chosen_scope = next(p.discussion_scope for p in saved(db, tenant).d2_request_parts if p.kind == 'price')
    assert click(client, body, 'price_select:'+chosen, **args, transport=transport, request_id='click') == detail
    send(client, transport, **args, request_id='follow', q='А подготовка?')
    history = wire.calls[-1]['messages'][1]['content']
    assert chosen in history
    context = json.loads(history.split('=== D2_SESSION_CONTEXT ===\n')[1].split('\n\n===')[0])
    scope = context['ordinary']['discussion_scope']
    assert scope['target'] == {'type':'service','id':service}
    assert scope['brand_id'] == chosen_scope.brand_id
    assert len(wire.calls) == 2


@pytest.mark.parametrize('option,expected', [('repeat','ent_consultation.repeat'), ('primary','ent_consultation.primary')])
def test_precise_medical_option_opens_detail(http_env, monkeypatch, option, expected):
    medical(http_env, monkeypatch)
    client, db, use, _ = http_env
    wire = native(use, 'ent_consultation', option_id=option)
    body = send(client, client_id='demo_medical', sid='variants')
    assert cards(body)[0]['price']['presentation'] == 'detail'
    assert [r['offer_id'] for r in cards(body)[0]['price']['rows']] == [expected]
    assert len(wire.calls) == 1


def test_one_option_with_several_brands_does_not_choose_first(http_env):
    client, db, use, tmp = http_env
    snapshot = load_d2_tenant_snapshot('demo', clients_root=tmp/'clients')
    offers = [o for o in snapshot.bundle.offers if o.service_id=='classic']
    assert len({o.option_id for o in offers}) == 1
    wire = native(use, 'classic', option_id=offers[0].option_id) if offers[0].option_id else native(use, 'classic')
    body = send(client, sid='variants')
    assert cards(body)[0]['price']['presentation'] == 'options'
    assert {r['offer_id'] for r in cards(body)[0]['price']['rows']} == {o.offer_id for o in offers}
    assert saved(db, 'demo').d2_request_parts[0].discussion_scope.brand_id is None
    assert len(wire.calls) == 1


def test_single_representative_topic_is_still_options(http_env):
    client, _, use, tmp = http_env
    path = tmp/'clients/demo/target_response/d2_direction_prices.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    # Keep the authored direction and scope; reduce only its preview pool.
    def narrow(value):
        if isinstance(value, dict):
            if value.get('topic_id') == 'implantation':
                value['offer_ids'] = ['classic.one_tooth.implantium']
                value['service_ids'] = ['classic']
            for child in value.values():
                narrow(child)
        elif isinstance(value, list):
            for child in value:
                narrow(child)
    narrow(data)
    path.write_text(json.dumps(data,ensure_ascii=False), encoding='utf-8')
    wire = Transport(message(None, {'target':{'type':'topic','id':'implantation'}}))
    use(D2HttpProvider(transport=wire))
    body = send(client)
    block = cards(body)[0]['price']
    assert len(block['rows']) == 1 and block['presentation'] == 'options'
    assert cards(body)[0]['choices']
    assert len(wire.calls) == 1


@pytest.mark.parametrize('option', ['three_zones', 'underarms', 'legs'])
def test_service_wide_beauty_promo_covers_all_laser_options(http_env, monkeypatch, option):
    medical(http_env, monkeypatch)
    client, db, use, _ = http_env
    wire = native(use, 'laser_hair_removal', option_id=option)
    send(client, client_id='demo_medical', sid='variants')
    plan = saved(db, 'demo_medical')
    assert plan.d2_price_block.presentation == 'detail'
    assert {p.fact_id for p in plan.promo_blocks} == {'demo_beauty_15'}
    assert len(wire.calls) == 1


@pytest.mark.parametrize('option,has_promo', [('three_zones', True), ('underarms', False)])
def test_scoped_laser_promo_only_on_its_exact_offer(http_env, monkeypatch, option, has_promo):
    medical(http_env, monkeypatch)
    client, db, use, tmp = http_env
    # The real demo promo is now service-wide. Narrow a test-owned copy to keep
    # proving exact-offer authorization independently of marketing content.
    path = tmp/'clients/demo_medical/target_response/pricebook/facts.json'
    facts = json.loads(path.read_text(encoding='utf-8'))
    facts['demo_beauty_15']['allowed_offer_ids'] = ['laser_hair_removal.three_zones']
    path.write_text(json.dumps(facts, ensure_ascii=False), encoding='utf-8')
    wire = native(use, 'laser_hair_removal', option_id=option)
    send(client, client_id='demo_medical', sid='variants')
    plan = saved(db, 'demo_medical')
    assert plan.d2_price_block.presentation == 'detail'
    assert {p.fact_id for p in plan.promo_blocks} == ({'demo_beauty_15'} if has_promo else set())
    assert len(wire.calls) == 1


def test_no_public_price_keeps_card_and_excludes_without_includes(http_env, monkeypatch):
    medical(http_env, monkeypatch)
    client, db, use, tmp = http_env
    path = tmp/'clients/demo_medical/target_response/pricebook/services/botulinum_therapy.individual.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    data['package']['includes'] = []
    data['package']['excludes'] = ['Дополнительная зона']
    path.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    wire = native(use, 'botulinum_therapy', needs_completion=True, option_id='individual')
    body = send(client, client_id='demo_medical', sid='variants')
    block = cards(body)[0]['price']
    assert block['presentation'] == 'detail'
    row = block['rows'][0]
    assert row['mode'] == 'no_public_price' and not row['includes']
    assert row['excludes'] == ['Дополнительная зона']
    send(client, client_id='demo_medical', sid='variants', request_id='follow', q='Что дальше?')
    assert 'Дополнительная зона' in wire.calls[-1]['messages'][1]['content']


@pytest.mark.parametrize('fault', ['missing','foreign_service','excluded','duplicate'])
def test_scoped_fact_refs_are_validated(fault):
    snapshot = load_d2_tenant_snapshot('demo_medical', clients_root=ROOT/'clients')
    data = snapshot.bundle.model_dump(mode='json')
    fact = data['facts']['demo_beauty_15']
    fact['allowed_offer_ids'] = ['laser_hair_removal.three_zones']
    if fault == 'missing':
        fact['allowed_offer_ids'] = ['foreign.offer']
    elif fault == 'foreign_service':
        fact['allowed_offer_ids'] = ['ent_consultation.repeat']
    elif fault == 'excluded':
        fact['excluded_service_ids'] = ['laser_hair_removal']
        fact['excluded_scope_text'] = 'Запрещено'
    else:
        fact['allowed_offer_ids'] *= 2
    with pytest.raises(ValidationError):
        ResponseDataCatalog.model_validate(data)


def test_existing_service_wide_nikadent_promo_not_limited_by_offer_fact_refs():
    snapshot = load_d2_tenant_snapshot('nikadent', clients_root=ROOT/'clients')
    fact = snapshot.bundle.facts['free_orthopedic_consult']
    assert not fact.allowed_offer_ids
    authority = _commercial_authority(snapshot.client_id,build_d2_model_view(snapshot),snapshot.bundle)
    checked = 0
    for offer in snapshot.bundle.offers:
        if offer.active and offer.service_id in fact.allowed_service_ids:
            plan = resolve_d2_commercial_plan(authority=authority,
                bundle=snapshot.bundle, as_of=date(2026,10,16), service_id=offer.service_id,
                offer_id=offer.offer_id, include_packages=True)
            assert fact.id in {p.fact_id for p in plan.promo_blocks}
            checked += 1
    assert checked >= 5


def test_scope_dates_and_inactive_fact_still_apply():
    snap = load_d2_tenant_snapshot('demo_medical', clients_root=ROOT/'clients')
    # Keep the exact-offer guard even though this demo promotion is now broader.
    snap.bundle.facts['demo_beauty_15'].allowed_offer_ids = ['laser_hair_removal.three_zones']
    authority = _commercial_authority(snap.client_id,build_d2_model_view(snap),snap.bundle)
    def promos(**kwargs):
        return {p.fact_id for p in resolve_d2_commercial_plan(authority=authority,
            bundle=snap.bundle, service_id='laser_hair_removal', include_packages=True,
            **kwargs).promo_blocks}
    offer = dict(offer_id='laser_hair_removal.three_zones')
    assert 'demo_beauty_15' not in promos(as_of=date(2026,10,17), **offer)
    assert 'demo_beauty_15' in promos(as_of=date(2026,10,18), **offer)
    assert 'demo_beauty_15' not in promos(as_of=date(2026,10,18))
    assert 'demo_beauty_15' in promos(as_of=date(2026,12,31), **offer)
    assert 'demo_beauty_15' not in promos(as_of=date(2027,1,1), **offer)
    snap.bundle.facts['demo_beauty_15'].active = False
    assert 'demo_beauty_15' not in promos(as_of=date(2026,10,18), **offer)


def test_unpublished_revision_and_other_tenant_cannot_select(http_env):
    client, _, use, _ = http_env
    wire = native(use, 'classic')
    body = send(client, sid='variants')
    for fields in [dict(client_id='demo',ui_revision=body['revision']+100),
                   dict(client_id='nikadent',ui_revision=body['revision'])]:
        response = post(client,sid='variants',q='',request_id='reject-'+fields['client_id'],
            ref='price_select:classic.one_tooth.nobel',**fields)
        assert response.status_code in {400,409}
    assert len(wire.calls) == 1
