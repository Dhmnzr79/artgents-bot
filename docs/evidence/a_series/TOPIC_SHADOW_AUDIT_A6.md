# Native topic quality audit — A6

**Статус:** ❓ технически неполный quality sample  
**Authority:** запрещена

Единственный live run целый и честный: 33 `A6_CASE`, один `A6_SUMMARY`, `A6_EXIT_CODE=1` (raw L108).  
Однако run **не является** полноценной оценкой всех 33 frozen кейсов: семь вызовов не вернули валидный `TurnPlan`, harness зафиксировал `planner_unavailable`.  
На **scoreable** подмножестве (26 планов) topic mismatches не обнаружены; качество topic на unavailable кейсах **неизмеримо** из этого raw.

---

## 1. Provenance

| Поле | Значение |
|------|----------|
| A5 native topic shadow | `8662300` |
| Frozen A6 matrix | `cd562fe` — `evals/v5/demo/topic_shadow_matrix.json` |
| Matrix git-blob hash | `dc356c9c738fb80a10cf0035508d7e8c8247979d` |
| Preservation hash | `c2072ca74c2da73bf657d793195d2eb6c8ba7bd5` |
| A6 harness | `952c50a` — `evals/v5/run_topic_shadow_eval.py` |
| A6 live governance | `307390d` |
| A6 audit governance | `02a169b` |
| Raw artifact | `eval_topic_shadow_a6_last.txt` (UTF-16 LE, gitignored) |
| Raw SHA256 | `2EF96AB8660657501137B0A6880E7EA54594E02417197F031BE1BCE2D9D5A40A` |
| Raw size | 77 262 bytes, 108 lines |
| Live attempts | **1** |
| `A6_CASE` lines | 33 (raw L3 … raw L106) |
| `A6_SUMMARY` | 1 (raw L107) |
| `A6_EXIT_CODE` | `1` (raw L108) |
| Observed time window (raw timestamps only) | `2026-07-13T12:03:36.539Z` (raw L1) … `2026-07-13T12:04:16.441Z` (raw L105) |

---

## 2. Методика

- Direct production `plan_turn(question, None, "demo")` — один вызов на case, без retry (`evals/v5/run_topic_shadow_eval.py`, harness `952c50a`).
- Порядок cases — frozen matrix (`evals/v5/demo/topic_shadow_matrix.json`).
- Observed topic — только `TurnPlan.topic` после успешной валидации; нормализация trim + lowercase.
- Confidence — только `TurnPlan.topic_confidence`, descriptive; не gate, не authority.
- Denominator frozen = **33**; skipped = 0.
- Downstream `/ask`, routing, evidence, composer, UI **не измерялись**.
- Audit оценивает только native topic classification на frozen matrix, не качество ответов бота.

---

## 3. Integrity

| Check | Result | raw ref |
|-------|--------|---------|
| Indices 1..33, no gaps/dupes | ✓ | parsed from raw L3–L106 |
| Frozen case order | ✓ | case ids match matrix order |
| First case | `topic_a6_01_clinic_payment` | raw L3 |
| Last case | `topic_a6_33_null_options` | raw L106 |
| `A6_SUMMARY` count | 1 | raw L107 |
| Second summary / second index=1 | absent | — |
| `A6_EXIT_CODE` | `1` | raw L108 |
| Live attempts | 1 | governance + single artifact |
| Raw SHA256 | `2EF96AB…D5A40A` | unchanged read-only |
| Matrix / preservation hashes | frozen values above | post-audit unchanged |
| Tracked tree | clean (audit-doc only, uncommitted) | — |

`passed + failed + errors = 26 + 0 + 7 = 33` (raw L107). `skipped = 0`.

---

## 4. Главная сводка — coverage vs correctness

**Нельзя** интерпретировать `26/33` (78.79%) как чистую classifier accuracy: семь строк не получили scoreable plan.

| metric | value | допустимая интерпретация |
|--------|------:|--------------------------|
| frozen total | 33 | полный denominator |
| scoreable plans | 26 | coverage **26/33 = 78.79%** |
| unavailable | 7 | не получили валидный `TurnPlan` |
| exact among scoreable | **26/26** | на доступной части mismatch **не найден** |
| topic mismatch (FAIL) | 0 | не доказывает качество unavailable кейсов |
| invalid / out-of-taxonomy | 0 | raw L107 |
| skipped | 0 | raw L107 |
| frozen overall exact | 26/33 (rate 0.7879) | **exact coverage over frozen denominator**, не полная accuracy |

