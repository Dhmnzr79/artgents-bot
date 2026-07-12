# TurnFrame shadow audit — A3

Read-only аудит `turn_frame_shadow` на шести frozen preservation-ходах.

| Поле | Значение |
|------|----------|
| Governance | `0486e87` (A3 TASK) |
| Runtime shadow | `3746d77` (A2) |
| Frozen spec | `evals/v5/demo/preservation.json` @ `c2072ca74c2da73bf657d793195d2eb6c8ba7bd5` |
| Live run | один полный прогон, без повторов кейсов |
| Raw artifact | `eval_turn_frame_shadow_a3_last.txt` (UTF-16 LE, gitignored) |
| Raw SHA256 | `97f806553db470a52e180441a428fe29e09cc650df696c840f4db6ef36a454c4` |
| Eval exit | `1` (3/6 FAIL — известный baseline, допустимо) |
| Env | `E2E_USE_TEST_CLIENT=1`, `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8` |

Источник telemetry: `turn_complete.details` из JSONL строк того же файла `eval_turn_frame_shadow_a3_last.txt` (см. **raw line**). Все ходы — `/ask/stream`.

Легенда **evaluation:** `correct` | `wrong` | `missing` | `default_only` | `not_applicable` | `value_match_unreliable_source` (значение внешне совпало, но provenance/confidence не дают опоры).

---

## Live-прогон (итог runner)

```
SUMMARY: passed=3, failed=3, errors=0, skipped=0, total=6 (accuracy=50.0%)
EVAL_EXIT_CODE=1
```

| case id | preservation | reason (факт) |
|---------|--------------|---------------|
| preservation_01_contacts_address | PASS | ok |
| preservation_02_osseointegration | FAIL | evidence_source: got='composer' want='implantation__faq__osseointegration' |
| preservation_03_all_on_4_vs_all_on_6 | FAIL | evidence_source: got='composer' want='comparison__all_on_4_vs_all_on_6' |
| preservation_04_classic_one_tooth_price | PASS | ok |
| preservation_05_all_on_4_jaw_price | FAIL | protected_ui.price_quick_reply_count: got=0 want=2 |
| preservation_06_marketing_optional_overlay | PASS | ok |

---

## Сводка shadow-статусов

| # | case | shadow status | reason | turn_planner_used | TurnFrame в turn_complete |
|---|------|---------------|--------|-------------------|---------------------------|
| 1 | preservation_01_contacts_address | `not_available` | `turn_plan_missing` | false | **not_applicable** (TARGET: early boundary) |
| 2 | preservation_02_osseointegration | `ok` | — | true | да |
| 3 | preservation_03_all_on_4_vs_all_on_6 | `ok` | — | true | да |
| 4 | preservation_04_classic_one_tooth_price | `ok` | — | true | да |
| 5 | preservation_05_all_on_4_jaw_price | `ok` | — | true | да |
| 6 | preservation_06_marketing_optional_overlay | `ok` | — | true | да |

**Уникальных preservation-ходов:** 6  
**Planner-success shadow coverage:** **5/5** `ok` (contacts **исключён** из denominator — в **TARGET** ранняя boundary, TurnFrame **not_applicable**; в текущем runtime planner на contacts всё же вызывался)  
**degraded:** 0  
**not_available:** 1 (contacts; shadow честно зафиксировал `turn_plan_missing` после planner validation fail)

---

## preservation_01_contacts_address — contacts (без frame)

| | |
|--|--|
| `/ask/stream` | да |
| preservation | **PASS** — ok |
| raw line | L28 (`turn_complete`; frame отсутствует) |
| request_id | `4b6f1ab1-9df9-438f-80e8-e38e21ec21d7` |
| shadow status / reason | `not_available` / `turn_plan_missing` |
| TurnFrame | **not_applicable** в **TARGET** (ранняя boundary до planner-success ветки shadow) |

**Факты telemetry (L7–L28):**

- turn planner **был вызван** (`turn_planner_plan`, L10);
- planner получил **validation error** — `TurnPlan.aspects` empty (L11–L12);
- произошёл **fail-open to resolver** (L13), `turn_planner_used=false`, `resolver_used=true`;
- продуктовый ответ — `contacts_chunk`, preservation **PASS** (детерминированный contacts payload).

**Интерпретация:** preservation PASS подтверждает **правильный продуктовый ответ**, но **не** правильность текущего внутреннего пути (planner → fail-open → resolver). В **TARGET** contacts должен стать **ранней boundary** без вызова planner; тогда TurnFrame для этого хода остаётся **not_applicable**. Создавать TurnPlan для contacts **не рекомендуется** — будущий перенос contacts на boundary — **отдельная boundary-задача**, не часть A4.

---

## preservation_02_osseointegration

| | |
|--|--|
| `/ask/stream` | да |
| preservation | **FAIL** — evidence_source: composer ≠ `implantation__faq__osseointegration` |
| raw line | L50 |
| request_id | `c7f0a527-09c2-4fdc-bec3-910a4c60858e` |
| shadow status | `ok` |

