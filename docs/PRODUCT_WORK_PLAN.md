# План работ: умный стоматологический бот (продукт)

**Статус:** план развития (не runtime-контракт). **Этапы 0–3 (demo):** сделаны. **В работе:** этап **3.5** (PriceBook v2). **Следующий после 3.5:** этап **3.6** (lead flow v2), затем **4** (planner-lite).  
**Scope работ:** до отмашки владельца — **только demo** (`clients/demo/`) + общий код; **cesi / nikadent — freeze** (см. `README.md`).  
**Дата:** 2026-06.  
**Источник:** обсуждение архитектуры, 101 вопрос по имплантации, продающие слоты, сложный прайс.

**Парные документы:**

| Документ | Роль |
|----------|------|
| `CURRENT_ARCHITECTURE.md` | Фактический runtime — обновлять при смене пайплайна |
| `MULTICLIENT.md` | Client pack, подключение клиник |
| `ROUTING_MAP.md` | Маршруты вопросов |
| `CLIENT_FILLING_SERVICES_PRICES.md` | Каталог, цены, md |
| `PRICEBOOK_V2.md` | PriceBook v2: схема, сценарии, миграция |
| `IMPLANT_QUESTIONS_COVERAGE.md` | 101 вопрос → контент / логика / отказ |
| `TECH_DEBT.md` | Открытый долг (дубли не копировать — закрывать строки в PR) |
| `drafts/2.md` | Follow-up, guard, aspect_registry (обсуждение → §3.3) |
| `drafts/1.md` | Черновик видения (история обсуждения) |

---

## 1. Цель

Сделать **масштабируемый консультационный бот** для стоматологии (не «RAG по markdown»), который:

- стабильно отвечает на **живые вопросы** пациентов (имплантация — первая эталонная батарея);
- звучит как **эксперт клиники**, а не справочник + кнопка;
- **не врёт** в ценах, гарантиях, акциях;
- подключается к **новой клинике** через грамотный knowledge pack + проверки, без шаманства с алиасами.

**Контент demo-пака (presentation «рыба»):**

- Пакет **`clients/demo/`** — **не прод-контент клиники**, а материал для **презентации и eval**: показать маршруты, слоты, цены, сравнения.
- Черновики md / comparison / faq / catalog / prices для demo **готовит AI в Cursor**; владелец не пишет «с нуля» для demo.
- **Рыба ≠ абстракция:** тексты и цифры должны быть **максимально правдоподобными** — реальная стоматологическая лексика, актуальные протоколы и формулировки, **рыночные цены** (порядок величин Москвы/РФ 2025–2026), согласованные между `prices.json`, `price_offers` и pricing-md.
- Явно не выдавать рыбу за факт конкретной клиники; бренд demo — вымышленный/нейтральный.
- Для **prod-клиентов** (`cesi`, `nikadent`, …) — только контент владельца; demo-рыбу не копировать без адаптации. **Сейчас cesi/nikadent не редактируем** — ждём отмашки; вся продуктовая работа в `clients/demo/`.

**Принципы (не нарушать):**

1. **Eval-first** — сначала golden-набор, потом архитектура.
2. **Не переписывать ядро** — надстройка над каталогом, policy, frontmatter, price flow.
3. **Contract-driven** — слоты ответа и цены собирает код, не «пусть LLM вспомнит».
4. **Один источник генерации** — LLM по одному чанку; доп. блоки — **детерминированный append**.
5. **Multiclient** — без `if client_id`, всё в `clients/{id}/`.
6. **Границы** — диагноз по снимку, арбитраж чужих планов, точная смета без КТ — не автоматизировать.

---

## 2. Текущее состояние (кратко)

### Уже есть

| Слой | Где |
|------|-----|
| Маршрутизация | Resolver, A3 `source_routing`, ingress, policy |
| Услуги | `service_catalog.json`, `md_entry_ref`, `concern_ref` |
| Простые цены | `prices.json` + `format_price_answer_from_item` |
| Объяснение цен | `implantation__pricing__*.md` (бренды, этапы оплаты) |
| Политики | `clinic_policies.yaml` |
| UI ответа | CTA, follow-ups, `consult_nudge` (промпт), empathy |
| **Answer slots** | `contracts/answer_slots.py`, `core/answer_slots.py`, frontmatter в service md (demo) |
| **Сложный прайс** | `price_offers.json`, `core/price_offers.py`, deterministic append в `price_flow` (demo) |
| Контент имплантации | ~24 md в demo, comparison частично |
| Линтер контента | `core/content_linter.py`, `scripts/lint_content.py` |
| Eval | `evals/v5/` smoke + layer |
| Образец слотов | `implantation__service__classic_test.md` (черновик); боевые поля — в `classic`, `all_on_4`, … |

### Главные пробелы

