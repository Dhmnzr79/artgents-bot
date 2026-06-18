# План работ: умный стоматологический бот (продукт)

**Статус:** план развития (не runtime-контракт).  
**Дата:** 2026-06.  
**Источник:** обсуждение архитектуры, 101 вопрос по имплантации, продающие слоты, сложный прайс.

**Парные документы:**

| Документ | Роль |
|----------|------|
| `CURRENT_ARCHITECTURE.md` | Фактический runtime — обновлять при смене пайплайна |
| `MULTICLIENT.md` | Client pack, подключение клиник |
| `ROUTING_MAP.md` | Маршруты вопросов |
| `CLIENT_FILLING_SERVICES_PRICES.md` | Каталог, цены, md |
| `IMPLANT_QUESTIONS_COVERAGE.md` | 101 вопрос → контент / логика / отказ |
| `TECH_DEBT.md` | Открытый долг (дубли не копировать — закрывать строки в PR) |
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
- Для **prod-клиентов** (`cesi`, `nikadent`, …) — только контент владельца; demo-рыбу не копировать без адаптации.

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
| Контент имплантации | ~24 md в demo, comparison частично |
| Линтер контента | `core/content_linter.py`, `scripts/lint_content.py` |
| Eval | `evals/v5/` smoke + layer |
| Образец слотов | `implantation__service__classic_test.md` (поля в frontmatter, **код не читает**) |

### Главные пробелы

| Пробел | Риск |
|--------|------|
| Нет **answer_slots** в runtime | Бот не «продаёт» предсказуемо; дубль с `consult_nudge` |
| `prices.json` плоский; implant-ключи не заполнены | Цена из каталога не срабатывает |
| Сложный прайс только в md | LLM округляет / путает «за зуб» и «за челюсть» |
| Один чанк на ответ | Составные вопросы (цена + рассрочка) неполные |
| Verifier в shadow | Нет gate на цифры и акции |
| `offer` / `promo_note` — заглушка | Акции нестабильны |
| Нет eval на 101 вопрос | Регрессии незаметны |
| Comparison md по имплантации мало | All-on-4 vs 6, classic vs one-stage |

---

## 3. Целевая архитектура (куда идём)

```
вопрос
→ guards / Resolver / A3 (как сейчас)
→ planner-lite (детерминированный, без LLM на MVP)
→ evidence: 1 md-чанк + structured facts (price_offers, policy)
→ Generator (суть, single source)
→ answer assembly: slots (clinic_note, consult_value, promo) + price append
→ verifier gate (tiered)
→ policy → JSON /ask
```

**Разделение данных:**

| Тип | Хранение | Назначение |
|-----|----------|------------|
| Услуга, маршрут | `service_catalog.json` | A3, session |
| Простая цена | `prices.json` | КТ, кариес, «от N ₽» |
| Пакет / под ключ | `price_offers.json` (новое) | Имплантация, All-on, unit, stages, includes |
| Объяснение | md (`service`, `faq`, `pricing`, `comparison`) | Смысл, этапы, страхи |
| Слоты ответа | frontmatter service md | clinic_note, consult_value, promo_note, h3_overrides |
| Ограничения | `clinic_policies.yaml` | Не делаем, альтернатива |

---

## 4. Этапы работ

Оценки: **календарь человека** / **оценка при работе с AI в Cursor** (код + eval, контент — отдельно).

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

**Сделать (контент demo — AI, правдоподобная рыба):**

- [ ] Тон и факты: как у реальной имплантологической клиники; без «lorem» и вымышленных протоколов
- [ ] Цены: вилки «от … ₽» в рынке; единый источник правды между json и md; этапы оплаты правдоподобны

- [x] Comparison: `comparison__all_on_4_vs_all_on_6.md`, `comparison__classic_vs_one_stage.md`, `comparison__bone_graft_vs_all_on_4.md`
- [x] Расширить: `bone_graft`, `contraindications`, `pain` (наркоз/седация), faq второе мнение / рынок цен
- [x] `clinic_policies` — бренды не в ассортименте, скуловые/базальная/мини (если не делаете)
- [ ] Проставить `clinic_note` / `consult_value` в **боевых** service md (не только `classic_test`)

**Сделать (данные):**

- [x] `service_catalog.json` — все имплантационные услуги: `md_entry_ref`, `price_key`, `concern_ref`, `price_ref`
- [x] `prices.json` — минимум ключи под каталог **или** явный переход на этап 2 (`price_offers`)
- [x] Пересборка индекса: `data/{client_id}/`

**Сделать (код, мелочь):**

- [x] `concern_ref` для `implant_supported_prosthetics` и `removable_dentures` (TECH_DEBT price_concern)

**Критерий готовности:** ≥70% из 25 golden — зелёные или осознанный known-fail с причиной.

**Не трогаем:** planner, verifier gate, retrieval 2.0.

---

### Этап 2 — Answer slots (продающая / консультационная сборка)

| | |
|--|--|
| **Срок** | 3–7 дней / **0.5–1 день** кода |
| **Eval** | уровень 2 + кейсы в golden |

**Сделать:**

