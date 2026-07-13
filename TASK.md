# TASK — A9 Patient-scope shadow audit

Один активный TASK на один checkpoint. Создать один read-only audit-документ по принятому A9 raw. На этом checkpoint запрещены code/test/spec/harness changes, live/LLM и новая попытка измерения.

Audit должен отделить:

1. целостность единственного run;
2. deterministic bridge/field fixtures;
3. live semantic quality current-turn shadow;
4. отдельные legacy session boundaries;
5. product behavior, которое этим harness не оценивалось.

Нельзя превращать правильные `unknown/defaulted` в доказательство распознавания положительных признаков пациента.

---

## 1. Baseline и provenance

- branch `codex/stage-a`;
- HEAD `9f9cbaf docs: define A9 one-run live proof`;
- A9 design `9ee8c34 docs: design A9 composable patient scope`;
- A9 contract `2a34b6c feat: add A9 patient scope contract`;
- raw extraction/bridge `0cc9042 feat: extract A9 patient scope shadow fields`;
- shadow wiring proof `33966e4 test: prove A9 patient scope shadow wiring`;
- frozen matrix `15d2ae7 test: freeze A9 patient scope quality matrix`;
- harness `3f11857 test: add A9 patient scope quality harness`;
- live governance `9f9cbaf docs: define A9 one-run live proof`;
- independent raw checker verdict: `✅` for integrity/calculation honesty, **not** quality green.

Frozen artifacts:

```text
A9 raw = eval_patient_scope_a9_last.txt
A9 raw SHA256 = 478CF92060557C2A915EBBEAFAC911829EADC64F490C86C6ABFADD423A3ECE21
A9 raw size = 712294 bytes
A9 raw encoding = strict UTF-8 without BOM
A9 raw lines = 696
A9 live attempts = 1
A9 matrix hash = d459073bbf8767f7ff590ece2958f7aa8cb18b25
topic matrix hash = dc356c9c738fb80a10cf0035508d7e8c8247979d
preservation hash = c2072ca74c2da73bf657d793195d2eb6c8ba7bd5
A7 raw SHA256 = EC009EF2157189A40FDDE6B819883D40678D6289F92EEB0CD74FD0AD9A294DDA
```

Raw gitignored, не staged. Не удалять, не переименовывать, не нормализовать и не перезаписывать.

## 2. Задача и allowlist

Создать только:

```text
docs/PATIENT_SCOPE_SHADOW_AUDIT_A9.md
```

Запрещено менять:

- `TASK.md` после governance commit;
- `docs/PATIENT_SCOPE_DESIGN_A9.md`, `docs/ARCH_TARGET_DESIGN.md`;
- matrix/spec/harness/tests;
- `contracts/**`, `core/**`, `orchestration/**`, `app.py`, `llm.py`, `session.py`;
- client content/config;
- raw artifacts.

Любой второй changed tracked/untracked file → `❌` и СТОП.

## 3. Источники истины

Audit строится только из:

1. frozen A9 raw с exact SHA256;
2. `evals/v5/demo/patient_scope_shadow_matrix.json`;
3. `evals/v5/run_patient_scope_shadow_eval.py` — только для frozen scoring semantics;
4. `docs/PATIENT_SCOPE_DESIGN_A9.md` — только для target/current-turn/firewall semantics;
5. committed contracts/bridge/shadow/session code — read-only code alignment;
6. independent raw review, но все числа повторно сверяются с raw.

Не использовать новый sample, ручной вызов planner, новый ответ LLM или предположение о скрытом payload.

## 4. Обязательный статус документа

В начале документа зафиксировать четыре независимых статуса:

```text
Raw integrity: ✅ accepted
Measurement completeness: 49/49 result rows, 30/30 endpoint calls
Live current-scope quality: ❌ not ready
Authority: forbidden
```

Пояснить:

- checker `✅` означает честность/целостность raw и расчётов;
- это не означает quality green;
- два live current-scope результата не scoreable;
- positive patient-scope signals в live subset не распознаны;
- `patient_scope` остаётся shadow-only и не управляет product.

## 5. Provenance и методика

Таблица provenance должна содержать:

- commits из §1;
- raw path/hash/size/encoding/line count;
- attempts=1, no retry;
- matrix/harness hashes/commits;
- 34 CASE + 10 TURN + 5 BOUNDARY + 1 SUMMARY + exit marker;
- observed raw time window как факт логов;
- `executed_live_calls=30`;
- 30 unique `/ask/stream` request IDs, 25 session IDs;
- 167 internal `llm_usage` events — это внутренние pipeline calls, не harness retry.

Методика:

- D1 bridge 10 и D2 field isolation 4 не вызывают endpoint;
- L1 single 20 + L2 multi 10 = 30 full `/ask/stream` requests;
- current shadow извлекается из `metadata_first.turn_frame_shadow`;
- session boundary оценивается отдельно;
- frozen order, no retry;
- product answer/evidence/UI correctness не score'ились;
- confidence не score'илась и не калибровалась.

## 6. Raw integrity

Зафиксировать:

| check | fact |
|---|---|
| SHA256 | exact §1 |
| strict UTF-8 | true |
| BOM | absent |
| lines | 696 |
| CASE/TURN/BOUNDARY/SUMMARY | 34/10/5/1 |
| exit marker | one, final line, `A9_SCOPE_EXIT_CODE=1` |
| frozen order | exact |
| attempts | 1 |
| second raw/summary/index=1 | absent |
| protected diff | empty |

Raw line anchors minimum:

```text
first CASE/index 1 = raw L646
single ERROR live_17 = raw L676
last CASE/index 34/live_20 = raw L679
TURN rows = raw L680–L689
BOUNDARY rows = raw L690–L694
SUMMARY = raw L695
EXIT = raw L696
```

Line refs считать read-only по фактическому UTF-8 raw. После нумерации SHA256 обязан совпасть.

## 7. Четыре слоя результатов — не смешивать

### 7.1 D1 deterministic scalar bridge

```text
10 total / 10 PASS / 0 FAIL / 0 ERROR
```

Допустимый вывод: текущий mapping frozen legacy `patient_situation` scalar → nested `PatientScopeFrame` детерминированно совпадает с ожидаемыми 10 mappings.

Недопустимый вывод: LLM распознаёт patient scope 10/10. D1 не вызывает LLM/endpoint.

### 7.2 D2 future field isolation

```text
4 total / 0 PASS / 4 FAIL / 0 ERROR
all shadow_status=partial
```

Это заранее frozen target-red fixtures для будущего nested raw extraction. Они доказывают текущий gap field isolation, но не product regression.

Покейсно перечислить 4 IDs/reasons и raw refs.

### 7.3 Live current-turn scope

Объединить только single+multi turns:

```text
30 total
7 PASS
21 semantic FAIL
2 ERROR / not scoreable current frame
28 scoreable
exact complete scope among scoreable = 7/28 = 25.00%
exact complete scope over frozen live denominator = 7/30 = 23.33%
```

Все 7 PASS — negative/default cases, где frozen expected scope полностью `unknown/defaulted`:

- single 15 information;
- single 16 generic price;
- single 18 named service;
- single 19 other dental;
- multi 01 turn 2 vague price;
- multi 02 turn 2 stale carry;
- multi 03 turn 2 topic replacement.

Явно написать: эти PASS подтверждают safe non-inference, но не positive scope recognition.

### 7.4 Legacy/session boundaries

```text
5 total / 2 PASS / 3 FAIL / 0 ERROR
```

Boundary denominator отдельный от 30 current-turn scope rows. Boundary PASS не превращается во второй scope PASS.

## 8. Group totals — frozen summary

Таблица exact:

| group | total | PASS | FAIL | ERROR |
|---|---:|---:|---:|---:|
| bridge | 10 | 10 | 0 | 0 |
| field isolation | 4 | 0 | 4 | 0 |
| single turn | 20 | 4 | 14 | 2 |
| multi turn | 10 | 3 | 7 | 0 |
| boundaries | 5 | 2 | 3 | 0 |

Нельзя сворачивать это в одну «accuracy» без слоя/denominator.

## 9. Per-axis: frozen summary и live-positive recall

Сначала воспроизвести frozen summary по всем 44 scope rows:

