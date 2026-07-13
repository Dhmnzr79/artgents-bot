# TASK — A7 Design: field-level planner outcome без смены product ownership

Один активный `TASK.md` на одну маленькую задачу. Файл подготовлен **Архитектором** после A6 Audit.
Общий закон — `.cursor/rules/00-guardrails.mdc`. Инварианты ревью — `REVIEW_CHECKLIST.md`.
Опора — `docs/ARCH_TARGET_DESIGN.md`, `docs/TOPIC_SHADOW_AUDIT_A6.md` и текущий runtime-код.

---

## 1. Зафиксированная точка старта

- A5 native topic shadow: `8662300`.
- A6 frozen matrix: `cd562fe`.
- A6 harness: `952c50a`.
- A6 audit: `4a6c867`.
- A6 raw SHA256: `2EF96AB8660657501137B0A6880E7EA54594E02417197F031BE1BCE2D9D5A40A`.
- Matrix hash: `dc356c9c738fb80a10cf0035508d7e8c8247979d`.
- Preservation hash: `c2072ca74c2da73bf657d793195d2eb6c8ba7bd5`.
- Рабочее дерево tracked должно быть чистым.

A6 доказал coupling: семь payload были отклонены целиком из-за `aspects=[]`, поэтому валидность `topic` нельзя было измерить независимо от unrelated legacy field.

## 2. Задача

Создать один архитектурный design-contract:

- `docs/FIELD_LEVEL_PLANNER_OUTCOME_A7.md`.

На этом checkpoint **нет реализации**. Документ должен заранее зафиксировать безопасную форму следующего strangler-шага:

```text
один raw JSON от существующего planner LLM
              ↓
field-level validation → partial TurnFrame shadow
              ↓ параллельно
strict legacy TurnPlan eligibility → текущий product path
```

Ключевой закон:

> Валидное поле нового TurnFrame не уничтожается ошибкой другого поля, но текущий strict `TurnPlan` и его влияние на продукт не ослабляются.

## 3. Что именно решает A7

Сейчас pipeline all-or-nothing:

```text
raw JSON → TurnPlan.model_validate()
                  ├─ success → DecisionFrame + shadow
                  └─ any field error → None → resolver; shadow unavailable
```

Target A7:

```text
raw JSON ─┬→ per-field normalized TurnFrame shadow
          │      topic может быть valid
          │      aspects может быть invalid: aspects_empty
          │
          └→ тот же strict TurnPlan.model_validate()
                 success → текущий planner product path
                 failure → тот же resolver/fail-open product path
```

То есть A7 разделяет **наблюдаемость** и **legacy eligibility**, но не переключает ownership.

## 4. Затрагиваемые файлы — строгий allowlist

Исполнитель может создать только:

- `docs/FIELD_LEVEL_PLANNER_OUTCOME_A7.md`.

Исполнитель не меняет:

- `TASK.md`;
- `docs/ARCH_TARGET_DESIGN.md`;
- `docs/TOPIC_SHADOW_AUDIT_A6.md`;
- `contracts/**`, `core/**`, `orchestration/**`;
- tests/evals/spec/harness;
- client content/config;
- raw artifacts.

Любой другой diff → ❌ и СТОП.

## 5. Решение, которое document обязан зафиксировать

Исполнитель не выбирает архитектурный вариант. Зафиксировать решение ниже.

### 5.1 Один semantic contract — partial-capable `TurnFrame`

Не создавать тематический `TopicObservation`, `TopicPlan`, `DoctorsPlan` или второй topic-classifier.

`TurnFrame` остаётся единым semantic contract, но становится способным честно представлять частично валидный результат:

- `aspects` может быть пустым в **shadow frame**;
- `primary_aspect` может быть `None`;
- если `primary_aspect` не `None`, он обязан входить в `aspects`;
- если `aspects=[]`, `primary_aspect=None`;
- отсутствие/ошибка одной оси фиксируется per-field, а не ломает весь frame;
- partial frame не может использоваться downstream без отдельного authority/gate.

Это изменение касается будущего TurnFrame shadow contract. Строгий legacy `TurnPlan.aspects = Field(min_length=1)` остаётся без изменений.

### 5.2 Field status/error — внутри общей metadata-модели

Design должен выбрать один source of truth внутри `FieldMeta`, расширив концепцию:

```text
confidence: 0..1
provenance: stable source
status: valid | defaulted | missing | invalid
error: stable reason | null
```

Не хранить одновременно независимые расходящиеся копии `FieldMeta.error` и top-level `field_errors`.

Термин `field_errors` в architecture означает агрегированное представление всех `FieldMeta(status=invalid)`, но source of truth — metadata конкретной оси. Если будущему telemetry нужен плоский `field_errors`, он **детерминированно выводится** из meta и не становится вторым состоянием.

### 5.3 Operational envelope — не новый semantic router

Один LLM-call должен возвращать внутренний execution outcome с двумя результатами:

```text
PlannerAttempt
  legacy_plan: TurnPlan | None
  shadow_frame: TurnFrame | None
  shadow_status: ok | partial | not_available | degraded
```

`PlannerAttempt` — технический envelope одного вызова, не новая классификация и не продуктовый маршрут.

Семантика:

- `ok`: strict legacy plan валиден, shadow frame собран без invalid fields;
- `partial`: JSON object получен, frame собран, одна или несколько осей invalid/missing; legacy plan может быть `None`;
- `not_available`: LLM не дал parseable JSON object / вызов недоступен;
- `degraded`: внутренняя ошибка field-level builder/serialization; product ход не падает.

Нельзя маркировать `partial` как `ok`.

### 5.4 Backward-compatible public seam

Design фиксирует безопасный migration seam:

- новая внутренняя функция условно `plan_turn_attempt(...) -> PlannerAttempt` делает **единственный** LLM-call;
- существующий `plan_turn(...) -> TurnPlan | None` остаётся совместимым wrapper и возвращает только `attempt.legacy_plan`;
- runtime wiring будущего этапа может вызвать attempt-функцию один раз, использовать `legacy_plan` ровно как сейчас и отправить `shadow_frame` только в observability;
- запрещено вызывать сначала `plan_turn`, затем отдельный attempt — это было бы два LLM-call;
- точные имена могут быть уточнены в implementation TASK, но семантика wrapper/envelope обязательна.

### 5.5 Две независимые ветки из одного raw object

После `json.loads()` одного LLM response:

1. Field-level builder читает raw dict и строит partial-capable shadow `TurnFrame`.
2. Strict legacy validator строит текущий `TurnPlan` или возвращает `None` по прежним правилам.

Обе ветки получают одну immutable/copy-on-read структуру. Ни одна не мутирует raw для другой.

Field-level builder не имеет права «чинить» raw перед strict legacy validation.

## 6. Required field-level semantics

Design должен задать общие правила, не только topic-specific patch.

### 6.1 Topic

- использовать A5 taxonomy и normalization;
- valid allowed string → value + confidence + provenance `turn_plan.raw.topic`, status `valid`;
- missing/null + confidence 0 → `None`, status `missing`;
- unknown/non-string/invalid confidence → безопасное `None/0`, status `invalid`, stable reason;
- не выводить topic из service_id/doc_id/filename/regex;
- native topic остаётся shadow-only.

### 6.2 Aspects

- raw list из разрешённых `AspectKind`;
- valid non-empty list → status `valid`;
- `[]` → value `[]`, status `invalid`, error `aspects_empty`;
- non-list → `[]`, `invalid`, `aspects_invalid_type`;
- неизвестный элемент → не молча удалять; status `invalid`, stable `aspect_not_allowed`;
- не подставлять `overview` автоматически;
- не выводить aspect из question regex в field-level builder.

### 6.3 Primary aspect

- берётся только из валидного ordered `aspects[0]` на первом implementation slice;
- при invalid/empty aspects → `None`, status `invalid` или `missing` с stable reason `primary_aspect_unavailable`;
- не выбирать primary отдельным classifier/regex.

### 6.4 Intent и остальные оси

Design должен описать общий паттерн для всех полей, но A7 implementation не обязан мигрировать все оси одним большим diff.

Для будущих slices:

- route/intent: invalid → `unknown` + field error;
- service_id: valid только по client catalog, иначе field error;
- followup_of: valid только по catalog/context contract;
- needs_clarify: strict bool, invalid → default false + field error;
- patient_situation/brand_filter: field-level validation без обрушения frame;
- emotion/specificity/patient_scope могут оставаться current default/missing provenance до своих задач.

Документ обязан разделить **общий target mechanism** и **минимальный первый implementation slice**.

