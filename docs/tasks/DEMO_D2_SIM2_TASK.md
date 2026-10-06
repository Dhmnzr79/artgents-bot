# SIM-2 — проект сокращённого контракта и границы с SIM-1/3

Статус: **SIM-1/2 закрыты владельцем 2026-10-02 в согласованном объёме;
SIM-0 и SIM-3–5/REC-5 остаются открытыми**.
Дата: 2026-10-01. Тип текущего изменения — архитектурное упрощение и отдельные исправления ошибок.
Основание: владелец согласовал совместное проектирование, D2-111 и подготовку
технической схемы. Единственная таблица ответственности —
[Target Contract §3](DEMO_D2_TARGET_CONTRACT.md); порядок —
[Roadmap](DEMO_D2_DELIVERY_ROADMAP.md).

## 1. Baseline и границы документального checkpoint

### Закрытие SIM-1/2 и публикация checkpoint, 2026-10-02

Owner «Давай, потом комит и пуш» согласовал учёт известного незелёного CI
как отдельного долга и commit/push проверенного checkpoint. SIM-1/2 закрываются
по заявленным удалениям повторных решений и затронутым диалогам: актуальный
Cursor PASS142/202.88s, independent Checker, widget3 и live4/4 PASS.
SIM-3 completion history, SIM-4 финансовый контроль, SIM-0 обзор, SIM-5/REC-5
не объявляются выполненными. Общая надёжность модели этим не доказана.

CI-долг: offline49 файлов672 PASS/149 FAIL/5 skipped; clean HEAD имеет те же
количества,148 совпавших node IDs. Различия local dotenv и archive Git mode
ограничивают сравнение; весь CI не зелёный. До merge нужен актуальный CI gate:
устаревшие тестовые consumers разобрать по требованиям, не возвращать старый
runtime и не ослаблять assertions. Приёмка этого долга не разрешает merge.

Baseline до публикации: root C:\Cursor Projects\artgents-bot-active,
branchcodex/d2-stage1-contract, HEAD4d240430c2ce056dc306c50e215dbb09843c6b8f,
origin/main и merge-base141ce91fb1731cd990fcf8391550150016c73e7f, staging пуст.
Точный commit scope — накопленный allowlist SIM-1/2 и последующих узких
checkpoint выше/ниже (38 изменённых/новых файлов); foreign data/,
docs/MARKETING_ANSWER_SCENARIOS.md и отдельный SIM0 Task исключены.
Для закрытия документации изменяются только SIM1/SIM2 Task, Current Status,
Roadmap и Ledger. Код и тесты после актуального review/live не меняются.
Новых provider calls0; прошлый live бюджет4/4 исчерпан. Staged diff проверяется
до commit; SHA и remote publication подтверждаются отдельным Git-отчётом.

Все незакрытые статусы и запреты commit/push ниже — исторические snapshots,
заменённые этим решением. Новые live, merge/deploy и очистка не разрешены.

### Live-критерий готового объяснения, 2026-10-02

Owner «Делай» разрешил ровно предложенный максимум4 provider attempts,
без повторов, остановка при первой ошибке. SDK max_retries=0 и общий hard
budget4 включены в отдельном временном стенде. Два новых SID через реальные
Flask /ask JSON и /ask/stream SSE, копии clients/баз/логов; сервер9001 и
foreign WIP не менялись. Runtime-правок нет, только отчёт в этой карточке,
Current Status и Ledger (узкий allowlist). Baseline/ветка прежние, staging пуст.

PASS: свежий вопрос о сроках classic one_tooth и продолжение после fear →
price → volume one_tooth дали готовые объяснения20–30 минут и3–6 месяцев
из текущего корпуса. Price/topic сохранился; клик0calls. Все5 ходов200,
provider4/4, retries0, lead_effect not_requested,SMTP0. Бюджет исчерпан.
Фактические ответы/JSON и временный evidence — верх Ledger. Это два диалога,
не доказательство качества всех запросов, полного CI или SIM-3/4.
Условие живого объяснения выполнено; перед закрытием SIM-1/2 остаётся решение
владельца об учёте известного незелёного CI. Commit/push/merge/deploy не разрешены.

### Актуальная приёмка Cursor и синхронизация документов, 2026-10-02

Владелец передал Cursor PASS актуальному незакоммиченному SIM-1/2:
142 PASS,202.88s,exit0 в test_d2_sim2_contract.py,
test_d2_sim2_dialogues.py,test_d2_ui_b12_scenarios.py,
test_d2_continuation_scenarios.py. Codex этот запуск не повторял.
Предоставленный review подтверждает реальные call paths и удаление повторных
решений, не живое понимание модели и не полный CI. SIM-1/2 ещё не закрыты:
остаются живой критерий объяснения из корпуса и решение владельца об учёте
известного незелёного CI. Commit/push/live/merge/deploy review не разрешает.

Owner «Ок» разрешил синхронизацию статуса и исторических записей. Тип —
документация только. Baseline4d24043, branchcodex/d2-stage1-contract,
origin/main и merge-base141ce91, прежний own WIP сохранён, staging пуст.
Allowlist: docs/tasks/DEMO_D2_SIM2_TASK.md,
docs/tasks/DEMO_D2_CURRENT_STATUS.md, docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md.
Foreign data/ и docs/MARKETING_ANSWER_SCENARIOS.md вне scope.

### Текущий checkpoint — врачи для услуги, 2026-10-02

Owner после ручного теста подтвердил ответ и согласовал правку шаблонной
вступительной фразы. Дополнительный узкий allowlist: core/d2_directory.py и
эта карточка. Текст «По этой услуге в клинике работают специалисты по
утверждённым карточкам:» заменён на «Эту услугу в клинике выполняют:».
Тип — редакционная правка; каталог, выбор врачей, CTA и контракт не меняются.

Owner «Давай делаем» согласовал узкую DoctorsOperation: kind=doctors,
request_id, один обязательный service target. Тип — исправление потерянной
возможности D2-035/D2-055/B12, не отдельное архитектурное упрощение.
Repo C:\Cursor Projects\artgents-bot-active, branch codex/d2-stage1-contract;
HEAD4d240430c2ce056dc306c50e215dbb09843c6b8f,
origin/main и merge-base141ce91fb1731cd990fcf8391550150016c73e7f.
Baseline — предыдущий незакоммиченный SIM-1/2 WIP; staging пуст.
Foreign data/ и docs/MARKETING_ANSWER_SCENARIOS.md, отдельный SIM0 WIP вне scope.

Allowlist: contracts/d2_dialogue_result.py, core/d2_dialogue.py,
core/response_plan_materialization.py, core/one_call_prompt_contract.py,
tests/test_d2_sim2_contract.py, tests/test_d2_sim2_dialogues.py,
tests/test_d2_ui_b12_scenarios.py, tests/test_d2_http_contract.py,
docs/tasks/DEMO_D2_SIM2_TASK.md, docs/tasks/DEMO_D2_TARGET_CONTRACT.md,
docs/tasks/DEMO_D2_ACCEPTANCE.md, docs/tasks/DEMO_D2_CURRENT_STATUS.md,
docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md.

