# PriceBook v2 — спецификация (demo → multiclient)

**Статус:** MVP runtime на demo (`pricebook_loader`, `price_answer_assembler`).  
**Demo:** единственный источник сумм — `pricebook/services/*.json` (см. `clients/demo/pricebook/README.md`).  
**Другие packs:** legacy `price_offers.json` / `prices.json` — fallback при отсутствии entry.  
**Связь:** этап 3 (MVP offers) → **3.5 PriceBook v2** → этап 4 planner-lite → этап 5 verifier gate.

**Граница:** документ описывает current Pricebook schema/runtime. Его старые примеры
promo-blocking не задают target marketing policy; актуальный target-контракт —
[`MARKETING_SCENARIO_ARCHITECTURE.md`](MARKETING_SCENARIO_ARCHITECTURE.md).

**Парные документы:** `CURRENT_ARCHITECTURE.md` §6, `ROUTING_MAP.md`, `contracts/pricebook.py`, `TECH_DEBT.md` § PriceBook v2.

---

## 1. Зачем

Раньше цена жила в нескольких местах (`prices.json`, `price_offers.json`, pricing-md). **На demo** это сведено в `pricebook/`. MD — для экспертных ответов, **не для ₽**.

---

## 2. Принципы

| # | Правило |
|---|---------|
| P1 | **Суммы только в PriceBook** — md и LLM не источник цифр |
| P2 | **Простая и сложная цена — одна модель**; «простая» = offer без variants или один variant |
| P3 | **Сборку блоков делает код** (PriceAnswerAssembler); суммы и **strict**-facts — код; LLM — intro/closer и **natural**-facts по whitelist |
| P4 | **Повторяющиеся факты** (вычет, рассрочка) — `pricing_facts`, ссылка `fact_ref`, не копипаст |
| P5 | **Кнопки price-сценария** — ref вида `price:{service_id}` или `price:{service_id}/{aspect}`, не `service__*.md` |
| P6 | **Multiclient** — всё в `clients/{id}/`, без `if client_id` в коде |
| P7 | **`text_fact` = утверждённый смысл**, не «LLM придумывает promo»; подача — `render_mode`: **strict** (дословно) или **natural** (LLM перефразирует без смены смысла и цифр) |

---

## 3. Файлы в client pack (целевые)

```
clients/{id}/
  service_catalog.json      # как сейчас + pricebook_id (вместо price_ref со временем)
  pricebook/
    manifest.json           # version, groups, fact index
    facts.json              # shared pricing_facts
    services/
      professional_whitening.json   # simple
      pulpitis.json                   # simple + followups
      classic.json                    # complex
      all_on_4.json
      all_on_6.json
  price_brand_aliases.json  # без изменений (MVP)
```

**Миграция (demo — завершена; другие packs):**

1. Legacy `price_offers.json` + `prices.json` — loader читает как fallback.
2. Если есть `pricebook/services/{id}.json` → PriceBook, иначе legacy.
3. ₽ не хранить в pricing-md; акции — в `facts.json` + `fact_refs`, не в поле `promo` на service file.

---

## 4. Схема данных

Полный Pydantic-контракт: `contracts/pricebook.py`.

### 4.1 Shared facts (`pricebook/facts.json`)

**Не «заготовки фраз на все случаи»**, а **whitelist смыслов**: LLM не придумывает новые выгоды; для чувствительных фактов — дословная вставка.

| Поле | Зачем |
|------|--------|
| `text_fact` | Канон смысла: что можно сказать (13%, 12 месяцев, бесплатная консультация) |
| `render_mode` | **`strict`** — код вставляет дословно (%, даты, акции, гарантии). **`natural`** — LLM перефразирует живо, но **не меняет смысл и числа** |
| `kind` | `payment` \| `benefit` \| `promo` \| `warranty` — для policy (не показывать promo на pain и т.д.) |
| `detail_ref` | Длинный текст / кнопка «подробнее» → md |
| `active_until` | Акция; после даты fact не подмешивается |

**Правило для модератора:** «Если бот скажет другими словами — я спокоен?» Нет → `strict`. Да → `natural`.

