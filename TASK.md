# TASK — A9 Frozen patient-scope quality matrix: spec authoring only

Один активный `TASK.md` на один checkpoint. Этот checkpoint создаёт **только замороженную спецификацию** качества nested `TurnFrame.patient_scope` до любого нового live/LLM-прогона.

Он не создаёт harness, не меняет planner/prompt/runtime/tests, не запускает LLM и не принимает решение об authority.

Общие правила: `.cursor/rules/00-guardrails.mdc`, `REVIEW_CHECKLIST.md`.

Архитектурные источники:

- `docs/PATIENT_SCOPE_DESIGN_A9.md` §6–§14 — target contract, session boundary, firewall и обязательные группы matrix;
- `docs/FIELD_LEVEL_PLANNER_OUTCOME_A7.md` — single-call dual branch и независимое field-level shadow;
- `contracts/turn_frame.py` — frozen nested value/meta schema;
- `core/turn_frame_from_raw.py` — текущий loss-aware scalar bridge;
- `session.py:221-249,523-579` — dialog history и отдельный legacy snapshot;
- `core/patient_situation_session.py:99-170` — текущее product carry только для vague price follow-up;
- `33966e4` — принятый A9 shadow wiring proof.

---

## 1. Точка старта

- Ветка: `codex/stage-a`.
- HEAD: `33966e4 test: prove A9 patient scope shadow wiring`.
- Рабочее дерево до spec diff чистое.
- Nested patient scope уже проходит только по shadow observability channel.
- Product продолжает читать только `PlannerAttempt.legacy_plan` и legacy `PatientSituationResult`.
- Новый scope не имеет authority.

Frozen integrity:

```text
preservation = c2072ca74c2da73bf657d793195d2eb6c8ba7bd5
topic matrix = dc356c9c738fb80a10cf0035508d7e8c8247979d
A7 raw SHA256 = EC009EF2157189A40FDDE6B819883D40678D6289F92EEB0CD74FD0AD9A294DDA
```

## 2. Цель checkpoint

Создать ровно один новый файл:

```text
evals/v5/demo/patient_scope_shadow_matrix.json
```

Spec должна до live зафиксировать:

1. точный loss-aware результат всех 10 current `PatientSituationKind`;
2. target field isolation, включая target-red возможности, которых bridge пока не умеет;
3. ожидаемый nested scope для single-turn вопросов;
4. current-turn-only семантику для multi-turn случаев;
5. отдельность legacy session carry от current shadow frame;
6. scoring contract без confidence threshold и без authority.

Spec замораживает **целевую семантику из repository evidence**, а не текущий output planner. Красные ожидания допустимы и обязательны, если текущий scalar bridge теряет jaw/composite fields.

## 3. Главная архитектурная граница

`TurnFrame.patient_scope` — наблюдение текущего хода. Legacy session snapshot — отдельный product source.

```text
current user turn + dialog context
  -> one planner call
  -> raw current-turn payload
  -> shadow patient_scope (измеряется matrix)

legacy PatientSituationResult/session snapshot
  -> existing product carry policy
  -> НЕ дописывает shadow patient_scope
```

Поэтому multi-turn cases обязаны хранить:

- ожидаемый `current_scope` каждого scoring turn;
- ожидаемую boundary-семантику (`session_boundary`);
- но не создавать `effective_scope`, не сливать current и carry и не объявлять legacy snapshot частью TurnFrame.

Product parity проверяется существующими regression tests и будущим live checkpoint отдельно. Frozen spec не resnapshot-ит старые product answers.

## 4. Allowlist

Исполнитель может создать только:

```text
evals/v5/demo/patient_scope_shadow_matrix.json
```

Запрещено менять:

- `TASK.md`;
- `docs/**`;
- `contracts/**`, `core/**`, `orchestration/**`, `app.py`, `llm.py`, `session.py`;
- `tests/**`;
- любые runners/harness;
- `clients/**`;
- `evals/v5/demo/preservation.json`;
- `evals/v5/demo/topic_shadow_matrix.json`;
- любые старые raw/artifacts.

Любой второй changed file → СТОП и `❓`.

## 5. Что checkpoint НЕ делает

1. Не запускает `plan_turn()`, `plan_turn_attempt()`, live/eval или любой LLM.
2. Не создаёт harness/validator/CLI/tests.
3. Не меняет prompt на direct nested output.
4. Не добавляет второй classifier/retry/repair.
5. Не подключает scope к route/evidence/price/playbook/composer/UI/session.
6. Не ослабляет strict legacy `TurnPlan`.
7. Не вводит confidence threshold, pass threshold или authority gate.
8. Не переносит observed/current/actual output в frozen expected.
9. Не чинит target-red cases под текущий scalar enum.
10. Не создаёт live raw-файл.

