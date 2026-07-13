# TASK — A8 Planner fields: service / follow-up / clarification shadow slice

Один активный `TASK.md` на один checkpoint. Этот checkpoint подготовлен после полного принятия A7 и не разрешает следующий runtime-этап автоматически.

Общие правила: `.cursor/rules/00-guardrails.mdc`, `REVIEW_CHECKLIST.md`.

Архитектурные источники:

- `docs/ARCH_TARGET_DESIGN.md` — target, field-level validation и product boundaries;
- `docs/FIELD_LEVEL_PLANNER_OUTCOME_A7.md` — single-call dual branch и product firewall;
- `docs/TOPIC_SHADOW_REAUDIT_A7.md` — принятый A7 measurement baseline.

---

## 1. Точка старта

- Ветка: `codex/stage-a`.
- A7 final audit: `596e809 docs: audit A7 attempt-aware topic quality`.
- A7 attempt-aware harness: `d0046ab`.
- A7 shadow wiring: `620657d`.
- A7 raw SHA256: `EC009EF2157189A40FDDE6B819883D40678D6289F92EEB0CD74FD0AD9A294DDA`.
- A6 raw SHA256: `2EF96AB8660657501137B0A6880E7EA54594E02417197F031BE1BCE2D9D5A40A`.
- Topic matrix hash: `dc356c9c738fb80a10cf0035508d7e8c8247979d`.
- Preservation hash: `c2072ca74c2da73bf657d793195d2eb6c8ba7bd5`.
- До implementation diff рабочее дерево обязано быть чистым.

## 2. Контекст проблемы

A7 доказал, что один parseable raw planner payload можно безопасно разделить на:

```text
raw JSON
  ├─ partial-capable TurnFrame → shadow/telemetry only
  └─ strict TurnPlan           → product path as today
```

Field-level raw builder уже независимо обрабатывает:

- `route → TurnFrame.intent`;
- `topic + topic_confidence → TurnFrame.topic`;
- `aspects → TurnFrame.aspects + primary_aspect`.

Но следующие уже существующие оси `TurnFrame` пока получают общий `a7.not_migrated` default:

- `service_id`;
- `followup_of` и производный `follow_up`;
- `needs_clarification` из raw `needs_clarify`.

Из-за этого ошибка в одном из этих raw-полей по-прежнему видна только как полный strict `TurnPlan` failure. Shadow не показывает, какое именно поле было корректным или некорректным.

## 3. Цель A8

Добавить в существующий **pure raw builder** независимую валидацию трёх групп полей:

1. `service_id` против переданного каталога услуг;
2. `followup_of` против того же каталога и детерминированный `follow_up`;
3. `needs_clarify` как strict boolean → `needs_clarification`.

Результат нужен только в `PlannerAttempt.shadow_frame` и существующей telemetry.

Главный инвариант:

> Некорректное `service_id`, `followup_of` или `needs_clarify` помечает только соответствующую shadow-ось как `invalid`; оно не стирает валидные topic/aspects/intent и не меняет strict product branch.

## 4. Что A8 принципиально НЕ делает

1. Не передаёт authority ни одной оси `TurnFrame`.
2. Не меняет routing, resolver, evidence, composer, UI, answer или price cards.
3. Не ослабляет `TurnPlan` и его strict validation.
4. Не исправляет raw перед `TurnPlan.model_validate()`.
5. Не добавляет LLM-call, retry, classifier, regex inference или service hardcode.
6. Не меняет prompt и не просит LLM о новых полях: эти поля уже есть в `_SYSTEM`.
7. Не меняет enrichment/guards legacy plan:
   - `_apply_protocol_choice_guard`;
   - `_apply_focus_followup_enrichment`;
   - brand canonicalization;
   - `turn_plan_to_decision_frame`.
8. Не переносит `patient_situation → patient_scope`: существующее имя не является готовой семантически тождественной осью; нужен отдельный mapping checkpoint.
9. Не переносит `brand_filter` в `TurnFrame`: это ограничение детерминированного price boundary / будущего `ResponseSpec`, а не разрешение расширить TurnFrame в A8.
10. Не меняет `emotion` и `specificity`.
11. Не повторяет A7 live/topic matrix.
12. Не чинит известные preservation target-red 02/03/05 через legacy router.