- [ ] `contracts/answer_slots.py` — схема полей frontmatter
- [ ] `meta_loader.py` — читать `clinic_note`, `consult_value`, `promo_note`, `h3_overrides`
- [ ] `core/answer_slots.py` — выбор слотов (h3 override → doc-level; session «не повторять»; promo только на commercial intent)
- [ ] Врезка в `chunk_responder.py` **после** Generator, **до** policy (как `generator_append_text`)
- [ ] Правила promo: не на `pain`, `contraindications`, `price_concern` с empathy, lead flow
- [ ] Сузить/отключить `consult_nudge` там, где есть `consult_value` (избежать дубля)
- [ ] `core/content_linter.py` — опциональная валидация длины полей для `doc_type: service`
- [ ] Обновить `CURRENT_ARCHITECTURE.md` + `WIDGET_ANSWER_FORMAT.md` (слоты — абзацы, не списки)
- [ ] Golden: 5–10 кейсов «есть clinic_note / нет повтора / нет promo на боль»

**Структура ответа:**

1. Суть (LLM по чанку)  
2. 0–1 `clinic_note`  
3. 0–1 `consult_value`  
4. 0–1 `promo_note` (если активна дата и intent уместен)  
5. CTA / follow-ups (policy, как сейчас)

**От чего избавляемся:** prompt-driven «не забудь про клинику»; реклама в embeddings.

**Не трогаем:** multi-source LLM; `pick_relevant_offer` можно перевести на `promo_note` в этом же PR или сразу после.

---

### Этап 3 — Price offers (сложный прайс)

| | |
|--|--|
| **Срок** | 1–2 недели / **2–4 дня** кода + контент |
| **Eval** | уровень 2–3, hard cases в golden |

**Сделать:**

- [ ] `contracts/price_offer.py` — `unit` (`one_tooth` \| `jaw` \| `full_mouth`), `total`, `payment_stages`, `includes`, `excludes`, `brand`, `recommended`
- [ ] `clients/{id}/price_offers.json` (или секция в каталоге — **один** канон на клиента)
- [ ] Loader + `get_price_offers(service_id, brand?, unit?)`
- [ ] Рендер в `ux_builder` / `price_flow` — **детерминированный** текст (не LLM)
- [ ] Связь: `service_catalog` → `price_offer_id` или набор offer по `service_id`
- [ ] Planner-lite hook: intent `price_lookup` + catalog match → append offer
- [ ] Уточнение: «за зуб или челюсть?» если `unit` неоднозначен
- [ ] Документировать в `CLIENT_FILLING_SERVICES_PRICES.md`
- [ ] Пилот: Implantium / Impro / Nobel **one_tooth** + All-on-4 **jaw** (данные с `pricing__implants` / `pricing__all_on_4`)

**Правило:** цифры в ответе на ценовой вопрос — из json; md — объяснение «почему этапы».

**От чего избавляемся:** LLM как источник прайса; путаница единиц измерения.

**Не трогаем:** удаление `prices.json` для простых услуг.

---

### Этап 4 — Planner-lite (составные вопросы)

| | |
|--|--|
| **Срок** | 1–3 недели / **1–2 дня** |
| **Eval** | уровень 3 |

**Сделать:**

- [ ] `core/answer_planner.py` — **без LLM**: вход DecisionFrame, catalog match, regex (`под ключ`, `рассрочка`, `акция`, `vs`, `боюсь`)
- [ ] Выход: `{ primary_chunk_ref, append: [price_offer, payment_terms, boundary], slots: [...], risk: [price] }`
- [ ] Интеграция в `orchestration/` после A3, до `chunk_responder`
- [ ] Golden: 10 составных вопросов из `IMPLANT_QUESTIONS_COVERAGE` (напр. 1+7+8, 3+7, 16+6)

**От чего избавляемся:** «ответил только про протокол, забыл рассрочку».

**Не трогаем:** LLM смешивает несколько md-чанков в одном промпте.

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

- [ ] metadata filter по `doc_type` (pricing vs service при `price_lookup`)
- [ ] hybrid / rerank (не удалять alias pipeline — только снизить зависимость)
- [ ] arbiter: приоритет `comparison` при `query_mode=comparison`

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

| День | Фокус |
|------|--------|
| 1 | Eval 25 вопросов; catalog↔price на demo; 3 comparison md (AI, правдоподобные) |
| 2 | **Answer slots** в коде; поля в 3–5 service md (demo, рыба) |
| 3 | Контент demo: bone_graft, contraindications, pain (AI, актуальная стоматология); прогон golden |
| 4 | **Price offers** MVP (3 бренда × 1 зуб); deterministic append в price_flow |
| 5 | Planner-lite для «цена + рассрочка»; прогон 30 golden; правки |

**Параллельно:** cesi / prod — только после зелёного demo; их контент — владелец, не копия demo-рыбы.

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
| 20 алиасов на тему | service entry + comparison + h3 |
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
| 4 | `core/answer_planner.py`, `orchestration/*` |
| 5 | verifier gate в `chunk_responder` / отдельный модуль |
| 6 | `scripts/audit_client_readiness.py`, retriever/rerank |

---

## 9. Критерии «готово» по продукту

| Уровень | Критерий |
|---------|----------|
| **MVP** | 25 golden зелёные; answer slots на service; цены импланта из structure или md+append |
| **Хороший бот** | 70%+ из 101; planner-lite на составные; verifier hard на цены |
| **Продукт** | readiness audit; второй клиент за &lt;2 недель контента; CI eval |

---

## 10. Связь с открытым TECH_DEBT

При закрытии в PR отмечать в `TECH_DEBT.md`:

- `price_concern` + пустой `concern_ref` у протезов
- `offer` / promo (после этапа 2)
- implant `prices.json` vs каталог (после этапа 1 или 3)

---

*Черновик видения и диалог: `drafts/1.md`. Матрица вопросов: `IMPLANT_QUESTIONS_COVERAGE.md`.*
