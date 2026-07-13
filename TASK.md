# TASK — A7 Planner split: один raw → partial shadow + strict legacy

Один активный `TASK.md` на одну маленькую задачу. Файл подготовлен **Архитектором** после принятого A7 Contract.
Общий закон — `.cursor/rules/00-guardrails.mdc`. Инварианты ревью — `REVIEW_CHECKLIST.md`.
Архитектурная опора — `docs/FIELD_LEVEL_PLANNER_OUTCOME_A7.md` и текущий код.

---

## 1. Точка старта

- A7 Design: `7f9cfe4`.
- A7 Contract: `077bb0a`.
- Рабочая ветка: `codex/stage-a`.
- A6 raw SHA256: `2EF96AB8660657501137B0A6880E7EA54594E02417197F031BE1BCE2D9D5A40A`.
- Matrix hash: `dc356c9c738fb80a10cf0035508d7e8c8247979d`.
- Preservation hash: `c2072ca74c2da73bf657d793195d2eb6c8ba7bd5`.
- Перед началом working tree должен быть чистым.

## 2. Цель

Реализовать unit-only dual branch одного planner-вызова:

```text
один chat_completions_create()
          ↓
один parseable raw dict
  ├─ pure field-level builder → TurnFrame
  └─ существующая strict _validate_plan() → TurnPlan | None
          ↓
PlannerAttempt(legacy_plan, shadow_frame, shadow_status)
```

Существующий публичный контракт сохраняется:

```python
plan_turn(q, sid, client_id) -> TurnPlan | None
```

Он становится тонким wrapper:

```python
return plan_turn_attempt(q, sid, client_id).legacy_plan
```

Никакой downstream-код в этом checkpoint не получает `PlannerAttempt`.

## 3. Главные инварианты

1. Ровно **один** LLM-call на один вызов `plan_turn()` или `plan_turn_attempt()`.
2. Один и тот же raw dict читают обе ветки.
3. Field-level builder не мутирует raw.
4. Strict `_validate_plan()` не получает «исправленный» builder payload.
5. `TurnPlan` и его eligibility не ослабляются.
6. `plan_turn()` возвращает те же legacy results/fail-open, что до A7.
7. Partial shadow не публикуется в ctx и не влияет на product.
8. Нет второго classifier, retry или тематических веток.

## 4. Строгий allowlist

Исполнитель может изменить только:

1. `core/turn_frame_from_raw.py` — новый pure builder
2. `core/turn_planner_llm.py`
3. `tests/test_turn_frame_from_raw.py` — новый файл
4. `tests/test_turn_planner_llm.py`
5. `tests/test_planner_attempt_contract.py` — только миграция firewall-теста: planner разрешён, downstream запрещён

Любой другой diff → ❌ и СТОП.

Особенно запрещено менять:

- `contracts/**`;
- `core/turn_frame_adapter.py`;
- `core/turn_frame_shadow.py`;
- `orchestration/**`;
- `llm.py`, `app.py`;
- `TASK.md`, design/audit docs;
- eval specs/harness/raw;
- client content, pricebook, marketing;
- продуктовые тесты вне allowlist.

## 5. Pure field-level builder

Создать `core/turn_frame_from_raw.py`.

Публичная функция:

```python
def build_turn_frame_from_raw(
    raw: dict[str, Any],
    *,
    allowed_topics: frozenset[str],
) -> TurnFrame:
    ...
```

### 5.1 Чистота

Builder:

- не мутирует `raw`, включая nested values;
- не логирует raw/exception/user text;
- не читает question/history/session/client files;
- не загружает taxonomy сам — получает `allowed_topics`;
- не импортирует planner, resolver, Flask, app, LLM, evidence/composer;
- не вызывает network/LLM;
- не исправляет strict payload;
- не содержит тематических if/regex.

### 5.2 Intent/route

Разрешённые значения берутся из `RouteIntent` contract, без локального dental hardcode.

