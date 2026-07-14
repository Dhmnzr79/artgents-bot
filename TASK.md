# TASK — A9 Native Patient-scope Extraction Design (shadow-only)

Один активный `TASK.md` на один checkpoint. Этот checkpoint создаёт только архитектурный design-документ для native field-level extraction `patient_scope` из **того же** planner JSON. Код, tests/spec/harness, prompt, runtime и live/LLM на этом checkpoint запрещены.

Общие правила: `.cursor/rules/00-guardrails.mdc`, `REVIEW_CHECKLIST.md`.

Главный исходный факт A9:

```text
Infrastructure integrity: accepted
Live native positive exact: extent=0, jaw=0, stage=0, modifiers=0
Composite exact: 0/9
Product firewall: preserved
Authority: forbidden
```

Design обязан закрыть архитектурную развилку до любой реализации. Он не должен объявлять качество зелёным, повторять первый A9 sample или передавать scope в product.

---

## 1. Baseline и frozen provenance

- branch: `codex/stage-a`;
- HEAD до governance diff: `10b4739 docs: audit A9 patient scope shadow quality`;
- origin: `origin/codex/stage-a` на том же commit;
- рабочее дерево до governance diff чистое;
- A9 design: `9ee8c34 docs: design A9 composable patient scope`;
- A9 contract: `2a34b6c feat: add A9 patient scope contract`;
- A9 scalar bridge: `0cc9042 feat: extract A9 patient scope shadow fields`;
- A9 wiring proof: `33966e4 test: prove A9 patient scope shadow wiring`;
- A9 frozen matrix: `15d2ae7 test: freeze A9 patient scope quality matrix`;
- A9 harness: `3f11857 test: add A9 patient scope quality harness`;
- A9 audit: `10b4739 docs: audit A9 patient scope shadow quality`.

Frozen artifacts:

```text
A9 raw = eval_patient_scope_a9_last.txt
A9 raw SHA256 = 478CF92060557C2A915EBBEAFAC911829EADC64F490C86C6ABFADD423A3ECE21
A9 raw attempts = 1, no retry
A9 matrix git hash = d459073bbf8767f7ff590ece2958f7aa8cb18b25
topic matrix git hash = dc356c9c738fb80a10cf0035508d7e8c8247979d
preservation git hash = c2072ca74c2da73bf657d793195d2eb6c8ba7bd5
A7 raw SHA256 = EC009EF2157189A40FDDE6B819883D40678D6289F92EEB0CD74FD0AD9A294DDA
```

Первый A9 raw запрещено удалять, переименовывать, нормализовать, переписывать или перезапускать. Любой новый live/LLM требует отдельного frozen spec/harness review и явного разрешения владельца.

## 2. Deliverable и allowlist

После отдельного governance commit создать ровно один новый файл:

```text
docs/PATIENT_SCOPE_NATIVE_EXTRACTION_DESIGN_A9.md
```

Design checkpoint не меняет:

- `TASK.md` после governance commit;
- `docs/PATIENT_SCOPE_DESIGN_A9.md`, `docs/PATIENT_SCOPE_SHADOW_AUDIT_A9.md`, `docs/ARCH_TARGET_DESIGN.md`;
- `contracts/**`, `core/**`, `orchestration/**`, `app.py`, `llm.py`, `session.py`;
- `tests/**`, `evals/**`, frozen matrix/harness/targets;
- `clients/**`, config, pricebook, policies;
- raw artifacts.

Любой второй changed tracked/untracked file на design authoring checkpoint → `❌` и СТОП.

## 3. Вопрос checkpoint

Нужно выбрать точный способ получить native nested `patient_scope`:

```text
один существующий planner request
  → один parseable JSON object
  → strict legacy TurnPlan branch с прежней product eligibility
  → независимый field-level PatientScopeFrame shadow branch
```

Design обязан ответить:

1. Как выглядит exact raw JSON shape после добавления native scope.
2. Как sibling `patient_scope` сосуществует с current scalar `patient_situation`.
3. Как strict `TurnPlan(extra="forbid")` сохраняет прежние validators/fail-open, хотя shadow-only sibling не является полем product contract.
4. Как builder материализует valid соседние subfields при missing/invalid другом subfield.
5. Когда используется уже принятый scalar bridge, а когда native container имеет приоритет.
6. Как hard/manual-contact path получает `not_applicable`, не fake frame и не transport error.
7. Какие отдельные implementation/spec/live checkpoints потребуются после design.

## 4. Read-only code alignment

Design обязан сверить фактические file:line и data flow минимум для:

- `core/turn_planner_llm.py`:
  - `_SYSTEM` и exact current output fields;
  - `max_completion_tokens=300`, one call, JSON object parsing;
  - immutable parsed `obj` → `build_turn_frame_from_raw()` и `_validate_plan()`;
  - current `_sanitize_topic_fields()` copy semantics;
  - `TurnPlan.model_validate()`;
  - `plan_turn_attempt()` status calculation;
  - `plan_turn()` backward-compatible wrapper;
- `contracts/turn_plan.py`:
  - required `route`, `aspects(min_length=1)`;
  - scalar `patient_situation`;
  - `extra="forbid"`;
- `core/turn_frame_from_raw.py`:
  - current scalar bridge and provenance;
  - current absence of native `raw["patient_scope"]` parsing;
  - per-field builder pattern and no raw mutation;
- `contracts/turn_frame.py`:
  - exact A9 nested values, defaults, metadata and stable errors;
- `contracts/planner_attempt.py`:
  - nested invalid/missing → `partial`;
  - `defaulted` не делает attempt partial;
- `orchestration/resolver_turn.py`:
  - product reads only `attempt.legacy_plan`;
  - shadow recorder is telemetry-only;
- `core/turn_frame_shadow.py` и `core/metadata_first_observability.py`:
  - current status/reason and response metadata contract;
- `orchestration/pre_resolver_turn.py`:
  - ingress `manual_contact` short-circuit occurs before planner;
- `evals/v5/demo/patient_scope_shadow_matrix.json`:
  - frozen sibling `patient_scope` fixtures and target-red field isolation;
- `evals/v5/run_patient_scope_shadow_eval.py`:
  - current missing-frame fallback/taxonomy;
- `docs/FIELD_LEVEL_PLANNER_OUTCOME_A7.md`:
  - one raw JSON, dual branch, strict legacy/product firewall;
- `docs/PATIENT_SCOPE_DESIGN_A9.md` и `docs/PATIENT_SCOPE_SHADOW_AUDIT_A9.md`:
  - contract, measured gap, claims boundary.

Claims о current behavior и выбранном seam должны иметь file:line. Design не копирует raw questions/answers/session IDs.

## 5. Неизменяемые target semantics

Native output использует принятый nested contract без расширения clinical semantics:

```json
"patient_scope": {
  "extent": "unknown | one_tooth | few_teeth | full_arch",
  "jaw": "unknown | upper | lower | both",
  "stage": "unknown | extraction_context | implant_placed",
  "modifiers": ["reported_bone_deficit"]
}
```

Законы:

- четыре subfields независимы;
- explicit `unknown` — валидное значение, не ошибка;
- absent, explicit unknown, invalid и defaulted различаются;
- jaw не выводится из extent, protocol не выводится из scope;
- urgency/pain, diagnosis, service choice и price group в scope не входят;
- `reported_bone_deficit` — сообщённый пациентом context, не диагноз;
- `full_arch != all_on_4`;
- `upper != zygomatic_implants`;
- `one_tooth != classic`;
- `reported_bone_deficit != sinus_lift`;
- session carry не смешивается с current-turn observation.

Расширять allowlist values/modifiers в этом design запрещено. Если code evidence требует изменения принятого A9 contract — `❓ эскалация`, не тихая правка.

## 6. Обязательная архитектурная развилка: raw shape и strict legacy isolation

