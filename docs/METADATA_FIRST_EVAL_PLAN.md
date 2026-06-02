# Metadata-First — план eval (Phase 1–3)

**Дата:** 2026-06-02  
**Статус Phase 1:** ✅ inventory + design (этот документ)  
**Статус Phase 2:** ✅ реализовано — отчёт **`docs/METADATA_FIRST_EVAL_PHASE2_REPORT.md`** (baseline golden=27, smoke=17)  
**Статус Этап 3 (CI):** ✅ `.github/workflows/ci.yml`  
**Статус Phase 3 (smoke):** ✅ первая волна — baseline smoke=33 (2026-06-02)

**Связанные документы:** `METADATA_FIRST_V1.md`, `METADATA_FIRST_V1_READINESS.md`, `evals/v5/README.md`, `evals/routing_smoke.md`.

---

## Краткий вывод

1. **Три клиента в базе есть** (demo 48 md, cesi 48, nikadent 45), но **eval сейчас в основном demo** — в `e2e_smoke.json` только 2 явных multiclient-кейса (contacts cesi/nikadent).
2. **41 doc_id общий** для всех трёх — FAQ/pricing/service golden можно гонять на all 3 одним вопросом.
3. **Контакты, врачи по ФИО, comparison** — только per-client (разный адрес, разные персоны, comparison только у demo).
4. **Phase 2** — 12–15 metadata-first golden + 12–18 critical smoke + минимальное расширение runner (обратно совместимо).
5. **Phase 3** — doctors, больше multiclient, layer/unit, замена хрупких `must_contain` — без раздувания дубликатов.

---

# Phase 1 — Inventory и design

## 1.1. Сводка контента по клиентам

| doc_type | demo | cesi | nikadent |
|----------|------|------|----------|
| comparison | 1 | 0 | 0 |
| contacts | 1 | 1 | 1 |
| doctor | 7 | 8 | 5 |
| faq | 7 | 7 | 7 |
| info | 12 | 12 | 12 |
| pricing | 3 | 3 | 3 |
| service | 17 | 17 | 17 |
| **Итого md** | **48** | **48** | **45** |

**Общее ядро:** 41 одинаковый `doc_id` на demo / cesi / nikadent.

**Только demo:** `comparison__implant_vs_bridge` + 6 карточек врачей demo.

**Только cesi:** 6 карточек врачей cesi (+ `doctors__doctor__kadiyev` — свой контент).

**Только nikadent:** 3 карточки врачей nikadent (+ `kadiyev` с другим профилем, чем в cesi).

---

## 1.2. Списки по категориям (общие doc_id)

### FAQ (implantation, все 3 клиента)

| doc_id | topic | subtopic |
|--------|-------|----------|
| `implantation__faq__cost` | implantation | cost |
| `implantation__faq__duration` | implantation | duration |
| `implantation__faq__osseointegration` | implantation | osseointegration |
| `implantation__faq__pain` | implantation | pain |
| `implantation__faq__safety` | implantation | safety |
| `implantation__faq__tooth_loss` | implantation | tooth_loss |
| `implantation__faq__tooth_one_day` | implantation | tooth_one_day |

### Info (clinic + implantation)

**Clinic:** `clinic__info__advantages`, `consultation`, `payment_terms`, `technology`, `warranty`  
**Implantation:** `implantation__info__aftercare`, `bone_graft`, `contraindications`, `curator`, `implant_systems`, `methods_overview`, `steps`

### Pricing

| doc_id | subtopic |
|--------|----------|
| `implantation__pricing__implants` | implants |
| `implantation__pricing__all_on_4` | all_on_4 |
| `implantation__pricing__all_on_6` | all_on_6 |

### Service (17 doc_id)

`extraction__service__tooth_extraction`, 6× `implantation__service__*`, `orthodontics__service__aligners`, `periodontology__service__periodontitis`, 5× `prosthetics__service__*`, 3× `treatment__service__*`

### Comparison (только demo)

| doc_id | doc_type | topic | subtopic |
|--------|----------|-------|----------|
| `comparison__implant_vs_bridge` | comparison | implantation | implant_vs_bridge |

**suggest_h3:** `esli-net-odnogo-zuba`, `kogda-chashche-vybirayut-implant`, `kogda-most-mozhet-byt-razumnym-variantom` — совпадают с `{#id}` в теле md.

### Contacts (один doc_id, разный текст)