## 7. Минимальный первый implementation slice — зафиксировать

После design review отдельный кодовый TASK должен быть ограничен:

1. Partial-capable TurnFrame contract + FieldMeta status/error.
2. Internal `PlannerAttempt` envelope.
3. Field-level extraction только достаточная для A6 blocker:
   - topic/topic_confidence;
   - aspects;
   - primary_aspect;
   - route/intent настолько, чтобы сформировать frame с `unknown` при ошибке.
4. Strict legacy `TurnPlan` validation без изменений.
5. Shadow observability получает `partial` frame.
6. Product продолжает использовать только `legacy_plan`.

Не включать в первый slice:

- ResponseSpec;
- evidence assembly;
- medzone/marketing;
- перенос route/aspects ownership;
- удаление resolver;
- полный рефактор всех TurnPlan полей;
- новый A6 live run.

## 8. Критический продуктовый инвариант

Для raw payload с:

```json
{
  "route": "content",
  "aspects": [],
  "topic": "doctors",
  "topic_confidence": 0.95
}
```

Target первого slice:

```text
PlannerAttempt.legacy_plan = None
PlannerAttempt.shadow_status = partial
PlannerAttempt.shadow_frame.topic = doctors
topic meta = valid
shadow_frame.aspects = []
aspects meta = invalid / aspects_empty
shadow_frame.primary_aspect = None
primary meta = invalid / primary_aspect_unavailable
```

Но product orchestration должна сделать ровно то же, что сейчас при `plan_turn() -> None`:

- `turn_planner_used=false` для legacy ownership;
- resolver/fail-open path остаётся текущим;
- route/decision/evidence/composer/UI/answer не читают partial frame;
- partial frame виден только ctx/logs/E2E observability.

Это главный acceptance invariant будущей реализации.

## 9. Telemetry/privacy contract

Design обязан зафиксировать:

- shadow status `partial` различим от `ok/not_available/degraded`;
- per-field stable errors без exception text;
- допустимые reasons — маленький allowlist;
- не логировать raw LLM JSON;
- не логировать question/answer/history в field-error event;
- не логировать неизвестное raw topic/aspect value;
- full partial TurnFrame допустим только в текущем защищённом ctx/E2E telemetry path по правилам A2;
- widget payload без `E2E_USE_TEST_CLIENT` не меняется;
- telemetry sink failure не ломает product ход.

## 10. Запрещённые решения

Документ должен явно отклонить:

1. Убрать `min_length=1` из legacy `TurnPlan` без eligibility guard.
2. Подставлять `aspects=["overview"]` ради валидности.
3. Переписать prompt так, чтобы LLM всегда выдумывал aspect.
4. Делать второй LLM-call/topic classifier.
5. Retry только для `aspects=[]`.
6. Сохранять raw LLM JSON в ctx/logs.
7. Создать topic-specific side channel вместо общего TurnFrame mechanism.
8. Использовать partial frame в routing/evidence/composer.
9. Считать `partial` успешным legacy plan.
10. Исправлять семь A6 кейсов тематическими if/regex.

## 11. Alternatives section

Кратко сравнить и отклонить:

| вариант | почему не выбран |
|---|---|
| Loosen legacy TurnPlan | меняет eligibility и product path |
| Force overview in prompt | подгоняет unrelated field и скрывает ошибку |
| Topic-only telemetry hook | создаёт side channel, не решает field-level target |
| Second classifier/call | повышает latency/cost и создаёт второй источник истины |
| Retry | нарушает one-call contract и скрывает planner degraded rate |
| Общий partial TurnFrame + strict legacy branch | **выбран**: один semantic contract, product ownership сохраняется |

## 12. Future implementation acceptance map

Design должен перечислить будущие обязательные тесты, не писать их сейчас:

- valid full payload → legacy plan + `ok` shadow;
- valid topic + aspects=[] → legacy None + `partial` shadow;
- topic invalid + legacy fields valid → legacy semantics прежние, topic field invalid в shadow;
- malformed/non-object JSON → `not_available`, не partial;
- builder/model_dump error → `degraded`, product не падает;
- telemetry emit failure не ломает ход;
- wrapper `plan_turn` backward compatible;
- runtime делает один LLM call;
- raw dict не мутируется;
- stable field errors без leaks;
- current seven fail-open product routes/answers не меняются;
- existing planner/shadow/contacts/price tests зелёные;
- smoke/preservation frozen hashes сохранены;
- widget без E2E не меняется;
- AST/firewall: partial frame не читается downstream.