| Пробел | Риск |
|--------|------|
| ~~Нет **answer_slots** в runtime~~ | ✅ этап 2 (demo) |
| ~~`prices.json` плоский; implant-ключи не заполнены~~ | ✅ этап 1 + 3 (demo) |
| ~~Сложный прайс только в md~~ | ✅ этап 3 (demo) |
| Один чанк на ответ | Составные вопросы (цена + рассрочка) неполные |
| Verifier в shadow | Нет gate на цифры и акции |
| `offer` / `promo_note` — заглушка | Акции нестабильны (`pick_relevant_offer` не переведён) |
| Нет eval на 101 вопрос | Регрессии незаметны |
| Comparison md по имплантации мало | All-on-4 vs 6, classic vs one-stage |
| **Lead flow v2** не реализован | slot-first retry; узкий interrupt; overlay paused только chunk-path |
| **Follow-up compat guard** | rewrite есть; guard режет cross-topic (warranty/clinic); нет единого focus |

---

## 3. Целевая архитектура (куда идём)

```
вопрос
→ guards / Resolver / A3 (как сейчас)
→ aspect + subject (topic, service_id) — metadata, не hard route
→ planner-lite (детерминированный, без LLM на MVP)
→ evidence: 1 md-чанк + structured facts (price_offers, policy)
→ Generator (суть, single source)
→ answer assembly: slots (clinic_note, consult_value, promo) + price append
→ verifier gate (tiered)
→ policy → JSON /ask
```

### 3.1 Aspect (question facets)

Помимо **`topic`** и **`service_id`**, у чанков и документов в metadata — **`aspect`**: *тип вопроса* (facets), а не отдельная услуга.

**Примеры aspect (MVP — 8–12, позже 15–25, без раздувания под каждый fail):**

`price`, `duration`, `pain`, `stages`, `included`, `payment`, `warranty`, `contraindications`, `comparison`, `aftercare`, `doctors`, `consultation`, …

**Принципы (важно):**

| Правило | Смысл |
|---------|--------|
| **Не hard route** | `aspect` **не** означает «aspect → один конкретный файл». Это soft signal для retrieval / planner / session, не замена A3 и arbiter |
| **Boost / filter** | При ranking кандидатов: бонус, если `chunk.aspect` совпадает с aspect запроса; при конфликте topic — subject из session |
| **Subject vs aspect в session** | Хранить отдельно: **`last_subject`** `{ topic, service_id, label }` и **`last_aspect`**. Subject — *о чём говорим*; aspect — *какой тип вопроса сейчас* |
| **Follow-up без потери темы** | «Сколько длится протезирование?» → «А это больно?»: subject остаётся `prosthetics` + тот же service, aspect меняется `duration` → `pain` |
| **Не плодить под eval** | Новый aspect — только если повторяется в живых диалогах / матрице 101, а не под один golden-кейс |

**Откуда берётся aspect (MVP):**

1. **Авто из имени / doc_type** при индексации: `faq__pain` → `pain`, `faq__duration` → `duration`, `comparison__*` → `comparison`, `__pricing__` → `price`, …
2. **Ручной override** во frontmatter: `aspect: payment` (если filename неоднозначен).

**Где используется:**

- **Retrieval 2.0** — metadata filter + soft boost вместо regex «вопрос → doc_id»
- **Planner-lite** — выбор append-слотов (`payment_terms` при `payment`, warranty-md при `warranty`) по subject + aspect
- **Dialog context** — Resolver / follow-up: короткая реплика наследует `last_subject`, aspect определяется заново

**Связь с текущим кодом:** pre-stage-2 routing hints (`COMMERCIAL_*`, `CONSULTATION_*`, …) — временный слой; целевой путь — вынести смысл в `aspect` + session, hints сузить (см. `TECH_DEBT.md`).

### 3.2 Lead flow v2 (запись + вопросы по ходу)

**Статус:** согласовано (2026-06); runtime частично не совпадает — `TECH_DEBT.md` → Lead flow v2, детали runtime — `CURRENT_ARCHITECTURE.md` § Lead flow v2.

**Цель:** человек может записаться без «формы-тюрьмы»; на любом шаге — задать вопрос (цена, страх, адрес) или выйти; бот не трактует любую реплику как «плохое имя».

#### Состояния

| Режим | Сессия | Поведение |
|-------|--------|-----------|
| **CONSULT** | нет active lead | Обычный диалог |
| **LEAD_ACTIVE** | collecting_name / phone / confirming_name | Сбор слотов; **intent before slot** |
| **LEAD_PAUSED** | `lead_paused` + `lead_resume_step` | Ответ как CONSULT + bridge + «Продолжить / Отменить» |

Refs: `lead:booking`, `lead:pause`, `lead:resume`, `lead:cancel`.

#### UX: exit доступен vs предложен

**Не путать:** отмена **всегда работает текстом**; кнопки exit **не обязаны** быть на каждом экране (conversion-first).

| Момент | UI | Бэкенд (текст) |
|--------|-----|----------------|
| **Первый экран** после «хочу записаться» | Только вопрос про имя. **Без** «Отменить» / «Не сейчас» | «не хочу», «передумал», «не сейчас» → CONSULT |
| **LEAD_ACTIVE** | Без exit-кнопок по умолчанию; «Задать вопрос» — **не** на первом экране (добавлять по метрикам застревания) | cancel; price / contacts / страх → pause; «задать вопрос» → pause |
| **После retry / сопротивления** | Опционально QR «Задать вопрос» | то же |
| **LEAD_PAUSED** после content-ответа | Bridge + **Продолжить запись** / **Отменить запись** (обязательно) | resume / cancel + синонимы |

