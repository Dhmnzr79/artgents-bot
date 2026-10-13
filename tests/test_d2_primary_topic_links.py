"""One MD primary-topic owner and one typed absent-brand policy source."""
from datetime import date
from pathlib import Path

import pytest
import yaml

from contracts.response_plan import SessionKey
from contracts.response_plan_fact_policy import RequestedFactPolicyContext
from core.d2_contacts_cta import resolve_d2_lead_cta_button
from core.d2_snapshot_sources import (
    build_d2_unknown_brand_response, resolve_d2_clarify_service_topic,
)
from core.d2_tenant_snapshot import load_d2_tenant_snapshot, build_d2_model_view
from core.response_plan_authored_alternative_policy import unambiguous_topic_for_service_ids
from core.response_plan_fact_policy import evaluate_requested_fact_display
from core.response_plan_fact_projection import project_commercial_fact_candidate
from tests.d2_ci_http import FakeProvider, http_env, raw, send

OSSTEM = ('Osstem в ассортименте нет. Работаем с Implantium, Impro и Nobel Biocare — могу рассказать '
          'про отличия систем и ориентиры по стоимости «под ключ».')


def forbid_filename(*args, **kwargs):
    raise AssertionError('D2 must use MD topic, not filename')


def test_demo_links_and_price_overview_remain_distinct():
    snapshot = load_d2_tenant_snapshot('demo', clients_root=Path('clients'))
    assert snapshot.service_topics['tomography'] == 'diagnostics'
    assert resolve_d2_clarify_service_topic(snapshot, ('tomography',)) == 'diagnostics'
    with pytest.raises(TypeError):
        snapshot.service_topics['tomography'] = 'clinic'
    view = build_d2_model_view(snapshot)
    overview = next(row for row in view.direction_prices if row.topic_id == 'implantation')
    assert len(overview.service_ids) == 4
    assert sum(topic == 'implantation' for topic in snapshot.service_topics.values()) == 9
    assert build_d2_unknown_brand_response(snapshot, session_key=SessionKey(client_id='demo', sid='links'),
                                           brand_id='osstem').rendered_text == OSSTEM
    policies = yaml.safe_load(dict(snapshot.files)['clinic_policies.yaml'])
    assert not any('osstem' in row.get('match_keywords', []) for row in policies['service_alternatives'])
    assert OSSTEM in view.clinic_policy_catalog_json


@pytest.mark.parametrize('topics', [{}, {'classic': 'clinic'}])
def test_empty_or_different_authoritative_index_never_reads_filename(monkeypatch, topics):
    import core.response_plan_fact_policy as policy
    import core.response_plan_authored_alternative_policy as alternative
    monkeypatch.setattr(policy, 'parse_service_catalog_content_topic', forbid_filename)
    monkeypatch.setattr(alternative, 'parse_service_catalog_content_topic', forbid_filename)
    snapshot = load_d2_tenant_snapshot('demo', clients_root=Path('clients'))
    fact = snapshot.bundle.facts['implant_warranty']
    candidate = project_commercial_fact_candidate(snapshot.bundle, fact, source_client_id='demo',
                    allowed_roles=('requested_fact',), service_topics=topics)
    assert candidate.requires_implant_scope is False
    assert unambiguous_topic_for_service_ids(snapshot.bundle, ('classic',), service_topics=topics) == topics.get('classic')
    context = RequestedFactPolicyContext(response_scope='service', reference_service_id='classic',
                                          resolved_topic_id=topics.get('classic'), implant_context_confirmed=False)
    assert evaluate_requested_fact_display(fact=fact, context=context, bundle=snapshot.bundle,
                                          service_topics=topics) == 'allowed'


