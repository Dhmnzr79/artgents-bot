# TASK — A3: аудит реального TurnFrame shadow на frozen-сценариях

Один активный `TASK.md` на одну маленькую задачу. Файл подготовлен **Архитектором** до выполнения.
Общий закон — `.cursor/rules/00-guardrails.mdc`. Инварианты ревью — `REVIEW_CHECKLIST.md`.
Проектная опора — `docs/ARCH_TARGET_DESIGN.md` v4.

---

## Зафиксированная точка старта

- A0 frozen spec: commit `e852f4b`, hash `c2072ca74c2da73bf657d793195d2eb6c8ba7bd5`.
- A0 harness: commit `a0e6926`.
- Старый live baseline: `preservation = 3/6`, `smoke = 24/24`.
- A1 TurnFrame contract: commit `0761213`.
- A2 shadow observability: commit `3746d77`.
- Рабочее дерево перед A3 должно быть чистым.

## Задача

**Название:** A3 — read-only аудит `turn_frame_shadow` на шести frozen preservation-ходах.

**Размер:** МАЛЕНЬКАЯ. Один live-прогон, анализ сырого telemetry и один audit-документ. **Код и spec не менять.**

**Цель:** увидеть, что фактически записывает новый `TurnFrame` на реальном `/ask/stream` pipeline, отделить заполненность полей от их корректности и выбрать следующий архитектурный шаг по evidence, а не по предположению.

A3 не пытается сделать старый runtime зелёным. Результат `preservation = 3/6` допустим как известный baseline. Блокерами A3 являются нечестный/неполный telemetry run, отсутствие shadow snapshot, ошибки среды или попытка подогнать spec/report.

## Затрагиваемые файлы (allowlist)

Исполнитель может создать/изменить **только**:

- `docs/TURN_FRAME_SHADOW_AUDIT_A3.md` — итоговый audit-документ.

Локальный сырой артефакт:

- `eval_turn_frame_shadow_a3_last.txt` — обязателен, но остаётся gitignored и не коммитится.

`TASK.md`, архитектурные документы, runtime, contracts, tests, eval runner, frozen spec и все существующие suite Исполнитель не меняет.

## Обязательный live-прогон

Использовать существующий suite без изменения spec:

```powershell
$env:E2E_USE_TEST_CLIENT="1"
$env:PYTHONUTF8="1"
$env:PYTHONIOENCODING="utf-8"
python evals/v5/run_demo_eval.py --client demo --suite preservation 2>&1 | Tee-Object -FilePath eval_turn_frame_shadow_a3_last.txt
$evalExit = $LASTEXITCODE
"EVAL_EXIT_CODE=$evalExit" | Tee-Object -FilePath eval_turn_frame_shadow_a3_last.txt -Append
Get-FileHash -Algorithm SHA256 eval_turn_frame_shadow_a3_last.txt
```

Exit code `1` допустим только из-за известных FAIL acceptance-кейсов. `errors`, timeout, skipped, transport failure или отсутствие одного из шести ходов — СТОП, а не повод объявить аудит готовым.

Не запускать кейсы повторно выборочно ради более красивого результата. Если полный прогон пришлось повторить по технической причине, сохранить отдельный файл с новым именем и перечислить все попытки в audit-документе; не перезаписывать неудачную попытку молча.

## Источник telemetry

Для каждого кейса использовать `turn_complete.details.turn_frame_shadow` из непрерывного JSONL-вывода того же live-прогона. Дополнительно сверить:

- `turn_frame_shadow_status`;
- `turn_frame_shadow_reason`, если есть;
- `request_id`, `sid`, `path`;
- фактический preservation PASS/FAIL и reason из итоговой таблицы runner.

Не собирать frame из разных событий/попыток. Не восстанавливать отсутствующие поля из ответа, вопроса или собственных догадок.

## Что выписать по каждому из 6 кейсов

В `docs/TURN_FRAME_SHADOW_AUDIT_A3.md` должна быть одна строка на кейс со следующими данными:

- case id;
- `/ask/stream` подтверждён;
- preservation result `PASS/FAIL` и краткая фактическая причина;
- shadow status/reason;
- `intent`;
- `topic`;
- `aspects` и `primary_aspect`;
- `emotion`;
- `specificity`;
- `patient_scope`;
- `service_id`;
- `follow_up` / `followup_of`;
- `needs_clarification`;
- request id или точная ссылка на строку сырого артефакта.

