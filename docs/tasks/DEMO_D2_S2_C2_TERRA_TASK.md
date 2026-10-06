# D2 S2-C2 — самостоятельная цена и информационный ответ с UI источника

Дата: 2026-09-18. Исполнитель: Terra. Статус: подготовленное ограниченное задание.
Это продолжение S2, не разрешение начинать S3 или переключать работающий бот.

## 1. Preflight, baseline и правила работы

Папка и Git root: `C:\Cursor Projects\artgents-bot`.
Ветка: `codex/demo-d2-service-volume`.
Implementation baseline: `b9e0de66b4b5ab992429ac9be41b1ee319699e67` (S2-C1).
Известный локальный `origin/main` и merge-base:
`141ce91fb1731cd990fcf8391550150016c73e7f`.

Прочитать AGENTS.md и выполнить его preflight до правок. Это продолжение текущей
задачи: не создавать ветку, worktree, соседнюю папку и не переключать checkout.
Если после подготовки задания HEAD изменился, установить точные новые коммиты:
допустимо продолжить через документационные коммиты этой же задачи, но изменение
кода/ветки/baseline требует остановки и сверки задания. Не делать reset/clean/stash.

До начала реализации в папке сохранены untracked:
- `docs/audits/DEMO_D2_ARCHITECTURE_REVIEW.md`;
- `docs/audits/DEMO_D2_LATENCY_BASELINE.json`;
- `docs/audits/DEMO_D2_LATENCY_BASELINE.md`;
- `scripts/measure_d2_latency_baseline.py`;
- `docs/tasks/DEMO_D2_S3_ARCHITECTURE_GATE.md` — готовый документ границ будущего S3.

Эти пять файлов не изменять и не включать в коммит C2. Само это задание пока также
untracked; оно входит в allowlist C2 и должно попасть в его checkpoint-коммит.
Сохранить текст требований; для отчёта дописать отдельный раздел результатов.

Авторитет: текущая инструкция владельца → AGENTS.md → это задание →
`DEMO_D2_TARGET_CONTRACT.md` и `DEMO_D2_ACCEPTANCE.md` →
`DEMO_D2_S1_EXECUTION_PLAN.md`. S3 gate — read-only ограничения интеграции.
Исторические документы не возвращают отменённые продуктовые правила.

## 2. Цель и точные границы

Развить **существующий** `resolve_d2_envelope_response`, чтобы он принимал:

1. Один `price` request без обязательной content-части.
2. Один `content` request без обязательной price-части.
3. Уже поддержанный C1 запрос `price + content` с прежними гарантиями.

Единственный смысловой вход — `OneCallEnvelope.request_understanding.requests`,
разобранный `parse_production_envelope_json`. Не создавать новый parser, второй
semantic envelope или service-specific обработчики вопросов.
Названия внутренних `PreComposerPlan`/`ComposerResult` можно сохранить как DTO
механической сборки. Это не разрешает вызывать `ComposerDecision`/отдельный Composer.

Пользовательские примеры — подписи сценариев, а не строки для сопоставления в коде:

| Пример | Что доказывает этот checkpoint |
|---|---|
| «Сколько стоит имплантация?» | Один price request, до 3 проверенных цен направления, единицы и условия; не нужен фиктивный вопрос о боли |
| «Сколько стоит отбеливание?» | Один price request точной услуги; тот же путь, без специальной ветки по названию |
| «Боюсь боли» | Один content request, проверенный текст/источник, video/follow-up из этого источника по лимитам |
| «А гарантия есть?» с явной привязкой в fixture envelope | Другой source/ref того же механизма; UI принадлежит материалу о гарантии, а не боли |
| «Сколько стоит имплантация и больно ли это?» | Цены и текст о боли; обычные follow-up/видео подавлены даже при наличии кандидатов |

