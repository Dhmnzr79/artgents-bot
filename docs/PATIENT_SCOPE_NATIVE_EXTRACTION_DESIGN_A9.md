# A9 — Native patient-scope extraction design (shadow-only)

**Статус:** design-only, shadow target; implementation не разрешена этим документом.
**Product authority:** forbidden.
**Live/LLM:** не запускались. Первый A9 raw сохраняется без изменений.

## 1. Решение

Единый planner продолжит возвращать один JSON object за один существующий LLM-call. В object добавляется top-level sibling `patient_scope`, а current scalar `patient_situation` остаётся для неизменного legacy product path. Original parsed dict не мутируется: native shadow builder читает его целиком, а strict branch получает точную branch-local view без единственного governed shadow sibling `patient_scope`. Все остальные keys и все legacy values сохраняются, поэтому `TurnPlan(extra="forbid")`, validators и product fail-open продолжают работать как сейчас.

Если `patient_scope` присутствует, его четыре subfields валидируются независимо и scalar bridge ничего в них не backfill'ит. Если sibling отсутствует, принятый deterministic scalar bridge остаётся backward-compatible fallback. Scope публикуется только в существующий shadow channel. Pre-planner `ingress_manual_contact` не получает fake frame: будущий harness классифицирует успешный boundary response без frame как `not_applicable`, отдельно от transport failure.

Это design materialization, а не authority decision. Audit остаётся красным по native-positive quality: exact `0` для extent/jaw/stage/modifiers и composite `0/9` (`docs/evidence/a9/PATIENT_SCOPE_SHADOW_AUDIT_A9.md:149-184`, `:200-205`).

## 2. Current evidence и причина checkpoint

### 2.1 Contract уже composable, extraction ещё scalar-only

`PatientScopeFrame` уже хранит независимые `extent`, `jaw`, `stage`, `modifiers`; allowlists и safe defaults определены в `contracts/turn_frame.py:15-18`, `:48-64`. Metadata также nested per subfield (`contracts/turn_frame.py:87-94`, `:109`, `:127`).

Но raw builder читает только `raw["patient_situation"]` и mapping `_PATIENT_SCOPE_BRIDGE` (`core/turn_frame_from_raw.py:48-61`, `:93-127`). `build_turn_frame_from_raw()` материализует результат этого bridge (`core/turn_frame_from_raw.py:326-365`); sibling `raw["patient_scope"]` не читается.

Frozen D2 уже задаёт будущий raw shape и field isolation:

- invalid jaw сохраняет extent (`evals/v5/demo/patient_scope_shadow_matrix.json:99-117`);
- invalid extent сохраняет jaw+modifier (`:119-137`);
- invalid modifier сохраняет stage (`:139-157`);
- missing stage сохраняет composite neighbors (`:159-177`).

Все четыре target-red в первом run (`docs/evidence/a9/PATIENT_SCOPE_SHADOW_AUDIT_A9.md:117-136`).

### 2.2 One-call dual branch уже существует

Planner prompt сейчас перечисляет только legacy fields и описывает scalar `patient_situation` (`core/turn_planner_llm.py:35-69`). `plan_turn_attempt()` делает один call, парсит один JSON object, передаёт один `obj` сначала shadow builder, затем strict validator (`core/turn_planner_llm.py:520-646`). Output budget сейчас `max_completion_tokens=300` (`:557`).

Strict `TurnPlan` имеет `extra="forbid"`, required `route`, `aspects(min_length=1)` и scalar `patient_situation` (`contracts/turn_plan.py:25-46`). `_validate_plan()` сохраняет current topic sanitization в copy и затем вызывает `TurnPlan.model_validate()` (`core/turn_planner_llm.py:328-374`).

Product wiring читает только `attempt.legacy_plan`; shadow записывается отдельно (`orchestration/resolver_turn.py:54-63`). Это принятый A7 dual-branch firewall, и A9 его не меняет.

A7 design требует immutable one-raw dual branch и unchanged strict validation (`docs/evidence/a_series/FIELD_LEVEL_PLANNER_OUTCOME_A7.md:91-124`, `:229`), а product firewall отделяет `legacy_plan` от telemetry-only `shadow_frame` (`:139-154`). Native seam обязан сохранить эти законы.