**Не смешивать** content-ответ и «как вас зовут» в одной реплике.

**Класс `defer`** («надо подумать», «подумаю»): мягкий выход без slot retry.

#### Порядок turn (LEAD_ACTIVE)

**Главное правило:** любое сообщение — **сначала намерение**, **потом** слот. Slot retry — **последний** resort.

```
1. ref / meta command
2. explicit cancel
3. explicit meta_pause
4. high-confidence slot (имя / телефон)
5. content interrupt → pause + price / contacts / retrieval
6. defer
7. unclear → «Напишите имя или задайте вопрос» (+ опц. QR pause)
```

#### LLM vs deterministic

| Класс | Примеры | Слой |
|-------|---------|------|
| Meta cancel | «не хочу», «передумал» | regex / ref |
| Meta pause | `lead:pause`, «задать вопрос» | ref + синонимы |
| Slot | «Мария», «+7…» | `name_gate`, `extract_phone` |
| Content (явный) | «сколько стоит», «адрес», «а больно?» | `price_intent`, `contacts_intent`, `lead_interrupt` |
| Content (gray) | «я переживаю», «дорого наверное» | structured mini-classifier (Pydantic, temp 0) |
| Unclear | шум, низкий confidence | мягкий retry, **не** «напишите имя» |

**Без LLM:** ref, телефон, имя, cancel/pause, pre-Resolver `explicit_booking_intent`.  
**Fail-loud:** confidence < порога (`routing.yaml`) → `unclear`; не чинить classifier пост-hoc regex.

Целевой контракт: `LeadTurnDecision` (`contracts/`) — `kind` ∈ slot \| meta_* \| content \| defer \| unclear; `content_hint` ∈ price \| contacts \| pain \| generic.

#### Связь с price / planner / policy

| Ситуация | Поведение |
|----------|-----------|
| «Сколько стоит…» в LEAD_ACTIVE | pause → тот же `price_lookup` / PriceAnswerAssembler, не slot retry |
| Price-ответ в LEAD_PAUSED | price-блок + **lead overlay** на **всех** маршрутах (chunk, price, contacts) |
| `promo_note` / commercial facts | не навязывать в bridge; только если пользователь спросил (content path) |
| `booking_intent()` LLM (CTA) | отдельно от lead gate; не дублировать «записаться» поверх paused bridge |
| Planner-lite (этап 4) | subject/aspect для follow-up **в PAUSED**; не заменяет lead turn classifier |

**Lead gate (pre-Resolver):** только `explicit_booking_intent()` (regex); booking LLM для gate **убран** (`TECH_DEBT.md` «Закрыто»).

**Eval (целевое):** `evals/v5/lead_turn_golden.json` — cancel / pause / price-in-lead / defer / unclear; smoke: «боюсь боли», «не хочу записываться» при сборе имени.

### 3.3 Follow-up без aspect_registry (короткие уточнения)

**Статус:** согласовано (2026-06); обсуждение — `drafts/2.md`. Runtime: жёсткий topic/alias guard режет cross-topic кандидаты (напр. warranty при focus=classic) — см. `TECH_DEBT.md` → Follow-up compatibility.

**Диагноз:** бот часто **уже склеивает** контекст (`rewrite`: «гарантия на классическую имплантацию») и **находит** нужный chunk (`clinic__info__warranty`), но **guard отбрасывает** его из‑за `topic=clinic` ≠ `implantation`. Проблема не в «понимании», а в фильтре после retrieval.

**Цель:** короткие follow-up («а гарантия?», «а больно?», «рассрочка?») отвечают по сути, **не уводя** в другую услугу; **без** большого `aspect_registry.yaml` на старте.

#### Принцип (главный)

> **Compatibility guard:** кандидат проходит, если **отвечает на rewritten query в текущем focus** и **нет явного конфликта** с focus (другая услуга / другой clinical intent).

**Не заменять** один жёсткий guard другим:

- ❌ `topic == topic` only  
- ❌ `doc_type ∈ allowlist` как **gate**  
- ✅ **relevance** к rewritten query + **conflict check**; `doc_type` / `aspect` — **мягкий boost**, tie-break

#### Session focus

После хорошего ответа по услуге сохранять **focus** (целевое имя полей — см. этап 4 `last_subject`):

| Поле | Смысл |
|------|--------|
| `service_id`, `topic`, `label` | о чём говорим (subject) |
| `last_route` | price_lookup / retrieval_chunk / … |
| `turn_age` | сколько ходов назад обновляли focus |

**Правила:** focus **не** сбрасывается на коротком follow-up; **сбрасывается** на явной смене темы («теперь про виниры») или после lead cancel. При `turn_age` выше порога — ослабить rewrite или уточняющий вопрос.

#### Follow-up rewrite

Для короткой реплики без новой услуги:

```
«а гарантия?» + focus → «гарантия на классическую имплантацию»
```

