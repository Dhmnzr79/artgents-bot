# Metadata-First V1 — readiness (content phase)

**Дата:** 2026-06-02  
**Статус:** фаза A завершена; фаза B (частично) — corpus `doc_id`/`subtopic`, candidate builder, capped alias, logging в `request.ctx`.

---

## Контент (demo, cesi, nikadent)

| Проверка | Результат |
|----------|-----------|
| `doc_id` / `doc_type` / `topic` / `subtopic` | demo **48**, cesi **48**, nikadent **45** md — поля в frontmatter (linter требует явный `doc_id`) |
| `doc_id` = stem файла | OK |
| `doc_type` по правилам пути | OK (`lint_content.py`) |
| Comparison docs | **demo:** `comparison__implant_vs_bridge.md`; cesi/nikadent — нет (ожидаемо) |

---

## Инструменты

| Команда | Назначение |
|---------|------------|
| `python scripts/lint_content.py` | Ошибки frontmatter / ref / alias |
| `python scripts/lint_content.py --collisions` | Отчёт cross-doc alias (без fail) |
| `python build_index.py --client all` | Lint перед сборкой (или `--skip-lint`) |

Код: `core/content_linter.py`, тесты: `tests/test_content_linter.py`.

---

## Alias collisions (не чинили в v1)

По 3 нормализованных ключа на клиента — дубли между `doctors__doctor__overview.md` и карточкой врача (общие формулировки). Массовая чистка — после candidate builder + evals.

---

## Фаза B (сделано в коде)

| Шаг | Статус |
|-----|--------|
| `doc_id` + `subtopic` в `build_index` / corpus | ✅ (нужен `build_index --client all`) |
| `core/candidate_builder.py` + пороги в `routing.yaml` | ✅ (comparison boost только при `service_topic` + comparison doc с тем же `topic`) |
| Capped alias (`alias_boost_max_delta`) | ✅ |
| Telemetry в `request.ctx` из retrieval debug_meta | ✅ |
| Evals на `doc_id` / `fallback_used` в smoke | ⏳ smoke-кейсы comparison уже есть; расширить meta-checks — следующий шаг |

Пороги: `core/routing.yaml` → `metadata_first.*`.