| axis | value | confidence | provenance | evaluation |
|------|-------|------------|------------|------------|
| intent | `content` | 0.9 | `decision_frame.route_intent` | correct |
| topic | `null` | 0.0 | `decision_frame.service_topic` | missing |
| aspects | `["overview"]` | 0.0 | `turn_plan.aspects` | wrong |
| primary_aspect | `overview` | 0.0 | `turn_plan.aspects[0]` | wrong |
| emotion | `none` | 0.0 | `default` | default_only |
| specificity | `general` | 0.85 | `decision_frame.query_mode` | wrong |
| patient_scope | `null` | 0.0 | `missing_legacy_axis` | missing |
| service_id | `null` | 0.0 | `missing_legacy_axis` | missing |
| follow_up | `false` | 0.0 | `missing_legacy_axis` | value_match_unreliable_source |
| followup_of | `null` | 0.0 | `missing_legacy_axis` | missing |
| needs_clarification | `false` | 0.0 | `turn_plan.needs_clarify` | value_match_unreliable_source |

**Связь с FAIL (без причинности):** `topic`/`service_id` missing **коррелирует** с отсутствием scoped evidence doc в продуктовом FAIL; **этот единичный аудит не доказывает**, что missing topic/service *вызвали* composer path.

---

## preservation_03_all_on_4_vs_all_on_6

| | |
|--|--|
| `/ask/stream` | да |
| preservation | **FAIL** — evidence_source: composer ≠ `comparison__all_on_4_vs_all_on_6` |
| raw line | L70 |
| request_id | `f9b21e***-ab76-47bb4f3e7299` (redacted в raw) |
| shadow status | `ok` |

| axis | value | confidence | provenance | evaluation |
|------|-------|------------|------------|------------|
| intent | `content` | 0.9 | `decision_frame.route_intent` | correct |
| topic | `null` | 0.0 | `decision_frame.service_topic` | missing |
| aspects | `["comparison"]` | 0.0 | `turn_plan.aspects` | correct |
| primary_aspect | `comparison` | 0.0 | `turn_plan.aspects[0]` | correct |
| emotion | `none` | 0.0 | `default` | default_only |
| specificity | `general` | 0.85 | `decision_frame.query_mode` | correct |
| patient_scope | `null` | 0.0 | `missing_legacy_axis` | missing |
| service_id | `null` | 0.0 | `missing_legacy_axis` | missing |
| follow_up | `false` | 0.0 | `missing_legacy_axis` | value_match_unreliable_source |
| followup_of | `null` | 0.0 | `missing_legacy_axis` | missing |
| needs_clarification | `false` | 0.0 | `turn_plan.needs_clarify` | value_match_unreliable_source |

**Связь с FAIL (без причинности):** один **correct** aspect (`comparison`) **недостаточен** — при missing `topic`/`service_id` scoped comparison doc не выбран; корреляция с FAIL есть, **причинность из n=1 не следует**.

---

## preservation_04_classic_one_tooth_price

| | |
|--|--|
| `/ask/stream` | да |
| preservation | **PASS** — ok |
| raw line | L84 |
| request_id | `c***c-4d8a-8f4b-181fbd071c41` (redacted в raw) |
| shadow status | `ok` |

| axis | value | confidence | provenance | evaluation |
|------|-------|------------|------------|------------|
| intent | `price_lookup` | 0.9 | `decision_frame.route_intent` | correct |
| topic | `null` | 0.0 | `decision_frame.service_topic` | missing |
| aspects | `["price"]` | 0.0 | `turn_plan.aspects` | correct |
| primary_aspect | `price` | 0.0 | `turn_plan.aspects[0]` | correct |
| emotion | `none` | 0.0 | `default` | default_only |
| specificity | `specific` | 0.85 | `decision_frame.query_mode` | correct |
| patient_scope | `null` | 0.0 | `missing_legacy_axis` | missing |
| service_id | `null` | 0.0 | `missing_legacy_axis` | wrong (preservation expects `classic`; value null, source absent) |
| follow_up | `false` | 0.0 | `missing_legacy_axis` | value_match_unreliable_source |
| followup_of | `null` | 0.0 | `missing_legacy_axis` | missing |
| needs_clarification | `false` | 0.0 | `turn_plan.needs_clarify` | value_match_unreliable_source |

**Примечание:** preservation **PASS** при `service_id` null в shadow — продукт выбрал classic price path вне зафиксированного в frame `service_id`; frame не authority.

---

## preservation_05_all_on_4_jaw_price

| | |
|--|--|
| `/ask/stream` | да |
| preservation | **FAIL** — `price_quick_reply_count: got=0 want=2` |
| raw line | L102 |
| request_id | `8ad2c8d8-5917-45b7-b648-9e2c84979fc8` |
| shadow status | `ok` |