Работа полностью изолирована, на fixture tenant-данных. HTTP/SSE/виджет/LLM не
подключать. Эти проверки не доказывают понимание живой моделью вопроса без контекста.
Автоматические акции, рассрочка и маркетинговые добавления остаются следующими
checkpoint S2; fixtures C2 не содержат применимых таких дополнений. Нельзя представить
результат как готовый полный ценовой ответ для production.
Кнопки объёма для направления и исполнения их кликов, continuity/TTL, политики,
неизвестная услуга, несколько разных услуг и частичные ошибки также не входят в C2.
Существующие C1-возможности не сокращать под новый узкий тест.

Для информационных примеров C2 проверяется **authored-блок**, как в C1: источник
предоставляет точный утверждённый текст. Не объявлять это общей политикой всех
информационных ответов. Свободная модельная проза и её правила T3 остаются явной
незавершённой возможностью S2; новый regex/semantic sanitizer здесь не строить.

## 3. Архитектурные требования

### Один центр и осмысленный план

Цена без content: не подставлять служебный `patient_text`, пустой source block или
фиктивный request, чтобы обойти `answer_requires_patient_text`. Согласованно
разрешить чистый ценовой окончательный план; окончательный ANSWER без видимого
содержимого по-прежнему недопустим. Не ослаблять все terminal/clarify инварианты.

Content без цены: не вызывать price projection и не требовать наличие offer/условий
для информационного ответа. Допускается общий материал без service_id/topic_id,
если authority явно общеклиническая. Источник с ограничением услуг не становится
общеклиническим при пустом ID: нужна подтверждённая привязка. Связи проверяет код
по typed refs/данным, не по словам вопроса или написанного ответа.

Цена использует C1 fixed/from/range/no_public, clinic order и лимит 3. Не умножать
стоимость; неизвестные/отсутствующие обязательные условия не считать complete.
Для составного сценария сохранить source/price provenance и запреты C1.
Неподдержанный режим даёт явную contract error; не переходит в старую сборку.

### Привязка UI к источнику

Связать разрешённый UI с `D2AuthoredContentAuthority`/его `content_ref` в проверенном
tenant snapshot: можно расширить существующий тип или добавить небольшой typed
source-UI record в том же contracts-файле. Использовать существующие типы UI,
не создавать альтернативный UI engine. Global `sources.ui_authority` сам по себе
не доказывает принадлежность follow-up/видео выбранному источнику.

Модель выбирает source ref, а код проверяет tenant, наличие в доступном снимке,
разрешённую связь с услугой и список UI этого источника. Не восстанавливать ref
по готовому тексту. Frozen plan содержит provenance выбранного source/UI;
последующие renderer/projection не перечитывают source/catalog и не меняют выбор.

Информационный ответ: непоказанное видео первым, затем непоказанные follow-up
в порядке материала, суммарно до 2 secondary. Если видео уже показано — можно
показать до двух оставшихся follow-up. Для этого достаточно **входного typed
snapshot уже показанных refs** в materialization sources, без session store.
Неповтор здесь проверяется на двух чистых вызовах с явной передачей фактически
выбранных refs; это не доказательство сохранения истории работающим ботом.
CTA — отдельный слот, максимум одна: утверждённая CTA источника, иначе явно
переданная общая CTA клиники. Не изобретать подпись/бесплатность и не добавлять
текстовый призыв самостоятельно. Правило неповтора secondary не запрещает CTA.

В C2 fixtures нет кандидата «Рассказать о ситуации»: его разрешения/lead-интеграция
не входят в scope; порядок/лимит для имеющихся video/follow-up не менять.
Для цены и price+content обычные secondary отсутствуют; явно разрешённая CTA
может остаться. Существующую явно выбранную textual CTA C1 не расширять и не
превращать в автоматическое завершение каждого ответа.

Сломанный необязательный UI не должен стирать корректный основной текст:
неразрешённый candidate исключается с диагностикой. Нарушение tenant ownership
самой authority/источника отклоняется до сборки, а не «исправляется» чужими данными.
Если UI просто отсутствует в источнике, не брать кнопки соседнего материала.

