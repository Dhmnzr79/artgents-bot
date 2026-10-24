# Общий каталог и цены — owner GO 2026-10-16

## Один вызов для успешной ценовой карточки — owner GO 2026-10-24

Owner после согласования схемы поручил зафиксировать предыдущий этап и приступить.
Checkpoint d0e9e68 создан и pushed в origin/codex/three-tabs-catalog; merge/deploy0.
Продолжаем этап той же задачи в C:/Cursor Projects/artgents-bot-active (Git root),
ветка codex/three-tabs-catalog, baseline/HEAD d0e9e68, свежий origin/main7ee6323,
merge base2502be7. Index после checkpoint пуст. Foreign WIP: прежние8playground
files, docs/ARTGENTS_VPS_PRODUCTION_STATE.md и otzyv-1/2/3.jpg; не изменяем.

Класс: архитектурное упрощение согласованного успешного native-price пути.
Before: первый text при tool call удаляется, готовая карточка всегда зависит от
второго writer. After: первый вызов владеет самостоятельной информационной прозой,
код замораживает карточку; полноценный успешный результат публикуется без completion.
Removed dependency: обязательный второй model writer после успешной materialization.
Смысл свободного вопроса/проза — модель, цены/предложения/допустимость — код, по
Target Contract §3. Не добавляем classifier, control fields, state или prose repair.
Прежний callback остаётся только для отказов/неполноты; это не удаление всех вторых
вызовов и не гарантия отсутствия модельных ошибок в произвольной прозе.

Successful здесь: готовая карточка, без failure/deferred/price_reference и без
no_public_price rows. Уточнение без карточки, missing data, policy refusal и
несколько цен с прежним deferral сохраняют completion. Его текст/источники заменяют
первую прозу целиком; contacts/booking/handoff owners не меняются. Модель с пустой
прозой при mixed не исправляется эвристикой/дополнительным вызовом: риск подлежит
проверке, HTTP200 сам по себе не доказывает полноту ответа. Astra consulted.

Exact allowlist: core/d2_live_provider.py; core/one_call_prompt_contract.py;
core/response_plan_materialization.py; tests/test_d2_native_price_runtime.py;
tests/test_d2_price_variants.py; tests/test_nikadent_price_authority_offline.py;
tests/test_d2_demo_limits.py; tests/test_d2_price_variants_browser.py
(уточнение allowlist: прежние assertions двухвызовного транспорта/его fixtures);
tests/test_d2_price_single_call.py (new); tests/release/offline.txt;
docs/tasks/THREE_TABS_CATALOG_TASK.md; docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md.
Приёмка: реальные offline JSON/SSE pure/mixed, контекст/replay/UI clicks, все3tenants,
ошибочные tools/metadata и отказы/partial/failed completion; один independent Checker.
Live provider/SMTP hard budget0; новый live benchmark и VPS не разрешены этим GO.
Прежние logs и experimental scripts сохраняют доказательства двухвызовного baseline;
автоматический повтор их live запуска после изменения контракта не выполняется.

Результат локального этапа: удалено отбрасывание первой informational prose и
безусловное исполнение completion для полноценной успешной карточки. В существующем
D2ParsedDialogueResult сохраняются первая проза/claims, r1; native prices r2...
и перенумерованные actions не пересекаются. Три runtime paths:
D2HttpProvider.generate -> dialogue price callback -> resolve_d2_operations.
Materialization сама определяет полноту по frozen outcome и не вызывает callback
при успешной цене. Остальные исходы сохраняют прежний callback и заменяют старые
content/claims/order. Новых полей/состояния/семантических классификаторов нет.
Prompt contract v50 описывает изменённое авторство текста. Кодовый price/UI/lead
owner неизменен. Поведение изменилось: successful pure/mixed теперь1modelcall;
refusal/missing/partial/no-public-price/clarification остаются2, UI clicks — прежние.

Root offline evidence: 227 различных выбранных cases покрыты PASS в нескольких
целевых запусках. Основной native/variants/Nikadent набор первоначально167PASS/
8FAIL: pytest уже собрал прежний assert2 для temporary_denture до его обновления.
С финальным файлом focused12temporary cases+2Nobel-chain cases —14PASS; все8
падений закрыты, остальные price assertions/guards не ослаблялись. Новый набор
22PASS +2chainPASS; additional quota/metrics/single-model/provider набор28PASS/
2FAIL. Эти2неизменённых test_d2_live_provider_offline ожидания старого schema
и старой фразы промпта воспроизведены на чистом git archive d0e9e68: те же2FAIL.
Они не исправляются этим этапом и не названы регрессией. Прежние diagnostics
baseline failures в текущий набор не включались; полный release CI не запускался.

Independent Astra Checker PASS, лично71offlinePASS (22new/native/demo limits),
реальные callers, ownership, adverse outputs, история/replay и removal dependency
проверены. Два добавленных chain cases прочитаны, root отдельно2PASS. Checker0
provider/network/SMTP и без edits. Diff--check PASS. Первый root run имел Windows
shared app.jsonl rotation warnings; последующие процессы изолировали BOT_LOG_DIR,
логгер/runtime ради проверки не меняли. Browser fixture assertions актуализированы,
Chrome geometry не перезапускали: JS/CSS/UI payload не менялись этим этапом.

Ограничение: live prose+tool нового контракта ещё не проверены ни для Qwen, ни
для DeepSeek. Пустая mixed-проза может оставить только карточку; скрытого repair
нет, это не считается успешным содержательным ответом. Исходный prose допускает
прежний явно принятый риск модельных ошибок, суммы/предложения карточки неизменны.
Live/provider/SMTP0, VPS0. Локальная реализация закончена; до live quality GO и
бюджета новый платный прогон не запускается. Checkpoint фиксируется отдельно от
merge/deploy, foreign WIP сохранён, logs/.env/SQLite не входят в Git.

## Парный Selectel / DeepSeek API — owner GO 2026-10-24

Owner явно просит два идентичных теста: Qwen Selectel VS DeepSeek API,
одинаковые вопросы. Новый отдельный hard budget16SDKcalls/arm,32total,
retries0, без SMTP/VPS и автоматического расширения. Это диагностический
frozen-context benchmark, не runtime изменение и не самостоятельные цепочки.
Ветка/HEAD/mergebase прежние codex/three-tabs-catalog /2502be7,
origin/main7ee6323. Предыдущие prep/test edits и foreign WIP сохраняются.
Allowlist: scripts/compare_selectel_deepseek.py,
tests/test_compare_selectel_deepseek.py, эта карточка. Локальный .env не меняется.

Общая история восстанавливается офлайн через прежние проверенные синтетические
публикации Qwen, price args и действующий D2. Перед каждым вопросом сохраняются
все SQLite состояния/session stores и IP buckets; оба плеча стартуют с одного
снимка и fixed clock. Reference source может влиять на стиль и явно указан.
Первый фактический SDK input (messages/tools/choice/temp/limit/timeout) обоих
плеч захватывается без сети и сверяется SHA256 до live; live сверяется с capture.
Только одинаковая техническая model_snapshot метка нейтрализована для обоих.
Endpoint/model/provider extras различаются. Второй completion получает собственный
кодовый результат модели, его равенство не утверждается и ответы не подменяются.
Порядок AB/BA чередуется по вопросам, кэш не сбрасывается. Provider costs считаются
по собственному actual usage, DeepSeek по существующему versioned tariff; RUB
перевод по CBR24.10.2026 80.5381 — оценка без банковских комиссий.

Результат: offline paired harness 3 PASS, вместе с прежними budget tests
independent Checker 6 PASS; восемь первых фактических SDK inputs равны,
pre-live scoped PASS. Live выполнено 14 calls/arm = 28/32 всего, retries0,
16/16 HTTP200; все calls received, транспортных ошибок0. Бюджет закрыт,
дополнительных provider calls0. Локальный report:
logs/provider-comparison-20261024/live/report.html, evidence JSON рядом.

Selectel: prompt494979 = cached377600 + miss117379 (76.3% cached),
completion4018 включает reasoning2665, оценка3.48284 RUB.
DeepSeek: prompt574908 = cached515584 + miss59324 (89.7% cached),
completion1219; reasoning usage не сообщён во всех14, это unknown, не ноль.
Стоимость $0.011176752 ≈0.90015 RUB по субботнему off-peak тарифу.
Среднее полное Flask /ask время4.197s против3.311s; медиана3.998s/3.287s;
mixed7.835s/4.157s. У каждого один вызов без cache hit, остальной кэш не
выравнивался. Это сравнение подключений в данном запуске, не pure model speed
или cold/warm experiment; токенизаторы/учёт различаются.

Independent Astra post-live semantic review PASS в границах8сценариев:
прочитаны все16ответов/tools, шесть ценовых случаев дают одинаковые offers и
суммы. Исторические Nobel loss, classic-only narrowing, invalid target и
missing mixed не воспроизвелись у обоих. Неблокирующие наблюдения: Selectel
опустил volume в case1 и показал уточнение, DeepSeek unknown его подавил;
Selectel case7 сделал неподтверждённое age_group:adult без наблюдаемого влияния
на цену. «Самая премиальная» Selectel и «одна из самых известных» DeepSeek —
дополнительные оценки, не буквальные факты базы. Полная фактическая точность,
длинные самостоятельные диалоги и общий рейтинг моделей не аттестованы.

Изменён только экспериментальный harness/test и эта карточка; рабочие prompts,
данные/runtime ради результатов не правились. HEAD2502be7, index пуст,
commit/push/PR/merge/deploy0; прежние prep edits и foreign WIP сохранены.
Release CI не запускался; прежний diagnostics baseline вне текущего набора.
SMTP/VPS0. Проверяющий новых живых запросов не выполнял.

## Selectel: исторические Qwen-сценарии, скорость и кэш — owner GO 2026-10-24

Owner просит повторить прежние проблемные Qwen-тесты и измерить время/кэш.
Объявлен hard budget 32 SDK/provider calls, retries=0, никаких SMTP/VPS.
Классификация: диагностический эксперимент, не runtime bug fix или упрощение.
Preflight: та же папка/top и ветка codex/three-tabs-catalog, HEAD/mergebase
2502be7, origin/main 7ee6323. Существующие Selectel prep edits и foreign WIP
сохраняются. Allowlist этого этапа: scripts/selectel_d2_regression.py,
tests/test_selectel_d2_regression.py, эта карточка. Evidence только ignored logs.

Восемь прежних вопросов в четырёх цепочках, два независимых повтора с настоящей
накопленной историей. Current D2 /ask в Flask test_client через действующий
Selectel SDK, без замены промпта/схемы или ответов. Это не воспроизведение старого
транспорта и не сравнение с DeepSeek. Reuse isolation harness: tenant copies,
SQLite только внутри sandbox, SMTP запрещён. Global experiment guard reserves
each SDK call before network, failures consume budget, no resume/overwrite.
Перед ходом требуется запас двух вызовов. SDK retries должны быть 0.

Время: complete local Flask route и каждый provider call; ни browser rendering,
ни TCP localhost overhead, ни time-to-first-visible-text не измеряются. API
streaming не включается ради опыта. Кэш не очищается; cold/warm определяется
по usage, неизвестные счётчики отмечаются. Reasoning входит в completion_tokens
API и не прибавляется второй раз; supplied RUB output/reasoning rate одинаков.
Никакого нового состояния/поля в рабочем боте, payload/protection изменений нет.

Evidence 2026-10-24: offline budget/isolation/accounting tests 3 PASS у root и
independent Checker; pre-live scoped PASS. Live ровно 28/32 SDK calls, retries0,
16/16 HTTP200, ошибок транспорта0; бюджет запуска закрыт, дополнительных calls0.
Все counters известны: prompt990409 = cached812800 + uncached177609 (82.1% hit);
completion8968 включает reasoning6694. Оценка по owner screenshot RUB rates:
5.95164 RUB; тот же measured volume без cached discount 21.19977 RUB, не счёт.
Все28calls имели cache hits 28800–32000, cold/warm speed comparison не выполнен.
Полное Flask route время 2.0543–7.3637s; mixed6.6845/7.3637s. TTFT/browser/VPS
и параллельная нагрузка не измерялись. Игнорируемый report.html содержит все
16 синтетических публикаций, суммы, аргументы tools и время двух повторов.

Independent Astra semantic review PASS в границах8сценариев×2: Nobel сохраняется,
«Один зуб» и mixed дают classic+one_stage, warranty без цены, All-on-6 valid,
нет markers/английского planning/повтора сумм перед карточкой. Ограничения:
«самая премиальная из трёх» — интерпретация позиционирования, не буквальный факт;
volume unknown/omitted меняет уточняющий текст обзора протезирования, не offers.
Полная фактическая точность/весь бот не аттестованы; это не A/B с DeepSeek и не
доказательство эффекта только архитектуры или модели. Новая Selectel-модель
отличается от исторической Qwen. Данные/промпт/runtime не правились по результатам.
Файлы добавлены только в объявленном allowlist; HEAD2502be7, index пуст,
commit/push/PR/merge/deploy0; прежние prep edits и foreign WIP сохранены.

## Локальная подготовка Selectel — owner GO 2026-10-24

Owner: «А ты можешь это указать? А я ключ вставлю», затем после разбора
прежнего WIP: «Делай подготовку». Продолжаем в текущей ветке, без удаления
или фиксации старых материалов. Классификация: подготовка транспорта/bug fix,
не архитектурное упрощение. Границы Target Contract §3 неизменны.

Preflight: C:/Cursor Projects/artgents-bot-active (также Git top),
codex/three-tabs-catalog; HEAD/baseline и merge base 2502be7;
origin/main 7ee6323, committed trees одинаковы. Foreign WIP: восемь изменённых
static/experiments/widget-playground файлов; untracked документ состояния VPS
и otzyv-1/2/3.jpg. Index пуст. Exact allowlist: .env (ignored/local only),
.env.example, core/alibaba_openai_transport_policy.py,
tests/test_chat_transport_policy.py, эта карточка.