До: новый target не выражал действие «врачи» вместе с услугой, каталог не
вызывался, B12 падал. После: модель один раз задаёт операцию/услугу; код прямо
вызывает существующий doctors_for_service каталог без старого classify wrapper.
Состав врачей, факты и применимость бесплатной CTA остаются у прежнего кода.
Astra подтвердила схему: scoped exact part участвует в общем расчёте focus,
catalog CTA идёт через существующий UI selector, document source CTA сохраняет
приоритет, контактный телефон добавляется независимо.

Добавлены один вариант операции и его active-tenant validation, исполнительная
ветка и внутренний аргумент directory_cta существующего selector. Scoped exact
parts подключены к существующему общему расчёту scope; отдельных исправлений
state нет. Новых model calls, памяти, retries, fallback и семантических regex нет.
Промпт29 описывает операцию; исходный каталог и правила отсутствующих связей
не меняются. Несколько врачебных операций используют одну существующую CTA
данной клиники/даты, без рейтинга врачей и автоматического выбора врача.

Проверки: narrow schema и отказ foreign/inactive, JSON/SSE/replay,
смена whitening → doctors classic → следующий ход, отсутствие медицинского
факта, mixed/same service scope, обе очередности price/contact/prose,
active/expired CTA и D2-012. Итог:128 PASS/2 FAIL (не scoped prose в новых
same-service fixtures), после разделения scoped/unscoped focused8 PASS.
Независимый read-only Checker: PASS, pytest не повторял; focused review
последнего уточнения теста: PASS. Полный набор130 повторно не запускался.
Ограничения и точные результаты — верх Ledger.
Live/provider, commit/push/merge/deploy этим checkpoint не разрешены.

### Предыдущий checkpoint — fixtures/widget и Cursor handoff, 2026-10-02

Owner согласовал «Делаем»: актуализировать документы после prompt28, довести
затронутые проверки и подготовить актуальный review Cursor. Тип: сопровождение
тестов и документации плюс обнаруженные исправления B11/D2-012; не новое
архитектурное упрощение.
Baseline own WIP на codex/d2-stage1-contract,
HEAD4d240430c2ce056dc306c50e215dbb09843c6b8f, main/merge-base141ce91.

Allowlist: docs/tasks/DEMO_D2_CURRENT_STATUS.md,
docs/tasks/DEMO_D2_SIM2_TASK.md, docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md;
tests/test_d2_session_context.py, tests/test_d2_widget_replay.py,
tests/js/d2_widget_harness.mjs, tests/test_d2_http_contract.py,
tests/test_d2_no_legacy_path.py, tests/test_d2_af1a_price_task_http.py,
tests/test_d2_continuation_scenarios.py, tests/test_d2_document_click_task_http.py,
tests/test_d2_ui_b12_scenarios.py, core/d2_dialogue.py (только исправление B11),
core/response_plan_materialization.py (только восстановление D2-012 CTA).
Расширения объяснены владельцу до правок.
Widget harness прошёл без новых edits; включение в allowlist не означает diff.

Проверять сохранившиеся требования новыми нативными fixtures: точные prices,
tenant/UI ownership, privacy/lead, pending/context, commit failure, JSON/SSE и
replay. Не сохранять ожидания удалённых управляющих полей и global CLARIFY.
Исторический parser для оставшихся consumers проверяется явно отдельно от
активного HTTP D2; не добавлять конвертацию старого envelope в runtime.
Модельные fake-ответы не доказывают качество понимания живой модели.
Сообщение владельца «Работает» фиксируется как ручная проверка одного диалога
после prompt28, не как полный live-gate или автономный запуск агента.

Проверки: session context58 PASS; widget3 PASS, включая headless DOM/transport.
Общий offline CI49 файлов:672 PASS/149 FAIL/5 skipped; clean HEAD имеет те же
количества и148 совпадающих failure IDs. Разница environmental: dotenv test
ключа в локальном checkout и executable-mode в archive без Git index.
Не объявлять CI зелёным; Linux/PG jobs не запускались. Итог шести обновлённых
файлов D2:64 PASS,1 FAIL,143.43s; единственный отказ — врачи для услуги.
Фокусный recheck B11/D2-012:9 PASS,1 FAIL с тем же blocker. Независимый Checker
дал PASS этого узкого checkpoint по коду и предоставленным результатам,
без повторного pytest; закрытие всего SIM-1/2 не подтверждено.
Commit/push/live/merge/deploy отсутствуют; foreign data/ и маркетинговый файл
вне scope. Отдельный Cursor review обязателен для SIM-2 перед закрытием.

Astra read-only подтвердила B11: при переносе в новом state_build появилась
дополнительная проверка subject_relation=self, которой не было в HEAD.
Удаление этой проверки восстанавливает прежнее сохранение явно reported/
correction ситуации другого человека с новым owner. Существующая защита от
переноса прежней ситуации и от записи hypothetical/unknown сохранена; клик
объёма по-прежнему не создаёт медицинский факт. Владелец записи — существующий
state_build; новых управляющих полей, веток, памяти и вызовов нет. Тест B11
сохраняет проверку нового owner, а не принимает прежнюю self-ситуацию.

D2-012: после снятия global CLARIFY чистое уточнение стало получать общую CTA
записи. Исправление в существующем единственном UI selector: передаются уже
разрешённые request_parts; CTA подавляется, если все части — уточнения или
deferred. Независимая опубликованная часть сохраняет прежнюю CTA, телефонная
кнопка не подавляется. Добавлены внутренний аргумент selector и одно условие;
новых wire-полей, состояний, модельных вызовов и способов памяти нет.
Основание — действующее D2-012, это bug fix, не новое продуктовое правило.

Исторический blocker до согласования врачей (снят новым checkpoint выше):
врачи для услуги. На тот момент старый topic=doctors + service=classic
передавал действие и предмет; один новый target не может выразить оба смысла.
Активный D2 тогда не вызывал существующий каталог directory renderer.
B12 assertion «бесплатная запись в действующее окно / обычная после окна»
не ослаблялся до generic CTA. Операция тогда была предложением и требовала
согласования по AGENTS. Владелец затем её согласовал; операция реализована,
проверка B12 прошла. Этот абзац не является действующим запретом.

#### Инструкция переданного и завершённого review Cursor

Read-only review по AGENTS и docs/WORKFLOW_CHECKER.md. Baseline выше;
проверить фактический незакоммиченный diff SIM-1/2 вместе с D2-113/prompt28 и
текущими fixture/B11/D2-012 исправлениями. Старый PASS не распространяется
автоматически на последующие правки. Foreign data/ и
docs/MARKETING_ANSWER_SCENARIOS.md не читать и не менять; SIM0 WIP отдельно.

Проследить оба endpoint до сохранения/replay и виджета. Проверить прямое
исполнение сохранённой задачи кнопки без модельной классификации, отсутствие
fallback в старый envelope и общий механизм price операции. Проверить готовый
content_text, сохранение независимых частей, локальный pending, B11 и D2-012.
Native fixtures должны сохранять смысл и защиты, не подменять их ожиданием
правильного модельного результата; fake-тест не доказывает качество модели.

