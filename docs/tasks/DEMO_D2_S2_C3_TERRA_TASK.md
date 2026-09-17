# D2 S2-C3 — типизированная ситуация лечения в единственном D1R-конверте

Дата: 2026-09-18. Исполнитель: Terra. Статус: подготовлено, код не менялся.
Это следующий изолированный checkpoint после S2-C2 (`cc66207`). Он не разрешает
начинать S3, подключать работающий бот или возвращать старую логику объёма.

## 1. Preflight и границы

Папка и Git root: `C:\Cursor Projects\artgents-bot`.
Ветка: `codex/demo-d2-service-volume`.
Baseline реализации: `cc66207a529771a15444aa7fed59179ece3322aa` (S2-C2).
`origin/main` и merge-base: `141ce91fb1731cd990fcf8391550150016c73e7f`.

Перед правками прочитать `AGENTS.md` и сообщить path/root, branch/HEAD,
`origin/main`/merge-base, полный concise status и foreign WIP. Сохранить без
изменений следующие untracked материалы:

- `docs/audits/DEMO_D2_ARCHITECTURE_REVIEW.md`;
- `docs/audits/DEMO_D2_LATENCY_BASELINE.json`;
- `docs/audits/DEMO_D2_LATENCY_BASELINE.md`;
- `scripts/measure_d2_latency_baseline.py`;
- `docs/tasks/DEMO_D2_S3_ARCHITECTURE_GATE.md`.

Это задание тоже пока untracked. Оно входит в C3 checkpoint-коммит. Не делать
reset/clean/stash, merge/deploy, реальных LLM/provider/SMTP-вызовов, live/browser
проверок и не начинать S3.

## 2. Цель

Добавить в **единственный** D1R semantic contract —
`OneCallEnvelope.request_understanding.requests` — одну необязательную
типизированную ситуацию лечения. Это turn-local факт, который принадлежит одному
уже существующему request и может быть связан с его `subject_id`, `service_id` и
`topic_id`.

Пример допустимого смысла:

```json
{
  "request_id": "r1",
  "kind": "price",
  "subject_id": "s1",
  "service_id": null,
  "topic_id": "implantation",
  "statement_mode": "question",
  "situation": {
    "scope_commitment": "reported",
    "extent": "few_teeth",
    "tooth_count": 3,
    "jaw": "upper",
    "continuity": "unknown"
  }
}
```

Здесь `statement_mode="question"` правильный: человек одновременно спрашивает
цену и сообщает факт. Поэтому `statement_mode` сам по себе не устанавливает
достоверность ситуации. Это делает `situation.scope_commitment`.

Результат C3 — проверенная и frozen ситуация в центральном response plan. Она ещё
не меняет каталог, цены, сессию или UI. Это важно: C3 переносит смысл из модели в
единый план, а следующий checkpoint отдельно применит этот смысл к данным и памяти.

## 3. Единственная модель данных и правила

Добавить `RequestTreatmentSituation | None` как поле `RequestUnderstandingRequest`.
Не создавать второй envelope, Composer parser, сервисный обработчик, словарь или
regex-классификатор.

У ситуации ровно такие данные:

- `scope_commitment`: `unknown | reported | correction | hypothetical | reset`;
- `extent`: `unknown | one_tooth | few_teeth | full_arch`;
- `tooth_count`: положительное число или `null`;
- `jaw`: `unknown | upper | lower | both`;
- `continuity`: `new | same | unknown`.

Ситуация не дублирует subject/service/topic: используются ссылки owning request.
В одном `RequestUnderstanding` допускается максимум одна непустая ситуация. Две
разные ситуации не склеивать и не выбирать «последнюю»: это явный contract error.

Проверки структуры:

- `one_tooth` допускает count `null` или `1`; `few_teeth` — `null` или `>= 2`;
  `unknown` не допускает count; `full_arch` может сохранить явно названный count,
  но не превращается из-за него в `few_teeth`;
- `reset` требует unknown extent/jaw и count `null`;
- `correction` — новое отдельное утверждение, без слияния с прошлым; `hypothetical`
  остаётся вариантом и не является командой менять факт;
- request с `subject_id=null` не может утверждать `continuity="same"`: D1R IDs
  существуют только внутри текущего envelope и не являются постоянными профилями;
- service/topic проверяются обычным C2 resolver по snapshot текущего tenant;
  оба отсутствовать могут, но это не разрешает коду выбрать услугу по словам;
- count не выводится из цены, протокола, числа имплантов, названия услуги или текста.

