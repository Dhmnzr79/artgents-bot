# D2 S2-C4 — опубликованные цены общего направления по typed situation

Дата: 2026-09-18. Исполнитель: Terra. Статус: подготовлено, код не менялся.
Продолжает S2-C3 (`3942318`). Это изолированный offline checkpoint, не разрешение
подключать D2 к работающему боту или начинать S3.

## 1. Preflight и границы

Папка/Git root: `C:\Cursor Projects\artgents-bot`.
Ветка: `codex/demo-d2-service-volume`.
Implementation baseline: `394231863c35005932422a5dbdb5ba6cdcaa9392`.
`origin/main` и merge-base: `141ce91fb1731cd990fcf8391550150016c73e7f`.

До правок прочитать `AGENTS.md` и сообщить полный preflight. Сохранить без
изменений external untracked WIP:

- `docs/audits/DEMO_D2_ARCHITECTURE_REVIEW.md`;
- `docs/audits/DEMO_D2_LATENCY_BASELINE.json`;
- `docs/audits/DEMO_D2_LATENCY_BASELINE.md`;
- `scripts/measure_d2_latency_baseline.py`;
- `docs/tasks/DEMO_D2_S3_ARCHITECTURE_GATE.md`.

Само это task file пока untracked; оно должно войти в C4 commit. Не делать
worktree, reset/clean/stash, merge/deploy, live/provider/SMTP calls, browser tests
или S3.

## 2. Цель простыми словами

Если человек одновременно спрашивает общую цену направления и сообщает объём,
например «Нет трёх зубов, сколько стоит восстановить?», C4 показывает только
утверждённые цены, которые каталог прямо считает применимыми к нескольким зубам.
Это **не** назначение моста, имплантов или другого лечения.

Если объём не сообщён, C4 показывает утверждённый общий обзор направления: до трёх
цен и, когда объём действительно меняет доступные цены, четыре утверждённые кнопки
«один зуб / несколько зубов / вся челюсть / Не знаю». Кнопки — необходимые choices
направления, не обычные price follow-up. Их подписи и refs не придумываются кодом.

«Не знаю» в этом checkpoint означает только утверждённый общий ответ без
персонального расчёта и без нового lead. Клик, session persistence, повтор вопроса
в следующих ходах и HTTP/UI остаются за C4.

## 3. Единственный путь и правила отбора

Единственный semantic input — parsed D1R `RequestUnderstanding.requests`. C3
already freezes optional `requests[].situation`; не создавать parser, envelope,
regex/dictionary recognizer или special-case по словам вопроса.

Применять situation к ценам **только** если всё верно одновременно:

1. request имеет `kind="price"`, `service_id=null` и подтверждённый `topic_id`;
2. это broad direction price request;
3. situation принадлежит этому же `request_id`;
4. `scope_commitment` — `reported`, `correction` или `hypothetical`, а extent
   известен.

`hypothetical` ограничивает только цены обсуждаемого варианта в этом ответе и не
меняет пациентский факт: `situation_delta` остаётся `keep`. `unknown`, `reset`,
отсутствующая situation и known structure с `extent=unknown` дают общий обзор и
не порождают повторное уточнение в этом ответе.

`tooth_count` и `jaw` хранятся в frozen plan, но не участвуют в арифметике. Для
`jaw=both` цена с единицей `jaw` остаётся ценой **за одну челюсть**. Не умножать,
не выбирать отдельный протокол и не спрашивать upper/lower, если цена одинаковая.

## 4. Данные и frozen plan

Не добавлять таблицу «scope → лечение». Использовать уже утверждённую применимость:
сначала `TargetOffer.applies_to_extents`, иначе явно заданный
`TargetService.selection.extent`, через существующий helper applicability. Это
проверка, что опубликованная цена применима, а не рекомендация лечения.