```json
{
  "version": 1,
  "facts": {
    "tax_deduction": {
      "id": "tax_deduction",
      "kind": "benefit",
      "text_fact": "Можно оформить налоговый вычет 13% от оплаченного лечения.",
      "render_mode": "strict",
      "detail_ref": "clinic__info__payment_terms.md#korotko",
      "usable_in": ["price_answer", "payment_question", "retrieval"]
    },
    "installment_12": {
      "id": "installment_12",
      "kind": "payment",
      "text_fact": "Доступна рассрочка на имплантацию и протезирование до 12 месяцев.",
      "render_mode": "strict",
      "detail_ref": "clinic__info__payment_terms.md#korotko",
      "usable_in": ["price_answer", "commercial_answer"]
    },
    "free_implant_consult": {
      "id": "free_implant_consult",
      "kind": "promo",
      "text_fact": "Сейчас можно пройти бесплатную консультацию по имплантации и протезированию. На приёме врач по снимкам проверит, какой протокол или конструкция подойдут именно вам.",
      "render_mode": "natural",
      "detail_ref": "clinic__info__consultation.md#korotko",
      "usable_in": ["price_answer"],
      "active_until": "2026-12-31"
    },
    "implant_same_day_discount": {
      "id": "implant_same_day_discount",
      "kind": "promo",
      "text_fact": "При оплате в день обращения — скидка до 15% на имплантацию.",
      "render_mode": "strict",
      "usable_in": ["price_answer", "commercial_answer"]
    },
    "professional_whitening_discount": {
      "id": "professional_whitening_discount",
      "kind": "promo",
      "text_fact": "Сейчас на профессиональное отбеливание действует скидка 10% до 15 августа.",
      "render_mode": "strict",
      "usable_in": ["price_answer"],
      "active_until": "2026-08-15"
    },
    "implant_warranty": {
      "id": "implant_warranty",
      "kind": "warranty",
      "text_fact": "Гарантия на работу врача — 1 год. На импланты Impro и Nobel — пожизненная, на Implantium — 5 лет.",
      "render_mode": "strict",
      "detail_ref": "clinic__info__warranty.md#korotko",
      "usable_in": ["price_answer", "commercial_answer"]
    }
  }
}
```

Полный актуальный файл: `clients/demo/pricebook/facts.json`. Правила показа promo — `clients/demo/marketing.yaml` → `promo_rules`.

**Runtime (целевой):**

- `strict` → блок `fact_refs` рендерит **код** (`text_fact` как есть).
- `natural` → в prompt LLM передаётся `text_fact` как обязательный смысл; verifier (этап 5) проверяет grounded, без новых процентов/дат.

### 4.2 Группа для overview (`manifest.json`)

```json
{
  "version": 1,
  "groups": {
    "implantation": {
      "label": "Имплантация",
      "overview_prompt": "Стоимость зависит от протокола и объёма работ.",
      "members": [
        { "service_id": "classic", "label": "Классическая", "unit_hint": "one_tooth", "from_total": 76200 },
        { "service_id": "one_stage", "label": "Одномоментная", "unit_hint": "one_tooth", "from_total": 86500 },
        { "service_id": "all_on_4", "label": "All-on-4", "unit_hint": "jaw", "from_total": 318000 },
        { "service_id": "all_on_6", "label": "All-on-6", "unit_hint": "jaw", "from_total": 398000 }
      ]
    },
    "full_jaw": {
      "label": "Имплантация целой челюсти",
      "unit_filter": "jaw",
      "members": [
        { "service_id": "all_on_4", "label": "All-on-4", "from_total": 318000 },
        { "service_id": "all_on_6", "label": "All-on-6", "from_total": 398000 }
      ]
    }
  }
}
```

`full_jaw` — для «сколько стоит имплантация челюсти?» когда протоколов несколько.

### 4.3 Simple service (`services/professional_whitening.json`)

```json
{
  "service_id": "professional_whitening",
  "price_model": "simple",
  "display_name": "Профессиональное отбеливание",
  "price": {
    "price_type": "from",
    "value": 18000,
    "currency": "RUB",
    "note": "Точная стоимость зависит от выбранного протокола"
  },
  "promo": null,
  "fact_refs": ["professional_whitening_discount"],
  "followups": []
}
```

Скидки и акции — через **`fact_refs` → `facts.json`**, не через поле `promo` на service file.

### 4.4 Simple + кнопка (`services/pulpitis.json`)

```json
{
  "service_id": "pulpitis",
  "price_model": "simple",
  "display_name": "Лечение пульпита",
  "price": { "price_type": "from", "value": 15000, "currency": "RUB" },
  "followups": [
    {
      "label": "Что входит в лечение",
      "action": "price_aspect",
      "aspect": "includes",
      "detail_ref": "therapy__service__pulpitis.md#chto-vhodit"
    }
  ]
}
```

