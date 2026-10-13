"""Isolated real-HTTP card experiment; explicit --live, otherwise offline smoke.

All conversations are synthetic. No production route, tenant file or database is
edited. Candidate protocols and the hard provider budget live in d2_card_candidates.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import shutil
import smtplib
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUTPUT = ROOT / "logs" / "cards-deepseek-20261012"
CHAINS = {
    "A": ["Nobel ставите?", "А сколько стоит?", "Один зуб", "А гарантия?"],
    "B": ["Сколько стоит имплантация?", "Сколько стоит All-on-6?"],
    "C": ["Сколько стоит протезирование?"],
    "D": ["Расскажите про импланты Nobel и сколько стоит на один зуб?"],
}


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


@contextmanager
def isolated_http(root):
    """Set paths before runtime imports; protect every SQLite connection."""
    import pytest

    root.mkdir(parents=True, exist_ok=False)
    clients = root / "clients"
    for tenant in ("demo", "nikadent"):
        shutil.copytree(ROOT / "clients" / tenant, clients / tenant)
    (root / "logs").mkdir()
    (root / "sessions").mkdir()
    real_connect = sqlite3.connect

    def connect(database, *args, **kwargs):
        if not Path(database).resolve().is_relative_to(root.resolve()):
            raise AssertionError("experiment_sqlite_outside_isolation")
        return real_connect(database, *args, **kwargs)

    def forbidden(*args, **kwargs):
        raise AssertionError("experiment_smtp_forbidden")

    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("BOT_LOG_DIR", str(root / "logs"))
        patch.setenv("D2_CLIENTS_ROOT", str(clients))
        patch.setenv("D2_DIALOGUE_DB_PATH", str(root / "d2.sqlite"))
        patch.setattr(sqlite3, "connect", connect)
        patch.setattr(smtplib, "SMTP", forbidden)
        patch.setattr(smtplib, "SMTP_SSL", forbidden)
        import session
        session.clear_session_store_cache()
        patch.setattr(session, "sqlite_path_for_client",
                      lambda client: str(root / "sessions" / f"{client}.sqlite"))
        import core.client_config_loader as loader
        import core.client_runtime as runtime
        patch.setattr(loader, "_REPO_ROOT", str(root))
        patch.setattr(runtime, "_REPO_ROOT", str(root))
        import config
        patch.setattr(config, "ALLOWED_CLIENTS", frozenset({"demo", "nikadent"}))
        import app
        import core.d2_http_adapter as adapter
        try:
            yield app.app.test_client(), patch, adapter
        finally:
            session.clear_session_store_cache()


def cards(body):
    return [part for part in body.get("ui", {}).get("body_parts", [])
            if part.get("kind") == "price_card"]


def choose_tab(body):
    """Only use a ref actually published in this exact response."""
    choices = [choice for card in cards(body) for choice in card.get("choices", [])
               if choice.get("reply_id", "").startswith("price_select:")]
    current = {row.get("offer_id") for card in cards(body)
               for row in card.get("price", {}).get("rows", [])}
    choices = [choice for choice in choices
               if choice["reply_id"].split(":", 1)[1] not in current]
    return next((choice for choice in choices
                 if "nobel" in json.dumps(choice, ensure_ascii=False).lower()),
                choices[0] if choices else None)


class ObservedProvider:
    def __init__(self, delegate):
        self.delegate = delegate
        self.calls = 0
        self.button = False
        self.histories = []

    def generate(self, request):
        if self.button:
            raise AssertionError("published_tab_must_not_call_model")
        self.calls += 1
        self.histories.append([
            {"user_text": pair.patient_text, "assistant_text": pair.assistant_text,
             "offer_ids": [offer.offer_id for offer in pair.offers]}
            for pair in request.context.ordinary.dialogue_pairs
        ])
        return self.delegate.generate(request)


class SmokeProvider:
    """Constant valid card; validates plumbing, never semantic quality."""
    def generate(self, request):
        metadata = {"actions": [{"name": "show_price", "arguments": {
            "target": {"type": "service", "id": "classic"},
            "volume": {"extent": "one_tooth"},
        }}]}
        return "\n<D2_META>\n" + json.dumps(metadata) + "\n</D2_META>"


def run(output, *, live=False):
    output = Path(output).resolve()
    if output != OUTPUT.resolve() and not output.is_relative_to(OUTPUT.resolve()):
        raise ValueError("output_must_be_in_fixed_experiment_logs")
    # Never resume/overwrite a run: a fresh attempt ledger is mandatory.
    if output.exists() and any(output.iterdir()):
        raise ValueError("existing_experiment_output_refused")
    output.mkdir(parents=True, exist_ok=True)
    turns = []
    with isolated_http(output / "isolated") as (client, patch, adapter):
        if live:
            from scripts.d2_card_candidates import ARMS, CandidateProvider, Runner
            runner = Runner(output, live=True)
            factories = [(arm, CandidateProvider(arm, runner)) for arm in ARMS]
        else:
            factories = [("offline-smoke", SmokeProvider())]
        for arm, delegate in factories:
            provider = ObservedProvider(delegate)
            patch.setattr(adapter, "D2HttpProvider", lambda **kwargs: provider)
            for repeat in (1, 2):
                for chain, questions in CHAINS.items():
                    sid = f"cards-{arm}-{repeat}-{chain}"
                    latest = None

                    def post(question, turn_id, *, choice=None):
                        payload = {"client_id": "demo", "sid": sid,
                                   "request_id": turn_id, "q": question}
                        if choice:
                            payload.update(ref=choice["reply_id"], ui_revision=latest["revision"])
                        before = provider.calls
                        provider.button = choice is not None
                        entry = {"arm": arm, "repeat": repeat, "chain": chain,
                                 "input": payload, "kind": "tab" if choice else "text"}
                        try:
                            response = client.post("/ask", json=payload)
                            body = response.get_json(silent=True) or {}
                            entry.update(http_status=response.status_code, response=body,
                                         failure=None if response.status_code == 200 else body.get("error", "http_failure"))
                            entry["cards"] = [{"offer_id": row.get("offer_id"),
                                               "amount": row.get("amount"),
                                               "price_display_text": row.get("price_display_text")}
                                              for card in cards(body)
                                              for row in card.get("price", {}).get("rows", [])]
                            return body if response.status_code == 200 else None
                        except Exception as exc:
                            entry.update(http_status=None, failure=type(exc).__name__)
                            return None
                        finally:
                            provider.button = False
                            # A generate may contain multiple network calls;
                            # attempts.json is the authoritative live-call ledger.
                            entry["provider_generate_calls"] = provider.calls - before
                            entry["input_histories"] = provider.histories[before:]
                            turns.append(entry)
                            dump(output / "turns.json", turns)

                    for index, question in enumerate(questions):
                        body = post(question, f"text-{index + 1}")
                        if body is not None:
                            latest = body
                        if chain == "A" and index == 2:
                            choice = choose_tab(latest) if latest else None
                            if choice:
                                selected = post("", "published-tab", choice=choice)
                                if selected is not None:
                                    latest = selected
                            else:
                                turns.append({"arm": arm, "repeat": repeat, "chain": chain,
                                              "kind": "tab_skipped", "reason": "no_published_brand_tab"})
        dump(output / "turns.json", turns)
        if not live:
            text_turns = [turn for turn in turns if turn["kind"] == "text"]
            tab_turns = [turn for turn in turns if turn["kind"] == "tab"]
            assert len(text_turns) == 16 and len(tab_turns) == 2
            assert all(turn["http_status"] == 200 for turn in text_turns + tab_turns)
            assert all(turn["provider_generate_calls"] == 0 and turn["cards"] for turn in tab_turns)
            assert all(turn["cards"] for turn in text_turns)
            for turn in text_turns:
                history = turn["input_histories"][0]
                if turn["input"]["request_id"] == "text-1":
                    assert history == [], "fresh_chain_history_not_empty"
                else:
                    assert history, "committed_history_missing"
    return turns


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--live", action="store_true")
    mode.add_argument("--offline-smoke", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or (OUTPUT if args.live else OUTPUT / "offline-smoke")
    turns = run(output, live=args.live)
    print(json.dumps({"output": str(output), "turns": len(turns),
                      "http_failures": sum(bool(t.get("failure")) for t in turns)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
