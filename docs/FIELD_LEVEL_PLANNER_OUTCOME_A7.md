# Field-level planner outcome — A7 design contract

**Статус:** design-only (Checkpoint 1) — **без реализации**  
**Authority:** partial `TurnFrame` остаётся shadow/telemetry-only; strict `TurnPlan` сохраняет product ownership  
**Governance:** `f2bceab` (A7 TASK) · A6 audit `4a6c867` · harness `952c50a`

---

## 1. Проблема (A6 evidence)

A6 Live Proof зафиксировал coupling all-or-nothing validation:

| metric | value | источник |
|--------|------:|----------|
| frozen denominator | 33 | `docs/TOPIC_SHADOW_AUDIT_A6.md` §4 |
| scoreable plans | 26 | coverage 26/33 |
| unavailable | 7 | все `planner_unavailable` |
| exact among scoreable | 26/26 | zero topic mismatches |
| doctors scoreable | 0/3 | exact rate **n/a** |

Все семь unavailable связаны с одной цепочкой: LLM вернул `aspects=[]` → `TurnPlan.model_validate()` отклонил весь payload → `plan_turn()` → `None` → shadow `not_available`.  
Raw **не доказывает** topic в отклонённых payload; audit не присваивает им значения.

См. `docs/TOPIC_SHADOW_AUDIT_A6.md` §6–§10. Original raw SHA256 неизменен: `2EF96AB8660657501137B0A6880E7EA54594E02417197F031BE1BCE2D9D5A40A`.

---

## 2. Current runtime (read-only baseline)

### 2.1 Single-call planner

`core/turn_planner_llm.py`:

```text
plan_turn(q, sid, client_id)
  → json.loads(raw_text)
  → _validate_plan(raw)
       → _sanitize_topic_fields(raw)   # topic normalize before full validate
       → TurnPlan.model_validate(plan_raw)   # strict, all-or-nothing
  → on any Exception: turn_planner_failed + return None
```

Ключевые символы: `plan_turn` (~L489), `_validate_plan` (L326–377), `turn_plan_to_decision_frame` (L426–444).

### 2.2 Strict legacy contract

`contracts/turn_plan.py` L39:

```python
aspects: list[AspectKind] = Field(min_length=1)
```

`aspects=[]` → Pydantic `List should have at least 1 item` → exception → `plan_turn` → `None`.  
**A7 design не ослабляет** `min_length=1` на `TurnPlan`.

### 2.3 Product orchestration

`orchestration/resolver_turn.py` `run_resolver_turn` (L35–167):

| `plan_turn` result | product path | shadow |
|--------------------|--------------|--------|
| `TurnPlan` valid | `turn_plan_to_decision_frame` → planner-owned; `turn_planner_used=true` | `record_turn_frame_shadow` → `ok` |
| `None` | `mark_turn_frame_shadow_not_available` → `resolve_with_fallback` (resolver); `turn_planner_used=false` | `not_available` / `turn_plan_missing` |

Fail-open log: `turn_planner_fail_open_to_resolver` (L94–98).

### 2.4 Shadow today

`core/turn_frame_shadow.py`:

- `mark_turn_frame_shadow_not_available()` (L35–42) — при `plan is None`
- `record_turn_frame_shadow(turn_plan, decision_frame)` (L45–81) — только при valid `TurnPlan`
- Статусы: `ok` | `not_available` | `degraded` (нет `partial`)

`core/turn_frame_adapter.py` `build_turn_frame_from_legacy` — строит `TurnFrame` только из **valid** legacy inputs.

### 2.5 TurnFrame contract today

`contracts/turn_frame.py`:

- `FieldMeta`: только `confidence` + `provenance` (L16–22)
- `TurnFrame.aspects`: `Field(min_length=1)` (L50)
- `primary_aspect` обязателен и ∈ `aspects` (L51, L61–64)

Partial-capable shadow **требует** будущего contract slice (A7 Contract checkpoint), не текущего runtime.

---

## 3. Target architecture — выбранный вариант

### 3.1 Dual branch из одного raw JSON

```text
один LLM response (raw dict, immutable copy)
        │
        ├─► [A] field-level builder → partial-capable TurnFrame (shadow only)
        │         per-field FieldMeta: status + error
        │
        └─► [B] strict legacy path → TurnPlan.model_validate() (unchanged rules)
                  ├─ success → legacy_plan (current product input)
                  └─ failure → legacy_plan = None (current fail-open)
```

Обёртка одного вызова:

```text
PlannerAttempt
  legacy_plan: TurnPlan | None      # branch [B] only
  shadow_frame: TurnFrame | None    # branch [A] only
  shadow_status: ok | partial | not_available | degraded
```

