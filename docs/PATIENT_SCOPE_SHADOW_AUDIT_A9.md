# Patient-scope shadow audit — A9

| Статус | Результат |
|---|---|
| Raw integrity | ✅ accepted |
| Measurement completeness | 49/49 result rows, 30/30 endpoint calls |
| Live current-scope quality | ❌ not ready |
| Authority | forbidden |

Единственный A9 run целый, воспроизводимо читается и честно пересчитывается. Это означает, что измерению можно доверять. Это **не** означает, что качество `patient_scope` зелёное: два live current-scope результата не получили scoreable frame, а среди явно заданных положительных признаков пациента measured current shadow не дал ни одного exact axis value.

`patient_scope` остаётся shadow-only. Красный shadow не доказывает, что пользователь получил плохой ответ: routing, evidence, composer и UI продолжают принадлежать действующим product/legacy путям и этим audit не оценивались.

---

## 1. Provenance

| Артефакт / checkpoint | Значение |
|---|---|
| A9 design | `9ee8c34 docs: design A9 composable patient scope` |
| A9 contract | `2a34b6c feat: add A9 patient scope contract` |
| Raw extraction / scalar bridge | `0cc9042 feat: extract A9 patient scope shadow fields` |
| Shadow wiring proof | `33966e4 test: prove A9 patient scope shadow wiring` |
| Frozen matrix | `15d2ae7 test: freeze A9 patient scope quality matrix` |
| Harness | `3f11857 test: add A9 patient scope quality harness` |
| Live governance | `9f9cbaf docs: define A9 one-run live proof` |
| Audit governance | `c242993 docs: define A9 patient scope audit` |
| Matrix | `evals/v5/demo/patient_scope_shadow_matrix.json` |
| Matrix git-blob hash | `d459073bbf8767f7ff590ece2958f7aa8cb18b25` |
| Raw | `eval_patient_scope_a9_last.txt` (gitignored) |
| Raw SHA256 | `478CF92060557C2A915EBBEAFAC911829EADC64F490C86C6ABFADD423A3ECE21` |
| Raw format | strict UTF-8 without BOM, 712,294 bytes, 696 lines |
| Attempts | **1**, no retry |
| Endpoint calls | **30/30** |
| Result rows | 34 CASE + 10 TURN + 5 BOUNDARY + 1 SUMMARY |
| Captured exit | `A9_SCOPE_EXIT_CODE=1` |
| Raw time window | `2026-07-13T20:14:11.029Z` (raw L1) — `2026-07-13T20:18:44.125Z` (raw L645) |
| Independent raw review | `✅` integrity/calculations; не quality/authority approval |

Protected baselines также неизменны:

```text
topic matrix = dc356c9c738fb80a10cf0035508d7e8c8247979d
preservation = c2072ca74c2da73bf657d793195d2eb6c8ba7bd5
A7 raw SHA256 = EC009EF2157189A40FDDE6B819883D40678D6289F92EEB0CD74FD0AD9A294DDA
```

## 2. Методика

A9 harness измерял четыре разных слоя:

1. **D1 scalar bridge** — 10 deterministic cases без endpoint и LLM.
2. **D2 field isolation** — 4 frozen future-target fixtures без endpoint и LLM.
3. **Live current-turn shadow** — 20 single-turn + 10 multi-turn requests через полный `/ask/stream`.
4. **Legacy/session boundary** — 5 отдельных проверок состояния после multi-turn сценариев.

Live current scope извлекался из `meta.metadata_first.turn_frame_shadow`. Frozen order соблюдён, на каждый live turn был ровно один endpoint request, retry отсутствовал.

В raw присутствуют 30 уникальных `/ask/stream` request IDs и 25 session IDs: 20 fresh single-turn sessions и 5 multi-turn sessions. За один full-pipeline run зарегистрировано 167 внутренних `llm_usage` events. Это ingress/planner/resolver/composer и другие внутренние calls, а не повтор harness cases.

Разбивка внутренних usage events:

