# TASK — A9 Patient-scope quality harness: no live

Один активный TASK на один checkpoint. Создать и unit-тестировать измерительный harness для frozen A9 matrix. На этом checkpoint запрещены реальные endpoint/LLM/eval вызовы.

Источники: `evals/v5/demo/patient_scope_shadow_matrix.json`, `docs/PATIENT_SCOPE_DESIGN_A9.md` §11–§15, `docs/FIELD_LEVEL_PLANNER_OUTCOME_A7.md`, `core/turn_frame_from_raw.py`, `core/metadata_first_observability.py`, `evals/v5/smoke_case_runner.py:1320-1366`, `session.py:173-256,523-579`.

---

## 1. Baseline

- branch: `codex/stage-a`;
- HEAD: `15d2ae7 test: freeze A9 patient scope quality matrix`;
- clean tree до governance diff.

Frozen:

```text
patient-scope matrix = d459073bbf8767f7ff590ece2958f7aa8cb18b25
preservation = c2072ca74c2da73bf657d793195d2eb6c8ba7bd5
topic matrix = dc356c9c738fb80a10cf0035508d7e8c8247979d
A7 raw SHA256 = EC009EF2157189A40FDDE6B819883D40678D6289F92EEB0CD74FD0AD9A294DDA
```

Matrix: 10 bridge + 4 field-isolation + 20 single-turn + 5 multi scenarios/10 turns; 39 ids; 30 future live endpoint calls.

## 2. Allowlist

Создать только:

```text
evals/v5/run_patient_scope_shadow_eval.py
tests/test_patient_scope_shadow_eval_contract.py
```

Запрещено менять TASK/docs/specs/contracts/core/orchestration/app/llm/session/smoke runner/existing tests/clients/raw. Третий changed file → СТОП `❓`.

## 3. Цель и четыре независимых слоя

```text
D1: 10 deterministic bridge cases
    frozen scalar -> real build_turn_frame_from_raw -> scope/meta compare

D2: 4 deterministic future nested fixtures
    real current builder + strict TurnPlan validation
    current target-red mismatch = FAIL, не config error

L1: 20 single-turn /ask/stream cases, fresh sid

L2: 5 multi-turn scenarios / 10 /ask/stream turns
    current shadow compare + separate legacy session boundary result
```

Deterministic/live/session/product metrics не смешиваются. Planner/endpoint unavailable = ERROR, semantic mismatch = FAIL.

## 4. Почему live path — `/ask/stream`

A9 измеряет уже доказанный production-shaped канал:

```text
/ask/stream
 -> planner attempt
 -> generic shadow recorder
 -> meta.metadata_first.turn_frame_shadow
 -> last SSE ui payload
```

Multi-turn также требует `patient_situation_carried`, `patient_situation_carry_age` и public session snapshot. Поэтому direct planner недостаточен.

Переиспользовать `post_ask_stream()` и `parse_sse_ui_payload()` из `evals/v5/smoke_case_runner.py`; HTTP/SSE parser не копировать и existing runner не менять.

Один live call = один endpoint request на frozen turn. Full run = 20+10=30 endpoint requests, без retry.

## 5. Что checkpoint НЕ делает

1. Не запускает production transport/harness CLI без fake.
2. Не вызывает endpoint/planner/LLM/classifier.
3. Не создаёт live raw.
4. Не меняет frozen expected ради зелёного.
5. Не добавляет retry/filter/resume/best-of-N.
6. Не меняет runtime/prompt/session/product.
7. Не печатает question/raw/answer/history/exception text.
8. Не вводит confidence threshold или authority.

## 6. Preflight до transport

До первого `post_turn_fn` runner проверяет:

1. canonical LF git-blob hashes matrix/preservation/topic;
2. JSON parse и exact top-level/scoring keys;
3. exact case/turn/scope/status/error keys;
4. counts/order/39 unique ids/10 multi turns;
5. planned live calls=30;
6. scope/status/error allowlists;
7. modifiers unique/sorted;
8. evidence paths существуют;
9. forbidden observed/resnapshot fields отсутствуют;
10. authority=false в обоих местах.

