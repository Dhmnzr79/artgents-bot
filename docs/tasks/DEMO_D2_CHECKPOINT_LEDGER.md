# D2 Checkpoint Ledger — таблица подтверждённых фактов

Обновлено: 2026-09-20, CP4 находится в незакоммиченном diff после focused recheck. Это не roadmap и не план: только
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
| CP2 — demo tenant data для A08 | Штатный `clients/demo` tenant pack содержит direction-level данные для `implantation` и `prosthetics`: порядок существующих прайс-карточек, цена/единица/обязательные условия и authored пояснения. Внутренний двухходовый A08 читает только temporary copy этого production pack через tenant snapshot, сохраняет один зуб при переходе темы и не берёт данные из test-only fixture | `core/d2_dialogue.py::run_d2_dialogue_turn` → `load_d2_tenant_snapshot` → `build_d2_snapshot_sources`; проверка в `tests/test_d2_dialogue_a08.py` | Не затронут: legacy path остаётся единственным обслуживающим `/ask`/`/ask/stream`/widget | Настоящая модель, HTTP/widget, replay/lead bridge и все сценарии кроме внутреннего A08 | **PASS** | `c195051`; 21 targeted offline tests, provider calls 0 |
| CP3 — ограниченная live-проверка A08 | Два точных последовательных хода A08 прошли через один production D1R parser и штатный demo tenant snapshot: `implantation` показала утверждённые три offer, затем `prosthetics` показало только `implant_supported_prosthetics.default` с перенесённым extent `one_tooth`. Совпадающий legacy duplicate канонизируется внутри единственной модели `RequestUnderstanding`; отличающийся по-прежнему отвергается. D2 follow-up instruction использует только typed `D2_SESSION_CONTEXT`, не создаёт новый tenant-data/wire/parser contract. | Только явно авторизованный internal runner `scripts/run_d2_a08_live.py` → `D2Cp3LiveProvider` → `run_d2_dialogue_turn`; данные — `clients/demo` через production loader/snapshot | Не затронут: `/ask`, `/ask/stream`, widget и legacy path не вызывались | HTTP/SSE/widget, другие A01–A12, replay/lead/privacy, deployment; результат не доказывает общий live runtime. Raw provider payload и текст не сохранены. | **PASS** | `8bfaf38`; 100 targeted offline tests; qwen3.8-flash, 2 explicitly authorized calls, no automatic retries; demo data baseline `c195051` |
| CP4 — common turn completion | Внутренний D2 route резервирует один `(tenant, sid, request_id)` до model call, атомарно фиксирует typed ordinary state и точный final result в одном `D2DialogueStore`, а повтор того же payload возвращает сохранённый result без model call. Иной payload с тем же request ID отклоняется; второй параллельный request того же session не становится final. PII-safe provider input использует существующий privacy boundary без обращения к legacy `session`. Явно переданный existing lead-effect сохраняется только как effect ID/status без контактов; после commit допускается ровно одна попытка dispatcher, ambiguous outcome остаётся `unknown` без automatic retry. | Только `core/d2_dialogue.py::run_d2_dialogue_turn` и `D2DialogueStore`; тестовый dispatcher не является HTTP/widget/lead UI entry | Не затронут: `/ask`, `/ask/stream`, widget, Composer, sales_fast и legacy runtime/selectors не вызываются | HTTP/SSE delivery/replay, реальный lead UI/transport, другие A01–A12, общий runtime, deployment; CP4 не меняет правила паузы/выхода/возврата lead flow и не создаёт пользовательский сценарий | Pending independent Cursor review | Uncommitted CP4 diff; 44 targeted offline tests, provider/live calls 0 |
| Current local runtime | `/ask` и `/ask/stream` отвечают через legacy one-call/sales_fast path (`orchestrate_sales_one_plus_ask_turn` → `run_sales_fast_widget_turn`), включая legacy semantic selectors до и после модели | `app.py` → `orchestration/sales_one_plus_ask_turn.py` | **Активен**; это не D2 route | Ничего из D2 в этом пути не участвует | — (не D2 checkpoint) | Observed at `7a0fa7c` |

## Явная фиксация

- **Никакие другие сценарии A01–A12 не считаются собранными D2
  пользовательскими сценариями.** Существующие зелёные unit/seam-тесты
  деталей (A01–A07, A09, A10, B06, B13–B17 и срезы C) — это доказательства
  компонентов, не сценариев.
- Собранным через D2 доказан ровно один сценарий: **A08**. CP3 отдельно
  подтвердил его тем же внутренним entry с ограниченным live provider; это
  не HTTP и не виджет.
- CP1 доказал только prompt/parser contract для этого внутреннего A08; он не
  является live-проверкой модели и не подключил D2 к пользователю.
- Внутренние result replay и PII-free lead-effect receipt доказаны только CP4
  internal route. HTTP/SSE integration, реальный lead UI/transport и общий runtime
  **не начаты**. Live-проверка ограниченно доказана только для CP3 A08, не для
  общего runtime.