| call type | count |
|---|---:|
| `booking_intent` | 24 |
| `chat_answer_stream` | 17 |
| `ingress_classify` | 30 |
| `packet_composer_fullctx` | 7 |
| `patient_situation_classify` | 28 |
| `price_intent` | 8 |
| `turn_planner_plan` | 28 |
| `v5_resolver` | 10 |
| `v5_verifier` | 15 |

Harness не score'ил корректность ответа, источников, денег, follow-up UI или маркетинга. Confidence не была предметом A9 matrix и не калибровалась.

## 3. Integrity

| Проверка | Факт | Raw ref |
|---|---|---|
| SHA256 | exact frozen hash | whole file |
| UTF-8 strict decode | true | whole file |
| BOM | absent | whole file |
| Lines | 696 | whole file |
| First CASE / index 1 | bridge one-tooth | raw L646 |
| CASE rows | 34, indices 1..34 | raw L646–L679 |
| TURN rows | 10, frozen 5×2 order | raw L680–L689 |
| BOUNDARY rows | 5, frozen order | raw L690–L694 |
| SUMMARY | exactly 1 | raw L695 |
| Exit marker | exactly 1, final line, exit 1 | raw L696 |
| Second raw / summary / index 1 | absent | artifact scan |
| Attempts | 1 | one artifact/time window |
| Protected diff | empty | post-run git check |

CASE/TURN/BOUNDARY order совпал с frozen matrix element-by-element. Независимо восстановленный summary полностью совпал с `A9_SCOPE_SUMMARY` в raw L695.

## 4. Сводка по независимым слоям

| Layer | total | PASS | FAIL | ERROR | Что измеряет |
|---|---:|---:|---:|---:|---|
| D1 bridge | 10 | 10 | 0 | 0 | deterministic legacy scalar mapping |
| D2 field isolation | 4 | 0 | 4 | 0 | future nested field-level target |
| Single-turn live | 20 | 4 | 14 | 2 | current-turn shadow |
| Multi-turn live | 10 | 3 | 7 | 0 | current-turn shadow |
| Session boundaries | 5 | 2 | 3 | 0 | separate legacy/session state contract |

Эти строки нельзя объединять в одну «accuracy»: у них разные источники, denominators и смысл.

## 5. D1 — deterministic scalar bridge

Все 10 frozen mappings прошли: raw L646–L655.

Допустимый вывод: текущий код детерминированно преобразует известные legacy `patient_situation` scalar kinds в ожидаемые значения nested `PatientScopeFrame`.

Недопустимый вывод: LLM распознаёт patient scope 10/10. D1 не вызывает endpoint или LLM и не измеряет семантическое распознавание текста.

## 6. D2 — field isolation target-red

Все четыре cases дали ожидаемо красный current baseline: FAIL, `shadow_status=partial`, без ERROR.

| Raw ref | Case | Результат |
|---|---|---|
| raw L656 | `patient_scope_a9_field_01_invalid_jaw_keeps_extent` | `scope_value_mismatch:extent` |
| raw L657 | `patient_scope_a9_field_02_invalid_extent_keeps_modifier` | `scope_value_mismatch:jaw` |
| raw L658 | `patient_scope_a9_field_03_invalid_modifier_keeps_stage` | `scope_value_mismatch:stage` |
| raw L659 | `patient_scope_a9_field_04_missing_stage_keeps_composite` | `scope_value_mismatch:extent` |

Это frozen fixtures для будущей независимой материализации nested fields. Они фиксируют gap current builder/contract slice, но не являются product regression.

## 7. Live current-turn quality

Только single-turn и multi-turn rows:

```text
frozen live denominator = 30
PASS = 7
semantic FAIL = 21
ERROR / not scoreable current frame = 2
scoreable = 28
exact complete scope among scoreable = 7/28 = 25.00%
exact complete scope over frozen live denominator = 7/30 = 23.33%
```

### 7.1 Что означает семь PASS

Все семь PASS — negative/default cases с полностью `unknown/defaulted` expected current scope:

| Raw ref | Case / turn |
|---|---|
| raw L674 | `patient_scope_a9_live_15_information` |
| raw L675 | `patient_scope_a9_live_16_generic_price` |
| raw L677 | `patient_scope_a9_live_18_named_service` |
| raw L678 | `patient_scope_a9_live_19_other_dental` |
| raw L681 | `patient_scope_a9_multi_01_safe_vague_price`, turn 2 |
| raw L683 | `patient_scope_a9_multi_02_stale_carry`, turn 2 |
| raw L685 | `patient_scope_a9_multi_03_topic_replacement`, turn 2 |

Они подтверждают **safe non-inference**: current shadow не выдумал scope там, где frozen contract требовал неизвестное значение. Они не подтверждают распознавание положительных признаков.

### 7.2 Positive live signals

Для live-only subset `positive expected` означает:

- scalar axis не равен `unknown`;
- modifiers list непустой.

| Axis | live scoreable | all-value exact | positive expected | positive available | positive exact |
|---|---:|---:|---:|---:|---:|
| extent | 28 | 15 | 13 | 13 | **0** |
| jaw | 28 | 19 | 9 | 9 | **0** |
| stage | 28 | 24 | 4 | 4 | **0** |
| modifiers | 28 | 25 | 3 | 3 | **0** |

Главный quality result: measured current shadow не материализовал ни одного exact positive axis value на frozen live subset.

Это утверждение относится только к наблюдаемому shadow-frame. Raw не доказывает, что LLM «не понял» ситуацию внутри; он доказывает отсутствие ожидаемого materialized field value в измеряемом контракте.

## 8. Почему frozen per-axis totals выглядят лучше

Raw summary L695 считает все 44 scope rows вместе — D1, D2, single и multi:

| Axis | scoreable | exact | unknown | defaulted | missing | invalid |
|---|---:|---:|---:|---:|---:|---:|
| extent | 42 | 25 | 39 | 39 | 0 | 0 |
| jaw | 42 | 29 | 41 | 41 | 0 | 0 |
| modifiers | 42 | 35 | 41 | 41 | 0 | 0 |
| stage | 42 | 34 | 40 | 40 | 0 | 0 |

Эти exact counts в основном образованы expected `unknown/defaulted` и deterministic bridge. Поэтому они корректны как frozen harness summary, но не являются native live positive-recognition accuracy.

Ненулевые confusion cells frozen summary:

- extent: `few_teeth→few_teeth=1`, `few_teeth→unknown=3`, `full_arch→full_arch=1`, `full_arch→unknown=6`, `one_tooth→one_tooth=1`, `one_tooth→unknown=6`, `unknown→unavailable=2`, `unknown→unknown=24`;
- jaw: `both→unknown=2`, `lower→unknown=3`, `upper→upper=1`, `upper→unknown=6`, `unknown→unavailable=2`, `unknown→unknown=30`;
- modifiers: `none→none=36`, `none→unavailable=2`, `reported_bone_deficit→none=5`, `reported_bone_deficit→reported_bone_deficit=1`;
- stage: `extraction_context→extraction_context=1`, `extraction_context→unknown=3`, `implant_placed→implant_placed=1`, `implant_placed→unknown=2`, `unknown→unavailable=2`, `unknown→unknown=35`.

Exact positive cells в этих maps принадлежат deterministic bridge; live-only positive exact остаётся нулём.

## 9. Composite scope

```text
composite total = 9
composite exact = 0
```

Ни один frozen scope с минимум двумя известными axes не совпал полностью. Это наиболее прямое доказательство, что current composable patient-scope shadow пока не готов даже к shadow quality gate.

## 10. Два не-scoreable current frames

| Case | Result | Pipeline observation |
|---|---|---|
| `patient_scope_a9_live_17_urgent_only` | ERROR `shadow_frame_missing`, `shadow_status=missing` — raw L676 | ingress `manual_contact` — raw L371 |
| `patient_scope_a9_live_20_booking_complaint` | ERROR `shadow_frame_missing`, `shadow_status=missing` — raw L679 | ingress `manual_contact` — raw L418 |