---

## 5. Per-topic coverage

| group | total | scoreable | exact | unavailable | coverage | exact among scoreable |
|-------|------:|----------:|------:|------------:|---------:|----------------------|
| clinic | 3 | 3 | 3 | 0 | 100% | 3/3 (100%) |
| doctors | 3 | **0** | 0 | 3 | 0% | **n/a** |
| extraction | 3 | 2 | 2 | 1 | 66.67% | 2/2 (100%) |
| implantation | 3 | 3 | 3 | 0 | 100% | 3/3 (100%) |
| orthodontics | 3 | 3 | 3 | 0 | 100% | 3/3 (100%) |
| periodontology | 3 | 3 | 3 | 0 | 100% | 3/3 (100%) |
| prosthetics | 3 | 3 | 3 | 0 | 100% | 3/3 (100%) |
| treatment | 3 | 3 | 3 | 0 | 100% | 3/3 (100%) |
| whitening | 3 | 3 | 3 | 0 | 100% | 3/3 (100%) |
| ambiguous null | 6 | 3 | 3 | 3 | 50% | 3/3 (100%) |

Для **doctors** exact rate among scoreable = **n/a** (scoreable = 0), не `0%` и не `100%`.

Harness per-topic summary в raw L107 согласуется: doctors `matched=0, total=3`; ambiguous `matched=3, total=6`.

---

## 6. Seven unavailable cases

Общая цепочка для всех семи:

```text
LLM payload был отклонён TurnPlan validation из-за aspects=[];
plan_turn вернул None;
harness корректно записал planner_unavailable.
```

Контракт: `contracts/turn_plan.py` L39 — `aspects: list[AspectKind] = Field(min_length=1)`.

**Ограничение доказательства:**

```text
Raw не сохраняет валидированное значение topic из отклонённого payload,
поэтому нельзя утверждать, был topic в этих семи ответах правильным,
неправильным или null.
```

| index | case id | expected | harness | validation field | raw refs |
|------:|---------|----------|---------|------------------|----------|
| 4 | `topic_a6_04_doctors_overview` | doctors | ERROR / `planner_unavailable` | `aspects` (empty list) | llm_error L11, `turn_planner_failed` L12, `A6_CASE` L13 |
| 5 | `topic_a6_05_doctors_named` | doctors | ERROR / `planner_unavailable` | `aspects` | llm_error L15, `turn_planner_failed` L16, `A6_CASE` L17 |
| 6 | `topic_a6_06_doctors_implants` | doctors | ERROR / `planner_unavailable` | `aspects` | llm_error L19, `turn_planner_failed` L20, `A6_CASE` L21 |
| 9 | `topic_a6_09_extraction_aftercare` | extraction | ERROR / `planner_unavailable` | `aspects` | llm_error L29, `turn_planner_failed` L30, `A6_CASE` L31 |
| 28 | `topic_a6_28_null_general_price` | null | ERROR / `planner_unavailable` | `aspects` | llm_error L87, `turn_planner_failed` L88, `A6_CASE` L89 |
| 30 | `topic_a6_30_null_booking` | null | ERROR / `planner_unavailable` | `aspects` | llm_error L94, `turn_planner_failed` L95, `A6_CASE` L96 |
| 31 | `topic_a6_31_null_pain` | null | ERROR / `planner_unavailable` | `aspects` | llm_error L98, `turn_planner_failed` L99, `A6_CASE` L100 |

Стабильное сообщение validation (все семь): `aspects: List should have at least 1 item` (см. `turn_planner_failed` lines above).

`observed_topic=null` у unavailable — **не** фактический LLM topic; harness не присваивает topic отклонённому payload.

---

## 7. Confusion matrix — ненулевые cells

Источник: `A6_SUMMARY` raw L107. Сумма = **33**.

| expected → observed | count |
|---------------------|------:|
| clinic → clinic | 3 |
| doctors → `__planner_unavailable__` | 3 |
| extraction → extraction | 2 |
| extraction → `__planner_unavailable__` | 1 |
| implantation → implantation | 3 |
| orthodontics → orthodontics | 3 |
| periodontology → periodontology | 3 |
| prosthetics → prosthetics | 3 |
| treatment → treatment | 3 |
| whitening → whitening | 3 |
| `__null__` → `__null__` | 3 |
| `__null__` → `__planner_unavailable__` | 3 |