| client | doc_id | Сигналы в контенте (для eval) |
|--------|--------|----------------------------------|
| demo | `clinic__info__contacts` | Москва, Тверская, +7 (495)… |
| cesi | `clinic__info__contacts` | Елизово, Ленина 15-а, +7 (4152)… |
| nikadent | `clinic__info__contacts` | Елизово, филиалы Рябикова / Пограничная |

> **Важно:** три разных адреса — это **три отдельных кейса** с разным `client_id`, а не один тест «на всех сразу». Один вопрос («Где вы находитесь?») + `client_id=cesi` → «елизово», не «тверск».

---

## 1.3. service_catalog.json (одинаковая структура × 3)

| Метрика | Значение |
|---------|----------|
| Всего services | 18 (active=18) |
| С `md_entry_ref` | 16 |
| Без md | `tomography`, `professional_whitening` |
| С `price_ref` | 4: `classic`, `one_stage`, `all_on_4`, `all_on_6` |
| С `concern_ref` | 5: те же 4 + `temporary_teeth` → `implantation__faq__cost.md#korotko` |

**price_ref (demo = cesi = nikadent):**

| service_id | price_ref |
|------------|-----------|
| classic | `implantation__pricing__implants.md#korotko` |
| one_stage | `implantation__pricing__implants.md#korotko` |
| all_on_4 | `implantation__pricing__all_on_4.md#korotko` |
| all_on_6 | `implantation__pricing__all_on_6.md#korotko` |

---

## 1.4. Врачи по клиентам (факт контента)

### demo

| doc_id | position | services (catalog ids) |
|--------|----------|------------------------|
| `doctors__doctor__volkov` | Главный врач, хирург, имплантолог | classic, one_stage, all_on_4, all_on_6, temporary_teeth, tooth_extraction |
| `doctors__doctor__orlov` | Врач-имплантолог | classic, one_stage, all_on_4, all_on_6, temporary_teeth, implant_supported_prosthetics |
| `doctors__doctor__kuznetsov` | Врач-стоматолог-ортопед | crowns, veneers, all_on_4/6, prosthetics |
| `doctors__doctor__fedorova` | Врач-стоматолог-терапевт | caries, pulpitis, teeth_treatment, veneers, zirconia_crowns |
| `doctors__doctor__grigoriev` | Врач-пародонтолог | periodontitis |
| `doctors__doctor__morozova` | Врач-ортодонт | aligners |
| `doctors__doctor__overview` | обзор | aliases «кто делает имплантацию» |

### cesi

| doc_id | position | Имплант-релевантность |
|--------|----------|------------------------|
| `doctors__doctor__moiseev` | Хирург-имплантолог | strong |
| `doctors__doctor__khan` | Хирург-имплантолог, главный врач | strong |
| `doctors__doctor__kadiyev` | Хирург-имплантолог | strong |
| `doctors__doctor__larin`, `boyarshina` | Стоматолог-ортопед | prosthetics |
| `doctors__doctor__goltsov` | Стоматолог-терапевт | therapy |
| `doctors__doctor__krivonosov` | Стоматолог-ортодонт | aligners |
| `doctors__doctor__overview` | обзор | strong для «кто по имплантам» |

### nikadent

| doc_id | position | Имплант-релевантность |
|--------|----------|------------------------|
| `doctors__doctor__kadiyev` | Стоматолог, имплантолог, хирург | strong |
| `doctors__doctor__minkov` | Стоматолог-ортопед | prosthetics |
| `doctors__doctor__danilov`, `gadzhimuradov` | Стоматолог (терапия) | weak для имплант-вопросов |
| `doctors__doctor__overview` | обзор | medium |

---

## 1.5. suggest_h3 / suggest_refs / anchors

| Поле | Покрытие |
|------|----------|
| `suggest_h3` | ~28–29 md на клиента; comparison-doc — эталон |
| `suggest_refs` | только `implantation__info__steps.md` (все 3 клиента) |
| `#korotko` | почти все content md |
| h3 `{#id}` | comparison + многие service/faq/info |

---

## 1.6. Матрица testability (Phase 1)

