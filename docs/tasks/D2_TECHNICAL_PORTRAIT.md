# D2 — технический портрет бота для внешнего архитектурного review

> **Исторический снимок на 2026-09-21, не текущая инструкция.** После него
> локальные `/ask`, `/ask/stream` и widget подключены к D2, а FullContext
> уже собирается. Текущий порядок и демо-договор — в
> [Delivery Roadmap](DEMO_D2_DELIVERY_ROADMAP.md) и
> [Target Contract](DEMO_D2_TARGET_CONTRACT.md). Описания ниже о ещё не
> подключённом HTTP или следующем CP5-M1 относятся только к этому снимку.

Дата снимка: 2026-09-21. Репозиторий: `artgents-bot`.
Ветка снимка: `codex/demo-d2-service-volume`.
Последний подтверждённый code baseline: `b66dc5c` (CP5-B13a).
`origin/main` / merge base: `141ce91`.

Статус документа: объяснительная карта для опытного разработчика без доступа к
репозиторию. Это не замена коду, тестам, Git diff или обязательному read-only
Checker review. При расхождении действует репозиторий и нормативные документы,
перечисленные ниже.

## 1. Зачем существует D2

Проект строит диалогового бота клиники. В production сейчас нет ни бота, ни
пользователей. Существующий локальный `/ask` и `/ask/stream` — одноразовая база
для сравнения, а не совместимость, которую требуется сохранять.

Цель D2 — заменить обычный диалог одним runtime:

- один вызов модели на обычный пользовательский ход;
- один D1R prompt и один production parser структурированного ответа модели;
- один владелец обычного dialog state и результата хода;
- typed tenant data с изоляцией клиник;
- один окончательный response/UI plan;
- один renderer после freeze плана;
- отсутствие второго смыслового анализа пользовательского текста в Python;
- отсутствие fallback на старый runtime.

Lead/privacy, tenant isolation, заявки, typed UI ownership и transport-защиты
сохраняются. Старые semantic selectors, Composer, `sales_fast` и старая ordinary
memory должны стать недостижимыми из normal answer path после переключения D2.

## 2. Нормативные источники

Порядок приоритета:

1. `AGENTS.md`;
2. `docs/tasks/DEMO_D2_EXECUTION_LOCK.md`;
3. `docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md`;
4. `docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md`;
5. `docs/tasks/DEMO_D2_TARGET_CONTRACT.md`;
6. `docs/tasks/DEMO_D2_PRODUCT_DECISIONS.md`;
7. `docs/tasks/DEMO_D2_ACCEPTANCE.md`;
8. процессные prompts исполнителя и Checker.

Исторические архитектурные отчёты и старые чаты помогают понять происхождение
решений, но не переопределяют этот список. Текущий незакоммиченный аудит
коммерческого слоя остаётся проектом до независимого PASS и commit.

## 3. Что было до D2

Локальный HTTP-путь построен вокруг прежней one-call/sales-fast архитектуры:

```text
/ask или /ask/stream
  → app.py
  → orchestrate_sales_one_plus_ask_turn
  → orchestrate_sales_fast_widget_turn
  → run_sales_fast_widget_turn
  → Composer / legacy selectors / presentation
  → HTTP или SSE
```

Эта цепочка содержит накопленные детерминированные выборщики темы, услуги,
объёма, цены, маркетинга, политики и UI. Часть смысла определяется моделью,
часть — дополнительными selectors до и после неё. Коммерческие данные имеют
несколько перекрывающихся способов связи:

- `initial_commercial_blocks`;
- `priority_service_promos`;
- `service_automatic_commercial`;
- global amplifier lists;
- `promotion_overview`;
- исторические `scenario_rules`;
- `offer.fact_refs`;
- попарный `incompatible_with`.

Она продолжает обслуживать только локальный baseline. D2 не обязан поддерживать
её внутренние контракты и не должен вызывать её при собственной ошибке.

## 4. Два фактических состояния системы

Важно не смешивать два утверждения:

### 4.1 Локально доступный бот сейчас

HTTP и widget используют legacy one-call/sales-fast путь. D2 не подключён к
`/ask`, `/ask/stream` или browser widget.

### 4.2 Внутренняя сборка D2

D2 существует как отдельный внутренний entry:

```text
run_d2_dialogue_turn
  → privacy-safe provider input
  → один provider call
  → production D1R parser
  → typed context binding
  → tenant snapshot и source authorities
  → D2 resolver/materializer
  → frozen response plan
  → text renderer + UI projection
  → atomic state/result commit
```