**Закон:** валидное поле shadow не уничтожается ошибкой другого поля; strict `TurnPlan` и product path **не ослабляются**.

### 3.2 Backward-compatible public seam

| API | роль |
|-----|------|
| `plan_turn_attempt(...) -> PlannerAttempt` | **новая** internal: один LLM-call, обе ветки |
| `plan_turn(...) -> TurnPlan \| None` | **существующий** wrapper: `return attempt.legacy_plan` |

Запрещено: `plan_turn` + отдельный attempt = два LLM-call.

Runtime wiring (будущий A7 Shadow checkpoint): один вызов `plan_turn_attempt`, product читает только `legacy_plan`, observability — `shadow_frame` + `shadow_status`.

### 3.3 Rejected alternatives

| вариант | почему не выбран |
|---------|------------------|
| Loosen legacy `TurnPlan.aspects min_length` | меняет eligibility → planner-owned path для `aspects=[]` |
| Force `aspects=["overview"]` in prompt/code | подгоняет unrelated field, скрывает LLM error |
| Topic-only telemetry hook / `TopicObservation` | side channel, не field-level target |
| Second classifier / second LLM-call | latency, cost, второй source of truth |
| Retry on `aspects=[]` | нарушает one-call contract, скрывает degraded rate |
| **Partial TurnFrame + strict legacy branch** | **выбран** — один semantic contract, ownership сохранён |

---

## 4. Partial shadow frame vs strict legacy plan

### 4.1 Разделение ответственности

| слой | источник | влияет на routing/evidence/composer/UI/answer |
|------|----------|-----------------------------------------------|
| **legacy_plan** (`TurnPlan`) | branch [B], unchanged rules | **да** (как сегодня) |
| **shadow_frame** (`TurnFrame`) | branch [A], partial-capable | **нет** — ctx/logs/E2E telemetry only |

Product firewall (обязателен для всех implementation checkpoints):

- `orchestration/resolver_turn.py` продолжает ветвление по `legacy_plan is None` / `is not None` **без** чтения `shadow_frame`
- `turn_plan_to_decision_frame`, `publish_turn_plan`, evidence, composer, widget — **не** импортируют partial frame
- `partial` ≠ успешный legacy plan; `turn_planner_used` остаётся привязан к legacy eligibility

### 4.2 Partial-capable TurnFrame (future contract)

Единый semantic contract `TurnFrame` (не topic-specific side channel):

- `aspects` **может** быть `[]` в shadow frame
- `primary_aspect` **может** быть `None`
- если `primary_aspect is not None` → обязан ∈ `aspects`
- если `aspects=[]` → `primary_aspect=None`
- per-field invalid/missing не ломает весь frame
- partial frame **не** downstream без отдельного authority gate (который A7 **не** вводит)

Строгий `TurnPlan.aspects min_length=1` **без изменений**.

---

## 5. FieldMeta — status / error model

### 5.1 Source of truth

Расширить `FieldMeta` (`contracts/turn_frame.py` L16–22) **в будущем** contract slice:

```text
confidence: float  # 0..1
provenance: str    # stable source id
status: valid | defaulted | missing | invalid
error: str | null  # stable reason from allowlist; null when status != invalid
```

**Один** source of truth: metadata конкретной оси.  
Термин `field_errors` (если нужен telemetry) = детерминированная агрегация всех `FieldMeta(status=invalid)`; **не** второе независимое состояние.

### 5.2 Stable error allowlist (первый slice)

| error | ось | когда |
|-------|-----|-------|
| `aspects_empty` | aspects | raw `[]` |
| `aspects_invalid_type` | aspects | non-list |
| `aspect_not_allowed` | aspects | unknown element |
| `primary_aspect_unavailable` | primary_aspect | empty/invalid aspects |
| `topic_not_allowed` | topic | outside taxonomy |
| `topic_invalid_type` | topic | non-string |
| `topic_confidence_invalid` | topic | out of range / non-number |
| `route_invalid` | intent | invalid route enum |

Не логировать raw exception text, question, answer, history, неизвестные raw topic/aspect values.

---

## 6. PlannerAttempt — operational envelope

Технический envelope **одного** LLM-call; не продуктовый маршрут.

```python
# pseudocode — names may be refined in implementation TASK
class PlannerAttempt:
    legacy_plan: TurnPlan | None
    shadow_frame: TurnFrame | None
    shadow_status: Literal["ok", "partial", "not_available", "degraded"]
```