| Сценарий | demo | cesi | nikadent | evidence |
|----------|------|------|----------|----------|
| **contacts** | strong | strong | strong | `clinic__info__contacts` |
| **price_lookup** | strong | medium | medium | pricing md + catalog `price_ref` |
| **price_concern** | medium | medium | medium | `implantation__faq__cost` + `concern_ref` |
| **content faq/process** | strong | strong | strong | 7 FAQ + info/steps; `routing_smoke.md` |
| **doctors** | strong | strong | medium | overview + персональные md |
| **lead/booking** | strong | strong | strong | template `lead_flow`, не doc_id |
| **continuation/pending** | medium | weak | weak | нужен `E2E_USE_TEST_CLIENT=1` |
| **comparison** | medium | not_testable_yet | not_testable_yet | comparison md только demo |
| **cross-topic confusion** | weak | weak | weak | нет dedicated comparison/pricing doc |
| **multiclient** | — | strong (contacts) | strong (contacts) | 2 кейса в e2e |

**Пробел инфраструктуры (as-is):**

| Что проверить | Phase 2 сразу | Нужна доработка runner / API |
|---------------|---------------|------------------------------|
| `expected_route` | ✅ `run_e2e_smoke.py` | — |
| `expected_doc_id` | ✅ derive из `meta.file` (без `.md`) | опционально `meta.doc_id` |
| `forbidden_doc_id` | ✅ тот же derive | — |
| `expected_query_mode` / `expected_service_topic` | layer eval (`resolver_golden`) | e2e — только если пробросить в `meta` |
| `expected_doc_type` | ❌ | `selected_doc_type` в `request.ctx` / `turn_complete`, **не** в публичном `/ask` |
| `expected_fallback_used` | ❌ | узкий флаг в retrieval debug (см. §1.8.1), не `low_score_fallback` |

---

## 1.7. Текущее состояние eval (as-is)

| Файл | Кейсов | Multiclient |
|------|--------|-------------|
| `evals/v5/e2e_smoke.json` | 54 | 2 (`smoke_cesi_contacts_address`, `smoke_nikadent_contacts_address`) |
| `evals/v5/resolver_golden.json` | 44 | нет `client_id` |
| `evals/routing_smoke.md` | ~20 | doc_id-ориентирован, demo-контекст |
| `tests/test_metadata_first_scope.py` | 2 unit | candidate_builder / soft_scope |

**Default client:** `demo` (`CLIENT_ID` env или отсутствие поля в кейсе).

---

## 1.8. Proposal — формат кейса metadata-first

### 1.8.1. Семантика `fallback_used` (код, не «общий откат»)

В `core/candidate_builder.py` telemetry `fallback_used: true` выставляется **только** когда:

- Resolver дал `query_mode=comparison`, **и**
- в corpus клиента **нет** comparison-doc для `service_topic` (`comparison_docs_for_topic=false`).

Тогда metadata-first **не** делает comparison-prefer, и retrieval идёт обычным пулом. Флаг попадает в `request.ctx` через `merge_retrieval_debug_meta` → `metadata_first_turn_details()` / `turn_complete`.

**Это не:**

- `low_score_fallback` / broad arbiter / «бот расширил retrieval»;
- любой fallback catalog vs chunk.

Eval-поле `expected_fallback_used` в Phase 2 имеет смысл **только** для comparison-miss сценариев (cesi/nika) и проверяется через **in-proc / test hook** к `request.ctx` или логам — **не** через публичный `meta` ответа `/ask`, пока поле туда не проброшено.

### 1.8.2. Жёсткие поля — два уровня

**A. Phase 2 — можно проверить без смены API `/ask`**

| Поле | Назначение |
|------|------------|
| `expected_route` | orch/service route (как сейчас) |
| `expected_route_any` | ambiguous routes |
| `expected_doc_id` | выбранный документ (`meta.file` → stem) |
| `expected_doc_id_any` | список допустимых **doc_id** (не doc_type) |
| `forbidden_doc_id` | запрещённые doc_id |
| `forbidden_doc_type` | запрещённые doc_type (derive type из corpus по file stem) |
| `expected_query_mode` | Resolver layer (`run_layer_eval.py`) |
| `expected_service_topic` | Resolver layer |

**B. Phase 2+ — после проброса telemetry в runner / test meta**

| Поле | Назначение |
|------|------------|
| `expected_doc_type` | faq / service / pricing / comparison / contacts / doctor — источник: `selected_doc_type` в ctx |
| `expected_doc_type_any` | OR по типам, если doc_id плавает |
| `expected_fallback_used` | **только** comparison-doc miss (`candidate_builder` telemetry) |

### Мягкие поля

| Поле | Назначение |
|------|------------|
| `answer_signals_any` | 2+ корня из `#korotko`, не одно слово |
| `answer_signals_all` | все обязательны (редко) |
| `must_match_any_regex` | вариативные формулировки |
| `must_not_contain` | цена в FAQ, чужой город в multiclient |