@pytest.mark.parametrize('transport', ['json', 'sse'])
def test_real_d2_fact_cta_context_follow_md_not_filename(http_env, monkeypatch, transport):
    client, db, use, tmp = http_env
    root = tmp/'clients'
    original = load_d2_tenant_snapshot('demo', clients_root=root)
    # All warranty services now deliberately disagree with their filenames.
    for service_id in original.bundle.facts['implant_warranty'].allowed_service_ids:
        path = root/'demo/md'/original.bundle.services[service_id].content_ref
        path.write_text(path.read_text(encoding='utf-8').replace('topic: implantation\n', 'topic: clinic\n', 1), encoding='utf-8')
    import core.response_plan_authored_alternative_policy as alternative
    import core.response_plan_fact_policy as policy
    monkeypatch.setattr(alternative, 'parse_service_catalog_content_topic', forbid_filename)
    monkeypatch.setattr(policy, 'parse_service_catalog_content_topic', forbid_filename)
    snapshot = load_d2_tenant_snapshot('demo', clients_root=root)
    assert snapshot.service_topics['classic'] == 'clinic'
    assert resolve_d2_clarify_service_topic(snapshot, ('classic',)) == 'clinic'
    button = resolve_d2_lead_cta_button(snapshot, as_of=date(2026, 10, 10),
                                      prefer_free_consult=True, service_id='classic')
    assert button is None or button.button_id != 'free_consult'
    fake = use(FakeProvider(raw({'kind':'commercial_fact', 'request_id':'r1',
                               'target':{'type':'service', 'id':'classic'}, 'fact_ids':['implant_warranty']})))
    args = dict(sid='links', request_id='warranty', q='Какая гарантия на классическую имплантацию?')
    body = send(client, transport, **args)
    from core.d2_dialogue_store import D2DialogueStore
    with D2DialogueStore(db) as store:
        result = store.read_latest_completion(SessionKey(client_id='demo', sid='links')).response.resolved
    assert result.finalized_commercial_ids.requested_fact_ids == ('implant_warranty',)
    assert original.bundle.facts['implant_warranty'].text_fact in body['answer']
    assert send(client, transport, **args) == body
    assert len(fake.inputs) == 1
    fake.raw = raw({'kind':'contact', 'request_id':'r1', 'contact_fields':['contact_address']})
    send(client, transport, sid='links', request_id='next', q='Где вы находитесь?')
    # 2B retains the explicitly scoped completed commercial subject.
    assert fake.inputs[-1].context.ordinary.discussion_scope.service_id == 'classic'
    fake.raw = raw({'kind':'doctors', 'request_id':'r1', 'target':{'type':'service','id':'classic'}})
    send(client, transport, sid='links', request_id='doctors', q='Кто проводит классическую имплантацию?')
    with D2DialogueStore(db) as store:
        doctor_result = store.read_latest_completion(SessionKey(client_id='demo', sid='links')).response.resolved
    assert doctor_result.d2_request_parts[0].topic_id == 'clinic'
    fake.raw = raw({'kind':'contact', 'request_id':'r1', 'contact_fields':['contact_address']})
    send(client, transport, sid='links', request_id='after-doctors', q='Где вы находитесь?')
    assert fake.inputs[-1].context.ordinary.discussion_scope.service_id == 'classic'


@pytest.mark.parametrize('transport', ['json', 'sse'])
def test_absent_brand_uses_single_typed_policy_and_replay(http_env, transport):
    client, db, use, tmp = http_env
    fake = use(FakeProvider(raw({'kind':'price', 'request_id':'r1',
                               'target':{'type':'service', 'id':'classic'}, 'brand_id':'osstem'})))
    args = dict(sid='osstem', request_id='brand', q='Сколько стоит имплантация Osstem?')
    body = send(client, transport, **args)
    assert OSSTEM in body['answer']
    assert send(client, transport, **args) == body
    assert len(fake.inputs) == 1
    from core.d2_dialogue_store import D2DialogueStore
    with D2DialogueStore(db) as store:
        result = store.read_latest_completion(SessionKey(client_id='demo', sid='osstem')).response.resolved
    assert result.d2_price_block is None
    assert result.finalized_commercial_ids.price_offer_ids == ()


def test_unknown_brand_foreign_session_stays_strict():
    snapshot = load_d2_tenant_snapshot('demo', clients_root=Path('clients'))
    with pytest.raises(ValueError, match='brand_client_mismatch'):
        build_d2_unknown_brand_response(snapshot, session_key=SessionKey(client_id='nikadent', sid='foreign'),
                                        brand_id='osstem')