- Сначала **шаблон + focus** (дешево)  
- Gray zone — **flash structured** (только строка rewrite, не маршрут)  
- Rewrite используется в **retrieval и guard**, не только в логах  

Связь с существующим `rewrite_query_for_retrieval` — привязать к **focus**, не только к hist.

#### Compatibility guard (алгоритм)

```
1. rewritten_query = follow_up_rewrite(q, focus)
2. candidate_pool = retrieval(rewritten_query)   // на follow-up не душить scope только implantation
3. score(c) = relevance(c, rewritten_query)    // embedding / lexical; arbiter pre-score на top-K
4. conflict(c, focus) = явно другая услуга?    // catalog / intent, не doc_type gate
5. PASS если score ≥ порога (routing.yaml) AND NOT conflict
6. doc_type / aspect metadata → +ε boost, не обязательное условие
7. FAIL → clarify или honest «в материалах не нашла», не молча current service md
```

**Reject только при:** низкая relevance **или** явный конфликт (classic → кандидат про брекеты).  
**Не reject** только потому что `topic=clinic` или `doc_type=warranty`.

На follow-up режим **`follow_up_mode`**: ослабить `scope_topic` / `alias_topic_guard` (`core/candidate_builder.py`), не отключать guard целиком.

#### aspect_registry — опционально, позже

**Не обязателен** для MVP follow-up. Схема может работать на docs + focus + compat guard.

Если golden покажет повторяющиеся дыры — точечный `clients/{id}/aspect_routing.yaml` (8–12 facet, 2–3 ref max, короткие triggers), **не** простыни phrases. Aspect в corpus (§3.1) + planner-lite — основной путь; registry — override для критичных facet (warranty, payment, contacts, pain).

#### Связь с lead-flow и planner

| Контекст | Тот же принцип |
|----------|----------------|
| Lead PAUSED, «боюсь боли» | content_hint=pain → retrieval, не slot retry (§3.2) |
| Consult, «а гарантия?» после classic | rewrite + compat guard |
| Planner-lite (этап 4) | append по subject+aspect; **не** заменяет compat guard |
| Lead overlay | после content-ответа; не смешивать с follow-up rewrite |

**Eval (целевое, до registry):** `evals/v5/follow_up_golden.json` — classic → warranty / pain / payment / contacts / doctor; **negative:** classic → «сколько брекеты?» (смена focus или clarify).

**Telemetry:** `meta.follow_up_rewritten`, `meta.focus_used`, `meta.guard_pass_reason`, `meta.compat_score`.

**Разделение данных:**

| Тип | Хранение | Назначение |
|-----|----------|------------|
| Услуга, маршрут | `service_catalog.json` | A3, session |
| Простая цена | `prices.json` | КТ, кариес, «от N ₽» |
| Пакет / под ключ | `price_offers.json` | Имплантация, All-on, unit, stages, includes (demo pilot) |
| Объяснение | md (`service`, `faq`, `pricing`, `comparison`) | Смысл, этапы, страхи |
| Слоты ответа | frontmatter service md | clinic_note, consult_value, promo_note, h3_overrides |
| Aspect (facets) | frontmatter + build_index | question facet: price, pain, duration, …; override в md |
| Ограничения | `clinic_policies.yaml` | Не делаем, альтернатива |

---

## 4. Этапы работ

Оценки: **календарь человека** / **оценка при работе с AI в Cursor** (код + eval, контент — отдельно).

**Дорожная карта (после 3.5):**

| Этап | Тема | Спека | Статус |
|------|------|-------|--------|
| **3.5** | PriceBook v2 | `PRICEBOOK_V2.md` | 🟢 MVP runtime |
| **3.6** | Lead flow v2 (запись, pause, overlay) | § **3.2** | 📋 спека, код нет |
| **4a** | Follow-up + compatibility guard | § **3.3**, `drafts/2.md` | 📋 спека, код нет |
| **4b** | Planner-lite (составные вопросы, aspect append) | § **3.1** | ⏳ |
| **5** | Verifier gate | § этап 5 | ⏳ |
| **6** | Retrieval 2.0 + aspect metadata | § этап 6 | ⏳ |

Этапы **4a** и **4b** — один календарный блок **«Этап 4»** ниже; **4a — приоритет** (без него planner не чинит warranty-кейсы).

### Этап 0 — Зафиксировать план и eval-скелет

| | |
|--|--|
| **Срок** | 0.5–1 день / **2–4 ч** |
| **Eval** | уровень 0 (docs) |

**Сделать:**

- [x] `IMPLANT_QUESTIONS_COVERAGE.md` — матрица 101 вопроса
- [x] `PRODUCT_WORK_PLAN.md` — этот документ
- [x] Пилот первой батареи: **`demo`** (presentation-рыба, пишет AI); prod-клиенты — после зелёного demo
- [x] Eval 0: `implant_golden.json` (28 кейсов) + `run_implant_eval.py`

**От чего избавляемся:** проверка «на глаз» без эталона.

**Не трогаем:** runtime pipeline.

---

### Этап 1 — Контент-пакет имплантации + связки каталога