Выдать отдельный verdict текущего проверенного checkpoint и отдельный список
условий закрытия SIM-1/2. Проверить новую согласованную doctors operation
и сохранённый B12 тест; исторический blocker ниже не является текущим запретом.
SIM-3/4 и полный CI не объявлять закрытыми. Live/provider, commit, push,
merge/deploy и любые правки этим review не разрешаются.
Исторический doctors blocker снят. Для закрытия SIM-1/2 остаются условия
актуальной приёмки в начале карточки, а не повторное согласование операции.

### Предыдущий checkpoint — prompt28 готовое объяснение, 2026-10-02

Тип: исправление ошибки инструкции, не архитектурное упрощение. Владелец
согласовал уточнение области действия инструкции и пример готового ответа
командой «Делай». Baseline: прежний own WIP, branch codex/d2-stage1-contract,
HEAD4d240430c2ce056dc306c50e215dbb09843c6b8f, main/merge-base141ce91.
Allowlist: core/one_call_prompt_contract.py, tests/test_d2_sim2_contract.py,
docs/tasks/DEMO_D2_SIM2_TASK.md, docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md.

Подтверждено в разрешённом read-only разборе: в запрос модели вошли материалы
о сроках, тема implantation и extent one_tooth. Модель вернула описание задания
в прямом content_text; renderer опубликовал его без изменения. Прежняя инструкция
«For content, write the actual unanswered question» не ограничивалась явно
вложенным clarification.operation. Причинная связь с выбором модели — гипотеза.

Исправление применяется ко всем прямым информационным ответам: content_text
содержит завершённое объяснение; незавершённый вопрос допустим только внутри
clarification.operation. Пример использует placeholders фактов текущего tenant,
не устанавливает медицинские сроки по умолчанию. Решение о смысле и объяснение
принадлежат модели по Target Contract §3; код не исправляет её текст.
Новых полей, веток исполнения, вызовов, regex, памяти или правил offers нет.

Проверка: реальные примеры отправляемого промпта проходят parser, существующие
offline-диалоги проверяют JSON/SSE, уточнение и продолжение. Fake-ответы не
доказывают исправление живой модели. Живой критерий: цена → выбор одного зуба →
вопрос о сроках даёт сроки из корпуса, а не задание; повторить в свежей сессии
и после предыдущих вопросов. Live в этом checkpoint не разрешён.
Независимый Checker prompt28: PASS, read-only, без повторного запуска тестов.
Offline SIM2 contract/dialogues:
107 passed за 116.87 с вне sandbox; первоначальный запуск дал 31 passed и
76 setup errors из-за WinError5 доступа к временной папке pytest. Это ограничение
среды, не результат сравнения с чистым baseline. Live/provider/SMTP0.
Проверка actual prompt example доказывает форму, fake-диалоги — контекст и
исполнение; реальные сроки в ответе живой модели пока не аттестованы.

### Текущий checkpoint — D2-113 единый владелец ценового ответа, 2026-10-02

Владелец согласовал: модель определяет ценовой запрос, услугу/направление и
явно сообщённый объём; понятная задача передаётся существующему ценовому
механизму. Удалить отдельное модельное уточнение объёма, обходящее исполнение;
не заменять его server repair. Уточнение непонятной услуги сохраняется.
Разрешение реализации: «Делай». Тип: архитектурное упрощение.
Baseline: own WIP на codex/d2-stage1-contract, HEAD4d24043, main/merge-base141ce91.

До: price/topic исполняется, но та же price внутри clarification/extent
перехватывается раньше и не доходит до price materializer. После: известная
ценовая задача имеет только прямую форму price; service/term уточнение цены
допускает лишь неизвестный target. Parameter clarification информации/details
сохраняется. Удаляется допустимая комбинация price + extent/jaw/stage
clarification и возможность сохранить её в pending state. Владелец достаточности
ценовых данных — существующий price materializer, владелец смысла — модель.
Offer policy/SIM-0, медицинские и lead/privacy правила не меняются. Новых
обязательных уточнений или правил ценовой применимости не вводить.

Allowlist: contracts/d2_dialogue_result.py, contracts/response_plan_session.py,
core/d2_dialogue.py, core/one_call_prompt_contract.py,
tests/test_d2_sim2_contract.py, tests/test_d2_sim2_dialogues.py;
SIM2 Task, Target Contract, Product Decisions, Acceptance, Current Status,
Delivery Roadmap, Checkpoint Ledger (все docs/tasks/DEMO_D2_*.md).
Astra одобрила явные варианты уточнения с общими ограничениями pending;
known-task клик должен создавать обычную операцию после подстановки target.

Проверки: фактическая JSON schema + parser запрещают старый обход; прямые
price одинаково работают в свежем диалоге/после страха боли, с независимой
информацией, явным объёмом, кнопками/replay, честным пробелом. Service/term
неоднозначность и параметрические information/detail сохраняются. Offline
не доказывает выбор модели; новый live-gate пока не разрешён. Предыдущий
live-gate остановлен и остаток не возобновляется. Несовместимый прежний
price pending отклоняется; migration/reset не добавлять. Staging пуст,
commit/push/merge/deploy не разрешены. Foreign WIP не трогать.

Реализация: два shared task-типа различают service/term и nonprice parameters;
wire использует производные варианты, persisted validator использует тот же
адаптер. Узкий UnresolvedPriceOperation не добавляет полей: ограничивает target.
Service click заново валидирует обычную операцию из сохранённых полей и уже
проверенного ID; модель не вызывается для цены. Общий абстрактный clarification
больше не входит в принимаемый union. Known price model clarification не
превращается в price скрытым серверным исправлением — старый payload невалиден.
Положительные диалоги проверяются отдельно; live надёжность пока не доказана.
Session schema2 остаётся; несовместимый старый pending даст invalid turn без
автоматического сброса. Старые локальные тестовые сессии нужно начинать заново.

Текущие проверки: test_d2_sim2_contract.py, test_d2_sim2_dialogues.py,
test_d2_sim1_known_actions_http.py — 125 PASS одним прогоном (138.18 с),
provider/network заблокированы fixtures. Schema negative и positive dialogue
проверяются отдельно. Additional session_context collection остановлен на
старой fixture axis/request_ids и т.д.; он не входит в 125, не починен и не
объявляется PASS. Это не результат сравнения с чистым baseline; полный CI
остаётся открытым. Предупреждения — utcnow deprecation logging_setup.
Независимый Checker D2-113: PASS, read-only, тесты повторно не запускал. Live0 в этом checkpoint.

### Live-gate prompt 26 — остановлен на смысловом несоответствии, 2026-10-01

Владелец «Давай» явно разрешил предложенные максимум 8 вызовов, без retry,
с остановкой при первой ошибке. Выполнены 4 фактических provider calls;
ещё 1 попытка блокирована sandbox WinError10013 до соединения. Всего в
консервативном счётчике 5/8, gate остановлен, остаток не расходовать.
SDK max_retries=0. Сетевой запуск после sandbox-разрешения выполнен отдельным
процессом с prompt26, копией clients и временными dialogue/lead DB/logs;
существующий сервер9001 и foreign data/ не менялись. Первый запуск стенда
потребовал копию nikadent для startup validation — до provider, 0 calls.

