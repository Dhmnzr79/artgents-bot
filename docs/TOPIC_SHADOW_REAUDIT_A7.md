# A7 Topic Shadow Re-audit

**Статус:** готово для independent doc↔raw review
**Ветка:** `codex/stage-a`
**Harness HEAD:** `d0046ab test: add A7 attempt-aware topic re-audit harness`
**Дата run:** 2026-07-13
**Authority:** запрещена; measurement-only

---

## 1. Вопрос re-audit

A6 измерял topic через strict `plan_turn() -> TurnPlan | None`. Если unrelated поле `aspects=[]` делало весь `TurnPlan` невалидным, topic становился технически недоступен.

A7 повторяет ту же frozen 33-case matrix, но читает field-level topic из одного `PlannerAttempt.shadow_frame`, сохраняя strict legacy branch отдельно.

Проверяемый вопрос:

> Можно ли честно измерить topic, когда strict legacy plan отклонён из-за другого поля?

Re-audit не подключает topic к routing/evidence/composer/UI и не принимает authority-решение.

## 2. Provenance

| Artifact | Value |
|---|---|
| Governance | `3691de4 docs: define A7 topic shadow re-audit` |
| Harness | `d0046ab test: add A7 attempt-aware topic re-audit harness` |
| Matrix git hash | `dc356c9c738fb80a10cf0035508d7e8c8247979d` |
| Preservation git hash | `c2072ca74c2da73bf657d793195d2eb6c8ba7bd5` |
| First A6 raw SHA256 | `2EF96AB8660657501137B0A6880E7EA54594E02417197F031BE1BCE2D9D5A40A` |
| A7 runner | `evals/v5/run_topic_shadow_attempt_eval.py` |
| A7 raw | `eval_topic_shadow_a7_last.txt` |

Frozen questions, expected topics, order, taxonomy and source-doc checks не менялись.

## 3. Run integrity

| Property | Verified |
|---|---|
| Attempts | 1 |
| Planner calls | 33 `turn_planner_plan` LLM usage events |
| Selective retry | 0 |
| `A7_CASE` | 33 |
| Indices | 1..33, без дублей/пропусков |
| Frozen order | exact |
| `A7_SUMMARY` | 1, raw L106 |
| Exit | `A7_EXIT_CODE=0`, raw L107 |
| Raw size | 84384 bytes |
| Raw lines | 107 |
| Raw encoding | UTF-16-LE with BOM (actual Tee-Object bytes) |
| Raw SHA256 | `EC009EF2157189A40FDDE6B819883D40678D6289F92EEB0CD74FD0AD9A294DDA` |

First planner usage: raw L1. First case: L3. Last planner usage: L103. Last case: L105.

Raw gitignored, не staged и не редактировался после run.

## 4. Главный результат

| Metric | A7 |
|---|---:|
| Frozen denominator | 33 |
| Scoreable | 33/33 |
| PASS | 33 |
| FAIL (topic mismatch) | 0 |
| ERROR | 0 |
| Skipped | 0 |
| Exact among scoreable | 33/33 |
| Frozen overall exact | 33/33 (1.0) |
| Technical unavailable | 0 |
| Invalid/out-of-taxonomy | 0 |
| Shadow degraded | 0 |

Источник: `A7_SUMMARY`, raw L106. Exit 0 согласован с 33 PASS и 0 FAIL/ERROR.

## 5. Per-topic и ambiguous

Все девять grounded topics: **3/3 exact**.

| Topic | Exact / total |
|---|---:|
| clinic | 3/3 |
| doctors | 3/3 |
| extraction | 3/3 |
| implantation | 3/3 |
| orthodontics | 3/3 |
| periodontology | 3/3 |
| prosthetics | 3/3 |
| treatment | 3/3 |
| whitening | 3/3 |

Ambiguous null: **6/6 exact**. Cases 28–33 имеют `observed_topic=null`, `topic_field_status=missing`, confidence 0.0 (raw L89, L92, L96, L99, L102, L105).

Confusion matrix содержит только diagonal cells: 3 для каждой grounded темы и `__null__→__null__=6`; сумма 33.

## 6. Shadow status и legacy availability

| Axis | Count |
|---|---:|
| shadow `ok` | 23 |
| shadow `partial` | 10 |
| shadow `not_available` | 0 |
| shadow `degraded` | 0 |
| topic FieldMeta `valid` | 27 |
| topic FieldMeta `missing` | 6 |
| topic FieldMeta `invalid/defaulted/unavailable` | 0 |
| legacy plan available | 27 |
| legacy plan unavailable | 6 |

`partial` не равен topic error:

- 4 grounded partial frames сохранили valid exact topic: cases 04/05/06/09 (raw L13/L17/L21/L31);
- 6 ambiguous frames имеют корректный missing/null topic: cases 28–33 (raw L89/L92/L96/L99/L102/L105).

Шесть strict legacy failures: cases 04/05/06/09/28/30. Перед соответствующими case lines raw содержит `turn_planner_failed` из-за `aspects=[]`: L12/L16/L20/L30/L88/L95. Все шесть при этом остались scoreable по topic.