### Пример (schema)

```json
{
  "id": "mf_faq_osseo",
  "client_id": "demo",
  "question": "какая приживаемость имплантов?",
  "expected_route": "retrieval_chunk",
  "expected_doc_id": "implantation__faq__osseointegration",
  "forbidden_doc_id": ["implantation__service__classic"],
  "answer_signals_any": ["прижив", "остеоинтеграц"],
  "must_not_contain": ["₽", "руб"],
  "testability": "strong",
  "evidence": "clients/demo/md/implantation__faq__osseointegration.md",
  "_phase2_plus_optional": {
    "expected_doc_type": "faq",
    "expected_query_mode": "specific",
    "expected_service_topic": "implantation"
  }
}
```

### Multiclient — два паттерна

1. **Shared case:** один `id`, поле `clients: ["demo","cesi","nikadent"]` — runner дублирует прогон (Phase 2).
2. **Per-client case:** явный `client_id` + client-specific `answer_signals_any` (contacts, врачи по имени).

---

# Phase 2 — Первая волна (реализация)

**Цель:** минимальный, но содержательный набор; не ломать `e2e_smoke.json` целиком.

## 2.1. Deliverables

| Артефакт | Действие |
|----------|----------|
| `evals/v5/metadata_first_golden.json` | **новый** — 12–15 кейсов |
| `evals/v5/metadata_first_smoke.json` | **новый** — 12–18 critical smoke (или slim-подмножество + link из README) |
| `evals/v5/run_metadata_first_eval.py` | **новый** runner или расширение `run_e2e_smoke.py` |
| `evals/v5/run_e2e_smoke.py` | **расширение** — optional fields, backward compatible |
| `evals/v5/README.md` | описание новых полей и команд |
| `METADATA_FIRST_V1_READINESS.md` | §10 evals → ✅ Phase 2 |

## 2.2. Metadata-first golden (12–15 кейсов)

**Файл:** `evals/v5/metadata_first_golden.json`  
**Уровень eval:** 2–3 (e2e с assert doc_id или in-proc + `meta.file`).

| # | id (draft) | client(s) | focus | expected_doc_id | testability |
|---|------------|-----------|-------|-----------------|-------------|
| 1 | `mf_contacts_demo` | demo | contacts | `clinic__info__contacts` | strong |
| 2 | `mf_contacts_cesi` | cesi | contacts | `clinic__info__contacts` | strong |
| 3 | `mf_contacts_nikadent` | nikadent | contacts | `clinic__info__contacts` | strong |
| 4 | `mf_price_all_on_4` | all 3 | price_lookup | `implantation__pricing__all_on_4` | strong |
| 5 | `mf_price_classic` | all 3 | price_lookup | `implantation__pricing__implants` | strong |
| 6 | `mf_concern_cost` | all 3 | price_concern | `implantation__faq__cost` | medium |
| 7 | `mf_faq_osseo` | all 3 | faq vs service | `implantation__faq__osseointegration` | strong |
| 8 | `mf_faq_pain` | all 3 | faq vs service | `implantation__faq__pain` | strong |
| 9 | `mf_info_bone_graft` | all 3 | info/specific | `implantation__info__bone_graft` | strong |
| 10 | `mf_service_classic_overview` | all 3 | service overview | `implantation__service__classic` | medium |
| 11 | `mf_comparison_hit` | demo | comparison hit | `comparison__implant_vs_bridge` | medium |
| 12 | `mf_comparison_miss_cesi` | cesi | comparison miss → RAG | `forbidden_doc_type: ["comparison"]`; `expected_fallback_used: true` (in-proc ctx); route + signals, без жёсткого doc_id | medium |
| 13 | `mf_wrong_topic_comparison` | demo | wrong-topic must not win | `forbidden_doc_type: ["comparison"]` при query про aligners; unit: `test_comparison_wrong_topic_*` | medium |
| 14 | `mf_comparison_fallback_telemetry` | cesi | `fallback_used` telemetry | in-proc: `query_mode=comparison` + нет comparison md → ctx `fallback_used=true` | weak (layer/in-proc, не public smoke) |

**Resolver-only (без doc_id):** часть полей дублирует `resolver_golden.json` — в Phase 2 **не копировать все 44**, а добавить 3–4 comparison/price query_mode кейса, если их нет.

## 2.3. Critical smoke (12–18 кейсов)