| axis | value | confidence | provenance | evaluation |
|------|-------|------------|------------|------------|
| intent | `price_lookup` | 0.9 | `decision_frame.route_intent` | correct |
| topic | `implantation` | 0.85 | `decision_frame.service_topic` | correct |
| aspects | `["price"]` | 0.0 | `turn_plan.aspects` | correct |
| primary_aspect | `price` | 0.0 | `turn_plan.aspects[0]` | correct |
| emotion | `none` | 0.0 | `default` | default_only |
| specificity | `specific` | 0.85 | `decision_frame.query_mode` | correct |
| patient_scope | `null` | 0.0 | `missing_legacy_axis` | missing |
| service_id | `all_on_4` | 0.0 | `turn_plan.service_id` | value_match_unreliable_source (value `all_on_4` совпадает с expected; confidence 0) |
| follow_up | `false` | 0.0 | `missing_legacy_axis` | value_match_unreliable_source |
| followup_of | `null` | 0.0 | `missing_legacy_axis` | missing |
| needs_clarification | `false` | 0.0 | `turn_plan.needs_clarify` | value_match_unreliable_source |

**Связь с FAIL:** shadow фиксирует price intent + `all_on_4`; FAIL — **UI** quick replies, не расхождение осей frame с pricebook amounts.

---

## preservation_06_marketing_optional_overlay

| | |
|--|--|
| `/ask/stream` | да |
| preservation | **PASS** — ok |
| raw line | L123 |
| request_id | `8fbb45f3-a025-422d-855b-48f4c193a128` |
| shadow status | `ok` |

| axis | value | confidence | provenance | evaluation |
|------|-------|------------|------------|------------|
| intent | `content` | 0.9 | `decision_frame.route_intent` | correct |
| topic | `null` | 0.0 | `decision_frame.service_topic` | missing |
| aspects | `["pain"]` | 0.0 | `turn_plan.aspects` | correct |
| primary_aspect | `pain` | 0.0 | `turn_plan.aspects[0]` | correct |
| emotion | `none` | 0.0 | `default` | default_only |
| specificity | `specific` | 0.85 | `decision_frame.query_mode` | correct |
| patient_scope | `null` | 0.0 | `missing_legacy_axis` | missing |
| service_id | `null` | 0.0 | `missing_legacy_axis` | missing |
| follow_up | `false` | 0.0 | `missing_legacy_axis` | value_match_unreliable_source |
| followup_of | `null` | 0.0 | `missing_legacy_axis` | missing |
| needs_clarification | `false` | 0.0 | `turn_plan.needs_clarify` | value_match_unreliable_source |

---

## Ответы на обязательную сводку

1. **Shadow-frame на всех preservation-ходах?** На **planner-success** ходах — **5/5** `ok`. Contacts — **not_applicable** в TARGET; в текущем прогоне frame отсутствует (`not_available`).
2. **`degraded` / `not_available`?** `degraded` — **0**; `not_available` — **1** (contacts после planner validation fail).
3. **Корректные оси на выборке:** `intent` — **корректен** (значения совпадают с route/кейсом, conf 0.9). `aspects`/`primary_aspect` — в части кейсов **семантически совпали** (03 comparison, 04–06 price/pain), но **confidence=0.0** и provenance aspects **не считаются надёжными** → **не готовы к authority**. `specificity` отражает legacy `query_mode` (conf 0.85). `topic` заполнен только в **05** (conf 0.85).
4. **Пустые / default / ненадёжные:** `topic` missing в **4/5** frame-кадров; `emotion` default_only везде; `patient_scope` missing; `service_id` missing или value_match_unreliable_source; оси с `missing_legacy_axis` часто имеют `false`/`null`, совпадающие с фактом, но **без опоры источника**.
5. **FAIL 02/03/05:** missing `topic`/`service_id` **коррелирует** с отсутствием scoped evidence в 02/03; **причинность не доказана**. Case **03** — correct `comparison` aspect **не спасает** routing evidence. Case **05** — FAIL не из frame.
6. **Authority:** **ни одна ось пока не готова к authority** (частые conf 0.0, missing topic, default emotion).
7. **Следующий TASK** — ниже.

---

## Рекомендация: один следующий маленький TASK

**A4 — native client-configurable topic axis в TurnPlan/TurnFrame (shadow-only).**

Заполнение `topic` из явного client-configurable источника в planner/adapter pipeline; только snapshot в ctx/telemetry. **Без authority**, без изменения routing, evidence selection или composer.

**Почему после A3:** `topic` missing в 4/5 frame-кадров; без native topic axis strangler не может опираться на TurnFrame для scoped evidence.

**Contacts не чинить** через создание TurnPlan или shadow на planner-path. Будущий перенос contacts на раннюю boundary — **отдельная boundary-задача**, вне scope A4.

**Не рекомендуется сейчас:** переключать ownership любой оси на TurnFrame; чинить preservation FAIL через shadow; менять routing/evidence/composer под A4.

---

## Ограничения A3

- Один прогон, n=6 — не статистика, корреляции ≠ причинность.
- A2 shadow-only; frame не участвовал в решениях.
- Preservation 3/6 — известный baseline, не дефект A3.
- Raw artifact UTF-16 LE (PowerShell `Tee-Object`); SHA256 для файла на диске.
