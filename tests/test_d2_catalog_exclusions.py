"""One canonical exclusion list survives card, plain response and completed history."""
from pathlib import Path
import json

import pytest
from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from core.d2_live_provider import D2HttpProvider
from tests.d2_ci_http import http_env,send,completed_context
from tests.test_d2_native_price_runtime import Transport,message,price
from tests.test_widget_catalog import admit_medical


@pytest.mark.parametrize('transport',['json','sse'])
@pytest.mark.parametrize('tenant,service,option,offer_id',[
    ('demo_medical','ultrasound_lifting','face350','ultrasound_lifting.face350'),
    ('demo_medical','laser_hair_removal','three_zones','laser_hair_removal.three_zones'),
    ('nikadent','classic',None,'classic.default'),
])
def test_exclusions_have_one_display_source_and_remain_in_plain_history(http_env,monkeypatch,transport,tenant,service,option,offer_id):
    if tenant=='demo_medical':admit_medical(http_env,monkeypatch)
    client,db,use,root=http_env
    wire=Transport(message(None,price(service,**({'option_id':option} if option else {}))),message('<NO_TEXT>'))
    use(D2HttpProvider(transport=wire))
    body=send(client,transport,client_id=tenant,sid='exclusion-proof',q='Стоимость?')
    card=next(part for part in body['ui']['body_parts'] if part['kind']=='price_card')
    assert card['price']['presentation']=='detail'
    row=card['price']['rows'][0]
    authored=json.loads((root/f'clients/{tenant}/target_response/pricebook/services/{offer_id}.json').read_text(encoding='utf-8'))
    assert row['offer_id']==offer_id and row['excludes']==authored['package']['excludes']
    assert row['includes']==authored['package']['includes']
    for line in row['excludes']:
        assert not any(line.casefold() in text.casefold() for text in row['condition_texts'])
        assert body['answer'].count('- '+line)==1
    with D2DialogueStore(db) as store:
        context=completed_context(store,SessionKey(client_id=tenant,sid='exclusion-proof'))
    history=context.ordinary.dialogue_pairs[-1].assistant_text
    assert all(history.count('- '+line)==1 for line in row['excludes'])
    # Independent scope conditions still appear; cleanup removes no unrelated clause.
    clauses=authored['package']['label'].split(';')[1:]
    assert all(clause.strip() in row['condition_texts'] for clause in clauses)