## 6. Строгий top-level schema

Top-level JSON содержит ровно эти ключи:

```text
schema_version
client_id
purpose
authority_decision_allowed
expected_scope_schema
scoring_contract
bridge_cases
field_isolation_cases
single_turn_cases
multi_turn_cases
```

Exact values:

```json
{
  "schema_version": "a9.patient_scope_shadow_matrix.v1",
  "client_id": "demo",
  "authority_decision_allowed": false
}
```

`purpose` — короткая строка: frozen pre-live semantics для shadow-only patient scope.

Unknown top-level key запрещён.

## 7. Frozen value schema

`expected_scope_schema` дословно фиксирует allowlists:

```json
{
  "extent": ["unknown", "one_tooth", "few_teeth", "full_arch"],
  "jaw": ["unknown", "upper", "lower", "both"],
  "stage": ["unknown", "extraction_context", "implant_placed"],
  "modifiers": ["reported_bone_deficit"]
}
```

Каждый `expected_scope` содержит ровно:

```json
{
  "extent": "unknown",
  "jaw": "unknown",
  "stage": "unknown",
  "modifiers": []
}
```

Правила:

- modifiers — unique, sorted list;
- нельзя выводить protocol/service/diagnosis из scope;
- `full_arch != all_on_4`;
- `upper != zygomatic_implants`;
- `one_tooth != classic`;
- `reported_bone_deficit` — сообщённый контекст, не диагноз.

Каждый `expected_field_status` содержит ровно `extent`, `jaw`, `stage`, `modifiers`; value каждого поля — `valid | defaulted | missing | invalid`.

## 8. Scoring contract

`scoring_contract` содержит ровно:

```json
{
  "scope_match": "per_field_exact_normalized",
  "metadata_match": "per_field_status_and_stable_error",
  "planner_availability_separate_from_semantic_mismatch": true,
  "current_frame_is_current_turn_only": true,
  "legacy_session_carry_scored_separately": true,
  "one_live_call_per_live_turn": true,
  "retry_failed_case": false,
  "confidence_is_descriptive_only": true,
  "confidence_pass_threshold": null,
  "authority_decision_allowed": false,
  "product_parity_source": "existing_regression_suites"
}
```

Будущий summary обязан будет отдельно считать:

- planner available/unavailable/error;
- exact per subfield among scoreable;
- unknown/defaulted/missing/invalid rates;
- confusion matrix отдельно для extent/jaw/stage/modifiers;
- exact whole-scope как дополнительную, не главную метрику;
- composite preservation;
- multi-turn boundary violations;
- product parity отдельно.

## 9. Bridge cases — ровно 10, deterministic, live_calls=0

Каждый объект содержит ровно:

```text
id
raw_patient_situation
expected_scope
expected_field_status
rationale
```

Для JSON null используется `raw_patient_situation: null` только там, где это явно указано. `unknown` — отдельный current kind.

Frozen list и порядок:

| id | raw kind | extent | jaw | stage | modifiers | valid fields |
|---|---|---|---|---|---|---|
| `patient_scope_a9_bridge_01_one_tooth` | `one_tooth_missing` | one_tooth | unknown | unknown | [] | extent |
| `patient_scope_a9_bridge_02_few_teeth` | `few_teeth_missing` | few_teeth | unknown | unknown | [] | extent |
| `patient_scope_a9_bridge_03_full_arch` | `full_arch_missing` | full_arch | unknown | unknown | [] | extent |
| `patient_scope_a9_bridge_04_upper` | `upper_jaw_missing_or_complex` | unknown | upper | unknown | [] | jaw |
| `patient_scope_a9_bridge_05_implant_placed` | `existing_implant_prosthetic_stage` | unknown | unknown | implant_placed | [] | stage |
| `patient_scope_a9_bridge_06_extraction_context` | `extraction_then_implant` | unknown | unknown | extraction_context | [] | stage |
| `patient_scope_a9_bridge_07_bone_context` | `bone_deficit_or_grafting` | unknown | unknown | unknown | [reported_bone_deficit] | modifiers |
| `patient_scope_a9_bridge_08_urgent_boundary` | `urgent_problem` | unknown | unknown | unknown | [] | none |
| `patient_scope_a9_bridge_09_generic_interest` | `generic_implant_interest` | unknown | unknown | unknown | [] | none |
| `patient_scope_a9_bridge_10_unknown` | `unknown` | unknown | unknown | unknown | [] | none |

