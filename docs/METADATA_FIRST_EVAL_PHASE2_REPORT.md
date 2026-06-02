# Metadata-First Eval — Phase 2 Report

**Дата прогона:** 2026-06-02  
**Режим:** `E2E_USE_TEST_CLIENT=1` (in-proc Flask `test_client`)  
**Команда:** `python evals/v5/run_metadata_first_eval.py --suite all`

---

## Результаты

| Набор | Кейсов (runs) | PASS | FAIL | ERROR | Baseline |
|-------|---------------|------|------|-------|----------|
| `metadata_first_golden.json` | 27 (13 шаблонов × `clients`) | 27 | 0 | 0 | 27 |
| `metadata_first_smoke.json` | 17 | 17 | 0 | 0 | 17 |

**Итого (Phase 2):** 44/44 PASS.

### Phase 2b — comparison hit cesi/nikadent (2026-06-02)

| Набор | Runs | PASS | Baseline |
|-------|------|------|----------|
| golden | 31 | 31 | 31 |
| smoke | 19 | 19 | 19 |

**Итого:** 50/50 PASS. Новые кейсы: `mf_comparison_hit_cesi_all_on_4`, `mf_comparison_bugel` (demo+nikadent), `mf_comparison_hit_nikadent_removable`; smoke: `mfs_comparison_cesi_all_on_4`, `mfs_comparison_nikadent_bugel`. `mf_comparison_miss_cesi` (implant vs bridge без doc) — без изменений.

### Phase 3 — smoke expansion (2026-06-02)

| Набор | Runs | PASS | Baseline |
|-------|------|------|----------|
| smoke | 33 | 33 | 33 |

**+14 runs:** doctors (overview×3, Orlov, Moiseev, Kadiyev), multiclient cesi/nika (duration, safety, price_concern), faq/process (duration, safety, steps), cross-topic (extraction, braces ingress).

**Итого eval:** golden 31 + smoke 33 = **64/64 PASS**.

### Phase 3 — unit / CI (2026-06-02)

| Область | Файл | Тестов |
|---------|------|--------|
| observability | `tests/test_metadata_first_observability.py` | 4 |
| candidate_builder | `tests/test_candidate_builder.py` | +5 (всего 10) |
| soft scope | `tests/test_metadata_first_scope.py` | +1 hard scope |
| CI | `.github/workflows/ci.yml` | +observability pytest, alias report |
| test hook | `finalize_turn.py` + `E2E_USE_TEST_CLIENT=1` | `meta.metadata_first` на `/ask` |

### Golden (шаблоны)

| id | clients | focus |
|----|---------|-------|
| mf_contacts_* | demo / cesi / nikadent | contacts + doc_id |
| mf_price_all_on_4, mf_price_classic | all 3 | price_lookup + pricing doc |
| mf_concern_cost | all 3 | price_concern → faq cost |
| mf_faq_osseo, mf_faq_pain, mf_info_bone_graft | all 3 | content doc_id |
| mf_service_classic_overview | all 3 | service overview |
| mf_comparison_hit | demo | comparison doc |
| mf_comparison_hit_cesi_all_on_4 | cesi | comparison all-on-4 vs classic |
| mf_comparison_bugel | demo, nikadent | comparison bugel vs bridge |
| mf_comparison_hit_nikadent_removable | nikadent | comparison removable vs all-on-4 |
| mf_comparison_miss_cesi | cesi | implant vs bridge — нет comparison doc |
| mf_wrong_topic_aligners | demo | aligners, forbidden comparison |

### Smoke

Contacts (4), price (4), lead (2), pending (2), comparison (3), cross-topic veneers (1), content (3).

---

## Реализовано (инфра)

| Файл | Назначение |
|------|------------|
| `evals/v5/smoke_case_runner.py` | общая валидация + `expand_cases(clients)` |
| `evals/v5/run_metadata_first_eval.py` | runner golden/smoke/all |
| `evals/v5/run_e2e_smoke.py` | тонкая обёртка (старый `e2e_smoke.json` без `clients`) |
| `tests/test_metadata_first_eval_helpers.py` | doc_type, expand, fallback_used unit |

**Новые поля runner (optional, backward compatible):**  
`expected_doc_id`, `expected_doc_id_any`, `forbidden_doc_id`, `forbidden_doc_type`, `answer_signals_any`, `must_match_any_regex`.

**Не в Phase 2 e2e:** `expected_fallback_used`, `expected_doc_type` — только при `meta.metadata_first` (test hook) или unit tests.

---

## Отложено (не в первой волне)

| Сценарий | Причина |
|----------|---------|
| `mf_comparison_fallback_telemetry` | `fallback_used` — telemetry `candidate_builder`, покрыт unit test |
| `smoke_comparison_crown_vs_filling` | нет comparison md |
| `smoke_comparison_missing_one_tooth` | weak, нет dedicated doc |
| comparison hit cesi/nikadent | ✅ Phase 2b: golden + smoke (2026-06-02) |
| multi-turn smoke (6+ кейсов) | known v4 / #1.3 |
| ingress / handoff / noise | вне scope metadata-first smoke |
| `smoke_price_concern_general_no_service` | known v4 failure |

---

## Запуск

### Локально

```bash
set E2E_USE_TEST_CLIENT=1
python evals/v5/run_metadata_first_eval.py --suite all
python evals/v5/run_metadata_first_eval.py --suite golden --client cesi
python evals/v5/run_e2e_smoke.py --case-id smoke_contacts_phone
```

HTTP (без in-proc): поднять бот, убрать `E2E_USE_TEST_CLIENT`, задать `BOT_URL`.

### CI (этап 3)

Workflow: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)

| Job | Что делает | Секреты |
|-----|------------|---------|
| `content-lint-and-unit` | `lint_content.py --client all` + pytest (helpers, scope, candidate_builder) | нет |
| `metadata-first-eval` | `run_metadata_first_eval.py --suite all` in-proc | **`OPENAI_API_KEY`** |

В GitHub: **Settings → Secrets and variables → Actions → New repository secret** → `OPENAI_API_KEY`.

Без секрета второй job падает с явной ошибкой (первый job всё равно полезен на PR).

---

## Примечания по кейсам

- **mf_wrong_topic_aligners:** фактический route `catalog_md_first` — в кейсе `expected_route_any` включает catalog.
- **mfs_cross_topic_veneers:** без жёсткого `doc_id` (catalog card может не отдавать `meta.file`).
- **Multiclient:** один шаблон + `clients: ["demo","cesi","nikadent"]` → id вида `mf_faq_osseo@cesi`.

Следующий шаг: **Phase 3** — см. `docs/METADATA_FIRST_EVAL_PLAN.md` §3.
