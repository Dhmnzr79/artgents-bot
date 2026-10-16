# Общий каталог и цены — owner GO 2026-10-16

Владелец подтвердил реализацию после согласования последовательности: общая
схема и ценовой слой → карточки в разговоре → самостоятельный каталог и три
вкладки → общая форма → два локальных демо. При архитектурных вопросах — Astra.
UX-решения: THREE_TABS_DEMOS_HANDOFF.md с последующими уточнениями в
MEDICAL_DEMO_CONTENT_TASK.md; последнее решение о клиентской подаче без демо-
маркировок сохраняется. Начальная тема страницы входит в первую готовую
локальную реализацию интерфейса, а не в этот отдельный schema checkpoint.

## Текущее уточнение владельца: общий новый продукт для трёх клиентов

2026-10-16: «не заливать без моей команды», а локально полностью новый продукт
для старого демо, нового медцентра и НикаДент. НикаДент нужен в новом формате
на VPS после локальных проверок и отдельной команды на выкладку. Прежняя
read-only граница НикаДент ниже относится к уже завершённому этапу 1.
Теперь не создаём tenant opt-in, старый price mode или исключение по client_id.
Один новый код и UI у всех трёх, отдельные базы/цены/lead settings. Доставка,
tenant/privacy/consent и прежние роли Target Contract §3 сохраняются.
Вопросы владельцу — только обычным текстом с примерами, без quiz/popup.

## Этап 5: точный перенос artgents-mobile-widget.html с Inter — owner GO 2026-10-16

Owner передал HTML и подробный prompt: точный перенос интерфейса, шрифт Inter.
Repo/top C:/Cursor Projects/artgents-bot-active, codex/three-tabs-catalog.
Baseline 81db5f1fb27ac0e87f2c4e9665de1afafefaf4d1, origin/main и merge base
f7629491f2bb93ed80e2f58aea53770841bbd6a3. Tracked/index чистые;
foreign otzyv-1/2/3.jpg сохраняются. Продолжение того же продукта/ветки.

Тип: UI bug fix и адаптивное представление, не архитектурное упрощение.
HTML прочитан целиком (CSS/JS): нейтральные tokens, основной текст16px,
служебный14px, цена под подписью в открытом списке без внешней рамки,
44–52px touch targets, container queries и200%text. По последнему уточнению
owner все существующие SVG внутри details и других компонентов сохраняются.
User отдельно требует Inter вместо Arial эталона. CSS/JS/разметка эталона
сохранены; в архивной копии удалены только пробелы пустой строки21 для
git diff --check. При сравнении шрифт эталона заменяется на Inter как явное исключение.

Последнее уточнение owner: «Переносишь только дизайн систему! ... Логику
не трогаем ... эти иконки сохрани». Scope сужен до CSS и проверки шрифта;
DOM/порядок раскрытия описания, аватары, тексты, callbacks, CTA и все SVG
сохраняются. Новых viewport/focus/draft handlers не вводить. Container styling
и touch targets — CSS. JS допускается лишь если проверка докажет, что без
регистрации font resource Inter не загружается в существующем Shadow DOM.
Не копировать JS эталона, не менять текущие способы submit/выбора услуги.

Runtime embed: обычный DOM в test panel, Shadow DOM через static/widget/embed.js
на сайте; iframe механизм не добавляется. Одна разметка/стили для обоих.
Viewport/focus/scroll handlers сохраняются; доступность и отступы проверяются
в существующей реализации. API, tenant routing/privacy/consent/delivery/model
semantics не меняются.

Выявленные различия поведения с reference: там auto-first price, ask-service,
new-application после success и preview-start-catalog; рабочие ранее согласованные
options-first, отсутствие этих двух кнопок, thank-you и assistant start сохраняются.
Реальные названия/суммы/тексты/выбор формы не заменяются demo JS. Прежняя цена справа
из screenshot отменяется новым прямым указанием: цена под подписью. Никаких новых
сценариев/модельных полей, источников прайса или backend изменений.

Exact allowlist:
- static/widget/widget.css
- static/widget/fonts.css
- static/widget/embed.js
- core/widget_cors.py
- tests/test_widget_embed_cors.py
- tests/test_widget_three_tabs_browser.py
- tests/test_widget_mobile_layout_browser.py
- tests/release/offline.txt
- docs/artifacts/artgents-mobile-widget.html
- docs/artifacts/artgents-mobile-widget-prompt.txt
- docs/tasks/THREE_TABS_CATALOG_TASK.md

Проверки блока: ширины320/360/390/430 и desktop container, DOM и Shadow DOM,
направления/длинные услуги/detail/variants/conditions/feed/composer/form/error/
success/back/draft;200%text; real Inter platform fonts. Эмуляция viewport и
фокуса не объявляется real-device iOS/Android/keyboard evidence. Offline fixtures,
никаких provider/SMTP/VPS/merge/deploy. Один independent Checker завершённого
блока из-за общего renderer/mobile behavior, без полного D2 архитектурного review.