| | |
|--|--|
| **Срок** | 3–10 дней / **код 1 день**, demo-контент **1–3 дня** (AI + прогон eval) |
| **Eval** | уровень 2–3 (smoke + ручные 5–10 вопросов) |
| **Статус** | ✅ **сделано** (demo) |

**Сделать (контент demo — AI, правдоподобная рыба):**

- [x] Тон и факты: как у реальной имплантологической клиники; без «lorem» и вымышленных протоколов *(demo-рыба)*
- [x] Цены: вилки «от … ₽» в рынке; единый источник правды между json и md; этапы оплаты правдоподобны *(demo: `prices.json` + `price_offers.json`)*

- [x] Comparison: `comparison__all_on_4_vs_all_on_6.md`, `comparison__classic_vs_one_stage.md`, `comparison__bone_graft_vs_all_on_4.md`
- [x] Расширить: `bone_graft`, `contraindications`, `pain` (наркоз/седация), faq второе мнение / рынок цен
- [x] `clinic_policies` — бренды не в ассортименте, скуловые/базальная/мини (если не делаете)
- [x] Проставить `clinic_note` / `consult_value` в **боевых** service md (не только `classic_test`) *(demo: classic, all_on_4/6, one_stage, benefits)*

**Сделать (данные):**

- [x] `service_catalog.json` — все имплантационные услуги: `md_entry_ref`, `price_key`, `concern_ref`, `price_ref`
- [x] `prices.json` — минимум ключи под каталог **или** явный переход на этап 2 (`price_offers`)
- [x] Пересборка индекса: `data/{client_id}/`

**Сделать (код, мелочь):**

- [x] `concern_ref` для `implant_supported_prosthetics` и `removable_dentures` (TECH_DEBT price_concern)

**Критерий готовности:** ≥70% текущего golden (20/28) — зелёные или осознанный known-fail с причиной.

**Факт (demo):** **28/28** implant golden — baseline зафиксирован. Достижение через **этап 1.5** (hint layer), не через чистый Resolver + arbiter. Детали и план снятия shims — **`TECH_DEBT.md` → Stage 1.5**.

**Не трогаем:** planner, verifier gate, retrieval 2.0.

---

#### Этап 1.5 — routing hints (промежуточный, зафиксирован)

Между этапами 1 и 2: deterministic routing для зелёного golden на demo. **Не откатывать**; считать **временным shim** до planner-lite + aspect (этапы 4–6).

| Тип | Оценка |
|-----|--------|
| Commercial vs `price_concern` | продуктовая логика |
| Comparison → `query_mode` | терпимый query-mode signal |
| Client pack aliases | норма, если не единственный путь |
| `catalog_md_direct`, regex → md | **debt** — см. `TECH_DEBT.md` |

**Правило с этапа 2:** новые **regex → doc** — только при блокере; иначе aspect / planner flag. Regex не сужать под один golden-кейс.

---

### Этап 2 — Answer slots (продающая / консультационная сборка)

| | |
|--|--|
| **Срок** | 3–7 дней / **0.5–1 день** кода |
| **Eval** | уровень 2 + кейсы в golden |
| **Статус** | ✅ **сделано** (demo, ветка `feature/demo-presentation`) |

**Сделать:**

- [x] `contracts/answer_slots.py` — схема полей frontmatter
- [x] `meta_loader.py` — читать `clinic_note`, `consult_value`, `promo_note`, `h3_overrides`
- [x] `core/answer_slots.py` — выбор слотов (h3 override → doc-level; session «не повторять»; promo только на commercial intent)
- [x] Врезка в `chunk_responder.py` **после** Generator, **до** policy (как `generator_append_text`)
- [x] Правила promo: не на `pain`, `contraindications`, `price_concern` с empathy, lead flow
- [x] Сузить/отключить `consult_nudge` там, где есть `consult_value` (избежать дубля)
- [x] `core/content_linter.py` — опциональная валидация длины полей для `doc_type: service`
- [x] Обновить `CURRENT_ARCHITECTURE.md` + `WIDGET_ANSWER_FORMAT.md` (слоты — абзацы, не списки)
- [x] Golden: 5–10 кейсов «есть clinic_note / нет повтора / нет promo на боль» (`evals/v5/answer_slots_golden.json`)

**Структура ответа:**

1. Суть (LLM по чанку)  
2. 0–1 `clinic_note`  
3. 0–1 `consult_value`  
4. 0–1 `promo_note` (если активна дата и intent уместен)  
5. CTA / follow-ups (policy, как сейчас)

**От чего избавляемся:** prompt-driven «не забудь про клинику»; реклама в embeddings.

**Не трогаем:** multi-source LLM; `pick_relevant_offer` можно перевести на `promo_note` в этом же PR или сразу после *(отложено — отдельный PR)*.

**Правило (наследие 1.5):** не добавлять direct **regex → doc** маршруты; словесные сигналы — в planner/aspect, не в `source_routing` ref. Shims из 1.5 не расширять — готовить замену в этапе 4.

---

### Этап 3 — Price offers (сложный прайс)