Unavailable отображаются в `__planner_unavailable__`, **не** как observed null.

---

## 8. Confidence — descriptive only

Источник: `A6_SUMMARY` raw L107.

| bucket | count | min | max | mean |
|--------|------:|-----|-----|------:|
| correct | 26 | 0.0 | 1.0 | 0.8692 |
| incorrect | 0 | — | — | — |
| invalid | 0 | — | — | — |

Три genuine null exact-match (indices 29, 32, 33) входят в **correct** с `topic_confidence=0.0`:

| index | case id | raw ref |
|------:|---------|---------|
| 29 | `topic_a6_29_null_choice` | raw L92 |
| 32 | `topic_a6_32_null_more` | raw L103 |
| 33 | `topic_a6_33_null_options` | raw L106 |

Семь unavailable **не имеют** confidence (`topic_confidence=null` в `A6_CASE`).

**Явно:**

- self-reported confidence **не калибрована**;
- из n=26 нельзя выбирать threshold;
- mean **не является** вероятностью правильности;
- confidence **не разрешает** authority.

---

## 9. Что доказано / не доказано

### Доказано

- Harness и raw integrity (33 cases, 1 summary, 1 attempt, frozen hashes).
- **26/26** scoreable topic values exact на frozen expectations.
- **Zero** observed topic mismatches на scoreable subset (`failed=0`, raw L107).
- Семь all-or-nothing rejections связаны с `aspects=[]` → `TurnPlan` validation → `plan_turn` → `None` (raw refs §6).
- Topic по-прежнему **не влияет** на product routing (shadow-only scope A6).

### Не доказано

- Качество topic на **doctors** (0 scoreable).
- Качество topic на четырёх остальных unavailable cases (1 extraction + 3 ambiguous).
- 100% accuracy на полных 33.
- Calibration / threshold suitability.
- Качество product answers, evidence, UI.
- Готовность к topic authority.

---

## 10. Архитектурный вывод

A6 обнаружил **coupling**: scoreability native `topic` зависит от валидности unrelated legacy field `aspects`.  
All-or-nothing `TurnPlan` validation мешает field-level наблюдаемости: при `aspects=[]` весь plan отбрасывается, topic из того же JSON не становится scoreable.

**Не рекомендуется** (вне scope A6, без отдельного design review):

- простое ослабление `aspects: Field(min_length=1)` в `contracts/turn_plan.py` L39;
- prompt-hardcode `aspects=["overview"]` для doctors/ambiguous кейсов.

Риск: текущие fail-open product paths (planner validation fail → resolver без planner-owned plan) могут смениться на planner-owned path и **изменить ответы**.

Повтор A6 без архитектурного изменения **не закрывает** пробел doctors/unavailable и запрещён one-run contract (первый raw сохраняется).

---

## 11. Рекомендация — A7 (будущий checkpoint only)

Отдельный **A7 contract/design checkpoint** (shadow-only, без реализации в этом документе):

```text
Field-level planner outcome / field_errors, shadow-only:
валидный topic может быть наблюдаем независимо от ошибки aspects,
но legacy TurnPlan eligibility и текущий product fail-open сохраняются.
```

Границы рекомендации:

- один существующий LLM-call;
- без нового topic classifier;
- без topic authority;
- без автоматического `aspects=["overview"]`;
- без изменения `turn_plan_to_decision_frame`, route/evidence/composer/UI;
- текущие семь product paths остаются прежними;
- новый A6 rerun — только после отдельного spec/review и с сохранением первого raw.

Полный A7 API **не проектируется** здесь; код **не пишется**.

---

## 12. Raw line reference index

| fact | raw line |
|------|----------|
| First planner usage log | L1 |
| First `A6_CASE` (`topic_a6_01_clinic_payment`, index 1) | L3 |
| First unavailable (`topic_a6_04_doctors_overview`, index 4) | L13 |
| `A6_SUMMARY` | L107 |
| Last `A6_CASE` (`topic_a6_33_null_options`, index 33) | L106 |
| `A6_EXIT_CODE=1` | L108 |

Line numbers — по фактическому UTF-16 файлу `eval_topic_shadow_a6_last.txt` (108 lines). Нумерация read-only; SHA256 raw не изменялся.
