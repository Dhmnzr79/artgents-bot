# Заполнение услуг и цен — шпаргалка

Кратко: что смотрит бот, в каком порядке, что отдаёт. Парные документы: `ROUTING_MAP.md`, `MULTICLIENT.md`.

---

## Три файла на клиента

| Файл | Роль |
|------|------|
| `service_catalog.json` | Реестр услуг: матч по aliases, маршрут, связи с ценой |
| `prices.json` | Цифры для прямого ответа «сколько стоит» |
| `md/` | Тексты: `*__service__*.md`, `*__pricing__*.md`, `*__faq__*.md` |

**Связка:** `service_id` (ключ в каталоге) → `price_key` (тот же ключ в `prices.json`, если есть цена).

---

## Поля каталога (что заполнять)

```json
{
  "classic": {
    "title": "Классическая имплантация",
    "aliases": ["поставить имплант", "..."],
    "active": true,
    "md_entry_ref": "implantation__service__classic",
    "facts": [],
    "price_key": "classic",
    "price_ref": "implantation__pricing__implants.md#korotko",
    "concern_ref": "implantation__faq__cost.md#korotko",
    "price_display": "on_request",
    "suggest_refs": [{ "label": "Условия оплаты", "ref": "clinic__info__payment_terms.md#korotko" }]
  }
}
```

| Поле | Зачем |
|------|--------|
| `title` + `aliases` | Матч услуги в вопросе (каталог, не RAG) |
| `md_entry_ref` | Страница услуги (`doc_id` без `.md`). Пусто → только `facts` |
| `facts` | Короткая карточка, если нет md (КТ, отбеливание) |
| `price_key` | Строка в `prices.json` |
| `price_ref` | При ценовом вопросе — ответ из md-чанка (развёрнуто), **приоритет над** `prices.json` |
| `concern_ref` | При «дорого / не по карману» — FAQ-страница про стоимость |
| `price_display` | `always` — подмешать цену в **информационный** ответ об услуге; `on_request` — только по явному вопросу о цене |
| `suggest_refs` | До **1** кнопки `quick_replies` в ценовых/facts-ответах |

---

## Порядок обработки вопроса (упрощённо)

```
вопрос
→ lead / situation / ref-кнопка / «да» (если pending)
→ короткое продолжение + current_doc_id → тот же md#korotko
→ Resolver (intent: content | price_lookup | price_concern | unknown)
→ regex цены ПЕРЕБИВАЕТ Resolver (price_rules_hint)
→ A3 source_routing:
     1) врачи (если не ценовой intent)
     2) каталог + content → catalog_md / catalog_facts
     3) каталог + price_concern → concern_ref
     4) price_lookup → prices.json / price_ref / clarify
→ иначе RAG (retrieval + arbiter)
```

**Сессия для «а сколько?»:** после ответа об услуге пишется `current_doc_id` (md) или `last_catalog_service_id` (facts без md).

---

## Два ценовых intent

| Intent | Триггеры в вопросе | Примеры |
|--------|-------------------|---------|
| `price_lookup` | цена, стоимость, сколько стоит, прайс, сколько обойдётся | «Сколько стоит all-on-4?» |
| `price_concern` | дорого, не по карману, почему так дорого, дешевле | «Почему имплантация такая дорогая?» |

Скидки / рассрочка / полис → **не** `price_concern`, идут в обычный retrieval (`payment_terms` и т.д.).

---

## Сценарий 1: вопрос об услуге (без цены)

**Пример:** «Расскажите про all-on-4»

1. Intent → `content`
2. Каталог матчится (score ≥ порога) → A3 `catalog_md` или `catalog_facts`
3. **Есть `md_entry_ref`** → чанк `{md_entry_ref}.md#korotko`, LLM-ответ + `meta.followups` из `suggest_h3` md
4. **Нет md, есть `facts`** → LLM-карточка из facts
5. **`price_display: always`** + есть `price_key` в `prices.json` → цена дописывается в конец ответа
6. Каталог не матчится → RAG по корпусу (aliases md, семантика)

**Кнопки:** `meta.followups` (подтемы из md), CTA из frontmatter md (`cta_text` / `cta_action: lead`), `quick_replies` из `suggest_refs` каталога — только в facts/price-путях, не в полном md-ответе.

---

## Сценарий 2: сначала услуга, потом цена

**Ход 1:** «Классическая имплантация» → как сценарий 1, в сессии `current_doc_id`.

**Ход 2:** «А сколько стоит?» / «Сколько?»

1. Intent → `price_lookup` (regex)
2. В вопросе нет названия услуги → **session fallback** по `current_doc_id` / `last_catalog_service_id`
3. Дальше — ветка цены (см. таблицу ниже)

Ограничение: если в ценовом вопросе явно названа **другая** услуга — session не подставляется.

---

## Сценарий 3: сразу цена на услугу

**Пример:** «Сколько стоит лечение кариеса?»