Этот путь вызывается тестами и ограниченным live harness, но не HTTP. Он уже
доказывает общий каркас, однако остаётся узким: entry ожидает один поддержанный
ценовой request и содержит экспериментальные gates и названия ошибок.

## 5. Основные модули текущего D2

### `core/d2_dialogue.py`

Текущий orchestration service одного D2 turn:

- резервирует `(tenant, session, request_id)` до model call;
- строит privacy-safe provider input;
- загружает tenant snapshot и session context;
- вызывает один provider;
- передаёт raw ответ production parser;
- связывает typed continuation с сохранённым контекстом;
- вызывает `resolve_d2_envelope_response`;
- формирует новый typed state;
- атомарно сохраняет state и replayable result;
- после commit допускает одну попытку lead effect dispatcher.

Ограничения текущей версии:

- только один request в envelope;
- narrow price-oriented shape;
- experimental errors `d2_experiment_*`;
- флаг `common_route_direct_service_only`;
- запрет service-price `fact_refs` проверяется уже после materialization;
- часть continuation invariants повторно проверяется перед persistence.

Это один внутренний entry, но ещё не общий пользовательский runtime всех A/B.

### D1R prompt и parser

`core/one_call_prompt_contract.py` содержит единственный production prompt
понимания запроса. `core/one_call_envelope_protocol.py` разбирает raw JSON модели
в typed envelope.

Модель отвечает за понимание свободного текста: части вопроса, service/topic,
continuation, statement mode и ситуацию. Код валидирует IDs и связи, но не
должен повторно определять смысл пользовательского текста regex или словарями.

### Tenant snapshot

`core/d2_tenant_snapshot.py` и `core/d2_snapshot_sources.py` загружают typed
данные конкретной клиники и создают source authorities для materializer.

Основной принцип: у каждого вида данных один владелец. Каталог владеет услугой,
прайс — суммой и единицей, commercial facts — акцией и условиями, материалы —
информационным текстом, UI/CTA schema — разрешёнными действиями.

Тесты используют временную копию production demo tenant pack, а не скрытые
test-only данные.

### Typed context

`core/d2_session_context.py`:

- проецирует свежий контекст с TTL;
- связывает D1R envelope с предыдущим typed state;
- создаёт plan focus;
- переносит ситуацию только по typed continuity, не по истории текста.

Целевой TTL обычного контекста — 30 минут бездействия. Lead state и replay не
должны исчезать вместе с ordinary context.

### Materializer и resolver

`core/response_plan_materialization.py` содержит две архитектурные эпохи:

- старую materialization цепочку с legacy offer/marketing selection;
- `resolve_d2_envelope_response` и D2 price/content blocks.

D2-функция не вызывает `select_target_marketing` в доказанных сценариях.
Однако `_d2_price_block` всё ещё может вызвать `project_target_service_offers`
в общей ветке, если не задан authored direction order и не включён узкий direct
service mode. Поэтому legacy authority ещё не полностью вытеснен из D2-модуля.

После materialization `core/response_plan_resolver.py` применяет ограничения
плана. Затем `core/response_text_renderer.py` и
`core/response_ui_projection.py` создают видимый текст и UI.

Целевой invariant: после freeze ни renderer, ни widget, ни transport не выбирают
данные заново и не меняют смысл.

### Store

`core/d2_dialogue_store.py` — единственный владелец D2 ordinary state и точного
результата:

- SQLite transaction;
- один inflight request на session;
- конфликт одинакового request ID с другим payload;
- atomic state/result completion;
- exact replay без повторного model call;
- PII-free receipt внешнего lead effect;
- `unknown` effect не получает автоматический retry.

Store не интерпретирует текст пользователя и не выбирает услугу.

### Legacy marketing owner

`core/target_marketing_selector.py` остаётся полноценным владельцем legacy
marketing selection и используется старой архитектурой. Он умеет выбирать
promos/amplifiers по нескольким старым mappings, history и compatibility links.

Цель CP5-M2 — сделать этот selector недостижимым из D2 route, а не удалить его
до HTTP cutover. Физическое удаление legacy запланировано позже.

## 6. Состояние доказательств

Сценарий считается собранным только если он прошёл через общий внутренний entry
`run_d2_dialogue_turn`. Unit/seam-тест отдельного resolver или selector не
доказывает пользовательский сценарий.