Font probe: CSS.getPlatformFontsForNode в Shadow DOM показывает Inter SemiBold,
isCustomFont=false: используется системный Inter, а не bundled webfont.
Добавлен fonts.css (только прежние @font-face), widget.css импортирует его,
embed.js регистрирует этот stylesheet в document.head: Chrome не регистрирует
@font-face из Shadow stylesheet. Это загрузка оформления, без widget handlers.
Нейтральные поверхности получают отдельный --clinic-soft, чтобы inherited
inline theme tint не заменял серый эталона. Действия сохраняют brand клиента.

Результат локального блока: убраны старая рамка списка/карточки, вложенные
боковые отступы, цена справа и мелкая типографика; прежние конфликтующие
правила заменены на общую шкалу эталона, не накоплены новыми overrides.
Добавлены CSS container query и отдельная регистрация прежних font-face.
Выбор вариантов, все SVG paths, порядок/раскрытие описания, тексты, avatar,
CTA, поля/согласие/доставка/история и JS обработчики widget не изменены.

Offline: 7 PASS (three-tabs3, embedded presentation3, no-public-price1).
Three-tabs:10 состояний ×5 ширин ×100/200% для каждого из3 tenants; форма,
validation, потерянный ответ/retry, success, общий draft, история/выбор цены.
Embed: настоящий bootstrap/Shadow DOM, CDP подтверждает bundled Inter
isCustomFont=true, сравнение размеров/цветов/отступов с неизменённым HTML
при390px с единственным разрешённым font override Inter. На3 tenants
5 ширин ×100/200%, короткий viewport560px, доступность phone/host scroll.
Дополнительно read-only real9001 screenshots направлений, услуг, деталей,
вариантов и формы всех3 клиентов просмотрены. Все /ask и /lead при этих
снимках блокировались; provider/SMTP0, VPS/merge/deploy0.
Новых baseline failures нет; прежние datetime.utcnow deprecation warnings.
Физические iOS/Android и настоящая экранная клавиатура не проверялись.
Independent Checker: PASS после focused recheck единственного font CORS P1;
собственный targeted run Checker16PASS. Foreign otzyv1/2/3 сохранены.

Checker focused finding P1: bundled fonts не получали CORS headers на внешнем
origin, same-origin browser не выявлял проблему. Добавлены только два точных
Inter asset paths в существующий CORS список, с прежним разрешением tenant/origin.
Это доставка оформления; allowedOrigins, API/lead/model и guard не меняются.
Allowlist выше расширен на core/widget_cors.py и его существующие offline tests
для этой конкретной причины. Browser proof дополняется двумя разными origins;
после REJECT требуется только focused recheck этого finding.

Focused result:19PASS (cross-origin embedded3 +CORS16), без повторения
не затронутых функциональных checks. Вместе с предшествующим7PASS покрыто
23 разных targeted cases. Браузерные снимки — локальные offline/read-only,
не доказательство VPS диалогов. Node syntax embed.js и diff --check PASS.
Файлы шрифтов уже находились в static/fonts; Google/CDN не подключались.
Checkpoint этапа: commit subject `Transfer reference widget design system with Inter`;
push в текущую codex/three-tabs-catalog, draft PR34; без merge/deploy.

## Этап 4: перенос дизайна сохранённого прототипа — owner GO 2026-10-16

Owner: «Сделай все как в прототипе», после скриншотов вкладок, списка услуг
и направлений. Продолжение той же ветки codex/three-tabs-catalog в repo/top
C:/Cursor Projects/artgents-bot-active. Baseline 2611529e5127d29fb06c96c3e6e547e35dcf8fc7;
origin/main и merge base f7629491f2bb93ed80e2f58aea53770841bbd6a3.
Tracked/index чистые; foreign otzyv-1/2/3.jpg сохраняются.

Тип: исправление интерфейса и authored presentation data, не архитектурное
упрощение. Визуальный источник static/experiments/three-tabs/{index.html,
styles.css,app.js}. Переносим шрифты/отступы/heading/search/direction tiles,
service rows, price details и форму; реальное наполнение, точные offers,
options-first и общая форма сохраняют owners этапов 1–3. Не возвращаем
отклонённую «Спросить об этой услуге», «Новая заявка» и демо-дисклеймеры.
Данные прототипа не становятся прайсом. Краткие подписи направлений и label
каталога — authored UI text, не новый semantic/control field модели.

Exact allowlist до редактирования:
- contracts/widget_catalog.py
- core/widget_catalog.py
- static/widget/catalog.js
- static/widget/price_card.js
- static/widget/booking_form.js
- static/widget/widget.js
- static/widget/widget.css
- static/experiments/three-tabs/app.js
- docs/artifacts/three-tabs-prototype/app.js
- clients/demo/target_response/widget_catalog.json
- clients/demo_medical/target_response/widget_catalog.json
- clients/nikadent/target_response/widget_catalog.json
- clients/_template/target_response/widget_catalog.json
- tests/test_widget_catalog.py
- tests/test_widget_three_tabs_browser.py
- docs/CLIENT_PACK_AUTHORING.md
- docs/tasks/THREE_TABS_CATALOG_TASK.md

Owner уточнил: не переносить «Выберите направление или найдите услугу.» и
«Демо-клиника · основные услуги», удалить эти строки и из standalone prototype.
Каталог без демонстрационных пояснений; подсказки внутри направлений сохраняются.