Подготовка: один точный Selectel base https://api.tf.selcloud.ru/v1 через
общую проверку runtime/SDK/readiness; placeholder ключа отклоняется до сети.
Локальный DEFAULT_LLM_MODEL=qwen3.8-flash-next, ключ вводит владелец.
Существующий enable_thinking=false сохраняется как запрос, не гарантия
отключения reasoning. В ручных Selectel-пробах reasoning оставался ненулевым.
Три локальные USD ставки очищаются: рублёвые тарифы не выдаются за USD.
Содержимое базы, промпт, два ценовых вызова, формы/почта и VPS не меняются.
Старые секреты не выводятся и не включаются в diff; прежний активный ключ
сохраняется в существующей provider-specific локальной настройке при необходимости.

Приёмка: targeted offline endpoint/adverse URL/key checks, запись аргументов
реального D2HttpProvider -> LLM wrapper -> фиктивный SDK create без сети,
unchanged native-price regression; один независимый Checker. Реальная SDK/HTTP
совместимость с Selectel и качество модели офлайн не подтверждаются.
Provider/model/SMTP calls: 0. Запуск, commit/push/merge/deploy не разрешены этим этапом.

Offline evidence: endpoint/arguments suite 22 PASS. Первоначальный общий набор
дал 84 PASS/4 FAIL: три новых теста предполагали отсутствующий httpx (локальный
OpenAI SDK использует другой HTTP backend); заменён только тестовый адаптер на
запись фактических SDK kwargs. После исправления все три проходят. Ещё один
существующий config-import test повторно загружал локальный .env после delenv;
readiness suite в изолированной среде PYTHON_DOTENV_DISABLED=1 и fake key —
26 PASS. Native price и single-model tests прошли в первоначальном наборе.
Итого все 88 различных выбранных cases покрыты PASS; это offline доказательство,
не проверка Selectel по сети и не новый full CI. Diff check чистый, index пуст.

Independent Astra Checker: PASS scoped transport preparation; independently
25 PASS (endpoint/SDK arguments + single model), actual runtime/readiness path
traced. Temp-directory permission issue resolved with dedicated workspace basetemp.
No live/provider/SMTP calls; no edits by Checker. Removed: no semantic paths;
added: exact Selectel endpoint admission and placeholder rejection. Only local
provider configuration changes after owner inserts key and restarts. No fallback,
model calls, prompt, tenant/privacy/lead/price ownership changes. HEAD unchanged
2502be7; four tracked files unstaged, ignored .env local only; no commit/push/PR/
merge/deploy. Eight playground files and four untracked old materials preserved.

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

## Отдельная песочница шрифтов и отступов — owner GO 2026-10-17

Owner попросил автономный HTML/CSS/JS виджет с основными UI состояниями,
Inter/Roboto и переключателем для телефона. Это отдельный статический макет
оформления в рамках текущей задачи; рабочий runtime/архитектура не меняются.
Preflight repo/top C:/Cursor Projects/artgents-bot-active, branch
codex/three-tabs-catalog, HEAD/baseline b3f14dd2e83048ddb6cd14781b7f443bc06445a0;
origin/main/mergebase f7629491f2bb93ed80e2f58aea53770841bbd6a3.
Tracked/index чистые, foreign otzyv-1/2/3.jpg сохраняются. Exact allowlist:
- static/experiments/widget-playground/index.html
- static/experiments/widget-playground/styles.css
- static/experiments/widget-playground/app.js
- static/experiments/widget-playground/fonts.css
- static/experiments/widget-playground/build.py
- static/experiments/widget-playground/README.md
- static/experiments/widget-playground/assets/avatar.png
- static/experiments/widget-playground/assets/inter-cyrillic-wght-normal.woff2
- static/experiments/widget-playground/assets/inter-latin-wght-normal.woff2
- static/experiments/widget-playground/assets/roboto-cyrillic-wght-normal.woff2
- static/experiments/widget-playground/assets/roboto-latin-wght-normal.woff2
- static/experiments/widget-playground/assets/OFL.txt
- static/experiments/widget-playground/assets/Roboto-LICENSE.txt
- docs/tasks/THREE_TABS_CATALOG_TASK.md

В макете подготовленные диалог/ценовые варианты/продолжения, каталог,
fixed/from/range/no-public/unit, группы/поиск, состав/доплаты/условия/оплата/акция,
общая форма и success. Никаких API/model/lead/SMTP вызовов; данные контактов
только в памяти страницы, localStorage только предпочтения оформления.
Форма имитирует UI, не доставку. Все примеры не являются новой базой клиентов.
Шрифты/аватар скопированы из имеющихся локальных assets с лицензиями.
Настройки font/size/line-height/spacing/weight/desktop-width, экспорт CSS.
build.py создаёт portable inline HTML и source ZIP в ignored drafts/widget-playground.
Отдельный static server192.168.0.2:9100 раздаёт только папку песочницы;
бот9001 и VPS не меняются. static/experiments/ локально ignored в .git/info/exclude;
при checkpoint разрешён force-add только перечисленных точных путей.
Проверки: JS syntax, Chromium mobile geometry/сценарии/InterRoboto/формы/
preferences/portable file, один пропорциональный Checker изолированного макета.

Результат: 12 экранов ×2 шрифта ×4 ширины (320/390/430/1280) —96 сочетаний PASS;
крупные настройки дополнительно320/390/430 PASS, поиск зон/выбранная позиция/
общий черновик/consent gate/success/escaping/history/settings persistence/CSS
export/portable file PASS. CDP подтвердил реальный custom Roboto, шрифты локальные.
Макет не делает network writes. Independent Checker PASS: JS syntax, portable
HTML без external resources с4 встроенными fonts, ZIP integrity,13 исходников
и card проверены; P0/P1/P2 нет. Прежние production suites не запускались.
Локальная страница http://127.0.0.1:9100/ отвечает200. Сервер макета теперь
bind0.0.0.0:9100, launcherPID23040; раздаёт только папку песочницы. LAN192.168.0.2
не подтвердился (timeout даже с компьютера), firewall/VPN не менялись;
доступ с реального телефона и клавиатура не проверены. Самодостаточный HTML
и ZIP готовы в drafts/widget-playground/. Provider/model/SMTP/VPS0.
14 точных путей, foreign3JPG сохранены. Checkpoint `Add standalone widget typography playground`,
push в текущую ветку; draft PR34, без merge/deploy. Владелец продолжает ручную проверку.

## Этап 7: структура каталога и устранение повторов — owner GO 2026-10-17

Owner GO после фиксации CATALOG_INTERFACE_SPEC.md: «Можешь делать правки».
Текущий блок — UI bug fix по этому документу, не архитектурное упрощение D2.
Preflight repo/top C:/Cursor Projects/artgents-bot-active, branch
codex/three-tabs-catalog, HEAD/baseline64853b363a6b30c2d998bde00ba483c3bca2bdc9;
origin/main/mergebase f7629491f2bb93ed80e2f58aea53770841bbd6a3.
Tracked/index чистые, foreign otzyv-1/2/3.jpg сохраняются. Exact allowlist блока:
- core/d2_price_offer.py
- core/widget_catalog.py
- static/widget/catalog.js
- static/widget/price_card.js
- static/widget/widget.css
- tests/test_widget_catalog.py
- tests/test_widget_catalog_structure_browser.py
- docs/tasks/THREE_TABS_CATALOG_TASK.md

Удаляем UI label/счётчик, отдельную подпись выбранного варианта, Об услуге,
дополнительные примечания из price-area. Добавляем summary цены сервиса
на сервере из canonical rows прежним форматтером; у multiple — minimum «от»,
no-public в списках пусто. Renderer сохраняет общий механизм; catalog-only
presentation переносит существенные condition_texts в нижний блок условий,
не меняя rows, eligibility, model/view/history/lead. Title выбранной позиции
владеет catalog, цена/условия — прежний builder, как в Target Contract §3.
Новых цен/акций/наполнения клиентов нет. UI-only renderer option не передаётся
в API/model и не меняет подбор offers. Проверки: catalog unit, structure browser,
shared form/remount, no-public chat regression, один focused Checker; provider0.

Результат блока по спецификации: label и счётчики убраны; цены списка справа,
стрелки под ними. Нет публичных rows — цены в списке нет, одна публичная row —
её исходная fixed/from/range строка, несколько — минимум нижних границ с «от».
Canonical rows, состав/доплаты/акции и условия клиентов не изменены. Заголовок
выбранной позиции берётся из variant_label; отдельный повтор label и общее
описание услуги не выводятся. Если отдельной authored расшифровки варианта нет,
общий текст или текст условий вместо неё не придумывается. Об услуге удалён.
Под ценой только scope_text; остальные condition_texts перенесены в conditions,
точные совпадения со scope/excludes повторно не выводятся. Порядок непустых
блоков: includes, excludes, conditions, payment, promotion. Chat layout прежний.

Astra подтвердила границы: локальная presentation option catalog=true,
canonical rows не меняются, summary использует прежний formatter, никаких
семантических фильтров/классификаторов/новой памяти. Текущие packs только RUB;
новое сравнение разных валют этим этапом не задаётся.
Offline33PASS (включая9 fixed/from/range/min/zero/no-public cases), browser7PASS
46.14s (structure3, three-tabs3, no-public chat1), итого40 разных cases.
Browser проверяет отсутствие label/count/extra-notes/Об услуге, blank no-public
списки и сохранённый no-public detail, title выбранного варианта, перенос
обязательных условий, поиск/назад/другой вариант/точную заявку и adaptive layout.
Real9001 read-only3tenant PASS: root/services/positions/detail снимки просмотрены;
снимки и harness ignored drafts/three-tabs-catalog/spec-*. /ask и /lead блокированы.
Новых failures нет; известные4 legacy failures прежнего этапа не затронуты,
прежние datetime.utcnow warnings сохраняются. Full release CI, live model,
physical iOS/Android/keyboard не проверялись. Provider/model/SMTP/VPS/merge0.
Восемь файлов allowlist; foreign3JPG сохранены, иных WIP нет. Checkpoint
`Apply agreed catalog presentation` в текущую ветку и draft PR34, без deploy.
Independent Checker PASS: собственные33PASS, JUnit7 browserPASS без пропусков;
P0/P1/P2 нет. Staged names/stat/diff/check проверяются перед commit;
после checkpoint индекс пуст, push в origin/codex/three-tabs-catalog.

Уточнение owner после просмотра: внутренние variant tabs в выбранной позиции
каталога убрать. Список вариантов → одна позиция с её названием, ценой и
условиями → возврат к тому же списку для другого выбора. Предыдущее решение
сохранить detail tabs ниже — неверная интерпретация исполнителя и отменено.
Это UI bug fix текущего этапа, не изменение архитектуры D2. Preflight:
repo/top C:/Cursor Projects/artgents-bot-active, codex/three-tabs-catalog,
HEAD/baseline44bb33df7eb62c8b997a18c8c5c0963ec992d277; origin/main/mergebase
f7629491f2bb93ed80e2f58aea53770841bbd6a3. Tracked/index чистые, foreign JPG3.
Allowlist уточнения: static/widget/catalog.js,
tests/test_widget_catalog_structure_browser.py, docs/tasks/THREE_TABS_CATALOG_TASK.md.
В detail каталог передаёт только выбранную row без sibling choices;
общий renderer показывает её variant_label. Options остаются полным списком,
price/conditions/lead и карточки разговора не изменяются. Удаляется обработка
переключения detail→detail в каталоге. Проверяется отсутствие tabs, сохранение
названия/цены/точной заявки и возврата к списку у трёх клиентов.
Результат уточнения: structure3PASS; shared-form browser demo/Nika2PASS,
medical после одного падения первого batch прошёл focused recheck1PASS без
изменения кода/теста. Итого6 разных cases прошли, первый прогон5PASS1FAIL;
причина непостоянного падения не установлена (traceback вывода был усечён).
Read-only real9001 HIFU detail просмотрен без tabs, /ask и /lead блокированы.
Provider/SMTP/VPS0, diff --checkPASS. Изменены только три allowlist пути;
старые baseline failures предыдущего блока не затронуты. Chat не менялся.
Focused Checker PASS: путь catalog→общий renderer→выбранный offer→форма
проверен; P0/P1 нет, новых P2 нет. Нестабильность первого browser прогона
не объявляется устранённой. Checkpoint: `Remove variant tabs from catalog details`,
push в текущую ветку и прежний draft PR34; индекс после commit пуст.

Owner подтвердил перенос структуры из artgents-three-clinics-arrow-below-price.html
в нашу дизайн-систему, затем остановил для замечания о дубле exclusions и дал
«Ладно делай, потом смотрим». Уточнения: prototype только про каталог;
прежняя логика карточек/conditions/lead и иконки сохраняются. Цена справа сверху,
SVG под ценой. Повтор раздела над названием услуги убрать. Никаких prototype
ask-service/new-lead/auto-booking, новых шрифтов/тем/данных/цен.

Preflight repo/top C:/Cursor Projects/artgents-bot-active,
branch codex/three-tabs-catalog; HEAD/baseline528b90c9bbf590fd423b0966ce8c5099c47e6135;
origin/main и merge base f7629491f2bb93ed80e2f58aea53770841bbd6a3.
Tracked/index чистые, foreign otzyv-1/2/3.jpg сохраняются. Продолжение той же ветки.
Тип: UI/data bug fix и согласованная структура каталога, не упрощение всей D2 архитектуры.

Astra консультация: только authored show_sections и группы canonical offers;
полнота/tenant/service/active refs проверяются snapshot loader. Без групп —
прежний полный список, с группами — каждый eligible offer ровно один раз.
Новые поля — только presentation metadata по прямому GO на структуру прототипа.
Строки/цены собирает прежний builder, показывает один общий price_card renderer;
поиск фильтрует видимость, не eligibility и не draft. Варианты в detail сохраняются.
Canonical medical service IDs не объединяются под широкие экраны прототипа.
Target Contract §3 применяется к каждому пути, роли/selection/model не меняются.