Current recorder различает только `ok | partial | not_available | degraded`, со stable reasons `turn_plan_missing` и `turn_frame_build_failed`; ctx contract — `turn_frame_shadow`, `turn_frame_shadow_status`, `turn_frame_shadow_reason` (`core/turn_frame_shadow.py:18-28`, `:37-94`). Metadata-first allowlist переносит эти три keys в turn details/response test slice (`core/metadata_first_observability.py:24-71`, `:101`, `:144-170`). Native design не переименовывает их и не использует `degraded` для model/schema invalidity.

### 2.3 Audit measurement boundary

Первый run доказал:

- D1 scalar bridge `10/10`;
- D2 field isolation `0/4` target-red;
- live current scope `7/30` PASS, но все PASS negative/default;
- live positive exact `0` по каждой оси;
- composite `0/9`;
- product firewall сохранён;
- authority forbidden.

Подробные denominators и claims boundary находятся в `docs/evidence/a9/PATIENT_SCOPE_SHADOW_AUDIT_A9.md:111-184`, `:203-215`, `:300-370`. Native design не переинтерпретирует эти результаты и не переписывает raw.

## 3. Exact raw contract

Future planner JSON остаётся flat object с прежними legacy fields и одним shadow sibling:

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

`patient_scope` — shadow-only observation текущего хода. `patient_situation` — current legacy scalar product input. Их одновременное присутствие не означает merge, reconciliation или две LLM-модели: это два outputs одного semantic call на время strangler migration.

Nested contract неизменен:

```text
extent    = unknown | one_tooth | few_teeth | full_arch
jaw       = unknown | upper | lower | both
stage     = unknown | extraction_context | implant_placed
modifiers = [] | [reported_bone_deficit]
```

Все четыре keys должны присутствовать. `unknown` и `[]` выражают явное незнание модели. `patient_scope=null` не является all-unknown: это invalid container.

Design/code alignment выявил structural state, которого accepted metadata ещё не умеет честно представить: unknown extra key внутри native container. Первый raw этот state не наблюдал. Поэтому **value contract не меняется**, но до raw implementation нужен отдельный contract checkpoint с минимальным container metadata:

```python
class PatientScopeFrameMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    container: FieldMeta
    extent: FieldMeta
    jaw: FieldMeta
    stage: FieldMeta
    modifiers: FieldMeta
```

Новые stable errors только для `container`:

```text
patient_scope_invalid_type
patient_scope_extra_field
```

Это осознанное узкое уточнение A9 metadata, а не новый value, product field или второй error store. Оно требуется, чтобы не смешивать model/schema invalidity с A7 `degraded`, зарезервированным для internal builder/serialization failure (`docs/evidence/a_series/FIELD_LEVEL_PLANNER_OUTCOME_A7.md:214-223`). Первый raw/v1 matrix не resnapshot'ятся; новое metadata expectation сначала freeze'ится в отдельном v2 contract spec.

## 4. Branch isolation без raw repair

### 4.1 Выбранный seam

После `json.loads()` original `obj` не изменяется:

```python
raw = obj  # original parsed dict; never mutated

shadow_frame = build_turn_frame_from_raw(raw, ...)

legacy_raw = {
    key: value
    for key, value in raw.items()
    if key != "patient_scope"
}
legacy_plan = _validate_plan(legacy_raw, ...)
```

Это exact projection, а не repair:

- удаляется только один governed shadow sibling;
- значения legacy keys не нормализуются новым A9 seam;
- missing/invalid legacy keys остаются missing/invalid;
- любой другой unexpected top-level key остаётся в `legacy_raw` и отклоняется `TurnPlan(extra="forbid")`;
- current `_sanitize_topic_fields()` behavior внутри `_validate_plan()` остаётся прежним и не расширяется на scope;
- native nested container не добавляется в `TurnPlan`, его dump или product ctx; existing legacy scalar `patient_scope`/`patient_situation_result` остаётся как сейчас.

Проекция нужна потому, что frozen D2 raw shape уже использует sibling (`evals/v5/demo/patient_scope_shadow_matrix.json:97-177`), а включение sibling прямо в strict `TurnPlan` сделало бы shadow parsing частью product eligibility.

### 4.2 Сохраняемые eligibility invariants