Проверки блока: schema/API existing catalog tests, JS syntax, targeted browser
workflow трёх tenants и screenshots 390/desktop сравнение с prototype.
Так как расширяется публичный presentation contract, один independent Checker
завершённого блока; без полного повторения аудита D2. Provider/SMTP/VPS — 0.

Результат блока: удалено прежнее оформление направлений (белые рамки/counts),
несогласованные font sizes/desktop overrides, прежняя компоновка формы/composer.
Перенесены prototype heading/search/soft tiles/list rows, размеры/типографика
всех трёх вкладок, price-card/формы, отдельный accordion исключений. Цены и
includes/excludes берутся из тех же frozen rows, public renderers общие.
Направления получили authored subtitle; label/subtitle обязательны в четырёх
packs, API только проецирует их. Стрелки направлений/услуг — тот же SVG path,
stroke 1.4 и 17px из прототипа; CTA тоже имеет декоративную стрелку.
Копия прототипа в docs/artifacts и ignored static/experiments очищены от
отклонённых подписей. Последняя намеренно остаётся вне Git по handoff.

Проверки: catalog API/schema **12 passed**, Chrome workflow **3 passed** у
трёх tenants (selection/form/consent/retry/restore, 320/390/1280). Screenshots
сняты для root каталога 390/1280, detail и формы; выполнена визуальная сверка
со standalone prototype. JS syntax/diff check проходят. Заключительный browser
run **3 passed** (24.30s); после финальной подгонки базового line-height отдельно
проверена настоящая локальная test panel всех трёх клиентов, со screenshots
390/1280: каталог, услуги, варианты, detail, форма. Harness блокировал /ask и
/lead, запрещённых POST не было. DEV overlay скрыт штатной test panel.
Independent Checker **PASS**, собственные **12 passed**, P0/P1/P2 нет.
Это UI bug fix, архитектурное упрощение не заявляется. Semantic/lead/price
owners, shared draft и options-first не меняются; live/provider/SMTP calls 0.
Изменены только 16 tracked путей allowlist и ignored локальная копия прототипа.
Foreign JPG сохранены, `.env`/SQLite/logs не входят в checkpoint. Checkpoint
остаётся в codex/three-tabs-catalog и draft PR34, без merge/deploy/full CI.

## Этап 3: рабочий каталог и три вкладки — owner GO 2026-10-16

Владелец: «Давай» после описания каталога, трёх вкладок, общей формы,
страничного входа и подключения медцентра в панель. Scope всех трёх tenants.
Это продолжение той же задачи/ветки, а не новая ветка от старого baseline.
Repo/top C:/Cursor Projects/artgents-bot-active, branch codex/three-tabs-catalog;
baseline HEAD fe165d42cf995787492f5552b20459018ffd6fa5, origin/main и merge base
f7629491f2bb93ed80e2f58aea53770841bbd6a3. До начала tracked/index чистые,
foreign otzyv-1/2/3.jpg сохраняются.

Тип: product feature; извлечение единственного renderer карточки — упрощение.
До → после → удалённая зависимость: карточка закрыта внутри chat closure →
один renderer получает frozen part и callbacks → каталог не копирует её DOM,
ценовые правила или ссылки price_select диалога. Общий row builder/selector
предыдущих этапов сохраняется. Каталог читает snapshot, не пишет dialogue
state/revision, не публикует dialogue refs и не вызывает модель. Его локальный
выбор варианта не объявляется новым ходом диалога. Авторские разделы задаются
в tenant data; никаких dental списков в коде. Полнота/ownership refs проверяются.
Нет JS-массивов с прайсом из прототипа. Отсутствие публичной суммы не скрывает
услугу; однозначное предложение открывается сразу, несколько сначала списком.
Browse не меняет выбранную заявку; только явная кнопка заявки переносит точный
service/offer в общий черновик. Поля имени/телефона доступны до галочки;
согласие не отправляет форму, нужна отдельная кнопка submit. После success
благодарность без новой заявки. Контакты не переходят в model/D2 history.
Форма сохраняет прежних consent/delivery/limit/replay owners; её receipt не
подменяет ordinary dialogue completion. Детали интеграции согласуются с Astra
по реальным paths до изменения lead runtime. VPS/merge/provider/SMTP запрещены.

Первый блок allowlist (каталог, общий renderer, UI shell и описание этапа):
- contracts/widget_catalog.py
- core/widget_catalog.py
- core/widget_cors.py
- app.py
- static/widget/price_card.js
- static/widget/catalog.js
- static/widget/widget.js
- static/widget/widget.css
- clients/demo/target_response/widget_catalog.json
- clients/demo_medical/target_response/widget_catalog.json
- clients/nikadent/target_response/widget_catalog.json
- clients/_template/target_response/widget_catalog.json
- tests/test_widget_catalog.py
- tests/test_widget_three_tabs_browser.py
- tests/release/offline.txt
- docs/CLIENT_PACK_AUTHORING.md
- docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md
- docs/tasks/THREE_TABS_CATALOG_TASK.md