## 5. Product firewall

После A8 product продолжает читать только `PlannerAttempt.legacy_plan`:

```text
plan_turn_attempt()
  ├─ shadow_frame: новые field statuses → ctx/logs/E2E only
  └─ legacy_plan: прежняя strict логика → resolver/product
```

Обязательно:

- `plan_turn()` остаётся backward-compatible wrapper над `.legacy_plan`;
- `orchestration/resolver_turn.py` не читает значения shadow frame для решений;
- `turn_plan_to_decision_frame`, `publish_turn_plan`, price/evidence/composer/widget не импортируют raw builder или `PlannerAttempt.shadow_frame`;
- invalid/missing shadow field не становится fallback-значением product;
- valid shadow field не подменяет legacy enrichment.

## 6. Семантика полей

### 6.1 Общие правила

- Builder получает immutable raw `dict` и отдельный `frozenset` разрешённых service ids.
- Builder не загружает client pack, pricebook, session/history и не читает вопрос.
- Raw и вложенные значения не мутируются.
- Неизвестное raw-значение не попадает в frame dump, telemetry reason или exception text.
- Confidence новых полей в этом slice = `0.0`: planner не возвращает отдельную confidence для них. Не выдумывать `0.9/1.0`.
- Provenance — только стабильные идентификаторы, перечисленные ниже.

### 6.2 `service_id`

| raw | shadow value | status | error | provenance |
|---|---|---|---|---|
| ключ отсутствует | `None` | `defaulted` | `None` | `turn_plan.schema_default` |
| `null` | `None` | `valid` | `None` | `turn_plan.raw.service_id` |
| разрешённая непустая строка | normalized string | `valid` | `None` | `turn_plan.raw.service_id` |
| non-string | `None` | `invalid` | `service_id_invalid_type` | `turn_plan.raw.service_id` |
| пустая/неизвестная строка | `None` | `invalid` | `service_id_not_allowed` | `turn_plan.raw.service_id` |

Normalization = `strip()` без lower/case conversion: service ids в каталоге считаются canonical и сравниваются точно.

### 6.3 `followup_of` и `follow_up`

`followup_of` валидируется только как optional catalog id. A8 **не утверждает**, что LLM правильно распознал продолжение истории — для этого нужен отдельный contextual quality checkpoint.

| raw `followup_of` | `followup_of` | followup meta | `follow_up` | follow_up meta |
|---|---|---|---|---|
| ключ отсутствует | `None` | `defaulted`, `turn_plan.schema_default` | `False` | `defaulted`, `turn_plan.schema_default` |
| `null` | `None` | `valid`, `turn_plan.raw.followup_of` | `False` | `valid`, `derived.followup_of` |
| разрешённая строка | normalized id, `valid` | no error | `True` | `valid`, `derived.followup_of` |
| non-string | `None`, `invalid` | `followup_of_invalid_type` | `False`, `invalid` | `follow_up_unavailable` |
| пустая/неизвестная строка | `None`, `invalid` | `followup_of_not_allowed` | `False`, `invalid` | `follow_up_unavailable` |

Нельзя подставлять session focus, `service_id` или прошлую тему в shadow builder.

### 6.4 `needs_clarify → needs_clarification`

| raw | value | status | error | provenance |
|---|---|---|---|---|
| ключ отсутствует | `False` | `defaulted` | `None` | `turn_plan.schema_default` |
| exact `true/false` | raw bool | `valid` | `None` | `turn_plan.raw.needs_clarify` |
| любой другой тип, включая `null`, `0/1`, строки | `False` | `invalid` | `needs_clarification_invalid_type` | `turn_plan.raw.needs_clarify` |

Pydantic/coercion semantics strict legacy branch не менять; shadow намеренно фиксирует тип raw до coercion.

## 7. Contract changes

В `FieldErrorReason` разрешено добавить **ровно**:

