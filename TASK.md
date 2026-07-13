# TASK — A9 Raw extraction: loss-aware scalar patient-situation bridge

Один активный `TASK.md` на один checkpoint. Этот checkpoint реализует **только pure bridge** из current scalar `patient_situation` одного raw planner payload в уже принятый nested `TurnFrame.patient_scope`.

Mapping не меняет strict `TurnPlan`, product behavior, prompt, число LLM-вызовов или authority.

Общие правила: `.cursor/rules/00-guardrails.mdc`, `REVIEW_CHECKLIST.md`.

Архитектурные источники:

- `docs/ARCH_TARGET_DESIGN.md` — target и product boundaries;
- `docs/FIELD_LEVEL_PLANNER_OUTCOME_A7.md` — single-call dual branch;
- `docs/PATIENT_SCOPE_DESIGN_A9.md` §8–§15 — exact scope contract, bridge и migration;
- commit `2a34b6c` — принятый A9 Contract;
- commit `fa0e556` — exact product baseline exception.

---

## 1. Точка старта

- Ветка: `codex/stage-a`.
- HEAD: `2a34b6c feat: add A9 patient scope contract`.
- Рабочее дерево до governance diff обязано быть чистым.
- A9 Design и Contract приняты independent checker.
- Current raw builder создаёт nested all-unknown/defaulted scope и намеренно игнорирует scalar `patient_situation`.
- Product продолжает использовать strict `PlannerAttempt.legacy_plan` и legacy `PatientSituationResult`.

Frozen integrity:

```text
preservation = c2072ca74c2da73bf657d793195d2eb6c8ba7bd5
topic matrix = dc356c9c738fb80a10cf0035508d7e8c8247979d
A7 raw SHA256 = EC009EF2157189A40FDDE6B819883D40678D6289F92EEB0CD74FD0AD9A294DDA
```

## 2. Проблема checkpoint

После A9 Contract shadow schema готова, но current raw builder всегда возвращает:

```json
{
  "extent": "unknown",
  "jaw": "unknown",
  "stage": "unknown",
  "modifiers": []
}
```

Даже когда **тот же** raw planner payload уже содержит валидный scalar kind, например `one_tooth_missing` или `existing_implant_prosthetic_stage`, lossless часть этого сигнала не видна в nested shadow.

Нужно добавить детерминированный loss-aware bridge из `docs/PATIENT_SCOPE_DESIGN_A9.md` §9, не превращая scalar kind в product authority и не угадывая отсутствующие части.

## 3. Цель

Внутри `core/turn_frame_from_raw.py` добавить pure extraction, которая:

1. читает только `raw.get("patient_situation")`;
2. переносит только exact allowlist mapping из §5;
3. возвращает `PatientScopeFrame` + `PatientScopeFrameMeta`;
4. для заполненного subfield ставит `status="valid"`, confidence `0.0`, exact stable provenance;
5. для незаполненного subfield сохраняет schema default;
6. не мутирует raw;
7. не меняет strict legacy validation и product branch.

Главный инвариант:

> Bridge может сохранить известную часть scalar kind, но не имеет права достроить jaw, extent, stage, modifier, услугу, диагноз или протокол, которых kind не гарантирует.

## 4. Что checkpoint НЕ делает

1. Не меняет `_SYSTEM` и planner prompt.
2. Не просит LLM возвращать nested `patient_scope`.
3. Не добавляет второй LLM-call, retry, classifier или detector.
4. Не читает question, answer, history, session, cues или legacy `PatientSituationResult`.
5. Не запускает `detect_patient_situation()` и patient-situation LLM.
6. Не меняет `TurnPlan`, `PatientSituationKind`, `PatientSituationResult` или A9 contract literals.
7. Не repair-ит raw перед `TurnPlan.model_validate()`.
8. Не передаёт nested scope в resolver/routing/evidence/price/playbook/composer/UI/marketing/booking/contacts/medzone/session.
9. Не добавляет `patient_scope_v2`, side channel, container status или второй error store.
10. Не реализует direct nested planner output.
11. Не реализует shadow wiring checkpoint, frozen matrix, live/audit, authority или legacy retirement.
12. Не чинит preservation target-red 02/03/05.
13. Не чинит два pre-existing playbook-теста из §15.1.

## 5. Exact bridge mapping

Mapping должен быть data-driven constant/table без question regex и тематических веток вне pure bridge.

| raw `patient_situation` | extent | jaw | stage | modifiers |
|---|---|---|---|---|
| `one_tooth_missing` | `one_tooth` | default | default | default |
| `few_teeth_missing` | `few_teeth` | default | default | default |
| `full_arch_missing` | `full_arch` | default | default | default |
| `upper_jaw_missing_or_complex` | default | `upper` | default | default |
| `existing_implant_prosthetic_stage` | default | default | `implant_placed` | default |
| `extraction_then_implant` | default | default | `extraction_context` | default |
| `bone_deficit_or_grafting` | default | default | default | `["reported_bone_deficit"]` |
| `urgent_problem` | default | default | default | default |
| `generic_implant_interest` | default | default | default | default |
| `unknown` | default | default | default | default |
| null / absent | default | default | default | default |

