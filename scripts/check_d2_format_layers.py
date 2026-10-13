"""Isolated Qwen format experiment; never changes the HTTP runtime or tenant.

Owner approval and an explicit hard budget are required for --live. No resume,
retry, fallback, sessions, materialization, or raw conversation persistence.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MAX_CALLS = 48
QUESTIONS = (
    ("overview", "Сколько стоит имплантация?"),
    ("nobel", "Сколько стоит имплантация Nobel Biocare?"),
    ("compound", "Сколько стоит отбеливание и где вы находитесь?"),
)
class SmallAction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    action: Literal["price", "clarify_service", "contact"]
    target_type: Literal["topic", "service", "unresolved"] | None = None
    target_id: str | None = None
    brand_id: str | None = None
    choices: tuple[str, ...] = ()
    contact_fields: tuple[str, ...] = ()


class SmallReply(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    actions: tuple[SmallAction, ...] = Field(min_length=1)


SMALL_SCHEMA = SmallReply.model_json_schema()
SHORT_INSTRUCTION = """Understand every independent question and return JSON matching the supplied schema.
For a known direction, request its price overview using a topic target; do not
ask the user to select a method merely because the direction has several services.
For a known service, request that service's price. Preserve an explicitly named
brand. Clarify only genuinely unidentified services. Include a separate contact
action for an address question. Do not quote prices or write prose.
Catalog: topic implantation (имплантация) has classic, all_on_4, all_on_6, one_stage.
Nobel Biocare brand_id=nobel_biocare. Отбеливание service_id=professional_whitening.
Address contact_fields=[contact_address]. There is no preceding conversation.
"""


def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def prepare_cases():
    from scripts.check_d2_structured_output import prepare_cases as originals
    from core.d2_live_provider import build_d2_d1r_messages, d2_strict_response_format
    from core.one_call_prompt_contract import D2_OPERATIONS_INSTRUCTIONS

    base = originals()[1]["request"]
    full_schema = d2_strict_response_format(base)["json_schema"]["schema"]
    cases = []
    for layer in ("small", "full_schema", "full_instructions", "full_context"):
        schema = SMALL_SCHEMA if layer == "small" else full_schema
        wire = ("Return {actions:[...]}; action is price, clarify_service or contact. "
                "Use target_type/target_id, brand_id, choices, contact_fields as needed."
                if layer == "small" else
                "Return {outcome:dialogue,blocks:[...]}; use kind=price/contact, target={type,id}, "
                "brand_id and contact_fields. A genuine unresolved price uses "
                "clarification={missing:service,choices:[...]}. Every block has request_id=r1,r2,...")
        system = SHORT_INSTRUCTION + "\n" + wire
        if layer == "full_instructions":
            system = D2_OPERATIONS_INSTRUCTIONS + "\n" + SHORT_INSTRUCTION + "\n" + wire
        system += "\n=== D2_RESULT_SCHEMA ===\n" + json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
        for name, question in QUESTIONS:
            request = replace(base, user_message=question)
            messages = (build_d2_d1r_messages(request) if layer == "full_context" else (
                {"role": "system", "content": system},
                {"role": "user", "content": question},
            ))
            for repeat in range(2):
                modes = ("json_object", "json_schema") if repeat == 0 else ("json_schema", "json_object")
                for mode in modes:
                    fmt = {"type": "json_object"} if mode == "json_object" else {
                        "type": "json_schema", "json_schema": {
                            "name": "d2_small_probe" if layer == "small" else "d2_dialogue", "strict": True, "schema": schema,
                        },
                    }
                    cases.append(dict(layer=layer, name=name, repeat=repeat, request=request,
                                      messages=messages, response_format=fmt, mode=mode))
    assert len(cases) == MAX_CALLS
    for i in range(0, len(cases), 2):
        assert cases[i]["messages"] == cases[i + 1]["messages"]
    return cases


def assess(case, raw):
    if case["layer"] == "small":
        payload = SmallReply.model_validate_json(raw).model_dump(mode="json", exclude_none=True)
        operations = []
        for item in payload["actions"]:
            op = {"kind": "price" if item["action"] == "clarify_service" else item["action"]}
            for field in ("brand_id", "contact_fields"):
                if field in item:
                    op[field] = item[field]
            if "target_type" in item:
                op["target"] = {"type": item["target_type"], "id": item.get("target_id", "")}
            if item["action"] == "clarify_service":
                op["clarification"] = {"missing": "service", "choices": item.get("choices", [])}
            operations.append(op)
    else:
        from core.one_call_envelope_protocol import parse_production_envelope_json
        request = case["request"]
        result = parse_production_envelope_json(
            raw, active_service_catalog=request.model_view.active_service_catalog,
            service_reference_catalog=request.model_view.service_reference_catalog,
            commercial_fact_catalog=request.model_view.commercial_fact_catalog, d2_contract=True,
        )
        fields = {"kind", "target", "brand_id", "volume", "clarification", "contact_fields"}
        operations = [{k: v for k, v in b.model_dump(mode="json", exclude_none=True).items() if k in fields}
                      for b in result.blocks]
    issues = []
    prices = [op for op in operations if op["kind"] == "price"]
    if len(prices) != 1:
        issues.append("expected_one_price")
    else:
        price = prices[0]
        expected = {"type": "service", "id": "professional_whitening"} if case["name"] == "compound" else {"type": "topic", "id": "implantation"}
        if price.get("target") != expected:
            issues.append("wrong_or_missing_price_target")
        if price.get("clarification"):
            issues.append("unnecessary_clarification")
        if case["name"] == "nobel" and price.get("brand_id") != "nobel_biocare":
            issues.append("nobel_constraint_missing")
        if case["name"] != "nobel" and price.get("brand_id"):
            issues.append("invented_brand")
        volume = price.get("volume") or {}
        if volume.get("extent", "unknown") != "unknown" or volume.get("tooth_count") is not None or volume.get("jaw", "unknown") != "unknown":
            issues.append("invented_volume")
    contacts = [op for op in operations if op["kind"] == "contact"]
    if case["name"] == "compound":
        if not any(set(op.get("contact_fields", [])) & {"contact_address", "contacts"} for op in contacts):
            issues.append("address_omitted")
    elif contacts:
        issues.append("unexpected_contact")
    if any(op["kind"] not in {"price", "contact"} for op in operations):
        issues.append("unexpected_operation")
    return operations, issues


def run(cases, *, output, model, transport):
    if len(cases) != MAX_CALLS:
        raise ValueError("exactly_48_cases_required")
    output.mkdir(parents=True, exist_ok=True)
    path = output / "report.json"
    report = {"model": model, "max_calls": MAX_CALLS, "attempts": 0, "results": []}
    with path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream)
    def save():
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for case in cases:
        if report["attempts"] >= MAX_CALLS:
            raise RuntimeError("budget_exhausted")
        row = {k: case[k] for k in ("layer", "name", "repeat", "mode")}
        row.update(status="reserved", messages_sha256=digest(case["messages"]),
                   format_sha256=digest(case["response_format"]))
        report["results"].append(row)
        report["attempts"] += 1
        save()
        stage = "transport"
        try:
            reply = transport(model=model, temperature=0, max_completion_tokens=1024, timeout=20,
                              messages=case["messages"], response_format=case["response_format"],
                              provider_call_source="d2_format_layers_probe")
            stage = "parse"
            choice = reply.choices[0]
            row["finish_reason"] = choice.finish_reason if choice.finish_reason in {"stop", "length", "content_filter"} else "other"
            row["raw_sha256"] = sha256(choice.message.content.encode()).hexdigest()
            usage = getattr(reply, "usage", None)
            row["usage"] = {k: v for k in ("prompt_tokens", "completion_tokens", "total_tokens")
                            if type(v := getattr(usage, k, None)) is int and v >= 0}
            operations, issues = assess(case, choice.message.content)
            row.update(status="parser_accepted", operations=operations, semantic_issues=issues,
                       target_checks_pass=not issues)
        except Exception as exc:
            row.update(status="failed", stage=stage, error_type=type(exc).__name__)
            save()
            if stage == "transport":
                break
        save()
        print(f"{report['attempts']}/{MAX_CALLS} {row['layer']} {row['name']} {row['mode']}: {row['status']} {row.get('semantic_issues', [])}", flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--max-calls", type=int, choices=[MAX_CALLS])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.live and (args.max_calls != MAX_CALLS or args.output is None):
        parser.error("live requires --max-calls 48 and a fresh output directory")
    if not args.live:
        cases = prepare_cases()
        print(json.dumps({"provider_calls": 0, "cases": len(cases), "max_calls": MAX_CALLS}))
        return
    os.environ["BOT_LOG_DIR"] = str(args.output.resolve())
    os.environ["D2_FULL_AUDIT_LOG"] = "0"
    from config import DEFAULT_LLM_MODEL
    from llm import chat_client, chat_completions_create
    if chat_client.max_retries != 0:
        raise RuntimeError("zero_sdk_retries_required")
    report = run(prepare_cases(), output=args.output, model=DEFAULT_LLM_MODEL, transport=chat_completions_create)
    print("EVIDENCE", args.output, flush=True)
    print(json.dumps({"attempts": report["attempts"], "results": len(report["results"])}))


if __name__ == "__main__":
    main()
