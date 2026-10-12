"""Offline candidate-boundary checks; no evidence of live model quality."""
from types import SimpleNamespace as NS
import json
import pytest
from scripts import d2_card_candidates as c
from contracts.d2_dialogue_result import parse_d2_text_reply,PriceOperation

@pytest.fixture
def provider_input(monkeypatch):
 monkeypatch.setattr(c,'base_messages',lambda provider_input,instructions:[{'role':'system','content':instructions},{'role':'user','content':'question'}])
 return NS(user_message='question',model_view=NS(active_service_catalog=NS(active_service_ids=('classic','all_on_6'))))

class Queue:
 def __init__(self,*responses):self.responses=list(responses);self.calls=[]
 def call(self,*args,**kwargs):self.calls.append((args,kwargs));return self.responses.pop(0)

def msg(content='',calls=None):
 class Message(NS):
  def model_dump(self,**kwargs):return {'role':'assistant','content':self.content,'tool_calls':[{'id':x.id,'type':'function','function':{'name':x.function.name,'arguments':x.function.arguments}} for x in self.tool_calls]}
 return Message(content=content,tool_calls=calls or [])

ARGS={'target':{'type':'topic','id':'implantation'},'brand_id':'nobel_biocare','volume':{'extent':'one_tooth'}}

def test_split_price_only_one_call(provider_input):
 q=Queue(msg(json.dumps({'price':ARGS,'text_question':None})))
 raw=c.CandidateProvider('split',q).generate(provider_input)
 p=parse_d2_text_reply(raw,active_service_ids=('classic',))
 assert len(q.calls)==1 and isinstance(p.blocks[0],PriceOperation)
 assert p.blocks[0].brand_id=='nobel_biocare' and p.blocks[0].target.id=='implantation'

def test_split_mixed_writer_cannot_change_price(provider_input):
 q=Queue(msg(json.dumps({'price':ARGS,'text_question':'Расскажите про Nobel'})),msg('Описание Nobel.'))
 raw=c.CandidateProvider('split',q).generate(provider_input)
 assert len(q.calls)==2 and 'Описание Nobel.' in raw
 assert json.loads(raw.split(c.OPEN if hasattr(c,'OPEN') else '<D2_META>')[1].split('</D2_META>')[0])['actions'][0]['arguments']==ARGS
 assert 'TEXT_QUESTION' in q.calls[1][0][3][1]['content']

def test_split_writer_action_rejected(provider_input):
 q=Queue(msg(json.dumps({'price':ARGS,'text_question':'Описание'})),msg('Текст\n<D2_META>\n'+json.dumps({'actions':[{'name':'show_price','arguments':ARGS}]})+'\n</D2_META>'))
 with pytest.raises(ValueError,match='writer_attempted_action'):c.CandidateProvider('split',q).generate(provider_input)

def test_tool_invalid_shape_no_second_call(provider_input):
 call=NS(id='t1',function=NS(name='show_price',arguments=json.dumps({'target':json.dumps(ARGS['target'])})))
 q=Queue(msg(calls=[call]))
 with pytest.raises(ValueError):c.CandidateProvider('tool',q).generate(provider_input)
 assert len(q.calls)==1

def test_tool_completion_preserves_original_args(provider_input):
 call=NS(id='t1',function=NS(name='show_price',arguments=json.dumps(ARGS)))
 q=Queue(msg(calls=[call]),msg('<NO_TEXT>'))
 raw=c.CandidateProvider('tool',q).generate(provider_input)
 p=parse_d2_text_reply(raw,active_service_ids=('classic',))
 assert len(q.calls)==2 and len(p.blocks)==1 and p.blocks[0].target.id=='implantation'
 assert q.calls[1][1]['tool_choice']=='none'

def test_schema_nullable_not_narrowed():
 s=c.schema();assert 'type' not in s['properties']['volume']
 assert any(x.get('type')=='null' for x in s['properties']['volume']['anyOf'])
 assert '$ref' not in json.dumps(s)