Результаты через настоящий Flask test_client /ask и /ask/stream:
- S1 общий вопрос о цене имплантации → price/topic implantation, обзор и
  три volume кнопки. Модель не выбрала classic; состав опубликованного
  обзора остался прежним кодовым выбором (три classic offers, SIM-0 открыт).
- Клик one_tooth → цены, 0 model calls; затем вопрос о сроках → ответ про
  20–30 минут установки и 3–6 месяцев до постоянной коронки. Эти сроки
  есть в implantation__faq__duration.md; это один успешный follow-up.
- S2 страх боли → content; затем общий вопрос о цене → валидный
  clarification(missing=extent, operation=price/target topic implantation).
  Сервер дал только текст уточнения; prices и quick_replies отсутствуют.
  Ожидаемый обзор направления не получен: semantic gate FAIL, HTTP при этом
  успешен. Малформатный вложенный target и выбор classic не повторились
  в этом вызове, но надёжность генерации в целом не доказана.

Точная услуга, неясная цена, информационное уточнение/клик не запускались
из-за stop-on-failure. Browser/full CI не проверялись. Код и настройки
провайдера в репозитории по результату не менялись; новый runtime-fix требует
разбора. Commit/push отсутствуют, staging пуст, SMTP0.
Временный evidence: C:/Users/denis/AppData/Local/Temp/d2-prompt26-live-owner-5lq93k1_/
(run.py, budget.json, overview/volume/duration/fear/after_fear.json, logs).
Raw prompts/логи не копируются в Git. Счётчик gate: stopped=true после
несоответствия overview для after_fear; 4 успешных ответа провайдера.

### Предшествующее исправление инструкции уточнения, 2026-10-01

Владелец согласовал план исправления «Ок, делаем». Тип — bug fix инструкции
и устаревшего текста; это не новое архитектурное упрощение и не доказательство
качества живой модели. Baseline: существующий SIM-1/2 WIP на 4d24043,
ветка codex/d2-stage1-contract, main/merge-base 141ce91.

До: модель может вложить target вместо целой operation; схема есть в промпте,
но нет компактных примеров различия. После: та же схема объяснена через
kind/request_id/target и примеры цены, информационного уточнения и обзора
направления. Owner понимания — модель, owner исполнения — существующий сервер.
Decoder repair, retry, новые поля/состояния/семантические ветки не добавляются.
D2-110: текст меню согласуется с one_tooth/full_arch/unknown; few_teeth в
свободном вопросе остаётся допустимым. Выбор методики и offers не меняется.

Allowlist: core/one_call_prompt_contract.py, core/d2_snapshot_sources.py,
clients/demo/target_response/d2_direction_prices.json,
tests/test_d2_sim2_contract.py, tests/test_d2_sim2_dialogues.py,
эта карточка, Current Status, Delivery Roadmap, Checkpoint Ledger.
Проверки: примеры из реально собранного prompt через действующий parser;
JSON/SSE, направление → объём → продолжение/replay; malformed operation
не восстанавливается кодом; текст меню и informational clarification.
Astra: read-only консультация по общей форме операции. Независимый Checker
до отчёта. Live требует отдельного call budget; commit/push не разрешены.

Результат offline: test_d2_sim2_contract.py + test_d2_sim2_dialogues.py —
79 PASS одним прогоном (88.91 с), сеть блокируется HTTP fixture; новые кейсы
берут три примера из реально собираемого промпта, проверяют JSON/SSE,
продолжение, UI, replay и отказ malformed operation без retry/изменения state.
Прогон не проверяет, что живая модель сама выдаст эти примеры. Parser/schema,
выбор offers, transport и механизм памяти этим исправлением не менялись.
Предупреждения pytest: существующий utcnow deprecation в logging_setup.
Независимый Checker текущего исправления — PASS (read-only, pytest не повторял). Browser и общий CI
не запускались; прежние ограничения остаются. Агентских provider calls 0.

