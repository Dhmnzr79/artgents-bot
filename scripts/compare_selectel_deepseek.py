"""Matched current-D2 experiment: max16 calls/arm,32 total; default offline.

Common history is rebuilt offline from the prior reviewed synthetic publications.
Every first SDK payload is matched before live calls; completions use own results.
"""
from __future__ import annotations
import argparse
from collections import deque
from contextlib import closing
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import selectel_d2_regression as observation
from scripts.experiment_d2_cards import isolated_http, cards

BASE_OUTPUT = ROOT / "logs" / "provider-comparison-20261024"
REFERENCE = ROOT / "logs" / "selectel-regression-20261024"
ARMS = {"selectel": ("qwen3.8-flash-next", "https://api.tf.selcloud.ru/v1"),
        "deepseek": ("deepseek-flash", "https://api.deepseek.com")}
RUB_PER_USD = 80.5381  # CBR 2026-10-24, conversion estimate only.


class CaptureStop(RuntimeError):
    pass


def payload_hash(kwargs):
    # Provider/model/extras deliberately differ; the actual content contract doesn't.
    keys = ("messages", "tools", "tool_choice", "temperature", "max_completion_tokens", "timeout")
    return sha256(json.dumps({k: kwargs[k] for k in keys if k in kwargs},
        ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def state_paths(root):
    return sorted({root / "d2.sqlite", *root.joinpath("sessions").glob("*.sqlite"),
                   *root.joinpath("data").rglob("*.sqlite")})


def save_state(root, destination):
    import session
    session.clear_session_store_cache()
    destination.mkdir(parents=True)
    names = []
    for source in state_paths(root):
        if not source.exists():
            continue
        rel = source.relative_to(root)
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(source)) as src, closing(sqlite3.connect(target)) as dst:
            src.backup(dst)
        names.append(str(rel))
    return names


def restore_state(root, source, names):
    import session
    session.clear_session_store_cache()
    wanted = {root / name for name in names}
    for path in state_paths(root):
        if path.exists() and path not in wanted:
            if not path.resolve().is_relative_to(root.resolve()):
                raise ValueError("state_outside_isolation")
            path.unlink()  # Only newly created SQLite files inside this experiment.
    for name in names:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(source / name)) as src, closing(sqlite3.connect(target)) as dst:
            src.backup(dst)


def reference_rows():
    path = REFERENCE / "isolated" / "d2.sqlite"
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        return [json.loads(row[0]) for row in conn.execute(
            "SELECT payload FROM d2_turn_request WHERE status='complete' ORDER BY rowid LIMIT 8")]


def synthetic_message(text=None, tools=()):
    return NS(choices=[NS(message=NS(content=text, tool_calls=list(tools)), finish_reason="stop")],
              model="offline-reference", usage=None)


def reference_replies(record, calls):
    info = record["response"]["resolved"]["information_blocks"]
    text = "\n\n".join(block["display_text"] for block in info) or "<NO_TEXT>"
    sources = [{"content_ref": block["content_ref"],
                "content_section_refs": block["source_section_refs"]}
               for block in info if block.get("content_ref")]
    if sources:
        text += '\n<D2_META>\n' + json.dumps({"sources": sources}, ensure_ascii=False) + '\n</D2_META>'
    initial = next(row for row in calls if row["phase"] == "initial")
    tools = [NS(id=f"reference-{i}", function=NS(name=tool["name"],
                arguments=json.dumps(tool["arguments"], ensure_ascii=False)))
             for i, tool in enumerate(initial["tool_calls"])]
    return [synthetic_message(None, tools), synthetic_message(text)] if tools else [synthetic_message(text)]


