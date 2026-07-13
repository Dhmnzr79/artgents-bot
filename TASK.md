# TASK — A7 Shadow wiring: partial TurnFrame только в observability

Один активный `TASK.md` на один checkpoint. Файл подготовлен Архитектором после принятых A7 Contract и A7 Planner split.

Общий закон — `.cursor/rules/00-guardrails.mdc`. Инварианты review — `REVIEW_CHECKLIST.md`. Архитектурная опора — `docs/FIELD_LEVEL_PLANNER_OUTCOME_A7.md`.

---

## 1. Точка старта

- Ветка: `codex/stage-a`.
- A7 Contract: `077bb0a`.
- A7 Planner split: `a6318a8`.
- A6 raw SHA256: `2EF96AB8660657501137B0A6880E7EA54594E02417197F031BE1BCE2D9D5A40A`.
- Matrix hash: `dc356c9c738fb80a10cf0035508d7e8c8247979d`.
- Preservation hash: `c2072ca74c2da73bf657d793195d2eb6c8ba7bd5`.
- До реализации рабочее дерево должно быть чистым после отдельного governance-коммита этого `TASK.md`.

## 2. Цель

Подключить уже существующий single-call `PlannerAttempt` к runtime:

```text
plan_turn_attempt() — ровно один существующий planner LLM-call
        │
        ├─ legacy_plan ──► текущие decision/routing/evidence/composer/UI
        │
        └─ shadow_frame + shadow_status ──► request.ctx/logs/E2E telemetry only
```

Главный кейс:

```text
raw: topic="doctors", aspects=[]
legacy_plan = None
shadow_status = "partial"
shadow_frame.topic = "doctors"

product: прежний fail-open → resolve_with_fallback
telemetry: partial frame сохранён, topic не потерян
```

Этот checkpoint **не улучшает ответы** и **не передаёт authority** новому `TurnFrame`.

## 3. Неподвижные инварианты

1. На один ход выполняется ровно один `plan_turn_attempt()` и не более одного planner LLM-call.
2. Runtime больше не вызывает рядом `plan_turn()` и `plan_turn_attempt()`.
3. Product-ветка читает только `attempt.legacy_plan`.
4. `legacy_plan is not None` сохраняет текущий planner-owned путь без смысловых изменений.
5. `legacy_plan is None` сохраняет текущий `resolve_with_fallback` fail-open.
6. `partial`, `not_available` и `degraded` не считаются успешным product-планом.
7. `shadow_frame`, `shadow_status` и per-field metadata не участвуют в route, intent, decision, evidence, composer, policy, marketing, UI или answer.
8. `TurnPlan.aspects min_length=1`, prompt, strict validation и guards не меняются.
9. Нет второго LLM-call, retry, classifier, regex/if под семь A6 кейсов.
10. Raw LLM JSON, question, answer, history и exception text не попадают в ctx/logs.
11. Ошибка shadow serialization/telemetry не ломает product-ход.
12. Widget без `E2E_USE_TEST_CLIENT=1` не получает нового payload.

## 4. Строгий allowlist реализации

Исполнитель может менять только:

1. `orchestration/resolver_turn.py`
2. `core/turn_frame_shadow.py`
3. `tests/test_turn_frame_shadow.py`
4. `tests/test_metadata_first_observability.py` — только тесты публикации существующих shadow ctx keys
5. `tests/test_turn_planner_wiring.py` — только runtime one-call/product-firewall проверки

Любой другой diff → ❌ и СТОП.

Особенно запрещено менять:

- `TASK.md` после governance-коммита;
- `contracts/**`;
- `core/turn_planner_llm.py`;
- `core/turn_frame_from_raw.py`;
- `core/turn_frame_adapter.py`;
- `core/metadata_first_observability.py`;
- другие `orchestration/**`;
- `app.py`, `llm.py`, resolver/evidence/composer/policy/UI;
- eval specs/harness/raw;
- client content, pricebook, marketing;
- старые product tests вне allowlist.

## 5. Runtime wiring

В `run_resolver_turn()`:

1. Импортировать `plan_turn_attempt`, а не вызывать старый wrapper `plan_turn`.
2. Выполнить один вызов:

```python
attempt = plan_turn_attempt(q, sid, client_id)
plan = attempt.legacy_plan
```

3. Вся существующая product-логика ниже ветвится только по локальному `plan`.
4. `turn_plan_to_decision_frame`, `publish_turn_plan`, overrides, `intent`, `turn_planner_used`, `resolver_used`, `scope_topic_candidate` получают только legacy данные как сегодня.
5. Записать shadow outcome через изолированный recorder. Его return value нигде не использовать.
6. При `partial + legacy_plan=None` обязательно вызвать старый resolver и одновременно сохранить partial shadow в ctx.
7. При `degraded + legacy_plan!=None` сохранить planner-owned product path; shadow status остаётся degraded.

Запрещено читать `attempt.shadow_frame.topic/intent/aspects/...` для product-решений.

## 6. Shadow recorder

Добавить в `core/turn_frame_shadow.py` attempt-aware recorder с узкой сигнатурой без question/answer/history/raw:

```python
record_planner_attempt_shadow(*, attempt: PlannerAttempt) -> TurnFrame | None
```

Семантика:

| attempt status | ctx status | ctx frame | stable reason |
|---|---|---|---|
| `ok` | `ok` | serialized `shadow_frame` | отсутствует |
| `partial` | `partial` | serialized `shadow_frame` | отсутствует; причины в FieldMeta |
| `not_available` | `not_available` | отсутствует | `turn_plan_missing` |
| `degraded` | `degraded` | отсутствует | `turn_frame_build_failed` |

Дополнительно:

