# A9 — unknown-safe composable patient scope

Статус: design-only, shadow target. Этот документ не передаёт authority, не меняет runtime и не разрешает реализацию без нового `TASK.md`.

## 1. Решение в одном абзаце

Выбран вариант **B: компактный nested/composable `patient_scope`**. Вместо одного взаимоисключающего enum будущий `TurnFrame` хранит четыре независимых части: масштаб отсутствующих/восстанавливаемых зубов (`extent`), явно названную челюсть (`jaw`), явно названный этап (`stage`) и короткий allowlist явно сообщённых обстоятельств (`modifiers`). У каждой части есть собственный `FieldMeta`; неизвестность нормальна и не уничтожает известные части. Срочность, диагноз, подходящий протокол и `service_id` в scope не входят. Первым источником shadow будет уже существующий `patient_situation` из **того же** planner-вызова, но только через консервативный loss-aware mapping; legacy detector и отдельный patient-situation LLM не становятся вторым target source of truth.

## 2. Что именно решает patient scope

Patient scope отвечает только на вопрос:

> Какие немедицинские, явно сообщённые признаки масштаба и текущего этапа ситуации известны в этом ходе?

Он может хранить, например:

- `extent=one_tooth`, когда явно говорится об одном зубе;
- `jaw=upper`, даже если количество зубов неизвестно;
- `stage=implant_placed`, даже если челюсть неизвестна;
- `modifiers=[reported_bone_deficit]`, когда пациент явно сообщает, что врач сказал о нехватке кости.

Он не обязан быть полностью заполнен. Состояние «известна верхняя челюсть, остальное неизвестно» корректно.

Patient scope **не** отвечает:

- какой у пациента диагноз;
- достаточно ли кости в действительности;
- показан ли конкретный метод;
- All-on-4 или All-on-6 нужен пациенту;
- нужна ли операция;
- насколько срочно лечение с медицинской точки зрения;
- какой `service_id`, документ, pricebook entry или ответ выбрать.

## 3. Current state: contracts и data flow

### 3.1 Текущие контракты смешивают разные понятия

`PatientSituationKind` содержит десять headline-категорий (`contracts/patient_situation.py:9-20`). `PatientScope` содержит девять значений (`contracts/patient_situation.py:22-32`), но они не являются значениями одной природы:

| Природа | Current `PatientScope` |
|---|---|
| масштаб | `one_tooth`, `few_teeth`, `full_jaw` |
| анатомия | `upper_jaw` |
| этап | `prosthetic_stage` |
| обстоятельство | `adjunct` |
| medical/boundary signal | `urgent` |
| отсутствие конкретного масштаба | `generic`, `unknown` |

Одновременно `PatientSituationResult` уже имеет composable-поля `problem`, `extent`, `jaw`, `modifiers` (`contracts/patient_situation.py:79-104`). Это доказывает полезность композиции, но current model остаётся legacy product contract, а не готовый target.

В `TurnFrame` пока есть scalar `patient_scope: str | None` и только один `FieldMeta` на всю ось (`contracts/turn_frame.py:55-89`).

### 3.2 Producers и два расходящихся profile path

Текущий runtime имеет два основных способа получить `PatientSituationResult`:

1. `detect_patient_situation()` извлекает regex/cues, определяет headline kind, строит composable profile и при включённом флаге может дополнить его отдельным semantic LLM (`core/patient_situation.py:486-562`).
2. Если strict `TurnPlan` содержит `patient_situation`, `resolve_patient_situation_for_turn()` строит результат через `_result_from_turn_plan()` (`core/patient_situation_session.py:34-78`, `:107-126`).

Оба пути дублируют kind → scope:

- `_scope_for_kind()` (`core/patient_situation.py:152-164`);
- `_PLANNER_SCOPE_BY_KIND` (`core/patient_situation_session.py:13-24`).

Сегодня таблицы совпадают, но это две копии с риском drift. Profile уже расходится:

