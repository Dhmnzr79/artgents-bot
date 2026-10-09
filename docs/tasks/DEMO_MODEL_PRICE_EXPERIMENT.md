# Эксперимент: ценовые ответы модели

## Явная область коммерческого вопроса — checkpoint C1, 2026-10-09

Owner GO после обсуждения: различать общий/scoped/неясный коммерческий вопрос.
Класс дефекта: missing target превращается в clinic, хотя модель могла потерять
явно названную услугу; в compound соседняя price scope не доказывает commercial
scope. Проверены live логи кариес/installment и whitening price+discount; это
подтверждённые semantic ошибки, не техническое падение и не регрессия KB2.

Классификация: архитектурное упрощение с исправлением контракта. Before → after
→ removed dependency: optional commercial target=none → обязательный явный
clinic/service/topic target в завершённой задаче либо unresolved+clarification
в pending → удаляется автоматическое достраивание отсутствующей области до
clinic. Единственный owner области — модель по §3. Существующий код проверяет
применимость фактов; ни текстовый классификатор, ни перенос из соседней операции,
ни second call/retry/fallback, ни новая память не добавляются. Pending commercial
использует существующий clarify_task/TTL/UI service click. Неизвестна область
уже распознанной commercial задачи; неизвестный сам предмет вопроса здесь не
получает нового pending_question/универсального сценария.

Содержательная операция: непустые fact_ids либо прежнее promotion_scope.
Общая область выражается ClinicTarget только в commercial; общий Target других
операций не расширяется. Existing promotion_scope остаётся независимым намерением
подбора: general=общий список (в том числе рядом с scoped direct facts), service=
прежний service profile, shown=прежние опубликованные promos. Нельзя запрещать
согласованный scoped direct fact + general promos или изобретать topic promo
selection. Пропущенная/невалидная форма остаётся прежним строгим отказом границы;
это не гарантия, что модель никогда ошибочно не выберет explicit clinic.

Preflight: C:/Cursor Projects/artgents-bot-active; codex/model-price-experiment;
HEAD 6108ac956e9589ac6a162f28d37c62844d24e02e; origin/main/merge-base efa3f77.
Staging пуст; pre-existing KB2 (15 файлов) + 2B WIP сохраняются целиком.
Exact C1 allowlist (8): contracts/d2_dialogue_result.py;
core/one_call_prompt_contract.py; tests/test_d2_commercial_route_fixes.py;
tests/test_d2_attribution.py; tests/test_d2_sim3_completion_context.py;
tests/test_d2_sim2_dialogues.py; tests/test_d2_commercial_scope.py; этот документ.
Клиентские данные и materializer не менять. Тестовые general fixtures получают
explicit clinic по смыслу; scoped fixtures сохраняют свои targets. Нельзя
добавлять автоматическое clinic-default к production parser или общему fake raw.

Acceptance: actual sent schema запрещает omitted/null/unresolved complete scope
и пустую задачу; generic/scoped/excluded по разным фактам; price+discount
не противоречат; pending→verified click без model call, textual follow-up→один
call, replay/next context, forged/stale/foreign click, pending TTL. Независимые
части сохраняются для корректного pending; invalid whole envelope по-прежнему
строгий. Offline/Checker; provider/live/SMTP 0; без commit/push.

Evidence C1: `c1-adverse-final.xml` — 38 passed, 0 failed, 31.86s на
финальном новом test file: scope/schema, две формы empty rejection, разные
факты/scopes/exclusions, compound whitening, pending service click/text/topic
change, term+независимый address, forged/stale/foreign/expired UI, replay.
`c1-prompt-final.xml` — 10 passed, 0 failed, 6.86s после устранения противоречия
старого общего перечня target и коммерческого clinic exception в instructions.
Actual schema/compound/term и pre-existing 2B input/known-task assertions зелёные.
Первичный `c1-scope.xml`: 104 passed, 2 failed только в новой TTL fixture
(несуществующий store.commit); исправлен тест через прежний isolated SQL activity
pattern. Прежние 72 commercial route cases в этом run прошли, runtime не менялся.
Основной `c1-final.xml` — 244 passed, 0 failed, 228.13s: новая коммерческая
форма + существующие SIM2 contracts/dialogues, attribution, SIM3 completion
context и 2B input. Runtime contract старше запуска; четыре adverse/term кейса
позже начала этого набора полностью проверены отдельным 38 PASS.
По P2 редакционному замечанию Checker общий закрытый перечень target заменён
ссылкой на формы соответствующей операции, без runtime изменения;
`c1-checker-recheck.xml` — 6 passed, 0 failed, 2.35s на конечной инструкции.
Client data неизменны, `git diff --check` чист. Live понимание модели этим
offline не доказано. Независимый Astra Checker PASS только C1: blockers/test
weakening нет, P2 prompt исправлен; traced pending→stored task→verified click,
explicit scope и отсутствие missing→clinic. XML 244/38/6 PASS прочитаны.
KB2/2B и модельные цены не входят в эту аттестацию. Staging пуст; без commit/push.

Widget acceptance: владелец проверил ответы и сообщил «Все ок».
Owner GO: сохранить KB2 и C1 отдельными коммитами и push; 2B оставить локально.

Commit isolation evidence: c1-staged-final.xml — 126 passed, 0 failed; C1 на сохранённом KB2 без 2B, provider 0.

## Снятие legacy-policy зависимости — checkpoint KB2, 2026-10-09

Owner GO: после объяснения, что D2 не использует marketing.yaml, но shared
loader требует его, владелец согласовал отделение действующего каталога D2
от старых маркетинговых настроек. Консультация Astra: общий каталог через
наследование без нового runtime decision layer и без new-to-old adapter.

Классификация: архитектурное упрощение. Before → after → removed dependency:
D2 snapshot/captured rebuild создаёт ResponseSchemaBundle с обязательными
marketing/strategy → создаёт ResponseDataCatalog с прежними data checks;
legacy bundle наследует каталог и добавляет только старые policy checks →
удалены вызовы legacy YAML parsing/validation и влияние этих файлов на D2
fingerprint. Единственный owner цен/коммерческого выбора — прежний D2 resolver
по §3; финансовые тексты всё ещё собирает код. Старые инструменты продолжают
явно использовать legacy bundle. Нет defaults legacy policy, конвертера,
второго snapshot object, semantic branch, retry/model call/memory.

