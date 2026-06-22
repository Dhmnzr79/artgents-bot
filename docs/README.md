# Документация

| Документ | Зачем |
|----------|--------|
| **`CURRENT_ARCHITECTURE.md`** | Как бот работает **сейчас** (runtime, модули, пайплайн) |
| **`MULTICLIENT.md`** | Client pack, домены, VPS, локальный запуск, prod-критерии |
| **`VPS_CHECKLIST.md`** | Чеклист деплоя M5 (новый чат / пошаговый prod) |
| **`ROUTING_MAP.md`** | Куда уходит вопрос (маршруты до retrieval) |
| **`CLIENT_FILLING_SERVICES_PRICES.md`** | Шпаргалка: каталог, цены, md, маршруты при заполнении клиента |
| **`WIDGET_ANSWER_FORMAT.md`** | Контракт текста ответа для виджета |
| **`CESI_WIDGET_PRESENTATION.md`** | Текстовая презентация виджета на примере ЦЭСИ (UX, CTA, меню) |
| **`DASHBOARD.md`** | Admin, Postgres, события, cost |
| **`TECH_DEBT.md`** | Открытый долг и следующие шаги |
| **`IMPLANT_QUESTIONS_COVERAGE.md`** | 101 вопрос по имплантации → контент / логика |
| **`PRODUCT_WORK_PLAN.md`** | План работ: eval, slots, price offers, planner, verifier |
| **`PRICEBOOK_V2.md`** | Целевая модель цен (PriceBook, сценарии S1–S8, миграция с offers/md) |

Корень репо: `DEPRECATED.md`, `contracts/`, `core/routing.yaml`.

**Правило:** код и `CURRENT_ARCHITECTURE.md` не расходятся — правим вместе в одном PR.

**Scope активной работы (до отдельной отмашки владельца):** контент, цены, eval-golden под продукт, презентационные правки — **только `clients/demo/`** + общий multiclient-код. Пакеты **`cesi`** и **`nikadent`** не трогать (ни md, ни catalog, ни prices, ни widget). Исключение: multiclient smoke с `client_id=cesi|nikadent` — только регрессия, без изменения их pack.

---

## Cursor (обязательно)

1. `README.md` → `CURRENT_ARCHITECTURE.md` → `MULTICLIENT.md` → `TECH_DEBT.md`
2. Задача по UI: `WIDGET_ANSWER_FORMAT.md`
3. Задача по VPS / prod: `VPS_CHECKLIST.md` + `MULTICLIENT.md` §8
4. Задача по admin/PG: `DASHBOARD.md`
5. Задача по маршрутам: `ROUTING_MAP.md`

---

## Evals

- Smoke: `evals/v5/run_e2e_smoke.py`
- Implant battery: `evals/v5/run_implant_eval.py` (`implant_golden.json`)
- Answer slots: `evals/v5/run_answer_slots_eval.py`
- Price offers: `evals/v5/run_price_offers_eval.py` (`E2E_USE_TEST_CLIENT=1`)
- CI eval (demo): `run_implant_eval.py`, `run_e2e_smoke.py` — `.github/workflows/ci.yml`; metadata-first — опционально на `multiclient`
- Layer: `evals/v5/run_layer_eval.py`