## 13. Migration checkpoints

Документ должен предложить последовательность:

1. **A7 Design** — текущий doc-only checkpoint.
2. **A7 Contract** — TurnFrame/FieldMeta/PlannerAttempt models + unit tests, без runtime wiring.
3. **A7 Planner split** — один raw → partial frame + strict legacy plan, unit-only.
4. **A7 Shadow wiring** — orchestration использует legacy plan как сейчас, partial только telemetry.
5. **A7 Regression/live proof** — проверить семь путей и smoke/preservation без смены product output.
6. **A7 Topic re-audit** — только отдельный frozen run с новым именем; первый A6 raw сохраняется.

Каждый пункт — отдельный `TASK.md`/review/commit. Не объединять всё в один diff.

## 14. Что design НЕ разрешает после принятия

Принятие design-doc:

- не разрешает менять код автоматически;
- не разрешает topic authority;
- не закрывает A6 sample;
- не разрешает повтор live;
- не делает TurnFrame product source of truth;
- не разрешает удалять legacy router/resolver;
- не начинает marketing stage.

## 15. Raw/frozen evidence

В design привести только минимальные подтверждения из A6 Audit:

- 26 scoreable / 7 unavailable;
- 0 mismatches среди scoreable;
- все 7 unavailable связаны с `aspects=[]` strict validation;
- doctors coverage 0/3;
- ссылки на `docs/TOPIC_SHADOW_AUDIT_A6.md`, не дублировать весь raw audit;
- original raw/hash остаются неизменными.

Не добавлять новые claims о topic отклонённых payload.

## 16. Проверки design checkpoint

```powershell
Get-FileHash -Algorithm SHA256 eval_topic_shadow_a6_last.txt
git diff --check
git status --short
git diff -- docs/ARCH_TARGET_DESIGN.md docs/TOPIC_SHADOW_AUDIT_A6.md contracts core orchestration tests evals
git hash-object evals/v5/demo/topic_shadow_matrix.json
git hash-object evals/v5/demo/preservation.json
```

Read-only проверить:

- changed only design-doc;
- выбранный вариант однозначен;
- strict legacy TurnPlan остаётся строгим;
- partial TurnFrame не получает authority;
- один LLM-call;
- семь product paths сохраняются;
- нет topic-specific workaround;
- migration разбита на отдельные checkpoints;
- raw/frozen hashes прежние.

Live/unit тесты не запускать: код не меняется, повторный LLM запрещён.

## 17. Стоп-условия

СТОП, если:

- нужен файл вне allowlist;
- для design требуется менять код;
- хочется ослабить legacy TurnPlan;
- невозможно сохранить current product path при partial shadow;
- предлагается новый LLM-call/retry/classifier;
- предлагается raw JSON telemetry;
- partial frame нужно читать downstream;
- raw/hash изменился;
- появился посторонний diff.

## 18. Контрольные точки

### Checkpoint 1 — Design authoring

Исполнитель создаёт только `docs/FIELD_LEVEL_PLANNER_OUTCOME_A7.md`, сверяет current code/read-only и делает СТОП без commit.

### Checkpoint 2 — Design review

Checker независимо проверяет выбранную dual-branch архитектуру, backward compatibility, отсутствие второго semantic contract/topic side channel, product firewall и migration boundaries.

Вердикт: `✅ / ❌ / ❓`.

### Checkpoint 3 — Design commit

Только после `✅` владелец разрешает commit одного design-doc.

## 19. Формат отчёта Исполнителя

1. Changed-files.
2. Карта разделов design.
3. Current→target data flow.
4. Выбранный вариант и rejected alternatives.
5. Product invariants.
6. Future acceptance tests/checkpoints.
7. Raw/matrix/preservation hashes.
8. Skipped/not run.
9. СТОП без commit.

## 20. Критерий приёмки A7 Design

A7 Design принят, когда один новый документ однозначно задаёт single-call dual-branch strangler: partial-capable `TurnFrame` с per-field status/error для shadow и неизменный strict `TurnPlan` для текущего product ownership; `aspects=[]` больше не уничтожает наблюдаемость других валидных осей, но по-прежнему не переводит ход на planner-owned route; implementation разбита на отдельные безопасные checkpoints.