Здесь `default` означает value `unknown` или `[]` и metadata schema default, а не `valid unknown`.

Запрещённые выводы:

```text
full_arch -> jaw=both
upper -> extent=full_arch
one_tooth -> service_id=classic
full_arch -> service_id=all_on_4/all_on_6
reported_bone_deficit -> service_id=sinus_lift
extraction_context -> one-stage protocol
urgent_problem -> scope value
generic_implant_interest -> scope value
```

## 6. Metadata semantics

### 6.1 Mapped subfield

Каждый mapped subfield:

```text
confidence = 0.0
status = valid
error = null
```

Exact provenance:

```text
extent    = turn_plan.patient_situation.extent
jaw       = turn_plan.patient_situation.jaw
stage     = turn_plan.patient_situation.stage
modifiers = turn_plan.patient_situation.modifiers
```

Confidence 0.0 обязательна: deterministic mapping не является уверенностью распознавания пользовательской фразы.

### 6.2 Unmapped/default subfield

```text
value = unknown / []
confidence = 0.0
provenance = turn_plan.schema_default
status = defaulted
error = null
```

Known kind заполняет только lossless subfield. Пустой `modifiers` у остальных kinds не означает доказанное отсутствие modifiers и остаётся `defaulted`.

### 6.3 Malformed scalar boundary

Current source — один scalar kind, а A9 errors относятся к независимым target subfields. Поэтому на этом bridge checkpoint:

- non-string scalar;
- arbitrary out-of-allowlist string;
- list/dict/bool/number;

не должны искусственно превращаться в четыре nested errors. Scope остаётся all-unknown/defaulted; strict `TurnPlan.model_validate()` по-прежнему отклоняет malformed `patient_situation`, поэтому `legacy_plan=None` и attempt остаётся `partial` через существующую dual-branch семантику.

Запрещено:

- fan-out одного scalar error на extent/jaw/stage/modifiers;
- использование raw value в error/provenance/telemetry;
- generic `patient_scope_invalid`;
- трактовать malformed dict как future direct nested output.

Exact 8 A9 error literals остаются в contract для будущего **явного per-subfield source**. Этот checkpoint не обязан создавать их, потому что scalar kind не сообщает независимые raw subfields.

Если checker считает эту семантику противоречащей принятому A9 Design — `❓` до implementation, не изобретать другую mapping/error policy в коде.

## 7. Pure implementation boundary

Допустима private pure функция в `core/turn_frame_from_raw.py`, например:

```python
def _patient_scope_from_raw(
    raw: dict[str, Any],
) -> tuple[PatientScopeFrame, PatientScopeFrameMeta]:
    ...
```

Требования:

- вход не мутируется;
- функция не вызывает I/O, config, client pack, pricebook, session, Flask, network или LLM;
- mapping constant immutable;
- возвращаемые lists/models не разделяют mutable state между вызовами;
- raw value не попадает в dump, provenance или exception;
- результаты deterministic для одинакового raw;
- existing extraction остальных axes не меняется.

`build_turn_frame_from_raw()` вызывает bridge ровно один раз и подставляет его value/meta в существующий `TurnFrame`.

## 8. Strict legacy branch и PlannerAttempt

Нельзя менять:

- `TurnPlan.model_validate()`;
- `TurnPlan.aspects min_length=1`;
- `_validate_plan()`;
- enrichment/guards;
- `plan_turn()` wrapper;
- `turn_plan_to_decision_frame()`;
- product fallback.

Ожидаемые случаи:

1. Valid raw + known scalar kind:
   - `legacy_plan` валиден как сегодня;
   - shadow nested subfield заполнен;
   - shadow status остаётся `ok`, потому что mapped/defaulted metadata не invalid/missing.
2. Valid raw + null/unknown/generic/urgent:
   - legacy behavior прежний;
   - nested scope all-defaulted;
   - attempt status определяется остальными axes как сегодня.
3. Malformed scalar:
   - shadow scope all-defaulted;
   - strict legacy plan отклонён;
   - attempt `partial`, не `ok` и не `not_available`;
   - валидные topic/aspects/intent/service axes в shadow не стираются.

## 9. Product firewall

После checkpoint product продолжает читать только `PlannerAttempt.legacy_plan`.

Запрещены imports/reads `shadow_frame.patient_scope`, `PatientScopeFrame` или bridge из:

