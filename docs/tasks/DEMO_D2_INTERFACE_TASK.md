# D2 — интерфейс модели, контекст обсуждения и source UI

> **Текущий статус 2026-10-11:** владелец согласовал новую дорожную карту свободного MD-разговора и точных ценовых карточек, разрешил checkpoint commit/push и начало реализации. Действующий ближайший этап — §42 в конце этого документа. Предыдущие §1–41 описывают историю; старые STOP/GO и 9-kind кандидат не отменяют новых решений. Подготовка Demo-базы закрыта отдельно и не аттестует runtime.


Актуально: 2026-10-10. Текущий шаг — DOC-план пунктов 1–4 после независимого
аудита, §38 ниже. Правило этапа 1 согласовано; форма нового wire и изменения базы
ещё требуют указанного там согласования. Реализация, новые live calls,
merge/deploy этим DOC не разрешены.
Предыдущие разделы сохраняют историю checkpoint и действовавших разрешений.
Scoped PASS относится к проверенному checkpoint, не ко всему боту.
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

Owner GO 2026-10-10: подготовить typed ordinary/known-task provider schemas и
bounded capability script, проверить offline. Последующий owner GO разрешил
4 live calls: все schemas приняты/parser accepted, бюджет исчерпан. HTTP
был переключён на runtime json_schema strict. Allowlist, acceptance и evidence —
раздел «Строгий формат D2» в [текущей карточке](DEMO_MODEL_PRICE_EXPERIMENT.md).
Это format bug fix, не закрытие всего этапа: compound price/address в probe
вернул только price; полнота смысла и публикация карточек не аттестованы live.
Позднее owner GO paired6/layered48: rich schema strict ухудшает targeted decisions
уже без full KB. По conditional approval HTTP возвращён к json_object, final39
offline PASS/Checker focused PASS. Strict helper/types сохранены; root-array риск
открыт. Текущий результат и пределы — верхний layered раздел указанной карточки.

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
age_group операции напрямую. `situation_action` во входе lead/transport был
сохранён как lead-контракт, не patient carry; решение владельца 2026-10-07
(§30) отключает его в текущем D2. Исторический reason
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

## §30. Situation intake dormant — owner GO 2026-10-07

Architecture simplification within explicitly approved removal; §3 unchanged.
Root C:/Cursor Projects/artgents-bot-active, codex/d2-stage1-contract,
baseline 8dccb3b, fetched origin/main and merge-base 141ce91. Foreign data/
and DEMO_D2_SIM0_TASK.md untouched. Allowlist: core/d2_http_adapter.py,
core/d2_dialogue.py, core/d2_lead_bridge.py, static/widget/widget.js,
tests/test_d2_no_legacy_path.py, tests/test_d2_lead_scenarios.py,
tests/test_d2_lead_cancel_ui.py, tests/test_demo_d1r_http_offline.py,
tests/test_d2_situation_disabled.py, this card, DEMO_D2_TARGET_CONTRACT.md,
DEMO_D2_DELIVERY_ROADMAP.md. Astra consulted before edits.
Before: action/start/back or old pending flag -> pre-provider situation branch
-> note-length check -> name collection. After: unsupported action rejected
before store/provider; historical flag ignored; ordinary Q&A or existing active
lead owner handles input. Removed decision dependency: situation action/flag
cannot select a D2 route or start a lead. Sole active lead owner remains bridge;
ordinary meaning stays with existing model call. No new fields/states/calls,
fallback, migration or recovery. Fingerprint keeps its old empty fourth slot
only as encoding for ordinary replay, without situation decisions.
Removed bridge branches/types, transport/function arguments, dormant widget
listeners and obsolete executable situation scenarios. Legacy storage/helpers
remain outside D2; no migration or bulk deletion of historical data. Established
PII cleanup on ordinary lead completion/cancel remains, including old notes.
Future idea: optional voluntary description before booking; no present UI or
server producer. Reintroduction requires explicit product/UI/privacy agreement.
Acceptance: JSON/SSE reject start/back without mutation/model; stale flag alone
does not trigger intake, active slots still work, CTA authenticity/replay hold.
Executor evidence: coherent offline run 42 PASS / 4 FAIL, 81.18s,
%TEMP%/d2-interface-offline-hslq5aay. Four failures were new-test assertions:
dataclass serialization and expecting an old note to survive normal PII cleanup.
Corrected without runtime changes; focused suite 18 PASS / 24.75s,
%TEMP%/d2-interface-offline-8wv8zse7, including JSON/SSE lead pause/resume.
The other 30 targeted tests passed in the initial run. Node syntax and diffcheck
PASS; isolated runner blocks network, provider/live/SMTP calls 0.
Independent Checker §30 PASS, P0/P1 none: 18 PASS / 25.95s,
%TEMP%/d2-interface-offline-ddgkvlfg; node syntax/diffcheck PASS. Traced removal
adapter -> dialogue -> bridge/widget; ordinary leads and privacy retained.
Full CI and live widget smoke not attested. Other stale CI groups
are outside this removal; this checkpoint does not certify entire PR CI.
No commit/push/live/deploy in this checkpoint.

## §31. PR CI migration — owner GO 2026-10-07

Test/CI migration, not runtime architecture simplification. Baseline 8dccb3b,
codex/d2-stage1-contract, root C:/Cursor Projects/artgents-bot-active,
origin/main and merge-base 141ce91. Existing §30 is included unchanged.
Foreign data/ and docs/tasks/DEMO_D2_SIM0_TASK.md excluded; staging empty.
Additional exact allowlist: tests/conftest.py, tests/d2_ci_http.py,
tests/test_one_call_tenant_isolation_offline.py,
tests/test_tenant_ingress_prod_boundary_offline.py,
tests/test_session_tenant_binding_hardening_offline.py,
tests/test_tenant_lead_pending_question_offline.py,
tests/test_d2_lead_interrupt_http.py, tests/test_d2_sim2_contract.py,
tests/test_d2_ci_clinic_policy.py, tests/test_g2_pr_ci_contract.py,
.github/workflows/ci.yml, this card. Astra consulted; §3 owners unchanged.
No legacy API/envelope adapter, patient memory, worker or provider call added.

Protection mapping for retired D1 clinic suites:
- request_understanding_schema -> D2 sim2 strict contract and actual prompt.
- D1 HTTP/authority -> D2 demo audit fixes and CI clinic policy: authored clinic
  rule, child prohibition, adult/paid booking, no foreign policy, next-turn IDs.
- composition -> D2 compound answers: both details, partial failure, booking
  plus information, adverse booking outputs, transactional state protection.
- route budget -> D2 no-legacy-path + demo limits: replay/free click, no extra
  model, quota exhaustion before transport, same-SID/shared-IP/daily limits.
- patient volume scope -> D2 discussion context: service/volume without subject,
  update/current scope, unrelated topic and contacts, persisted next-turn input.
- tenant/pending HTTP -> migrated original modules: tenant corpus/contacts/prices,
  same-SID/replay, host-bound JSON/SSE, forged/stale UI, provider PII exclusion,
  pending clearing, name/phone resume and request binding/teardown.
Retired D1 modules remain historical files outside explicit CI commands;
no blanket skip/deselection. Unit/privacy/ingress/PG tests remain in CI.
Per-test D2 DB isolates completion and quota without disabling limits;
HTTP fixture also isolates tenant session DBs and forbids network/provider.
Baseline CI evidence supplied/reviewed: 31 failed/610 passed and second
136 failed/103 passed.
Executor full Offline unit and contracts module list: 670 PASS / 5 SKIP,
120.52s, %TEMP%/d2-interface-offline-mszg_2m3. Skips are unchanged Windows
symlink prerequisites in G4/G7; Linux execution is not certified locally.
Initial full migrated policy list: 253 PASS / 3 FAIL, 261.42s,
%TEMP%/d2-interface-offline-nshj2gd3. Failures were new-test no_braces YAML
assumption (2) and old shown_options_snapshot assertion (1), not runtime bugs.
Both corrected: real no_dms policy plus distinct braces service alternative;
hidden volume verified against durable UI and rejected forged click.
Independent Checker §30–31 PASS: initial 129 PASS / 2 fixture FAIL, 81.46s,
%TEMP%/d2-interface-offline-k77vy_qt; focused policy/workflow recheck
30 PASS / 16.95s, ofpu1pc2; additional hidden-volume recheck 1 PASS / 3.80s,
axrmsm8b. No new runtime change beyond §30.
Final-order policy run exposed one flaky privacy assertion: substring 999
matched timestamp microseconds, not a phone. Changed both migrated persisted
privacy assertions to reject the full canonical phone after digit normalization;
name/provider/context assertions retained. Independent focused recheck:
5 PASS / 16.54s, %TEMP%/d2-interface-offline-glk78vbv; diffcheck PASS.
Final full Offline unit and contracts list: 671 PASS / 5 unchanged Windows
symlink SKIP, 116.02s, %TEMP%/d2-interface-offline-h97ts24k.
Final full Demo D1 clinic policy regression module list: 258 PASS / 0 FAIL,
255.39s, %TEMP%/d2-interface-offline-hef2svuo. Counts are separate overlapping
workflow jobs, not summed. Both requested module lists pass locally; actual
GitHub/Linux checks have not rerun because no push was authorized.
Node syntax/diffcheck PASS; provider/live/SMTP calls 0; network blocked.
No push/merge/deploy/live authorized. Commit not requested for this checkpoint.

Final checkpoint inventory (23 files, exact; §30 + §31):
- Runtime/UI: core/d2_http_adapter.py, core/d2_dialogue.py,
  core/d2_lead_bridge.py, static/widget/widget.js.
- Docs: docs/tasks/DEMO_D2_INTERFACE_TASK.md,
  docs/tasks/DEMO_D2_TARGET_CONTRACT.md, docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md.
- CI: .github/workflows/ci.yml.
- Tests: tests/conftest.py, tests/d2_ci_http.py,
  tests/test_d2_ci_clinic_policy.py, tests/test_d2_situation_disabled.py,
  tests/test_d2_lead_cancel_ui.py, tests/test_d2_lead_interrupt_http.py,
  tests/test_d2_lead_scenarios.py, tests/test_d2_no_legacy_path.py,
  tests/test_d2_sim2_contract.py, tests/test_demo_d1r_http_offline.py,
  tests/test_g2_pr_ci_contract.py, tests/test_one_call_tenant_isolation_offline.py,
  tests/test_session_tenant_binding_hardening_offline.py,
  tests/test_tenant_ingress_prod_boundary_offline.py,
  tests/test_tenant_lead_pending_question_offline.py.
Staging remains empty, HEAD 8dccb3b; no commit/push/merge/deploy. Foreign data/
and docs/tasks/DEMO_D2_SIM0_TASK.md unchanged and excluded. Historical suites
outside the requested CI jobs are not certified green by this checkpoint.


## §32. Clinic policy route consistency — owner GO 2026-10-08

Baseline f593248, codex/d2-stage1-contract, root C:/Cursor Projects/artgents-bot-active;
origin/main cdeddc4, merge-base f593248. Existing widget-test.html/widget.css WIP
and foreign data/ and DEMO_D2_SIM0_TASK.md are outside this checkpoint.
Snapshot policy authority is architecture simplification: cached filesystem keys
plus repeated age/payment inference -> captured tenant answers + one resolver decision
-> remove cached loader and duplicate inference from all reachable D2 policy/booking paths.
Sole decision owner remains clinic_policy_resolver; §3 responsibility is unchanged.
Execution/projection fixes and prompt instruction are bug fixes, not simplification.
Exact allowlist: core/clinic_policy_resolver.py, core/d2_snapshot_sources.py,
core/d2_dialogue.py, core/d2_lead_bridge.py, core/d2_completion_context.py,
core/one_call_prompt_contract.py, core/d2_tenant_snapshot.py, tests/test_d2_policy_route_fixes.py,
this card and DEMO_D2_DELIVERY_ROADMAP.md.
Known inactive services retain their original typed ID; alternatives are not ambiguity
choices or user-selected services. Singleton clarification remains invalid.
Ambiguous insurance question uses existing clarification part + ordinary history;
no new payment axis/pending state. Explicit payment with absent clinic rule uses the
existing information gap, without silently continuing a payable price.
Completion projection retains reference identities, the fixed insurance clarification and
effective policy IDs. Captured service_alternatives IDs enter the existing model catalog;
arbitrary authored reference text stays in receipts, since it may contain money.
No full rendered financial answer, prices/details/promos or PII copied.
Pure booking refusal keeps applied policy IDs without duplicate displayed text.
Mixed child/adult booking semantics and generic expansion of policy registry are excluded.
No new fields, session schema, semantic classifier, retries, model calls or recovery.
Tests: JSON/SSE decisions/UI/replay/history, captured rules vs legacy loader, empty
registry, inactive services, strict bad outputs, payment gaps, lead/privacy boundaries.
Astra consulted before implementation. Offline-only; live quality remains unverified.
Implementation authorization initially excluded commit/push/merge/deploy/provider calls.
Owner subsequently authorized a separate §32 checkpoint commit and push; merge/deploy
and new live provider calls remain unauthorized.

§32 implementation evidence, 2026-10-08:
- Removed cached policy-key lookup from active D2 policy/price/booking calls and
  duplicate age/payment inference from the policy text producer. The historical
  understanding wrapper remains outside the active D2 route; its API was not deleted.
- Added existing resolver-result consumption, clarification part/history, explicit
  payment information-gap execution, original inactive-service identity and captured
  alternative IDs, and booking refusal policy-ID projection. No schema/state/calls added.
- New regression cases: 26 PASS across two isolated network-blocked runs (22 + 4).
  Related main run: 157 PASS / 7 FAIL, 675.68s; edge run: 4 PASS, 28.20s.
  All seven failures belong to historical D1-envelope test_d2_lead_scenarios.py;
  clean HEAD f593248 archive reproduces exactly the same seven (1 PASS / 7 FAIL).
  These tests were neither weakened nor migrated in this checkpoint.
- Artifacts under allowed visualization root: policy-route-check-6cr6u0fp,
  policy-edge-check-1qyieaxc, policy-head-baseline-ueyb_oxo (JUnit results.xml).
- Live/provider/SMTP: 0. Prompt guidance does not prove live inactive-service
  recognition; user widget acceptance remains necessary.
- Scope limitation: after prior price service A, a missing insurance rule for service B
  may retain A's discussion pointer (existing clinic-scope price_reference behavior).
  No new carry semantics introduced. Mixed child/adult booking remains excluded.
- Staging empty; HEAD f593248 unchanged. Widget HTML/CSS WIP and foreign data/,
  DEMO_D2_SIM0_TASK.md preserved. No commit/push/merge/deploy.
- Independent Checker: PASS for §32, no P0/P1. Actual call path, new tests and
  all three JUnit reports reviewed; seven legacy failures independently confirmed.
  P2 gap carry limitation remains explicit. No live/widget acceptance claimed.

§32 checkpoint limitation after full read-only Astra audit, 2026-10-08:
The narrow offline PASS is not full architecture or live acceptance. Audit reproduced
six open mechanisms: comma-prefix privacy stripping loses question meaning;
commercial applicability can reject a valid operation and cancel independent answers;
stale offer refs survive topic change; doctors CTA ignores free-consult applicability;
direct promotions can lose mandatory compatibility copy; paused lead text cancellation
does not reach its existing owner. Model schema/parser/executor mismatches and incomplete
doctors-result projection also remain open. These findings are not fixed by this commit.
The four proposed repair groups (input/lead, commercial rules, context, model contract)
are proposals, not implementation authority. No new responsibility or product rule is
introduced by recording them. Prior widget HTML/CSS and foreign WIP are excluded.

## §33. Audit group 1 — input privacy and paused cancellation, owner GO 2026-10-09

Baseline: `f9f017955aae0ea9f1b369aac545305b891d8bac`, branch
`codex/d2-stage1-contract`. Owner approved the concrete first-group plan in chat.
Allowlist: `core/user_text_privacy.py`, `core/d2_lead_bridge.py`,
`core/d2_dialogue.py`, `tests/test_user_text_privacy_contract_offline.py`,
`tests/test_d2_lead_interrupt_http.py`,
`tests/test_tenant_lead_pending_question_offline.py`, this card and Roadmap.
Foreign widget HTML/CSS, `data/` and SIM-0 remain excluded.

Classification: input-path simplification plus paused-cancellation bug fix.
Before → after → removed dependency: arbitrary comma prefixes (including `Я …`)
were structurally guessed as names and deleted before model understanding;
now only an exact bound profile name is stripped on those two paths.
The structural name-acceptance calls on both paths are removed. Explicit
`Меня зовут…` introductions and existing phone/email masking remain.
Per Contract §3, the model still owns question meaning; privacy only removes
identified contact data, without a new semantic classifier or exception words.

Paused text cancellation previously bypassed the existing lead owner; now
the tenant-bound admission gate checks the existing `parse_lead_cancel` only
for an existing paused lead, then the same owner executes `exit_lead_flow`.
Ordinary paused questions and cancel text outside a lead remain ordinary turns.
No new cancellation language, state, payload field, model call or retry.

Acceptance: complete provider-visible question meaning on fresh, pending and
paused turns; explicit-introduction/bound-name/contact privacy; cancellation
at paused name and phone slots, PII/pending cleanup, no provider/effect, replay;
ordinary paused questions retain lead state, UI authenticity and tenant isolation.
Targeted offline checks and independent Checker precede completion. No live,
commit, push, merge or deploy is authorized by this checkpoint.

§33 offline evidence, 2026-10-09: **105 passed**, 443.27s across privacy,
D2 lead interruption, cancel UI and tenant pending-question suites. The 30 new
cases cover 14 privacy cases and 16 endpoint cases; no skips or failing tests.
Only the old bare-name privacy fixture was updated to supply an actually bound
profile name; no substantive assertion was removed. The isolated runner disables
dotenv loading, blocks network and places logs/SQLite under the evidence folder.
JUnit: `C:/Users/denis/.codex/visualizations/2026/10/02/01a0fd5a-1bf9-7ed0-9738-a748f948637a/input-lead-check/results.xml`.
Existing `datetime.utcnow()` deprecation warnings remain outside scope.
Provider/live/SMTP calls: 0. No whole-CI or live/widget acceptance claimed.
Independent Checker: **PASS**, no P0/P1; read tests first, traced actual JSON/SSE
call paths, removed dependency and existing cancellation owner, and independently
read the JUnit (105 PASS / 0 FAIL / 0 SKIP). No redundant test rerun. PASS is §33
only; other audit groups, full CI and live/widget acceptance remain open.
Staging empty; HEAD remains `f9f0179`; no commit/push/merge/deploy.

§33 subsequent acceptance, 2026-10-09: owner reported widget scenarios OK;
Cursor read-only review also PASS, no P0/P1 or weakened tests. Its two P2 notes
(the same cancellation predicate evaluated twice and a second pause-flag SQLite
read) are non-blocking and do not authorize extra refactoring. Widget acceptance
is the owner's manual report; implementer made no live provider calls.
Owner then explicitly authorized a separate commit and push of these eight files.
Other audit groups and foreign WIP remain excluded; merge/deploy not authorized.

## §34. Audit group 2 — commercial applicability and final compatibility

Owner GO 2026-10-09: continue the described second-group plan, including neutral
absence-of-data response and one existing failure-reason enum extension.
Baseline `746229b3e75ecc28b5ef4596d8eeed4c35563d80`, branch
`codex/d2-stage1-contract`. Allowlist: `contracts/response_plan.py`,
`core/response_plan_materialization.py`, `core/d2_commercial_plan.py`,
`core/response_plan_fact_policy.py`, `core/d2_contacts_cta.py`,
`core/d2_directory.py`, `clients/demo/target_response/pricebook/facts.json`,
`tests/test_d2_commercial_route_fixes.py`, `tests/test_d2_directory_ui_scenarios.py`,
`tests/test_response_plan_fact_policy.py`, this card and Roadmap.
Widget HTML/CSS, `data/` and SIM-0 excluded. No live/commit/push/merge/deploy.

Classification: applicability bug fixes and compatibility-path simplification.
Before → after → removed dependency: compatibility was calculated inside
individual promo selection using an incomplete offer/promo set; now only the
final materializer's published positive fact/promo and price/detail offer IDs
are checked by the existing commercial owner. Remove the early calculation
and its offer-ID input; retain authored groups and explanations, not a new policy.
Contract §3 price/commercial owner and protections remain unchanged.

Direct self-qualified free-consult information is allowed clinic/topic-wide
using existing requested_display_policy, never as blanket service entitlement.
Free CTA uses the same existing applicability evaluator in automatic mode plus
date and resolved service scope; neutral CTA remains for unsupported scope.
Explicit installment exclusions use only authored excluded_scope_text; other
known but inapplicable/expired facts get a neutral existing-style gap rather
than an invented refusal. Unknown/foreign IDs remain strict errors.
The gap uses d2_commercial_fact_unavailable in the existing failure enum/block,
preserving sibling answers. No new model operation, memory, retry or call.

Acceptance: direct clinic/topic/service facts; excluded and unknown applicability;
expiry; doctors CTA caries/classic; direct and automatic promo combinations;
final price/detail IDs; rejected or negative facts do not trigger compatibility;
JSON/SSE/replay, tenant and UI boundaries. Targeted offline and independent Checker.

Partial commercial execution uses the existing request-part granularity: useful
approved text and positive IDs are retained, but any unavailable requested member
marks that whole commercial part unavailable. A lone such part has result failed;
with an answered sibling it has result degraded. Both remain ordinary published
responses, not transport errors. Existing exact/failure blocks must freeze identical
text, rendered once; there is no new partial status or provenance field.
Independent Checker first rejected false complete accounting; the focused repair
covers mixed available/expired facts and available fact/empty requested promotions.

§34 final targeted offline evidence, 2026-10-09: **77 passed**, 241.49s,
0 failed/errors/skipped. Suites: commercial route fixes, fact policy, D2 commercial
plan and tenant commercial contract; targeted date/scope CTA and child refusal/
forged booking checks. Forty new JSON/SSE cases plus two new pure policy cases
cover conditions, exclusions, expiry, final price/detail combinations, missing
detail provenance, partial execution, replay and next-turn projection. Earlier
new-case failures were corrected; existing selected checks passed throughout.
The runner disables dotenv, blocks network and isolates SQLite/logs. JUnit:
`C:/Users/denis/.codex/visualizations/2026/10/02/01a0fd5a-1bf9-7ed0-9738-a748f948637a/commercial-route-check/results.xml`.
Provider/live/SMTP calls: 0. Existing utcnow deprecation warnings remain.
No whole-CI or live model/widget acceptance claimed. HEAD remains `746229b`;
staging empty; no commit/push/merge/deploy. Foreign widget WIP hashes unchanged;
data/ and SIM-0 were neither read nor changed. Context/model-contract groups open.
Independent Checker focused recheck: **PASS**, sole P1 closed, no new blockers.
Checker independently read final JUnit/output and actual renderer/projection paths,
without rerunning tests. Early compatibility dependency removed; final published-ID
check remains with the commercial owner. PASS is §34 only; Cursor/widget acceptance
and whole-CI remain open. `git diff --check` clean; no staging or Git mutation.

§34 widget follow-up, owner GO: live owner runs exposed visible_fact_id_role_conflict
for free_implant_consult or implant_same_day_discount requested both directly and
through promotion_scope=general. Widget acceptance remains open; earlier scoped
PASS did not cover these combinations. Bug fix allowlist: materialization module,
commercial route tests, this card and Roadmap. Keep prior §34 and foreign WIP.
Direct approved fact publication has priority over its promo copy; other selected
promos remain. Preserve strict role uniqueness, tenant/price/medical protections,
existing request parts and absence-of-data semantics. No phrase-specific rule,
new model call, state, retry or fields. Commit/push/live not authorized.
Assembly first resolves each direct fact in its own operation scope, then assigns
promotional roles against the complete applicable direct-ID set. Role provenance
is recorded once in stable operation order; independent repeated requests may
repeat authored prose, as the owner preferred to losing an answer. An otherwise
fully covered promo request retains its approved prose without a second role ID.
Eligibility gaps are determined before deduplication; rejected/expired/negative
direct facts do not reserve a positive ID. Automatic promo filtering and final
compatibility remain unchanged. General vs service selection by the model is
not repaired by the server in this follow-up; audit group 4 remains separate.

Overlap follow-up offline evidence: **98 passed**, 378.17s, no failures/errors/skips.
Coherent run: all 68 commercial route cases (28 new overlap cases), 11 fact-policy,
4 commercial-plan and 15 tenant commercial-contract cases. Exact live output shapes
for consultation and discount are represented; both operation orders, auto promo,
repeat direct/promo requests, fully covered promo-only request, inapplicable direct,
replay, next projection and strict role-conflict rejection pass. No validator change.
Evidence: `C:/Users/denis/.codex/visualizations/2026/10/02/01a0fd5a-1bf9-7ed0-9738-a748f948637a/commercial-overlap-check/results.xml`;
runner network/dotenv/SQLite isolation unchanged. Provider/live/SMTP: 0.
Whole CI and widget acceptance still open; previous 77-case count is not added to 98.
Baseline/HEAD `746229b`, staging empty, no commit/push/merge/deploy.
Focused overlap Checker: **PASS**, no P0/P1. Independently read 98-case JUnit/output;
role guard, partial results, automatic filtering and final compatibility preserved.
No rerun or Checker edits; general/service model choice remains separate.

