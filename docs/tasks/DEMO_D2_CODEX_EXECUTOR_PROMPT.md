# D2 — процесс исполнителя Codex

Назначение: постоянные правила процесса для Codex Terra/Sol.
В каждый новый этап владелец вставляет только короткий
[мини-промпт](DEMO_D2_STAGE_TASK_MINI_PROMPT.md) и карточку этапа с целью,
baseline, allowlist, приёмкой и тестами. Этот документ не может ослабить
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

До независимого review:
1. Выполни только согласованный checkpoint и assigned offline tests.
2. Используй временные DB, BOT_LOG_DIR и temporary tenant pack.
3. Добавь в тот же незакоммиченный diff строку Ledger только с доказанными
   фактами checkpoint. Укажи устойчивое имя, но не hash будущего commit.
4. Не делай staging, commit или push.
5. Передай точный diff и доказательства независимому Checker; на рубежах
   0, 3 и 5 отдельно передай их мощной модели в Cursor.

После требуемых PASS:
1. Сделай exact staging, staged diff/stat/diff --check, commit и push.
2. Не меняй Ledger после PASS.
3. В финальном отчёте укажи фактический hash commit.
4. Кратко объясни владельцу по-человечески, что изменилось, что проверено,
   что осталось открытым и какой следующий этап по roadmap. Не выдавай
   огромный автоматический prompt для нового чата.

Следующий checkpoint определяй только по Delivery Roadmap и Ledger.
Не меняй порядок roadmap и не расширяй scope.
```

Если checkpoint card конфликтует с этим prompt, действуют документы в порядке
приоритета из Execution Lock. Технический выбор, уже заданный contract,
acceptance или decision log, исполнитель делает сам и фиксирует ссылку. Он
останавливается только при конфликте требований, новом видимом правиле либо
двух допустимых реализациях с заметно разным пользовательским поведением.