- `_profile_for()` учитывает cues и текст, поэтому может сохранить одновременно extent, jaw и modifier (`core/patient_situation.py:218-276`);
- `_result_from_turn_plan()` знает только scalar kind; он принудительно выводит `upper_jaw → full_arch` и теряет составные cues (`core/patient_situation_session.py:26-74`).

Особенно показателен `upper_jaw_missing_or_complex`: current rule может означать как отсутствие зубов сверху, так и только фразу «мало кости сверху» (`core/patient_situation.py:402-412`). Поэтому из этого kind безопасно вывести `jaw=upper`, но небезопасно всегда выводить `extent=full_arch`.

### 3.3 Два semantic LLM source сегодня

Единый turn planner уже делает один semantic вызов и возвращает scalar `patient_situation` (`core/turn_planner_llm.py:36-69`, `:528-655`).

Отдельно legacy detector может вызвать `classify_patient_situation_semantic()` (`core/patient_situation.py:279-337`). Этот второй классификатор имеет собственные allowlists `problem/extent/jaw/modifiers` (`core/patient_situation_llm.py:10-29`) и отдельный LLM-call (`llm.py:1551-1611`).

Target не должен получать два конкурирующих semantic ответа на один пользовательский ход. Отдельный classifier допускается только как временная comparison telemetry до удаления, не как authority или fallback, который переписывает target scope.

### 3.4 Current TurnFrame mismatch

Legacy adapter сейчас копирует `TurnPlan.patient_situation` в `TurnFrame.patient_scope` как строку (`core/turn_frame_adapter.py:130-140`). Поэтому значение `one_tooth_missing` объявляется valid patient scope, хотя current `PatientScope` ожидает `one_tooth`. Это semantic mismatch, а не target mapping.

Pure raw builder, напротив, пока выставляет `patient_scope=None` с provenance `a7.not_migrated` (`core/turn_frame_from_raw.py:245-285`). Именно этот незаполненный shadow slice должен стать будущей точкой A9 extraction.

### 3.5 Current product consumers

Legacy `PatientSituationResult` уже влияет на продукт. Это нельзя путать с будущим TurnFrame authority:

| Consumer | Current effect |
|---|---|
| `orchestration/ask_turn.py:174-183` | вычисляет, пишет в ctx и сохраняет current legacy situation |
| `core/patient_situation.py:565-600` | пишет scalar scope и composable fields в telemetry/`request.ctx` |
| `core/patient_situation_routing.py:40-69` | разрешает soft unit bias только для allowlist scopes и confidence gate |
| `core/patient_situation_routing.py:72-117` | может дополнить price scope и выбрать jaw/one-tooth/prosthetic group |
| `core/patient_playbook.py:202-245` | сопоставляет kind/problem/extent/jaw/intent/modifiers |
| `core/patient_playbook.py:250-318` | выбирает configured service options и переносит scalar scope в result |
| `orchestration/patient_playbook_flow.py:98-237` | использует options overview в product path |
| `orchestration/composer_flow.py:73-120` | читает legacy scalar из ctx и откладывает jaw price composer |
| `session.py:523-558` | хранит snapshot с age guard и умеет очищать его |
| `core/patient_situation_session.py:99-149` | применяет carry только к vague price follow-up |

Есть и параллельные cue-consumers: `core/patient_scope_cues.py:9-145`, `core/price_scope.py:114-194`, `core/price_offers.py:216-278`, `core/explicit_service.py:82-246`. Они повторно читают пользовательский текст для price/service boundaries. A9 Design не удаляет их и не объявляет target scope заменой этих guards.

## 4. Полный inventory current kinds и потерь