Любой preflight drift → `HarnessConfigError`, exit 2, transport calls 0. Hash code не вызывает subprocess git.

## 7. Dependency injection

Public entry сохраняет seams:

```python
run_harness(
    *,
    post_turn_fn=None,
    reset_session_fn=None,
    age_snapshot_fn=None,
    read_snapshot_fn=None,
) -> dict
```

Допустимы typed output/timeout parameters.

Defaults:

- post → existing `post_ask_stream()`;
- reset → public `session.mem_reset()`;
- age → public blank-turn mechanism §11;
- read → public `session.get_last_patient_situation()`.

Все unit tests передают fake transport. Production default только source/AST/signature-check, не вызов. Runner не monkeypatch-ит planner.

## 8. D1 — bridge 10

Создать minimal raw с frozen scalar и neutral соседями:

```json
{"route":"content","aspects":["overview"],"service_id":null,"followup_of":null,"needs_clarify":false,"patient_situation":"<kind>","brand_filter":null,"topic":null,"topic_confidence":0.0}
```

Вызвать real `build_turn_frame_from_raw()` и сравнить только nested scope values/statuses.

- exact → PASS;
- mismatch → FAIL `scope_value_mismatch:<field>` или `scope_status_mismatch:<field>`;
- builder exception → ERROR `bridge_builder_error`, без текста exception.

No endpoint/LLM/session.

## 9. D2 — field isolation 4

Для frozen `raw_payload`:

1. real `build_turn_frame_from_raw(raw_payload)`;
2. strict branch через `TurnPlan.model_validate(raw_payload)` без repair;
3. observed attempt status: strict valid + no invalid/missing → ok; strict invalid или invalid/missing frame → partial; builder failure → degraded;
4. сравнить scope values/status/errors/attempt status.

Current builder не читает future nested `patient_scope`: все четыре current target-red результата обязаны быть обычными FAIL, не PASS/ERROR/config failure. Tests это фиксируют честно.

## 10. L1 — single-turn 20

Для каждого case:

1. unique sid `a9_scope_single_<index>_<run_id>`;
2. public reset;
3. ровно один fake/live post с `{q,sid,client_id}`;
4. извлечь last ui → `meta.metadata_first`;
5. извлечь shadow status/frame;
6. сравнить nested scope value/status/error.

Классификация:

- exact frame → PASS;
- semantic/meta mismatch → FAIL;
- not_available/missing slice/frame/transport exception → ERROR stable reason;
- degraded → ERROR `shadow_degraded`.

Fresh cases не переиспользуют sid.

## 11. L2 — multi-turn 5

Для каждого scenario: unique sid, reset только до turn 1, frozen order, один post на turn, без reset между turns. Каждый current turn сравнивается независимо; после turn 2 создаётся отдельный boundary result.

Full endpoint сам пишет normal history и product snapshot; harness не дублирует обычные messages.

### 11.1 Stale preparation только public API

Для `expired_legacy_snapshot_not_materialized` между turns:

1. public read подтверждает snapshot после turn 1;
2. вызвать public `mem_add_user(sid, "")` до age > `THRESHOLDS.patient_situation.max_turn_age`;
3. blank content фильтруется `recent_dialog_history()` и не загрязняет planner prompt;
4. public read должен вернуть None до turn 2;
5. запрещены `_persist_unlocked`, `_lock`, SQL/direct state mutation.

Если precondition не выполнен → boundary ERROR, но turn 2 всё равно вызывается один раз для frozen call count.

### 11.2 Exact boundary checks после turn 2

