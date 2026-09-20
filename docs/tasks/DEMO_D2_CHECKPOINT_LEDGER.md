# D2 Checkpoint Ledger — таблица подтверждённых фактов

Обновлено: 2026-09-20 на HEAD `8e7a3b6`. Это не roadmap и не план: только
факты с доказательствами. Правила ведения — в
[DEMO_D2_EXECUTION_LOCK.md](DEMO_D2_EXECUTION_LOCK.md). Новая строка
добавляется только вместе с checkpoint, который её доказывает.

| Checkpoint | Что реально работает | Где вызывается | Статус legacy runtime | Что не доказано | Cursor verdict | Commit |
|---|---|---|---|---|---|---|
| D2 component series C2–C15 | Отдельные D2 seams/детали: расширенный D1R envelope (части, typed situation), price modes, deferral, part failure, prose realization, tenant snapshot/sources, TTL-проекция, continuation binding, plan focus, cross-topic carry | Только изолированные unit/seam-тесты (`tests/test_d2_*`); из общего маршрута и HTTP не вызываются | Не затронут: `/ask` и виджет продолжают работать через legacy path | Полный пользовательский сценарий, сборка компонентов вместе, HTTP integration, реальная модель | PASS отдельных изолированных checkpoint (по журналу задач S2); сборку и сценарии не подтверждают | `b9e0de6`–`0f8e405` |
| S2-V0 A08 | Внутренний D2 route проходит **два хода A08** целиком: raw fake provider → production D1R parser → production tenant loader → resolver/materializer → text/UI → persistent typed SQLite state, включая close/reopen store; legacy Composer/sales_fast/вторая ordinary memory не вызываются (runtime observer); сеть запрещена; tenant isolation, TTL, invalid provider output и атомарность записи проверены | `core/d2_dialogue.py::run_d2_dialogue_turn`; вызывается только из `tests/test_d2_dialogue_a08.py` | Не затронут: legacy path остаётся единственным обслуживающим `/ask`/`/ask/stream`/widget | Подключение к `/ask`, `/ask/stream`, widget; реальная модель (prompt для расширенного envelope отсутствует); replay результата по request_id; lead/privacy мост; все сценарии кроме A08 | **PASS** (независимый Checker этого checkpoint) | `8e7a3b6` |
| Current local runtime | `/ask` и `/ask/stream` отвечают через legacy one-call/sales_fast path (`orchestrate_sales_one_plus_ask_turn` → `run_sales_fast_widget_turn`), включая legacy semantic selectors до и после модели | `app.py` → `orchestration/sales_one_plus_ask_turn.py` | **Активен**; это не D2 route | Ничего из D2 в этом пути не участвует | — (не D2 checkpoint) | `8e7a3b6` (HEAD) |

## Явная фиксация

- **Никакие другие сценарии A01–A12 не считаются собранными D2
  пользовательскими сценариями.** Существующие зелёные unit/seam-тесты
  деталей (A01–A07, A09, A10, B06, B13–B17 и срезы C) — это доказательства
  компонентов, не сценариев.
- Собранным через D2 доказан ровно один сценарий: **A08**, и только через
  внутренний entry с fake provider — не через HTTP, не в виджете и не
  реальной моделью.
- HTTP integration, lead/privacy мост, replay результата, live-проверка
  модели — **не начаты** на HEAD `8e7a3b6`.
