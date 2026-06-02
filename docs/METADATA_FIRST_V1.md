# Metadata-First V1

**Статус:** рабочий план v1 (2026-06).  
**Связанные документы:** `CURRENT_ARCHITECTURE.md`, `ROUTING_MAP.md`, `TECH_DEBT.md`.

Цель: уменьшить зависимость retrieval/routing от aliases без большой смены поведения бота.

---

## Идея v1

V1 — это **не** попытка убрать aliases из системы.

V1 — это переход к схеме:

`Resolver -> metadata-aware candidate builder -> retrieval -> arbiter`

где:

- `Resolver` задаёт направление запроса
- `metadata` мягко сужает область поиска
- `retrieval` выбирает внутри более релевантного пула
- `aliases` остаются как `precision boost` / `rescue fallback`, но не как главный механизм выбора документа

---

## Чистые оси модели

В v1 сохраняем простую и понятную схему:

- `route_intent` — что делать по смыслу: `content`, `price_lookup`, `price_concern`, ...
- `query_mode` — форма вопроса:
  - `overview`
  - `specific`
  - `comparison`
  - `process`
- `doc_type` — тип документа:
  - `service`
  - `faq`
  - `info`
  - `pricing`
  - `doctor`
  - `contacts`
  - `comparison`
- `topic`
- `subtopic`
- `doc_id`

Не добавлять в v1:

- `query_mode=price`
- `query_mode=doctor`
- `query_mode=contacts`
- `clinic_info`
- `policy`
- обязательный `content_role`
- `taxonomy.yaml`
- `canonical_topics`
- `comparison_pair` в Resolver

---

## Doc Type Rules

Для текущей базы используем простой словарь `doc_type`:

- `__service__` -> `service`
- `__faq__` -> `faq`
- `__info__` -> `info`
- `__pricing__` -> `pricing`
- `doctors__doctor__*` -> `doctor`
- `clinic__info__contacts.md` -> `contacts`
- comparison docs -> `comparison`

Важно:

- `clinic__info__contacts.md` остаётся special-case с `doc_type: contacts`
- остальные `clinic__info__*` остаются `doc_type: info`
- `comparison` вводится сразу, если в базе появляются отдельные comparison-документы

---

## Comparison In V1

Comparison — отдельная полезная ветка, но не центр всей реформы retrieval.

Если у клиента есть comparison-документы, они должны быть обычными `md` в привычном формате, но с отдельным типом:

```yaml
doc_id: comparison__implant_vs_bridge
doc_type: comparison
topic: implantation
subtopic: implant_vs_bridge
```

Comparison в v1:

- определяется на уровне запроса через `query_mode=comparison`
- определяется на уровне контента через `doc_type=comparison`
- не требует `LLM slot filling`
- не требует agent-like сценария
- не требует нового UI-движка

Если comparison-doc найден:

- он получает приоритет в candidate builder / scoring

Если comparison-doc не найден:

- система спокойно уходит в обычный retrieval/RAG

Паттерн контента (эталон — `clients/demo/md/comparison__implant_vs_bridge.md`): короткий ответ в `#korotko`, уточняющие блоки — отдельные `h3` в том же файле; в frontmatter `suggest_h3` с id этих секций.

---

## План Работ V1

### 1. Audit readiness

Проверить `clients/{id}/md/` и зафиксировать:

- где уже есть `doc_id`
- где уже есть `topic`
- где уже есть `subtopic`
- где отсутствует `doc_type`

Результат:

- короткий readiness report по контенту
- список файлов, где metadata надо нормализовать

### 2. Normalize frontmatter

Проставить или выровнять `doc_type` по правилам выше.

Минимальный контракт frontmatter для v1:

- `doc_id`
- `doc_type`
- `topic`
- `subtopic`

Никаких новых тяжёлых обязательных полей в v1 не вводить.

### 3. Put metadata into corpus/index

**Реализовано в `build_index.py`** (нужен пересбор индекса). Каждый chunk в `corpus.jsonl` должен содержать минимум:

- `client_id`
- `doc_id`
- `doc_type`
- `topic`
- `subtopic`

Без этого metadata-first схема останется только внешней идеей.

### 4. Add candidate builder

**Реализовано (частично):** `core/candidate_builder.py` — post-retrieve score boosts: только `comparison_doc_type_boost` (при `query_mode=comparison` и comparison-doc с тем же `topic`) и `service_topic_match_boost` (при совпадении chunk `topic` с `service_topic`). Общего prefer по `doc_type` для faq/service/info/pricing/doctor/contacts **нет**. Отдельного слоя до retriever нет — boosts после `merge_retrieval_candidates`. Soft-scope: при `metadata_first.soft_scope_enabled` и `guard_reason=none` candidate topic уходит в telemetry, hard filter не применяется (`apply_content_retrieval_scope_ctx`); при `catalog_match` / `alias_hit` hard scope по-прежнему может не включаться по другим правилам; иначе возможен прежний hard scope.