| axis | scoreable | exact | unknown | defaulted | missing | invalid |
|---|---:|---:|---:|---:|---:|---:|
| extent | 42 | 25 | 39 | 39 | 0 | 0 |
| jaw | 42 | 29 | 41 | 41 | 0 | 0 |
| modifiers | 42 | 35 | 41 | 41 | 0 | 0 |
| stage | 42 | 34 | 40 | 40 | 0 | 0 |

Но обязательно объяснить: эти totals смешивают D1, D2 и live и в основном вознаграждают expected `unknown/defaulted`. Они не являются native live recognition accuracy.

Отдельно пересчитать **только 30 live rows**:

| axis | live scoreable | all-value exact | positive expected | positive available | positive exact |
|---|---:|---:|---:|---:|---:|
| extent | 28 | 15 | 13 | 13 | **0** |
| jaw | 28 | 19 | 9 | 9 | **0** |
| stage | 28 | 24 | 4 | 4 | **0** |
| modifiers | 28 | 25 | 3 | 3 | **0** |

`positive expected`:

- axis scalar не `unknown`;
- modifiers list non-empty.

Главный допустимый вывод: на frozen live subset current shadow не дал ни одного exact positive axis value. Высокие all-value exact counts происходят из negative/default matches.

Не утверждать причинность «LLM не понял»: raw доказывает отсутствие materialized positive value в measured current shadow, а не внутреннее рассуждение модели.

## 10. Composite

```text
composite total=9
composite exact=0
```

Пояснить: ни один frozen scope с минимум двумя известными axes не совпал полностью в measured shadow. Это strongest evidence, что current native/composable scope пока не готов даже для shadow quality gate.

## 11. Два не-scoreable current frames

Exact cases:

| case | result | result ref | pipeline ref |
|---|---|---|---|
| `patient_scope_a9_live_17_urgent_only` | ERROR `shadow_frame_missing`, shadow_status=`missing` | raw L676 | ingress `manual_contact`, raw L371 |
| `patient_scope_a9_live_20_booking_complaint` | ERROR `shadow_frame_missing`, shadow_status=`missing` | raw L679 | ingress `manual_contact`, raw L418 |

Обязательная семантика:

- оба запроса прошли hard/manual-contact ingress path;
- для соответствующих request IDs нет scoreable current shadow frame;
- это не semantic mismatch и не correct-null;
- raw не показывает network/HTTP exception; internal `level=ERROR` count = 0;
- frozen summary помещает их в bucket с именем `transport_error` из-за текущего fallback mapping, но нельзя называть их фактическими transport failures;
- audit должен зафиксировать taxonomy gap: future harness/status model должен отличать `not_applicable` hard boundary от transport failure.

Не менять harness в этом checkpoint и не пересчитывать frozen summary задним числом.

## 12. Semantic FAIL reasons

Воспроизвести counts:

```text
15 scope_value_mismatch:extent
5 scope_value_mismatch:jaw
4 scope_value_mismatch:stage
1 scope_value_mismatch:modifiers
2 boundary_current_merge
1 boundary_snapshot_mismatch
2 shadow_frame_missing (ERROR, отдельно)
```

Покейсный список 14 single FAIL и 7 multi FAIL обязателен. Не вставлять question/raw answer в audit.

## 13. Five boundaries

Таблица с raw L690–L694:

1. safe vague price — PASS exact; carried=true; snapshot `one_tooth_missing`;
2. stale carry — PASS exact; carried=false; snapshot null;
3. topic replacement — FAIL `boundary_snapshot_mismatch`; old snapshot `one_tooth_missing` остался наблюдаем;
4. conflicting current — FAIL `boundary_current_merge`; snapshot `upper_jaw_missing_or_complex`;
5. jaw arrives second — FAIL `boundary_current_merge`; snapshot null.

Формулировать как наблюдаемое соответствие frozen boundary contract. Не выводить root cause без дополнительного доказательства.

## 14. Planner/product firewall interpretation

Зафиксировать:

- full product endpoint был вызван, но harness score'ил shadow metadata/session boundary, не качество answer/evidence/UI;
- `patient_scope`/partial shadow не управляет route, evidence, composer, UI;
- product сохраняет legacy `patient_situation`/session path;
- поэтому red shadow quality не означает автоматически плохой или отсутствующий ответ пользователю;
- `product_parity_source=existing_regression_suites` — ссылка на ранее выполненные regressions, не live proof ответов;
- audit не разрешает заменять legacy path новым scope.

