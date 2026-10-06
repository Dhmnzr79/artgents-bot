"""Two explicitly authorized fresh-session probes; no retry or runtime edits."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CASES = [("oms", "А взрослому по ОМС можно у вас лечить зубы?"),
         ("braces", "Вы устанавливаете брекеты и сколько это стоит?")]


def save(output, rows, calls):
    (output / "records.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "state.json").write_text(json.dumps({"attempts": calls, "limit": 2}), encoding="utf-8")
    lines = ["# ОМС и брекеты: две новые сессии", "", f"Живых попыток: {calls}/2. Без повторов.", "",
             "Обычный D2, qwen из конфигурации бота, пустой контекст каждого вопроса. Ответы без редакции.", ""]
    for row in rows:
        lines += ["## " + row["question"], "", "### Окончательный ответ бота", "",
                  row.get("answer", "Ответ не опубликован: " + row.get("error", "ожидается")), "",
                  "### Сырой ответ модели", "", "```json", row.get("raw", "Нет ответа"), "```", ""]
    (output / "answers.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    if not args.live:
        from contracts.d2_dialogue_result import D2DialogueResult
        bad = {"outcome": "dialogue", "blocks": [{"kind": "clinic_policy", "request_id": "r1",
               "policy_ids": [0], "age_group": "adult", "context": "general_information"}]}
        from pydantic import ValidationError
        try:
            D2DialogueResult.model_validate(bad)
            raise AssertionError("numeric policy ID unexpectedly accepted")
        except ValidationError as exc:
            print(json.dumps(exc.errors(include_url=False), ensure_ascii=False, default=str))
        bad["blocks"][0]["policy_ids"] = ["no_oms"]
        D2DialogueResult.model_validate(bad)
        print("Offline: same payload with exact string ID validates; zero provider calls.")
        return
    output = Path(tempfile.mkdtemp(prefix="d2-oms-braces-probe-"))
    os.environ["BOT_LOG_DIR"] = str(output)
    os.environ["BOT_LOG_FILE"] = "app.jsonl"
    os.environ["D2_FULL_AUDIT_LOG"] = "0"
    from config import DEFAULT_LLM_MODEL
    from core.d2_live_provider import D2HttpProvider
    from core.d2_dialogue import run_d2_dialogue_turn
    from core.d2_dialogue_store import D2DialogueStore
    from contracts.response_plan import SessionKey
    from llm import chat_completions_create, chat_client
    assert chat_client.max_retries == 0
    rows, calls = [], 0

    def reserve():
        nonlocal calls
        if calls >= 2:
            raise RuntimeError("two-attempt budget exhausted")
        calls += 1
        rows[-1]["attempt"] = calls
        save(output, rows, calls)

    def transport(**kwargs):
        response = chat_completions_create(**kwargs)
        rows[-1].update(raw=response.choices[0].message.content or "", observed_model=response.model,
                        usage=response.usage.model_dump() if response.usage else None,
                        finish_reason=response.choices[0].finish_reason)
        return response

    class ProbeProvider(D2HttpProvider):
        def generate(self, request):
            assert not request.context.ordinary.dialogue_pairs and request.context.source_revision == 0
            rows[-1]["context"] = request.context.model_dump(mode="json")
            return super().generate(request)

    provider = ProbeProvider(model=DEFAULT_LLM_MODEL, transport=transport, admission=reserve)
    print(f"OUTPUT {output}; model={DEFAULT_LLM_MODEL}", flush=True)
    with D2DialogueStore(output / "isolated.sqlite") as store:
        for sid, question in CASES:
            rows.append({"question": question, "sid": sid})
            try:
                turn = run_d2_dialogue_turn(session_key=SessionKey(client_id="demo", sid="fresh-" + sid),
                    user_message=question, provider=provider, clients_root=ROOT / "clients", store=store,
                    now=datetime.now(timezone.utc), request_id=sid, lead_bridge=False)
                rows[-1]["answer"] = turn.response.rendered_text
                rows[-1]["ui"] = turn.response.ui_projection.model_dump(mode="json")
            except Exception as exc:
                rows[-1]["error"] = type(exc).__name__
            save(output, rows, calls)
            print(f"{calls}/2 {sid}: {rows[-1].get('error', 'published')}", flush=True)
    print(f"REPORT {output / 'answers.md'}", flush=True)


if __name__ == "__main__":
    main()