Клик → не прямой md-chunk, а **price_aspect** (код подставляет факты / retrieval по `detail_ref` с price-контекстом).

### 4.5 Complex service (`services/classic.json`)

```json
{
  "service_id": "classic",
  "price_model": "complex",
  "display_name": "Классическая имплантация",
  "default_unit": "one_tooth",
  "tags": ["implantation", "one_tooth", "turnkey"],
  "variants": [
    {
      "offer_id": "classic.one_tooth.implantium",
      "brand": "Implantium",
      "brand_label": "Implantium (Южная Корея)",
      "brand_group": "korean",
      "unit": "one_tooth",
      "total": 76200,
      "recommended": false,
      "payment_stages": [
        { "name": "Хирургия и имплант", "amount": 42000 },
        { "name": "Коронка после приживления", "amount": 34200 }
      ],
      "includes": ["имплант", "хирургия", "анестезия", "коронка", "осмотры"],
      "excludes": ["КТ — отдельно", "костная пластика по показаниям"]
    }
  ],
  "fact_refs": ["free_implant_consult"],
  "followups": [
    { "label": "Что будет на консультации", "action": "md_ref", "ref": "clinic__info__consultation.md#korotko" },
    { "label": "Оплата по этапам", "action": "price_aspect", "aspect": "stages" },
    { "label": "Что входит", "action": "price_aspect", "aspect": "includes" }
  ],
  "cta_key": "price"
}
```

`variants[]` совместим с текущим `PriceOffer` — миграция = перенос offers в service file.

---

## 5. Сценарии → блоки ответа

Planner (этап 4) выбирает **сценарий**; Assembler собирает **блоки**. LLM разрешён только в блоках `intro`, `closer` (и то по whitelist).

| Сценарий | Триггер (пример) | Блоки (порядок) | LLM | Кнопки |
|----------|------------------|-----------------|-----|--------|
| **S1 simple** | «Сколько стоит отбеливание?» | intro → **price_line** → fact_refs | code / facts | 0–1 followup |
| **S2 simple+aspect btn** | «Сколько пульпит?» | intro → price_line → closer | да | «Что входит» → aspect |
| **S3 overview group** | «Сколько имплантация?» | intro → **mini_summary** (from по members) → closer | intro/closer | по member: `price:classic`, … |
| **S4 complex specific** | «Классическая имплантация цена?» | intro → **price_table** → stages? → includes? → fact_refs → closer | intro/closer | followups из service |
| **S5 unit filter** | «Имплантация челюсти?» | если 1 member в group `full_jaw` → S4; иначе S3 по `full_jaw` | как S3/S4 | All-on-4 / All-on-6 |
| **S6 brand filter** | «Корейские импланты» | filter variants `brand_group=korean` → **price_table** (subset) | intro/closer | «Другие бренды» optional |
| **S7 aspect follow-up** | клик «Оплата по этапам» | context service_id + aspect → **stages block** only (+ closer) | короткий intro | назад / consult |
| **S8 shared fact Q** | «Налоговый вычет?» | retrieval / `facts.json` detail_ref | content route | — |

### Блоки (кто рендерит)

| Блок | Источник | Код / LLM |
|------|----------|-----------|
| `intro` | service tags + group overview_prompt | LLM, **без ₽** |
| `price_line` | simple.price | **код** |
| `price_table` | variants[] | **код** |
| `mini_summary` | group.members[].from_total | **код** |
| `stages` | variant.payment_stages | **код** |
| `includes` / `excludes` | variant | **код** |
| `fact_refs` | facts.json `text_fact` | **strict** → код дословно; **natural** → LLM по whitelist (+ verifier) |
| `closer` | centralized facts/slots only | disabled by default in PriceBook assembler |
| `followups` | service.followups | **код** → widget quick_replies |

---

## 6. Примеры диалогов (контракт eval)

### 6.1 Отбеливание (S1)

**Q:** Сколько стоит отбеливание?  
**A:** Живое intro (1–2 предложения) → «**от 18 000 ₽**» → `professional_whitening_discount` (10% до 15 августа), если разрешено `promo_rules`.  
**must_not:** дубль суммы; «точную стоимость уточните» без данных.

### 6.2 Пульпит (S2)

**Q:** Сколько стоит лечение пульпита?  
**A:** «от **15 000 ₽**» + кнопка **[Что входит в лечение]**.  
**Click:** aspect includes → текст из md/detail_ref, без новой цены.

### 6.3 Имплантация общая (S3)

