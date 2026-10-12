"""Isolated paired frozen-context price transport experiment; no runtime imports this."""
import copy,json,os,sys,time,hashlib,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
OUT=ROOT/'logs/price-transport-20261012'
os.environ['BOT_LOG_DIR']=str(OUT/'harness')
os.environ['D2_FULL_AUDIT_LOG']='0'
from scripts.probe_d2_native_models import dump
from scripts.probe_d2_text_tail import prepare
from core.one_call_envelope_protocol import _loads_strict_json_object
def inline_schema(schema):
 def walk(x):
  if isinstance(x,list):return [walk(v) for v in x]
  if not isinstance(x,dict):return x
  if "$ref" in x:
   name=x["$ref"].split("/")[-1]
   return {**walk(schema["$defs"][name]),**walk({k:v for k,v in x.items() if k!="$ref"})}
  return {k:walk(v) for k,v in x.items() if k not in ("$defs","discriminator")}
 return walk(schema)
from contracts.d2_dialogue_result import PriceOperation,parse_d2_text_reply,D2RejectedOperation,split_d2_text_reply
from core.one_call_prompt_contract import D2_OPERATIONS_INSTRUCTIONS
IDS={'nobel':'a44179d1eadc4fe6a5ab5263d2592a99','price_followup':'5a1415826f0b4464922a79e155d3cd8b','one_tooth':'0f6d3339591d44a8b461d0dda1144565','warranty':'af71978b5e274ffe8eec6d00d392da63','prosthetics':'d374e0917c554538af43364c665a3023','implantation':'a04ffecf944c48da9386a730686d9523','all_on_6':'97a89c3af5b74f778512fb4d80eae237'}
def tool_prompt():
 s=D2_OPERATIONS_INSTRUCTIONS.replace('API tools are not available. Do not wrap the answer in JSON or put it in metadata.','The only API tool is show_price. Do not wrap the ordinary answer in JSON or put it in metadata.')
 s=s.replace('Code-owned action requests and optional sources go in one final metadata block.','Request prices using the show_price API tool. Other action requests and optional sources go in one final metadata block.')
 s=s.replace('actions is an ordered list of {"name":"...","arguments":{...}} for show_price,\nshow_contacts, start_booking, off_topic or handoff.','actions is an ordered list of {"name":"...","arguments":{...}} for\nshow_contacts, start_booking, off_topic or handoff. show_price belongs only in the API tool, never this list.')
 start=s.index('Example price:')
 s=s[:start]+'''Example price: call show_price with {"target":{"type":"service","id":"classic"},"brand_id":"nobel_biocare","volume":{"extent":"one_tooth"}}.
A price-only request may have no prose, only its valid show_price call. Sources alone
are never an answer: informational questions need actual ordinary text.
'''
 return s

