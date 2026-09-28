# D2 — указатель текущего состояния

Дата: 2026-09-28. Владелец согласовал небольшой отдельный документальный
checkpoint для навигации по D2 перед разбором прерывания записи и возвратом к
REC-4-P2. Этот checkpoint не утверждает новое поведение бота.

## Preflight и границы

- Git root: `C:\Cursor Projects\artgents-bot-active`; ветка
  `codex/d2-stage1-contract`.
- HEAD и локальный `origin/codex/d2-stage1-contract`:
  `e246f1e7132596e20b8f81db7bc911855678ad8e`.
- `origin/main` и merge-base:
  `141ce91fb1731cd990fcf8391550150016c73e7f`.
- До правок tracked diff и staging пусты. Чужие untracked `data/` и
  `docs/MARKETING_ANSWER_SCENARIOS.md` сохраняются. Локальная БД обновлялась
  2026-09-28 21:13:41 UTC; её содержимое не входит в checkpoint.
- Нет запуска бота, live/provider/SMTP вызовов, merge/deploy, изменения
  архитектуры или ценовой логики.

## Точный write allowlist

```text
docs/tasks/DEMO_D2_CURRENT_STATUS_INDEX_TASK.md
docs/tasks/DEMO_D2_CURRENT_STATUS.md
docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md
docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md
```

## Результат и приёмка

- Один короткий указатель на текущую папку/ветку, последний принятый checkpoint,
  действующие правила, активную последовательность и открытые вопросы.
- Исторические `Draft`, «сейчас» и baseline объяснены через дату и SHA;
  старые карточки и Ledger не переписываются.
- Прямые ссылки на AGENTS.md, Execution Lock, Delivery Roadmap, Target Contract,
  Product Decisions, Acceptance, Ledger, D2-DOC-CLICK и карточку REC-4-P.
- Локальный widget дефект «Ответить» во время сбора имени фиксируется только как
  открытая находка. Read-only логи 2026-09-28: `40820dcb` показал выбор,
  `96b02f07` после `lead:pending:answer` снова запросил имя без provider call.
  Исходная реализация явно возвращает к слоту в `core/d2_lead_bridge.py`.
  Решение о поведении и код — отдельная карточка; этот checkpoint их не меняет.

**ACCEPTANCE:** корректная навигация и статус с подтверждённым SHA; не
функциональная приёмка A/B/C. **D2 ROUTE:** не изменяется. **LEGACY IMPACT:**
не изменяется. **OWNER DECISION:** согласован указатель; исправление lead
выносится отдельно. **FUTURE SCOPE:** read-only аудит и карточка lead-сценария,
REC-4-P2, REC-5 и live-качество по отдельному GO.

Проверка: ссылки/статусы и `git diff --check`, независимый Checker;
Cursor review до сохранения по привычному рубежу владельца. Тесты не требуются:
runtime и данные не меняются. Ledger Draft записать до review. После PASS
не дописывать Ledger; stage exact paths, commit/push — только с разрешения.