Перед изменением других путей формы/page context/admission allowlist расширяется
с объяснением, а не задним числом при staging. Целевые проверки: read-only API
всех tenants, точные rows/условия/акции/ref isolation, browser desktop/mobile:
направления/global search/back position/variants/tab history/общий draft.
Один independent Checker завершённого substantive этапа, focused recheck findings.

Расширение allowlist перед интеграцией общей формы (Astra consultation):
- contracts/booking_form.py
- contracts/response_plan.py
- core/d2_booking_form.py
- core/d2_dialogue_store.py
- core/d2_lead_bridge.py
- core/d2_dialogue.py
- core/response_plan_resolver.py
- core/response_ui_projection.py
- core/lead_email.py
- lead_service.py
- static/widget/booking_form.js
- tests/test_widget_booking_form.py

До → после → removed dependency: booking → private slots/name/phone classifier
и сообщения → одно предложение формы и private structured submit → удаляются
достижимые collecting/interrupt/resume paths и phone composer режима записи.
Согласие и доставка остаются server-owned. Тот же D2 store сохраняет приватный
PII-free receipt через общий namespace reservation, без ordinary revision/history.
Единственный sender handle_lead, request fingerprint keyed; unknown не resend.
Форма учитывает существующие usage limits и server-owned catalog selection.
В demo_stub сервер всё равно требует accepted=true, но consent_receipt=null
как прежде; показываем текст без выдуманных юридических URLs. НикаДент требует
existing definition fingerprint и строгий LeadConsentReceipt. Клиент не выбирает
delivery mode; после включения реальной доставки definition обязателен.

Расширение allowlist перед page entry/local admission и проверками:
- contracts/widget_config.py
- contracts/d2_dialogue.py
- core/d2_tenant_snapshot.py
- core/d2_live_provider.py
- core/d2_http_adapter.py
- core/d2_demo_limits.py
- tests/test_d2_demo_session_budget.py
- clients/demo/widget_config.json
- clients/demo_medical/widget_config.json
- clients/nikadent/widget_config.json
- static/widget-test.html
- static/widget-test-panel.js
- scripts/start_local_widget.ps1
- tests/test_widget_entry_context.py
- tests/test_lead_consent.py
- tests/test_d2_phone_mask.py
- tests/test_d2_native_price_runtime.py
- tests/test_widget_page_menus.py
- tests/js/widget_page_menus_harness.mjs
- core/widget_session.py
- core/d2_completion_context.py
- tests/test_widget_session.py

Full navigation remount восстанавливает сохранённую публикацию из того же store.
POST /api/widget-session read-only (SID в JSON, не в URL/access log), UUID SID,
no-store, прежние origin/tenant guards. Страницы по 50 ordinary completions,
private form receipts не входят. Existing current receipt ref хранится также
у своего completion, чтобы UI не ограничивался окном model-context в 3 хода.
Это ссылка на уже выполненный ход, не summary/второй владелец истории. История
не продлевает TTL/revision, не переавторизует старые действия. Контакты в прозе
маскируются, цены и canonical клинические данные не пересобираются.

Начальная страница — immutable provenance в существующем D2 record, не текущая
потребность пациента и не parallel semantic memory. Только authored exact path
→ canonical topic из captured widget config. Даётся модели при первом ordinary
ходе; далее его повторно не навязываем, TTL не начинает тему заново. Клиент не
присылает тему или URL/query/hash. Общая local launcher admission включает три
клиента; production registry/host rules не расширяются. Новый medical использует
существующий demo admission c tenant namespace, не новый набор лимитов.

### Реализация и evidence этапа 3

Reachable path: `/api/widget-catalog` → captured snapshot/navigation.bind →
existing `build_d2_price_offer_row`/commercial selector → общий `price_card.js`.
Nav содержит только разделы и service IDs: полнота/active/tenant проверяются
также при snapshot load. НикаДент: 5 активных услуг без offers остаются видимыми;
никаких синтетических offers/фиктивных сумм. Полное описание свёрнуто после цен.
Каталог: вертикальный список, поиск по всей клинике, back/scroll/variant state.

Booking path: обычное понимание booking и прежний policy gate → booking_form
UI; опубликованная CTA локально открывает ту же форму. Проверенный вариант
передаёт service/offer и frozen catalog version. `/lead` → typed validation →
same store reservation/HMAC fingerprint → consent/current catalog/usage owners →
PII-free form_pending → единственный `handle_lead` → terminal receipt. Имя,
телефон и пожелание только в private closure sender, не в payload SQLite/model.
Удалены D2 collecting_consent/name/phone classifiers, pause/resume/reconcile и
phone composer: следующий вопрос после открытия формы — обычный вопрос модели.
Старые unrelated session/legacy sales_fast APIs вне reachable D2 не объявлены
полностью удалёнными. Общий effect protocol остаётся для других D2 операций.
Форма не меняет ordinary record/revision/activity и не ломает старые price refs.
Pending/unknown replay не отправляет письмо заново; неподтверждённая отправка
не сбрасывается простым открытием другой формы/выбором услуги.

Page path: widget capture → HTTP pathname validation → captured exact authored
config/topic validation → immutable D2 entry provenance → только первый ordinary
model input. Повторный переход/TTL не задают новую тему. Default menu сохраняет
authored video/buttons; удалено необоснованное требование, чтобы само наличие
pageMenus превращало default menu ровно в три question-only кнопки. Отдельные
page menus по-прежнему имеют три вопроса, blank q отклоняется.