Status rule:

- перечисленные `valid fields` → `valid`;
- остальные → `defaulted`;
- errors в bridge cases не задаются, потому что все current kinds валидны, но loss-aware.

`null`/absent parity будет обязательным harness-тестом позже; он не является 11-м current kind и не расширяет frozen case count.

## 10. Field-isolation cases — ровно 4, deterministic target-red allowed

Эти cases замораживают target field-level semantics из A9 Design §8.3. Они не утверждают, что current scalar bridge уже принимает nested payload.

Каждый объект содержит ровно:

```text
id
raw_payload
expected_scope
expected_field_status
expected_field_errors
expected_attempt_status
rationale
```

`raw_payload` содержит минимальный полный planner object с валидными legacy-neutral соседями и дополнительным `patient_scope` object. Это future target fixture, не LLM output snapshot.

Frozen cases:

1. `patient_scope_a9_field_01_invalid_jaw_keeps_extent`
   - patient_scope: extent=`one_tooth`, jaw=`right`, stage=`unknown`, modifiers=[];
   - expected: extent one_tooth valid; jaw unknown invalid/error `patient_jaw_not_allowed`; stage unknown valid; modifiers [] valid;
   - attempt status: `partial`.
2. `patient_scope_a9_field_02_invalid_extent_keeps_modifier`
   - extent=`several`, jaw=`upper`, stage=`unknown`, modifiers=[`reported_bone_deficit`];
   - expected: extent unknown invalid/error `patient_extent_not_allowed`; jaw upper valid; stage unknown valid; modifier preserved valid;
   - attempt status: `partial`.
3. `patient_scope_a9_field_03_invalid_modifier_keeps_stage`
   - extent=`unknown`, jaw=`unknown`, stage=`implant_placed`, modifiers=[`sinus_lift`];
   - expected: extent/jaw unknown valid; stage implant_placed valid; modifiers [] invalid/error `patient_modifier_not_allowed`;
   - attempt status: `partial`.
4. `patient_scope_a9_field_04_missing_stage_keeps_composite`
   - extent=`full_arch`, jaw=`both`, stage key absent, modifiers=[`reported_bone_deficit`];
   - expected: extent/jaw/modifier valid; stage unknown missing/error null;
   - attempt status: `partial`.

`expected_field_errors` содержит ровно четыре keys; value — exact stable error или null.

## 11. Single-turn live semantics — ровно 20 cases

Каждый объект содержит ровно:

```text
id
category
question
expected_scope
expected_field_status
evidence_refs
rationale
```

`evidence_refs` — непустой список repository paths/sections. Это provenance ожидания, не source document для ответа.

Frozen list и порядок:

| # | id | category | question | expected scope |
|---:|---|---|---|---|
| 1 | `patient_scope_a9_live_01_one_tooth` | extent | `У меня нет одного зуба, чем его восстановить?` | one_tooth |
| 2 | `patient_scope_a9_live_02_few_teeth` | extent | `Не хватает трёх зубов подряд, что можно сделать?` | few_teeth |
| 3 | `patient_scope_a9_live_03_full_arch` | extent | `Нужно восстановить всю челюсть, зубов на ней нет.` | full_arch |
| 4 | `patient_scope_a9_live_04_upper_full_arch` | composite | `Нет зубов на верхней челюсти.` | full_arch + upper |
| 5 | `patient_scope_a9_live_05_lower_jaw` | jaw | `Восстановление нужно на нижней челюсти, какие варианты?` | lower |
| 6 | `patient_scope_a9_live_06_both_jaws` | jaw | `Нужно восстановить обе челюсти.` | both |
| 7 | `patient_scope_a9_live_07_implant_placed` | stage | `Имплант уже установлен, что делать дальше?` | implant_placed |
| 8 | `patient_scope_a9_live_08_planned_extraction` | stage | `Нужно удалить зуб и потом поставить имплант.` | extraction_context |
| 9 | `patient_scope_a9_live_09_already_removed` | stage | `Зуб уже удалили, хочу поставить имплант.` | extraction_context |
| 10 | `patient_scope_a9_live_10_bone_context` | modifier | `Врач сказал, что у меня мало кости.` | reported_bone_deficit |
| 11 | `patient_scope_a9_live_11_full_composite` | composite | `Нет зубов на верхней челюсти, врач сказал, что мало кости.` | full_arch + upper + reported_bone_deficit |
| 12 | `patient_scope_a9_live_12_scoped_price` | composite | `Сколько стоит восстановление всей верхней челюсти?` | full_arch + upper |
| 13 | `patient_scope_a9_live_13_one_tooth_extraction` | composite | `Один зуб нужно удалить и затем восстановить имплантом.` | one_tooth + extraction_context |
| 14 | `patient_scope_a9_live_14_upper_bone` | composite | `Сверху мало кости, врач обсуждает восстановление.` | upper + reported_bone_deficit |
| 15 | `patient_scope_a9_live_15_information` | negative | `Что такое имплантация?` | all unknown |
| 16 | `patient_scope_a9_live_16_generic_price` | negative | `Сколько стоит имплантация?` | all unknown |
| 17 | `patient_scope_a9_live_17_urgent_only` | negative | `Очень болит зуб, что делать?` | all unknown |
| 18 | `patient_scope_a9_live_18_named_service` | negative | `Сколько стоит All-on-4?` | all unknown |
| 19 | `patient_scope_a9_live_19_other_dental` | negative | `Безопасно ли отбеливание зубов?` | all unknown |
| 20 | `patient_scope_a9_live_20_booking_complaint` | negative | `Очень болит зуб, срочно запишите меня.` | all unknown |