- valid route string → значение route, `status="valid"`, provenance `turn_plan.raw.route`;
- missing/non-string/out-of-contract route → `intent="unknown"`, `status="invalid"`, error `route_invalid`;
- confidence для route в этом slice `0.0` (LLM не возвращает route confidence).

### 5.3 Topic/topic_confidence

Semantics должны соответствовать A7 Design, не product sanitizer side effects:

- allowed normalized string + confidence 0..1 → topic, `valid`, provenance `turn_plan.raw.topic`;
- missing/null/blank topic при missing/null/0 confidence → `None`, `missing`, error `None`, confidence `0.0`;
- non-string topic → `None`, `invalid`, `topic_invalid_type`;
- topic вне `allowed_topics` → `None`, `invalid`, `topic_not_allowed`;
- invalid/non-number/bool/out-of-range confidence → `None`, `invalid`, `topic_confidence_invalid`;
- positive confidence без topic также маппится в `topic_confidence_invalid` (не расширять frozen error allowlist);
- не сохранять неизвестное raw topic value в frame/error/log.

Не выводить topic из service_id, filename, doc_id, question, regex или legacy `DecisionFrame`.

### 5.4 Aspects

Allowed values получают из `AspectKind`, не из отдельного hardcoded dental списка.

- valid non-empty list разрешённых строк → list в исходном порядке, `valid`;
- `[]` → `[]`, `invalid`, `aspects_empty`;
- missing/non-list → `[]`, `invalid`, `aspects_invalid_type`;
- хотя бы один unknown/non-string element → `[]`, `invalid`, `aspect_not_allowed`;
- не удалять неизвестные элементы молча;
- не подставлять `overview`;
- provenance `turn_plan.raw.aspects`, confidence `0.0`.

### 5.5 Primary aspect

- только первый элемент valid non-empty aspects;
- provenance `turn_plan.raw.aspects[0]`;
- valid aspects → `status="valid"`;
- empty/invalid aspects → `None`, `invalid`, `primary_aspect_unavailable`;
- builder не принимает отдельный primary из raw.

### 5.6 Остальные оси первого slice

Они пока не валидируются из raw и получают безопасные значения со статусом `defaulted`, чтобы не создавать ложный `missing`:

| axis | value | provenance |
|------|-------|------------|
| emotion | `none` | `a7.not_migrated` |
| specificity | `unknown` | `a7.not_migrated` |
| patient_scope | `None` | `a7.not_migrated` |
| service_id | `None` | `a7.not_migrated` |
| follow_up | `False` | `a7.not_migrated` |
| followup_of | `None` | `a7.not_migrated` |
| needs_clarification | `False` | `a7.not_migrated` |

Для всех: confidence `0.0`, error `None`.

`defaulted` здесь честно означает: axis не мигрирована и не используется. Нельзя переносить эти значения в product.

## 6. Planner attempt API

В `core/turn_planner_llm.py` добавить:

```python
def plan_turn_attempt(
    q: str,
    sid: str | None,
    client_id: str | None,
) -> PlannerAttempt:
    ...
```

### 6.1 До parseable dict

- empty question → `not_available` без LLM-call;
- empty service catalog → `not_available` без LLM-call;
- LLM/network/JSON parse/non-object failure → существующий fail-open logging + `not_available`;
- не класть exception/raw в `PlannerAttempt`.

### 6.2 После parseable dict

Обе ветки выполняются независимо:

1. `build_turn_frame_from_raw(obj, allowed_topics=...)`.
2. Существующая `_validate_plan(obj, ...)` + существующие protocol/focus guards.

Builder failure:

- не мешает strict branch;
- `shadow_frame=None`;
- итог `degraded`;
- valid legacy plan сохраняется и возвращается wrapper;
- не логировать exception text/raw как field error.

Strict failure:

- сохраняет существующий `turn_planner_failed`/fail-open semantics;
- не уничтожает успешно собранный frame;
- frame + `legacy_plan=None` → `partial`.

Обе ветки успешны:

- frame без `invalid/missing` → `ok`;
- frame с `invalid/missing` → `partial`, даже если legacy plan valid;
- guards/enrichment применяются только к `legacy_plan`, как сегодня;
- shadow frame остаётся описанием raw, не post-guard product decision.