- `orchestration/**` для решений;
- resolver/routing/decision conversion;
- evidence/source selection;
- price scope/offers/pricebook;
- patient playbook/detector/session;
- composer/answer/UI;
- marketing/promo/booking/contacts/medzone.

`core/turn_frame_shadow.py` и existing metadata/E2E serializer могут сериализовать весь TurnFrame без schema-specific product logic; менять их на extraction checkpoint не требуется.

## 10. Allowlist production

Разрешён ровно один production-файл:

1. `core/turn_frame_from_raw.py`

Любой другой production-файл → СТОП и эскалация.

Особенно protected:

- `contracts/**`;
- `core/turn_planner_llm.py`;
- `core/turn_frame_adapter.py`;
- `core/turn_frame_shadow.py`;
- `orchestration/**`;
- `core/patient_situation*.py`;
- `core/patient_playbook.py`;
- composer/price/evidence/session/UI.

## 11. Allowlist tests

Разрешены только:

1. `tests/test_turn_frame_from_raw.py`
2. `tests/test_turn_planner_llm.py`
3. `tests/test_planner_attempt_contract.py` — только если нужен integration invariant для malformed scalar/partial; без изменения contract models.

Новый test-файл не создавать. Existing asserts не ослаблять и не удалять; contract-checkpoint tests «scalar ignored» заменить более точными extraction cases, сохранив immutability/privacy/default проверки.

Любой иной test-файл → СТОП.

## 12. Обязательные tests

### 12.1 Exact mapping

1. Parameterized test всех 10 allowlist kinds + null + absent.
2. Ровно семь mapped outcomes соответствуют таблице §5.
3. `urgent_problem`, `generic_implant_interest`, `unknown`, null, absent → exact all-defaulted dump.
4. Каждая mapped axis имеет exact provenance/status/confidence/error.
5. Каждая unmapped axis остаётся exact schema default.
6. `modifiers` создаётся новым list без shared mutable state.

### 12.2 Loss-awareness

7. `full_arch_missing` не заполняет jaw.
8. `upper_jaw_missing_or_complex` не заполняет extent/modifier.
9. `one_tooth_missing` не меняет service_id.
10. `bone_deficit_or_grafting` не меняет service_id/intent/aspects.
11. `extraction_then_implant` не утверждает protocol/extent.
12. generic/urgent не становятся scope.

### 12.3 Malformed/privacy

13. Parameterized malformed scalar: int, bool, list, dict, arbitrary string.
14. Для malformed scope/meta exact all-defaulted; нет synthetic nested invalid.
15. Raw object и вложенные mutable values не мутируются.
16. Raw value/question/answer/history/exception не попадают в frame dump или stable metadata.
17. Malformed scalar не стирает valid topic/aspects/intent/service shadow axes.

### 12.4 Attempt integration

18. `plan_turn_attempt()` с valid known scalar делает один planner call, сохраняет strict `legacy_plan.patient_situation` и mapped nested shadow.
19. Такой attempt остаётся `ok` при валидных остальных axes.
20. Malformed scalar даёт `legacy_plan=None`, nested all-defaulted и `status="partial"`; не вызывает второй call/retry.
21. Valid topic/aspects остаются в partial shadow при malformed patient scalar.
22. `plan_turn()` backward-compatible wrapper возвращает только legacy plan/None как сегодня.

### 12.5 Firewall/source

23. Source/AST test: bridge не читает question/history/session/cues и не импортирует detector/LLM.
24. Source/AST test: product modules не импортируют bridge и не читают `shadow_frame.patient_scope`.
25. `core/turn_planner_llm.py`, contracts, adapter, orchestration и protected product files имеют zero diff.
26. Frozen hashes/raw unchanged.

## 13. Protected artifacts

Не менять:

- `evals/v5/demo/preservation.json`;
- `evals/v5/demo/topic_shadow_matrix.json`;
- A6/A7/A8 raw artifacts;
- A9 Design/Contract docs;
- client content/pricebook/playbook YAML;
- eval harnesses/specs.

## 14. Обязательные команды implementation checkpoint

```powershell
.venv\codex312\Scripts\python.exe -m pytest -q `
  --basetemp=.pytest_cache/a9_raw_core `
  tests/test_turn_frame_from_raw.py `
  tests/test_turn_planner_llm.py `
  tests/test_planner_attempt_contract.py

.venv\codex312\Scripts\python.exe -m pytest -q `
  --basetemp=.pytest_cache/a9_raw_contract_regression `
  tests/test_turn_frame_contract.py `
  tests/test_turn_frame_shadow.py `
  tests/test_metadata_first_observability.py `
  tests/test_turn_planner_wiring.py `
  tests/test_turn_plan_protocol_guard.py

.venv\codex312\Scripts\python.exe -m pytest -q `
  --basetemp=.pytest_cache/a9_raw_product `
  tests/test_patient_situation.py `
  tests/test_patient_situation_session.py `
  tests/test_patient_situation_routing.py `
  tests/test_patient_playbook.py `
  tests/test_composer_flow.py `
  tests/test_price_scope_router.py

