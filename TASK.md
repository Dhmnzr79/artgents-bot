# TASK — A2: подключить TurnFrame только в shadow-observability

Один активный `TASK.md` на одну маленькую задачу. Файл подготовлен **Архитектором** до реализации.
Общий закон — `.cursor/rules/00-guardrails.mdc`. Инварианты ревью — `REVIEW_CHECKLIST.md`.
Проектная опора — `docs/ARCH_TARGET_DESIGN.md` v4.

---

## Зафиксированная точка старта

- A0 frozen spec: commit `e852f4b`, hash `c2072ca74c2da73bf657d793195d2eb6c8ba7bd5`.
- A0 harness: commit `a0e6926`.
- A0 live baseline: `preservation = 3/6`, `smoke = 24/24`.
- A1 governance: commit `631abc1`.
- A1 contract + pure adapter: commit `0761213`.
- Рабочее дерево перед A2 должно быть чистым.

## Задача

**Название:** A2 — построение `TurnFrame` на реальном planner-turn только для наблюдаемости.

**Размер:** МАЛЕНЬКАЯ. Одно shadow-подключение, telemetry slice и unit/integration-тесты.

**Цель:** на успешном пути текущего `TurnPlan` построить канонический `TurnFrame`, положить его снимок в `request.ctx` и включить в технический `turn_complete`/E2E telemetry. В A2 ни одно поле `TurnFrame` не используется для выбора ответа, источника, route, UI или policy.

Целевая форма A2:

```text
legacy TurnPlan + итоговый DecisionFrame
                │
                ├── прежний runtime без изменений
                │
                └── TurnFrame shadow snapshot → ctx/logs only
```

## Где подключать

Подключение разрешено только в planner-success ветке `run_resolver_turn()`:

1. `TurnPlan` уже получен.
2. `DecisionFrame` уже получил существующие effective override (`content` для consultation/commercial и `comparison` для comparison query).
3. Существующий `record_decision_frame_ctx(decision)` уже выполнен.
4. После этого вызывается shadow-recorder с `plan` и итоговым `decision`.
5. Возвращаемый `TurnFrame` не присваивается `decision`, `intent`, `scope_topic_candidate` и не передаётся downstream.

Если planner не дал `TurnPlan` и ход ушёл в resolver/legacy fallback, telemetry должна честно получить:

- `turn_frame_shadow_status = "not_available"`;
- `turn_frame_shadow_reason = "turn_plan_missing"`.

Не строить искусственный `TurnPlan` из resolver-результата в A2.

## Shadow-recorder

Новый маленький модуль должен:

- вызывать существующий `build_turn_frame_from_legacy()`;
- при успехе записывать в `request.ctx`:
  - `turn_frame_shadow` — полный `model_dump()`;
  - `turn_frame_shadow_status = "ok"`;
  - удалять/не оставлять старый `turn_frame_shadow_reason`;
- при отсутствии `TurnPlan` уметь явно отметить `not_available`;
- при внутренней ошибке **не менять продуктовый ход и не бросать исключение наружу**, но записывать:
  - `turn_frame_shadow_status = "degraded"`;
  - `turn_frame_shadow_reason` — стабильный машинный код без текста вопроса и без exception message;
  - отдельный структурированный log/event со status `degraded`;
- возвращать `TurnFrame | None` только для unit-тестируемости; runtime не использует return value;
- не принимать текст вопроса, answer, историю диалога или payload виджета;
- не читать базу знаний, PriceBook, session state или network;
- не вызывать LLM/resolver/classifier;
- не содержать тематических веток.

Полный `TurnFrame` не должен появляться в обычном widget payload. Он может попадать в ответ только через уже существующий E2E test-hook `E2E_USE_TEST_CLIENT=1` внутри `meta.metadata_first`.

## Telemetry contract

В `metadata_first_turn_details()` и E2E metadata slice должны быть доступны только три новых ключа:

- `turn_frame_shadow`;
- `turn_frame_shadow_status`;
- `turn_frame_shadow_reason` — только когда есть причина.

Не раскладывать оси `TurnFrame` ещё раз в десятки плоских ctx-полей. Не менять существующие telemetry keys.

## Затрагиваемые файлы (allowlist)

Исполнитель может менять **только**:

- `core/turn_frame_shadow.py` — новый recorder/marker;
- `orchestration/resolver_turn.py` — одна точка shadow wiring и unavailable marker;
- `core/metadata_first_observability.py` — только три telemetry keys;
- `tests/test_turn_frame_shadow.py` — recorder + реальное wiring через `run_resolver_turn`;
- `tests/test_metadata_first_observability.py` — только проверка нового telemetry slice.

`TASK.md`, архитектурные документы, contracts, adapter A1, eval-spec, harness, runtime policies и существующие продуктовые тесты Исполнитель не меняет.

## Явно НЕ делать