§34 final acceptance, 2026-10-09: owner reported widget OK after the overlap repair;
Cursor focused review PASS, no blockers/test weakening/scope creep, SAFE_TO_COMMIT=YES.
Owner then explicitly authorized commit and push of the complete 12-file §34
checkpoint, including the overlap fix. Widget HTML/CSS, data/ and SIM-0 remain
excluded. Full CI, groups 3/4 and merge/deploy are not authorized or closed here.

## §37 — single-offer price paragraph (owner GO, 2026-10-09)

Owner requested fixing detached lower-case conditions in the aligners price
answer. Classification: presentation bug fix, not architecture simplification.
Baseline HEAD6381945 plus reviewed §36 WIP. Allowlist:
`core/response_text_renderer.py`, `tests/test_d2_price_copy.py`, this card.
Preserve §36 and foreign widget/data/SIM0 work; no commit/push/live/deploy.
The existing renderer joins a single offer's name, price, billing scope and
conditions into one paragraph. Conditions become sentences with initial upper
case, preserving the remaining authored text, amount/mode/unit and order.
No model routing, selection, frozen data, multi-offer grouping, UI or task
contract changes. Natural wrapping at the widget width remains; no forced
single-line CSS, phrase-specific template or model call.
Acceptance: fixed/from/range/no-public-price retain every condition and amount;
actual JSON/SSE aligners and periodontitis responses keep scope and conditions
with their price paragraph, frozen data unchanged. Targeted offline and Checker.

§37 evidence: **8 passed**, 15.29s, 0 failures/skips; isolated offline runner,
dotenv disabled, network blocked, logs/SQLite outside repository data.
JUnit: `C:/Users/denis/.codex/visualizations/2026/10/02/01a0fd5a-1bf9-7ed0-9738-a748f948637a/price-paragraph-check/results.xml`.
Independent Checker **PASS**, no blockers; presentation bug fix only.
`git diff --check` clean, provider/live/SMTP0. HEAD6381945, staging empty;
no commit/push/merge/deploy. Prior §36 and foreign WIP preserved.

## §36 — audit group 4: ordinary contract / authorized task boundary

Owner GO 2026-10-09: proceed with the fourth agreed audit group after §35.
Baseline `6381945762102a6934df45e2a6c1ccadfed2802c`, branch
`codex/d2-stage1-contract`. Classification: architecture simplification.
Before → after → removed dependency: ordinary output/schema allowed a
server-only explanation without clarification, then the ordinary parser
rejected it → ordinary pending content requires clarification, while verified
explanation-only tasks live solely in the existing server task input → remove
the ordinary schema's dependence on internal click state and its compensating
post-checks. Sole owners remain Target Contract §3:
model owns ordinary meaning; server owns verified UI task; price owner owns sums.

Allowlist: `contracts/d2_dialogue_result.py`, `contracts/d2_dialogue.py`,
`core/d2_dialogue.py`, `core/d2_snapshot_sources.py`,
`core/one_call_envelope_protocol.py`, `core/one_call_prompt_contract.py`,
`tests/test_d2_sim2_contract.py`, `tests/test_d2_sim2_dialogues.py`,
`tests/test_d2_document_click_task_http.py`, this card, Roadmap, Checkpoint Ledger.
Foreign widget HTML/CSS, `data/` and SIM-0 excluded. No live/commit/push/merge/deploy.

The internal authorized explanation type replaces the broad result constructor;
it is not an ordinary wire variant or a persisted state. Existing task fields,
source/brand/volume/ID and explanation-only reply remain. All price types and
their late target check remain unchanged. No semantic heuristics, adapters,
retry, new wire fields,
memory or provider calls. Schema continues to come from ordinary Pydantic types.
Contract header advances to v41 solely for changed structural requirements.

Acceptance: actual sent schema and parser agree on pending clarification;
internal task cannot become ordinary output or persisted pending; authorized
reply cannot mutate task/source and never publishes seed. JSON/SSE document,
service and price/detail actions, independent siblings, replay, next context,
tenant/UI/lead/privacy and medical protections remain. Targeted offline tests
with isolated SQLite/network followed by independent Checker.

Limits: provider still requests json_object, not enforced full schema. Whitening
root-array error and second-doctor semantic mistake are not closed by this
structural change. No phrase-specific prompt patch or server semantic repair.

Scope correction before completion: requiring direct-price target is deferred.
The late target gate follows child/payment/brand policy execution, so null target
is not universally unexecutable: it can publish an authored clinic answer.
Rejecting it earlier would hide that answer. No conditional exception, inferred
target or new refusal is introduced. This unresolved price-contract aspect
needs an owner decision; this checkpoint certifies only the independent
ordinary/authorized explanation replacement, not closure of the whole group.

§36 evidence: preliminary wider selection **93 passed**, 330.64s; its code
preceded the price-scope correction, so it is not a final-tree attestation.
Final focused recheck **64 passed**, 124.89s, zero failures/skips: full SIM-2
contract suite, eight null-target child/payment/brand JSON/SSE cases, service
clarification→explanation, and document task/click/replay through JSON/SSE.
The wider selection also covered malformed task replies, UI authenticity,
price/detail/volume clicks without model, siblings and pending lead privacy.
Both runners disabled dotenv, blocked network and isolated logs/SQLite.
Final JUnit: `C:/Users/denis/.codex/visualizations/2026/10/02/01a0fd5a-1bf9-7ed0-9738-a748f948637a/contract-boundary-final/results.xml`.
No new baseline failure found in these selections; historical suites/full CI
not attested. Existing datetime.utcnow warnings out of scope. Provider/live/SMTP
0, staging empty, no commit/push/merge/deploy. Widget hashes unchanged.
Independent Checker: **PASS** for narrow §36, no blockers/test weakening;
independently read final JUnit and traced removal and preserved policy paths.
This does not close the entire group, residual price decision or live errors.

## §35 — audit group 3: completed-result context (owner GO, 2026-10-09)

Baseline: `49cf0b4d003abbba4e977e6851a2234690547835`, branch
`codex/d2-stage1-contract`, permanent root `C:/Cursor Projects/artgents-bot-active`.
origin/main `cdeddc4952254b7c8d7e96201d8fb77bf5267e73`; merge base
`c085c387b1a6ef278d6e83387082f1542759f9c1`. Staging empty at entry.
Foreign widget HTML/CSS, untracked data/ and SIM-0 preserved and excluded.

Classification: offer context is architecture simplification; preserving the
doctors result type is a bug fix. Before: discussion receipt plus separately
updated persisted offer list. After: current scope and offers read from completed
results by the existing context projection owner (§3). Remove the state field,
two helpers and both ordinary/non-price offer writers. Existing input refs remain
a derived projection, not a parallel memory. Latest published rows replace refs;
non-price results retain input refs only for the same nonempty scope. Pending,
mixed, expired and changed scopes cannot retain them. Missing price/detail does
not resurrect old offers. Price policy gaps preserve the original valid target.
Contacts retain discussion as before; no new semantic carry rules.

Doctors keep the existing operation's type through exact publication, rendering
and safe bounded history, including public names/order. General financial
reference text remains excluded. No new memory, field, classifier, retry or model
call. State schema 5→6 rejects old local sessions; owner uses New conversation.
No automatic recovery, migration or deletion of saved leads.

Exact allowlist: `contracts/d2_session_context.py`, `contracts/response_plan.py`,
`core/d2_session_context.py`, `core/d2_completion_context.py`, `core/d2_dialogue.py`,
`core/response_text_renderer.py`, `tests/d2_ci_http.py`,
`tests/test_d2_session_context.py`, `tests/test_d2_sim3_completion_context.py`,
`tests/test_d2_continuation_scenarios.py`, `tests/test_d2_sim2_dialogues.py`,
this card and `docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md`.
Tests migrate assertions to actual completion projection, preserving ownership,
money/privacy, pending, TTL, real UI and replay checks. Offline targeted checks
and independent Checker required; live/commit/push/merge/deploy not authorized.

Historical REC-4/old stage3 suites still contain superseded D1 envelopes or
patient-state expectations and are outside this checkpoint; no legacy restoration
or wholesale test migration is claimed. Current D2 assertions use the real
completion projection. Checker caught loss of scope after a targetless detail:
final publication now freezes the existing input descriptor only for resolved
rows belonging to the verified input refs, with no explicit target/volume/brand.
Explicit model parameters remain authoritative; no phrase parsing or new memory.

§35 final evidence: coherent final selection had **80 passed, 1 baseline failure**,
271.05s. The old continuation assertion expected three overview offers. Clean
tracked HEAD export reproduced the identical failure (1 failed, 11.55s), with
the existing two SIM-4 offer IDs. Assertion now checks those exact ordered IDs,
not merely a count; publication/next-input/both stored projections stay checked.
Focused final continuation recheck: **1 passed**, 11.67s. No remaining failure
in the selected checkpoint. Counts from earlier runs are not added to these.
The remaining 80 final checks cover TTL/schema, JSON/SSE contacts beyond bounded
history, same/new/ambiguous/pending scopes, explicit missing DMS policy, exact
doctors names/order and adverse shapes, missing detail exclusion, replay and
tenant/receipt ownership. Pre-existing child-price denial and absent-payment-rule
checks pass. Dependency collection: **366 collected**, 7.43s, no import errors;
collection is not execution. Existing utcnow deprecation warnings remain.

Artifacts under `C:/Users/denis/.codex/visualizations/2026/10/02/01a0fd5a-1bf9-7ed0-9738-a748f948637a/`:
`context-route-final/results.xml`, `context-continuation-recheck/results.xml`,
`context-baseline-check/results.xml`, `context-helper-collection/output.txt`.
Network/dotenv blocked; isolated SQLite/logs. Provider/live/SMTP calls: **0**.
Independent Checker: **PASS** after focused repair, no open P1/test weakening;
read actual paths and JUnit, no edits or test reruns. Original separate carrier
and both helpers/writers removed; existing guards remain. Added only derived
completion read and preserved doctors type/provenance, not prompt rules.
Saved leads untouched. Full CI, live understanding, Cursor/widget acceptance
and group 4 remain open. `git diff --check` clean. HEAD `49cf0b4`, staging empty,
no commit/push/merge/deploy. Thirteen checkpoint files; foreign widget WIP hashes
unchanged, data/ and SIM-0 preserved and excluded.

§35 checkpoint authorization, 2026-10-09: owner supplied Cursor **PASS**, no
blockers/test weakening/scope creep, SAFE_TO_WIDGET_TEST=YES, and explicitly
authorized commit/push of these 13 files. Independent Checker PASS remains
scoped to the completed-result mechanism, not live interpretation quality.
Owner widget run confirmed correct input context but exposed two open model
defects: professional_whitening → targetless includes returned an unrelated
root array and failed parsing (invalid_envelope); doctors list → second doctor
received the complete correct list/order but selected Kuznetsov (first) instead
of Orlov (second). Whitening includes data is empty, but this observed failure
occurred at parse before missing-detail execution. No new fix or provider call
was made during the read-only log investigation. Live/widget acceptance is
therefore not closed. Group 4 must address model-contract reliability and test
context use without treating schema compliance as proof of semantic correctness.
Checkpoint preserves this known debt; it does not authorize merge/deploy.
Foreign widget HTML/CSS, data/ and SIM-0 remain excluded and untouched.

## §38. План пунктов 1–4 после независимого аудита — 2026-10-10

### Статус и единственный план

Владелец поручил составить чёткий план пунктов 1–4, проверить документы и Git.
Это DOC-подготовка, не реализованное упрощение и не аттестация всего бота.
Позднейшее явное согласие владельца «с этим согласен» утверждает правило
этапа 1 ниже. Остальные конкретные изменения wire/данных не утверждаются
самой записью в карточке. Постоянная ответственность — Target Contract §3.
Подробности исполнения вести здесь; Roadmap ссылается сюда. Старые отчёты
и Model Price Experiment остаются историей и evidence, не отдельным планом.

Root/Git top: C:/Cursor Projects/artgents-bot-active; branch
codex/model-price-experiment. HEAD и GitHub branch совпали read-only ls-remote:
9bcdbe34110df273e5a3d3f05909aac967ec4bb5. origin/main, GitHub main и merge-base:
efa3f773bcf10891e2997addf8bbec38c7ae1317. Непушенных коммитов нет; staging пуст.
Продолжение существующей задачи в той же папке/ветке, не новая задача от main.
Историческое имя ветки не включает модельные цены; менять/переименовывать ветку
или создавать checkout не требуется. Main не трогать.

На входе WIP: core/one_call_prompt_contract.py (prompt44, editorial brand/direction,
58 offline PASS + независимый scoped Checker PASS) и DEMO_MODEL_PRICE_EXPERIMENT.md
(запись этой правки и подготовка пунктов 1–4). Foreign untracked prototypes/
сохранить и не stage. .env, ignored logs, data/DB, сырые provider payloads и
пользовательские разговоры не читать/публиковать для Git checkpoint.
Текущий DOC allowlist: эта карточка; DEMO_D2_DELIVERY_ROADMAP.md;
DEMO_MODEL_PRICE_EXPERIMENT.md (все docs/tasks). Prompt44 сохранить без новых edits.
Exact runtime allowlist каждого этапа определить по call-path перед его правками.

### Этап 0 — чистая точка сохранения

1. Завершить DOC-план и независимый scoped Checker; проверить ссылки и отсутствие
   противоречий с текущими решениями. Отдельно учесть уже проверенный prompt44.
2. До реализации сохранить prompt44 + согласованную DOC-подготовку одним именованным
   checkpoint. Запрос проверки Git не считать отдельной командой commit/push:
   если разрешение публикации не дано явно, получить его перед Git mutation.
3. Stage только exact четыре пути: core/one_call_prompt_contract.py и три DOC пути
   текущего allowlist. Проверить staged names/stat/full diff/diff --check; commit,
   push текущей ветки, сверить remote SHA. В отчёте назвать фактический новый SHA.
4. Tracked tree и staging после сохранения пусты; prototypes/ отдельно и неизменен.
   Не обещать полностью пустой status при сохранённом untracked прототипе.

### Этап 1 — ошибка обычной ссылки не уничтожает независимый ответ

Runtime preflight 2026-10-10: owner «Давай» разрешил реализацию этапа 1.
Repository/Git top: C:/Cursor Projects/artgents-bot-active;
branch codex/model-price-experiment; baseline HEAD/origin branch
4e9bb7686b65789d6b2c84cd69ff322229b525a8; origin/main/merge-base
efa3f773bcf10891e2997addf8bbec38c7ae1317. Tracked/staging пусты;
foreign untracked prototypes/ вне задачи. Exact allowlist:
core/response_plan_materialization.py; tests/test_d2_content_reference_gaps.py;
tests/test_d2_multi_request.py; tests/test_d2_independent_request_parts.py;
docs/tasks/DEMO_D2_INTERFACE_TASK.md.
Классификация: bug fix, не аттестация упрощения всего бота.
Единственный owner подтверждения ordinary content target — материализация;
модель остаётся owner смысла. Удалить повторный _d2_content_scope и повторные
membership checks; подтверждённый scope использовать в parts/detail filter.
Неподтверждённый target получает existing unavailable/source_missing, scope mixed
без descriptor/IDs/source, чтобы существующий completion reader не сохранял
предыдущую тему как после clinic address. Context carry rules не менять.
Existing source association и optional provenance behavior сохраняются.
Provider/browser calls: 0; commit этого runtime после Checker/widget отдельно.

Реализация этапа 1 (2026-10-10, checkpoint относительно 4e9bb76):
- Удалены _d2_content_scope и его повторные вызовы/membership проверки.
  _d2_typed_content_scope_from_part подтверждает предмет один раз; результат
  используется для publication, part identity, descriptor и detail narrowing.
- Unknown service/topic (включая направление в service namespace) получает
  existing d2_content_source_missing + approved gap. Неподтверждённая prose,
  IDs, source UI и discussion descriptor не публикуются. Existing mixed scope
  очищает предыдущую discussion reference через прежний completion reader.
- Valid optional/missing document provenance сохраняет model prose без source UI;
  proven foreign source/direction остаются fatal раньше локального gap.
  Независимые address/price/detail сохраняются в исходном порядке. Новых wire,
  storage/context fields, memory, классификаторов, retry и model calls нет.
- Новая HTTP JSON/SSE матрица: 54 PASS (unknown targets × source presence,
  обе очередности address/price, replay, previous price → gap → next context,
  independent detail, optional prose, foreign source/direction).
- Итоговый d2-stage1-final-f.xml: 81 cases, 77 PASS / 4 FAIL, 186.17s.
  Все четыре failures совпали по именам с чистым checkpoint 4e9bb76
  (d2-stage1-baseline-g.xml: 33 cases, 11 PASS / 22 FAIL). Это прежние price
  fixtures без подходящего overview/part-failure authority; новые регрессии
  не обнаружены. Изменённые assertions unknown service/topic и foreign-source
  guard исполняются на действующем wire. Два legacy content_realization поля
  убраны только из тестовых payloads, assertions не ослаблены.
- Ранний guards-d: 8 PASS / 10 FAIL; все десять старых wire-fixture failures
  воспроизведены на чистом baseline. Setup-only baseline-e и первый прогон
  новых тестов с ошибочными r-ID не считаются аттестацией runtime.
- XML вне Git в Local/Temp. Provider/live/browser/SMTP: 0. CI целиком не запускался;
  это offline execution evidence, не гарантия живого понимания моделью.
  Independent Checker: PASS, blockers/test weakening/scope creep нет;
  SAFE_TO_WIDGET_TEST=YES только для stage 1 bug fix. Checker прочитал XML,
  pytest повторно не запускал. Владелец проверил widget; логи подтверждают
  сохранение контактов и точной classic/Implantium цены при неподтверждённой
  content-теме, а также корректный следующий includes по показанному offer.
  Первоначальная root-array ошибка произошла до материализации и остаётся
  открытой; неверный выбор topic моделью также не исправлен этим этапом.
  Это ограниченный live результат защиты независимых частей, не полный
  live PASS составных вопросов. Этап 1 принят владельцем в этих границах.
  Widget: 6 provider attempts владельца; агент дополнительных live calls не делал.
  Owner «Делай комит пуш» разрешил сохранение exact пяти файлов.
  Staging перед сохранением пуст; предыдущий remote checkpoint 4e9bb76;
  prototypes/ вне checkpoint. Фактический SHA/push проверить после commit.

Тип: общий bug fix исполнения, не semantic repair. Правило утверждено владельцем.
Если ordinary операция структурно прочитана, но её предмет нельзя подтвердить:
проблемная часть получает спокойный gap по существующему approved failure text;
независимые правильные parts сохраняются в исходном порядке. Не публиковать
неподтверждённое объяснение как подтверждённое. Не выбирать другой target за модель.
Настоящие tenant/source ownership, snapshot binding, UI authenticity и lead/privacy
нарушения остаются строгими отказами. Неизвестный model ID сам по себе не доказывает
foreign tenant. Пустой/обрезанный/непарсируемый общий ответ не позволяет выделить
parts и не превращается в частичный успех. Новых retries/calls/classifiers нет.

До → после: content с отсутствующим service/topic сейчас может обрывать весь turn
и местами называется foreign_material; после ordinary reference failure локален,
а trust violation отделён. Убирается ложная зависимость успешного адреса/цены
от корректности unrelated informational target. Понимание остаётся у модели;
код владеет проверкой ссылки и результатом исполнения. Не называть это удалением
всего старого сборщика; точную классификацию checkpoint отразить по фактическому diff.

Проверки: валидные content/service/topic; direction переданный как service;
неизвестный service/topic; отдельно допустимое omission optional content_ref и
неизвестный supplied document ref (не превращать omission в gap автоматически);
content+address и content+price
в обеих очередностях; honest gap/status/no bogus scope; finalized offers и следующий
context; replay/один вызов; настоящие foreign source/snapshot/session/UI failures.
Проверить /ask и /ask/stream на одном исполнителе, не только seam HTTP200.
Объект проверки — весь класс неверных ordinary ссылок, без phrase-specific условий.

### Этап 2 — один каталог сущностей и явных связей

Сначала read-only карта существующих service/direction/material relationships:
что задаётся явно, что выводится из frontmatter или имени файла, где есть дубли
и неоднозначность. Охватить ссылки offers/brands/doctors/policies/commercial,
не сводя разные предметные сущности в один тип и не меняя clinic selection policy.
Показать владельцу конкретные изменения исходных файлов до KB edits.

Цель: единый источник явных связей, из которого строятся code indexes и model
projection. Filename не должен оставаться параллельным owner той же связи.
Сначала использовать имеющиеся утверждённые данные; не начинать тотальный перенос
всех JSON/YAML/MD. Форму authoritative registry и удаления прежних выводов определить
на основании карты и отдельно согласовать, если нужны новые KB fields/files.
Новый слой/параллельный registry, который повторяет старое решение, не цель этапа.

Критерии: прежние canonical relationships/offer order/doctor links/applicability
сохранены; новые indexes выводятся из одного owner; старые reachable способы
получения заменённых связей удалены; ambiguity/битые связи обнаруживаются при
проверке pack; tenant protections сохранены. Тексты, суммы и клинические утверждения
не редактировать. До реализации exact allowlist и before/after/removal в этой карточке.

#### Read-only карта этапа 2 — 2026-10-10

Классификация checkpoint: documentation only, предложение до реализации.
Owner «Делаем» разрешил продолжение этапа 2; изменения KB требуют отдельного
согласования. Repository/Git top: C:/Cursor Projects/artgents-bot-active;
branch codex/model-price-experiment; HEAD/origin branch baseline
4fa440803d256a975414483d7b0013d670cff070 (этап 1 сохранён и pushed).
origin/main и merge-base efa3f773bcf10891e2997addf8bbec38c7ae1317.
Exact DOC allowlist: docs/tasks/DEMO_D2_INTERFACE_TASK.md.
На входе tracked tree/staging пусты; foreign untracked prototypes/ сохранить.
Runtime, wire, KB, суммы, тексты и выбор предложений не меняются этой записью.

Карта владельцев существующих связей:

