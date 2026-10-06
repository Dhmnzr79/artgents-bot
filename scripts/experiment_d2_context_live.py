"""Twenty authorized live attempts through ordinary D2, isolated state, no retries.

Default prints cases and initializes an output folder without provider calls.
--live --output <that folder> runs once. No scripted interpretation or rewriting.
"""
import argparse
from datetime import datetime, timezone
import html
import json
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CASES = [
    ("classic", "Хочу узнать о классической имплантации: как проходит установка и больно ли это?"),
    ("classic", "А от первого приёма до постоянной коронки сколько времени проходит?"),
    ("classic", "А гарантия на неё какая?"),
    ("classic", "Кто из ваших врачей этим занимается?"),
    ("classic", "А если выбрать систему Impro, какой ценовой ориентир?"),
    ("all6", "Чем All-on-6 отличается от All-on-4 и в каких случаях их обсуждают?"),
    ("all6", "А если такой имплант не приживётся, что тогда?"),
    ("all6", "Я спрашиваю именно про All-on-6 на верхней челюсти: когда будет постоянный протез и что до этого?"),
    ("all6", "А кто из врачей проводит такую операцию?"),
    ("whitening", "Расскажите про профессиональное отбеливание: как оно проходит и сколько стоит?"),
    ("whitening", "А результат надолго сохраняется?"),
    ("whitening", "А во время процедуры может быть больно или повышаться чувствительность?"),
    ("whitening", "И кто это делает у вас, как выбрать врача?"),
    ("policy", "Сыну 12 лет, нужна профессиональная чистка. Вы принимаете детей и можно ли по ОМС?"),
    ("policy", "Тогда вопрос уже обо мне: мне 38 лет, хочу профессиональную чистку. Вы делаете её взрослым и сколько стоит?"),
    ("policy", "А взрослому по ОМС можно у вас лечить зубы?"),
    ("policy", "Хорошо, платно. Где вы находитесь и работаете ли в субботу?"),
    ("medical", "Боюсь лечения кариеса: как обезболивают и что делать, если страшно?"),
    ("medical", "Но сейчас другая проблема: вчера удалили зуб, сегодня сильно болит, щека опухла и идёт кровь. Что мне делать?"),
    ("medical", "Понял. А про будущее лечение кариеса: можно заранее обсудить обезболивание с врачом?"),
]