Navigation restore: POST read-only → ordinary completed receipts того же store →
existing public_dialogue_plan masking → UI. Нет localStorage копии переписки,
private form/lead blocks и их UI не восстанавливаются. Цена frozen, не пересчёт.
Price clicks восстанавливаются в исходную карточку тем же mergePriceMessage,
который используется streaming UI. Restore блокирует первый send, проверяет SID
и generation после reset. Ошибка старого/повреждённого receipt требует явного
нового разговора; silent migration/fallback не добавлены.

Проверки: targeted form/catalog/native **69 passed**; заключительный расширенный
offline run **141 passed** (каталог, форма, entry, restore, consent, phone,
page-menu contracts, demo budget, native price, variants). Браузер трёх tenants
с реальными offline API fixtures — **3 passed**, включая chat CTA exact offer,
общий draft, checkbox gate, lost-response immutable retry, success, remount,
price merge, геометрию 320/390/1280. Screenshots визуально проверены: dental chat
detail, медицинский каталог и форма НикаДент на 390px. Focused старый page-menu
Chrome harness **1 passed**: 10 routes, вопросы/promo, root video/gallery,
исходная страница при SPA до первого send и новая страница после явного reset.
Он выявил потерю default gallery от самого наличия pageMenus: устранено для
default с authored video, explicit question-only меню по-прежнему без галереи.
Initial pathname теперь фиксируется при mount/reset и используется welcome
и запросами. Изменение базы требует явного reload в сообщении catalog_changed,
а не повторного выбора из прежнего cache. Новые targeted файлы включены в
release/offline.txt. Independent Checker: **PASS**, собственные **48 passed**;
focused recheck initial-page/gallery/stale-catalog изменений без P0/P1/P2.

Остаточные ограничения: живое понимание модели/SMTP не проверены; full CI перед
merge не запускался. Старые сценарии последовательного conversational intake
заменены тестами нового согласованного form-контракта, не пропущены условием.
Известные до этапа raw-JSON helper failures не объявляются исправленными.
Локальный сервер перезапущен штатным launcher после проверки PID/commandline
только этого repo. Startup check OK, read-only API: demo 5 разделов/22 услуги,
medical 10/21, НикаДент 5/27. Никаких POST к работающему /ask или /lead.
Provider/SMTP/VPS calls **0**, merge/deploy нет. Review выполнен до staging;
для checkpoint `feat(widget): ship shared three-tab catalog and private form`
подготовлены только 51 точный путь из allowlist. Checkpoint остаётся в той же
topic branch/PR34; hash и push state приведены в итоговом сообщении и Git log.
Foreign otzyv JPG сохранены.

## Этап 2: варианты цен, общая карточка, точная применимость акций

Baseline 2a7870e1f9973f84e067850cfe7396671090ce2e, та же task branch
codex/three-tabs-catalog; repo/top C:/Cursor Projects/artgents-bot-active.
origin/main и merge base f7629491f2bb93ed80e2f58aea53770841bbd6a3.
Tracked/index перед этапом чистые; foreign три otzyv JPG сохраняются.

Тип: архитектурное упрощение согласованного выбора и presentation feature;
дополнительно исправление offer applicability промо и пустых блоков карточки.
До → после → удаляемая зависимость:
- Первая строка/первое совпадение option становится выбранным → публикуются все
  допустимые варианты; ровно одно однозначное предложение или проверенный клик
  раскрывает детали → автоматический выбор по порядку удаляется целиком.
- Режим карточки выводится renderer из количества строк → materializer один раз
  фиксирует options/detail в существующем D2FrozenPriceBlock до completion →
  виджет и текстовая история больше не делают разных предположений о выборе.
- Promo ограничено service/topic → тот же selector дополнительно проверяет
  optional allowed_offer_ids самого факта → исчезает ошибочное расширение
  акции выбранной зоны на соседние offers; fact_refs не становится selector.

Правила публикации (завершают рекомендованный владельцу пример с ЛОР):
прямая услуга с одним допустимым offer — detail; несколько offers — options.
Явный option_id фильтрует offers: один — detail, несколько — options; первый
из нескольких не выбирается. Проверенный price_select — detail конкретного
offer. Обзор направления всегда options, даже с единственным представителем:
он не доказывает, что услуга имеет только один вариант. Нет утверждения, что
пациент сам выбрал единственное предложение. Новых команд модели/API нет.

Один presentation field — данные уже согласованной публикации, его задаёт
сервер; модель не выбирает режим. Completed receipt сохраняет показанные offers
и исходный service/topic/действительные ограничения, без бренда первой строки.
Скрытые детали списка не объявляются уже показанными в следующем model context.
Одна карточка показывает только заполненные блоки. No-public-price остаётся
карточкой с approved_text, исключения не зависят от наличия includes.

