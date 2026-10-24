"""Controlled Selectel-only audit: two frozen inputs, four predeclared settings.

Default offline. --live allows at most eight SDK calls, retries=0. No runtime edits.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import compare_selectel_deepseek as pair
from scripts import selectel_d2_regression as observation
from scripts.experiment_d2_cards import isolated_http, cards

OUTPUT = ROOT / "logs" / "selectel-thinking-controls-20261024"
REFERENCE = ROOT / "logs" / "provider-single-call-20261024" / "live"
CASES = (2, 7)
MODES = ("current_1536", "current_4096", "nested_off_4096", "nested_on_4096")
MAX_CALLS = 8


def settings(kwargs, mode):
    if mode not in MODES:
        raise ValueError("unapproved_mode")
    result = deepcopy(kwargs)
    if result.get("extra_body") != {"enable_thinking": False}:
        raise ValueError("unexpected_original_thinking_settings")
    result["timeout"] = 60  # Common to all modes; allow a larger output to finish.
    result["max_completion_tokens"] = 1536 if mode == "current_1536" else 4096
    if mode.startswith("nested_"):
        result["extra_body"] = {"chat_template_kwargs": {
            "enable_thinking": mode == "nested_on_4096"}}
    return result


def run(*, live=False):
    from dotenv import dotenv_values
    from openai import OpenAI

    output = OUTPUT / ("live" if live else "offline")
    if output.exists():
        raise ValueError("existing_experiment_refused")
    output.mkdir(parents=True)
    reference = json.loads((REFERENCE / "manifest.json").read_text(encoding="utf-8"))
    env = dotenv_values(ROOT / ".env")
    key = env.get("CHAT_API_KEY")
    if live and (not key or key == "PASTE_SELECTEL_API_KEY_HERE"):
        raise ValueError("selectel_key_missing")

    class Clock(datetime):
        instant = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)
        @classmethod
        def now(cls, tz=None):
            return cls.instant.astimezone(tz) if tz else cls.instant.replace(tzinfo=None)

    results, captured = [], {}
    with isolated_http(output / "isolated") as (client, patch, adapter):
        import config
        import llm
        import core.one_call_prompt_contract as contract
        from core.d2_live_provider import D2HttpProvider
        from orchestration import route_guards

        root = output / "isolated"
        model, base = pair.ARMS["selectel"]
        patch.setenv("D2_FULL_AUDIT_LOG", "0")
        patch.setenv("CHAT_BASE_URL", base)
        patch.setattr(adapter, "datetime", Clock)
        patch.setattr(contract, "ONE_CALL_MODEL_SNAPSHOT", "paired-current-d2")
        patch.setattr(config, "CHAT_BASE_URL", base)
        patch.setattr(config, "CHAT_API_KEY", key or "offline-key")
        patch.setattr(llm, "CHAT_BASE_URL", base)
        patch.setattr(llm, "QWEN_ENABLE_THINKING", False)
        patch.setattr(adapter, "D2HttpProvider", lambda **kwargs: D2HttpProvider(model=model, **kwargs))
        patch.setattr(observation, "MAX_CALLS", MAX_CALLS)
        patch.setattr(observation, "MODEL", model)

        fixtures = {}
        for case in CASES:
            source = REFERENCE / "isolated" / "fixtures" / str(case)
            target = root / "references" / str(case)
            shutil.copytree(source, target)
            names = [str(p.relative_to(target)) for p in target.rglob("*.sqlite")]
            if "d2.sqlite" not in names:
                raise ValueError("reference_state_missing")
            fixtures[case] = (target, names)

        def restore(case):
            target, names = fixtures[case]
            pair.restore_state(root, target, names)
            Clock.instant = datetime(2026, 10, 24, 12, tzinfo=timezone.utc) + timedelta(seconds=case)
            with route_guards._IP_RATE_LOCK:
                route_guards._IP_RATE_BUCKETS.clear()

        def payload(case):
            return {"client_id": "demo", "sid": "paired-nobel" if case == 2 else "paired-mixed",
                    "request_id": f"paired-{case}", "q": reference["cases"][case]["question"]}

        with OpenAI(api_key=key or "offline-key", base_url=base, max_retries=0) as sdk:
            patch.setattr(llm, "chat_client", sdk)
            original_create = sdk.chat.completions.create
            observed = observation.BoundedCalls(output / "calls.json", original_create)
            # Capture original production kwargs before any changed settings/network.
            for case in CASES:
                restore(case)
                def capture(**kwargs):
                    captured[case] = deepcopy(kwargs)
                    raise pair.CaptureStop("offline_only")
                with patch.context() as scoped:
                    scoped.setattr(sdk.chat.completions, "create", capture)
                    client.post("/ask", json=payload(case))
                if case not in captured or pair.payload_hash(captured[case]) != reference["input_hashes"][case]:
                    raise ValueError("input_differs_from_previous_frozen_case")
                for mode in MODES:
                    settings(captured[case], mode)  # Validate all settings before any call.
            observation.dump(output / "manifest.json", {
                "max_calls": MAX_CALLS, "retries": 0, "cases": {str(c): payload(c)["q"] for c in CASES},
                "modes": {m: {k: settings(captured[CASES[0]], m)[k]
                    for k in ("max_completion_tokens", "timeout", "extra_body")} for m in MODES},
                "previous_first_payloads_equal": True, "runtime_changes": False,
                "sampling": {"temperature": captured[CASES[0]]["temperature"]},
                "cache_flush": False, "reference": str(REFERENCE.relative_to(ROOT)),
                "scope": "Actual Flask /ask, one initial live SDK call per case/mode; not standalone dialogue chains",
                "second_call": "forbidden before network; not a tested adverse-completion flow",
            })
            if not live:
                return {"prepared": True, "calls": 0, "matched_cases": len(captured), "planned_calls": 8}

            for case in CASES:
                # Reverse order for the second case; keep the predefined comparisons.
                order = MODES if case == CASES[0] else tuple(reversed(MODES))
                for mode in order:
                    restore(case)
                    before = len(observed.rows)
                    observed.turn = f"{case}:{mode}"
                    def guarded(**kwargs):
                        if len(observed.rows) != before:
                            raise ValueError("second_live_call_forbidden")
                        if pair.payload_hash(kwargs) != pair.payload_hash(captured[case]):
                            raise ValueError("original_payload_changed")
                        changed = settings(kwargs, mode)
                        response = observed(**changed)
                        row = observed.rows[-1]
                        choices = observation.field(response, "choices", []) or []
                        msg = observation.field(choices[0], "message") if choices else None
                        row["message_content"] = observation.field(msg, "content")
                        row["settings"] = {k: changed[k] for k in ("max_completion_tokens", "timeout", "extra_body")}
                        observation.dump(observed.path, observed.rows)
                        return response
                    with patch.context() as scoped:
                        scoped.setattr(sdk.chat.completions, "create", guarded)
                        started = perf_counter()
                        response = client.post("/ask", json=payload(case))
                        seconds = perf_counter() - started
                    body = response.get_json(silent=True) or {}
                    row = {"case": case, "mode": mode, "question": payload(case)["q"],
                        "http_status": response.status_code, "seconds": round(seconds, 4),
                        "calls": len(observed.rows) - before, "answer": body.get("answer", ""),
                        "cards": cards(body), "error": body.get("error")}
                    results.append(row)
                    observation.dump(output / "turns.json", results)
                    print(json.dumps({k: row[k] for k in ("case", "mode", "http_status", "seconds", "calls")}), flush=True)
                    if any(x["status"] == "failed" for x in observed.rows[before:]):
                        return {"stop": "provider_failure_no_retry", "calls": len(observed.rows), "turns": len(results)}
    return {"calls": len(observed.rows), "turns": len(results)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    print(json.dumps(run(live=parser.parse_args().live)), flush=True)