| `PatientSituationKind` | Current coarse scope | Rule profile, если cues достаточны | Что теряется/смешивается |
|---|---|---|---|
| `one_tooth_missing` | `one_tooth` | problem `missing_teeth`, extent `one_tooth`, возможны jaw/modifiers | headline не хранит jaw/stage |
| `few_teeth_missing` | `few_teeth` | problem `missing_teeth`, extent `few_teeth` | jaw и распределение дефекта неизвестны |
| `full_arch_missing` | `full_jaw` | problem `missing_teeth`, extent `full_arch`, возможны jaw/modifiers | `full_jaw` смешивает extent и anatomy; не ясно one/both jaws |
| `upper_jaw_missing_or_complex` | `upper_jaw` | jaw `upper`; problem часто `missing_teeth`; extent зависит от cues | один kind объединяет full-arch missing и bone-only complexity |
| `existing_implant_prosthetic_stage` | `prosthetic_stage` | problem `existing_implant`, modifier `existing_implant` | этап смешан с coarse scope; extent/jaw обычно теряются |
| `extraction_then_implant` | `one_tooth` | problem `missing_teeth`, extent `one_tooth`, иногда modifier `extracted` | planned extraction и already extracted не различаются |
| `bone_deficit_or_grafting` | `adjunct` | problem/modifier `bone_deficit` | explicit reported context смешан с процедурой/диагнозом |
| `urgent_problem` | `urgent` | problem/modifier `urgent` | medical boundary ошибочно помещён в scope |
| `generic_implant_interest` | `generic` | problem `generic_implant_interest`, scope details unknown | «интерес» не является масштабом |
| `unknown` | `unknown` | все независимые поля могут быть unknown | корректное состояние, не ошибка само по себе |

Фактические profile values ограничены current code:

- `problem`: `unknown`, `missing_teeth`, `bone_deficit`, `existing_implant`, `urgent`, `generic_implant_interest` (`core/patient_situation.py:248-263`);
- `extent`: `unknown`, `one_tooth`, `few_teeth`, `full_arch` (`core/patient_situation.py:265-274`);
- `jaw`: `unknown`, `upper`, `lower`; отдельный LLM также допускает `both` (`core/patient_situation.py:234-237`, `core/patient_situation_llm.py:27-29`);
- `modifiers`: `bone_deficit`, `extracted`, `existing_implant`, `urgent` (`core/patient_situation.py:239-246`).

## 5. Repository evidence inventory

Это read-only inventory, не frozen eval и не заявление о текущей точности. Колонка «design gap» показывает, какую информацию должен уметь представить target contract.

| # | Existing question | Source | Evidence category | Design gap |
|---:|---|---|---|---|
| 1 | «нет одного зуба» | `tests/test_patient_situation.py:12-19` | one tooth | extent известен; jaw/stage unknown |
| 2 | «Не хватает нескольких зубов, что лучше поставить?» | `tests/test_patient_playbook.py:106-117` | few teeth | extent известен независимо от treatment choice |
| 3 | «нужно восстановить всю челюсть» | `tests/test_patient_situation.py:21-26` | full arch | extent full arch; какая jaw не сказано |
| 4 | «нет зубов на верхней челюсти» | `tests/test_patient_situation.py:28-32` | upper full arch | extent и jaw известны одновременно |
| 5 | «У меня снизу съёмный протез, можно заменить на несъёмный на имплантах?» | `evals/v5/archive/implant_golden.v4.json:230` | lower jaw/context | jaw lower; extent и stage нельзя угадывать |
| 6 | «имплант уже стоит, нужна коронка» | `tests/test_patient_situation.py:34-39` | implant placed | stage известен, extent/jaw могут быть unknown |
| 7 | «нужно удалить зуб и поставить имплант» | `tests/test_patient_situation.py:48-51` | extraction context | этап известен, service suitability не следует |
| 8 | «удалили зуб, хочу имплант» | `tests/test_patient_situation.py:12-19` | already removed | current kind теряет отличие от planned extraction |
| 9 | «сказали кости мало» | `tests/test_patient_situation.py:41-46` | reported bone context | modifier допустим; это не подтверждённый диагноз |
| 10 | «болит зуб» | `tests/test_patient_situation.py:53-58` | urgent complaint | medical boundary, не patient scope |
| 11 | «что такое имплантация» | `tests/test_patient_situation.py:60-64` | generic information | все scope subfields unknown — это нормально |
| 12 | «имплант» | `tests/test_patient_situation.py:66-70` | short/vague | unknown не заменяется nearest value |
| 13 | «нечем жевать справа» | `tests/test_patient_situation.py:164-167` | ambiguous extent/location | current `few_teeth` не должен стать frozen target truth |
| 14 | «Нет зубов на верхней челюсти, мало кости, что посоветуете?» | `tests/test_patient_situation.py:183-189` | composite | одновременно extent + jaw + modifier |
| 15 | «Сколько стоит имплантация?» | `tests/price_query_cases.py:13-16` | generic price | price intent известен, patient scope unknown |
| 16 | «Сколько стоит имплантация всей верхней челюсти?» | `tests/price_query_cases.py:24-26` | scoped price | extent+jaw известны; protocol неизвестен |
| 17 | «У меня уже стоит имплант, сколько стоит коронка?» | `tests/test_price_scope_router.py:93-100` | stage + price | stage известен; product route сегодня отдельный legacy path |
| 18 | «А сколько стоит?» после «У меня нет одного зуба…» | `tests/test_patient_situation_session.py:67-80` | session carry | current turn unknown; carried extent остаётся отдельным source |
| 19 | новый вопрос про All-on-4 после one-tooth context | `tests/test_patient_situation_session.py:83-92` | topic/scope replacement | explicit new context должен заменить stale carry |
| 20 | «Очень болит зуб, срочно запишите меня пожалуйста» | `tests/test_explicit_booking_lead_gate.py:8-17` | explicit booking + complaint | booking/boundary обрабатываются вне scope |

