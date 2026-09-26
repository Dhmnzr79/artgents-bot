# D2-REC-1 — карточка безопасной диагностики

Дата: 2026-09-25. Статус: Draft реализации REC-1. После review документов владелец отдельно разрешил реализацию на текущей ветке и точечную установку тестовых пакетов. Новые Checker/Cursor verdict нужны для кода; они сообщаются отдельными отчётами, не записываются внутрь проверяемого diff. REC-2–5, live, merge и deploy не разрешены.

## 1. Что предлагается согласовать

Не новый rewrite, не возврат старой ветки и не перенос папок. Продолжить сверку/доработку существующего D2 в одной active-папке. Первый ограниченный checkpoint — безопасная диагностика существующего runtime. Остальные обнаруженные дефекты остаются открытыми и получают собственные карточки.

Связь с действующей roadmap: восстановление недостающего evidence/diagnostics перед завершением демо-приёмки этапа 5; пробелы этапов 1–4 не объявлять закрытыми. Порядок восстановления закреплён в [действующем roadmap](DEMO_D2_DELIVERY_ROADMAP.md) по разрешению владельца на документацию. Это единственный источник последовательности; [inventory](DEMO_D2_RECONCILIATION_INVENTORY.md) фиксирует сохранённую работу, а [Ledger](DEMO_D2_CHECKPOINT_LEDGER.md) — evidence. Исторические PASS не переписывать задним числом.

## 2. Preflight и baseline

- Единственная папка разработки/запуска: `C:\Cursor Projects\artgents-bot-active`.
- Подтверждённый baseline реализации: `a185b54a19481d83af9998fd8f6176b0baadfad7`; diff от `e261383` содержит только четыре проверенных документа. Tracked clean до начала REC-1, staging пуст; foreign `data/` сохранён.
- Git top level должен совпадать с ней.
- Документы готовятся в существующей незавершённой D2-задаче на `codex/d2-stage1-contract`, без создания новой ветки от старого main. Продолжение реализации на этой ветке должно быть явно включено в последующий GO владельца.
- Зафиксированный runtime baseline: `e261383515d94e7d925acc705d8a6731aa704e48`.
- Baseline текущего review документов — тот же HEAD плюс только четыре разрешённых документа ниже. После их review и отдельно разрешённого commit будущая реализация стартует с точного hash документационного checkpoint, указанного в closeout и подтверждённого новым preflight. Diff от `e261383` до этого hash должен содержать только эти четыре документа. Произвольный более новый descendant не считается разрешённым baseline.
- `origin/main` и merge-base: `141ce91fb1731cd990fcf8391550150016c73e7f`.
- До документального diff tracked clean, staging пуст. Foreign/untracked: active `data/`; old WIP, архивы, логи, env, venv, debug SQLite вне записи.
- Новый preflight обязателен перед исполнением. При другом HEAD, содержательном dirty diff, занятом другим исполнителем файле или другой папке — остановиться и показать расхождение.
- `b8b28d3` — read-only reference, НЕ baseline реализации и НЕ разрешение cherry-pick/merge.

### Allowlist завершённой подготовки — только документы

```text
docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md
docs/tasks/DEMO_D2_RECONCILIATION_INVENTORY.md
docs/tasks/DEMO_D2_RECOVERY_DIAGNOSTICS_TASK.md
docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md
```

На документальном шаге: без code edits, тестовых запусков, установки пакетов, staging,
commit/push, live, merge, deploy и очистки. Новые untracked Markdown-файлы
проверяются явно: обычный `git diff` их не показывает.
PASS документов не является PASS runtime и не разрешает следующую реализацию.

## 3. Checkpoint D2-REC-1 — диагностируем, не меняя ответы

### Результат для владельца

При следующей проверке можно установить: какая сборка обрабатывала запрос, на каком шаге он остановился, был ли вызов модели, был ли сохранён результат и завершилась ли доставка. Один случайный номер попытки связывает события этой попытки. Новые диагностические события не содержат переписку или личные данные; очистка всех прежних app-логов этим checkpoint не обещается.

Это НЕ исправление всех ответов и НЕ закрытие C03: публикация prose будет отдельным следующим checkpoint.

### Write allowlist REC-1 — активирован отдельным GO владельца