Frozen D2 fixtures уже используют top-level sibling `patient_scope`. Design обязан проверить его совместимость с `TurnPlan(extra="forbid")` и сравнить минимум:

1. **Exact sibling + branch-local legacy projection** — shadow читает original raw; strict branch валидирует только прежние legacy keys, при этом любой другой неожиданный extra key остаётся fatal.
2. **Добавить shadow field в `TurnPlan`** — оценить product-contract coupling, dump/log leakage и влияние invalid nested value на legacy eligibility.
3. **Raw envelope с отдельным legacy object** — оценить изменение prompt/response shape, backward compatibility и число новых сущностей.
4. **Repurpose scalar / second LLM / regex extraction** — объяснить, почему это нарушает accepted contract или single-source target.

Design выбирает один вариант, показывает exact pseudocode/data flow и доказывает:

- parsed raw object не мутируется;
- shadow builder видит original native container;
- значения pre-existing legacy fields не чинятся и не заменяются ради `TurnPlan`;
- required fields, enum validators, `aspects min_length=1`, catalog/topic/brand guards и fail-open сохраняются;
- кроме exact governed shadow sibling никакой extra key не маскируется;
- invalid/missing native scope не уничтожает valid legacy plan;
- invalid legacy field не уничтожает valid native scope shadow;
- `patient_scope` не появляется в `TurnPlan.model_dump()`, decision frame или product ctx;
- выбранный seam не является общим `extra="ignore"` и не ослабляет strict branch.

Если это нельзя доказать без изменения frozen matrix или legacy eligibility — СТОП и `❓ эскалация`.

## 7. Native-vs-bridge precedence

Design обязан выбрать и зафиксировать exact precedence. Минимально допустимая target policy:

- top-level `patient_scope` **absent** → existing scalar `patient_situation` bridge работает byte/behavior unchanged;
- top-level `patient_scope` **present** → native container является единственным source для всех четырёх subfields этого frame;
- native missing/invalid subfield не backfill'ится scalar bridge, иначе ошибка/неполнота будет скрыта;
- scalar `patient_situation` продолжает обслуживать legacy product path независимо;
- divergence scalar vs nested не разрешается в пользу product или shadow и не запускает retry;
- bridge/native provenance не смешиваются.

Design может выбрать другую policy только с доказательством, что она сохраняет D1 compatibility, D2 isolation и не создаёт второго semantic source of truth внутри одного scope frame.

Обязательно определить semantics для:

- container absent;
- container `null`;
- container wrong type;
- unknown extra subfield;
- each subfield absent;
- explicit scalar `unknown`;
- invalid scalar type/value;
- modifiers wrong type, unknown item, duplicate item, mixed valid+invalid items.

Unknown/invalid raw values не попадают в telemetry, error string или provenance.

## 8. Field-level parsing и metadata

Для каждого native subfield design фиксирует:

- exact safe value после valid/missing/invalid;
- `FieldMeta.status`;
- stable `FieldMeta.error`;
- provenance;
- confidence;
- влияние на `PlannerAttempt.shadow_status`.

Initial native provenance должен быть отдельным от scalar bridge, например:

```text
turn_plan.raw.patient_scope.extent
turn_plan.raw.patient_scope.jaw
turn_plan.raw.patient_scope.stage
turn_plan.raw.patient_scope.modifiers
```

Confidence остаётся descriptive `0.0`: current raw не несёт per-subfield confidence. Нельзя вводить threshold или выдавать deterministic validation за model confidence.

Frozen D2 semantics обязательны:

1. invalid jaw сохраняет valid extent;
2. invalid extent сохраняет valid jaw+modifier;
3. invalid modifier сохраняет valid stage;
4. missing stage сохраняет valid composite neighbors и делает attempt `partial`.

Design обязан отдельно решить structural container/extra-key semantics. Запрещено молча игнорировать unknown nested keys. Если для честной модели нужен новый stable container error/status, это должно быть явно обосновано как contract follow-up, а не спрятано в implementation.