Отдельной компактной таблицей показать для каждой смысловой оси:

- значение;
- confidence;
- provenance;
- оценку `correct | wrong | missing | default_only | not_applicable`.

Если полей слишком много для одной широкой Markdown-таблицы, сделать по кейсу короткий блок и общую сводку по осям. Не исключать неудобные поля ради компактности.

## Правила честной оценки

- Заполненное поле не означает корректное поле.
- `confidence > 0` не доказывает корректность.
- `confidence = 0` не называть уверенным результатом.
- `topic = None` с `missing_legacy_axis` → `missing`.
- `emotion = none` с provenance `default` → `default_only`, а не распознанная эмоция.
- Значение, унаследованное из legacy, получает оценку по смыслу кейса, а не автоматически `correct`.
- Несовпадение с frozen target фиксируется как долг новой архитектуры; spec не менять.
- Свободную формулировку ответа не оценивать дословно.
- Один прогон из шести кейсов не доказывает статистическую стабильность и не разрешает перевод оси в authority без отдельной acceptance-сети.

## Обязательная итоговая сводка

Audit-документ должен ответить простыми словами:

1. Во всех ли шести ходах создан shadow-frame?
2. Были ли `degraded/not_available`?
3. Какие оси выглядят корректными на этой выборке?
4. Какие оси пустые, default-only или наследуют известную legacy-ошибку?
5. Совпадает ли frame с фактической причиной FAIL cases `02/03/05`?
6. Есть ли хоть одна ось, которую уже можно рассматривать кандидатом на следующий strangler-шаг?
7. Какой **один** следующий маленький TASK рекомендуется и почему?

Допустимый вывод: «ни одна ось пока не готова к authority; сначала нужен контракт/источник для topic». Нельзя обязательно выдумывать перенос, если telemetry этого не подтверждает.

## Запрещено

- Не менять runtime, shadow recorder, adapter, TurnFrame contract или telemetry wiring.
- Не менять `preservation.json`, harness, вопросы, expected/forbidden поля или hash.
- Не добавлять новый script/parser в репозиторий.
- Не менять существующие tests и не писать тесты под наблюдаемый результат.
- Не чинить cases `02`, `03`, `05`.
- Не resnapshot'ить LLM-ответы.
- Не выбирать лучший из нескольких прогонов и скрывать остальные.
- Не называть A2 authority: frame остаётся shadow-only.
- Не коммитить raw eval-файл.
- Не создавать commit/ветку/stash без явной команды владельца.

## Стоп-условия

Исполнитель обязан остановиться и выдать `СТОП: требуется решение владельца/Архитектора`, если:

- изменился любой файл вне allowlist;
- frozen hash не совпал;
- получено меньше или больше шести уникальных preservation-ходов;
- хотя бы один ход не прошёл через `/ask/stream`;
- shadow-frame отсутствует либо status не `ok` хотя бы в одном planner-success ходе;
- есть timeout/error/skipped/transport failure;
- сырые JSONL-строки невозможно однозначно связать с case id;
- для заполнения отчёта требуется догадаться о значении, которого нет в telemetry;
- live run пришлось повторить, но предыдущий сырой артефакт утрачен;
- требуется изменить код, spec или runner.

Формат остановки:

```text
СТОП: требуется решение владельца/Архитектора
Что обнаружено:
Какие есть варианты:
Риск каждого варианта:
Какие файлы потребуются:
```

## Проверки перед review

```powershell
git diff --check
git status --short
git diff --name-only
git hash-object evals/v5/demo/preservation.json
Get-FileHash -Algorithm SHA256 eval_turn_frame_shadow_a3_last.txt
```

Ожидание для tracked diff: только `docs/TURN_FRAME_SHADOW_AUDIT_A3.md`.

## Контрольная точка и приёмка

1. Выполнить один полный live-прогон.
2. Сохранить непрерывный сырой вывод и SHA256.
3. Создать audit-документ без изменений кода/spec.
4. Показать checker raw evidence, таблицу и tracked diff.
5. СТОП → checker → Архитектор.

A3 готова, когда все шесть ходов однозначно отражены в отчёте, оценки не путают наличие поля с корректностью, frozen hash сохранён и checker подтвердил происхождение каждой строки. Следующую реализационную задачу автоматически не начинать.
