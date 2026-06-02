# Metadata-First V1 — readiness

**Дата:** 2026-06-02  
**Статус:** код §1–9 готов (кроме §6 доп. comparison-md и §10 evals).

---

## Контент (demo, cesi, nikadent)

| Проверка | Результат |
|----------|-----------|
| `doc_id` / `doc_type` / `topic` / `subtopic` | demo **48**, cesi **48**, nikadent **45** md |
| Явный `doc_id` в YAML | linter требует (не подставляет из имени файла) |
| Comparison docs | **demo:** `comparison__implant_vs_bridge.md` только; остальные comparison — позже |

---

## Инструменты

| Команда | Назначение |
|---------|------------|
| `python scripts/lint_content.py` | Frontmatter / ref / alias |
| `python scripts/lint_content.py --collisions` | Краткий collision-отчёт |
| `python scripts/alias_collision_report.py` | §9 полный отчёт |
| `python build_index.py --client all` | Lint + индекс (`doc_id`, `subtopic` в corpus) |

---

## Код (§3–§9)

| § | Статус |
|---|--------|
| 3 corpus metadata | ✅ `build_index` |
| 4 candidate builder | ✅ post-retrieve: `comparison_doc_type_boost` + `service_topic_match_boost` только (`candidate_builder.py`); не общий doc_type-scoring |
| 4b soft scope (частично) | ✅ при `soft_scope_enabled` + guard `none` — scope в telemetry, без hard filter; иначе hard scope может остаться (`helpers.py`) |
| 5 capped alias | ✅ `cap_alias_score_vs_semantic` в `candidate_builder.py`, вызов в `query_selector.py` |
| 7 observability | ✅ `metadata_first_observability.py`, `turn_complete`, `retrieval_metadata` |
| 8 linter | ✅ |
| 9 collision report | ✅ `alias_collision_report.py` |
| 10 evals | ✅ Phase 2 + CI: `.github/workflows/ci.yml` (`metadata-first-eval` in-proc) |
| 6 comparison content (3 docs) | ⏸ контент позже |

Пороги: `core/routing.yaml` → `metadata_first.*`.

---

## Не в v1

Массовая чистка aliases, `taxonomy.yaml`, pre-retriever candidate builder, общий prefer по всем `doc_type`.
