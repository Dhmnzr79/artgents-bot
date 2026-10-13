"""Experiment-only protocol and real publication checks; no live provider."""
import json
from types import SimpleNamespace
from pathlib import Path
import pytest
from scripts import experiment_d2_cards_round2 as exp
from scripts.experiment_d2_cards import isolated_http, ObservedProvider, choose_tab, cards


def test_strict_schema_and_null_decode_are_narrow():
    shape = exp.strict_schema(exp.corrected_schema())
    assert set(shape['required']) == set(shape['properties'])
    assert shape['additionalProperties'] is False
    assert all('type' in part for part in shape['properties']['target']['anyOf'])
    def check_branches(node):
        if isinstance(node, dict):
            if 'anyOf' in node:
                assert all('type' in part for part in node['anyOf'])
            for v in node.values(): check_branches(v)
        elif isinstance(node, list):
            for v in node: check_branches(v)
    check_branches(shape)
    data = dict(target={'type':'service','id':'classic'}, clarification=None,
                age_group=None, volume={'extent':'one_tooth','jaw':None,'tooth_count':None}, brand_id=None)
    decoded = exp.decode_strict(data)
    assert 'clarification' not in decoded and 'age_group' not in decoded
    assert decoded['volume'] == {'extent':'one_tooth','tooth_count':None}
    assert decoded['brand_id'] is None
    assert data['clarification'] is None
    assert exp.decode_strict({'target':'broken'}) == {'target':'broken'}
    assert exp.decode_strict({'clarification':{'missing':'term','choices':None}}) == {'clarification':{'missing':'term'}}
    assert exp.decode_strict({'clarification':{'missing':'service','choices':None}})['clarification']['choices'] is None


def test_classifier_schema_does_not_offer_null_clarification():
    options = exp.corrected_schema()['properties']['clarification']['anyOf']
    assert options and all(v.get('type') != 'null' for v in options)


def test_information_writer_cannot_override_classifier(monkeypatch):
    monkeypatch.setattr(exp.old, 'base_messages', lambda *a: [{'role':'system','content':''},{'role':'user','content':''}])
    class AdverseRunner:
        def call(self, arm, phase, request, messages, **kwargs):
            text = (json.dumps({'price':None,'text_question':'Гарантия?'}) if phase=='extract'
                    else 'Ответ.\n<D2_META>\n{"actions":[{"name":"show_price","arguments":{"target":{"type":"topic","id":"implantation"}}}]}\n</D2_META>')
            return SimpleNamespace(content=text, tool_calls=None)
    with pytest.raises(ValueError, match='writer_attempted_action'):
        exp.Candidate('split_grounded', AdverseRunner()).generate(SimpleNamespace())


class FakeRunner:
    def __init__(self): self.calls=[]
    def call(self, arm, phase, request, messages, **kwargs):
        self.calls.append((phase, messages))
        if phase == 'selection':
            if request.user_message == 'Что входит?':
                history = request.context.ordinary.dialogue_pairs
                assert 'classic.one_tooth.nobel' in [o.offer_id for p in history for o in p.offers]
                return SimpleNamespace(tool_calls=None, content='Состав выбранной карточки есть в истории.')
            from openai.types.chat import ChatCompletionMessage
            return ChatCompletionMessage(role='assistant', content='Internal planning must not be published.',
                tool_calls=[{'id':'test-tool','type':'function','function':{'name':'show_price', 'arguments': json.dumps({'target':{'type':'service','id':'classic'},'volume':{'extent':'one_tooth'}})}}])
        assert phase == 'completion'
        tool_result = json.loads(next(m['content'] for m in messages if m['role']=='tool'))
        assert tool_result['price']['rows'][0]['offer_id'] == 'classic.one_tooth.implantium'
        assert any(p['kind']=='price_card' for p in tool_result['ui']['body_parts'])
        return SimpleNamespace(tool_calls=None, content='Обезболивание обсуждают с врачом.')


def test_real_card_completion_single_commit_and_tab_history(tmp_path):
    with isolated_http(tmp_path / 'isolated') as (client, patch, adapter):
        import core.d2_dialogue as dialogue
        runner = FakeRunner()
        candidate = exp.Candidate('tool_grounded', runner)
        observed = ObservedProvider(candidate)
        patch.setattr(adapter, 'D2HttpProvider', lambda **kw: observed)
        patch.setattr(dialogue, 'resolve_d2_operations', exp.materializer(dialogue.resolve_d2_operations, candidate))
        first = client.post('/ask', json=dict(client_id='demo',sid='r2-test',request_id='p1',q='Цена классики и обезболивание?'))
        assert first.status_code == 200, first.get_json()
        body=first.get_json()
        assert body['revision']==1 and cards(body)
        assert 'Обезболивание обсуждают' in body['answer']
        assert 'Internal planning' not in body['answer']
        assert len(runner.calls)==2
        replay=client.post('/ask',json=dict(client_id='demo',sid='r2-test',request_id='p1',q='Цена классики и обезболивание?'))
        assert replay.get_json()==body and len(runner.calls)==2
        choice=choose_tab(body)
        assert choice and 'nobel' in choice['reply_id']
        observed.button=True
        selected=client.post('/ask',json=dict(client_id='demo',sid='r2-test',request_id='p2',q='',ref=choice['reply_id'],ui_revision=body['revision']))
        observed.button=False
        assert selected.status_code==200 and selected.get_json()['revision']==2
        assert len(runner.calls)==2
        follow=client.post('/ask',json=dict(client_id='demo',sid='r2-test',request_id='p3',q='Что входит?'))
        assert follow.status_code==200 and follow.get_json()['revision']==3
        assert len(runner.calls)==3