Старые глобальные `RequestUnderstanding.scope_commitment/tooth_count` и top-level
`OneCallEnvelope.extent/jaw` не являются входом C3. Для fixture с новой situation
глобальные поля остаются нейтральными (`unknown`/`null`). Ненейтральное legacy поле
вместе с nested situation — явный conflict, не объединение. C3 resolver не читает
top-level `extent/jaw`; замена их значений не меняет frozen situation.

Не использовать `ResponseSituationState` из post-Composer/session пути: это старый
сессионный тип без count/subject, а не semantic input D1R.

## 4. Frozen plan

Расширить центральный plan только небольшим typed turn-local decision, содержащим:

- source request ID;
- subject relation и age group из текущего parsed envelope (если subject есть);
- проверенные service/topic refs;
- `scope_commitment`, extent, count, jaw и continuity.

`resolve_d2_envelope_response` получает уже parsed D1R envelope, валидирует refs и
вкладывает эту decision в frozen plan до renderer/UI projection. Renderer и UI её не
пересчитывают. `situation_delta` остаётся `keep`: C3 не пишет session и не реализует
TTL, continuation или merge прошлых ходов.

Чистый вопрос о цене без `situation` не создаёт потребность, не выбирает лечение и
сохраняет C2 поведение. Цена без объёма по-прежнему определяется только существующим
C2 scope; C3 не добавляет фильтрацию цен по situation.

## 5. Exact allowlist

```text
contracts/request_understanding.py
contracts/response_plan.py
core/response_plan_materialization.py
core/response_plan_resolver.py
tests/test_request_understanding_schema_offline.py
tests/test_d2_treatment_situation.py                 NEW
docs/tasks/DEMO_D2_S2_C3_TERRA_TASK.md
```

Production parser уже вызывает `RequestUnderstanding.model_validate`, поэтому
`core/one_call_envelope_protocol.py` и `contracts/one_call_envelope.py` не менять.
Если конкретный parser blocker докажет обратное, остановиться, назвать символ и
предложить два варианта Astra; не расширять allowlist молча.

Запрещены изменения HTTP/SSE, widget, session store, lead/privacy, prompt/provider,
clinic data, legacy runtime, Composer parser/executor, migrations, `app.py`,
orchestration, `.env` и foreign WIP.

## 6. Обязательные offline-проверки

Все positive fixtures строятся raw JSON → `parse_production_envelope_json` →
`resolve_d2_envelope_response` → frozen plan/renderer/UI. Нельзя создавать
positive input через `model_copy(update=...)` без валидации или подменять resolver.

Проверить:

1. Цена направления без situation не создаёт потребность.
2. Reported: один зуб; несколько зубов без числа; явно три; полная верхняя,
   нижняя и обе челюсти.
3. `reported`, `correction`, `hypothetical`, `reset` дают разные frozen решения;
   `question` request с reported situation допустим.
4. Unknown/null не дополняются из catalog или legacy `extent/jaw`.
5. Invalid: неизвестный subject, `same` без subject, service/topic mismatch,
   две situation, неверный count, unknown с count, reset с фактами и conflict
   legacy+nested input.
6. Смена top-level legacy `extent/jaw` при неизменном typed request не меняет
   frozen situation. Смена prose при неизменной typed structure также не меняет её.
7. После materialization изменение snapshots не меняет повторный renderer/UI frozen
   plan. C1/C2 standalone price/content/source UI regressions остаются зелёными.
8. Sentinel доказывает, что direct D2 path не вызывает старый Composer/legacy entry.

В конце выполнить только такой связный offline набор:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_request_understanding_schema_offline.py tests/test_one_call_stage4_2_closed_envelope_production.py tests/test_response_plan_materialization.py tests/test_response_plan_materialization_integration.py tests/test_d2_multi_request.py tests/test_d2_price_modes.py tests/test_d2_single_request.py tests/test_d2_content_source_ui.py tests/test_d2_treatment_situation.py
```

Во время работы запускать только затронутые nodes. Полный CI, HTTP/browser и live
tests не запускать. Затем independent read-only Checker только по C3 diff.

## 7. Stop conditions и Git

Остановить работу и сформулировать точный вопрос Astra с двумя вариантами, если
потребуются второй semantic envelope/parser, разбор raw user text кодом, session
write, HTTP/UI, клиническая политика, данные клиники или файл вне allowlist.

После PASS Checker: stage только реальные файлы allowlist, проверить staged
names/stat/full diff/`git diff --cached --check`, commit и push в текущую ветку.
Не начинать S3. В отчёте указать branch/commit/push, changed files, tests, Checker,
provider calls, staging и foreign WIP. Явно сказать, что C3 ещё не включён в bot.
