"""Owner-authorized isolated current-D2 Qwen regression; no alternate prompts.

Default: prepare only. --live permits at most 32 SDK invocations, retries=0.
Reports contain synthetic Demo questions/publications and technical usage only.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from time import perf_counter
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUTPUT = ROOT / "logs" / "selectel-regression-20261024"
MODEL = "qwen3.8-flash-next"
BASE = "https://api.tf.selcloud.ru/v1"
MAX_CALLS = 32
CHAINS = {
    "nobel": ["Nobel ставите?", "А сколько стоит?", "Один зуб", "А гарантия?"],
    "implantation": ["Сколько стоит имплантация?", "Сколько стоит All-on-6?"],
    "prosthetics": ["Сколько стоит протезирование?"],
    "mixed": ["Расскажите про импланты Nobel и сколько стоит на один зуб?"],
}


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def field(obj, key, default=None):
    return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)


class BoundedCalls:
    def __init__(self, path, transport):
        if path.exists():
            raise ValueError("existing_call_ledger_refused")
        self.path, self.transport, self.rows = path, transport, []
        self.turn = None
        dump(self.path, self.rows)

    def __call__(self, **kwargs):
        if kwargs.get("model") != MODEL:
            raise ValueError("unexpected_model")
        if len(self.rows) >= MAX_CALLS:
            raise ValueError("hard_call_budget_exhausted")
        row = {"number": len(self.rows) + 1, "turn": self.turn,
               "phase": "completion" if kwargs.get("tool_choice") == "none" else "initial",
               "status": "reserved"}
        self.rows.append(row)
        dump(self.path, self.rows)  # Reserve before transport; failures consume budget.
        started = perf_counter()
        try:
            response = self.transport(**kwargs)
            usage = field(response, "usage")
            from core.d2_costing import cache_split, token_count
            prompt = token_count(usage, "prompt_tokens")
            completion = token_count(usage, "completion_tokens")
            cached, uncached = cache_split(usage, prompt)
            reasoning = token_count(field(usage, "completion_tokens_details"), "reasoning_tokens")
            choices = field(response, "choices", [])
            first = choices[0] if choices else None
            message = field(first, "message")
            tools = []
            for call in field(message, "tool_calls", []) or []:
                function = field(call, "function")
                arguments = field(function, "arguments", "")
                try:
                    arguments = json.loads(arguments)
                except (TypeError, ValueError):
                    arguments = {"invalid_json": True}
                tools.append({"name": field(function, "name"), "arguments": arguments})
            row.update(status="received", model=field(response, "model"),
                prompt_tokens=prompt, cached_tokens=cached, uncached_tokens=uncached,
                completion_tokens=completion, reasoning_tokens=reasoning,
                finish_reason=field(first, "finish_reason"), tool_calls=tools)
            if None not in (cached, uncached, completion):
                # Screenshot RUB rates. completion already includes reasoning;
                # both output/reasoning have the same supplied rate: count once.
                row["estimated_rub"] = (cached * 2.09 + uncached * 20.85 + completion * 61.3) / 1_000_000
            return response
        except BaseException as exc:
            row.update(status="failed", error_type=type(exc).__name__)
            raise
        finally:
            row["seconds"] = round(perf_counter() - started, 4)
            dump(self.path, self.rows)


def run(*, live=False):
    if OUTPUT.exists():
        raise ValueError("existing_run_refused_no_resume")
    OUTPUT.mkdir(parents=True)
    dump(OUTPUT / "manifest.json", {
        "model": MODEL, "base_url": BASE, "max_calls": MAX_CALLS,
        "repeats": 2, "chains": CHAINS, "current_runtime": True,
        "cache_flush": False, "smtp": False, "api_streaming": False,
        "scope": "Flask test_client /ask + real provider; not browser/network latency or TTFT",
    })
    if not live:
        return {"prepared": True, "provider_calls": 0}

    # Reuse the existing isolated Flask harness: captured tenant copies, strict
    # SQLite path guard, temporary session storage, SMTP/SMTP_SSL forbidden.
    from scripts.experiment_d2_cards import isolated_http, cards
    turns = []
    with isolated_http(OUTPUT / "isolated") as (client, patch, _adapter):
        import config
        import llm
        if config.CHAT_BASE_URL.rstrip("/") != BASE or config.DEFAULT_LLM_MODEL != MODEL:
            raise ValueError("configured_provider_mismatch")
        if not config.CHAT_API_KEY or config.CHAT_API_KEY == "PASTE_SELECTEL_API_KEY_HERE":
            raise ValueError("selectel_key_not_inserted")
        if llm.chat_client.max_retries != 0:
            raise ValueError("sdk_retries_must_be_zero")
        from core.chat_transport_policy import validate_chat_transport_config
        validate_chat_transport_config()
        # No raw provider inputs/outputs. Only final synthetic /ask publications.
        patch.setenv("D2_FULL_AUDIT_LOG", "0")
        observed = BoundedCalls(OUTPUT / "calls.json", llm.chat_client.chat.completions.create)
        patch.setattr(llm.chat_client.chat.completions, "create", observed)
        for repeat in (1, 2):
            for chain, questions in CHAINS.items():
                sid = uuid4().hex
                for index, question in enumerate(questions):
                    observed.turn = f"{repeat}:{chain}:{index + 1}"
                    before = len(observed.rows)
                    # Reserve room for a full two-call turn; don't begin half a turn.
                    if MAX_CALLS - before < 2:
                        dump(OUTPUT / "turns.json", turns)
                        return summarize(observed.rows, turns, "budget_stop")
                    started = perf_counter()
                    response = client.post("/ask", json={"client_id": "demo", "sid": sid,
                        "request_id": uuid4().hex, "q": question})
                    seconds = round(perf_counter() - started, 4)
                    body = response.get_json(silent=True) or {}
                    entry = {"turn": observed.turn, "repeat": repeat, "chain": chain,
                        "question": question, "http_status": response.status_code,
                        "seconds": seconds, "calls": len(observed.rows) - before,
                        "answer": body.get("answer", ""), "cards": cards(body),
                        "error": body.get("error")}
                    turns.append(entry)
                    dump(OUTPUT / "turns.json", turns)
                    print(json.dumps({k: entry[k] for k in
                        ("turn", "http_status", "seconds", "calls")}), flush=True)
                    if response.status_code != 200:
                        # Model-contract failures are evidence; continue independent
                        # chains, but don't pretend their failed history completed.
                        if any(r["status"] == "failed" for r in observed.rows[before:]):
                            return summarize(observed.rows, turns, "transport_failure_stop")
                        break
        return summarize(observed.rows, turns, "complete")


def summarize(calls, turns, status):
    received = [row for row in calls if row["status"] == "received"]
    result = {"status": status, "provider_calls": len(calls), "turns": len(turns),
              "http_200": sum(row["http_status"] == 200 for row in turns)}
    for key in ("prompt_tokens", "cached_tokens", "uncached_tokens", "completion_tokens", "reasoning_tokens"):
        result[key] = sum(row[key] for row in received if row.get(key) is not None)
        result[key + "_known_calls"] = sum(row.get(key) is not None for row in received)
    result["estimated_rub"] = round(sum(row.get("estimated_rub", 0) for row in received), 5)
    dump(OUTPUT / "summary.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    arguments = parser.parse_args()
    print(json.dumps(run(live=arguments.live), ensure_ascii=False), flush=True)
