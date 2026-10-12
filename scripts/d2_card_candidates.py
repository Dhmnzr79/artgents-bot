"""Experimental providers only; never selected/imported by the running application."""
from __future__ import annotations
import copy,json,os,time
from pathlib import Path
from contracts.d2_dialogue_result import PriceOperation,parse_d2_text_reply,split_d2_text_reply
from core.d2_live_provider import build_d2_d1r_messages
from core.one_call_prompt_contract import D2_OPERATIONS_INSTRUCTIONS
from core.one_call_envelope_protocol import _loads_strict_json_object
ARMS=('tail','tool','split')
ROOT=Path(__file__).resolve().parents[1]
PRICE_RULES='''PRICE RESPONSIBILITY
A request for price of an identified service OR direction must request a price card.
This includes conversational continuations and repeated prices already visible in history.
Unknown extent or method does not block a direction overview: send the known direction.
Never replace a price request with prose asking for method/extent when its direction is known.
Keep the explicitly discussed brand and extent. Brand and extent do not select a method.
Never choose classic or another method merely because a brand or one tooth is mentioned.
For a price-only question, supply the price action without introduction, copied sums or conditions.
Code owns monetary amounts, overview introduction, volume choices and card conditions.
For a mixed question, also answer its independent informational question in ordinary prose.
For information alone (availability, warranty, pain, included treatment), answer naturally;
do not request a price just because a service or brand is mentioned.
Use existing catalog IDs, preserve explicitly named option; never invent arguments.
'''

def strict_load(raw):return _loads_strict_json_object(raw)

def price_args(data,request):
 if not isinstance(data,dict) or {'kind','request_id','content_text'}.intersection(data):raise ValueError('price_argument_shape')
 p=PriceOperation.model_validate(dict(data,kind='price',request_id='r2'))
 if p.clarification is not None and any(x not in request.model_view.active_service_catalog.active_service_ids for x in p.clarification.choices):raise ValueError('inactive_clarification')
 return data

def schema():
 s=PriceOperation.model_json_schema()
 def walk(x):
  if isinstance(x,list):return [walk(v) for v in x]
  if not isinstance(x,dict):return x
  if '$ref' in x:return {**walk(s['$defs'][x['$ref'].split('/')[-1]]),**walk({k:v for k,v in x.items() if k!='$ref'})}
  return {k:walk(v) for k,v in x.items() if k not in ('$defs','discriminator')}
 s['properties'].pop('kind');s['properties'].pop('request_id');s['required']=[k for k in s.get('required',[]) if k not in ('kind','request_id')]
 return walk(s)

def base_messages(request,instructions):
 messages=list(build_d2_d1r_messages(request));system=messages[0]['content']
 if D2_OPERATIONS_INSTRUCTIONS not in system:raise ValueError('unexpected_known_task')
 system=system.replace(D2_OPERATIONS_INSTRUCTIONS,instructions)
 begin='=== D2_DIRECTION_PRICES ===\n';end='\n\n=== BRAND_CATALOG ==='
 before,tail=system.split(begin,1);raw,after=tail.split(end,1)
 directions=json.loads(raw)
 for d in directions:
  d.pop('introduction_text',None);d.pop('unknown_extent_text',None)
 messages[0]['content']=before+begin+json.dumps(directions,ensure_ascii=False,separators=(',',':'))+end+after
 return messages

def tail_instructions():
 s=D2_OPERATIONS_INSTRUCTIONS
 a=s.index('Use show_price');b=s.index('If an ordinary informational question',a)
 s=s[:a]+PRICE_RULES+'\n'+s[b:]
 # Neutral example preserves a direction rather than teaching an implicit method.
 s=s.replace('{"target":{"type":"service","id":"classic"},"brand_id":"nobel_biocare","volume":{"extent":"one_tooth"}}','{"target":{"type":"topic","id":"implantation"},"brand_id":"nobel_biocare","volume":{"extent":"one_tooth"}}')
 return s