## 9. Prompt contract — design, не prompt implementation

Design задаёт будущий prompt contract достаточно точно для review:

- `patient_scope` возвращается на каждом planner response как object, а не как `null`;
- all-unknown object допустим и предпочтительнее guessing;
- извлекаются только явно сообщённые current-turn признаки;
- history может помогать понять referent текущего вопроса, но native current scope не копирует session carry и не материализует старое значение без явного current-turn mention;
- scalar `patient_situation` пока сохраняется для legacy product compatibility;
- nested и scalar выводятся одним LLM-call, retry запрещён;
- никаких case-ID, frozen question strings, phrase catalog или protocol mapping в prompt;
- scope не выбирает treatment/service/price/evidence;
- output-token budget/latency impact оценён; изменение `max_completion_tokens` не разрешается этим docs checkpoint и требует доказательства на implementation governance.

Design должен привести несколько семантических examples, покрывающих composite, all-unknown, stage и reported context, но не превращать examples в exhaustive classifier.

## 10. Hard/manual-contact `not_applicable`

Audit доказал два `shadow_frame_missing` после pre-planner `manual_contact`; это не semantic mismatch и не доказанный transport failure.

Design обязан:

- показать exact short-circuit path до `plan_turn_attempt()`;
- выбрать runtime-status или harness-derived semantics и объяснить ownership;
- определить stable `not_applicable` status/reason только для доказанного pre-planner boundary;
- не создавать fake/default `TurnFrame`;
- не вызывать planner ради telemetry;
- не менять manual-contact answer/payload/route;
- не смешивать `not_applicable`, `not_available`, `degraded` и transport error;
- определить denominator: frozen total сохраняется, `not_applicable` не входит в scoreable/current-scope exact;
- не переписывать первый raw или его frozen summary задним числом.

Если taxonomy требует runtime/harness change, это отдельный checkpoint после design.

## 11. Product firewall и privacy

До отдельного authority checkpoint запрещены imports/reads native/nested scope из:

- `turn_plan_to_decision_frame()` и resolver/routing;
- evidence/source selection;
- price scope/offers/pricebook;
- patient playbook;
- composer/answer/UI;
- marketing/promo;
- booking/contacts/medzone;
- session mutation/carry.

Future acceptance должен доказать:

1. product branch читает только `legacy_plan`;
2. `shadow_frame.patient_scope` публикуется только в existing ctx/log/E2E shadow channel;
3. no second classifier/LLM/retry;
4. current `PatientSituationResult` consumers unchanged;
5. no scope → service/document/price mapping;
6. no question/answer/history/sid/raw payload/unknown values/exception text in scope telemetry;
7. answer, route, evidence, money, actions/buttons and deterministic payloads unchanged.

## 12. Alternatives и trade-offs

Кроме raw-shape вариантов design сравнивает:

- native-only vs absent-container scalar bridge fallback;
- whole-container validation vs field-level parsing;
- prompt always-object vs nullable container;
- runtime `not_applicable` vs harness-derived classification;
- mixed modifier handling;
- handling of unknown nested extra keys.

Для каждого: correctness, strict legacy eligibility, field isolation, observability honesty, privacy, latency/token cost, rollback и путь удаления scalar bridge.

Нельзя выбрать смесь без единого data flow и source precedence.

## 13. Future checkpoints

Design обязан разбить дальнейшую работу минимум так:

1. **A9 Native Extraction Design** — этот doc-only checkpoint.
2. **A9 Native raw contract/prompt spec** — protected fixtures/expected statuses до code; без live.
3. **A9 Native extraction implementation** — one JSON, field-level builder, strict legacy isolation; unit-only.
4. **A9 Native shadow wiring/firewall proof** — existing telemetry only; product parity/AST.
5. **A9 `not_applicable` taxonomy** — runtime или harness seam согласно design; без fake frame.
6. **A9 Frozen quality matrix/harness v2 review** — новый version/artifact name; первый matrix/raw неизменны.
7. **A9 One-run live re-audit** — только после явного разрешения владельца; one attempt/no retry.
8. **Authority decision** — отдельный checkpoint; может снова решить «not ready».
9. **Legacy retirement** — только после принятого authority design.

