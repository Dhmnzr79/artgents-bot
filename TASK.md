# TASK — A9 Shadow wiring proof: nested patient scope only in observability

Один активный `TASK.md` на один checkpoint. Этот checkpoint **не добавляет новое runtime wiring**: A7 уже передаёт весь `PlannerAttempt.shadow_frame` через generic recorder в `request.ctx`, turn details и protected E2E metadata.

После A9 Raw extraction нужно test-only доказать, что nested `patient_scope` проходит по существующему каналу целиком и при этом не влияет на product behavior.

Общие правила: `.cursor/rules/00-guardrails.mdc`, `REVIEW_CHECKLIST.md`.

Архитектурные источники:

- `docs/FIELD_LEVEL_PLANNER_OUTCOME_A7.md` — single-call dual branch;
- `docs/PATIENT_SCOPE_DESIGN_A9.md` §12–§15 — product firewall и shadow wiring;
- `0cc9042` — принятый A9 Raw extraction;
- `620657d` — существующий A7 attempt-aware shadow wiring;
- `fa0e556` — exact product baseline exception.

---

## 1. Точка старта

- Ветка: `codex/stage-a`.
- HEAD: `0cc9042 feat: extract A9 patient scope shadow fields`.
- Рабочее дерево до governance diff чистое.
- `plan_turn_attempt()` уже строит nested shadow scope из того же raw payload.
- `run_resolver_turn()` уже вызывает `record_planner_attempt_shadow(attempt=attempt)` до product branch.
- Recorder уже сохраняет `frame.model_dump()` без schema-specific фильтрации.
- `core/metadata_first_observability.py` уже включает `turn_frame_shadow/status/reason` в turn details и protected response metadata.
- Без `E2E_USE_TEST_CLIENT=1` final response/widget не получает metadata-first payload.

Frozen integrity:

```text
preservation = c2072ca74c2da73bf657d793195d2eb6c8ba7bd5
topic matrix = dc356c9c738fb80a10cf0035508d7e8c8247979d
A7 raw SHA256 = EC009EF2157189A40FDDE6B819883D40678D6289F92EEB0CD74FD0AD9A294DDA
```

## 2. Цель

Добавить только tests, которые независимо доказывают путь:

```text
one raw planner call
  -> PlannerAttempt.shadow_frame.patient_scope
  -> record_planner_attempt_shadow()
  -> request.ctx["turn_frame_shadow"]
  -> metadata_first_turn_details()
  -> protected E2E response meta only

PlannerAttempt.legacy_plan
  -> прежний product path без чтения nested scope
```

Главный инвариант:

> Nested patient scope можно наблюдать и измерять, но ни одно его value/meta не участвует в route, decision, evidence, price, playbook, composer, UI или session.

## 3. Почему production diff не нужен

Current generic code уже выполняет target:

1. `core.turn_frame_shadow.record_planner_attempt_shadow()` сериализует полный `TurnFrame.model_dump()`.
2. `orchestration.resolver_turn.run_resolver_turn()` использует только `attempt.legacy_plan` для product и отдельно вызывает recorder.
3. `_METADATA_FIRST_TURN_KEYS` уже содержит полный `turn_frame_shadow`, status и reason.
4. `finalize_ask()` прикладывает metadata-first к response только под existing E2E gate.

Поэтому production allowlist пуст. Запрещено менять production ради cosmetic refactor, нового alias/key, duplicate patient-scope telemetry или специального nested serializer.

Если test невозможно написать без production change — СТОП и `❓`; исполнитель не расширяет scope самостоятельно.

## 4. Что checkpoint НЕ делает

1. Не меняет contracts/models/errors/mapping.
2. Не меняет raw builder, planner, recorder, resolver или metadata-first production code.
3. Не добавляет отдельные ctx keys вроде `patient_scope_shadow`.
4. Не копирует nested scope в existing legacy `patient_scope` telemetry key.
5. Не меняет prompt/LLM-call/retry/classifier/detector.
6. Не подключает scope к product consumers.
7. Не добавляет direct nested planner output.
8. Не добавляет session carry/effective scope.
9. Не создаёт frozen matrix и не запускает live/audit.
10. Не передаёт authority и не удаляет legacy.
11. Не чинит preservation target-red или playbook baseline failures.

## 5. Exact observability contract

### 5.1 Recorder / ctx

Для `ok` attempt с mapped scope recorder обязан сохранить exact `attempt.shadow_frame.model_dump()`:

```text
request.ctx.turn_frame_shadow_status = ok
request.ctx.turn_frame_shadow.patient_scope = nested value
request.ctx.turn_frame_shadow.field_meta.patient_scope = nested metadata
turn_frame_shadow_reason отсутствует
```