Preflight: C:/Cursor Projects/artgents-bot-active; codex/model-price-experiment;
HEAD 6108ac956e9589ac6a162f28d37c62844d24e02e; origin/main и merge-base efa3f77.
Staging пуст. Сохранить пять pre-existing 2B WIP файлов, включая untracked
tests/test_d2_price_catalog_input.py; core/d2_live_provider.py не менять.

Exact KB2 allowlist (15 файлов): contracts/response_schema.py;
contracts/d2_tenant_snapshot.py; contracts/response_plan_post_composer.py;
core/response_schema_loader.py; core/d2_tenant_snapshot.py;
core/d2_snapshot_sources.py; core/service_reference_catalog.py;
core/one_call_active_service_catalog.py; core/one_call_commercial_fact_catalog.py;
core/service_data_context.py; core/response_plan_fact_projection.py;
core/response_plan_fact_policy.py; tests/test_response_schema_loader.py;
tests/test_d2_tenant_snapshot.py; этот документ.

Все client files сохранить. Это снятие runtime-зависимости, не удаление
legacy YAML из папки и не retirement legacy tooling/onboarding. Проверить
отсутствующие/испорченные legacy YAML, неизменные fingerprint/view/prompt/sources,
constructor sentinel, общие data guards, JSON/SSE commercial/replay/context,
tenant/privacy и прежнюю обязательность политики для legacy loader.
Offline и независимый Checker; provider/live/SMTP 0, без commit/push.

Evidence KB2: `kb2-final.xml` — 230 passed, 0 failed, 86.38s: schema contract,
legacy loader/external refs, D2 snapshot/commercial contract, pre-existing 2B
input assertions и все commercial JSON/SSE route cases. `kb2-guards.xml` —
26 passed, 0 failed, 18.58s: новые data guards, snapshot/source/prompt equality,
JSON/SSE price/replay/next context, installment exclusion, lead privacy и
foreign-tenant pending. Первичный `kb2-catalog.xml`: 138 passed, 1 failed —
новая family-price fixture использовала amount вместо min_amount; исправлена,
содержательная проверка неизвестной услуги сохранена. Это не runtime failure.
`git diff --check` чист. Client files побайтно неизменны. Независимый Astra
Checker PASS KB2: blockers/test weakening нет; подтверждены удаление D2
legacy parsing/validation/fingerprint зависимости и сохранность data guards.
230 final + 10 final recheck + 26 guards JUnit прочитаны независимо.
После запуска final исправлены только endings трёх annotation-only файлов;
`kb2-final-recheck.xml` на финальном runtime: 10 passed, 0 failed, 13.54s,
snapshot + JSON/SSE replay/next context и lead privacy/tenant boundary.
Независимый trace отмечается отдельно.

Commit isolation evidence: kb2-staged-final.xml — 44 passed; staged KB2 без C1/2B, provider 0.

## Чистка коммерческой базы — checkpoint KB1, 2026-10-09

Offline evidence: `kb1-targeted.xml` — 37 passed, 0 failed, 22.51s.
Набор: commercial contract, 2B input projection, JSON/SSE price/discount
compatibility, qualified free consultation + replay, unknown-fact strict guard.
Новый тест меняет только facts.json, проверяет обе формы через реальный
snapshot source builder и запрещает чтение диска после capture.
`git diff --check` чист; facts.json и весь MD-корпус не изменены.
Provider/live/SMTP: 0. Commit/push разрешены владельцем после PASS; результаты — в сообщении о checkpoint. Независимый Astra Checker:
PASS KB1, blockers/test weakening нет. Все шесть удалённых строк точно совпадают
с сохранёнными facts; старые поля отвергаются, authority/resolver/context traced.
2B WIP и полная очистка базы в PASS не входят.

Дополнительно перед коммитом: `kb1-staged.xml` — 32 passed, 0 failed, 19.23s.
Общие модули загружены из Git index, provider — из HEAD: KB1 проверен без 2B.

Owner GO после read-only аудита Astra: «не понимаю, где править акции/маркетинговые
факты; давай сделаем чистку базы». Первый coherent checkpoint ограничен удалением
ручных копий short/full текста между facts и D2 commercial. Ни даты, ни цифры,
ни условия, ни промо-политика не меняются. Promo MD с уникальными объяснениями и
legacy marketing/strategy/microfacts зависимости — следующие отдельные шаги;
этот checkpoint не объявляет всю базу очищенной.

Классификация: архитектурное упрощение. Before → after → removed dependency:
тексты вручную записаны в facts.json и d2_commercial.json, загрузчик требует
совпадения копий → в D2 commercial только упорядоченные fact_id, существующая
authority материализует текст из captured facts → удалены второй редактируемый
источник и обязательная синхронизация. Текст short/full принадлежит facts.json;
выбор формы, порядка и применимости — прежним D2 resolver/evaluator по §3.
Старые поля и чтения удаляются, старый формат не поддерживается. Нет адаптера,
двух форматов, классификатора, состояния, памяти, retry или новых model calls.

Preflight: C:/Cursor Projects/artgents-bot-active, codex/model-price-experiment,
HEAD fadf71cc9ab332fb7c3aab0c86ae8373e12efb1b; origin/main и merge-base efa3f77.
Staging пуст. Pre-existing WIP: пять файлов 2B выше/ниже; сохранить все hunks.
Точный дополнительный allowlist: clients/demo/target_response/d2_commercial.json;
contracts/d2_tenant_snapshot.py; core/d2_tenant_snapshot.py;
core/d2_snapshot_sources.py; tests/test_d2_commercial_contract.py;
tests/test_d2_price_catalog_input.py; этот документ. core/d2_live_provider.py —
WIP 2B, в KB1 не изменять. facts.json и весь MD-корпус побайтно сохраняются.

Для автора клиента после KB1:
- text_fact / microfact_text, active и даты, allowed/excluded scope —
  target_response/pricebook/facts.json;
- ссылки/порядок promo_facts и service_profiles, пакеты дополнений и группы
  несовместимости — target_response/d2_commercial.json;