```text
app.py
core/d2_diagnostics.py                         # новый, внутренний observer
core/d2_http_adapter.py
core/d2_dialogue.py
core/d2_live_provider.py
tests/test_d2_diagnostics.py                   # новый
tests/test_d2_http_contract.py
tests/test_d2_http_scenarios.py
tests/test_d2_live_provider_offline.py
docs/tasks/DEMO_D2_RECOVERY_DIAGNOSTICS_TASK.md # evidence исполнения карточки
docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md          # только явно одобренное дополнение
docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md        # новая Draft/evidence строка
```

Наличие файла в allowlist не обязывает менять его. Любая необходимость другого файла — сначала объяснение и согласование, не молчаливое расширение.

Read-only: все contracts, store/schema, price/content materializers, state contracts, tenant data, logging_setup, widget assets, launcher, requirements, `.env`, `.venv`, runtime data. Старые `d2_full_audit.py`/`d2_outcome.py` не копировать.

### Архитектурная граница

Единственный существующий путь: `/ask` или `/ask/stream` → D2 adapter → common turn → существующий provider/parser/materializer/store → готовый ответ. Observer наблюдает эти шаги, но не выбирает ветку, не чинит envelope и не управляет состоянием.

- Без изменения visible answer/UI, HTTP-кодов, public JSON/SSE payload, done/error semantics или headers.
- Без изменения исходных классов исключений, их propagation, rollback/retry/commit/effect порядка.
- Не импортировать старый finalizer/semantic runtime ради логов.
- Не запускать второй prompt/parser/provider или дополнительный selection/render.
- Не создавать новый persisted state, DB/schema/migration, запись в completion/fingerprint/session или глобальную карту запросов.
- Ошибка построения/сериализации/записи события не влияет на исход операции. Нельзя замаскировать исходное исключение ошибкой logger.

### Состав и защита новых событий

Явный allowlist скалярных полей: случайный `attempt_trace_id`, имя события/шага, закрытый reason code, безопасный относительный code site, известный outcome, длительность по monotonic clock, число реально начатых provider attempts. Код сборки/путь исходников — в безопасном startup/provenance событии; commit только когда достоверно установлен, иначе unknown, без fetch и без Git-процесса на каждом ходе.

Нельзя писать: raw question/answer, HTTP body/headers/cookies, provider messages/raw envelope, content snippets, model_dump целых объектов, exception message/traceback/locals, имена/телефоны, произвольные request_id/sid/tenant strings.

Использовать existing no-context logging (`log_json_no_context`) или эквивалентную уже имеющуюся безопасную точку, чтобы обычный Flask logger не добавлял raw identifiers обратно. Форматные reason codes — закрытый словарь, неизвестное исключение → unknown; не извлекать произвольный текст ошибки.

**Выбранное минимальное предложение корреляции:** только случайный trace одной попытки. Raw `request_id` не считать безопасным: текущая валидация допускает произвольный текст. Не добавлять хеширование, HMAC-ключи или новую персистентность в REC-1. Replay логируется как исход текущей попытки, но автоматическая связь повторов между попытками/рестартами этим checkpoint не обещается. Если такая связь обязательна, это отдельный выбор до расширения карточки.

Trace/stage не являются ordinary state, живут только в попытке, очищаются в `finally`, включая исключения и SSE disconnect. Генератор SSE не читает уже закрытый Flask request context.

### Честная фиксация исходов

- Отдельно отличать сохранение результата, повтор сохранённого результата и завершение транспорта.
- Disconnect после подтверждённого commit не помечается как утрата результата.
- Если состояние commit нельзя подтвердить из уже существующего control flow — `unknown`, не придумывать false/true и не выполнять дополнительный SQL ради логов.
- HTTP 200 не считать готовым ответом; duration до конца SSE не подменять latency открытия потока.
- Таймер охватывает существующий provider call и фиксирует duration при успехе/исключении. Replay/provider bypass — 0 попыток; не придумывать provider latency.

## 4. Проверки и критерий закрытия REC-1

Сначала фиксируются текущие ответы/статусы/state как baseline; этот checkpoint не должен менять их. Fake provider/внешний effect и diagnostic sink допускаются; production parser и общий turn не заменяются обходным успешным stub. Для негативных тестов разрешена точечная fault injection на существующих store/transport/serialization границах с проверкой исходного поведения. Это не разрешение заменять семантическую сборку или ослаблять контракты.