| | |
|--|--|
| **Срок** | 1–2 недели / **2–4 дня** кода + контент |
| **Eval** | уровень 2–3, hard cases в golden |
| **Статус** | ✅ **сделано** (demo: classic, one_stage, all_on_4, all_on_6 × 3 бренда) |

**Сделать:**

- [x] `contracts/price_offer.py` — `unit` (`one_tooth` \| `jaw` \| `full_mouth`), `total`, `payment_stages`, `includes`, `excludes`, `brand`, `recommended`
- [x] `clients/{id}/price_offers.json` (или секция в каталоге — **один** канон на клиента)
- [x] Loader + `get_price_offers(service_id, brand?, unit?)`
- [x] Рендер в `ux_builder` / `price_flow` — **детерминированный** текст (не LLM)
- [x] Связь: `service_catalog` → `price_offer_id` или набор offer по `service_id`
- [x] Planner-lite hook: intent `price_lookup` + catalog match → append offer *(через `price_flow` / A3 `price_ref`, без полного planner)*
- [x] Уточнение: «за зуб или челюсть?» если `unit` неоднозначен
- [x] Документировать в `CLIENT_FILLING_SERVICES_PRICES.md`
- [x] Пилот: Implantium / Impro / Nobel **one_tooth** + All-on-4 **jaw** (данные с `pricing__implants` / `pricing__all_on_4`)
- [x] Golden + meta-телеметрия: `evals/v5/price_offers_golden.json` (`price_offers_applied`, `price_offer_ids`)
- [x] `price_brand_aliases.json` в pack (синонимы брендов без хардкода в коде)
- [x] Rich append: **Входит / Не входит / Оплата по этапам**; полная карточка при одном бренде
- [x] Offers: `one_stage` + `all_on_6` × 3 бренда; unit clarify с All-on-6 (3 quick reply на demo)

**Правило:** цифры в ответе на ценовой вопрос — из json; md — объяснение «почему этапы».

**От чего избавляемся:** LLM как источник прайса; путаница единиц измерения.

**Не трогаем:** удаление `prices.json` для простых услуг.

---

### Этап 3.5 — PriceBook v2 (ценовой движок)

| | |
|--|--|
| **Срок** | 1–2 недели / **3–5 дней** код + контент demo |
| **Eval** | уровень 2–3; golden по сценариям S1–S5 из `PRICEBOOK_V2.md` |
| **Статус** | 🟢 **MVP runtime** (loader + assembler на demo; legacy fallback) |

**Спека:** `docs/PRICEBOOK_V2.md`, контракт `contracts/pricebook.py`.

**Сделать:**

- [x] Схема PriceBook: simple/complex, groups, pricing_facts, followups `price:*`
- [x] Таблица сценариев S1–S8 → блоки ответа (Assembler)
- [x] Demo draft: `clients/demo/pricebook/manifest.json`, `facts.json` (`text_fact`, `render_mode`: strict \| natural)
- [x] Loader + миграция offers → `pricebook/services/{id}.json`
- [x] Offers-only path: при `price_offers` — без LLM pricing-md (нет дублей ₽)
- [x] Quick reply `price:{service_id}` (unit clarify → price lookup)
- [x] `PriceAnswerAssembler`: deterministic blocks + template intro/closer (LLM natural — этап 5)
- [x] `pricing_facts` на price-ответах: `strict`/`natural` кодом (natural без LLM paraphrase — TECH_DEBT)
- [x] Lint: `scripts/lint_pricebook.py` (sum(stages)=total, no ₽ in pricing md)
- [x] Golden unit: S1/S2/S4/S5 в `tests/test_pricebook_golden.py`

**Правило:** одна логическая точка модерации на клиента; md — не источник сумм.

**Не трогаем:** cesi/nikadent; полный planner (этап 4) — только стыковка.

---

### Этап 3.6 — Lead flow v2 (диалог записи)

| | |
|--|--|
| **Срок** | 3–7 дней / **1–2 дня** кода |
| **Eval** | уровень 2–3; `lead_turn_golden.json` |
| **Статус** | 📋 **спека согласована**; код — см. `TECH_DEBT.md` |

**Спека:** § **3.2 Lead flow v2** (этот документ), runtime — `CURRENT_ARCHITECTURE.md` § Lead flow v2.

**Сделать:**

- [ ] `LeadTurnDecision` в `contracts/` + `core/lead_turn_classifier.py` (regex/meta/slot → gray LLM)
- [ ] Перестроить `flow_handlers`: intent before slot; расширить cancel/pause текстом; класс `defer`
- [ ] Первый экран записи: только имя, без exit-кнопок; текстовый cancel всегда
- [ ] Единый **lead overlay** после `finalize_turn` (chunk + price + contacts)
- [ ] Price interrupt в lead → pause → PriceAnswerAssembler; followups `price:*` в PAUSED
- [ ] `evals/v5/lead_turn_golden.json` + smoke-кейсы из реальных застреваний
- [ ] Обновить `tests/test_lead_interrupt.py` под новый контракт (не slot-first)

**Не трогаем:** pre-Resolver lead gate (regex-only); cesi/nikadent.

---

### Этап 4 — Follow-up (4a) + Planner-lite (4b)