### Доказано

- **A08:** два хода «известная ситуация → цена → другое направление» через
  parser, tenant snapshot, materializer, renderer и persistent state.
- **CP1:** production prompt/parser принимает расширенный typed D1R для A08.
- **CP2:** A08 получает цены и условия из production demo tenant data.
- **CP3:** A08 ограниченно проверен настоящей моделью: два разрешённых вызова.
- **CP4:** reservation, atomic state/result, replay, isolation и lead-effect
  receipt во внутреннем D2 route.
- **A10a:** узкое same-topic price continuation из настоящего предыдущего D2
  turn с TTL-gated typed carry.
- **B13a:** одна простая опубликованная цена услуги с режимом `from`, единицей и
  условием, без commercial facts.

### Не доказано

- D2 через `/ask`, `/ask/stream` и widget;
- полный A10 или B13;
- остальные A01–A12 и B01–B17;
- общий commercial response;
- все price modes в assembled common route;
- HTTP/SSE replay и parity;
- недостижимость legacy от реального endpoint;
- физическое удаление legacy;
- качество и latency полного D2 runtime.

Некоторые неподтверждённые семьи имеют unit/seam-компоненты. Корректная
формулировка — «не собраны и не доказаны», а не обязательно «работа не начата».

## 7. Почему сценарии упрощаются

A01–A12 и B01–B17 — acceptance examples, а не 29 production routes. Если каждый
пример реализовывать отдельной веткой, временные gates и service flags образуют
вторую архитектуру.

Оставшийся CP5 должен дробиться по общим механизмам:

- commercial profile;
- continuation и choice;
- multi-part request;
- policy/availability;
- terminal и lead;
- directory/content/UI.

Дополнительная услуга уже доказанного механизма — data-driven test case, а не
новый resolver и не новый checkpoint только по имени услуги.

## 8. Упрощённый коммерческий ответ

Текущий незакоммиченный governance checkpoint предлагает следующий target.
До независимого PASS это проект следующего канона, а не доказанный runtime.

### 8.1 Один commercial fact

У факта один стабильный ID:

```text
commercial_fact
  id
  kind
  short_form
  full_form_or_source_ref
  active_dates
  applicability
```

Короткая форма используется при автоматическом дополнении. Полная — при прямом
вопросе об акции или другом commercial fact. Это не два независимых факта.

### 8.2 Один профиль услуги

```text
service_commercial_profile
  promo_refs
  price_booster_id
  also_list_id
```

- `promo_refs`: до двух коротких применимых акций;
- `price_booster_id`: 0 или 1 готовый пакет ценового усилителя;
- `also_list_id`: 0 или 1 готовый пакет «Также мы предлагаем».

В каталоге клиники пакетов может быть несколько; у каждого имя и содержание.
Код не склеивает пакеты и не набирает пункты «Также» из fact refs. Длину
текста задаёт редактор. Нет ссылки — блока нет, цена сохраняется.

D2-O4 закрыто D2-090. Числовые caps «Также 1–3» (D2-064) и «Также 0–5»
(D2-087) этим же решением отменены: действует один пакет, не длина списка.

### 8.3 Compatibility groups

```text
incompatibility_group
  offer_or_fact_ids
  explanation_text
```

Если в plan вошли два элемента одной группы, они показываются как альтернативы
с готовым текстом клиники. Код не скрывает второй элемент, не складывает выгоды,
не выбирает вариант за пациента и не применяет глобальное предположение
«скидка всегда несовместима с рассрочкой».

### 8.4 Видимый результат

- Первый содержательный вопрос о конкретной услуге: основной материал и до двух
  коротких применимых акций.
- Первый прямой вопрос о цене: цена, единица, обязательные условия, до двух
  коротких акций, необязательный один пакет усилителя и необязательный один
  пакет «Также».
- Прямой вопрос об акции: полная форма того же fact ID; direct request может
  повторить ранее автоматически показанную акцию.
- Несовместимость: обе применимые альтернативы и authored explanation.

Commercial blocks должны попасть в единый plan до freeze. Renderer не должен
добирать акции после плана.

## 9. Предлагаемая последовательность ближайшей работы

Текущий проект roadmap задаёт:

1. независимый PASS документационного commercial audit, включая D2-090;
2. CP5-M1 — commercial data contract в существующем tenant snapshot;
3. CP5-M2 — один D2-native commercial plan до freeze;
4. CP5-M3 — assembled A02/A11/B08 через `run_d2_dialogue_turn`.