**Q:** Сколько стоит имплантация?  
**A:** 2–3 строки overview + mini from-цены + кнопки **[Классическая] [All-on-4] [All-on-6]** (+ one_stage при наличии).  
**Click «Классическая»:** → S4 для `classic` (не service md).

### 6.4 Классическая (S4)

**Q:** Сколько стоит классическая имплантация?  
**A:** intro → таблица 3 бренда → этапы (recommended) → входит/не входит → «бесплатная консультация…» → **[Что на консультации]**.

### 6.5 Челюсть (S5)

**Q:** Сколько имплантация целой челюсти?  
**A (2+ протокола):** mini All-on-4 / All-on-6 from + кнопки.  
**A (1 протокол в pack):** сразу S4.

---

## 7. Quick reply / ref контракт

| ref | Поведение |
|-----|-----------|
| `price:classic` | price_lookup, service_id=classic, сценарий S4 |
| `price:all_on_4` | S4 |
| `price:implantation/overview` | S3 group implantation |
| `price:classic/includes` | S7 aspect |
| `md:clinic__info__consultation.md#korotko` | content (как сейчас ref) |

**Запрет:** для price-clarify не использовать `implantation__service__*.md#korotko`.

---

## 8. Связь с md-базой

| Нужен длинный текст | Где |
|---------------------|-----|
| Как проходит классическая имплантация | `service__classic.md` — **content**, не price button |
| Условия вычета | `clinic__info__payment_terms.md` + `facts.tax_deduction` |
| All-on-4 vs 6 | `comparison__*.md` — followup comparison |
| Состав пакета (развёрнуто) | optional md; в price — краткий `includes[]` |

Retrieval-вопрос «можно вычет?» → md/fact. Price-ответ → `fact_refs` (strict/natural) + кнопка «подробнее».

---

## 9. Модерация (для владельца)

**Один экран на услугу** (`services/classic.json`):

- название, tags, unit
- variants (бренды, суммы, этапы, входит)
- `fact_refs` (не дублировать promo-текст в service `promo`)
- кнопки

**Shared** — только в `facts.json` (вычет, рассрочка). Для каждого fact явно выставить **`render_mode`**.

**Шпаргалка render_mode:**

| Тип | Пример | Режим |
|-----|--------|--------|
| Процент, сумма скидки, дата акции | 13%, до 15 августа | strict |
| Рассрока «до N месяцев» | 12 месяцев | strict |
| Мягкий promo / консультация | бесплатная консультация | natural |

**Линтер (этап 3.5):**

- sum(stages) = total
- нет ₽ в pricing-md
- `active_until` не в прошлом (warn)
- followup ref resolvable
- `from_total` в group = min(variants)

---

## 10. Runtime (целевой пайплайн)

```
price_lookup
  → PricePlanner (rules + DecisionFrame + catalog)
      → scenario S1…S8
  → PriceAnswerAssembler
      → blocks (deterministic)
      → optional LLM intro/closer (no digits)
  → merge followups / meta (price_offers_applied, fact_ids)
  → verifier gate (этап 5): любая ₽ ∈ PriceBook
```

**Legacy path:** `price_offers.json` + append — только клиенты без pricebook entry (`TECH_DEBT.md`).

---

## 11. Этапы внедрения (demo only)

| Шаг | Что | Eval |
|-----|-----|------|
| 3.5a | Док + `contracts/pricebook.py` + lint sketch | 0 |
| 3.5b | `pricebook/` demo JSON из текущих offers/prices | 0 |
| 3.5c | Assembler S1,S3,S4 без LLM-цифр; offers-path bypass md | price_offers golden |
| 3.5d | Quick reply `price:*` + fix unit clarify buttons | smoke + 3 ручных |
| 3.5e | facts.json + promo на S1/S4 | golden промо |
| 3.5f | S6 brand_group | отдельный golden |
| 4 | Planner-lite стыкует aspect (рассрочка + цена) | implant composite |

---

## 12. Что не делаем в v2

- Диагноз и смета по снимку без КТ
- Автоматический парсинг прайса из PDF
- LLM выбирает суммы или этапы
- Один JSON на 500 услуг без split по files

---

## 13. Открытые решения

1. **Скуловая имплантация** — добавить в group `full_jaw` или policy «не делаем».
2. **LLM intro** — всегда или только complex; MVP complex-only.

**Закрыто:** цена отбеливания demo = **18 000 ₽** (`from`); акции demo сведены в `facts.json` (см. `MARKETING_EDITING_GUIDE.md`).