Причина дубля: полный перечень package.excludes повторялся агрегированной
строкой mandatory_exclusion metadata. Удалены45 списочных копий medical и4
дословные копии nikadent. Dental16 остаются без изменений: их отдельные краткие
mandatory caveats нужны действующему price contract, полный перенос их authority
не входит в UI этап. Sole owner полных списков — package.excludes; самостоятельные
caveats, completeness и scope сохраняются. Runtime semantic/string фильтров
не добавлять. build_d2_published_offer_terms уже включает все excludes. Plain
detail теперь должен публиковать их один раз и при include_card_details=False,
чтобы не потерять условия вне виджета; history читает тот же frozen row.
Это bug fix повторной авторской записи, без нового source-ref или модели.

Exact allowlist:
- contracts/widget_catalog.py
- core/widget_catalog.py
- core/d2_tenant_snapshot.py
- core/response_text_renderer.py
- static/widget/catalog.js
- static/widget/price_card.js
- static/widget/widget.css
- clients/demo/target_response/widget_catalog.json
- clients/demo_medical/target_response/widget_catalog.json
- clients/nikadent/target_response/widget_catalog.json
- tests/test_widget_catalog.py
- tests/test_widget_three_tabs_browser.py
- tests/test_widget_catalog_structure_browser.py
- tests/test_d2_catalog_exclusions.py
- tests/release/offline.txt
- docs/CLIENT_PACK_AUTHORING.md
- docs/tasks/THREE_TABS_CATALOG_TASK.md
- docs/artifacts/artgents-three-clinics-arrow-below-price.html
- clients/demo_medical/target_response/pricebook/services/abdominal_ultrasound.standard.json
- clients/demo_medical/target_response/pricebook/services/abdominal_ultrasound.with_kidneys.json
- clients/demo_medical/target_response/pricebook/services/biorevitalization.face.json
- clients/demo_medical/target_response/pricebook/services/biorevitalization.face_neck.json
- clients/demo_medical/target_response/pricebook/services/botulinum_therapy.individual.json
- clients/demo_medical/target_response/pricebook/services/botulinum_therapy.unit.json
- clients/demo_medical/target_response/pricebook/services/cardiology_consultation.primary.json
- clients/demo_medical/target_response/pricebook/services/cardiology_consultation.with_ecg.json
- clients/demo_medical/target_response/pricebook/services/cervical_screening.basic.json
- clients/demo_medical/target_response/pricebook/services/cervical_screening.extended.json
- clients/demo_medical/target_response/pricebook/services/dermatology_consultation.primary.json
- clients/demo_medical/target_response/pricebook/services/dermatology_consultation.repeat.json
- clients/demo_medical/target_response/pricebook/services/digital_dermatoscopy.extended.json
- clients/demo_medical/target_response/pricebook/services/digital_dermatoscopy.one.json
- clients/demo_medical/target_response/pricebook/services/digital_dermatoscopy.three.json
- clients/demo_medical/target_response/pricebook/services/ecg.default.json
- clients/demo_medical/target_response/pricebook/services/ent_consultation.primary.json
- clients/demo_medical/target_response/pricebook/services/ent_consultation.repeat.json
- clients/demo_medical/target_response/pricebook/services/ent_endoscopy.default.json
- clients/demo_medical/target_response/pricebook/services/gynecology_consultation.primary.json
- clients/demo_medical/target_response/pricebook/services/gynecology_consultation.repeat.json
- clients/demo_medical/target_response/pricebook/services/laser_hair_removal.legs.json
- clients/demo_medical/target_response/pricebook/services/laser_hair_removal.three_zones.json
- clients/demo_medical/target_response/pricebook/services/laser_hair_removal.underarms.json
- clients/demo_medical/target_response/pricebook/services/nasal_lavage.single.json
- clients/demo_medical/target_response/pricebook/services/nasal_lavage.three_visits.json
- clients/demo_medical/target_response/pricebook/services/neurology_consultation.primary.json
- clients/demo_medical/target_response/pricebook/services/neurology_consultation.repeat.json
- clients/demo_medical/target_response/pricebook/services/pediatric_consultation.primary.json
- clients/demo_medical/target_response/pricebook/services/pediatric_consultation.repeat.json
- clients/demo_medical/target_response/pricebook/services/photorejuvenation.face.json
- clients/demo_medical/target_response/pricebook/services/photorejuvenation.face_neck.json
- clients/demo_medical/target_response/pricebook/services/photorejuvenation.hands.json
- clients/demo_medical/target_response/pricebook/services/plasma_therapy.face.json
- clients/demo_medical/target_response/pricebook/services/plasma_therapy.scalp.json
- clients/demo_medical/target_response/pricebook/services/plasma_therapy.three_visits.json
- clients/demo_medical/target_response/pricebook/services/therapist_consultation.primary.json
- clients/demo_medical/target_response/pricebook/services/therapist_consultation.repeat.json
- clients/demo_medical/target_response/pricebook/services/thyroid_ultrasound.standard.json
- clients/demo_medical/target_response/pricebook/services/thyroid_ultrasound.with_cervical_nodes.json
- clients/demo_medical/target_response/pricebook/services/ultrasound_lifting.face350.json
- clients/demo_medical/target_response/pricebook/services/ultrasound_lifting.face_neck500.json
- clients/demo_medical/target_response/pricebook/services/ultrasound_lifting.lower_face.json
- clients/demo_medical/target_response/pricebook/services/urology_consultation.primary.json
- clients/demo_medical/target_response/pricebook/services/urology_consultation.repeat.json
- clients/nikadent/target_response/pricebook/services/classic.default.json
- clients/nikadent/target_response/pricebook/services/core_inlay.default.json
- clients/nikadent/target_response/pricebook/services/implant_supported_prosthetics.crown.json
- clients/nikadent/target_response/pricebook/services/one_stage.default.json

Проверки: targeted catalog/schema/группы completeness и bad refs, scaffold;
общие цена/exclusions/plain/history, browser sections/flat/groups/search/back,
320/360/390/430/desktop и200%text, exact draft/lead/restore. Один independent
Checker завершённого блока; после finding focused recheck. Provider/SMTP0,
VPS/merge/deploy0. Full releaseCI/physicaliOSAndroid не заявляются.

Результаты до Checker: новый catalog/schema/exclusions subset30PASS,
новый structure Chrome3PASS; earlier shared three-tabs/no-public4PASS.
Новый длинный canonical pack выявил ошибку active=None: UI catalog исключал
варианты с отсутствующим active, хотя shared builder считает их enabled.
Исправлено единственное условие на `active is not False`, согласованное
с общим builder; inactive=False по-прежнему исключён и проверяется тестом.
Никаких новых fallback/eligibility heuristics. Остальные роли не меняются.
Baseline archive528b90c: старые visual/legacy tests17PASS4FAIL (3 stale imports
_d2_brief_price_conditions из старого модуля,1 прежнее ожидание Nika unknown
completeness). Эти же файлы сравниваются с финальным кодом, не ослабляются.
Первичная более широкая чистка Dental вызвала5 дополнительных legacy failures;
Dental правки полностью отменены, отдельный renderer/adapter для legacy не добавлен.

Финальный результат: разделы → услуги с числом позиций → сгруппированные
предложения → прежняя подробная карточка. Доступен плоский список услуг через
authored show_sections; у длинных прайсов поиск, возврат сохраняет запрос и
прокрутку. Цена справа, прежний SVG под ценой; длинная цена без публичного
числа остаётся читаемой. Повтор section eyebrow удалён. Inter, дизайн-токены,
иконки, canonical выбор, detail tabs и общая форма сохранены.

Финальная проверка: catalog/schema/exclusions30PASS, browser7PASS
(three-tabs3 + structure3 + no-public1), embedded3PASS. Structure проверяет
все три tenant, плоский каталог, группы, длинный canonical pack, фильтрацию,
возврат, точный выбор, 5 ширин и текст100/200%. После ожидания fonts.ready
финальный layout run полностью зелёный. Baseline/current legacy одинаковы:
17PASS4 прежних FAIL, описанных выше; новых регрессий в этом subset нет.
Independent Checker PASS: собственные30PASS, все49 JSON сверены по полям,
67 изменённых/новых файлов в allowlist, P0/P1/P2 отсутствуют. Это подтверждение
локального этапа UI/data, не сертификация всей D2 архитектуры или живой модели.

Real9001 read-only скриншоты всех трёх клиентов просмотрены; финальные экраны
demo positions и medical HIFU detail с раскрытыми исключениями проверены.
Снимки и локальные harness находятся в ignored drafts/three-tabs-catalog/;
/ask и /lead блокировались. Provider/model/SMTP0, VPS/merge/deploy0.
Full release CI, физические устройства и экранная клавиатура не проверялись.
Foreign otzyv-1/2/3.jpg сохранены. Итоговый staged diff проверяется перед commit;
checkpoint `Transfer grouped catalog structure and remove duplicate exclusions`
публикуется в прежнюю ветку codex/three-tabs-catalog и draft PR34, без merge.

## Этап 6: короткая подпись каждой услуги — owner GO 2026-10-16

Owner: «Мы можем добавить для каждой услуги такие описания?» после объяснения,
что нынешняя подпись складывается из первого варианта и счётчика и потому
отсутствует у части услуг. Добавляем authored краткое пояснение для каждой
из70 услуг трёх клиентов; оно выводится в списке вместо этих технических данных.
Тип: UI/data bug fix и наполнение, не архитектурное упрощение D2.

Preflight repo/top C:/Cursor Projects/artgents-bot-active,
codex/three-tabs-catalog, baseline/HEAD eced7141b5e9dea32979bcadd071d8aa7bd7e4ad.
origin/main и merge base f7629491f2bb93ed80e2f58aea53770841bbd6a3.
Tracked/index чистые; foreign untracked otzyv-1/2/3.jpg сохраняются.
Продолжение того же продукта/ветки, новая ветка и merge не нужны.

Единственный источник UI-подписей: существующий authored widget_catalog.json
клиента, рядом с подписями направлений, карта service_subtitles по service_id.
Полное совпадение ключей с service_ids валидируется; пустая/чужая/пропущенная
подпись — ошибка базы, без fallback из вариантов, MD или модели. Endpoint
отдаёт subtitle, renderer только выводит его. Полное описание услуги по-прежнему
из MD; никаких новых медицинских/ценовых обещаний в кратких подписях.
Ответственность Target Contract §3, price/selection/model/privacy/lead/transport
не меняется. Новых runtime handlers/состояний/модельных вызовов нет.

Exact allowlist:
- contracts/widget_catalog.py
- core/widget_catalog.py
- static/widget/catalog.js
- clients/demo/target_response/widget_catalog.json
- clients/demo_medical/target_response/widget_catalog.json
- clients/nikadent/target_response/widget_catalog.json
- clients/_template/target_response/widget_catalog.json
- tests/test_widget_catalog.py
- tests/test_widget_three_tabs_browser.py
- docs/CLIENT_PACK_AUTHORING.md
- docs/tasks/THREE_TABS_CATALOG_TASK.md

Проверки блока: completeness/invalid map refs/tenant endpoint и прежние exact
price/read-only invariants; browser показывает authored subtitle и сохраняет
сценарии/геометрию. Один independent Checker для нового presentation contract.
Никаких provider/SMTP/VPS/merge/deploy; физические устройства не заявляются.

Checker finding: новый обязательный presentation field нужен также scaffold
template. Allowlist дополнен clients/_template/target_response/widget_catalog.json:
добавлена подпись единственной sample_service без runtime/прочих шаблонных правок.
Проверяется существующим test_client_pack_template_scaffold.py вместе с текущим
catalog subset; это согласование нового общего поля, не расширение функций.
По замечанию Checker также дополнен docs/CLIENT_PACK_AUTHORING.md: описание
новой обязательной карты и её границы, чтобы следующий клиент не пропускал поле.

Результат: заполнены70 service_subtitles (demo22, medical21, nikadent27),
обновлён scaffold. Удалена сборка строки first variant + «Вариантов:N»;
добавлена единственная прямая authored projection, без новых состояний/эвристик.
Полные описания MD/цены/варианты/иконки/CSS/формы/consent не изменены.
Offline18PASS (catalog15+three-tabs3), focused19PASS (template4+catalog15),
то есть22 различных targeted cases. CheckerPASS: собственные15PASS +focused
template validatorPASS; замечание по authoring docs устранено текстовой правкой.
Read-only real9001: startup_check_ok всех3 клиентов, снимки списков с новыми
подписями просмотрены; /ask и /lead блокировались. Provider/SMTP0, VPS0.
Новых baseline failures нет; прежние datetime.utcnow warnings остаются.
Полный release CI и физические устройства не проверялись. Foreign JPG сохранены.
Checkpoint subject: `Add authored subtitles for every catalog service`;
push в текущую ветку/PR34 без merge/deploy.

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


## 2026-10-17 — полноценный автономный образец (owner GO)

Bug fix образца, не изменение архитектуры бота. Baseline 3c2b446, ветка codex/three-tabs-catalog; origin/main и merge base f762949. В allowlist только static/experiments/widget-playground/{index.html,app.js,styles.css,build.py,README.md,sync-reference.py,reference-data.js,reference-renderer.js,reference-cards.css} и этот документ. Существующие незавершённые правки index/build и generated reference-файлы продолжаем. Foreign otzyv-1/2/3.jpg сохраняем.

Owner: несколько полноценных услуг из реальных демо без сокращения состава, исключений, условий, этапов оплаты и акций; диалог, каталог и форма как в виджете. Убрать ползунки, оставить Inter/Roboto. Под ценой один scope, стрелка раскрытия аккордеона; самолётик внутри поля. Восстановить прежнюю высоту образца: из 7c7ca52 — 720 px, при высоте экрана до 800 px — 680 px; ограничить доступным местом. Только статический образец, без API/отправки заявок/VPS. Проверки: точность всех экспортированных offers, мобильная вёрстка, раскрытие разделов, форма и согласие, автономный HTML. Затем один focused Checker.