## 4. Exact write allowlist

```text
contracts/response_plan.py
contracts/response_plan_materialization.py
core/response_plan_materialization.py
core/response_plan_resolver.py
core/response_text_renderer.py
core/response_ui_projection.py
tests/test_d2_multi_request.py
tests/test_d2_price_modes.py
tests/test_d2_single_request.py                 NEW
tests/test_d2_content_source_ui.py              NEW
docs/tasks/DEMO_D2_S2_C2_TERRA_TASK.md
```

Это максимальная граница, а не требование изменить все файлы. Новые маленькие
типизированные data records размещать в указанных contracts, не в новых модулях.
D1R contract/parser читать и использовать без изменения: уже умеет одноэлементный
requests. Если это неверно для необходимого fixture, остановиться и показать
точное ограничение, не обходить parser через model_copy/model_construct.

Запрещены правки `app.py`, orchestration, prompt/provider, session/lead/privacy,
данных клиник, старого runtime, Composer parser/executor, migrations, виджета,
`.env` и старых временных папок. Никаких live/provider/SMTP, merge/deploy.

## 5. Порядок выполнения и доказательства

1. Preflight и краткий отчёт; убедиться, что этот scope соответствует HEAD.
2. Добавить проверяемые fixtures самостоятельной цены и content, разобранные
   настоящим D1R parser. Не добавлять второй request ради зелёного теста.
3. Обобщить существующую materialization для отсутствующей price/content-части,
   согласовать инварианты окончательного плана. UI source binding и выбор до freeze.
4. Проверить полный изолированный путь parser → resolver → renderer → UI projection,
   включая negative cases; затем один перечисленный regression набор.
5. Independent Checker по готовому diff; при REJECT исправить причину и перепроверить
   только находки/затронутые тесты. Затем точный commit/push. S3 не начинать.

Минимальная матрица новых тестов:

| Проверка | Что проверять снаружи |
|---|---|
| Один price, общее направление и точная услуга | Не пустой ответ; 1–3 правильные цены/единицы/реальные непустые условия, без выдуманного content, correct frozen IDs; второй fixture направления исключает special-case |
| Одна цена без условий | Unknown/missing completeness не публикует цену; нет старого fallback |
| Один content | Утверждённый текст и нужный ref, отсутствуют цены даже при наличии offers; общеклинический source допустим без услуги |
| Pain vs warranty | В snapshot одновременно оба источника с разными кнопками; ответ по одному не получает UI другого |
| Лимит и повтор | Видео+1 follow-up, затем показанное видео отфильтровано и до 2 новых follow-up; израсходованные refs не возвращаются; CTA считается отдельно |
| Пустой/недопустимый UI | Нет UI в документе → нет заимствования; invalid optional candidate не уничтожает текст; foreign tenant source отклонён |
| Price+content regression | Доступны видео, follow-up и CTA: первые два подавлены, CTA допустима; обе части текста присутствуют |
| Freeze | После получения плана изменение исходных data/UI snapshots не меняет повторный renderer/projection этого плана |
| Инварианты | Окончательный полностью пустой ANSWER невозможен; чистая цена допустима; terminal/clarify запреты не ослаблены |
| Только D1R | Parser получает raw JSON fixtures; отдельный Composer/legacy callable под sentinel не вызывается новым путём |

Не подменять resolver или renderer готовым результатом. Не считать проверку
`quick_replies == ()` достаточной без доступных запрещённых кандидатов. Не использовать
только пустые условия для доказательства условий цены. Новые positive scenarios
не должны обходить схему через `model_copy(update=...)` без повторной валидации.
Для corrupt-boundary negative tests обход допустим лишь с явным объяснением цели.