Spec, implementation, wiring, taxonomy, live и authority нельзя объединять в один diff.

## 14. Protected artifacts

На design checkpoint protected и read-only:

- `evals/v5/demo/patient_scope_shadow_matrix.json`, включая questions, raw payloads, expected scope/status/error, order и rationales;
- `evals/v5/run_patient_scope_shadow_eval.py`;
- `tests/test_patient_scope_shadow_eval_contract.py`;
- `eval_patient_scope_a9_last.txt`;
- topic/preservation matrices и A7 raw;
- A9 contract/design/audit documents.

Design может выявить future spec gap, но не меняет protected expectation. Спор с frozen target → `❓ эскалация`.

## 15. Запрещённые shortcuts и claims

Запрещены:

- второй patient-situation classifier/LLM-call;
- retry, majority vote или hidden repair;
- `extra="ignore"` для legacy plan;
- добавление nested field в product contract без анализа eligibility/leakage;
- bridge backfill поверх present invalid/missing native field;
- regex/keyword extraction или hardcode A9 cases;
- inference protocol/service/diagnosis/urgency;
- merge session carry в current frame;
- fake all-unknown frame на manual-contact boundary;
- rewrite/resnapshot первого raw;
- claims `quality green`, `ready`, `calibrated`, `product fixed` или `LLM не понял`;
- authority, route/evidence/composer/UI consumption.

## 16. Read-only проверки design checkpoint

Live/LLM/pytest не запускать: diff docs-only.

```powershell
git status --short
git diff --check
git diff --name-only
git diff -- contracts core orchestration tests evals clients
Get-FileHash -Algorithm SHA256 eval_patient_scope_a9_last.txt
git hash-object evals/v5/demo/patient_scope_shadow_matrix.json
git hash-object evals/v5/demo/topic_shadow_matrix.json
git hash-object evals/v5/demo/preservation.json
Get-FileHash -Algorithm SHA256 eval_topic_shadow_a7_last.txt
```

Checker обязан независимо сверить code claims/file:line, raw-shape feasibility, strict legacy isolation, D1/D2 compatibility, `not_applicable` semantics и запрещённые claims.

## 17. Checkpoints

### Checkpoint 1 — governance review

Checker проверяет этот TASK до design authoring. После `✅` — отдельный commit/push только `TASK.md`.

### Checkpoint 2 — design authoring

Создать только `docs/PATIENT_SCOPE_NATIVE_EXTRACTION_DESIGN_A9.md`, выполнить read-only проверки, без commit, СТОП.

### Checkpoint 3 — independent design review

Checker независимо проверяет design против code/audit/TASK. Verdict `✅/❓/❌`.

### Checkpoint 4 — design commit

Только после `✅`: commit/push одного design-doc в `codex/stage-a`.

## 18. Definition of Done

1. Governance TASK принят и committed отдельно.
2. Design diff = один allowlist document.
3. Выбран один exact raw shape и source precedence.
4. Strict legacy eligibility/fail-open сохранены без общего ослабления extra validation.
5. Native per-field parsing покрывает present/absent/null/wrong/extra/invalid cases.
6. D1 scalar bridge compatibility и D2 field isolation одновременно сохранены.
7. Prompt остаётся one-call/current-turn/unknown-safe, без phrase catalog.
8. Manual-contact missing frame получает честную future `not_applicable` semantics.
9. Product firewall, UI/money/session parity и privacy определены.
10. Первый A9 raw и frozen hashes неизменны; live не запускался.
11. Authority явно forbidden.
12. Independent checker дал `✅` до design commit.

После design commit — СТОП. Native extraction code/spec/live/authority не начинать без нового `TASK.md` и checker review.
