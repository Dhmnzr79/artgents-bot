# TASK — A9 Contract: composable patient scope models

Один активный `TASK.md` на один checkpoint. Этот checkpoint реализует **только contract/schema slice** принятого A9 Design. Mapping из raw `patient_situation`, product wiring, live и authority запрещены.

Общие правила: `.cursor/rules/00-guardrails.mdc`, `REVIEW_CHECKLIST.md`.

Архитектурные источники:

- `docs/ARCH_TARGET_DESIGN.md` — target TurnFrame и boundaries;
- `docs/FIELD_LEVEL_PLANNER_OUTCOME_A7.md` — single-call dual branch;
- `docs/PATIENT_SCOPE_DESIGN_A9.md` — принятый A9 target contract, bridge и migration.

---

## 1. Точка старта

- Ветка: `codex/stage-a`.
- HEAD: `9ee8c34 docs: design A9 composable patient scope`.
- A9 governance: `9fcbb7f`.
- A8 implementation: `38d29f3`.
- A7 raw SHA256: `EC009EF2157189A40FDDE6B819883D40678D6289F92EEB0CD74FD0AD9A294DDA`.
- Topic matrix hash: `dc356c9c738fb80a10cf0035508d7e8c8247979d`.
- Preservation hash: `c2072ca74c2da73bf657d793195d2eb6c8ba7bd5`.
- До implementation diff рабочее дерево чистое.

## 2. Проблема checkpoint

Current `TurnFrame.patient_scope` — `str | None`, а `TurnFrameMeta.patient_scope` — один `FieldMeta`.

Legacy adapter копирует `TurnPlan.patient_situation` прямо в scope:

```text
one_tooth_missing → patient_scope="one_tooth_missing"
```

Это semantic mismatch: `PatientSituationKind` и legacy `PatientScope` — разные словари, а target A9 вообще является nested/composable contract.

Одновременно `PlannerAttempt` и planner wrapper обходят metadata плоско и ожидают `.status` у каждой top-level meta-оси. После nested patient scope такой обход должен рекурсивно проверять четыре subfields.

## 3. Цель

Добавить contract из A9 Design §8:

```text
PatientScopeFrame
  extent
  jaw
  stage
  modifiers

PatientScopeFrameMeta
  extent: FieldMeta
  jaw: FieldMeta
  stage: FieldMeta
  modifiers: FieldMeta
```

И безопасно перевести existing shadow constructors на all-unknown/defaulted nested scope.

Главный инвариант:

> A9 Contract меняет только внутреннюю shadow schema. Он не извлекает scope из raw kind и не влияет на strict `TurnPlan`, resolver, price, playbook, composer, UI или session.

## 4. Что checkpoint НЕ делает

1. Не реализует bridge из `docs/PATIENT_SCOPE_DESIGN_A9.md` §9.
2. Не читает raw `patient_situation` для заполнения nested values.
3. Не меняет `_SYSTEM` и не просит LLM возвращать nested scope.
4. Не меняет `TurnPlan` / `PatientSituationKind` / `PatientSituationResult`.
5. Не меняет legacy detector, regex/cues, отдельный patient-situation LLM или session carry.
6. Не подключает scope к routing/evidence/price/playbook/composer/UI/marketing/booking.
7. Не добавляет `patient_scope_v2`, side channel или второй error store.
8. Не запускает второй LLM-call, retry или classifier.
9. Не меняет strict raw validation и не repair-ит raw.
10. Не передаёт authority.
11. Не создаёт frozen matrix и не запускает live/LLM/eval.
12. Не чинит preservation target-red 02/03/05.

## 5. Target value contract