Coverage gaps, которые будущая matrix обязана включить, но current examples не закрывают качественно:

- явное `both` jaws без предположения из «нет зубов вообще»;
- составной multi-turn случай, где jaw приходит на втором ходу;
- конфликт current turn и carried jaw/extent;
- invalid raw subfield при валидных соседних subfields;
- planned extraction против already removed;
- explicit absence/unknown, а не только отсутствие ключа;
- вопросы вне имплантации, чтобы scope не стал implant-only classifier.

## 6. Orthogonal dimensions: что входит в target

| Dimension | Target decision | Почему |
|---|---|---|
| extent/quantity | входит | это собственно масштаб: один, несколько, full arch, unknown |
| jaw/anatomy | входит | независимо от extent: upper/lower/both/unknown |
| care stage | входит в узком виде | только явно названный extraction context или уже установленный implant |
| explicit modifiers | входит с минимальным allowlist | только reported bone deficit; не диагноз |
| urgency/pain | **не входит** | это medical/boundary policy axis; нельзя делать разновидностью масштаба |
| generic implant interest | **не входит** | topic/intent уже описывают предмет и намерение |
| treatment/service recommendation | **не входит** | является downstream decision и требует evidence/clinical boundary |

## 7. Сравнение архитектурных вариантов

| Критерий | A. Scalar | B. Nested/composable | C. Top-level axes | D. Current result / parallel detector |
|---|---|---|---|---|
| Составной случай | плохо: одно значение вытесняет другое | хорошо | хорошо | частично, но два producer path |
| Unknown по части данных | невозможно без потери | естественно по subfield | естественно по axis | частично, но coarse scope остаётся |
| Field-level errors | одна ошибка на всё поле | per subfield через общий `FieldMeta` | per axis через общий `FieldMeta` | отдельная legacy confidence/evidence модель |
| Backward compatibility | малый diff, но закрепляет ошибку | shadow type меняется, product legacy остаётся | добавляет 4 top-level TurnFrame axes | максимальный runtime coupling |
| Число сущностей | мало, но семантика неверна | один value-contract + один meta-contract | раздувает TurnFrame/TurnFrameMeta | сохраняет kind/scope/profile/regex/second LLM |
| Session semantics | coarse snapshot | можно различить subfields, но carry остаётся внешним | то же, с большим API | current carry уже product-coupled |
| Latency | без изменений | без изменений | без изменений | возможен второй LLM-call |
| Удаление legacy | нет ясного пути | loss-aware bridge → direct raw → retire duplicate paths | возможно, но больше consumers | плохой путь: legacy становится target |