После seam product success/fail-open всё ещё определяется только current legacy contract:

- `route` required и enum-valid;
- `aspects` required, list-valid и non-empty;
- service/follow-up ids проходят current catalog guards;
- topic проходит current taxonomy sanitization;
- brand проходит current PriceBook guards;
- legacy scalar `patient_situation` проходит current enum;
- любой extra, кроме exact `patient_scope`, остаётся fatal;
- native scope missing/invalid не делает valid legacy plan invalid;
- legacy failure не уничтожает independently valid shadow fields.

`plan_turn()` остаётся wrapper, возвращающим только `attempt.legacy_plan` (`core/turn_planner_llm.py:650-652`). `turn_plan_to_decision_frame()`, `publish_turn_plan()` и resolver не получают `patient_scope`.

### 4.3 Почему это не общий extra-ignore

Нельзя строить legacy dict allowlist'ом известных fields: такой allowlist случайно удалил бы любой новый/ошибочный extra и ослабил `extra="forbid"`. Projection обязана исключать по имени только `patient_scope`, оставляя остальные entries нетронутыми.

Future contract tests должны отдельно доказать:

1. payload с exact native `patient_scope` и valid legacy fields даёт valid `legacy_plan`;
2. payload с `patient_scope` и вторым unknown top-level key отклоняет legacy plan;
3. invalid nested scope не меняет legacy plan;
4. invalid legacy aspect сохраняет valid native scope в partial shadow;
5. input dict после обеих веток byte/deep-equal исходному.

## 5. Native-vs-bridge source precedence

Выбрано container-level source ownership:

| Raw state | Shadow source | Правило |
|---|---|---|
| key `patient_scope` absent | scalar bridge | D1 values и четыре existing child metas unchanged; additive `container` meta меняет только v2 shadow serialization |
| key present, object | native parser | все четыре subfields только из object |
| key present, `null`/wrong type | native invalid container semantics | scalar bridge не маскирует failure |
| key present с missing/invalid member | native parser | member остаётся missing/invalid; no backfill |

Причины:

- absent fallback сохраняет уже доказанные D1 values/child statuses `10/10` и rollback старого prompt;
- present native container показывает реальную полноту нового output;
- per-field overlay из scalar скрыл бы missing/invalid и искусственно улучшил availability;
- scalar остаётся product input, но не второй source внутри native scope frame;
- divergence scalar/nested допустима как measurement fact, не разрешается кодом и не вызывает retry.

Bridge provenance остаётся `turn_plan.patient_situation.*` (`core/turn_frame_from_raw.py:36-39`). Native provenance новое:

```text
turn_plan.raw.patient_scope.extent
turn_plan.raw.patient_scope.jaw
turn_plan.raw.patient_scope.stage
turn_plan.raw.patient_scope.modifiers
```

Confidence для native subfields — `0.0`: raw не содержит per-field confidence. Это descriptive placeholder, не threshold и не calibration.

## 6. Exact field-level parser semantics

### 6.1 Known subfields

| Input | Value | Status | Error |
|---|---|---|---|
| allowed scalar / allowed modifiers list | normalized allowed value | `valid` | null |
| explicit scalar `unknown` | `unknown` | `valid` | null |
| explicit `modifiers=[]` | `[]` | `valid` | null |
| member absent | scalar `unknown` / modifiers `[]` | `missing` | null |
| wrong member type | safe default | `invalid` | corresponding `*_invalid_type` |
| scalar outside allowlist | `unknown` | `invalid` | corresponding `*_not_allowed` |
| modifiers has unsupported string | `[]` | `invalid` | `patient_modifier_not_allowed` |

Stable errors остаются current contract allowlist (`contracts/turn_frame.py:37-44`). Invalid одного known subfield не стирает соседей. Любой nested `missing`/`invalid` делает `PlannerAttempt.shadow_status=partial`; `defaulted` сам по себе partial не делает (`contracts/planner_attempt.py:15-31`, `:34-67`).

### 6.2 Container metadata

Container status отделяет structural validity от member validity:

| Raw container | Container meta | Subfields |
|---|---|---|
| sibling absent | `defaulted`, `turn_plan.schema_default` | current bridge values и четыре existing child metas unchanged; новый container meta additive |
| object, only allowed keys | `valid`, `turn_plan.raw.patient_scope` | parse independently |
| `null` / non-object | `invalid`, `patient_scope_invalid_type` | safe values; all four member metas `defaulted` |
| object с unknown extra key | `invalid`, `patient_scope_extra_field` | known members всё равно parse independently |

Container confidence всегда `0.0`. Для любого present container provenance — `turn_plan.raw.patient_scope`, включая invalid type/extra; для absent — `turn_plan.schema_default`. Container `invalid` делает attempt `partial`, но не уничтожает valid TurnFrame axes или valid known scope neighbors. Raw container value и unknown extra name/value не включаются в error/provenance/log.

Добавление обязательного `container` меняет serialized `TurnFrame.field_meta.patient_scope` shape для всех frames, включая D1 bridge. Это явная additive v2 shadow schema change: value frame и четыре прежних child metas сохраняются, но полный `model_dump()` не объявляется byte-identical. V1 artifacts остаются immutable; v2 contract/spec получают новый schema version до implementation.

### 6.3 Modifiers

- input обязан быть list of allowed strings;
- duplicates canonicalize в unique sorted list, как current model validator (`contracts/turn_frame.py:58-64`);
- если хотя бы один item non-string → whole field `invalid`, value `[]`, error `patient_modifiers_invalid_type`;
- если все items strings, но хотя бы один outside allowlist → whole field `invalid`, value `[]`, error `patient_modifier_not_allowed`;
- mixed valid+invalid не фильтруется частично: один `FieldMeta` относится ко всему list, silent deletion исказила бы source.

### 6.4 Unknown nested extra key

`PatientScopeFrame(extra="forbid")` нельзя превращать в silent ignore. Builder валидирует exact key set до создания value model. При extra key container получает `invalid/patient_scope_extra_field`, а четыре known members сохраняют собственные valid/missing/invalid results. Attempt — `partial`, не `degraded`; raw extra name/value не сериализуется. Legacy plan/product path продолжаются независимо.

Так schema drift видим, D2-style neighbor preservation сохраняется, а A7 internal-error taxonomy не расширяется.

## 7. Prompt semantics

Future `_SYSTEM` добавляет один output field и краткие semantic rules. Он не получает frozen case IDs или exhaustive phrase list.

Обязательный смысл:

1. `patient_scope` всегда object с четырьмя keys.
2. Извлекаются только явно сообщённые признаки **текущего сообщения**.
3. Если признак не сообщён — вернуть `unknown` или `[]`, не угадывать.
4. History помогает разрешить referent, но не переносит старое значение в current observation без явного current mention.
5. `patient_situation` продолжает возвращаться отдельно по current legacy enum.
6. Scope не выбирает service, protocol, price unit, document, evidence или diagnosis.
7. Urgency/pain не входят в scope.
8. `reported_bone_deficit` означает reported context, не клиническое подтверждение.
9. Только JSON, no extra fields.

Минимальные semantic examples:

| Current message meaning | Native scope |
|---|---|
| один отсутствующий зуб | `one_tooth / unknown / unknown / []` |
| вся верхняя челюсть и сообщено о нехватке кости | `full_arch / upper / unknown / [reported_bone_deficit]` |
| имплант уже установлен | `unknown / unknown / implant_placed / []` |
| informational question без patient facts | all unknown / empty |
| vague follow-up «а сколько стоит?» | all unknown / empty, даже если session snapshot содержит old extent |

Examples показывают composition/unknown; они не являются phrase classifier. Конкретные All-on-4/All-on-6/service mappings запрещены.

Остаётся один `chat_completions_create()` и один response parse (`core/turn_planner_llm.py:520-577`). Retry, second classifier и `classify_patient_situation_semantic()` как target fallback запрещены. Добавление object увеличит output size; initial implementation не меняет model/temperature/timeout. Решение по `max_completion_tokens=300` принимается только отдельным spec/implementation governance после статического worst-case JSON check, не live-подбором.

## 8. Current-turn и session boundary

Native frame — observation текущего turn:

- scalar bridge fallback читает только current raw scalar;
- native parser не читает question/history/session сам;
- history используется только внутри единого planner call;
- session snapshot не merge'ится в native frame;
- explicit current value не переписывает snapshot на extraction checkpoint;
- all-unknown current scope не запускает clarification;
- carry/effective-context остаются отдельным future authority design.