## 7. Семь прежних A6 unavailable cases

| Case | A6 | A7 topic | A7 shadow | A7 legacy | Evidence |
|---|---|---|---|---|---|
| 04 doctors overview | unavailable | doctors exact | partial | unavailable | L13 |
| 05 doctors named | unavailable | doctors exact | partial | unavailable | L17 |
| 06 doctors implants | unavailable | doctors exact | partial | unavailable | L21 |
| 09 extraction aftercare | unavailable | extraction exact | partial | unavailable | L31 |
| 28 general price | unavailable | null exact | partial | unavailable | L89 |
| 30 booking | unavailable | null exact | partial | unavailable | L96 |
| 31 pain | unavailable | null exact | partial | available | L99 |

Все семь стали scoreable и exact. Но причинность разделяется:

- для **шести** cases legacy plan всё ещё отсутствует в этом же A7 run — field-level branch непосредственно сохранил измеримый topic;
- case 31 в A7 получил legacy plan, поэтому его улучшение относительно A6 нельзя приписывать только архитектуре: это также совместимо с вариативностью LLM между runs.

Unit replay отдельно доказал deterministic fail-open/partial поведение для всех семи, но live quality claims основаны только на фактическом A7 raw.

## 8. A6 ↔ A7 comparison

| Metric | A6 direct strict plan | A7 field-level attempt | Delta |
|---|---:|---:|---:|
| Frozen cases | 33 | 33 | 0 |
| Scoreable coverage | 26/33 (78.8%) | 33/33 (100%) | +7 cases |
| Technical unavailable | 7 | 0 | −7 |
| Exact among scoreable | 26/26 | 33/33 | both exact on scoreable sample |
| Frozen overall exact | 26/33 | 33/33 | +7 exact observations |
| Topic mismatches | 0 | 0 | 0 |

A6 source: `docs/TOPIC_SHADOW_AUDIT_A6.md` + first raw. A7 source: raw L106.

Вывод ограничен: A7 устранил all-or-nothing **observability loss** на этой выборке. Один stochastic run не доказывает стабильность 100% на будущих runs.

## 9. Confidence — descriptive only

| Slice | Count | Min | Max | Mean |
|---|---:|---:|---:|---:|
| All correct | 33 | 0.0 | 1.0 | 0.8061 |
| Grounded correct | 27 | 0.95 | 1.0 | 0.9852 |
| Ambiguous null correct | 6 | 0.0 | 0.0 | 0.0 |

Нулевой confidence у null является contract-семантикой отсутствующей темы, а не «низкой уверенностью в неправильном классе».

Confidence не калибрована; threshold/gate не вводился.

## 10. Errors, privacy и console

- Harness FAIL: 0.
- Harness ERROR: 0.
- Logging errors: 0.
- `UnicodeEncodeError`: 0.
- Traceback: 0.
- Planner call events: 33, ровно по одному на case.
- Strict `turn_planner_failed`: 6; это ожидаемая legacy validation telemetry, не harness error.

`A7_CASE` содержит только 12 contract fields и не содержит question/raw/answer/history/exception. Полный raw при этом сохраняет существующую planner telemetry, включая stable validation traceback text для strict failures; privacy claim относится к case-result contract, не ко всем pre-existing logs.

## 11. Frozen evidence after run

| Artifact | Verified |
|---|---|
| A6 runner git hash | `23150c7d47950a5b7127a44120963632bc230b00` |
| A6 tests git hash | `e1153a4e11ed22978fa3ac644f436bc26c30f17e` |
| Matrix git hash | `dc356c9c738fb80a10cf0035508d7e8c8247979d` |
| Preservation git hash | `c2072ca74c2da73bf657d793195d2eb6c8ba7bd5` |
| First A6 raw SHA256 | `2EF96AB8660657501137B0A6880E7EA54594E02417197F031BE1BCE2D9D5A40A` |

Tracked tree после run clean; единственный новый tracked candidate — этот audit-doc.

## 12. Что доказано

- Attempt-aware field-level topic был scoreable во всех 33 cases этого run.
- Все 33 observations exact относительно frozen ground truth.
- Шесть actual strict legacy failures не уничтожили topic observation.
- A7 coverage на этом sample выросла с 26/33 до 33/33.
- Product authority и runtime behavior не менялись.

## 13. Что не доказано

- 100% стабильность на повторных stochastic runs.
- Confidence calibration.
- Готовность topic или TurnFrame к product authority.
- Качество остальных TurnFrame axes.
- Улучшение ответов пользователю: этот harness не запускает product pipeline.
- Исправление старых preservation target-red 02/03/05.

## 14. Архитектурный вывод

Цель A7 достигнута на измерительном уровне: unrelated strict validation failure больше не уничтожает валидное topic-поле в shadow observability. A7 завершает strangler-подготовку topic axis, но не разрешает переключение ownership.

Следующий шаг требует отдельного governance-решения владельца/Архитектора: либо собрать повторяемость/калибровку перед authority gate, либо продолжить field-level migration других осей. Автоматически подключать topic к routing/evidence/composer после одного re-audit запрещено.