### Почему не A

Scalar не может представить `full_arch + upper + reported_bone_deficit`. Значения `full_jaw`, `upper_jaw`, `urgent`, `prosthetic_stage` взаимоисключаются технически, хотя не взаимоисключаются семантически.

### Почему не C

Top-level axes выразительны, но добавят минимум четыре поля в `TurnFrame` и четыре поля в `TurnFrameMeta`, хотя они образуют один логический scope. Это увеличит поверхность всех consumers и противоречит meta-goal «меньше сущностей».

### Почему не D

`PatientSituationResult` уже product-coupled, имеет headline kind, coarse scope, hints, action, clarification и отдельный semantic LLM. Сделать его authority — значит сохранить параллельную архитектуру вместо strangler migration.

### Выбор B

Nested contract сохраняет одну логическую ось `patient_scope`, но делает её внутренне composable. Он переиспользует `FieldMeta`, не добавляет LLM-call и даёт понятный путь удалить scalar mappings после измерения.

## 8. Точный target contract

Имена ниже являются решением A9 Design. Их изменение потребует нового governance review.

```python
PatientExtent = Literal[
    "unknown",
    "one_tooth",
    "few_teeth",
    "full_arch",
]

PatientJaw = Literal[
    "unknown",
    "upper",
    "lower",
    "both",
]

PatientCareStage = Literal[
    "unknown",
    "extraction_context",
    "implant_placed",
]

PatientScopeModifier = Literal[
    "reported_bone_deficit",
]

class PatientScopeFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    extent: PatientExtent = "unknown"
    jaw: PatientJaw = "unknown"
    stage: PatientCareStage = "unknown"
    modifiers: list[PatientScopeModifier] = Field(default_factory=list)

class PatientScopeFrameMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    extent: FieldMeta
    jaw: FieldMeta
    stage: FieldMeta
    modifiers: FieldMeta

class TurnFrame(BaseModel):
    ...
    patient_scope: PatientScopeFrame

class TurnFrameMeta(BaseModel):
    ...
    patient_scope: PatientScopeFrameMeta
```

### 8.1 Семантика значений

- `extent` описывает число/масштаб отсутствующих или восстанавливаемых зубов, а не метод лечения.
- `full_arch` означает явно названный полный зубной ряд как минимум одной челюсти. Какая челюсть — только `jaw`.
- `jaw=both` требует явного указания обеих челюстей; «нет зубов вообще» не обязано автоматически означать `both` до frozen spec review.
- `stage=extraction_context` означает только явное обсуждение удаления до/в связи с восстановлением. Он не утверждает, что одномоментная имплантация возможна.
- `stage=implant_placed` означает явное сообщение, что имплант уже установлен. Он не утверждает, какая коронка нужна.
- `reported_bone_deficit` означает, что вопрос содержит сообщение пациента о нехватке/атрофии кости или уже названной костной процедуре. Это не медицинская верификация.

### 8.2 Invariants

1. Все четыре subfields независимы; all-unknown frame валиден.
2. `modifiers` уникальны и сериализуются в canonical sorted order.
3. `jaw` не выводится из `extent`; `extent` не выводится из `jaw`.
4. `service_id`, protocol, diagnosis и urgency не выводятся из scope.
5. Invalid одного subfield заменяет только его value безопасным unknown/empty и не меняет соседние subfields.
6. `extra="forbid"` действует и для value, и для meta contract.
7. Расширение allowlist values/modifiers — отдельное contract decision, не client content change.

### 8.3 Metadata granularity

Каждый subfield получает обычный `FieldMeta` с `confidence`, `provenance`, `status`, `error`. Отдельный `field_errors` store запрещён.