Это сохраняет исходные A9 session laws (`docs/PATIENT_SCOPE_DESIGN_A9.md:399-412`) и не чинит три legacy boundary FAIL из первого audit.

## 9. Manual-contact `not_applicable`

### 9.1 Observed path

Ingress вызывается до resolver/planner; non-normal route немедленно возвращает service reply (`orchestration/pre_resolver_turn.py:145-176`). Route materializes как `ingress_<route>` (`ingress_gate.py:580-583`) и app сохраняет `meta.service_route` (`app.py:158`, `:588`). Поэтому `ingress_manual_contact` не создаёт `PlannerAttempt` и не обязан иметь `turn_frame_shadow`.

Первый harness при отсутствии frame возвращает `shadow_frame_missing`; generic availability fallback затем относит неизвестный status к `transport_error` (`evals/v5/run_patient_scope_shadow_eval.py:677-727`, `:953-983`). Audit правильно зафиксировал taxonomy gap, а не transport failure (`docs/evidence/a9/PATIENT_SCOPE_SHADOW_AUDIT_A9.md:217-236`).

### 9.2 Выбран harness-owned seam

`turn_frame_shadow_status` описывает результат существующего planner attempt. На manual-contact boundary attempt не было, поэтому runtime не должен фабриковать planner status.

Future harness v2 после успешного endpoint response применяет порядок:

```text
request exception                     -> transport_error
scoreable shadow frame                -> ok/partial + semantic comparison
runtime not_available/degraded        -> exact runtime bucket
meta.service_route=ingress_manual_contact
  and shadow frame absent             -> not_applicable / pre_planner_manual_contact
прочее missing frame                  -> shadow_frame_missing (ERROR)
```

`not_applicable`:

- является harness observation status, не fake `TurnFrame`;
- применяется только к доказанному `ingress_manual_contact` path;
- не вызывает planner;
- не меняет answer/payload/route;
- считается в frozen total/endpoint completeness, но исключается из scoreable scope/exact/positive denominators;
- имеет отдельный availability count;
- не переписывает v1 matrix, harness, raw или summary.

Расширять `not_applicable` на noise/promo/ref/lead и другие short-circuits без отдельного inventory/spec запрещено.

## 10. Product firewall

Data flow после будущей implementation:

```text
one planner JSON object
          │
          ├─ original raw ─► native/bridge TurnFrame builder ─► shadow ctx/log/E2E only
          │
          └─ exact legacy view (minus patient_scope only)
                    └─► current _validate_plan ─► TurnPlan | None
                                                   │
                                                   └─► current product path
```

Запрещены imports/reads `shadow_frame.patient_scope` из route/resolver, evidence, price, playbook, composer/UI, marketing, booking/contacts/medzone и session mutation. Current `PatientSituationResult` consumers остаются прежними.

Future firewall proof должен подтвердить:

- `orchestration/resolver_turn.py` product decision зависит только от `attempt.legacy_plan`;
- `turn_plan_to_decision_frame()` не получает scope;
- native nested sibling отсутствует в `TurnPlan.model_dump()` и product ctx; existing legacy scalar `patient_scope` в `patient_situation_result` остаётся byte/behavior unchanged (`core/patient_situation.py:565-600`, `orchestration/composer_flow.py:73-82`);
- native value не участвует в service/doc/price mapping;
- no second LLM/retry;
- answer text, evidence, money, UI actions/buttons/order и deterministic contacts/booking payload unchanged;
- only demo/dental touched; `cesi`/`nikadent` unchanged.

Privacy: shadow dump содержит только allowlisted normalized values, `0.0` confidence, stable provenance/status/error. Question, answer, history, sid, raw payload, unknown raw values и exception text не сериализуются.

## 11. Рассмотренные альтернативы

### 11.1 Raw transport / ownership