| boundary | Checks |
|---|---|
| `legacy_carry_not_materialized_into_current_shadow` | metadata carried=true; current all unknown/defaulted; snapshot kind one_tooth_missing |
| `expired_legacy_snapshot_not_materialized` | pre-turn expired; metadata carried=false; current all unknown/defaulted; old one-tooth snapshot не восстановлен |
| `explicit_topic_replacement_clears_legacy_scope` | carried=false; current all unknown/defaulted; public snapshot None |
| `explicit_current_values_win_without_frame_merge` | carried=false; current few_teeth+lower; snapshot few_teeth_missing, не old kind |
| `prior_extent_remains_separate_from_current_observation` | carried=false; current extent unknown/defaulted + jaw lower valid; legacy few-teeth snapshot может остаться отдельно |

Turn semantic FAIL и boundary FAIL имеют разные denominators. Это не двойной semantic PASS.

## 12. Privacy-safe JSONL

Exact prefixes:

```text
A9_SCOPE_CASE {json}
A9_SCOPE_TURN {json}
A9_SCOPE_BOUNDARY {json}
A9_SCOPE_SUMMARY {json}
```

### Case: ровно 34 строки

Bridge 10 + field 4 + single 20. Exact keys:

```text
index, group, case_id,
expected_scope, observed_scope,
expected_field_status, observed_field_status,
expected_field_errors, observed_field_errors,
shadow_status, status, reason
```

### Turn: ровно 10 строк

Exact keys:

```text
scenario_index, scenario_id, turn,
expected_scope, observed_scope,
expected_field_status, observed_field_status,
expected_field_errors, observed_field_errors,
shadow_status, status, reason
```

### Boundary: ровно 5 строк

Exact keys:

```text
scenario_index, scenario_id, session_boundary,
observed_carried, observed_carry_age, observed_snapshot_kind,
status, reason
```

Ни одна строка не содержит question/answer/history/raw payload/exception/path/sid/full response/recommendation.

Stable reason allowlist минимум:

```text
exact
scope_value_mismatch:<field>
scope_status_mismatch:<field>
scope_error_mismatch:<field>
attempt_status_mismatch
shadow_not_available
shadow_degraded
metadata_first_missing
shadow_frame_missing
transport_error
bridge_builder_error
field_builder_error
snapshot_missing_after_turn_1
snapshot_not_expired
boundary_carried_mismatch
boundary_snapshot_mismatch
boundary_current_merge
```

Никакого `str(exception)`.

## 13. Summary

Одна `A9_SCOPE_SUMMARY` с exact keys:

```text
schema_version, matrix_hash, authority_decision_allowed,
planned_live_calls, executed_live_calls,
bridge, field_isolation, single_turn, multi_turn, boundaries,
per_axis, field_status_counts, planner_availability, composite,
product_parity_source, overall_exit_code
```

Group blocks содержат total/passed/failed/errors, sum=total.

Exact totals full run:

```text
bridge=10; field_isolation=4; single_turn=20;
multi_turn=10; boundaries=5;
planned_live_calls=30; executed_live_calls=30.
```

`per_axis` отдельно для extent/jaw/stage/modifiers: scoreable, exact, unknown, defaulted, missing, invalid, confusion.

`planner_availability`: available/not_available/degraded/transport_error. `composite`: total/exact. `product_parity_source` = `existing_regression_suites`. Authority=false.

## 14. Exit semantics

```text
0 = 34 case + 10 turn + 5 boundary PASS, errors=0
1 = любой execution FAIL/ERROR
2 = preflight/config/CLI error до измерения
```

Field-isolation target-red честно делает current full run exit 1. Это не повод менять spec.

CLI не принимает filters/retry/resume. Unknown arg → exit 2 до transport.

## 15. Unit tests

Новый test file покрывает:

### Preflight

- frozen hashes/schema/counts/order/ids;
- unknown key/hash/scoring/evidence drift → config error;
- config error → fake post count 0.

### Deterministic

- real bridge 10 PASS;
- builder error privacy-safe;
- real field fixtures 4 FAIL, не ERROR/PASS;
- observed strict status partial.

### Fake endpoint

- exactly 20 fresh single + 10 ordered multi calls;
- unique/reset semantics;
- metadata extraction;
- not_available/degraded/missing slice/transport error;
- value/status/error mismatch stable reasons;
- no secret leaks.