Для known situation отсутствие этих метаданных **не доказывает** применимость:
такие offers допустимы только для общего overview. Фильтровать кандидаты до
ranking/clinic order/лимита трёх, иначе допустимый четвёртый вариант может быть
потерян. Пустой strict набор даёт явный `d2_no_scope_price_candidates`; не
подставлять несовместимые цены и не строить пользовательский fallback в C4.

Добавить в materialization contract typed tenant-owned authority:

```text
D2VolumeChoice:
  extent: one_tooth | few_teeth | full_arch | unknown
  candidate: UiQuickReplyCandidate

D2DirectionPricePresentation:
  source_client_id
  topic_id
  introduction_text
  unknown_extent_text
  volume_choices
```

Authority проверяет tenant ownership, существующее `D2DirectionAuthority`,
уникальные topic/extent/reply IDs и не строит labels/ref сам. Fixture authority
может иметь четыре выбора; C4 не меняет clinic data.

Добавить в frozen response plan `D2PriceScopeDecision` с source price request/topic,
applied extent или `null`, причиной применения/неприменения, selected offer IDs,
утверждённым introduction/unknown text и typed mapping choices. Renderer и UI
projection используют только frozen plan.

Обычные source video/follow-up при цене по-прежнему подавлены. C4 volume choices
разрешены отдельно; CTA остаётся отдельным слотом. Direct exact-service цена C2 не
фильтруется scope правилом, не превращается в overview и не получает choices.

## 5. Exact allowlist

```text
contracts/response_plan.py
contracts/response_plan_materialization.py
core/response_plan_materialization.py
core/response_plan_resolver.py
core/response_text_renderer.py
core/response_ui_projection.py
tests/test_d2_price_scope_selection.py              NEW
tests/test_d2_volume_choices.py                      NEW
docs/tasks/DEMO_D2_S2_C4_TERRA_TASK.md
```

Читать, но не менять D1R/parser, response schema, clinic data, legacy scope helpers,
session, HTTP/SSE, widget, lead/privacy, prompt/provider, migrations, `app.py` и
orchestration. Если это невозможно, остановиться с точным blocker и двумя
вариантами Astra; не расширять scope молча.

## 6. Обязательные offline tests

Все positive fixtures: raw D1R JSON → `parse_production_envelope_json` →
`resolve_d2_envelope_response` → frozen plan → renderer/UI projection. Никаких
`model_copy(update=...)` без validation для positive input и никакой подмены
resolver/renderer.

Проверить:

1. Два направления: general overview до трёх цен и четыре authority-owned choices.
2. Reported/correction/hypothetical known one/few/full: только подтверждённо
   применимые offers; меню не показывается; delta остаётся `keep`.
3. Unknown/reset/absent situation: approved overview без персонального отбора и
   без повторного меню; «Не знаю» не создаёт lead или scope.
4. Choice menu отсутствует, если authority отсутствует либо extents дают одинаковый
   набор offers до обрезки. Допустимый offer после первых трёх исходных не теряется.
5. Offer без applicability metadata не попадает в known-scope ответ; пустой strict
   set не получает случайную цену.
6. Три зуба и обе челюсти: суммы/единицы неизменны, нет умножения/назначения.
7. Situation другого content request не влияет на price request.
8. Price+content: choices допустимы, видео/follow-up подавлены, CTA отдельна.
9. Foreign/duplicate authority отклоняется; frozen output стабилен после мутации
   input snapshots. Direct-service C2 price остаётся прежним.
10. Sentinel доказывает отсутствие Composer/legacy entry на direct D2 пути.

В конце выполнить один связный offline набор, составленный из C1–C4 тестов после
создания файлов; не запускать полный CI, HTTP/browser/live suite. Checker может
перезапустить только nodes для сомнительных C4 findings.

## 7. Checker и Git

Независимый read-only Checker обязателен до commit. После PASS: stage только exact
allowlist, inspect staged names/stat/full diff/`git diff --cached --check`, commit
и push в текущую branch. В отчёте указать tests/Checker/provider calls/staging/foreign
WIP. Явно сообщить: C4 не подключён к running bot, не исполняет кнопки, не пишет
session и не начинает S3.