| shadow_status | условие |
|---------------|---------|
| `ok` | strict legacy plan valid **и** shadow без invalid fields |
| `partial` | parseable JSON object, shadow собран, ≥1 invalid/missing field **или** legacy plan `None` при валидных shadow-осях |
| `not_available` | no parseable JSON object / LLM unavailable |
| `degraded` | builder/serialization internal error; product ход не падает |

**Нельзя** маркировать `partial` как `ok`.

Текущие shadow constants (`core/turn_frame_shadow.py` L17–22) дополняются `partial` на wiring checkpoint; product semantics `not_available`/`degraded` сохраняются.

---

## 7. Field-level semantics (builder rules)

Builder читает **immutable copy** raw dict. **Не** мутирует raw перед strict legacy validation. **Не** «чинит» raw.

### 7.1 Topic

- taxonomy: A5 `load_client_topic_taxonomy` + frozen client frontmatter (как `core/turn_planner_llm._sanitize_topic_fields`)
- valid allowed string → value, confidence, provenance `turn_plan.raw.topic`, status `valid`
- missing/null + confidence 0 → `None`, status `missing`
- unknown / non-string / bad confidence → safe `None`/0, status `invalid`, stable error
- **не** выводить topic из `service_id`, doc_id, filename, regex
- native topic остаётся **shadow-only** (product `DecisionFrame.service_topic` по-прежнему из catalog mapping в `turn_plan_to_decision_frame`)

### 7.2 Aspects

- raw list of allowed `AspectKind`
- valid non-empty → status `valid`
- `[]` → value `[]`, status `invalid`, error `aspects_empty`
- non-list → `[]`, `invalid`, `aspects_invalid_type`
- unknown element → status `invalid`, `aspect_not_allowed` (не молча удалять)
- **не** подставлять `overview` автоматически
- **не** выводить aspect из question regex

### 7.3 Primary aspect

- только `aspects[0]` после валидной ordered list (первый slice)
- invalid/empty aspects → `None`, status `invalid` или `missing`, error `primary_aspect_unavailable`

### 7.4 Intent и остальные оси (pattern)

Общий паттерн для будущих slices; первый implementation slice **не обязан** мигрировать все:

| ось | invalid handling (target) |
|-----|---------------------------|
| route/intent | `unknown` + field error |
| service_id | catalog check; field error |
| followup_of | catalog/context contract |
| needs_clarify | invalid → default `false` + error |
| patient_situation / brand_filter | field-level, frame survives |
| emotion / specificity / patient_scope | default/missing provenance до своих задач |

---

## 8. Critical product invariant — worked example

Raw payload (A6-class coupling):

```json
{
  "route": "content",
  "aspects": [],
  "topic": "doctors",
  "topic_confidence": 0.95
}
```

**Target первого slice:**

```text
PlannerAttempt.legacy_plan = None
PlannerAttempt.shadow_status = partial
PlannerAttempt.shadow_frame.topic = "doctors"
  topic meta: status=valid, confidence=0.95, provenance=turn_plan.raw.topic
PlannerAttempt.shadow_frame.aspects = []
  aspects meta: status=invalid, error=aspects_empty
PlannerAttempt.shadow_frame.primary_aspect = None
  primary meta: status=invalid, error=primary_aspect_unavailable
```

**Product orchestration — идентично сегодня при `plan_turn() -> None`:**

```text
turn_planner_used = false
mark_turn_frame_shadow → partial (NEW) or dedicated partial recorder
resolve_with_fallback → legacy resolver path
route / decision / evidence / composer / UI / answer — НЕ читают shadow_frame
```

Семь A6 fail-open product routes/answers **не меняются** на regression checkpoint.

---

## 9. Минимальный первый implementation slice

Отдельный кодовый TASK после design review — **только**:

1. Partial-capable `TurnFrame` contract + `FieldMeta` status/error
2. `PlannerAttempt` envelope
3. Field-level extraction для A6 blocker:
   - topic / topic_confidence
   - aspects
   - primary_aspect
   - route/intent (достаточно для `unknown` при ошибке)
4. Strict legacy `TurnPlan` validation **без изменений**
5. Shadow observability получает `partial` frame
6. Product использует только `legacy_plan`

**Не включать** в первый slice: ResponseSpec, evidence assembly, medzone/marketing, route ownership transfer, resolver removal, full TurnPlan field refactor, новый A6 live run.

---

## 10. Telemetry / privacy

- `shadow_status=partial` различим от `ok` / `not_available` / `degraded`
- per-field stable errors; **без** exception text
- **не** логировать raw LLM JSON
- **не** логировать question / answer / history в field-error events
- **не** логировать неизвестные raw topic/aspect values
- full partial `TurnFrame` — только защищённый ctx/E2E path (правила A2)
- widget без `E2E_USE_TEST_CLIENT` **не меняется**
- telemetry sink failure **не ломает** product ход

