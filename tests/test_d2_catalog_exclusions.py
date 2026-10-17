"""One canonical exclusion list survives card, plain response and completed history."""
from pathlib import Path
from datetime import date
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from core.d2_live_provider import D2HttpProvider
from tests.d2_ci_http import http_env,send,click,completed_context
from tests.test_d2_native_price_runtime import Transport,message,price
from tests.test_widget_catalog import admit_medical


@pytest.mark.parametrize('transport',['json','sse'])
@pytest.mark.parametrize('tenant,service,option,offer_id',[
    ('demo_medical','ultrasound_lifting','face350','ultrasound_lifting.face350'),
    ('demo_medical','laser_hair_removal','three_zones','laser_hair_removal.three_zones'),
    ('nikadent','classic',None,'classic.default'),
    ('demo','classic',None,'classic.one_tooth.implantium'),
    ('demo','one_stage',None,'one_stage.one_tooth.implantium'),
    ('demo','sinus_lift','closed','sinus_lift.one_site.closed'),
    ('demo','temporary_teeth',None,'temporary_teeth.default'),
])
def test_exclusions_have_one_display_source_and_remain_in_plain_history(http_env,monkeypatch,transport,tenant,service,option,offer_id):
    if tenant=='demo_medical':admit_medical(http_env,monkeypatch)
    client,db,use,root=http_env
    wire=Transport(message(None,price(service,**({'option_id':option} if option else {}))),message('<NO_TEXT>'))
    use(D2HttpProvider(transport=wire))
    sid=uuid4().hex
    args=dict(client_id=tenant,sid=sid,request_id='price',q='Стоимость?')
    body=send(client,transport,**args)
    assert send(client,transport,**args)==body and len(wire.calls)==2
    card=next(part for part in body['ui']['body_parts'] if part['kind']=='price_card')
    if card['price']['presentation']=='options':
        body=click(client,body,'price_select:'+offer_id,request_id='selected',transport=transport,client_id=tenant,sid=sid)
        card=next(part for part in body['ui']['body_parts'] if part['kind']=='price_card')
    assert card['price']['presentation']=='detail'
    row=card['price']['rows'][0]
    authored=json.loads((root/f'clients/{tenant}/target_response/pricebook/services/{offer_id}.json').read_text(encoding='utf-8'))
    assert row['offer_id']==offer_id and row['excludes']==authored['package']['excludes']
    assert row['includes']==authored['package']['includes']
    for line in row['excludes']:
        assert not any(line.casefold() in text.casefold() for text in row['condition_texts'])
        assert body['answer'].count('- '+line)==1
    price_paragraph=next(block for block in body['answer'].split('\n\n') if row['price_display_text'] in block)
    assert price_paragraph.endswith(row['scope_text'] or row['price_display_text'])
    assert all(text not in price_paragraph for text in row['condition_texts'])
    if row['condition_texts']:
        assert 'Условия и преимущества:\n' in body['answer']
    with D2DialogueStore(db) as store:
        context=completed_context(store,SessionKey(client_id=tenant,sid=sid))
    history=context.ordinary.dialogue_pairs[-1].assistant_text
    assert all(history.count('- '+line)==1 for line in row['excludes'])
    restored=client.post('/api/widget-session',json=dict(client_id=tenant,sid=sid)).get_json()
    assert restored['current']['answer']==body['answer']
    assert restored['current']['ui']==body['ui'] and len(wire.calls)==2
    # Independent scope conditions still appear; cleanup removes no unrelated clause.
    clauses=authored['package']['label'].split(';')[1:]
    assert all(clause.strip() in row['condition_texts'] for clause in clauses)


def test_all_current_price_rows_keep_conditions_out_of_price_paragraph(monkeypatch):
    from contracts.response_plan import D2FrozenPriceBlock,ResponsePriceCardPart
    from core.d2_tenant_snapshot import load_d2_tenant_snapshot
    from core.widget_catalog import build_widget_catalog
    from core import response_text_renderer as renderer

    root=Path(__file__).resolve().parents[1]
    count=0
    for folder in sorted((root/'clients').iterdir()):
        if not (folder/'target_response/widget_catalog.json').exists():continue
        snapshot=load_d2_tenant_snapshot(folder.name,clients_root=root/'clients')
        catalog=build_widget_catalog(snapshot,as_of=date(2026,10,17))
        for service in catalog['services']:
            for detail in service['details'].values():
                block=D2FrozenPriceBlock.model_validate(detail['price']);row=block.rows[0]
                part=ResponsePriceCardPart(price=block)
                monkeypatch.setattr(renderer,'render_response_parts',lambda *args,**kwargs:(part,))
                text=renderer.render_response_text(SimpleNamespace(),include_card_details=True)
                price_paragraph=text.split('\n\n',1)[0]
                assert price_paragraph.endswith(row.scope_text or row.price_display_text)
                expected=f'**{row.service_name}**'
                if row.variant_label:expected+=' — '+row.variant_label
                expected+=' — '+(row.price_display_text if row.mode=='no_public_price' else f'**{row.price_display_text}**')
                if row.scope_text:expected+=' '+row.scope_text
                assert price_paragraph==expected
                for heading,items in [('В стоимость входят',row.includes),('Отдельно оплачиваются / не входят',row.excludes),
                    ('Условия и преимущества',row.condition_texts),('Этапы оплаты',row.stages)]:
                    if items:assert heading+':\n'+'\n'.join('- '+line for line in items) in text
                count+=1
    assert count==105


def test_price_group_formatter_has_no_condition_append_path():
    from core.response_text_renderer import _render_compact_price_group
    from contracts.response_plan import D2FrozenPriceRow

    row=D2FrozenPriceRow(source_client_id='new-clinic',offer_id='new.default',service_id='new',
        mode='fixed',display_text='Процедура — 100 ₽ за один визит',service_name='Процедура',
        price_display_text='100 ₽',scope_text='за один визит',amount=100,currency='RUB',billing_unit='visit',
        condition_texts=('Совершенно новое условие, не известное коду',))
    for rows in [(row,),(row,row.model_copy(update={'offer_id':'new.other','variant_label':'Другой вариант'}))]:
        parts=[];_render_compact_price_group(rows,parts,show_service_in_each_row=False)
        assert 'Совершенно новое условие' not in '\n'.join(parts)
        assert '\n'.join(parts).count('за один визит')==len(rows)
