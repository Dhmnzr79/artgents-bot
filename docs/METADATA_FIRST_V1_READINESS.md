# Metadata-First V1 — readiness

**Дата:** 2026-06-02  
**Статус:** код §1–9 готов; eval Phase 2–3 + test hook §7 в `/ask` meta.

---

## Контент (demo, cesi, nikadent)

| Проверка | Результат |
|----------|-----------|
| `doc_id` / `doc_type` / `topic` / `subtopic` | linter на все pack'и |
| Comparison docs | **demo:** implant_vs_bridge, bugel; **cesi:** all_on_4 vs classic; **nikadent:** bugel, removable vs all-on-4 |
| Явный `doc_id` в YAML | linter требует |

---

## Инструменты

| Команда | Назначение |
|---------|------------|
| `python scripts/lint_content.py` | Frontmatter / ref / alias |
| `python scripts/lint_content.py --collisions` | Краткий collision-отчёт |
| `python scripts/alias_collision_report.py` | §9 полный отчёт |
| `python build_index.py --client all` | Lint + индекс |

---

## Eval + CI

| Набор | Baseline | Команда |
|-------|----------|---------|
| golden | 31 | `run_metadata_first_eval.py --suite golden` |
| smoke | 33 | `--suite smoke` |
| CI | lint + unit + eval | `.github/workflows/ci.yml` |

Test hook: при `E2E_USE_TEST_CLIENT=1` в ответе `/ask` → `meta.metadata_first` (telemetry для `expected_fallback_used`, `expected_doc_type`).

---

## Код (§3–9)

| § | Статус |
|---|--------|
| 3 corpus metadata | ✅ `build_index` |
| 4 candidate builder | ✅ `candidate_builder.py` |
| 4b soft scope | ✅ `helpers.py` |
| 5 capped alias | ✅ `query_selector.py` |
| 7 observability | ✅ ctx + `turn_complete` + **eval hook** |
| 8 linter | ✅ |
| 9 collision report | ✅ + CI inventory |
| 10 evals | ✅ golden/smoke + Phase 3 |

Пороги: `core/routing.yaml` → `metadata_first.*`.

---

## Не в v1

Массовая чистка aliases, `taxonomy.yaml`, pre-retriever candidate builder, общий prefer по всем `doc_type`.
