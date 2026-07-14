# TASK — A9 Native Container Metadata Contract

Один активный `TASK.md` на один checkpoint. Цель — добавить в shadow-контракт отдельную метаданную самого контейнера `patient_scope`, чтобы будущая native extraction могла отличать отсутствие контейнера от неверного типа и неизвестного вложенного ключа.

Checkpoint contract/unit-only. Он **не** добавляет чтение native `patient_scope` из raw, не меняет planner prompt, product routing, ответы, цены, UI или authority. Live/LLM запрещены.

Общие правила: `.cursor/rules/00-guardrails.mdc`, `REVIEW_CHECKLIST.md`.

---

## 1. Baseline

- branch `codex/stage-a`;
- HEAD `27114a8 docs: add A-series strangler roadmap`;
- `origin/codex/stage-a` на том же commit;
- рабочее дерево до governance diff чистое;
- approved design: `docs/PATIENT_SCOPE_NATIVE_EXTRACTION_DESIGN_A9.md` (`16ced47`);
- первый A9 raw immutable и не перезапускается без отдельного разрешения;
- product firewall сохранён, patient-scope authority запрещена.

Фактическая проблема:

- `PatientScopeFrameMeta` сейчас описывает только четыре дочерних поля;
- контракт пока не может отдельно показать, что весь будущий native-контейнер имел неверный тип или неизвестный extra key;
- recursive `PlannerAttempt` уже обходит поля metadata-моделей динамически, но новый контейнерный статус должен быть доказан тестами;
- все действующие producer-конструкторы должны одновременно получить безопасную defaulted metadata, иначе обязательное поле сломает построение shadow frame.

## 2. Frozen design semantics

Реализовать ровно решение из approved design:

1. `PatientScopeFrameMeta` получает обязательное поле `container: FieldMeta`; `extra="forbid"` сохраняется.
2. `FieldErrorReason` получает только:
   - `patient_scope_invalid_type`;
   - `patient_scope_extra_field`.
3. На этом checkpoint native sibling ещё не читается. Поэтому все существующие producers задают container metadata как:
   - `confidence=0.0`;
   - `provenance="turn_plan.schema_default"`;
   - `status="defaulted"`;
   - `error=None`.
4. Existing `patient_scope` values и четыре child metadata (`extent`, `jaw`, `stage`, `modifiers`) не меняются.
5. Recursive invalid/missing semantics автоматически распространяются на `container`:
   - `defaulted` не делает attempt partial;
   - `invalid` или `missing` запрещает `shadow_status="ok"` и допускает `partial` по существующему контракту.
6. Полный `field_meta.patient_scope.model_dump()` получает новый additive key `container`. Byte-identical v1 serialization не обещается; frozen v1 artifacts не переписываются.

## 3. Deliverables и allowlist

После отдельного governance commit разрешено менять только:

### Contract и обязательные shadow constructors

1. `contracts/turn_frame.py`
2. `core/turn_frame_adapter.py`
3. `core/turn_frame_from_raw.py`

В `core/*` разрешены только атомарные добавления defaulted `container` в существующие конструкторы `PatientScopeFrameMeta`. Новое raw parsing/wiring запрещено.

### Tests

4. `tests/test_turn_frame_contract.py`
5. `tests/test_planner_attempt_contract.py`
6. `tests/test_turn_frame_from_raw.py`
7. `tests/test_turn_planner_llm.py`
8. `tests/test_turn_frame_shadow.py`
9. `tests/test_metadata_first_observability.py`

Test allowlist разрешает только additive expectations/coverage нового container metadata и доказательство неизменности существующих scope values/child metas/firewall. Нельзя ослаблять старые assertions.

### Roadmap после checker ✅

10. `docs/STRANGLER_ROADMAP.md` — только в completion diff после code-review `✅`:
    - отметить `[x] Native container metadata contract`;
    - обновить последний завершённый и следующий checkpoint;
    - сохранить A9 parent `[ ]`, shadow-only и authority forbidden.

`TASK.md` после governance commit не менять. Любой другой tracked/untracked file → `❌` и СТОП.

## 4. Explicit non-goals

Запрещено:

- изменять `_SYSTEM`, planner output schema или prompt;
- читать `raw["patient_scope"]` / `raw.get("patient_scope")`;
- реализовывать native field parser, projection или fallback selection;
- менять `TurnPlan`, legacy validation, eligibility, retry/fail-open;
- менять resolver/composer/product routing, response payload, prices, UI;
- давать `patient_scope` право влиять на product answer;
- добавлять session/history/question detectors или второй LLM-call;
- менять eval matrix/harness/raw/audit/design docs;
- запускать live/LLM или полный pytest без новой причины и отдельного согласования;
- закрывать A9 parent, native extraction или authority checkbox.