def tool_instructions():
 s=tail_instructions().replace('API tools are not available.','Only the show_price API tool is available.')
 s=s.replace('Code-owned action requests and optional sources go in one final metadata block.','Price actions go only through show_price API calls. Optional sources go in a final metadata block.')
 s=s.replace('The response is final: there is no tool execution loop and no next model turn.','After a valid price request, one completion turn is available for independent informational text. A pure price needs no prose.')
 a=s.index('actions is an ordered list');b=s.index('Example source:',a)
 s=s[:a]+'''Do not put actions in metadata. show_price arguments use catalog target objects, brand_id, option_id, volume and payment fields. target is an object, not a JSON string. volume is an object, not a JSON string.
'''+s[b:]
 s=s[:s.index('Example price:')]+'''For a requested direction use show_price(target={"type":"topic","id":"implantation"}, brand_id="nobel_biocare", volume={"extent":"one_tooth"}) when those parameters match the dialogue. Do not select a method not stated by the user.
'''
 return s

def writer_instructions():
 return '''Write a complete natural Russian answer to the informational question supplied in TEXT_QUESTION, using the full clinic base and actual history. Do not promise to answer later.
The price decision is already made elsewhere. Do not choose or change price parameters, ask for price parameters, give monetary quotations or request any action. Do not repeat card introduction or automatic advertisements.
Warranty, pain, doctors, brands and treatment explanations are ordinary prose. Preserve clinical caveats and clinic facts; do not diagnose or prescribe.
Optional source references may follow prose as <D2_META> on its own line, a JSON object {"sources":[{"content_ref":"exact.md"}]}, then </D2_META> on its own line. No actions. No outer JSON for the text.
'''

def combine(prose_raw,actions,request):
 text,meta=split_d2_text_reply(prose_raw or '')
 if meta and meta.get('actions'):raise ValueError('writer_attempted_action')
 data={'actions':actions}
 if meta and 'sources' in meta:data['sources']=meta['sources']
 if not text and not actions:raise ValueError('empty_candidate')
 return text+'\n<D2_META>\n'+json.dumps(data,ensure_ascii=False)+'\n</D2_META>'

class Runner:
 def __init__(self,output,live=True):
  self.output=Path(output).resolve();self.live=live;self.records=[]
  if not self.output.is_relative_to(ROOT/'logs'):raise ValueError('outside_logs')
  self.output.mkdir(parents=True,exist_ok=True);self.ledger_path=self.output/'attempts.json'
  if self.ledger_path.exists():raise ValueError('existing_ledger_do_not_repeat')
  self.save()
  from dotenv import load_dotenv
  load_dotenv(ROOT/'.env')
  self.model=os.environ.get('DEEPSEEK_MODEL');base=os.environ.get('DEEPSEEK_BASE_URL','https://api.deepseek.com').rstrip('/')
  if self.model!='deepseek-flash' or base not in ('https://api.deepseek.com','https://api.deepseek.com/v1'):raise ValueError('unexpected_provider')
  from openai import OpenAI
  self.client=OpenAI(api_key=os.environ['DEEPSEEK_API_KEY'],base_url=base,max_retries=0,timeout=60)
 def save(self):self.ledger_path.write_text(json.dumps(self.records,ensure_ascii=False,indent=2),encoding='utf-8')
 def call(self,arm,phase,request,messages,**kwargs):
  if not self.live:raise ValueError('live_not_authorized')
  if len(self.records)>=80:raise ValueError('budget_exhausted')
  limits={'tail':16,'tool':32,'split':32}
  if sum(r['arm']==arm for r in self.records)>=limits[arm]:raise ValueError('arm_budget_exhausted')
  row={'arm':arm,'phase':phase,'question':request.user_message,'sid':request.context.session_key.sid,'status':'reserved','messages':messages}
  self.records.append(row);self.save();t=time.monotonic()
  try:
   response=self.client.chat.completions.create(model=self.model,messages=messages,temperature=0,max_tokens=1536,extra_body={'thinking':{'type':'disabled'}},**kwargs)
   ch=response.choices[0];row.update(status='received',response=ch.message.model_dump(),finish_reason=ch.finish_reason,usage=response.usage.model_dump())
   return ch.message
  except Exception as e:
   row.update(status='error',error_type=type(e).__name__,http_status=getattr(e,'status_code',None));raise
  finally:
   row['ms']=round((time.monotonic()-t)*1000);self.save()
   print(json.dumps({k:row.get(k) for k in ('arm','phase','question','status','finish_reason','ms')},ensure_ascii=False),flush=True)