Команда связного offline набора после появления NEW-файлов:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_request_understanding_schema_offline.py tests/test_one_call_stage4_2_closed_envelope_production.py tests/test_response_plan_materialization.py tests/test_response_plan_materialization_integration.py tests/test_d2_multi_request.py tests/test_d2_price_modes.py tests/test_d2_single_request.py tests/test_d2_content_source_ui.py
```

В разработке запускать отдельные nodes из этого списка. На готовом checkpoint —
один связный прогон. Полный CI, HTTP/browser/live latency не запускать. Checker
может использовать этот отчёт и запускать только нужные nodes для конкретных
сомнений; не повторять автоматически весь зелёный набор. Сеть заблокирована,
backend только fixture: C2 не вызывает модель даже ради «одного smoke».

## 6. Остановка, проверка и Git

Остановить затронутую часть и сформулировать вопрос Astra с двумя вариантами, если
нужны второй смысловой контракт, восстановление источника по словам, обход D1R,
изменение клинических правил/PII или файл вне allowlist. Показать конкретный тип,
fixture и конфликт. Не расширять scope до всех оставшихся возможностей S2.
Если архитектура ясна, но две содержательные попытки реализации одной причины
безуспешны — передать Sol только воспроизведение и diff этого участка.

Checker — независимый read-only агент по `docs/WORKFLOW_CHECKER.md`, scope только
C2 diff и перечисленные проверки. Ни повторного аудита бота, ни заявления о готовом
runtime. PASS нужен до commit. Существующие baseline failures отделить от новых.

Stage только реально изменённые точные пути allowlist и это задание. Перед commit:
staged names/stat/полный diff/`git diff --cached --check`. Затем commit с названием
`feat: support standalone D2 price and source-bound content` и push в
`origin codex/demo-d2-service-volume`. Не создавать/merge новый PR автоматически.

В финальном отчёте: branch/commit/push, изменённые файлы, доказанные сценарии,
тесты/Checker, provider calls 0, staging и внешние WIP. Чётко указать: изменения
пока не включены в работающий бот; остальные S2-возможности и S3 ещё не завершены.

## 7. Результаты реализации

Выполнено на `b9e0de66b4b5ab992429ac9be41b1ee319699e67`:

- `resolve_d2_envelope_response` принимает одну price-часть, одну content-часть
  или сохранённую C1-пару частей из того же разобранного D1R envelope.
- Чистая цена получает видимый frozen price block без служебного текста; финальный
  ANSWER без текста, source block или цены остаётся запрещённым.
- У source content появился typed source-owned UI: video, follow-up и одна CTA.
  Выбор сохраняет `source_content_ref` в frozen UI plan. Цена подавляет source
  secondary, но сохраняет явно разрешённую CTA.
- Новый вход `shown_d2_secondary_ref_ids` моделирует неповтор показанных refs
  только в чистой materialization fixture; два чистых вызова проверяют перенос
  фактически показанных secondary refs. persistence/runtime не подключались.
- Некорректный необязательный source UI (например, CTA не типа `cta`) исключается
  с диагностикой и не стирает approved text. Tenant ownership authority по-прежнему
  отклоняется на входе.
- Frozen plan повторно рендерится после мутации исходных data snapshots без
  повторного чтения каталога; пустой final ANSWER и terminal/clarify с visible price
  остаются недопустимы.

Проверка выполнена локально, без сети/provider/SMTP:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_request_understanding_schema_offline.py tests/test_one_call_stage4_2_closed_envelope_production.py tests/test_response_plan_materialization.py tests/test_response_plan_materialization_integration.py tests/test_d2_multi_request.py tests/test_d2_price_modes.py tests/test_d2_single_request.py tests/test_d2_content_source_ui.py
```

Результат: `174 passed` (231 существующее предупреждение `datetime.utcnow` в
logging). Provider/SMTP calls: 0. HTTP/SSE/widget/session/lead/privacy и S3 не
менялись. Independent Checker: PASS после focused recheck прежних P1; staging
был пуст, `git diff --check` прошёл.