- добавить `SHADOW_STATUS_PARTIAL = "partial"`;
- serialization failure превращается в `degraded/turn_frame_build_failed`;
- ctx degraded выставляется до best-effort event;
- failure `emit_bot_event` поглощается, потому что primary observability уже в ctx;
- exception text нигде не сохраняется;
- старый `record_turn_frame_shadow(turn_plan, decision_frame)` можно оставить для compatibility/unit history, но runtime после A7 его не вызывает;
- не перестраивать raw shadow из `DecisionFrame`: source of truth — `attempt.shadow_frame`.

## 7. Metadata/E2E

Существующие ключи уже входят в metadata-first slice:

- `turn_frame_shadow`
- `turn_frame_shadow_status`
- `turn_frame_shadow_reason`

Production-файл `core/metadata_first_observability.py` менять запрещено.

Нужно тестами подтвердить:

- partial frame присутствует в protected E2E metadata path;
- status/error FieldMeta сериализуются;
- без `E2E_USE_TEST_CLIENT` widget/final response не расширяется по сравнению с текущим механизмом;
- raw/question/exception отсутствуют.

## 8. Обязательные тесты

Сначала reviewer смотрит diff тестов.

### 8.1 Recorder

1. `ok` сохраняет точный `shadow_frame.model_dump()`.
2. `partial` сохраняет frame, status=`partial`, очищает stale reason.
3. `not_available` очищает frame, пишет stable reason.
4. `degraded` очищает frame, пишет stable reason.
5. `model_dump()` failure → degraded, не выходит наружу.
6. `emit_bot_event()` failure не ломает recorder/product.
7. Сигнатура не принимает q/question/answer/history/raw/payload.

### 8.2 Runtime/product firewall

8. `run_resolver_turn()` вызывает `plan_turn_attempt` ровно один раз и не вызывает `plan_turn`.
9. `ok + legacy plan` даёт тот же decision/intent/product ctx, что до wiring.
10. `partial + legacy None` вызывает `resolve_with_fallback`, но ctx содержит partial topic/status/errors.
11. Partial topic не переписывает fallback `decision.service_topic`, intent или `scope_topic_candidate`.
12. `degraded + valid legacy` не уничтожает planner-owned product path.
13. `not_available` сохраняет прежний fail-open.
14. Product код не использует return value recorder.
15. AST/source firewall: кроме recorder/metadata tests downstream не читает `attempt.shadow_frame` и `attempt.shadow_status` для решений.

### 8.3 Regression

16. Existing shadow/metadata tests обновлены только под намеренную смену source: legacy adapter snapshot → attempt raw snapshot.
17. Planner/contract/product tests не ослаблены.
18. Нет skip/xfail/assert True/условного PASS.

## 9. Команды проверки

Исполнитель и checker независимо запускают через `.venv/codex312`:

```powershell
.venv\codex312\Scripts\python.exe -m pytest -q `
  tests/test_turn_frame_shadow.py `
  tests/test_metadata_first_observability.py `
  tests/test_turn_planner_wiring.py

.venv\codex312\Scripts\python.exe -m pytest -q `
  tests/test_turn_frame_from_raw.py `
  tests/test_turn_planner_llm.py `
  tests/test_turn_frame_contract.py `
  tests/test_planner_attempt_contract.py `
  tests/test_turn_plan_protocol_guard.py

.venv\codex312\Scripts\python.exe -m pytest -q `
  tests/test_contacts_routing.py `
  tests/test_pricebook_golden.py `
  tests/test_price_layer_parity.py

.venv\codex312\Scripts\python.exe -m py_compile `
  orchestration/resolver_turn.py `
  core/turn_frame_shadow.py

git diff --check
git diff --name-only
git diff -- `
  contracts core/turn_planner_llm.py core/turn_frame_from_raw.py `
  evals/v5/demo/topic_shadow_matrix.json evals/v5/demo/preservation.json
git hash-object evals/v5/demo/topic_shadow_matrix.json
git hash-object evals/v5/demo/preservation.json
```

Допустимый production diff внутри `core/**` — только `core/turn_frame_shadow.py`; отдельный разрешённый runtime diff — `orchestration/resolver_turn.py`.

Live/LLM/eval **не запускать**.

## 10. Checker review

Checker обязан:

1. Начать с diff тестов.
2. Показать полный changed-files и сверить allowlist.
3. Самостоятельно выполнить команды §9.
4. Проверить exactly-one attempt call и отсутствие соседнего `plan_turn()`.
5. Сравнить legacy product ветки до/после по diff и тестам.
6. Проверить partial fail-open, degraded-with-legacy и telemetry isolation.
7. Проверить отсутствие raw/question/exception leaks.
8. Перечислить failed/skipped/not run/warnings.
9. Дать вердикт `✅`, `❌` или `❓` с `file:line` для нарушений.

До checker `✅` implementation commit и push не создавать.

## 11. Стоп-условия

Немедленный СТОП и эскалация, если:

- нужен файл вне allowlist;
- для wiring требуется второй planner/LLM call;
- partial frame нужен product-коду;
- меняется legacy decision/intent/resolver eligibility;
- требуется ослабить `TurnPlan` или переписать prompt;
- recorder failure выходит в product runtime;
- тест можно сделать зелёным только изменением frozen spec/product expectation;
- live/LLM кажется необходимым для этого checkpoint.

## 12. Definition of Done

A7 Shadow wiring завершён, когда runtime один раз получает `PlannerAttempt`, использует только `legacy_plan` для продукта, сохраняет `shadow_frame/status` только в observability, partial `topic` переживает strict failure другого поля, старый fail-open остаётся неизменным, все unit/regression тесты зелёные, checker дал `✅`, создан отдельный commit и push только в `codex/stage-a`.