Current `PlannerAttempt` и planner wrapper обходят `TurnFrameMeta` как плоский набор и ожидают `.status` непосредственно у каждой meta-оси (`contracts/planner_attempt.py:15-21`, `core/turn_planner_llm.py:500-504`). После замены `patient_scope: FieldMeta` на `PatientScopeFrameMeta` этот обход должен быть обновлён **в contract checkpoint**: для patient scope он рекурсивно проверяет `extent/jaw/stage/modifiers`, для остальных осей сохраняет текущую проверку. Любой nested `invalid`/`missing` делает attempt `partial`; `defaulted` не делает. Container-level status и второй агрегат ошибок не добавляются.

Stable provenance initial allowlist:

```text
turn_plan.patient_situation.extent
turn_plan.patient_situation.jaw
turn_plan.patient_situation.stage
turn_plan.patient_situation.modifiers
turn_plan.schema_default
```

Suffix обозначает результат deterministic bridge mapping, а не прямое поле current raw JSON. Confidence initial bridge всегда `0.0`, потому что current scalar planner не возвращает per-subfield confidence. Нельзя выдавать deterministic mapping за уверенность распознавания исходной фразы.

Stable errors:

```text
patient_extent_invalid_type
patient_extent_not_allowed
patient_jaw_invalid_type
patient_jaw_not_allowed
patient_stage_invalid_type
patient_stage_not_allowed
patient_modifiers_invalid_type
patient_modifier_not_allowed
```

Raw value, вопрос, answer/history и exception text не включаются в value dump ошибки, provenance или telemetry.

### 8.4 Default / missing / invalid

- raw `patient_situation` отсутствует/null/`unknown`/`generic_implant_interest` → все values unknown/empty, metadata `defaulted`, provenance `turn_plan.schema_default`;
- известный legacy kind заполняет только lossless subfields; остальные остаются `defaulted`;
- будущий явный nested subfield со значением `unknown` считается `valid`, confidence `0.0`;
- structurally ожидаемый, но потерянный при bridge subfield может быть `missing` только если frozen contract требует его для конкретного source; сам Design таких обязательных пар не вводит;
- неверный тип или значение → только соответствующий subfield `invalid` с exact stable error.

Unknown value и metadata status различаются: `unknown + valid` означает, что source явно не знает значение; `unknown + defaulted` — source его не предоставлял; `unknown + invalid` — source предоставил неприемлемое значение.

## 9. Консервативный bridge из current scalar kind

Первый implementation slice не меняет planner prompt. Он использует current `patient_situation` из того же raw JSON и переносит только семантически безопасные части:

| Current kind | extent | jaw | stage | modifiers | Почему не больше |
|---|---|---|---|---|---|
| `one_tooth_missing` | `one_tooth` | unknown | unknown | `[]` | kind не хранит jaw/stage |
| `few_teeth_missing` | `few_teeth` | unknown | unknown | `[]` | kind не хранит jaw |
| `full_arch_missing` | `full_arch` | unknown | unknown | `[]` | нельзя угадывать upper/lower/both |
| `upper_jaw_missing_or_complex` | unknown | `upper` | unknown | `[]` | kind объединяет missing и bone-only context |
| `existing_implant_prosthetic_stage` | unknown | unknown | `implant_placed` | `[]` | количество и jaw неизвестны |
| `extraction_then_implant` | unknown | unknown | `extraction_context` | `[]` | planned/already removed и quantity не гарантированы scalar kind |
| `bone_deficit_or_grafting` | unknown | unknown | unknown | `[reported_bone_deficit]` | modifier — context, не диагноз |
| `urgent_problem` | unknown | unknown | unknown | `[]` | urgency остаётся boundary axis |
| `generic_implant_interest` | unknown | unknown | unknown | `[]` | topic/intent, не scope |
| `unknown`/null/absent | unknown | unknown | unknown | `[]` | не угадывать |

Этот bridge shadow-only и loss-aware. Он не читает question/history/session, не запускает detector/LLM и не чинит strict raw перед `TurnPlan.model_validate()`.

Прямой nested output от единого planner может обсуждаться только после bridge matrix/audit. Это отдельный prompt checkpoint; второй LLM-call не требуется.

## 10. Worked examples

### 10.1 Составной случай

Вопрос: «Нет зубов на верхней челюсти, врач сказал, что мало кости».

