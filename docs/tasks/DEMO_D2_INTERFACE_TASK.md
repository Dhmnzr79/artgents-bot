# D2 — интерфейс модели: подготовка следующего checkpoint

Дата: 2026-10-02. Статус: DOC-only подготовка разрешена; runtime GO ещё нет.
Единственный план работ — верх [Roadmap](DEMO_D2_DELIVERY_ROADMAP.md).
Правила: [AGENTS](../../AGENTS.md), [Checker](../WORKFLOW_CHECKER.md),
[контракт §3](DEMO_D2_TARGET_CONTRACT.md), [Acceptance](DEMO_D2_ACCEPTANCE.md).

Обязательный контроль: [Audit change-map discipline](../../AGENTS.md#audit-change-map-discipline)
и [Mandatory change-map check](../WORKFLOW_CHECKER.md#mandatory-change-map-check).
Переход к следующему этапу, новая ветка поведения или преобразователь к старой
структуре не разрешаются этой карточкой автоматически. Проект ниже не является
runtime GO. В финальном отчёте отдельно перечислить удаления, добавления и их
основание, изменения поведения, offline/live/widget проверки и остаточные риски.

## 1. Baseline и сохранение работы

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
предлагается pending_question вместо content_text: поля взаимоисключающие;
pending_question не публикуется. Это замена двойного смысла, не копия вопроса
в нескольких состояниях. После разрешённого выбора модель получает готовую
задачу с этим вопросом и возвращает только объяснение. Перед runtime GO
ревьюер проверяет форму всех текущих content/detail parameter consumers;
новое поведение при невозможном уточнении не придумывается.

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

## 5. Приёмка / дальнейшие решения

Offline: фактически отправленная схема; отказ старой/рекурсивной формы;
известная цена; genuine unresolved + scoped click/replay/next input;
content/detail pending; mixedprice+prose в обеих очередностях; JSON/SSE;
tenant/stale/forged/foreign/medical/lead/privacy. Сохранить исходный смысл
adverse тестов, не подгонять fixtures ради PASS. Доказать удаления по call graph.
Затем independent Checker, отдельно разрешённый live/widget, Cursor gate.
Перед реализацией уточнить exact runtime allowlist по потребителям и показать
его владельцу в preflight. Текущий DOC allowlist не разрешает runtime edits.

Открытые продуктовые вопросы НЕ блокируют подготовку интерфейса:
общий unit-reference для разных услуг; B14 против желания отвечать на обе
независимые цены; удаление автопромо — только идея. Не считать их решёнными.
История3пары/1000символов/TTL30мин — текущие ограничения, не полная память диалога.
D2-114 residual financial prose risk остаётся принятым; новые verifier/retry
или обрезание текста не добавлять как стандартное решение.

## 6. Handoff для нового чата

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