def main():
 a=argparse.ArgumentParser();a.add_argument('--live',action='store_true');args=a.parse_args()
 OUT.mkdir(parents=True,exist_ok=True)
 captured={}
 for line in (ROOT/'logs/d2_full_audit.jsonl').open(encoding='utf-8'):
  r=json.loads(line)
  if r.get('event')=='provider_messages' and r.get('trace_id') in IDS.values():captured[r['trace_id']]=[r['system'],r['user']]
 cells,view=prepare()
 cases=[{'case':name,'messages':captured[tid]} for name,tid in IDS.items()]
 cases.append(next(c for c in cells if c['case']=='mixed'))
 schema=PriceOperation.model_json_schema()
 for k in ('kind','request_id'):schema['properties'].pop(k,None)
 schema['required']=[k for k in schema.get('required',[]) if k not in ('kind','request_id')]
 schema=inline_schema(schema)
 tool={'type':'function','function':{'name':'show_price','description':'Show the requested service or direction price using the clinic catalog. Code selects and renders the price card.','parameters':schema}}
 for c in cases:
  assert D2_OPERATIONS_INSTRUCTIONS in c['messages'][0]['content'],c['case']
  c['hash']=hashlib.sha256(json.dumps(c['messages'],ensure_ascii=False).encode()).hexdigest()
 dump(OUT/'manifest.json',{'budget':32,'model':'qwen3.8-flash','history':'paired frozen captured contexts; warranty from previous synthetic integrated run; mixed fresh','cases':[{'case':c['case'],'sha256':c['hash']} for c in cases],'tool':tool,'tool_instructions':tool_prompt()})
 if not args.live:print('Prepared 32 calls; provider calls 0; all 8 prompts match current instructions.');return
 ledger_path=OUT/'attempts.json'
 if ledger_path.exists():raise RuntimeError('existing ledger: no repeat')
 from dotenv import load_dotenv
 load_dotenv(ROOT/'.env')
 from config import CHAT_API_KEY,CHAT_BASE_URL,DEFAULT_LLM_MODEL
 from core.alibaba_openai_transport_policy import validate_alibaba_chat_base_url
 validate_alibaba_chat_base_url(CHAT_BASE_URL)
 assert DEFAULT_LLM_MODEL=='qwen3.8-flash'
 from openai import OpenAI
 ledger=[];dump(ledger_path,ledger)
 with OpenAI(api_key=CHAT_API_KEY,base_url=CHAT_BASE_URL,max_retries=0,timeout=45) as client:
  for repeat in range(2):
   for c in cases:
    for variant in (('tail','tool') if repeat==0 else ('tool','tail')):
     assert len(ledger)<32
     messages=copy.deepcopy(c['messages']); kwargs={}
     if variant=='tool':
      messages[0]['content']=messages[0]['content'].replace(D2_OPERATIONS_INSTRUCTIONS,tool_prompt())
      kwargs={'tools':[tool],'tool_choice':'auto'}
     row={'repeat':repeat+1,'case':c['case'],'variant':variant,'status':'reserved','input_sha256':c['hash']};ledger.append(row);dump(ledger_path,ledger)
     t=time.monotonic()
     try:
      resp=client.chat.completions.create(model=DEFAULT_LLM_MODEL,messages=messages,temperature=0,max_completion_tokens=1024,extra_body={'enable_thinking':False},**kwargs)
      ch=resp.choices[0];raw=ch.message.content or '';calls=ch.message.tool_calls or []
      row.update(status='received',raw=raw,tool_calls=[x.model_dump() for x in calls],finish_reason=ch.finish_reason,usage=resp.usage.model_dump())
      parsed=None
      if raw.strip():
       try:parsed=parse_d2_text_reply(raw,active_service_ids=view.active_service_catalog.active_service_ids)
       except Exception as exc:row['text_parse_error']=str(exc)[:160]
      tailprices=[b.model_dump(mode='json') for b in parsed.blocks if isinstance(b,PriceOperation)] if parsed else []
      prices=[];errors=[]
      for i,call in enumerate(calls):
       try:
        assert call.function.name=='show_price'
        data=_loads_strict_json_object(call.function.arguments)
        assert not {'kind','request_id','content_text'}.intersection(data)
        action=PriceOperation.model_validate(dict(data,kind='price',request_id=f'r{i+1}'))
        if action.clarification is not None and any(v not in view.active_service_catalog.active_service_ids for v in action.clarification.choices):raise ValueError('clarify_service_not_active')
        prices.append(action.model_dump(mode='json'))
       except Exception as exc:errors.append(type(exc).__name__+':'+str(exc)[:160])
      row.update(prices=tailprices if variant=='tail' else prices,tool_errors=errors,wrong_channel_prices=tailprices if variant=='tool' else [],prose=split_d2_text_reply(raw)[0],rejected=[b.kind for b in parsed.blocks if isinstance(b,D2RejectedOperation)] if parsed else [])
     except Exception as exc:row.update(error_type=type(exc).__name__,http_status=getattr(exc,'status_code',None))
     row['ms']=round((time.monotonic()-t)*1000);dump(ledger_path,ledger)
     print(json.dumps({k:row.get(k) for k in ('repeat','case','variant','status','error_type','finish_reason')},ensure_ascii=False),flush=True)
     if row.get('http_status') in (401,402,403,429):return
if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf-8');main()
