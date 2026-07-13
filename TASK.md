# TASK — A6 Harness: честный direct-planner runner для frozen topic matrix

Один активный `TASK.md` на одну маленькую задачу. Файл подготовлен **Архитектором** до реализации.
Общий закон — `.cursor/rules/00-guardrails.mdc`. Инварианты ревью — `REVIEW_CHECKLIST.md`.
Опора — `docs/ARCH_TARGET_DESIGN.md` v4, A5 commit `8662300` и frozen A6 spec commit `cd562fe`.

---

## 1. Зафиксированная точка старта

- A5 native topic shadow: `8662300`.
- A6 governance/spec task: `3f205f4`.
- Frozen A6 matrix: `cd562fe`.
- Frozen matrix path: `evals/v5/demo/topic_shadow_matrix.json`.
- Frozen matrix git-blob hash: `dc356c9c738fb80a10cf0035508d7e8c8247979d`.
- A0 preservation hash: `c2072ca74c2da73bf657d793195d2eb6c8ba7bd5`.
- Рабочее дерево перед реализацией должно быть чистым.

`topic` остаётся **shadow-only**. Этот harness только измеряет; он не меняет продукт и не разрешает authority.

## 2. Задача

**A6 Harness — создать отдельный строгий CLI-runner и unit-контракт для однократного direct-live измерения `TurnPlan.topic`.**

На этом checkpoint:

- создаётся harness;
- пишутся unit-тесты harness-контракта;
- unit/regression тесты запускаются;
- frozen spec не меняется;
- реальный LLM/live matrix **не запускается**;
- runtime/prompt/routing/evidence/composer/UI не меняются.

```text
frozen topic_shadow_matrix.json
          ↓ strict hash/schema/source validation
standalone run_topic_shadow_eval.py
          ↓ 33 × plan_turn(question, None, "demo")
A6_CASE JSONL + A6_SUMMARY JSON

product /ask pipeline ← не участвует и не меняется
```

## 3. Почему direct planner, а не `/ask`

A6 измеряет качество одной новой оси — native `TurnPlan.topic`.

Полный `/ask` добавил бы другие причины отсутствия frame: ingress, contacts boundary, resolver, evidence и composer. Это исказило бы denominator и снова проверяло бы старую маршрутизацию вместо topic-классификации.

Direct mode обязан использовать **реальный production `core.turn_planner_llm.plan_turn`**, его реальный prompt, taxonomy loader, sanitization и один существующий LLM-call. Разрешено исключить downstream, но запрещено подменять planner.

## 4. Затрагиваемые файлы — строгий allowlist

Исполнитель может создать только:

- `evals/v5/run_topic_shadow_eval.py`;
- `tests/test_topic_shadow_eval_contract.py`.

Исполнитель не меняет:

- `TASK.md`;
- `evals/v5/demo/topic_shadow_matrix.json`;
- `evals/v5/demo/preservation.json`;
- `core/**`, `contracts/**`, `orchestration/**`;
- существующие tests/runners/specs;
- client MD/config/pricebook/policies;
- architecture/audit docs.

Любой другой diff → ❌ и СТОП.

## 5. Frozen spec — protected

Runner до первого planner/LLM-вызова обязан:

1. Прочитать только canonical path `evals/v5/demo/topic_shadow_matrix.json`.
2. Самостоятельно вычислить git-blob hash байтов файла без вызова shell/git.
3. Сравнить с константой:

   `dc356c9c738fb80a10cf0035508d7e8c8247979d`

4. Аналогично проверить `evals/v5/demo/preservation.json`:

   `c2072ca74c2da73bf657d793195d2eb6c8ba7bd5`

5. При любом mismatch завершиться как **harness/config error до LLM calls**.

Допустимая реализация git-blob hash:

```text
sha1(b"blob " + ascii(len(data)) + b"\0" + data)
```

Не использовать `subprocess git hash-object`: runner должен быть воспроизводим без зависимости от git CLI.

## 6. Strict spec validation

До первого LLM-вызова runner валидирует весь frozen contract.

### 6.1 Верхний уровень

Разрешены ровно ключи frozen spec. Обязательные значения:

- `schema_version == 1`;
- `suite_id == "a6_topic_shadow_quality_matrix"`;
- `client_id == "demo"`;
- `execution_mode == "planner_direct_live"`;
- `fresh_session_per_case is true`;
- `authority == "shadow_only"`;
- taxonomy source совпадает со spec;
- frozen ordered taxonomy содержит ровно 9 ожидаемых тем;
- scoring contract совпадает со frozen semantics;
- cases = 33.