def save(output, rows, state):
    (output / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "records.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    md = ["# Живой тест контекста, составных вопросов и политик", "",
        f"Модель: {state.get('model', 'по конфигурации бота')}. Попыток: {state['calls']}/20.", "",
        "Обычный prompt и strict parser D2. Смысл вопросов определяет модель. "
        "Память существующая, SQLite отдельный. Итоговые цены/политики/врачи могут собираться кодом; "
        "это не эксперимент prose-only. Предыдущие ответы в контексте — окончательные ответы D2.", ""]
    cards = []
    for row in rows:
        answer = row.get("answer", "Ответ не опубликован: " + row.get("error", "не запускался"))
        md += [f"## {row['index']}. Диалог {row['dialogue']}", "", "**Вопрос:** " + row['question'], "",
               "**Окончательный ответ бота:**", "", answer, "",
               "**Сырой ответ модели:**", "", "```json", row.get("raw", "Нет ответа модели"), "```", "",
               "**UI:**", "", "```json", json.dumps(row.get("ui", {}), ensure_ascii=False, indent=2), "```", ""]
        if row.get("error"):
            md += ["**Ошибка:** " + row["error"], ""]
        cards.append(f"<section><h2>{row['index']}. {html.escape(row['dialogue'])}</h2><p><b>Вопрос:</b> {html.escape(row['question'])}</p>"
            f"<h3>Окончательный ответ бота</h3><pre>{html.escape(answer)}</pre>"
            f"<details><summary>Сырой ответ модели и UI</summary><pre>{html.escape(row.get('raw', 'Нет'))}</pre>"
            f"<pre>{html.escape(json.dumps(row.get('ui', {}), ensure_ascii=False, indent=2))}</pre></details></section>")
    (output / "dialogues.md").write_text("\n".join(md), encoding="utf-8")
    (output / "dialogues.html").write_text("<!doctype html><meta charset='utf-8'><title>Живые диалоги D2</title>"
        "<style>body{font:17px/1.6 system-ui;max-width:850px;margin:40px auto;padding:20px;color:#29243b}"
        "section{padding:24px;background:#f4f1fa;border-radius:16px;margin:24px 0}pre{white-space:pre-wrap;font:inherit}</style>"
        f"<h1>Живые диалоги D2</h1><p>Попыток {state['calls']}/20. Смысл вопросов определяет модель. "
        "Финальный ответ — обычный D2; финансовые и точные блоки могут быть кодовыми. Тексты без редакции.</p>"
        + "".join(cards), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or Path(tempfile.mkdtemp(prefix="d2-context-live-"))
    output.mkdir(parents=True, exist_ok=True)
    if (output / "state.json").exists():
        old = json.loads((output / "state.json").read_text(encoding="utf-8"))
        if old["calls"] or old.get("started"):
            raise RuntimeError("This experiment already started; no rerun or recovery allowed")
    os.environ["BOT_LOG_DIR"] = str(output.resolve())
    os.environ["BOT_LOG_FILE"] = "app.jsonl"
    os.environ["D2_FULL_AUDIT_LOG"] = "0"
    state = {"calls": 0, "started": bool(args.live)}
    rows = []
    save(output, rows, state)
    print(f"OUTPUT {output}", flush=True)
    if not args.live:
        for index, (dialogue, question) in enumerate(CASES, 1):
            print(index, dialogue, question)
        return
    from config import DEFAULT_LLM_MODEL
    from core.d2_live_provider import D2HttpProvider
    from core.d2_dialogue import run_d2_dialogue_turn
    from core.d2_dialogue_store import D2DialogueStore
    from contracts.response_plan import SessionKey
    from llm import chat_completions_create, chat_client
    assert chat_client.max_retries == 0
    state["model"] = DEFAULT_LLM_MODEL

    def reserve():
        if state["calls"] >= 20:
            raise RuntimeError("hard 20-attempt budget exhausted")
        state["calls"] += 1
        rows[-1]["attempt"] = state["calls"]
        save(output, rows, state)  # Persistent reservation before the network.

    def transport(**kwargs):
        result = chat_completions_create(**kwargs)
        row = rows[-1]
        row["raw"] = result.choices[0].message.content or ""
        row["observed_model"] = result.model
        row["usage"] = result.usage.model_dump() if result.usage else None
        row["finish_reason"] = result.choices[0].finish_reason
        return result

    class CapturedProvider(D2HttpProvider):
        def generate(self, request):
            rows[-1]["context_received"] = request.context.model_dump(mode="json")
            return super().generate(request)

    provider = CapturedProvider(model=DEFAULT_LLM_MODEL, transport=transport, admission=reserve)
    with D2DialogueStore(output / "dialogue.sqlite") as store:
        for index, (dialogue, question) in enumerate(CASES, 1):
            rows.append({"index": index, "dialogue": dialogue, "question": question})
            row = rows[-1]
            started = time.monotonic()
            try:
                turn = run_d2_dialogue_turn(session_key=SessionKey(client_id="demo", sid="ctx-" + dialogue),
                    user_message=question, provider=provider, clients_root=ROOT / "clients", store=store,
                    now=datetime.now(timezone.utc), request_id=f"context-{index}", lead_bridge=False)
                row["answer"] = turn.response.rendered_text
                row["ui"] = turn.response.ui_projection.model_dump(mode="json")
                row["resolved"] = turn.response.resolved.model_dump(mode="json")
                row["revision"] = turn.committed_revision
            except Exception as exc:
                # Only short typed contract codes; no exception bodies/transport secrets.
                row["error"] = type(exc).__name__
                if isinstance(exc, ValueError) and str(exc).startswith("d2_"):
                    row["error"] += ": " + str(exc)[:160]
            row["duration_ms"] = round((time.monotonic() - started) * 1000)
            save(output, rows, state)
            print(f"{index}/20 calls={state['calls']} {dialogue}: {row.get('error', 'published')}", flush=True)
    print(f"REPORT {output / 'dialogues.md'}", flush=True)


if __name__ == "__main__":
    main()
