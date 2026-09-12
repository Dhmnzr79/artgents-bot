# A9 Native Patient-scope — Raw Contract и Prompt Spec

Статус: **frozen specification, shadow-only, implementation disabled**.

Этот документ замораживает входной контракт для следующего code checkpoint. Он не меняет действующий planner prompt, не включает native parser и не даёт patient scope влиять на ответ пациенту.

Канонический machine-readable fixture: `tests/fixtures/patient_scope_native_contract_a9_v2.json`.

## Что это даст боту

Сейчас — никакого изменения текста, цены, рекомендаций, CTA или UI. Мы заранее определяем, какой JSON будущий planner должен вернуть и как безопасно отделить новые shadow-данные от работающего legacy product path.

После отдельной реализации это позволит измерять четыре независимых признака текущего сообщения пациента:

- масштаб: один зуб, несколько зубов или вся дуга;
- верхняя/нижняя/обе челюсти;
- контекст удаления или уже установленного импланта;
- явно сообщённый контекст нехватки кости.

Это наблюдение, не диагноз и не автоматический выбор лечения.

## 1. Версия и границы

Schema version: `a9.patient_scope_native_contract.v2`.

- один существующий planner call;
- один flat JSON object;
- прежние legacy fields сохраняются;
- добавляется один top-level shadow sibling `patient_scope`;
- `patient_situation` остаётся отдельным legacy product input;
- merge/reconciliation scalar и nested scope запрещены;
- retry, второй classifier и второй LLM-call запрещены;
- authority: **forbidden**;
- live: **не разрешён этим checkpoint**.

## 2. Exact raw shape

Будущий planner output:

```json
{
  "route": "content",
  "aspects": ["overview"],
  "service_id": null,
  "followup_of": null,
  "needs_clarify": false,
  "patient_situation": "upper_jaw_missing_or_complex",
  "brand_filter": null,
  "topic": "implantation",
  "topic_confidence": 0.8,
  "patient_scope": {
    "extent": "full_arch",
    "jaw": "upper",
    "stage": "unknown",
    "modifiers": ["reported_bone_deficit"]
  }
}
```

`patient_scope` всегда object ровно с четырьмя keys:

| Field | Allowed values | Safe value |
|---|---|---|
| `extent` | `unknown`, `one_tooth`, `few_teeth`, `full_arch` | `unknown` |
| `jaw` | `unknown`, `upper`, `lower`, `both` | `unknown` |
| `stage` | `unknown`, `extraction_context`, `implant_placed` | `unknown` |
| `modifiers` | list, единственный allowed item `reported_bone_deficit` | `[]` |

`unknown` и `[]` означают явное незнание модели. `patient_scope=null` — неверный тип контейнера, а не all-unknown.

## 3. Exact legacy projection

После `json.loads()` original dict не изменяется. Будущий seam создаёт отдельный legacy object, удаляя только exact sibling:

```python
legacy_raw = {
    key: value
    for key, value in raw.items()
    if key != "patient_scope"
}
```

Обязательные свойства:

1. Ни одно legacy value не нормализуется новым A9 seam.
2. Любой другой unknown top-level key сохраняется и остаётся fatal для `TurnPlan(extra="forbid")`.
3. Invalid nested scope не меняет legacy eligibility.
4. Invalid legacy field не уничтожает independently valid native observation.
5. Original dict остаётся deep-equal исходному.
6. `patient_scope` не попадает в `TurnPlan`, product ctx/dump, resolver или composer.

Пять frozen projection cases перечислены в JSON fixture и независимо зафиксированы hardcoded manifest в `tests/test_patient_scope_native_contract_spec.py`.

## 4. Container metadata

| Raw state | Container metadata | Children |
|---|---|---|
| sibling отсутствует | `defaulted`, error `None`, `turn_plan.schema_default` | текущий scalar bridge без изменений |
| object только с allowed keys | `valid`, error `None`, `turn_plan.raw.patient_scope` | все members парсятся независимо |
| `null` или не-object | `invalid`, `patient_scope_invalid_type`, `turn_plan.raw.patient_scope` | четыре safe values, child metas `defaulted` |
| object с unknown extra | `invalid`, `patient_scope_extra_field`, `turn_plan.raw.patient_scope` | known neighbors всё равно парсятся |
| object с missing/invalid member | container остаётся `valid` | member остаётся missing/invalid, без scalar backfill |

Confidence всегда `0.0`. Это descriptive placeholder, не вероятность и не threshold.

Unknown extra name/value не сериализуются в frame metadata или error. Container/member `missing` или `invalid` означает `shadow_status=partial`, не `degraded`.

## 5. Source precedence

Ownership выбирается на уровне всего контейнера:

| Raw state | Source |
|---|---|
| `patient_scope` отсутствует | current scalar bridge |
| `patient_scope` присутствует object | только native object |
| container неверного типа | native invalid-container result |
| member missing/invalid | native member result без bridge backfill |

Даже если legacy `patient_situation` содержит безопасное значение, он не должен маскировать ошибку present native container/member. Расхождение scalar и nested — допустимый measurement fact; оно не вызывает retry и не меняет product branch.

При absent sibling существующий bridge provenance сохраняется буквально:

```text
turn_plan.patient_situation.extent
turn_plan.patient_situation.jaw
turn_plan.patient_situation.stage
turn_plan.patient_situation.modifiers
```

Mapped child получает соответствующий bridge provenance; unmapped children остаются `turn_plan.schema_default`. Для present native object provenance каждого child — `turn_plan.raw.patient_scope.<field>`.

## 6. Member parser states

| Input | Expected result |
|---|---|
| allowed value | value, `valid`, error `None` |
| explicit `unknown` / `[]` | safe value, но status `valid` |
| member отсутствует | safe value, `missing`, error `None` |
| wrong type | safe value, `invalid`, corresponding `*_invalid_type` |
| scalar вне allowlist | safe value, `invalid`, corresponding `*_not_allowed` |
| modifiers не list или содержит non-string | `[]`, `invalid`, `patient_modifiers_invalid_type` |
| modifiers содержит unsupported string | `[]`, `invalid`, `patient_modifier_not_allowed` |
| duplicate allowed modifiers | unique sorted list, `valid` |

Mixed valid+invalid modifiers целиком становятся `[]/invalid`; partial filtering запрещён. Invalid одного member не стирает valid neighbors.

Fixture содержит exact ordered manifest:

- 5 projection cases;
- 4 source-precedence cases;
- 18 parser-state cases;
- 5 abstract prompt examples.

Test code хранит IDs независимо от JSON, поэтому неполный или расширенный fixture не может подтвердить сам себя.

## 7. Prompt semantic contract

Следующий implementation checkpoint сможет добавить в `_SYSTEM` краткие правила, но обязан сохранить этот смысл:

1. `patient_scope` — object с четырьмя обязательными keys.
2. Извлекаются только явно сообщённые признаки текущего сообщения.
3. Если признак не сообщён — `unknown`/`[]`; угадывать нельзя.
4. History помогает понять referent, но не переносит старое scope-value без explicit current mention.
5. Legacy `patient_situation` возвращается отдельно.
6. Scope не выбирает service, protocol, price unit, document, evidence или diagnosis.
7. Urgency и pain не относятся к scope.
8. `reported_bone_deficit` — сообщённый контекст, не клиническое подтверждение.
9. Только JSON, без extra fields.

Frozen examples хранят только abstract meaning IDs и expected scope:

- one tooth → `one_tooth / unknown / unknown / []`;
- full upper + reported bone context → `full_arch / upper / unknown / [reported_bone_deficit]`;
- implant already placed → `unknown / unknown / implant_placed / []`;
- informational, no patient facts → all unknown/empty;
- vague follow-up with old session extent but no current facts → all unknown/empty.

В fixture нет пользовательских фраз, session IDs или копий live raw. Exhaustive phrase classifier, frozen live case IDs и service mappings запрещены.

## 8. Completion-size evidence

Fixture содержит representative upper-size schema sample:

- все legacy fields заполнены;
- перечислены все allowed aspects;
- native sibling заполнен длинными enum values.

Compact UTF-8 measurement:

| Sample | Bytes |
|---|---:|
| без `patient_scope` | 465 |
| с `patient_scope` | 585 |
| additive native sibling delta | 120 |

Это **не общий worst-case**: catalog-derived strings зависят от клиента и не имеют length bound в `TurnPlan`. Bytes также не равны tokenizer-exact tokens.

Поэтому этот spec не заявляет, что текущего `max_completion_tokens=300` точно достаточно. Runtime limit здесь не меняется. До implementation code новый TASK обязан принять явное решение: сохранить `300` только с model-tokenizer/static evidence либо обосновать консервативный новый limit. Live-подбор запрещён.

## 9. Privacy и product firewall

Fixture разрешает synthetic governed planner objects, необходимые для schema tests. Запрещены:

- копии первого/v1 live raw;
- вопросы и ответы пациентов;
- history/session IDs/PII/secrets;
- product answer, price, UI или routing authority;
- изменение v1 matrix/harness/audit artifacts.

Первый A9 raw остаётся immutable. Native patient scope остаётся shadow-only, authority forbidden.

## 10. Следующий checkpoint

`A9 Native Extraction Implementation` — отдельный governance TASK, checker review до кода, unit-only implementation prompt + exact projection + native parser. Scalar bridge должен сохраниться как fallback только при полном отсутствии sibling.

Live/LLM, wiring audit, harness v2 и authority остаются отдельными будущими checkpoints.
