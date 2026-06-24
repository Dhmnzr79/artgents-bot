# Документация

Только **архитектура бота** и **фактический runtime**. Контент demo, гайды для ИИ/редактора, продуктовые планы и ops-чеклисты — вне `docs/` (черновики в `drafts/`, client pack в `clients/{id}/`).

Корень репо: `DEPRECATED.md`, `contracts/`, `core/routing.yaml`.

**Правило:** код и `CURRENT_ARCHITECTURE.md` не расходятся — правим вместе в одном PR.

**Scope активной работы:** контент и eval-golden под продукт — **только `clients/demo/`** + общий код. Пакеты **`cesi`** и **`nikadent`** не трогать.

---

## Архитектура и runtime

| Документ | Зачем |
|----------|--------|
| **`CURRENT_ARCHITECTURE.md`** | Пайплайн `/ask`, модули, Resolver, retrieval 2.0, slots, price, observability |
| **`MULTICLIENT.md`** | Client pack, домены, VPS, локальный запуск, prod-критерии |
| **`TECH_DEBT.md`** | Открытый долг и следующие шаги |

## Маршрутизация

| Документ | Зачем |
|----------|--------|
| **`ROUTING_MAP.md`** | Куда уходит вопрос (ingress → Resolver → A3 → retrieval / price / lead) |

## Подсистемы

| Документ | Зачем |
|----------|--------|
| **`PRICEBOOK_V2.md`** | Целевая и фактическая модель цен (demo на PriceBook; legacy fallback) |
| **`WIDGET_ANSWER_FORMAT.md`** | Контракт текста ответа для виджета |
| **`DASHBOARD.md`** | Admin, Postgres, события, cost |

---

## Cursor (обязательно)

1. `README.md` → `CURRENT_ARCHITECTURE.md` → `MULTICLIENT.md` → `TECH_DEBT.md`
2. UI виджета: `WIDGET_ANSWER_FORMAT.md`
3. VPS / prod: `MULTICLIENT.md` §8
4. Admin / PG: `DASHBOARD.md`
5. Маршруты: `ROUTING_MAP.md`

---

## Evals (проверка runtime)

**CI:** `run_demo_eval.py --suite product`, `run_price_offers_eval.py`, `run_layer_eval.py --layer ingress`, unit routing/pricebook.

| Набор | Runner |
|-------|--------|
| Product (smoke+risk) | `python evals/v5/run_demo_eval.py --suite product --client demo` |
| Golden (14) | `python evals/v5/run_demo_eval.py --suite golden --client demo` |

Детали: `evals/v5/README.md`, `CURRENT_ARCHITECTURE.md` § eval.