1. Regex → `price_lookup` (до Resolver)
2. `match_service_from_catalog` по `title` + `aliases`
3. Уверенный матч → `select_price_service_route`

### Приоритет источника цены (`price_lookup`)

```
1. price_ref в каталоге  →  ответ из md-чанка (LLM по тексту pricing/faq)
2. иначе price_key       →  prices.json («Название — от N ₽.»)
3. иначе                 →  clarify или заглушка
```

Для `price_concern` (не «сколько», а «дорого»):

```
1. услуга в каталоге + concern_ref     →  md-чанк concern_ref
2. иначе session + concern_ref
3. иначе DEFAULT: implantation__faq__cost.md#korotko
```

> Пробел: услуга без `concern_ref` при «дорого» → default cost FAQ (часто имплантация). Для протезных услуг лучше задать свой `concern_ref`.

---

## Матрица: услуга есть / цены нет / услуги нет

### Информационный вопрос (`content`)

| Ситуация | Что отдаёт бот |
|----------|----------------|
| Услуга в каталоге + md | Страница услуги `#korotko`, followups, CTA |
| Услуга в каталоге + facts | Карточка facts; цена если `price_display: always` |
| Услуга в каталоге, md пустой, facts пустые | RAG (каталог не сработал на A3) |
| Только md, нет в каталоге | RAG по aliases/семантике (без catalog_md) |
| Ничего не найдено | `guided` / low_score / уточнение |

### Ценовой вопрос (`price_lookup`)

| Ситуация | Что отдаёт бот |
|----------|----------------|
| Услуга + `price_ref` | Текст из pricing/faq md |
| Услуга + `price_key` в prices.json | «Название — цена.» + note |
| Услуга есть, цены нет | Clarify: «Не могу определить…» или заглушка про консультацию |
| Услуга не найдена | Clarify + при `clinic_policies.yaml` — альтернатива («у нас нет детской…») |
| Короткое «сколько?» без контекста | Clarify `continuation_no_context` |

### «Дорого» (`price_concern`)

| Ситуация | Что отдаёт бот |
|----------|----------------|
| Услуга + `concern_ref` | FAQ-страница про стоимость |
| Услуга без `concern_ref` | Default cost FAQ (имплантация) |
| Услуга не найдена | Default cost FAQ |

---

## Кнопки и ссылки — откуда берутся

| UI | Источник | Где |
|----|----------|-----|
| `meta.followups` | `suggest_h3` в frontmatter md | Ответ по md-чанку |
| `quick_replies` | `suggest_refs` в каталоге (макс. 1) | facts, price_lookup, price_concern payload |
| `cta` | frontmatter md (`cta_action: lead`) | md-ответы; шаблон в price_concern без concern_ref |
| Кнопка с `ref` в виджете | пользователь жмёт → POST `/ask` с `ref` → сразу нужный чанк | |

**Два типа pricing-контента:**

- `prices.json` — короткая цифра для бота
- `*__pricing__*.md` — развёрнутое объяснение; подключается через `price_ref` в каталоге

---

## Режимы услуги в каталоге

| Паттерн | md | facts | price | Типичный ответ |
|---------|----|-------|-------|----------------|
| Полная услуга | ✓ | — | key + опц. price_ref | md + цена по запросу / `always` в контенте |
| Простая услуга | — | ✓ | key | facts-карточка |
| Справочник | md без каталога | — | — | только RAG |
| FAQ / info / doctors | md | — | — | RAG или прямой ref |

---

## Чеклист перед `build_index.py`

- [ ] Каждая **продающая** услуга: запись в `service_catalog.json`
- [ ] `md_entry_ref` = `doc_id` в md (или осознанно только `facts`)
- [ ] `price_key` совпадает с ключом в `prices.json` (если цена нужна)
- [ ] Для имплантации/сложных: `price_ref` на `*__pricing__*.md#korotko`
- [ ] Для «дорого»: `concern_ref` на тематический FAQ (не полагаться на default)
- [ ] `aliases` в каталоге покрывают разговорные формулировки
- [ ] В md: `suggest_h3` указывает на реальные `{#anchor}` в файле
- [ ] `active: false` — услуга не матчится (временно скрыть)

---

## Примеры (demo)

| Вопрос | Маршрут | Откуда контент |
|--------|---------|----------------|
| Классическая имплантация | `catalog_md_first` | `implantation__service__classic.md` |
| КТ | `catalog_facts` | facts в каталоге + цена (`price_display`) |
| Сколько стоит all-on-4? | `price_lookup` | `price_ref` → `implantation__pricing__all_on_4.md` |
| Сколько стоит кариес? | `price_lookup` | `prices.json` → `caries` |
| Почему так дорого? (после all-on-4) | `price_concern` | `concern_ref` услуги |
| Преимущества имплантации | `retrieval_chunk` | md есть, в каталоге нет |