---

## 11. Product firewall — запрещённые решения

1. Убрать `min_length=1` из legacy `TurnPlan` без eligibility guard
2. Подставлять `aspects=["overview"]` ради валидности
3. Переписать prompt, чтобы LLM всегда выдумывал aspect
4. Второй LLM-call / topic classifier
5. Retry только для `aspects=[]`
6. Сохранять raw LLM JSON в ctx/logs
7. Topic-specific side channel вместо общего `TurnFrame`
8. Читать partial frame в routing / evidence / composer
9. Считать `partial` успешным legacy plan
10. Исправлять семь A6 кейсов тематическими if/regex

AST/firewall acceptance (будущий): downstream modules **не** import/read `shadow_frame` для decisions.

---

## 12. Future acceptance tests (design map, не писать сейчас)

| scenario | expected |
|----------|----------|
| valid full payload | legacy plan + shadow `ok` |
| valid topic + `aspects=[]` | legacy `None` + shadow `partial`, topic valid |
| topic invalid + legacy fields valid | legacy semantics unchanged; topic invalid in shadow |
| malformed / non-object JSON | `not_available`, not `partial` |
| builder `model_dump` error | `degraded`, product continues |
| telemetry emit failure | product continues |
| `plan_turn` wrapper | backward compatible (`legacy_plan` only) |
| runtime | exactly one LLM call |
| raw dict | not mutated between branches |
| stable field errors | no leaks |
| seven fail-open product routes | unchanged answers |
| planner/shadow/contacts/price tests | green |
| smoke/preservation | frozen hashes preserved |
| widget without E2E | unchanged |
| AST scan | partial frame not read downstream |

---

## 13. Migration checkpoints

| # | checkpoint | deliverable |
|---|------------|-------------|
| 1 | **A7 Design** | этот документ (doc-only) |
| 2 | **A7 Contract** | `TurnFrame`/`FieldMeta`/`PlannerAttempt` models + unit tests; **без** runtime wiring |
| 3 | **A7 Planner split** | один raw → partial frame + strict legacy; unit-only |
| 4 | **A7 Shadow wiring** | orchestration: legacy plan as today; partial → telemetry only |
| 5 | **A7 Regression / live proof** | seven paths + smoke/preservation; product output unchanged |
| 6 | **A7 Topic re-audit** | отдельный frozen run, **новое** имя артефакта; первый A6 raw сохраняется |

Каждый пункт — отдельный `TASK.md` / review / commit. **Не** объединять в один diff.

---

## 14. Что принятие design **не** разрешает

- автоматически менять код
- topic authority
- закрыть A6 sample как полный
- повторить A6 live без нового governance
- сделать `TurnFrame` product source of truth
- удалять legacy router/resolver
- начинать marketing stage

---

## 15. Code alignment index (read-only verification)

| файл | сверено для |
|------|-------------|
| `core/turn_planner_llm.py` | `plan_turn`, `_validate_plan`, `_sanitize_topic_fields`, fail-open `None` |
| `contracts/turn_plan.py` | `aspects: Field(min_length=1)`, topic invariants |
| `orchestration/resolver_turn.py` | planner success vs `resolve_with_fallback` |
| `core/turn_frame_shadow.py` | `ok`/`not_available`/`degraded`, ctx keys |
| `core/turn_frame_adapter.py` | `build_turn_frame_from_legacy` (valid plan only today) |
| `contracts/turn_frame.py` | current `FieldMeta`, `TurnFrame` constraints |
| `contracts/decision_frame.py` | product routing contract |
| `docs/TOPIC_SHADOW_AUDIT_A6.md` | 26/33, 7 unavailable, coupling evidence |
| `evals/v5/run_topic_shadow_eval.py` | A6 harness `planner_unavailable` semantics |

---

## 16. Data flow diagram

```text
                    ┌─────────────────────┐
                    │  LLM (one call)     │
                    └──────────┬──────────┘
                               │ raw dict (immutable)
              ┌────────────────┴────────────────┐
              ▼                                 ▼
   field-level builder                  TurnPlan.model_validate
   (partial TurnFrame)                  (strict legacy, unchanged)
              │                                 │
              ▼                                 ▼
   shadow_frame + FieldMeta              legacy_plan | None
   shadow_status: ok|partial|...                │
              │                                 │
              └──────── ctx/telemetry ──────────┼──► product path
                     (read-only)              │    (legacy_plan only)
                                              ▼
                                    planner-owned OR resolver fail-open
                                    (identical to today)
```

---

*End of A7 design contract. Implementation forbidden until separate TASK + checker review per checkpoint.*
