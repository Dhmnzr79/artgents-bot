# v5 evals

Контекст: `docs/CURRENT_ARCHITECTURE.md`, `docs/MULTICLIENT.md`, план вопросов: `drafts/test.md`.

## Demo product eval (CI)

| Suite | Cases | Path |
|-------|-------|------|
| smoke | 24 | `demo/smoke.json` |
| risk | 20 | `demo/risk.json` |
| golden | 14 (§2.1, растёт) | `demo/golden.json` |

```bash
set E2E_USE_TEST_CLIENT=1
python evals/v5/run_demo_eval.py --client demo --suite product   # CI: smoke+risk
python evals/v5/run_demo_eval.py --client demo --suite golden   # core golden batch
python evals/v5/run_demo_eval.py --client demo --suite all      # всё
python evals/v5/run_demo_eval.py --suite smoke --case-id demo_smoke_05_phone
```

Env: `DEMO_EVAL_CLIENT`, `DEMO_EVAL_SMOKE_PATH`, `DEMO_EVAL_RISK_PATH`, `DEMO_EVAL_CASE_ID`.

### Формат кейса (v5)

- `expected_route` / `expected_route_any` — главный сигнал (см. `smoke_case_runner.infer_route_from_response`, `docs/ROUTING_MAP.md`)
- `expected_doc_id` / `expected_doc_id_any`, `expected_service_id` / `expected_service_id_any`
- `expected_pricebook_group_id`, `expected_price_status` — group overview из pricebook manifest
- `answer_signals_any` — OR по подстрокам (предпочтительно для LLM-текста)
- `forbidden_signals` / `must_not_contain` — запрещённые обещания или неверный маршрут
- `must_contain` — только для детерминированных шаблонов (lead flow)

Не использовать `must_contain` на свободный текст LLM. Не ослаблять ожидания ради зелёного прогона.

## Детерминированные слои (CI + локально)

```bash
python evals/v5/run_layer_eval.py --layer ingress
python evals/v5/run_price_offers_eval.py --client demo
python -m pytest tests/test_price_offers.py tests/test_price_group_overview.py -q
```

## Per-layer golden (разработка слоёв)

- `resolver_golden.json`, `arbiter_golden.json`, `generator_golden.json`, …
- `run_layer_eval.py --layer resolver|all`

## Metadata-first (опционально, multiclient branch)

- `metadata_first_golden.json`, `metadata_first_smoke.json`
- `run_metadata_first_eval.py`

## Архив

`archive/` — `e2e_smoke.v4.json`, `implant_golden.v4.json` (не в CI).

## Deprecated runners

- `run_e2e_smoke.py` → `run_demo_eval.py --suite smoke`
- `run_implant_eval.py` → `run_demo_eval.py --suite risk`

Общий движок: `smoke_case_runner.py`.
