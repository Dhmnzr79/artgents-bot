# D2 Checkpoint Ledger — таблица подтверждённых фактов

Обновлено: 2026-09-20 после CP1 `7a0fa7c`. Это не roadmap и не план: только
факты с доказательствами. Правила ведения — в
[DEMO_D2_EXECUTION_LOCK.md](DEMO_D2_EXECUTION_LOCK.md). В будущем новая строка
добавляется в незакоммиченный diff **до** Cursor review вместе с кодом и
тестами. Она называет checkpoint; фактический hash сообщается в финальном
closeout, потому что commit не может содержать свой собственный hash.

Исключение ниже отмечено явно: CP1 был уже закоммичен без строки Ledger. Его
факт добавлен отдельным документным correction checkpoint и не выдаётся за
часть исходного проверенного diff.

| Checkpoint | Что реально работает | Где вызывается | Статус legacy runtime | Что не доказано | Cursor verdict | Evidence commit / closeout |
|---|---|---|---|---|---|---|
| D2 component series C2–C15 | Отдельные D2 seams/детали: расширенный D1R envelope (части, typed situation), price modes, deferral, part failure, prose realization, tenant snapshot/sources, TTL-проекция, continuation binding, plan focus, cross-topic carry | Только изолированные unit/seam-тесты (`tests/test_d2_*`); из общего маршрута и HTTP не вызываются | Не затронут: `/ask` и виджет продолжают работать через legacy path | Полный пользовательский сценарий, сборка компонентов вместе, HTTP integration, реальная модель | PASS отдельных изолированных checkpoint (по журналу задач S2); сборку и сценарии не подтверждают | `b9e0de6`–`0f8e405` |
| S2-V0 A08 | Внутренний D2 route проходит **два хода A08** целиком: raw fake provider → production D1R parser → production tenant loader → resolver/materializer → text/UI → persistent typed SQLite state, включая close/reopen store; legacy Composer/sales_fast/вторая ordinary memory не вызываются (runtime observer); сеть запрещена; tenant isolation, TTL, invalid provider output и атомарность записи проверены | `core/d2_dialogue.py::run_d2_dialogue_turn`; вызывается только из `tests/test_d2_dialogue_a08.py` | Не затронут: legacy path остаётся единственным обслуживающим `/ask`/`/ask/stream`/widget | Подключение к `/ask`, `/ask/stream`, widget; реальная модель; replay результата по request_id; lead/privacy мост; все сценарии кроме A08 | **PASS** (независимый Checker этого checkpoint) | `8e7a3b6` |
| CP1 — D1R prompt-contract (late Ledger correction) | Единственный production prompt v17 явно требует для каждого request typed `service_id`, `topic_id`, `statement_mode` и `situation`; production parser принимает корректный raw A08 envelope и отвергает неверный enum `continuity` | `core/one_call_prompt_contract.py`; production parser проверен в `tests/test_request_understanding_schema_offline.py`; внутренний A08 test использует isolated tenant copy | Не затронут: legacy path остаётся единственным обслуживающим `/ask`/`/ask/stream`/widget | Approved demo tenant data, настоящая модель, HTTP/widget, replay/lead bridge и все сценарии кроме внутреннего A08 | **PASS** для исходного CP1 по отчёту независимого Cursor; данная строка требует отдельной проверки только как поздняя документационная коррекция | Original CP1 `7a0fa7c`; 20 targeted offline tests, provider calls 0 |
| Current local runtime | `/ask` и `/ask/stream` отвечают через legacy one-call/sales_fast path (`orchestrate_sales_one_plus_ask_turn` → `run_sales_fast_widget_turn`), включая legacy semantic selectors до и после модели | `app.py` → `orchestration/sales_one_plus_ask_turn.py` | **Активен**; это не D2 route | Ничего из D2 в этом пути не участвует | — (не D2 checkpoint) | Observed at `7a0fa7c` |

## Явная фиксация

- **Никакие другие сценарии A01–A12 не считаются собранными D2
  пользовательскими сценариями.** Существующие зелёные unit/seam-тесты
  деталей (A01–A07, A09, A10, B06, B13–B17 и срезы C) — это доказательства
  компонентов, не сценариев.
- Собранным через D2 доказан ровно один сценарий: **A08**, и только через
  внутренний entry с fake provider — не через HTTP, не в виджете и не
  реальной моделью.
- CP1 доказал только prompt/parser contract для этого внутреннего A08; он не
  является live-проверкой модели и не подключил D2 к пользователю.
- HTTP integration, lead/privacy мост, replay результата, live-проверка
  модели — **не начаты** на HEAD `7a0fa7c`.