| | |
|--|--|
| **Срок** | 1–3 недели / **1–2 дня** |
| **Eval** | уровень 3 |
| **Статус** | ⏳ **4a** и **4b** не начаты |

#### 4a — Follow-up & compatibility guard (§3.3)

**Спека:** § **3.3**, `drafts/2.md`, runtime — `CURRENT_ARCHITECTURE.md` § Follow-up.

**Сделать:**

- [ ] Session **focus** / `last_subject` `{ service_id, topic, label }`, `turn_age`, сброс на смене темы
- [ ] `core/follow_up_rewrite.py` — короткая реплика + focus → rewritten query (шаблон → flash structured)
- [ ] `core/compatibility_guard.py` — pass если **relevance(rewritten query)** и **нет conflict**; `doc_type`/aspect — boost only, не gate
- [ ] `follow_up_mode` в retrieval/guard: ослабить `scope_topic` / `alias_topic_guard` на follow-up (`core/candidate_builder.py`)
- [ ] Conflict check: явно другая услуга → reject; **не** reject только `topic=clinic`
- [ ] Telemetry: `meta.follow_up_rewritten`, `meta.focus_used`, `meta.guard_pass_reason`
- [ ] `evals/v5/follow_up_golden.json` — classic → warranty / pain / payment / contacts; negative: «сколько брекеты?»
- [ ] Optional позже: `clients/{id}/aspect_routing.yaml` — только если golden 4a не зелёный

**От чего избавляемся:** «гарантия на classic» → rewrite ok, warranty отброшен guard'ом → «в материале не указано».

#### 4b — Planner-lite (§3.1)

**Сделать:**

- [ ] `core/answer_planner.py` — **без LLM**: вход DecisionFrame, catalog match, regex (`под ключ`, `рассрочка`, `акция`, `vs`, `боюсь`)
- [ ] **Aspect + session:** резолв `aspect` (MVP: rules + `last_aspect`); subject carry-over («А это больно?»)
- [ ] Session: `last_aspect` — отдельно от `last_subject` (не смешивать с `last_catalog_service_id`)
- [ ] Planner: append по **subject + aspect** (`payment` → payment_terms), не «aspect → один файл»
- [ ] Выход: `{ primary_chunk_ref, append: [price_offer, payment_terms, boundary], slots: [...], risk: [price] }`
- [ ] Интеграция в `orchestration/` после A3, до `chunk_responder`
- [ ] Golden: 10 составных вопросов из `IMPLANT_QUESTIONS_COVERAGE` (напр. 1+7+8, 3+7, 16+6)

**От чего избавляемся:** «ответил только про протокол, забыл рассрочку».

**Не трогаем:** LLM смешивает несколько md-чанков в одном промпте. **4b после 4a** — planner не заменяет compat guard.

---

### Этап 5 — Verifier gate (tiered)

| | |
|--|--|
| **Срок** | 1–2 недели / **1 день** MVP |
| **Eval** | уровень 2–3 |

**Hard gate** (блок / перегенерация / safe fallback):

- цены, этапы оплаты, акции, гарантии, сроки с цифрами, «входит / не входит»

**Soft guard** (добавить boundary-фразу, не блокировать):

- противопоказания, боль, «можно ли мне»

**Сделать:**

- [ ] Режим gate для price append и answer_slots с цифрами
- [ ] Сверка с `price_offers` / `prices.json` / разрешённым md-хвостом
- [ ] Лог `verifier_blocked` / `verifier_softened` в meta
- [ ] Флаг в `features.yaml` per client: `verifier_gate.enabled`

**От чего избавляемся:** выдуманные 85 200 ₽ и «пожизненная гарантия клиники».

---

### Этап 6 — Retrieval 2.0 + content readiness

| | |
|--|--|
| **Срок** | 2–6 недель / **3–5 дней** код + 1–2 недели стабилизации |
| **Eval** | уровень 3, полная батарея 101 |

**Retrieval:**

- [ ] **`aspect` в corpus/chunk metadata** — авто из path/doc_type (`faq__pain` → `pain`, `comparison__*` → `comparison`) + frontmatter override; канон 8–12 aspect на MVP
- [ ] metadata filter / soft boost по **`topic` + `service_id` + `aspect`** (не hard route «aspect → файл»)
- [ ] metadata filter по `doc_type` (pricing vs service при `price_lookup`)
- [ ] hybrid / rerank (не удалять alias pipeline — только снизить зависимость)
- [ ] arbiter: приоритет `comparison` при `query_mode=comparison`; согласовать с `aspect=comparison`
- [ ] Свести routing regex-hints к aspect/session там, где дублируют смысл (post-MVP cleanup)

**Content compiler (расширение линтера):**

- [ ] Отчёт readiness %: цены, concern_ref, comparison, consult_value, пробелы по 101 вопросу
- [ ] `scripts/audit_client_readiness.py` → markdown/json для онбординга клиники

**От чего избавляемся:** гонка алиасов; запуск клиники «вслепую».

---

### Этап 7 — Платформа (масштаб)

| | |
|--|--|
| **Срок** | 2–4 месяца |