Обязательные случаи:

1. JSON success и malformed-provider failure: trace, step, safe reason; исходный ответ/код неизменен.
2. SSE success, failure до commit, disconnect до начала и после commit; корректное разделение commit/delivery.
3. Replay даёт тот же сохранённый answer/UI/state, 0 новых provider calls; event replay не выдаётся за новую генерацию.
4. Provider error и timeout: одна фактическая попытка, правильный stage/timing, без raw error text.
5. Parser, materialization, store и payload/transport failure: различимые безопасные категории; при недостатке сведений unknown.
6. Принудительно сломанный diagnostic sink/serializer: обычный успех остаётся успехом, исходное исключение не меняется, повторного эффекта/записи нет.
7. Две сессии/tenant и последовательные запросы: traces не смешиваются и не остаются в следующем ходе. Cleanup при GeneratorExit.
8. Синтетические PII/secrets во всех входах, request_id, sid, exception text: в новых диагностических событиях ничего из этого нет. Не заявлять scrub всех старых app-логов: проверяется новый diagnostic channel.
9. Existing no-legacy, lead/privacy, JSON/SSE parity, mixed plan и frozen replay продолжают проходить на зафиксированных fake envelopes.

Planned focused set:

```text
tests/test_d2_diagnostics.py
tests/test_d2_live_provider_offline.py
tests/test_d2_http_contract.py
tests/test_d2_http_scenarios.py
tests/test_d2_no_legacy_path.py
tests/test_d2_lead_scenarios.py
tests/test_d2_stage4_mixed_response.py
tests/test_d2_widget_replay.py
```

Сеть/provider/SMTP запрещены. Temporary tenant copy/DB/logs; рабочие data/SQLite не трогать. Browser harness использует fake transport и отдельный temporary профиль, не рабочий порт 9001.

Gate окружения закрыт отдельным разрешением владельца: в active `.venv` добавлены только pytest 9.1.1, colorama 0.4.6, iniconfig 2.3.0, packaging 26.3, pluggy 1.6.0, Pygments 2.21.0. Установка exact versions с `--no-deps`; ранее установленные версии сохранены, `pip check` успешен. Interpreter: `C:\Cursor Projects\artgents-bot-active\.venv\Scripts\python.exe`, Python 3.12.14. Старый аудит на другом interpreter остаётся только историческим evidence; новые установки или обновления не разрешены автоматически.

Связь с acceptance: диагностика поддерживает C01/C05/C06/C09/C10; regression constraints C04/C08 и A12. REC-1 не объявляет эти требования полностью закрытыми и не закрывает A01–A15 автоматически.

Один независимый Checker на готовый checkpoint, focused recheck после REJECT. Для документальной карточки и первого checkpoint восстановления обязателен отдельный Cursor review. До review Ledger содержит только проверенные факты/Draft; не присваивать overall demo PASS.

## 5. После REC-1 — отдельные согласуемые карточки

| Часть | Что исправлять | Что не терять / что доказать |
|---|---|---|
| REC-2: контракт/prose | Optional ref missing/malformed/nonexistent, existing ref без service/topic; сохранение пригодной prose по D2-092/C03; выровнять содержательные ожидания тестов | Один parser, source UI только при проверенном ref, foreign tenant rejection, mixed partial failure, пустой/unparseable текст не fake success |
| REC-3: память | Однозначно выбранный exact service без topic → persisted state → следующий вопрос; situation, clarify task, typed clicks, TTL | Не угадывать по label/тексту и не назначать фокус произвольно из нескольких услуг multipart; не переносить ситуацию другого человека/темы; не возвращать lead consent; сохранить price refs |
| REC-4: цены/UI | Различимые названия/бренды и краткая цена; существенные условия; детали по запросу; нейтральная overview вводная; очистка anchor label | Exact ascending без лимита, overview authored cap 3, brand/volume filter, отсутствие арифметики «три зуба», demo-only complex offer, refs не меняются |
| REC-5: общая приёмка | Все A/B/C семьи, commercial/directory, ошибки, lead/tenant/privacy, replay/обрыв SSE; сверка remaining old tests | Не скрывать baseline failures; одна сборка и её окружение; затем отдельно разрешённые live и owner widget checks |