**Файл:** `evals/v5/metadata_first_smoke.json` (отдельно от полного `e2e_smoke.json`).

**Принцип:** взять проверенные id из текущего smoke + новые doc_id-asserts; **не** тащить ingress/handoff/noise/multi-turn v4 debt.

| Группа | id (из e2e или новый) | count |
|--------|------------------------|-------|
| contacts | `smoke_contacts_phone`, `smoke_contacts_address`, `smoke_cesi_contacts_address`, `smoke_nikadent_contacts_address` | 4 |
| price_lookup | `smoke_price_all_on_4`, `smoke_price_classic` | 2 |
| price_concern | `smoke_price_concern_expensive`, `smoke_price_concern_why` | 2 |
| lead/booking | `smoke_booking_want`, `smoke_booking_today` | 2 |
| continuation/pending | `smoke_pending_lead_offer_no`, `smoke_pending_lead_offer_yes` | 2 |
| comparison | `smoke_comparison_implant_vs_bridge` | 1 |
| cross-topic | `smoke_cross_topic_veneers`, `smoke_content_impl_pain` (FAQ не service) | 2 |
| content sanity | `smoke_content_impl_osseointegration`, `smoke_content_impl_contra` | 2 |

**Итого:** ~17 кейсов. Multi-turn и `known_v4_failures` — **вне** Phase 2 smoke.

## 2.4. Расширение runner (обратно совместимо)

Добавить в `run_e2e_smoke.py` (и/или `run_metadata_first_eval.py`) **optional** проверки:

```python
# derive doc_id — не ломает старые кейсы
def _doc_id_from_meta(meta: dict) -> str:
    if meta.get("doc_id"):
        return str(meta["doc_id"]).strip()
    f = str(meta.get("file") or "").strip()
    return f.removesuffix(".md") if f else ""
```

| Новое поле | Phase | Поведение если отсутствует |
|------------|-------|----------------------------|
| `expected_doc_id` | 2 | skip |
| `expected_doc_id_any` | 2 | skip; значения — только doc_id |
| `forbidden_doc_id` | 2 | skip |
| `forbidden_doc_type` | 2 | skip; type из corpus index по stem `meta.file` |
| `answer_signals_any` | 2 | OR по списку (мягче одного `must_contain`) |
| `must_match_any_regex` | 2 | skip; re.search CI, any match = pass |
| `expected_doc_type` | 2+ | skip; источник: test hook / `request.ctx`, не публичный `/ask` |
| `expected_doc_type_any` | 2+ | skip |
| `expected_fallback_used` | 2+ | skip; **только** ctx `fallback_used` из `candidate_builder` (comparison miss), не orch `low_score_fallback` |

**Старые поля** `must_contain` / `must_not_contain` / `expected_route` — без изменений.

**Запуск:**

```bash
python evals/v5/run_e2e_smoke.py --client demo
python evals/v5/run_metadata_first_eval.py   # Phase 2
python evals/v5/run_e2e_smoke.py --case-id smoke_cesi_contacts_address
```

## 2.5. Отчёт по прогону Phase 2

После реализации — таблица в PR / комментарии:

- PASS / FAIL / SKIP по каждому id
- baseline для `metadata_first_golden.json` и `metadata_first_smoke.json`
- отдельно: FAIL из `known_v4_failures` (не смешивать с metadata-first baseline)

---

## 2.6. Кейсы, отложенные из Phase 2 (слабая база)

| id / сценарий | Причина отложить | Когда Phase 3+ |
|---------------|-----------------|----------------|
| `smoke_comparison_crown_vs_filling` | нет comparison md | после контента §6 |
| `smoke_comparison_missing_one_tooth` | weak, нет dedicated doc | comparison content |
| comparison hit cesi/nikadent | `not_testable_yet` | comparison md для клиентов |
| `smoke_price_concern_general_no_service` | known v4 failure | после #1.4 |
| `mf_fallback_broad` (low_score как fallback_used) | неверная семантика поля | заменён на `mf_comparison_fallback_telemetry` |
| `smoke_contacts_hours` | weak signals | Phase 3 signals |
| `smoke_doctors_*` | client-specific ФИО | Phase 3 doctors |
| multi-turn smoke (6+ кейсов) | v4 query_rewrite debt | отдельный PR #1.3 |
| ingress / handoff / noise | не metadata-first focus | остаются в full e2e |
| doctor named nikadent (danilov vs implant) | weak implant coverage | content или weak tier |