Результат: удалены сокращённые придуманные услуги/самодельный price renderer и панель ползунков. Добавлены полный снимок 8 услуг/16 offers, копии настоящего price renderer/formatter и формы с локальными load/submit. Перенесены стили карточек/формы; Inter/Roboto, компактные 720/680 px, самолётик внутри поля, шеврон вниз/вверх. Production-код и контент клиентов не менялись. HTML/ZIP: drafts/widget-playground/artgents-widget-playground-v2.{html,zip}.

Offline evidence: check-v2.mjs — PASS: полные includes/excludes/stages/commercial parts всех 16 offers, 4 размера × 2 шрифта, общий черновик и согласие, отправка сообщения, кнопка внутри поля, автономный HTML, отсутствие ошибок JS. Независимый Checker — PASS; отдельно сравнил все offers с build_widget_catalog и копии renderer/formatter с исходниками. diff --check PASS. Это browser emulation, не физический телефон; живую модель не проверяли. Historical production test failures вне этого этапа, полный CI не запускался. Provider/model/SMTP calls 0. Git: точный allowlist будет сохранён в topic commit/push, PR34 остаётся draft; merge/deploy не выполняются. Foreign otzyv-1/2/3.jpg сохранены.


## 2026-10-17 — единая подробная ценовая карточка (owner GO)

Bug fix общего UI, не изменение архитектуры D2. Baseline 21b52ba, branch codex/three-tabs-catalog; origin/main / merge base f762949. Exact allowlist: static/widget/price_card.js, static/widget/widget.css, static/experiments/widget-playground/{reference-renderer.js,reference-cards.css,README.md}, tests/test_widget_price_details_browser.py, docs/tasks/{CATALOG_INTERFACE_SPEC.md,THREE_TABS_CATALOG_TASK.md}. Foreign otzyv-1/2/3.jpg read-only.

Owner GO: один scope под ценой в каталоге и диалоге; все condition_texts внутри раскрытия. Первые три секции — единые маркированные списки, начальная заглавная; оплата остаётся этап/сумма/срок. Четыре секции максимум, пустые не показывать; promo UI без изменений. Проверка всех существующих pack/offer и совпадения канонических материалов, browser proof обоих путей. Sole presentation owner — price_card.js; строки/выбор/tenant/privacy/transport остаются прежними по Target Contract §3. Удаляем отдельный вывод condition_texts под ценой в диалоге и check-list-only оформление includes; новый сборщик списка общий для includes/excludes/conditions. Данные не переписываем и смысловые повторы эвристиками не удаляем. Provider/VPS 0; затем один независимый Checker.

Результат: в общем renderPriceBody удалён reachable вывод condition_texts дополнительными строками под ценой в диалоге. Catalog и widget.js вызывают один renderer: scope_text — единственный блок уточнения. Условия перенесены в conditions, точные совпадения с scope/excludes не повторяются. Includes/excludes/conditions используют один addItems: точки, начальная заглавная, сохранение safe emphasis, без вложенных старых списков/абзацев. Точные повторения пунктов после оформления не выводятся; полностью пустые секции удаляются. Payment stage formatter и promo UI не изменены. Образец регенерирован из общего кода, HTML/ZIP v2 обновлены.

Аудит данных: demo 22 services/33 offers; demo_medical 21/45; nikadent 27/26; _template 1/1 — всего 105 offers. Прочитаны все scope_text; непустые короткие объёмы в одном поле без переносов/списка примечаний. No-public-price остаётся со своим approved_text и без выдуманного scope. Введён UI-инвариант, а не семантическая проверка качества новых авторских формулировок. В данных остаются возможные смысловые повторы разными фразами (например, общий текст про доплаты и отдельные исключения); их автоматическое угадывание/удаление не добавляли. Content rewrite отложен владельцем.

Evidence: 101 существующий тест PASS (3 catalog structure browser + 98 catalog generalization). Новый browser test PASS — 105 offers × catalog/chat = 210 displays, все исходные includes/excludes/условия/stages/commercial parts, exact price/scope, единые списки/регистр/порядок, generic future-service rich-text и пустые блоки. Первое падение нового теста было ошибкой чтения textContent между heading и p этапа (конкатенация без пробела); test reader исправлен на объединение текстовых узлов, focused повтор PASS. Sample check-v2 PASS: 16 полных offers, 4 размера × 2 шрифта, форма/согласие/shared draft/composer/portable. Независимый Checker PASS после чтения двух call paths и повторного запуска нового теста. diff --check PASS. Только существующие datetime.utcnow warnings; полный CI не запускался. Provider/model/SMTP calls 0, VPS не менялся. Физический телефон и живые ответы модели не проверяли. Индекс будет содержать только allowlist, topic commit/push без merge/deploy; фактический hash в ответе. Foreign JPG сохранены.


## 2026-10-17 — весь активный путь цены, owner GO

Bug fix источника доплат и текстовой проекции, не полное архитектурное упрощение. Baseline e32b76d; branch codex/three-tabs-catalog, origin/main и merge base f762949. Foreign otzyv-1/2/3.jpg read-only. Owner требует один scope под ценой в коде всего бота; доплаты только в собственном раскрытии, без runtime semantic filters. Astra consulted read-only: подтверждены общий price builder, API answer, JSON/SSE, модельная история и восстановление; D2 §3 остаётся нормативной таблицей.

Exact allowlist:
- core/response_text_renderer.py
- tests/test_d2_catalog_exclusions.py
- docs/tasks/CATALOG_INTERFACE_SPEC.md
- docs/tasks/THREE_TABS_CATALOG_TASK.md
- static/experiments/widget-playground/reference-data.js
- clients/demo/target_response/pricebook/services/classic.one_tooth.implantium.json
- clients/demo/target_response/pricebook/services/classic.one_tooth.impro.json
- clients/demo/target_response/pricebook/services/classic.one_tooth.nobel.json
- clients/demo/target_response/pricebook/services/one_stage.one_tooth.implantium.json
- clients/demo/target_response/pricebook/services/one_stage.one_tooth.impro.json
- clients/demo/target_response/pricebook/services/one_stage.one_tooth.nobel.json
- clients/demo/target_response/pricebook/services/all_on_4.jaw.implantium.json
- clients/demo/target_response/pricebook/services/all_on_4.jaw.impro.json
- clients/demo/target_response/pricebook/services/all_on_4.jaw.nobel.json
- clients/demo/target_response/pricebook/services/all_on_6.jaw.implantium.json
- clients/demo/target_response/pricebook/services/all_on_6.jaw.impro.json
- clients/demo/target_response/pricebook/services/all_on_6.jaw.nobel.json
- clients/demo/target_response/pricebook/services/implant_supported_prosthetics.default.json
- clients/demo/target_response/pricebook/services/sinus_lift.one_site.closed.json
- clients/demo/target_response/pricebook/services/sinus_lift.one_site.open.json
- clients/demo/target_response/pricebook/services/zygomatic_implants.default.json
- clients/demo/target_response/pricebook/services/removable_dentures.jaw.partial.json
- clients/demo/target_response/pricebook/services/removable_dentures.jaw.full.json
- clients/demo/target_response/pricebook/services/pterygoid_implants.default.json
- clients/demo/target_response/pricebook/services/temporary_teeth.default.json
- clients/demo/target_response/pricebook/services/zirconia_crowns.default.json
- clients/demo/target_response/pricebook/services/pulpitis.default.json

До: в demo одно исключение записано в package.excludes, хвосте package.label и required_conditions_metadata; backend compact renderer дописывает condition_texts в ценовой абзац, а потом печатает excludes. После: авторская доплата только в excludes; price paragraph formatter печатает только цену и scope, отдельно именованные разделы. Важные прочие условия и few_teeth сохраняются, полная published-terms проекция не обнуляется. Убираем inline-конкатенацию условий и повторные авторские копии исключений; без классификатора, новых полей/enum, поисковых словарей или вызовов модели. Смешанные подписи с независимыми неценовыми условиями не перепроектируем: для их полного разнесения понадобился бы новый общий тип condition_id, это отдельный scope и здесь не делается. Никаких новых проверяющих слоёв.

Проверки: все105 canonical offers → текст/карточка; реальные локальные HTTP routes JSON/SSE с подставным provider, выбор и replay, публичная история/remount; targeted current native/catalog tests. Live provider/VPS calls не разрешались, 0. Затем один Checker.

Результат этапа: из _render_compact_price_group удалены include_conditions, сбор common/local notes и их конкатенация в ценовой абзац/строку. Он форматирует только service/variant, price_display_text и scope_text. render_response_text печатает condition_texts отдельным разделом после исключений; тот же renderer используется API, completion, модельной историей и widget-session. Старые текстовые строки без card metadata сохраняют свой display_text, а их отдельные условия теперь имеют явный заголовок вместо bare paragraphs; новую миграцию receipt/данных не вводили. UI использует ранее проверенный единственный scope.

В 22 demo offers убраны авторские копии исключений из label/metadata. У пяти списки excludes явно заполнены ранее указанными доплатами: removable partial/full, pterygoid, temporary_teeth, zirconia. Git-сравнение всех22JSON подтверждает неизменные суммы/режимы/объёмы/includes/stages/facts/refs и сохранность всех прежних excludes. Условия sinus lift о зависимости цены от материала/доступа сохранены. НикаДент/медцентр/шаблон данные не менялись. Общая схема/поля и few_teeth пояснение не менялись. Это исправление источника дублей и отображения; нормализация всех смешанных authoring labels и общая чистка исторических tests не заявляются.

Evidence: 60 PASS — tests/test_d2_catalog_exclusions.py, test_widget_price_details_browser.py, test_widget_session.py, test_d2_native_price_runtime.py. В том числе16 проверок exclusions: реальные Flask /ask и /ask/stream c подставным provider, click, replay без нового вызова, история и POST /api/widget-session; pure text всех105offers, unknown-condition formatter. DOM proof105×2contexts. Ещё4PASS validator всех pack. Lint pricebook0warnings/PASS. Sample check-v2 PASS: 16 полных предложений,4размера×2шрифта,форма/черновик/согласие/composer/portable HTML. Независимый Checker PASS после чтения actual API/completion/history/remount paths и повторных16тестов. diff --check PASS. Наблюдались только прежние datetime.utcnow deprecation warnings; новых падений в этом наборе нет, полный CI/исторические внеочередные suites не запускались.

Live/provider/model/SMTP/VPS calls0. Это локальная проверка текущего кода с подставной моделью, не проверка реальных ответов модели или развёрнутого VPS. Образец и HTML/ZIP v2 обновлены. Git: commit/push только topic branch;PR34 draft, без merge/deploy; hash в ответе. Exactallowlist27paths, индекс очищается commit, foreign3JPG сохранены.

## 2026-10-18 — Aura / Orbit в локальном рабочем виджете, owner GO

Классификация: UI bug fix / перенос согласованного дизайна, не D2 архитектурное упрощение. Источник artgents-clean-v6.html и handoff-v5 в Downloads; owner подтвердил Inter-only, текущий межбуквенный интервал, три стартовых пункта и сохранение рабочего выбора объёма в диалоге. Demo Aura (синий), ArtMed Orbit (бирюзовый), НикаДент Orbit (фиолетовый). Только локальная реализация: без merge/VPS/provider/SMTP.

Baseline: C:/Cursor Projects/artgents-bot-active, codex/three-tabs-catalog, HEAD6674f4a, origin/main и mergebasef762949. Предыдущий WIP прототипа сохраняется; чужие otzyv-1/2/3.jpg не трогаем. Allowlist: static/widget/{widget.js,widget.css,fonts.css,icons.js,catalog.js,price_card.js,booking_form.js}; contracts/widget_config.py; clients/{demo,demo_medical,nikadent}/widget_config.json; tests/{test_widget_new_design.py,test_widget_config_contract.py,test_widget_three_tabs_browser.py}; tests/js/widget_new_design_harness.mjs; эта карточка. Вспомогательные локальные результаты проверки в drafts/widget-redesign не входят в коммит.

Сохраняем API/модель/память/SSE/tenant ownership, canonical prices и объём в диалоге, единый приватный черновик и подтверждённую API-отправку. UI: общий набор SVG, компактные темы из финального CSS, групповые меню, карточки списка с ценой снизу, split detail, списки-черточки, минимальная форма без выбора услуги; выбранная услуга и offer остаются контекстом заявки с «Убрать». Никакой fake логики/контента из HTML в runtime.

Baseline offline: 83PASS — config contract, widget catalog, booking form; 872 прежних warnings. Первый запуск не получил доступ к общему pytest tmp; отдельный basetemp внутри drafts устранил проблему без изменения исходников. Проверки после изменения: узкие unit/API/DOM, доступный браузер, ширины320/360/390/412/440 и три цвета, один независимый Checker. Live provider/model/SMTP вызовы не разрешены.

### Итог переноса 2026-10-18

Удалены прежние достижимые стили обновляемых компонентов и последовательные override-слои; сохранены launcher, видео, галерея, rich answers и транспортные состояния. Убраны повторный корневой заголовок каталога, заголовок большой формы и системный select услуг. Старый значок отправки заменён общим SVG-самолётиком. Публичные цены, authored scope, состав/исключения/условия/все этапы оплаты и порядок разделов сохранены.

Добавлены presentation-настройки design (aura/orbit) и iconKey, общий локальный SVG-набор, компактная типографика Inter400/500 и две темы на одной структуре. Цвета из прежних brand.yaml: demo#0C2FE0/Aura, demo_medical#196E76/Orbit, nikadent#762E94/Orbit. Для primary/send вычисляется black/white ink отдельно для обычного/hover brand. В форме «Интересует» можно убрать выбор: selection становится null, контакты/пожелания/consent сохраняются; pending и неопределённый результат защищают неизменяемое тело повторной отправки. Успех показывается только по подтверждению API. Слова «сейчас онлайн» — прежний presentation-статус демо; новая интеграция доступности не вводилась.

