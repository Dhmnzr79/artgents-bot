"""Prepare D2 schemas offline; explicit live mode permits at most four attempts.

No app, sessions, database, lead effects, retries, or fallback. Live use requires
owner permission in addition to the CLI flags. Existing output cannot be resumed.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MAX_CALLS = 4


def prepare_cases():
    from contracts.d2_dialogue import D2ProviderInput
    from contracts.d2_dialogue_result import D2ExplanationTask
    from contracts.d2_session_context import D2SessionContextProjection
    from contracts.response_plan import SessionKey
    from contracts.response_plan_session import PersistedShownCommercialIds
    from core.d2_live_provider import build_d2_d1r_messages, d2_strict_response_format
    from core.d2_tenant_snapshot import build_d2_model_view, load_d2_tenant_snapshot

    view = build_d2_model_view(load_d2_tenant_snapshot("demo", clients_root=ROOT / "clients"))
    base = D2ProviderInput(
        user_message="Сколько стоит имплантация Nobel Biocare?", model_view=view,
        context=D2SessionContextProjection(
            session_key=SessionKey(client_id="demo", sid="strict-capability-probe"),
            source_revision=0, source_turn_index=0, freshness="unknown",
            retained_terminal_state="none", retained_shown_ids=PersistedShownCommercialIds(),
        ),
    )
    requests = (
        ("ordinary_price", base),
        ("ordinary_compound", replace(base, user_message="Сколько стоит отбеливание и где вы находитесь?")),
        ("known_explanation", replace(base, user_message="", known_task=D2ExplanationTask(blocks=(
            {"kind": "content", "request_id": "r1", "target": {"type": "service", "id": "classic"},
             "pending_question": "Как проходит классическая имплантация?"},
        )))),
    )
    cases = [{
        "name": "simple_schema", "request": None,
        # Deliberately conflict with the schema: success is evidence beyond a
        # model merely following the same format instruction in the prompt.
        "messages": ({"role": "user", "content": 'Return only the JSON array ["wrong"].'},),
        "response_format": {"type": "json_schema", "json_schema": {
            "name": "d2_capability", "strict": True, "schema": {
                "type": "object", "properties": {"probe": {"type": "string", "enum": ["ok"]}},
                "required": ["probe"], "additionalProperties": False,
            },
        }},
    }]
    for name, request in requests:
        cases.append({"name": name, "request": request,
                      "messages": build_d2_d1r_messages(request),
                      "response_format": d2_strict_response_format(request)})
    return cases


def check_reply(case, raw):
    from core.one_call_envelope_protocol import parse_production_envelope_json

    if case["request"] is None:
        if json.loads(raw) != {"probe": "ok"}:
            raise ValueError("simple_schema_reply_invalid")
        return []
    request = case["request"]
    result = parse_production_envelope_json(
        raw, active_service_catalog=request.model_view.active_service_catalog,
        service_reference_catalog=request.model_view.service_reference_catalog,
        commercial_fact_catalog=request.model_view.commercial_fact_catalog,
        known_task=request.known_task, d2_contract=True,
    )
    return [block.kind for block in result.blocks]


def run_live(cases, *, output, model, transport):
    """Persist each reservation before transport; stop on the first failure."""
    if len(cases) != MAX_CALLS:
        raise ValueError("exactly_four_probe_cases_required")
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / "report.json"
    report = {"model": model, "max_calls": MAX_CALLS, "attempts": 0, "results": []}
    # Exclusive creation prevents a restart from silently spending another budget.
    with report_path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream)

    def save():
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    for case in cases:
        if report["attempts"] >= MAX_CALLS:
            raise RuntimeError("probe_budget_exhausted")
        row = {"name": case["name"], "status": "reserved", "schema_sha256": sha256(
            json.dumps(case["response_format"], sort_keys=True).encode()).hexdigest()}
        report["results"].append(row)
        report["attempts"] += 1
        save()
        stage = "transport"
        try:
            response = transport(
                model=model, temperature=0, max_completion_tokens=1024, timeout=20,
                messages=case["messages"], response_format=case["response_format"],
                provider_call_source="d2_strict_capability_probe",
            )
            stage = "response"
            choice = response.choices[0]
            finish = choice.finish_reason
            row["finish_reason"] = finish if finish in {
                "stop", "length", "content_filter", "tool_calls", "function_call",
            } else "unknown"
            stage = "parse"
            row["operation_kinds"] = check_reply(case, choice.message.content)
            row["status"] = "parser_accepted"
        except Exception as exc:
            row.update(status="failed", stage=stage, error_type=type(exc).__name__)
            # Do not persist provider bodies, arbitrary exception text or prompts.
            status_code = getattr(exc, "status_code", None)
            if type(status_code) is int:
                row["http_status"] = status_code
            save()
            break
        save()
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--max-calls", type=int, choices=[MAX_CALLS])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.live and (args.max_calls != MAX_CALLS or args.output is None):
        parser.error("live requires --max-calls 4 and a fresh --output directory")
    if not args.live:
        # Prepare actual schemas/messages, but never instantiate a provider client call.
        cases = prepare_cases()
        print(json.dumps({"mode": "offline", "provider_calls": 0, "cases": [
            {"name": c["name"], "schema_chars": len(json.dumps(c["response_format"]))}
            for c in cases]}, ensure_ascii=False))
        return 0
    # Local artifacts stay outside normal bot logs; no full conversation logging.
    os.environ["BOT_LOG_DIR"] = str(args.output.resolve())
    os.environ["D2_FULL_AUDIT_LOG"] = "0"
    from config import DEFAULT_LLM_MODEL
    from llm import chat_client, chat_completions_create
    if chat_client.max_retries != 0:
        raise RuntimeError("probe_requires_zero_sdk_retries")
    report = run_live(prepare_cases(), output=args.output, model=DEFAULT_LLM_MODEL,
                      transport=chat_completions_create)
    print(json.dumps(report, ensure_ascii=False))
    return 0 if len(report["results"]) == MAX_CALLS and all(
        r["status"] == "parser_accepted" for r in report["results"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