После каждой реализации — целые затронутые диалоги, включая следующий ход и replay; общая приёмка не заменяет эти локальные доказательства.

Для этих частей код сейчас не разрешён. Точные baseline/allowlist формируются после предыдущего checkpoint. Не превращать таблицу в бессрочный допуск править любые файлы.

## 6. Что требуется решить владельцу

Владелец разрешил документационную фиксацию, затем реализацию REC-1 в текущей D2-ветке и отдельно шесть тестовых пакетов. Режим логов — без переписки/PII, trace одной попытки, без изменений публичного протокола. Никакие последующие продуктовые изменения этим GO не разрешены.

Не требуется сейчас выбирать формат каждой строки кода или повторно утверждать уже принятые D2-092/093.

До последующих visible changes отдельно решить только реально открытые варианты:

- общий `contacts`: сохранить нынешний телефон или показывать адрес+телефон; точные `contact_address`/`contact_phone` остаются точными;
- если данных недостаточно для безопасного отделения существенных условий от подробностей — не скрывать условия самостоятельно, показать владельцу конкретный пример;
- raw transcript, correlation между рестартами, новый wire, новая персистентность — не входят в это согласование.

## 7. Исторический Cursor prompt проверки документов на e261383

```text
Проверь documentation-only checkpoint D2-REC-DOC и карточку D2-REC-1 read-only.
Это review плана, не задача реализации.
Активный repo: C:\Cursor Projects\artgents-bot-active.
Ветка codex/d2-stage1-contract; HEAD/baseline e261383515d94e7d925acc705d8a6731aa704e48.
Сначала AGENTS.md, docs/WORKFLOW_CHECKER.md, затем docs/tasks/:
DEMO_D2_EXECUTION_LOCK.md, DEMO_D2_DELIVERY_ROADMAP.md,
DEMO_D2_TARGET_CONTRACT.md, DEMO_D2_ACCEPTANCE.md,
DEMO_D2_CHECKPOINT_LEDGER.md, DEMO_D2_RECOVERY_DIAGNOSTICS_TASK.md,
DEMO_D2_RECONCILIATION_INVENTORY.md.
Проверь diff только четырёх документов из allowlist текущей задачи;
две новые Markdown-карточки могут быть untracked — открой их явно.
Остальной tracked код должен совпадать с HEAD; data/ — foreign WIP, не трогать.
Проверь 36/36 inventory, связь пяти шагов с этапами 1–5, отсутствие
задним числом назначенных PASS и необоснованных гарантий сохранности.
Проверь актуальность preflight и точный будущий allowlist. Ничего не меняй.
b8b28d3 из старого репозитория — только историческое evidence, не патч к переносу.
Проверь: diagnostic-only действительно не меняет parser/prompt/state/rollback/
commit/effect/error или public JSON/SSE/widget contract; нет raw PII через
автоматический context; trace очищается; sink failure не меняет исход;
commit/replay/delivery и неизвестный исход различаются честно;
provider timing не запускает новые вызовы; known baseline failures не скрыты.
Не требуй возврата legacy finalizer или raw transcript для полноты логов.
Проверь, не выдаёт ли карточка разрешение исправлять следующие этапы заранее.
Дай PASS/REJECT именно для документационного checkpoint и карточки,
с severity, файлом/строкой, противоречием и минимальным исправлением.
PASS карточки не является implementation PASS или owner approval.
Без edits/tests/live/staging/commit/push/merge/deploy.
```

## 8. Stop conditions и завершение

Остановиться при drift baseline, неизвестном WIP, необходимости изменить пользовательское поведение/wire/tenant/lead boundaries, установить пакеты без отдельного решения или выйти за allowlist. Astra помогает разобрать архитектурный конфликт, но не даёт owner approval.

После одобрения и реализации — отчёт: HEAD, exact diff, тесты и окружение, baseline failures, provider calls, review status, staging/push state, remaining WIP. Commit/push только после требуемых review и в рамках полученного разрешения; merge/deploy отдельно. Текущий подготовительный шаг ничего не stage/commit/push.

Старые папки, архивы, data, logs, env и venv не удалять даже после REC-1 PASS. Завершение диагностики не равно готовности бота.

## 9. REC-1 — evidence реализации и точечных проверок