Поведение модели, серверная маршрутизация, tenant/price ownership, SSE, память и backend lead не менялись. Существующие volume controls в диалоге остались: одна карточка, три кнопки, опубликованные ref/revision. Это перенос интерфейса и исправление несоответствий макету, не сертификация D2 архитектурного упрощения.

Evidence: 94 уникальных PASS:83 config/catalog/booking API;6 new_design (включая все три цвета,320/360/390/412/440/1280, clear/private draft/immutable retry, current-native volume flows для demo и НикаДент);1 all-price-details (105offers×2contexts);3 three-tabs (каталог, точный offer, чат, форма, remount, root font100/200%);1 no-public-price browser. Последний focused запуск new_design+no_public:7PASS,672 прежних deprecation warnings. Проверены JS syntax и git diff--check. Скриншоты локальных offline fixtures: drafts/widget-redesign/screenshots. Дополнительно CUA: на реальном локальном9001 просмотрены работающий каталог Aura и старт Orbit АртМед, без /ask или отправки формы.

Два старых теста test_d2_price_cards_browser не проходят подготовку API-фикстур до браузера: test_real_card_fonts_selection_and_session_in_browser line216 (HTTP400), test_overview_same_card_navigation_and_unknown_volume_in_browser line270 (нет revision). Оба воспроизведены с тем же результатом на чистом gitarchiveHEAD6674f4a под drafts/widget-redesign/baseline-6674f4a. Это известные baseline failures; их fixtures/backend здесь не изменялись. Действующие volume paths отдельно проверены на текущем native provider contract и канонических HTTP receipts. Изначально новый test предполагал original revision; исправлена именно неверная тестовая гипотеза: существующий renderer использует revision последнего опубликованного overview.

Независимый Checker:PASS; лично35 offline tests, тесты прочитаны первыми, проверены actual presentation/brand/mount, catalog+chat CTA/shared draft/lead и price renderer paths. Замечания о самолётике и контрасте исправлены и перечитаны. Полные browser tests Checker не дублировал. Последний focused review добавленного native-volume evidence фиксируется в ответе.

Live provider/model/SMTP/VPS calls0. Browser/API tests используют подставные provider/delivery/fetch; локальный9001 запущен штатным scripts/start_local_widget.ps1 из этого checkout. Проверка ширин — desktop Chrome, не физические iOS/Android; поведение клавиатуры на реальном телефоне остаётся для owner проверки. Merge/deploy не выполнялись.