allowed_offer_ids у TargetCommercialFact: отсутствие/[] оставляет прежнюю
service/topic применимость; непустой список дополнительно сужает её. Unknown,
foreign, duplicate и противоречащие service scope IDs отклоняются. Узкая акция
автоматически прикрепляется только к точному detail offer; не к списку или
общему информационному ответу. Обычный прямой вопрос об акции по-прежнему
получает полный квалифицированный текст по базе. В options не вываливаем
дополнительные коммерческие пакеты; после выбора действует прежний selector.

Владелец смыслового запроса — модель; допустимых offers — существующий код по
каталогу; сумм/состава/акции — данные; presentation — materializer до freeze;
виджет/renderer только отображают. История/replay/revision/lead owner прежние.
Нет нового resolver, памяти, fallback, параллельного legacy UI или вызова модели.

Точный allowlist этапа 2:
- contracts/response_plan.py
- contracts/response_schema.py
- core/response_plan_materialization.py
- core/response_ui_projection.py
- core/response_text_renderer.py
- core/d2_commercial_plan.py
- core/one_call_exact_commercial_catalog.py
- clients/demo_medical/target_response/pricebook/facts.json
- static/widget/widget.js
- static/widget/widget.css
- docs/CLIENT_PACK_AUTHORING.md
- docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md
- docs/tasks/THREE_TABS_CATALOG_TASK.md
- tests/test_d2_price_variants.py
- tests/test_d2_price_variants_browser.py
- tests/test_d2_native_price_runtime.py
- tests/test_nikadent_price_authority_offline.py — прежние ожидания text-only для
  no_public_price заменяются проверкой общей карточки; money/guards сохраняются.
- tests/test_d2_catalog_generalization.py
- tests/release/offline.txt

Проверки: actual native fake provider JSON/SSE для всех трёх клиентов: список →
точный click → replay → continuation; нет выбранного первого бренда; один offer,
несколько offers одного option, no_public_price, пустой includes с excludes,
однострочный обзор; чужой/поддельный/stale action; scoped promo на нужном и
соседнем offers, data refs, сроки и прежние общие акции НикаДент. DOM/geometry
проверки на desktop/mobile. Один independent read-only Checker на завершение.
Provider/model/SMTP calls 0. Полный CI перед merge; merge/deploy без команды
владельца запрещены. Ни local сервер, ни VPS в этом этапе не перезапускаются.
Ignored результаты только drafts/three-tabs-catalog/. Новые API/три вкладки/
форма/page context/demo admission остаются следующими этапами.

### Результат этапа 2 — Checker PASS

Удалён reachable auto-first в `resolve_d2_operations`: нет среза rows к первой
строке, первого совпадения option и присвоения его бренда списку. Единственный
владелец options/detail — `_d2_price_block`, до price completion. Реальный путь:
HTTP JSON/SSE → native `show_price` → materializer → frozen block → completion
→ общий UI/text/history. Проверенный `price_select` восстанавливает сохранённую
задачу и offer, без нового определения смысла моделью. Replay читает тот же
receipt. Topic preview остаётся options даже с одной строкой. Добавлен output
presentation и его инвариант detail/one row; новых model/API commands нет.

Изменение поведения общее для demo, demo_medical, nikadent: цены вариантов
сначала; подробности после точного запроса/клика. No-public предложения теперь
карточки, а не отдельная text-only ветка. Empty includes не скрывает excludes.
Список не публикует скрытые состав/этапы в текстовой истории; открытая карточка
передаёт их. Существующий коммерческий selector проверяет optional offer scope;
общие акции НикаДент не зависят от `fact_refs` и сохраняются в detail.

Offline evidence (внешняя сеть заблокирована в HTTP fixtures):
- Основной прогон: 152 passed — 98 catalog generalization, 37 native price и
  17 новых variants; ещё один новый тест имел неверный test adapter, исправлен.
  Два чистых promo tests после исправления authority: 2 passed. Новый тест
  чужого tenant/неопубликованной revision прошёл в focused run.
- Регрессии НикаДент/current UI/schema: 191 passed. 10 старых ожиданий
  text-only/no-public или деталей ещё не выбранного варианта обновлены по
  согласованной новой подаче; focused recheck: 21 passed, 94 deselected.
- Реальный Chrome DOM: четыре новых widget сценария (все три клиента,
  no-public с excludes без includes) и прежняя смешанная no-public/numeric
  геометрия прошли на ширинах 320/390/1280. Первоначальный sandbox запретил
  Chrome loopback; разрешённый локальный recheck снял эту средовую ошибку.
  Browser assertion этапов сравнивает текст с нормализацией пробелов между
  отдельными DOM-блоками; суммы/состав проверяются целиком.
- До этапа на 2a7870e отдельно зафиксированы 118 passed / 4 failed в старом
  raw-JSON helper `test_d2_commercial_plan`; они не менялись и не названы
  регрессией. Прежний stage1 historical debt также не закрывается этим этапом.