**ACCEPTANCE:** узкая диагностика C01/C05/C06/C09/C10; no-legacy и lead/privacy
регрессии C04/C08/A12. Не закрывает C03 или всю демо-приёмку.
**D2 ROUTE:** реальные JSON/SSE → существующий adapter/common turn →
тот же provider/parser/materializer/store. **LEGACY IMPACT:** legacy не добавлен.
**OWNER DECISION:** получен GO только на REC-1 и шесть тестовых пакетов.
**FUTURE SCOPE:** REC-2–5 и live остаются отдельными задачами.

Фактические файлы: app.py; core/d2_diagnostics.py (новый),
core/d2_http_adapter.py, core/d2_dialogue.py, core/d2_live_provider.py;
tests/test_d2_diagnostics.py (новый); эта карточка, Roadmap, Ledger.
Остальные разрешённые тестовые файлы не потребовали изменения.

Наблюдатель:
- Один случайный attempt_trace_id; только закрытые шаги/reason и скаляры.
  Существующий log_json_no_context; сырые exception args, сообщения модели,
  request_id/sid/tenant IDs, body, headers и traceback не публикуются.
- Первая ошибка сохраняет исходный шаг, наружные catch не перетирают его.
  Неизвестная причина/commit остаются unknown.
- Метки после обоих store.complete; replay отдельный, без нового вызова.
  Уже существующий rollback SQL не дублируется; отсутствие записи complete
  логируется как completion_not_found, не как доказанный rollback.
- Счётчик/timer измеряет вызов D2HttpProvider._transport, не prompt builder
  и не возможные внутренние SDK retries. Подменённый целиком FakeProvider
  не является транспортной попыткой; тесты диагностики подменяют transport.
- JSON http_returned и SSE stream_done_emitted не доказывают получение
  браузером. SSE ContextVar устанавливается только на время next/close,
  сбрасывается до yield; close до первого next также наблюдается.
- Startup source_snapshot содержит commit=unknown и SHA256 только пяти
  файлов _SOURCE_FILES в d2_diagnostics.py на диске на момент startup.
  Это не хеш всего репозитория и не гарантия соответствия уже импортированному
  коду после правок на диске. Абсолютные пути/имена пользователя не логируются.
- Ошибки построения/сериализации/записи событий не управляют ответом.
  Новые события идут в существующий локальный app.jsonl; старые события
  не очищаются и не объявляются полностью свободными от PII.

### Выполненные проверки

До code edits, на a185b54, согласованные семь existing test files:
38 passed / 2 failed. Один failure — test_cp3_prompt_reuses_v19_contract_and_typed_d2_snapshot:
ожидается v19 при существующем v20; второй — browser harness timeout в sandbox.
Первичный temp root: d2-rec1-baseline-ab988dd5c0894ec69421001bcab04cdf.

После реализации: восемь файлов, 64 passed / 2 failed; browser harness прошёл
при разрешённом offline-запуске вне sandbox. Оставались тот же v19 failure
и новый диагностический fixture, ошибочно разрешавший authored recovery.
У fixture убран только content_fallback_section_ref, чтобы он действительно
проверял существующий content gate; код поведения и assertions не ослаблены.
Focused recheck всего нового файла после уточнения: **26 passed**.
На тот момент полный повтор после изменения одного fixture не выполнялся;
26 passed не пересчитывались в новый aggregate. Первый aggregate root:
d2-rec1-verify-66aeba8097d4480c936131f4214eec89; focused root:
d2-rec1-focused-bf0da95e25d84124b41816f91b1710b2. Все находятся в OS temp.

Последующий независимый полный прогон восьми файлов §4, согласно отчёту
Cursor, переданному владельцем: **65 passed / 1 failed**, 111 секунд.
Единственный failure — прежний test_cp3_prompt_reuses_v19_contract_and_typed_d2_snapshot
(v19 вместо v20). Provider/live/SMTP 0; рабочая data не изменялась по отчёту.
Это отдельный последующий прогон, а не исправление исторического 64/2.