CP5-M1 не должен подключать runtime. CP5-M2 должен убрать достижимость legacy
marketing selection из D2 commercial path. Только CP5-M3 доказывает собранные
пользовательские сценарии.

HTTP cutover относится к CP6, удаление legacy — к CP7, итоговый evidence pack —
к CP8.

## 10. Неподвижные запреты

Нельзя:

- fallback «D2 не справился → legacy»;
- выбирать runtime по услуге, сценарию или ошибке;
- второй prompt/parser обычного диалога;
- второй ordinary state или двойную запись памяти;
- второй tenant-data или wire contract;
- compatibility fields «временно» без отдельного решения;
- semantic inference из raw user text после D1R;
- service-specific production branches;
- выдавать helper/unit test за assembled scenario;
- подключать HTTP до завершения CP5;
- делать live/provider calls без явного разрешения и бюджета.

## 11. Основные риски

### Архитектурные

- Экспериментальные gates могут размножиться вместо исчезновения.
- Большой materializer содержит legacy и D2 обязанности в одном файле.
- Общая ветка D2 price selection пока может достигать legacy offer projection.
- Continuation invariants частично повторяются в materializer и turn service.
- Поздний запрет `fact_refs` проверяет результат после сборки, а не выражает
  правильный contract до freeze.
- Один внутренний entry формально общий, но пока принимает узкую price shape.

### Продуктовые

- D2-090 закрыл stacking усилителей и числовые caps «Также», но пакеты ещё
  не выражены в tenant data и runtime.
- Short/full presentation может стать двумя расходящимися фактами, если loader
  не закрепит один ID и общую applicability.
- Compatibility без authored patient copy вернёт молчаливое скрытие предложений.

### Доказательные

- Большое число зелёных unit-тестов может создать ложное ощущение готового бота.
- Fake provider доказывает wiring, но не понимание живого русского текста.
- Внутренний D2 route не доказывает HTTP/SSE/widget.
- Проверка одного сервиса не доказывает data-driven общий механизм.
- Малый live-набор не доказывает полное качество или надёжный p95.

### Процессные

- Два Cursor-чата видят один изменяемый working tree. Если исполнитель пишет во
  время review, Checker проверяет движущуюся цель.
- Внешняя browser-модель не видит Git, полный diff, тесты и достижимость функций.
- Архитектурное мнение внешней модели легко принять за фактический PASS.
- Незакоммиченный governance diff нельзя описывать как уже принятый baseline.

## 12. Как использовать внешнего эксперта

Внешней модели передают:

1. этот портрет с baseline и датой;
2. заполненный `D2_EXTERNAL_REVIEW_PACKET_TEMPLATE.md`;
3. безопасные точные выдержки из изменённых contracts/tests/code;
4. результаты назначенных offline tests;
5. список известных ограничений и foreign WIP.

Полезные вопросы внешнему эксперту:

- соответствует ли изменение заявленной целевой архитектуре;
- создаёт ли оно второй owner, contract, selector или route;
- действительно ли checkpoint сгруппирован по механизму;
- достаточно ли доказательств для заявленного уровня;
- какие риски пропущены в FUTURE SCOPE;
- есть ли противоречие в видимом поведении.

Внешняя модель не может подтвердить:

- что предоставленные выдержки полны;
- что функция реально достижима или недостижима в репозитории;
- что тест не ослаблен и действительно запускался;
- что allowlist и staging соблюдены;
- что foreign WIP не затронут;
- что секреты отсутствуют во всём diff.

Поэтому её результат называется **external architecture opinion**, а не
`Checker PASS`. Формальный PASS остаётся read-only проверкой реального working
tree по `docs/WORKFLOW_CHECKER.md`.

## 13. Короткий словарь

- **D1R:** единственный структурированный результат понимания запроса моделью.
- **D2 entry:** `run_d2_dialogue_turn`.
- **Assembled scenario:** сценарий, прошедший через D2 entry с настоящими
  parser, tenant snapshot, plan, renderer и state transition.
- **Seam/unit evidence:** доказательство отдельного компонента, не сценария.
- **Frozen plan:** окончательный набор текста, цен, условий, UI и state delta.
- **Legacy:** текущий локальный Composer/sales-fast runtime и semantic selectors.
- **Checkpoint:** ограниченный проверяемый шаг с allowlist, acceptance, tests,
  Ledger draft и независимым verdict.