Добавить в `contracts/turn_frame.py`:

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
```

Изменить:

```python
TurnFrame.patient_scope: PatientScopeFrame
TurnFrameMeta.patient_scope: PatientScopeFrameMeta
```

`TurnFrame.patient_scope` получает `default_factory=PatientScopeFrame`, чтобы value-side all-unknown был безопасным default. `TurnFrameMeta.patient_scope` остаётся required: metadata нельзя молча придумать внутри TurnFrame.

### 5.1 Modifiers invariant

`modifiers` после model validation:

- не содержит дублей;
- сериализуется в canonical sorted order;
- принимает только `PatientScopeModifier` allowlist;
- unknown modifier rejected Pydantic-валидацией.

Допустима pure normalization `sorted(set(value))` внутри `PatientScopeFrame`; raw extraction later обязана отдельно отметить malformed raw metadata, поэтому contract normalization не является raw repair.

### 5.2 Независимость

Не добавлять cross-field inference/validators:

- `full_arch` не задаёт jaw;
- `upper` не задаёт extent;
- stage не задаёт extent/service;
- modifier не задаёт diagnosis/service;
- all-unknown frame валиден.

## 6. Exact FieldErrorReason extension

Добавить **ровно восемь** literals, не удаляя существующие:

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

На contract checkpoint эти errors могут ещё не создаваться production builder: они замораживают schema для следующего raw-extraction checkpoint. Нельзя добавлять generic `patient_scope_invalid`, raw values или exception text.

## 7. Metadata и safe defaults

### 7.1 Default scope value

Оба existing constructors:

- `core/turn_frame_adapter.py::build_turn_frame_from_legacy`;
- `core/turn_frame_from_raw.py::build_turn_frame_from_raw`

возвращают:

```json
{
  "extent": "unknown",
  "jaw": "unknown",
  "stage": "unknown",
  "modifiers": []
}
```

### 7.2 Default nested metadata

Для всех четырёх subfields:

```text
confidence = 0.0
provenance = turn_plan.schema_default
status = defaulted
error = null
```

Это contract placeholder, не extraction.

`core/turn_frame_adapter.py` больше не читает/копирует `turn_plan.patient_situation`. Даже при known kind nested scope остаётся all-unknown/defaulted до A9 Raw extraction.

`core/turn_frame_from_raw.py` также игнорирует absent/null/known/malformed `patient_situation`; raw object не мутируется. `emotion` и `specificity` сохраняют current `a7.not_migrated`. Только patient scope переходит с `a7.not_migrated` на nested schema defaults.

Нельзя использовать provenance `a9.not_extracted`: A9 Design зафиксировал initial default `turn_plan.schema_default`.

## 8. Recursive issue traversal

Создать один shared public helper в `contracts/planner_attempt.py`:

```python
turn_frame_has_invalid_or_missing(frame: TurnFrame) -> bool
```

Он:

- для обычных top-level axes проверяет current `FieldMeta.status`;
- для `patient_scope` рекурсивно обходит ровно `PatientScopeFrameMeta.model_fields`;
- возвращает `True` при любом `invalid` или `missing`;
- не считает `valid`/`defaulted` проблемой;
- не создаёт container-level status/error;
- не зависит от raw/question/history/session.

`PlannerAttempt` использует этот helper для existing `ok/partial` invariants.

`core/turn_planner_llm.py` удаляет локальный duplicate `_frame_has_invalid_or_missing` и импортирует shared helper. Другой production diff в planner запрещён.

Семантика сохраняется:

- nested invalid/missing + valid legacy plan → `partial`;
- nested all-defaulted + valid legacy plan → может быть `ok`;
- legacy plan `None` + frame → `partial`;
- degraded/not_available invariants без изменений.

## 9. Exports

`contracts/__init__.py` экспортирует:

- `PatientExtent`;
- `PatientJaw`;
- `PatientCareStage`;
- `PatientScopeModifier`;
- `PatientScopeFrame`;
- `PatientScopeFrameMeta`;
- `turn_frame_has_invalid_or_missing`.

Старые exports не удалять.

## 10. Разрешённые production-файлы

Ровно:

1. `contracts/turn_frame.py`
2. `contracts/planner_attempt.py`
3. `contracts/__init__.py`
4. `core/turn_frame_adapter.py`
5. `core/turn_frame_from_raw.py`
6. `core/turn_planner_llm.py`

Любой другой production-файл → СТОП.

Допустимый diff `core/turn_planner_llm.py` — import shared helper, удаление local duplicate и замена call site. `_SYSTEM`, `plan_turn_attempt()` call count, raw/strict branches, `_validate_plan`, enrichment, decision conversion и logging не менять.

## 11. Разрешённые test-файлы

Ровно:

1. `tests/test_turn_frame_contract.py`
2. `tests/test_planner_attempt_contract.py`
3. `tests/test_turn_frame_from_raw.py`
4. `tests/test_turn_frame_shadow.py`
5. `tests/test_turn_planner_llm.py`

Новый test-файл не создавать. Existing asserts не ослаблять: flat helpers в tests заменить recursive helper/assertions, а не удалять проверки ошибок/status.

## 12. Обязательные tests

Checker начинает с полного diff тестов.

### 12.1 Value/meta contract

1. Default `PatientScopeFrame()` = exact all-unknown/empty dump.
2. Каждый allowed extent/jaw/stage/modifier принимается.
3. Unknown enum values и extra fields rejected.
4. Modifiers deduplicated и canonical sorted.
5. `PatientScopeFrameMeta` требует ровно четыре `FieldMeta`, extra forbidden.
6. `TurnFrame.patient_scope` принимает только nested contract; legacy scalar string rejected.
7. TurnFrame dump содержит exact nested value/meta shape.
8. Existing `FieldMeta` status/error invariants не ослаблены.
9. Exact `FieldErrorReason` set = old set + ровно 8 A9 errors.

### 12.2 Recursive PlannerAttempt contract

10. Shared helper returns false для nested all-valid.
11. Shared helper returns false для nested all-defaulted.
12. Каждый nested subfield `invalid` по очереди → true.
13. Каждый nested subfield `missing` по очереди → true.
14. `ok` rejects nested invalid/missing.
15. `partial` accepts nested invalid/missing with valid legacy plan.
16. `partial` rejects fully valid/defaulted frame with valid legacy plan.
17. Top-level invalid/missing semantics остаются прежними.
18. Source/AST test доказывает один shared helper и отсутствие local duplicate в planner.

### 12.3 Constructors / no extraction

19. Legacy adapter с `patient_situation=None`, `unknown` и known kind даёт одинаковый all-unknown/defaulted nested scope.
20. Source test: adapter не читает `turn_plan.patient_situation` и не содержит старый string-copy.
21. Raw builder с absent/null/known/malformed `patient_situation` даёт одинаковый all-unknown/defaulted nested scope.
22. Raw input не мутируется.
23. Unknown raw value/question/answer/history/exception не попадает в dump.
24. `emotion`/`specificity` остаются `a7.not_migrated`; patient scope — `turn_plan.schema_default`.
25. Shadow snapshot/E2E metadata сохраняет nested schema без product consumption.
26. Valid planner payload с known scalar `patient_situation` остаётся `ok`, но nested scope defaulted: extraction не началась.

### 12.4 Firewall / honesty

27. `TurnPlan`, `PatientSituationResult`, routing/playbook/composer/session tests не изменены.
28. Source/AST firewall не допускает `PatientScopeFrame` consumers вне contract/adapters/raw builder/shadow telemetry/tests.
29. Нет skip/xfail/assert True/conditional PASS/resnapshot.
30. Негативные tests проверяют exact exception/status/error, а не только отсутствие exception.

## 13. Product firewall

После implementation:

```text
one planner raw JSON
  ├─ nested patient scope = all unknown/defaulted (contract only)
  └─ strict TurnPlan.product branch = unchanged