### 6.3 Logging compatibility

- `log_llm_usage` ровно один раз на реальный call;
- legacy success event `turn_planner_llm` сохраняется при valid plan;
- legacy failure logging сохраняется при strict failure;
- не добавлять raw JSON/question/history в новые events;
- новый attempt не публикуется через `publish_turn_plan()`.

## 7. Backward-compatible wrapper

`plan_turn()`:

- сохраняет сигнатуру;
- сам не вызывает LLM кроме вызова `plan_turn_attempt()`;
- возвращает только `.legacy_plan`;
- не читает `.shadow_frame` для решений;
- existing callers/tests получают прежний `TurnPlan | None`.

Запрещено делать так:

```python
plan_turn_attempt(...)
plan_turn(...)  # второй LLM-call
```

Один публичный вызов = один attempt = максимум один call.

## 8. Обязательные тесты pure builder

Новый `tests/test_turn_frame_from_raw.py`:

1. valid full slice → correct intent/topic/aspects/primary + statuses/provenance.
2. A6 blocker `topic=doctors`, `aspects=[]` → topic valid, aspects/primary invalid с точными errors.
3. aspects missing/non-list/unknown/non-string.
4. route missing/non-string/unknown.
5. topic missing/null/blank с zero confidence.
6. topic invalid type/outside taxonomy.
7. confidence bool/non-number/out-of-range/positive without topic.
8. raw dict и nested values не мутируются.
9. unknown raw fields не попадают в frame.
10. model dump не содержит question/answer/history/raw/exception.
11. non-migrated axes имеют только `defaulted`, provenance `a7.not_migrated`.
12. source/AST firewall: нет planner/Flask/LLM/session/resolver/network imports и thematic tokens.

Не мокать production builder в его functional tests.

## 9. Обязательные тесты planner split

В `tests/test_turn_planner_llm.py` добавить/усилить:

1. valid payload → `PlannerAttempt(legacy_plan, shadow_frame, ok)`.
2. A6 aspects=[] + valid topic → legacy None, shadow partial, topic сохранён.
3. invalid topic + otherwise valid legacy → legacy semantics unchanged, shadow partial/topic invalid.
4. malformed JSON → not_available.
5. non-object JSON → not_available.
6. builder exception + valid strict plan → degraded + legacy plan сохранён.
7. builder exception + strict failure → degraded + legacy None.
8. strict exception + valid frame → partial.
9. empty question/catalog → not_available и 0 LLM calls.
10. `plan_turn()` вызывает LLM ровно один раз.
11. `plan_turn_attempt()` вызывает LLM ровно один раз.
12. wrapper result равен attempt legacy semantics для одинакового mocked response.
13. raw не мутируется между ветками; strict branch получает исходные values.
14. protocol guard/focus enrichment по-прежнему применяются только к legacy plan.
15. existing bad-json/fail-open tests сохраняются, не переписываются под новый status.
16. telemetry не получает raw/question/history/exception от builder.
17. downstream modules не импортируют/не читают `PlannerAttempt.shadow_frame`.

В `tests/test_planner_attempt_contract.py` разрешено изменить только прежний
`test_runtime_modules_do_not_import_planner_attempt`: `core/turn_planner_llm.py`
теперь является ожидаемым единственным runtime import для создания attempt,
но `core/turn_frame_shadow.py`, resolver, orchestration, app/llm и прочий
downstream по-прежнему обязаны не импортировать `PlannerAttempt` и не читать
`shadow_frame`.

LLM в unit tests только fake/mocked. Реальных вызовов быть не должно.

## 10. Product firewall

Доказать diff/AST/grep:

- `orchestration/**` без изменений;
- `core/turn_frame_shadow.py` без изменений;
- resolver/composer/evidence/policy/UI не импортируют `PlannerAttempt`;
- `turn_plan_to_decision_frame()` не читает native `shadow_frame`;
- `publish_turn_plan()` получает только valid `TurnPlan`;
- `TurnPlan` contract без изменений;
- widget response без изменений.

