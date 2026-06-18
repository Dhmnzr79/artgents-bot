# v5 per-layer evals

Этот каталог содержит per-layer golden sets и smoke runner. Контекст: `docs/CURRENT_ARCHITECTURE.md`, `docs/MULTICLIENT.md`, долг: `docs/TECH_DEBT.md`.

## Файлы

- `smoke_case_runner.py` — общая валидация e2e / metadata-first кейсов
- `metadata_first_golden.json` — Phase 2 golden (route + doc_id)
- `metadata_first_smoke.json` — Phase 2 critical smoke
- `run_metadata_first_eval.py` — runner metadata-first наборов
- `resolver_golden.json` — кейсы для Resolver (`DecisionFrame`)
- `arbiter_golden.json` — кейсы для Arbiter (`ArbiterDecision`)
- `verifier_golden.json` — кейсы для Verifier (`VerifierVerdict`)
- `generator_golden.json` — кейсы для Generator (faithfulness)
- `run_layer_eval.py` — запуск eval по слоям
- `implant_golden.json` — golden по имплантации (28 вопросов, `IMPLANT_QUESTIONS_COVERAGE` #1–28)
- `run_implant_eval.py` — runner implant golden (demo)

## Запуск

```bash
python evals/v5/run_layer_eval.py --layer resolver
python evals/v5/run_layer_eval.py --layer all
```

Пока runtime-слои ещё не реализованы, runner будет помечать результаты как `SKIP` (это ожидаемо на Phase 0).

## E2E smoke (PR #E.0)

Цель: минимальный end-to-end smoke runner, который дёргает `/ask` целиком и проверяет:
- **inferred smoke route** — `_infer_route_from_response()` по `meta.orch_route`, `meta.ingress_route`, флагам и `meta.file` (см. `docs/ROUTING_MAP.md`; **не** `meta.route`)
- `must_contain` — подстроки, которые **обязаны** быть в `answer` (case-insensitive)
- `must_not_contain` — подстроки, которых **не должно** быть в `answer` (case-insensitive)

### Файлы

- `e2e_smoke.json` — набор кейсов + baseline (root `baseline`)
- `run_e2e_smoke.py` — runner

### Формат кейса (кратко)

- `question`: текущий turn
- `history`: опционально, массив предыдущих turns вида `[{\"question\": \"...\"}]` (runner проигрывает их в `/ask` с той же `sid`)
- `client_id`: опционально, переопределяет `CLIENT_ID` env для этого кейса (multiclient golden)
- `expected_route`: опционально, строка (см. `_infer_route_from_response` — приоритет `meta.service_route`)
- `session_seed`: опционально, объект (напр. `{"pending_lead_offer": true}`) — только с `E2E_USE_TEST_CLIENT=1`; runner делает `mem_reset(sid)` перед кейсом, затем seed
- `expected_route_any`: опционально, массив строк (ambiguous кейсы)
- `must_contain` / `must_not_contain`: опционально, массив строк (case-insensitive substring)

**Phase 2 (metadata-first, опционально в любом json):**

- `expected_doc_id` / `expected_doc_id_any` / `forbidden_doc_id` — derive doc_id из `meta.file` (stem)
- `forbidden_doc_type` — эвристика по doc_id (`__faq__`, `comparison__`, …)
- `answer_signals_any` — OR по подстрокам (предпочтительнее одного слова в `must_contain`)
- `must_match_any_regex` — хотя бы один regex match
- `clients` — дублировать кейс на несколько `client_id` (`id@demo`, …); только в `run_metadata_first_eval.py`
- `expected_fallback_used` / `expected_doc_type` — при `E2E_USE_TEST_CLIENT=1` через `meta.metadata_first`

См. `docs/METADATA_FIRST_EVAL_PLAN.md`.

### Metadata-first eval (Phase 2)

```bash
# in-proc (рекомендуется для CI без поднятого сервера):
set E2E_USE_TEST_CLIENT=1
python evals/v5/run_metadata_first_eval.py --suite golden
python evals/v5/run_metadata_first_eval.py --suite smoke
python evals/v5/run_metadata_first_eval.py --suite all --client demo
```

Env: `MF_EVAL_SUITE`, `MF_EVAL_PATH`, `MF_EVAL_CLIENT`, `MF_EVAL_CASE_ID`.

### Implant golden eval (PRODUCT_WORK_PLAN stage 0)

```bash
set E2E_USE_TEST_CLIENT=1
python evals/v5/run_implant_eval.py --client demo
python evals/v5/run_implant_eval.py --case-id implant_q16_all_on_4_vs_6
```

Env: `IMPLANT_EVAL_PATH`, `IMPLANT_EVAL_CLIENT`, `IMPLANT_EVAL_CASE_ID`.

Кейсы поддерживают `expected_route`, `expected_doc_id` / `expected_doc_id_any`, `expected_service_id` / `expected_service_id_any` (из `meta.matched_service_id`).

**CI:** `.github/workflows/ci.yml` — job `metadata-first-eval` (нужен repo secret `OPENAI_API_KEY`, `E2E_USE_TEST_CLIENT=1`).

### Как запустить

1) Подними бота локально (по умолчанию ожидается `http://localhost:5000/ask`).

2) Запусти:

```bash
python evals/v5/run_e2e_smoke.py
```

Параметры через env:
- `BOT_URL` — URL endpoint `/ask` (default: `http://localhost:5000/ask`)
- `BOT_TIMEOUT_SEC` — timeout на запрос (default: 20)
- `CLIENT_ID` — default client_id для кейсов без поля `client_id` (default: `demo`)
- `E2E_SMOKE_CLIENT` / `--client` — запустить только кейсы для указанного client_id

CLI: `python evals/v5/run_e2e_smoke.py --client cesi --case-id smoke_cesi_contacts_address`
- `E2E_SMOKE_PATH` — путь к json (default: `evals/v5/e2e_smoke.json`)

### Как обновлять baseline

- Первый запуск: если `baseline=null`, runner выдаёт таблицу PASS/FAIL. После этого baseline фиксируется вручную: поставить `baseline=<passed>` в `e2e_smoke.json`.
- После улучшений: baseline обновлять **только** когда изменения осознанные и ожидаемые (не “подгонка” под текущий вывод).

### Что считать регрессией

- Любое падение ниже `baseline - 2` по количеству PASS (при фиксированном baseline).
- Сдвиг route в критичных кейсах (contacts/lead/price/handoff) даже если ответ «примерно похож».

### known_v4_failures

В корне `e2e_smoke.json` есть массив `known_v4_failures`: каждая запись связывает `case_id` с кратким описанием причины (типичный v4-баг) и полем `expected_fix_in_pr` (например `#1.3`, `#1.7`).

Это **намеренные регрессионные цели**, а не «сломанный» набор целиком: соответствующие кейсы в `cases[]` могут сейчас быть FAIL, но после merge указанного PR ожидается, что кейс начнёт **стабильно проходить**. Baseline по количеству PASS по-прежнему задаётся вручную; список `known_v4_failures` нужен для отслеживания прогресса и приоритетов без потери истории «почему этот сценарий важен».

