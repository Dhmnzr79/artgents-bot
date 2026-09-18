# D2 S2-C5 — независимые части составного вопроса в едином frozen plan

Дата: 2026-09-18. Исполнитель: Terra. Статус: подготовлено, код не менялся.
Продолжает S2-C4 (`552d425`). Это изолированный offline checkpoint. Он не
подключает D2 к работающему боту и не начинает S3.

## 1. Preflight и границы

Папка/Git root: `C:\Cursor Projects\artgents-bot`.
Ветка: `codex/demo-d2-service-volume`.
Implementation baseline: `552d425d841e8ac26f8fc458fcac52a7ae32baa2`.
`origin/main` и merge-base: `141ce91fb1731cd990fcf8391550150016c73e7f`.

До правок прочитать `AGENTS.md` и сообщить полный preflight. Сохранить без
изменений external untracked WIP:

- `docs/audits/DEMO_D2_ARCHITECTURE_REVIEW.md`;
- `docs/audits/DEMO_D2_LATENCY_BASELINE.json`;
- `docs/audits/DEMO_D2_LATENCY_BASELINE.md`;
- `scripts/measure_d2_latency_baseline.py`;
- `docs/tasks/DEMO_D2_S3_ARCHITECTURE_GATE.md`.

Само это task file пока untracked; оно должно войти в C5 commit. Не делать
worktree, reset/clean/stash, merge/deploy, live/provider/SMTP calls, browser
tests или S3.

## 2. Цель простыми словами

Один пользователь может задать несколько независимых вопросов в одном сообщении:

> «Сколько стоят виниры и есть ли гарантия на импланты?»

Цена относится к винирам, а материал о гарантии — к имплантам. C5 сохраняет обе
связи в одном plan и выводит ответ в исходном порядке вопросов. Ни цена, ни
первый найденный материал не могут назначить услугу соседней части.

Это не новый parser: единственный semantic input остаётся parsed D1R
`RequestUnderstanding.requests`. Не вводить regex, словари, ComposerDecision,
второй envelope или новый путь понимания.

## 3. Граница checkpoint

Поддержать уже допустимые виды: `ANSWER`, максимум одну price-часть и одну или
несколько content-частей. Они могут относиться к разным услугам, направлениям
или, для явно общеклинического материала, к клинике в целом.

Не входят: несколько price requests, свободная модельная проза/T3, degraded
частичный успех, политики/контакты/terminal, акции, сравнения, session/TTL,
продолжения, click execution, tenant-data adapter, prompt/provider/runtime и
изменение clinic data. Ошибка ownership/schema остаётся явной ошибкой этого
turn, а не поводом тихо скрыть одну часть.

## 4. Единый frozen plan

D1R уже несёт `request_id`, `subject_id`, `service_id`, `topic_id` и
`content_ref`; его не менять. Добавить в `contracts/response_plan.py` frozen
`D2ResolvedRequestPart`:

```text
request_id
kind: price | content
status: answered
subject_id: str | null
scope: service | topic | clinic
service_id: str | null
topic_id: str | null
content_ref: str | null
```

В упорядоченном `d2_request_parts` существующих `PreComposerPlan` и
`ResolvedResponsePlan` хранится provenance, а не второе место для текста/цен.
Content-part связан с `InformationSourceBlock.request_id`; price-part — с
существующим `d2_price_block`.

Инварианты обязаны отвергать потерянную, лишнюю или повторённую part, mismatch
`content_ref`, content без source block и price без price block. Resolver, а не
модель, выставляет `status="answered"`.

Если в одном plan подтверждены разные scopes, разрешён ровно один новый маркер
`response_scope="mixed"`. Для него не выбирать общий `selected_service_id` или
`selected_topic_id`; session delta получает оба значения `null`. Это защита от
ложного фокуса, не реализация памяти. Однозначные прежние ответы не меняют
service/topic/clinic поведение.

## 5. Resolver, renderer и UI

- Каждая content part проходит `_d2_content_scope` по собственным refs и tenant
  snapshot. Source, ограниченный услугой/темой, без подтверждённой собственной
  привязки отклоняется. Clinic-wide source без service/topic разрешён независимо
  от соседней цены.