| Связь | Текущий источник | Что обнаружено |
| --- | --- | --- |
| Услуга → основной документ | service_catalog.json: content_ref | Явная ссылка; сохранить |
| Документ → направление | MD frontmatter: topic | Явное направление; subtopic не является canonical topic |
| Услуга → направление | Topic основного MD в snapshot; префикс filename в commercial/CTA | Два способа получить один смысл |
| Направление → услуги первого ценового обзора | d2_direction_prices.json: service_ids/offer_ids | Это выбор клиники для обзора, не полный состав направления |
| Offer → услуга/вариант/бренд | target_response/pricebook/services/*.json | Явные типизированные ссылки |
| Врач → услуги/профиль | doctor_catalog.json: service_ids/profile_ref | Явные связи; не заменять медицинским подбором модели |
| Коммерческий факт → применимость/деталь | pricebook/facts.json | Явные ограничения и ссылки |
| Автопоказ фактов/совместимость | d2_commercial.json | Другой предмет ответственности, не копия facts.json |
| Политика услуги/бренда | clients/demo/clinic_policies.yaml | Для отсутствующего бренда есть конкурирующий legacy путь |
| Название/страна бренда | brand_catalog.json | Явные данные; сохранить |

Call-path evidence:
- core/d2_tenant_snapshot.py строит service_topics через service.content_ref →
  metadata.topic и allowed_service_ids документов. core/d2_snapshot_sources.py
  повторно читает MD topic в resolve_d2_clarify_service_topic; build sources
  заменяет состав d2_directions настроенным ценовым пулом для таких направлений.
- contracts/target_service_content_topic.py выводит направление из filename.
  Reachable потребители: core/response_plan_authored_alternative_policy.py →
  response_plan_materialization.py (commercial scope); core/d2_contacts_cta.py;
  response_plan_fact_policy.py и response_plan_fact_projection.py (warranty scope).
  Перед реализацией повторно проследить каждый вызов; не чистить legacy код
  только по текстовому совпадению.
- core/d2_dialogue.py сначала направляет отсутствующий в brand_catalog бренд
  в build_d2_unknown_brand_response. Эта функция в d2_snapshot_sources.py читает
  legacy service_alternatives.match_keywords/note и привязана к конкретному
  implant_systems document ref. Typed brand_alternatives.approved_text уже
  передаётся модели, но другой reader используется позднее для известного бренда.

Конкретные неоднозначности, не объявленные исправленными:
1. tomography: content_ref diagnostics__service__tomography.md, MD topic=clinic,
   filename-derived topic=diagnostics. Это доказанное расхождение источников,
   не доказанный живой ошибочный ответ КТ. Не выбирать topic по family автоматически.
2. implantation: 9 услуг с primary MD topic, в price overview — 4; prosthetics:
   5 против 3. restoration содержит curated price overview classic +
   removable_dentures, хотя их primary topics — implantation/prosthetics.
   Не расширять обзор и не переносить primary topic из настроек обзора.
   Разделение этих отношений не разрешает молча менять информационный охват
   existing d2_directions или context carry; такие потребители проверить отдельно.
3. Osstem: legacy note содержит «Osstem в ассортименте нет. Работаем с Implantium,
   Impro и Nobel Biocare — могу рассказать про отличия систем и ориентиры по
   стоимости «под ключ».» Typed approved_text заканчивается после Nobel Biocare.
   Сведение к одному source требует согласовать, какой текст сохранить.

Предлагаемый минимальный вариант (ещё не реализован):
- Сохранить нынешние файлы владельцами своих данных. Не создавать editable
  d2_entities.json и не дублировать в нём offers, doctors или commercial facts.
- Sole owner primary topic услуги: topic её основного MD, найденного по явному
  service_catalog.content_ref. Один проверенный производный индекс snapshot
  используют потребители этой связи. До → после: разные MD/filename readers →
  один MD owner через explicit content_ref → удалён вывод смысла из имени файла
  и повторное самостоятельное чтение этой связи в runtime.
  Это сохраняет зависимость primary topic от основного документа; не выдавать
  вариант за независимый registry направлений. Отдельный topic_id в service_catalog
  возможен, но означает новые KB/schema edits и сейчас не утверждён.
- Настроенный ценовой обзор оставить отдельной явной связью и с прежним порядком.
  Не добавлять новый selector, semantic repair, fallback или память.
- Для отсутствующего бренда предложить один typed brand_alternatives owner,
  удалив заменённый reachable legacy reader и его filename binding. Вариант
  сохранения длинного нынешнего ответа: перенести legacy note дословно в typed
  approved_text. Конкретные KB правки и удаление legacy записи — только после GO.

Перед реализацией показать владельцу два решения: primary topic КТ (clinic либо
diagnostics) и сохранение длинного Osstem текста в единственном typed источнике.
После решений определить точный runtime/KB allowlist, cross-tenant coverage,
before/after/removal и минимальную матрицу проверок. Не начинать этапы 3/4 попутно.

Read-only evidence: demo содержит 23 услуги (22 active), 58 MD, 33 offers,
3 бренда, 6 врачей, 10 коммерческих фактов. У всех active услуг основной MD найден;
все MD имеют topic, doc_id совпадает с filename без расширения. Проверенные
offer service/brand refs, doctor service/profile refs и fact service/detail refs
существуют; broken links в этом проверенном наборе нет. Это статическая проверка
названных связей, не полная аттестация pack, runtime или понимания моделью.
Консультация Astra выполнена read-only; provider/live/browser/SMTP: 0.
Bot tests не запускались ради документации. Independent DOC Checker: PASS;
blockers нет, карта и reachable readers подтверждены. Это не аттестация
реализованного архитектурного упрощения. Staging пуст; commit/push новой DOC
записи пока не выполнялись.

#### Реализация этапа 2 — согласование и preflight

Owner «СОгласнен» утвердил primary topic КТ=diagnostics и перенос длинного
Osstem текста дословно в typed brand_alternatives с удалением его legacy строки.
Классификация: scoped architecture simplification + согласованные metadata edits.
Root/Git top C:/Cursor Projects/artgents-bot-active; branch codex/model-price-experiment;
baseline HEAD/origin branch 4fa440803d256a975414483d7b0013d670cff070;
main/base efa3f773bcf10891e2997addf8bbec38c7ae1317. На входе только DOC-карта
этого этапа и foreign untracked prototypes/; staging пуст.
Exact allowlist: contracts/d2_tenant_snapshot.py; core/d2_tenant_snapshot.py;
core/d2_snapshot_sources.py; core/d2_contacts_cta.py;
core/response_plan_authored_alternative_policy.py; core/response_plan_fact_policy.py;
core/response_plan_fact_projection.py; core/response_plan_materialization.py;
clients/demo/clinic_policies.yaml;
clients/demo/md/diagnostics__service__tomography.md;
tests/test_d2_primary_topic_links.py; docs/tasks/DEMO_D2_INTERFACE_TASK.md.

До → после → удалённая зависимость: D2 commercial/CTA читают filename, content/context
читают MD → primary topic принадлежит MD основного документа по content_ref →
filename больше не определяет primary topic в D2. Snapshot хранит immutable derived
service_topics; materialization использует существующую projection MD topics из sources.
Общие helpers получают authoritative mapping, в том числе пустой; старое поведение
None остаётся только для callers вне D2, не fallback D2. Wire/storage/model calls
не меняются. Удаляется duplicate warranty derivation из fact projection, остаётся
один fact-policy evaluator. Unknown brand reader больше не читает legacy keywords
или фиксированное имя implant_systems; использует существующий typed policy reader.
Price overview membership/order остаётся отдельным curated relation.
Техническая консультация Astra выполнена; проверки и Checker записать по результатам.

Результат реализации (2026-10-10):
- Удалены filename-based primary topic на D2 commercial/CTA paths и повторное
  чтение service topic в clarification/context helper; общий warranty policy
  заменил дублированное вычисление в fact projection. Legacy callers вне D2
  остаются вне этого checkpoint; отсутствие MD связи в D2 не вызывает их parser.
- Snapshot index immutable; materialization projection строится из уже переданной
  MD topic map по explicit content_ref. Новых KB fields, wire/storage fields,
  semantic selectors, retries, provider calls и session memory нет.
- КТ: только topic clinic → diagnostics. Osstem: длинный note перенесён дословно
  в typed approved_text, legacy row и его runtime reader удалены. Unknown brand
  без typed policy сохраняет прежний gap; другой brand price не подставляется.
- Новые тесты намеренно расходят filename и MD topic и запрещают вызов parser:
  commercial policy, warranty candidate, CTA, doctor completion, clarification
  и следующий service context. Проверены empty authoritative map, JSON/SSE,
  replay, exact typed Osstem text, отсутствие цены для отсутствующего бренда
  и foreign session refusal. Price overview остаётся 4 services против 9
  primary implantation members. Реальный model understanding не аттестуется.
- d2-stage2-links-green.xml: 8 PASS, 13.48s. Коммерческие прежние сценарии:
  38 PASS в d2-stage2-final.xml. Карточки и snapshot guards: 71 PASS в
  d2-stage2-final-guards.xml (полный ранний XML: 79 cases, 77 PASS / 2 FAIL;
  оба FAIL — новые неверные ожидания topic в service DiscussionScope, исправлены
  и повторно проверены в links-green). Независимые guard suites не падали.
  Итого 117 разных scoped cases PASS, не полный CI.
- Ранний setup sandbox failure и промежуточные новые test/code failures не считаются
  аттестацией; исправлены collision имени warranty helper и ошибки тестовой
  contact operation/контекстных ожиданий. Существующие tests не ослаблены.
  Полного baseline/CI прогона нет; прежний долг вне этих suites не закрыт.
- Provider/live/browser/SMTP: 0; tests используют fake provider. Для widget нужна
  новая беседа после изменения tenant fingerprint. Staging пуст; commit/push
  не выполнялись. Foreign prototypes/ вне allowlist. Independent Checker: PASS;
  blockers/test weakening/scope creep нет. SAFE_TO_WIDGET_TEST=YES для этого
  scoped этапа 2; вся архитектура, этапы 3/4 и live understanding не аттестуются.
  Checker прочитал XML, pytest повторно не запускал.

Widget finding после этапа 2 (owner screenshot, 2026-10-10): КТ → свой КТ →
Osstem availability → «Расскажите» возвращает описание КТ. В read-only последних
логах (16:29 UTC) verified Osstem reply опубликован correctly, но следующий
provider input содержит прежний discussion_scope service:tomography и пустой
assistant_text для reference ответа про Osstem (brand_id в parts сохранён).
Модель затем выбирает service:tomography. Это наблюдаемая ошибка whole dialogue,
не неправильная сумма/карточка или потеря typed Osstem policy текста при публикации.
Причина передачи: completion _project_pair не копирует этот authored reference,
retain_discussion_reference сохраняет прежнюю тему при scope=clinic без descriptor.
Этап 2 эти history/carry rules не менял. Scoped offline PASS не закрывает finding.
Не исправлять phrase-specific prompt/regex на «Расскажите». Общий boundary для
brand/service availability continuation, допустимой reference history и замены/
очистки предыдущего scope предложить владельцу до изменения этих правил.
Агент дополнительных provider calls не делал; сырые логи/разговоры не включены в Git.

Сохранение checkpoint 2А: owner «Давай коим и пуш его» явно разрешил commit/push
этого exact 12-file allowlist в текущую ветку. Этап 2А фиксируется в проверенных
границах связей; выявленная ошибка продолжения остаётся открытой. Обсуждённый
пункт 2Б про целостный контекст — предложение следующей работы, в этом checkpoint
не реализован и не аттестован. Foreign prototypes/ не stage. Финальный SHA и
совпадение remote сообщить после сохранения; merge/deploy не входят в команду.

#### Подготовка 2Б — целостный контекст, 2026-10-10

Классификация текущего checkpoint: documentation only. Owner «Давай дальше»
разрешил подготовку следующего пункта после сохранённого 2А. Runtime и новые
carry/product rules ещё не реализованы; ниже предложение для согласования.
Root/Git top C:/Cursor Projects/artgents-bot-active; branch
codex/model-price-experiment; baseline HEAD/origin branch
723e6aaa203d1286898b22d3ad8ab634012c4dd6; origin/main/merge-base
efa3f773bcf10891e2997addf8bbec38c7ae1317. На входе tracked/staging чисты,
foreign untracked prototypes/ сохранить. Exact DOC allowlist:
docs/tasks/DEMO_D2_INTERFACE_TASK.md; docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md.

Read-only консультация Astra: существующий receipt/store остаётся sole memory
owner по Target Contract §3. Причина шире пропуска текста: generic reference
и commercial parts теряют source identity/исходный предмет; history исключает
authored text и допускает policy clarification по точному совпадению строки;
retain_discussion_reference удерживает прошлую тему для любого clinic scope.
Нельзя восстанавливать пропущенный смысл анализом пользовательской фразы,
rendered_text, отдельным summary, regex или дополнительным model call.

Предлагаемая цель: producers сохраняют существенный завершённый результат
в существующем completion; один projector передаёт предмет, опубликованный
исход и проверенные источники в порядке частей. Цены/финансовые условия
остаются через offer/fact references, не копируются в ordinary prose.
До → после → удалённая зависимость: выборочная передача текста и generic
результаты → projection завершённых частей с их происхождением и исходом →
нет зависимости от происхождения текста модель/код, одной policy строки
и broad clinic scope как универсального keep. Это цель будущей реализации,
не доказанное упрощение текущего DOC checkpoint.

Правила для owner agreement перед runtime:
- Контакты/часы работы сохраняют обсуждаемую услугу в пределах прежнего TTL.
- Однозначная новая scoped задача заменяет прежнюю; mixed/неоднозначность
  не выбирает услугу по позиции. Существующие правила не расширяются молча.
- Самостоятельный ответ о новом бренде/недоступной услуге не оставляет старую
  КТ активным предметом. Если нового предмета нет в DiscussionScope, прежний
  scope очищается, а предмет/результат остаются в history. Availability той же
  услуги не считать автоматически новой темой только из-за наличия brand_id.
- Scoped commercial результат сохраняет исходный service/topic; согласовать
  его влияние на активный scope. Отрицательная применимость остаётся отдельным
  исходом, не positive published fact ID. Отказ по недоступной услуге не означает
  автоматический выбор предложенной альтернативы.
- Смысл короткого продолжения определяет модель по переданному разговору.
  При нескольких возможных предметах она уточняет, а не выбирает за человека.

Граница полноты: Osstem approved answer уже есть в policy model catalog;
source identity позволит связать его с опубликованным ответом. Service
alternatives передают IDs без произвольного authored текста, который может
содержать суммы. Нельзя обещать понимание любого приглашения из такого текста
по одним IDs. Если для общей цели недостаточно существующих полей, предложить
точную форму provenance/outcome/continuation в том же completion владельцу
до реализации. Новые поля, KB правки и отдельный clear_context flag этой записью
не разрешены; не обходить финансовый запрет другой секцией provider input.

Будущие проверки: JSON/SSE completed turn → next provider input для смены
предмета и availability той же услуги, альтернатив без автоматического выбора,
commercial positive/negative/gap, policy/clarification, card → contacts → detail,
mixed, TTL, foreign receipt, длинного ответа и authored текста с суммой/ПД.
Лимиты 3 пары/1000 символов/30 минут сохранить. Fake provider проверяет передачу,
не живое понимание. Live calls требуют отдельного hard budget; текущие старые
бюджеты исчерпаны. Runtime allowlist определить после согласования границ.
В подготовке tests/provider/browser/SMTP: 0; commit/push пока не выполнялись.

Дополнение после owner «Ну окей тогда следующий давай. 2B тогда.»:
общая работа 2Б согласована; точное расширение контракта ниже предложено,
но отдельно ещё не согласовано. Astra подтвердила, что existing content_ref,
brand_id и positive fact IDs не выражают provenance/outcome без искажения.
Предлагается одно поле source_results на D2ResolvedRequestPart: tuple записей
source_ref и outcome answered/excluded/unavailable. Код создаёт ссылку только
на действительно использованный tenant источник: brand_policy, service_alternative,
policy или fact. answered означает публикацию ответа источника, не доступность
услуги и не разрешение политики. Отказ commercial не попадает в positive fact IDs.
История уже передаёт parts, отдельная projection-копия не добавляется.
Меняются форма сохранённого completion и provider input; model output schema,
отдельный session state и KB не меняются. Исторические уточнения не маскировать
под искусственный source namespace; текущая clarify_task сохраняется.
Это не гарантирует восстановление любого authored приглашения service alternative:
такое обещание потребовало бы отдельной согласованной KB identity продолжения.
Runtime заблокирован только на согласование этого нового поля и точных carry
границ, не на повторный аудит. Tests/provider calls: 0 в подготовке.

Реализация 2Б: owner «Ок» согласовал source_results и продолжение работы.
Классификация: scoped architecture simplification плюс исправление потерь
provenance/outcome. Baseline/root/branch/main остаются указанными выше.
Exact runtime/test/DOC allowlist: contracts/response_plan.py;
core/d2_snapshot_sources.py; core/d2_dialogue.py;
core/response_plan_materialization.py; core/d2_completion_context.py;
core/d2_live_provider.py; tests/test_d2_completed_source_context.py;
docs/tasks/DEMO_D2_INTERFACE_TASK.md; docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md.
Pre-existing WIP — два DOC этой подготовки; prototypes/ foreign, не трогать.
Before/after/removal и sole owner — предыдущая карточка 2Б. Model output,
отдельная память, KB и дополнительные provider calls не меняются; completion
и provider input расширяются ровно согласованным source_results.

Allowlist дополнен tests/test_d2_primary_topic_links.py: утверждённый 2Б меняет
ровно прежнее ожидание «commercial не устанавливает scope» на явный service
classic после scoped commercial и контакта. Filename/topic/tenant guards
этого теста сохраняются; это миграция согласованного поведения, не ослабление.

Результат реализации 2Б перед Checker:
- Удалено сравнение history с буквальной _POLICY_CLARIFY; отвеченное уточнение
  проецируется по типу completed part, при отсутствии financial fact/policy IDs.
  Code-owned answers не копируются в ordinary prose. Source/outcome остаются
  в существующих ordered parts, отдельной памяти и projected копии нет.
- Удалено universal keep по response_scope=clinic: contacts, policy и clarification
  сохраняют прежний scope, новая scoped часть заменяет его; неоднозначный результат
  без descriptor очищает. Availability нового предмета не оставляет КТ активной;
  same-target availability сохраняет existing descriptor без выбора альтернативы.
- Brand/service producers замораживают использованный источник с exact block.
  Policy IDs связаны с частью; commercial сохраняет исходный service/topic и
  answered/excluded/unavailable по факту. Scoped commercial той же услуги без
  нового volume сохраняет проверенный brand/volume descriptor. Отрицательные
  результаты не учитываются как published positive facts.
- source_results добавлен только в completion/provider input; model output schema,
  KB, финансовый selector, цена/CTA, lead store и отдельный session state не менялись.
  Краткая provider инструкция описывает значение metadata, не исправляет route.
- Финальные текущие scoped cases: 110 PASS в d2-2b-card-guards.xml; 46 PASS и
  4 FAIL новых fixture assertions в d2-2b-final-source-policy.xml; исправленные
  четыре случая 4 PASS в d2-2b-focused.xml. Итого 160 разных scoped cases green
  для текущего runtime, не полный CI и не live. Новых cases в сумме 24.
- Ранний run d2-2b-final.xml: 131 PASS/14 FAIL. Причина runtime failures —
  producer добавил reference part без matching exact block (исправлено);
  новый detail fixture использовал неверное поле aspect (исправлено).
  Ранний green не заменяет финальную аттестацию. Setup sandbox temp failures
  не являются runtime evidence. Test с inactive=false нарушал snapshot pack;
  для unavailable fact используется валидный истёкший active_until.
- New bounded-history test использует email с разделителем ';'. Прежний,
  неизменённый mask_emails helper не маскирует email перед точкой; это отдельное
  обнаруженное ограничение baseline, не исправление/гарантия этого checkpoint.
  Телефон и email с указанным разделителем проверены; лимит 1000 сохраняется.
- Старые completion без provenance задним числом не восстанавливаются. Для
  widget начать новую беседу. Не гарантируется восстановление любых authored
  service invitations, отсутствующих в допустимом model catalog/typed данных.
  Clarify pending использует прежнюю задачу; новая незавершённая память не создана.
- Provider/live/browser/SMTP: 0. Staging пуст; commit/push/merge/deploy не выполнялись.
  Foreign prototypes/ сохранён. Independent Checker: PASS для checkpoint 2Б.

Focused Checker findings исправлены в том же checkpoint:
- Повтор fully-covered promo response сохраняет source_results каждой части;
  used_promo_ids отражает реально показанный источник, promo_ids остаются
  единственным deduplicated positive ledger. Recheck8PASS.
- Известный факт не подтверждает неизвестную service/topic. Commercial descriptor
  создаётся только по active tenant service или d2_canonical_topic_ids; price
  direction membership не является registry всех тем. Foreign direction fatal.
  Wrong namespace и clinic-wide fact с unknown service не дают active scope;
  canonical clinic без price direction допустим. Membership recheck8PASS.
- В составном price+commercial same-target ответе descriptor коммерческой части
  берётся из matching опубликованной цены текущего completion, прежде прежнего
  input. Разные descriptors не выбираются по позиции. Explicit volume не заменяется.
  Новый composition fixture исправлен с ошибочного brand substring на exact
  tenant offer_id classic.one_tooth.nobel; runtime selection не менялась.
- Новый test module содержит 38 cases. Итоговый coherent run после всех code
  исправлений — d2-2b-final-checkpoint.xml (new context, commercial, primary-topic),
  итог: 84 PASS, 0 FAIL. Предыдущие 160 cases — промежуточные
  scoped guards до focused findings; не заменяют аттестацию финального дерева.
  KB/model calls/staging/foreign WIP не менялись. Checker focused recheck: PASS.

Финальный runtime checkpoint 2Б: d2-2b-final-checkpoint.xml — 84 PASS,
0 FAIL, pytest 108.14s: new context38 + commercial38 + primary-topic8.
Код и tests старше этого прогона; предыдущие policy26/card64/session38 guards
записаны отдельно, их не называть повторным полным CI финального дерева.
Во время final run были неблокирующие Windows logging rotation errors:
существующий app.jsonl занят локальным процессом (WinError32). Runtime tests
не падали; logging setup не изменён этим этапом. Не выводить из scoped PASS
полную аттестацию diagnostics/logging или живого понимания Qwen.
Staging пуст, HEAD723e6aa, новая работа не committed/pushed; prototypes/ untouched.
Independent Checker: PASS для checkpoint 2Б, включая focused recheck трёх
findings. TEST_WEAKENING: нет. SAFE_TO_WIDGET_TEST=YES — новая беседа.
Полный CI и живое понимание Qwen не аттестуются; provider/live/browser/SMTP0.

### Актуализация §38 после аудита свободного диалога — 2026-10-10

Owner поручил полную дорожную карту с учётом 2Б и внешних разборов. Классификация
этого изменения: documentation only. Текущий порядок и acceptance записаны в
[Roadmap](DEMO_D2_DELIVERY_ROADMAP.md), подраздел «Единый план после аудита свободного
диалога — 2026-10-10» внутри канонического раздела 2026-10-02. Он уточняет будущие
этапы 3/4 ниже; прежние идеи не автоматически approved implementation.

2А committed/pushed723e6aa; 2Б implemented WIP, final84PASS и Checker PASS,
live-open, не committed/pushed. Root-array Osstem failure не является доказательством
неработающего 2Б: execution не начался. Одновременно целый живой диалог не принят.
Точка отсчёта, существующий exact allowlist и чужой prototypes/ сохраняются.

Новый порядок: сохранить честный checkpoint → 2В воспроизводимые input/privacy
bug fixes → 3А согласованный design model wire + existing completion projection →
3Б ограниченное факторное исследование Qwen → 3В replacement с удалением старого
reachable boundary → 4 whole-dialogue/cards acceptance → 5 отдельная owner-approved
KB cleanup → 6 integration/legacy/diagnostic debt. Никаких новых provider budgets
этим документом не выдано. Exact schema/input/history limits и состав KB изменений
показать владельцу до dependent edits. No new memory/secondcall/adapter/repair.

Аудит read-only подтвердил: short <3 gate блокирует ordinary Да/Ок; ** gate
блокирует содержательную разметку; email перед точкой не маскируется (user input
затем блокируется @guard, assistant projection без такого guard); content_text
обязателен до замены code-owned availability; structural validation атомарна;
clarification до reference; technical snapshot в model input; bounded history
1000chars/3pairs; output1024tokens при text4000chars. Причина последнего Osstem
не доказана объёмом42000tokens. Не объявлять nine kinds или every validator лишними.
Mixed booking потеря опровергнута: actual поздняя ветка966+ сохраняет запись.
pending_question хранит unfinished task, не просто показанное уточнение.

Результат упрощения проверяется снятыми независимыми решениями и удалёнными
call paths, а не renamed parts, shorter JSON, prompt patch или tests count.
Cursor/Checker трассирует actual path и adverse whole dialogues; offline и live
статусы отдельно. Два полных одинаковых review не нужны. KB facts/numbers/medical
wording не менять без exact owner согласования; не создавать гарантию правильности
произвольной financial prose новым verifier. §3 остаётся владельцем ответственности.

### 2В — входной privacy boundary, owner GO 2026-10-10

Owner «Делай. Потом строгий промпт курсору...» разрешил этот bug-fix checkpoint.
Root C:/Cursor Projects/artgents-bot-active; branch codex/model-price-experiment;
baseline056cac4cf3a7b9a4d54a041c8fbd8b897e95518e; origin/main/merge-base
efa3f773bcf10891e2997addf8bbec38c7ae1317. Tracked checkout был чист, staging пуст;
foreign prototypes/ сохранить. Exact allowlist: core/user_text_privacy.py;
tests/test_user_text_privacy_contract_offline.py; tests/test_d2_input_boundary.py;
docs/tasks/DEMO_D2_INTERFACE_TASK.md; docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md.

Классификация bug fix, не общий architecture PASS. До: длина <3 и наличие **
превращали содержательную обычную реплику в privacy-only; email перед точкой
оставался без маски. После: существующий guard оценивает очищенный текст без
двух этих gates; existing email boundary различает sentence dot и продолжение
домена. Удалены length и Markdown barriers, не добавлены semantic rules.
Meaning owner — модель; privacy owner — существующий helper. Проверки пустого/
contact-only текста, немаскированного @, phone leak и bound lead name сохранены.
Lead intake/pause, provider schema/context/calls, prices/UI/KB не меняются.
Однобуквенный текст с буквами также проходит ordinary guard; это общая структурная
граница, не whitelist Да/Ок. Разрешение input не гарантирует верный ответ Qwen.

Проверки: positive short/formatted text, punctuation/plus/subdomain email,
negative contact-only/unmasked @/phone leak/bound name; actual JSON/SSE следующий
input, completed history и replay; existing lead interruption/cancel guards.
Данные тестов синтетические; сеть/провайдер не вызываются. Не запускать browser
для этой правки. Cursor должен отвергнуть phrase allowlists, новые states/fields,
handlers/calls/repair adapters и ослабление privacy, и проследить actual path.
Evidence: d2-2v-targeted.xml — 108 PASS, 0 FAIL, 85.72s; privacy contract,
новый JSON/SSE boundary, existing lead_interrupt_http и lead_cancel_ui.
Из них 42 новых cases и 66 прежних guards. Полный CI не запускался; известных
падений в этих четырёх modules нет, чужой baseline debt этим не закрыт.
Тестовые логи изолированы через BOT_LOG_DIR во временной папке, logging runtime
не менялся. Provider/live/browser/SMTP: 0. Fake inputs доказывают ingress/privacy,
не живое понимание короткого продолжения или устранение root-array Osstem.
Чистые цифры/небуквенные реплики остаются blocked; active bound lead-name guard
также не изменён и может отклонить короткое буквенное слово. Это прежние границы,
не обещание свободного dialogue во всех lead phases. Независимый Checker:
PASS scoped bug fix 2В; actual path/guards/отсутствие новых слоёв проверены,
TEST_WEAKENING нет; final XML108PASS. SAFE_TO_WIDGET_TEST=YES. Staging пуст,
commit/push не выполнялись. Cursor review по owner запросу — следующая внешняя
проверка удаления причин и отсутствия возврата к усложнениям, не общий runtime PASS.

### Предыдущее предложение этапа 3 — одна ссылка вместо независимых type и ID

Предпочтительное предложение: canonical entity ref, чей тип определяет registry
этапа 2. Представление, например direction:implantation/service:classic, — эскиз,
не уже утверждённый новый wire. Перед кодом показать точный ordinary результат,
завершённую операцию, уточнение и known-task reply; согласовать форму/границы.
Не менять определение clinic-wide commercial scope, unknown brand, inactive
service, volume/count, policy precedence, first-price/deferred или product limits.

Цель: удалить возможность независимо прислать несовместимые type и ID.
Не обещать устранения выбора неверной существующей сущности. Заменить старую
wire форму и её reachable readers; не сохранять постоянный new-to-old converter,
dual contracts или вторую память. Серверные actions/receipts/следующий context
должны использовать один согласованный reference boundary.
Один model call и ordinary json_object сохраняются; strict activation не входит.
Существующие локальные DB не мигрировать/удалять автоматически; перед widget
указать необходимость новой беседы, если локальные frozen receipts несовместимы.

Проверки: все operation kinds/completed/clarification формы; known task identity;
неверная/неизвестная ref и trust negatives; direction overview + brand, concrete
service prices, volume, detail, promotions, doctors, policy, clinic contacts;
mixed части, historical tabs после адреса, дальнейшие текстовые includes/stages;
replay/context/один вызов и price click без модели. Не заменить их schema collection.

### Этап 4 — компактное представление модели и оставшиеся aliases

4A: из проверенной базы построить одно модельное представление с полезным
содержанием и необходимыми IDs/связями. Убрать доказанные дубли каталогов и
служебный MD шум из model input, не из исходной базы автоматически. Перед исключением
frontmatter/aliases/comments проверить, не несут ли они единственную информацию
для понимания; полезные сведения явно сохранить в projection. Сначала показать
владельцу точный список исключаемых/сохраняемых/переносимых model-input данных
и получить согласование до изменения его состава — даже без edits исходных MD.
Не удалять clinical
content по случайному top-k; не вводить RAG/второй вызов/новый semantic selector.
Начальные измерения audit: system153454 chars, corpus112068; это диагностика,
не доказанный причинный вклад в сбои. Сравнить размер и фактический content coverage.

4B: report оставшихся Markdown alias дублей по DEMO_KB_EDITOR_AGENT.md, вместе
проверить шапку, comments, headings и body. Пример: extraction__service__tooth_extraction.md,
mozhno-li-srazu-implant — exact heading duplicate «можно ли сразу поставить имплант»,
пересказ «удалить зуб и сразу имплант», широкое «имплантация после удаления».
Предложить удаление комментария, не выполнять без согласования списка владельцем.
Предыдущие 83 удалённых вхождения не означают полную чистку. Не переносить правило
на aliases каталогов services/brands/doctors. Утверждённые удаления исходных MD —
отдельный data checkpoint от изменения модельного представления.
Сохранить видимый текст/цифры/факты/силу обещаний/медицинские формулировки, anchors,
suggest_h3, CTA и ссылки. Никакого медицинского/юридического сглаживания.

4A проверять на единой неизменной матрице вопросов с этапом 3, отдельно measurement
и смысловую корректность; offline coverage, scoped model-input и runtime проверки.
Для live сравнения заранее предложить owner бюджет и hard cap; все прошлые бюджеты
исчерпаны. Не выдавать уменьшение chars или fake-provider PASS за live reliability.
4B: exact deletion list и preservation guard; не запускать большой runtime CI ради
комментариев. Fingerprint change явно сообщить, widget начать новой беседой.

### Процесс каждого checkpoint и границы

Порядок: exact preflight/allowlist → реализация в согласованных границах → минимальные
offline проверки → один independent Checker → owner widget → явный commit/push GO
→ exact staging и проверка → checkpoint commit/push + remote SHA. После REJECT —
focused recheck, не новый полный аудит. Cursor — независимый review на существенных
границах 1 и 3, вместо дублирующего полного Checker; если нужен второй, обосновать
конкретную непокрытую границу. Мелкое UI проверяет владелец; browser automation
только для сложного interaction/auth/context риска. Full CI перед merge, не каждым
малым edit. Baseline failures сверять с чистой точкой, не скрывать/ослаблять tests.

Отчёт этапа: что убрано/добавлено, owner, affected path, changed behavior, tests,
baseline failures, live budget usage, staging/commit/push и foreign WIP. Каждый
следующий baseline — сохранённый предыдущий checkpoint, проверенный на GitHub.
При паузе named checkpoint должен быть сохранён и pushed по явной команде владельца.
Новый чат/ветка/папка не нужны. Merge/deploy/destructive cleanup не разрешены.
За рамками: новый выбор лечения/предложений, цены через model prose, содержание
акций, redesign виджета, compiled pack/caching, тотальная legacy cleanup, новый
summary/patient state/second memory. Эти audit предложения не добавлять попутно.


## §39. 3А — переработка проекта после Cursor REJECT, 2026-10-10

Статус: revised design, НЕ implemented; Cursor REJECT исходного §39 принят.
Ни сравнение3Б, ни runtime3В не начинать до закрытия перечисленных design gates.
Предыдущий documentation Checker PASS означал честность статуса и scope, но не
полноту архитектурной замены. Называть такой PASS готовностью проекта было неверно.

Root C:/Cursor Projects/artgents-bot-active; branch codex/model-price-experiment;
baseline/HEAD и remote340fd771e38d9bb80ececb01bac99e8c326972e1; origin/main/merge-base
 efa3f773bcf10891e2997addf8bbec38c7ae1317. 2В сохранён/pushed, scoped Cursor PASS,
108 offline cases. WIP только этот файл и DEMO_D2_DELIVERY_ROADMAP.md, staging пуст,
foreign prototypes/ сохраняется. Allowlist этой доработки — ровно два документа.
Классификация documentation/design. Это НЕ implementation architecture PASS.
Table §3 DEMO_D2_TARGET_CONTRACT.md не меняется. Предложения не дают себе owner GO.

### 39.1. Ответ на blockers и единый владелец

1. История должна включать фактически опубликованный текст brand/service policy
   из completion, в паре с соответствующим вопросом. Source ID и lookup в текущем
   каталоге не заменяют показанную реплику. Invitation не сочиняется projection.
2. Предложение availability ОТОЗВАНО. Новый kind не нужен; существующие девять
   operations сохраняются. Approved brand/service precedence общий для content,
   price и price_detail, согласно core/d2_dialogue.py reference_response901–926.
   Эта ветка — владелец exact ответа, а не лишний semantic route. Удаляем требование
   обязательного черновика перед ней, НЕ её бизнес-правила. Нельзя дублировать её
   отдельным content resolver, price resolver и новым availability resolver.
3. Canonical target требует прямой замены всех readers ниже, включая clinic,
   unresolved, doctors, detail и clarification. String→old {type,id} adapter запрещён.
4. Model-generated ordinary IDs нужны joins, но их генерация не обязана лежать
   на модели. Полная схема identity ниже включает filtered/deferred/pending/known
   paths. Недоказанную идентичность нельзя объявлять удалённой dependency.

### 39.2. Кандидат wire и структурная форма

Сохранить корень outcome/ordered blocks и существующие девять kinds. Ни phrase
allowlist, ни новый discriminator/realization/availability field не вводится.
Смысл определяет один model call; code-owned факты — прежние владельцы.

Content имеет две непересекающиеся структурные формы, отражённые в одной
генерируемой JSON Schema и тех же Python types:
- Completed request: content_text optional; pending_question/clarification absent
  или null; target/content_ref/sections/brand сохраняют свои прежние ограничения.
- Unfinished request: clarification и pending_question required/nonblank,
  content_text absent/null. Не менять смысл pending_question на displayed question.

Удалить explanation_form hidden requirement completed_explanation_text_required
и зависимости от model_fields_set для absent/null optional fields. Actual typed
alternatives должны выдавать ту же валидность в schema и parser; не поддерживать
вторую вручную исправляющую schema. Kind=content у alternatives одинаковый:
не лечить техническое ограничение discriminator добавлением нового model field.
Пустая строка не означает пригодный ответ; supplied text сохраняет nonblank/length
checks. Для optional clarification/selector отсутствие и null эквивалентны;
volume absent/null и volume.extent=unknown НЕ эквивалентны.
Service clarification сохраняет choices2–3 unique active service refs;
term/parameter не требуют бессодержательного choices:[].

Execution completed content:
existing exact brand/service owner → найденный approved block публикуется;
если такого ответа нет → existing ordinary prose materialization;
нет пригодного ответа → existing per-part unavailable, не выдуманный текст.
Это предложенное изменение ошибки missing content: structurally valid request
может не иметь ответа, вместо прежнего rejection всего model result. Этот пункт
ТРЕБУЕТ OWNER СОГЛАСОВАНИЯ; malformed root JSON не становится valid part.
Existing _d2_information_blocks1779 уже умеет gap без prose, но новая structural
граница сделает этот путь достижимым шире. Не объявлять это отсутствием поведения.

Короткие примеры будущего ordinary wire (catalog placeholders, НЕ live payload):
Osstem:
{"outcome":"dialogue","blocks":[{"kind":"content","brand_id":"<osstem_id>"}]}
Цена Osstem:
{"outcome":"dialogue","blocks":[{"kind":"price","target":"service:<service_id>","brand_id":"<osstem_id>"}]}
Price_detail с тем же брендом применяет ту же действующую precedence; отсутствующая
цена не подменяется ценой альтернативного бренда. New availability не используется.
Osstem+адрес:
{"outcome":"dialogue","blocks":[{"kind":"content","brand_id":"<osstem_id>"},
{"kind":"contact","contact_fields":["contact_address"]}]}
Обычный ответ без обязательной ссылки на документ:
{"outcome":"dialogue","blocks":[{"kind":"content","content_text":"<ответ из FullContext>"}]}
Source-aware ordinary ответ может дополнительно иметь content_ref и section refs.
Genuine service уточнение:
{"outcome":"dialogue","blocks":[{"kind":"price","clarification":
{"missing":"service","choices":["service:<id1>","service:<id2>"]}}]}
Information clarification:
{"outcome":"dialogue","blocks":[{"kind":"content","pending_question":"<неотвеченная задача>",
"clarification":{"missing":"term"}}]}
Age/context/payment, volume/count/jaw, facts/policy IDs и offer selectors остаются
в нужных видах операций. Короткие примеры не являются сокращённой полной schema.

### 39.3. Target replacement: значение, readers, removal

Одна native scalar reference выбирается из списка captured tenant snapshot;
нет нового файла KB, regex по user text или второго semantic registry.
Derived index связывает exact ref с уже существующей сущностью, проверяет scope.

| Путь | Допустимая native target и смысл |
|---|---|
| content/price/detail/policy/booking | service:<id>, topic:<id>, unresolved, либо отсутствие там, где допустимо сейчас |
| doctors | Только active service:<id> |
| commercial_fact | service/topic, clinic либо unresolved с прежними pending restrictions |
| DiscussionScope | Только service/topic; clinic/unresolved запрещены |
| service choices | Только active service refs; после click тот же native target |
| offer ID/ordinal | Отдельный прежний selector; ref не подменяет offer/ordinal |

clinic не совпадает с topic:clinic; unresolved не совпадает с отсутствием.
Volume:null vs {extent:unknown} сохраняется. Unknown service/topic, inactive service,
unknown brand, missing price и foreign source не объединяются в один outcome.
Ссылка не гарантирует верного model выбора существующей сущности.

Прямые заменяемые readers/constructors:
- contracts/d2_dialogue_result.py: ServiceTarget/TopicTarget/ClinicTarget/
  UnresolvedTarget, Target union, ScopedOperation и DiscussionScope properties,
  DoctorsOperation.target, CommercialOperation.target, clarification/price validators.
- core/d2_dialogue.py:_volume_price_task; _run_reserved_d2_dialogue_turn:
  service/doc/price/detail known-task constructors, price-policy discussion scope,
  reference target branches, scope equality и commercial carry joins.
- core/d2_snapshot_sources.py:build_d2_document_task и source-target binding.
- core/response_plan_materialization.py:resolve_d2_operations commercial scope,
  selected frozen price DiscussionScope; _discussion_descriptor,
  _d2_price_scope_decision и content scoped resolution.
- contracts/d2_session_context.py:clarify_task и projected discussion scope;
  contracts/response_plan.py и contracts/response_plan_session.py captured scope
  on parts/actions: сохраняют единственную новую reference, не вторую old форму.
- prompt/derived catalogs/schema: target examples, choices, known-task input.
- core/one_call_envelope_protocol.py D2 parser сразу выдаёт новый domain.

Из ordinary model path удаляются old target classes/unions и reachable old
constructor/type branches. service_id/topic_id как readonly доступ к native ref
может сохраниться, но не создаёт old targets. Старый non-D2 legacy protocol не
удаляется автоматически; доказать отсутствие нового D2→legacy semantic adapter.

### 39.4. Ordinary identity: producer/consumer карта

Три разных identity НЕ смешивать:
HTTP request_id/replay receipt — прежний server key;
ordinary block key — серверный rN по исходной позиции;
known-task echo — уже назначенный сервером key, модель только повторяет.

Исполнение назначает key при первом обходе полного blocks ДО booking skip,
first-price deferral и разделения exact/content/commercial/detail. Каждая
дальнейшая рабочая часть несёт пару key+native operation. Это transient data
текущего вызова, НЕ новая persisted memory и не wrapper поверх старого domain.
Не добавлять request_id в raw payload и не валидировать обогащённый JSON старым
D2DialogueResult. Existing native executor functions напрямую принимают key
от server owner вместо чтения model operation.request_id.

| Producer/consumer | Прямое изменение / сохранённая связь |
|---|---|
| contracts/d2_dialogue_result.py Operation/shape | ordinary request_id и duplicate model IDs удаляются; ordered blocks authoritative |
| core/d2_dialogue.py:_run_reserved_d2_dialogue_turn | enumerate complete blocks once; exact_text/parts/deferred/contact/booking и render_order сохраняют исходный key |
| core/response_plan_materialization.py:resolve_d2_operations | коммерческие, price/content/detail scopes и failures получают bound key, не перенумеровывают filtered tuples |
| _d2_information_blocks / _d2_price_detail_block / _d2_price_scope_decision | key передаётся к information/price/detail/failure, UI source_request_id остаётся тем же |
| core/clinic_policy_resolver.py:resolve_clinic_policy_operations | policy decisions/ledger/active_booking связываются server key, не model ID |
| core/d2_snapshot_sources.py:build_d2_clinic_policy_response/build_d2_clinic_policy_fact_block | key для exact response и policy decision join задаёт вызывающий executor |
| core/d2_lead_bridge.py:resolve_d2_booking_lead_entry | booking_request_id использует bound source key; lead effect/PII rules прежние |
| core/response_text_renderer.py:render_response_parts | result IDs/order остаются; модельной operation identity не читает |
| core/d2_completion_context.py:_project_pair | join опубликованных blocks/parts по server key; receipt HTTP key не меняется |
| contracts/response_plan.py part/result validators | unique/failure/deferred/order checks для server result остаются |
| contracts/response_plan_session.py action validators | UI source_request_id остаётся server-owned authenticated reference |
| core/d2_dialogue.py:run_d2_dialogue_turn | price volume/source/action joins читают frozen completion IDs, не ordinary model payload |
| known-task validate_d2_payload | expected server key/count проверяются; создаётся новый native completed domain, не old wire |

Сценарий filtered/deferred: blocks [booking, content, price, price] получают
[r1,r2,r3,r4]. Published text r2, first price r3, deferred r4; booking r1 не
превращает r2 в r1. Renderer/next history/UI должны сохранить это равенство.

Pending clarification — конкретная согласуемая native форма того же clarify_task:
{"request_id":"r3","operation":{"kind":"price_detail","price_detail_aspect":"includes",
"clarification":{"missing":"service","choices":["service:<id1>","service:<id2>"]}}}
request_id — существующая identity, теперь server-owned по исходной позиции;
operation — native unfinished block нового ordinary domain без model-generated ID.
Wrapper разделяет владельцев identity и meaning. Это изменение формы одного
существующего слота, не новая память/queue/state или model discriminator.
Owner GO2026-10-10: после подробного объяснения server number + native task
в existing slot владелец ответил «Ладно делаем». Точная server-bound wrapper
форма39.4 согласована. Повторное согласование этой формы не требуется.
Это design GO, а не обход последовательности3А→3Б→3В или разрешение любых states.
Не использовать пример placeholders как клинически выбранные реальные alternatives.

Прямой путь записи/исполнения:
1. _run_reserved_d2_dialogue_turn назначает key ДО любой фильтрации. Первая
   активная clarification получает {request_id:key,operation:native_pending}.
   Остальные остаются deferred, не становятся очередью автоматического исполнения.
2. _commit_non_price_d2_turn записывает это в прежний clarify_task; clarify_pending,
   TTL и очистка остаются прежними. D2SessionState и D2OrdinarySessionContext читают
   одну server-bound форму; project_d2_session_context не интерпретирует её смысл.
3. Service click проходит существующие tenant/revision/ownership проверки, читает
   clarify_task.operation и проверяет выбранную услугу из clarification choices.
   Меняются только native target и завершённость этого уточнения.
4. Kind, detail aspect, brand/volume/payment/age/context и исходный информационный
   pending_question сохраняются. Executed part/known-task echo используют r3,
   даже если остальные blocks раньше отфильтрованы.
5. Price/detail выполняются без модели; content даёт один narrow known-task call
   для объяснения исходного вопроса по выбранной услуге. Модель не выбирает kind
   заново. Старый task_type.model_validate с **pending.model_dump и {type,id}
   в d2_dialogue688–692 удаляется; legacy wire не восстанавливается.
6. Свободный текст после уточнения — ordinary meaning path. Input содержит native
   pending целиком, включая исходный вопрос/aspect и варианты. Модель понимает
   продолжение/поправку/новую тему; сервер НЕ вставляет old kind в произвольный
   новый ответ. Новые ordinary IDs локальны для нового хода. Между текстовыми
   ходами не добавляется автоматический identity-link или второй классификатор.

Приёмка той же кнопки услуги для разных задач:
- price → выбранная услуга → price card, не includes;
- price_detail/includes → выбранная услуга → exact includes, не новая цена;
- price_detail/stages → выбранная услуга → exact stages;
- content → выбранная услуга → объяснение исходного pending_question, не цена.
Это общая task conservation, не словарь сценариев коронки/имплантации.
Коронка «на свой зуб/на имплант» — объясняющий пример, не новая KB или policy.
Tests должны использовать реально существующие active services из snapshot.

Минимальные future offline guards: все четыре pending формы JSON/SSE;
third-position r3 через filter/deferred/click/completion/history; price/detail
zero provider, content one known call и reject wrong echo; foreign/stale/TTL,
choices validation/replay/clear; fake input полного pending и независимой новой
темы. Existing test_d2_clarification_scope_http сохраняет scope/brand/payment;
test_d2_operation_unification — старые формы storage. Их assertions не ослаблять
без объяснения direct replacement и эквивалентной проверки нового native slot.
Live понимание свободного текста отдельно на3Б; fake не аттестует Qwen/DeepSeek.

Не удаляются HTTP request_id, D2CompletedTurn identity, D2DialogueStore replay,
D2DialogueReceiptRef, response/UI source IDs и known-task echo. Глобальная замена
всех строк request_id была бы поломкой контрактов, не упрощением.

### 39.5. История фактически показанного диалога

Пара получает ordered опубликованные body blocks ИЗ СОХРАНЁННОГО COMPLETION.
Не делать lookup современного approved_text по source_id вместо frozen ответа.
Обычная assistant prose отдельно; published exact text отдельно с source/outcome;
card отдельно с captured rows/conditions/includes/stages и выбранным offer.
Не складывать financial text в ordinary assistant_text и не пересчитывать суммы.
source/outcome поясняют published/excluded/unavailable, не заменяют текст.
Не создавать событие/summary store или модель пересказа.

Конкретная обязательная пара Osstem:
patient_text: А Osstem у вас есть?
published_exact: source=brand_policy:<id>, outcome=answered,
text=<дословный display_text опубликованного exact block с приглашением продолжить>.
Следующее Расскажите/Да интерпретирует модель по этой паре, без phrase handlers.

| Класс опубликованного результата | Откуда брать содержание / граница |
|---|---|
| model prose | information_blocks.display_text с publication=model_prose, фактический порядок |
| brand/service alternative | exact block display_text + matching part.source_results; approved invitation целиком |
| clinic policy, включая отказ | exact/policy display_text, matching part и policy IDs; не только список IDs |
| unknown reference/brand, generic gap | тот же exact/failure display_text, даже при пустом source_results; требуется доказать ordinary origin |
| off-topic | _run_reserved OffTopicOperation branch exact_text; не маскировать как предыдущую тему |
| contacts/doctors | published contact/exact blocks; clinic contacts не patient contact intake |
| price/detail/card | captured financial typed blocks и facts/conditions; UI selected offer из existing authenticated action |
| commercial/promo/consultation additions | реально published finalized blocks, не все доступные fact IDs каталога |
| clarification/deferred/unavailable | displayed question/deferral/gap и unfinished task; не выдавать их за ответ |
| medical admin | published terminal/handoff из completion; сохранённый medical subject и privacy |
| lead/pause/name/phone | existing lead owner; PII/intake данные НЕ ordinary history |
| transport/root parse failure | нет успешного completion — не создавать fictitious answered pair |

Финансовый approved_text альтернатив допускается только как exact structured
publication; это предложенное расширение model input, требует owner GO.
Нельзя проецировать все exact_text_blocks: mixed booking создаёт generic
reference/clarification (d2_dialogue972–983), а generic gaps имеют тот же kind.
Existing source IDs достаточны для source-bound cases, недостаточны для universal
origin claim. ОТКРЫТЫЙ GATE: для mixed lead нужно явно разделить происхождение
в том же completion у producer. Кандидат — изменить server-owned part kind для
lead/intake части вместо generic reference; это новый внутренний enum value,
не модельный kind/state, но требует отдельного owner согласования. Без него
не обещать полный safely-all projection и не вводить фильтр по тексту/фразам.
При отклонении такого изменения надо спроектировать иной доказуемый existing-data
путь, а не молча исключить целый mixed turn вместе с полезной карточкой.

Оба источника обрезания включены в removal list:
core/d2_completion_context.py:_project_pair assistant_text[:limit];
core/d2_dialogue.py:_commit_non_price_d2_turn patient_text=_bounded_d2_text(...).
Нельзя восстановить уже обрезанный patient_text из несуществующего полного receipt.
Новые turns должны фиксировать безопасный вопрос полностью в existing receipt;
старые local incomplete receipts не аттестуются как magically repaired.

Candidate input сохраняет: whole approved corpus, все business catalogs,
current safe user text, ordered completed pairs, discussion_scope,
shown/selected offers, explicit pending/known task и необходимые source outcomes.
Исключает только model-facing session_key/SID, revision, timestamps,
receipt/fingerprint IDs, suppression ledger. Они остаются на сервере.
Финальный exact removal/preservation list ещё нужно согласовать.

### 39.6. Неохваченные обязанности — явный статус

- content_ref остаётся OPTIONAL source attribution/UI metadata. General content
  пример без него разрешён. Удалить prompt blanket требование возвращать документ
  на каждый grounded answer, сохранив source-auth проверки, sections и UI.
  Модель выбирает документ для source UI, но отсутствие ref не ломает полезную prose.
  Не выводить ref из prose и не добавлять второй document selector.
- Target для connected general prose OPTIONAL; для typed price/doctors/facts
  нужны точные сущности. Не требовать одновременно target+doc+text каждому ответу.
- JSON Schema/Python должны совпадать по completed/pending/null формы. Dynamic
  tenant/reference checks неизбежно выполняются executor по captured data;
  не путать их со скрытыми purely structural правилами.
- Рассрочка: general useful explanation, direct requested exact fact и payment
  stage breakdown — разные requested actions, не три попытки одной задачи.
  У текущего D2 есть свои exact-operation инструкции. Cursor ссылки126–141
  относятся к ONE_CALL_TYPED_ENVELOPE_INSTRUCTIONS, которые build_d2_d1r_messages
  НЕ включает: one_call_contract_header152–157 только version/model markers.
  Это не доказательство live тройного prompt. Однако actual D2 messages нужно
  свести к одной недублирующей meaning→operation таблице и проверить конкретные
  общие payment questions/условия/«этапы оплаты» на3Б. Не claim all existing
  payment semantics resolved только удалением старого unreachable prompt.
- Повтор brand/volume на продолжении остаётся model meaning responsibility;
  новый автоперенос кодом не разрешён. Readable selected-offer/scope уменьшает
  двусмысленность, но не гарантирует inference. Отдельно проверять «А рассрочка?»
  после смены бренда, topic switch, явный новый бренд и настоящую неоднозначность.
- Ordinary model-generated IDs убрать только после focused proof карты39.4,
  включая pending slot. Пока это candidate removal, не выполненное упрощение.
- Auto marketing, price/detail exclusions и CTA остаются product policies,
  не удалять их попутно под видом свободного диалога.

### 39.7. Бюджеты и приёмка — до запуска эксперимента

Три пары и TTL30min сохраняются. Предложение whole-turn budget: newest complete
pair сохраняется полностью в пределах существующих ingress/output bounds;
ещё две старые пары добавляются целиком, если помещаются в согласованный общий
budget. Нет обрезания внутри текста; oversized newest turn требует явного
решения, не silent drop. Точное число budget и overflow НЕ выбраны/не согласованы.
Output1024 tokens при допустимых4000 chars/нескольких blocks также требует
явного candidate budget, сопоставимого между Qwen/DeepSeek. Не обещать closure
этих числовых решений документом без owner GO.

3Б пока НЕ READY. Pending identity теперь имеет concrete candidate39.4,
и explicit owner GO2026-10-10. Wrapper больше не открытый approval gate.
Сначала закончить lead origin representation,
выбрать whole-turn/output budget, согласовать wire/model input/error semantics.
Далее temporary isolated harness с одинаковым synthetic input и facts:
current vs candidate, Qwen vs DeepSeek Flash disabled thinking. Сравнивать
structure/meaning/completeness/continuation/facts/latency/tokens, не лишь parse200.
JSON mode/strict отдельная ось; root array не извлекать догадками. Новый hard
call/cost budget ещё не дан. Credentials locally prepared, API live не проверен.

Focused review после REJECT проверяет именно findings/removal maps, не новый
полный аудит и не повторную историю108offline. Перед implementation Cursor
должен получить complete executable design и отвергнуть new-to-old adapter,
retained hidden structural validation, newkind availability, phrase handlers,
parallel memory и потери цельного диалога. Adverse matrix включает mixed booking,
unknowns, compound/deferred order, genuine clarification, next «Да/Расскажите»,
Nobel→адрес→includes, смену бренда→рассрочка и два исторических предмета.
Astra пересмотрела availability recommendation и поддерживает optional completed
content + existing exact owner; её консультация не заменяет owner decision.
Runtime/tests/KB не менялись. Provider/live/browser/SMTP0, staging пуст,
commit/push этих двух draft документов не делались.


### 39.8. Контрольный свободный FullContext, owner GO 2026-10-10

Owner после обсуждения «всё дать модели и общаться» разрешил добавить такой
контроль в эксперимент; после annotation также подтвердил task conservation
через уточнение. Это GO на preparation/design, не отмена этапов3А→3Б→3В и не
числовой hard live budget. Runtime/KB/основная модель не переключаются.

Контрольный вариант получает те же synthetic patient questions, frozen factual
corpus/catalogs и те же полные readable history pairs, что candidate structured
variant. У control нет обязательных operations/IDs/schema и обязанности рисовать
карточки: он пишет естественный ответ. Clinical/admin/privacy ограничения
сохраняются. Не объявлять diagnostic prose финансовым publication path бота.

Различать:
A — текущий договор и его текущий input: локальная baseline точка;
B — тот же текущий договор с целой readable history: вклад истории;
C — свободный ответ с той же readable history: вклад командного договора;
D — proposed compact native contract с той же history: будущая замена.
Не менять history, facts, output budget и instructions одновременно и затем
приписывать эффект модели. Сравнение B/C не делает current runtime автоматически
пригодным; C не доказывает точность карточек или authentication. D запускается
только после design GO. Выбор Qwen/DeepSeek — отдельная ось.

Предварительный различающий набор, без вызовов:
- Osstem первый самостоятельный вопрос: структурная упаковка и правильный факт.
- КТ→Osstem approved invitation→Расскажите: правильный referent, не КТ.
- То же приглашение→Да: используется предыдущая фактическая реплика.
- Typed includes task→genuine service clarification→выбор: сохранение includes.
- Карточка Nobel→адрес→Что входит в Nobel: offer/service binding.
- Selected brand→А рассрочка: нужный смысл и scope без автопереноса кодом.
- Осstem+адрес: полнота обеих частей, ошибка одной не скрывает другую.

Набор и subsets/call count сначала фиксируются, а не автоматически7×4×2.
Использовать frozen synthetic history: цена/бренд/приглашение берутся из demo
approved фактов, не генерируются предварительными платными calls и не содержат
реальные logs/личные данные. Отдельно отличать одношаговую diagnostic проверку
от end-to-end новых диалогов, где ошибки предыдущего хода влияют на следующий.
Метрики: формат, предмет, полнота, continuation, нужные/лишние уточнения,
факты/claims, calls/tokens/latency. Ожидания фиксируются до response.
Если C верен, B неверен — evidence в пользу влияния договора при одинаковой
истории. Если B и C верны, A неверен — evidence в пользу input/history. Одна
попытка не является надёжным доказательством; повторы требуют общего hard budget.
DeepSeek Flash thinking disabled, Qwen параметры отдельно зафиксированы;
retries0, failures входят в cap. Provider calls пока0. Хранить artifacts вне Git,
ключи не читать в вывод/отчёт. Free control не встраивается в runtime как fallback.


### 39.9. Пакет перед 3Б — owner GO 2026-10-11

Pending wrapper39.4 уже согласован; не спрашивать его повторно.
Owner GO2026-10-11: ответ «Да» на общий пакет в разговоре разрешает whole3pairs
без обрезания фраз, ordinary server identity вместо model IDs, отдельную
server-owned метку служебных lead parts, output4096 и per-part gap с сохранением
остальных ответов. Это design GO для подготовки3Б, не runtime replacement,
не разрешение paid calls и не blanket approval всех исторических предложений.
Технические изменения должны оставаться в границах39.3–39.6 и TargetContract§3.

Lead origin: использовать новый server-owned result part kind=lead в существующем
D2ResolvedRequestPart, без нового поля/памяти/модельного kind. Назначает producer
по уже исполненной lead ветке, не classifier и не история по тексту.

| Existing producer | Предлагаемый результат / history |
|---|---|
| d2_lead_bridge._name_prompt_response/_phone_prompt_response | lead: name/phone requests и повторные slot prompts; не ordinary history |
| resolve_d2_lead_pre_provider resume/retry/continue | lead: исполненный intake prompt, прежние UI/auth rules |
| resolve_d2_lead_pre_provider cancel/defer/submitted | lead acknowledgement из того же owner; исключён из ordinary history, lead owner знает исход |
| pending_interrupt и paused intake prompt | lead; ordinary вопрос после verified answer-ref идёт отдельно прежним safe boundary |
| resolve_d2_booking_lead_entry booking_blocked | PUBLIC policy/reference, approved text/source остаётся видимым в history, не помечать автоматически lead |
| booking policy gap/unclear без запуска intake | PUBLIC authored gap, не путать с повторным вопросом имени/телефона |
| mixed booking siblings + collecting_name/phone | обычные siblings сохраняются; добавляется отдельный lead part с его server key |
| apply_d2_lead_pause_ui | меняется UI существующей lead flow; ordinary answer не перекрашивается целиком в lead |

_plain_answer сейчас ставит attribution_kind=lead всему ответу, а mixed merge
помещает generic reference/clarification в exact_text. Это presentation-признак,
не достаточная provenance. Не использовать его как whole-turn history filter.
В revised result источник intake на уровне части задаётся её producer; публичный
policy/gap берёт origin из booking outcome, не из слов отображаемого текста.
Для public booking policy сохранить источник в existing source_results/IDs.
Нужны direct callers updates _plain_answer и mixed merge972–983, validators
contracts/response_plan.py, render_response_parts и history projection.
Renderer читает явный lead kind и ставит prompt после siblings; удалить нынешний
trailing generic reference/clarification эвристический цикл. History исключает
только intake parts; не теряет карточку/адрес в mixed response. Новый enum согласован в пакете owner GO2026-10-11.
This change is origin fidelity, not model routing expansion.

History candidate для сравнительного эксперимента: прежние последние3пары,
TTL30min, каждая пара целиком, без отдельного character cap/нового отбора старых
пар по бюджету. Это минимальный removal двух1000slices без новой soft-budget
политики. Current discussion и card selection сохраняются по прежним правилам.
Provider-facing projection включает safe user text, ordinary prose и ordered
published exact/card data; policy alternative invitation находится в самой паре.

Это count bound, НЕ доказанный hard token bound. До каждого isolated live case
harness обязан измерить полный prepared input и проверить применимость реального
model/endpoint context limit с reserved output. Если case выходит за range —
не вызывать provider, не обрезать реплики и не делать fallback; показать конкретный
непомещающийся case. Исполнимый method/tokenizer/endpoint limits фиксируется в
3Б harness перед call budget GO; approximate chars не выдавать за точный token count.
Для unrestricted runtime3В эта overflow граница требует отдельной приёмки: нельзя
распространить evidence малого набора на любой длинный input.

Output candidate4096 tokens на вызов, одинаковый у Qwen/DeepSeek и сравниваемых
вариантов. Current baseline1024 выделяется отдельной budget axis, а не скрыто
сравнивается с4096 вместе с другим prompt. Существующий cap4000Unicodechars
НА CONTENT BLOCK сохраняется; новый суммарный cap прозы не добавляется.
Truncated/invalid root не чинить repair/retry. Бюджет повышает доступное место,
не гарантирует верный смысл или JSON.

Пакет owner decisions теперь конкретен: native pending wrapper (уже GO),
lead result provenance enum, whole3pairs/nocharcut window, output4096,
missing completed content как structurally valid/per-part gap, canonical refs,
ordinary server identity и точный input preservation/removal list39.3–39.6.
Пять перечисленных выше решений согласованы; подготовка3Б candidate разрешена.
Смысл canonical refs не меняется этим GO: применять только уже согласованные
ответственности и домены39.3, без самостоятельного расширения product semantics.
Hard live call/cost budget — отдельно по конкретному subset, до первого вызова.
Не превращать каждую routine technical detail в отдельный permission round.

Current evidence этого documentation checkpoint: Astra consult; staged empty,
только2docs WIP, runtime/KB/tests неизменны, provider/live/browser/SMTP0.
Diff check чист. Никакого architecture runtime PASS не объявляется.


### 39.10. Первый различающий subset 3Б — выполнен 2026-10-11

Классификация: изолированный live diagnostic, не runtime-изменение. Runtime
baseline340fd77 остаётся нетронутым. По GO39.11 выполнены 24 попытки на модель
(12 ячеек × 2 прогона), retries0; все 48 запросов получили ответ. Остаётся
по 6 попыток в согласованном лимите. Денежный cap отдельно не задан.

Три frozen synthetic cases, одинаковые approved facts и ожидаемые смыслы:
1. «А у вас есть Osstem?» без истории. Ожидается отсутствие бренда и доступные
   альтернативы из approved demo данных; не отсутствие предмета вопроса.
2. История КТ, затем вопрос Osstem и фактически опубликованное приглашение
   рассказать про доступные бренды; новый вопрос «Расскажите». Ожидается
   продолжение последнего приглашения, не возврат к КТ.
3. «Какие корейские импланты у вас есть и где вы находитесь?» Ожидаются обе
   части по approved данным. Оценивать формат, оба предмета, полноту и факты
   отдельно; один верный фрагмент не является PASS всего ответа.

Каждый case: A/B/C/D из39.8 × Qwen/DeepSeek =8 attempts; всего3×8=24.
Один повтор на ячейку отсутствует: это диагностический screening, не оценка
частоты ошибок и не доказательство надёжности. Повторы — только новым subset GO.
Для этих24 output4096 одинаков у всех вариантов. A сохраняет current input и
current contract, но output переопределён на4096: называть его controlled baseline,
не exact runtime baseline1024. Влияние1024 отдельно этим subset не измеряется.
Температура, facts, история B/C/D и остальные поддержанные параметры одинаковы;
различия API/support явно записываются, а не скрываются под «одинаковые условия».

Подготовка исполнимого harness требует следующего конкретного allowlist до edits:
изолированный экспериментальный runner и synthetic fixtures; runtime files не
редактировать. Проверить существующие runners перед созданием нового, не
дублировать provider adapters и не добавлять candidate→old runtime converter.
Ожидания/frozen inputs фиксируются до responses. Raw provider artifacts вне Git,
ключи не выводятся. Offline подготовка не доказывает живое понимание.

Этот subset НЕ покрывает end-to-end verified clarification click, selected card
после адреса, lead flow или unrestricted runtime overflow. Сохранение задач и
точных карточек проверяется отдельным минимальным offline набором при3В;
живые multi-turn проверки требуют отдельного bounded subset, не объявлять их
закрытыми по трём случаям. Эксперимент не подменяет готовность всех ценовых карточек.


### 39.11. Hard provider budget — owner GO 2026-10-11

Owner: «Можешь брать больше вызовов если нужно я даю добро. До30 на модель можно».
Разрешено до30 attempts Qwen и до30 attempts DeepSeek, максимум60 суммарно,
для3Б comparison39.8–39.10 и нужных диагностических повторов/дополнительных cases.
Это отдельное live GO, не runtime replacement, не переключение local widget.
Не переносить неиспользованные attempts одной модели в другую.
Ошибки/timeouts/повторы включены в лимит; automatic transport retries0.
Начальный subset24 был запущен в двух прогонах: израсходовано24 attempts на
модель, осталось6 на Qwen и6 на DeepSeek. Не требуется тратить остаток.
Все attempts считаются одним cumulative ledger для этого approved experiment;
restart runner не обнуляет бюджет. Считать также неуспешные отправленные запросы.
До live проверить provider capability/context window и prepared inputs; если
измерение недоступно, не выдавать approximate count за exact и не заявлять
доказанную применимость. Thinking DeepSeek disabled. Ключи/сырые payloads вне Git.
Отдельный денежный cap owner не задавал: не придумывать денежное разрешение,
не делать пополнение баланса и не расширять scope за пределы этих attempts.
Budget GO39.11 использован для указанного screening. Остаток:6 attempts/model.
Текущие harness offline проверки прошли; live results записаны в§41.


## 40. 3Б — isolated comparison harness, preparation checkpoint 2026-10-11

Classification: experimental implementation, not runtime architecture simplification.
Baseline340fd77, branch codex/model-price-experiment; origin/main/merge-base efa3f77.
Owner GO39.9/39.11; allowlist expanded before edits to these exact paths:
- docs/tasks/DEMO_D2_INTERFACE_TASK.md
- docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md
- scripts/d2_context_candidate_protocol.py
- scripts/experiment_d2_interface_comparison.py
- tests/test_d2_interface_comparison_offline.py
Foreign prototypes preserved; staging empty; no KB/runtime edits/commit/push.

Candidate native9-kind wire directly typed in scripts, including completed vs
unfinished content alternatives, canonical target refs, no ordinary model IDs.
Its parser returns native objects, never old operations; no materialization,
offer selection, server memory, model-output repair or second semantic call.
Shared DiscussionVolume preserves baseline domain constraints. Cross-field and
source checks not fully expressible in schema are domain checks, not evidence
of provider structured-output failure. This is trial removal of wire duties,
not proof that the reachable bot dependency was removed (that belongs to3В).

A actual current prompt/input, output4096 controlled baseline. B same exact
system and non-history context, replacing ONLY published history text from
frozen completions. C/D same B user segment and byte-identical factual suffix.
C free prose; D full candidate wire. No tiny schema tailored to the3questions.
History prepared using synthetic offline turns. The Osstem turn uses the
owner-provided observed widget answer inviting the visitor to hear about
Implantium/Impro/Nobel differences; this is frozen dialogue context, not a new
clinic claim or a content approval. No paid pre-generation, patient logs, or live
bot state.
A/B current parser; D direct native parser/reference checks; C manual prose rubric.
No candidate→old converter, endpoint import, HTTP route replacement or auth bypass.

C/D instructions are a manual compact interface rewrite. Mapping of preserved
product obligations: medical/admin and clinic boundary; factual/no invention;
identified direction overview and volume/brand preservation; independent
questions/order; age/payment semantics; scope-sensitive follow-up; inactive
services/brand precedence; contact scope; doctors ownership; commercial scope;
privacy/no PII collection. Native wire requirements are separately named.
These are NOT byte-identical semantic paragraphs to B: B/C/D measures the
interface+instruction package, NOT pure JSON-format causality. Never conclude
that any structured answer intrinsically prevents free dialogue from these cells.
All9kinds remain exposed; no extra Osstem/Расскажите hint in candidate prompt.

Live: official documented1M windows for qwen3.8-flash and deepseek-flash.
Model/endpoint configuration checked before calls; DeepSeek thinking disabled,
Qwen enable_thinking false; supported generation settings temperature0/output4096.
A/B/D json_object, C unrestricted prose; strict schema transport not mixed in.
Official offline estimators: QwenCloud documented o200k_base and DeepSeek
cdn.deepseek.com/api-docs/deepseek_v4_tokenizer.zip. These are ESTIMATES, not
exact API counts. Measured complete serialized messages with 4x estimate +
32768 template reserve +4096 output, must remain under1M before calls.
This technical screening margin is not a proven hard bound for3В runtime.
Exact usage is reported from provider response. No truncation/fallback if
estimator unavailable or margin fails. Sources:
https://docs.qwencloud.com/developer-guides/run-and-scale/token-counting
https://www.alibabacloud.com/help/en/model-studio/qwen3-8-flash
https://api-docs.deepseek.com/quick_start/token_usage/
https://api-docs.deepseek.com/quick_start/pricing/

Cumulative ledger outside Git:30attempts/model, reservation persisted BEFORE
transport, exclusive lock, atomic replacement, retries0. Re-running existing
job skips it; explicit repeat consumes remaining budget. No counter reset on
new artifact directory. Auth/quota failure stops that provider's batch. All
raw synthetic payloads/results and isolated SQLite are outside repository.
No changes to .env, widget runtime provider, prices or approved formulations.

Preparation evidence:12cells/model, largest prepared input237069UTF8bytes,
provider0. Official tokenizer preflight prepared outsideGit, no patient data;
max estimated input48,140 Qwen /54,153 DeepSeek. The script applies an explicit
4× estimate +32,768 template reserve +4,096 output margin, resulting maximum
screening reserves229,424 /253,476 respectively. Estimates are not API counts.
45 offline tests passed in5.99s, including budget restart/cap/failure/lock and
published invitation continuation. The sandbox run had3 Windows PermissionError
failures at atomic temp rename (42 passed); outside sandbox all45 passed. Not a
baseline bot regression.
No browser checks/SMTP, no runtime architecture PASS or live dialogue PASS.
Independent Checker: scoped PASS after tracing preparation/parser/transport/
ledger paths; canonical topic binding fixed. Owner has approved up to30 calls per
model and explicit transmission of synthetic demo-clinic facts to Qwen/DeepSeek.
Live screen can start within that hard cumulative cap; no further approval round.


### 41. 3Б — результаты первого live comparison, 2026-10-11

Отправлены synthetic demo facts и три истории в Qwen3.8-Flash и DeepSeek-Flash;
пользователь отдельно разрешил передачу этих данных. По каждой модели выполнены
12 ячеек A/B/C/D и их один повтор:24 attempts/model из разрешённых30. Итого48
ответов получено, timeout/HTTP/provider failures0, automatic retries0. Реальные
API usage: Qwen945,174 input +3,435 output tokens; DeepSeek1,142,752 input +3,844
output tokens. Raw ответы и полный локальный summary находятся вне репозитория.
Вход содержал только frozen demo facts/synthetic dialogue, без patient logs/PII.

A/B — единственное различие для follow-up case: в A assistant_text последнего
показанного ответа пуст; B получает фактический ответ с приглашением рассказать
про Implantium/Impro/Nobel. C — свободная проза с полной историей; D — компактный
native protocol с той же полной историей. Температура0, output4096, retries0.
B/C/D меняют interface instructions пакетом; разница B/C не изолирует одну только
JSON-форму.

- «Расскажите»: Qwen A дважды не попал в вопрос (один раз ответил о КТ, один —
  о клинике); DeepSeek A дважды вернулся к КТ. B обе модели рассказали про системы
  имплантов в обоих прогонах. Это evidence в пользу передачи видимой реплики в
  provider history именно для этого frozen диалога.
- C: DeepSeek дал обзор в2/2; Qwen — полноценный обзор в1/2, в другом вместо него
  попросил уточнить объём. Свободный текст сам по себе не устраняет нестабильность.
- D: Qwen дважды вернулся к КТ. DeepSeek оба ответа не прошли domain validation:
  выбрал незарегистрированные section refs, а один ответ был ещё и без текста.
  JSON object и принятие части D результатов parser-ом не гарантируют правильную
  тему: семантика и каталожные значения всё ещё расходятся.
- Прямой Osstem: DeepSeek prose A/B/C правильно сообщает об отсутствии Osstem;
  D содержит тот же смысл, но дважды использует незарегистрированный topic ID.
  Qwen стабильность не показал: C/D ответили верно, A пустой, B один из двух
  завершён, другой запросил ненужное уточнение.
- Двойной вопрос «корейские импланты + адрес»: обе модели во всех вариантах
  распознали Implantium; A/B/D выбрали отдельное поле contact_address. В C обе
  модели не назвали конкретный адрес. Поле D проверено только структурно,
  кодом оно не исполнялось.

Из18 structured outputs у Qwen typed/domain parser принял14; у DeepSeek12.
Отказы: неполный explanation или несовместимые target/section IDs. Это реальные
response validation failures, а не transport failures. Частый target tomography
в D Qwen проходил структуру и был семантически неверен.

Вывод ограничен3 synthetic cases и2 samples/cell. Он не оценивает частоту ошибок
во всём боте, не аттестует текущую runtime архитектуру и не разрешает подключать
D к виджету. Данные напрямую показывают конкретный дефект A: текущая projection
иногда отдаёт модели пустой assistant turn, хотя пользователь видел приглашение.
До новой архитектурной задачи нужно separately decide/implement the agreed
history projection change; не обобщать этот screening на все dialogue types.
Остаток hard cap —6 attempts/provider; дополнительный screening не обязателен.

## 42. Свободный разговор и общая история — owner GO 2026-10-11

Классификация: **архитектурное упрощение**, реализация начинается после проверки опубликованного checkpoint данных/документов в Cursor и виджете и подтверждения владельца (последующее решение об остановках). Основание: прямое поручение владельца «Давай зафиксируем всё это… И начинаем вот это всё делать» после подробного 12-пунктного плана. Канонический порядок — актуальный верх Roadmap. Сохраняется единственная таблица ответственности Target Contract §3.

До → после → удаляемая зависимость:
- Обычный вопрос требует информационных kinds/ID и может попадать в кодовый шаблон → связное объяснение по MD → удалить обязательность информационных commands и их старые достижимые ветки, без нового-to-old adapter.
- Следующий вызов видит только выбранные категории текста и теряет показанное предложение продолжить → читает достоверный завершённый разговор из существующего receipt → удалить перечни специальных разрешённых происхождений ответа. Новая memory/summarizer/model call не создаётся.
- Врачи дублируются в MD/JSON и шаблонах → один фактический источник MD для обычного разговора → удалить старых потребителей и каталог вместе, а не скрыть их prompt-инструкцией.

Реализация идёт проверяемыми последовательными checkpoint. Первый точный runtime allowlist и конкретное изменение формы фиксируются здесь до редактирования после Astra-разбора потребителей. Это не повод повторно спрашивать согласие на уже утверждённые обязанности; новый неутверждённый механизм отдельно обсуждается. Прежние native scalar refs/server identity из экспериментального §39 не внедряются автоматически ради упрощения, если не нужны актуальному результату.

Поведение: свободные продолжения и смена темы; исходная задача сохраняется при проверенном уточнении; видимые ответы/предложения и выбранные карточки доступны следующему ходу; прошлые суммы не являются источником новой цены. История использует существующий store, TTL, проверки принадлежности receipt и privacy. Ранее согласованный design whole последних 3 пар без произвольного посимвольного обрезания не заменяется новым лимитом молча. Lead-контакты и служебные данные не уходят провайдеру.

Приёмка первого этапа включает обычный текст, кодовый ответ, отказ по наличию, уточнение, смешанный ответ и последующий ход; price card/selected tab контекст, source UI, lead/privacy и replay. Проверки направлены на классы запросов, не на особый список реплик. Форматные и adverse-output проверки обязательны; точные цены и проверенные кнопки остаются кодовыми.

### Checkpoint подготовки данных и документации

Root/top: C:/Cursor Projects/artgents-bot-active. Branch: codex/model-price-experiment. Baseline HEAD340fd771e38d9bb80ececb01bac99e8c326972e1; fetched origin/main и merge-base efa3f773bcf10891e2997addf8bbec38c7ae1317. Разрешён commit/push текущего подготовленного этапа. Runtime до него не меняется.

Allowlist: изменённые существующие clients/demo/md/*.md и новый clinic__info__policies.md; doctor_catalog.json; target_response/service_catalog.json, d2_direction_prices.json, pricebook/facts.json и существующие pricebook/services/*.json; tests/test_demo_target_service_catalog.py, test_demo_target_price_offers.py, test_demo_doctor_catalog.py; docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md, DEMO_D2_INTERFACE_TASK.md, DEMO_D2_TARGET_CONTRACT.md, DEMO_D2_OWNER_DECISIONS.md, DEMO_D2_DEMO_BASE_REVIEW.md, DEMO_D2_RULES_INVENTORY_AUDIT.md. Включение исторического аудита — документация, не runtime-изменение. Содержимое разрешённых ранних DOC WIP сохраняется как история.

Исключённый WIP: prototypes/, scripts/d2_context_candidate_protocol.py, scripts/experiment_d2_interface_comparison.py, tests/test_d2_interface_comparison_offline.py. Не удалять и не переносить в другую ветку. Ключи, логи, локальные БД и сырые разговоры не публиковать.

### 42.1. Проект первого runtime checkpoint — достоверная история

Подготовка опубликована: `f9b2b84` в origin/codex/model-price-experiment. Root/top/branch прежние; origin/main/merge-base efa3f77. Staging пуст. Исключённый прежний WIP: prototypes/ и три экспериментальных файла из §42. Часть MD может отображаться Git как stat/line-ending dirty без содержательного diff; не включать это в runtime-изменение.

Astra consultation: сначала заменить выборочную history projection, затем отдельно удалять информационные kinds и их потребителей. Это последовательные части одного согласованного этапа, не объявление всего диалога готовым после первой.

**Точный allowlist:** core/d2_completion_context.py, core/d2_dialogue.py, core/d2_lead_bridge.py, core/d2_live_provider.py, core/response_text_renderer.py; contracts/response_plan.py, contracts/d2_session_context.py; tests/test_d2_sim3_completion_context.py, tests/test_d2_completed_source_context.py, tests/test_d2_lead_interrupt_http.py, tests/test_d2_live_provider_offline.py, tests/test_d2_session_context.py; docs/tasks/DEMO_D2_INTERFACE_TASK.md, DEMO_D2_DELIVERY_ROADMAP.md, DEMO_D2_TARGET_CONTRACT.md.

До: _project_pair собирает model_prose и отдельные виды exact, обрезает до1000символов; receipt capture обрезает вопрос; provider просит восстанавливать ответ по source ID. После: безопасная текстовая проекция упорядоченного опубликованного результата того же completion, целые последние3пары, без реконструкции по текущему каталогу. Единственный владелец — существующий completion/store/projection. Удаляются whitelist происхождений, обе1000slices/настройка cap, инструкция реконструкции.

Защита lead: ранее согласованный §39.9 server result kind=lead, без нового model kind/state/field. Назначает существующий producer служебного запроса/ack. Public booking-blocked policy и public gap остаются обычными частями. Mixed merge сохраняет provenance каждой части; renderer заменяет эвристику хвостового reference/clarification на явный lead. В историю не попадают intake-текст и contactslots; siblings сохраняются. Existing receipt ownership/revision, TTL, выбранные UI и структурные ссылки не меняются. Phone/email masking сохраняется.

Новая цена всегда читается из прайса. Цифры ранее показанной карточки в истории — только содержимое прошлого ответа, не authority новой цены. Контекст3пар — countbound, не обещание любого tokenbudget. Новые livecalls/overflowfallback не добавляются. Provider settings/model/outputbudget не меняются этим checkpoint.

Тесты: сравнение реально опубликованного ответа и следующего provider input JSON/SSE; code invitation, policy/fact/gap, price/detail/tab, mixedlead+price/contact, pureintakeexcluded/publicbookingdenialretained, длинная реплика, privacy, replay, TTL. Затем независимый Checker и commit/push. Тесты данных уже приняты, повторять их без причины не требуется.

### 42.2. STOP после каждого этапа — последнее решение владельца

Классификация текущего изменения: только документация. Данные опубликованы commit `f9b2b846e48ab7f6e435174e33eb40bc1c8575e8`; runtime §42.1 ещё не реализован. После каждого этапа и промежуточного checkpoint обязательны отдельные Cursor review и проверка владельцем в виджете. До результатов обеих проверок и подтверждения владельца следующий шаг не начинать. Подготовленный allowlist §42.1 не является подтверждением прохождения этой остановки.

Текущий allowlist документации: DEMO_D2_DELIVERY_ROADMAP.md, DEMO_D2_INTERFACE_TASK.md, DEMO_D2_TARGET_CONTRACT.md. Корень, ветка, origin/main и merge-base прежние; baseline этого doc-delta — f9b2b84. Прежний исключённый WIP сохранён. Новых provider/browser/SMTP вызовов нет.

Дополнительный offline baseline перед будущим изменением истории: test_d2_sim3_completion_context.py, test_d2_completed_source_context.py, test_d2_lead_interrupt_http.py, test_d2_live_provider_offline.py, test_d2_session_context.py — 147 PASS / 3 FAIL. Все три FAIL в test_d2_live_provider_offline.py: ожидание v19 вместо текущего v44, старой инструкции content_ref и секции D2_DIRECTION_PRICE. Это результат до runtime-изменений, не приёмка этапа истории; отдельного сравнения этих трёх с чистым старым HEAD не делали. Он не заменяет 40 целевых PASS данных и не скрывается в отчёте об успешной подготовке базы.

### 42.3. Принятие подготовки и начало истории — 2026-10-11

Owner подтвердил Cursor PASS и виджет (кроме известного старого doctor route) и разрешил работать. Последний порядок отменяет STOP после каждой малой части: связанные шаги можно объединять, на значимой границе Cursor/widget review, затем commit/push. Архитектурные отклонения отдельно согласовать. §42.2 сохраняется как история.

Начинается архитектурное упрощение истории §42.1, exact allowlist там не расширяется. Baseline a0042624486fb19acb05b37d9ba4f456584e05f6; root/top C:/Cursor Projects/artgents-bot-active; branch codex/model-price-experiment; origin/main/merge-base efa3f773bcf10891e2997addf8bbec38c7ae1317. Staging пуст. Прежний untracked WIP и stat-only MD сохранены. Содержательных предшествующих правок нет. До → после → удалённая зависимость и владелец описаны в §42.1. Provider calls этого изменения: 0.

Уточнение отчёта данных: 33 теста — три изменённых файла; 40 — те же три плюс неизменённый test_d2_tenant_snapshot.py. Allowlist редактирования не равен списку запуска тестов. Замечание Cursor о применимости скидки к bone_graft сохраняется для этапов 3–4; здесь данные не меняются.

### 42.4. Отчёт реализации истории — рабочее дерево, ещё без commit/push

Классификация: архитектурное упрощение истории, не завершение всего свободного диалога. Единственный владелец истории — существующий completion/store и его read projection. Реальный путь: /ask и /ask/stream → run_d2_ask_json → run_d2_dialogue_turn → commit receipt ref → project_completed_dialogue → render_response_text по frozen plan → D2ProviderInput.context.

Удалено: ручной whitelist частей для assistant_text, дедупликация/сборка второго текста истории, обе обрезки до 1000 символов, настройка history_text_max_chars, prompt-восстановление пропущенного ответа по текущему каталогу, эвристика хвостового clinic reference/clarification в renderer. Последние три целые пары, TTL, receipt ownership/revision, выбранные UI/offer refs остаются.

Добавлено: ранее согласованный server result kind=lead у существующего producer приёма контактов; модель его не выдаёт. Public booking denial остаётся reference, public gap — clarification, mixed merge сохраняет producer kind/source_results. Renderer показывает intake последним; история использует тот же renderer без intake. Pure intake не добавляет ordinary receipt. Новых model fields, состояний, вызовов, fallback, parallel memory и правил по фразам нет.

Privacy: прежние маски применяются к model_prose, patient_text и terminal_text во временной read projection. Публичные frozen exact/contact/card данные не маскируются как личные контакты: иначе существующий phone regex превращает дату31.12.2026 в телефон. Сам regex не менялся. Служебные lead parts исключаются структурно. Сохранённая цена описывает прошлое; новый price materializer использует текущие tenant data.

Изменение поведения: следующий ход видит показанный отказ по бренду/услуге, политику, факт, цену, состав и коммерческие вставки; длинные вопросы и ответы не теряют конец. Это передача контекста, не гарантия правильного решения живой модели. DoctorsOperation и другие информационные команды пока остаются; пример об Орлове не объявлен исправленным.

Дополнительные проверки к §42.1: публичная дата и контакт сохраняются; модельный phone/email маскируется; mixed price/contact+booking, pure intake, публичный запрет/неясность записи; исторический таб без provider-call; неверная сумма в модельной прозе истории не подменяет новый кодовый прайс. Попытка менять весь tenant pack внутри существующей сессии блокируется прежним fingerprint guard; этот guard не ослаблен ради теста.

Проверка этапа остановлена перед следующим архитектурным шагом для Cursor и виджета. Commit/push до этих проверок не делаются по последнему указанию владельца. Foreign WIP прежний; временный .tmp-history-tests.txt — только локальный вывод тестов, будет удалён, не публикация.

Расширение test-only allowlist: tests/test_d2_code_answer_fixes.py, одна assertion в параметризованном тесте effective_policy_is_in_next_provider_context (6 случаев). Старое требование пустого assistant_text заменено точным совпадением с опубликованным ответом; policy IDs, запрет CTA и соседние проверки не ослаблены. Это тот же утверждённый контракт истории, без расширения runtime.

Результаты offline: основной расширенный прогон семи файлов (пять из §42.1 плюс test_d2_compound_answers.py и test_d2_code_answer_fixes.py) — 191 PASS/9 FAIL. Шесть FAIL требовали прежнюю пустую историю политики; после замены на точное совпадение опубликованного ответа focused recheck — 6 PASS. Четыре дополнительно добавленных случая (JSON/SSE неверная сумма в истории и исторический таб) — 4 PASS отдельными прогонами. Таким образом, остаются только три заранее наблюдавшихся FAIL старых prompt expectations в test_d2_live_provider_offline.py; их assertions не менялись. Полный набор повторно после test-only замены не запускался. Независимый Checker отдельно выполнил 11 PASS (10 новых lead cases и history prompt). git diff --check PASS. Live/provider/browser/SMTP: 0. Staging пуст, baseline/HEAD a004262, commit/push/PR не делались; исключённый WIP сохранён.

Для Cursor: read-only проверить весь рабочий diff относительно a004262, точный allowlist §42.1 + test-only расширение выше; прочитать тесты прежде runtime. Проследить реальный путь JSON/SSE → receipt → projection → renderer → provider context, удаление обеих обрезок, whitelist и реконструкции; сохранить TTL/tenant/privacy, целые 3 пары, выбранный tab, публичные отказы и mixed lead siblings. Проверить, что server kind=lead не добавлен в модельный контракт. Не аттестовать свободный диалог и удаление DoctorsOperation. Не изменять код/Git, не делать live/provider вызовов, не читать .env и сырые разговоры. Прежние untracked вне scope. Выдать PASS/REJECT с конкретными доказательствами и ограничениями.

## 43. Обычный текст без информационных команд — owner GO 2026-10-11

История опубликована в5f47ee6 по прямому поручению владельца; разрешён следующий этап. Root/top C:/Cursor Projects/artgents-bot-active, branch codex/model-price-experiment, baseline5f47ee6, origin/main/merge-base efa3f773bcf10891e2997addf8bbec38c7ae1317. Staging пуст; foreign WIP прежний. Astra consulted, архитектурных вопросов владельцу нет.

Классификация: архитектурное упрощение. До: информационные doctors/clinic_policy/commercial_fact команды и перехват обычного текста по бренду/услуге, отказ публикации из-за неверного optional target. После: existing content_text — единый обычный ответ по FullContext; optional метаданные предоставляют только проверенные UI/context/marketing права. Единственный владелец смысла — существующий один вызов модели. Удаляется весь достижимый путь трёх команд и ordinary authored interception, без адаптера старого формата. Цена/detail сохраняют проверки бренда/услуги, code prices; medical/lead/privacy/tenant и известные задачи кнопок сохранены. Естественный уточняющий вопрос допустим обычным текстом; существующая typed service-choice задача остаётся для проверенных кнопок. Парсер отсутствующего текста и новый формат envelope не входят в этот шаг.

Exact runtime allowlist: contracts/d2_dialogue_result.py; core/d2_dialogue.py; core/one_call_prompt_contract.py; core/d2_live_provider.py; core/response_plan_materialization.py; core/d2_snapshot_sources.py; core/d2_tenant_snapshot.py; core/d2_directory.py; contracts/response_plan.py; core/response_text_renderer.py; core/d2_completion_context.py.
Test allowlist: tests/test_d2_operation_unification.py, test_d2_sim2_contract.py, test_d2_sim2_dialogues.py, test_d2_live_provider_offline.py, test_d2_r3_free_dialogue.py, test_d2_code_answer_fixes.py, test_d2_policy_route_fixes.py, test_d2_commercial_route_fixes.py, test_d2_commercial_scope.py, test_d2_completed_source_context.py, test_d2_sim3_completion_context.py, test_d2_availability_scenarios.py, test_d2_content_reference_gaps.py, test_d2_document_click_task_http.py, test_d2_demo_snapshot.py; новый tests/test_d2_ordinary_prose_http.py для совместной приёмки. Документы: этот файл, DEMO_D2_DELIVERY_ROADMAP.md, DEMO_D2_TARGET_CONTRACT.md.

Ограничения: doctor_catalog.json имеет non-D2 consumers; здесь убирается активный D2 dependency, физическое удаление позже без MD→legacy adapter. YAML action rules пока защищают цену/запись; единый источник политики ещё не объявляется готовым. Автовставки акций сохраняются, единый маркетинговый источник/применимость и взаимодействие свободного прямого ответа с автопромо — этапы3–4, без нового классификатора прозы. Provider calls0.

Test-only расширение §43: tests/test_d2_directory_scenarios.py и tests/test_d2_offtopic_overview_scenarios.py — убрать импорт удалённого D2 directory/classifier и заменить проверку классификатора проверкой обычной content-операции. Остальные старые envelope-сценарии этих файлов не объявляются мигрированными.


### 43.1 Реализация и проверка checkpoint

Удалено: три model-operation типа doctors/clinic_policy/commercial_fact, их обработчики и коммерческий scope carry; весь D2 directory module и его CTA; doctor_catalog.json из D2 snapshot; перехват обычной прозы по unavailable service/brand; отказ публикации обычной прозы по неверному optional target; старые команды из обоих участков собранного промпта. Нет новых runtime полей, состояний, обработчиков, адаптеров, памяти, retry или вызовов. Sole semantic owner — существующий model call. Опциональный source/target по-прежнему проверяется для UI/контекста/автопромо, а не переписывает смысл ответа. Кодовый price/detail путь, медицинский handoff, контакты и lead/privacy остаются.

Поведение: «Расскажите об Орлове» публикует модельное объяснение по MD вместо списка врачей услуги. «Есть Osstem/брекеты/ОМС/рассрочка?» — обычная проза, не заполнение отдельной команды. Естественный уточняющий вопрос допускается content_text; сохранённые задачи проверенных кнопок не переопределяются. Цены отсутствующего бренда по-прежнему не публикуются. Автоматическая акция остаётся один раз за беседу, прямой текстовый вопрос может повторить её. Полное устройство маркетинга/обязательность акции в карточке — дальнейшие этапы, не результат §43.

Offline evidence:
- ordinary prose + operation unification + sim2 contract: 109 PASS/2 FAIL; оба FAIL — цифровая дата в новой model-prose fixture маскировалась существующей privacy-функцией в истории. В fixture дата написана словами; privacy-код не менялся. Ограничение цифровых дат в модельной истории остаётся и не скрывается заявлением о полной точности истории.
- policy routes + document-click + operation unification: 57 PASS/5 FAIL. Три обновлённых assertion относились к удалённой policy operation/обычному уточнению; повторно проверены в следующем наборе. Два legacy authored-source FAIL воспроизведены на baseline.
- итоговый набор ordinary_prose_http, policy_route_fixes, code_answer_fixes, live_provider_offline, demo_snapshot: **96 PASS/7 FAIL**. Все семь FAIL в demo_snapshot воспроизведены на чистом `git archive 5f47ee6`: три старых ожидания пары extraction offers, одно прежнего short price, одно authored-текста и два порядка price/section. Вместе с двумя legacy authored-source — baseline **9 FAIL/23 deselected**, без копирования .env, с offline-placeholder key и fake provider.
- дополнительные HTTP JSON/SSE случаи: неизвестный/отсутствующий бренд после обычной прозы не создаёт цену; auto promo один раз, прямой повтор разрешён — **6 PASS**.

Это targeted offline evidence, не проверка качества живых Qwen/DeepSeek и не полный CI. Остальные исторические тесты старого envelope/удалённых информационных команд не объявляются мигрированными или зелёными. Перед merge требуется общий CI и разбор его результатов. В ходе тестов были logging warnings о ротации общего локального app.jsonl; логика ответа проверялась fake-provider в изолированных БД, сеть запрещена fixture.

Git: branch codex/model-price-experiment; HEAD/baseline 5f47ee6, предыдущий этап уже pushed. Этот checkpoint не staged/committed/pushed; merge/PR нет. Live/provider/browser/SMTP текущего этапа: **0**. Foreign WIP и line-ending-only MD сохранены. Doctor JSON физически остаётся из-за non-D2 consumer; YAML action rules остаются для цены/записи. Новую архитектуру целиком и roadmap 2–4 завершёнными не объявляем.

### 43.2 Проверка Cursor и виджета

Cursor: read-only проверить рабочий diff против 5f47ee6, AGENTS.md, WORKFLOW_CHECKER.md, текущий верх Roadmap и Target §3, allowlist §43 + test-only расширение. Прочитать changed tests до кода. Проследить /ask и /ask/stream → model schema/prompt → ordinary content → materializer → published receipt/history. Проверить физическое удаление трёх информационных команд, отсутствие обходного адаптера/классификатора/новых состояний или вызовов; ordinary source/target не должен заменять прозу кодовым ответом. Обязательно проверить price/detail brand/service protections, child/payment booking guards, проверенные document buttons и replay, tenant/privacy. Новые проверки: tests/test_d2_ordinary_prose_http.py; связанные guard tests — policy_route_fixes/code_answer_fixes; schema — operation_unification/sim2_contract; полный источник и инструкции — live_provider_offline. Отличать старые воспроизведённые FAIL от регрессий. Не менять файлы/Git, не читать .env/raw conversations, не делать live calls. Выдать PASS/REJECT с конкретными причинами и пределами evidence; не аттестовать весь бот.

После Cursor — перезапустить локальный сервер существующим scripts/start_local_widget.ps1, открыть новую беседу (старые receipts специально не мигрируются). Проверить: КТ → «Есть Osstem?» → «Расскажите»; All-on-4 цена → «А кто делает?» → «Расскажите об Орлове»; «Детей принимаете?» и «Работаете по ОМС?»; «Есть рассрочка?»; страх боли → follow-up ссылка; услуга с акцией → продолжение без повторной автопромо → прямой вопрос об акции. Отдельно цена Osstem и запись ребёнка не должны создавать неподходящие карточки/заявку. Любой сбой расследуется по реальному request_id, без добавления сценария под фразу. До этой приёмки следующий маркетинговый этап не начинается.

Независимый Checker §43: 43 ordinary HTTP + 6 source-follow-up/tenant проверок = **49 PASS**. Проверка runtime не обнаружила достижимого прежнего информационного handler/adapter; прежние direct_fact/promotion аргументы shared materializer не задаются единственным D2 caller и не являются параллельным информационным путём. Итоговый verdict Checker — **PASS, только checkpoint §43** после сверки документов. Блокирующих замечаний нет; повторный live/CI прогон не выполнялся.

### 43.3 Приёмка владельцем

Cursor PASS получен: 186 PASS/10 legacy FAIL (8 старых directory/offtopic envelope и 2 ранее воспроизведённых authored-source), весь бот этим не аттестуется. После перезапуска текущего локального сервера владелец проверил виджет и подтвердил: «Все ок. Давай дальше». Checkpoint §43 принят для commit/push; разрешено продолжение актуальной дорожной карты. Исполнитель новых provider-вызовов не делал; ручные диалоги владельца не считаются проведённым автоматическим сравнением моделей.

## 44. Этап 2: единый источник врачей и политики

Preflight: root/top C:/Cursor Projects/artgents-bot-active, branch codex/model-price-experiment, HEAD/baseline/upstream0b9d26c, origin/main/merge-base efa3f77. Staging пуст; прежний foreign WIP неизменен. §43 опубликован после Cursor/виджета. Astra consult выполнен. Маркетинг3–4 не начинается, пока не разобран оставшийся этап2.

44А — архитектурное упрощение источника врачей, уже разрешённое владельцем. До: D2 читает MD, но штатный pack validator требует параллельный doctor JSON, а legacy marketing ссылается на doctor IDs. После: профили только MD, валидатор проверяет KB-ссылки без doctor index; старые doctor refs удалены. Единственный источник врачебных фактов — MD. Удалить Demo JSON и его обязанность в валидаторе, без MD→catalog adapter. Старый target_runtime_client_context и его инструменты не являются поддерживаемым normal-dialogue runtime; их невозможность загрузить Demo после удаления JSON не обходится fallback. Другие tenant JSON не удаляются.

Exact allowlist44А: clients/demo/doctor_catalog.json; clients/demo/target_response/marketing.yaml; scripts/validate_client_pack.py; tests/test_validate_client_pack.py; tests/test_d2_ordinary_prose_http.py; docs/tasks/DEMO_D2_INTERFACE_TASK.md; docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md. MD-профили сохраняются без изменения. Нет новых runtime fields/states/model calls.

Baseline перед правкой: tests/test_validate_client_pack.py —3PASS/2FAIL, оба FAIL из-за md/clinic__info__contacts.md:duplicate_contact_facts_forbidden. Это существующий отдельный долг, проверки не ослаблять.

44Б — пока предложение, не runtime GO: единственный policy MD с отдельными разделами и явное новое поле text_ref в существующих YAML-правилах вместо answer/approved_text. Существующие машинные правила цены/записи сохраняются, код берёт утверждённый текст из указанного раздела captured MD. Неверная ссылка — ошибка базы, без YAML fallback/поиска по словам/скрытой таблицы. Контакты, spam/offtopic, medical handoff вне этой замены. Новая связь требует отдельного решения владельца по AGENTS.md; зависимая реализация остановлена. Удаление physician JSON от этого решения не зависит.

44А allowlist дополнен core/target_client_data.py: тест HTTP выявил обязательное чтение doctor JSON на реальном startup_check→load_target_client_data→_validate_external_refs, до входа в D2. Удаляется этот read/index, общая проверка KB-ссылок сохраняется. Первые два HTTP setup ERROR отражали найденную зависимость и требуют успешного повторного прогона; это не baseline.


44А targeted recheck: **8 PASS/2 baseline FAIL**, setup ERROR устранены удалением реальной startup-зависимости. Старые assertions не ослаблены. Новые проверки: шесть MD-профилей без JSON, нормальный HTTP JSON/SSE и полный корпус, отклонение отсутствующих doctor/KB refs без doctor index. Startup зависит от MD/KB, не от скрытого адаптера. Изменения 44А ещё не staged/committed/pushed; код политики 44Б не тронут; provider/live calls — 0. Маркетинг ещё не начат. Локальный сервер, остановившийся при обнаруженной startup-ошибке, повторно запущен после исправления через штатный launcher.

Независимый Checker 44А выполнил **5 PASS**: три проверки MD/reference в валидаторе и два HTTP startup/fullcontext случая JSON/SSE. Достижимый путь startup_check → load_target_client_data → KB-only index проверен. Неверные doctor/KB refs по-прежнему отклоняются; содержательных изменений MD нет. Итоговый verdict Checker — PASS только 44А после сверки документов; блокирующих замечаний нет. Следующую внешнюю проверку Cursor можно объединить с политикой после решения владельца; этот результат не разрешает добавление text_ref без согласования.

### 44Б — owner GO для text_ref

Владелец подтвердил явную ссылку text_ref в существующих правилах. До: MD/YAML содержат копии текста, lead отдельно читает YAML answer. После: единственный текст в MD, правила указывают точный раздел, все потребители читают его; YAML answer/approved_text и отдельный lead reader удалены. Единственный источник текста — MD; запретом действия владеет прежний resolver. Не добавляются модельные команды, состояния, fallback или поиск по словам.

Preflight root/top/branch/HEAD прежние: C:/Cursor Projects/artgents-bot-active, codex/model-price-experiment,0b9d26c; origin/main/merge-base efa3f77. WIP44А и чужие файлы сохранены. Exact дополнительный allowlist: clients/demo/clinic_policies.yaml; clients/demo/md/clinic__info__policies.md; clients/nikadent/clinic_policies.yaml; clients/nikadent/md/clinic__info__policies.md (новый, дословный перенос существующего правила для общего reader); core/clinic_policies_loader.py; core/d2_snapshot_sources.py; core/d2_tenant_snapshot.py; core/d2_lead_bridge.py; scripts/validate_client_pack.py; tests/test_d2_policy_route_fixes.py; tests/test_clinic_policies_loader.py; tests/test_validate_client_pack.py; tests/test_d2_live_provider_offline.py; tests/test_d2_policy_text_refs.py (новый); три текущих документа Interface/Roadmap/Target. Поля/данные контактов и медицинского handoff не меняются. Неверная ссылка — ошибка данных, без старого текстового fallback.


### 44Б. Реализация и границы проверки

Классификация — архитектурное упрощение источников, без изменения владельца смыслового решения. Удалены YAML answer/approved_text/legacy keyword note в Demo, отдельный lead _authored_policy_answer, повторный текст из provider policy catalog. Полный текст читается из captured MD через точный text_ref. Старые keyword alternative rows больше не являются источником Demo; их сведения о базальных/мини-имплантах остаются в MD. Legacy helper без Demo-строк больше не выдаёт эти заготовки; normal D2 их не вызывает. Старые тесты этого поведения заменены явными проверками отсутствия параллельных строк, остальные assertions сохранены.

Добавлен один согласованный text_ref и его проверка: корректный файл/единственный непустой H3; нет inline fallback и перехода к другому tenant. Никadent: дословно перенесено одно существующее правило, нового поведения нет. Служебные output dataclasses по-прежнему содержат разрешённый текст (answer/approved_text); это результат чтения, не второй редактируемый источник.

Предварительный targeted результат: 67 PASS, 2 старых FAIL контактов в validate_client_pack. Дополнительные негативные HTTP проверки сначала имели ошибку тестовой привязки session_client_scope; поправлена только fixture-подобная обвязка, assertions не ослаблены. Итоговый набор в работе. Live/provider/SMTP вызовов — 0. Новых model states/команд/вызовов/слоёв памяти нет. Свободное понимание живой моделью и маркетинг этим этапом не аттестуются.


### 44В. Итоговый checkpoint и внешняя проверка

Основной targeted набор из пяти файлов (policy_text_refs, policy_route_fixes, clinic_policies_loader, validate_client_pack, ordinary_prose_http): **119 PASS / 2 baseline FAIL**. Только прежние test_demo_pack_passes_validator и test_validator_cli_demo_exit_zero: duplicate_contact_facts_forbidden в clinic__info__contacts.md. До изменения44А эти же два теста падали по той же причине. Вне этого набора исторические тесты старых informational kinds/doctor JSON не объявляются мигрированными; общий CI нужен перед merge.

Дополнительные четыре HTTP JSON/SSE теста меняют только MD-текст отсутствующего бренда/услуги и требуют его точного показа без ценового offer. Первое ожидание для braces не учитывало прежний суффикс названия разрешённой альтернативы; тест скорректирован на точный полный ответ с этим суффиксом, runtime не менялся. Никadent перенесён дословно; сведения Demo о диагностике, оплате и применимости бренда сохранены отдельным общим разделом.

Изменённые paths — объединение точных allowlist44А/Б выше (core/target_client_data.py включён пояснением44А). tests/test_d2_live_provider_offline.py фактически не менялся. Риски: модель по-прежнему может ошибиться в обычном ответе; этот checkpoint убирает дубли источников, не обещает безошибочную модель. Битая ссылка — диагностируемая ошибка базы до model call, а не разрешение цены/записи. Отдельные template/contact/medical тексты не переносились. Marketing/card-поведение не менялось.

Git: codex/model-price-experiment, HEAD/baseline/pushed0b9d26c; текущие44А/Б не staged/committed/pushed, PR/merge/deploy нет. Foreign WIP: prototypes/, scripts/d2_context_candidate_protocol.py, scripts/experiment_d2_interface_comparison.py, tests/test_d2_interface_comparison_offline.py;14 прежних MD line-ending-only сохранены. Provider/live/SMTP вызовы исполнителя и Checker:0. Static виджет вернул HTTP200; это доступность страницы, не живой функциональный прогон.

**Промпт Cursor:** проведи read-only проверку объединённого рабочего diff44А/Б против0b9d26c в codex/model-price-experiment. Прочти AGENTS.md, WORKFLOW_CHECKER.md, актуальный Roadmap, Interface§44 и единственную таблицу Target§3. Exact allowlist44А/Б указан выше, включая пояснение startup consumer. Сначала changed tests, затем trace startup→/ask и /ask/stream→capturedMD/modelview→policy/brand/service price guards→lead→receipt/history. Убедись, что Demo doctorJSON/index и двеdoctor refs удалены, шестьMD доступны, KB validation сохранена. У политики единственный полный текст MD; YAMLtext_ref явно согласован владельцем. Нет inline answer/approved_text fallback, скрытой карты, нового классификатора/команды/modelcall/memory. Неверныеrefs и tenantescape отвергаются. Обычную прозу не подменяет код; цены/booking child/ОМС/ДМС сохраняют прежнюю защиту, Osstem/braces не создают offer. Проверь что nikadent-текст дословно перенесён. Запусти пропорциональные offline tests выше, отдели известные2contactFAIL. Не ослабляй tests, не читай .env/rawconversations, не делайprovidercalls/commit/push. Дай PASS/REJECT с конкретными расхождениями, сохрани границы evidence: свободный диалог и маркетинг целиком не аттестуются.

**После Cursor — новая беседа в виджете:** ценаAll-on-4 → «А кто делает?» → «Расскажите об Орлове»; «Принимаете детей?» → «Запишите ребёнка»; «Работаете по ОМС?» → «Сколько стоит лечение по ОМС?»; «У вас есть Osstem?» → «Сколько он стоит?»; «Ставите брекеты?» → «Сколько стоят?»; обычная услуга → follow-up. Проверить разговорный текст, отсутствие неподходящей цены/записи и сохранение follow-up. Маркетинговые дубли и обязательные акции каждой карточки — следующий этап3–4, не объявлять закрытыми. Commit/push после принятия checkpoint.

Независимый Checker: **PASS объединённого checkpoint44А/44Б**, блокирующих замечаний нет. Самостоятельно34PASS, дополнительные4price-ref tests прочитаны и4PASS подтверждены. Итог исполнителя **123PASS/2baselineFAIL**. Старые источники/lead-reader удалены, capturedMD и прежние price/booking guards проверены. Полный этап2, live/widget и маркетинг этим не аттестуются. git diff --check прошёл, staging пуст; HEAD/upstream0b9d26c. Следующая остановка — Cursor и виджет по44В выше.

### 44Г. Приёмка владельцем

Cursor PASS получен:123PASS/2прежних contactFAIL. Владелец подтвердил виджет: «Идем дальше, ответы в боте вроде нормально пока». Checkpoint44А/Б принят для commit/push и перехода к этапам3–4. Это не аттестация всех будущих карточек/маркетинга. Исполнитель provider calls не делал.


## 45. Единственная применимость акций — owner GO

Классификация: архитектурное упрощение. 44А/Б опубликован e744ab7 после Cursor/widget. Root/top C:/Cursor Projects/artgents-bot-active, branch codex/model-price-experiment, baseline e744ab78a6e2887033f21f76b3b20bbd5cc4321a, origin/main/merge-base efa3f77; staging пуст. Прежний foreign WIP и14 line-ending MD сохранены.

Astra consult: удалить promo_facts/profile.promo_refs, использовать captured facts; не создавать новый-to-old adapter. Последнее решение владельца отменяет правило пересечения общих акций: ориентир — вкладки с одним выбранным предложением, акции принадлежат выбранному варианту. Старый обзор нескольких разных услуг пока остаётся навигацией без выбранного предложения; акции появятся после выбора, без union/intersection. Перестройка начального обзора под визуал — следующий UI checkpoint. Неповтор обычного текста не подавляет акции карточки. Тема получает только явное allowed_topics, не union услуг. Прямой вопрос остаётся свободной прозой. Цены/бренды/объём/кнопки/lead/privacy не меняются.

До → после → удалённая зависимость: facts плюс ручные списки в d2_commercial → факты напрямую определяют активность и применимость → удалить обе promo-структуры и их промежуточные authority-копии. Sole owner применимости — существующий commercial resolver по captured bundle. Профили остаются для оформления/detail UI. Порядок фактов детерминированный по id; обычный текст сохраняет лимит2, карточка публикует все подходящие акции согласно owner решению. Существующий ledger остаётся, нового нет.

Точный allowlist этого checkpoint: contracts/d2_tenant_snapshot.py; contracts/response_plan_materialization.py; core/d2_tenant_snapshot.py; core/d2_snapshot_sources.py; core/d2_commercial_plan.py; core/response_plan_materialization.py; clients/demo/target_response/d2_commercial.json; tests/test_d2_commercial_contract.py; tests/test_d2_commercial_plan.py; tests/test_d2_ordinary_prose_http.py; tests/test_d2_promo_authority.py (новый); docs/tasks/DEMO_D2_INTERFACE_TASK.md; docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md. Нет новых полей модели/состояний/вызовов. Следующий связанный проход — полные factual данные модели и MD-дедупликация с точным списком файлов; этот checkpoint сам по себе не объявляет все маркетинговые дубли удалёнными.

Allowlist45 расширен только tests/test_d2_price_cards.py: старое ожидание отсутствия коммерческих секций у All-on-4 заменяется ожиданием согласованных акций из facts. Остальные exact/UI/tenant/receipt assertions сохраняются. Baseline основной тройки tests:67PASS.


### 45.1 Реализация и проверка

Удалены D2CommercialPromoFact/D2CommercialPromoAuthority, pack.promo_facts и profile.promo_refs вместе с чтением/валидацией старых списков. Старые поля теперь отклоняются закрытой схемой, а не преобразуются. Применимость вычисляет resolve_d2_commercial_plan прямо по captured bundle.facts: kind, active/date, allowed_service_ids/excluded_service_ids либо явный allowed_topics. offer.fact_refs не является вторым разрешающим списком D2-промо. Профиль не нужен для акции; его прежние packages/detail остаются.

Дата проверяется существующим fact_active_as_of. Только карточка игнорирует прежний shown-ledger; обычный автоматический текст ограничен двумя акциями и неповтором. Прямой вопрос остаётся ordinary content_text, без нового recognizer. Выбор price_select сохраняет существующую проверку принадлежности/revision и обход modelcall. Нет автоматического пересчёта цены/скидки.

Граница UI: этот checkpoint не меняет widget/prototypes. Точный service-card использует реально опубликованную услугу. Старый multi-service overview без выбранного предложения не добавляет общий рекламный хвост. Нет алгоритма пересечения/union акций; после выбора применяется правило конкретного варианта. Промо по бренду отдельно пока не моделируются текущими facts; настраивать новый brand/offer scope здесь не пытались. Для Demo существующие акции применимы к услуге целиком.

Baseline67PASS. Первый post-change прогон66PASS/1FAIL: оставшаяся assertion удалённой authority-копии; заменена проверкой того же captured bundle. Новые7PASS/2ошибки тестовых данных (отсутствующий clients_root и обязательное excluded_scope_text) исправлены без runtime fallback. Recheck27PASS; ещё1PASS подтверждает третью акцию без offer-ref и без обрезания карточки. Итог карточных тестов и Checker ожидается. Изменённые старые тесты запрещают старые поля и сохраняют проверки текста/пакетов/tenant/incompatibility. Ранее ожидаемый неповтор карточки заменён требованием её повторного показа по решению владельца.

Весь этап3–4 не завершён: перед удалением коммерческих условий из MD нужно передать полный текст/сроки/исключения из captured facts в существующую factual проекцию модели. Затем проверить все33предложения и реализовать визуал. Существующие2baselineFAIL контактов из§44 не исправлялись; в набор§45 они не входят. Provider/live/browser/SMTP:0. HEAD/pushed e744ab7; новые изменения пока не staged/committed/pushed, foreign WIP сохранён.


### 45.2 Итог и следующая остановка

Итог целевых прогонов с исправленными assertions/fixture: **138 PASS / 4 baseline FAIL** (18 commercial_contract + 4 commercial_plan + 45 ordinary_prose + 11 promo_authority + 60 price_cards). Четыре FAIL — обе consultation-параметризации двух тестов free_text_can_repeat_information_after_card_selection / historical_tab_returns_scope_after_other_turns_and_supports_text. Они отправляют удалённый ранее kind commercial_fact. Все четыре воспроизведены на чистом archive e744ab7 тем же Python: 4 FAIL / 60 deselected. Это не регрессия45; тесты не исправлялись и не пропускались. Общий CI не заявлен.

Checker заметил остаточную зависимость fact-validation от наличия optional d2_commercial: проверка перенесена перед ранним return. Новый negative HTTP подтверждает ошибку до provider при missing config + invalid short text. Дополнительный тест подтверждает третью акцию без offer ref и без card cap. Независимый Checker выполнил 11 PASS; окончательный verdict ожидается после документов. git diff --check PASS, staging пуст. Static widget HTTP200; живые ответы/визуал не проверялись. Provider/live calls: 0. Foreign WIP прежний; commit/push45 ещё нет, HEAD/upstream e744ab7.

**Cursor:** read-only проверить рабочий diff против e744ab7, AGENTS/WORKFLOW_CHECKER/Interface§45/актуальный Roadmap/Target§3. Changed tests перед кодом. Trace /ask + SSE → snapshot facts → materializer → commercial resolver → price-owned promo → receipt/ledger → verified tab/replay. Проверить удаление promo_facts/promo_refs/authority-копий без адаптера, отсутствие зависимости от profile/offer refs; даты, исключения, explicit allowed_topics, все акции выбранной карточки независимо от ledger, ordinary once/direct prose. Старый multi-service overview без выбранного предложения не выбирает метод ради акции; intersection/union нет. UI-дизайн, brand-specific promo, новая память и model calls не добавлялись. Exact allowlist§45 + price_cards test extension. Запустить пропорциональные offline-наборы, отделить четыре воспроизведённых baseline FAIL. Не редактировать, не делать Git/provider операции, не читать .env/raw conversations. Дать PASS/REJECT. Этот checkpoint не аттестует полный маркетинг или живую модель.

**Виджет после Cursor:** новая беседа «Расскажите об All-on-4» → «Подробнее» → «Сколько стоит?» → переключить бренд → ещё раз цену. Акция после обычного текста один раз, в каждой ценовой карточке снова. Прямой вопрос «Какая акция?» — обычный текст. Отбеливание получает свою акцию, кариес не получает имплантационные. Контроль цены Osstem/брекетов и follow-up сохраняется. Точный текст живой модели не предписывается. Затем owner-приёмка и commit/push; следом полные facts модели, MD cleanup и UI по макету.

Независимый Checker: **PASS только §45**, блокирующих замечаний нет. Самостоятельно11PASS; итог138PASS/4воспроизведённых baselineFAIL проверен. Удаление старых структур, реальные HTTP/tab/replay и исправление независимой валидации подтверждены. Полные facts для модели, MD-дедупликация и визуал остаются следующей работой. Документное замечание Roadmap о номере текущего этапа исправлено.


### 45.3 Приёмка и уточнение карточек владельцем

Владелец подтвердил виджет и Cursor: «В курсоре всё хорошо, идём дальше». После обсуждения структуры карточек разрешил зафиксировать решения и продолжить. §45 принят для commit/push. Новые UI-решения ниже — согласованная будущая работа, не часть реализованного promo checkpoint.

Сложная карточка: «Что входит в стоимость» (работы/материалы), «Как оплачивается лечение» (этапы, скидка, рассрочка и их совместимость), «Гарантия и преимущества» (только применимые условия). Пустые разделы и прочерки не показывать. Простая карточка использует те же смыслы, но только имеющиеся разделы. Гарантия и вычет не являются оплаченным составом. Отдельный видимый блок акции ориентирован на выбранную вкладку; «Сравнить три варианта» не нужно.

Тип факта и место показа различаются: скидка остаётся акцией, даже если расположена внутри оплаты. Настройки клиники определяют главную выделенную акцию и места остальных фактов, код исполняет их после проверки применимости/сроков. Новая применимость в настройках оформления не создаётся. Один факт не повторяется в карточке вторым рекламным блоком; необходимые условия совместимости остаются понятными. Если главная акция неприменима, её не показывать; автоматическую замену другой акцией без решения не придумывать. Прямой вопрос об акциях включает скидку независимо от её UI-раздела.

Одна запись содержит заголовок, краткий текст и полные условия одной акции. Полные условия — основа; краткая версия не меняет смысл («до15%» не превращается в «15%»). Каждый отображаемый текстовый блок — цельная формулировка одного источника, не склейка предложений из разных файлов. В базовых строках не должно быть случайных переносов, разорванных слов и технических разделителей; осмысленную структуру разделов/списков задаёт renderer. После переноса источников обязательно пройти все Demo-формулировки: грамматика, полнота условий, краткая/полная версии, даты, исключения и внешний вид. Это не новая маршрутизация модели.


## 46. Полные коммерческие факты в контексте и удаление MD-дублей

Архитектурное упрощение источников: thin ID/label projection + повторённые условия в MD → полная существующая fact-проекция из captured bundle в ordinary и known-task контексте → удалить thin whitelist и числовые/условные MD-дубли. Единственный источник коммерческих условий — facts.json; MD хранит объяснения процесса и прежние якоря. Не создавать второй serializer, memory, model call, модельные команды или clock field. Astra consulted: known_task до изменения не получал факты, этот путь включён в тот же checkpoint. Передача дат не является доказательством живого понимания «сегодня»; кодовый показ акций проверяет срок как прежде.

Preflight: root/top C:/Cursor Projects/artgents-bot-active, branch codex/model-price-experiment, HEAD/baseline/upstream fe1ec48, origin/main/merge-base efa3f77. §45 опубликован после Cursor/widget. Staging пуст, foreign WIP прежний.

Exact allowlist: core/one_call_exact_commercial_catalog.py; core/one_call_commercial_fact_catalog.py; core/d2_live_provider.py; clients/demo/target_response/pricebook/facts.json; clients/demo/md/clinic__info__payment_terms.md; clients/demo/md/clinic__info__warranty.md; clients/demo/md/clinic__info__consultation.md; clients/demo/md/clinic__info__promo__implant_same_day_discount.md; clients/demo/md/clinic__info__promo__professional_whitening_discount.md; clients/demo/md/clinic__info__promo__free_implant_consult.md; tests/test_commercial_fact_catalog_snapshot.py; tests/test_d2_full_commercial_context.py (новый); docs/tasks/DEMO_D2_INTERFACE_TASK.md; docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md.

Сохранить уникальные сведения о диагностике, процессе консультации/оплаты, вычете, договоре и обращении по гарантии; все MD frontmatter/CTA/H3/follow-up остаются. Публикационные формулировки фактов цельные, без переносов внутри строк. UI highlight/placement поля пока не реализуются: они требуют отдельного согласованного дизайна данных в рамках принятого поведения45.3.


### 46.1 Результат реализации и проверка

Удалены thin whitelist фактов и повторные условия в шести MD; один существующий serializer теперь сохраняет полные тексты, короткие формы, сроки, исключения, применимость и несовместимость. Одна и та же captured fact projection включена в ordinary и known-task prompt. Новых runtime-полей/состояний/вызовов/маршрутов нет. Модель по-прежнему владеет смыслом обычной прозы; код владеет точными карточками по §3 Target Contract. Наличие полного текста в prompt не доказывает точность живого ответа.

Три полные формулировки facts дополнены прежними MD-условиями: ограничения налогового вычета, применимость скидки к подготовительной хирургии и базовая цена до скидки, отдельная оплата подготовки к отбеливанию. Цены/проценты/сроки/списки применимости не менялись. Frontmatter/CTA/H3/follow-up шести документов сохранены; уникальные объяснения процесса оставлены. Новая текстовая склейка не добавлена.

Offline: targeted18PASS (snapshot9 + fullcontext3 + live-provider6); regression54PASS/8FAIL. Всего72PASS/8baselineFAIL. Шесть document-click отказов воспроизведены ДО edits (logs/stage46-baseline.txt:19PASS/6FAIL): четыре ожидают отсутствие впервые применимой автоакции, два legacy authored-source. Ещё два exact-commercial теста воспроизведены в чистом git archive fe1ec48 (logs/stage46-clean-baseline/baseline-result.txt): устаревшие offers32 вместо33 и promptversion13 вместо44. Они не исправлялись и не объявлены зелёными. Новые HTTP JSON/SSE проверки проверяют реальные ordinary→verified follow-up→replay, целые условия из изменённого fixture-source, один model call на ход. Не подтверждают живое понимание модели. Все публикационные строки Demo facts проверены на случайные переводы строк/табуляцию/двойные пробелы; полный редакторский/визуальный проход всех данных ещё впереди.

Branch codex/model-price-experiment, baseline/HEAD fe1ec48.14 содержательно изменённых/новых файлов по allowlist. Staging пуст; §46 commit/push пока нет. Provider/live/browser calls0. Foreign14EOL MD, prototypes/ и три experiment untracked сохранены. §45 уже commit/push fe1ec48 принятого checkpoint. Следующая работа после проверки: настройки/вид карточек по45.3, затем общий проход формулировок и виджета.

Cursor: read-only проверить diff к fe1ec48 в allowlist46, §3 Target Contract, удаление thin копии и получение полных captured фактов в обеих ветках build_d2_d1r_messages. Проследить JSON/SSE→snapshot→modelview→prompt, verified follow-up/replay. Проверить сохранность шестиMD ссылок, перенос всех удалённых условий в facts, отсутствие новых семантических слоёв/вызовов/публикационной склейки. Сверить baselineFAIL отдельно; не ослаблять тесты и не делать live calls/commit/push. Вердикт относится только46, не всему диалогу/UI.

Виджет: «Какая рассрочка?»→«А на удаление зуба?»; новая беседа «Консультация бесплатная?»→«А КТ входит?»; «Какая скидка на отбеливание?»; «Какая гарантия?»→follow-up «Что делать, если возникла проблема». Проверить условия из facts, сохранность follow-up и отсутствие рваных формулировок. Точная модельная проза не предписывается. Аккордеоны/главная акция в этом checkpoint не менялись.

Независимый Checker: PASS только46, blockers нет. Самостоятельно12PASS; подтвердил единыйserializer/обеpromptветки,14fileallowlist, перенос условий без потери anchors/CTA/follow-up и baseline evidence. Живая модель/виджет/новыйUI/полныйредакторскийпроход не аттестуются. Стоп на Cursor и виджет перед фиксацией46.


## 47. Полный аудит цепочки после инцидента консультации — 2026-10-11

**Классификация: аудит и документация, без реализации.** Владелец попросил сначала полный независимый аудит на Astra и разбор результатов. Эта запись не разрешает новые runtime-поля, состояния, сценарии, слои, retries или изменение продуктовых правил. Исправления и визуальный этап приостановлены до обсуждения аудита. Предыдущие scoped PASS не равны общей приёмке свободного диалога.

Preflight: repository/top C:/Cursor Projects/artgents-bot-active; branch codex/model-price-experiment; HEAD/baseline fe1ec48a63c60195bac874452924cb48124b8231; origin/main и merge-base efa3f773bcf10891e2997addf8bbec38c7ae1317. Проверялось текущее дерево с §46 WIP, а не только чистый HEAD. Allowlist изменений ЭТОГО аудита — только docs/tasks/DEMO_D2_INTERFACE_TASK.md. Предыдущий §46 WIP сохранён; foreign14EOL MD, prototypes/ и три экспериментальных untracked сохранены. Staging пуст. Runtime/tests/client data в ходе аудита не редактировались.

Три независимых прохода gpt-6-astra high: вся серверная цепочка; история/виджет/транспорт; цены/бренды/объёмы/33 предложения. Root проверил входные gates, provider contract и существующие логи. Покрытие: /ask и /ask/stream → input/privacy/lead/UI binding → tenant snapshot → history/model view → ordinary/known-task prompt → provider → parser → resolver/materialization → renderer/UI → commit/replay/next-turn context. Исторические недостижимые маршруты не объявлены причинами текущего D2. Нет полного CI или доказательства отсутствия всех возможных ошибок.

### 47.1 Подтверждённые проблемы

**A1 · P1. Пригодный обычный текст зависит от всей технической оболочки.** contracts/d2_dialogue_result.py:13,44–50,121–146,237–243; core/d2_dialogue.py:734. Общие extra=forbid и model_validate отклоняют всё до публикации. Read-only probes с одним и тем же пригодным текстом подтвердили отказы: чужое age_group; content_ref без .md; sections без ref; противоречивый optional volume; clarification:null; текст4001 символ. Неверная optional ссылка missing.md может пережить позднюю проверку, а missing без суффикса — нет. Реальный случай18:44:07: модель правильно ответила о консультации, но пять ненужных полей уничтожили ответ. Принцип исправления: отдельно пригодность текста и права необязательных metadata; без глобального отключения проверок цены/записи и без списка исключений под сегодняшние пять полей.

**A2 · P1. Локальная ошибка команды отменяет независимую часть даже после успешного parse.** core/d2_dialogue.py:885–886; core/response_plan_materialization.py:517–519,1033–1045,1279–1281; core/d2_contacts_cta.py:292–295,317–318. Price без target вызывает исключение; good content + detail offer_id=does_not_exist → d2_price_detail_offer_foreign; good content + detail service:does_not_exist → materialization_foreign_material. Неизвестный branch в ordinary contact тоже fatal. Отсутствующая модельная ссылка текущей клиники здесь смешана с нарушением ownership. Пример: нормальный ответ о консультации + ошибочная ссылка на состав цены → пользователь теряет обе части. Настоящие tenant/auth нарушения нельзя ослаблять. Предлагается общая согласованная граница локального отказа части, без поиска замены и угадывания команды.

**A3 · P1. Новое направление игнорируется при выборе состава цены.** core/response_plan_materialization.py:491–511,981–1046,636. После classic/Nobel/one_tooth валидный price_detail(topic:prosthetics,includes), равно как topic:orthodontics, выбирает classic.one_tooth.nobel. При этом discussion_scope уже записан новым направлением. Helper читает service, но не topic; historical refs оказываются сильнее явно нового предмета. Пример: «Цена Nobel на один зуб?» → «А что входит в протезирование?» → состав прежнего импланта. Подтверждено pure execution, не предположение о модели. Исправление должно согласовать предмет выбора и предмет сохранённого результата, не выбирать за человека конкретную услугу нового направления.

**A4 · P1. Явный вариант простой услуги нельзя передать в текущем ценовом контракте.** contracts/d2_dialogue_result.py:96; core/response_plan_materialization.py:1299 и первый selected row; core/d2_dialogue.py:914–917. PriceOperation передаёт service/brand/volume, но не option/offer. «Открытый синус-лифтинг» сводится к sinus_lift: по умолчанию открывается закрытый42тыс., а не открытый68тыс. «Сложное удаление» — обычное5тыс., вместо сложного8тыс. Другие варианты доступны во вкладках, но исходный явный запрос не выбирает их. Probe: server selected open показывает open; следующий price по sinus_lift даже с shown refs open возвращается к closed. Модельное option_id=open отвергается как extra. Это не ошибка прайса и не оформление вкладок. Нужен минимальный согласованный способ передать уже понятый вариант; добавление нового поля не разрешается одним этим отчётом.

**A5 · P1/P2. История не включает весь доступный пользователю состав карточки.** core/response_plan_materialization.py:1423–1425; static/widget/widget.js:2065–2093; core/d2_completion_context.py:44; core/response_text_renderer.py:15–25,243+; core/d2_live_provider.py:113–134. В frozen row есть includes/excludes/stages, но projection истории использует plain rendered_text. У classic.one_tooth.nobel четыре includes и два stages; все шесть отсутствуют в этом тексте. Аккордеоны раскрываются локально; ordinary prompt не содержит полного offer/package/stages каталога. «Почему второй платёж такой?» после раскрытия этапов может не иметь в контексте самих этапов. Предлагается проверить полноту существующей projection из frozen completion, без второй памяти и без нового модельного вызова. Это не доказательство, что модель обязательно ошибётся: price_detail может повторно дать данные кодом.

**A6 · P2. Сохранение выбранного предложения всё ещё зависит от optional metadata обычного текста.** core/d2_completion_context.py:9–17,76–95,130–146; core/response_plan_materialization.py:610. После classic/Nobel/one_tooth ordinary «Есть рассрочка…» без target очищает scope; с target classic, но без brand/volume — заменяет его урезанным. Три последние пары временно помогают модели, но deterministic targetless detail лишается текущего offer. Старый тест сохранения предложения через факт tests/test_d2_completed_source_context.py:90+ по-прежнему использует удалённый commercial_fact. Нельзя лечить автоматическим переносом темы на любой текст: это вернёт залипание после смены темы. Требуется единое согласованное правило ответственности существующей истории/выбранной карточки.

**A7 · P1. При переключении бренда текст рядом с карточкой может относиться к прежнему варианту.** static/widget/widget.js:1458–1473. Реальный HTTP offline probe: price classic без brand + связанная ordinary prose о корейской системе → три tabs; click Nobel меняет карточку без модели, но сохраняет prose price_owned=false. Фраза «Эта система производится в Южной Корее» визуально остаётся рядом с Nobel. Для explicit single-brand price проблема не воспроизведена: там один offer. Это mismatch принадлежности текста и изменяемой карточки. Не исправлять генерацией новой prose при каждом tab и не изобретать новые semantic flags без решения; определить, какая часть видимого ответа принадлежит неизменному сообщению, а какая карточке.

**A8 · P1. После некоторых транспортных ошибок теряется возможность повторить тот же незавершённый запрос.** static/widget/api.js:128,176; static/widget/widget.js:1477,1644; app.py:355,380. Node offline probe: network break → повтор получает request_in_progress → onError(retryable:false); аналогично d2_stream_transport_failed. Widget сбрасывает retryBody. Первый запрос может позже завершиться на сервере, но следующий ввод пойдёт с новым request_id; результат останется невидимым пользователю, хотя попадёт в history. Нужен корректный транспортный replay существующего request_id, не дополнительный модельный retry и не скрытая повторная отправка заявки.

**A9 · архитектурная область отказа. Ошибка оформления одной акции блокирует любой вопрос до модели.** core/d2_dialogue.py:202; core/d2_tenant_snapshot.py:147–148,364–407. In-memory probe: активный free_implant_consult без microfact_text → commercial_promo_short_missing. Это происходит при загрузке общего snapshot, до обычного ответа «Расскажите об Орлове». Валидировать данные необходимо; вопрос — делать ли весь pack недоступным на любом ходе. Это существующая связность, не регрессия46. Не предлагается молча пропускать ошибочные данные или добавлять fallback; политика области отказа/момента валидации требует отдельного решения.

**A10 · вопрос продуктовой границы, P2. Booking не проверяет доступность явно названной услуги.** core/d2_dialogue.py:757–766,775–777; core/clinic_policy_resolver.py:104–165; core/d2_lead_bridge.py:253–285. Валидные booking service:braces и service:does_not_exist дают active_booking=r1,suppress=False,decisions0, после чего путь начинает intake. Это не доказывает, что общая консультация о проблеме должна быть запрещена. Но нельзя считать resolver полной кодовой защитой записи на отсутствующую услугу. Требуется различить общую консультацию и обещание отсутствующей услуги; без самовольного запрета общей консультации.

### 47.2 Сохранённые ограничения и риски, не новые регрессии

- История: DEFAULT_D2_HISTORY_PAIR_LIMIT=3 и idle TTL30мин (contracts/d2_session_context.py:25–26). FullContext относится к базе, а не бесконечной истории. В §42.1 целые три пары были явно сохранены; это не скрытая новая обрезка.
- Вход: «Да», «Ок», «Расскажите» проходят; «2», «35», «4000», 👍 получают spam/privacy rejection. «Даааааа» попадает под repeated-character spam. Подтверждено чистыми helper probes. Повтор noise может закрыть беседу. Numeric-only запрет уже был сохранён прошлыми этапами. Пример ограничения: естественное «Сколько зубов?» → «2» до модели не доходит. Изменение фильтра/границ privacy требует отдельного согласования.
- Изменение клиентского pack в ходе беседы: fingerprint mismatch → d2_experiment_tenant_changed (core/d2_dialogue.py:209–210). Реальное событие16:43:08UTC в логах. При разработке/редактировании базы нужен новый чат; обычное обновление страницы не обязательно создаёт новую серверную сессию. Это существующая защита согласованности, не доказательство нужды в production migration.
- Provider: действующий D2HttpProvider запрашивает json_object, а не provider-enforced strict schema; max_completion_tokens1024 (core/d2_live_provider.py:215–246). finish_reason не проверяется. Offline fake finish_reason=length с оборванным JSON возвращается дальше как raw. Это риск обрыва/плохой диагностики, а не причина консультационного incident: среди29 реальных provider responses за11октября до аудита достижения1024 не найдено. Не предлагать automatic retry или смену модели/формата без отдельного сравнения.
- Даты: code-owned promo проверяет сроки; наличие dates в fullfacts не доказывает корректное живое понимание «сегодня». Новый clock field не добавлялся.
- Демо имеет явные лимиты вызовов (core/d2_demo_limits.py):10на sid, IP-window,200за24ч; ошибки провайдера тоже расходуют бюджет. Это ограничение demo, не ошибка диалогового понимания.

### 47.3 Что подтверждено работающим и что не следует удалять

Кодовые клики выбранной цены/объёма исполняют известную задачу без повторной классификации моделью. Follow-up known-task использует определённый документ и текущие fullfacts. Для точного server-selected offer проход snapshot→sources→resolve→render→UI проверен по всем33 предложениям: identity, includes, excludes, stages, обязательные условия —33/33 без расхождений. Это подтверждает основу данных и исполнения выбранной карточки, но не правильность выбора по свободному вопросу (A3/A4).

Tenant/UI ownership, privacy/lead protections, медицинская граница и проверка точных цен остаются необходимыми. Остаточный риск свободной финансовой prose явно принят; аудит не разрешает semantic verifier, второй вызов, шаблонную подмену или обрезку текста. Mixed booking не объявлен silently dropped: siblings обрабатываются до lead mutation. Согласованный будущий визуал45.3/редакторский проход ещё не реализован и не исправит A1–A8 автоматически.

### 47.4 Почему прежние проверки не закрыли эти случаи

Scoped PASS доказывали удаление команд/дублей и работу конкретных fixtures, но не устойчивость всего ответа к неблагоприятному output и переходам между предметами. Часть прежних тестов продолжения всё ещё использует удалённые commercial_fact/clinic_policy. Новое обычное content-поведение нельзя считать проверенным таким тестом. Структурно валидная новая тема отдельно не была достаточным acceptance case для detail selector. Нужны полные цепочки и негативные входы на действующем формате; не ослабление assertions и не ещё один слой, который исправляет решение другого.

### 47.5 Предлагаемый порядок, пока НЕ реализация

1. Согласовать общую границу отказа: текст / optional UI-context metadata / исполнимая команда. Закрывать A1+A2 единым механизмом, включая mixed outputs и повреждённый текст, без списка частных фраз.
2. Согласовать точный выбор уже названного варианта и смену предмета цены (A3+A4). Полные33offer данные уже исправны; нельзя подменять отсутствующий вариант первым дешёвым.
3. Свести содержимое видимой карточки, её соседней prose и существующей истории (A5+A6+A7), без второй памяти и дополнительных вызовов на tab.
4. Исправить transport replay A8 отдельно от модельных retries. A9/A10 и input/history ограничения обсудить как продуктовые/эксплуатационные решения, не смешивать с механическим удалением checks.
5. Общая регрессия на действующем формате: ordinary/price/booking mixed, плохие refs, смена направления, явный вариант, card→follow-up, tab→короткий вопрос, transport break→same request replay. После offline/независимой проверки — ограниченный live/widget. Затем оформление и редакторский проход.

Никакое «если других находок нет, сразу исправить» не применяется: дополнительные существенные находки есть. Аудит останавливается на отчёте владельцу. Отсутствие других ошибок не гарантируется.


### 47.6 Итог доказательств и состояние работы

Astra pricing:33/33 точных server-selected offers сохранены; дополнительно8комбинаций обзора имплантации/протезирования по объёмам; Nobelclassic101200, unavailable/unknownbrand не подставляет чужую цену; промо соответствуют данным услуг. Для A4 суммы обозначают «от»: закрытый синус-лифтинг от42000 против открытого от68000; обычное удаление от5000 против сложного от8000. Сам выбор по свободному названному варианту сломан, хотя выбранная кнопкой строка исполняется правильно.

Astra history/widget:132PASS/4FAIL в tests/test_d2_price_cards.py, tests/test_d2_ordinary_prose_http.py, tests/test_d2_source_followup_http.py (259.36s). Четыре consultation fixtures возвращают удалённый commercial_fact; parser/schema наHEAD уже не допускают его. Эти отказы совпадают с ранее отмеченными §45 baseline failures; отдельный clean-baseline прогон в этом аудите не запускался. Их не исправляли, не пропускали и не объявляли новыми регрессиями. Дополнительные доказательства: Node mockedfetch replay probe, HTTP fake-provider mixedcard→tab, in-memory invalidmarketing snapshot. MainAstra: три read-only Python группы для parser/detail/history/booking. Root: helper input probes, fake provider finish_reason=length, анализ существующих логов. Это не полныйCI и не live-model acceptance.

Во время существующих pytest logging_setup записывал синтетическую диагностику в локальный logs/app.jsonl; при rotation наблюдался WinError32. Эти записи не являются пользовательскими/live evidence. SQLite/tenant fixtures использовали временные каталоги. Исходные29providerresponse и3уникальныхfailure событий за11октября root сосчитал ДО этих прогона/синтетическихзаписей: дваparseотказа (pending_explanation_question_required и extra_forbidden), одинtenant_changed. Новых внешних provider/live/browser calls0; никакие исходные разговоры или секреты в Git не добавлены.

**Итог: общий PASS устойчивости диалога не получен.** Найдены восемь конкретных функциональных областей A1–A8; A9–A10 — вопросы области отказа/продуктовой границы. Цены как данные и исполнение точной выбранной строки подтверждены; выбор и контекст ещё требуют исправлений. Root сохраняет только данный отчёт. Branch/HEAD прежние, staging пуст, новых commit/push/PR нет; §46 WIP/foreign WIP сохранены. Следующий шаг — обсуждение владельцем этого списка и минимального плана, не автоматическая реализация предложений аудита.


## 48. Порядок работ и документальный checkpoint после аудита

Классификация: только документация. Пользователь попросил упорядочить дорожную карту, документы и Git, уточнить остаток работ. Root переносит обсуждённую группировку A1–A8 в актуальный верх Roadmap. Это не реализация и не принятие ещё не показанного формата/поведения. Обсуждение перед изменениями A4/A6/A7 сохраняется. Исторический статус «следующий шаг — обсуждение списка» в47.6 дополнен этим порядком, но продуктовые вопросы не закрыты автоматически.

Preflight: root/top C:/Cursor Projects/artgents-bot-active; branch codex/model-price-experiment; HEAD/baseline fe1ec48; origin/main и merge-base efa3f77; upstream синхронизирован (0/0), staging пуст. Exact allowlist документального checkpoint: docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md, docs/tasks/DEMO_D2_INTERFACE_TASK.md. Эти два документа включают ранее подготовленные отчёты46/47 и последние решения по UI45.3; они фиксируют WIP честно, не объявляют соответствующий код опубликованным. Runtime/data/tests46 и foreign14EOL MD/prototypes/три experiments не stage/commit.

Порядок: I=A1–A2 устойчивость текста/частей; II=A3–A4 выбор цены; III=A5–A7 карточка/история с особым контролем A6; IV=A8 transport replay и общий прогон. Внутри — целевые offline и один независимый Checker на связный checkpoint; повторная проверка по замечаниям. После этапа — Cursor/виджет владельца, затем отдельный commit/push. Если появляется архитектурный вопрос, зависимая работа останавливается до обсуждения. Изменения схемы варианта II и поведения III сначала показываются на простых примерах.

Статус46: scoped Checker PASS, результаты72PASS/8baselineFAIL; Cursor-подтверждение и успешная widget-приёмка не получены. Ошибка консультации стала основанием аудита47. Поэтому runtime46 не включается в документальный commit. Последний опубликованный runtime — fe1ec48 (§45). Сохранение отчёта46 в Git не означает сохранение его реализации в том же commit.

Четыре этапа закрывают найденные существенные разрывы основного пути, но не весь Roadmap. Затем ещё реализация согласованного UI/маркетинговых настроек45.3, цельные краткие/полные тексты и редакторский проход, остатки/актуализация тестов, общая приёмка. A9/A10 и ограничения истории/ввода остаются вопросами, не скрытыми новыми задачами. Нельзя объявлять основную перестройку завершённой до этих работ и обязательных проверок. Последующая настройка качества живой модели может идти отдельно после приёмки.

В этом checkpoint новых provider/live/browser calls0, runtime/tests не изменяются; тесты бота не запускаются для редакции документов. Проверка — согласованность статусов/границ, ссылки и staged diff --check. Перед commit нужен независимый read-only Checker документации. Никакие сырые логи, payload, .env и local DB не включаются.

## 49. Этап I — независимая приёмка частей ответа (A1–A2)

Owner GO: начать этап устойчивости ответа, затем строгая проверка Cursor на возврат сложности. Классификация: упрощение границы приёмки плюс исправление классификации локальных ошибок ссылок. До: whole-list model_validate и отдельные fatal model-reference ошибки отменяют пригодный соседний ответ. После: единственный parser принимает операции независимо, существующий исполнитель публикует принятые части и существующий результат unavailable для отклонённой части. Удаляемая зависимость — принятие обычной prose от optional metadata и корректности независимой команды. Владельцы смысла/цен/истории остаются по Target Contract §3.

Preflight: root/top C:/Cursor Projects/artgents-bot-active; branch codex/model-price-experiment; baseline/HEAD 1975eb3; origin/main/merge-base efa3f77; staging пуст. Exact allowlist: contracts/d2_dialogue_result.py; contracts/response_plan.py; core/d2_dialogue.py; core/d2_contacts_cta.py; core/response_plan_materialization.py; tests/test_d2_response_resilience.py (новый); docs/tasks/DEMO_D2_INTERFACE_TASK.md; docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md; docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md. §46 WIP, 14 EOL-only MD, prototypes/ и три экспериментальных файла остаются вне этапа.

Astra consultation: внутренний результат разбора должен представлять как принятую операцию, так и локальный отказ; это необходимая реализация уже согласованного partial-answer, не новый модельный формат или состояние беседы. Wire outcome/blocks/kinds прежний. Ordinary identity принадлежит серверному порядку; verified known-task identity остаётся строгой. Content-text проверяется отдельно от source/scope claims; неподтверждённые claims не дают UI/контекста/промо. Команды не чинятся и не расширяются удалением неверных параметров. Existing unavailable расширяется технической причиной invalid operation. Нет catch-all recovery, повторного parser, модели, адаптера назад к whole-list, semantic regex или новой памяти. Лимит отдельной ordinary prose 4000 удаляется при сохранении общего raw-envelope лимита; текст не обрезается. Настоящее clarification вместе с готовым content остаётся противоречием, не выбираем одно за модель. Все непригодные части, повреждённый JSON/root/admin conflict и tenant/auth/UI нарушения не превращаются в успешный ответ.

Пример: пригодный ответ о консультации + неверная команда цены → ответ сохраняется, ошибочная часть получает нейтральный технический отказ без чужой цены/кнопки. Проверки: JSON/SSE, исходный порядок, следующая история/replay, плохие metadata/команды, пустой текст, реальные UI/tenant/lead ограничения. Baseline до edits: test_d2_sim2_contract.py + test_d2_commercial_scope.py — 55 passed / 33 failed; failures старого commercial_fact в текущем дереве до изменений, отдельно от новых регрессий. Runtime ещё не изменён на момент записи. Provider calls0. Приёмка: targeted offline → независимый Checker → Cursor/виджет → commit/push после принятия.

### 49.1 Реализация и доказательства

Allowlist расширен до edits теста: tests/test_d2_price_reference_gaps.py. В нём request_id проверяется по серверному порядку; unknown detail теперь проверяется как failed completion без карточки/деталей/UI, а не как глобальный HTTP отказ. Tenant/source guards не ослаблены. Иные старые assertions не переписаны и не скрыты.

Удалено: обязательная whole-list приёмка ordinary результата, зависимость prose от optional claims, лимит4000 на content_text, глобальный отказ при missing price target и unknown ordinary detail/branch. Добавлено: внутренние D2ParsedDialogueResult/D2RejectedOperation (не wire и не память), одна техническая причина existing unavailable, существующие linkage-проверки учитывают unavailable contact/reference. Единственный parser принимает части, не повторяет валидацию всего результата после ремонта. Для content отдельно проверяются текст/уточнение и необязательные claims; при непригодных claims никакие их поля не переходят в UI/контекст. Цена/запись/контакты остаются строго типизированными; неверные параметры не удаляются для исполнения. Known-task binding и root/admin/tenant/auth остаются строгими. Ordinary request_id задаётся порядком сервера, не влияет на смысл. Первая отклонённая цена сохраняет ограничение первой цены: следующая откладывается, а не продвигается. Новых model calls, сценарных словарей, prompt repair, memory/state и converter обратно в старый envelope нет.

Итоговые наборы: logs/stage49-focused-final.txt —119PASS/2FAIL (42 новых,50 parser,29 price-reference); оба FAIL — прежнее ожидание трёх rows вместо выбранного таба. Чистый fe1ec48 (runtime идентичен1975eb3) в logs/stage49-baseline-gaps.txt воспроизвёл их:50FAIL/33PASS в старых content/price-reference наборах; остальные48 относятся к старым запретам ordinary prose и не чинятся этим этапом. logs/stage49-guards.txt —30PASS: foreign source/direction, source-follow-up, price-detail без модели, known-task binding, input boundary, lead cancel. В logs/stage49-final-targeted.txt ordinary-prose45PASS; там была одна регрессия alias requests, исправлена и перепроверена в последующих50 parser tests. Промежуточные падения из-за типизации claims исправлены, не объявлены baseline. Совокупность последних проверок по этим группам194PASS/2known baselineFAIL. Не полный CI, не живая модель/виджет. Fake-provider network запрещён фикстурами. Логи тестов/БД — локальные; начальный прогон выявил прежний WinError32 rotation, дальнейшие запуски имеют отдельный BOT_LOG_DIR. Сырые логи не коммитятся.

Независимый Checker запрошен; Cursor/widget ещё впереди. Staging пуст; provider/live/browser calls0. Код §46 не смешивается с итогом этого этапа и остаётся отдельно не принятым. Commit/push49 пока не делались.

### 49.2 Строгий Cursor review

Read-only, baseline1975eb3, branchcodex/model-price-experiment. Проверить exact allowlist49 и его test-only расширение, не включать §46/foreign WIP. Сначала тесты, затем обе HTTP цепочки до parser→executor→frozen response→history/replay. По AGENTS/WORKFLOW_CHECKER/TargetContract§3 проверить полное удаление ordinary whole-list зависимости, не только текущую фразу. REJECT при новом semantic gate/regex/списке фраз, дополнительном model call, второй памяти, fallback/repair/adapter назад к старому envelope, скрытом ослаблении цены/lead/privacy/tenant/UI и молчаливом выполнении испорченной команды. Проверить root/admin конфликт, полностью непригодный результат, ошибки command и optional claims, обе стороны mixed response, порядок, первую цену, rejected booking, известную кнопку/подмену её задачи, историю/replay. Проверить, что internal result не попадает в модельную схему, сессия не получила новых управляющих полей, а правила A3–A10 не реализованы скрыто. Не ослаблять assertions и не называть obsolete test зелёным; сравнить с baseline evidence. Не делать edits/provider/browser/SMTP/commit/push. Вердикт PASS/REJECT только49 с конкретными путями, удалённой зависимостью, рисками, тестами и WIP; полная архитектура этим не аттестуется.

Виджет после Cursor: новая беседа «Консультация бесплатная?»→«А КТ входит?»; новая «У вас есть Osstem?»→«Расскажите»; «Сколько стоит Nobel на один зуб?»→«Что входит?»; «Вы принимаете детей?»→«Сколько стоит лечение ребёнку?». Проверить связность ответа, exact карточку/отказ, follow-up, отсутствие лишнего начала записи. Эти вопросы не заменяют offline adverse-output проверки и не обещают исправления контекстных A3–A7.

### 49.3 Исправления по независимому Checker

Первый verdict REJECT: (1) optional-claims приёмка ошибочно распространялась на unfinished content task и могла удалить brand/volume/target перед сохранением уточнения; (2) несовместимость brand/extent для ordinal detail ещё отменяла весь ответ, в отличие от explicit offer_id. Оба исправлены в той же границе: мягкая приёмка только completed prose; unfinished content целиком проверяется прежним строгим operation type. У detail отдельно проверены captured source/action ownership и ограничения ordinary selector: несовместимый model selector локален независимо от формы, настоящая чужая привязка fatal.

Добавлены14 проверок:4HTTP JSON/SSE для pending (нет кнопок и сохранённой урезанной задачи);8HTTP для ID/ordinal и brand/extent конфликта;2pure foreign history/action. Recheck logs/stage49-recheck.txt:104PASS/2FAIL — два FAIL были ошибкой импорта в новых тестах, не runtime; исправлены, точечный повтор2PASS (logs/stage49-ownership-recheck.txt, затем прямой импорт из response_plan_session также2PASS). Совокупность последних групп208PASS/2known baselineFAIL. Старые assertions не ослаблены. Повторный Checker — только findings и затронутые защиты; до его вердикта этап не принят. Provider/live/browser calls0, staging пуст, commit/push нет.

Итог независимого focused Checker: PASS только§49, оба P1 закрыты. Собственные12read-only probes PASS (корректная pending-задача, оба selector, локальные конфликты, чужие history/action); test weakening не найден. Подтверждено удаление ordinary whole-list зависимости, отсутствие repair/fallback/model calls/wire-полей/памяти. Cursor и виджет остаются обязательной следующей остановкой; A3–A10 и весь D2 не аттестуются. Код после recheck не менялся, только записан вердикт. Commit/push49 не выполнялись.

### 49.4 Приёмка Cursor и владельца

Владелец подтвердил: «В виджете ок». Получен Cursor PASS только§49(A1–A2): удалена общая зависимость ordinary списка от ошибки одной части; внутренние dataclass не входят в model schema/session; строгие pending/price/booking и ownership сохранены. Новых сценариев, памяти, fallback, model fields/calls и скрытых A3–A10 нет.

По отчёту Cursor: основной offline-набор232PASS/3FAIL, отдельные guards50PASS/1FAIL. Два price-reference FAIL — прежнее ожидание трёх rows вместо выбранного таба; structured-output FAIL — прежнее ожидание9kind вместо6; detail known-action FAIL — проверка подстроки «входит» при ответе «В стоимость входят», HTTP200 и запрете provider. Это не зелёный полный CI; старые проверки остаются долгом. Новые resilience проверки прошли. Новых provider/live/browser/SMTP вызовов со стороны агентов0; пользовательская проверка виджета учтена отдельно.

Приёмка разрешает отдельный commit/push exact allowlist49 от1975eb3. §46, прочие MD, prototypes и экспериментальные файлы исключены. Следующий этапII требует согласования способа передачи явно названного варианта; этим PASS весь бот не закрыт.
