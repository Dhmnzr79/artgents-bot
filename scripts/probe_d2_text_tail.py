"""Twelve-call experiment of ordinary text plus optional metadata; no runtime hook."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.probe_d2_native_models import dump
from core.d2_live_provider import build_d2_d1r_messages
from contracts.d2_dialogue_result import parse_d2_text_reply


def prepare():
    from contracts.d2_dialogue import D2ProviderInput
    from contracts.d2_dialogue_result import DiscussionScope
    from contracts.d2_session_context import D2SessionContextProjection,D2OrdinarySessionContext,D2ProjectedDialoguePair
    from contracts.response_plan import SessionKey
    from contracts.response_plan_session import PersistedShownCommercialIds
    from core.d2_tenant_snapshot import load_d2_tenant_snapshot,build_d2_model_view
    view=build_d2_model_view(load_d2_tenant_snapshot("demo",clients_root=ROOT/"clients"))
    context=D2SessionContextProjection(session_key=SessionKey(client_id="demo",sid="text-tail-probe"),
        source_revision=0,source_turn_index=0,freshness="unknown",retained_terminal_state="none",retained_shown_ids=PersistedShownCommercialIds())
    scope=DiscussionScope(target={"type":"service","id":"classic"},brand_id="nobel_biocare",volume={"extent":"one_tooth"})
    offer=json.loads((ROOT/"clients/demo/target_response/pricebook/services/classic.one_tooth.nobel.json").read_text(encoding="utf-8"))
    pair=D2ProjectedDialoguePair(patient_text="Сколько стоит Nobel на один зуб?",committed_at_turn=1,
        assistant_text="Nobel Biocare. "+json.dumps(offer,ensure_ascii=False),price_scope=scope)
    history=context.model_copy(update={"freshness":"fresh","source_revision":1,"source_turn_index":1,
        "ordinary":D2OrdinarySessionContext(dialogue_pairs=(pair,),discussion_scope=scope)})
    cases=[("nobel","Nobel ставите?",context),("fear","Я боюсь боли при имплантации.",context),
        ("healing","Сколько приживается имплант?",context),("price","Сколько стоит Nobel на один зуб?",context),
        ("mixed","Расскажите про импланты Nobel и сколько стоит на один зуб?",context),("warranty","А гарантия?",history)]
    cells=[]
    for name,q,ctx in cases:
        messages=list(build_d2_d1r_messages(D2ProviderInput(user_message=q,model_view=view,context=ctx)))
        cells.append({"case":name,"question":q,"messages":messages,"sha256":hashlib.sha256(json.dumps(messages,ensure_ascii=False).encode()).hexdigest()})
    return cells,view


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--live",action="store_true")
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    output=args.output.resolve()
    if not output.is_relative_to(ROOT/"logs"):raise ValueError("output_outside_logs")
    output.mkdir(parents=True,exist_ok=True)
    os.environ["BOT_LOG_DIR"]=str(output/"harness-logs")
    os.environ["D2_FULL_AUDIT_LOG"]="0"
    from dotenv import load_dotenv
    load_dotenv(ROOT/".env")
    from config import CHAT_API_KEY,CHAT_BASE_URL,DEFAULT_LLM_MODEL
    from core.alibaba_openai_transport_policy import validate_alibaba_chat_base_url
    validate_alibaba_chat_base_url(CHAT_BASE_URL)
    base=os.getenv("DEEPSEEK_BASE_URL","https://api.deepseek.com").rstrip("/")
    if base not in {"https://api.deepseek.com","https://api.deepseek.com/v1"}:raise ValueError("unapproved_endpoint")
    if DEFAULT_LLM_MODEL!="qwen3.8-flash" or os.getenv("DEEPSEEK_MODEL")!="deepseek-flash":raise ValueError("models_changed")
    configs={"qwen":(DEFAULT_LLM_MODEL,CHAT_API_KEY,CHAT_BASE_URL,{"enable_thinking":False}),
        "deepseek":("deepseek-flash",os.getenv("DEEPSEEK_API_KEY"),base,{"thinking":{"type":"disabled"}})}
    if any(not c[1] for c in configs.values()):raise ValueError("key_missing")
    cells,view=prepare()
    ledger_path=output/"attempts.json"
    if ledger_path.exists():raise ValueError("ledger_exists_do_not_repeat")
    dump(output/"manifest.json",{"budget":{"qwen":6,"deepseek":6},"snapshot":view.fingerprint,
        "history":"synthetic warranty Demo-offer JSON, not live widget history","transport":"no tools, no response_format",
        "cases":[{k:v for k,v in c.items() if k!="messages"} for c in cells]})
    if not args.live:
        print(json.dumps({"prepared":len(cells)*2,"provider_calls":0}));return
    ledger=[]
    dump(ledger_path,ledger)
    from openai import OpenAI
    from contracts.d2_dialogue_result import D2RejectedOperation
    for provider,(model,key,endpoint,extra) in configs.items():
        with OpenAI(api_key=key,base_url=endpoint,max_retries=0,timeout=30) as client:
            for cell in cells:
                if sum(r["provider"]==provider for r in ledger)>=6:raise ValueError("call_budget_exhausted")
                row={k:v for k,v in cell.items() if k!="messages"}
                row.update(provider=provider,requested_model=model,status="reserved")
                ledger.append(row);dump(ledger_path,ledger)
                started=time.monotonic()
                try:
                    tokens={"max_completion_tokens":1024} if provider=="qwen" else {"max_tokens":1024}
                    response=client.chat.completions.create(model=model,messages=cell["messages"],temperature=0,extra_body=extra,**tokens)
                    choice=response.choices[0]
                    row.update(status="received",observed_model=response.model,finish_reason=choice.finish_reason,
                        raw=choice.message.content,usage=response.usage.model_dump() if response.usage else None)
                    try:
                        result=parse_d2_text_reply(choice.message.content,active_service_ids=view.active_service_catalog.active_service_ids)
                        row["parsed"]={"status":"accepted","outcome":result.outcome,
                            "blocks":[b.model_dump(mode="json") if not isinstance(b,D2RejectedOperation) else {"rejected":True,"kind":b.kind,"request_id":b.request_id} for b in result.blocks],
                            "sources":[c.model_dump(mode="json") for c in result.source_claims] if result.source_claims is not None else None}
                    except Exception as exc:row["parsed"]={"status":"rejected","error":str(exc)[:200]}
                except Exception as exc:row.update(status="error",error_type=type(exc).__name__,http_status=getattr(exc,"status_code",None))
                row["duration_ms"]=round((time.monotonic()-started)*1000)
                dump(ledger_path,ledger)
                print(json.dumps({"provider":provider,"case":row["case"],"status":row["status"],
                    "parser":row.get("parsed",{}).get("status"),"kinds":[b.get("kind") for b in row.get("parsed",{}).get("blocks",[])],
                    "source_slots":len(row.get("parsed",{}).get("sources") or [])}),flush=True)
                if row.get("http_status") in {401,402,403,429}:break


if __name__=="__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