Unknown/missing keys → harness/config error, не warning.

### 6.2 Case schema и counts

Для каждого case разрешены ровно:

- `id`;
- `case_kind`;
- `question`;
- `expected_topic`;
- `source_doc_id`;
- `rationale`.

Проверить:

- 33 cases и 33 unique ids;
- 27 `grounded_single_topic`;
- 6 `ambiguous_null`;
- по 3 grounded на каждую из 9 тем;
- grounded: непустые expected/source/rationale;
- ambiguous: `expected_topic is None`, `source_doc_id is None`;
- expected только из taxonomy или `None`;
- вопрос непустой;
- никаких observed/current/pass/alternative fields.

### 6.3 Client source verification

Read-only проверить текущий demo pack **до LLM calls**:

- production `load_client_topic_taxonomy("demo")` как set совпадает с frozen taxonomy;
- каждый grounded `source_doc_id` найден по frontmatter `doc_id`, а не по имени файла;
- frontmatter `topic` source doc точно равен `expected_topic`;
- duplicate `doc_id`, malformed frontmatter или mismatch → harness/config error.

Не выводить полный текст клиентского документа.

## 7. CLI contract

Файл `evals/v5/run_topic_shadow_eval.py` — standalone CLI из корня репозитория:

```powershell
python evals/v5/run_topic_shadow_eval.py
```

CLI:

- не принимает `--case-id`;
- не принимает `--spec`, `--client`, `--retry`, `--repeat`;
- неизвестный аргумент → exit `2`;
- canonical spec/client зафиксированы внутри harness;
- не импортирует `app.py` и не поднимает HTTP server;
- корректно добавляет repo root в `sys.path` для запуска по указанной команде;
- не меняет environment flags;
- не пишет в spec/client files;
- не создаёт собственный cache/result JSON.

Raw console output будет сохранён внешним `Tee-Object` только на будущем Live checkpoint.

## 8. Planner call contract

После успешной preflight validation runner идёт по cases **в frozen порядке**.

Для каждого case ровно один вызов:

```python
plan_turn(case["question"], None, "demo")
```

Обязательно:

- production `plan_turn` загружается из `core.turn_planner_llm`;
- `sid=None` для каждого case гарантирует отсутствие history/follow-up context и не создаёт session DB rows;
- один case → один вызов функции;
- нет retry при `None`, exception, mismatch или timeout;
- ошибка одного case фиксируется, runner продолжает остальные cases;
- нельзя вызывать LLM заранее для taxonomy/source validation;
- нельзя использовать `turn_plan_to_decision_frame`, resolver или `/ask`;
- нельзя брать observed topic из legacy `service_topic`;
- observed = только возвращённый `TurnPlan.topic`;
- confidence = только `TurnPlan.topic_confidence`.

Dependency injection/fake planner разрешён **только unit-тестам** функции harness. Production CLI без параметров обязан использовать реальный symbol `core.turn_planner_llm.plan_turn`.

## 9. Case result contract

После каждого case runner печатает одну машиночитаемую строку:

```text
A6_CASE {json}
```

JSON содержит ровно:

- `index` — 1..33;
- `case_id`;
- `case_kind`;
- `expected_topic` — string/null;
- `observed_topic` — normalized string/null;
- `topic_confidence` — number/null;
- `status` — `PASS | FAIL | ERROR`;
- `reason` — стабильный enum.

Стабильные reasons:

- `exact_match` → `PASS`;
- `topic_mismatch` → `FAIL`;
- `planner_unavailable` → `ERROR` для `plan_turn() is None`;
- `planner_exception` → `ERROR`, exception не прерывает остальные cases;
- `invalid_or_out_of_taxonomy` → `ERROR`.

Правила безопасности output:

- не печатать raw LLM response;
- не печатать exception message/traceback в `A6_CASE`;
- не печатать вопрос повторно в result JSON;
- допустимо вывести только стабильный reason и `exception_type` отдельным optional полем **не добавлять** — case schema должна оставаться ровно указанной выше;
- production logging самого planner может присутствовать рядом в raw console, но метрики парсятся только по префиксам `A6_CASE`/`A6_SUMMARY`.

## 10. Нормализация и честная классификация результата