- цены/состав/этапы — target_response/pricebook/services/*.json;
- marketing.yaml не редактировать для D2: это пока обязательный legacy-файл,
  не действующая политика D2; снятие его зависимости ещё не выполнено;
- promo MD пока остаются самостоятельными источниками дополнительных объяснений.
  Их консолидация не разрешает потерять уникальные условия или ослабить обещания.

Acceptance: одна правка только facts меняет обе формы ответа без синхронизации
commercial; exact прежние ответы/order/CTA/replay/context; неизвестный, inactive,
non-promo и foreign ID, отсутствие короткой формы, scope/exclusions, duplicate
meaning и поддельные UI по-прежнему проверяются; старые text fields отвергаются;
authority использует captured bundle без чтения диска после snapshot.
Offline → independent Checker. Provider/live/SMTP budget 0; commit/push разрешены владельцем.

## Текущее продолжение — checkpoint 2B, 2026-10-09

Owner GO: модель формулирует финансовый ответ; код сохраняет выбор допустимых
предложений и структурные проверки. Непригодная финансовая часть не публикуется,
независимые части сохраняются с честным спокойным пробелом. Без второго вызова,
retry и автоматической подстановки кодовой прозы. Проверенные price/detail clicks
получат один вызов вместо нуля. Эти изменения исполнения — следующий checkpoint;
2B их ещё не включает и не меняет таблицу ответственности §3.

2B — подготовка входа, не архитектурное упрощение и не включение модельных цен.
Before: thin fact identity и direction IDs без полного offer price/package/stages.
After: полная структурированная проекция того же captured tenant bundle до
единственного вызова, без выбора по свободной реплике. Кодовый selector/auto-promo
resolver остаются владельцами окончательного набора. Новых решений не удаляется;
проекция не является памятью, кешем или вторым каталогом на диске.

Preflight: C:/Cursor Projects/artgents-bot-active, codex/model-price-experiment,
HEAD fadf71cc9ab332fb7c3aab0c86ae8373e12efb1b; origin/main и merge-base efa3f77.
Working tree и staging чистые; foreign WIP нет.

Exact allowlist: contracts/d2_tenant_snapshot.py; core/d2_tenant_snapshot.py;
core/d2_live_provider.py; tests/test_d2_price_catalog_input.py; этот документ.
База клиента, parser, selection, renderer, HTTP, storage и quotas не изменяются.

Проекция содержит все offers без фильтрации (включая inactive и no_public_price),
все price modes/amounts/currencies/units, package includes/excludes, stages,
applicability/required conditions; services и options с активностью и selection;
полные факты с прежними fact_id/labels, условиями, датами, exclusions;
существующий commercial pack с профилями/пакетами/совместимостью. Null/defaults
сохраняются. Thin COMMERCIAL_FACT_CATALOG в ordinary prompt заменяется полными
fact rows с теми же identity fields; parser catalog не меняется. Directions,
brand catalog, весь MD corpus и user context сохраняются. Known-task prompt
побайтно прежний. Ввод не разрешает модели финансовую прозу до следующего
checkpoint. Расширенный вход может изменить live-выбор операций; offline PASS
не является аттестацией live-понимания. Provider/live/SMTP budget 0.

### Продолжение 2B после KB2/C1 — 2026-10-09

Owner GO: «Делаем» после плана фиксации 2B и последующего эксперимента.
Repository/Git top: C:/Cursor Projects/artgents-bot-active; branch codex/model-price-experiment;
HEAD 39329895ded64688892ed372fa9473cca67aaaed; origin/main/merge-base efa3f77.
Staging пуст. Только прежний 2B WIP (точный allowlist из пяти файлов выше); foreign WIP нет.
Тип: подготовка входа, не включение ценовой прозы и не архитектурное упрощение.
§3 owners неизменны; база клиента/known-task/renderer/selector остаются прежними.
Повторить focused offline input + snapshot + provider проверки на базе KB2/C1,
с изолированными БД/логами и заблокированной сетью, затем фиксация checkpoint.
Предыдущий Checker PASS 2B относится к этому же runtime diff; новый review нужен
при изменении механизма, а не при сохранении уже проверенных файлов.
Provider/live/SMTP budget 0.

### Evidence 2B

В модель передаются 33 offers, 23 services и 10 facts. Offers сериализованы
целиком, включая UI followups; уникальные клиник-approved поля не отбрасываются.
В services опущены aliases/content_ref/roles/family/service_value_ref: названия и
identity уже в существующих service/reference catalog; selection/options остаются
точными, option aliases/content_ref не копируются. Никакой фильтрации по вопросу.
Новый обязательный атрибут D2ModelView — производная captured projection,
не поле ответа, wire или состояния сессии.

`2b-current-http.xml`: 22 passed, 0 failed, 21.86s. Новый input/catalog guard,
captured no-I/O, known-task byte equivalence, snapshot, цена+discount/installment,
exclusions и verified document click/replay по JSON/SSE.
`2b-input.xml`: 8 passed, 7 failed в старых fixtures price_modes/rec2 mixed.
`2b-baseline.xml`: те же семь имён падают на исходных contracts/snapshot/provider
из fadf71c, загруженных только в память; рабочие файлы не подменялись.
Старые тесты не изменены и не ослаблены. Baseline failures не закрыты.

System prompt: 154074 → 198419 символов (+44345); новый price block 37687 символов,
остальной рост — полные коммерческие факты вместо thin identity. Остальные
system-блоки и весь user prompt побайтно прежние. Это подготовка полного входа,
не экономия токенов. Реальный tokenizer/provider usage не измерялся. Сокращение
данных без потери условий и вопрос поддерживаемой strict schema остаются открытыми.
JSON object transport не менялся. База клиента побайтно не менялась.
Staging пуст, commit/push/merge/deploy не выполнялись; diff --check чист.

Независимый Checker 2B: PASS, blockers/test weakening нет. Проверены реальный
captured→model view→prompt путь, сохранность offer/fact fields, прежний known-task,
неизменность parser/selector/renderer/memory/quota и оба JUnit/baseline. PASS только
для подготовки входа; архитектурное упрощение, модельные цены, живой выбор и
экономия токенов не аттестованы. Следующий checkpoint — модельный финансовый
результат и согласованный локальный отказ части, затем verified price/detail call.

### Evidence сохранения 2B на базе KB2/C1

`2b-after-c1-guards.xml`: 50 passed, 0 failed, 41.46s (input, snapshot, C1 scope/UI/replay).
`2b-after-c1-final.xml`: 14 passed, 3 failed; все три старых prompt assertions
воспроизведены на HEAD-only runtime в памяти (`2b-after-c1-baseline.xml`: 2 passed, 3 failed).
Ожидают v19/прежнюю content_ref phrase/старый D2_DIRECTION_PRICE header.
Не изменены и не ослаблены. Новых regression failures не найдено.
Independent Checker PASS на текущей базе: captured projection, полные facts/IDs,
known-task byte path, selectors/parser/renderer/C1 pending/memory неизменны.
Это preparation-only PASS, не включение модельных цен. `git diff --check` чист.
Provider/live/SMTP 0; owner разрешил фиксацию 2B отдельным checkpoint.

## Статус и сохранённая точка

Owner GO — 2026-10-09: сохранить нынешнюю работу и подготовить отдельную ветку
для эксперимента. Этот checkpoint — **только документация**. Модельные ценовые
ответы ещё не включены; локальный бот по-прежнему собирает их кодом.

- Одна рабочая папка: `C:/Cursor Projects/artgents-bot-active`.
- Ветка эксперимента: `codex/model-price-experiment`.
- Baseline: свежий `origin/main`, `efa3f773bcf10891e2997addf8bbec38c7ae1317`.
- Сохранённый тег: `checkpoint/pre-model-price-2026-10-09` на том же commit.
- PR [#22](https://github.com/Dhmnzr79/artgents-bot/pull/22) влит с сохранением
  истории checkpoint-коммитов после всех пяти зелёных CI checks.
- Локальный архив: `C:/Cursor Projects/_recovery_backups/artgents-bot/20261009T130441Z-pre-model-price`.
  Git bundle проверен; четыре SQLite backup прошли проверку целостности.
  `.env`, логи и локальные файлы сохранены вне Git. SIM-0 находится в архиве.

Это сохранённый **локальный baseline**, не аттестация production-бота.
Deploy и новые live/provider-вызовы на этом шаге не выполнялись.
Зелёный CI не закрывает все ошибки живого понимания модели.

## Цель

Проверить вариант, в котором модель пишет весь ценовой ответ, включая состав,
этапы и оплату, по компактным структурированным данным клиники. Пользователь
предпочёл этот эксперимент варианту с одной модельной вводной и кодовым телом.
Сохранить один вызов модели на ход и существующие границы tenant, заявки,
privacy, медицинской политики и подлинности UI.

Текущая таблица ответственности — `DEMO_D2_TARGET_CONTRACT.md` §3. Этот файл
сам по себе её не меняет. До реализации нужно явно описать экспериментальную
границу точных данных и модельного текста, включая поведение при неверном ответе.
Аудит — источник предложений, а не разрешение внедрить каждую находку.

## Порядок работы

1. **Общие ошибки связей.** Проверить привязку ссылок модели к каталогу,
   применимость и несовместимость коммерческих фактов, наблюдаемость usage и
   `finish_reason`, открытый вопрос цены без цели. Правки должны помогать обоим
   вариантам ответа. Для обычной ценовой части с отсутствующим ID/обзором
   владелец подтвердил сохранение независимых частей и честный ценовой пробел
   (см. уточнение ниже); произвольные новые исходы не придумывать.
2. **Компактный вход модели.** Измерить фактический prompt, убрать повторение
   данных и ненужные для этого входа метаданные. Данные клиента пока не удалять.
   Проверить, поддерживает ли фактический provider строгую схему. Экономию токенов
   подтверждать измерениями, а не предполагать по размеру файлов.
3. **Минимальный эксперимент.** Согласовать точный allowlist и критерии,
   затем заменить кодовую ценовую прозу модельной в экспериментальном пути.
   Суммы, единицы, «от», состав и условия остаются из утверждённых данных.
   Не добавлять второй вызов, retry, классификатор или параллельную память.
   Проверка чисел сама по себе не доказывает правильность всех условий текста.
4. **Сравнение.** Сначала offline: transport, кнопки, клики, контекст следующего
   хода и неблагоприятные ответы модели. Затем живые диалоги и виджет с отдельно
   разрешённым жёстким бюджетом. Сравнить естественность, точность, токены,
   задержку и невалидные ответы. Сохранить доступный владельцу отчёт вне Git.
5. **Решение по результату.** Принять эксперимент, доработать или оставить
   сохранённый кодовый вариант. Переход в `main` — отдельный PR после проверок
   и решения владельца; автоматическое переключение между вариантами не вводить.

Удаление старого сборщика **входит в дальнейший план**, но не является условием
первого эксперимента. Мёртвые параметры можно удалять отдельными проверенными
изменениями. Массовое удаление legacy, отдельный D2 renderer и cache снимка —
позднее, с доказательством реально удалённых путей. Файлы `marketing.yaml`,
`clinic_strategy.yaml`, `price_microfacts.yaml` и алиасы не удалять по названию:
сначала проверить их чтение, fingerprint, validators и CI.

## Данные и запуск тестов

Для D2-диалогов эксперимента использовать существующий `D2_DIALOGUE_DB_PATH`
с отдельным локальным SQLite-файлом и новые беседы. Это также отделяет demo
quota, хранящуюся в этом файле. `.env` на этом checkpoint не менялся.
Настройка не переносит lead/session `bot.db`: её отдельную изоляцию при тестах
заявки нужно обеспечить до таких тестов. Нельзя объявлять все БД изолированными
только по установке `D2_DIALOGUE_DB_PATH`.

Все offline-прогоны используют temporary DB/логи/tenant pack и блокируют сеть.
Архивы, реальные диалоги и provider payload не коммитить. Старые базы и
зарегистрированные worktree не удалять. Не переключать грязный checkout.

## Открыто и отложено

- Whitening root-array/невалидный envelope и неверный выбор второго врача —
  исторические live-находки. После §36 владелец проверил оба сценария успешно;
  их текущее воспроизведение не установлено. Offline CI не гарантирует live-понимание.
- Цена без цели и неизвестные ID за пределами согласованной обычной ценовой
  части остаются отдельными вопросами. Частичный ответ для отсутствующего
  ценового ID/обзора согласован ниже, но пока не реализован.
- Чистка корпуса клиента и единый источник повторяющихся фактов — позднее,
  после карты использования. Качество и простота модерации важнее удаления строк.
- Админка и отдельная очередь пометок ошибок — будущая задача, сейчас не добавлять.
- Старые разрешения на 8/20/2 live-вызова не являются бюджетом этого эксперимента.
  На текущем checkpoint provider/live/SMTP calls: **0**.

## Этап 1 — checkpoint 1A, owner GO 2026-10-09

Владелец разрешил начать первый этап с offline-проверками, Checker, Cursor и
последующей проверкой виджета. Baseline checkpoint: `3c78cc0` на
`codex/model-price-experiment`; `origin/main`/merge-base `efa3f77`.
Preflight: staging и working tree пустые, foreign WIP отсутствует.

Классификация 1A: **bug fix**, не архитектурное упрощение и не закрытие этапа 1.
Два независимых дефекта исправляются до решения о новых исходах ссылок:

- Группа «скидка или рассрочка» привязана к `pterygoid_implants.default` вместо
  существующего факта `installment_12`. Меняется только ошибочная связь данных;
  authored-условие, суммы и единственный resolver совместимости сохраняются.
- Существующее событие `provider_finished` получает ограниченные числовые
  usage и allowlisted `finish_reason` до разбора content. Наблюдение не меняет
  исход хода, лимиты, число вызовов или wire; сырые payload/ПД не экспортируются.

Exact allowlist:
`clients/demo/target_response/d2_commercial.json`, `core/d2_diagnostics.py`,
`tests/test_d2_commercial_route_fixes.py`, `tests/test_d2_provider_observation.py`,
`docs/tasks/DEMO_MODEL_PRICE_EXPERIMENT.md`.

Acceptance: цена птеригоидного импланта без рассрочки не получает ложное
пояснение несовместимости; опубликованные скидка + рассрочка получают его один
раз; отрицательный/недоступный факт не учитывается. Общий механизм fact/offer
совместимости проверяется отдельно на явно заданной тестовой группе.
JSON/SSE, completion/replay, ошибка пустого/обрезанного content, отказ observer
и отсутствие ПД в диагностике сохраняются. Один fake transport call, 0 live.

Общая граница ссылок checkpoint 1A не заменяет. На его baseline D2-116 запрещает
превращать чужие/некорректные ссылки в мягкий пробел; authored gaps для бренда
и неактивной услуги имеют отдельные основания. Нет настроенного обзора известной
темы сейчас даёт ошибку всего хода. Последующее решение владельца о частичном
ответе записано ниже; runtime этого решения пока не выполнен.
Проверки нельзя переносить перед детской/payment/brand policy: это изменит
принятую очередность. Следующий checkpoint должен удалить разрозненные решения,
а не спрятать их за новым fallback или prompt.

Актуальная widget-обратная связь владельца: после §36 вопросы про отбеливание
и второго врача отработали успешно. Старые ошибки — исторические наблюдения;
сейчас их воспроизведение не установлено, полной гарантии live-понимания нет.

### Evidence 1A

На неизменённом runtime корректные новые D2 fake cases воспроизвели дефекты:
`red-valid.xml` — 17 failed, 3 passed; причина падений — отсутствующие metrics
и ошибочная группа совместимости. Предварительные collection/fixture ошибки
runner не являются runtime-аттестацией и были исправлены перед этим прогоном.

Финальные тесты на текущем коде:
- `tests/test_d2_provider_observation.py`, полный
  `tests/test_d2_commercial_route_fixes.py`, `tests/test_d2_commercial_plan.py`:
  **88 passed**, 104.82s, 0 failures/skips.
- Четыре выбранные защиты из `tests/test_d2_diagnostics.py` (параметризация
  даёт 9 cases): **9 passed**, 2.14s, 0 failures/skips.

Runner и JUnit находятся вне Git в локальной temporary-папке `d2-stage1-5omr8j_3`:
`runner.py`, `red-valid.xml`, `green.xml`, `observer-guards.xml`.
Runner отключает dotenv, подставляет только dummy credentials для SDK import,
блокирует сеть; HTTP fixtures изолируют tenant packs, SQLite, логи и quotas.
Команда основного прогона (путь runner — из указанной temporary-папки):
`.venv/Scripts/python.exe <runner.py> green tests/test_d2_provider_observation.py tests/test_d2_commercial_route_fixes.py tests/test_d2_commercial_plan.py`.
Связанные проверки: тот же runner с label `observer-guards` и selectors
`test_late_clock_failure_preserves_result_exception_and_context`,
`test_close_exception_identity_is_preserved_even_when_sink_fails`,
`test_real_logger_does_not_inject_request_context`,
`test_startup_snapshot_has_only_scoped_code_hash` в `tests/test_d2_diagnostics.py`.

Baseline failures в этих выбранных существующих suites не выявлены; исторические
D1 fixture suites целиком не аттестованы. `git diff --check` чист.
Provider/live/SMTP: 0. Staging пуст; commit/push/merge/deploy не выполнены.
Независимый Checker: **PASS 1A**, блокеров/test weakening/scope creep нет;
прочитал финальные JUnit и фактический путь provider/materialization/replay.
Cursor: **PASS 1A**. Владелец проверил widget; наблюдения и отдельный открытый
дефект выбора коммерческих блоков записаны ниже. Owner разрешил commit/push 1A.
Не закрывает общую границу ссылок, весь этап 1 или готовность модельных цен.

### Открыто после widget-проверки — лишние коммерческие блоки, 2026-10-09

Cursor передал PASS 1A. В просмотренных шести пользовательских widget-ходах
ответы завершились успешно, `finish_reason=stop`: ложное предупреждение при
одной цене не появилось, при скидке вместе с рассрочкой пояснение выводилось
один раз. Это подтверждает два исправления 1A, но не закрывает весь этап 1.

На вопрос «Какая скидка и есть ли рассрочка на птеригоидные импланты?» модель
в одном ходе запросила общие акции клиники и дополнительно этапы оплаты.
Сервер исполнил допустимые операции: появились посторонние акции, включая
отбеливание, и сообщение об отсутствии порядка оплаты. Соседние ответы
выбирали нужные условия по услуге; ещё один ход снова добавил лишние этапы.
Это отдельный открытый дефект качества выбора, не сбой транспорта или `length`.

Следующая задача: проверить неоднозначность существующих `fact_ids`,
`promotion_scope`, target и `price_detail_aspect`, а также различение условий
рассрочки и порядка оплаты. Цель — ответ по запрошенной услуге без посторонних
акций и незапрошенных деталей для всего класса подобных вопросов.
До реализации — консультация Astra и конкретное before → after с владельцем
решения по §3. Не добавлять серверное угадывание лишних блоков, правила под
отдельные фразы, новый классификатор, retry или второй вызов модели.
Запись задачи не разрешает новый механизм и не меняет порядок уже согласованных
работ. Точный scope и место исправления определить после разбора; в 1A оно
не входит и пока не реализовано. Новые live-вызовы для этой записи не выполнялись.

## Следующая часть этапа 1 — согласован частичный ценовой ответ, 2026-10-09

Owner GO на примере «Сколько стоит отбеливание и где вы находитесь?»:
когда обычную ценовую часть нельзя разрешить из-за отсутствующего в текущем
каталоге модельного ID или известной темы без настроенного обзора, готовый
независимый ответ (например адрес) не теряется. Ценовая часть честно сообщает
о недостатке данных/невозможности дать цену и возможности уточнить её у
администратора. Другая цена, услуга или ближайший похожий ID не подставляются.
При доступных данных публикуются обе части. Правило относится к классу составных
вопросов, не к фразе про отбеливание. Для одиночной ценовой части применяется
тот же результат этой части; наличие адреса не условие её исполнения.

Это узкое уточнение D2-116 по обычным модельным ценовым ссылкам. Подтверждённые
нарушения tenant/UI/privacy остаются отказом. Структура envelope, подлинность
клика, другие fact/policy/source ID и принятая очередь детской/payment/brand
policy не ослабляются этим решением. Единую границу нужно спроектировать с
удалением прежних разрозненных решений, без нового классификатора или retry.
На момент согласования изменение ещё не было реализовано. Очередность:
Cursor/widget для 1A, затем отдельный allowlist и проверки этой части.
Реализация и приёмка 1B записаны ниже; весь этап 1 этим не закрывается.

### Checkpoint 1B — общая граница ordinary price, owner GO 2026-10-09

Baseline `cbe4628` (1A сохранён и pushed), та же ветка
`codex/model-price-experiment`, чистый checkout, staging пуст, foreign WIP нет.
Классификация: архитектурное упрощение узкой ценовой границы и согласованное
изменение исхода отсутствующих данных; не полное упрощение D2.

До: отсутствие overview обрывает snapshot binding, затем отдельная проверка
membership scope обрывает материализацию всех частей. После: ordinary price
разрешается materializer по текущему проверенному снимку; отсутствующий ID
или обзор даёт существующий price failure, независимая часть сохраняется.
Удаляемая зависимость: snapshot binding и предварительная membership-проверка
больше не принимают решение о доступности обычной цены. Единственный владелец
этого решения — существующая материализация price по §3.

Astra проверила общую границу: низкоуровневый `_d2_price_block` также используется
price_detail, поэтому его строгие ownership проверки не смягчаются. Отсутствующая
ordinary-price услуга получает gap только в существующей обработке ordinary price.
Подтверждённый чужой source/session/view/UI/offer остаётся fatal. Детская/payment/
brand policy и проверенные клики сохраняют прежнюю очередь и авторизацию.
Исполняется первая цена; последующие остаются deferred, без поиска замены.

Exact allowlist: `core/d2_snapshot_sources.py`,
`core/response_plan_materialization.py`, `tests/test_d2_price_reference_gaps.py`,
`tests/test_d2_demo_snapshot.py`, `tests/test_d2_price_deferral.py`,
`docs/tasks/DEMO_MODEL_PRICE_EXPERIMENT.md`.
Allowlist расширен одним существующим deferred-тестом: отсутствие обычного ID
раньше называлось foreign без доказательства tenant mismatch; новое ожидание
проверяет сохранение первой цены и отсутствие публикации отложенной.
Проверки: JSON/SSE, цена отдельно/с адресом в обоих порядках, неизвестные service/
topic и известная тема без обзора, доступная цена, replay/следующий context,
первый/последующий отсутствующий ID; price_detail, tenant/UI и policy guards.
Без live-вызовов, новых полей, fallback, классификатора, второго вызова или памяти.
Порядок приёмки: Checker → Cursor → widget; результаты записаны ниже.

#### Evidence 1B

Runtime реализован в двух указанных файлах. Удалены snapshot overview gate,
membership helper и оба его reachable вызова; отсутствующий ordinary target
разрешается внутри существующей price-materialization обработки, без общего
catch ownership errors. Строгий общий price/detail helper не изменён.
Отсутствующий direction сохраняет исходный topic без поиска другой услуги;
чужая authority найденного direction отклоняется.

Артефакты в прежней temporary-папке `d2-stage1-5omr8j_3` вне Git:
- `1b-red.xml`: 22 failed на исходном runtime. Contact fixture затем исправлена
  на действующее `contact_address`; red не является отдельной аттестацией
  составных contact случаев с ошибочным тестовым payload.
- `1b-final-guards.xml`: **47 passed**, 44.51s, 0 failures/skips, окончательный
  runtime и тесты. Проверены ordinary gaps, порядок адреса, completion/replay,
  следующий provider context без старых offers, deferred порядок, strict detail,
  foreign snapshot/direction, volume/detail клики без модели и policy precedence.
- `1b-ui-auth.xml`: **1 passed**, 3.20s: forged/stale/foreign service click
  отклонены до provider.
- Более широкий `1b-final.xml`: 48 passed, 8 failed. Все восемь неизменённых
  старых assertions воспроизведены на двух runtime-файлах из `cbe4628` в
  изолированном `baseline_runner.py` (`1b-baseline.xml`: те же 8 failed).
  Это старые expectations content copy и legacy detail payload; не исправлялись.
  Старый snapshot assertion про implantation также уже не задавал отсутствующий
  overview; заменён на текущую canonical whitening без настроенного overview.

Прогон: прежний network-blocked `runner.py`, label `1b-final-guards`,
`tests/test_d2_price_reference_gaps.py`, новый snapshot selector и deferred
selector; актуальные selectors из `test_d2_sim2_dialogues.py`: volume/followup,
price-details known action, null target policy/reference, child policy;
`test_d2_commercial_route_fixes.py::test_unknown_fact_remains_strict_and_does_not_publish_sibling`.
Отдельный label `1b-ui-auth` для
`test_d2_sim2_dialogues.py::test_service_authenticity_before_provider`.
Network blocked, временные БД/tenant packs; provider/live/SMTP calls: **0**.
`git diff --check` чист. На момент review staging пуст, foreign WIP отсутствует;
1B commit/push ещё не выполнялись. Независимый Checker: **PASS 1B**; прочитал фактические пути
ordinary price/verified clicks/detail, JUnit и точное совпадение baseline failures.
Подтвердил удаление заявленных gate/helper/calls, отсутствие ослабления проверок
и сохранение policy precedence. Cursor: **PASS 1B** по переданному владельцем
review. Владелец подтвердил успешную widget-проверку 1B: составной вопрос
с ценой/адресом в обоих порядках и обычный ценовой ответ. При доступной цене
она публикуется; недоступные модельные ID отдельно проверены offline.
Checkpoint 1B принят для сохранения commit/push. Модельные цены, весь этап 1
и UI ошибок этим PASS не закрываются.

#### Widget-наблюдение владельца — оформление кодового ответа, 2026-10-09

На вопрос «Сколько стоит отбеливание и где вы находитесь?» на скриншоте
показаны доступная цена от 18 000 ₽ и адрес. Это успешный ответ с доступными
данными, не демонстрация ценового gap. Владелец отметил неудачную подачу
кодовой сборки: цена/условия, контактные сведения, скидка и общие маркетинговые
фразы выглядят разрозненно, без естественной связи между частями.
Прямое решение владельца: пока оставить оформление как есть, без runtime
правок. Сохранить этот составной вопрос для будущего сравнения с модельными
ценовыми ответами: проверить связность, краткость и отсутствие незапрошенных
вводных при сохранении точных сумм, единиц и условий. Замечание о подаче
само по себе не означает принятия всех widget-сценариев 1B и не разрешает новый
фильтр/вызов модели/изменение выбора данных.

## Обязательно перед демонстрациями — сообщение сбоя в обычной ленте

Владелец отметил красный блок ошибки как важный недостаток демонстрационного UI.
Нужно вывести понятную техническую фразу как обычное сообщение от бота:
нормальный цвет текста, без красного фона, обводки или warning-оформления.
Текущий текст из `static/widget/api.js`: «Не получилось показать ответ.
Понимаю, что это неудобно». Предлагаемый: «Сейчас не получилось ответить.
Понимаю, что это неудобно. Попробуйте задать другой вопрос.»
Обычная подпись имени бота, без ссылки на материалы клиники.

Отдельный presentation checkpoint: серверная ошибка и её логи сохраняются;
не создавать успешный completion, не менять маршруты/контракты/число вызовов,
не сбрасывать SID/заявку и не утверждать её исход. Продолжение возможно при
допускающем его состоянии, существующие quotas/spam/privacy остаются в силе.
Технический сбой не называть доказательством «в базе нет информации».
Не сводить задачу к перекраске прежней панели: сообщение должно быть в ленте
бота. Имеющиеся controls повторной отправки/новой беседы проверить отдельно;
автоматический retry/reset не добавлять.

Точки реализации: `setError`/`renderFeed` в `static/widget/widget.js`,
`.clinic-shell__error` в `static/widget/widget.css`, копия в `static/widget/api.js`.
При согласовании был записан только план. Реализация и evidence — в 1C ниже;
до демонстрации требуются Cursor и widget acceptance владельца.

### Checkpoint 1C — спокойное отображение сбоя, owner GO 2026-10-09

Baseline `b56db62`, ветка `codex/model-price-experiment`; preflight: чистая
рабочая папка/staging, foreign WIP нет; `origin/main`/merge-base `efa3f77`.
Классификация: presentation bug fix, не архитектурное упрощение.
Существующий `errorLine` показывается обычным bot turn в feed, с plain-подписью,
без записи в messages/server completion и без отдельной красной панели.
Это временное отображение текущего сбоя: очищается при следующем запросе,
повторе или явном reset как прежняя панель. Существующие manual retry/new chat
controls сохраняются; новые вызовы, автоматический reset/retry не добавляются.
Серверные статусы, логирование, последняя опубликованная UI revision и заявка
не меняются. Сообщения demo quotas сохраняют отдельную копию и действующие лимиты.
Config error вне диалога не меняется.

Exact allowlist: `static/widget/widget.js`, `static/widget/api.js`,
`static/widget/widget.css`, `tests/js/d2_widget_harness.mjs`,
`tests/js/d2_error_copy.mjs`, `docs/tasks/DEMO_MODEL_PRICE_EXPERIMENT.md`.
Acceptance: ошибка внутри feed как обычный текст, только имя бота; нет source
подписи/клинического CTA/технических деталей, повтор сохраняет request ID,
продолжение сохраняет SID, reset только явный, quota copy не заменена общим
сбоем. JSON/SSE/network/accepted UI preservation и браузерный DOM/CSS offline.
Checker → Cursor → widget. Live/provider/SMTP budget 0.

#### Evidence 1C

Удалены отдельный dialogue error DOM-slot и его `errBox` writer. `setError`
теперь обновляет прежний errorLine; renderFeed выводит его через обычные bot
классы и plain attribution. Manual retry/new chat controls перенесены туда же.
CSS добавляет только раскладку этих controls; config error CSS не менялся.
Новых сообщений в серверной/клиентской истории, payload, revision или вызовов нет.

- `node --check static/widget/widget.js` и JS harness: PASS.
- `node tests/js/d2_error_copy.mjs`: PASS — JSON/SSE/network copy, сохранение
  accepted UI, прежний same-ID transport replay и отдельные quota сообщения.
- Network-blocked offline runner, label `1c-browser-verified`,
  `tests/test_d2_widget_replay.py::test_real_d2_payloads_render_and_retry_in_browser`:
  **1 passed**, 19.99s. Это headless browser с реальными D2 fake-provider
  HTTP-payloads, mock browser fetch и временными tenant/БД.
  DOM/CSS: ошибка внутри feed, цвет как у обычного текста, plain имя без source,
  без красной панели/клинического CTA; явный retry с прежним request ID,
  продолжение с тем же SID, quota copy и явная новая беседа.
- Старый harness остановился на `scope UI missing`: искал volume через link
  selector, хотя baseline уже использует chips. Selector актуализирован без
  ослабления label/ref/ui_revision/click assertions. Точная ошибка воспроизведена
  на виджете/harness из `b56db62` во временном `1c-baseline-harness.mjs`.
  Mock reply теперь привязывает SID к текущему запросу для проверки продолжения
  без reset; это browser fixture, не runtime изменение tenant/authentication.

Артефакты/JUnit/payloads вне Git в `d2-stage1-5omr8j_3`; сырой пользовательский
диалог не копировался. Provider/live/SMTP calls: 0. `git diff --check` чист.
Шесть файлов allowlist, staging пуст, foreign WIP нет; commit/push не выполнялись.
Независимый Checker: **PASS 1C**; проследил API callbacks, все setError callers,
feed/controls/retryBody, отсутствие поддельного completion и ослабления tests.
Focused recheck добавленной проверки нового SID после явного reset:
ослабления нет, runtime PASS сохраняется. Cursor/widget acceptance ещё впереди.

Cursor: PASS 1C; владелец проверил виджет и подтвердил обычное оформление сбоя.
Дополнение по просьбе владельца: controls «Повторить» / «Новая беседа» оформлены
компактными чипсами без заливки, с фирменной обводкой 1px и круглым радиусом.
Изменение только CSS внутри error-actions; callbacks, запросы и остальные
ghost-кнопки не меняются. Дополнение — presentation bug fix.
Над чипсами отступ 10px по последнему уточнению владельца. Focused Checker
подтвердил изоляцию chip CSS и сохранение focus-style; финальный отступ —
только CSS, `git diff --check` чист. Owner GO: сохранить 1C и продолжить.

### Checkpoint 2A — измерение входа и компактная сериализация, 2026-10-09

1C сохранён и отправлен: `7c78ea3723042523ea3de489abfd10914d50a62c`.
Baseline 2A — тот же commit, ветка `codex/model-price-experiment`;
`origin/main`/merge-base `efa3f77`, working tree/staging чистые, foreign WIP нет.
Exact allowlist: `core/d2_live_provider.py`, этот файл.
Классификация: оптимизация представления, не архитектурное упрощение.
Owner GO — продолжить подготовку эксперимента. Модельные цены ещё не включены.

Offline измерение реального ordinary prompt Demo до изменения:
- system: 158917 символов; user начального запроса: 701;
- APPROVED_MD_CORPUS: 115588 символов, 58 документов;
- D2_OPERATIONS_INSTRUCTIONS: 14067;
- JSON schema: 17510 без заголовка;
- остальные каталоги/заголовки и разделители составляют остаток.

В JSON схемы удаляются только сериализационные пробелы: 17510 → 16160
символов. Экономия 1350 символов, около 0,85% исходного system prompt.
Ни title, ни descriptions, defaults, constraints, required, discriminator,
$defs или другие поля не удаляются. Ожидаемый system после: 157567 символов.
Known-task path не содержит эту схему и должен остаться побайтно прежним.
Весь корпус, каталоги, context, IDs, порядок offers, policy и binding сохраняются.
Количество символов — не количество токенов и не доказанная экономия расходов:
локальный tokenizer отсутствует, реальные provider calls запрещены бюджетом 0.

Astra consultation: начинать с сериализации; не удалять blanket null/defaults,
документы, service/brand/source bindings или catalog IDs. Основной объём — корпус;
более существенное сокращение требует отдельной карты использования/дублирования.
Оно пока не выполнено, весь этап 2 этим checkpoint не закрывается.

Transport сейчас посылает `response_format={type: json_object}`; `llm.py`
передаёт kwargs SDK без запрета json_schema. Это не подтверждает фактическую
поддержку strict schema endpoint/model. Transport/схема проверки не переключаются.

Acceptance: decoded JSON отправленной схемы полностью равен прежнему,
все остальные system/user части ordinary и known-task побайтно равны baseline;
сохранены полный корпус, ограничения clarification и валидность prompt examples.
Offline → независимый Checker → Cursor; provider/live/SMTP budget 0.

#### Evidence 2A

Network-blocked сравнение с исходником provider из `git show 7c78ea3`:
decoded schema полностью равна baseline и текущему `D2DialogueResult`;
ordinary остальные system/user части совпадают побайтно. Все 58 полных MD
сохранены. Known-task system/user совпадают побайтно (system 117703 символа).
Ordinary system измерен: 158917 → 157567 символов, ровно 1350 разницы.
Числовые отчёты `2a-prompt-inventory.json`, `2a-equivalence.json` вне Git,
в прежнем temporary artifact root `d2-stage1-5omr8j_3`; сырые prompt/ПД не сохранены.

`2a-prompt-guards.xml`: 8 passed, 1 failed. Прошли фактически отправленная схема,
шесть prompt examples через parser и изоляция authorized explanation/known task.
Единственный fail `test_prompt_contains_the_complete_tenant_fullcontext_corpus_and_policies`
ожидает устаревшую инструкцию `content_ref: exact filename ...`.
`2a-baseline.xml` подтверждает тот же fail на provider из `7c78ea3`.
Содержательная отдельная проверка полного корпуса и равенства схемы прошла;
старый тест/промпт под его строку не менялись.

Тесты не изменялись; staging пуст, provider/live/SMTP 0; commit/push 2A не выполнялись.
Независимый Checker и Cursor проверяют только этот узкий checkpoint;
весь этап 2, дубли корпуса и модельные цены ещё не закрыты.
Checker: PASS 2A, блокеров/test weakening/scope creep нет; прочитаны отчёты
равенства и оба JUnit. Следующий шаг — Cursor review этого узкого diff.