```text
service_id_invalid_type
service_id_not_allowed
followup_of_invalid_type
followup_of_not_allowed
follow_up_unavailable
needs_clarification_invalid_type
```

Новые status/error сущности, второй `field_errors` store или raw payload в `PlannerAttempt` запрещены. Единственный source of truth — существующий `TurnFrame.field_meta`.

`TurnFrame`, `TurnFrameMeta` и `PlannerAttempt` не получают новых полей.

## 8. Разрешённые production-файлы

Implementation allowlist — ровно:

1. `contracts/turn_frame.py`
2. `core/turn_frame_from_raw.py`
3. `core/turn_planner_llm.py`

Допустимый production diff:

- расширить только allowlist `FieldErrorReason`;
- добавить pure field extractors в raw builder;
- передать уже рассчитанный `allowed_ids` в raw builder из `plan_turn_attempt()`.

Запрещены изменения в `_SYSTEM`, LLM parameters, `_validate_plan`, legacy enrichment, decision conversion, publish и product wrapper. Если implementation требует другое production-изменение — СТОП.

## 9. Разрешённые test-файлы

1. `tests/test_turn_frame_from_raw.py`
2. `tests/test_turn_planner_llm.py`
3. `tests/test_planner_attempt_contract.py`

Новые test-файлы не создавать без отдельного решения. Existing asserts не ослаблять.

## 10. Protected files / artifacts

Не менять:

- `evals/v5/demo/preservation.json`;
- `evals/v5/demo/topic_shadow_matrix.json`;
- A6/A7 runners и harness tests;
- `docs/TOPIC_SHADOW_REAUDIT_A7.md`;
- `docs/A7_REGRESSION_LIVE_PROOF.md`;
- все A6/A7 raw artifacts;
- client content/frontmatter/pricebook;
- `TASK.md` после governance commit.

Frozen integrity:

```text
topic matrix git hash = dc356c9c738fb80a10cf0035508d7e8c8247979d
preservation git hash = c2072ca74c2da73bf657d793195d2eb6c8ba7bd5
A7 raw SHA256 = EC009EF2157189A40FDDE6B819883D40678D6289F92EEB0CD74FD0AD9A294DDA
```

## 11. Обязательные unit tests

Checker начинает с diff тестов.

### Raw builder

1. Valid explicit `service_id` переносится с `status=valid`, `confidence=0.0`, stable provenance.
2. Explicit `service_id=null` — valid absence; отсутствующий ключ — schema default.
3. Unknown/blank/non-string service id → safe `None`, exact stable error, raw value не утекает.
4. Valid explicit/null/missing `followup_of` формируют согласованные `follow_up` и metadata.
5. Unknown/blank/non-string followup → обе связанные оси invalid с exact errors.
6. `needs_clarify` принимает только exact bool; missing → default; null/int/string → invalid false.
7. Invalid одно новое поле не стирает valid topic/aspects/intent.
8. Raw и nested values не мутируются.
9. `patient_scope`, `emotion`, `specificity` остаются `a7.not_migrated` defaulted.
10. Unknown raw/question/answer/history/exception не попадают в dump.
11. Builder остаётся pure: без planner/session/history/LLM/resolver/pricebook/client-loader imports и без тематических строк.

### Planner split

12. `plan_turn_attempt()` передаёт в builder каталог ids, уже рассчитанный для strict branch.
13. Unknown service/followup или non-bool clarify: shadow сохраняет остальные valid поля и получает `partial`; strict legacy outcome остаётся таким, каким его определяет прежняя `_validate_plan`.
14. Полностью валидный raw с explicit optional fields сохраняет `ok` при valid legacy plan.
15. Missing optional keys используют schema defaults и сами по себе не превращают attempt в `partial`.
16. Один builder failure → `degraded`; legacy branch продолжает работать как до A8.
17. `plan_turn()` по-прежнему возвращает только `.legacy_plan`.
18. Product firewall source/AST test не допускает новых shadow consumers.

### Честность