- `expected_topic` уже frozen normalized string/null.
- observed string: trim + lowercase.
- observed empty string → `null`.
- observed `null` точно сравнивается с expected `null`.
- observed string вне frozen taxonomy → `ERROR: invalid_or_out_of_taxonomy`, не обычный mismatch.
- confidence должен быть реальным number `0..1`; bool/NaN/out-of-range/non-number → `ERROR: invalid_or_out_of_taxonomy`.
- при observed `null` confidence должен быть `0.0`; иначе `ERROR: invalid_or_out_of_taxonomy`.
- при валидном observed topic confidence `0.0` допустим: confidence descriptive, это не fail само по себе.
- `topic_confidence` не используется для выбора observed topic и не влияет на match.

## 11. Summary contract

После 33 cases runner печатает ровно одну строку:

```text
A6_SUMMARY {json}
```

Summary обязан содержать:

- `suite_id`;
- `client_id`;
- `total` = 33;
- `passed`;
- `failed`;
- `errors`;
- `skipped` = 0;
- `overall_exact_match`: `{matched, total, rate}`; denominator всегда 33;
- `per_topic_exact_match` для всех 9 grounded topics: `{matched, total, rate}`;
- `ambiguous_null_exact_match`: `{matched, total, rate}` с total=6;
- `confusion_matrix`;
- `planner_unavailable_count`;
- `invalid_or_out_of_taxonomy_count`;
- `confidence_by_correctness_descriptive`;
- `authority_decision_allowed` = `false`.

### Confusion matrix

- строки = frozen expected topics + `__null__`;
- колонки = observed topics + `__null__`, `__planner_unavailable__`, `__invalid__`;
- сумма всех cells = 33;
- planner exception/None идут в `__planner_unavailable__`;
- invalid observed/confidence идут в `__invalid__`;
- confusion matrix не скрывает errors и не исключает их из denominator.

### Confidence descriptive

Отдельные buckets:

- `correct`;
- `incorrect` — только валидные mismatches;
- `invalid`;

Для каждого: `count`, `values`, `min`, `max`, `mean`.

Для пустого bucket: `count=0`, `values=[]`, `min/max/mean=null`.
Planner unavailable не имеет confidence и учитывается отдельным count.
Mean можно округлить детерминированно до 4 знаков; это зафиксировать тестом.

Никаких слов `calibrated`, `reliable`, `authority-ready` в вычисляемом результате.

## 12. Exit codes

- `0`: все 33 exact match, failed=0, errors=0;
- `1`: harness отработал честно, но есть topic mismatch и/или planner unavailable/invalid;
- `2`: spec/hash/taxonomy/source/schema/CLI configuration error до измерения.

Exit `1` — нормальный результат будущего аудита, не причина менять spec.

Harness не должен возвращать `0` только потому, что смог завершить run.

## 13. Unit-тесты — обязательный минимум

`tests/test_topic_shadow_eval_contract.py` должен доказать как минимум:

1. Frozen canonical spec проходит strict validation.
2. Git-blob hash вычисляется корректно.
3. Matrix hash mismatch останавливает runner до planner calls.
4. Preservation hash mismatch останавливает runner до planner calls.
5. Unknown/missing top-level key → config error.
6. Unknown/missing case key → config error.
7. Изменение scoring contract → config error.
8. Неверные counts/duplicate id/per-topic distribution → config error.
9. Taxonomy mismatch → до planner calls.
10. Source doc missing/duplicate/topic mismatch → до planner calls.
11. Fake planner в unit-тесте вызывается ровно 33 раза, по порядку, всегда с `sid=None`, `client_id="demo"`.
12. `None` не retry'ится, отмечается unavailable, следующие cases выполняются.
13. Exception не retry'ится, не escape'ится, следующие cases выполняются.
14. Exact string/null match работает.
15. Valid mismatch → FAIL и confusion cell.
16. Out-of-taxonomy/invalid confidence → ERROR и `__invalid__`.
17. Summary denominator и сумма confusion = 33 даже при errors.
18. Per-topic + ambiguous metrics корректны.
19. Confidence buckets descriptive и empty bucket null semantics.
20. Exit codes 0/1/2 различимы.
21. CLI не предлагает selective/retry arguments и rejects unknown args.
22. Production CLI default импортирует реальный `core.turn_planner_llm.plan_turn`; test injection не является CLI path.
23. Runner не импортирует `app`, resolver/composer/routing и не вызывает HTTP.
24. Frozen matrix и preservation hashes неизменны.

Тесты могут использовать fake planner только для детерминированной проверки harness-логики. Они не доказывают качество LLM; это сделает один будущий live run.

Запрещено:

- `skip`/`xfail`/`assert True`;
- тестировать только happy path;
- подменять frozen spec упрощённым файлом во всех тестах;
- ослаблять strict validation ради удобства fixtures;
- считать fake planner live proof.

## 14. Явно НЕ делать

- Не запускать реальный A6 live/LLM на Harness checkpoint.
- Не менять frozen matrix или expected.
- Не добавлять matrix в `run_demo_eval.py`.
- Не изменять smoke runner.
- Не менять `plan_turn`, prompt, taxonomy loader или contracts.
- Не добавлять новую классификацию/LLM-call.
- Не добавлять retry/parallelism/case filtering.
- Не добавлять confidence gate.
- Не давать topic authority.
- Не исправлять будущие mismatches в этом checkpoint.
- Не создавать commit/branch/stash без команды владельца.

## 15. Команды проверки Harness checkpoint

```powershell
python -m pytest -q tests/test_topic_shadow_eval_contract.py
python -m pytest -q tests/test_turn_planner_llm.py tests/test_turn_frame_shadow.py tests/test_turn_frame_contract.py
python -m pytest -q tests/test_contacts_routing.py tests/test_pricebook_golden.py tests/test_price_layer_parity.py
python -m py_compile evals/v5/run_topic_shadow_eval.py
python evals/v5/run_topic_shadow_eval.py --unexpected-argument
git diff --check
git status --short
git diff -- evals/v5/demo/topic_shadow_matrix.json evals/v5/demo/preservation.json
git hash-object evals/v5/demo/topic_shadow_matrix.json
git hash-object evals/v5/demo/preservation.json
```

Для команды с `--unexpected-argument` ожидается exit `2` и **0 planner/LLM calls**. Это CLI negative test, не live run.

Не запускать CLI без аргументов на этом checkpoint: это уже сделает 33 live LLM calls.

## 16. Стоп-условия

СТОП и эскалация, если:

- рабочее дерево до начала не чистое;
- нужен файл вне allowlist;
- frozen hashes не совпадают;
- для harness нужен runtime/prompt change;
- невозможно вызвать production planner без `/ask`;
- runner не может гарантировать один call на case;
- нужен retry/selective case flag;
- strict validation конфликтует со frozen spec;
- unit-тест расходится с planned live path;
- команда с unknown arg доходит до planner;
- preservation/matrix получили diff;
- появился посторонний файл или live artifact.

Формат:

```text
СТОП: требуется решение Архитектора
Факт:
Файл/строка:
Почему TASK нельзя выполнить дословно:
Варианты без самостоятельного выбора:
```

## 17. Контрольные точки

### Checkpoint 1 — Harness implementation

Исполнитель:

1. Создаёт только два allowlist-файла.
2. Запускает unit/regression команды раздела 15, кроме live CLI без args.
3. Показывает diff тестов первым.
4. Показывает полный production harness diff и changed-files.
5. Подтверждает hashes и отсутствие spec diff.
6. Делает СТОП без commit.

### Checkpoint 2 — Harness review

Checker независимо проверяет:

- protected spec/hash;
- allowlist;
- strict fail-before-LLM preflight;
- один call/case, no retry/filter;
- real production planner default;
- честные error/summary/exit semantics;
- негативные тесты;
- отсутствие live calls/artifacts.

Вердикт: `✅ / ❌ / ❓`.

### Checkpoint 3 — Harness commit

Только после `✅` владелец разрешает отдельный commit двух harness-файлов.

### Checkpoint 4 — Live proof

Будет отдельным следующим заданием после чистого harness commit. В нём допускается ровно один полный run, raw artifact и read-only audit. Этот checkpoint live не начинает.

## 18. Формат отчёта Исполнителя

1. Diff тестов — первым.
2. Полный changed-files.
3. Объяснение runner по блокам: preflight/calls/results/summary/exit.
4. Результаты каждой команды.
5. Все skipped/not run.
6. Доказательство no live/LLM calls и отсутствия A6 raw artifact.
7. Matrix/preservation hashes.
8. Нарушения/сомнения с `file:line`.
9. СТОП без commit.

## 19. Критерий приёмки A6 Harness

Harness принят, когда два новых файла позволяют честно и воспроизводимо измерить frozen 33-case matrix через реальный существующий `plan_turn`, до вызовов строго защищают spec/taxonomy/sources, гарантируют один call на case без retry/filter, сохраняют все ошибки в denominator/confusion matrix, не используют confidence как gate, не затрагивают runtime/downstream и полностью покрыты негативными unit-тестами.

Даже идеальный будущий live-результат не включает authority автоматически.