Git: codex/three-tabs-catalog, HEAD6674f4a; реализация остаётся в рабочем дереве, индекс пуст, новый commit/push/PR update в этом этапе не выполнялись. Exactallowlist указан выше; предыдущий WIP static/experiments/widget-playground/* сохранён, чужие otzyv-1/2/3.jpg не менялись. Проверочные snapshot/логи/скриншоты находятся в игнорируемом drafts.

Уточнение owner после просмотра: функционал рабочего виджета сохраняем, тестовые сценарии/ответы прототипа не переносим. В обзоре цен диалога убран видимый H3 «Услуги и цены»; названия конкретных услуг/предложений сохранены. Между текстом помощника и следующей ценовой карточкой добавлено16px, чтобы выбор объёма не прижимался к ответу. Это небольшая правка представления: обработчики/ref/revision/суммы не менялись. Прочитан точный diff, JS syntax и diff--check PASS; повторный browser/Checker для косметического уточнения не запускался по verification cadence. Focused Checker добавленного native-volume evidence предыдущего этапа:PASS.


## 2026-10-18 — Контент НикаДент и демонстрационные акции АртМед, owner GO

Классификация: исправление контента и привязок существующего commercial contract, не архитектурное упрощение. Baseline: C:/Cursor Projects/artgents-bot-active, codex/three-tabs-catalog, HEAD6674f4a, origin/main и mergebasef762949. Предыдущий UI/prototype WIP сохраняется; otzyv-1/2/3.jpg — foreign WIP. Клиент demo (стоматологический) вне текущего content scope.

НикаДент: проверить всю имплантацию/протезирование, включая эстетические ортопедические конструкции; распространить существующую бесплатную консультацию, убрать бессодержательное «хирургический этап» из двух package labels; использовать подтверждённые payment_terms.md преимущества (согласованный план/стоимость в договоре, документы для вычета). Подключить все27 активных услуг через существующий D2CommercialPack — это tenant authoring, без нового handler/model/enum/слоя. Технические существенные ограничения объёма и цены сохраняем.

АртМед: заменить три прежних pseudo-promo на три явные демоакции:10% два УЗИ до30.11.2026;15% эпиляция/фотоомоложение до31.12.2026; бесплатная консультация косметолога перед биоревитализацией/ультразвуковым лифтингом до31.12.2026. Шесть из21услуг, без случайного назначения при рендере. Остальные без promo. Цена/состав/исключения/этапы оплаты не меняются. Устаревшие MD/presentation подписи тоже синхронизировать.

Exact allowlist:

- clients/nikadent/target_response/pricebook/facts.json
- clients/nikadent/target_response/d2_commercial.json
- clients/nikadent/target_response/pricebook/services/classic.default.json
- clients/nikadent/target_response/pricebook/services/one_stage.default.json
- clients/demo_medical/target_response/pricebook/facts.json
- clients/demo_medical/md/clinic__info__promotions.md
- clients/demo_medical/widget_config.json
- docs/tasks/THREE_TABS_CATALOG_TASK.md
- clients/demo_medical/target_response/pricebook/services/abdominal_ultrasound.standard.json
- clients/demo_medical/target_response/pricebook/services/abdominal_ultrasound.with_kidneys.json
- clients/demo_medical/target_response/pricebook/services/biorevitalization.face.json
- clients/demo_medical/target_response/pricebook/services/biorevitalization.face_neck.json
- clients/demo_medical/target_response/pricebook/services/botulinum_therapy.individual.json
- clients/demo_medical/target_response/pricebook/services/botulinum_therapy.unit.json
- clients/demo_medical/target_response/pricebook/services/cervical_screening.basic.json
- clients/demo_medical/target_response/pricebook/services/cervical_screening.extended.json
- clients/demo_medical/target_response/pricebook/services/laser_hair_removal.legs.json
- clients/demo_medical/target_response/pricebook/services/laser_hair_removal.three_zones.json
- clients/demo_medical/target_response/pricebook/services/laser_hair_removal.underarms.json
- clients/demo_medical/target_response/pricebook/services/photorejuvenation.face.json
- clients/demo_medical/target_response/pricebook/services/photorejuvenation.face_neck.json
- clients/demo_medical/target_response/pricebook/services/photorejuvenation.hands.json
- clients/demo_medical/target_response/pricebook/services/plasma_therapy.face.json
- clients/demo_medical/target_response/pricebook/services/plasma_therapy.scalp.json
- clients/demo_medical/target_response/pricebook/services/plasma_therapy.three_visits.json
- clients/demo_medical/target_response/pricebook/services/thyroid_ultrasound.standard.json
- clients/demo_medical/target_response/pricebook/services/thyroid_ultrasound.with_cervical_nodes.json
- clients/demo_medical/target_response/pricebook/services/ultrasound_lifting.face350.json
- clients/demo_medical/target_response/pricebook/services/ultrasound_lifting.face_neck500.json
- clients/demo_medical/target_response/pricebook/services/ultrasound_lifting.lower_face.json

Проверки: tenant loaders/commercial/catalog/offline native price; audit canonical каталога до/после для всех26+45offers, сверка неизменности финансовых полей и scope; даты/границы promo; один Checker для нового Nika tenant pack и связей. Live/model/provider/SMTP/VPS0, без merge/deploy. Baseline snapshots/allowlist/evidence в игнорируемом drafts/tenant-marketing-20261018.

Owner steering: имя АртМед → Виктория во widget_config/page greetings и tone.yaml. Для понятных условий НикаДент дополнительно редактируем хвосты labels, не первые scope clauses; fixed_bridge redundant tail уже объяснён в approved price text. Дополнение exact allowlist:

- clients/demo_medical/tone.yaml
- clients/nikadent/target_response/pricebook/services/bone_graft.default.json
- clients/nikadent/target_response/pricebook/services/caries.default.json
- clients/nikadent/target_response/pricebook/services/clasp_dentures.default.json
- clients/nikadent/target_response/pricebook/services/core_inlay.default.json
- clients/nikadent/target_response/pricebook/services/denture_repair.default.json
- clients/nikadent/target_response/pricebook/services/fixed_bridge.default.json
- clients/nikadent/target_response/pricebook/services/implant_supported_prosthetics.crown.json
- clients/nikadent/target_response/pricebook/services/sinus_lift.default.json
- clients/nikadent/target_response/pricebook/services/tooth_extraction.default.json

Исходный test run:49PASS, baseline failure test_d2_commercial_contract::test_tenants_do_not_share_commercial_packages — переименованная fixture копирует widget_catalog с чужим owner; и исходный test_d2_commercial_plan::test_price_profile_freezes_short_promo_and_packages — старый FakeProvider не даёт текущего price block. Оба наблюдались ДО правок коммерческих данных; старые tests/backend не меняем.

Owner steering cosmetic: price-card title18px/margin-bottom10px; bigprice24px. Добавлено в exact allowlist static/widget/widget.css. По изменённому авторскому предложению scope old three-zones→service discount необходимо обновить tests/test_widget_catalog.py: сохранить точные суммы и заменить прежнее offer-only ожидание проверкой всех variants и отрицательной проверкой другой услуги. Итого42paths в allowlist.json. Это обновление проверки изменённого продукта, не ослабление price/tenant scope.

### Результат контентного этапа

АртМед: удалены три прежние псевдоакции и их ссылки из предложений. Добавлены три демонстрационные акции: скидка 10% на УЗИ брюшной полости и щитовидной железы до 30.11.2026; скидка 15% на эпиляцию и фотоомоложение до 31.12.2026; бесплатная консультация косметолога перед биоревитализацией или ультразвуковым лифтингом до 31.12.2026. Они действуют на 6 из 21 услуги, то есть на 15 из 45 предложений. Остальные услуги без акций. MD и welcomePromotion согласованы. Оплата плазмотерапии по выполненным посещениям сохранена как порядок оплаты. Имя Виктория установлено в widget_config, обоих приветствиях страниц и tone.yaml; старого имени в клиентском пакете нет.

НикаДент: существующая бесплатная консультация распространена на 20 услуг имплантации и ортопедии, включая эстетические конструкции, и тему restoration. Она появляется во всех 23 соответствующих ценовых предложениях. Из подписей classic и one_stage убран «хирургический этап». Остальные обрывочные условия переписаны понятными предложениями. Повтор про расчёт моста после осмотра убран из хвоста label, но сохранён в approved_text. Два преимущества взяты из существующего clinic__info__payment_terms.md: стоимость согласованного лечения фиксируем в договоре; подготовим документы об оплате для оформления налогового вычета. Размер возврата в новом коммерческом блоке не обещаем.

Созданы 27 профилей услуг НикаДент; преимущества видны во всех 26 ценовых предложениях. У пяти услуг — pulpitis, periodontitis, ceramic_inlays, tooth_restoration, teeth_cleaning — нет offers/details. Существующий renderer не показывает у них коммерческие аккордеоны. Этот этап не расширял renderer и не создавал вымышленные ценовые предложения.

Дополнительные косметические правки owner: заголовок ценовой карточки 18 px, margin-bottom 10 px; большая цена 24 px. Шапка и заголовок раздела каталога не менялись. Отдельный browser/Checker для этих микроправок не запускался.

Проверки после изменения контента: 145 уникальных PASS — 113 проверок каталога и текущего native D2 до известного старого падения, затем 32 проверки конфигурации и консультации. Предыдущие 49 baseline PASS частично пересекаются и к 145 не прибавляются. Audit в drafts/tenant-marketing-20261018/audit.py прошёл: во всех 71 предложениях сохранены финансовые поля, scope_text, состав, исключения и этапы оплаты. Проверены положительные и отрицательные границы акций, даты до начала и после окончания, отсутствие нескольких акций на одном предложении, старых ссылок и имени. Результат — audit-result.json. GET к работающему локальному серверу 9001 подтвердил имя Виктория, новые акции и преимущества. Запросы /ask и /lead живому серверу не отправлялись.

Известные baseline failures: два старых commercial-теста падали до изменения данных — fixture с чужим owner и FakeProvider без текущего price block. Дополнительно test_core_inlay_known_volume_retains_unit_price_and_crown_exclusion ожидает условие оплаты коронки в condition_texts, хотя оно уже находится в excludes. Первый параметр воспроизвёл тот же FAIL на чистом git archive HEAD 6674f4a. Четыре параметра этого сценария не объявлены успешными. Исключение коронки сохранено, дубли не возвращались; тест и runtime этого сценария не подменялись. Полный CI не запускался.

Независимый Checker: PASS. Изменённый тест прочитан первым; прослежены snapshot → commercial authority → resolver → каталог/диалог → renderer. Checker лично повторил audit без записи файлов и учёл ограничение пяти услуг без ценовых предложений. Это проверка исправления данных и привязок, а не сертификация архитектурного упрощения или качества живой модели. git diff --check прошёл.

Git: codex/three-tabs-catalog, HEAD 6674f4a, origin/main и merge base f762949. Точный allowlist из 42 файлов указан выше и в drafts/tenant-marketing-20261018/allowlist.json. Индекс пуст; commit, push, обновление PR, merge и развёртывание не выполнялись. Прежние правки интерфейса и прототипа, а также чужие otzyv-1/2/3.jpg сохранены. Живые вызовы provider/model/SMTP/VPS: 0. Реализация остаётся в локальном рабочем дереве.

Последующие согласованные правки интерфейса: короткая форма в ленте и каталоге содержит контекст услуги, имя, телефон, согласие и кнопку; заголовок, вводный текст и поле пожеланий оставлены только в полной форме там, где они предусмотрены. Статусы и подпись источника приведены к 14 px и одному цвету с иконками 16×16. В CTA общий белый SVG справа; подарок в приветственной акции выровнен сверху. При открытии формы кнопка запуска удаляется из каталога, а общий renderTrail не создаёт CTA для уже открытой формы, включая галерею. Существующий флаг bookingForm, общий приватный черновик, валидация и отправка сохранены. Три offline Chrome-проверки клиентов прошли: верхней CTA нет, контекст и согласие сохранены, повторная отправка неизменяема даже после открытия другого предложения. Проверка короткой формы и дубликатов выполнена в существующем tests/test_widget_three_tabs_browser.py; ослабления защиты заявки нет. JS syntax и diff --check прошли. Вызовы живой модели и доставки: 0.


## 2026-10-18 — подготовка релиза и VPS, owner GO

Owner явно разрешил commit/push и выгрузку на VPS. Baseline/merge base origin/main f762949, HEAD6674f4a, codex/three-tabs-catalog, Git root C:/Cursor Projects/artgents-bot-active. Классификация: bug fix тестовых fixtures и метаданных; архитектурных изменений D2 нет. Сохраняем принятый приватный booking form; не возвращаем слоты контактов в чат. Тесты переводятся на реальный /lead с согласием, durable receipt, send-once/replay, изоляцией и отказами; негативные проверки ownership/PII/лимитов остаются. Старые release-сценарии читаются и исправляются, не исключаются из selection, CI/protections не меняются. В семь MD АртМед добавляем обязательный subtopic; doc_type FAQ согласуем с существующим именем info.

Exact release allowlist:

- clients/demo/widget_config.json
- clients/demo_medical/md/clinic__info__about.md
- clients/demo_medical/md/clinic__info__faq.md
- clients/demo_medical/md/clinic__info__first_visit.md
- clients/demo_medical/md/clinic__info__payment.md
- clients/demo_medical/md/clinic__info__promotions.md
- clients/demo_medical/md/clinic__info__quality.md
- clients/demo_medical/md/clinic__info__technology.md
- clients/demo_medical/target_response/pricebook/facts.json
- clients/demo_medical/target_response/pricebook/services/abdominal_ultrasound.standard.json
- clients/demo_medical/target_response/pricebook/services/abdominal_ultrasound.with_kidneys.json
- clients/demo_medical/target_response/pricebook/services/biorevitalization.face.json
- clients/demo_medical/target_response/pricebook/services/biorevitalization.face_neck.json
- clients/demo_medical/target_response/pricebook/services/botulinum_therapy.individual.json
- clients/demo_medical/target_response/pricebook/services/botulinum_therapy.unit.json
- clients/demo_medical/target_response/pricebook/services/cervical_screening.basic.json
- clients/demo_medical/target_response/pricebook/services/cervical_screening.extended.json
- clients/demo_medical/target_response/pricebook/services/laser_hair_removal.legs.json
- clients/demo_medical/target_response/pricebook/services/laser_hair_removal.three_zones.json
- clients/demo_medical/target_response/pricebook/services/laser_hair_removal.underarms.json
- clients/demo_medical/target_response/pricebook/services/photorejuvenation.face.json
- clients/demo_medical/target_response/pricebook/services/photorejuvenation.face_neck.json
- clients/demo_medical/target_response/pricebook/services/photorejuvenation.hands.json
- clients/demo_medical/target_response/pricebook/services/plasma_therapy.face.json
- clients/demo_medical/target_response/pricebook/services/plasma_therapy.scalp.json
- clients/demo_medical/target_response/pricebook/services/plasma_therapy.three_visits.json
- clients/demo_medical/target_response/pricebook/services/thyroid_ultrasound.standard.json
- clients/demo_medical/target_response/pricebook/services/thyroid_ultrasound.with_cervical_nodes.json
- clients/demo_medical/target_response/pricebook/services/ultrasound_lifting.face350.json
- clients/demo_medical/target_response/pricebook/services/ultrasound_lifting.face_neck500.json
- clients/demo_medical/target_response/pricebook/services/ultrasound_lifting.lower_face.json
- clients/demo_medical/tone.yaml
- clients/demo_medical/widget_config.json
- clients/nikadent/target_response/d2_commercial.json
- clients/nikadent/target_response/pricebook/facts.json
- clients/nikadent/target_response/pricebook/services/bone_graft.default.json
- clients/nikadent/target_response/pricebook/services/caries.default.json
- clients/nikadent/target_response/pricebook/services/clasp_dentures.default.json
- clients/nikadent/target_response/pricebook/services/classic.default.json
- clients/nikadent/target_response/pricebook/services/core_inlay.default.json
- clients/nikadent/target_response/pricebook/services/denture_repair.default.json
- clients/nikadent/target_response/pricebook/services/fixed_bridge.default.json
- clients/nikadent/target_response/pricebook/services/implant_supported_prosthetics.crown.json
- clients/nikadent/target_response/pricebook/services/one_stage.default.json
- clients/nikadent/target_response/pricebook/services/sinus_lift.default.json
- clients/nikadent/target_response/pricebook/services/tooth_extraction.default.json
- clients/nikadent/widget_config.json
- contracts/widget_config.py
- docs/tasks/THREE_TABS_CATALOG_TASK.md
- static/widget/booking_form.js
- static/widget/catalog.js
- static/widget/fonts.css
- static/widget/icons.js
- static/widget/price_card.js
- static/widget/widget.css
- static/widget/widget.js
- tests/d2_ci_http.py
- tests/js/widget_new_design_harness.mjs
- tests/test_client_usage_limits.py
- tests/test_d2_af1b_contacts_http.py
- tests/test_d2_contact_model_context.py
- tests/test_d2_demo_limits.py
- tests/test_d2_demo_release_gate.py
- tests/test_d2_results_document.py
- tests/test_d2_situation_disabled.py
- tests/test_nikadent_price_authority_offline.py
- tests/test_nikadent_technical_onboarding.py
- tests/test_tenant_lead_routing_context_offline.py
- tests/test_validate_client_pack.py
- tests/test_widget_catalog.py
- tests/test_widget_config_contract.py
- tests/test_widget_new_design.py
- tests/test_widget_three_tabs_browser.py

Прежние WIP static/experiments/widget-playground (8 файлов) и чужие otzyv-1/2/3.jpg сохраняются вне коммита. Релиз только через GitHub CI, immutable image и штатный manual deploy. Проверки локально offline, без живых model/SMTP вызовов; после deploy только read-only health/static/config/catalog GET.

Release checkpoint: независимый Checker PASS по 73 путям. Его37PASS/1FAIL выявили только коллизию тестового имени «Анна» с authored врачом; уникальный маркер сохранён в проверках PII, focused JSON/SSE2PASS. Линтер контента всех pack, pricebook0warnings, validators и синтаксис изменённых Python PASS; staged diff--check чистый. Общий локальный regression run ещё выполняется; исходный pre-fix run остановлен после воспроизведения известных старых failures и не объявляется успешным. Release CI обязан пройти на новом SHA до merge. Live provider/SMTP0. Дальнейшие GitHub/build/deploy evidence фиксируем в PR и ответе, а не объявляем по локальным проверкам.

Release follow-up exact allowlist + tests/js/client_launcher_harness.mjs: offline Windows browser нашёл устаревшие exact visual assertions (старый зелёный dot, удалённая promo-more, прежние promo fills и composer border). Обновляем assertions по согласованному дизайну Aura/Orbit: muted green, brand-derived 9% promo, gift brand и subdued arrow, focus35% brand. Все проверки timer, anchored corner, focus, reduced motion, visualViewport/mobile scroll и отсутствия provider network сохраняются. Runtime не меняется.

Follow-up evidence: локальный focused набор284cases завершился281PASS/3FAIL: два до исправления unique PII sentinel, третий устаревший launcher browser assertion. JSON/SSE sentinel отдельно2PASS; launcher после визуального обновления1PASS (11.46s), включая mobile visualViewport18resize steps/reading positions/reduced motion. Independent focused Checker PASS, тестовые защиты сохранены. Полный releaseCI на edeb031 в GitHub выполняется; зелёный результат пока не заявляется. Дополнительных живых model/SMTP вызовов0.

CI e09b01e: lint/policy/PostgreSQL/secret scan PASS; offline1266PASS/8FAIL/16platform skips. Новые failures — stale promo fixtures, не новый runtime. Дополнение exact allowlist: tests/test_d2_price_variants.py; tests/test_nikadent_client_pack_offline.py. Согласованные новые акции проверяем на полном service scope; offer-only mechanism сохраняем отдельной синтетической fact fixture, не возвращаем удалённые pseudo-promo. Сохраняем негативные ownership/scope/schema/date/inactive guards, добавляем положительные граничные даты. НикаДент allowed_service_ids сверяем с owner-approved20 услугами вместо старого запрета classic/one_stage. Product/runtime/CI selection не меняем.

Promo release recheck:49PASS,2652 прежних datetime warnings,44.89s, без skips/failures. Independent focused Checker PASS: позитивный service-wide scope и отдельный exact-offer negative/positive, schema/date/inactive guards сохранены/расширены. Только tests/card, runtime не менялся. Нужен повторный CI нового SHA; предыдущий красный результат не обходится. Живые provider/SMTP0.


## Локальная админка D2 — owner GO 2026-10-19

Owner запросил простой локальный запуск из widget-test и адаптацию админки к текущему D2, с подготовкой безопасности/кэширования к будущему VPS. Отдельно подтверждены: первая версия только просмотр, без удаления; сбор технических метрик новых обращений без текста и контактов. Merge/deploy/provider/SMTP calls не разрешены.

Класс этапа: исправление и адаптация административного интерфейса. Не заявляет упрощение семантической архитектуры D2. §3 Target Contract сохраняется: админка наблюдает сохранённую публикацию и receipts, не пересчитывает цены/смысл и не меняет память/доставку.

База: C:/Cursor Projects/artgents-bot-active, codex/three-tabs-catalog, HEAD/merge base 80b1df76878529e43995b589dd52005729402fb1, свежий origin/main d9d1f49bb797bde848e848f554e3e2bf4fc7e56d. Продолжение текущей задачи в той же папке; грязный checkout не переключается. Foreign WIP: три widget_config.json, static/widget/widget.css, восемь static/experiments/widget-playground файлов, docs/ARTGENTS_VPS_PRODUCTION_STATE.md, otzyv-1/2/3.jpg — сохранить.

Замена: admin PG bot_events/leads/v5 и старый purge → read-only D2 SQLite с проверкой владельца row/payload, безопасная публичная проекция и typed form receipts. Старые PG queries, RAG metrics, visit reconstruction и mutation routes удалить, без fallback/конвертера в старые turn_complete. Единственный владелец истории/результата — существующий D2 store. Метрики — отдельное техническое наблюдение, не память диалога; ошибки наблюдения не влияют на ответ. Исторически отсутствующие время/расходы не выдаются за нули или восстановленные суммы.

Exact allowlist:
- admin_dashboard/app.py
- admin_dashboard/repository.py (new)
- admin_dashboard/dialog_segments.py (remove)
- admin_dashboard/templates/index.html
- admin_dashboard/static/dashboard.js
- admin_dashboard/static/dashboard.css
- core/d2_storage.py (new)
- core/d2_publication.py (new)
- core/d2_admin_metrics.py (new)
- core/d2_http_adapter.py
- core/d2_diagnostics.py
- core/d2_booking_form.py
- core/widget_session.py
- scripts/start_local_admin.ps1 (new)
- static/widget-test.html
- static/widget-test-panel.js
- clients/demo/features.yaml
- clients/demo_medical/features.yaml
- clients/nikadent/features.yaml
- deploy/production/compose.yml
- docs/DASHBOARD.md
- docs/tasks/THREE_TABS_CATALOG_TASK.md
- tests/test_admin_dashboard_schema_health_offline.py
- tests/test_admin_dashboard_tenant_offline.py
- tests/test_dialog_segments.py (remove)
- tests/test_migrations_postgresql_static.py (removed admin PG dependency assertion only)
- tests/test_d2_admin_dashboard.py (new)
- tests/test_d2_admin_metrics.py (new)

Проверки: targeted offline API/store/tenant/privacy/read-only/auth/no-store/pagination/adverse-output и метрики fake-provider без лишних вызовов; действующие D2 HTTP/история/форма/диагностика regressions; синтаксис launcher/JS; локальное открытие UI без model/SMTP; независимый Checker завершённого этапа. Никаких автоматических запросов к модели, писем или live admin mutations.

Allowlist clarification before staging: deploy/production/README.md and tests/test_t6b_pass3_production_deploy_offline.py — admin loses unused PG credentials/network/migration dependency; retain bot migration guard and assert exact read-only D2 volume + private admin access instead.

### Evidence локального этапа админки

Удалены старые PG/RAG queries, реконструкция визитов, dialog_segments и пути удаления. Добавлены read-only D2 reader, общий путь store и публичная проекция сохранённого результата, новый технический ledger, локальный launcher и вход из панели widget-test. Доставка, replay, цена, модельные решения и D2 context ownership не менялись; новый наблюдатель не создаёт вызовов модели и закрывает SQLite соединение после каждой записи.

Offline regression: 179 PASS / 11 FAIL / 1 SKIP. Все 11 FAIL находятся в неизменённом test_d2_diagnostics.py и воспроизведены на отдельном чистом git archive baseline 80b1df7: 29 PASS / те же 11 FAIL. Причины — прежние ожидания старого envelope/request_understanding и старого error reason; они не объявлены исправленными этим этапом. Docker compose config пропущен из-за отсутствия Docker CLI. После исправления закрытия соединений focused metrics + real-adapter admin tests: 16 PASS. Первый admin/schema/tenant/metrics/period набор: 39 PASS; последний regression включает добавленный adapter usage/replay/failure case.

Python AST, JS syntax (admin + module widget-test), PowerShell parser, YAML/private mount assertions и diff --check прошли. В реальном локальном браузере проверены три клиента, сброс истории при смене клиента, чтение сохранённых ходов и статуса отправленной заявки без полей контактов. Админка запущена на 127.0.0.1:9100 через новый launcher, без debugger/reloader; бот на 9001 запускается отдельно. Скриншот результата сохранён в локальном visualization workspace. Живых model/SMTP calls: 0. VPS не изменялся; GitHub CI, deployment и deployed dialogue этой проверкой не подтверждаются.

Ветка codex/three-tabs-catalog, HEAD остаётся 80b1df76878529e43995b589dd52005729402fb1. Изменения не staged, новый commit/push/PR этого этапа не создавались. Foreign WIP из preflight сохранён вне scope. Ограничения: старые расходы неизвестны; оценка новых расходов требует usage и настроенных ставок; полная анонимизация свободного текста и retention/удаление самой D2 истории не заявляются. Перед VPS остаются release CI, отдельный owner deploy GO и проверка приватного входа/read-only mount на точном image.

Независимый Checker: PASS; лично 37 основных проверок, 1 дополнительная проверка закрытия соединения и UTC period bounds PASS. Неблокирующее замечание про health при неверных колонках исправлено: reader проверяет требуемые колонки фиксированных таблиц read-only PRAGMA; optional observation остаётся необязательной. Focused recheck Checker 3 PASS, замечание закрыто. Executor schema + admin integration после этой правки 14 PASS. Админка перезапущена с финальным кодом; проверки касались только локального GET, без запросов к модели/отправки заявок.

### Cache-aware расходы — owner GO 2026-10-19

Owner подтвердил учёт фактических входящих токенов с/без кэша и исходящих, затем вычисление оценки. Класс: bug fix расчёта административных метрик, не семантическое упрощение D2. Продолжаем тот же checkout/branch/baseline 80b1df7; свежий origin/main d9d1f49. Индекс пуст. Весь предыдущий admin WIP и foreign WIP из preflight сохраняется; QUICK_COMMANDS.html также вне изменений этапа. Provider/SMTP/deploy не разрешены.

Exact allowlist этапа: core/d2_admin_metrics.py; core/d2_costing.py (new); admin_dashboard/repository.py; admin_dashboard/static/dashboard.js; admin_dashboard/templates/index.html; deploy/production/compose.yml; docs/DASHBOARD.md; docs/tasks/THREE_TABS_CATALOG_TASK.md; tests/test_d2_admin_metrics.py; tests/test_d2_admin_dashboard.py; tests/test_d2_costing.py (new). Nullable расширение только technical observation table делает её единственный bot-writer; admin остаётся read-only и показывает прежние записи как прежнюю неполную оценку, не переписывая их. Canonical D2 state/replay/lead tables не мигрируются.

Источник объёмов — provider usage: native DeepSeek hit/miss либо standard prompt_tokens_details.cached_tokens; проверка арифметической согласованности. Отсутствующая/некорректная разбивка не считается нулевым кэшем. Тарифный snapshot и время начала вызова сохраняются вместе с суммой, текущие тарифы не пересчитывают прошлые суммы. Для direct api.deepseek.com/deepseek-flash используется опубликованный rate card 2026-10-19 и UTC weekday peak schedule; календарь китайских праздников не автоматизируется, поэтому сумма остаётся оценкой. Для прочих endpoints/models — явно настроенные ставки, без подстановки тарифа DeepSeek. Учитываются только наблюдаемые transport invocations, не скрытые SDK retries. Ошибка учёта не меняет диалог/ценовые карточки/квоты/доставку.

Проверки: targeted offline token accounting, malformed usage, rate boundaries, saved snapshot, old telemetry, tenant/read-only/replay/no extra model calls; синтаксис JS; один независимый Checker. Живые model/SMTP вызовы — 0.

Результат этапа: удалена функция _estimate с умножением всего prompt на одну ставку. Единственный владелец арифметики/тарифного snapshot — core/d2_costing.py; provider_finished сохраняет actual usage и snapshot в d2_admin_observation. Добавлены семь nullable technical колонок, атомарное дополнение только writer-ом и read-only чтение прежних строк без DDL. В API/UI отдельные объёмы cache/miss/output, число неполных вызовов и отдельная сумма прежних оценок. Смысл диалогов, цена услуг, контекст, replay, admission и отправка заявок не менялись. Заявляется bug fix учёта, не архитектурное упрощение D2.

Offline: 120 PASS / 1 SKIP (Docker CLI отсутствует) за13.62s: costing, metrics, real-adapter admin, schema/tenant, period и deployment static contracts. Независимый Checker PASS, лично50PASS, включая SDK usage, tariff boundaries, snapshot/legacy integrations. Python AST, JS syntax, diff--check PASS. Прежние11 diagnostics failures из предыдущего baseline-аудита не исправлялись и в текущий целевой набор не включены; общий release CI не запускался.

Локальная админка перезапущена с финальным кодом; GET /api/health200 и все3storesready, /api/costs?client_id=nikadent200 с честным available:false (пока нет новых реальных наблюдений). Новые объёмы проверены fake transport через actual D2 endpoint, не живым провайдером. Реальных model/SMTP вызовов0; VPS не изменялся. После новых обращений нажать «Обновить» в админке; для загрузки кода бота нужен его перезапуск/штатный dev reloader.

HEAD80b1df7, веткаcodex/three-tabs-catalog, новых commit/push/PR/deploy этого этапа нет, индекс пуст. Изменены только перечисленные stage paths; чужой/предыдущий WIP сохранён. Остаточные ограничения: оценка по тарифному snapshot, без автоматического CN holiday calendar и сверки со счётом/неотданными SDK usage; прошлый неизвестный кэш не восстанавливается. На VPS эта версия не проверена/не развёрнута.

### Подготовка доступа/готовности VPS admin — owner запрос2026-10-19

Owner просит полностью разобраться с выкладкой, текущим входом/доменом, запуском и тем, что от него требуется. Merge/deploy/VPS mutations не разрешены. Подтвердил, что помнит admin login/password. Класс этапа: операционные помощники и инструкция, без изменения runtime бота/админки и без семантического упрощения D2.

Baseline: тот же C:/Cursor Projects/artgents-bot-active/Git root, codex/three-tabs-catalog, HEAD/merge-base80b1df7, origin/main d9d1f49, индекс пуст. Весь предыдущий admin/cache/UI WIP, QUICK_COMMANDS и исходные foreign WIP сохраняются. Exact allowlist: scripts/start_vps_admin.ps1 (new), scripts/audit_vps_admin.ps1 (new), tests/test_vps_admin_helpers_offline.py (new), docs/DASHBOARD.md, docs/QUICK_COMMANDS.html, docs/tasks/THREE_TABS_CATALOG_TASK.md.

Read-only live evidence: SSHdeploy с существующим owner key проходит; server ss показывает127.0.0.1:9100, без credentials HTTP401. sudo -n требует интерактивный пароль, Docker/env/root metadata не получены и не объявляются проверенными. Старый handoff dated2026-10-15 не используется как доказательство текущего SHA. Локальный helper создаёт только private SSH forwarding127.0.0.1:19100→VPS127.0.0.1:9100; второй helper после пользовательского sudo выполняет только allowlisted metadata reads, не печатает inspected Env/токены/хеши/пароли/разговоры и не пишет файлы на VPS. StrictHostKeyChecking/ExitOnForwardFailure обязательны, занятый локальный порт не освобождается автоматически.

Deployment readiness gap: existing backup-postgres не сохраняет current D2 SQLite. До отдельного deploy GO нужны root inventory, согласованный SQLite backup/restore и release CI+immutable image. Никакого скрытого install/backup/deploy/helper replacement на VPS не выполняется. Проверки: офлайн sanitized-output/adversarial Docker metadata и ambiguous services, PowerShell parser; фактический loopback tunnel/HTTP401 без логина; один independent Checker для transport/security помощников. Live model/SMTP0.

Evidence: 7 offline tests PASS, PowerShell AST обоих scripts PASS, HTML8copy controls/unique references PASS, diff--check PASS. Independent Checker PASS; focused recheck передачи generated Base64 отдельным sys.argv[1] PASS. Реальный локальный helper создал SSH-туннель127.0.0.1:19100→VPS127.0.0.1:9100, через него HTTP401 с BasicAuth challenge. Туннель оставлен для owner browser login; это текущая серверная версия. Privileged audit не выполнялся: пользователь должен локально ввести sudo-пароль в script8, его вывод без секретов позволит завершить inventory. В этой части server readiness остаётся непроверенной, а не объявленной готовой.

Веткаcodex/three-tabs-catalog, HEAD80b1df7, индекс пуст, commit/push/PR/merge/deploy не выполнялись. Изменены только6paths allowlist; старый WIP сохранён. Действия на VPS — только SSH/read-only listener+HTTP checks и forwarding, без записи/перезапуска. Модель/SMTP0. Полная инструкция в docs/DASHBOARD.md, копируемые команды7/8 и ссылка на19100 в docs/QUICK_COMMANDS.html. Оставшиеся необходимые шаги: root read-only inventory с owner terminal password, SQLite backup/restore, releaseCI+immutableimage, отдельный owner GO на merge/deploy, postdeploy authorization/data/metrics checks.

Owner выполнил root read-only helper и предоставил вывод2026-10-19T14:55:26UTC: bot/admin healthy наd9d1f49, bot RWvolume/app/data+deepseek-flash; admin production/tokenpresent, ноmounts[]/allowedclients[]/PGcredentialspresent — старый adminконтур. Caddy9100loopback+HTTP401, credentials присутствуют; production.envroot0600, deploy/PGbackuphelpersroot0750, известныйbackup-sqlitehelperabsent. Это закрывает metadata inventory gap, не доказывает SQLite backup, наличие нового collector-а, успешный browserlogin или совпадение внутреннихтокенов. Caddyhealthnot_configured/vendorSHAunknown не объявляются аварией. Инструкция обновлена только по предоставленному выводу; новые SSH/root/provider/SMTP/mutation вызовы0. Локальная Compose уже содержит замену adminmount/registry/PGsettings. Перед deploy сохраняются SQLitebackup/restore+releaseCI/image+ownerGO и postdeployauth/data проверки. Для этой фиксации изменены только docs/DASHBOARD.md и существующий taskcard; контент/diff прочитан, новые тесты для prose не запускались.

Позднейшее owner уточнение2026-10-19 имеет приоритет над прежним backup readiness gap: текущие данные только тестовые/фейковые, реальных заявок и метрик нет, сохранять их перед первой выкладкой админки не требуется. SQLite backup/restore больше не блокирует этот релиз; отдельный helper/автоматизация бэкапов сейчас вне scope. Удаление/reset/migration данных не поручены. Существующий PostgreSQL backup gate, CI/immutable image и отдельная authority на merge/deploy сохраняются. Будущая аналитика страниц/воронки обсуждается как возможность, не как owner GO на новые события/поля/трекеры; runtime не менялся. Обновлены только текущие положения docs/DASHBOARD.md и эта запись, прежний WIP сохранён; prose прочитан, тесты/Checker/SSH/provider/SMTP/deploy для микроуточнения не запускались.

### Аналитика страниц/воронки — owner GO 2026-10-19

Owner просит первое полезное расширение аналитики прямо сейчас: страницы открытия виджета и путь к заявке. UTM/внешняя Метрика не нужны. Класс этапа: новое техническое наблюдение и административный отчёт; не семантическое упрощение D2. Таблица ответственности Target Contract §3 сохраняется: технические события не участвуют в диалоге, цены/память/квоты/доставка не меняются. Astra boundary review: отдельный sidecar допустим; доставка только canonical receipt; distinct submit requests нельзя терять при повторной попытке.

Preflight: C:/Cursor Projects/artgents-bot-active = Git root; codex/three-tabs-catalog; HEAD/merge-base80b1df76878529e43995b589dd52005729402fb1; свежий origin/main d9d1f49bb797bde848e848f554e3e2bf4fc7e56d. Продолжение текущего admin stage в dirty checkout, без переключения/сброса. Индекс пуст. Все прежние admin/cache/helpers/client/CSS/playground WIP и foreign VPS doc/jpg сохраняются.

Exact allowlist: app.py; core/widget_analytics.py (new); core/widget_cors.py; static/widget/analytics.js (new); static/widget/widget.js; static/widget/booking_form.js; admin_dashboard/app.py; admin_dashboard/repository.py; admin_dashboard/static/dashboard.js; admin_dashboard/templates/index.html; tests/test_widget_analytics.py (new); tests/js/widget_analytics_test.mjs (new); docs/DASHBOARD.md; docs/tasks/THREE_TABS_CATALOG_TASK.md. Никаких других изменений/стадирования этого этапа.

События: открытие, отправка вопроса браузером, показ формы, попытка отправить валидную форму. Одно in-memory view UUID на mount, без нового persistent visitor ID и без хранения сообщений/контактов/query/UTM. Путь только из server pageMenus или /, прочие сгруппированы (other); домен только matched allowed Origin/Referer. Не уникальные люди/не показы страницы/не строго последовательная воронка. Счётчик — distinct view на действие/статус; разные попытки формы сохраняются, retry одного request дедуплицируется. Принятая заявка и sent/demo/unknown/failed/pending — только tenant-validated canonical BookingFormReceipt; в sidecar доставки нет. SHA256 случайных UUID совместим с существующей read-only admin identity, не идентификатор человека и не ключ D2.

Sidecar widget_analytics.sqlite рядом с canonical store, единственный writer bot endpoint; не создаёт/мигрирует canonical DB. Admin оба источника читает mode=ro/query_only. Собственный endpoint bounded2048bytes, tenant+matched origin, rate120/min/client+peer с bounded4096 in-memory buckets, retention30days, server time. Наблюдение best effort без повторов/влияния на ask/form; выключается существующим D2_ADMIN_METRICS_ENABLED=0. До50000event rows за отчёт, явное предупреждение о неполном результате при превышении. Исторические данные не восстанавливаем; новые события только после загрузки обновлённого widget. Офлайн тесты endpoint/privacy/tenant/CORS/dedup/retention/busy-storage/read-only/canonical receipts и actual JS observer/form handler; один independent Checker. Live provider/SMTP/VPS mutations не разрешены.

Allowlist дополнен .gitignore: исключить новый runtime sidecar widget_analytics.sqlite и SQLite journal-файлы из Git, чтобы не допустить случайного коммита технической базы. Это не удаление/миграция данных и не изменение иных ignore-правил.

Evidence этапа аналитики: добавлены независимый от D2 semantics best-effort collector/sidecar, четыре события действий и read-only отчёт по клинике/домену/публичной странице. Старых смысловых decision paths не заменяли и не заявляем simplification; добавлены только согласованные технические точки наблюдения. Состояние/история диалога, выбор услуг/цен, квоты, replay и транспорт доставки не менялись. Серверный receipt остаётся единственным источником статуса заявки. Неизвестный путь теперь заменяется на (other) ещё в браузере перед HTTP, затем проверяется server allowlist; приватные сегменты URL не отправляются в analytics. Typed client_id guard до tenant resolver закрывает malformed {} / null без500.

Expanded targeted offline:110PASS/1FAIL за55.93s (analytics, admin, metrics, tenant/schema, booking, session, page menus). Единственный FAIL — неизменённый real browser harness не подключился по CDP: Network.enable timeout ДО выполнения widget. Это не объявляется ни доказанным baseline failure, ни runtime regression; отдельное baseline browser сравнение не выполняли. После узкого hardening analytics suite23PASS/8.69s; затем актуальный Node observer+real booking handler с private pathname и hidden form assertions PASS. JSsyntax admin/analytics/booking/widget и diff--check PASS. Ранее установленные11старых diagnostics baseline failures остаются вне этапа и не исправлялись. Общий release CI не запускался.

Independent Checker PASS: лично21новый тест до двух дополнительных malformed-client cases, затем focused closed_event_input11PASS; проверил actual endpoint/hooks/sidecar→canonical receipt→admin call path, tenant/privacy/auth/read-only/fail-safe. Никаких live provider/SMTP вызовов или VPS действий. Локальная админка перезапущена на127.0.0.1:9100, GETстраницы200 с блокомfunnel; /api/funnel всех3клиник200 available:false/items[] — пока нет новых реальных событий, фиктивные счётчики не добавлялись. Локальный бот9001 загрузил новый POSTroute (GET405). Это HTTP/offline evidence, не визуальная проверка всего браузера, не deployed dialogue.

Веткаcodex/three-tabs-catalog, HEAD80b1df76878529e43995b589dd52005729402fb1. Новогоcommit/push/PR/merge/deploy нет, индекс пуст. Все изменения только в exactallowlist с отдельно объяснённым .gitignore; остальной предыдущий/foreignWIP сохранён. На VPS ничего не выкладывали согласно повторному owner запрету. Ограничения: новые наблюдения только после обновления widget, возможные потери browser/network событий, knownpublicroutes/(other), counts по загрузкам widget вместо людей, server statuses не означают прочтение письма, 30дней retention и явный лимит50000events/report. UTM/внешняяМетрика/рекламнаяатрибуция/автоматическиебэкапы в этот этап не добавлялись.

### Каталог → вопрос ИИ-помощнику — owner GO 2026-10-19

Owner одобрил вторичное действие «Задать вопрос об услуге» после ценовой карточки: переключить на первую вкладку, подготовить «По услуге «Название»: », пользователь дописывает/отправляет сам. Первая вкладка у всех клиентов — «ИИ-помощник». Уточнил обязательную проверку: все три названия в одну строку на минимальных телефонах, начиная с320px; сохранить шрифты, при необходимости уменьшить gap/padding. Для черновика owner спросил совет; исполнитель предложил и применяет сохранение набранного текста: непустой пользовательский черновик не менять, только открыть помощник. Нетронутую служебную заготовку можно заменить заготовкой другой услуги.

Класс этапа — frontend feature, не архитектурное упрощение D2. Данные услуги берутся из уже загруженного канонического каталога как обычный текст поля ввода; нет скрытой отправки, новых полей ask, model calls, server context, memory, выбора темы/услуги за модель, ценового/lead изменения. Ответственность Target Contract§3 сохраняется. Каталог не перемонтируется при переходе, existing switchTab сохраняет scroll state. После открытия формы ссылку убрать вместе с верхним CTA по ранее утверждённому принципу.

Baseline: C:/Cursor Projects/artgents-bot-active=Gitroot; codex/three-tabs-catalog; HEAD/mergebase80b1df76878529e43995b589dd52005729402fb1; origin/main d9d1f49bb797bde848e848f554e3e2bf4fc7e56d. Индекс пуст, dirty checkout продолжает текущую owner-задачу. Все прежние admin/analytics/helper/client/playground/CSS WIP и foreignVPSdoc/jpg сохраняются. Exactallowlist: static/widget/catalog.js; static/widget/widget.js; static/widget/widget.css; tests/test_widget_catalog_question.py(new); tests/js/widget_catalog_question_test.mjs(new); docs/tasks/THREE_TABS_CATALOG_TASK.md. Для UIverification допустим временный static/debug/widget-catalog-check.html (после проверки удалить только этот созданный файл, не включать вrelease). Тесты: actualcatalog/realcomposer callback/switchTab offline; CUA UI320/360/390/440 обе темы, catalogstate/draft/noautoask/formlinkhiding. Один independent Checker из-за cross-module UI callback. Provider/SMTP/VPScalls0; deploy прямо запрещёнowner.

Evidence каталога→composer: добавлен необязательный onAsk callback к существующему mountCatalog; служебная ссылка под основным CTA передаёт только опубликованное service.name в обычный textarea. OpenCatalogQuestion переключает existing switchTab, при пустом поле готовит текст, сохраняет пользовательский черновик, заменяет только собственную нетронутую заготовку, пересчитывает высоту/состояние кнопки, ставит фокус и курсор в конец. Не вызывает отправку/модель, не меняет историю/серверный context и не создаёт второй semantic owner. При открытии короткой формы оба catalog actions удаляются, ниже формы ссылок нет. Каталог сохраняет DOM/навигацию/scroll через прежний switchTab. Новое имя первой вкладки и aria-label панели — ИИ-помощник во всех клиентах.

Новых compact typography override не понадобилось: существующие nowrap/flex/min-width и containerpadding/gap уже вмещают названия. Реальный CUA iframe320px: Demo, ArtMed, НикаДент × Aura/Orbit всеPASS, DOM Range высота1строка, textfits/tabbounds insidepanel. Дополнительно360/390/440px обе темы на ArtMed PASS. Это реальные CSSmedia/container queries внутриiframe с viewport заданнойширины, не уменьшенный скриншот desktop; реальная клавиатура физического Android/iOS не проверена. Настоящий CUA click по карточке ArtMed→question подтвердил выбранную первуювкладку и textarea prefix при всё ещё welcome feed (нет autosend), typingdraft→catalog→question сохраняет текст, catalog return содержит тужеценовуюкарточку, CTA открывает короткуюформу без исходныхдвухactions. Screenshot saved C:/Users/denis/.codex/visualizations/2026/10/16/01a1450e-6723-7531-923b-fc8110b307c2/catalog-question-320.png. Проверочный iframe перехватывал ask/lead с запретом вызова, widget-events глушил204 чтобы не засорять реальные счётчики; были только local GETconfiguration/catalog/booking/history. Временная собственная static/debug/widget-catalog-check.html удалена, её вкладка закрыта; пользовательские вкладки/черновики не изменены.

77targetedofflinePASS/32.37s: новый actualJS catalog+composer/switchTab тест, текущие catalog/bookingform/analytics regressions. NodeJS syntaxcatalog/widget и scoped diff--check PASS. Независимый Checker PASS, лично1новый runtimeUItest; actualcallerpath и связь с existingtab/booking просмотрены read-only, scopefrontendfeature (не архитектурноеупрощение). Прежний diagnosticsbaseline11FAIL и CDPsetup timeout предыдущегоэтапа не исправлялись/вэтотнаборневключены. Общий releaseCI не запускался. Liveprovider/SMTPcalls0, VPSrequests/mutations0.

Branchcodex/three-tabs-catalog, HEAD80b1df76878529e43995b589dd52005729402fb1, origin/main d9d1f49. Changedstagefiles static/widget/catalog.js, widget.js, widget.css, tests/test_widget_catalog_question.py(new), tests/js/widget_catalog_question_test.mjs(new), текущий taskcard. Предыдущий CSS12px для submit/admin/analytics/client/playground/helpers и прочий foreignWIP сохранён. Индекс пуст, commit/push/PR/merge/deploy не делали. После обновления страницы widget доступен локально; VPS остаётся без этих изменений по прямому запрету владельца.

### Release — owner GO2026-10-19: проверка → commit/push → merge/deploy

Owner после ручной проверки интерфейса прямо разрешил короткую проверку и при успешном результате commit, push и выкладку. Этот GO отменяет прежний запрет выкладки для согласованных изменений текущего этапа. Следуем штатному PR→CI→main→immutableimage→manualDeployproduction, без ручного копирования runtime или обнуления данных. Live model/SMTP тесты этим GO не поручены: бюджет0, postdeploy только health/config/static/auth/metadata read-only.

Preflight C:/Cursor Projects/artgents-bot-active=Gitroot; codex/three-tabs-catalog; HEAD/mergebase80b1df76878529e43995b589dd52005729402fb1; послеfetchorigin/main d9d1f49bb797bde848e848f554e3e2bf4fc7e56d. HEAD и origin/main имеют одинаковые tracked trees, отличаются только уже mergedPR34 commit. Продолжаем текущую задачу, не переключаем dirtycheckout. Индекс пуст. Release включает одобренные admin/technicalmetrics/funnel/UX/content/helpers, все прежние stage CheckerPASS сохраняются. Playgrounds8files, userVPSdoc и3jpg остаются foreignWIP и вreleaseнепопадают. Runtime/.env/databases/logs/credentials вGitнепопадают. Классreleaseintegration и testcoverage, не семантическоеупрощениеD2.

Allowlist фиксируется списком54путей в staging manifest исполнителя: .gitignore; все текущие изменения admin_dashboard(app.py,dialog_segments.py deletion,repository.py,static/dashboard.css/js/logo.svg,templates/index.html); app.py; clients/{demo,demo_medical,nikadent}/{features.yaml,widget_config.json}; core/{d2_booking_form.py,d2_diagnostics.py,d2_http_adapter.py,d2_admin_metrics.py,d2_costing.py,d2_publication.py,d2_storage.py,widget_analytics.py,widget_cors.py,widget_session.py}; deploy/production/{README.md,compose.yml}; docs/{DASHBOARD.md,QUICK_COMMANDS.html,tasks/THREE_TABS_CATALOG_TASK.md}; scripts/{audit_vps_admin.ps1,start_local_admin.ps1,start_vps_admin.ps1}; static/{widget-test-panel.js,widget-test.html,widget/booking_form.js,widget/catalog.js,widget/widget.css,widget/widget.js,widget/analytics.js}; tests/{test_admin_dashboard_schema_health_offline.py,test_admin_dashboard_tenant_offline.py,test_dialog_segments.py deletion,test_migrations_postgresql_static.py,test_t6b_pass3_production_deploy_offline.py,test_d2_admin_dashboard.py,test_d2_admin_metrics.py,test_d2_costing.py,test_vps_admin_helpers_offline.py,test_widget_analytics.py,test_widget_catalog_question.py,js/widget_analytics_test.mjs,js/widget_catalog_question_test.mjs,release/offline.txt}.

Release-only уточнение beforestaging: шесть новых offline testfiles добавлены в общий tests/release/offline.txt, чтобы PRиpublish оба запускали новую админку/кэш/воронку/UX/helperпроверки. Это расширениепокрытия, прежние проверки не удаляются/ослабляются; CI/workflows/runtimeнеизменены. Deployment README исправляет устаревшуюстроку adminPGcredentials по текущейCompose и отличает technicalSQLiteDDL от запрещённого applicationPostgreSQLDDL. Старый diagnostics11FAIL и browserCDPsetupнеобъявляются новыми регрессиями, releaseверифицирует штатный CIнаLinuxдоmerge.

Release precommit evidence:168PASS/1SKIP (локальный DockerCLI отсутствует) за19.85s; lintcontent all3packsOK, pricebook0warnings, validated demo/templateOK. Независимый focusedreleaseCheckerPASS, лично80PASS release/sharedselection/Compose/immutableimagecontracts, нового runtimefindingнет. Стадированы ровно54allowlistedpaths, cachednames/stat/diff/check просмотрены; foreign8playground+VPSdoc+3jpg внеиндекса. CIнаGitHubдоmerge и postdeployimmutableSHA/health ещё обязательны, локальныеchecksихнезаменяют. Provider/SMTP0; новыхVPSдействийпока0. Owner GOнаmerge/deploy получен в текущем сообщении, повторного подтверждения не требуется.

2026-10-20 release continuation: GitHub CI39282094405 завершился1387PASS/16SKIP/1FAIL: единственный test_nikadent_presentation_valid_v1 всё ещё ожидал прежнее приветствие, тогда как owner прямо утвердил новый текст в widget_config.json. Исправлено только строгое ожидаемое значение теста, без изменения runtime/validator/защит и без удаления assert. BaselineHEAD5b0836c, origin/main/mergebased9d1f49; exactallowlist tests/test_widget_config_contract.py + эта карточка; прежний foreignWIP сохранён. Focused30PASS/4.95s. Повторный Checker для чистой актуализации текстового ожидания не требуется по cadenceAGENTS; существующий releaseCheckerPASS сохраняется, полный CI повторится наGitHub. Новыхprovider/SMTP/VPSвызовов0; новыйimage/deployдоgreenCIнеобъявляютсявыполненными.