Проверки офлайн не доказывают качество живой модели. Provider/model/SMTP: 0.
Ни локальный сервер, ни VPS не перезапускались. Старые persisted price receipts
не мигрируются: новые проверки используют новые сессии; compatibility mode не
вводится. Полный CI, live dialogue, merge и deployment не выполнялись.
Independent Astra Checker: PASS, собственный targeted run 20 passed; call path,
реальное удаление auto-first, scope/history/promo и финальный CSS проверены.
После визуального просмотра исправлено сжатие длинных подписей detail tabs;
повторный affected Chrome run 3 passed. Скриншоты всех трёх клиентов просмотрены.
Контрольный checkpoint `feat(prices): show options before details for all clients`
сохраняется в этой же branch/PR34 после PASS. Foreign otzyv-1/2/3.jpg сохранены.
Следующий этап — самостоятельный каталог/три
вкладки и admission медцентра в локальную панель; текущий этап этого не обещает.

## Этап 1: единый действующий каталог и сборка предложения (завершён)

Тип: архитектурное обобщение/упрощение, дополнительно исправление startup.
Ответственность — только таблица DEMO_D2_TARGET_CONTRACT.md §3.

До → после → удаляемая зависимость:
- Встроенный dental enum пропускает pack → непустые авторские family/unit IDs
  проходят тот же строгий каталог → загрузка не зависит от списка ниш в коде.
- Числовой offer сначала требует legacy billing dictionary, потом берёт свою
  обязательную подпись → берёт авторскую подпись сразу → legacy unit dictionary
  удалён из D2 сборки цены и опубликованных условий.
- Frozen row собирается внутри dialogue materializer → одна чистая функция
  собирает существующий D2FrozenPriceRow для выбранного canonical offer → старое
  тело и дублирование форматирования удалены; chat использует её непосредственно.
- Startup/операционный validator требуют старые strategy/marketing → используют
  текущий immutable D2 snapshot/catalog/model view → эти legacy readers и
  обязательные файлы удалены из startup/validator/template. Legacy tooling
  вне живого D2 пути не переводится и не служит fallback.

Единственные владельцы: таксономия и подписи — pack; суммы/состав/условия — offers;
форматирование — общая чистая сборка; применимость/выбор — прежний код по данным;
свободный смысл — модель; контекст/revision/replay/lead/privacy — прежние owners.
Нет нового resolver, API, control envelope, модели, fallback или второй цены.

Результат этапа: medical pack загружается и готовые предложения формируются тем
же кодом, что dental. Tenant ещё не регистрируется в runtime/panel. Это не
приёмка трёх вкладок и не обещание готовности общего интерфейса.

Следующие этапы сохраняют свою очередь: точная offer-применимость промо;
выбор вариантов перед раскрытием деталей/no-public-price card; read-only API
без изменения беседы; общая форма; начальная тема страницы; demo admission.
Dental volume controls, niche prompt примеры и hint ещё не обобщены здесь.
Удалять defaults без сохранения прежних dental кнопок нельзя. Pack НикаДент
остаётся read-only; зависимый перенос controls в его данные отложен.

## Preflight и границы

Repository/Git top: C:/Cursor Projects/artgents-bot-active.
Fresh fetch origin/main: f7629491f2bb93ed80e2f58aea53770841bbd6a3; merge base тот же.
Ветка codex/three-tabs-catalog создана от этого ref. Явно перенесены handoff
cefb2ee → 6081343, content 5d463e0 → a718e12, copy cleanup 6b9dbf5 → c3d61ae.
Implementation baseline: c3d61aeeb9a3b789e20c48483836a72bac8f5b5e.
Tracked/index перед этапом чистые. Foreign otzyv-1/2/3.jpg не трогать.
VPS, deployed demo, НикаДент pack, routing и ALLOWED_CLIENTS не менять.
Provider/SMTP calls: 0; merge/deploy запрещены. Topic push/draft PR разрешены.
Временные offline результаты только в ignored drafts/three-tabs-catalog/.

Точный allowlist:
- contracts/response_schema.py
- core/d2_price_offer.py
- core/d2_published_offer_terms.py
- core/response_plan_materialization.py
- core/startup_check.py
- core/prod_readiness.py
- core/d2_tenant_snapshot.py
- core/d2_http_adapter.py
- scripts/validate_client_pack.py
- clients/_template/target_response/marketing.yaml (удаление)
- clients/_template/target_response/clinic_strategy.yaml (удаление)
- clients/_template/target_response/d2_commercial.json
- clients/demo_medical/README.md
- docs/CLIENT_PACK_AUTHORING.md
- docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md
- docs/tasks/THREE_TABS_CATALOG_TASK.md
- tests/test_response_schema_contract.py
- tests/test_validate_client_pack.py
- tests/test_client_pack_template_scaffold.py
- tests/test_d2_catalog_generalization.py
- tests/release/offline.txt

## Приёмка и проверки

Одинаковый snapshot/validator для demo, nikadent, demo_medical и _template.
Все medical offers; fixed/from/range/no_public_price; произвольная новая family
и единица с авторской подписью; refs/неактивные/чужие IDs/forged terms reject.
Проверить старые dental brand/extent/count и актуальные price/native/replay,
JSON/SSE paths с fake provider; отсутствие model/effect у чистой сборки.
Consent/UI/contact/MD refs остаются проверяемыми, legacy YAML не влияет на D2.
Startup должен читать тот же root, что проверяемый D2 pack; malformed current
commercial/tenant/ref должен блокировать, а не проходить через legacy fallback.
Один независимый read-only Checker завершённого этапа. Полный CI перед merge.