- Не использовать `TurnFrame` для изменения `intent`, `decision`, `scope_topic_candidate`, source selection или answer plan.
- Не подключать `TurnFrame` к composer, evidence, verifier, UI, price или marketing.
- Не менять `TurnPlan`, `DecisionFrame`, `TurnFrame` и A1 adapter.
- Не чинить preservation cases `02`, `03`, `05`.
- Не добавлять feature flag: A2 дешёвый и behavior-neutral; ошибки recorder уже изолированы.
- Не добавлять новый LLM prompt/call, resolver, classifier, router или handler.
- Не передавать в recorder вопрос пользователя ради inference.
- Не логировать exception message, вопрос, ответ или историю.
- Не добавлять silent `except: pass`: degraded должен быть виден.
- Не менять существующие `smoke/risk/golden/emotion/preservation` ожидания.
- Не добавлять skip/xfail/условный PASS.
- Не создавать commit/ветку/stash без явной команды владельца.

## Обязательные тесты

1. Успешный recorder сохраняет `TurnFrame.model_dump()` и status `ok` в request ctx.
2. Snapshot содержит field metadata из A1 adapter без повторного inference.
3. `not_available` явно записывает reason `turn_plan_missing` и не создаёт frame.
4. Ошибка builder изолирована: recorder возвращает `None`, status становится `degraded`, стабильный reason записан, исключение не выходит наружу.
5. При degraded записывается структурированный event/log без вопроса и exception message.
6. Recorder не принимает question/answer/history/payload параметры.
7. Интеграционный тест `run_resolver_turn` с успешным `TurnPlan` доказывает наличие shadow snapshot в ctx.
8. Интеграционный тест доказывает, что `ResolverTurnOutcome.intent` и `decision` остаются прежними и не заменяются `TurnFrame`.
9. Planner-missing путь помечает shadow как `not_available` перед resolver/legacy continuation.
10. `metadata_first_turn_details()` включает frame/status/reason.
11. E2E metadata slice включает новые ключи через существующий test-hook; обычный `finalize_ask` без env не добавляет `meta.metadata_first` в widget payload.
12. Frozen A0 hash не изменён.

Узкие monkeypatch допустимы только для изоляции builder failure и внешнего planner/resolver в integration unit-тесте. Нельзя мокать утверждаемое ctx/telemetry поведение.

## Стоп-условия

Исполнитель обязан остановиться и выдать `СТОП: требуется решение владельца/Архитектора`, если:

- требуется файл вне allowlist;
- для wiring нужно изменить сигнатуру или поведение `run_resolver_turn`;
- downstream-код должен начать читать `turn_frame_shadow`;
- существующий ответ/payload меняется без `E2E_USE_TEST_CLIENT=1`;
- невозможно изолировать ошибку shadow-recorder без silent failure;
- нужен вопрос пользователя или новый inference для заполнения frame;
- существующие тесты требуют изменения;
- frozen A0 spec/hash изменился;
- есть незакоммиченный diff, не относящийся к A2.

Формат остановки:

```text
СТОП: требуется решение владельца/Архитектора
Что обнаружено:
Какие есть варианты:
Риск каждого варианта:
Какие файлы потребуются:
```

## Контрольная точка

1. Реализовать только allowlist.
2. Показать diff тестов первым.
3. Запустить все команды проверки.
4. СТОП → checker → Архитектор.

Не использовать shadow-frame downstream после зелёных тестов. Это будет отдельная задача после анализа telemetry.

## Команды проверки

```powershell
python -m pytest -q tests/test_turn_frame_shadow.py tests/test_metadata_first_observability.py
python -m pytest -q tests/test_turn_frame_contract.py tests/test_turn_planner_llm.py tests/test_turn_planner_wiring.py tests/test_turn_plan_protocol_guard.py
python -m pytest -q tests/test_contacts_routing.py tests/test_pricebook_golden.py tests/test_price_layer_parity.py
git diff --check
git status --short
git hash-object evals/v5/demo/preservation.json
```

Live eval не требуется на A2: продуктовый output не меняется, а реальное wiring проверяется integration unit-тестом. Если обычный widget payload изменился, это нарушение задачи, а не повод resnapshot eval.

## Критерии приёмки

- [ ] Изменены только allowlist-файлы.
- [ ] Shadow строится только после итоговых existing decision overrides.
- [ ] Runtime не читает результат `TurnFrame` для решений.
- [ ] Успех, отсутствие и ошибка различимы как `ok/not_available/degraded`.
- [ ] Ошибка shadow не ломает продуктовый ход и не скрыта.
- [ ] В telemetry нет вопроса, ответа, истории или exception message.
- [ ] Обычный widget payload не получил новых полей.
- [ ] Нет новых LLM-вызовов, маршрутов, тематических веток и feature flags.
- [ ] Existing tests не изменены и остаются зелёными.
- [ ] Frozen A0 spec/hash не изменены.
- [ ] Checker подтвердил границы, честность тестов и behavior-neutral wiring.

## Готово, когда

A2 готова после принятого checker-review и отдельного коммита allowlist. Следующий TASK определяется только после просмотра shadow telemetry; автоматически downstream на `TurnFrame` не переключать.
