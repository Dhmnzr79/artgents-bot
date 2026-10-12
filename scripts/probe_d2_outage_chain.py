"""Bounded diagnostic comparison of the same FullContext through four transports."""
from __future__ import annotations
import argparse
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.probe_d2_native_models import dump, prepare


def baseline_contract():
    path = "contracts/d2_dialogue_result.py"
    source = subprocess.check_output(["git", "show", f"e4a098a:{path}"], cwd=ROOT).decode("utf-8")
    module = types.ModuleType("outage_baseline_contract")
    sys.modules[module.__name__] = module
    exec(compile(source, f"baseline:{path}", "exec"), module.__dict__)
    prompt_source = subprocess.check_output(["git", "show", "e4a098a:core/one_call_prompt_contract.py"], cwd=ROOT).decode("utf-8")
    for node in ast.parse(prompt_source).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "D2_OPERATIONS_INSTRUCTIONS" for t in node.targets):
            return module, ast.literal_eval(node.value)
    raise ValueError("baseline_instructions_missing")


def inline_schema(schema):
    def walk(value):
        if isinstance(value, list):
            return [walk(v) for v in value]
        if not isinstance(value, dict):
            return value
        if "$ref" in value:
            parts = value["$ref"].split("/")
            if parts[:2] != ["#", "$defs"]:
                raise ValueError("nonlocal_schema_ref")
            expanded = walk(schema["$defs"][parts[2]])
            return {**expanded, **walk({k:v for k,v in value.items() if k != "$ref"})}
        result = {k:walk(v) for k,v in value.items() if k not in {"$defs", "discriminator"}}
        variants = result.get("anyOf", result.get("oneOf", []))
        if variants and all(v.get("type") in {"object", "null"} for v in variants) and any(v.get("type")=="object" for v in variants):
            # Experimental provider projection: explicit object type; optional
            # fields may be omitted. This narrows explicit null, not runtime types.
            result["type"] = "object"
        return result
    return walk(schema)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / "logs"):
        raise ValueError("output_outside_logs")
    output.mkdir(parents=True, exist_ok=True)
    os.environ["BOT_LOG_DIR"] = str(output / "harness-logs")
    os.environ["D2_FULL_AUDIT_LOG"] = "0"
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    from config import CHAT_API_KEY, CHAT_BASE_URL, DEFAULT_LLM_MODEL
    from core.alibaba_openai_transport_policy import validate_alibaba_chat_base_url
    validate_alibaba_chat_base_url(CHAT_BASE_URL)
    deep_base = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    if deep_base not in {"https://api.deepseek.com", "https://api.deepseek.com/v1"}:
        raise ValueError("deepseek_endpoint_not_approved")
    if DEFAULT_LLM_MODEL != "qwen3.8-flash" or os.getenv("DEEPSEEK_MODEL") != "deepseek-flash":
        raise ValueError("models_changed")
    if not CHAT_API_KEY or not os.getenv("DEEPSEEK_API_KEY"):
        raise ValueError("key_missing")
    cells, view = prepare()
    current = cells[0]
    legacy, legacy_instructions = baseline_contract()
    schema = legacy.D2DialogueResult.model_json_schema()
    from scripts.native_transport_archive import ARCHIVED_D2_INSTRUCTIONS as D2_OPERATIONS_INSTRUCTIONS
    questions = {"nobel":"Nobel ставите?", "fear":"Я боюсь боли при имплантации.",
        "healing":"Сколько приживается имплант?", "anesthesia":"Больно ли ставить имплант и какая анестезия?",
        "price":"Сколько стоит Nobel на один зуб?"}
    configs = {
        "qwen":(DEFAULT_LLM_MODEL, CHAT_API_KEY, CHAT_BASE_URL, {"enable_thinking":False}, 20),
        "deepseek":("deepseek-flash", os.getenv("DEEPSEEK_API_KEY"), deep_base, {"thinking":{"type":"disabled"}}, 5),
    }
    jobs = []
    for provider in configs:
        for variant in (("current", "tools_off", "inlined_tools", "baseline_json") if provider == "qwen" else ("current",)):
            for name, question in questions.items():
                messages = copy.deepcopy(current["messages"])
                messages[1]["content"] = messages[1]["content"].rsplit("=== USER_MESSAGE ===",1)[0] + "=== USER_MESSAGE ===\n" + question
                tools = copy.deepcopy(current["tools"])
                if variant == "tools_off":
                    tools = None
                if variant == "inlined_tools":
                    for t in tools:
                        t["function"]["parameters"] = inline_schema(t["function"]["parameters"])
                    assert "$ref" not in json.dumps(tools) and "$defs" not in json.dumps(tools)
                if variant == "baseline_json":
                    tools = None
                    messages[0]["content"] = messages[0]["content"].replace(D2_OPERATIONS_INSTRUCTIONS, legacy_instructions)
                    marker = "=== SERVICE_REFERENCE_CATALOG ==="
                    head, tail = messages[0]["content"].split(marker,1)
                    messages[0]["content"] = head + "=== D2_RESULT_SCHEMA ===\n" + json.dumps(schema, ensure_ascii=False,separators=(",",":")) + "\n\n" + marker + tail
                wire = {"messages":messages}
                if tools is not None:
                    wire.update(tools=tools, tool_choice="auto")
                if variant == "baseline_json":
                    wire["response_format"] = {"type":"json_object"}
                fingerprint = hashlib.sha256(json.dumps(wire,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
                jobs.append({"provider":provider,"variant":variant,"case":name,"question":question,"wire":wire,"sha256":fingerprint})
    ledger_path = output / "attempts.json"
    if ledger_path.exists():
        raise ValueError("ledger_exists_do_not_repeat")
    dump(output / "manifest.json", {"budget":{"qwen":20,"deepseek":5}, "snapshot":view.fingerprint,
        "history":"empty synthetic", "jobs":[{k:v for k,v in j.items() if k != "wire"} for j in jobs]})
    dump(output / "schemas.json", {"current":current["tools"], "inlined":[j for j in jobs if j["variant"]=="inlined_tools"][0]["wire"]["tools"],"baseline":schema})
    if not args.live:
        print(json.dumps({"prepared":len(jobs),"provider_calls":0,"runtime_unchanged":True}))
        return
    ledger = []
    dump(ledger_path, ledger)
    from openai import OpenAI
    from scripts.native_transport_archive import _native_reply
    from scripts.native_transport_archive import parse_d2_native_reply
    from contracts.d2_dialogue_result import D2RejectedOperation
    for provider, (model,key,base,extra,limit) in configs.items():
        with OpenAI(api_key=key,base_url=base,max_retries=0,timeout=20) as client:
            for job in (j for j in jobs if j["provider"]==provider):
                if sum(r["provider"]==provider for r in ledger) >= limit:
                    raise ValueError("budget_exhausted")
                row = {k:v for k,v in job.items() if k != "wire"}
                row.update(status="reserved",requested_model=model)
                ledger.append(row)
                dump(ledger_path, ledger)
                started = time.monotonic()
                try:
                    # Qwen matches current runtime token argument/timeout/thinking configuration.
                    tokens = {"max_completion_tokens":1024} if provider=="qwen" else {"max_tokens":1024}
                    response = client.chat.completions.create(model=model,temperature=0,extra_body=extra,**tokens,**job["wire"])
                    choice = response.choices[0]
                    row.update(status="received",observed_model=response.model,finish_reason=choice.finish_reason,
                        usage=response.usage.model_dump() if response.usage else None,
                        raw_message=choice.message.model_dump(exclude_none=True))
                    try:
                        if job["variant"]=="baseline_json":
                            result = legacy.validate_d2_payload(json.loads(choice.message.content),active_service_ids=view.active_service_catalog.active_service_ids)
                            row["parser"] = {"status":"accepted","blocks":[b.kind for b in result.blocks]}
                        else:
                            result = parse_d2_native_reply(_native_reply(choice.message),active_service_ids=view.active_service_catalog.active_service_ids)
                            row["parser"] = {"status":"accepted","blocks":[b.kind for b in result.blocks],"rejected_actions":sum(isinstance(b,D2RejectedOperation) for b in result.blocks)}
                    except Exception as exc:
                        row["parser"] = {"status":"rejected","error":str(exc)[:220]}
                except Exception as exc:
                    row.update(status="error",error_type=type(exc).__name__,http_status=getattr(exc,"status_code",None))
                row["duration_ms"] = round((time.monotonic()-started)*1000)
                dump(ledger_path,ledger)
                msg = row.get("raw_message",{})
                print(json.dumps({"provider":provider,"variant":row["variant"],"case":row["case"],"status":row["status"],
                    "text":bool(msg.get("content")),"tools":[c["function"]["name"] for c in msg.get("tool_calls",[])],"parser":row.get("parser")}),flush=True)
                if row.get("http_status") in {401,402,403,429}:
                    break


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