## 15. Что доказано / не доказано

**Доказано:**

- raw integrity и one-run discipline;
- harness denominators/calculations;
- scalar bridge 10/10;
- nested field isolation пока target-red 0/4;
- live safe non-inference на семи negative/default turns;
- zero exact positive axis values на frozen live subset;
- composite 0/9;
- 2/5 frozen session boundaries выполняются;
- два manual-contact requests не дали scoreable current shadow;
- product firewall остаётся.

**Не доказано:**

- что ответы бота на 21 scope mismatch плохие;
- что model internally не распознала ситуацию;
- root cause каждого mismatch;
- confidence calibration;
- качество вне frozen matrix;
- готовность patient scope к routing/evidence/composer/UI;
- authority.

## 16. Архитектурный вывод и следующий checkpoint

Audit должен рекомендовать отдельный **A9 Native Patient-scope Extraction Design** checkpoint, не реализацию внутри audit.

Цель будущего design:

```text
Один существующий planner JSON / один LLM-call;
field-level nested patient_scope extraction в partial shadow;
positive axes материализуются независимо;
strict legacy TurnPlan eligibility и product fail-open не меняются.
```

Обязательные границы рекомендации:

- shadow-only;
- без второго classifier/LLM/retry;
- не ослаблять legacy validators;
- не hardcode'ить patient situations/cases;
- не repair'ить raw перед strict legacy validation;
- не merge'ить session carry в current frame;
- не подключать scope к route/evidence/composer/UI;
- hard/manual-contact boundary получить отдельную `not_applicable` semantics, не fake default frame;
- сохранить первый A9 raw;
- новый live только после отдельного spec/harness review и разрешения владельца.

Не проектировать API/schema/prompt полностью в audit-документе. Не объявлять следующий этап A10 до закрытия решения по A9 gap.

## 17. Privacy и запрещённые claims

Audit не содержит:

- questions/answers/history/sid/raw payload/exception text;
- PII;
- «quality green», «ready», «calibrated», threshold;
- «LLM точно не понял»;
- «product сломан»;
- объединённую accuracy из D1+D2+live+boundaries;
- recommendation включить scope в product;
- обещание исправить все ответы.

Raw result JSONL privacy scan = 0 forbidden hits; ordinary observability logs не копировать в audit кроме минимальных stable facts/line refs.

## 18. Read-only проверки

```powershell
Get-FileHash -Algorithm SHA256 eval_patient_scope_a9_last.txt
git diff --check
git status --short
git diff -- evals/v5/demo/patient_scope_shadow_matrix.json evals/v5/run_patient_scope_shadow_eval.py tests/test_patient_scope_shadow_eval_contract.py
git hash-object evals/v5/demo/patient_scope_shadow_matrix.json
git hash-object evals/v5/demo/topic_shadow_matrix.json
git hash-object evals/v5/demo/preservation.json
Get-FileHash -Algorithm SHA256 eval_topic_shadow_a7_last.txt
```

Read-only parser допустим. Unit/regression/live/LLM не запускать: код не меняется, второй sample запрещён.

## 19. Checkpoints

### Checkpoint 1 — governance review

Checker проверяет этот TASK до audit authoring. После `✅` — отдельный commit только `TASK.md`.

### Checkpoint 2 — audit authoring

Создать только audit-doc, выполнить read-only сверку, без commit, СТОП.

### Checkpoint 3 — independent doc↔raw review

Checker независимо проверяет line refs, все пересчёты, layer separation, manual-contact taxonomy и запрещённые claims. Verdict `✅/❓/❌`.

### Checkpoint 4 — audit commit

Только после `✅`: commit/push одного audit-doc.

## 20. Definition of Done

1. Governance TASK принят отдельно.
2. Audit diff = один allowlist document.
3. Raw SHA/frozen hashes неизменны.
4. Integrity, deterministic, live current scope и boundaries разделены.
5. Live-positive exact=0 по всем четырём axes зафиксирован без ложной причинности.
6. Два manual-contact missing frames не названы transport failures.
7. Product firewall объяснён.
8. Authority запрещена.
9. Следующий шаг только отдельный shadow-only design.
10. Independent checker `✅` до doc commit.

После governance review — СТОП. Audit-doc не начинать.