---

# Phase 3 — Расширение без «болота»

**Цель:** закрыть gaps, layer tests, multiclient — **без** дублирования почти одинаковых вопросов.

## 3.1. Дополнительные smoke (+10–15 max)

| Группа | Что добавить | Лимит |
|--------|--------------|-------|
| doctors | overview all 3; named: demo Orlov, cesi Moiseev, nika Kadiyev | 5 |
| multiclient | price FAQ на cesi/nika (shared doc_id); запрет demo-адреса | 3 |
| faq/process | duration, safety, steps (process query_mode) | 3 |
| cross-topic | extraction vs implant; ortho vs implant (без comparison doc) | 2–3 |

**Не добавлять:** ещё 7 FAQ с тем же assert osseointegration-паттерна.

## 3.2. Unit / layer tests

| Область | Где | Статус |
|---------|-----|--------|
| candidate_builder boosts | `tests/test_candidate_builder.py` | ✅ расширено |
| metadata observability | `tests/test_metadata_first_observability.py` | ✅ ctx / turn_details |
| soft_scope hard path | `tests/test_metadata_first_scope.py` | ✅ + hard scope when soft off |
| alias collision report | CI job `content-lint-and-unit` | ✅ non-blocking inventory |

**Resolver golden:** 44 кейса — layer eval 1, не раздувать в Phase 3 без новых route_intent.

## 3.3. Замена хрупких must_contain

| Было | Станет | Пример |
|------|--------|--------|
| `must_contain: ["корон"]` | `must_match_any_regex: ["корон\\w*", "пломб"]` | crown_vs_filling |
| `must_contain: ["телефон"]` | `answer_signals_any: ["телефон", "+7", "495"]` | contacts phone |
| `must_contain: ["как к вам"]` | оставить (lead template stable) | booking |

Только там, где substring даёт ложные FAIL.

## 3.4. Классификация coverage (зафиксировать в кейсах)

Поле `testability` / `coverage_class` в json:

| Tier | Критерий | В baseline? |
|------|----------|-------------|
| **strong** | stable doc_id + route + client content | да, жёсткий baseline |
| **medium** | doc_id или route может плавать | baseline −1 допуск |
| **weak** | только signals, нет doc_id assert | informational, не блок merge |
| **not_testable_yet** | нет контента у клиента | SKIP, список gaps |

### Gaps in content (not_testable_yet)

| Gap | Клиенты | Действие |
|-----|---------|----------|
| comparison docs | cesi, nikadent | контент §6 METADATA_FIRST_V1 |
| crown vs filling comparison | all | отдельный comparison md или weak RAG |
| nikadent implant doctors depth | nikadent | контент или только overview tests |
| tomography / whitening pricing md | all | catalog card only — price_lookup weak |

---

# Приложение A — Multiclient: как гонять тесты

```
┌─────────────────────────────────────────────────────────┐
│  Shared golden (FAQ, pricing)                           │
│  Один question → clients: [demo, cesi, nikadent]        │
│  Один expected_doc_id                                   │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  Per-client smoke (contacts)                            │
│  Тот же question, разный client_id + answer_signals     │
│  demo: тверск/495  |  cesi: елизово  |  nika: рябиков   │
└─────────────────────────────────────────────────────────┘
```

**CI (рекомендация Phase 2):**

```yaml
# pseudo: 3 job или matrix client_id
- run: python evals/v5/run_metadata_first_eval.py --client demo
- run: python evals/v5/run_metadata_first_eval.py --client cesi
- run: python evals/v5/run_metadata_first_eval.py --client nikadent
```

Shared-кейсы входят в каждый job; per-client — фильтруются по `client_id`.

---

# Приложение B — Связь с eval levels (rules v5)

| Phase | Уровень | Команда |
|-------|---------|---------|
| Phase 2 golden (Resolver fields) | 1 | `run_layer_eval.py --layer resolver` |
| Phase 2 retrieval doc_id | 2 | `run_metadata_first_eval.py` |
| Phase 2 smoke | 3 | `run_e2e_smoke.py` / `metadata_first_smoke.json` |
| Phase 3 linter | 0 | `lint_content.py --client all` |

---

# Changelog

| Дата | Изменение |
|------|-----------|
| 2026-06-02 | Phase 1 inventory + design; планы Phase 2–3 |
| 2026-06-02 | Уточнены `fallback_used`, tier полей eval, кейс comparison_miss_cesi |
