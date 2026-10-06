# D2 — интерфейс модели, контекст обсуждения и source UI

Актуально: 2026-10-03. D2-119/120 и UI отмены на этапе телефона реализованы;
scoped offline проверки и независимые review — §10.6–12. Полного live/widget
PASS нет. Текущий шаг — сверка документов и разрешённые владельцем commit/push.
§1–10.5 сохраняют историю прежних этапов и действовавших тогда разрешений.
Новый runtime, live, merge/deploy и восстановление сессии в этот шаг не входят.
Единственный план работ — верх [Roadmap](DEMO_D2_DELIVERY_ROADMAP.md).
Правила: [AGENTS](../../AGENTS.md), [Checker](../WORKFLOW_CHECKER.md),
[контракт §3](DEMO_D2_TARGET_CONTRACT.md), [Acceptance](DEMO_D2_ACCEPTANCE.md).

Обязательный контроль: [Audit change-map discipline](../../AGENTS.md#audit-change-map-discipline)
и [Mandatory change-map check](../WORKFLOW_CHECKER.md#mandatory-change-map-check).
Переход к следующему этапу, новая ветка поведения или преобразователь к старой
структуре не разрешаются этой карточкой автоматически. Выполненные runtime GO
и их точные границы записаны в соответствующих разделах. В финальном отчёте
отдельно перечислить удаления, добавления и их
основание, изменения поведения, offline/live/widget проверки и остаточные риски.

## 1. Baseline и сохранение работы

### Runtime GO / preflight реализации — 2026-10-02

Прямое решение владельца: «Делай в указанном allowlist, с offline-проверками,
без live, commit/push и расширения задачи». Согласованы одна операция/один ID,
локальное clarification, pending_question/content_text и сохранение самой
операции без wrapper/адаптера. Точный allowlist — §3.3, не расширяется.
Root/Git top/branch/HEAD/main/merge-base совпали с preflight ниже. На старте
свой WIP только два DOC подготовки; чужие три untracked пути неизменны,
staging пуст. Baseline — a53e6b4 плюс эти подготовленные документы.
Тип — архитектурное сокращение формы операции по before/after/removal §3.2,
с прежними владельцами Contract §3. Кодовые цены/UI/память/lead/privacy не получают
нового владельца. Реализация/результаты проверок фиксируются после offline.

### Исторический preflight DOC-подготовки — 2026-10-02

Root/Git top: `C:\Cursor Projects\artgents-bot-active`; ветка
`codex/d2-stage1-contract`. HEAD, tracking ref и удалённая ветка совпали:
`a53e6b4f37e1d35474f6e8c8c41bcdcb0767bddf`.
Remote `https://github.com/Dhmnzr79/artgents-bot.git`; локальная/удалённая main
и merge-base: `141ce91fb1731cd990fcf8391550150016c73e7f`.
Удалённые SHA проверены read-only `git ls-remote`; fetch/checkout не выполнялись.
Tracked diff/staging до подготовки пусты. Untracked только три исключённых
пути ниже; их содержимое не читалось. Git сообщил недоступность global ignore
и `.pytest_cache`; их содержимое проверенным не объявляется.

Текущий шаг — **документация**, не реализованное упрощение. Allowlist записи:
`docs/tasks/DEMO_D2_INTERFACE_TASK.md`, `docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md`.
Runtime/live/commit/push/merge/deploy GO отсутствует. Разрешение публикации
a53e6b4 уже исполнено; продолжение в той же папке/ветке, без новой ветки от main.

### Исторический preflight до публикации

Дополнение публикации: владелец разрешил commit/push накопленного WIP и
документов. Имя checkpoint: `chore(d2): checkpoint sim4 and audit handoff`.
После успешного push база продолжения — SHA этого коммита, сверенный с remote.
Получить SHA: `git log -1 --format=%H --grep="checkpoint sim4 and audit handoff"`.
Следующие сведения о незакоммиченном состоянии описывают preflight ДО публикации.
Продолжение идёт в той же ветке; новый runtime GO этим разрешением не дан.

Root/Git top: `C:\Cursor Projects\artgents-bot-active`.
Branch `codex/d2-stage1-contract`.
HEAD и локальная origin branch: `e6756ee59df4f186e499c29ae41cda0e993d80fe`.
origin/main и merge-base: `141ce91fb1731cd990fcf8391550150016c73e7f`.
Рабочая база включает незакоммиченные SIM4/D2-116/prompt33; один HEAD её не
воспроизводит. Staging пуст. Git-публикация этого WIP не разрешена текущим GO.
Перед паузой нужен отдельный разрешённый named checkpoint commit/push согласно
[AGENTS](../../AGENTS.md). Пока разрешение/публикация отсутствуют, не объявлять
handoff завершённым и не начинать код в отдельном чистом checkout.

Foreign WIP: `data/`, `docs/MARKETING_ANSWER_SCENARIOS.md`,
`docs/tasks/DEMO_D2_SIM0_TASK.md`: не читать, не менять, не stage.
Свой WIP: SIM4 runtime/data/tests, prompt31–33 и документы перечислены в
[SIM4 Task](DEMO_D2_SIM4_TASK.md). Не смешивать DOC PASS с проверкой всего WIP.

DOC allowlist первоначальной подготовки handoff: эта карточка; DEMO_D2_DELIVERY_ROADMAP.md,
DEMO_D2_TARGET_CONTRACT.md, DEMO_D2_ACCEPTANCE.md, DEMO_D2_CURRENT_STATUS.md,
DEMO_D2_CHECKPOINT_LEDGER.md, DEMO_D2_SIM4_TASK.md (все в docs/tasks).
Последующее согласованное дополнение правил ограничено четырьмя файлами:
AGENTS.md, docs/WORKFLOW_CHECKER.md, Roadmap и этой карточкой.
Код, настройки провайдера, данные клиник и тесты этими DOC-шагами не меняются.

## 2. Доказанное и пределы

- Схема из сбойного запроса не рекурсивна: pending допускает price/content/detail,
  но не новое clarification; situation содержит скалярные поля.
- Trace7ca91fe2: 41 ошибочный kinds, повтор situation, незавершённый JSON;
  ответ provider за18.2s, output1024/max1024. finish_reason не сохранялся:
  length нельзя выдавать за прочитанное поле. Ошибка parse, не timeout.
- Модель уже выбирала unnecessary clarification до ценового resolver.
  Поздний price layer не превращал правильную задачу в неправильную.
- Prompt33 устранил неоднозначный пример; причинность/устойчивость не доказаны.
- Сохранённое hypothetical count не входит в длительный discussion_scope;
  список врачей из code exact blocks не передаётся в исходном порядке.
- Активны authored/fallback content, current/same/cross price scope paths.
  Legacy helpers вне D2 не объявлять причиной активного сбоя.

Предыдущие результаты: D2-116 основной92PASS, соседний49PASS+3FAIL;
availability/recovery10FAIL. Те же13failure IDs повторены на чистом HEAD.
Независимый D2-116 Checker36PASS. Prompt33:17PASS, independent5PASS.
Это отдельные прогоны с пересечениями, не суммировать как единый CI.
Аудит тесты не перезапускал. Ручные prompt33:7попыток,6ответов,1ошибка;
не общая приёмка виджета. Не добавлять сырой лог/промпт/PII в Git.

## 3. Проект ближайшего изменения (до runtime GO)

Тип: архитектурное сокращение формы операции; не обещание устранить все ошибки модели.
До: ClarificationOperation(request_id, missing, choices, operation(request_id,...)).
После: единственная операция(request_id, kind, target, параметры,
optional clarification(missing, choices)). В clarification нет operation/kind/ID.
Поля ситуации, бренда, оплаты и субъекта остаются на одной операции.

Для готового content используется content_text. Для незавершённого content
согласован pending_question вместо content_text: поля взаимоисключающие;
pending_question не публикуется. Это замена двойного смысла, не копия вопроса
в нескольких состояниях. После разрешённого выбора модель получает готовую
задачу с этим вопросом и возвращает только объяснение. Фактические consumers
и минимальная форма проверены при подготовке ниже; узкий runtime GO дан выше.
Новое поведение при невозможном уточнении не придумывается.

Удалить: внешний clarification-kind, nested operation, повтор request_id и
identity_mismatch; requests/block.operation unwrap; PersistedClarifyTask wrapper.
Тот же объект операции читают parser, executor, pending и click. Запрещён
adapter «новая форма → старый wrapper», dual runtime и fallback к старой схеме.
При необходимости локальную disposable schema можно заменить явно; не
строить миграцию без требования. Состояние заявки/PII не удалять.

Сохранить: genuine unknown service/term; 2–3 уникальных active choices;
parameter clarification extent/jaw/stage только для content/detail, не price;
первую активную clarification, B14/D2-112; порядок независимых частей.
Проверенная service-кнопка дополняет target и снимает clarification.
Цена/detail без объяснения — без модели; content — прежний explanation-only
вызов, без повторной классификации. Tenant/revision/TTL/shown refs остаются
единственным разрешением клика, choices не становятся вторым auth-источником.

Владельцы по Contract §3 неизменны. Сокращение не включает удаление памяти,
автопромо, изменение offers, B14, medical/privacy или финансового компромисса.
Удаление authored/fallback, каталогов и scope-carry — следующие отдельные
checkpoint, не скрытое расширение этой карточки.

### 3.1. Согласованная форма после трассировки

Класс запросов: price/content/price_detail с реальным допустимым уточнением,
в том числе в составном вопросе; тот же content для проверенного document click.

| Сейчас | Предлагается |
|---|---|
| `{kind:"clarification",request_id:"r1",missing:"service",choices:[...],operation:{kind:"price",request_id:"r1",situation:...}}` | `{kind:"price",request_id:"r1",situation:...,clarification:{missing:"service",choices:[...]}}` |
| Вопрос в nested `content_text` | Вопрос в `pending_question` на самой content-операции |
| `PersistedClarifyTask{missing,operation}` | Сам незавершённый runtime-объект в существующем `clarify_task` |

ID r1/r2 здесь принадлежит части вопроса; HTTP request ID хода/replay сохраняется.
Target/subject/context/situation/brand/payment и source/detail-параметры остаются
на той же операции. В clarification нет kind/ID/operation.

- Price: optional clarification только service/term, target absent/unresolved.
  Известный service/topic исполняется прайсом; price+extent/jaw/stage запрещён.
- Content: прежние scoped/source-поля и ровно одно непустое поле
  content_text / pending_question с прежним пределом 4000. Clarification требует
  pending_question и запрещает content_text. Realization/ref/sections/fallback
  сохраняются; authored/fallback и их правила публикации не удаляются.
- Detail: прежние aspect и offer ID/ordinal плюс optional clarification;
  вопрос уже задан aspect, новые текстовые поля не нужны. ID/ordinal по-прежнему
  взаимоисключающие. Параметрические уточнения только content/detail.
- Service choices: 2–3 уникальных active ID, target absent/unresolved. При иных
  missing choices пуст. Другие виды операций clarification не получают.

Закрытые альтернативы одного runtime-типа выражают XOR текста и ограничения
price; schema генерируется из них. Нет нового status/phase, состояния, ручного
второго договора или рекурсии. Обычный raw result с pending_question без
clarification отклоняется существующим validate_d2_payload. Для серверного
known_task эта форма допустима: после service-клика уточнение уже снято,
а объяснение ещё не получено; document-клик вообще не требует уточнения.
Общая standalone schema сама не различает эти контексты; это существующая
parser boundary, не новый выбор задачи. Отдельная input projection и strict
provider mode в этот checkpoint не входят.

Service-клик меняет target и снимает clarification, сохраняя параметры.
Price/detail исполняются напрямую. Content получает прежний explanation-only
вызов с pending_question. Parser принимает только прежние explanations,
при замене готовым content_text удаляет pending_question и валидирует готовую
операцию. Пустой/неправильный ответ не публикует вопрос и не запускает retry.
У document task section_title переносится из content_text в pending_question;
ref/section и прежняя возможность explicit authored сохраняются.

В materializer поступают только готовые content и операции без clarification.
Pending даёт прежний кодовый вопрос уточнения/UI; pending_question не становится
information block, rendered_text или предыдущим assistant answer. Сам pending
остаётся в существующем typed поле, без параллельной памяти. Свободный ответ на
term/параметр продолжает обычный model turn с этим контекстом; нового обработчика
нет. В частности stage не добавляется в RequestTreatmentSituation.

### 3.2. Путь и удаления (строки baseline a53e6b4)

1. `core/d2_live_provider.py:70–125` отправляет instruction и generated schema;
   `:200` — HTTP json_object (`:159` — CP3). `core/one_call_envelope_protocol.py:724–754` вызывает
   validate_d2_payload через единственный strict JSON decoder.
2. `contracts/d2_dialogue_result.py:157–210,244,258–278`: wrapper-типы, повтор ID,
   requests unwrap, replacement explanation и active choices. Requests может
   остаться прямым read-only alias blocks, без unpack/copy.
3. `core/d2_dialogue.py:840–889`: второй unwrap, B14/D2-112, сборка persisted
   wrapper. Сохранять первую операцию напрямую; остальные задачи deferred,
   без answered-статуса и автоматической очереди.
4. `contracts/response_plan_session.py:249–259,446` и
   `contracts/d2_session_context.py:115`: заменить тип wrapper на тот же runtime
   pending. `core/d2_session_context.py:123–129` уже переносит поле напрямую;
   `core/d2_dialogue_store.py:70–91` читает typed JSON. Disposable schema 3→4,
   без миграции/адаптера/очистки БД. Старый ordinary SID может отклоняться;
   lead/PII owner и активная заявка сохраняются, новый SID её не наследует.
5. `core/d2_dialogue.py:267–329,760–800`: shown UI/tenant/revision/TTL разрешают
   клик, pending supplies task. Choices не второй auth. Lead/policy до execution
   `:820–829`, price policy после clarification `:913–926`: последовательность и
   subject/context/payment сохраняются, не появляется новая policy-ветка.
6. `core/d2_snapshot_sources.py:150–159`: document known_task сейчас кладёт
   section_title в content_text. Этот consumer обязательно меняется, иначе
   двойной смысл поля остаётся достижимым.
7. `core/response_plan_materialization.py:396–449,692–736,1791–1942`,
   `core/d2_content_realization.py:43–121`: ready content/source/detail consumers.
   Их решения не меняются. Renderer, `core/d2_http_adapter.py:33–51` и
   `app.py:242–363` доставляют frozen answer/UI через JSON/SSE.
8. `core/d2_dialogue.py:679–685,1062–1071` сохраняет pending/receipt;
   `core/d2_completion_context.py:41–100` проектирует completed result в следующий
   input. Count/порядок врачей и полнота history — следующие пункты карты.

Before → after → removed dependency: wrapper+nested operation → одна операция
с локальным clarification → нет повторного ID, двух unwrap и persisted wrapper.
Content дополнительно перестаёт зависеть от местоположения поля content_text.
Удаляются прежние Meaning/ParameterClarifyTask, ClarificationOperation и его
подтипы, CLARIFY_TASK_ADAPTER wrapper, вложенный UnresolvedPriceOperation,
PersistedClarifyTask и clarification_identity_mismatch. Прежние ограничения
unresolved price выражает закрытая альтернативная форма той же операции.
Source/tenant/subject/situation/UI/replay проверки остаются требованиями.

Владельцы по Contract §3 применены к этому пути: смысл свободного вопроса —
модель; проверенный click — сервер по pending; offers/суммы — код прайса;
следующий input — существующая память по completion. План применяет B14/D2-112,
renderer выводит frozen результат. Нового владельца/решения нет.
Добавлены только clarification вместо wrapper и pending_question вместо
двойного смысла текста; это требуется единой структурой и запретом публиковать
незавершённое задание. Astra read-only consultation поддержала эту форму и
шесть runtime-файлов; её вывод не является Checker PASS или runtime GO.

### 3.3. Exact allowlist реализации — разрешён владельцем

Runtime:

- `contracts/d2_dialogue_result.py`
- `contracts/response_plan_session.py`
- `contracts/d2_session_context.py`
- `core/d2_dialogue.py`
- `core/d2_snapshot_sources.py`
- `core/one_call_prompt_contract.py`

Tests (замена затронутых входов/assertions и проверки новых границ, без
ослабления adverse сценариев):

- `tests/test_d2_sim2_contract.py`
- `tests/test_d2_sim2_dialogues.py`
- `tests/test_d2_clarification_scope_http.py`
- `tests/test_d2_session_context.py`
- `tests/test_d2_continuation_scenarios.py`
- `tests/test_d2_ui_b12_scenarios.py`
- `tests/test_d2_sim3_completion_context.py`
- `tests/test_d2_document_click_task_http.py`
- `tests/test_d2_sim1_known_actions_http.py`

Отчёт: эта карточка и `docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md`.
Parser entry/provider mode/limit, materializer/realizer, store/context
implementation, renderer, endpoints/widget и tenant data не требуют правки.
Strict provider mode/finish_reason — отдельная проверка, не скрытая часть этого
allowlist. Выход за список сначала объяснить владельцу. Исторические legacy
fixtures и посторонние baseline failures массово не переводить.

## 4. Строгая схема: отдельная проверка возможности

Фактически: Frankfurt MaaS compatible-mode/v1, qwen3.8-flash, thinking off,
json_object, схема только текстом. Документация перечисляет модель как
поддерживающую json_schema, но наша схема/регион не проверены:
[Alibaba structured output](https://www.alibabacloud.com/help/en/model-studio/qwen-structured-output).
Строгая схема должна генерироваться из единственного runtime-контракта,
не поддерживаться вручную как второй семантический контракт. SDK-сериализация
схемы не должна создавать преобразователь модельного решения в старую форму.
Проверить ограничения schema dialect; при несовместимости остановить зависимый
шаг, не включать молчаливый fallback. Наблюдаемость finish_reason нужна;
ни увеличение лимита, ни новые предупреждения не считаются устранением причины.
Строгий JSON не гарантирует смысл, финансовую prose или отсутствие truncation.
Live только после отдельного явного hard budget; прежние предложения8calls
не были приняты пользователем и не являются разрешением.

Подготовка 2026-10-02 сверила официальный раздел Supported models: JSON Schema
перечисляет Qwen3.8-Flash. Это read-only документация, не проверка Frankfurt,
доступности аккаунта или совместимости нашего schema dialect. Настройки и
provider calls не менялись. Строгая схема не гарантирует смысл свободного вопроса.

## 5. Приёмка / дальнейшие решения

Offline: фактически отправленная схема; отказ старой/рекурсивной формы;
известная цена; genuine unresolved + scoped click/replay/next input;
content/detail pending; mixedprice+prose в обеих очередностях; JSON/SSE;
tenant/stale/forged/foreign/medical/lead/privacy. Сохранить исходный смысл
adverse тестов, не подгонять fixtures ради PASS. Доказать удаления по call graph.
Затем independent Checker, отдельно разрешённый live/widget, Cursor gate.
Exact runtime allowlist §3.3 показан в preflight и согласован владельцем.
Разрешение DOC-подготовки заменено узким runtime GO в начале этой карточки.

Открытые продуктовые вопросы НЕ блокируют подготовку интерфейса:
общий unit-reference для разных услуг; B14 против желания отвечать на обе
независимые цены; удаление автопромо — только идея. Не считать их решёнными.
История3пары/1000символов/TTL30мин — текущие ограничения, не полная память диалога.
D2-114 residual financial prose risk остаётся принятым; новые verifier/retry
или обрезание текста не добавлять как стандартное решение.

### 5.1. Минимальные доказательства согласованного runtime GO

ACCEPTANCE: затронутые S01/S02/S06, B11/B12/B14/B15/B19/B20,
C01/C03–C10; не вся архитектура или общее закрытие D2.

| Проверка | Целая цепочка / ожидаемое доказательство |
|---|---|
| Sent schema + parser + persisted type | Одинаковые runtime constraints; нет старого wrapper/recursive payload; price+extent и известный price target+clarification отвергнуты; content XOR, ordinary pending без clarification отвергнут. Negative inputs не ремонтируются |
| Known price | Известное направление/услуга + объём → прежние offers/unit/reference либо честный gap; отсутствие цены не запускает service choice |
| Genuine service ambiguity | Вопрос с известными count/subject/brand/payment → pending same operation → shown click → intended service offers → replay без provider → следующий input. Omission модели не восстанавливается серверной эвристикой |
| Content и detail pending | Вопрос не виден как ответ; service content click → known_task.pending_question → один explanation-only reply → готовый content и следующий input. Detail aspect/selectors сохраняются, click без модели. Term/parameter свободное уточнение через обычный turn |
| Document click | Captured section title в pending_question, source ref/section прежние; пустой q; ready prose/authored; adverse пустой JSON/text/route/target mutation не публикуют seed и не меняют память |
| Mixed и порядок | Цена+объяснение в обеих очередностях; понятный content рядом с genuine pending; два уточнения с одной активной задачей; две цены с B14. Порядок частей в frozen result, deferred не answered, клик не запускает отложенное |
| Guards и оба transport | JSON/SSE parity и cross replay; TTL/stale/forged/foreign/tenant; admin/medical без ordinary publication; child/policy, lead interruption/privacy, отсутствие повторной заявки |

Первый proportional offline набор:
`python -m pytest -q -p no:cacheprovider tests/test_d2_sim2_contract.py tests/test_d2_session_context.py tests/test_d2_live_provider_offline.py`.
После coherent runtime — девять tests из §3.3 плюс
`tests/test_d2_http_contract.py`, `tests/test_d2_no_legacy_path.py` и
`tests/test_d2_lead_interrupt_http.py`; detail regression ограничить
`tests/test_d2_price_details_http.py` случаями прямой задачи/кнопки/ambiguous
detail, tenant/stale и обеих очередностей с prose/contact.
Изоляция: temporary DB/log/tenant copies, BOT_LOG_DIR во временной папке,
PYTHONDONTWRITEBYTECODE=1, pytest tmp/cache вне постоянных данных, socket block
и существующий central provider block. Полный CI только перед merge.

Independent Checker проверяет реальные callers/removal и полные диалоги,
потом Cursor по действующим правилам. Тест правильного raw JSON доказывает
исполнение, не качество понимания модели. Новые live/widget проверки только
после отдельного разрешения; старые бюджет/результаты не переносятся.

Неопределённости: поддержка strict mode нашим подключением/schema; adherence
живой модели; общий unit-reference; две независимые цены сверх B14; автопромо.
Пример residual: «На каком этапе?» → «После установки» сейчас понимает модель
по pending/context, отдельного stage в situation нет. Новый stage-field/handler
не вводится. Смена формы не исправляет omission/truncation или будущую полноту
памяти (например count после четырёх контактных вопросов).

## 6. Исторический handoff до текущего runtime GO

Открыть ту же папку и ветку. Сначала прочитать AGENTS.md, верх Current Status,
Roadmap и эту карточку. Сверить Git с фактическим checkpoint после отдельной
публикации; если публикация ещё не выполнена — WIP является частью baseline,
не переключать dirty checkout и не терять незакоммиченные файлы.
Продолжить только ближайшую задачу §3 после runtime GO. Начать с проверки
единой схемы и call graph, затем согласованный exact allowlist. Новые продуктовые
вопросы обсуждать обычным сообщением. Живые вызовы, commit/push требуют
своих разрешений; merge/deploy/destructive не разрешены. Отчёт: удаления,
добавленная сложность, владельцы, проверки и пределы; не обещать общую готовность.

DOC Checker: PASS для этих семи документов; 110 локальных ссылок разрешаются,
git diff --check чист. Runtime WIP этим review повторно не аттестован.
Публикация разрешена; успешный push и SHA подтверждаются Git и отчётом передачи.

## 7. Runtime checkpoint — фактическая реализация 2026-10-02

Тип: **архитектурное сокращение**, только согласованная форма уточнения.
Branch `codex/d2-stage1-contract`, HEAD/baseline
`a53e6b4f37e1d35474f6e8c8c41bcdcb0767bddf`; main/merge-base
`141ce91fb1731cd990fcf8391550150016c73e7f`. Изменены ровно 17 файлов §3.3.
Новый commit не создан. Staging пуст, commit/push/PR/merge/deploy не выполнялись.
Три foreign untracked пути §1 сохранены и не читались. Предупреждения Git
о недоступных global ignore/.pytest_cache не объявлены результатом их проверки.

### 7.1. Удаления и действительный путь

Before → after → removed dependency: внешний `kind=clarification` с nested
операцией → одна price/content/detail операция с локальным clarification →
убраны повтор rN ID, `clarification_identity_mismatch`, два unwrap и зависимость
сохранённой задачи от отдельной wrapper-схемы.

- Из `contracts/d2_dialogue_result.py` физически удалены `ClarifyTask`,
  `Meaning/ParameterClarifyTask`, `CLARIFY_TASK_ADAPTER`, старые
  `ClarificationOperation`/подтипы и вложенный `UnresolvedPriceOperation`.
  `requests` теперь прямой alias `blocks` (:250), не unpack/copy.
- `core/d2_dialogue.py:838–880` больше не читает `block.operation` и не собирает
  `PersistedClarifyTask`; сохраняет `pending = block`, затем :1070 тот же объект.
  Persisted wrapper физически удалён из `contracts/response_plan_session.py`.
  State (:431) и context (`contracts/d2_session_context.py:116`) используют
  runtime-операцию через один alias `ClarifiedOperation`, без конвертера.
- `core/d2_dialogue.py:759–783`: verified click меняет только target и снимает
  локальное clarification. Price/detail исполняются без provider; content
  остаётся вопросом до существующего explanation-only вызова.
- `contracts/d2_dialogue_result.py:260–296`: replacement удаляет вопрос и
  локальное clarification, валидирует завершённый `ExplanationOperation`.
  Ветка старой формы отсутствует. Обычный pending без clarification отвергнут.
- `core/d2_snapshot_sources.py:150–159`: section_title document-клика больше
  не записывается как completed content_text; он только pending_question.
  Готовая публикация поступает из ответа explanations, не из seed.

Проверенный путь: реальные app `/ask` и `/ask/stream` → общий adapter/turn →
существующий strict JSON parser → flat runtime → existing materializer/realizer
→ один frozen result/state/receipt → существующая completion projection →
следующий input. Поиск удалённых symbols/`.operation` в contracts/core пуст.
Нет нового-to-old adapter, fallback, parallel runtime или второго model decision.

Владельцы Contract §3 остаются единственными: модель определяет смысл свободного
хода; сервер исполняет verified click по сохранённой операции; код прайса выбирает
offers/суммы; existing completion projection формирует следующий input; renderer
выводит frozen результат. Проверка lead/policy до executor и price policy после
уточнения сохранена. Choices сохранены как параметры задачи, не второй UI authority.

### 7.2. Добавлено и сохранённое поведение

Добавлены узкие формы PendingPrice/Explanation/DetailOperation того же договора
и локальные Service/Term/ParameterClarification. Generated schema выражает
закрытые ready/pending альтернативы без status/phase; Price исключает parameter
clarification и известный target. `ExplanationFields` разделяет общие поля и
source-проверки ready/pending; это общий тип, не дополнительный execution слой.
Storage alias проверяет наличие clarification на тех же runtime-объектах.
`pending_question` заменяет двойное значение content_text и никогда не публикуется.
Prompt version 33→34 и примеры описывают эту же форму; отдельной ручной схемы нет.

Прежние ограничения/поведение сохранены: scope/subject/context/brand/payment,
source/ref/section/realization/fallback, detail aspect/selectors, 2–3 unique active
choices, B14 первая цена и deferral следующих, D2-112 первая активная задача,
независимые ответы/порядок, shown UI tenant/revision/TTL, replay, medical,
lead/privacy. Дополнительные calls, semantic repair/retry и новые handlers не
добавлены. Authored/catalogs/memory/unit-reference/autopromo не менялись.
Риск D2-114 свободной финансовой prose остаётся принятым.

### 7.3. Старая сессия и заявка

Disposable ordinary schema 3→4. Новый ход с сохранённой схемой 3 отклоняется
прежним путём: JSON 400 `d2_invalid_turn`, SSE error без ui. Никакого reset,
migration/adapter/DB cleanup, новой кнопки/смены SID или восстановления не добавлено.
Offline сравнение подтверждает byte-equal payload ordinary state, строки
request/completion и отдельную запись lead owner после отказа. Активная заявка
с именем и collecting_phone остаётся в исходной сессии.

Отдельно выполнена demo_stub заявка через прежние name/phone ходы: её receipt
и completion не удаляются. Replay того же phone request возвращает тот же
receipt/ответ после изменения ordinary schema, не вызывает provider и не создаёт
новую заявку (два focused PASS). Это existing replay сохранённого результата,
не восстановление ordinary диалога. ПД не добавлены в D2 receipt/memory;
существующая очистка ПД после отправки не менялась. External lead store/delivery
не проверены live и вообще не редактировались.

Явно другой SID создаёт независимый новый диалог и не наследует name/phone или
старую заявку. Автоматического перехода на него нет. Продолжение активной заявки
в несовместимом ordinary SID через новый ход сейчас тоже отклоняется — запись
сохранна, но новый способ продолжить её не реализован и не обещается.

### 7.4. Offline evidence и ограничения

Все прогоны: repo `.venv/Scripts/python.exe`; внешний временный runner отключает
dotenv/реальные ключи, блокирует sockets; central provider block сохранён.
DB/logs/tenant copies/pytest artifacts в temporary paths, cache отключён,
PYTHONDONTWRITEBYTECODE=1. Live/provider/network/SMTP calls **0**.

- Первый contract/session/provider-offline набор: **106 PASS / 4 FAIL**.
  Все четыре FAIL воспроизведены на чистом archive baseline a53e6b4.
- Assembled набор семи HTTP/scenario файлов allowlist плюс http_contract,
  no_legacy_path, lead_interrupt_http: **176 PASS / 22 FAIL**. Из них 21 FAIL
  воспроизведён чистым baseline. Собственная ошибка появления слова KNOWN_TASK
  в ordinary prompt исправлена без изменения теста; повтор ниже подтверждает.
- Финальный contract/session/sim1-known-actions/document-click набор:
  **143 PASS / 1 FAIL**, остаётся только baseline extent-menu-copy.
- Scope с сохранением payment: **8 PASS**; сначала запуск вместе с old-session
  дал ещё четыре PASS (две новые submitted проверки имели неверное ожидаемое
  имя статуса sent; исправлены на реальный local demo_stub).
- Old schema none/active/submitted и detail service click, JSON/SSE:
  **8 PASS**. После добавления receipt-replay assertions: **2 PASS**.
- Девять выбранных старых price_details_http cases: **9 FAIL**, те же **9 FAIL**
  на чистом baseline; fixtures используют прежний envelope. Эти файлы не менялись.
- Independent Checker: **PASS**, блокирующих P0/P1 нет; собственные
  **32 PASS / 0 FAIL**. Проверены actual path/removal, test diff, этот отчёт,
  final143/1baseline и receipt-replay2PASS. `git diff --check` чистый;
  AST всех 15 изменённых Python файлов валиден, 40 локальных doc-ссылок без missing.
- Cursor independent review: **PASS**, передан владельцем в чате 2026-10-02;
  блокирующих P0/P1 нет. По отчёту reviewer собственный изолированный прогон:
  **164 PASS / 1 FAIL**, 115.22 с; FAIL —
  `test_sent_prompt_contains_only_current_extent_menu_copy`, тот же подтверждённый
  baseline extent-menu-copy. Reviewer повторно проверил actual path/removal,
  владельцев §3, adverse explanation, old-session/lead и Git/allowlist.
  Эти числа не суммируются с прогонами исполнителя или Checker.

Числа прогонов пересекаются и **не суммируются**. Новых сохраняющихся регрессий
в этих проверках нет; весь test suite не объявлен зелёным. Ровно 34 уникальных
baseline failure ID подтверждены в текущих выбранных наборах:
4 prompt/extent, 5 continuation, 1 B12, 15 lead_interrupt, 9 price_details.
Они не ремонтируются этим интерфейсным checkpoint. Узкий Cursor gate пройден
по переданному review; полный CI перед merge, live model/strict-provider
compatibility и widget с моделью не запускались. Offline raw fixtures не доказывают понимание живой модели,
устойчивость к truncation/omission или закрытие последующих этапов карты.

Cursor P2: верх Roadmap ещё описывает исторический DOC-only/runtime e6756ee;
этот файл вне текущего allowlist и не менялся. Прямой runtime GO и фактический
checkpoint записаны в этой карточке и Ledger. Generated schema допускает
pending content без обязательного clarification; ordinary parser отвергает
его, server known_task допускает — согласованная граница §3.1, не новый дефект.
P2 не расширяют scope и не требуют нового recovery/контракта. Ни narrow PASS,
ни фиксация отчёта не разрешают Git-публикацию или начало следующего этапа.

## 8. Следующая замена — единый контекст и follow-up

### 8.1. Решение, baseline и границы документации

Тип текущей работы: **документация**. D2-117 принят владельцем после обсуждения
двух способов памяти: выбран один обсуждаемый контекст без отдельной личной
ситуации. D2-118 — прямое требование починить тематические follow-up. Технический
план ниже проверяется до реализации; сама запись не создаёт runtime GO.
Единственные владельцы решений — [Contract §3](DEMO_D2_TARGET_CONTRACT.md).

Root/Git top `C:\Cursor Projects\artgents-bot-active`, branch
`codex/d2-stage1-contract`, HEAD `a53e6b4f37e1d35474f6e8c8c41bcdcb0767bddf`,
origin/main и merge-base `141ce91fb1731cd990fcf8391550150016c73e7f`.
Baseline этого DOC-шага: HEAD плюс существующий проверенный 17-file WIP §7.
Staging пуст. Foreign `data/`, `docs/MARKETING_ANSWER_SCENARIOS.md`,
`docs/tasks/DEMO_D2_SIM0_TASK.md` не читать/менять. Ветка не переключается.

Точный DOC allowlist: эта карточка, DEMO_D2_DELIVERY_ROADMAP.md,
DEMO_D2_TARGET_CONTRACT.md, DEMO_D2_PRODUCT_DECISIONS.md,
DEMO_D2_ACCEPTANCE.md, DEMO_D2_CHECKPOINT_LEDGER.md (все в docs/tasks/).
AGENTS/Checker не меняются. Код, тесты, tenant data и лог-файлы не редактируются.

### 8.2. Before → after → removed dependency

Следующий runtime checkpoint — **архитектурное упрощение**, не условие для
одной фразы: discussion через patient situation/subject/current-same-cross
→ готовая операция с target и volume → прямой price и completion projection.
Объём не признаётся медицинским фактом. Модель понимает свободный вопрос в
существующем вызове; память читает завершённый результат; код прайса исполняет
полученную задачу. Никакого нового классификатора/regex/repair/retry/call.

Предлагаемая форма (вместо situation, не рядом):

```json
{"kind":"price","request_id":"r1","target":{"type":"service","id":"classic"},"volume":{"extent":"few_teeth","tooth_count":3,"jaw":"unknown"}}
```

Один тип volume для price/content/detail и их pending-форм. Существующие
проверки чисел/extent остаются; неизвестное не достраивается сервером.
Новые hypothesis/correction/same-person/continuation flags не вводятся.
Разговор «один → а если три → всё-таки три» использует текущие три; прежняя
личная единица не хранится параллельно. Объём другой услуги не копируется
автоматически; смысл явного продолжения определяет модель по контексту.

Удаляемые активные пути:

| Участок | Удаление / замена |
|---|---|
| contracts/d2_dialogue_result.py | situation, subject identity/registry, scope_commitment/continuity, treatment_same_requires_subject, binding-conflict/multiple-situation guards; сохраняются target, local clarification и ready/pending text |
| core/d2_dialogue.py | искусственная hypothetical situation volume-click; чтение/запись/перенос PersistedSituationState, создание owner ID, условия reported/correction/reset |
| core/d2_session_context.py и contracts/d2_session_context.py | subject-is-self, same/cross situation carry, D2CrossTopicSituationCarry, bind/seed и D2EnvelopeSessionBinding/D2PlanFocusSeed как повторный путь разрешения ситуации |
| core/response_plan_materialization.py и contracts/response_plan.py | d2_treatment_situation; _d2_treatment_situation и каскад current/same/cross applied extent. Единственный объём цены — operation.volume |
| core/d2_completion_context.py | price-only источник обсуждения и чтение treatment decision; completed content/price/detail содержат параметры задачи напрямую |
| contracts/d2_dialogue.py и D2 state/store consumers | focus с patient carry в completion; сохранённый patient slot в принятой D2 schema, не только записи в него |
| core/one_call_prompt_contract.py | инструкции поддерживать пациентские commitment/continuity вместо обсуждаемого volume |

Для storage предлагается замещающий D2 state-контракт без situation_state,
с существующими счётчиками, UI/pending и receipt-ссылками, напрямую в D2 record.
Общий legacy-тип не подставляется через адаптер. SQLite/store owner остаётся
прежним. Nullable patient slot в активной D2 schema не считается удалением.
Общие legacy-типы вне D2 могут остаться только с доказанной недостижимостью
из активного маршрута; это отдельно перечисляется, не объявляется удалённым.

Параметры обсуждения (target/volume/brand) замораживаются в завершённой части
результата. Существующая ссылка на receipt указывает на единственный текущий
контекст. В следующий provider input идут этот контекст, существующая история,
pending и проверенный UI ref. Конкурирующие active-service/topic/patient copies
как самостоятельные источники смысла модели не передаются. Служебные ссылки
для tenant/replay/UI не становятся второй памятью разговора.

Контакты сохраняют receipt-ссылку; новый завершённый scoped-вопрос обновляет её.
Pending не объявляется завершённым контекстом. B14/T4 учитывают и отложенную
вторую цену: нельзя выбрать первую/последнюю услугу по позиции. Пограничный
пример для проверки до кода: одна услуга, два разных объёма в одном ответе.
Оба остаются доступны в истории; единственный объём не выбирается произвольно.
«А для одного?» однозначно; «а для этого варианта?» уточняется лишь при
недостаточном контексте, не автоматически по тексту.

### 8.3. Правила клиники и сохранность заявки

Политики используют возраст/context/payment (core/clinic_policy_resolver.py),
а не patient carry. Предложение: age_group напрямую на price/booking/policy;
убрать D2 subject_id/relation/registry без синтеза старого subject-объекта.
Тот же policy owner и его правила; потребители: core/d2_lead_bridge.py,
core/d2_snapshot_sources.py, core/d2_dialogue.py. Past-history не становится
текущим детским запросом; запрет детского приёма и оплаты по полису сохраняется.
Это замена представления известного факта, не постоянный профиль пациента.

Medical/admin, lead consent/active/pause/contact/privacy, exact prices/units,
tenant/revision/TTL и подлинность UI сохраняются. Новое состояние не мигрирует
старый SID и не вводит reset/recovery. До реализации установить последствия
смены schema для чтения старого completion/replay, не обещать совместимость
на основании предыдущего §7. Проверить отдельные request/lead rows, активную
заявку и receipt; новый SID не наследует контакты. Публикация не разрешена.

### 8.4. Follow-up — обязательный следующий bug fix

Историческое состояние до следующего GO. Реализация и уточнение границы
после обсуждения с владельцем — §9; повторного решения правил кнопок не нужно.

Тип: исправление поведения; не называть один prompt tweak упрощением.
Фактический пробел пользователя: ответы про боль и сроки публиковались без
content_ref, поэтому core/response_plan_materialization.py:_d2_source_ui
получал None и возвращал пустой UI. В demo pain/duration материалы имеют
suggest_h3. Виджет получил пустой quick_replies; это не доказанный сбой renderer.

Общая проверяемая цепочка: ответ → установленный материал → authored UI →
показанный click → explanation-only результат → completion → следующий ход.
Переключатели публикации/каталоги сокращаются после этой трассировки.

1. Known click: source/section уже взяты из показанного UI, заморожены в
   known_task; explanation не должен возвращать их заново. Отсутствие ref в
   ответе модели не отменяет известный источник. Сохраняются существующие
   ограниченные explanation-only поля и один вызов, без нового route/kind.
2. Свободный первый вопрос: источник выбирает модель в том же существующем
   вызове через content_ref. Код проверяет ссылку и строит authored suggestions;
   renderer не выбирает материал. Общая тема implantation не определяет,
   нужен ли pain, duration или иной материал.

Открытый до runtime пример: «Боюсь боли при имплантации» → полезный ответ,
content_ref=null, хотя материал есть. Пока разрешена source-free prose; код
не может восстановить выбор источника без нового смыслового решения.
Нужно определить границу ответа с обязательной связью с материалом и допустимый
исход её отсутствия либо явно сохранить отсутствие кнопок в этом случае.
Цель исправления принята, выбор этого исхода ещё не принят. Нельзя молча
ввести topic→document fallback, новый call, выдуманные кнопки или блокировать
полезный текст. Только зависимое source-UI решение остаётся открытым.

Сохраняются до двух secondary-слотов, неповтор, приоритет разрешённых
video/follow-up, отдельный CTA и запреты дополнений. Не требуются кнопки после
каждого ответа; mixed/price+content и несколько материалов проверяются по
существующим правилам, а не получают новую политику выбора источника.

### 8.5. Приёмка и следующий исполняемый checkpoint

Сценарии и разделение evidence — [Acceptance](DEMO_D2_ACCEPTANCE.md).
Offline: raw parser/schema, actual HTTP JSON/SSE, полный путь memory/click/replay,
отрицательные patient поля, явный unknown, mixed/B14/T4, policy/medical/lead/TTL.
Обязательны live переформулировки, включая достаточный/недостаточный контекст,
первый source-answer и follow-up click. Fixtures не доказывают живое понимание.
Live — отдельное разрешение и жёсткий бюджет до запуска; сейчас agent calls 0.

Этот шаг не добавляет runtime файлы в прежний §3.3 allowlist. Перед новым кодом
зафиксировать точный runtime/test allowlist по перечисленным consumers,
последствия storage schema и открытый source-UI исход. D2-117 не согласовывать
заново; нерешённые технические/product границы не закрывать правкой карточки.
Одно independent DOC Checker по текущим шести документам; затем при готовом
коде независимая проверка удаления и полных диалогов, отдельно live/widget.


### 8.6. Runtime GO — 2026-10-02

Владелец: «Делаем». Текущая работа — архитектурное упрощение D2-117 по §8.2;
D2-118 остаётся отдельным bug fix в этой задаче. §8.1 описывает завершённый DOC checkpoint.
Baseline: HEAD a53e6b4 + проверенный 21-file WIP, снимок в temp
`d2-discussion-runtime-baseline-mzxnerjc`. Git/staging/foreign WIP без изменений.
Точный runtime allowlist:
- contracts/d2_dialogue_result.py, contracts/d2_session_context.py,
  contracts/d2_dialogue.py, contracts/response_plan.py;
- core/d2_dialogue.py, core/d2_session_context.py, core/d2_completion_context.py,
  core/response_plan_materialization.py, core/response_plan_resolver.py,
  core/one_call_prompt_contract.py, core/clinic_policy_resolver.py,
  core/d2_lead_bridge.py, core/d2_snapshot_sources.py, core/d2_dialogue_store.py;
- tests/test_d2_sim2_contract.py, tests/test_d2_sim2_dialogues.py,
  tests/test_d2_sim3_completion_context.py, tests/test_d2_session_context.py,
  tests/test_d2_continuation_scenarios.py, tests/test_d2_clarification_scope_http.py,
  tests/test_d2_document_click_task_http.py, tests/test_d2_sim1_known_actions_http.py,
  tests/test_d2_ui_b12_scenarios.py, tests/test_d2_http_contract.py,
  tests/test_d2_live_provider_offline.py, tests/test_clinic_policy_resolver_offline.py,
  tests/test_d2_discussion_context_http.py;
- те же шесть документов §8.1.
`core/response_plan_resolver.py` добавлен для удаления пяти механических копий
удаляемого d2_treatment_situation. Единственные владельцы — Contract §3.
Старый schema 4 SID и его completion несовместимы с новым D2 state/schema5:
отказ до provider/effect, сохранённые state/request/lead rows не удаляются.
Нового migration/reset/recovery нет; старый replay не обещается.
Live/provider/SMTP/commit/push не разрешены.

Дополнение allowlist: перенос существующих тестов удаляемых API и patient
fixtures на прямые операции; без возвращения runtime-адаптера:
- tests/test_d2_content_source_ui.py
- tests/test_d2_demo_snapshot.py
- tests/test_d2_diagnostics.py
- tests/test_d2_dialogue_a08.py
- tests/test_d2_dialogue_b13.py
- tests/test_d2_independent_request_parts.py
- tests/test_d2_multi_request.py
- tests/test_d2_part_failure.py
- tests/test_d2_price_deferral.py
- tests/test_d2_price_modes.py
- tests/test_d2_price_presentation_http.py
- tests/test_d2_price_scope_selection.py
- tests/test_d2_prose_realization.py
- tests/test_d2_prose_violation.py
- tests/test_d2_sim2_dialogues.py
- tests/test_d2_single_request.py
- tests/test_d2_snapshot_sources.py
- tests/test_d2_stage3_prices_scope.py
- tests/test_d2_treatment_situation.py
- tests/test_d2_volume_choices.py
- tests/test_d2_price_guidance_http.py
- tests/test_d2_af1a_price_task_http.py

### 8.7. Runtime D2-117 — результат и границы evidence, 2026-10-02

**Тип: архитектурное упрощение.** До: обсуждаемый вариант и отдельная
patient situation; price/context зависели от subject и current/same/cross carry.
После: операция содержит target, nullable volume `{extent, tooth_count, jaw}`
и brand; завершённая часть хранит тот же DiscussionScope. Один
`discussion_request_id` указывает на завершённый результат. Его проекция,
ограниченная история, pending и проверенный UI ref идут в следующий input.
Удалена зависимость обычного продолжения и ценового объёма от личной ситуации.
Смысл свободной реплики определяет модель в прежнем вызове; code-owned цена,
проверенный click и клинические правила имеют прежних владельцев по Contract §3.

Фактическая цепочка: `/ask`, `/ask/stream` → `run_d2_ask_json` →
`run_d2_dialogue_turn` → `validate_d2_payload` → `resolve_d2_operations` →
frozen response/store → `project_completed_dialogue` → следующий provider input.
Price/detail click исполняются без модели; content click — один существующий
explanation-only вызов. Ни дополнительных calls, ни разбора пользовательских
фраз сервером, ни нового-to-old адаптера не добавлено.

**Фактические удаления:**

- В `contracts/d2_dialogue_result.py` нет situation, subject/subjects/subject_id,
  scope_commitment/continuity и treatment_same_requires_subject. Старые поля
  отвергаются закрытым parser, а не игнорируются или конвертируются.
- Удалены D2CrossTopicSituationCarry, D2EnvelopeSessionBinding, D2PlanFocusSeed,
  D2TreatmentSituationDecision, bind/seed и current/same/cross applied-extent
  пути. `resolve_d2_envelope_response` удалён, включая сам адаптер.
- Активные D2 record/completion больше не используют patient state/focus;
  создание owner ID, запись/перенос patient state и пять копий
  d2_treatment_situation в resolver удалены.
- В следующий D2 input не идут competing active_service/topic/situation_state
  и самостоятельные копии показанных цен. Служебные offer/receipt/UI refs
  сохраняются для подлинности, replay и исполнения уже показанного действия.

**Что добавлено и зачем:** DiscussionVolume/DiscussionScope напрямую в задаче
и результате; D2SessionState/schema5 вместо прежнего активного state-типа;
receipt-ссылка единственного текущего обсуждения; age_group/context на
price/booking/policy для прежних правил клиники без subject registry.
`volume=null` — объём не задан; explicit unknown — явно неизвестен, включая
проверенный ответ «Не знаю», без повторного volume-меню. Новых hypothesis,
correction, continuation, same-person flags и параллельной памяти нет.

Контакты удерживают обсуждение в пределах TTL, в том числе после трёх history
пар. Новая scoped-задача обновляет контекст; объём другой услуги автоматически
не переносится. Явное межуслуговое продолжение получает объём от модели.
Разные задачи/объёмы, включая deferred, не выбираются по позиции; pending один
не становится завершённым контекстом. «А в моём случае?» не имеет отдельного
обработчика: уточнение остаётся решением модели при нехватке контекста.

**Что осталось вне удаляемого пути:** RequestTreatmentSituation и сообщение
treatment_same_requires_subject в `contracts/request_understanding.py`,
PersistedSituationState и общий legacy state в `contracts/response_plan_session.py`,
legacy materialization/policy entry остаются для не-D2 потребителей. D2 не
создаёт эти типы и не передаёт им ordinary semantic result. В общем policy
resolver прежняя ветка получает request_ages из legacy registry; D2 использует
age_group операции напрямую. `situation_action` во входе lead/transport —
существующий lead-контракт, не patient carry. Исторический reason
`known_situation` в price trace — метка, не отдельный путь решения.
Не объявляем всю legacy-архитектуру репозитория удалённой.

**Сохранённые защиты:** medical/admin и правила child/past_history/payment;
утверждённые price rows/units и действующая граница D2-114; tenant/revision/TTL,
проверка показанного UI; consent/lead/privacy и receipt idempotency. Прямые
age-тесты покрывают price, booking, clinic_policy, adult/child/past_history.
Это представление факта для текущей задачи, не постоянная возрастная запись.

**Отдельный bug fix известного click:** `core/d2_dialogue.py` читает target,
volume и brand из завершённой source-part показанного ответа. Checker обнаружил
P1: authored fallback с status=recovered терял эти параметры, поскольку чтение
допускало только answered. Теперь принимаются оба завершённых статуса;
JSON/SSE регрессия проверяет click, replay, следующий input и подлинность ref.
Источник не выбирается повторно моделью. Это не закрывает D2-118 целиком:
первичный полезный ответ без content_ref по §8.4 по-прежнему может не иметь
source follow-up. Topic→document fallback, блокировка текста и новый вызов
самостоятельно не вводились. Виджет не изменялся.

**Старая сессия и заявка:** schema4/state и прежний completion несовместимы
со schema5. Новый ход старого SID и его replay отклоняются до provider/effect;
нет migration/reset/recovery. Тест сравнивает SQLite state payload, request rows
и lead row до/после отказа: они byte-equal. Активная заявка с именем сохранена.
У завершённой demo_stub заявки прежний receipt остаётся в записи, но replay
старого несовместимого SID не обещается и отклоняется. Новый SID контактов
не наследует. Это локальный baseline без production-пользователей.

**Astra:** отдельная read-only консультация именно D2-117 (не перенос PASS
clarification): nullable volume/explicit unknown; прямые age/context/payment
прежнему policy owner; заменяющий D2 state и одна receipt projection;
несовместимый старый state/completion без удаления lead; известный click;
deferred участвует в ambiguity, но не выбирается как completed context.
Консультация не является финальным Checker review или live evidence.

**Проверки исполнителя:** изолирующий runner блокирует сеть, отключает dotenv,
использует fake provider и временные DB/logs. Основной прогон 543 тестов:
**447 PASS / 96 FAIL**, 511.70 с (`d2-interface-offline-j13lsz1h/results.xml`).
Из 96 падений 32 — недоделанная миграция тестовых fixture/assertion на volume
и ошибочная проверка отсутствия нового API. Исправлены только эти тесты;
focused recheck **57 PASS / 0 FAIL**, 88.11 с
(`d2-interface-offline-vewcs5ct/results.xml`). Runtime после исправления P1
Checker не менялся. Это не новый полный зелёный прогон и числа не суммируются.
Отдельный новый context/volume/cross-service набор ранее: **47 PASS / 0 FAIL**
(`d2-interface-offline-2t26dk3v/results.xml`).

Оставшиеся **64 текущих fail cases** сопоставлены с preimplementation snapshot
`d2-discussion-runtime-baseline-mzxnerjc` (HEAD + прежний 21-file WIP), без foreign
файлов. Артефакты baseline в `%TEMP%`: `d2-interface-offline-1rl6fbi_` (3/7),
`on3rlkf_` (55/35), `0lq67uzi` (30/28), `hymbwov8` (79/11), числа PASS/FAIL.
Сопоставление учитывает rename situation→volume, новый заголовок A01 и
свёрнутые reported/correction/hypothetical параметры в одном scope-тесте.
Долг: прежние catalog/price/extent-menu ожидания; authored-vs-model-prose
ожидания; неполные test source authorities; старые raw envelope fixtures
diagnostics/stage3/presentation. В diagnostics/materialize baseline падал на
старом monkeypatch API; после его замены тест доходит до другого прежнего
дефекта — raw envelope отвергается parser раньше materialize. Не выдаём
совпадение одного fail ID за тождество этой причины. Полный CI не зелёный.

Разбивка 64 fail cases по файлам: continuation 5, demo_snapshot 4, diagnostics 11,
independent_request_parts 4, multi_request 4, part_failure 4, price_deferral 1,
price_presentation_http 12, price_scope_selection 5, prose_realization 1,
sim2_contract 1, single_request 3, snapshot_sources 3, stage3_prices_scope 4,
ui_b12_scenarios 1, volume_choices 1. Их исправление не объявлено частью D2-117.

Independent Checker: собственные **77 уникальных PASS / 0 FAIL** в трёх
непересекающихся наборах 59+9+9; P1 recovered-click закрыта focused recheck.
Финальный verdict после чтения отчёта и сверки 45 файлов: **PASS**,
блокирующих P0/P1 нет. Удаления и владельцы подтверждены по реальному пути.
Эти числа не суммируются с прогонами исполнителя. Live/provider/SMTP calls **0**;
понимание живых переформулировок, strict provider и widget этим не аттестованы.

**Изменённые файлы и Git:** root/Git top `C:\Cursor Projects\artgents-bot-active`,
ветка `codex/d2-stage1-contract`, HEAD `a53e6b4f37e1d35474f6e8c8c41bcdcb0767bddf`,
origin/main и merge-base `141ce91fb1731cd990fcf8391550150016c73e7f`.
Точный allowlist §8.6 соблюдён. Этот этап меняет 13 runtime-файлов:
четыре contracts §8.6 и девять core §8.6 кроме `core/d2_dialogue_store.py`;
28 существующих tests и новый `test_d2_discussion_context_http.py`; Interface
Task, Roadmap, Ledger. Итого 45 файлов относительно preimplementation snapshot.
`contracts/response_plan_session.py`, `test_d2_document_click_task_http.py` и три
других task docs byte-equal предыдущему WIP: их diff к HEAD не новая работа.
Весь накопленный diff: 49 tracked modified + один новый тест; staging пуст.
Новых commit/push/PR/merge/deploy нет. Foreign `data/`,
`docs/MARKETING_ANSWER_SCENARIOS.md`, `docs/tasks/DEMO_D2_SIM0_TASK.md` сохранены,
не читались и не менялись. Git предупреждает о недоступности global ignore;
его содержимое и `.pytest_cache` не проверялись. Финальные проверки: diff
--check чист; AST 44 Python-файлов корректен; 102 локальные файловые ссылки
в шести документах, отсутствующих 0. Никаких raw private logs в diff не добавлено.

## 9. D2-118 — источник ответа и показ продолжений, 2026-10-02

GO владельца после разбора уже принятых правил: «Ок, делаем и потом промпт
в курсоре и тест в виджете по всем правкам». Тип: **bug fix**, не новая
архитектурная замена. Порядок: реализация/offline → independent Checker →
промпт Cursor → проверка владельцем в виджете. Agent live/provider сейчас 0;
будущий live требует отдельного ограниченного бюджета перед запуском.

Preflight: root/Git top C:\Cursor Projects\artgents-bot-active;
codex/d2-stage1-contract; HEAD a53e6b4f37e1d35474f6e8c8c41bcdcb0767bddf;
origin/main/merge-base 141ce91fb1731cd990fcf8391550150016c73e7f.
Baseline — текущие 49 tracked modified + test_d2_discussion_context_http.py,
сохранённые поверх git archive HEAD в temp `d2-followup-baseline-70ysjbqa`.
Staging пуст. Foreign data/, MARKETING_ANSWER_SCENARIOS.md и SIM0_TASK не читать
и не менять. Commit/push/merge/deploy не разрешены.

Exact allowlist этого bug fix:
- core/one_call_prompt_contract.py;
- core/response_plan_materialization.py;
- core/d2_dialogue.py (сохранить одинаковый frozen scope нескольких частей
  одного источника при известном click и цепочке price→detail→detail,
  без выбора между разными scope);
- tests/test_d2_content_source_ui.py;
- tests/test_d2_source_followup_http.py (новый);
- docs/tasks/DEMO_D2_INTERFACE_TASK.md;
- docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md;
- docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md;
- docs/tasks/DEMO_D2_PRODUCT_DECISIONS.md;
- docs/tasks/DEMO_D2_ACCEPTANCE.md.

Согласованная коррекция: в существующем вызове модель указывает используемый
документ в существующем content_ref; согласовать с этим инструкции и примеры.
Два фрагмента одного проверенного документа используют его UI; два разных
документа не заимствуют UI одного из них. Price/choice/detail ограничения,
неповтор, видео → follow-up → situation-action, CTA отдельно сохраняются.
Не менять маркетинговую политику по числу частей. Known click использует уже
закреплённые source/section и прежний explanation-only ответ. Sole owners §3.

Astra read-only consult: existing content_ref достаточен, нового поля/parser/
call не нужно; source selection инструкции и проводка — bug fix, не доказательство
упрощения. Пригодная prose без ref сохраняется без выдуманного source UI;
нового отказа/retry/topic→document fallback нет. Это adverse-граница приёмки,
а не повторное согласование правил показа. Offline доказывает проводку и
ограничения; фактический выбор документа требует live перефраз после Cursor.

### 9.1. Реализация и offline evidence

Изменено три runtime-файла: prompt v36 связывает обычное объяснение по
конкретному документу с existing content_ref и исправляет пример duration;
materializer проверяет единый **валидированный** источник всех content-частей
вместо автоматического запрета по числу частей; known click сохраняет scope,
если все завершённые source-parts содержат одинаковый непустой descriptor.
Часть без descriptor не отбрасывается из этой проверки. При разных
объёмах ни один не выбирается. Detail click читает descriptor не только из
price, но и из уже показанного price_detail: «цена → Что входит → Этапы оплаты»
больше не теряет объём/бренд. Новых полей, states, source classifiers,
model calls, source fallback, prose refusal или retry нет. Marketing rules
по числу частей, price/choice/detail/CTA и tenant/privacy не менялись.

Первый исполнительский прогон: `test_d2_content_source_ui.py` и новый
`test_d2_source_followup_http.py`: **37 PASS / 0 FAIL**, 34.25 с,
temp `d2-interface-offline-q13tgdkd/results.xml`. Новая HTTP regression probe
на нетронутом runtime baseline `d2-followup-baseline-70ysjbqa`:
**4 PASS / 7 FAIL / 10 deselected**, 18.39 с (`d2-interface-offline-6xkvkckt`).
FAIL — прежняя инструкция и отсутствие source UI при двух частях одного
материала, JSON/SSE. Probe скопирован в baseline только как новый test-файл.
Обычный single-part UI проходит на baseline; его прежнее отсутствие при
опущенном model ref не воспроизводится fake-ответом с заполненным ref.

Новые проверки: первый pain/duration source-answer, один/два фрагмента,
видео/порядок/CTA, показанный click без повторного model ref, replay, следующий
scope, неповтор, цена → отдельный duration, цена+content, два документа,
missing/invalid ref с сохранением prose, одинаковый документ с разными объёмами.
Повторные показанные элементы не появляются. Это offline подтверждение кода,
а не доказательство, что реальная модель всегда выбирает подходящий документ.
Дополнительный regression: **131 PASS / 19 FAIL**, 162.05 с, temp
`d2-interface-offline-2dkt4wcq/results.xml`. Это document click, три volume
actions, completion/context/старый SID/age, strict parser, lead interruption,
booking, historical price-details. Все 19 fail IDs и сообщения **точно совпали**
с baseline-прогоном **3 PASS / 19 FAIL**, 19.60 с (`d2-interface-offline-md3w71r6`):
18 старых raw-envelope cases в price_details_http и прежний extent-menu-copy.
Эти тесты не редактировались; весь CI не объявлен зелёным. Offline browser test
в старом price-details наборе упал до renderer; реальный виджет не аттестован.

Новая цепочка price→includes→stages на новом контракте воспроизвела потерю
descriptor в обоих transports: **2 FAIL** до коррекции (`d2-interface-offline-27lwuksw`).
После исправления чтения price_detail **5 PASS / 0 FAIL**, 14.90 с
(`d2-interface-offline-u392kg22`): два полных JSON/SSE dialogue/replay/next-input
и три existing known-detail/service-clarification случая. Offer IDs совпадают
с показанными ценами; ни includes, ни stages не вызывают модель.
Прогоны не суммируются с независимым Checker и предыдущим D2-117.

Checker нашёл P1: у двух частей одного документа первая имела classic/3/brand,
вторая не имела scope. Фильтр исключал вторую до проверки равенства и переносил
параметры первой на click при исходном mixed ответе. Исправлен фильтр, все
matching source-parts участвуют, перенос требует nonnull и полного равенства.
Добавлена JSON/SSE × оба порядка regression: mixed context, known task без
заимствованного объёма/бренда, replay и следующий input. Ни новый selector,
ни семантическое объединение параметров не введены. Исполнительский повтор
всего нового HTTP-файла после коррекции: **27 PASS / 0 FAIL**, 54.06 с
(`d2-interface-offline-wj5n8l85`). Independent focused recheck: **6 PASS / 0 FAIL**,
19.70 с (`d2-interface-offline-lnffwd56`), P1 закрыта.

Всего этого этапа 10 файлов allowlist: 3 runtime, 2 tests (один новый),
5 существующих docs. D2-117 WIP вне них сохранён. Independent Checker:
41 PASS (`c0i2vld6`, 48.82 с), 14 PASS (`ceakvr69`, 20.99 с), focused 6 PASS;
61 execution / **59 уникальных cases**, два detail-chain повторяются.
Итоговый verdict после отчёта: **PASS — D2-118**, P0/P1 нет; это bug fix,
не аттестация новой архитектуры или live-качества. Provider/live/SMTP 0; staging пуст,
commit/push/PR/merge/deploy нет. Финальные AST 45 Python корректны;
103 локальные ссылки, отсутствующих 0; Git diff --check чист.

### 9.2. Исторический промпт review D2-117/118 (до D2-119)

```text
Проведи независимый read-only review накопленных D2-117 и D2-118 правок.
Репозиторий C:\Cursor Projects\artgents-bot-active, ветка codex/d2-stage1-contract,
HEAD a53e6b4f37e1d35474f6e8c8c41bcdcb0767bddf,
origin/main и merge-base 141ce91fb1731cd990fcf8391550150016c73e7f.
Прочитай AGENTS.md, docs/WORKFLOW_CHECKER.md, текущий верх Roadmap,
Target Contract §3 и Interface Task §8.7, §9 с результатами и allowlist.
Не редактируй файлы, не делай live/provider/SMTP, commit/push/merge/deploy.
Не читай foreign data/, docs/MARKETING_ANSWER_SCENARIOS.md,
docs/tasks/DEMO_D2_SIM0_TASK.md. Staging должен оставаться пустым.

Проверь фактический JSON/SSE → parser → operation → price/materializer →
source UI → click → completion/store → следующий input. D2-117: действительно
удалены subject/patient state/focus/current-same-cross carry/adapter; один
discussion context и прямой volume. Проверить возраст/payment/medical,
tenant/UI/lead/privacy, старый SID без recovery и сохранность заявки.
D2-118 отдельно как bug fix: existing content_ref в том же вызове, правила
показа документа, один документ с двумя частями, два разных источника,
price+content, known click без нового выбора source, неповтор и CTA.
Не пропустить adverse missing/invalid ref: пригодный ответ сохраняется,
кнопки не выдумываются, нет нового отказа/repair/retry/второго вызова.
Не считать prompt проверкой живого понимания или offline HTTP тестом виджета.

Baseline D2-117: temp d2-discussion-runtime-baseline-mzxnerjc (HEAD + 21-file WIP).
Baseline D2-118: temp d2-followup-baseline-70ysjbqa (HEAD + предыдущие 50 файлов).
Изолирующий runner: %TEMP%\d2-interface-offline-runner.py, запуск .venv Python.
Он блокирует сеть и направляет DB/logs в temp; не импортируй приложение вне него.
Выполни пропорциональные offline проверки и сравни failures с baseline;
не суммируй пересекающиеся прогоны. Собственный verdict PASS/REJECT с P0/P1,
удалёнными зависимостями, поведением, тестами, ограничениями и Git status.
PASS не разрешает публикацию; после review владелец проверяет виджет по §9.3.
```

### 9.3. Ручная проверка виджета после Cursor

Новый локальный SID для независимых сценариев (существующая DEV-кнопка),
без переноса старой сессии. Сервер перезапустить из текущего checkout после
остановки прежнего процесса в его терминале. Команда PowerShell с логами:

```powershell
$env:D2_FULL_AUDIT_LOG = "1"
$env:APP_ENV = "local"
$env:PYTHONIOENCODING = "utf-8"
& "C:\Cursor Projects\artgents-bot-active\scripts\start_local_widget.ps1"
```

Адрес: http://127.0.0.1:9001/static/widget-test.html . Launcher не останавливает
чужой процесс и отказывается запускать второй на занятом порту.
Full audit пишет выбранный документ, UI и ошибки в BOT_LOG_DIR/d2_full_audit.jsonl
(без настройки — logs/d2_full_audit.jsonl). Использовать вымышленные данные;
не добавлять raw логи в Git. Существующий механизм, новый logger не добавлен.

Этот план составлен до пользовательского widget-прогона; фактические найденные дефекты и следующий план — §10. Прежний лимит не является разрешением новых вызовов.
Один проход: максимум **40 пользовательских отправок/кликов**, консервативный
потолок 40 model calls; не повторять автоматически неудачные вопросы.
Запись завершением телефона не отправлять: проверить имя/паузу/отмену.
Фиксировать фактические calls и request_id ошибок; при достижении лимита стоп.

| Отдельный сценарий | Действия и ожидаемый результат |
|---|---|
| Страх боли | «Боюсь боли при имплантации» → показанное продолжение → «Расскажи ещё об обезболивании». У первого ответа video pain-doctor-explains + «Какую анестезию используют»; после клика отвечать на выбранный раздел, прежние video/follow-up не повторять. CTA отдельно |
| Цена → сроки → контакты | «Сколько стоит восстановить три зуба с помощью классической имплантации?» → «А сколько времени занимает лечение?» → показанное продолжение → «Какой у вас адрес?» → «А сколько ждать постоянную коронку?». На duration две ссылки: «От чего зависит срок имплантации», «Можно ли ускорить имплантацию», если не показаны ранее. Сохраняются classic/три, subject не требуется; цены не умножаются |
| Альтернатива/исправление/смена | «Сколько стоит восстановить один зуб?» → «А если три?» → «Нет, всё-таки три» → «Расскажите про отбеливание». Текущий объём три, без параллельной личной единицы; отбеливание не наследует три |
| Три выбора объёма | В трёх новых сессиях «Сколько стоит имплантация?» → соответственно «Один зуб», «Вся челюсть», «Пока не знаю». Ровно три кнопки, без «Несколько зубов»; click даёт цену/честный пробел без модели, unknown не повторяет меню и не начинает заявку |
| Детали цены | «Сколько стоит классическая имплантация?» → «Что входит» → «Этапы оплаты» → «А что входит во второй вариант?». Если показано несколько offers, кнопки раскрывают весь показанный набор, свободный вопрос — указанный вариант; данные из прайса, не суммы из prose |
| Смешанный ответ | «Сколько стоит классическая имплантация и больно ли это?» — информация и цена сохраняются, обычных pain follow-up/video нет; допустимый price-detail и CTA по правилам |
| Два документа | «Расскажите про обезболивание и сроки имплантации» — если выбраны два разных документа, их secondary не показывать. Один документ определяется фактическим ref в логе, не догадкой по вопросу |
| Возраст и medical | Новые сессии: «Можно записать ребёнка 12 лет на имплантацию?»; «В детстве лечил зубы, сейчас мне 35, хочу консультацию»; «После вчерашней операции сильная боль». Правило детского приёма/прошлого возраста сохраняется; текущая боль — утверждённый контакт без рекламы, не обычный fear-сценарий |
| Заявка | Разрешённая CTA → вымышленное имя → вопрос об адресе во время запроса телефона → существующий путь ответа/продолжения → отмена. Имя не теряется при паузе, отмена штатна; новый SID его не наследует. Телефон не отправлять |

Нет кнопок там, где ожидаются: по request_id различить отсутствие ref у модели,
валидированный источник, разрешённые/уже показанные кнопки и итоговый UI.
Не называть пропущенный моделью ref успешной live-проверкой только потому,
что сам текст ответа пригоден. После Cursor можно собрать фактический результат
этого прохода; новых провайдерных вызовов автоматически не запускать.

## 10. D2-119 — согласованные правила и план доведения

### 10.1. DOC checkpoint и baseline

Классификация этого шага: **документация**, runtime не меняется.
Owner разрешил зафиксировать все обсуждённые правила и устранить расхождения.
Корень/Git top: `C:\Cursor Projects\artgents-bot-active`, branch
`codex/d2-stage1-contract`, HEAD `a53e6b4f37e1d35474f6e8c8c41bcdcb0767bddf`,
origin/main и merge-base `141ce91fb1731cd990fcf8391550150016c73e7f`.
Baseline: текущий WIP, включая D2-117/118 и локальное логирование; копия семи
документов до этого шага — `%TEMP%/d2-rules-doc-baseline-xza1b8ng`.
Exact DOC allowlist: `docs/MARKETING_ANSWER_SCENARIOS.md` и
`docs/tasks/DEMO_D2_{PRODUCT_DECISIONS,ACCEPTANCE,TARGET_CONTRACT,DELIVERY_ROADMAP,INTERFACE_TASK,CHECKPOINT_LEDGER}.md`.
Это перечисление семи файлов, не разрешение править произвольные совпадения.
Памятка ранее была foreign/untracked, теперь явно входит в запрос владельца;
не заменять её целиком и не трогать чужую работу. `data/`, SIM0 Task и все
runtime/tests вне allowlist сохраняются. Staging пуст; публикация не входит.
Ответственность — только Target Contract §3, таблица не копируется и не меняется.

### 10.2. Исторические находки до D2-119

Статусы «Открыто» ниже относятся к исходному разбору. Последующие исправления
и границы доказательств — §10.7–12; это не список текущих runtime TODO.

Прочитан существующий локальный журнал из `%TEMP%/d2-widget-20261002-192344`.
В анализируемом отрезке 2026-10-02 20:45–21:17 UTC: 44 запроса, 37 записанных
модельных ответов, 43 опубликованных результата и один неуспешный ход. Это
действия владельца, не вызовы агента и не заранее ограниченный агентский прогон.
Raw диалоги/контакты в Git не копировать; здесь только признаки и trace-prefix.

| Наблюдение | Доказательство | Статус |
|---|---|---|
| Исходный MD вместо живого ответа | c09481a5: модель вернула prose + authored, materializer опубликовал раздел с якорем | Открыто, правило D2-119.1 |
| Unknown повторяет обзор | 3537195e и d369520f: цены повторно, model call отсутствует | Открыто, новое конкретное поведение D2-119.2 |
| Price-detail повторяется | 9bb54488: после includes снова includes/stages; старый тест требует повтор | Открыто, D2-119.3: исключать нажатое |
| Текущая боль/кровотечение идёт в dialogue | 1da1409e, 72e0a5c0, cf1897f5: ordinary content и тематический UI вместо admin | Открыто, нарушение D2-023 |
| Ребёнок: неустойчивый policy payload | 21adff58: policy_ids=[0], отказ parser; две позднейшие формулировки получили policy-ответ | Открыто; два успеха не закрывают устойчивость |

Три зуба → сроки и ряд source-click работают в этом отрезке; это не полный
PASS архитектуры, strict provider или всех сценариев. Логи были в BOT_LOG_DIR,
не потеряны: прежнее предположение агента об отсутствии записи было неверным.
Логирование исправлено отдельным предшествующим шагом: локально default ON,
explicit off/prod запрет сохранены, launcher показывает фактический путь и
проверяет запись. Старые ручные setenv-команды §9.3 не обязательны при default.

### 10.3. План runtime в существующей задаче

Все правила согласованы D2-119. Следующий runtime checkpoint требует обычного
preflight и точного списка файлов по трассировке; этот DOC allowlist не разрешает
править код. Не просить повторного согласования уже принятых правил.

| Порядок / класс | До → после | Что убрать / сохранить | Предполагаемые места трассировки (не runtime allowlist) |
|---|---|---|---|
| 1. Bug fix medical/policy | Модель отправляет текущую личную проблему в dialogue → тот же вызов различает страх/текущую проблему и возвращает admin; возрастные политики используют корректные ID | Существующий admin-текст/телефон и policy owner; никаких regex фраз, нового классификатора, второго вызова или угадывания ID | one_call_prompt_contract, d2_live_provider, d2_dialogue_result, clinic_policy_resolver, d2_dialogue, d2_snapshot_sources |
| 2. Архитектурное сокращение ordinary authored | Модель выбирает prose/готовый MD → обычное объяснение только prose | Удалить режим и достижимые ветви выбора/подстановки обычного MD, включая known-task и recovery, а не спрятать условием. Source/section для grounding/UI, точные price/policy/admin остаются | d2_dialogue_result, explanation parser, d2_content_realization, response_plan_materialization, prompt/schema |
| 3. Bug fix unknown action | Unknown click повторно запускает обзор → известное действие публикует согласованную короткую фразу + CTA без модели | Убрать повторный вывод прайса именно для явного unknown-click; тема/unknown идут в тот же completion и store. Общий первый обзор и прочие price-click сохраняются | d2_dialogue known action, materialization, completion projection, existing CTA |
| 4. Bug fix price-detail UI | После detail обе кнопки возвращаются → исключена нажатая, другая остаётся; новая услуга получает свой набор | Использовать существующую память/подлинное действие, без отдельного semantic state. Сохранить offers/brand/volume, tenant/revision/replay; content/video shown-rule не менять | price_detail UI, existing UI history/action, completion и session projection |

Владелец смысла свободной реплики/объяснения — модель в существующем вызове;
known clicks исполняет сервер, суммы и условия выбирает прежний price owner,
следующий контекст читает завершённый результат. §3 остаётся неизменным.
Для пункта 2 нужен список удалённых достижимых символов/call paths и adverse
старого режима. Для bug fixes достаточно доказанного поведения; их нельзя
выдавать за завершение всей архитектуры. Если существующая память не позволяет
выразить нужный неповтор, сначала показать минимальную необходимую замену,
не добавлять самостоятельно поля/параллельную память.

D2-117 не переделывать: обсуждаемый объём сохраняется напрямую, patient/subject
не возвращаются. Stage-факты — доступная история, обязательные специальные
меню отменены. Заявка, контакты и их пауза/отмена сохраняются; новый recovery
старого SID не вводится. Остальные SIM-4 selection и SIM-5 cleanup вне шага.

### 10.4. Проверка готового результата

Один соразмерный offline набор на целостный checkpoint, без повторных полных
прогонов после каждой мелочи. Проверить обе HTTP формы, answer/UI → click →
completion → следующий input и replay; готовые payload доказывают программу,
не живое понимание. Минимальные группы: страх/текущая боль/отёк/кровь + цена;
ребёнок и взрослый с прошлым детством; несколько document-click с old authored;
unknown без цен/вызова с сохранением темы; includes→stages, смена услуги,
длинное продолжение и stale/foreign кнопки; отсутствие автозаявки.
Независимый Checker на готовом checkpoint, focused recheck только находок.
Cursor — review того же целостного результата, не новые продуктовые согласования.
Затем пользовательский widget с живыми переформулировками. Для агентского live
нужен отдельный явный hard budget; сейчас новых вызовов не разрешено.
Полный CI — перед merge. Ни PASS docs, ни offline PASS не закрывают виджет.

### 10.5. Результат DOC checkpoint

На момент этого исторического DOC checkpoint код D2-119 ещё не был реализован.
Последующая реализация и проверки — §10.6–10.8.
Проверки ссылок/внеallowlist/независимого DOC review фиксируются в Ledger.
Новые runtime tests/provider/live/SMTP: 0; commit/push/merge/deploy: нет.

### 10.6. Runtime D2-119 — preflight 2026-10-03

Owner GO: «Ок. Тогда идем дальше». Repository/Git top:
`C:\Cursor Projects\artgents-bot-active`, branch `codex/d2-stage1-contract`,
HEAD `36105d784dc672228a693e30ee3948c95bc43dcc`; origin/main и merge-base
`141ce91fb1731cd990fcf8391550150016c73e7f`. Tracked checkout/staging чисты.
Foreign `data/`, `docs/tasks/DEMO_D2_SIM0_TASK.md` не читать/не менять.
Baseline: `%TEMP%/d2-119-baseline-36105d7.zip` (git archive HEAD).

Exact runtime allowlist: `contracts/d2_dialogue_result.py`,
`contracts/response_plan.py`, `core/d2_dialogue.py`,
`core/d2_snapshot_sources.py`, `core/d2_content_realization.py`,
`core/d2_completion_context.py`, `core/response_plan_materialization.py`,
`core/one_call_prompt_contract.py`, `tests/test_d2_119_http.py`,
`tests/test_d2_sim1_known_actions_http.py`,
`tests/test_d2_sim2_dialogues.py` (обновление старого ожидания цены после unknown),
`tests/test_d2_discussion_context_http.py`,
`docs/tasks/DEMO_D2_INTERFACE_TASK.md`, `docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md`.

Классификация/владельцы — §10.3 и Target Contract §3. Архитектурное удаление:
ordinary input mode/fallback → только content_text с optional provenance →
удаляются поля, known-parser mode, document-task authored default,
realizer authored/recovery и ordinary publication alternatives. Объясняет
модель прежним вызовом; сервер больше не выбирает заменяющий текст документа.
Medical/policy, unknown click и clicked price UI — bug fixes, не новые слои.
Astra read-only консультация подтверждает existing exact-result для unknown
и namespaced service/aspect в existing secondary_ref_ids для verified clicks.
Проверки/результат пока впереди; live/commit/push не входят в этот шаг.

### 10.7. Реализация D2-119, 2026-10-03

Статус §10.5 относится к предыдущему DOC checkpoint. Runtime теперь изменён
в пределах §10.6. Новых calls, классификаторов, patient memory, адаптеров,
авторского policy текста или восстановления старого SID не добавлено.

- **Удаление зависимости:** `ExplanationFields.content_realization` и
  `content_fallback_section_ref`; known parser принимает только ID/text;
  document task больше не задаёт authored. `_exact_authored_text`,
  `_recovery_section_refs`, `_is_korotko_section` и ветви их публикации удалены.
  Realizer больше не получает authority/текст документа. Ordinary publication
  допускает только model_prose; recovered/fallback удалены из результата.
  Provenance ref/sections остаётся для grounding и проверенного source UI.
- **Medical/policy bug fix:** prompt v37 явно разделяет текущую личную проблему
  и страх будущего лечения, требует существующий admin даже вместе с ценой;
  policy IDs — точные строковые ключи tenant, не номера. Исполняются прежние
  code-owned clinic/admin/price/age guards. Это инструкция прежнему вызову,
  не доказательство живого выбора и не новый медицинский классификатор.
- **Unknown bug fix:** verified volume unknown после прежних policy/reference
  guards становится existing exact reference result с согласованной фразой,
  topic/service/brand и unknown volume. Прайс и модель не вызываются; общий CTA,
  commit и completion pointer сохраняют тему. Автозаявки нет.
- **Price UI bug fix:** builder одновременно исключает текущий verified click
  и прошлые `price_detail_clicked:<service>:<aspect>` в existing secondary IDs.
  Эти ключи сохраняются только вместе с успешным commit. Показ ценовых кнопок
  больше не считается их нажатием; другая услуга имеет отдельный набор при
  наличии её конфигурации и данных. Source follow-up/video скрывают показанное.

Путь: `/ask` и `/ask/stream` → `run_d2_ask_json` →
`run_d2_dialogue_turn` → `validate_d2_payload` / existing known action →
`resolve_d2_operations` → common commit → `project_completed_dialogue`.
Модель владеет prose и свободным смыслом; сервер исполняет verified action;
price owner выбирает утверждённые данные. §3 не изменён.
Оставшиеся legacy input mode-поля в старом request_understanding и legacy
parser не используются active `d2_contract=True`; shared realizer даже для
них больше не имеет механизма подстановки MD. Их общая уборка вне этого шага.

**Offline executor:** isolated runner отключает dotenv/network, использует
временные SQLite/логи. Первый coherent набор: 178 PASS / 5 FAIL, 291.95 с,
`%TEMP%/d2-interface-offline-fb3j_9_g/results.xml`. Пять исправленных test
expectations: typed not_requested receipt вместо None; настроенные price
buttons новой услуги; SSE error event вместо HTTP400; прежняя цена после unknown.
Адресный проход: 17 PASS / 1 FAIL (SSE assertion), 36.01 с, `...h9yysaez`;
после исправления оба price-chain cases PASS, 19.80 с, `...qggb7fff`.
Дополнительные два old-authored/lead probes сначала ошибочно ожидали отказ
на lead-only pause; он не читает ordinary history. Корректный probe переходит
к обсуждению через verified pending-answer click: **2 PASS**, 7.51 с,
`%TEMP%/d2-interface-offline-_88aedke/results.xml`.
Итого покрыты 185 уникальных cases с успешной последней проверкой каждого;
повторные прогоны не суммируются. Это не полный CI и не live PASS.

Основной набор: `test_d2_119_http`, `test_d2_sim1_known_actions_http`,
`test_d2_discussion_context_http`, `test_d2_source_followup_http`,
`test_d2_sim2_dialogues`. Проверены JSON/SSE, prose/source-click и adverse
старые поля без retry, unknown/replay/next-context, includes→stages и другая
услуга, неповтор после выхода за историю трёх ходов, stale clicks, age guards,
admin exact phone/urgent copy, lead pause/privacy и старые SID.
Новые fixtures не проверяют, что live модель выберет правильный admin/policy.
Исторические legacy-fixture/menu-copy failures общего набора здесь не
перепроверялись и не объявляются устранёнными. Новых baseline failures в
выбранном наборе не заявляем.

**Старая сессия и заявка:** state schema остаётся 5. Предыдущие model_prose
результаты совместимы. Старые authored/fallback/recovered completions и pending
с удалёнными input-полями несовместимы при чтении; обычный ход отклоняется
`d2_invalid_turn`, без migration/reset/recovery. Lead-only путь может работать
без чтения ordinary receipt. Probe старого authored через переход из паузы
к обсуждению сохраняет байты заявки с именем, state и request rows; модель
не вызывается. Старые schema3 tests также подтверждают сохранение заявки и
replay завершённого demo_stub receipt. Это не обещание replay любого старого
authored ответа: он сам больше не соответствует контракту.

Independent Checker: **PASS**, P0/P1 нет. Независимо 48 уникальных cases
с успешным последним результатом (initial 35/36, focused 12/14, fresh old
receipt 2/2; повторяющиеся cases не суммировать). Артефакты
`%TEMP%/d2-interface-offline-{mkzzhjwq,9iggmxzw,ro2qtrml}/results.xml`.
Подтверждены 185 executor cases по XML, active schema и AST 12 Python-файлов.
Сверены 1615 tracked файлов вне allowlist с archive baseline (CRLF normalized):
изменений нет. `git diff --check` чист. PASS только текущего checkpoint;
живой выбор модели, widget, полный CI и архитектура всего бота не аттестованы.
Provider/live/SMTP: 0. Staging пуст; HEAD 36105d7, commit/push/PR/merge/deploy
этого шага не выполнялись. Foreign paths из §10.6 сохранены.

### 10.8. Следующая проверка Cursor и widget

Промпт для Cursor (review, не новая реализация):

```text
Независимый read-only review D2-119 в C:\Cursor Projects\artgents-bot-active.
Ветка codex/d2-stage1-contract; baseline/HEAD 36105d784dc672228a693e30ee3948c95bc43dcc.
Проверь текущий diff и новый tests/test_d2_119_http.py по AGENTS.md,
WORKFLOW_CHECKER.md, Target Contract §3, Product Decisions D2-119,
Interface Task §10.3 и §10.6–10.7. Exact allowlist — §10.6.
Сначала прочитай изменённые тесты, затем проследи реальные JSON/SSE пути.
Проверь удаление ordinary authored/fallback, сохранение source UI/контекста,
unknown без цен/модели/автозаявки, price buttons hide-clicked per service,
medical/age instructions при прежних code-owned guards, replay и lead/privacy.
Проверь adverse output и старые несовместимые receipts без migration/reset.
Не исправляй код и не расширяй задачу. Foreign data/ и DEMO_D2_SIM0_TASK.md
не читать. Никаких live/provider/SMTP, commit/push/merge/deploy.
Только соразмерные offline тесты с изоляцией dotenv/network/SQLite как в §10.7.
Дай PASS/REJECT с P0/P1, отдельными P2 и точной границей доказательств.
Не выдавай offline prompt/payload тесты за живое понимание модели.
```

После review — перезапуск локального бота прежним `scripts/start_local_widget.ps1`
и пользовательский проход из **новых бесед**, без удаления старых данных:

1. «Я боюсь боли при имплантации» → живое объяснение и разрешённые source
   продолжения. Клик → ответ на выбранный вопрос без заголовка `{#...}`;
   ранее показанные content/video не повторяются.
2. «Сколько стоит имплантация?» → «Пока не знаю» → ровно согласованная фраза
   и CTA, без прайса/повторного уточнения → «А сколько займёт лечение?».
3. «Сколько стоит классическая имплантация?» → «Что входит» → остаются только
   «Этапы оплаты» → клик → ценовых кнопок больше нет. Новая услуга получает
   кнопки только при наличии configured profile и данных; у текущего demo
   All-on-4 price_detail profile отсутствует, автоматически его не добавляли.
4. Новые беседы для «После операции сильно болит и опухло», «Кровь не
   останавливается», «После лечения больно, сколько будет стоить помощь?» →
   утверждённый admin/телефон, без объяснения лечения и рекламных продолжений.
5. «Можно записать ребёнка 12 лет?» → clinic policy без ошибки. Отдельно:
   «В детстве лечил зубы, сейчас мне 35» → не применять детское ограничение.
6. «Цена восстановления трёх зубов классической имплантацией?» → «А сроки?» →
   тема/объём сохраняются, subject не требуется. Затем разрешённая CTA →
   вымышленное имя → адрес → продолжение/отмена заявки; телефон не отправлять.

Фиксировать request_id и фактический BOT_LOG_DIR launcher. Неправильный выбор
admin/policy/source моделью — открытый дефект live, не оправдание офлайн PASS.
Агентский live не запускается без отдельного согласованного бюджета.

## 11. D2-120 — продолжение после medical и сообщение при сбое

Owner GO 2026-10-03: «Давай». Классификация: **bug fixes**, не завершение
архитектурного этапа. Target Contract §3 сохраняется. Root/Git top:
`C:\Cursor Projects\artgents-bot-active`, branch `codex/d2-stage1-contract`,
HEAD `36105d784dc672228a693e30ee3948c95bc43dcc`, main/merge-base
`141ce91fb1731cd990fcf8391550150016c73e7f`. Staging пуст.
Baseline — предыдущий 14-file D2-119 WIP, snapshot
`%TEMP%/d2-120-baseline-36105d7-wip.zip`.
Foreign `data/` и `docs/tasks/DEMO_D2_SIM0_TASK.md` не читать/не менять.

Exact allowlist: `core/d2_dialogue.py`, `core/d2_snapshot_sources.py`,
`core/d2_completion_context.py`, `core/one_call_prompt_contract.py`,
`static/widget/api.js`, `static/widget/widget.js`,
`tests/test_d2_120_http.py`, `tests/js/d2_error_copy.mjs`,
`tests/js/d2_widget_harness.mjs`, `docs/MARKETING_ANSWER_SCENARIOS.md`,
`docs/tasks/DEMO_D2_PRODUCT_DECISIONS.md`, `docs/tasks/DEMO_D2_ACCEPTANCE.md`,
`docs/tasks/DEMO_D2_TARGET_CONTRACT.md`, `docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md`,
`docs/tasks/DEMO_D2_INTERFACE_TASK.md`, `docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md`.

До: medical marker запрещает следующий ordinary ответ, medical ход не входит
в history. После: медицинский ответ завершает только текущий вопрос, следующий
смысл решает модель в прежнем вызове с existing receipt history. Маркер остаётся
в exact response contract, перестаёт быть D2 session lock; spam_closed не меняется.
Жалоба → лекарства/лечение этой жалобы остаётся admin; жалоба → детский приём
или адрес может получить обычный policy/contact. Не вводить classifier/reset.
Astra read-only консультация: использовать existing receipts/projection,
сохранить terminal/current-turn запреты UI и прежний spam guard.

Ошибки: existing error display, не успешный bot answer. Нейтральная фраза
«Не получилось показать ответ. Понимаю, что это неудобно». Не утверждает, что
заявка отправлена/не отправлена, не просит повторять контакты. Server error codes,
HTTP/SSE error, diagnostics/audit и rollback/receipt semantics сохраняются.
Новых retries нет; существующий transport replay с тем же ID не удаляется.
Исправляется пробел между admin phone и urgent sentence. Offline проверки:
medical→medical/policy/contact, history/age/spam; ошибка до/после commit,
lead preservation/replay; mocked JSON/SSE/network display. Затем Checker.
Live/provider/SMTP/commit/push/merge/deploy не входят в этот шаг.

### 11.1. Результат реализации и проверки

Реализовано: предыдущий medical marker больше не отклоняет новый dialogue;
medical receipt с вопросом и masked/bounded terminal_text входит в прежнюю
историю. Текущий admin сохраняет exact copy/no UI; spam_closed остаётся hard
stop, обычный spam guard действует и после medical. Prompt v38 объясняет
разницу независимого вопроса и медицинского продолжения в том же вызове.
Shared resolver/terminal schema, price и lead owner не менялись. Исправлен
пробел перед urgent copy. Старый medical marker обрабатывается без reset;
прошлые не записанные в history реплики не восстанавливаются задним числом.

Widget `setError` и JSON `postAsk` отображают общий нейтральный текст; SSE
сохраняет error code до слоя отображения. Не добавлен новый успешный answer,
completion или журнал. Сервер по-прежнему логирует exception/trace/diagnostic,
JSON сохраняет error status, SSE — event:error. Прежний transport replay с
тем же request ID сохраняется, новых повторов/модельных вызовов нет.
Ошибка после commit не доказывает неотправку заявки: поэтому текст не зовёт
повторно отправить контакты. Сам error display не меняет receipt/lead/state.

Executor offline: **33 PASS**, 62.76 с — `test_d2_120_http.py` (16),
`test_d2_119_http.py` (15), две lead pause/privacy проверки SIM2.
Артефакт `%TEMP%/d2-interface-offline-bi86g41a/results.xml`.
`node tests/js/d2_error_copy.mjs` — **PASS**: JSON/SSE/network failures,
неразглашение технического текста, same-ID transport replay, сохранение
уже полученного UI при поздней ошибке. Socket/provider изолированы; контакты
в тестах вымышленные, отправка только demo_stub, SMTP не вызывался.

Real browser harness — **не прошёл**: `CDP timeout: Runtime.enable` до
проверки DOM, `%TEMP%/d2-interface-offline-50rnps9m/results.xml`. Чистые harness
и static baseline из snapshot в `d2-120-baseline-check-cz5ce222` с теми же
payloads дают ту же ошибку Runtime.enable. Это воспроизведённый baseline
сбой браузерного подключения; browser/widget PASS не заявлен. Общий CI не
запускался. Живое понимание медицинских продолжений проверяет пользователь.

16 файлов нового allowlist; 1615 файлов вне него побайтно совпали с baseline,
включая предыдущие D2-119 изменения вне нового шага. Foreign WIP не читался.
Staging пуст, branch/HEAD прежние; commit/push/PR/merge/deploy нет.
Provider/live/SMTP агента: 0. Independent Checker: **PASS D2-120**,
18 уникальных HTTP PASS и node error-copy PASS; P0/P1 нет. Проверены bug fixes,
не архитектура всего бота. Финальный вердикт записан в Ledger.

Checker обнаружил P1 в новом достижимом переходе medical→spam_warn→medical:
правильный admin блокировался прежним guard. Исправлено в том же guard:
spam_warn допускает admin; ранний spam_closed hard stop неизменён.
Добавлены две JSON/SSE проверки этой цепочки. Адресно новая цепочка и
spam_closed: **4 PASS**, 8.00 с, `...d2-interface-offline-4v1yyaqz/results.xml`.
Итого executor 35 уникальных HTTP cases с успешным последним результатом;
33 + 4 не суммируются, две hard-stop проверки повторные. Independent focused
recheck: **4 PASS**, 7.79 с, `...d2-interface-offline-kxvbtu60/results.xml`;
P1 закрыта. Initial independent 16 PASS, 30.64 с, `...h7iml0wg/results.xml`.
18 уникальных HTTP cases, 20 executions; полный review не повторялся.

После перезапуска widget проверить в **одной** беседе: «Болит имплант после
установки» → «Можно записать ребёнка 12 лет?»; в другой: жалоба → «Что выпить?»
→ «Какой адрес клиники?». Первое/последнее должны получить policy/contact,
медицинское продолжение — утверждённый телефон, без медицинского совета.
Искусственно ломать живой provider для проверки заглушки не требуется:
offline fault injection проверяет ошибки до commit и после demo_stub заявки.

## 12. Кнопка отмены только на этапе телефона — 2026-10-03

Тип: UI bug fix по прямому указанию владельца; не архитектурное упрощение.
База: HEAD 36105d784dc672228a693e30ee3948c95bc43dcc плюс существующий
незакоммиченный D2-119/120. Снимок затрагиваемых старых файлов:
`%TEMP%/d2-name-cancel-baseline`. Allowlist: `core/d2_lead_bridge.py`,
`tests/test_d2_lead_cancel_ui.py`, эта карточка.

На запросе имени (включая повтор и возврат из паузы) кнопки отмены нет.
В паузе до имени остаётся «Продолжить запись». На этапе телефона, включая
паузу этого этапа, «Отменить запись» сохраняется. Текстовый отказ не запрещаем.
Владелец UI — существующий lead bridge; используем существующий этап lead owner.
Новых состояний, полей, вызовов модели и классификаторов нет. Reconcile паузы
узнаёт её по существующей кнопке продолжения, независимо от наличия отмены;
проверки владельца и revision в lead owner остаются.

Проверки: адресные offline JSON/SSE имя → пауза → возврат → телефон → отмена,
replay и сохранение этапа; существующая phone-pause/privacy проверка.
Foreign WIP: все остальные текущие изменения, включая пользовательский файл
врача, `data/`, `DEMO_D2_SIM0_TASK.md`; не включаются в эту правку.
Live/provider/SMTP, commit/push/merge/deploy не разрешены этой задачей.

Результат §12: изменены только указанные три файла. Удалён показ отмены
из обоих путей запроса имени; добавлена проверка существующего этапа при
публикации pause UI. Заявка, её состояния и текстовый отказ не заменялись.
Executor: новые 6 cases PASS (4 в k8lzhjzp, 2 в k4piymse); старый phone-pause
SSE PASS, JSON FAIL: проверка ищет «999» во всём JSON и нашла их в timestamp
23:41:49.499958Z. Independent: новые 6 PASS, старый phone-pause JSON PASS,
SSE FAIL на той же проверке, timestamp 23:43:41.999984Z; 7 PASS / 1 FAIL,
25.16 с, `%TEMP%/d2-interface-offline-zz5ol93s/results.xml`.
Это ограничение неизменённого теста; полный зелёный прогон не заявляется.
Проверка реального виджета/live не проводилась. `git diff --check` чист.
HEAD/ветка прежние, staging пуст, commit/push/PR/merge/deploy нет.
Independent Checker: PASS UI §12, P0/P1 нет. Подтверждено: единственное
вхождение «999» в упавшей SSE проверке — activity.last_user_turn_at;
новые 6 cases PASS. Это UI bug-fix PASS, не аттестация live/widget.

## 13. Сверка документов и публикация checkpoint — 2026-10-03

Владелец разрешил commit/push после сверки. Baseline HEAD 36105d7 плюс
проверенный WIP §10.6–12. DOC baseline: `%TEMP%/d2-publish-doc-baseline-pjbvxo_h`.
Allowlist сверки: Marketing, Acceptance, Checkpoint Ledger, Delivery Roadmap,
Interface Task, Product Decisions, Target Contract. Изменены только текущие
статусы и согласованное правило отмены; runtime не менялся. Старые результаты
проверок не заменяются обещанием общего PASS. Foreign data/ и SIM0 не включать.
Независимый DOC review нашёл stale header этой карточки; исправлен, направлен
на focused recheck. Commit включает 26 файлов D2-119/120/§12 и документации;
файл врача после отмены пользовательского эксперимента чистый и не включён.
Independent DOC focused recheck: PASS; stale header исправлен, P0/P1 нет.
109 локальных ссылок существуют; Target §3 не изменён; diff --check чист.
Runtime/provider проверки повторно не запускались, ранее записанные ограничения
и результаты §10.7–12 сохраняются. Публикация остаётся scoped checkpoint.

## 14. Защита публичного demo и явная новая беседа — 2026-10-06

Техническое дополнение allowlist: `tests/test_d2_diagnostics.py` и
`tests/test_d2_no_legacy_path.py`. Передача admission/peer_ip требует обновить
test constructor и два точных source assertions; прежние проверки диагностики
и запрета legacy остаются. Продуктовый scope не расширяется.

Owner GO: реализовать три обсуждённых пункта, затем остановиться с отчётом
для Cursor. Лимит выбран владельцем: 200 модельных попыток за 24 часа;
10 на SID; существующая IP-настройка 40/60 секунд. Запись оставить demo_stub.
Визуальные изменения и финальная проверка диалогов — следующие отдельные шаги.
Тип: технические bug fixes/защита расходов, не архитектурное упрощение.
§3, понимание вопроса, цены, UI authenticity, medical и lead/privacy сохраняются.

Root/Git top C:/Cursor Projects/artgents-bot-active, ветка codex/d2-stage1-contract.
HEAD 4d4b0276d83208f2043f31f6af31be35b4d496ae; main/merge-base
141ce91fb1731cd990fcf8391550150016c73e7f. Baseline — текущий HEAD плюс
5-file SIM-4 acceptance WIP; затрагиваемые старые файлы сохранены в
%TEMP%/d2-demo-limits-baseline-0qudrdhf. Staging пуст.
Foreign data/ и SIM0 не читать/не менять. SIM4 WIP сохранить.

Exact allowlist:
- app.py;
- core/d2_http_adapter.py;
- core/d2_live_provider.py;
- core/d2_demo_limits.py (новый);
- static/widget/api.js;
- static/widget/widget.js;
- tests/test_d2_http_contract.py (factory принимает optional admission);
- tests/test_d2_diagnostics.py (factory передаёт admission);
- tests/test_d2_no_legacy_path.py (точные вызовы adapter с peer_ip);
- tests/test_d2_demo_limits.py (новый);
- tests/js/d2_error_copy.mjs;
- docs/tasks/DEMO_D2_INTERFACE_TASK.md;
- docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md;
- docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md.

Astra: одна техническая таблица в существующем SQLite demo, атомарная проверка
всех квот перед transport, commit до network. Считаются допущенные попытки,
включая ошибки provider; повтор готового ответа и клики без модели не считаются.
Квоты не добавляются в dialogue schema/контекст/receipt. HTTP429 или SSE error,
без успешного completion; существующий rollback сохраняет lead и освобождает
reservation. Другие tenant не подключаются к quota callback.

IP берётся из захваченного remote_addr до SSE; forwarded header не считается
доверенным. За прокси это может быть один адрес для нескольких посетителей:
проверить trusted proxy настройку отдельно до публикации; не называть это
доказанной идентификацией публичного IP. Дневной предел скользящий за24часа,
IP окно скользящее, SID лимит сохраняется при рестарте процесса.
Предел общий для процессов с одним SQLite-файлом demo; раздельные копии БД
не образуют общий счётчик. Это ограничение числа попыток, не точной суммы/токенов.

После ошибки demo показывает кнопку, вызывающую существующий resetSession
только по клику. Старые server rows/заявка не удаляются и не восстанавливаются.
Лимит IP/суток новым SID не сбрасывается. Это новый разговор, не отмена заявки.
Демо dispatcher/lead text/доставка остаются прежними по прямому указанию владельца.

Проверки одним адресным offline checkpoint: admission реального HTTP provider
со stub transport, JSON/SSE,11-я попытка, daily/IP, replay/free clicks, ошибки,
другой tenant, persisted counters и конкурентный остаток квоты. JS error copy
без автоповтора. Browser/live не запускать без бюджета. Один независимый Checker.
Commit/push/merge/deploy не входят. После отчёта — Cursor; затем визуал,
затем финальный checklist/public demo проверка.

### 14.1. Результат реализации и offline evidence

Добавлены одна техническая таблица attempts и admission callback непосредственно
перед transport существующего D2HttpProvider. В HTTP/SSE добавлена передача peer
и публикация quota error; в клиенте — понятный текст и ручная «Новая беседа».
Удалённых semantic dependencies нет: это bug fix/техническая защита, не SIM.
Новые классификаторы, model calls, dialogue поля, patient memory, auto recovery
не добавлены. Demo lead dispatcher, receipt и тексты не менялись.

Executor: 48 PASS/94.94s (9 quota + D2-119/120 и lead cancel), artifacts
%TEMP%/d2-interface-offline-__2jjas8/results.xml. Дополнительные 3 quota cases
PASS/8.43s, ssjhdaw9: истечение rolling daily/IP; named lead при quota denial
сохраняется целиком, новый SID не наследует имя. Всего 51 PASS в этих наборах.
JS d2_error_copy: PASS (JSON/SSE, no retry, сохранение прежнего UI).

Diagnostics/direct-D2 compatibility: 28 PASS/11 FAIL/46.36s, mh00wnny.
Чистый exported HEAD 4d4b027: те же 28 PASS/11 FAIL/49.36s, gqhn37bi,
baseline root %TEMP%/d2-demo-clean-baseline-fb1swnao. Failures по тем же IDs:
старые fixtures/parse и request_understanding; не исправляются этим scope.
Проверки не ослаблялись; весь CI зелёным не объявляется.

Реальный browser/new-chat click и live качество не проверены; модельный transport
во всех прогонах offline stub, network blocked. Calls provider/live/SMTP:0.
Старый SID и server lead rows не удаляются; новый разговор начинается только
по клику и не сбрасывает daily/IP. Прежний разговор можно продолжить, если его
schema совместима и квоты допускают новый модельный вызов. Несовместимая schema
остаётся ошибкой прежнего валидатора; новый recovery/migration не вводится.

Branch/HEAD прежние; staging пуст; commit/push/PR/merge/deploy нет.
5-file SIM4 WIP, foreign data/ и SIM0 сохранены. Independent Checker: PASS,
P0/P1 нет. Независимые 12 уникальных cases PASS:9/16.74s (9m01b_zr) и
3/7.68s (vd1cfm2e); JS PASS. Checker сверил XML: те же 11 baseline failure IDs.
Фактический admission/rollback/manual reset и границы §3 подтверждены чтением
call path. Реальный DOM click/live widget не аттестованы. Результаты executor
и Checker не суммируются. Node syntax и diff --check чистые.
Cursor review: PASS, P0/P1 нет. Независимый прогон12 PASS/21.42s,
%TEMP%/d2-interface-offline-jkbkakgi; JS PASS; provider/live/SMTP:0.
Снимок baseline Cursor прочитать не смог; SIM4 WIP отделён по diff, не побайтово.
P2: tests/test_d2_full_audit.py factory не принимала новый admission keyword.
Для focused исправления объявлено расширение allowlist ровно этим test файлом,
Interface Task и Ledger; baseline/ветка прежние, runtime не меняется.
Factory передаёт kwargs в реальный D2HttpProvider, не обходит admission.
Focused full-audit прогон:12 PASS/10 FAIL/14.96s (accrzrk9); чистый HEAD:
12 PASS/те же10 FAIL/16.07s (624a6mm5). Ошибка constructor исправлена,
прежние ошибки fixtures/assertions остаются; full-audit PASS не заявляется.
Проверки/fixtures не ослаблялись, live/provider/SMTP:0, commit/push нет.
Далее визуал и финальная widget приёмка — отдельные шаги.

## 15. Итоговый demo audit: policy CTA и brand details — 2026-10-06

Owner GO после read-only Astra: исправить запрет записи после детского отказа
и передачу brand в существующий подбор деталей, затем Cursor и widget.
Тип: два bug fixes, не архитектурное упрощение. Sole owners — Target§3:
clinic_policy_resolver решает разрешение записи, price owner выбирает offers.
Read-only аудит нашёл статически достижимые P1/P2, новые live случаи не заявлялись.
Medical UI во время lead pause, «Позвонить», hard-crash recovery, визуал,
админка/KB cleanup/SIM5/общий REC5 не входят в реализацию этого checkpoint.

Root/Git C:/Cursor Projects/artgents-bot-active; codex/d2-stage1-contract,
HEAD4d4b0276d83208f2043f31f6af31be35b4d496ae, main/mergebase141ce91fb1731cd990fcf8391550150016c73e7f.
Baseline текущий WIP§14 и SIM4 плюс HEAD. Staging пуст. Foreign data/ и SIM0
не читать/менять; остальные изменения сохранять. Snapshot трёх runtime файлов:
%TEMP%/d2-demo-audit-fix-baseline-20261006.
Exact allowlist: core/d2_dialogue.py, core/response_plan_materialization.py,
core/clinic_policy_resolver.py, tests/test_d2_demo_audit_fixes.py (новый),
этот Interface Task, DEMO_D2_DELIVERY_ROADMAP.md, DEMO_D2_CHECKPOINT_LEDGER.md.
Необходимое техническое расширение allowlist: contracts/response_plan.py,
только существующий whitelist failure_reason price_detail. Пустой выбор после
brand filter должен публиковать согласованный gap; существующие d2_no_price_candidates
и d2_no_scope_price_candidates разрешаются без новых полей/состояний/schema version.

Policy: существующий suppress_forbidden_booking_cta не теряется между policy
owner и final UI; он передаётся локальным аргументом функции, не новым полем
model/state/schema/wire. Source/directory/global и textual CTA подчиняются
одному готовому запрету до final render/freeze. Для применённого детского отказа
PolicyOperation тот же resolver выставляет тот же флаг; отсутствие ОМС само
по себе не запрещает взрослую платную консультацию. Возраст/subject classifier
не добавляется; медицинские и lead/privacy правила не заменяются.

Details: существующий _d2_price_block получает brand/известный extent. Новый
явный параметр не теряется из-за старых shown refs. Selected action сохраняет
точный показанный набор без модели; противоречащие offer ID/ordinal не подменяют
вариант. Отсутствие подходящих offers публикует явный пробел в существующем
failure block, не заимствует другой бренд и не добавляет model call/retry.

Offline: JSON/SSE полный refusal→UI→forged click→adult continuation; replay,
child policy/mixed, adult ОМС CTA, fresh Nobel detail/смена бренда после цены,
детали без бренда и verified click, gap и conflicting selector; saved offers
и следующий input. Один независимый focused Checker, затем Cursor.
Live/provider/SMTP, commit/push/merge/deploy не разрешены; runtime/tests verdict
до фактических результатов не объявляется.

### 15.1. Результат и доказательства

Устранены потеря computed запрета CTA и потеря brand/extent при прямом detail.
Добавлены только локальная передача существующего policy флага, разрешение
existing price-gap reasons для detail unavailable и адресные dialogue tests.
Selected UI action остаётся owner показанного набора; обычный brand request
использует canonical brand ID из каталога (Nobel = nobel_biocare).
Новые функции-классификаторы, поля model/state/wire, patient память, model calls
и retry не добавлены. История/completion/replay и server lead сохранены.

Красное воспроизведение двух исходных дефектов на чистом HEAD:
2 FAIL/4.39s, %TEMP%/d2-interface-offline-b6d1gj8u/results.xml. Новый detail
возвращал3бренда; child refusal имел default_consult CTA. Исходный fake output
имел правильные age/brand; проблема исполнения, не промпта или live provider.
Первый прогон новых fixtures ошибочно использовал alias nobel вместо canonical
nobel_biocare; исправлены tests. Temporary pack для отсутствующих данных
остаётся валидным; реальный pack не меняется.

Executor coherent checkpoint:60 PASS/105.84s,8717warnings,
%TEMP%/d2-interface-offline-dic2tpmj/results.xml (20 new +D2-119/120+policy).
После запуска уточнён forged-click ref до фактического button:default_consult;
runtime не менялся, окончательную версию новых20cases проверяет Checker.
Staging пуст; branch/HEAD прежние; previous WIP и foreigndata/SIM0 сохранены.
Полный CI и старые diagnostics/full-audit debt не закрываются. Live/widget
качество не проверено; provider/live/SMTP/network0. Commit/push/merge/deploy нет.
Дополнительно extent applicability:2 PASS/4.26s e5u9ev54/results.xml,
full_arch Nobel и one_tooth без подходящего offer. Новых cases теперь22.
Independent Checker:PASS bug-fix§15, P0/P1 нет. Независимые22 уникальных cases:
20 PASS/43.32s o2bhrwwj +2 PASS/4.03s r6etvt5b. Focused6child cases с фактическим
default_consult ref:PASS/14.99s ahi2taso, повтор не прибавляется к уникальным.
Проверены owners/call path, сохранение adult/ОМС CTA, brand/extent/gap,
strict selector и frozen click/replay без provider. Cursor и owner widget
acceptance остаются; PASS относится только к bug fixes, не закрывает весь REC5.

## 16. Передача явно заданных параметров моделью — 2026-10-06

Owner GO после live/widget наблюдения: уточнить существующий D2 prompt одним
общим правилом и нейтральным структурным примером detail с брендом. Только
prompt bug fix, не архитектурное упрощение. Target§3: понимание реплики остаётся
у единственного existing model call; сервер выполняет полученные параметры.
§15 Cursor PASS22/43.68s shf_m7eo подтверждает исполнение правильного payload,
не надёжность извлечения бренда живой моделью. Последние widget trace8219c3a/
e009f213: свежий Nobel вопрос, price_detail безbrand_id, сервер показал3offers.
Raw модельного понимания нельзя исправлять серверным поиском слов/вторым вызовом.

Root/Git C:/Cursor Projects/artgents-bot-active, codex/d2-stage1-contract,
HEAD4d4b0276d83208f2043f31f6af31be35b4d496ae; main/mergebase141ce91fb1731cd990fcf8391550150016c73e7f.
BaselineHEAD плюс прежние SIM4/§14/§15 WIP. Staging пуст; всё вне allowlist
сохранить, foreigndata/иSIM0 не читать/менять.
Exact allowlist: core/one_call_prompt_contract.py, этот Interface Task,
DEMO_D2_DELIVERY_ROADMAP.md, DEMO_D2_CHECKPOINT_LEDGER.md.
После finding Checker allowlist адресно расширен tests/test_d2_sim2_contract.py:
существующий helper ожидал пять примеров; обновлены количество/индексы и
placeholder-подстановка шестого примера, сохранены прежние проверки parser.

Заменить общее brand правило формулировкой обязательного сохранения явно
заданного ограничения услуги в существующих typed fields price/detail/content.
Это применяется к составу, этапам, свежему вопросу и продолжению всех tenant.
Один пример с placeholders service/brand, без Nobel/All-on-4/особой фразы.
Сохраняются unknownbrandlowercase и отсутствие параметра, если его не задали;
упоминание бренда при сравнении не превращается в выбор. Контекст применяется
только для ясного продолжения; явный новый бренд заменяет предыдущий, не
переносится в несвязанную услугу. Schema/required/null, provider settings,
серверные handlers/memory и число вызовов не меняются. Prompt version39.

Offline проверить достижение current instructions в production prompt и
соседние clarification/known-action/admin cases. Не писать mirror-тест текста.
Независимый scoped Checker, затем live owner widget: fresh brand, состав,
смена бренда, переформулировки, без бренда и другая услуга. Offline PASS не
закрывает brand extraction; provider calls агента0, новый live-budget не дан.
Commit/push/merge/deploy и прочие SIM stages не входят.

Executor §16: 18 PASS /41.19s, y9vm5dbg/results.xml, изолированный offline
runner с заблокированной сетью. Clarification module, current document click
и admin clinic-contact node покрыли сборку production prompt и соседние пути.
Новый mirror-тест не добавлен. Live извлечение параметров не аттестовано.
Checker воспроизвёл новую несовместимость helper: current FAIL6==5 /2.16s
ocirb69c, clean HEAD тот же node PASS /2.80s ef4u5p3m. После исправления
executor targeted conformance/repair: 7 PASS /4.67s, 9wcu020b/results.xml.
Independent Checker: PASS prompt bug fix v39 после focused recheck;
P1 helper закрыт. Независимые 7 PASS /4.69s, 378a272v/results.xml.
Production ordinary prompt содержит v39/BRAND_CATALOG; known-task прежний.
P0/P1 нет; live extraction не аттестована. Owner передал Cursor PASS §16:
47 PASS/1 baseline FAIL, 15.67s, 8eyvfyjb (extent menu copy вне §16).
Затем owner сообщил по widget «вроде всё окей»; это наблюдение владельца,
не новый анализ raw trace и не независимая live аттестация.

## 17. Редактура кодовых цен, состава и этапов оплаты — 2026-10-06

Owner GO на таблицу формулировок в чате. Bug fix представления, не
архитектурное упрощение. Target §3: модель понимает запрос; price owner
выбирает и замораживает факты; renderer меняет только оформление.
Baseline: C:/Cursor Projects/artgents-bot-active, codex/d2-stage1-contract,
HEAD4d4b0276d83208f2043f31f6af31be35b4d496ae, origin/main/merge-base
141ce91fb1731cd990fcf8391550150016c73e7f плюс прежний SIM4/§14–16 WIP.
Staging пуст; foreign data/ и SIM0 не читать/менять.

Exact allowlist:
- core/response_text_renderer.py
- core/response_plan_materialization.py
- core/d2_snapshot_sources.py
- clients/demo/target_response/d2_direction_prices.json (только introduction_text)
- docs/tasks/DEMO_D2_INTERFACE_TASK.md
- docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md
- docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md
- tests/test_d2_price_copy.py (проверка фактов и объединения, не mirror-копия кода)
- tests/test_d2_clarification_scope_http.py
- tests/test_d2_af1a_price_task_http.py
- tests/test_d2_discussion_context_http.py
- tests/test_d2_price_guidance_http.py
- tests/test_d2_sim4_overview_http.py
- tests/test_d2_snapshot_sources.py
- tests/test_d2_price_details_http.py
- tests/test_d2_rec4_price_ui_http.py
- tests/test_d2_demo_audit_fixes.py (только expectations изменённого detail gap)

Один заголовок варианта/услуги; естественные подписи общего состава и
различий; исключения означают «не входят в стоимость», не автоматически
«оплачиваются отдельно». Этапы и условия сохраняют исходные сроки, суммы,
порядок и текст данных, меняются только разделители/служебные фразы.
Fixed/from/range/no_public_price, offers, UI IDs/labels, CTA, lead/privacy,
medical policy, replay и next-turn projection не меняются. Нет смыслового
удаления условий, новой памяти, классификатора или model call.
Вводные demo сокращаются с сохранением зависимости цены от объёма/протокола,
разного состава/способов и уточнения подходящего варианта на консультации.
Сам состав, специальные условия и authored no_public_price не переписывать.
Пропорциональный offline набор + один scoped Checker. Live/provider/SMTP0;
commit/push/merge/deploy и закрытие SIM4/5/REC5 не входят.

Результат §17: убраны повторные заголовки и разделители «;» в price/detail
подаче. Общий/частично общий состав и разные exclusions остаются различимы.
Добавлены только редакторские подписи и 16 адресных presentation cases
(8 formatter invariants, 4 price modes, 4 JSON/SSE click/replay).
Новых model calls/полей schema/state/решений о цене нет; UI labels и refs прежние.
Executor: 82 PASS/5 FAIL, 135.85s moz7_83i/results.xml; затем новые 4 mode
cases PASS/1.83s st61nm01/results.xml. Пять FAIL старого test_d2_price_modes
на clean HEAD те же: 5 FAIL/2.43s y_x040ua, content_realization extra_forbidden
до materializer/renderer. Этот старый fixture не мигрировался и не скрывался.
Independent Checker: 12 PASS/8.92s 99_z7tq9, focused4 PASS/1.61s t12_sog9;
повторы не суммировать. Own baseline/current XML mode failures совпали.
Финальный Independent Checker PASS §17, P0/P1 нет. Прочитаны финальные
документы и все 17 файлов allowlist; старый completion replay возвращает
сохранённый текст, не переоформляет receipt. diff --check чист;
provider/live/SMTP0; staging пуст, commit/push/merge/deploy нет.
Foreign data/SIM0 и прежний WIP сохранены; widget/Cursor §17 pending.

### Owner widget findings и публикация checkpoint — 2026-10-06

Owner показал три price-overview ответа. Widget §17 НЕ принят: сервер
создаёт indented продолжения price list, а widget answer_format.js выводит
их отдельными p. В removable_dentures повторяется один смысл из package.label
и required_conditions_metadata с разным регистром/точкой; exact dedup не
объединяет их. Это presentation defect последней правки плюс прежний authored
дубль, не ошибка модельной прозы. Общие вводные/unknown extent тоже требуют
редакторской приёмки. Данные и UI сейчас не исправлялись.

Owner GO: commit/push накопленного checkpoint SIM4/§14–17. Сохранить факты
offline/Checker PASS отдельно от отрицательной widget приёмки. Состав:
все уже изменённые tracked файлы этих работ плюс core/d2_demo_limits.py,
tests/test_d2_demo_limits.py, tests/test_d2_demo_audit_fixes.py,
tests/test_d2_price_copy.py. Exact staged names проверить до commit; foreign
data/ и SIM0 исключены. Дополнительный allowlist документации этой фиксации:
этот Task, Roadmap, Ledger, Current Status. Нового runtime здесь нет.
Merge/deploy, исправление widget defects и live experiment не разрешены этим GO.
Обсуждён следующий отдельный тест готовых frozen structured facts моделью;
скрипт/модель/call budget ещё не выбраны и тест не запускался.

## 18. Явные дубли в demo price data перед экспериментом — 2026-10-06

Owner GO: убрать очевидные повторные формулировки из структурированных
данных перед отдельным model test. Data bug fix, не simplification/schema
change. Runtime, подбор, model/UI/lead и финансовые значения не менять.
Root C:/Cursor Projects/artgents-bot-active, codex/d2-stage1-contract,
HEAD e19fd5ebac42c1d6846adf8072e7124a597d1ebc, main/mergebase
141ce91fb1731cd990fcf8391550150016c73e7f. Staging пуст; foreign data/ и SIM0
сохранить. Цена остаётся у прежнего owner Target §3.

Exact allowlist: следующие файлы под clients/demo/target_response/pricebook/services/:
- all_on_4.jaw.implantium.json
- all_on_4.jaw.impro.json
- all_on_4.jaw.nobel.json
- all_on_6.jaw.implantium.json
- all_on_6.jaw.impro.json
- all_on_6.jaw.nobel.json
- classic.one_tooth.implantium.json
- classic.one_tooth.impro.json
- classic.one_tooth.nobel.json
- removable_dentures.jaw.full.json
- removable_dentures.jaw.partial.json
- sinus_lift.one_site.closed.json
- sinus_lift.one_site.open.json
- implant_supported_prosthetics.default.json
И docs/tasks/DEMO_D2_INTERFACE_TASK.md, DEMO_D2_DELIVERY_ROADMAP.md,
DEMO_D2_CHECKPOINT_LEDGER.md, DEMO_D2_CURRENT_STATUS.md.

Из package.label удаляется только повторное условие, уже полностью
представленное в required_conditions_metadata. Для implant-supported цена
за постоянную коронку на установленном импланте сохраняется, полное условие
с хирургической установкой И КТ остаётся. Никакой runtime нормализации/regex.
Includes/excludes остаются структурированными деталями состава, это намеренные
представления для разных задач, не удалять их как повторы price caveat.
One_stage: фразы о «по показаниям» не полностью эквивалентны; не унифицировать
их под видом чистки. Суммы/modes/units/IDs/conditions/стадии/сроки/рассрочки
не меняются. Schema та же, новый эксперимент ещё не создаётся/не запускается.

Verification: сравнить все поля 33 demo offers с HEAD, разрешить только
14 label-изменений, проверить сохранность удалённых условий в mandatory
metadata и загрузку bundle/snapshot. Адресные existing price guidance,
JSON/SSE details/replay и независимый scoped Checker. Live/provider/SMTP0.
Commit/push этой новой правки не входят в текущий GO; прошлый checkpoint pushed.

Executor §18: 52 PASS/63.28s, h5zp3brp/results.xml, offline runner с
блокировкой сети и временными tenant/SQLite/logs. Price guidance36 +price copy16
проверили условия/units/бренды/объёмы, JSON/SSE click/replay и frozen metadata.
Сравнение всех 33 JSON с HEAD и загрузка snapshot/bundle/model_view: PASS;
вне 14 package.label отличий нет. Runtime/tests не редактировались.
diff --check чист; provider/live/SMTP0, staging пуст, commit/push нет.
Independent Checker: PASS, P0/P1 нет; известный widget line-break остаётся открытым.
Независимые 16 price-copy cases: PASS/8.71s kaokna0z. Checker сверил все 33
JSON и фактический _d2_brief_price_conditions/model_view: caveats сохранены.
Изменение файлов меняет tenant fingerprint. Новый ход прежнего SID может
получить существующий d2_experiment_tenant_changed; replay старого receipt
возвращает сохранённое. Lead rows не удаляются. Для проверки обновлённых данных
использовать «Новую беседу»; migration/recovery не добавлять.

## §19. Изолированный эксперимент модельного ценового текста — owner GO 2026-10-06

Классификация: эксперимент, не упрощение и не замена runtime. Владелец разрешил
до 8 живых попыток на текущей модели бота; ошибки входят в лимит, повторов нет.
Baseline e19fd5e плюс сохранённый §18 WIP. Allowlist этого эксперимента:
scripts/experiment_d2_price_prose.py и этот документ. Артефакты — отдельная
временная папка; HTTP, widget, lead и данные клиники не редактируются.
Foreign data/ и DEMO_D2_SIM0_TASK.md сохраняются.

Восемь вопросов: обзоры implantation/prosthetics/restoration, All-on-4 Nobel,
его состав и этапы оплаты текстовыми продолжениями, рассрочка, три зуба classic.
Понимание задаётся fixture; подбор предложений, frozen plan и контекст создаются
существующим run_d2_dialogue_turn в отдельном SQLite. FullContext и план одной
клиники; предыдущие ответы в истории кодовые. Финансовую реализацию в этом
эксперименте пишет модель по выбранным данным: это явное отличие от §3/T3.
Никакой смены владельца в действующем runtime эксперимент не разрешает.
Та же config.DEFAULT_LLM_MODEL, llm.chat_completions_create, temperature0,
max_completion_tokens1024, штатный timeout/Qwen thinking policy, SDK retries0.
Prompt экспериментальный prose-only, не обычный контракт v39.
Полные ответы без редакции сравниваются с renderer; входы и usage сохраняются.
Нет исправления текста, второго verifier, fallback или новых transport retries.
Офлайн подготовка 8/8 прошла; live результаты и независимый review ниже.

Live: 8 попыток, 8 ответов, errors0, retries0, все observed_model=qwen3.8-flash,
finish_reason=stop. Всего 309406 токенов (FullContext отправлялся каждый раз).
Артефакты: %TEMP%/d2-price-prose-wphqopp8/comparison.html, comparison.md,
records.json. Исходные ответы модели не редактировались; runtime не изменён.
В прочитанных примерах выбранные offers/бренды, суммы и базовые оговорки сохранены;
три зуба не превращены в расчёт 3×unit. Это ручное наблюдение восьми примеров,
не гарантия финансовой корректности всех возможных ответов.
Ограничения: модель копирует часть готовых вводных из frozen plan, в обзоре
restoration остаётся смысловой повтор про стоимость; этапы оплаты звучат длиннее
и официальнее. All-on-4 дополнен консультацией из базы, рассрочка — известными
ограничениями из FullContext (кариес/удаление); это не выдуманные цены, но выход
за краткую кодовую формулировку. Модельный CTA обратного звонка не проверяет UI.
Для принятия будущего решения нужно обсудить границу полезных дополнений и
подачу выбранных данных; новую архитектуру/вызовы тест не внедряет.
В stages модель заменяет «обычно через 3–6 месяцев» на «в среднем 3–6 месяцев»
и добавляет «по факту выполнения»: суммы совпадают, но точная оговорка времени
не воспроизведена дословно. Это наблюдаемый риск свободного изложения условий,
не повод корректировать сохранённый ответ или объявлять финансовую гарантию.
Независимый Checker: PASS для метода и изоляции, P0/P1 нет. Live-артефакты
независимо не прочитаны из-за ограничений доступа к elevated Temp; показатели
8 ответов и наблюдения о тексте — executor evidence. Финансовую корректность
свободных ответов этот PASS не подтверждает. Commit/push/merge/deploy нет.

## §20. Живые контекстные диалоги — owner GO 2026-10-06

Классификация: тестовый эксперимент, не правка архитектуры. Owner разрешил
20 дополнительных живых попыток без повторения первых 8 prose cases.
Baseline e19fd5e + сохранённый §18/19 WIP. Allowlist: этот документ,
scripts/experiment_d2_context_live.py; отчёт/сырой output/SQLite в отдельной
временной папке. Foreign data/ и SIM0 не трогать. Runtime/tenant не изменять.

20 вопросов в пяти диалогах: classic (процесс/боль, срок, гарантия, врачи,
цена Impro); All-on-6 (отличие All-on-4, неприживление, верхняя челюсть/сроки,
врачи); whitening (процесс+цена, сохранность результата, чувствительность,
врачи); policy (12 лет+чистка+ОМС, взрослый38+чистка+цена, ОМС взрослому,
адрес+суббота); medical (страх лечения кариеса, текущая сильная боль/отёк/кровь,
возврат к будущему обезболиванию). Новые вопросы, no fixtures for meaning.

Обычный D2HttpProvider/build_d2_d1r_messages v39 → strict parser → materializer
→ renderer/store; модель самостоятельно понимает каждый вопрос. Память создаёт
существующая D2 completion projection, в пяти отдельных SID одного temporary
SQLite. Это действующий путь понимания/ответа, не §19 prose-only: финансовые,
policy и doctors блоки сохраняют кодовых владельцев §3. В отчёте отдельно raw
model JSON и окончательный ответ/UI. HTTP/SSE/DOM/lead delivery не аттестуются.
lead_bridge=False, session binding отсутствует, lead/contact хранилища не пишутся.

Глобальный предел20 reserve-before-provider; SDK retries0, штатный timeout,
thinking/model/transport/settings. Ошибки входят в лимит. Никакого retry,
подмены ответа, auto-reset или переписывания результата. Дальнейший вопрос
после ошибки получает последний действительно завершённый контекст.
Состояние вызовов сохраняется; повторный запуск начатой папки отвергается.
Report содержит весь опубликованный текст и raw model без редакции.

Executor results: 20 попыток и 20 raw model replies, 19 опубликованных ответов,
1 OneCallEnvelopeProtocolError. Все observed_model=qwen3.8-flash; provider
повторов нет, дополнительного prose/verifier вызова нет. Usage894917 tokens.
Артефакты %TEMP%/d2-context-live-yxxrc2y8/: answers.md (читаемый отчёт),
dialogues.md/html (все вопросы/ответы/raw/UI), records.json, state.json,
dialogue.sqlite. FullContext/context/финальный текст не редактировались.

Явные findings: №15 professional cleaning → professional_whitening/18000₽,
неверная услуга выбрана моделью; отдельного cleaning service в текущем каталоге
нет, но gap не оправдывает чужую цену. №16 policy_ids=[0] вместо string ID,
strict parser отверг, retry нет; №17 продолжил с завершённым контекстом №15.
Качество: №11 расплывчатое «надолго» и повтор про чувствительность; в материале
нет точного срока эффекта. №2 расширяет срок приживления3–6мес до полного цикла
от первого приёма; слишком широкое изложение. Никаких исправлений этих findings
в runtime/data/prompt по итогам теста не выполнялось.

Наблюдения: classic срок/гарантия/doctors/Impro связаны с предыдущей темой;
All-on-6 и whitening followups поняты; compound №10/13 разрешены несколькими
operations. №14 дети+ОМС без CTA; №15 взрослому CTA возвращён, но услуга неверна.
№19 текущая боль/отёк/кровь → admin с телефоном; №20 future caries → dialogue.
Это конкретные live примеры, не полная widget/medical/архитектурная приёмка.

Independent method review выявил guard P1: offline --output мог обнулить started
state. Исправлено общей проверкой existing state независимо от --live.
Focused offline probe: offline/live оба отвергают calls1/startedTrue и сохраняют
state побайтово, provider0. Live вопросы не повторялись; финальный counter20.
Staging пуст, diff --check чист, commit/push/merge/deploy нет. Foreign сохранён.
Независимый focused финал: PASS метода/изоляции, guard P1 закрыт. Live
observations и чтение всех 20 ответов — executor evidence; качество ответов,
архитектура и widget этим method PASS не аттестуются. Checker provider0.

## §21. Две свежие пробы ОМС/брекеты — owner GO 2026-10-06

Классификация: диагностический тест, не bug fix runtime и не упрощение.
Owner дополнительно разрешил ровно2 provider attempts: вопрос №16 дословно
без истории и новый вопрос о наличии/цене брекетов, каждый отдельный новый SID.
Allowlist: scripts/experiment_d2_oms_braces_probe.py и этот документ;
артефакты/SQLite/logs в отдельной Temp папке. Baseline e19fd5e + WIP§18–20,
foreign data/ и SIM0 сохранены. Commit/push/live runtime edits не разрешены.
Обычный D2HttpProvider v39, пустота history/source_revision0 проверяется до
вызова. Hard cap2 reserve-before-transport, SDK retries0, ошибки входят в лимит.
Нет автоматического повторного запуска, преобразования0→no_oms или fallback.
Offline отдельно проверяется Pydantic тип policy_ids: [0] не string ID.
Новые результаты не доказывают причинность history: модельный sampling/output
может отличаться; внутреннюю причину токена0 нельзя восстановить по двум пробам.
Read-only консультация GPT-6 Astra: провайдерные вызовы бота не выполняет.

Executor live: 2/2 attempts, 2 raw replies, обе observed_model=qwen3.8-flash,
finish_reason=stop, 88372 tokens. Оба результата отклонены strict parser,
transport ошибок нет; retries0, lead/SMTP0. Артефакты
%TEMP%/d2-oms-braces-probe-qpkb_wt7/answers.md, records.json, state.json,
isolated.sqlite. У обоих inputs history0 и source_revision0 проверены.

ОМС: вновь clinic_policy policy_ids=[0]. История не обязательна для воспроизведения
№16. ID no_oms есть в каталоге, prompt явно запрещает numeric positions; причина
генерации именно0 не установлена. Ошибка возникает до применения policy owner.
Обычный provider запрашивает json_object; схема результата дана в prompt,
не как отдельное принудительное ограничение всего output на стороне transport.

Брекеты: price clarification missing=service choices=[] при уже указанном target
braces, плюс content pending term. Pydantic подтверждает min2 violation в price
choices; target уже известной услуги противоречит этому запросу clarification.
Неактивность известного catalogID сама по себе не делает его неизвестной услугой.
Нельзя объяснять оба случая утратой памяти; они подтверждают нарушения разных
полей D2 контракта. Astra подтвердил read-only вывод; provider0/edits0.

Offline: №16 payload [0] отвергается типом string_type; гипотетическая замена
единственного поля на [no_oms] проходит. Это только диагностическая проба,
конвертера в runtime нет. Новые реальные payloads подтверждены offline:
OMS string_type, braces too_short(min2); дополнительные API calls0.
Независимый Checker: PASS метода/изоляции, P0/P1 нет, provider0. Live-артефакты
независимо не читались; live findings executor evidence, не quality acceptance.
Staging пуст, diff --check чист; commit/push/merge/deploy/runtime fixes нет.

## §22. Read-only аудит формирования ответов — 2026-10-06

Классификация: аудит/документация, не runtime bug fix и не упрощение.
Owner запросил комплексную проверку GPT-6 Astra и уточнил полезность при
нынешней кодовой финансовой презентации. Три read-only проверки: prompt/
contract, runtime/state/owners, demo sources. Baseline e19fd5e + WIP§18–21.
Allowlist: этот раздел и Temp report d2-full-answer-audit-20261006.md.
Runtime/prompt/данные не менялись; foreign data/ и SIM0 не читались.

Новые подтверждённые P2: multiple ready price_detail accepted→whole-turn
reject; off_topic получает default dental CTA вопреки D2-040; booking
needs_clarification ошибочно превращается в pediatric refusal; booking
early return теряет sibling operations; completion теряет inferred policy
IDs; ordinal true coerces→1. Первые пять — traced static paths, ordinal и
приём двух details — малые offline contract probes. Новый live/DOM не был.
Commercial absent-fact whole-turn отказ требует отдельного разграничения
valid gap и malformed/unauthorized input перед классификацией исправления.

Generated pending content/schema boundary — ранее согласованная §3.1,
не новая регрессия. Direct price без target проходит parser и падает позже;
предложение согласовать validation не является полномочием менять контракт.
OMS numeric0 и braces empty choices — model contract violations, strict
rejection корректен. Cleaning→whitening — wrong semantic service selection.
Уточнение №2: classic MD сам неоднозначно говорит «полное восстановление
3–6 месяцев»; прежнее объяснение только модельной выдумкой неполно.

Ordinary prompt содержит RAW MD/catalogs/policies, не полный published_terms/
offers. §19 prose experiment получает frozen plan; он проверяет изложение
выбранных фактов, не ordinary semantic selection. Общий quality PASS нет.
Provider/live/SMTP0; один малый network-blocked contracts-only offline probe
у Astra, root — read-only trace. Новых classifier/retry/adapter/memory/calls
нет. Предложения требуют согласования в существующей карте до реализации.
Report: %TEMP%/d2-full-answer-audit-20261006.md. Staging пуст; commit/push/
merge/deploy нет; прежний WIP сохранён.

## §23. Кодовые ответы и исправления исполнения — owner GO 2026-10-06

Классификация: bug fixes и presentation, не архитектурное упрощение.
Baseline checkpoint 9179cbb, branch codex/d2-stage1-contract; origin/main и
merge-base 141ce91. Root C:/Cursor Projects/artgents-bot-active. Staging пуст.
Foreign data/ и DEMO_D2_SIM0_TASK.md не читать/не изменять.
Allowlist: core/response_text_renderer.py, core/response_plan_materialization.py,
core/d2_dialogue.py, core/d2_snapshot_sources.py, core/d2_lead_bridge.py,
contracts/d2_dialogue_result.py, tests/test_d2_price_copy.py,
tests/test_d2_code_answer_fixes.py, этот документ, DEMO_D2_CURRENT_STATUS.md,
DEMO_D2_DELIVERY_ROADMAP.md, DEMO_D2_CHECKPOINT_LEDGER.md в docs/tasks/.

Owner: сохранить кодовые цены, улучшить компоновку/повторы и исправить
выявленные runtime defects существующими owners §3. Model prose не фильтровать;
новых полей/состояний/вызовов/классификаторов/адаптеров не добавлять.
Суммы, единицы, условия, medical/tenant/UI authenticity/lead privacy сохраняются.
Порядок booking+sibling относительно начала заявки не согласован: dependent
изменение раннего return не делать до отдельного решения. Multi-detail
ограничение обсудить с Astra: существующий single frozen block не даёт права
переименовать финансовую операцию в reference или завести второй owner.

Acceptance: компактные цена+единица без forced line breaks; facts/conditions
сохранены; pure off_topic без CTA; ordinal отвергает bool; completion отражает
effective policy IDs, не private text; booking clarification не публикует
несуществующий pediatric запрет. Точные tests JSON/SSE, replay и следующий
provider context с fake provider, socket block/isolated DB через runner.
Один coherent checkpoint → independent Checker; live/provider/SMTP0.

Executor: локальный checkpoint9179cbb сохранён до runtime edits (21files
§18–22), push не делался. Действительный diff: пять runtime/contract файлов,
два tests (один новый), четыре docs. d2_snapshot_sources.py не менялся.
Компоновка: frozen scope_text получает уже authored первый package clause,
остальные clauses и mandatory conditions сохранены; цена/единица вместе,
нет list continuation lines; дополнительный textual CTA при visible booking
button не печатается. Model prose не обрезается/не дедуплицируется.
Off_topic сохраняет запрет CTA текущего хода через existing suppression,
дальнейшая dental CTA возвращается. Effective policy_ids берутся из уже
готового policy resolution, price-blocked сохраняет actual blocked keys.
Lead bridge больше не придумывает pediatric key при no active booking;
existing unclear outcome просит уточнение, не начинает lead collection.
Новых fields/states/schema version/model calls/owners нет; ordinal strict.

Целевой прогон49PASS/53.93s: new tests18+copy16+HTTP+cancel.
Guidance36PASS/55.29s: темы/объёмы/единицы/продолжения. Последняя малая
punctuation правка покрывается independent final new+copy прогоном.
Старый test_d2_lead_scenarios.py 7FAIL воспроизводится на чистом9179cbb
(7FAIL/2PASS/17.40s): legacy envelope не принимается текущим D2 parser.
Multi details и booking+sibling НЕ исправлены: Astra подтвердил, что
доступные детали нельзя silently convert→reference (теряется финансовая
lineage) или объявить unavailable. Требуются решения о замене single frozen
detail несколькими и о порядке ответа/начала lead; dependent edits остановлены.
Артефакты0vh_6gg3/813k4cts/k6e6prxm в Temp; provider/live/SMTP0.

Независимый Checker: PASS bug fixes/presentation; P0/P1 нет. Final new+copy
34PASS/31.59s 0up1l3nv, latest punctuation проверена. Рекомендация расширить
booking evidence закрыта четырьмя child/OMS JSON/SSE/replay/no-lead fixtures:
executor4PASS/5.50s 2fi43peu и focused Checker4PASS/5.11s 709rnsug.
Прогон не аттестует живое понимание модели/DOM или architecture whole-bot.
Итоговый diff11files (five runtime/contract, two tests, four docs); staging
пуст; implementation commit/push/merge/deploy0; baseline checkpoint9179cbb
локально. Foreign сохранён. Dependent два пункта открыты.

## §24. Несколько деталей и ответ перед записью — owner GO 2026-10-06

Owner явно согласовал оба оставшихся пункта §23: final plan хранит несколько
price_detail вместо одного и отвечает на каждую; booking+информация сначала
публикует ответ, затем existing lead owner спрашивает имя. Классификация:
bug fixes/contract replacement, не SIM simplification. Baseline9179cbb +
проверенный WIP§23; staging пуст. Foreign data/SIM0 сохранить/не читать.
Allowlist (включая WIP§23): contracts/response_plan.py,
contracts/d2_session_context.py, contracts/d2_dialogue_result.py;
core/response_plan_materialization.py, core/response_plan_resolver.py,
core/response_text_renderer.py, core/d2_dialogue.py,
core/d2_completion_context.py, core/d2_lead_bridge.py;
scripts/experiment_d2_price_prose.py (потребитель renamed frozen field);
tests/test_d2_price_copy.py, tests/test_d2_code_answer_fixes.py,
tests/test_d2_compound_answers.py, tests/test_d2_price_details_http.py,
tests/test_d2_demo_audit_fixes.py, tests/test_d2_source_followup_http.py,
tests/test_d2_sim2_dialogues.py, tests/test_d2_sim3_completion_context.py;
четыре текущих docs/task status/roadmap/ledger/interface.

§3 owners сохраняются: model operations, price owner selection/freeze,
existing lead owner state/privacy, renderer display, completion memory.
Удаляются singular frozen slot и multiple_unsupported, не появляются
reference adapters для финансовых details. Scalar detail_aspect в projection
заменяется ordered aspects. Mixed booking early return удаляется; lead owner
вызывается после materialization, его prompt/result добавляется в конец.
Один provider call, verified detail clicks остаются без модели.

Acceptance: JSON/SSE compound includes+stages и price+details, per-part missing
данные сохраняют siblings; бренды/offer selectors/tenant ownership строги;
replay прежнего request без повторной модели; следующий input содержит все
показанные refs/aspects, mixed service не создаёт произвольный focus/UI.
Info+booking (оба исходных порядка), blocked child/OMS, failure до lead
mutation, следующий name/phone intake — existing owner. Offline isolated DB,
socket block, provider/live/SMTP0. Astra consultation read-only подтвердил
схему; не Checker PASS. Strict frozen rename может отвергнуть old local
receipt; DB/lead rows не удалять, recovery/migration/adapter не добавлять.

Executor §24: singular d2_price_detail_block и detail_aspect удалены, plural
collection проходит все frozen consumers; multiple_unsupported удалён. Каждый
part materialized отдельно, recoverable missing data сохраняют остальные.
Offer refs union/dedup в completion; разные наборы не получают произвольных
detail actions. Mixed booking materializes siblings до lead mutation, existing
lead result последний; rollback при failed completion проверяется.
Executor90PASS/123.66s (_yjedewx). Старые price_details_http18FAIL/3PASS
воспроизведены на clean9179cbb/21.47s (owiluild), legacy envelope baseline.
Independent Checker19PASS/27.39s, REJECT P1: addons после name prompt.
Исправлено: closing clinic reference/clarification после всех answer addons;
JSON/SSE price+booking с nonempty promo/packages добавлены. Focused recheck
PASS10/12.88s xcv1ucp7: исходный P1 закрыт. Финальный executor
48PASS/75.92s uxsljsme (compound21 + source_followup27). Provider/live/SMTP0;
no commit/push/merge/deploy, staging пуст.
Old receipt strict rejection и неизменность raw payload/state проверены;
никакого migration/reset/recovery. Lead/privacy rows не удаляются.

Owner widget smoke §24 — 2026-10-06: после предложенных сценариев владелец
сообщил «Вроде ок» и разрешил commit/push §23–24. Это owner smoke, не
полная REC-5/live quality аттестация. Далее — внешний вид виджета без
изменения архитектуры ответов. Foreign data/SIM0 в checkpoint не включать.

## §25. Volume chips — owner GO 2026-10-06

Presentation bug fix, не architecture simplification. Root
C:/Cursor Projects/artgents-bot-active; branch codex/d2-stage1-contract;
baseline db332cda882c6069d1e2fff2ba01d9430f828d19; origin/main и merge-base
141ce91fb1731cd990fcf8391550150016c73e7f. Foreign data/SIM0 не читать/не менять.
Allowlist: static/widget/widget.js, static/widget/widget.css, этот документ.
Существующие volume:* quick replies получают clinic-msg__volume-chip;
контейнер flex-wrap с gap8px. Ширина по тексту, высота минимум44px,
transparent background, radius999px и outline border1px. Стрелки у chips
не выводятся. Theme action color и focus-ring сохранены. Остальные replies
и CTA не меняются; click/ref/ui_revision/visibility работают прежним путём.
Новых contracts/state/provider calls нет. node --check и diff --check PASS.
Independent Checker PASS: CSS scope и unchanged click/ref/ui_revision
подтверждены. Real widget layout пока не аттестован.
Commit/push этой presentation правки не выполнялись.

## §26. Flat primary palette — owner GO 2026-10-06

Presentation only; baseline db332cd + uncommitted §25 volume chips.
Allowlist: static/widget/widget.js, static/widget/widget.css,
clients/demo/brand.yaml, static/widget-test.html, этот документ. Foreign data/SIM0 сохранить.
Owner: убрать24/7 badge, translucent/blur header, button gradients;
demo primary #0C2FE0 для buttons/outlines/link arrows; user bubble
#F3F4F6 одинаковый для всех clinics. Primary brand применяется к action,
hover вычисляется прежним helper. Gradient assembly/button1/button2 vars
и badge DOM/CSS удалены; sticky header остаётся opaque white без blur.
Demo brand pack теперь один brand key. Старые palette fields других
клиник не редактировались. Reply handlers/backend/answer contracts не менялись.
node --check и diff --check PASS; independent Checker PASS §26,
blocking findings0. Browser подтвердил
white header/no badge; работающий server отдаёт cached purple tenant theme,
нужен restart для нового demo brand. Provider calls0.

§26 correction: screenshot расследование выявило отдельный inline theme
в static/widget-test.html, переданный прямо mountWidget без brand.yaml.
Старый purple не был server cache: первоначальное объяснение неверно.
Тестовый theme заменён одним brand #0C2FE0; obsolete gradient fields удалены.
Для test page достаточно reload; API embed читает brand.yaml отдельно.

§26 visual continuation: owner requested thin right arrow with shaft
instead of chevron, currentColor (client primary). Allowlist unchanged
widget.js/widget.css/task. Existing reply click handlers unchanged; volume
chips stay icon-free. SVG24x24 with1.5pxstroke; no model/provider calls.

§26 owner continuation: arrow reduced18px, compact arrowhead; welcome
logo DOM/helper/SVG/CSS removed, welcome text left aligned. Config/backend
logo fields not changed. No provider calls or answer-contract changes.

## §27. Waiting labels and relevant attribution — owner GO2026-10-06

Bug fix/presentation, не architecture simplification. Root
C:/Cursor Projects/artgents-bot-active; branch codex/d2-stage1-contract;
HEAD db332cd + visual WIP§25–26, origin/main и merge-base141ce91.
Foreign data/SIM0 сохранить. Allowlist current addition: contracts/response_plan.py,
core/response_plan_resolver.py, core/d2_lead_bridge.py, core/d2_dialogue.py,
core/d2_http_adapter.py, static/widget/widget.js, static/widget/widget.css,
tests/test_d2_attribution.py, tests/js/d2_attribution_waiting.mjs, этот документ.
Existing visual WIP clients/demo/brand.yaml и static/widget-test.html preserve.
Owner approved display field and cosmetic sequential searching/checking/writing.
ResolvedResponsePlan attribution_kind content/lead/plain defaultplain freezes
proven published result only; bridge owns lead label. HTTP copies field,
widget uses it for final/live UI. No model-input/schema or completion-pair
changes; no routing/policy/price/UI authorization changes. Old receipts default
plain conservatively, no migration. Astra consulted, §3 owners unchanged.
Icons: book/content, calendar/lead, message/plain; search/checkdocument/pencil
for waiting. Cosmetic timers1500/3500ms stop on result/error/reset; lead clicks
show writing directly. No extra provider calls or checks. Targeted offline
attribution/replay/context and compound regression; JS waiting timer checks.
Evidence/Checker pending. No staging/commit/push/live/SMTP.

§27 evidence: executor35PASS/50.55s d281mxnj (attribution14+compound21).
JS waiting labels/timer cancellation PASS; node syntax/diff checkPASS.
Independent Checker PASS:14PASS/21.76s td3f_m8m, routing/modelinput/replay
boundaries подтверждены. P2 commercial-fact signature omission исправлена
по уже frozen requested_fact_ids/promo_fact_ids; extra2JSON/SSE PASS/4.98s
4ploxov3; focused independent Checker PASS2/5.02s5ne5m3qu, P2 закрыт. Lead-name waiting использует последний
attribution_kind только для cosmeticwriting; JS covers. Provider/live/SMTP0.
## §28. Caddy client IP — owner GO 2026-10-06

Technical bug fix, not architecture simplification. Baseline db332cd on
codex/d2-stage1-contract, origin/main and merge-base 141ce91; existing visual
and attribution WIP preserved. Foreign data/ and SIM0 untouched.
Allowlist: app.py, deploy/production/Caddyfile, deploy/production/compose.yml,
deploy/production/README.md, tests/test_proxy_client_ip.py, this card.
Owner approved single-Caddy-hop IP correction for public demo. Compose enables
BOT_TRUST_CADDY_IP=1; ProxyFix trusts one IP hop only, all other header trust
disabled. Caddy replaces X-Forwarded-For with direct peer IP. Bot port stays
internal. Local startup ignores forwarded headers by default. Both ask routes
retain request.remote_addr and existing quota ownership; §3 owners unchanged.
No dialogue, model, quota thresholds, tenant or lead changes. Offline tests
cover separate IP buckets, same IP across sessions, disabled trust, JSON/SSE.
Evidence: executor 19 PASS / 32.01s (proxy7 + demo-quota12), isolated runner
artifacts %TEMP%/d2-interface-offline-3_j9tmym. Independent Checker functional
PASS, proxy7 PASS / 11.61s, s51zo7pf. Diff check clean after line-ending
correction. Real Caddy / external deployment not tested; no local Caddy binary.
No live/provider calls, staging, commit, push or deploy.

## §29. Demo greeting and checkpoint — owner GO 2026-10-06

Presentation/content only. Owner-provided greeting copied verbatim into
clients/demo/widget_config.json and static/widget-test.html. Header close icon
uses existing clinic brand color. No dialogue behavior or provider changes.
Owner authorized commit/push of accumulated §25–29 changes on the existing
task branch; exact file list includes their runtime/config/docs and three new
offline test files. data/ and docs/tasks/DEMO_D2_SIM0_TASK.md remain excluded.
Prior independent PASS for §25–28 and targeted offline evidence apply; minor
greeting/color edits do not require another bot test run. External deployment
and public embed smoke remain pending. No merge/deploy authorization.