Оба запроса прошли hard/manual-contact ingress path. Для соответствующих request IDs scoreable current shadow frame отсутствует. Это не semantic mismatch и не correct-null.

Raw не содержит network/HTTP exception для этих rows; internal `level=ERROR` count равен нулю. Frozen summary помещает оба результата в bucket с именем `transport_error` из-за generic fallback mapping harness, однако наблюдаемый факт — `shadow_frame_missing` после manual-contact boundary, а не доказанный transport failure.

Это taxonomy gap измерителя: будущая схема должна отличать `not_applicable` hard boundary от фактического transport error. Frozen harness/summary задним числом не меняются.

## 11. Semantic failures

### 11.1 Stable reason counts

```text
15 scope_value_mismatch:extent
5  scope_value_mismatch:jaw
4  scope_value_mismatch:stage
1  scope_value_mismatch:modifiers
2  boundary_current_merge
1  boundary_snapshot_mismatch
2  shadow_frame_missing (ERROR, отдельно)
```

### 11.2 Single-turn FAIL

| Raw ref | Case | Reason |
|---|---|---|
| raw L660 | `patient_scope_a9_live_01_one_tooth` | extent |
| raw L661 | `patient_scope_a9_live_02_few_teeth` | extent |
| raw L662 | `patient_scope_a9_live_03_full_arch` | extent |
| raw L663 | `patient_scope_a9_live_04_upper_full_arch` | extent |
| raw L664 | `patient_scope_a9_live_05_lower_jaw` | jaw |
| raw L665 | `patient_scope_a9_live_06_both_jaws` | jaw |
| raw L666 | `patient_scope_a9_live_07_implant_placed` | stage |
| raw L667 | `patient_scope_a9_live_08_planned_extraction` | stage |
| raw L668 | `patient_scope_a9_live_09_already_removed` | stage |
| raw L669 | `patient_scope_a9_live_10_bone_context` | modifiers |
| raw L670 | `patient_scope_a9_live_11_full_composite` | extent |
| raw L671 | `patient_scope_a9_live_12_scoped_price` | extent |
| raw L672 | `patient_scope_a9_live_13_one_tooth_extraction` | extent |
| raw L673 | `patient_scope_a9_live_14_upper_bone` | jaw |

### 11.3 Multi-turn FAIL

| Raw ref | Scenario / turn | Reason |
|---|---|---|
| raw L680 | `patient_scope_a9_multi_01_safe_vague_price`, turn 1 | extent |
| raw L682 | `patient_scope_a9_multi_02_stale_carry`, turn 1 | extent |
| raw L684 | `patient_scope_a9_multi_03_topic_replacement`, turn 1 | extent |
| raw L686 | `patient_scope_a9_multi_04_conflicting_current_value`, turn 1 | extent |
| raw L687 | `patient_scope_a9_multi_04_conflicting_current_value`, turn 2 | extent |
| raw L688 | `patient_scope_a9_multi_05_jaw_arrives_second`, turn 1 | extent |
| raw L689 | `patient_scope_a9_multi_05_jaw_arrives_second`, turn 2 | jaw |

Таблицы фиксируют observed mismatch, но не устанавливают root cause каждого случая.

## 12. Session boundaries

Boundary results имеют отдельный denominator:

| Raw ref | Scenario | Result | Observed stable facts |
|---|---|---|---|
| raw L690 | safe vague price | PASS `exact` | carried=true; snapshot `one_tooth_missing` |
| raw L691 | stale carry | PASS `exact` | carried=false; snapshot null |
| raw L692 | topic replacement | FAIL `boundary_snapshot_mismatch` | carried=false; snapshot `one_tooth_missing` |
| raw L693 | conflicting current | FAIL `boundary_current_merge` | carried=false; snapshot `upper_jaw_missing_or_complex` |
| raw L694 | jaw arrives second | FAIL `boundary_current_merge` | carried=false; snapshot null |

Итог: 2/5 frozen boundary contracts выполняются. PASS boundary не превращается во второй current-scope PASS. FAIL фиксирует несоответствие frozen boundary expectation, но raw сам по себе не доказывает root cause.