19. Нет `skip`, `xfail`, `assert True`, conditional PASS или resnapshot.
20. Негативные тесты проверяют exact status/error, а не только отсутствие exception.
21. Моки допускаются только на существующем LLM boundary/catalog helpers; нельзя мокать сам builder в functional extraction tests.

## 12. Обязательные команды implementation checkpoint

```powershell
.venv\codex312\Scripts\python.exe -m pytest -q `
  tests/test_turn_frame_from_raw.py `
  tests/test_planner_attempt_contract.py `
  tests/test_turn_planner_llm.py

.venv\codex312\Scripts\python.exe -m pytest -q `
  tests/test_turn_frame_contract.py `
  tests/test_turn_frame_shadow.py `
  tests/test_metadata_first_observability.py `
  tests/test_turn_planner_wiring.py `
  tests/test_turn_plan_protocol_guard.py

.venv\codex312\Scripts\python.exe -m pytest -q `
  tests/test_contacts_routing.py `
  tests/test_pricebook_golden.py `
  tests/test_price_layer_parity.py `
  tests/test_preservation_eval_contract.py

.venv\codex312\Scripts\python.exe -m pytest -q `
  tests/test_topic_shadow_attempt_eval_contract.py `
  tests/test_topic_shadow_eval_contract.py

.venv\codex312\Scripts\python.exe -m py_compile `
  contracts/turn_frame.py `
  core/turn_frame_from_raw.py `
  core/turn_planner_llm.py

git diff --check
git status --short
git diff -- evals/v5/demo/preservation.json evals/v5/demo/topic_shadow_matrix.json
git hash-object evals/v5/demo/preservation.json
git hash-object evals/v5/demo/topic_shadow_matrix.json
```

Все `failed/skipped/xfail/not run`, warnings и logging errors перечислить явно.

## 13. Live / LLM

На этом implementation checkpoint:

- live eval запрещён;
- прямой вызов `plan_turn_attempt()` с real LLM запрещён;
- A7 raw не повторять и не перезаписывать;
- новые `eval_*.txt` не создавать.

После принятого implementation commit отдельный governance checkpoint решит, нужен ли A8 regression/live sample. Автоматического разрешения нет.

## 14. Checker review

Checker обязан:

1. Начать с полного diff тестов.
2. Проверить allowlist всех changed files.
3. Проверить, что optional null/default semantics совпадают с §6.
4. Проверить exact `FieldErrorReason` allowlist и отсутствие raw value leaks.
5. Самостоятельно запустить §12.
6. Source/AST-поиском подтвердить product firewall.
7. Проверить, что `_SYSTEM`, `_validate_plan`, enrichment и `turn_plan_to_decision_frame` не изменены.
8. Проверить protected hashes и отсутствие live artifacts.
9. Дать `✅/❌/❓` по двум слоям `REVIEW_CHECKLIST.md`.

## 15. Стоп-условия

СТОП и эскалация, если:

- нужен файл вне allowlist;
- требуется изменить target/protected spec/raw;
- нужно менять prompt, legacy validation или enrichment;
- хочется выводить service/follow-up из question/history/session внутри builder;
- нужно добавить `brand_filter` или `patient_scope` в этот slice;
- optional absence невозможно представить без изменения общего status contract;
- shadow field предлагается подключить к product;
- для зелёного нужен skip/xfail/resnapshot/ослабление assert;
- live отличается от unit — live вообще не разрешён на этом checkpoint.

## 16. Definition of Done

A8 implementation checkpoint завершён, когда:

1. Изменены только 3 production + до 3 test allowlist-файлов.
2. Три группы raw-полей имеют independent value/status/error/provenance.
3. Ошибка одного поля не уничтожает остальные shadow axes.
4. Strict `TurnPlan` и product behavior не изменены.
5. Product firewall доказан тестами и source review.
6. Все §12 tests зелёные без skip/xfail.
7. Frozen hashes и A7 raw SHA256 неизменны.
8. Independent Cursor checker дал `✅`.
9. Создан отдельный implementation commit и push только в `codex/stage-a`.

После этого — СТОП. A8 live/authority, patient scope, brand price constraint, boundary/evidence/marketing не начинать без нового `TASK.md`.
