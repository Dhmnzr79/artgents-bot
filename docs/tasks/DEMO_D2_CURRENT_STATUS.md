# D2 demo — текущее состояние

## Подтверждённая выкладка и передача — 2026-10-16

PR [32](https://github.com/Dhmnzr79/artgents-bot/pull/32) объединён в main:
`f7629491f2bb93ed80e2f58aea53770841bbd6a3`, включает `8b0abd9` и лимиты НикаДент.
GitHub CI [38823531784](https://github.com/Dhmnzr79/artgents-bot/actions/runs/38823531784),
publish [38823531777](https://github.com/Dhmnzr79/artgents-bot/actions/runs/38823531777),
deploy [38823973366](https://github.com/Dhmnzr79/artgents-bot/actions/runs/38823973366) — SUCCESS.
Владелец сообщил, что клиентский и демо-виджеты работают на VPS.
Новая независимая проверка серверного диалога/заявок в этом этапе не проводилась.
Нижние записи о подготовке кандидата и паузе публикации относятся к прежним этапам.

Создан только автономный UX-прототип: две конфигурации каталога, три вкладки,
общие формы с тестовым подтверждением. Runtime/клиентские данные не менялись.
Дальнейшая реализация — [отдельный этап и новый чат](THREE_TABS_DEMOS_HANDOFF.md).

## Локальные лимиты НикаДент — 2026-10-16

Владелец возобновил выпуск: commit/push и штатный VPS deploy после проверок.
На момент подготовки main/VPS ещё не менялись; серверный результат проверяется отдельно.
По новому ownerGO локально добавлены настройки features.yaml→usage_limits:
10сообщений/мин посетитель,40/мин tenant+IP,40AI-вопросов/24часа посетитель,
1000попыток модели/24часа клиника,1500символов,16КиБ запроса,3заявки/час.
Окна скользящие; новый чат/страница сохраняют browser bucket; удаление storage
или другой браузер меняют его — это не авторизация. Demo сохраняет прежние
AI-квоты, общий ограничитель размера HTTP защищает также Demo и /lead.
Счётчики durable/atomic, телефон/имя/вопросы в них не записываются. При отказе
AI остаются канонические контакты и CTA записи/согласие/приватные слоты без модели.
Четвёртая заявка не отправляется и не объявляется успешной; failed provider/send
attempts тоже учитываются. Переполненная ценовая операция не публикуется частично.

Проверки:32новых тестаPASS +9focused после исправления failed-retry throttle
(33уникальных новых сценария);236связанных regressionsPASS, включая browser,
consent,Nika prices,Demo quota,pack/page contracts. Независимый Astra CheckerPASS:
8focused +6внешних probes. Ника/template validators и diff--checkPASS.
GET локального config подтвердил Ольга/messageMaxChars1500; модель/SMTP0.
Этап подготовлен к commit/push;3foreignJPG сохраняются вне коммита.
Настройка/ограничения описаны в CLIENT_PACK_AUTHORING, Interface§82.

## Кандидат выпуска НикаДент — 2026-10-16

Owner разрешил проверку, commit/push и последующую выкладку на VPS. Текущая
ветка codex/nikadent-technical-onboarding / PR31; подготовка описана в Interface§81.
До подтверждения workflow deployment это локальный кандидат, не установленная
серверная версия. Статус VPS не выводится из зелёных локальных тестов.

Собраны: редактированная база НикаДент, явные цены/объёмы/условия, заявки на
gothica@mail.ru и vikadent2025@mail.ru, персонализация Ольга/#762E94/аватар,
меню по страницам и общий первый пункт «Давно не был у стоматолога», компактное
согласие, свёрнутый виджет, общая акция консультации. Исправлены предел1–3зуба,
применимость культевой вкладки и отдельная стоимость коронки, предварительная
запись, налоговая формулировка. Общий код используется Demo; alias cleanup Demo
сохраняет тексты/факты. Неподтверждённые вопросы хранятся отдельно от patientMD.

Уточнение исторической заметки ниже: прямой GET15октября подтвердил, что обе
юридические ссылкиHTTP200, а personal-data-consent содержит имя/телефон/заявки.
Ранняя заметка о cookies относилась к устаревшему поисковому кэшу. Проверка
содержания ссылки не является юридическим заключением.

Аудит изоляции:91проверкаPASS;11старых failures имеют те же имена/сообщения на
чистомHEAD2a2f2f1. Актуальные HTTP/SSE сценарии разделяют контекст/историю/цены/
кнопки/заявки при одинаковыхID и параллельных запросах. ЖивойVPS в том аудите
не проверялся. Переход страницы не должен сбрасывать диалог; полноценное
восстановление видимой переписки после reload этим выпуском отдельно не заявлено.

Проверка кандидата:1155PASS/5платформенныхSKIP в общем release-наборе после
точечного повторения10тестов с коротким временным путём Windows; открытых
падений нет. AstraPASS, актуальная браузерная проверка ценовых поясненийPASS.
GitHub CI/publish/deploy и серверные параметры НикаДент ещё не подтверждены.

## Первая чистка клиентских пакетов — 2026-10-15

Interface §71, owner GO по четырём отмеченным пунктам аудита. Из72 MD demo/НикаДент
удалены три устаревших поля (104 вхождения) и151 HTML alias comment; тексты,
якоря и действующие метаданные сохранены. Убраны45 алиасов, повторявших название
услуги. Для НикаДент добавлены четыре существующих CTA-варианта из demo, чтобы
20 документов имели соответствующую запись в tone. Шаблон: полный CTA-словарь,
заявки/админка/PG выключены до настройки, заготовка consent с пустыми реквизитами.
Валидатор проверяет согласие при включённой реальной доставке и ссылки CTA на tone.
Это data cleanup + bug fixes, не архитектурное упрощение D2. Ветка onboarding,
база8364092; модель/SMTP0, без merge/deploy. Marketing/strategy/doctor/family prices
в этой чистке не меняются. Проверки и точный allowlist — в карточке §71.
30 targeted +42 broader tests PASS;2 старых policy-replay теста воспроизводимо
падают на чистой базе8364092. Checker PASS. Проза/якоря/активные метаданные115MD
сохранены; MD-контекст меньше на17,739символов/9.67%. Live модель не вызывалась.

## НикаДент/demo — чистка старых стилей, 2026-10-15

Interface §69, owner GO: из общего виджета удалены 18 классов без создаваемой
разметки (старый launcher/видео-модалка/кнопки),4 неиспользуемых CSS-токена и
3 stale DOM lookups. Из загрузчика/НикаДент/шаблона удалены прежние поля цветов
action/button_1/button_2. Палитра brand/promo_background/promo_accent сохранена.
Активные price/menu/consent/inline-video и динамические video-aspect классы прежние.
Продолжение codex/nikadent-technical-onboarding, baseline5a9f0ba / PR31.
Это presentation maintenance, не D2 architecture simplification. Только локально;
VPS не меняется, фото остаётся локальным WIP. Проверки — в текущей карточке §69.
41 targeted tests + launcher/consent DOM PASS;8 скриншотов побайтно совпали.
Checker PASS. Старый price-detail browser test падает до браузера; идентичный
StopIteration подтверждён на чистой базе5a9f0ba. Provider/SMTP0, merge/deploy0.

## НикаДент — свёрнутый виджет concept1, 2026-10-15

§68, branch codex/nikadent-technical-onboarding / PR31, baseline50d61af.
Первый вариант из локального widget-concepts.html владельца: белая капсула,
SVG-avatar+зелёная точка, синяя стрелка. Через10с расширяется одним контейнером
с фиксированным bottom/right; close/Escape сворачивают, CTA открывает настоящий
чат. Прежняя отдельная bubble/scale удалена. Demo launcher сохранён.
Mobile320/390 и desktop900 проверены; reduced motion без morph. Существующие
текстовые поля widget_config.json, новых pack fields нет. В панели — повтор
приглашения, без сброса SID/messages/lead/consent. Once-per-session marker сохранён.

86 targeted offline tests PASS (onboarding/config/page menus/consent/current UI),
Chrome DOM launcher proof PASS: scheduled delay10000, actual avatar/white/green/
blue, fixed corner, close/Escape/chat reopen/draft preservation/seen marker/demo,
320/390/900 geometry and reduced motion. Только mocked video catalog GET3;
model/provider/SMTP calls0. Independent Checker PASS:30 config tests, panel-module
harness, actual call-path/diff review. diff--check PASS. CI на предыдущем50d61af
все5SUCCESS. На VPS/сайте клиента эта версия не проверялась и не выкладывалась.
Посторонние3otzyv.jpg сохранены; прежние historical replay2fail вне этапа.

## НикаДент — согласие перед сбором контактов, 2026-10-15

§67, continuation branch codex/nikadent-technical-onboarding / PR31,
checkpoint baseline2beb02b. Для реальной доставки сервер теперь требует
согласие до имени/телефона; demo_stub без изменений. В диалоге компактный блок:
пустой checkbox, короткая подпись13px, две ссылки12px, «Продолжить»/«Без записи».
Ссылки/версия/подпись — clients/nikadent/lead_config.yaml -> consent.
Без галочки input заблокирован; без записи доступны обычные вопросы.
Прямой /lead не принимает клиентский JSON за доверенное подтверждение.

Доказательство UTC/version/definition хранится в существующем acceptance
completion без контактов; private session и отправленная заявка ссылаются на
него. Отмена/завершение/новая запись очищают активную ссылку. Старый replay,
чужой tenant/session/revision и смена версии не открывают сбор данных.
Модель не участвует в согласии и не получает его настройки/контакты.

Проверки:47 targeted PASS до расширения adverse cases; release offline+policy
884PASS5platformSKIP0FAIL. Затем focused16PASS, включая missing-proof name/phone/
pause, version refresh and re-gating, actual Chrome DOM with rejected accept503 /
cancel400 recovery, reset, compact390/900px geometry. Independent Checker first
REJECT on UI dead end after rejected consent; fixed with existing new-chat action
for retained consent; focused recheck PASS (4 independent lifecycle tests).
Final UI/phone/consent nonbrowser repeat22PASS (browser covered in focused16).
Model/provider calls0, actual SMTP0; mocked delivery only. No merge/deploy/site
installation. Existing historical replay2 failures remain outside release scope.

Временные URL переданы владельцем. Содержимое consent URL при read-only проверке
оказалось о cookies/внешних сервисах, а не заявке с именем/телефоном: требуется
уточнение документа у клиента перед публичным запуском. Юридическая достаточность
не подтверждена; сбор медданных/рекламных согласий не добавлялся.

## НикаДент — стартовое меню по странице, 2026-10-15

Продолжение §66 в ветке codex/nikadent-technical-onboarding / PR #31,
checkpoint baseline8161637. Локально реализовано: общее приветствие/три вопроса,
меню для All-on-4, съёмных протезов и коронок по точным URL сайта; общая карточка
бесплатной консультации из существующей базы. Источник настройки —
clients/nikadent/widget_config.json; инструкция в CLIENT_PACK_AUTHORING.md.
В тестовой панели появился выбор страницы. На клиентском сайте путь будет
читаться автоматически после выкладки; эта выкладка не выполнялась.

106 targeted offline tests PASS (schema, API, origin/tenant, panel, real browser
DOM/clicks, existing visual/lead and authoring/release checks). Browser:
10 routes, 31 mocked clicks, shared promo, exactly3 buttons, reset, demo gallery,
mobile390/desktop900 geometry. Independent Checker PASS:50 schema/API tests,
panel module harness, call-path review; browser execution — executor evidence.
Model calls0, actual SMTP0 for this checkpoint. No /ask contract, D2 memory,
semantic/model/price/lead delivery changes. Existing demo presentation preserved.

Additional historical tests/test_d2_widget_replay.py:2 FAIL/1 PASS, reproduced
identically on a clean archive of baseline8161637 before any changes. Both fail
before browser launch while expecting removed legacy scope quick_replies.
This file is outside current release selections; not changed or claimed fixed.
Initial new-browser sandbox CDP timeout disappeared in approved headless execution;
one old config assertion expecting no Nikadent promotion updated to own promo.
No customer-site/live-model acceptance or SPA navigation integration claimed.

## НикаДент — техническое подключение, 2026-10-15

Текущий этап: Interface §65 / codex/nikadent-technical-onboarding, baseline e93cb12.
Последнее уточнение owner: **пока только локальный тестовый виджет**. Merge/deploy
отложены. Контент/новые цены отложены. PR #31 открыт, VPS не изменён.
Актуальная demo handoff-документация отдельно в fc84066, PR #30 пока открыт.
Этот раздел заменяет старые сведения о текущей ветке/релизе ниже: demo ранее
развёрнут на e93cb12, PR #27–29 merged, Inter 400–600. Старый срез ниже исторический.

Локально: Nikadent snapshot загружается после заполнения существующего обязательного
microfact_text; назначен временный получатель gothica@mail.ru. Убран универсальный
demo dispatcher: действующий lead/effect путь использует прежний tenant delivery
service. Accepted PII живёт только в private session/request closure; terminal text
и effect receipt сохраняются вместе, без автоматического resend. Demo остаётся stub.
Панель получает конфигурацию выбранной клиники с API; SID и teaser keys разделены
по клиентам. Nikadent41.ru и локальная панель разрешены exact-origin настройками;
аватар временный SVG, MD и суммы не редактировались.

Проверки на момент записи: 32 targeted offline PASS (actual JSON/SSE + mocked
SMTP, replay, tenant/contact/doctor grounding, phone modes, existing SMTP unit
tests), panel Node harness PASS. Первые ошибки новых tests относились к использованию
historical JSON helper и неверной метке boundary; tests исправлены под current
text protocol. Ни одного live/provider/SMTP вызова.
Независимый Checker PASS, собственные 13 onboarding tests PASS. Full release
selection выполняется отдельно. Публичные health/config demo и nikadent вернули
200 при корректном Origin: hostname/registry уже подключены. SMTP на VPS
и установка на сайт клиента ещё не проверялись.

Windows release union: 882 PASS, 5 SKIP, 4 FAIL. Три прежних теста ожидали успех
при ошибке SMTP / имитировали несуществующий статус email_sent; обновлены на
503+ok:false+точный error_code и действительный email. Четвёртый — влияние
локальной .env на reload config. Изолированный focused repeat: 60 PASS;
Checker focused recheck PASS. Полный изолированный Windows repeat: **886 PASS,
5 platform SKIP, 0 FAIL**. На runtime/UI checkpoint 2164c53 все пять CI jobs SUCCESS
([CI](https://github.com/Dhmnzr79/artgents-bot/actions/runs/38719946271)).

Локальный live: **5 model calls, 1 email**, без повторных model attempts. НикаДент
назвал Елизово, свои два филиала/телефоны и врачей из собственного pack. Настоящая
синтетическая заявка (не пациентские данные) получила sent; владелец подтвердил
получение письма на gothica@mail.ru. Demo получил demo_stub без SMTP. Повторы
одинаковых submit requests вернули сохранённый ответ без повторной отправки.
SMTP пароль сохранён владельцем только в локальной ignored .env, в Git не попал.
Локальный сервер запущен штатным scripts/start_local_widget.ps1 из текущей ветки:
http://127.0.0.1:9001/static/widget-test.html — выбор demo/nikadent, отдельные вкладки.
Это подтверждение локальной работы, не deployed/customer-site acceptance.

Срез 2026-10-13. Здесь только актуальные факты и незакрытые задачи.
Датированные записи прежних веток, экспериментов и checkpoint сохранены целиком
в [архиве состояния](../archive/pre-d2/tasks/DEMO_D2_CURRENT_STATUS.md).
Они описывают момент записи, а не разрешают возвращать удалённые механизмы.

## Развёрнутая версия и локальные изменения

- Demo работает на VPS по подтверждению владельца. Последний подтверждённый
  GitHub release — `8888fdd`, PR #26; CI, Publish image и Deploy production успешны.
  Новый SSH-аудит контейнера не выполнялся. Реальные production-пользовательские
  диалоги и требования миграции не заявлены.
- Локальная чистка — ветка `codex/docs-tests-cleanup`, baseline `origin/main=8888fdd`.
  Изменения идут в draft [PR #27](https://github.com/Dhmnzr79/artgents-bot/pull/27).
  Push этой ветки сам по себе VPS не обновляет; merge/deploy ещё не выполнялись.
- Roboto400/500/600, интервалы0 и замены14.5→15 сохранены исходным checkpoint
  `9f8c8f7`, тегом `checkpoint/pre-cleanup-2026-10-13` и перенесены в `58c1afa`.
  На VPS эта версия оформления ещё не выкладывалась.
- Прежние14 MD отличались только EOL: исходные байты сохранены локально в ignored
  `logs/pre-cleanup-md-eol-20261013/`; содержимое не менялось. Prototypes удалены
  по решению владельца. `.env`, raw logs, локальные БД не публикуются.

## Нынешний ответ бота

- Рабочая модель — DeepSeek Flash: `DEFAULT_LLM_MODEL=deepseek-flash`,
  `CHAT_BASE_URL=https://api.deepseek.com`, `CHAT_API_KEY`.
  Чистая конфигурация без env имеет Qwen default; это не fallback при ошибке DeepSeek.
- Обычный ответ — свободная prose с optional `<D2_META>` для действий/источников.
  Уточнение и вопрос о составе не требуют отдельной команды. Обязательный
  JSON-envelope, model ordinary price_detail/clarify_content и doctor_catalog удалены.
- Цена — native `show_price`: модель выбирает запрос/аргументы, код собирает
  фактическую карточку, затем второй provider response пишет окончательный текст.
  Оба вызова используют настроенную модель и расходуют quota. Strict и отдельный
  классификатор не выбраны. Карточка без tool не гарантируется; полезная prose
  сохраняется, риск модельных финансовых неточностей принят владельцем.
- Full context содержит approved MD, completed history и показанную карточку.
  Canonical публичные контакты — `clinic_policies.yaml -> contact`; мост в обычный
  model context включён в release (`0a9b1ce`). Readiness для DeepSeek — `33c1f55`.
- Verified UI clicks, tenant isolation, lead/privacy, transactional commit/error
  и replay сохраняются. Situation intake выключен. Demo-заявка учебная.
- Demo quota:30 model calls/session,400/day. Это число provider calls,
  не пользовательских сообщений; price второй вызов тоже считается.

Подробности и sole responsibility table:
[текущая архитектура](../CURRENT_ARCHITECTURE.md),
[Target Contract §3](DEMO_D2_TARGET_CONTRACT.md).
Позднейшие явные решения владельца заменяют противоречащие старые записи.

## Что подтверждено в чистке

| Checkpoint | Результат |
|---|---|
| §60 | Contact model context regression включён в PR/publish gate; списки защищены G2/G3 |
| §60.1 | Current docs entry и architecture/test index; situation suite18PASS, возвращён в gate |
| §60.2 | Quota fixtures мигрированы на native price и30calls;12PASS, возвращены в gate |
| §60.3 | Policy/text_ref38cases и contacts20cases; проверки tenant/data/missing/replay сохранены, оба suite в gate |
| §60.4 | Удалены15 obsolete cases; text protocol27cases усилен и в gate; три старых документа архивированы |
| §60.5 | Старую хронику статуса вынесли в архив; этот путь оставлен актуальным кратким статусом |
| §60.6 | PR и Publish используют shared release selections; прежние проверки сохранены, добавлен selection contract |
| §60.7 | Новый owner behavior entry;19 старых планов/аудитов перенесены в архив с явной исторической пометкой |
| §60.8 | 50 старых task cards/prompts и полные Interface/Roadmap snapshots архивированы; current очередь и process pointers очищены |
| §60.9 | Старые reference-bound документы явно помечены историческими; июльский backlog архивирован, current debt pointer обновлён |
| §60.10 | Ещё3 отменённых ONE_CALL wiring assertions удалены; current native model consistency guards усилены |

Последний локальный прогон точного publish offline selection (50 файлов, §60.6):
**821 passed,5 skipped,0 failed**. Все5 skips — ограничения symlink на Windows/POSIX.
Все49 прежних файлов сохранены; добавлен только selection contract. Targeted
selection/G2–G8:271PASS5SKIP, independent selection/G2/G3:65PASS и Checker PASS.
Targeted text/native-price/G2/G3:120PASS; independent Checker §60.4 — PASS.
Два trailing-whitespace места архива исправлены в `2cbbd15`, focused Checker PASS.
Это offline evidence, не повторная проверка Docker/PG/deploy и не полный historical suite.
GitHubCI checkpoint `f8c1700`: все5jobs SUCCESS, включая PostgreSQL и secret scan.
Publish image/deploy этого PR не запускались. Новых live/provider/SMTP calls в чистке:0. Runtime и client KB не менялись.

## Что осталось

1. Закончить карту historical tests: полезные guards мигрировать, доказанные дубли
   и assertions удалённых механизмов убрать. Не удалять тест только потому, что он красный.
2. Архивировать остальные устаревшие планы/аудиты, выделив действующие invariants.
   Прежние Interface/Roadmap sections архивированы; оставшиеся rootdocs/evidence
   и historical-reader bindings ещё классифицируются, весь корпус не очищен.
3. Завершить сверку SIM/REC evidence: «выполнено / заменено / отменено / отложено».
   Общая whole-bot acceptance не закрыта; offline fixtures не доказывают live model quality.
4. Temporary demo gate пока ограничен. Постоянный набор утвердить по законченной
   карте полезных проверок; Secret scan, PostgreSQL и Docker/deploy защиты не ослаблять.
5. Client KB cleanup и экономия full-context tokens — следующий отдельный этап.
   Optional doctor/case UI — будущая идея. Итоговая совместная выкладка требует
   отдельного разрешения; текущий VPS demo не менять в чистке.

Порядок работ — [верх Roadmap](DEMO_D2_DELIVERY_ROADMAP.md),
карточка/доказательства — [Interface §60](DEMO_D2_INTERFACE_TASK.md#60-cleanup-checkpoint--2026-10-13),
проверки — [Test index](../TEST_SUITE_ARCHITECTURE.md).
Процесс — [AGENTS](../../AGENTS.md), [Execution Lock](DEMO_D2_EXECUTION_LOCK.md),
[Git/запуск](../WORKFLOW_GIT.md), [Checker](../WORKFLOW_CHECKER.md).


Prompt§61 (ownerGO): clinic facts grounded, general dental knowledge permitted;
mild redundancy reduction without paragraph/word caps. Version47 guidance shared
ordinary/known/nativecompletion. Offline delivery checks don't prove livecompliance;
no live agentcalls/China MD changes. Runtime mechanics unchanged.

Prompt§62/version48: generalquestion→#korotko ifpresent with necessary relevant
microfacts; specificquestion→matchingsections, clickedfollowup→selectedsection.
No full-documentdump or conditions withheld for followup. UI/code unchanged,
no new calls; offline delivery evidence does not prove live compliance.