## 13. Product firewall

Full `/ask/stream` pipeline действительно выполнялся, однако A9 score измерял только shadow metadata и отдельное session boundary state.

Текущая архитектурная граница сохраняется:

```text
PlannerAttempt.legacy_plan -> product decision/fail-open
PlannerAttempt.shadow_frame -> ctx / telemetry / E2E metadata only
```

Partial/current `patient_scope` не является consumer input для route, evidence, composer или UI. Product продолжает использовать legacy `patient_situation`/session path. Поэтому:

- red shadow quality требует исправления до будущей authority;
- red shadow quality **не** равна автоматически плохому ответу пользователю;
- A9 audit не разрешает заменять legacy path новым scope;
- `product_parity_source=existing_regression_suites` в summary — provenance ранее выполненных regressions, а не score live answers в этом raw.

## 14. Privacy

Рекурсивный scan 34+10+5+1 result JSONL не нашёл forbidden result keys/content: question, answer, history, sid, raw payload, exception text/path, full response, recommendation.

Ordinary internal observability logs содержат служебный pipeline context по действующему logging contract; audit не копирует вопросы, ответы, session IDs или raw payload.

## 15. Что доказано

- Один immutable raw, один attempt, no retry/tampering.
- Полная структура 34+10+5+1 и 30/30 endpoint calls.
- Независимые group/per-axis/confusion/status/availability/composite расчёты совпадают с summary.
- Scalar bridge: 10/10 deterministic exact.
- Field isolation: 0/4, все honest target-red partial.
- Safe non-inference: семь negative/default live turns exact.
- Live-only positive exact: 0 для extent, jaw, stage и modifiers.
- Composite: 0/9.
- Boundary contract: 2/5 exact.
- Два manual-contact requests не дали scoreable current shadow.
- Product firewall остаётся в силе.

## 16. Что не доказано

- Что ответы бота в 21 semantic mismatch case плохие или отсутствуют.
- Что модель внутренне «не поняла» ситуацию.
- Root cause каждого mismatch.
- Confidence calibration или допустимый threshold.
- Качество вне frozen demo matrix.
- Качество answer/evidence/money/UI/marketing в этом run.
- Готовность `patient_scope` к product consumption.
- Authority.

## 17. Архитектурный вывод

A9 доказал инфраструктурную часть — контракт, deterministic bridge, generic shadow transport и честный harness. Он также показал, что текущий measured live path сохраняет safe defaults, но не материализует frozen positive patient-scope axes.

Следующий checkpoint должен быть отдельным **A9 Native Patient-scope Extraction Design**, а не немедленным product wiring.

Цель будущего design:

```text
Один существующий planner JSON / один LLM-call;
field-level nested patient_scope extraction в partial shadow;
валидные positive axes материализуются независимо;
strict legacy TurnPlan eligibility и product fail-open не меняются.
```

Границы:

- shadow-only;
- без второго classifier, LLM-call или retry;
- не ослаблять legacy validators;
- не repair'ить raw перед strict legacy validation;
- не hardcode'ить A9 cases/patient situations;
- не merge'ить legacy session carry в current frame;
- не подключать scope к route/evidence/composer/UI;
- hard/manual-contact path должен получить отдельную `not_applicable` semantics, а не fake default frame;
- первый A9 raw сохраняется;
- новый live возможен только после отдельного frozen spec/harness review и явного разрешения владельца.

Полный API/schema/prompt здесь не проектируется. Переход к A10 до отдельного решения по A9 gap преждевременен.

## 18. Итог

```text
Infrastructure integrity: accepted
Deterministic scalar compatibility: proven
Live native positive-scope recognition: not demonstrated (0 exact per positive axis)
Composite scope: not ready (0/9)
Session boundary contract: partially met (2/5)
Product behavior: unchanged and not quality-scored here
Authority: forbidden
```

A9 следует продолжить отдельным shadow-only design checkpoint. Повторять первый sample без архитектурного изменения и нового governance нельзя.