После этого владелец разрешил точечную проверку замечания о позднем сбое
monotonic. При чтении текущего кода подтверждено: _finish уже имеет @_quiet;
новая production-правка не требуется и не выполнялась. В tests/test_d2_diagnostics.py
добавлены шесть случаев сбоя часов после успешного _begin: HTTP success/error,
SSE exhaustion/error и close success/error. Проверяются фактический вызов
сломанных часов, идентичность результата/исключения, значение StopIteration,
сброс ContextVar и повторный close. Старые тесты не ослаблялись.
Focused прогон всего файла после добавления: **32 passed**, 143 существующих
utcnow warnings, 20.84 секунды. Temp root:
d2-rec1-late-clock-bc9a1e632b4346969d2498fd64305a64.
Команда и изоляция те же, что ниже; выбран только tests/test_d2_diagnostics.py.
Новый полный aggregate после этих шести случаев не заявляется.

Использованы существующие production parser, tenant snapshot, D2 turn,
store и реальные Flask endpoints. Внешний transport fake, сеть/SMTP
заблокированы fixtures, временные tenant/SQLite/logs. Widget harness
headless, temporary профиль и динамический localhost-порт, не 9001.
PYTHON_DOTENV_DISABLED=1, CHAT_API_KEY=offline-placeholder, BOT_PG_DSN пуст,
APP_ENV=local, PYTHONDONTWRITEBYTECODE=1, PYTEST_DISABLE_PLUGIN_AUTOLOAD=1.
BOT_LOG_DIR и pytest --basetemp направлены в уникальный OS temp root;
-p no:cacheprovider. Запуск: active .venv python -B -m pytest -q
с восемью файлами из §4 и --tb=short. Focused recheck — только новый файл.

Код существующего v19-теста не менялся; baseline failure не скрыт.
Warnings datetime.utcnow — существующий logging_setup, не исправлялся.
Live/provider/SMTP calls 0; staging/commit/push не выполнялись.
data/, старые worktrees, env и tenant data не изменялись.
Независимые Checker/Cursor verdict хранятся отдельными отчётами, не внутри
проверяемого diff; новое тестовое дополнение требует focused recheck.

### Точный manifest тестового interpreter

```text
DAWG2-Python==0.9.0
Flask==3.1.3
Jinja2==3.1.6
MarkupSafe==3.0.3
PyYAML==6.0.3
Pygments==2.21.0
Werkzeug==3.1.8
annotated-types==0.8.0
anyio==4.15.1
blinker==1.9.0
click==8.5.0
colorama==0.4.6
gunicorn==26.2.0
h11==0.16.0
httpcore2==2.13.1
httpx2==2.13.1
idna==3.20
iniconfig==2.3.0
itsdangerous==2.2.0
jiter==0.17.0
numpy==2.2.6
openai==3.19.2
packaging==26.3
pip==25.0.1
pluggy==1.6.0
psycopg-binary==3.3.6
psycopg==3.3.6
pydantic==2.13.5
pydantic_core==2.46.5
pymorphy3-dicts-ru==2.4.417150.4580142
pymorphy3==2.0.6
pytest==9.1.1
python-dotenv==1.2.3
python-frontmatter==1.3.0
setuptools==84.0.0
sniffio==1.3.1
truststore==0.10.4
typing-inspection==0.4.4
typing_extensions==4.16.0
tzdata==2026.4
```

### Cursor: review реализации, не исторического документационного diff

Проверить read-only diff от a185b54a19481d83af9998fd8f6176b0baadfad7 в
C:\Cursor Projects\artgents-bot-active, codex/d2-stage1-contract.
Сначала AGENTS/Execution Lock/Roadmap/Target Contract/Acceptance/Ledger,
затем §3–4 и §9 этой карточки, новые tests и production diff.
Два новых файла читать явно, даже если untracked. Точный allowlist — §3.
Проверить неизменность wire, exceptions, state/effects/rollback и frozen plan,
отсутствие утечек через logger context, изоляцию interleaved SSE, early close,
post-commit disconnect/replay, prompt vs transport counting, sink failure,
и отсутствие подгонки существующих тестов. Известный v19 failure сравнить
с baseline, не исправлять. PASS не закрывает REC-2–5 и не разрешает live.
Вердикт PASS/REJECT отдельным отчётом с file/line/evidence; не вписывать в diff.
Без edits/staging/commit/push/merge/deploy и установки зависимостей.
Только согласованные offline tests с изоляцией выше; никаких запросов
к работающему боту или реальному provider.
