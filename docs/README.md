# Документация

| Документ | Зачем |
|----------|--------|
| **`CURRENT_ARCHITECTURE.md`** | Как бот работает **сейчас** (runtime, модули, пайплайн) |
| **`MULTICLIENT.md`** | Client pack, домены, VPS, локальный запуск, prod-критерии |
| **`VPS_CHECKLIST.md`** | Чеклист деплоя M5 (новый чат / пошаговый prod) |
| **`ROUTING_MAP.md`** | Куда уходит вопрос (маршруты до retrieval) |
| **`CLIENT_FILLING_SERVICES_PRICES.md`** | Шпаргалка: каталог, цены, md, маршруты при заполнении клиента |
| **`WIDGET_ANSWER_FORMAT.md`** | Контракт текста ответа для виджета |
| **`DASHBOARD.md`** | Admin, Postgres, события, cost |
| **`TECH_DEBT.md`** | Открытый долг и следующие шаги |
| **`IMPLANT_QUESTIONS_COVERAGE.md`** | 101 вопрос по имплантации → контент / логика |
| **`PRODUCT_WORK_PLAN.md`** | План работ: eval, slots, price offers, planner, verifier |

Корень репо: `DEPRECATED.md`, `contracts/`, `core/routing.yaml`.

**Правило:** код и `CURRENT_ARCHITECTURE.md` не расходятся — правим вместе в одном PR.

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
- Metadata-first: `evals/v5/run_metadata_first_eval.py` (CI: `.github/workflows/ci.yml`)
- Layer: `evals/v5/run_layer_eval.py`
