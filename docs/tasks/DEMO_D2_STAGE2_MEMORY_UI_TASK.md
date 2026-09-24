# D2 — этап 2: память и typed UI

Статус: в работе. База: `21051f7` (`fix(d2): align stage1 semantic contract`).
Реализация ведётся в текущей папке и ветке только по этой карточке и
`DEMO_D2_DELIVERY_ROADMAP.md`, этап 2.

## Цель

Общий D2 turn сохраняет и использует только typed ordinary state: обсуждаемую
услугу, явно названный объём, незавершённое уточнение с исходной задачей,
достаточную очищенную историю в пределах TTL и показанный typed UI ref с
revision. Follow-up передаёт модели проверенный ref, а не подпись кнопки;
ценовой клик сохраняет исходное ценовое намерение. Явная смена услуги заменяет
focus, не перенося прежние факты автоматически. После TTL короткое
неоднозначное продолжение уточняется; новая сессия не наследует ordinary state.

Lead/privacy остаются у существующего owner. Чужой, непоказанный или устаревший
UI ref отклоняется до provider/effect. Replay того же `request_id` возвращает
сохранённый результат и delta без второго provider-вызова.

## Точный write allowlist

```text
contracts/d2_session_context.py
contracts/response_plan_session.py
contracts/d2_dialogue.py
core/d2_session_context.py
core/d2_dialogue_store.py
core/d2_dialogue.py
core/d2_live_provider.py
core/one_call_prompt_contract.py
tests/test_d2_session_context.py
tests/test_d2_r1_contract.py
tests/test_d2_continuation_scenarios.py
tests/test_d2_widget_replay.py
docs/tasks/DEMO_D2_STAGE2_MEMORY_UI_TASK.md
docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md
```

Все остальные пути read-only: в частности HTTP/SSE, browser widget, tenant
snapshot/catalog, parser/envelope schema, данные клиники и lead/privacy owner.

## Неподвижные границы

Не добавлять semantic regex, ветки под фразы или услуги, fallback к старому
runtime, второй prompt/parser/state, эвристику по подписи кнопки, новые видимые
правила или нового owner ordinary state. Не менять цену, объёмные расчёты,
HTTP/SSE, widget, tenant boundary, lead/privacy или данные клиники.

При потребности в файле вне allowlist, изменении архитектурной границы или
видимого поведения остановиться. Архитектурный разбор с Astra не заменяет
решение владельца.

## Обязательная форма checkpoint

- **ACCEPTANCE:** этап 2 из roadmap: общий D2 turn сохраняет typed service,
  extent, исходную задачу CLARIFY, очищенную историю и verified UI ref;
  проверяются follow-up, короткое продолжение, смена услуги, CLARIFY,
  «Не знаю», новая сессия, stale/foreign UI и replay.
- **D2 ROUTE:** `run_d2_dialogue_turn` → один D1R prompt/parser → tenant
  snapshot/materializer → один `D2DialogueStore`; offline tests используют
  fake provider и temporary DB.
- **LEGACY IMPACT:** Composer/sales_fast, legacy ordinary memory, второй
  prompt/parser/state и fallback не подключаются и не становятся owner.
- **OWNER DECISION:** не требуется для технической реализации roadmap;
  владелец отдельно утвердил 3 пары, 1000 символов на сторону, TTL 30 минут,
  отдельное typed сохранение service/extent/source task и ordered offer IDs
  без ценового free text, а также включение `core/d2_live_provider.py`.
- **FUTURE SCOPE:** сборка/переформулирование цен, HTTP/SSE/widget wire,
  live-provider и deploy не входят в этап.
- **Test isolation:** только temporary DB/log/копия tenant pack, blocked
  network и fake provider; `data/` и её SQLite не трогаются и не добавляются.
- **Ledger draft:** строка `D2-S2` в
  `DEMO_D2_CHECKPOINT_LEDGER.md` обновляется до review вместе с этим diff.

## Offline evidence и закрытие

Через общий `run_d2_dialogue_turn` с fake provider и temporary DB доказать:
follow-up по показанному ref, короткое продолжение, ценовой typed click, смену
услуги, CLARIFY, «Не знаю», fresh/expired TTL, новую сессию, stale/foreign/
unshown UI, replay того же request ID и tenant/lead/privacy sentinels. Сеть,
provider и live-вызовы запрещены.

Перед закрытием: targeted offline tests, `git diff --check`, независимый Checker
PASS и отдельный Cursor review. Commit/push, merge, deploy и cleanup — только
по отдельному разрешению владельца.