Для таблицы выше неуказанные axes всегда unknown/empty.

Status rules:

- явно ожидаемое значение, включая target explicit `unknown`, → `valid` только если вопрос явно сообщает/отрицает axis;
- обычный неуказанный axis → `defaulted`;
- negative all-unknown cases → все `defaulted`;
- никаких `invalid/missing` в semantic questions не ожидается.

Target-red examples обязательны: lower, both и composite fields нельзя заменять nearest current scalar kind.

## 12. Multi-turn cases — ровно 5 scenarios / 10 live turns

Каждый scenario содержит ровно:

```text
id
category
turns
session_boundary
rationale
```

Каждый turn содержит ровно:

```text
turn
question
score_current_scope
expected_current_scope
expected_current_field_status
```

Оба хода scoreable. Один scenario использует один новый isolated `sid`; между scenarios session полностью сбрасывается. На один turn допускается ровно один planner call; retry запрещён.

Frozen scenarios:

1. `patient_scope_a9_multi_01_safe_vague_price`
   - turn 1: `У меня нет одного зуба, хочу его восстановить.` → current extent one_tooth;
   - turn 2: `А сколько это стоит?` → current all unknown/defaulted;
   - `session_boundary = "legacy_carry_not_materialized_into_current_shadow"`.
2. `patient_scope_a9_multi_02_stale_carry`
   - turn 1: `У меня нет одного зуба, хочу его восстановить.` → extent one_tooth;
   - перед turn 2 harness позже обязан сделать legacy snapshot expired через public session age semantics, не правкой raw/spec;
   - turn 2: `А сколько это стоит?` → current all unknown/defaulted;
   - `session_boundary = "expired_legacy_snapshot_not_materialized"`.
3. `patient_scope_a9_multi_03_topic_replacement`
   - turn 1: `У меня нет одного зуба, хочу его восстановить.` → extent one_tooth;
   - turn 2: `А теперь расскажите про отбеливание.` → current all unknown/defaulted;
   - `session_boundary = "explicit_topic_replacement_clears_legacy_scope"`.
4. `patient_scope_a9_multi_04_conflicting_current_value`
   - turn 1: `Нет зубов на верхней челюсти.` → full_arch + upper;
   - turn 2: `Нет, я ошибся: проблема на нижней челюсти, не хватает нескольких зубов.` → few_teeth + lower;
   - `session_boundary = "explicit_current_values_win_without_frame_merge"`.
5. `patient_scope_a9_multi_05_jaw_arrives_second`
   - turn 1: `Не хватает нескольких зубов.` → few_teeth;
   - turn 2: `Они снизу.` → current jaw lower, extent unknown/defaulted;
   - `session_boundary = "prior_extent_remains_separate_from_current_observation"`.

Важно: это frozen current-frame semantics. Spec не создаёт future `effective_scope` и не требует, чтобы current frame копировал старые fields. Если checker считает, что `recent_dialog_history()` делает такое ожидание неоднозначным, он обязан дать `❓`, а не молча переписать expected под текущий planner.

## 13. Запрещённые поля и признаки resnapshot

Ни на каком уровне spec не допускаются keys/substrings:

```text
observed
actual
current_output
planner_output
pass
passed
failed
accuracy
threshold
authority_ready
recommended_route
service_choice
price_choice
diagnosis
answer
```

Исключения только для exact approved keys:

- `authority_decision_allowed`;
- `confidence_pass_threshold`;
- `expected_current_scope` / `expected_current_field_status` (слово current здесь описывает архитектурный слой, не observed output).

Запрещено копировать raw A6/A7/A9 live output, потому что A9 live ещё не запускался.

## 14. Spec authoring procedure

1. До изменения: `git status --short` должен быть пуст.
2. Проверить frozen hashes.
3. Создать только allowlist JSON.
4. Не импортировать/не вызывать planner.
5. Проверить JSON parse.
6. Независимо посчитать:
   - bridge = 10;
   - field isolation = 4;
   - single turn = 20;
   - multi scenarios = 5;
   - multi live turns = 10;
   - planned future live calls = 30;
   - unique ids = 39;
   - duplicate ids = 0.
7. Проверить exact schema/allowlists/status/errors/order.
8. Проверить, что target-red expectations не заменены current scalar output.
9. `git diff --check`.
10. Повторно проверить frozen hashes.
11. Не stage/commit до независимого Spec review.
12. СТОП.

## 15. Команды checkpoint

Использовать `.venv/codex312` только для local JSON validation; pytest не требуется.

```powershell
git status --short
git branch --show-current
git log -1 --oneline

.\.venv\codex312\Scripts\python.exe -m json.tool evals/v5/demo/patient_scope_shadow_matrix.json > $null

git diff --check
git diff -- evals/v5/demo/preservation.json evals/v5/demo/topic_shadow_matrix.json
git hash-object evals/v5/demo/preservation.json
git hash-object evals/v5/demo/topic_shadow_matrix.json
git status --short
```

Запрещено запускать:

```text
plan_turn
plan_turn_attempt
run_*eval
pytest, который вызывает live/LLM
любой новый harness
```

## 16. Отчёт исполнителя

Отчёт обязан содержать:

1. pre-status/HEAD;
2. полный changed-files;
3. JSON parse result;
4. counts по четырём группам и planned live calls;
5. таблицу всех 39 ids с category/expected scope;
6. отдельное подтверждение 10 bridge kinds;
7. отдельное подтверждение four field-isolation target fixtures;
8. объяснение current-vs-carry для пяти multi-turn scenarios;
9. forbidden-field scan;
10. `live_calls=0` с доказательством;
11. frozen hashes;
12. skipped/not run;
13. нарушения/сомнения file:line;
14. явное `Commit не создан`;
15. СТОП для Spec review.

## 17. Checker — Spec review

Checker читает spec, Design и repository evidence read-only. Live/LLM запрещены.

Он обязан проверить:

1. only allowlist;
2. strict schema/counts/order/unique ids;
3. все 10 current kinds и exact loss table;
4. target-red field isolation не выдаётся за current capability;
5. вопросы и expected axes не содержат diagnosis/protocol inference;
6. lower/both/composite ожидания не подменены scalar enum;
7. negative cases действительно не сообщают patient scope;
8. `current_scope` не смешан с legacy carry;
9. safe/stale/replacement/conflict/jaw-second multi-turn покрыты;
10. planned 30 calls и no retry однозначны;
11. confidence descriptive, authority false;
12. frozen hashes unchanged;
13. live artifacts/calls отсутствуют;
14. spec не resnapshot current output.

Особые вопросы для `❓`:

- Достаточно ли current-turn-only semantics для multi-turn cases или spec незаметно проектирует effective view?
- Технически воспроизводим ли stale snapshot без изменения production?
- Корректно ли в одном frozen artifact держать deterministic bridge/field fixtures и live semantic cases при раздельном scoring?
- Не противоречат ли explicit unknown/status rules текущему A9 contract?

При сомнении checker не меняет spec и возвращает `❓` с точным file/field/case.

## 18. Definition of Done

Checkpoint завершён только если:

1. создан ровно один JSON allowlist-файл;
2. JSON строгий и parseable;
3. counts = 10 + 4 + 20 + 5 scenarios;
4. planned live turns = 30, фактические live calls = 0;
5. ожидания основаны на Design/repository evidence до live;
6. current scope и legacy carry разделены;
7. target-red gaps сохранены честно;
8. frozen hashes неизменны;
9. independent checker дал `✅`;
10. после отдельной команды владельца создан отдельный freeze commit только JSON.

После Spec review — СТОП. Harness/live/authority не начинать.
