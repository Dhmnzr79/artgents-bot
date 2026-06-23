# Документация

| Документ | Зачем |
|----------|--------|
| **`CURRENT_ARCHITECTURE.md`** | Как бот работает **сейчас** (runtime, модули, пайплайн) |
| **`MULTICLIENT.md`** | Client pack, домены, VPS, локальный запуск, prod-критерии |
| **`VPS_CHECKLIST.md`** | Чеклист деплоя M5 (новый чат / пошаговый prod) |
| **`ROUTING_MAP.md`** | Куда уходит вопрос (маршруты до retrieval) |
| **`DEMO_KNOWLEDGE_BASE_GUIDE.md`** | **Гайд для ИИ/редактора:** как устроен demo-пак, цены, md, слоты, тесты |
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

## Evals (demo product — v5)

**CI (обязательно):** `run_demo_eval.py` (smoke + risk), `run_price_offers_eval.py`, `run_layer_eval.py --layer ingress`, unit routing/pricebook tests.

**GitHub Actions secrets:** `OPENAI_API_KEY` (embeddings / retrieval) + `DASHSCOPE_API_KEY` (Qwen chat). Без второго в CI будет `model_not_found` для `qwen3.7-plus`.

| Набор | Файл | Runner |
|-------|------|--------|
| Smoke (24) | `evals/v5/demo/smoke.json` | `python evals/v5/run_demo_eval.py --suite smoke --client demo` |
| Risk regression (20) | `evals/v5/demo/risk.json` | `python evals/v5/run_demo_eval.py --suite risk --client demo` |
| Оба | | `python evals/v5/run_demo_eval.py --suite all --client demo` |

Формат кейса: `expected_route`, `expected_doc_id` / `expected_service_id`, `answer_signals_any`, `forbidden_signals` — без дословных `must_contain` на текст LLM (кроме шаблонов lead).

Архив v4: `evals/v5/archive/` (`e2e_smoke.v4.json`, `implant_golden.v4.json`).

**Детерминированные слои:** `run_layer_eval.py`, `run_price_offers_eval.py`, `run_answer_slots_eval.py`.

**Опционально (ветка multiclient):** `run_metadata_first_eval.py` — `continue-on-error` в CI.

План расширения golden: `drafts/test.md` §2 → будущий `demo/golden.json`.