.venv\codex312\Scripts\python.exe -m pytest -q `
  --basetemp=.pytest_cache/a9_raw_regression `
  tests/test_contacts_routing.py `
  tests/test_pricebook_golden.py `
  tests/test_price_layer_parity.py `
  tests/test_preservation_eval_contract.py `
  tests/test_topic_shadow_attempt_eval_contract.py `
  tests/test_topic_shadow_eval_contract.py

.venv\codex312\Scripts\python.exe -m py_compile core/turn_frame_from_raw.py

git diff --check
git status --short
git diff -- contracts core/turn_planner_llm.py core/turn_frame_adapter.py core/turn_frame_shadow.py orchestration
git diff -- evals/v5/demo/preservation.json evals/v5/demo/topic_shadow_matrix.json
git hash-object evals/v5/demo/preservation.json
git hash-object evals/v5/demo/topic_shadow_matrix.json
Get-FileHash -Algorithm SHA256 eval_topic_shadow_a7_last.txt
```

Для production boundary команда `git diff -- contracts core/turn_planner_llm.py ...` должна показывать только allowlist `core/turn_frame_from_raw.py`; checker обязан сверить полный `git diff --name-only` отдельно.

Все failed/skipped/xfail/not run, warnings и logging errors перечислить.

### 14.1 Exact pre-existing product baseline exception

Product gate принимается только как:

- `127 passed, 0 failed, 0 skipped`; или
- `125 passed, 2 failed, 0 skipped`, где failed ровно:
  1. `tests/test_patient_playbook.py::test_extraction_then_implant_prefers_one_stage_then_classic`;
  2. `tests/test_patient_playbook.py::test_no_playbook_returns_none`.

Причины должны совпадать с `fa0e556` / предыдущим checker review. Любой иной/третий fail, skip/xfail, assertion drift или diff playbook/product files → СТОП. Не называть suite зелёным при baseline exception.

## 15. Live / LLM

Запрещены:

- live eval;
- прямой real-LLM вызов;
- новый raw artifact;
- retry/resnapshot;
- изменение `.env`/flags.

Fake planner/unit integration допустимы. Shadow wiring, matrix и live — следующие отдельные checkpoints.

## 16. Checker review

Checker обязан:

1. Начать с diff allowlist test-файлов.
2. Проверить полный changed-files: один production + до трёх tests.
3. Сверить mapping element-by-element с A9 Design §9.
4. Проверить exact mapped/default metadata.
5. Проверить, что mapping loss-aware и не выводит service/protocol/diagnosis/urgency.
6. Отдельно оценить malformed scalar policy §6.3 на соответствие принятому Design; при противоречии дать `❓`, не менять код.
7. Доказать raw immutability/privacy и отсутствие shared mutable state.
8. Доказать strict legacy/product parity и single-call behavior.
9. Source/AST review подтвердить product firewall.
10. Самостоятельно запустить §14.
11. Проверить product baseline строго по §14.1.
12. Проверить frozen hashes/raw и отсутствие live artifacts.
13. Дать `✅/❌/❓` по двум слоям `REVIEW_CHECKLIST.md`.

## 17. Стоп-условия

СТОП и эскалация, если:

- нужен production/test-файл вне allowlist;
- mapping требует question/history/session/cues/detector;
- хочется заполнить больше, чем гарантирует таблица §5;
- нужен новый error literal или fan-out scalar error;
- требуется менять prompt/TurnPlan/contracts/planner/orchestration;
- nested scope нужен product consumer;
- хочется реализовать direct nested output;
- для зелёного нужен skip/xfail/resnapshot/assert weakening;
- появляется новый product fail;
- нужен live для contract-решения.

## 18. Definition of Done

A9 Raw extraction завершён, когда:

1. Изменены только `core/turn_frame_from_raw.py` и до трёх allowlist tests.
2. Все exact mappings §5 реализованы без дополнительных inference.
3. Mapped/default metadata соответствует §6.
4. Malformed scalar policy independently принята checker.
5. Raw immutable; privacy/no-leak tests зелёные.
6. Strict legacy plan и product path unchanged.
7. Planner остаётся single-call; valid known kind сохраняет `ok`, malformed даёт honest `partial`.
8. Product firewall подтверждён source/AST и zero protected diff.
9. Все §14 gates удовлетворены с учётом exact §14.1 baseline exception.
10. Frozen hashes/raw unchanged; live не запускался.
11. Independent Cursor checker дал `✅`.
12. Governance и implementation созданы отдельными commits и push только в `codex/stage-a`.

После этого — СТОП. A9 Shadow wiring, matrix, live, authority и retirement не начинать без нового `TASK.md`.