def run(*, live=False):
    from time import perf_counter
    from openai import OpenAI
    from dotenv import dotenv_values

    output = BASE_OUTPUT / ("live" if live else "offline")
    if output.exists():
        raise ValueError("existing_run_refused")
    output.mkdir(parents=True)
    reference = reference_rows()  # Read only prior synthetic test DB, before SQLite guard.
    old_calls = json.loads((REFERENCE / "calls.json").read_text(encoding="utf-8"))
    env = dotenv_values(ROOT / ".env")
    keys = {"selectel": env.get("CHAT_API_KEY"), "deepseek": env.get("DEEPSEEK_API_KEY")}
    if live and any(not value or value == "PASTE_SELECTEL_API_KEY_HERE" for value in keys.values()):
        raise ValueError("comparison_key_missing")
    turns, fixtures, expected_hashes = [], [], {}

    class Clock(datetime):
        instant = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)
        @classmethod
        def now(cls, tz=None):
            return cls.instant.astimezone(tz) if tz else cls.instant.replace(tzinfo=None)

    with isolated_http(output / "isolated") as (client, patch, adapter):
        import config
        import llm
        import session
        import core.one_call_prompt_contract as contract
        from core.d2_live_provider import D2HttpProvider
        from core.d2_dialogue_store import D2DialogueStore
        from core.d2_tenant_snapshot import load_d2_tenant_snapshot
        from orchestration import route_guards

        root = output / "isolated"
        patch.setenv("D2_FULL_AUDIT_LOG", "0")
        patch.setattr(adapter, "datetime", Clock)
        # One neutral metadata label; substantive production instructions unchanged.
        patch.setattr(contract, "ONE_CALL_MODEL_SNAPSHOT", "paired-current-d2")
        snapshot = load_d2_tenant_snapshot("demo", clients_root=root / "clients")
        if any(row["catalog_version"] != snapshot.fingerprint for row in reference):
            raise ValueError("reference_catalog_changed")
        with D2DialogueStore(root / "d2.sqlite"):
            pass
        for chain, questions in observation.CHAINS.items():
            for index, question in enumerate(questions):
                number = len(fixtures)
                if reference[number]["dialogue_ref"]["patient_text"] != question:
                    raise ValueError("reference_question_mismatch")
                Clock.instant = datetime(2026, 10, 24, 12, tzinfo=timezone.utc) + timedelta(seconds=number)
                payload = {"client_id": "demo", "sid": f"paired-{chain}",
                           "request_id": f"paired-{number}", "q": question}
                location = root / "fixtures" / str(number)
                names = save_state(root, location)
                buckets = {k: deque(v) for k, v in route_guards._IP_RATE_BUCKETS.items()}
                fixture = {"payload": payload, "location": location, "names": names,
                           "clock": Clock.instant, "buckets": buckets}
                fixtures.append(fixture)
                queue = reference_replies(reference[number], [r for r in old_calls
                    if r["turn"] == f"1:{chain}:{index+1}"])
                def fake_create(**kwargs):
                    if not queue:
                        raise ValueError("reference_extra_call")
                    return queue.pop(0)
                with patch.context() as scoped:
                    scoped.setattr(llm.chat_client.chat.completions, "create", fake_create)
                    result = client.post("/ask", json=payload)
                if result.status_code != 200 or queue:
                    raise ValueError(f"reference_replay_failed_{number}_{result.status_code}")

        clients = {arm: OpenAI(api_key=keys[arm] or "offline-key", base_url=base, max_retries=0)
                   for arm, (_, base) in ARMS.items()}
        original_create = {arm: sdk.chat.completions.create for arm, sdk in clients.items()}
        budgets = {arm: observation.BoundedCalls(output / (arm + "-calls.json"), original_create[arm])
                   for arm in ARMS}
        patch.setattr(observation, "MAX_CALLS", 16)

        def restore(fixture):
            restore_state(root, fixture["location"], fixture["names"])
            Clock.instant = fixture["clock"]
            with route_guards._IP_RATE_LOCK:
                route_guards._IP_RATE_BUCKETS.clear()
                route_guards._IP_RATE_BUCKETS.update({k: deque(v) for k, v in fixture["buckets"].items()})

        def setup_arm(scoped, arm, create):
            model, base = ARMS[arm]
            scoped.setattr(config, "CHAT_BASE_URL", base)
            scoped.setattr(config, "CHAT_API_KEY", keys[arm] or "offline-key")
            scoped.setattr(llm, "CHAT_BASE_URL", base)
            scoped.setattr(llm, "chat_client", clients[arm])
            scoped.setattr(llm, "QWEN_ENABLE_THINKING", False)
            scoped.setattr(adapter, "D2HttpProvider", lambda **kwargs: D2HttpProvider(model=model, **kwargs))
            scoped.setattr(clients[arm].chat.completions, "create", create)
            scoped.setattr(observation, "MODEL", model)
            scoped.setenv("CHAT_BASE_URL", base)

        # Capture BOTH actual first SDK payloads offline before any paid calls.
        for number, fixture in enumerate(fixtures):
            for arm in ARMS:
                restore(fixture)
                def capture(**kwargs):
                    expected_hashes[(number, arm)] = payload_hash(kwargs)
                    raise CaptureStop("offline_payload_captured")
                with patch.context() as scoped:
                    setup_arm(scoped, arm, capture)
                    client.post("/ask", json=fixture["payload"])
            if expected_hashes.get((number, "selectel")) != expected_hashes.get((number, "deepseek")):
                raise ValueError("paired_first_payload_mismatch")
        manifest = {"max_per_arm": 16, "max_total": 32, "retries": 0,
            "arms": ARMS, "synthetic_reference": str(REFERENCE.relative_to(ROOT)),
            "initial_inputs_equal": True, "model_snapshot_label": "paired-current-d2",
            "input_hashes": [expected_hashes[(i, "selectel")] for i in range(8)],
            "fixed_context_time": "2026-10-24T12:00:00Z + case index seconds",
            "completion_inputs": "own frozen code result; not forced equal",
            "timing": "full Flask /ask and SDK; no browser/TTFT", "cache_flush": False,
            "usd_rub_conversion_estimate": RUB_PER_USD}
        observation.dump(output / "manifest.json", manifest)
        if not live:
            for sdk in clients.values():
                sdk.close()
            return {"prepared": True, "provider_calls": 0, "matched_cases": len(fixtures)}

        try:
            for number, fixture in enumerate(fixtures):
                order = ("selectel", "deepseek") if number % 2 == 0 else ("deepseek", "selectel")
                for arm in order:
                    restore(fixture)
                    budget = budgets[arm]
                    if len(budget.rows) > 14 or sum(len(b.rows) for b in budgets.values()) > 30:
                        raise ValueError("insufficient_full_turn_budget")
                    before = len(budget.rows)
                    budget.turn = str(number)
                    def guarded(**kwargs):
                        if len(budget.rows) == before and payload_hash(kwargs) != expected_hashes[(number, arm)]:
                            raise ValueError("live_payload_differs_from_matched_capture")
                        started_at = datetime.now(timezone.utc)
                        response = budget(**kwargs)
                        row = budget.rows[-1]
                        if arm == "deepseek":
                            from core.d2_costing import cost_snapshot
                            cost = cost_snapshot(ARMS[arm][0], started_at, row["cached_tokens"],
                                                 row["uncached_tokens"], row["completion_tokens"])
                            row["estimated_usd"] = cost["estimated_usd"]
                            row["pricing_basis"] = cost["pricing_basis"]
                            row["estimated_rub"] = cost["estimated_usd"] * RUB_PER_USD if cost["estimated_usd"] is not None else None
                            observation.dump(budget.path, budget.rows)
                        return response
                    with patch.context() as scoped:
                        setup_arm(scoped, arm, guarded)
                        started = perf_counter()
                        response = client.post("/ask", json=fixture["payload"])
                        elapsed = perf_counter() - started
                    body = response.get_json(silent=True) or {}
                    entry = {"case": number, "arm": arm, "question": fixture["payload"]["q"],
                        "seconds": round(elapsed, 4), "http_status": response.status_code,
                        "calls": len(budget.rows)-before, "answer": body.get("answer", ""),
                        "cards": cards(body), "error": body.get("error")}
                    turns.append(entry)
                    observation.dump(output / "turns.json", turns)
                    print(json.dumps({k: entry[k] for k in ("case", "arm", "seconds", "http_status", "calls")}), flush=True)
                    if any(r["status"] == "failed" for r in budget.rows[before:]):
                        raise ValueError("transport_failure_stop_no_retry")
        finally:
            for sdk in clients.values():
                sdk.close()
        return {"provider_calls": sum(len(b.rows) for b in budgets.values()), "turns": len(turns)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    print(json.dumps(run(live=parser.parse_args().live)), flush=True)