Для `partial` из-за unrelated axis (например `aspects=[]`) mapped patient scope не теряется:

```text
turn_frame_shadow_status = partial
patient_scope mapped subfield = valid
unmapped subfields = defaulted
aspects error = aspects_empty
```

Partial status не делает scope product-valid/authoritative; это только telemetry.

### 5.2 Turn details/log path

`metadata_first_turn_details()` должен возвращать тот же nested snapshot без flattening, rename или потери metadata. Этот slice используется существующим turn-complete/log path; новый success-event и отдельный log payload не добавляются.

### 5.3 Protected E2E response meta

При `E2E_USE_TEST_CLIENT=1` `finalize_ask()` должен сохранить nested value/meta внутри:

```text
response.meta.metadata_first.turn_frame_shadow
```

Без флага final response не содержит `metadata_first` и nested scope не появляется в widget payload.

### 5.4 Privacy

Ни ctx snapshot, ни turn details, ни E2E meta не содержат:

- raw `patient_situation` source value сверх mapped safe enum values;
- question/answer/history/session;
- exception text;
- arbitrary malformed scalar;
- duplicate raw JSON.

## 6. Product firewall

Tests обязаны доказать:

1. `run_resolver_turn()` ветвится только по `attempt.legacy_plan`.
2. `partial + legacy_plan=None` вызывает прежний `resolve_with_fallback`.
3. Mapped scope не переписывает fallback:
   - `decision.route_intent`;
   - `decision.service_topic`;
   - `decision.service_id`;
   - `intent`;
   - `scope_topic_candidate`.
4. `ok + legacy_plan` сохраняет planner-owned product path как сегодня.
5. Recorder return value не используется product runtime.
6. Никакой product module не читает:

```text
attempt.shadow_frame.patient_scope
turn_frame_shadow["patient_scope"]
.patient_scope.extent/.jaw/.stage/.modifiers
```

7. `PatientSituationResult`/playbook/price/session consumers unchanged.

## 7. Strict allowlist

Разрешены только test-файлы:

1. `tests/test_turn_frame_shadow.py`
2. `tests/test_metadata_first_observability.py`
3. `tests/test_turn_planner_wiring.py` — только если требуется отдельный AST/product-firewall assert; не менять product expectations.

Production allowlist пуст.

Особенно запрещены:

- `contracts/**`;
- `core/**`;
- `orchestration/**`;
- `app.py`, `llm.py`;
- patient-situation/playbook/price/evidence/composer/session/UI;
- eval specs/harness/client content/docs;
- `TASK.md` после governance commit.

Новый test-файл не создавать. Existing tests/asserts не ослаблять и не удалять.

## 8. Обязательные tests

### 8.1 Recorder

1. `ok` attempt с `one_tooth_missing` сохраняет exact nested extent value/meta.
2. `ok` attempt с `bone_deficit_or_grafting` сохраняет exact modifier value/meta.
3. Unmapped nested fields остаются exact schema-default metadata.
4. Recorder snapshot строго равен `attempt.shadow_frame.model_dump()`.
5. Stale reason очищается.

### 8.2 Partial/runtime

6. Partial attempt с mapped scope + invalid unrelated aspects сохраняет оба факта независимо.
7. `run_resolver_turn()` вызывает recorder ровно один раз.
8. Partial mapped scope остаётся в ctx, а product вызывает `resolve_with_fallback`.
9. Fallback decision/intent/service_topic/service_id/scope_topic_candidate не меняются mapped scope.
10. Ни recorder result, ни snapshot не читаются для product decision.

### 8.3 Metadata/E2E

11. `metadata_first_turn_details()` сохраняет exact nested value/meta.
12. `metadata_first_response_meta()` сохраняет nested snapshot как existing internal slice.
13. `finalize_ask()` под E2E flag содержит exact nested scope/meta.
14. `finalize_ask()` без E2E flag не содержит `metadata_first`.
15. Partial nested snapshot также доступен под E2E, без превращения status в ok.

### 8.4 Privacy/firewall

16. Malformed raw secret/question/history/exception отсутствуют во всех наблюдаемых payload.
17. Source/AST scan не находит product reads nested scope/ctx shadow patient scope.
18. Production diff пуст.
19. No skip/xfail/assert True/conditional PASS.
20. Frozen hashes/raw unchanged; live artifacts не создаются.

## 9. Test construction rules

- Использовать real `build_turn_frame_from_raw()` для создания mapped nested frame.
- Использовать real `record_planner_attempt_shadow()` для ctx snapshot.
- Допустим mock planner attempt и fallback только для изоляции runtime ветвления.
- Нельзя вручную собрать упрощённый dict вместо real frame там, где проверяется schema preservation.
- Для `finalize_ask()` допустим existing patch pattern `mem_get/record_last_bot_payload/emit_bot_event`.
- AST/source test дополняет functional tests, а не заменяет их.