- C4 цена не меняется: known same-request situation фильтрует offers до
  ranking/cap независимо от optional presentation; отсутствие applicability не
  означает совместимость; strict empty остаётся `d2_no_scope_price_candidates`.
  Situation content part не влияет на price part.
- Renderer выводит проверенные blocks по порядку `requests`. Intro/цены/условия
  остаются единым price block; renderer не читает каталог.
- Content-only ответ показывает secondary UI первого content source по порядку;
  второй source не смешивает свои кнопки с первым. При наличии price source
  follow-up/video остаются подавленными; C4 volume choices и CTA сохраняют свои
  отдельные правила.
- После freeze изменение snapshot не изменяет повторный renderer/UI projection.

## 6. Exact allowlist

```text
contracts/response_plan.py
core/response_plan_materialization.py
core/response_plan_resolver.py
core/response_text_renderer.py
tests/test_d2_independent_request_parts.py           NEW
tests/test_d2_multi_request.py
docs/tasks/DEMO_D2_S2_C5_TERRA_TASK.md               NEW
```

`response_ui_projection.py`, D1R/parser, C1–C4 tests, session, HTTP/SSE,
widget, lead/privacy, data клиники, legacy runtime, prompt/provider и S3 gate
только читать. Если необходимо выйти за список или нарушить C4 semantics,
остановиться с точным blocker и двумя вариантами для Astra.

## 7. Обязательные offline tests

Positive fixtures проходят raw D1R JSON → настоящий
`parse_production_envelope_json` → `resolve_d2_envelope_response` → frozen plan
→ renderer/UI projection. Не подменять resolver/renderer и не собирать positive
input через `model_copy(update=...)` без validation.

Проверить не менее следующего:

1. Цена услуги A + content услуги B: верные независимые IDs/texts, `mixed`, без
   ложного active focus.
2. Тот же запрос в обратном порядке: порядок вывода соответствует `requests`,
   каждая привязка остаётся своей.
3. Две content parts разных услуг: оба authored text, secondary UI только у
   первого source.
4. Цена + clinic-wide гарантия без service/topic разрешены; ограниченный source
   без собственной привязки отклоняется.
5. Source другой услуги, чем указано в его собственной part, отклоняется. Успех
   A/B не ослабляет этот tenant/scope check.
6. Foreign tenant/source и повреждённый frozen linkage отклоняются без пропуска
   части или подстановки соседнего материала.
7. Broad price с own situation + content другого направления сохраняет C4
   filtering; чужая situation не влияет; strict-empty без presentation остаётся
   прежней ошибкой.
8. Цена вместе с source, у которого есть video/follow-up и C4 choices: обычные
   video/follow-up подавлены, допустимые choices и CTA сохраняются. Повторный
   renderer/UI после mutation snapshots неизменен.
9. Sentinel доказывает, что новый сценарий не вызывает Composer/parser executor
   или legacy semantic entry point и не делает сетевых вызовов.

Во время работы запускать только затронутые nodes. На checkpoint выполнить один
связный offline набор C1–C5, без полного CI, HTTP/browser/live suite:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_request_understanding_schema_offline.py tests/test_one_call_stage4_2_closed_envelope_production.py tests/test_response_plan_materialization.py tests/test_response_plan_materialization_integration.py tests/test_d2_single_request.py tests/test_d2_content_source_ui.py tests/test_d2_price_modes.py tests/test_d2_multi_request.py tests/test_d2_treatment_situation.py tests/test_d2_price_scope_selection.py tests/test_d2_volume_choices.py tests/test_d2_independent_request_parts.py
```

## 8. Checker и Git

Независимый read-only Checker обязателен до commit. После PASS: stage только
exact allowlist, inspect staged names/stat/full diff/`git diff --cached --check`,
commit и push в текущую branch. В отчёте указать tests/Checker/provider calls,
staging и foreign WIP. Явно сообщить: C5 не подключён к running bot, не исполняет
кнопки, не пишет session и не начинает S3.