### Boundaries

- five semantics;
- stale uses only public blank ticks;
- stale precondition error still calls turn 2;
- no current/effective merge.

### Summary/CLI/firewall

- exact schemas/denominators/sums/confusion/status/availability/composite;
- exit 0/1/2;
- unknown arg before transport;
- production default points to existing `/ask/stream` helper;
- runner не импортирует direct planner/resolver/composer/detector/second LLM.

Запрещены skip/xfail/importorskip/assert True/conditional PASS.

## 16. Regression commands

Использовать `.venv/codex312`:

```powershell
.\.venv\codex312\Scripts\python.exe -m pytest -q tests/test_patient_scope_shadow_eval_contract.py

.\.venv\codex312\Scripts\python.exe -m pytest -q tests/test_turn_frame_contract.py tests/test_turn_frame_from_raw.py tests/test_planner_attempt_contract.py tests/test_turn_frame_shadow.py tests/test_metadata_first_observability.py

.\.venv\codex312\Scripts\python.exe -m pytest -q tests/test_turn_planner_llm.py tests/test_turn_planner_wiring.py tests/test_turn_plan_protocol_guard.py tests/test_patient_situation_session.py

.\.venv\codex312\Scripts\python.exe -m pytest -q tests/test_contacts_routing.py tests/test_pricebook_golden.py tests/test_price_layer_parity.py

.\.venv\codex312\Scripts\python.exe -m py_compile evals/v5/run_patient_scope_shadow_eval.py tests/test_patient_scope_shadow_eval_contract.py

git diff --check
git diff -- evals/v5/demo/patient_scope_shadow_matrix.json evals/v5/demo/preservation.json evals/v5/demo/topic_shadow_matrix.json
git hash-object evals/v5/demo/patient_scope_shadow_matrix.json
git hash-object evals/v5/demo/preservation.json
git hash-object evals/v5/demo/topic_shadow_matrix.json
```

Product baseline:

```powershell
.\.venv\codex312\Scripts\python.exe -m pytest -q tests/test_patient_playbook.py tests/test_patient_playbook_flow.py tests/test_patient_situation.py tests/test_patient_situation_session.py
```

Допустим только exact `fa0e556`: 125 passed + те же failures:

```text
test_extraction_then_implant_prefers_one_stage_then_classic
test_no_playbook_returns_none
```

Любой новый failure → `❌`; suite нельзя называть зелёным.

## 17. Запрещённый live запуск

На этом checkpoint запрещено выполнять runner с production default, `/ask/stream`, planner или LLM. Tests используют только fake transport. `live_calls=0` обязателен.

## 18. Отчёт и checker

Исполнитель: test diff первым; changed-files; preflight; D1/D2; fake counts 20+10; boundaries; output/privacy/summary/exit; команды; baseline 125+2; hashes; skipped/live=0; нарушения; commit не создан; СТОП.

Checker независимо запускает §16 и проверяет:

1. ровно два allowlist files;
2. no hidden live;
3. preflight до transport;
4. real D1/D2;
5. fake full run 30 calls/49 measured results;
6. production default `/ask/stream`, не direct planner;
7. stale only public blank ticks;
8. current frame не становится effective merged scope;
9. errors не masquerade как FAIL;
10. privacy/metrics/exit;
11. exact product baseline;
12. frozen hashes/live=0.

## 19. Definition of Done

1. Diff ровно два allowlist files.
2. Frozen/runtime unchanged.
3. Strict runner + tests реализованы.
4. Unit tests доказывают 0 real endpoint/LLM calls.
5. D1 green и D2 target-red классифицируются честно.
6. Fake full run = 30 calls, 34 case + 10 turn + 5 boundary.
7. Session boundaries отдельны.
8. Regressions соответствуют baseline.
9. Checker `✅`.
10. Отдельный harness commit только после команды владельца.
11. Live checkpoint — только после отдельного разрешения владельца.

После Harness review — СТОП.