```

Запрещено читать nested values в:

- `orchestration/**` product decisions;
- resolver/routing/evidence;
- price scope/offers/pricebook;
- patient playbook;
- composer/answer/UI;
- marketing/booking/contacts/medzone;
- session persistence/carry.

`core/turn_frame_shadow.py` может сериализовать весь TurnFrame как и раньше; менять его не требуется и он не входит в allowlist.

## 14. Protected files / artifacts

Не менять:

- `TASK.md` после governance commit;
- `docs/PATIENT_SCOPE_DESIGN_A9.md`;
- `docs/ARCH_TARGET_DESIGN.md`;
- `contracts/turn_plan.py`;
- `contracts/patient_situation.py`;
- `core/patient_situation*.py`;
- routing/playbook/composer/session/product tests;
- eval specs/harnesses/client content/pricebook;
- A6/A7/A8 raw artifacts.

Frozen integrity:

```text
topic matrix = dc356c9c738fb80a10cf0035508d7e8c8247979d
preservation = c2072ca74c2da73bf657d793195d2eb6c8ba7bd5
A7 raw SHA256 = EC009EF2157189A40FDDE6B819883D40678D6289F92EEB0CD74FD0AD9A294DDA
```

## 15. Обязательные команды implementation checkpoint

```powershell
.venv\codex312\Scripts\python.exe -m pytest -q `
  --basetemp=.pytest_cache/a9_contract_core `
  tests/test_turn_frame_contract.py `
  tests/test_planner_attempt_contract.py `
  tests/test_turn_frame_from_raw.py `
  tests/test_turn_frame_shadow.py `
  tests/test_turn_planner_llm.py

.venv\codex312\Scripts\python.exe -m pytest -q `
  --basetemp=.pytest_cache/a9_contract_wiring `
  tests/test_metadata_first_observability.py `
  tests/test_turn_planner_wiring.py `
  tests/test_turn_plan_protocol_guard.py

.venv\codex312\Scripts\python.exe -m pytest -q `
  --basetemp=.pytest_cache/a9_contract_product `
  tests/test_patient_situation.py `
  tests/test_patient_situation_session.py `
  tests/test_patient_situation_routing.py `
  tests/test_patient_playbook.py `
  tests/test_composer_flow.py `
  tests/test_price_scope_router.py

.venv\codex312\Scripts\python.exe -m pytest -q `
  --basetemp=.pytest_cache/a9_contract_regression `
  tests/test_contacts_routing.py `
  tests/test_pricebook_golden.py `
  tests/test_price_layer_parity.py `
  tests/test_preservation_eval_contract.py `
  tests/test_topic_shadow_attempt_eval_contract.py `
  tests/test_topic_shadow_eval_contract.py

.venv\codex312\Scripts\python.exe -m py_compile `
  contracts/turn_frame.py `
  contracts/planner_attempt.py `
  contracts/__init__.py `
  core/turn_frame_adapter.py `
  core/turn_frame_from_raw.py `
  core/turn_planner_llm.py

git diff --check
git status --short
git diff -- evals/v5/demo/preservation.json evals/v5/demo/topic_shadow_matrix.json
git hash-object evals/v5/demo/preservation.json
git hash-object evals/v5/demo/topic_shadow_matrix.json
Get-FileHash -Algorithm SHA256 eval_topic_shadow_a7_last.txt
```

Все failed/skipped/xfail/not run, warnings и logging errors перечислить. Environment permission error не считать test pass; повтор разрешён только с workspace `--basetemp`, без изменения tests.

### 15.1. Узкое baseline-исключение для product suite

Решением владельца от 2026-07-13 зафиксировано: до начала A9 Contract в protected `patient_playbook` уже существуют ровно два воспроизводимых падения, не вызванных A9 diff:

1. `tests/test_patient_playbook.py::test_extraction_then_implant_prefers_one_stage_then_classic` — current composable rules выбирают `one_tooth_restore`, тогда как старый assert ожидает `extraction_then_implant_restore`; конфликт существует с `90d4cc1` (`problem+extent` получает большую specificity, чем `kind` alone).
2. `tests/test_patient_playbook.py::test_no_playbook_returns_none` — тест из `77eb0e6` подменяет только `load_patient_playbook`, но current runtime с `90d4cc1` сначала читает `load_patient_playbook_rules`, поэтому возвращает `full_arch_restore`.

Это **не** общее разрешение на красные тесты и не изменение ожидаемого product behavior. Для A9 Contract product gate принимается только в одном из двух состояний:

- `127 passed, 0 failed, 0 skipped`; или
- `125 passed, 2 failed, 0 skipped`, где failed — ровно два test node id выше и причины совпадают с зафиксированным baseline.

Любой другой fail, третий fail, skip/xfail, изменение assertion, изменение `core/patient_playbook.py`, `tests/test_patient_playbook.py`, `clients/demo/patient_playbook.yaml` или иных protected product-файлов → СТОП и `❌`/`❓`.

В рамках A9 запрещено чинить, удалять, ослаблять или подменять эти два теста. Их исправление требует отдельного TASK и отдельного commit. Checker обязан перечислить исключение явно, а не назвать весь product suite зелёным.

## 16. Live / LLM

На этом checkpoint запрещены:

- live eval;
- прямой real-LLM вызов `plan_turn_attempt()`;
- новый raw artifact;
- retry/resnapshot A7/A8;
- изменение `.env`/flags.

## 17. Checker review

Checker обязан:

1. Начать с diff пяти allowlist test-файлов.
2. Проверить полный changed-files allowlist: 6 production + до 5 tests.
3. Сверить exact nested contract и 8 errors с A9 Design.
4. Проверить recursive traversal и отсутствие ослабления `PlannerAttempt` invariants.
5. Доказать, что scalar bridge **не** реализован.
6. Доказать, что adapter больше не копирует Kind-string.
7. Проверить raw immutability/privacy и safe defaults.
8. Source/AST review подтвердить product firewall.
9. Самостоятельно запустить §15.
10. Проверить product result строго по §15.1 и доказать отсутствие diff в protected playbook/product-файлах.
11. Проверить protected hashes/raw и отсутствие live artifacts.
12. Дать `✅/❌/❓` по двум слоям `REVIEW_CHECKLIST.md`.

## 18. Стоп-условия

СТОП и эскалация, если:

- нужен файл вне allowlist;
- nested schema требует product consumer change;
- требуется менять `TurnPlan`/`PatientSituationResult`;
- хочется реализовать kind bridge сейчас;
- хочется читать question/history/session в builder;
- требуется prompt/LLM change;
- recursive traversal нельзя сделать без ослабления `ok/partial`;
- нужна временная `patient_scope_v2` ось;
- для зелёного нужен skip/xfail/resnapshot/ослабление assert;
- live нужен для решения contract-вопроса.

## 19. Definition of Done

A9 Contract завершён, когда:

1. Изменены только 6 production и до 5 test allowlist-файлов.
2. Nested value/meta models точно соответствуют A9 Design.
3. Modifiers canonical, extras/unknown values rejected.
4. Exact 8 errors добавлены без удаления старых.
5. Shared recursive helper сохраняет `PlannerAttempt` semantics.
6. Оба shadow constructors дают all-unknown/defaulted scope и не извлекают scalar kind.
7. Старый Kind-string copy удалён.
8. Product contracts/behavior untouched; regression tests зелёные; product suite либо зелёный, либо совпадает только с exact baseline-исключением §15.1.
9. Все §15 tests зелёные без skip/xfail, кроме ровно двух pre-existing failures, разрешённых только по exact условиям §15.1.
10. Frozen hashes/raw неизменны.
11. Independent Cursor checker дал `✅`.
12. Создан отдельный implementation commit и push только в `codex/stage-a`.

После этого — СТОП. A9 Raw extraction, shadow live, matrix и authority не начинать без нового `TASK.md`.