class CandidateProvider:
 def __init__(self,arm,runner):self.arm=arm;self.runner=runner
 def generate(self,request):
  if self.arm=='tail':
   msg=self.runner.call(self.arm,'reply',request,base_messages(request,tail_instructions()))
   if msg.tool_calls:raise ValueError('unexpected_tools')
   return msg.content or ''
  if self.arm=='tool':
   messages=base_messages(request,tool_instructions())
   tool={'type':'function','function':{'name':'show_price','description':'Request the code-owned price card only when the user asks for a price. Known directions are valid; method and extent may be unspecified.','parameters':schema()}}
   msg=self.runner.call(self.arm,'selection',request,messages,tools=[tool],tool_choice='auto')
   if not msg.tool_calls:return msg.content or ''
   if len(msg.tool_calls)!=1 or msg.tool_calls[0].function.name!='show_price':raise ValueError('unexpected_tool_count')
   call=msg.tool_calls[0];args=price_args(strict_load(call.function.arguments),request)
   # Acknowledgement only, no fabricated price result or second selection.
   messages.append(msg.model_dump(exclude_none=True))
   messages.append({'role':'tool','tool_call_id':call.id,'content':json.dumps({'accepted_for_card_rendering':args},ensure_ascii=False)})
   messages.append({'role':'user','content':'The price request is accepted for code-owned rendering. If the ORIGINAL question has independent informational content, answer that part now. Otherwise return exactly <NO_TEXT>. Do not quote prices, change the request, ask for price parameters or emit actions. Do not repeat your preceding explanation.'})
   msg2=self.runner.call(self.arm,'completion',request,messages,tools=[tool],tool_choice='none')
   if msg2.tool_calls:raise ValueError('completion_tool')
   t2='' if (msg2.content or '').strip()=='<NO_TEXT>' else msg2.content or ''
   # Preserve separate prose pieces; do not repair duplicates semantically.
   t1=msg.content or '';text1,meta1=split_d2_text_reply(t1);text2,meta2=split_d2_text_reply(t2)
   if any(m and m.get('actions') for m in (meta1,meta2)):raise ValueError('wrong_channel_actions')
   sources=[s for m in (meta1,meta2) if m for s in m.get('sources',[])]
   return '\n\n'.join(t for t in (text1,text2) if t)+'\n<D2_META>\n'+json.dumps({'actions':[{'name':'show_price','arguments':args}],'sources':sources},ensure_ascii=False)+'\n</D2_META>'
  instructions='''You are solely responsible for extracting a requested price, not writing the answer. Return JSON with exactly two fields: price (null, or show_price argument object) and text_question (null, or the user's independent informational question to answer). Read current question and full conversation. For information alone price=null and text_question preserves the question and its referent. For price alone text_question=null. For mixed requests preserve only independent explanation in text_question. Do not replace an answerable price with a request to choose method or volume. No prose outside JSON.\n'''+PRICE_RULES+'\nPrice argument JSON schema:\n'+json.dumps(schema(),ensure_ascii=False)
  msg=self.runner.call(self.arm,'extract',request,base_messages(request,instructions),response_format={'type':'json_object'})
  obj=strict_load(msg.content or '')
  if set(obj)!={'price','text_question'}:raise ValueError('extract_shape')
  args=price_args(obj['price'],request) if obj['price'] is not None else None
  q=obj['text_question']
  if q is not None and (not isinstance(q,str) or not q.strip()):raise ValueError('text_question_shape')
  raw=''
  if q is not None:
   messages=base_messages(request,writer_instructions());messages[1]['content']+='\n\n=== TEXT_QUESTION ===\n'+q
   out=self.runner.call(self.arm,'write',request,messages)
   if out.tool_calls:raise ValueError('writer_tool')
   raw=out.content or ''
   if not split_d2_text_reply(raw)[0]:raise ValueError('writer_empty')
  return combine(raw,[{'name':'show_price','arguments':args}] if args else [],request)
