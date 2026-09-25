# D2-REC-1 — карточка безопасной диагностики

Дата: 2026-09-25. Статус: Draft; документальная фиксация разрешена владельцем; ожидается независимый Checker и завершение Cursor review исправленного diff. Вердикты сообщаются отдельными отчётами проверяющих, не записываются внутрь проверяемого diff. Реализация REC-1 НЕ разрешена этим документом; после review требуется отдельный GO.

## 1. Что предлагается согласовать

Не новый rewrite, не возврат старой ветки и не перенос папок. Продолжить сверку/доработку существующего D2 в одной active-папке. Первый ограниченный checkpoint — безопасная диагностика существующего runtime. Остальные обнаруженные дефекты остаются открытыми и получают собственные карточки.

Связь с действующей roadmap: восстановление недостающего evidence/diagnostics перед завершением демо-приёмки этапа 5; пробелы этапов 1–4 не объявлять закрытыми. Порядок восстановления закреплён в [действующем roadmap](DEMO_D2_DELIVERY_ROADMAP.md) по разрешению владельца на документацию. Это единственный источник последовательности; [inventory](DEMO_D2_RECONCILIATION_INVENTORY.md) фиксирует сохранённую работу, а [Ledger](DEMO_D2_CHECKPOINT_LEDGER.md) — evidence. Исторические PASS не переписывать задним числом.

## 2. Preflight и baseline

- Единственная папка разработки/запуска: `C:\Cursor Projects\artgents-bot-active`.
- Git top level должен совпадать с ней.
- Документы готовятся в существующей незавершённой D2-задаче на `codex/d2-stage1-contract`, без создания новой ветки от старого main. Продолжение реализации на этой ветке должно быть явно включено в последующий GO владельца.
- Зафиксированный runtime baseline: `e261383515d94e7d925acc705d8a6731aa704e48`.
- Baseline текущего review документов — тот же HEAD плюс только четыре разрешённых документа ниже. После их review и отдельно разрешённого commit будущая реализация стартует с точного hash документационного checkpoint, указанного в closeout и подтверждённого новым preflight. Diff от `e261383` до этого hash должен содержать только эти четыре документа. Произвольный более новый descendant не считается разрешённым baseline.
- `origin/main` и merge-base: `141ce91fb1731cd990fcf8391550150016c73e7f`.
- До документального diff tracked clean, staging пуст. Foreign/untracked: active `data/`; old WIP, архивы, логи, env, venv, debug SQLite вне записи.
- Новый preflight обязателен перед исполнением. При другом HEAD, содержательном dirty diff, занятом другим исполнителем файле или другой папке — остановиться и показать расхождение.
- `b8b28d3` — read-only reference, НЕ baseline реализации и НЕ разрешение cherry-pick/merge.

### Allowlist текущей задачи — только документы

```text
docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md
docs/tasks/DEMO_D2_RECONCILIATION_INVENTORY.md
docs/tasks/DEMO_D2_RECOVERY_DIAGNOSTICS_TASK.md
docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md
```

Сейчас: без code edits, тестовых запусков, установки пакетов, staging,
commit/push, live, merge, deploy и очистки. Новые untracked Markdown-файлы
проверяются явно: обычный `git diff` их не показывает.
PASS документов не является PASS runtime и не разрешает следующую реализацию.

## 3. Checkpoint D2-REC-1 — диагностируем, не меняя ответы

### Результат для владельца

При следующей проверке можно установить: какая сборка обрабатывала запрос, на каком шаге он остановился, был ли вызов модели, был ли сохранён результат и завершилась ли доставка. Один случайный номер попытки связывает события этой попытки. Новые диагностические события не содержат переписку или личные данные; очистка всех прежних app-логов этим checkpoint не обещается.

Это НЕ исправление всех ответов и НЕ закрытие C03: публикация prose будет отдельным следующим checkpoint.

### Будущий write allowlist REC-1 — только после отдельного GO

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

Окружение — отдельный входной gate: active `.venv` пока без pytest, версии библиотек отличаются от прежнего тестового окружения. Перед реализацией представить точный тестовый interpreter/dependency manifest. Не устанавливать и не менять пакеты молча. Старый аудит на другом interpreter — историческое evidence, не доказательство идентичного active-окружения.

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

Владелец уже разрешил документационную фиксацию и передачу в Cursor. Для старта кода REC-1 после review требуется отдельный GO на эту ограниченную карточку и продолжение текущей D2-ветки. Предлагаемый режим логов — без переписки/PII, trace одной попытки, без изменений публичного протокола. После согласования отдельно закрыть gate тестового окружения; установка пакетов не подразумевается автоматически.

Не требуется сейчас выбирать формат каждой строки кода или повторно утверждать уже принятые D2-092/093.

До последующих visible changes отдельно решить только реально открытые варианты:

- общий `contacts`: сохранить нынешний телефон или показывать адрес+телефон; точные `contact_address`/`contact_phone` остаются точными;
- если данных недостаточно для безопасного отделения существенных условий от подробностей — не скрывать условия самостоятельно, показать владельцу конкретный пример;
- raw transcript, correlation между рестартами, новый wire, новая персистентность — не входят в это согласование.

## 7. Строгий Cursor prompt для проверки карточки

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