| Вариант | Correctness / field isolation | Strict eligibility / product | Observability / privacy | Latency / tokens | Rollback / scalar-bridge retirement | Вердикт |
|---|---|---|---|---|---|---|
| sibling + exact legacy projection | Native members независимы; invalid legacy не стирает scope | Удаляется только governed sibling; остальные extras и validators strict | Один original raw; normalized allowlisted shadow only | Один call; небольшой output growth | Убрать prompt sibling → automatic absent bridge; после authority scalar/bridge удаляются отдельным slice | **выбран** |
| добавить typed `patient_scope` в `TurnPlan` | Pydantic isolation возможно, но invalid scope может разрушить весь plan | Shadow schema становится product eligibility и попадает в dump/ctx | Product/shadow provenance смешивается; nested raw шире product logs | Один call; такой же token growth | Rollback требует contract/dump migration; bridge retirement сцеплен с product | rejected |
| добавить `patient_scope: Any` в `TurnPlan` | Invalid members не валидируются strict branch | Eligibility формально сохраняется ценой ослабления exact contract | Raw/unknown nested values могут попасть в dumps; privacy boundary хуже | Один call | Rollback прост, но bridge не заменён честным target | rejected |
| envelope `{legacy_plan, patient_scope}` | Хорошая физическая isolation | Inner `TurnPlan` strict, но весь response contract/parse seam меняется | Provenance явный; privacy достижима отдельной валидацией | Один call, больше wrapper tokens/prompt complexity | Rollback переписывает response shape; bridge можно удалить позднее | rejected: новая сущность без необходимости |
| repurpose scalar `patient_situation` | Не представляет composite; ломает D1/product meaning | Current enum/product validation несовместимы | Теряется параллельное comparison measurement | Token neutral | Нет безопасного compatibility/rollback window | rejected |

### 11.2 Source и validation policy

| Вариант | Correctness / field isolation | Strict eligibility / product | Observability / privacy | Latency / tokens | Rollback / scalar-bridge retirement | Вердикт |
|---|---|---|---|---|---|---|
| native present, bridge only when sibling absent | Missing/invalid видимы; D1 fallback и D2 isolation совместимы | Product scalar независим | Native/bridge provenance раздельны; raw invalid values не пишутся | No extra call | Prompt rollback автоматически возвращает bridge; bridge удаляется после native authority/product migration | **выбран** |
| native-only, absent sibling = all defaulted | Честен для нового source, но немедленно теряет D1 compatibility старого prompt/raw | Product scalar работает, shadow backward compatibility ломается | Source простой и privacy-safe, но absence rate смешивает rollout/semantic unknown | No extra call | Prompt rollback не восстанавливает прежний shadow; bridge удалён до доказанной native quality | rejected |
| per-subfield scalar backfill | Маскирует native missing/invalid и создаёт ложный exact | Product не меняется | Availability/quality искусственно зелёные; source смешан | No extra call | Bridge становится постоянной скрытой зависимостью | rejected |
| whole-container Pydantic validation | Один invalid/missing member уничтожает valid composite neighbors и D2 isolation | Legacy branch можно изолировать | Один coarse error проще, но скрывает per-axis quality; raw leak можно предотвратить | No extra call | Легко заменить parser, но bridge retirement опирался бы на неполную telemetry | rejected |
| field-level parser + container schema meta | Known member failures изолированы; structural extra видим отдельно | Shadow-only, legacy независим | Per-axis status честный; normalized values/stable errors only | No extra call; небольшой metadata growth | Rollback к bridge через absent sibling; metadata удаляется после full migration | **выбран** |
| second LLM/classifier | Может заполнить fields, но два semantic source конфликтуют | Legacy eligibility напрямую не меняется | Нельзя честно назначить authority; больше raw/usage surface | Второй call, latency/cost; retry-like behavior | Call легко выключить, но bridge retirement/source ownership не решены | rejected |
| regex/keyword extraction | Неполна для composition/языка; hardcode cases | Legacy path не меняется | Ошибки выглядят deterministic, privacy узкая | No LLM tokens, CPU cheap | Легко удалить, но создаёт новый thematic classifier вместо retirement | rejected |
| nullable container (`null` = unknown) | Теряет per-field availability и explicit unknown semantics | Legacy projection возможна | `null` смешивает absence/unknown/schema error | Чуть меньше tokens | Rollback прост; native quality не измерима достаточно для bridge retirement | rejected |
| mixed modifiers: whole-list invalid | Не публикует неподтверждённый partial list; соседние axes сохраняются | Product не меняется | Один list-level error честно показывает unusable source; raw item не пишется | No cost | Policy обратима отдельным contract decision; bridge не закрепляет modifiers | **выбран** |
| mixed modifiers: отфильтровать invalid items | Valid item сохраняется, но source частично переписывается без item-level meta | Product не меняется | Unsupported item исчезает, quality выглядит лучше; privacy-safe, honesty хуже | No cost | Трудно доказать безопасный retirement по искажённой telemetry | rejected |
| silent ignore nested extra | Known fields сохраняются, но schema drift скрыт | Product не меняется | Extra key исчезает без error; honesty нарушена, хотя raw не логируется | No cost | Drift мешает безопасному retirement | rejected |