Проверка strict output по официальной документации Alibaba на 2026-10-01:
[Structured output](https://www.alibabacloud.com/help/en/model-studio/qwen-structured-output)
перечисляет Qwen3.8-Flash среди JSON Schema models, но одновременно содержит
ограничение Singapore и примеры с Singapore endpoint. Поддержка конкретного
подключения и используемых union/$ref не подтверждена. Response format не
переключён, модель/endpoint не менялись; транспорт остаётся json_object.
Смена режима не является результатом этого checkpoint. Примеры улучшают
инструкцию, но не гарантируют соблюдение схемы или смысловой выбор.

Историческое предложение live-gate (впоследствии разрешён и остановлен, см. выше): максимум 8 provider calls,
без retry: общий ценовой вопрос → объём (0 calls) → срок (2); страх боли →
общая цена (2); точная услуга All-on-4 (1); неясная услуга для цены (1);
информационное уточнение → выбор (2). Синтетические данные, отдельные сессии,
без заявки/SMTP. При ошибке остановить gate и разобрать evidence. Проверять
направление/методику отдельно от JSON. На момент предложения требовалось одобрение; фактическое разрешение и результат выше.

### Действующее уточнение D2-112 после review

Владелец согласовал одно активное уточнение без отказа всего составного
вопроса. Полное правило — [D2-112](DEMO_D2_PRODUCT_DECISIONS.md#d2-112--одно-активное-уточнение-без-потери-понятного-ответа).
Первое по порядку уточнение владеет единственной pending operation/UI;
понятные части публикуются сразу, остальные требующие уточнения задачи
явно deferred, без очереди и автоматического запуска после клика.

До → после: нынешний d2_multiple_active_clarifications прерывает весь ход
→ код применяет согласованное ограничение публикации, сохраняя понятные части.
Owner порядка/смысла — модель; owner выбора первого из упорядоченных задач
для единственного UI — сервер. Это исправление поведения по принятому правилу,
не новая память или повторная классификация. Некорректные ID/actions остаются
ошибками. Приёмка — D2-112/S02 в Acceptance; исправление реализовано в WIP.
Focused независимый Checker: PASS. Отдельный Cursor ещё требуется.

Последствия schema 1 проверены на синтетических изолированных fixtures:
тот же SID получает d2_invalid_turn (JSON 400 / SSE error), без provider call.
Старый dialogue payload и активная заявка остаются неизменными; новый SID
работает как отдельный разговор, старую заявку автоматически не переносит.
Migration/reset не добавлены. Cursor проверяет прямые, косвенные и error
paths оставшихся wrappers; прежний PASS не заменяет этот review.

Узкий runtime-шаг D2-112 разрешён владельцем «Давай» после фиксации правила.
Baseline — текущий own WIP на HEAD 4d24043. Allowlist этого шага:
`core/d2_dialogue.py`, `contracts/response_plan.py`,
`core/response_plan_materialization.py`, `core/response_text_renderer.py`,
`core/one_call_prompt_contract.py`,
`tests/test_d2_sim2_dialogues.py`, эта карточка, Current Status, Roadmap, Ledger.
Astra рассмотрела применение существующего deferred-механизма: один результат
на исходный request ID, один pending/UI. Authored availability остаётся
answered; меню создаёт только explicit clarification. У действующих
availability producers нет service menu: прежняя недостижимая ветка удалена,
новое меню альтернатив не добавлено. Старые сессии проверяются
только синтетическими offline fixtures, без чтения/изменения foreign data/.

### Действующее разрешение реализации

После предложения §9.2 владелец ответил «Да»: объединение и его реализация
согласованы. Прежние формулировки «не принято / не runtime GO» ниже описывают
историю проектирования и заменены этим разрешением. SIM-3/4 остаются своими
этапами; live, commit/push, merge и deploy этим не разрешены.

Baseline — текущий рабочий diff поверх указанного HEAD. Прежний WIP сохраняется.
Точный allowlist реализации:

- `contracts/d2_dialogue_result.py` (новый), `contracts/d2_dialogue.py`,
  `contracts/response_plan_session.py`, `contracts/response_plan.py`;
- `core/d2_dialogue.py`, `core/d2_live_provider.py`,
  `core/d2_snapshot_sources.py`, `core/d2_session_context.py`,
  `core/one_call_envelope_protocol.py`, `core/one_call_prompt_contract.py`,
  `core/response_plan_materialization.py`, `core/d2_lead_bridge.py`,
  `core/clinic_policy_resolver.py`, `core/d2_offtopic.py`,
  `core/response_plan_resolver.py`, `core/response_text_renderer.py`;
- `tests/test_d2_sim2_contract.py`, `tests/test_d2_sim2_dialogues.py`
  (новые), `tests/test_d2_sim1_known_actions_http.py`, `tests/test_d2_widget_replay.py`,
  `tests/test_d2_commercial_plan.py`;
- эти пять документов: SIM2 Task, SIM1 Task, Roadmap, Current Status, Ledger.

Изменения — архитектурное упрощение по §2/5/9.2 и отдельно исправление
зависимости сохранения ситуации от цены (§9.3). Проверки — §8; независимые
Checker и Cursor до закрытия. Недостижимые legacy wrappers допустимы для
исторических consumers, но новый D2 не восстанавливает старый envelope.

- Root: `C:\Cursor Projects\artgents-bot-active`; branch: `codex/d2-stage1-contract`.
- HEAD: `4d240430c2ce056dc306c50e215dbb09843c6b8f`;
  локальный tracking ref ветки совпадает. Новый fetch не выполнялся.
- `origin/main` / merge-base: `141ce91fb1731cd990fcf8391550150016c73e7f`.
- Исторический allowlist документального checkpoint: эта новая карточка, `DEMO_D2_SIM1_TASK.md`,
  `DEMO_D2_DELIVERY_ROADMAP.md`, `DEMO_D2_CURRENT_STATUS.md`,
  `DEMO_D2_CHECKPOINT_LEDGER.md` — все в `docs/tasks/`.
- Существующий runtime/test/doc WIP сохраняется. Foreign `data/` и
  `docs/MARKETING_ANSWER_SCENARIOS.md` не читать и не изменять.
- В документальном шаге код и смена порядка этапов не входили в scope.
  Действующее runtime-разрешение и allowlist указаны выше.

## 2. До → после

Сейчас модель одновременно задаёт глобальные `route`, услугу и коммерческое
намерение и повторяет смысл внутри `request_understanding.requests`.
Глобальный CLARIFY завершает ход раньше независимого ответа. После service
click модель снова выбирает kind/route; сервер проверяет и подставляет услугу.

После: свободный вопрос один раз превращается в связное объяснение и операции
для точных данных/действий. Уточнение содержит конкретную незавершённую
операцию. Сервер проверяет клик, заполняет её параметр и исполняет.
Исчезают повторная классификация кнопки и глобальное взаимоисключение
«объяснение или уточнение». Это относится ко всем таким составным вопросам,
а не к отдельным словам про зубы или дёсны.

## 3. Минимальный модельный результат

Один исключительный выбор `outcome`: `dialogue` либо существующий терминальный
`admin`. Последний не допускает обычные блоки рядом и сохраняет действующие
медицинские основания и правила ответа; новые основания не вводятся.

`dialogue.blocks` — упорядоченные элементы:

| Тип | Единственное содержимое и потребитель |
|---|---|
| explanation | Связный текст, существующий realization и необязательные source refs; renderer/source UI. Один ответ «как проходит, больно ли, сколько заживает» не требует трёх задач |
| price | Target, бренд и применимый объём одной ценовой операции; код подбора из прайса |
| price_detail | Includes/stages и допустимая ссылка на предложение/показанный набор; существующий detail resolver |
| contact | Запрошенные поля и выбранный branch ID; tenant contact resolver |
| policy / commercial_fact | Идентификаторы утверждённых правил/фактов и необходимые параметры применимости; существующий код точных данных |
| booking | Только существующее намерение передать управление lead owner; не отправка и не самостоятельное изменение заявки |
| clarification | Одна вложенная операция, недостающий параметр и допустимые варианты; существующий owner уточнения |

Это узкие варианты типов, не широкий объект с обязательными пустыми полями
всех остальных типов. `explanation` сохраняет authored/model_prose и ссылки
на разделы для существующего UI; authored не удаляется. Общий `other`,
который сервер затем исправляет в `content`, не нужен.

Target операции — взаимоисключающее значение: известная услуга, известная тема
или неразрешённая ссылка. Неизвестная ссылка не равна отсутствующей в клинике
услуге. Известная неактивная услуга проверяется по tenant-каталогу. Бренд —
отдельный параметр операции, не альтернативный источник service ID.
Для неразрешённой ссылки достаточно typed-маркера: текущий
`build_d2_unknown_reference_response` не использует название из текста,
а публикует утверждённый tenant-пробел. Известная неактивная услуга остаётся
`known_service(id)` и проходит `build_d2_service_availability_response`:
утверждённая альтернатива либо информационный пробел, без вывода «не оказываем»
только по inactive. Серверного поиска по русскому тексту нет.

Порядок ценовых операций соответствует порядку вопросов пользователя.
Код применяет D2-080/B14: первая исполняется или уточняется, остальные явно
deferred, без автоматической очереди и второй группы кнопок. Отдельный
`primary_price_request_id` не дублирует порядок. Проверка структуры не может
доказать, что модель верно поняла порядок; это проверяется диалогами.

Сведения о субъекте/ситуации сохраняют только действующее назначение:
применимость правил и явно сообщённые/исправленные факты. Они не обязательная
классификация каждой prose-части. Для объяснения без ценовой операции нельзя
потерять явное сообщение ситуации. Техническая привязка уточнена в §9:
одна необязательная связанная ситуация у блока, включая explanation,
без нового извлекателя фактов и без записи клика как медицинского факта.

## 4. D2-111: полный пример и сохранённая задача

Пользователь: «Сколько стоит восстановить зуб? И как ухаживать за дёснами?»

Первый модельный результат концептуально:

```text
dialogue.blocks:
  explanation: понятный ответ об уходе по материалам клиники
  clarification:
    missing: service
    operation: price(target ещё не определён, остальные известные параметры)
    choices: допустимые service IDs текущей клиники
```

Реальные ID берутся из каталога; этот пример не утверждает набор методик.
Бот сразу отвечает об уходе и показывает уточнение услуги. Существующий
owner `PersistedClarifyTask` сохраняет вложенную операцию и missing; безопасная
исходная формулировка нужна задаче, которой ещё предстоит пояснение. Полный
envelope, уже отвеченное объяснение и независимые dedup-массивы не сохраняются
как pending task. Membership и revision принадлежат существующему сохранённому
UI, второго независимого списка полномочий кнопок нет.

После выбора: tenant/client/revision/TTL/UI membership → сохранённая операция
→ заполнение service → подбор и текст цены → completion → projection.
Чистая цена и details: 0 model calls. Для информационного уточнения сохранена
задача объяснения с фокусом: один существующий вызов получает готовое задание,
возвращает лишь разрешённое пояснение, не выбирает route/kind/service заново.
Уход за дёснами не становится новым заданием этого клика.

Общий strict JSON decoder и provider entry остаются одни. Нельзя сделать
адаптер, который восстановит старый полный envelope и сохранит его семантические
развилки под новой оболочкой. Текущий combined WIP переводит также
volume/document на новый тип; исторический частичный WIP использовал старый.

## 5. Удаления и фактические потребители

Пути относительно корня. Это инвентаризация будущей реализации, не allowlist кода.

| Удаляется / заменяется | Где сейчас и что должно исчезнуть из D2 пути |
|---|---|
| ANSWER/CLARIFY как решение всего хода | `contracts/one_call_envelope.py:OneCallEnvelope`; `core/d2_dialogue.py:_run_reserved_d2_dialogue_turn`: ранний возврат CLARIFY. Остаются terminal и локальная pending operation |
| Верхние service_id, extent, jaw, stage, scenario | Тот же envelope, `core/one_call_envelope_protocol.py:_validate_structure`, `core/d2_session_context.py:bind_implicit_price_service`: дубли и проверки их согласования. Нужные параметры принадлежат операции |
| commercial_intent, promotion_scope, references.direct_fact_ids | `core/d2_dialogue.py` и `core/response_plan_materialization.py:resolve_d2_envelope_response`: глобальные комбинации promotion/payment/content. Локальные точные операции сохраняют действующие правила |
| service_reference_status + requested_service_id | `core/one_call_envelope_protocol.py:_validate_reference_context`, unknown/inactive ветки dialogue: заменяются единственным typed target, без потери unknown/inactive различия |
| clarify_axis/clarify_service_options, patient_text/price_text | Envelope/parser/prompt и `core/d2_snapshot_sources.py:build_d2_focus_clarify_response`: нет глобальной копии задачи и prose. Уточнение собирается вместе с независимыми блоками |
| primary_price_request_id и его normalizations | Envelope/parser/prompt и B14 consumers: единственный порядок операций. Проверить также `contracts/sales_one_plus.py`, `core/one_call_response_composition.py` и sales consumers; не объявлять их недостижимыми без трассировки |
| Универсальный RequestUnderstandingRequest и legacy scope_commitment/tooth_count дубли | `contracts/request_understanding.py`: узкие варианты и одна привязка ситуации; удалять legacy-normalizer только после замены потребителей |
| request_ids/request_kinds/topic_ids/service_ids/requested_extents в PersistedClarifyTask | `contracts/response_plan_session.py`, `core/d2_dialogue.py:_d2_clarify_task`, projection в `core/d2_session_context.py`: одна связанная pending operation |
| service post-model override, other→content, whitelist multipart shapes | `core/d2_dialogue.py:_run_reserved_d2_dialogue_turn`, `_d2_multipart_shape_ok`, `_d2_supported_price_shape_failure_codes`: прямое исполнение известных действий и локальные валидаторы операций |
| Неявное угадывание сервиса по пустым полям | `core/d2_session_context.py:bind_implicit_price_service`: модель видит допустимый контекст и выбирает target свободного вопроса; кнопка имеет готовый target. Не переносить эту догадку в renderer |

Общие точки замены: `core/d2_live_provider.py`,
`core/one_call_prompt_contract.py`, `core/one_call_envelope_protocol.py`,
`core/response_plan_materialization.py` и binding в `core/d2_session_context.py`.
Глобальный focus не должен заново разрешать смысл независимых операций.
Проверки ID, источников, допустимого объёма, subject binding и TTL сохраняются.
Необходим отдельный reachability inventory общих sales/legacy потребителей
перед удалением shared-типа; fallback к ним запрещён.

## 6. Совместная граница SIM-2/3

Имеющийся `D2CompletedTurn` хранит опубликованный результат в `response`,
а также отдельные `context` и `focus`. Существующая projection становится входом следующего хода, включая
ответы кода и pending/deferred, без новой сводки и второго хранилища.
Обсуждаемый объём связан с услугой; историческая сумма не становится прайсом.

Сейчас `core/d2_dialogue.py:_d2_live_prose_for_history` и
`_next_d2_dialogue_pairs` исключают часть code-only/clarify истории; существуют
частные `recent_price_scope` переносы. В SIM-3 после замены потребителей
удаляются это исключение и специальный перенос объёма. SIM-2 должен передать
завершённый результат существующему owner, но не объявлять SIM-3 выполненным.
Активная заявка, приватность, медицинские факты и TTL сохраняют своих owners.

## 7. Финансовая граница: обязательный пример, нерешённый механизм

Условные данные для проверки, не реальный прайс клиники:
прайс — 20 000 ₽, включение снимка не подтверждено.
Модель пишет: «Заживление проходит постепенно. Всё обойдётся в 15 000 ₽,
снимок включён».

Требуемый результат: полезное независимое объяснение сохраняется рядом с
20 000 ₽ из данных; 15 000 ₽ и обещание включённого снимка не публикуются.
Структура price/explanation и запрет в промпте этого не гарантируют.
Способ предотвращения такой публикации ещё не выбран; произвольное вырезание
текста, semantic regex, новый verifier/call или отказ от всего ответа не
разрешены. Это открытая техническая граница SIM-2/SIM-4. Если механизм меняет
видимый UX, до реализации показать владельцу конкретный результат.

## 8. Последовательность и проверки

Объединённый checkpoint разрешён владельцем: полное service clarification
с D2-111 требует замены глобального CLARIFY из ядра SIM-2. Действующее
разрешение и allowlist приведены в начале карточки; временного адаптера,
восстанавливающего старый envelope, в новом D2 нет.

Обязательная приёмка соответствующей реализации:

1. Цена+независимое объяснение → уточнение → service click → цена → продолжение.
   Объяснение сразу, клик не повторяет его и не вызывает классификатор.
2. Два ценовых вопроса в обеих очередностях, первый требует уточнения:
   B14/deferred сохраняется, первая подходящая услуга не выбирается сервером.
3. Информационное уточнение → выбор → пояснение, без фиктивной цены;
   обычное связное объяснение допускает один prose-блок.
4. Контакт+политика, неизвестная услуга/бренд+адрес в обеих очередностях;
   authored/source UI, booking и medical terminal не теряются.
5. Цена одного зуба → сроки → адрес → сроки лечения; смена услуги,
   неоднозначный референт, явное сообщение ситуации без цены и TTL.
6. `/ask`, `/ask/stream`, widget, replay, stale/forged/foreign; provider stub
   падает при неожиданном вызове чистой кнопки. Explanation-only ответ с
   управляющими полями не может переопределить известное действие.
7. Checker трассирует удалённые зависимости от входа до completion и проверяет
   отсутствие старого envelope adapter/повторного resolver. Правильный fixture
   модели не объявляется доказательством живого понимания.

Разрез и привязка ситуации реализованы в текущем WIP; достижимые consumers
нового D2 переведены на операции, оставшиеся shared wrappers перечислены ниже.
Финансовая публикация остаётся SIM-4. Документальный PASS предыдущего шага
не заменяет runtime-проверки и отдельный Cursor общего checkpoint.

## 9. Уточнение технических зависимостей — 2026-10-01

После разрешения продолжить проверены producer, parser, service click,
state-build и оба endpoint. Astra повторно участвовала read-only.
Этот раздел сохраняет обоснование объединения этапов. Владелец позднее
принял §9.2; действующее разрешение реализации записано в начале карточки.

### 9.1. Почему изолированного service-click исправления недостаточно

`core/d2_dialogue.py:_run_reserved_d2_dialogue_turn` сейчас:

1. Сначала вызывает provider/parser; service-блок затем принимает лишь одну
   request, проверяет её route/kind и переписывает service/topic.
2. При глобальном CLARIFY вызывает `build_d2_focus_clarify_response` и сразу
   `_commit_non_price_d2_turn`; независимая prose в этот результат не попадает.
3. `_d2_clarify_task` сохраняет независимые dedup-массивы. Их нельзя достоверно
   соединить обратно в исходную задачу при нескольких вопросах.

Следовательно, прямое исполнение клика требует изменить создание задачи
на первом ходе. D2-111 требует одновременно изменить сборку первого ответа.
Эти изменения уже затрагивают ядро SIM-2 (producer/parser и общий CLARIFY).
Оставить старый формат для части ordinary-запросов или восстановить его
адаптером означало бы сохранить запрещённую зависимость.

### 9.2. Конкретное предложение владельцу: один общий checkpoint

**Остаток SIM-1 + необходимое ядро SIM-2** с общими критериями приёмки:

- Заменить ordinary producer/parser единым целевым результатом из §3.
  Перенести все его достижимые варианты (включая contacts/policies, booking,
  authored, unknown/inactive, ADMIN/medical), без второго контракта или fallback.
- Вложить уточняемую операцию в clarification; сохранить её у прежнего owner.
  Выдать независимый ответ сразу по D2-111.
- Удалить service post-model override. Проверенные price/service/volume/details
  исполняются сервером; информационные действия допускают только пояснение
  готовой задачи. Привести нынешний partial WIP к тем же прямым типам.
- Удалить верхние дубли, глобальный ANSWER/CLARIFY и перечни разрешённых
  сочетаний ordinary-частей из достижимого пути (§5). Это существенная часть
  SIM-2, её нельзя выдать за небольшой локальный фикс SIM-1.
- Сохранить атомарный completion и действующую projection. Устранить зависимость
  применения явно сообщённой ситуации от наличия ценового расчёта (§9.3).
- Проверить все диалоги §8, оба endpoint и затронутый widget; Checker и Cursor
  обязательны, поскольку checkpoint затрагивает рубеж SIM-2.

SIM-1 остаётся открытым до этой приёмки. SIM-2 закрывается лишь при выполнении
всех его критериев, а не автоматически вслед за объединением. Если останется
независимая очистка недостижимых shared/legacy потребителей, перечислить её
явно; повторные решения в достижимом runtime оставлять нельзя.
SIM-3 сохраняет унификацию истории завершённых ответов; SIM-4 — финансовую
публикацию и утверждённый подбор offers. Их результат здесь не объявляется.
Новый verifier/call, финансовый sanitizer, новое правило памяти или offers
в объединение автоматически не входят.

### 9.3. Ситуация без цены: привязка и найденная зависимость

Предлагаемая структура сохраняет уже существующие subject, scope_commitment,
extent/tooth_count/jaw и continuity в одном необязательном вложении у owning
блока. Оно допустимо и у explanation. Сохраняется нынешнее ограничение одной
сообщённой ситуации на ход; не создаётся второй список facts/state_updates.
Если одна ситуация нужна цене и объяснению, запись одна, потребители используют
её связь с субъектом и услугой/темой по действующим правилам. На обычном
информационном вопросе поле отсутствует; гипотеза и клик не становятся фактом.

Пример: «У меня нет зубов на нижней челюсти. Как проходит восстановление?» —
один связный explanation с явно сообщённой ситуацией. Продолжение «Сколько
времени это займёт?» использует допустимый контекст. «Я ошибся, речь о верхней»
проверяет correction, затем короткий ценовой вопрос проверяет сохранённую связь.
Это перенос существующих правил, без самостоятельного диагноза или лечения.

Важное уточнение к раннему проекту: нынешняя схема допускает situation на
content, и `_d2_treatment_situation` извлекает её в materialized result.
Однако `core/d2_dialogue.py` сохраняет reported/correction в ветке
`decision.applied_extent`. Поэтому наличие поля не доказывает сохранения факта
на информационном ходе. Цель — применять действующие правила к валидированной
ситуации при completion независимо от ценового решения. Этот дефект и удаление
его зависимости проверяются отдельно от упрощения самого JSON. Не расширять
правила subject/reset/TTL/correction под видом переноса полей.

### 9.4. Проверенные входы и общие потребители

| Путь | Установленный факт и граница изменения |
|---|---|
| `app.py:ask`, `ask_stream` → `core/d2_http_adapter.py:run_d2_ask_json` → `run_d2_dialogue_turn` | Оба endpoint используют один D2 turn. SSE оформляет его завершённый результат, отдельного semantic runtime здесь нет |
| D2 turn → `parse_production_envelope_json` → `OneCallEnvelope` | Старый тип достижим непосредственно; заменить только внешний JSON недостаточно |
| D2 turn → `build_d2_snapshot_sources` / `bind_d1r_envelope_to_d2_context` / `resolve_d2_envelope_response` | Старый тип и RequestUnderstanding проходят дальше в источники, focus и materializer. Все эти входы требуют согласованной замены; exact-data selection и renderer не должны снова выбирать задачу |
| `core/d2_live_provider.py:build_d2_d1r_messages` → `core/one_call_prompt_contract.py` | D2 использует общий prompt contract; при замене обновить обычный и known-task вход, не оставлять старое обучение route/kind |
| `core/sales_one_plus_turn.py`, `core/sales_one_plus_stream.py`, `contracts/sales_one_plus.py:answer_allows_empty_patient_text` | Другие потребители общего parser/envelope существуют. App endpoints выше не вызывают sales turn, но это не доказательство удаления всех транзитивных shared-зависимостей |
| `core/one_call_response_composition.py`, `contracts/sales_one_plus_semantic.py`, `core/one_call_presentation_pass.py` | Отдельные потребители primary ID остаются в репозитории. Нельзя механически удалить shared-поле, сославшись лишь на отсутствие прямого вызова в app |

Перед удалением shared-символов нужен полный поиск их references/imports и
точная замена достижимых потребителей. Отдельный старый runtime не получает
статус production-совместимости; его существование не основание для адаптера,
fallback или сохранения конкурирующей логики. Этот inventory не выдаёт
утверждение, что весь legacy уже недостижим.

### 9.5. Что требует решения, а что является работой исполнителя

Изменение границы checkpoint из §9.2 согласовано владельцем. Оно заменяет
порядок «закрыть SIM-1 перед реализацией SIM-2» общим checkpoint.
Структуру связанной ситуации, references/imports, точный кодовый allowlist и
offline-проверки готовит исполнитель. Уже принятые D2-111/B14 не пересогласуются.
Финансовый механизм §7 остаётся отдельной технической задачей: изменение
его UX потребует конкретного примера, а не общего разрешения на этот checkpoint.


## 10. Реализованный combined WIP — 2026-10-01

### Фактическая замена и владельцы

| До | После и единственный владелец | Удалено из активного D2 |
|---|---|---|
| Общий route/commercial_intent/service/primary плюс повторные requests | Модель возвращает outcome и ordered narrow blocks; код проверяет структуру и источники | Глобальные route, commercial_intent, primary_price_request_id, references.direct_fact_ids и дубли target; старые prompt-инструкции D2 |
| Глобальный CLARIFY подавлял независимый ответ | Локальная clarification содержит одну operation; renderer публикует независимую prose сразу | Взаимоисключение всего ответа и уточнения; whitelist комбинаций multipart |
| Service click снова проходил модельный выбор | Сервер читает сохранённую operation, заполняет service и исполняет; пояснение получает explanation-only output | Post-model service override, other→content, зависимость известных ценовых действий от route/kind |
| Pending хранил несвязанные массивы IDs/kinds/scopes | Существующий PersistedClarifyTask хранит missing + operation | request_ids/request_kinds/topic_ids/service_ids/requested_extents |
| Ситуация сохранялась через успешную ценовую ветку | Существующий state owner принимает явный reported/correction и из content | Зависимость личного факта от applied_extent цены; это отдельное исправление ошибки |

Wire spelling объяснения — kind=content, правила — clinic_policy; это
доменные имена, не дополнительная классификация текста. off_topic сохраняет
прежний ответ о границах клиники. Read-only свойства service_id/topic_id
вычисляются из одного target и не являются отдельными хранимыми полями.

Один строгий JSON decoder — parse_production_envelope_json(d2_contract=True).
Новый runtime вызывает resolve_d2_operations напрямую. Price/service/volume/detail
не требуют ответа модели на ходе кнопки; explanation-only не допускает новых
target/kind/route и требует явного непустого текста вместо наследования seed.
Обычные связные объяснения остаются одним content-блоком.

### Общие потребители и границы удаления

- Старый resolve_d2_envelope_response оставлен как wrapper для исторических
  unit consumers; новый D2 его не вызывает. Wrapper вызывает тот же нижний
  resolve_d2_operations, обратного адаптера к OneCallEnvelope нет.
- Исторические bind_implicit_price_service и resolve_d2_optional_content_claims
  ещё определены и проверяются старыми unit tests, но отсутствуют в активном
  D2 call path. Их физическое удаление вместе с историческими consumers здесь
  не заявлено. Новый D2 не использует server guessing пустого target.
- resolve_clinic_policies сохраняет старый wrapper для внешних consumers;
  D2 передаёт операции/subjects существующему владельцу правил напрямую.
  Аналогично snapshot и lead принимают narrow inputs, без fake understanding.
- Прежний отдельный detail response shortcut удалён: общий detail resolver
  сохраняет captured offer set и даёт прежнее уточнение при отсутствии контекста.
- После D2-112 prompt version 25; session schema 2. Local records schema 1 не мигрированы.
  Проверки используют новые изолированные сессии; пользовательская data/
  не открывалась и не переписывалась.

### Что проверяется и что остаётся

Тесты нового контракта проверяют отказ конкурирующим управляющим полям и
неполным explanation-only ответам. Сквозные тесты проходят реальный HTTP
adapter, parser, materializer, store, следующий ход и replay с подставленным
raw ответом модели. Отдельный тест запрещает вызовы старого envelope/understanding.

Исторический прогон до D2-112: 41 сквозная проверка прошла после исправлений Checker: JSON/SSE mixed
clarification, сервисный клик, объём, details, B14/T4, явная ситуация и
коррекция, contact/policy/authored alternatives, commercial facts+prose,
medical terminal, lead interruption/privacy/resume/replay, stale/forged/foreign,
смена темы и expired detail context. Domain/contracts/actions: 140 PASS, ещё 4 commercial PASS после обновления
только raw fixture; итог 185 непересекающихся offline PASS. Независимый
Checker после focused recheck дал PASS; детали в Ledger. Cursor ещё нужен.

Browser harness: два transport/widget replay теста прошли; настоящий browser
тест не завершён из-за CDP timeout Runtime.enable. Это не browser PASS.
Старые end-to-end fixtures прежнего envelope ещё не все переведены: полный CI
не объявляется зелёным. Новый протокол не должен получать fallback ради них.

SIM-3 ещё должен заменить prose-only history/recent_price_scope перенос
единым доступом к сохранённому completion. SIM-4 ещё должен обеспечить
D2-108 для всей опубликованной prose. Текущие offline fixtures не доказывают
качество понимания живой модели и не закрывают эти этапы.

### D2-112: результат и новые проверки

Удалён отказ всего хода d2_multiple_active_clarifications. Сервер оставляет
первую pending operation; последующие уточнения получают существующий deferred
block и фиксированный текст, без persistent queue. Понятная цена/контакт/
объяснение сохраняются. B14 действует отдельно. Validator запрещает price
block у deferred/unavailable первой цены и разрешает её deferral только после
более раннего активного информационного уточнения.

Это исправление по D2-112, а не закрытие всего архитектурного этапа. Добавлены
ветка публикации последующего уточнения и второй разрешённый фиксированный
deferred-текст, расширена строгая проверка результата; новых model fields,
состояний памяти или model calls нет. Порядок задаёт модель, сервер публикует
первое уточнение, parser проверяет все choices, включая скрытые.

161 непересекающийся offline PASS: полный dialogue run 53 PASS, остальные
contract/action/resolver/renderer 107 PASS; добавленный shape guard отдельно
1 PASS. Итого dialogue cases 54, но одним полным прогоном 54 не запускались.
Первые прогоны выявили ошибочные SSE/menu ожидания, остаточный validator и
несогласованную негативную fixture; они исправлены, focused rerun PASS.
Старые schema-1 fixtures проверяют оба endpoint с заявкой и без неё; реальная
foreign data/ не читалась. Источники: response_plan_session.py schema validator,
d2_dialogue_store.py read, app.py error handlers.

Focused независимый Checker D2-112: PASS по коду, pytest сам не запускал.
Cursor, общий CI и browser acceptance остаются открытыми. Provider/live/SMTP
0; staging пуст, commit/push/PR не выполнялись.
