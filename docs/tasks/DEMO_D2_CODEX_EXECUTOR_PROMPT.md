# Master prompt исполнителя Codex для D2 checkpoint

Назначение: постоянный шаблон для Codex/Terra на каждом D2 checkpoint.
Текущий checkpoint card задаёт только его цель, baseline, allowlist,
acceptance и tests; этот документ не может ослабить
[Execution Lock](DEMO_D2_EXECUTION_LOCK.md) или
[Delivery Roadmap](DEMO_D2_DELIVERY_ROADMAP.md).

```text
Ты выполняешь только checkpoint, названный в текущем задании.

Перед любыми действиями полностью прочитай:
- AGENTS.md
- docs/tasks/DEMO_D2_EXECUTION_LOCK.md
- docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md
- docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md

Затем сделай preflight: repo path, git top-level, branch, HEAD, origin/main,
merge-base, status/staging/untracked, baseline, foreign WIP и точный
allowlist. Остановись при несовпадении.

Соблюдай Lock и roadmap:
- bot не в production; legacy не является compatibility target;
- не возвращай Composer, sales_fast, legacy selectors или старую ordinary memory;
- не добавляй fallback, второй prompt/parser/state/wire contract;
- не придумывай новый сценарий, strict refusal/gate или другое заметное
  пользователю правило без OWNER DECISION;
- не трогай foreign WIP;
- не создавай worktree, ветку, PR, merge, deploy или live/provider calls,
  если это прямо не разрешено checkpoint.

До Cursor review:
1. Выполни только согласованный checkpoint и assigned offline tests.
2. Используй временные DB, BOT_LOG_DIR и temporary tenant pack.
3. Добавь в тот же незакоммиченный diff строку Ledger с доказанными фактами
   checkpoint. Укажи устойчивое имя checkpoint, но не hash будущего commit.
4. Не делай staging, commit или push.
5. Подготовь точный prompt для независимого Cursor review.

После Cursor PASS:
1. Сделай exact staging, staged diff/stat/diff --check, commit и push.
2. Не меняй Ledger после PASS.
3. В финальном отчёте укажи фактический hash commit.
4. Выдай блок:

NEXT CHECKPOINT:
BASELINE:
ЦЕЛЬ:
ПОЧЕМУ ЭТО СЛЕДУЮЩИЙ ШАГ:
ЧТО НЕ ТРОГАТЬ:
ЧТО НУЖНО ОТ ВЛАДЕЛЬЦА:
READY-TO-PASTE NEXT CHAT PROMPT:

Следующий checkpoint определяй только по Delivery Roadmap и Ledger.
Не меняй порядок roadmap и не расширяй scope.
```

Если checkpoint card конфликтует с этим prompt, действуют документы в порядке
приоритета из Execution Lock. Технический выбор, уже заданный contract,
acceptance или decision log, исполнитель делает сам и фиксирует ссылку. Он
останавливается только при конфликте требований, новом видимом правиле либо
двух допустимых реализациях с заметно разным пользовательским поведением.
