# TASK — A6 Live Proof: один frozen topic-matrix run

Один активный `TASK.md` на одну маленькую задачу. Файл подготовлен **Архитектором** до live-прогона.
Общий закон — `.cursor/rules/00-guardrails.mdc`. Инварианты ревью — `REVIEW_CHECKLIST.md`.
Опора — frozen A6 spec и принятый A6 harness.

---

## 1. Зафиксированная точка старта

- A5 native topic shadow: `8662300`.
- Frozen A6 matrix commit: `cd562fe`.
- A6 harness governance: `b99f02d`.
- A6 harness implementation: `952c50a`.
- Matrix path: `evals/v5/demo/topic_shadow_matrix.json`.
- Matrix git-blob hash: `dc356c9c738fb80a10cf0035508d7e8c8247979d`.
- Preservation git-blob hash: `c2072ca74c2da73bf657d793195d2eb6c8ba7bd5`.
- Harness: `evals/v5/run_topic_shadow_eval.py`.
- Рабочее дерево перед прогоном должно быть чистым.

`topic` остаётся **shadow-only**. Live Proof измеряет качество; не меняет runtime и не даёт authority.

## 2. Задача

Выполнить **ровно один** полный запуск frozen 33-case matrix через принятый direct-planner harness и сохранить непрерывный raw console output.

```text
frozen matrix + frozen harness
          ↓ один запуск без аргументов
33 × real plan_turn(question, None, "demo")
          ↓
33 A6_CASE + 1 A6_SUMMARY + exit code
          ↓
raw artifact → независимый checker
```

На этом этапе:

- код/spec/tests/docs не меняются;
- один полный live run разрешён;
- отдельные кейсы и повторный полный run запрещены;
- результат не исправляется;
- raw не коммитится;
- audit-doc пока не создаётся.

## 3. Разрешённый локальный артефакт

Разрешён только один новый gitignored-файл:

- `eval_topic_shadow_a6_last.txt`.

Он должен содержать весь вывод одной команды от начала до конца и последнюю строку:

```text
A6_EXIT_CODE=<0|1|2>
```

Не создавать:

- `_retry`, `_best`, `_fixed`, `_2`, `_final`;
- отдельные case dumps;
- обработанный/сокращённый log вместо raw;
- JSON/CSV summary рядом;
- audit markdown до checker review.

## 4. Pre-run gate — без LLM

До live-команды выполнить и показать:

```powershell
git status --short
git log -1 --oneline
git hash-object evals/v5/demo/topic_shadow_matrix.json
git hash-object evals/v5/demo/preservation.json
python -m pytest -q tests/test_topic_shadow_eval_contract.py
python -m py_compile evals/v5/run_topic_shadow_eval.py
Get-ChildItem -Force -File -Filter "eval_topic_shadow_a6*.txt" | Select-Object -ExpandProperty Name
```

Ожидается:

- clean status;
- HEAD содержит harness `952c50a` или более поздний governance commit без изменения harness;
- оба hash совпадают;
- harness unit = `34 passed`, skipped=0;
- raw-файлов A6 до запуска нет.

Если pre-run gate не совпал — **СТОП**, live не запускать.

## 5. Environment

Запускать из корня репозитория в текущем чистом PowerShell-сеансе.

Перед командой задать только кодировку:

```powershell
$env:PYTHONUTF8="1"
$env:PYTHONIOENCODING="utf-8"
```

Не переключать feature flags для улучшения результата. Direct harness не использует `/ask` и не требует `E2E_USE_TEST_CLIENT`.

Не менять model, timeout, prompt, API parameters или client.

## 6. Единственная live-команда

Выполнить ровно один раз:

```powershell
python evals/v5/run_topic_shadow_eval.py 2>&1 |
  Tee-Object -FilePath eval_topic_shadow_a6_last.txt
$a6Exit = $LASTEXITCODE
"A6_EXIT_CODE=$a6Exit" |
  Tee-Object -FilePath eval_topic_shadow_a6_last.txt -Append
```

После начала команды:

- не прерывать из-за первых FAIL;
- не перезапускать отдельный case;
- не запускать второй полный run;
- не редактировать raw;
- не менять spec/harness/tests;
- дождаться всех 33 case results и summary, если процесс технически продолжает работать.

## 7. Если run технически оборвался

Если PowerShell/процесс/машина/сеть оборвали run до `A6_SUMMARY`:

1. Сохранить неполный `eval_topic_shadow_a6_last.txt` как есть.
2. Не удалять и не перезаписывать его.
3. Не делать автоматический retry.
4. Зафиксировать фактический exit/code и последний case index.
5. СТОП → эскалация Архитектору.

Повтор возможен только отдельной явной командой владельца с новым именем артефакта. Лучший из нескольких run выбирать запрещено.

## 8. Честная семантика результата

### Topic mismatch допустим

`FAIL: topic_mismatch` — полезный результат аудита. Он не блокирует честность raw и не является поводом менять frozen expected.

### Technical error не скрывать

Следующие результаты блокируют признание run полноценным quality sample:

- `planner_unavailable_count > 0`;
- `invalid_or_out_of_taxonomy_count > 0`;
- `errors > 0`;
- отсутствует хотя бы один case/summary;
- harness/config exit `2`.

При этом raw всё равно сохраняется. Автоматический retry запрещён; дальнейшее решение принимает Архитектор.

### Exit codes

- `0`: 33/33 exact match;
- `1`: harness завершил matrix, есть mismatch и/или technical case error;
- `2`: preflight/config failure.

Exit `1` сам по себе не говорит, честный это mismatch или техническая проблема. Нужно читать `A6_SUMMARY`.

## 9. Проверки raw после run — read-only