### 11.3 Manual-contact taxonomy

| Вариант | Correctness / field isolation | Strict eligibility / product | Observability / privacy | Latency / tokens | Rollback / bridge retirement | Вердикт |
|---|---|---|---|---|---|---|
| harness-derived `not_applicable` по successful `ingress_manual_contact` response | Честно отражает отсутствие attempt/frame | Runtime/product untouched | Отдельно от transport; читает только stable route, без question/session | No call/token/runtime overhead | Versioned harness rollback; к scalar bridge не относится | **выбран** |
| runtime fake frame | Создаёт ложный all-unknown observation | Может затронуть pre-resolver response plumbing | Availability выглядит выше; privacy безопасна, но semantics ложна | No LLM, лишняя serialization | Удаляемо; bridge retirement не решает | rejected |
| runtime `turn_frame_shadow_status=not_applicable` без attempt | Frame не фабрикуется, но planner-attempt taxonomy расширяется чужим owner | Product payload не должен меняться, однако ctx/metadata contract меняется на всех paths | Явно, privacy-safe, но ownership смешан | No LLM, небольшой runtime seam | Versioned rollback возможен; bridge не относится | rejected в A9: harness уже владеет denominator taxonomy |

Rollback выбранного native extraction: удалить prompt sibling. Absent-container rule автоматически возвращает current scalar bridge, product branch не меняется. Retirement обратный и отдельный: после принятой native quality/authority и переноса product ownership измерить отсутствие fallback, затем удалить scalar prompt field, bridge mapping и legacy consumers последовательными governed slices.

## 12. Future checkpoints

1. **A9 Native Extraction Design** — этот документ; docs-only.
2. **A9 Native container metadata contract** — `container: FieldMeta`, два stable errors, recursive partial semantics и contract tests; no prompt/runtime/live.
3. **A9 Native raw contract/prompt spec** — frozen unit fixtures для raw shape, projection, parser states и prompt semantics; no live.
4. **A9 Native extraction implementation** — prompt + exact projection + field parser; unit-only, existing bridge preserved.
5. **A9 Native shadow wiring/firewall proof** — existing ctx/log/E2E only; AST/product parity.
6. **A9 `not_applicable` harness taxonomy** — new harness version; no first-artifact rewrite.
7. **A9 Frozen matrix/harness v2 review** — expectations/version/artifact name frozen до live.
8. **A9 One-run live re-audit** — только после явного разрешения владельца; one attempt, no retry.
9. **Authority decision** — отдельный checkpoint; может снова вернуть `forbidden/not ready`.
10. **Legacy retirement** — только после принятого authority design.

Contract/spec, code, wiring, taxonomy, live и authority не объединяются.

## 13. Definition of design success

Design успешен, если independent review подтверждает:

1. Raw shape совместим с frozen D2 и one-call planner.
2. Exact projection удаляет только governed sibling и не маскирует другие extras.
3. Legacy validators/eligibility/fail-open и product dumps сохраняются.
4. Present native container никогда не backfill'ится scalar bridge.
5. Known subfield invalid/missing сохраняет valid neighbors.
6. Null/wrong container и unknown nested extra имеют fail-visible semantics.
7. Prompt current-turn/unknown-safe и не содержит treatment routing.
8. Manual-contact честно становится harness `not_applicable`, не fake frame/transport failure.
9. Product firewall/session/privacy проверяемы.
10. Первый A9 raw/frozen artifacts не изменены, live не запускался.
11. Authority остаётся forbidden.

После принятия design — СТОП. Spec/code/live начинаются только по новому `TASK.md` и после checker review.
