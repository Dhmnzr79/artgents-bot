"""Isolated native-channel comparison; never executes actions or changes runtime."""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
LIMIT = 10


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def prepare():
    from contracts.d2_dialogue import D2ProviderInput
    from contracts.d2_dialogue_result import DiscussionScope
    from scripts.native_transport_archive import d2_native_tools
    from contracts.d2_session_context import D2SessionContextProjection, D2OrdinarySessionContext, D2ProjectedDialoguePair
    from contracts.response_plan import SessionKey
    from contracts.response_plan_session import PersistedShownCommercialIds
    from core.d2_tenant_snapshot import load_d2_tenant_snapshot, build_d2_model_view
    from scripts.native_transport_archive import build_archived_messages as build_d2_d1r_messages
    snapshot = load_d2_tenant_snapshot("demo", clients_root=ROOT / "clients")
    view = build_d2_model_view(snapshot)
    context = D2SessionContextProjection(session_key=SessionKey(client_id="demo", sid="native-probe"),
        source_revision=0, source_turn_index=0, freshness="unknown", retained_terminal_state="none",
        retained_shown_ids=PersistedShownCommercialIds())
    offer = json.loads((ROOT / "clients/demo/target_response/pricebook/services/classic.one_tooth.nobel.json").read_text(encoding="utf-8"))
    scope = DiscussionScope(target={"type":"service", "id":"classic"}, brand_id="nobel_biocare", volume={"extent":"one_tooth"})
    history = D2ProjectedDialoguePair(patient_text="Сколько стоит Nobel на один зуб?", committed_at_turn=1,
        assistant_text="Nobel Biocare. " + json.dumps(offer, ensure_ascii=False), price_scope=scope)
    historical = context.model_copy(update={"freshness":"fresh", "source_revision":1, "source_turn_index":1,
        "ordinary":D2OrdinarySessionContext(dialogue_pairs=(history,), discussion_scope=scope)})
    cases = [("nobel_caps", "NObel ставите?", context), ("nobel", "Nobel ставите?", context),
        ("price", "Сколько стоит Nobel на один зуб?", context),
        ("mixed", "Расскажите про импланты Nobel и сколько стоит на один зуб?", context),
        ("warranty", "А гарантия?", historical)]
    cells = []
    for variant in ("current", "no_source_tool"):
        for name, question, ctx in cases:
            request = D2ProviderInput(user_message=question, model_view=view, context=ctx)
            system, user = build_d2_d1r_messages(request)
            tools = d2_native_tools()
            if variant == "no_source_tool":
                # Remove precisely the source-tool paragraph, not other rules or facts.
                start = system["content"].index("Use optional content_source")
                end = system["content"].index("\nD2_SESSION_CONTEXT", start)
                system = {**system, "content":system["content"][:start] + system["content"][end:]}
                tools = [t for t in tools if t["function"]["name"] != "content_source"]
            messages = [system, user]
            cells.append(dict(variant=variant, case=name, question=question, messages=messages, tools=tools,
                sha256=hashlib.sha256(json.dumps(messages, ensure_ascii=False).encode()).hexdigest()))
    return cells, view


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / "logs"):
        raise ValueError("output_must_be_workspace_logs")
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
        raise ValueError("unapproved_deepseek_endpoint")
    if DEFAULT_LLM_MODEL != "qwen3.8-flash" or os.getenv("DEEPSEEK_MODEL") != "deepseek-flash":
        raise ValueError("configured_models_changed")
    configs = {
        "qwen": (DEFAULT_LLM_MODEL, CHAT_API_KEY, CHAT_BASE_URL, {"enable_thinking":False}),
        "deepseek": ("deepseek-flash", os.getenv("DEEPSEEK_API_KEY"), deep_base, {"thinking":{"type":"disabled"}}),
    }
    if any(not c[1] for c in configs.values()):
        raise ValueError("configured_key_missing")
    cells, view = prepare()
    manifest = {"limits":{"qwen":LIMIT,"deepseek":LIMIT}, "snapshot":view.fingerprint,
        "history":"synthetic Demo offer context, not widget projection", "cases":[
        {k:c[k] for k in ("case","variant","question","sha256")} for c in cells]}
    dump(output / "manifest.json", manifest)
    if not args.live:
        print(json.dumps({"prepared":len(cells),"key_present":True,"models":[c[0] for c in configs.values()],"provider_calls":0}))
        return
    ledger_path = output / "attempts.json"
    if ledger_path.exists():
        raise ValueError("existing_live_ledger_do_not_repeat")
    ledger = {p:[] for p in configs}
    dump(ledger_path, ledger)
    from openai import OpenAI
    from scripts.native_transport_archive import _native_reply
    from scripts.native_transport_archive import parse_d2_native_reply
    from contracts.d2_dialogue_result import D2RejectedOperation
    for provider, (model, key, base, extra) in configs.items():
        with OpenAI(api_key=key, base_url=base, max_retries=0, timeout=45) as client:
            for cell in cells:
                if len(ledger[provider]) >= LIMIT:
                    raise ValueError("hard_call_budget_exhausted")
                row = {"provider":provider,"requested_model":model,"case":cell["case"],"variant":cell["variant"],
                    "question":cell["question"],"sha256":cell["sha256"],"status":"reserved"}
                ledger[provider].append(row)
                dump(ledger_path, ledger)  # Reserve durably before network; errors count.
                started = time.monotonic()
                try:
                    response = client.chat.completions.create(model=model, messages=cell["messages"], tools=cell["tools"],
                        tool_choice="auto", temperature=0, max_tokens=1024, extra_body=extra)
                    choice = response.choices[0]
                    reply = _native_reply(choice.message)
                    row.update(status="received", observed_model=response.model, text=reply.text,
                        tool_calls=[{"name":c.name,"arguments":c.arguments} for c in reply.tool_calls],
                        finish_reason=choice.finish_reason, usage=response.usage.model_dump() if response.usage else None)
                    try:
                        result = parse_d2_native_reply(reply, active_service_ids=view.active_service_catalog.active_service_ids)
                        row["parser"] = {"status":"accepted", "blocks":[b.kind for b in result.blocks],
                            "rejected_actions":sum(isinstance(b,D2RejectedOperation) for b in result.blocks),
                            "verified_shape_sources":sum(bool(c.content_ref) for c in (result.source_claims or ())) }
                    except Exception as exc:
                        row["parser"] = {"status":"rejected", "error":str(exc)}
                except Exception as exc:
                    row.update(status="error", error_type=type(exc).__name__, http_status=getattr(exc,"status_code",None))
                row["duration_ms"] = round((time.monotonic()-started)*1000)
                dump(ledger_path, ledger)
                print(json.dumps({"provider":provider,"attempt":len(ledger[provider]),"case":row["case"],
                    "variant":row["variant"],"status":row["status"],"text_nonempty":bool(row.get("text")),
                    "tools":[c["name"] for c in row.get("tool_calls",[])],"parser":row.get("parser")}), flush=True)
                if row.get("http_status") in {401,402,403,429}:
                    break


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