Не создавая скрипт/файл и не меняя raw, проверить:

- строк `A6_CASE ` = 33;
- indices = 1..33 без дублей/пропусков;
- case ids совпадают с frozen spec и идут в frozen порядке;
- строк `A6_SUMMARY ` = 1;
- `summary.total = 33`;
- `passed + failed + errors = 33`;
- `skipped = 0`;
- сумма confusion matrix = 33;
- per-topic содержит все 9 тем с total=3;
- ambiguous total=6;
- `authority_decision_allowed=false`;
- последняя строка `A6_EXIT_CODE=...` согласуется с summary;
- в raw нет второго набора `index=1`/второго summary.

Одноразовая read-only команда/inline parser допустимы. Не сохранять обработанный результат в новый файл.

## 10. Что показать в отчёте

### 10.1 Raw integrity

- полный путь и размер raw;
- SHA256 raw после добавления `A6_EXIT_CODE`;
- число `A6_CASE` и `A6_SUMMARY`;
- first/last case id;
- continuity/order check;
- exit code.

### 10.2 Quality metrics — переписать из raw без переоценки

- overall matched/33 и rate;
- passed/failed/errors/skipped;
- per-topic matched/3 для всех 9 тем;
- ambiguous-null matched/6;
- `planner_unavailable_count`;
- `invalid_or_out_of_taxonomy_count`;
- только ненулевые confusion cells;
- confidence buckets как descriptive values/mean, без слов о калибровке;
- список каждого FAIL/ERROR: case id, expected, observed, confidence, stable reason.

### 10.3 Инварианты

- tracked `git status --short` после run;
- hashes matrix/preservation после run;
- подтверждение, что code/spec/tests не менялись;
- список всех файлов `eval_topic_shadow_a6*.txt`;
- количество live attempts = 1.

## 11. Запрещённые интерпретации

Даже если результат 33/33:

- не писать, что confidence calibrated;
- не объявлять topic authority-ready;
- не подключать topic к routing/evidence/composer;
- не менять TARGET architecture;
- не переходить автоматически к удалению legacy route;
- не исправлять продуктовые preservation FAIL этим run.

Если результат красный:

- не менять вопросы/expected/source docs;
- не ослаблять exact match;
- не объединять темы задним числом;
- не добавлять aliases/hardcode prompt в рамках A6;
- не запускать ещё раз «для проверки».

A6 Live Proof отвечает только на вопрос: **как существующий native topic сработал на заранее замороженной матрице в одном честном run**.

## 12. Затрагиваемые файлы

Tracked changes не разрешены.

Единственный разрешённый local artifact:

- `eval_topic_shadow_a6_last.txt` — gitignored.

Если `git status --short` после run показывает tracked/untracked не-gitignored файл — СТОП.

## 13. Post-run команды

```powershell
Get-FileHash -Algorithm SHA256 eval_topic_shadow_a6_last.txt
Get-Item eval_topic_shadow_a6_last.txt | Select-Object FullName,Length,LastWriteTime
Get-ChildItem -Force -File -Filter "eval_topic_shadow_a6*.txt" |
  Select-Object Name,Length,LastWriteTime
git status --short
git diff --check
git diff -- evals/v5/demo/topic_shadow_matrix.json evals/v5/demo/preservation.json evals/v5/run_topic_shadow_eval.py tests/test_topic_shadow_eval_contract.py
git hash-object evals/v5/demo/topic_shadow_matrix.json
git hash-object evals/v5/demo/preservation.json
```

`git diff` по protected/harness должен быть пустым.

## 14. Стоп-условия

СТОП, если:

- pre-run gate не прошёл;
- raw уже существовал до запуска;
- команда была запущена более одного раза;
- процесс оборвался;
- нет 33 cases или одного summary;
- exit=2;
- errors/unavailable/invalid > 0;
- raw/summary расходятся;
- hashes изменились;
- появился tracked diff;
- хочется исправить mismatch или повторить run.

При mismatch с errors=0 run не повторять: показать честный результат checker.

## 15. Контрольные точки

### Checkpoint 1 — One live run

Исполнитель выполняет pre-run gate, один live run, read-only raw checks и СТОП без commit.

### Checkpoint 2 — Independent raw review

Checker:

- не запускает live повторно;
- проверяет raw hash/continuity;
- независимо пересчитывает summary из 33 `A6_CASE`;
- сверяет frozen expected/order;
- проверяет отсутствие технических ошибок и повторов;
- отделяет topic mismatches от harness failures;
- не даёт authority.

Вердикт:

- `✅` — один полный технически чистый quality sample, даже если есть honest mismatches;
- `❌` — raw/spec/harness подогнаны или нарушены границы;
- `❓` — sample технически неполный, нужен отдельный выбор владельца о новом полном run.

### Checkpoint 3 — Audit document

Только после raw review Архитектор подготовит отдельное задание на audit-doc. На текущем этапе audit-doc не создавать.

## 16. Формат отчёта Исполнителя

1. Pre-run gate.
2. Live command и attempts=1.
3. Raw path/size/SHA256/exit.
4. Continuity/schema checks.
5. Полные quality metrics.
6. FAIL/ERROR cases.
7. Confidence descriptive buckets.
8. Post-run git/hashes.
9. Skipped/not run.
10. Явный СТОП без commit.

## 17. Критерий приёмки A6 Live Proof

Этап принят, когда один и только один непрерывный run содержит все 33 frozen cases и один summary, raw сохранён без редактирования, метрики независимо воспроизводимы, технических errors/unavailable/invalid нет, mismatches не скрыты и не перезапущены, protected hashes и tracked tree не изменились.

Это измерение, а не переключение архитектуры.