- шаблон knowledge pack + чеклист онбординга
- admin: правка price_offers / promo / слотов (или documented YAML-first workflow)
- quality dashboard, провалы по intent
- eval CI на 101 + per-client smoke
- версионирование контента

**Вне scope до стабильного этапа 1–5.**

---

## 5. Приоритетный спринт (рекомендация)

**Цель:** заметный скачок за **5–7 календарных дней** (demo-рыба — AI; владелец — ревью по желанию, не блокер).

| День | Фокус | Статус |
|------|--------|--------|
| 1 | Eval 25 вопросов; catalog↔price на demo; 3 comparison md (AI, правдоподобные) | ✅ |
| 2 | **Answer slots** в коде; поля в 3–5 service md (demo, рыба) | ✅ |
| 3 | Контент demo: bone_graft, contraindications, pain (AI, актуальная стоматология); прогон golden | ✅ |
| 4 | **Price offers** MVP (3 бренда × 1 зуб); deterministic append в price_flow | ✅ |
| 5 | **4a** follow-up guard + **4b** planner «цена + рассрочка»; **3.6** lead flow; прогон golden | ⏳ |

**Параллельно:** cesi / nikadent — **не в scope** до отмашки; только demo + общий код.

---

## 6. Что не автоматизировать (явные границы)

| Тема | Поведение бота |
|------|----------------|
| Расчёт по снимку без визита | «Точную сумму после осмотра и КТ» + CTA |
| Чужая цена («у них 180k») | Объяснить из чего складывается **ваша** цена; не оценивать чужую клинику |
| Второе мнение / два плана лечения | Пригласить с планом на консультацию; **не** арбитр |
| Индивидуальное «можно ли мне» | Инфо из contraindications + boundary |
| Multi-chunk LLM synthesis | Не делать; только append-слоты |

---

## 7. Риски и анти-паттерны

| ❌ Не делать | ✅ Вместо этого |
|-------------|----------------|
| Новый монолит «domain core» | Контракты поверх catalog / prices / meta_loader |
| LLM-planner на старте | Rule-based planner-lite |
| LLM смешивает 3 чанка | 1 чанк + append |
| Реклама в body md | frontmatter slots |
| 20 алиасов на тему | service entry + comparison + h3 + **aspect** metadata |
| Aspect под каждый golden-fail | 8–12 канонических facet; расширять по матрице 101, не по eval |
| Ослаблять golden ради зелёного | known-fail + задача в TECH_DEBT |
| Абстрактная «рыба» (lorem, нереальные цены) | Правдоподобный стомат. контент + рыночные вилки; demo ≠ prod-клиника |
| `if client_id ==` | `clients/{id}/` + policies |

---

## 8. Файлы по этапам (ожидаемые)

| Этап | Новые / основные файлы |
|------|-------------------------|
| 0 | `evals/v5/implant_golden.json` |
| 1 | `clients/*/md/comparison__*.md`, правки catalog/prices |
| 2 | `contracts/answer_slots.py`, `core/answer_slots.py`, `meta_loader.py`, `chunk_responder.py` |
| 3 | `contracts/price_offer.py`, `clients/*/price_offers.json`, `price_flow.py`, `ux_builder.py` |
| 3.5 | `contracts/pricebook.py`, `clients/demo/pricebook/`, `core/price_answer_assembler.py` |
| 3.6 | `contracts/lead_turn.py`, `core/lead_turn_classifier.py`, lead overlay в `finalize_turn` |
| 4a | `core/follow_up_rewrite.py`, `core/compatibility_guard.py`, `evals/v5/follow_up_golden.json` |
| 4b | `core/answer_planner.py`, session `last_subject` / `last_aspect`, orchestration |
| 5 | verifier gate в `chunk_responder` / отдельный модуль |
| 6 | `scripts/audit_client_readiness.py`, retriever/rerank, `aspect` в build_index / corpus |

---

## 9. Критерии «готово» по продукту

| Уровень | Критерий |
|---------|----------|
| **MVP** | golden ≥70% (20/28); answer slots на service; цены импланта из structure или md+append *(demo: slots ✅, price_offers ✅, implant golden 28/28)* |
| **Хороший бот** | 70%+ implant golden; planner-lite на составные; verifier hard на цены |
| **Продукт** | readiness audit; второй клиент за &lt;2 недель контента; CI eval |

---

## 10. Связь с открытым TECH_DEBT

При закрытии в PR отмечать в `TECH_DEBT.md`:

- `price_concern` + пустой `concern_ref` у протезов
- `offer` / promo (после этапа 2) — частично: `promo_note` в slots; `pick_relevant_offer` ещё заглушка
- implant `prices.json` vs каталог (после этапа 1 или 3) — ✅ demo
- **Stage 1.5 routing shims** — закрывать по мере этапов 4–6 (planner-lite + aspect)
- **Lead flow v2** — закрывать в этапе 3.6 (см. §3.2)
- **Follow-up compatibility** — этап 4, §3.3 (до optional aspect_routing.yaml)

---

*Черновик видения и диалог: `drafts/1.md`. Матрица вопросов: `IMPLANT_QUESTIONS_COVERAGE.md`.*