## 10. Protected product baseline

Product files/tests не меняются. Regression product gate остаётся:

- `127 passed, 0 failed, 0 skipped`; или
- `125 passed, exact 2 failed, 0 skipped`:
  1. `test_extraction_then_implant_prefers_one_stage_then_classic`;
  2. `test_no_playbook_returns_none`.

Любой иной fail, reason drift, skip/xfail или product diff → СТОП. Suite при baseline exception не называть зелёным.

## 11. Обязательные команды implementation checkpoint

```powershell
.venv\codex312\Scripts\python.exe -m pytest -q `
  --basetemp=.pytest_cache/a9_shadow_wiring `
  tests/test_turn_frame_shadow.py `
  tests/test_metadata_first_observability.py `
  tests/test_turn_planner_wiring.py

.venv\codex312\Scripts\python.exe -m pytest -q `
  --basetemp=.pytest_cache/a9_shadow_contract_regression `
  tests/test_turn_frame_from_raw.py `
  tests/test_turn_planner_llm.py `
  tests/test_turn_frame_contract.py `
  tests/test_planner_attempt_contract.py `
  tests/test_turn_plan_protocol_guard.py

.venv\codex312\Scripts\python.exe -m pytest -q `
  --basetemp=.pytest_cache/a9_shadow_product `
  tests/test_patient_situation.py `
  tests/test_patient_situation_session.py `
  tests/test_patient_situation_routing.py `
  tests/test_patient_playbook.py `
  tests/test_composer_flow.py `
  tests/test_price_scope_router.py

.venv\codex312\Scripts\python.exe -m pytest -q `
  --basetemp=.pytest_cache/a9_shadow_regression `
  tests/test_contacts_routing.py `
  tests/test_pricebook_golden.py `
  tests/test_price_layer_parity.py `
  tests/test_preservation_eval_contract.py `
  tests/test_topic_shadow_attempt_eval_contract.py `
  tests/test_topic_shadow_eval_contract.py

git diff --check
git status --short
git diff --name-only
git diff -- contracts core orchestration app.py llm.py
git diff -- evals/v5/demo/preservation.json evals/v5/demo/topic_shadow_matrix.json
git hash-object evals/v5/demo/preservation.json
git hash-object evals/v5/demo/topic_shadow_matrix.json
Get-FileHash -Algorithm SHA256 eval_topic_shadow_a7_last.txt
```

Все failed/skipped/xfail/not run, warnings и logging errors перечислить. Live/LLM не запускать.

## 12. Checker review

Checker обязан:

1. Начать с полного diff allowlist tests.
2. Проверить, что production diff действительно пуст.
3. Подтвердить, что generic wiring уже существовало до checkpoint и tests не маскируют runtime gap.
4. Проверить real-frame construction и exact nested serialization.
5. Проверить partial/fallback product parity.
6. Проверить E2E gate и отсутствие widget payload без flag.
7. Проверить privacy/no-leak и AST firewall.
8. Самостоятельно выполнить §11.
9. Проверить product baseline строго по §10.
10. Проверить frozen hashes/raw и отсутствие live artifacts.
11. Дать `✅/❌/❓` по двум слоям `REVIEW_CHECKLIST.md`.

## 13. Стоп-условия

СТОП и эскалация, если:

- нужен production diff;
- generic recorder теряет nested value/meta;
- turn details/E2E flatten или удаляют nested fields;
- mapped scope нужен product decision;
- требуется новый ctx/meta key;
- нужен prompt/LLM/retry/detector/session change;
- тесты требуют product expectation change;
- для зелёного нужен skip/xfail/assert weakening;
- появляется новый product fail;
- требуется live для wiring proof.

## 14. Definition of Done

A9 Shadow wiring proof завершён, когда:

1. Изменены только до трёх allowlist test-файлов; production diff пуст.
2. Real mapped nested scope проходит recorder → ctx → turn details → protected E2E без потерь.
3. Partial status и unrelated field error сохраняются независимо от valid scope subfield.
4. Product fallback/planner path не читает и не меняется из-за scope.
5. Без E2E flag widget/final response не расширен.
6. Privacy/no-leak и AST firewall подтверждены.
7. Все §11 gates удовлетворены с учётом exact product baseline exception.
8. Frozen hashes/raw unchanged; live/LLM не запускались.
9. Independent Cursor checker дал `✅`.
10. Governance и test-only implementation созданы отдельными commits и push только в `codex/stage-a`.

После этого — СТОП. A9 Frozen quality matrix, live/audit, authority и legacy retirement не начинать без нового `TASK.md`.