## 11. Запрещённые решения

Нельзя:

- второй LLM-call;
- retry;
- prompt changes ради `aspects`;
- `aspects=["overview"]` fallback;
- ослаблять strict validation;
- строить topic-only side channel;
- мутировать raw;
- передавать sanitized builder dict в `_validate_plan`;
- использовать partial frame downstream;
- логировать raw/user text/exception в field errors;
- расширять FieldErrorReason;
- добавлять новые runtime flags;
- тематические branches для doctors/extraction/A6 ids;
- менять frozen specs/hash;
- запускать live/LLM.

## 12. Acceptance criteria

A7 Planner split принят, если:

- allowlist соблюдён;
- pure builder покрыт functional negative tests;
- один raw идёт в две независимые ветки;
- raw immutable;
- strict branch unchanged;
- wrapper backward compatible;
- exactly one LLM-call;
- A6 blocker даёт partial frame, но wrapper `None`;
- builder failure не ломает legacy success;
- strict failure не уничтожает frame;
- no downstream wiring/authority;
- старые planner/shadow/product suites зелёные;
- 0 skip/xfail;
- hashes неизменны;
- live/LLM не запускались.

## 13. Команды проверки

Исполнитель запускает:

```powershell
python -m pytest -q tests/test_turn_frame_from_raw.py tests/test_turn_planner_llm.py
python -m pytest -q tests/test_turn_frame_contract.py tests/test_planner_attempt_contract.py
python -m pytest -q tests/test_turn_frame_shadow.py tests/test_metadata_first_observability.py tests/test_turn_planner_wiring.py tests/test_turn_plan_protocol_guard.py
python -m pytest -q tests/test_contacts_routing.py tests/test_pricebook_golden.py tests/test_price_layer_parity.py
python -m py_compile core/turn_frame_from_raw.py core/turn_planner_llm.py
git diff --check
git diff -- contracts core/turn_frame_adapter.py core/turn_frame_shadow.py orchestration llm.py app.py
git hash-object evals/v5/demo/topic_shadow_matrix.json
git hash-object evals/v5/demo/preservation.json
Get-FileHash -Algorithm SHA256 eval_topic_shadow_a6_last.txt
git status --short
```

В команде protected diff допустим только allowlist-файл `core/turn_planner_llm.py`; отдельно показать, что все остальные protected paths пусты.

## 14. Checker policy

Этот checkpoint меняет planner и поэтому требует **Cursor checker до implementation commit**.

Исполнитель после своих тестов:

1. не stage/commit;
2. готовит `drafts/checker_request.md`;
3. владелец запускает `.cursor/agents/checker.md`;
4. checker пишет `drafts/checker_last.md`;
5. только после `✅` и повторной проверки разрешён commit.

Checker обязательно проверяет exactly-one-call, raw immutability, fail-open compatibility и product firewall.

## 15. Stop conditions

СТОП, если:

- требуется файл вне allowlist;
- plan_turn legacy semantics меняются;
- невозможно изолировать builder failure;
- нужен новый error reason;
- strict branch получает modified raw;
- нужен runtime wiring;
- старый planner test требует ослабления;
- появляется реальный LLM-call;
- frozen hash изменён;
- найден unrelated WIP.

## 16. Отчёт Исполнителя

1. Diff тестов — первым.
2. Changed-files.
3. Builder semantics table.
4. Planner attempt state table.
5. Exactly-one-call evidence.
6. Raw immutability evidence.
7. Legacy/fail-open compatibility.
8. Product firewall.
9. Все команды §13: passed/failed/skipped/warnings.
10. Not run/logging errors.
11. Frozen hashes/raw SHA256.
12. Нарушения/сомнения `file:line`.
13. Commit не создан до checker.

## 17. Definition of Done

A7 Planner split завершён, когда один существующий LLM-call создаёт `PlannerAttempt` с независимыми partial shadow и strict legacy branches; `plan_turn()` остаётся backward-compatible product wrapper, partial frame ещё нигде не публикуется и не влияет на ответы.