## 5. Product firewall

Для маркетинга и логики ответов результат этого checkpoint такой:

- бот получает более точный внутренний «индикатор исправности» будущего блока patient scope;
- текущий механизм ответа пациенту не переключается и не читает этот индикатор;
- текст ответа, факты, цены, рекомендации, CTA и UI остаются на legacy path;
- новый metadata key — только shadow observability, не диагноз и не выбор лечения.

## 6. Required tests

Сначала минимальный contract slice:

```powershell
python -m pytest tests/test_turn_frame_contract.py tests/test_planner_attempt_contract.py tests/test_turn_frame_from_raw.py -q
```

Затем только связанные shadow serialization regressions:

```powershell
python -m pytest tests/test_turn_planner_llm.py tests/test_turn_frame_shadow.py tests/test_metadata_first_observability.py -q
```

Full suite не является обязательной для этого изолированного additive checkpoint. Если targeted regression обнаружит широкий риск, СТОП и новая оценка scope до дополнительных прогонов.

Обязательное покрытие:

1. `PatientScopeFrameMeta` требует все пять metadata fields и запрещает extra.
2. Exact `FieldErrorReason` allowlist содержит ровно два новых stable error.
3. Dump содержит `container` с defaulted schema provenance в adapter/raw builder paths.
4. Scalar bridge сохраняет прежние values и статусы/provenance четырёх child fields.
5. Container `defaulted` совместим с `PlannerAttempt.shadow_status="ok"`.
6. Container `invalid` и `missing` обнаруживаются recursive helper; `ok` отклоняется, `partial` принимается.
7. Shadow/observability serialization сохраняет новый key без утечки raw.

## 7. Static/read-only checks

```powershell
git status --short
git diff --check
git diff --name-only
rg -n 'raw\.get\("patient_scope"\)|raw\["patient_scope"\]' core contracts
rg -n 'patient_scope_invalid_type|patient_scope_extra_field|container' contracts core tests
Get-FileHash -Algorithm SHA256 eval_patient_scope_a9_last.txt
git hash-object evals/v5/demo/patient_scope_shadow_matrix.json
```

Frozen expected hashes:

- first A9 raw SHA256: `478CF92060557C2A915EBBEAFAC911829EADC64F490C86C6ABFADD423A3ECE21`;
- A9 matrix git blob: `d459073bbf8767f7ff590ece2958f7aa8cb18b25`.

## 8. Checkpoints

### Checkpoint 1 — governance review

Independent checker проверяет этот TASK до code changes: design fidelity, allowlist, test sufficiency, firewall и отсутствие скрытого native implementation. После `✅` — отдельный commit/push только `TASK.md`.

### Checkpoint 2 — contract implementation

Изменить только allowlist contract/constructors/tests. Выполнить targeted tests и static checks. Без roadmap checkbox и без commit.

### Checkpoint 3 — independent code/runtime review

Checker проверяет diff и результаты тестов, отдельно подтверждает:

- container metadata additive и required;
- producers используют безопасный default;
- recursive partial semantics доказана;
- existing bridge/value/child metadata не изменены;
- native raw parsing/prompt/product authority не появились;
- protected hashes неизменны.

### Checkpoint 4 — completion

Только после checker `✅` обновить один roadmap checkbox/status, повторить diff/static checks, затем один implementation completion commit и push в `codex/stage-a`.

## 9. Definition of Done

1. Новый обязательный `container: FieldMeta` есть в contract и во всех существующих producers.
2. Добавлены ровно два approved container error reasons.
3. Defaulted/invalid/missing recursive semantics доказаны unit tests.
4. Existing scalar bridge values и четыре child metadata не изменились.
5. Оба targeted pytest slice зелёные; full suite обоснованно не запускался.
6. Prompt/native extraction/product routing/live не затронуты.
7. Первый A9 raw и frozen matrix hashes неизменны.
8. Independent checker дал `✅` до completion diff/commit.
9. Roadmap отмечает только этот subcheckpoint; A9 parent остаётся open, authority forbidden.

После completion commit — СТОП. Следующий checkpoint `A9 Native Raw Contract / Prompt Spec` начинается только с нового TASK и governance review.