Baseline: старый test_d2_price_modes не проходит из-за удалённого поля
content_realization в его историческом helper; это не регрессия нового этапа.
Текущие HTTP tests на исходном c3d61ae падают при app import: startup использует
legacy load_target_client_data и обнаружение pack из другого root, видит новую
папку demo_medical, которой нет в изолированном root fixture. Исправляется общий
startup механизм, не отключение проверки. Первый запуск pytest также упирался
в системный sandbox TEMP; последующие используют отдельные ignored basetemp.

## Результат

Реализован этап 1 на codex/three-tabs-catalog поверх c3d61ae. Нормативные роли
не изменились. Основной путь: /ask либо /ask/stream → D2 turn →
resolve_d2_operations → _d2_price_block → build_d2_price_offer_row. Прежнее тело
_d2_frozen_price_row и копии formatter/variant/payment-stage helpers удалены из
materializer. Один core/d2_price_offer.py собирает существующую frozen row;
выбор offers, цена из данных, native completion, история и replay прежние.

Удалены закрытые ServiceFamily/BillingUnit перечисления, вызовы legacy unit
dictionary из D2 row и published terms, legacy loader из startup/readiness и
операционного validator, старые обязательные strategy/marketing из шаблона.
Добавлены непустые data-owned IDs, чистая общая сборка предложения, один
configured D2 root для dialogue/startup/readiness, текущий commercial scaffold,
проверка authored refs по captured snapshot и целевые offline regressions.
Эта ref-проверка общая для startup/readiness/validator; не создаёт semantic
проверку модельного ответа и не меняет per-turn recoverable source-claim путь.

Изменение поведения: новые медицинские family/unit теперь загружаются и
показывают точную авторскую подпись; startup проверяет реально используемый D2
pack выбранного root. Невалидные current commercial/tenant/content refs
блокируют readiness/startup/validator. Стоматологический выбор/суммы/бренды,
consent, privacy, effects, replay и transport owners не заменены. Все правки
в пределах exact allowlist; данные clients/demo и clients/nikadent не менялись.

Offline evidence:
- Snapshot/model view/validator: demo 23 services/33 offers, nikadent 34/26,
  medical 21/45, template 1/1 — PASS одним loader.
- Основной набор: test_d2_catalog_generalization, response_schema_contract,
  validate_client_pack, template_scaffold, d2_tenant_snapshot,
  d2_native_price_runtime — 225 passed, 2 historical failures ниже.
  Проверены все 45 medical offers, fixed/from/range/no_public_price, новая
  произвольная family/unit, ownership/forged terms/disabled option, current
  graph, native JSON/SSE price → replay → continuation и adverse completion.
- Focused после исправлений: 43 passed — 12 dental topic/count/transport,
  6 local/prod startup/ref failures, validator и release selection.
  Промежуточная ref-проверка отдельно: 12 passed.
- Для независимого сравнения экспортирован чистый origin/main f762949 в ignored
  drafts/three-tabs-catalog/baseline-main (не Git checkout/worktree). Шесть
  native topic×count сценариев там дали 6 passed. Новые regression tests
  фиксируют именно эти offer tuples и точные суммы, включая отсутствие
  умножения. Начальные ошибочные ожидания были взяты из obsolete helper и
  исправлены по clean baseline; production selection не менялся.
- Обе historical ошибки test_d2_tenant_snapshot::test_legacy_policy_edits_preserve_price_replay_and_next_turn
  (json/sse) воспроизведены на чистом main: тот же assert строки 128, старый
  raw JSON публикуется как prose вместо native show_price. Это существующий
  долг тестового helper, не регрессия. Старый test_d2_price_modes также падал
  до edits из-за удалённого content_realization. Их внеочередная миграция не
  выполнялась; пробные старые cards/guidance suites не считаются приёмкой.
- Independent Astra Checker первоначально REJECT: authored MD refs не были
  общими для readiness/startup; dental test expectations не совпадали с
  baseline. Исправления описаны выше. Focused recheck: 22 passed, оба P1
  устранены; финальный focused verdict Astra — PASS после чтения этого
  результата. Новых P0/P1/P2 нет. PASS относится только к этапу 1.
- diff --check PASS. Новый набор включён в tests/release/offline.txt.

Остатки/риски: medical пока не зарегистрирован в маршрутизации/панели; offer-
применимость акции «Три зоны» остаётся следующему этапу. UI по-прежнему открывает
первый вариант; общий новый список и no-public-price card не приняты этим
checkpoint. Dental controls/prompt/hint, read-only API, общая форма, page context
и demo admission не объявляются реализованными. Поэтому живое обобщение всего
помощника не сертифицируется. Общий код изменён локально, НикаДент pack read-only.

Provider/model calls бота 0, SMTP 0. Только подставные транспорты и локальные
offline данные. VPS, серверы и deployed dialogue не проверяли и не меняли.
Полный CI/build/deploy не запускались; merge/deploy не разрешены. Перед commit
будут проверены staged names/stat/diff/check; commit/push/PR и фактический hash
сообщаются в итоговом ответе. Foreign otzyv-1/2/3.jpg сохранены вне индекса.