Target после будущего direct extraction:

```json
{
  "extent": "full_arch",
  "jaw": "upper",
  "stage": "unknown",
  "modifiers": ["reported_bone_deficit"]
}
```

Это не означает All-on-4, All-on-6, синус-лифтинг или скуловую имплантацию.

### 10.2 Частично неизвестный случай

Вопрос: «Имплант уже стоит, что дальше?»

```json
{
  "extent": "unknown",
  "jaw": "unknown",
  "stage": "implant_placed",
  "modifiers": []
}
```

Известный stage сохраняется; extent/jaw не угадываются.

### 10.3 Invalid unrelated subfield

Raw future payload содержит valid `extent=one_tooth`, invalid `jaw="right"`, stage отсутствует.

```json
{
  "patient_scope": {
    "extent": "one_tooth",
    "jaw": "unknown",
    "stage": "unknown",
    "modifiers": []
  },
  "field_meta": {
    "extent": {"status": "valid", "error": null},
    "jaw": {"status": "invalid", "error": "patient_jaw_not_allowed"},
    "stage": {"status": "defaulted", "error": null},
    "modifiers": {"status": "defaulted", "error": null}
  }
}
```

Ошибка jaw не стирает extent и не влияет на strict legacy plan/product.

## 11. Session semantics

`TurnFrame.patient_scope` описывает **только current turn observation**. Session snapshot — другой источник и не должен незаметно переписывать current frame.

Правила будущего shadow measurement:

1. Current frame сериализуется отдельно от carried snapshot.
2. Carry может заполнять только отдельный future effective-context view после собственного authority checkpoint; A9 его не проектирует и не подключает.
3. Если carry когда-либо материализуется, каждый перенесённый subfield сохраняет исходный provenance и отдельный `session_carry` marker; confidence не повышается.
4. Explicit current value имеет приоритет над carried value только в effective view, не задним числом в current observation.
5. Explicit смена темы/ситуации очищает carry; current behavior подтверждён `tests/test_patient_situation_session.py:83-92`.
6. Age больше configured limit делает snapshot недоступным (`session.py:523-533`).
7. `clear_focus_context()` очищает и patient situation (`session.py:562-579`).
8. All-unknown current turn сам по себе не вызывает clarification. Clarification — отдельная безопасная policy decision.

## 12. Medical и product firewall

До отдельного authority checkpoint запрещены imports/reads нового nested scope из:

- routing/resolver/decision conversion;
- evidence/source selection;
- price scope/offers/pricebook;
- patient playbook;
- composer/answer/UI;
- marketing/promo;
- booking/contacts/medzone;
- session mutation.

Future AST/source tests должны подтверждать:

1. `PatientScopeFrame` создаётся только contract/raw-builder/adapter/shadow telemetry code.
2. `PlannerAttempt.shadow_frame.patient_scope` не читается product modules.
3. `turn_plan_to_decision_frame()` не использует scope.
4. No scope value appears in service-id mapping, price-group mapping or document-id mapping.
5. No second LLM-call added to `plan_turn_attempt()`.
6. Current `PatientSituationResult` consumers byte/diff unchanged на contract/extraction/wiring checkpoints.

Отдельно: `full_arch != all_on_4`, `upper != zygomatic_implants`, `one_tooth != classic`, `reported_bone_deficit != sinus_lift`.

## 13. Backward-compatible migration

Target меняет тип **shadow** `TurnFrame.patient_scope`, поэтому migration должна быть атомарной для shadow contract, но не для product:

1. `PatientSituationResult.patient_scope: PatientScope` остаётся неизменным на всех A9 shadow checkpoints.
2. Все current routing/playbook/composer/session consumers продолжают читать только legacy result.
3. A9 Contract добавляет nested value/meta models и одновременно обновляет legacy adapter/raw builder/tests; runtime product wiring не меняется.
4. В том же contract commit flat meta-status helpers в `PlannerAttempt` и planner wrapper получают единый recursive traversal для nested patient scope; правила `ok/partial` не ослабляются.
5. Старый ошибочный string-copy adapter удаляется в том же contract commit; временное `patient_scope_v2` запрещено.
6. Existing shadow telemetry schema change явно фиксируется в contract tests; A6/A7 frozen artifacts не resnapshot.
7. A9 extraction использует только bridge mapping из §9.
8. A9 shadow wiring публикует nested frame только в существующий ctx/log/E2E shadow channel.
9. Legacy scalar mappings удаляются только после quality audit и отдельного product migration; до этого два контракта сосуществуют, но nested shadow не влияет на scalar product.

Так backward compatibility относится к пользовательскому поведению и current product contracts. Внутренний shadow JSON меняется осознанно и проверяется как новый schema contract, а не маскируется вторым полем.

## 14. Quality matrix до authority

Frozen spec создаётся до live и оценивает каждую независимую часть, а не требует «полностью угадать ситуацию».

Обязательные группы:

- single-turn: extent, jaw, stage, modifier, all-unknown;
- composite: extent+jaw, jaw+modifier, stage+extent;
- partial/invalid: один invalid при valid соседях;
- negative: informational, other dental topics, urgency-only, named service without patient scope;
- multi-turn: safe carry, stale carry, topic replacement, conflicting current/carried value;
- bridge-specific: все 10 current kinds и documented loss table.

Метрики:

- per-subfield scoreable coverage;
- exact match among scoreable;
- unknown/defaulted/missing/invalid rates;
- confusion matrix по каждому enum;
- composite preservation rate;
- product parity (route/evidence/composer/UI unchanged);
- planner availability/errors отдельно от semantic mismatch.

Нельзя вводить confidence threshold или authority gate по одному live-run. Confidence descriptive до отдельной calibration task.

## 15. Future checkpoints

1. **A9 Design** — этот документ; один docs-файл.
2. **A9 Contract** — `PatientScopeFrame`, nested metadata, exact errors и unit tests; no runtime/live.
3. **A9 Raw extraction** — pure bridge §9 из одного raw planner payload; strict legacy branch unchanged.
4. **A9 Shadow wiring** — existing ctx/log/E2E channel only; AST firewall.
5. **A9 Frozen quality matrix** — expectations из repository semantics до live; single + multi-turn.
6. **A9 One-run live/audit** — один raw artifact, no retry; coverage/correctness/unknown/error separated.
7. **Authority decision** — отдельный checkpoint. Он может решить «ещё не готово»; shadow не обязан стать product authority.
8. **Legacy retirement** — только после принятого authority design; удалить duplicate mappings/second classifier по отдельным slices.

Contract, extraction, wiring, matrix, live и authority нельзя объединять в один diff.

## 16. Rejected shortcuts

Запрещены:

- enum на каждую пользовательскую фразу;
- подстановка ближайшего известного scope вместо unknown;
- inference jaw из extent или protocol из scope;
- признание `urgent` patient scope;
- признание reported bone deficit диагнозом;
- hardcode семи/других eval-кейсов;
- второй постоянный LLM-classifier;
- repair raw перед strict legacy validation;
- session carry внутри pure raw builder;
- временный `patient_scope_v2` side channel;
- подключение nested scope к price/playbook/composer до authority;
- resnapshot A6/A7/A8 artifacts ради зелёного результата.

## 17. Definition of design success

A9 Design успешен, если independent review подтверждает:

1. Current flow, дублирование и product coupling описаны точно.
2. Evidence inventory grounded в repository sources.
3. Выбран один компактный contract, а не смесь вариантов.
4. Unknown разрешён по каждой независимой части.
5. Scope не является диагнозом, urgency axis, service route или price decision.
6. Один invalid subfield не уничтожает остальные.
7. Single-call target и no-second-LLM boundary однозначны.
8. Session current/carry различены.
9. Product firewall и future checkpoints проверяемы.
10. Код, tests, live и frozen artifacts не изменены.

После принятия документа — СТОП. A9 Contract начинается только после нового governance `TASK.md`.