Встроить слой:

`Resolver -> Candidate Builder -> Retriever -> Arbiter`

Задача candidate builder:

- `soft narrowing` по `service_topic`
- `prefer` по `doc_type`
- fail-open fallback при слабом topic или пустом narrowing

Для comparison:

- при `query_mode=comparison` сначала поднимать `doc_type=comparison`
- если таких документов нет, fallback в текущий retrieval

В v1 не делать жёсткий hard filter.

### 5. Add capped alias boost

**Реализовано:** `cap_alias_score_vs_semantic` в `core/candidate_builder.py`, вызов из `query_selector.py` (`metadata_first.alias_boost_max_delta`).

Alias должен:

- помогать
- усиливать точные попадания
- оставаться rescue fallback

Alias не должен:

- в одиночку побеждать semantic + metadata сигналы

То есть scoring должен стать составным:

- semantic score
- metadata/topic/doc_type boost
- capped alias boost

### 6. Add comparison content

Создать первые curated comparison docs, например:

- `comparison__implant_vs_bridge.md`
- `comparison__braces_vs_aligners.md`
- `comparison__crown_vs_filling.md`

Они должны оставаться обычными `md`:

- фронтматтер
- `#korotko`
- follow-up через `suggest_h3` → якоря `### ... {#h3_id}` **внутри того же** comparison-doc (не cross-doc `suggest_refs` в v1)
- мягкий CTA
- при необходимости эмпатичный тон

### 7. Add observability

**Реализовано:** `core/metadata_first_observability.py` — поля в `request.ctx`, событие `retrieval_metadata`, блок в `turn_complete` (`finalize_turn.py`).

Логировать минимум:

- `route_intent`
- `query_mode`
- `service_topic`
- `candidate_pool_before`
- `candidate_pool_after`
- `selected_doc_id`
- `selected_doc_type`
- `alias_hit`
- `alias_boost`
- `fallback_used`

### 8. Add content linter

**Реализовано:** `python scripts/lint_content.py` (`core/content_linter.py`); `build_index.py` запускает lint по умолчанию (`--skip-lint` — аварийно).

Проверять перед build/index:

- нет `doc_id`
- нет `doc_type`
- нет `topic`
- нет `subtopic`
- битый `ref`
- неизвестный `doc_type`
- слишком короткий alias
- дубли alias

### 9. Add alias collision report

**Реализовано:** `python scripts/alias_collision_report.py` (и `lint_content.py --collisions`).

Отдельный отчёт:

- alias -> список документов
- сколько раз alias повторяется
- какие alias слишком broad

### 10. Add evals

Проверять не только текст ответа, а:

- `route_intent`
- `query_mode`
- `service_topic`
- `doc_type`
- `doc_id`
- fallback
- при необходимости `suggest_refs` / buttons

Особенно важно:

- обычные content-smoke кейсы не просели
- comparison-кейсы идут в comparison docs, если они есть
- при отсутствии comparison docs поведение не ломается

---

## What Not To Do In V1

Не делать в этой задаче:

- `taxonomy.yaml`
- `canonical_topics`
- `comparison_pair` в Resolver
- `LLM slot filling`
- `guide_router`
- новый большой UI-слой
- дробление `info` на `clinic_info/policy`
- массовую чистку aliases

Это не значит, что идеи плохие. Это значит, что они не первый слой.

---

## Alias Policy For V1

До rollout новой retrieval-схемы:

- не делать массовую чистку старых aliases
- запретить добавлять новые broad aliases

Чистить aliases только после:

1. metadata в corpus
2. candidate builder
3. capped alias boost
4. decision logging
5. evals

---

## V2

Во v2 можно брать:

- 5-10 curated comparison docs для ключевых кейсов
- stronger comparison routing через `doc_type=comparison`
- более качественные `suggest_refs` / quick replies
- отдельные golden evals на comparison
- точечную чистку broad/duplicate aliases по collision report
- optional soft `content_role`, если для policy станет тесно

---

## V3

Во v3 можно думать про:

- `taxonomy.yaml`
- `canonical_topics`
- richer frontmatter contract
- `comparison_pair`
- более богатый Resolver contract
- более умный candidate builder
- rule-based slot filling для 1-2 ключевых comparison сценариев

Это имеет смысл только тогда, когда станет видно, что текущих полей:

- `service_topic`
- `topic`
- `subtopic`
- `doc_type`

реально не хватает.

---

## Success Criteria

V1 успешен, если:

- бот ведёт себя не хуже на текущих smoke-кейсах
- retrieval чаще работает внутри релевантного подкорпуса
- aliases архитектурно теряют роль “главного судьи”
- comparison docs выбираются там, где они есть
- отсутствие comparison docs ничего не ломает
- решение остаётся небольшим, безопасным и расширяемым
