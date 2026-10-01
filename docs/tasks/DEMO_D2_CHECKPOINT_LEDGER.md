# D2 Checkpoint Ledger — таблица подтверждённых фактов

## Draft — 2026-10-01: D2-SIM-DOC, актуальная сверка

Дополнение по запросу владельца после первого документального PASS: SIM-1
исключает повторную классификацию; SIM-2 сокращает контракт и не требует
дробления связной речи; SIM-2/3 проектируются совместно через существующий
completion/projection, объём связан с услугой; SIM-4 требует механизма,
поведения неподтверждённой части и оценки сложности; каждый SIM доказывает
свой результат до закрытия. Согласованы Roadmap/Contract/Acceptance и инструкции
исполнителя/Checker; конкретный scope итерации — в текущей карточке.
Baseline неизменён `0691217`; до этой итерации 15 документов уже изменены,
staging пуст. Старый PASS не заявляется проверкой дополнения; независимый
review дополнения выполняется отдельно, внешний Cursor ещё впереди.

Документальный checkpoint по верхнему разделу Audit Followup Task (15 путей).
Baseline `0691217b888b92b49ba2c288452ed8a053f31206`, active branch
`codex/d2-stage1-contract`; fresh fetch origin подтвердил tracking 0/0,
main `141ce91fb1731cd990fcf8391550150016c73e7f`, ahead/behind 101/0.
AF-1a `4e435ce` и AF-1b `0691217` опубликованы; это не новая аттестация runtime.
Девять ранее изменённых правил сохранены в общем diff; staging пуст,
foreign `data/` и маркетинговая памятка не затронуты, worktrees не менялись.

ACCEPTANCE: правила в начале Roadmap; D2-107–109, новый C03/S01–S06;
текущий статус и порядок SIM-0–5/REC-5, явные границы нерешённых деталей.
Astra read-only: подтверждены конфликт старого финансового допуска,
необходимость утверждённых обзорных offers и память контактного отвлечения.
Её рекомендация не является GO. D2 ROUTE/LEGACY IMPACT: только документация;
удаление runtime-зависимостей не заявляется. Tests/live/provider/SMTP: 0;
проверки diff/ссылок и независимый Checker — перед передачей. Cursor pending;
commit/push новых документов не выполнялись. FUTURE SCOPE — runtime карточки.
Исторические Draft ниже читаются на их дату, не как текущее разрешение.

## Draft — 2026-10-01: D2-ARCH-RULES

Baseline HEAD/local origin `0691217b888b92b49ba2c288452ed8a053f31206`,
ветка `codex/d2-stage1-contract`, Git root `C:\Cursor Projects\artgents-bot-active`;
локальные `origin/main`/merge-base `141ce91fb1731cd990fcf8391550150016c73e7f`.
Tracked diff/staging до работы пусты; foreign untracked `data/` и
`docs/MARKETING_ANSWER_SCENARIOS.md` сохранены. Тип изменения — документация.
Owner GO: закрепить согласованные правила упрощения и строгую проверку Cursor.
Точный write allowlist: `AGENTS.md`, `docs/WORKFLOW_CHECKER.md`,
`docs/tasks/DEMO_D2_TARGET_CONTRACT.md`, `docs/tasks/DEMO_D2_EXECUTION_LOCK.md`,
`docs/tasks/DEMO_D2_CODEX_EXECUTOR_PROMPT.md`,
`docs/tasks/DEMO_D2_CURSOR_CHECKER_PROMPT.md`, этот Ledger,
`.cursor/rules/00-guardrails.mdc`, `.cursor/agents/checker.md`.
Allowlist расширен с объяснением до правок двух действующих инструкций Cursor:
alwaysApply guardrails подключает критерий, агент Checker устраняет task-only
ограничение. Схема ответственности в них не копируется.

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-ARCH-RULES | **ACCEPTANCE:** единая схема ответственности в Target Contract §3; архитектурное изменение требует «до → после → удаляется», единственного владельца и доказательств по вызываемому коду и целому диалогу. Bug fix и документация отделены от runtime-упрощения. Checker/Cursor обязаны отклонять сохранённую или перенесённую заявленную зависимость; узкая карточка/FUTURE SCOPE не обходят критерий. **D2 ROUTE / LEGACY IMPACT:** документальные правила; runtime не менялся, удаление его зависимостей не заявляется. **OWNER DECISION:** явный запрос владельца 2026-10-01; схема не требует повторного согласования на каждой малой правке. **Evidence:** сверены действующие AGENTS, Lock, контракт, процесс исполнителя и Cursor prompt; приоритет task-first в общем Checker приведён к Lock §6. Новых документов и review-кругов нет. **Test isolation:** документация; pytest/бот/provider/live/SMTP 0. **FUTURE SCOPE:** реализации по обновлённым правилам после согласования конкретных карточек; этот checkpoint не разрешает runtime-правки и не закрывает AF-1a/1c/2 или REC-5. | Draft до независимого Checker и внешнего Cursor review; проверки ссылок и diff выполняются перед review. Staging пуст; commit/push не выполнялись. |

## Draft — 2026-09-30: реализация D2-AF-1b

Baseline HEAD/local origin `4e435ce8006cc2df07930a40d058f278469a99f6`,
ветка `codex/d2-stage1-contract`, Git root `C:\Cursor Projects\artgents-bot-active`;
локальный `origin/main`/merge-base `141ce91fb1731cd990fcf8391550150016c73e7f`.
Implementation GO и точный 11-file allowlist — в
[карточке AF-1b](DEMO_D2_AF1B_CONTACTS_TASK.md). Foreign `data/` и
`docs/MARKETING_ANSWER_SCENARIOS.md` не открывались и не stage.

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-AF-1b-IMPL | **ACCEPTANCE:** AF-02, узкая B09/D2-095/C02: конкретный typed contact field даёт точное значение текущего tenant, `contacts` — телефон+адрес+часы; absent parking — согласованный честный пробел, без телефона вместо неё. Несколько полей и независимая prose сохраняются. Typed `contact_branch_id` выбирает только названный филиал; без него обе адресные строки снабжены названиями, произвольной кнопки звонка нет. **D2 ROUTE / LEGACY IMPACT:** один `/ask`/`/ask/stream` D1R parser/provider → tenant facts → common materializer/frozen response/store; второго selector/parser/state/fallback нет. **OWNER DECISION:** после принятой карточки дан отдельный GO на AF-1b, но не на live/commit/push/merge/deploy. **Evidence:** новый HTTP набор 19 passed; соседний контактный/branch/mixed 19 passed/80 deselected; baseline и повтор тех же соседних сценариев 9 passed/те же 4 failed/9 deselected. Fake provider, temp DB/tenant/log, network blocked; provider/live/SMTP 0. **FUTURE SCOPE:** живое качество выбора полей, AF-1c/2 и REC-5. | Draft после Checker REJECT P1: пустой contact_fields теперь отклоняется; focused recheck и Cursor review впереди. Staging пуст, commit/push не выполнялись. |

## Draft — 2026-09-30: карточка D2-AF-1b после AF-1a

Git root `C:\Cursor Projects\artgents-bot-active`, ветка
`codex/d2-stage1-contract`, baseline HEAD/local origin
`4e435ce8006cc2df07930a40d058f278469a99f6`; локальный `origin/main` и
merge-base `141ce91fb1731cd990fcf8391550150016c73e7f`.
Перед правками tracked diff/staging пусты; foreign untracked `data/` и
`docs/MARKETING_ANSWER_SCENARIOS.md` оставлены без изменений. Write allowlist:
эта Draft-строка и [карточка AF-1b](DEMO_D2_AF1B_CONTACTS_TASK.md).

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-AF-1b-DOC | **ACCEPTANCE:** узкая B09/D2-095/C02 и AF-02; конкретный вопрос получает соответствующий точный tenant contact, несколько вопросов сохраняются, общий `contacts` — телефон+адрес+часы, WhatsApp/парковка по запросу; контакт не стирает независимую prose. **D2 ROUTE / LEGACY IMPACT:** только план для одного D2 provider/parser/materializer/store, без второго semantic selector/fallback. **OWNER DECISION:** согласованы оба адреса с названиями филиалов на общий вопрос, один адрес при названном филиале и честное «нет информации о парковке» при отсутствии этих сведений; другой контакт не подменяет отсутствующее поле. Implementation GO отсутствует. **Evidence:** read-only сверка AF-02, текущего `contacts → phone`/phone fallback, существующих typed fields и mixed contact+content; реализация, offline tests и live не запускались. **FUTURE SCOPE:** AF-1c/2, REC-5 и live quality. | Draft до focused Checker recheck и Cursor; runtime, commit/push, merge/deploy не разрешены. |

## Draft — 2026-09-30: реализация D2-AF-1a

Владелец уточнил текущий UI: после выбора услуги сразу цена, без кнопок
объёма; плановая цепочка «услуга → объём» неприменима к этому tenant.

Git root `C:\Cursor Projects\artgents-bot-active`, ветка
`codex/d2-stage1-contract`, baseline HEAD/local origin
`8cea81125cfc9ad8898b0e4ab43a6dc42bf15331`; `origin/main` и
merge-base `141ce91fb1731cd990fcf8391550150016c73e7f`.
Перед правками staging/tracked diff пусты. Foreign untracked `data/` и
`docs/MARKETING_ANSWER_SCENARIOS.md` не открывались и не stage.
Точный implementation allowlist и решения владельца — в
[карточке AF-1a](DEMO_D2_AF1A_PRICE_TASK_TASK.md).
После изменения scope отдельный набор context/scope/continuation дал
87 passed / те же 3 baseline failed из continuation; новых отказов нет.

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-AF-1a-IMPL | **ACCEPTANCE:** проверенный volume choice продолжает frozen price task с topic/service/brand; цена берётся из tenant snapshot, при отсутствии подходящего offer — честный пробел. Неверный `content/other` не убирает цену; пригодная prose сохраняется. Кнопка не создаёт личную `situation_state`: выбранный объём хранится в последнем frozen completion и TTL-gated projection следующего хода как контекст разговора, без второй памяти и угадывания по label/ref. **D2 ROUTE / LEGACY IMPACT:** один `/ask`/`/ask/stream` provider/parser/materializer/store; нового semantic selector, fallback или owner нет. **OWNER DECISION:** после read-only Astra владелец отменил self/other/hypothesis-ветвление AF-1a и согласовал расширение allowlist для typed recent scope; live/commit/push/merge/deploy не разрешены. **Evidence:** AF-1a HTTP 19 passed: JSON/SSE, бренд, четыре объёма, wrong kind, цена-gap, следующий provider input, TTL, смена темы, replay/conflict. Соседний набор 53 passed / 1 browser deselected / 1 старый failed: `test_d2_live_provider_offline.py` ожидает prompt v19, хотя HEAD уже v23. Pre-edit baseline 33 passed / 3 failed; после предыдущей правки тот же набор 33 passed / те же 3 failed. Browser harness до этого дважды дал `CDP timeout: Runtime.enable` до DOM assertions; это не browser PASS. Offline fixtures: temporary tenant/SQLite/log, сеть блокирована, provider/live/SMTP 0. **FUTURE SCOPE:** AF-1b/1c/2, полная A/B/C, REC-5 и разрешённое live-качество. | Draft до нового независимого Checker и Cursor review изменённого scope. Staging пуст; commit/push не выполнялись. После PASS reviewed diff не дописывать. |

## Draft — 2026-09-30: карточка D2-AF-1a после D2-AUDIT-PLAN

Git root `C:\Cursor Projects\artgents-bot-active`, ветка
`codex/d2-stage1-contract`, HEAD и локальная origin-ветка до правок
`fb81a9af2e1c4e654d9040013c3c6f528d89b5d4`; `origin/main` и merge-base
`141ce91fb1731cd990fcf8391550150016c73e7f`. Staging/tracked diff до
правок пусты; foreign `data/` и `docs/MARKETING_ANSWER_SCENARIOS.md`
сохранены. Write allowlist — эта строка и
[карточка AF-1a](DEMO_D2_AF1A_PRICE_TASK_TASK.md). Локальный `origin/*`
прочитан без нового fetch/remote-запроса. Историческая Draft
D2-AUDIT-PLAN ниже относится к прежнему `f4a08ea`, не к сегодняшнему HEAD.

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-AF-1a-DOC | **ACCEPTANCE:** подготовлен узкий план D2-094/A14 по AF-01, без закрытия A/B/C. **D2 ROUTE / LEGACY IMPACT:** только read-only сверка проверки UI ref, volume refs и существующего price path; runtime/legacy не менялись. **OWNER DECISION:** владелец разрешил подготовить карточку; implementation GO и точный code allowlist впереди. **Evidence:** прежний log prefix `a07cab18` дал описание без цены; статически на `fb81a9a` service-clarify binding не распространяется на volume-click; удачные fake-provider price tests не покрывают неверный kind. Это не новое воспроизведение живой моделью. **Test isolation:** документация, без pytest/бота/БД/сырых диалогов; provider/live/SMTP 0. **FUTURE SCOPE:** offline baseline, отдельный implementation GO, Checker/Cursor, AF-1b/1c/2 и REC-5. | Draft до независимого Checker и Cursor review карточки. Staging пуст; commit/push не выполнялись. После PASS reviewed diff не дописывать. |

## Draft — 2026-09-29: D2-AUDIT-PLAN после сохранённого REC-4-P2

Git root `C:\Cursor Projects\artgents-bot-active`, ветка
`codex/d2-stage1-contract`, baseline HEAD/local origin/GitHub branch
`f4a08ea75b284cb51291fd7fe6ca64d842d8e2d0`; main/merge-base
`141ce91fb1731cd990fcf8391550150016c73e7f`. GitHub проверен read-only
`ls-remote` в этой сессии; до правок tracked/staging пусты. Write allowlist —
шесть документов [карточки](DEMO_D2_AUDIT_FOLLOWUP_TASK.md). Foreign `data/`
и `docs/MARKETING_ANSWER_SCENARIOS.md` сохранены, не stage. Старая папка,
worktree и backup не менялись. БД/сырые логи не открывались в doc-checkpoint.

Предыдущая Draft P2 ниже относится к `abcb8ee` до review. Позже владелец
передал Cursor PASS: P2 HTTP 20 passed / 1 browser deselected; отдельный
browser 1 passed (26.76 s), четыре назначенных файла 65 passed / 15 прежних
failed; широкий адресный набор 118 passed / 1 deselected. После независимых
Checker/Cursor и разрешения сохранён `f4a08ea`. Это evidence прежних review,
не новый тестовый прогон; авторский CDP timeout не переписывается, visual
360/768, полный REC-5 и live-качество не объявляются закрытыми.

Процессное исключение `6c4a963`, ранее принятое владельцем: по передаче
статусные строки Full Audit Task/Ledger менялись после Cursor PASS, runtime
после review не менялся. История не исправляется задним числом; запрет
после-review правок остаётся. Это не выдача нового PASS тому checkpoint.

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-AUDIT-PLAN | **ACCEPTANCE:** актуальные указатели и links, точный Git baseline, разделение утверждённого поведения / audit findings / proposed scope; A/B/C не закрываются. **D2 ROUTE / LEGACY IMPACT:** без runtime изменений; статический вход D2 и старые файлы сверены, полного C08 proof здесь нет. **OWNER DECISION:** разрешена документальная сверка; proposed порядок AF-1a/b/c → AF-2 → общая приёмка, CTA/оформление/authored и остальные новые правила не утверждены. **Evidence:** read-only GitHub refs и ancestry; stale P2 статусы исправлены, исторические строки сохранены; Astra сверила архитектурные границы и приоритет D2-092/094/095/099/102/105/106. Marketing памятка прочитана для сверки, не изменена: её cap 3 и запрет detail UI не authority против поздних D2-100/102. **Test isolation:** только документация, pytest/бот/provider/live/SMTP 0; проверка local links и diff до review, без БД/сырых payload. **FUTURE SCOPE:** принятие проекта порядка, отдельные implementation cards/GO, REC-5 и разрешённое live-качество. | Draft до независимого Checker и Cursor. Staging пуст; commit/push этого checkpoint не выполнялись. После PASS Ledger не дописывать. |

## Draft — 2026-09-29: реализация REC-4-P2

Git root `C:\Cursor Projects\artgents-bot-active`, ветка
`codex/d2-stage1-contract`, baseline HEAD и origin branch
`abcb8ee2bad72ef5d5be689cb21964e63af8dfbc`; `origin/main` и merge-base
`141ce91fb1731cd990fcf8391550150016c73e7f`. До правок tracked diff и
staging пусты; чужие untracked `data/` и
`docs/MARKETING_ANSWER_SCENARIOS.md` сохранены. Предыдущая Draft карточки
ниже — её исторический снимок до Checker/Cursor PASS и commit/push `abcb8ee`.

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-REC-4-P2-IMPL | **ACCEPTANCE:** адресный A16/B19, затронутые A02/A05/B12/B14/B18/C01/C03–C05/C07/C09/C10, не весь REC-5. **D2 ROUTE:** `/ask`/`/ask/stream` → один parser для свободного вопроса или проверенный 0-call detail click → captured tenant offers → frozen detail block/action map в существующем плане → renderer/UI → store/replay. `price_detail_ids` 0–2 в существующем профиле, demo `classic` с обеими кнопками только при полных данных всех показанных offers; прямой вопрос независимо от настройки читает опубликованные данные даже при выключенном followup и называет реальные пробелы. Состав и платежи из captured offer, одинаковое общее один раз, разные графики отдельно; RUB формат P1. Lead pause вытесняет detail-кнопки. Astra нашла три P1: старый набор offers после смены услуги, потерю независимой prose при неоднозначной detail и потерю exact contact рядом с detail. Checker добавил три границы: переход к другой услуге внутри того же multipart, разные явные услуги в price+detail и неоднозначный короткий вопрос после mixed ответа; исправлены проверкой текущих refs, локальной frozen gap-частью и общим multipart route. **LEGACY IMPACT:** второй parser/model call, semantic regex, старый price_aspect runtime, новый state owner и fallback не добавлялись. **OWNER DECISION:** D2-102, `classic` и code GO даны владельцем; commit/push отдельно. **Test isolation/evidence:** fake provider, временные tenant/DB/log, сеть заблокирована; baseline назначенных четырёх файлов до правок 59 passed / 15 failed, после правок 65 passed / те же 15 failed (6 новых schema-тестов). Адресный P2 HTTP JSON/SSE 20 passed / 1 browser deselected; P2 + lead + multipart + price-scope 76 passed / 1 browser deselected. Отдельный browser harness 1 failed из-за `CDP timeout: Runtime.enable` до проверки widget assertions; локальный Chrome открывает WebSocket, но не отвечает на команду, виджет не объявлен проверенным. Provider/live/SMTP 0, бот не запускался. **FUTURE SCOPE:** независимый Checker, Cursor, browser/widget proof, REC-5 и отдельно разрешённое качество модели/live. | Draft до независимого Checker и Cursor review реализации. Staging пуст; commit/push не выполнялись. После PASS Ledger не дописывать. |

## Draft — 2026-09-29: подготовка карточки REC-4-P2

Git root `C:\Cursor Projects\artgents-bot-active`, ветка
`codex/d2-stage1-contract`, baseline HEAD и origin branch
`71d746793ffbd3ef796ae81cd6d0eae09d8cfd69`; `origin/main` и merge-base
`141ce91fb1731cd990fcf8391550150016c73e7f`. До правок tracked diff и
staging пусты. Чужие untracked `data/` и
`docs/MARKETING_ANSWER_SCENARIOS.md` сохранены. Нижняя Draft реализации
D2-LEAD-INTERRUPT — снимок до её Checker/Cursor PASS и commit/push `71d7467`,
не текущий Git-status.

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-REC-4-P2-DOC | **ACCEPTANCE:** план A16/B19 и затронутых A02/A05/B12/B14/B18/C01/C03–C05/C07/C09/C10; runtime P2 ещё не проверен. **D2 ROUTE:** документально сверены действующие `/ask`/`/ask/stream`, tenant snapshot, один parser/frozen plan/store/replay и typed UI, без изменения runtime. **LEGACY IMPACT:** старый price_aspect selector, semantic regex и fallback не разрешаются. **OWNER DECISION:** D2-102 и варианты нескольких/частичных offers утверждены; владелец выбрал обе кнопки у `classic` при полном наборе данных, остальные услуги выключены; GO на код впереди. **Test isolation/evidence:** read-only Git/код/документы и demo commercial/offer inventory: три `classic.one_tooth.*` имеют includes/stages/followups, runtime captured set ещё не доказан; pytest, бот, provider/live/SMTP 0. **FUTURE SCOPE:** P2 implementation, Checker/Cursor, REC-5 и отдельно разрешённое live-качество. | Draft до независимого Checker и Cursor review карточки. Staging/commit/push не выполнялись; после PASS Ledger не дописывать. |

## Draft — 2026-09-29: реализация D2-LEAD-INTERRUPT

Git root `C:\Cursor Projects\artgents-bot-active`, ветка
`codex/d2-stage1-contract`, baseline HEAD и локальный origin branch
`43c0aba362403ac144e88809e4f8ff5a81e6bc2a`; `origin/main` и merge-base
`141ce91fb1731cd990fcf8391550150016c73e7f`. До правок tracked diff и
staging пусты; чужие untracked `data/` и
`docs/MARKETING_ANSWER_SCENARIOS.md` сохранены. Allowlist и решение владельца —
[карточка](DEMO_D2_LEAD_INTERRUPT_TASK.md). Нижняя Draft карточки — снимок до
её Checker/Cursor PASS и commit/push `43c0aba`, не текущий Git-status.

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-LEAD-INTERRUPT-IMPL | **ACCEPTANCE:** A12/B11/C05–C07 проверяются на D2 HTTP; это не полный REC-5. **D2 ROUTE:** current tenant/revision `lead:pending:answer` берёт сохранённый вопрос только у bound lead owner, существующий privacy scrub идёт до единственного provider/parser, обычный D2 сохраняет ответ и typed resume/cancel в одном completion. После D2 commit lead owner одним row write переходит в paused; replay/следующий запрос согласует post-commit gap только для последнего completion и той же версии pending-вопроса. Старый replay не стирает новый pending. Resume восстанавливает исходный name/phone без provider, cancel чистит ПД. В paused ответах CTA скрыта, выход к записи остаётся в frozen UI. **LEGACY IMPACT:** старый answer→resume runtime не вызывался; semantic regex/второй parser/state owner не добавлены. **OWNER DECISION:** ответ + явный resume и code GO даны владельцем после Cursor PASS карточки; D2-106. **Test isolation/evidence:** fake provider, временные tenant/SQLite/log, сеть заблокирована; адресный HTTP JSON/SSE 15 passed, соседние lead/HTTP 18 passed, документный клик 16 passed. Provider/live/SMTP 0. Рабочие БД/логи не открывались. **FUTURE SCOPE:** общий hard-crash `inflight` без lease/recovery остаётся отдельным ограничением D2; REC-4-P2 и REC-5 впереди. | Draft до независимого Checker и Cursor review реализации. Staging пуст; commit/push не выполнялись. После PASS Ledger не дописывать. |

## Draft — 2026-09-28: карточка D2-LEAD-INTERRUPT

Папка/Git root `C:\Cursor Projects\artgents-bot-active`, ветка
`codex/d2-stage1-contract`, baseline HEAD и локальный origin branch
`b39ed36cdbc57f608da1c199cf45ce938e70b6dc`; `origin/main` и merge-base
`141ce91fb1731cd990fcf8391550150016c73e7f`. До правок tracked diff и
staging пусты. Чужие untracked `data/` и
`docs/MARKETING_ANSWER_SCENARIOS.md` сохранены. Точный документальный
allowlist — [карточка](DEMO_D2_LEAD_INTERRUPT_TASK.md). Нижняя Draft строка
указателя — снимок до его Checker/Cursor PASS и сохранения в `b39ed36`;
Ledger после её review не переписывали.

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-LEAD-INTERRUPT-DOC | **ACCEPTANCE:** план A12/B11/C05–C07; runtime пока не проверен. **D2 ROUTE:** read-only разобраны D2 pre-provider lead bridge, pending/resume, обычный D2, UI revision, HTTP replay и существующая очистка ПД. **LEGACY IMPACT:** старый answer→resume путь только историческая сверка, не fallback. **OWNER DECISION:** требуется выбор поведения после «Ответить» и отдельный GO на код по Execution Lock §4. Astra read-only рекомендовала ответ + typed resume к прежнему name/phone. **Test isolation/evidence:** widget trace `40820dcb` → `96b02f07`; исходный D2 bridge стирает pending и повторяет слот, provider attempts 0. Сырые сообщения и БД не перенесены. Только чтение кода/документов, pytest/бот/live/provider/SMTP 0. **FUTURE SCOPE:** отдельный implementation preflight и allowlist, offline HTTP/PII/replay tests, Checker/Cursor, REC-4-P2, REC-5. | Draft до независимого Checker и Cursor review карточки. Staging пуст; commit/push не выполнялись. После PASS Ledger не дописывать. |

## Draft — 2026-09-28: указатель текущего состояния D2

Папка/Git root `C:\Cursor Projects\artgents-bot-active`, ветка
`codex/d2-stage1-contract`, baseline HEAD и локальный origin branch
`e246f1e7132596e20b8f81db7bc911855678ad8e`; `origin/main` и merge-base
`141ce91fb1731cd990fcf8391550150016c73e7f`. До правок tracked diff и
staging пусты. Чужие untracked `data/` и
`docs/MARKETING_ANSWER_SCENARIOS.md` сохраняются. Точный allowlist и владелец
решения — [карточка](DEMO_D2_CURRENT_STATUS_INDEX_TASK.md). Предыдущая Draft
D2-DOC-CLICK ниже — историческая строка до его Checker/Cursor PASS и commit/push
`e246f1e`, не текущий Git-status; после review её не переписывали.

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-CURRENT-STATUS | **ACCEPTANCE:** корректный указатель и ссылки, без закрытия A/B/C. **D2 ROUTE / LEGACY IMPACT:** код и маршруты не меняются. **OWNER DECISION:** владелец согласовал отдельный порядок в документах; lead-исправление требует отдельной карточки и решения. **Test isolation/evidence:** read-only Git/документы и полный локальный журнал; `40820dcb` фиксирует pending choice, `96b02f07` — клик `lead:pending:answer`, запрос имени и 0 provider calls. `core/d2_lead_bridge.py` явно реализует возврат к слоту. В новый checkpoint не включены сырые сообщения, PII или БД. Документальные ссылки и diff проверить до Checker; runtime pytest не требуется. Provider/live/SMTP 0, бот не запускался. **FUTURE SCOPE:** отдельная карточка lead-прерывания и исправление после согласования, REC-4-P2 после нового preflight/GO, REC-5 и live-качество. | Draft до независимого Checker и Cursor review. Staging пуст, commit/push не выполнялись; после PASS Ledger не дописывать. |

## Draft — 2026-09-28: D2-DOC-CLICK перед возвратом к REC-4-P2

Папка/Git root `C:\Cursor Projects\artgents-bot-active`, ветка
`codex/d2-stage1-contract`; baseline HEAD и локальный origin branch
`a930ed70df9d2d709cc36b9076be55659485c582`. `origin/main` и merge-base
`141ce91fb1731cd990fcf8391550150016c73e7f`. Это принятый Checker/Cursor и
сохранённый с разрешения владельца REC-4-P1; его нижняя Draft-строка — снимок
до review, не нынешний Git-status. До этой коррекции tracked/staging пусты.
Чужие untracked `data/` и `docs/MARKETING_ANSWER_SCENARIOS.md` сохранены;
БД не открывались. Точный allowlist —
[D2-DOC-CLICK](DEMO_D2_DOCUMENT_CLICK_TASK.md). Старые строки не переписываются.

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-DOC-CLICK | **ACCEPTANCE:** срез A03/B12/B15/B20/C01, не полный REC-5. Проверенный документный action с section_title из captured snapshot поступает в единственный provider input/prompt до генерации; текущий вопрос по клику отделён от истории, q остаётся пустым. В production parser omitted mode для непустого content/other становится model_prose; explicit authored/invalid/null и empty other сохраняют прежние правила. **D2 ROUTE:** JSON/SSE → текущий проверенный action → provider prompt → production parser → прежние materializer/source/CTA → store/history/replay. **LEGACY IMPACT:** второго parser/call, semantic regex, замены prose абзацем MD, нового state owner или legacy fallback нет. **OWNER DECISION:** GO на обе коррекции и документы перед возвратом к ценам; Astra read-only подтвердила эту ограниченную архитектуру. **Test isolation/evidence:** fake provider, временные DB/tenant/logs, запрет сети; BOT_LOG_DIR до imports. Чистый baseline до правок: R1/REC2/envelope-correction 54 passed / 1 failed (исторический other). Те же три файла плюс новый HTTP-набор после правок: 71 passed; прежний other тест проходит без изменения. Соседние scope/lead/replay/B14/fullcontext/offtopic/free-dialogue: 20 passed / 3 failed. Все три воспроизведены теми же assertions в чистом tracked архиве a930ed7 во временной папке: test_offtopic_polite_refuse_from_ui_yaml — patient_text_required; test_greeting_prose_is_not_replaced_by_guided_menu — d2_experiment_content_not_resolved (fixture явно задаёт authored); test_available_contact_leaves_an_unavailable_information_part_degraded — нет INFO_GAP. Тесты не ослаблены. Первые два запуска baseline-архива не собрали tests из-за отсутствия локального CHAT_API_KEY; после фиктивного offline key сравнение состоялось, реальные credentials не копировались. Provider/live/SMTP 0, бот не запускался; browser harness не запускался. **FUTURE SCOPE:** качество настоящей генерации и отсутствие смысловых повторов проверять отдельно с GO/бюджетом; fake ответы доказывают передачу задания и сохранение prose, а не качество модели. REC-4-P2 — после принятого checkpoint и отдельного GO. | Draft до независимого Checker и отдельного Cursor review. Staging пуст, commit/push не выполнены и требуют отдельного разрешения. После PASS Ledger не дописывать. |

## Draft — 2026-09-28: REC-4-P1 компактное оформление цен

Рабочая папка/Git root `C:\Cursor Projects\artgents-bot-active`, ветка
`codex/d2-stage1-contract`; baseline HEAD и локальный origin branch
`04657f10e6e01162e9513a602424dbcccb594ac2` (после Checker/Cursor PASS,
разрешённого commit/push документального checkpoint REC-4-P). `origin/main`
и merge-base `141ce91fb1731cd990fcf8391550150016c73e7f`. До P1 tracked
diff/staging чисты; чужие untracked `data/` и
`docs/MARKETING_ANSWER_SCENARIOS.md` не менялись. Git предупреждал о
недоступных global ignore и `.pytest_cache/`. Точный будущий P1 allowlist —
§4 [карточки REC-4-P](DEMO_D2_PRICE_PRESENTATION_DETAILS_TASK.md); новый
`tests/test_d2_price_presentation_http.py` входит в него.

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-REC-4-P1 | **ACCEPTANCE:** срез A02/A05, B18 и регрессий B12/B14, C03–C05/C07/C09/C10; не полный A16/B19/REC-5. У точной услуги проверенные frozen service/variant/price поля дают короткий список, общие точные условия один раз, частные остаются у offer; RUB в формате `20 000 ₽` с NBSP. У overview остаётся один authored факт зависимости от протокола/объёма и choices. `patient_text` для ANSWER с реально разрешённой ценой — 0–1 optional live intro из одного model call, перед ценой; независимые content parts в порядке requests. Ordinary history хранит всю живую prose, не копирует code-owned цену; replay сохраняет итоговый ответ. **D2 ROUTE:** офлайн `/ask`/`/ask/stream` → единый production envelope/parser → captured tenant snapshot → materializer/frozen plan → renderer/UI → store/replay; browser harness с fake D2 payloads и штатным CSS. **LEGACY IMPACT:** второго model call/parser, semantic regex, старого assembler/fallback или нового state owner нет. **OWNER DECISION:** владелец подтвердил Cursor PASS карточки, отдельно разрешил doc commit/push и дал GO на P1; решения D2-101/103 и границы D2-092/B14 действуют. Astra ранее read-only проверила reuse existing `patient_text` и history boundary. **Test isolation/evidence:** на чистом baseline назначенный набор 28 passed; после P1 адресные пять файлов 39 passed, соседние request order/memory/UI 10 passed, B14 оба порядка 3 passed, headless Chrome widget 1 passed, `node --check`/Python compile/diff check clean. Визуально осмотрены временные скриншоты 360/768 px: список/переносы без горизонтального overflow. Первый baseline pytest без явного basetemp дал 9 setup errors из-за прав на стандартную temp-папку; с отдельным temp 28 passed. Исторический `test_price_content_price_preserves_independent_content_and_request_order` по-прежнему падает: отсутствует «Материал терапии.» (0 вместо 1); тест не менялся и не скрыт; прежнее evidence REC-4 уже сравнивало этот ID с чистым HEAD, на чистом `04657f1` отдельно не воспроизводили. Fake provider, временные tenant/DB/log/Chrome profile, локальная сеть браузера, provider/live/SMTP 0. **FUTURE SCOPE:** P2 exact details/buttons только после принятого P1 и отдельного GO, полный A16/B19/REC-5, старый multipart/content разрыв, живость optional intro в реальном widget/live только по отдельному разрешению и бюджету. | Draft до независимого Checker реализации и отдельного Cursor review. Staging/commit/push P1 не выполнены. После PASS Ledger не дописывать. |

## Draft — 2026-09-28: карточка REC-4-P и согласование документов

Папка/Git root `C:\Cursor Projects\artgents-bot-active`, ветка
`codex/d2-stage1-contract`; HEAD и локальный origin branch
`b02db8ee010b3431ab24f6e3ef98e5392a591673`, `origin/main` и merge-base
`141ce91fb1731cd990fcf8391550150016c73e7f`. До правок tracked/staging чисты;
чужие untracked `data/` и `docs/MARKETING_ANSWER_SCENARIOS.md` сохранены.
Git предупреждает о недоступных global ignore/`.pytest_cache/`; свежего fetch
не было. Семь разрешённых doc paths перечислены в §1
[карточки REC-4-P](DEMO_D2_PRICE_PRESENTATION_DETAILS_TASK.md).
Предыдущая строка REC-4 ниже — snapshot **до** его review, не текущий status:
его последующий Checker/Cursor PASS и сохранение относятся к `b02db8e`.
Старые строки, включая процессное исключение `6c4a963`, не переписываются.

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-REC-4-P-DOC | **ACCEPTANCE:** план A16/B18/B19 и регрессий, без runtime PASS. **D2 ROUTE:** read-only изучены текущие materializer/renderer, Markdown widget, service profile, offer details и ordered shown refs; код не изменён. **LEGACY IMPACT:** старый widget-format текст явно отделён от текущего D2; legacy selector/runtime не подключается. **OWNER DECISION:** согласованы D2-101–103; владелец отдельно выбрал детали всех показанных вариантов и скрытие кнопки при неполных данных, сохраняя прямой вопрос. Astra выполнила read-only архитектурный разбор; карточка делит реализацию на P1/P2 с точными allowlists и отдельными GO. Синхронизированы Decisions/Target/Acceptance/Roadmap/Widget Format. **Test isolation/evidence:** только чтение репозитория и документальные проверки, pytest/бот не запускались, provider/live/SMTP 0; БД/логи не открывались. Старые REC-4 75/10 — исторический отчёт Cursor, не новый прогон и не доказательство baseline будущей реализации. **FUTURE SCOPE:** код P1/P2, отдельные reviews, REC-5/A15, ручной/live тест с разрешением. | Draft до независимого Checker и отдельного Cursor review. Staging пуст; commit/push не разрешены и не выполнены. Ledger после PASS не дописывать. |

## Draft — 2026-09-28: REC-4 короткие цены и кнопки

Рабочая папка и Git root `C:\Cursor Projects\artgents-bot-active`, ветка
`codex/d2-stage1-contract`, baseline HEAD и локальный origin branch
`cebd09bd0deca0dd5c52fd0b3c4b70d6ef8dc654`; `origin/main` и merge-base
`141ce91fb1731cd990fcf8391550150016c73e7f`. Перед реализацией tracked
diff и staging пусты. Чужие untracked `data/` и
`docs/MARKETING_ANSWER_SCENARIOS.md` не правились и не stage. Карточка REC-4
была untracked и входит в checkpoint. Полный точный write allowlist — § «Точный
write allowlist будущей реализации» [карточки REC-4](DEMO_D2_REC4_PRICE_BUTTONS_TASK.md),
включая три отдельно разрешённых старых test-файла. Владелец отдельно
разрешил обновить в них проверку краткой цены и проверку опубликованного
объёма удаления зуба; остальные изменения в этих файлах касаются CTA.

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-REC-4 — краткие цены и кнопки | **ACCEPTANCE:** срез A01/A02/A07/A09/A10/A13/A14/A15, B06/B08/B12/B13/B14/B16/B17, C04/C05/C07/C09/C10 только в границе REC-4: одна точная услуга показывает все применимые опубликованные offers текущего tenant по возрастанию, включая четвёртую временную позицию, с именем варианта, scope и обязательными оговорками; первый ответ не перечисляет состав пакета и этапы оплаты, но они остаются в captured offer. Общий authored обзор до трёх цен и четыре кнопки объёма; follow-up подпись без якоря при сохранённом section ref; CTA документа приоритетна, иначе разрешённая нейтральная `default_consult`, без auto-lead. **D2 ROUTE:** offline JSON/SSE → один production parser → captured tenant snapshot и price/UI authority → frozen plan/render/store/replay → существующий widget/lead owner; цена и CTA не извлекаются из прозы модели. **LEGACY IMPACT:** второго prompt/parser, semantic regex, старого runtime, fallback и второго owner состояния нет; JSON/SSE и lead/privacy wire не менялись. **OWNER DECISION:** владелец подтвердил D2-100: для одного точного вопроса нет лимита три; общий обзор и B14 остаются отдельно. Владелец дал GO реализации и разрешил перечисленные расширения старых тестов; Astra дала read-only архитектурное заключение. **Test isolation:** fake provider, временные tenant copy/DB/logs, блокировка внешней сети; рабочий `data/` не открывался на запись, provider/live/SMTP 0. **Evidence:** адресный REC-4/price/snapshot набор 37 passed; широкий набор семи файлов на clean HEAD 61 passed / 9 failed и на REC-4 diff 61 passed / 9 failed с теми же девятью test IDs; B14, lead CTA, stale/forged и запреты CTA 6 passed, 1 failed. Последний `test_price_content_price_preserves_independent_content_and_request_order` падает тем же assertion на clean HEAD. Старые девять: doctor authored `patient_text_required`, history `spam_closed`, три старых content/source assertions и четыре старых snapshot/scope assertions; тесты не скрыты и не ослаблены. **FUTURE SCOPE:** REC-5 полная приёмка и ручная widget-проверка, отдельный анализ старых красных тестов, возможный показ большого каталога частями, live/merge/deploy. Это не полный A15/REC-5. | Draft до независимого Checker и отдельного Cursor review реализации. Staging, commit и push не выполнялись. После PASS Ledger не дописывать. |

## Draft — 2026-09-26: коррекция model envelope и подписи цены

Baseline `28ff60a4f51228dec1409e7b703cd279ea2dcee7`, ветка
`codex/d2-stage1-contract`; origin branch совпал, `origin/main` и merge-base
`141ce91`. До работы tracked/staged diff пуст. Чужой untracked `data/`
сохранён; лог теста владельца прочитан только для диагностики. Точный
allowlist — [карточка коррекции](DEMO_D2_ENVELOPE_CORRECTION_TASK.md).

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-ENVELOPE-CORR | **ACCEPTANCE:** B14/D2-080/T2, C01/R4 и подпись проверенной цены D2-093; не полный REC-4/5. **D2 ROUTE:** единственный действующий prompt явно отделяет самостоятельные вопросы текущего сообщения от пропущенного referent из истории; production parser по-прежнему отвергает `resolved` с null ID. Materializer замораживает имя услуги именно из `bundle.services[offer.service_id].name` рядом с price offer; renderer, числовые цены и условия не менялись. Widget преобразует только видимый `d2_invalid_turn` в человеческий текст; JSON/SSE error code остаётся, failed turn не commit ordinary/lead. **LEGACY IMPACT:** нового parser, второго call, semantic regex и старого fallback нет. **OWNER DECISION:** владелец разрешил отдельную коррекцию перед REC-4 и подпись услуги перед ценой; Astra дала read-only архитектурное заключение. **EVIDENCE:** три trace из карточки без копирования raw payload. До правок baseline 15 passed / 1 failed: старый prompt-version тест ждёт v19 при текущем v20; штатный browser fixture внутри sandbox истёк по timeout. После правок адресный набор 14 passed; расширенный набор 75 passed / 2 failed: старый `other` → `d2_experiment_content_not_resolved` и `test_price_content_price_preserves_independent_content_and_request_order`. Последний тест не менялся и повторил то же падение после удаления нового service-name префикса только в памяти процесса; это ограниченная изоляция, не clean HEAD baseline. Отдельный JSON/SSE tenant/replay тест 4 passed; browser harness с fake provider вне sandbox 1 passed. Сеть/provider 0, временные DB/logs. **FUTURE SCOPE:** REC-4 — краткость цены, повтор единицы, кнопки/CTA; REC-5 и отдельно разрешённый live eval; упрощение schema только новой карточкой. | Независимый Checker PASS: P0/P1 нет, его офлайн набор 16 passed. Cursor review ещё требуется. Staging/commit/push отсутствуют; после Cursor PASS Ledger не менять. |

## Draft — 2026-09-26: REC-3 память точной услуги

Baseline `279b21c3504b1c2ae999575e1f44eb85567d3ac7`, ветка
`codex/d2-stage1-contract`; локальный origin branch совпал, `origin/main` и
merge-base `141ce91`. До реализации tracked/staged diff пуст, чужой `data/`
сохранён. Точный allowlist — [карточка REC-3](DEMO_D2_RECOVERY_MEMORY_TASK.md),
включая отдельно разрешённый владельцем `core/response_plan_materialization.py`.

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-REC-3 — сохранение фокуса | **ACCEPTANCE:** точная услуга без topic сохраняется и связывается с одной следующей короткой ценовой частью, даже если модель не повторила ID; две разные ценовые услуги не превращают первую в фокус; одинаковые части оставляют однозначный фокус; CLARIFY service click сохраняет ценовую задачу; новая услуга и TTL не наследуют старую память или чужую ситуацию. Это REC-3, не полный A15/REC-5. **D2 ROUTE:** offline JSON/SSE → production parser → captured tenant/context → effective typed envelope → итоговый response plan и `session_delta` → ordinary state/store/replay. Первая цена, отложенная часть и UI сравнивались с одиночной ценой. **LEGACY IMPACT:** нового parser, semantic regex и fallback нет. **OWNER DECISION:** GO REC-3 и отдельное расширение allowlist для сборщика плана получены; Astra проверила две узкие коррекции после Checker REJECT. Исходный выбранный offline baseline: 70 passed / 1 failed (`spam_closed` в старом тесте истории). До Checker находок новый REC-3 и соседний набор: 84 passed / 1 failed (то же историческое падение); отдельные проверки границ 37 passed / 46 deselected. Затем Checker выявил два P1: короткая цена без повторного ID уходила в CLARIFY, а no-topic service click мог сохранять старую ситуацию/варианты. Оба случая воспроизведены красными HTTP-тестами до исправления. После исправления REC-3 + session-context: **73 passed**; REC-3 + session-context + multipart + R1: **91 passed / 1 failed**, старый `other` → `d2_experiment_content_not_resolved`. Более широкий промежуточный набор до P1-правок: 114 passed / 1 failed, старый тест истории; финальным aggregate его не считать. Вопрос о враче проверен через текущий `model_prose` с сохранённым service и replay; прежний `authored` directory path всё ещё отвергается, детерминированный справочник врачей этим checkpoint не подтверждён. Fake provider, временные DB/logs, live/provider/SMTP 0. **FUTURE SCOPE:** REC-4/5, отдельный разбор старых authored/`other` отказов, live/merge/deploy. | Draft. Первый независимый Checker review дал REJECT по двум P1; после их исправления требуется focused Checker recheck и отдельный Cursor review рубежа 3. Staging/commit/push не выполнены. Ledger после PASS не дописывать. |

## Draft — 2026-09-26: коррекция REC-2 D2-097/098

Baseline `7621441ca84e6bfc39fce79b744b647cc521a8b4`, ветка
`codex/d2-stage1-contract`; origin branch совпал, `origin/main` и merge-base
`141ce91`. Tracked/staged diff до работы пуст; чужой untracked `data/`
сохранён. Точный allowlist — § «Точный write allowlist» в
[карточке коррекции](DEMO_D2_REC2_CORRECTION_TASK.md).

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-REC-2-CORR | **ACCEPTANCE:** A03/B12/C01 и регрессии C04/C05/C07/C09/C10, не полный REC-5. **D2 ROUTE:** `/ask`/`/ask/stream`, один parser, captured tenant snapshot разрешает optional claims и проверенный document action в одном effective envelope **до** session binding; затем прежний materializer/frozen plan/store/replay. **LEGACY IMPACT:** запрещённый runtime/fallback не подключается. **OWNER DECISION:** владелец отнёс D2-097/098 к REC-2, после первого Cursor REJECT согласовал узкое правило для чистого документного клика и разрешил добавить Product Decisions в allowlist; D2-099 остаётся REC-4. До кода baseline: 2 passed / 18 deselected в узком HTTP-тесте. Новый P1-тест до fix: 6 failed / 1 passed. После fix и окончательного ограничения чистым кликом: целевой P1/source/multipart набор **18 passed / 44 deselected**, соседний widget/replay/lead/R1 набор **24 passed / 2 deselected**. Широкий aggregate шести файлов до последнего ограничения: **86 passed / 1 failed / 1 deselected**; красный `test_other_with_prose_gets_authored_help_not_price_gate` упирается в старый `d2_experiment_content_not_resolved` для `other`, описанный в исходной REC-2 карточке; тест не ослаблялся. В соседнем наборе исключены старый `other` и browser-case; browser в этом checkpoint не запускался. Тестовые DB/логи в `%TEMP%`, fake provider; live/provider/SMTP 0. **FUTURE SCOPE:** REC-3–5, live/merge/deploy и старые read-only падения REC-2 открыты. | Draft после Cursor REJECT; требуется focused Checker recheck находки и новый отдельный Cursor review diff до commit; staging пуст. Исторический PASS `bc76169` и прежний Checker PASS этой коррекции не переносятся на изменённый diff. |

## Draft — 2026-09-26: документальная фиксация widget-дефектов

Baseline `6c4a96339a2eb293fa3dc2b95e253ad6efedd1c9`, ветка
`codex/d2-stage1-contract`, `origin/main` и merge-base `141ce91`.
Перед правкой tracked/staged diff пуст; чужой untracked `data/` сохранён.
Точный write allowlist: этот Ledger, `DEMO_D2_PRODUCT_DECISIONS.md`,
`DEMO_D2_ACCEPTANCE.md`, `DEMO_D2_DELIVERY_ROADMAP.md`.

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-WIDGET-FINDINGS-DOC | **ACCEPTANCE:** только уточнённый план A03/B12/C01 и регрессии C04/C05/C07/C09/C10, без runtime PASS. **D2 ROUTE:** текущие `/ask`/`/ask/stream` не меняются. **LEGACY IMPACT:** код и старый runtime не меняются. **OWNER DECISION:** владелец попросил зафиксировать общий D2-сбой, связь CTA с документом и нейтральную CTA; отдельно подтвердил, что она показывается только в разрешённых D2-012 ответах. Полный локальный журнал подтвердил `d2_invalid_turn` (`276c9af0caf245bebc04fa56e65370d2`) и потерю source CTA (`f60977c81a8d4dc9a170496195526beb`); сырые переписки и ПД в commit не включаются. **FUTURE SCOPE:** владелец ещё определит место D2-097/098 в ограниченной карточке и даст отдельный GO; D2-099 проверить в REC-4; REC-3–5/live/merge/deploy не разрешены. | Draft до review. Независимый Checker ожидается; Cursor на требуемом рубеже отдельно. Документальный diff ещё не stage/commit/push; офлайн-тесты не запускались, provider/live/SMTP 0. Известные старые падения REC-2 не меняют статуса. |

## Дополнение — 2026-09-26: локальная полная D2-трассировка, offline-reviewed

REC-2 после отдельных независимых Checker и Cursor отчётов сохранён и отправлен
в `codex/d2-stage1-contract` как `bc7616999ed9fa2a9a3f74a3e7bdc8b47ba0e171`.
Его historical Draft ниже описывает состояние проверяемого diff до checkpoint.
Новый baseline: `bc76169`; staging до работы пуст, foreign `data/` не тронут.

По отдельному запросу владельца создаётся opt-in локальный полный журнал D2,
включая тестовые ПД. Он не заменяет REC-1 безопасные события и не разрешает
live/merge/deploy. Исторический `d2_full_audit.py` используется только как
reference writer; старый dialogue/HTTP runtime не переносится. Карточка:
[D2 local full audit](DEMO_D2_FULL_AUDIT_TASK.md). Код прошёл offline review:
последний полный прогон нового `tests/test_d2_full_audit.py` — **15 passed**;
связанный офлайн-набор full audit + diagnostics/HTTP/SSE/widget/no-legacy/lead
до последнего расширения маски credentials — **71 passed**. После расширения
отдельные 3 целевых теста также прошли; это не повтор общего набора.
Независимый Checker дважды указал на пробелы маскировки и перехода lead state;
после исправлений его focused recheck дал PASS. Переданный владельцем отдельный
read-only Cursor review также дал PASS: 15 новых и 67 связанных тестов прошли.
Статусы записаны после получения отчётов, не как предварительный вердикт.
Локальное включение журнала, live, merge и deploy отдельно не разрешены.
Fake provider и временные DB/log/tenant; provider/live/SMTP 0.

## Дополнение — 2026-09-26: реализация REC-2 на проверке

Active-папка `C:\Cursor Projects\artgents-bot-active`, ветка
`codex/d2-stage1-contract`, implementation baseline `ce47c16f564498165c1d00b2d0efd997dcbb9c22`.
Карточка получила внешние Checker/Cursor PASS, затем владелец дал отдельный GO
на реализацию. Это не PASS реализации. Staging/commit/push для текущего diff не
выполнены, live/provider/SMTP 0; foreign `data/` не менялся.

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-REC-2 — пригодная проза и optional provenance | **ACCEPTANCE:** C01–C03 и регрессии C04/C05/C08/C09/C10/A12; не полный REC-5. **D2 ROUTE:** `/ask`/`/ask/stream` → один parser → тот же materializer/plan/store. **LEGACY IMPACT:** fallback и semantic selector не добавлены. **OWNER DECISION:** GO на код REC-2 получен; REC-3/4 и live отдельно. На исходном baseline 8 файлов: 83 passed / 27 failed. Последний полный набор 10 файлов: 150 passed / 13 failed; после него точечно восстановлен прежний код ошибки неизвестной услуги (2 passed; новый полный aggregate не заявлен). Остаток — старые parser/R1 проверки (v19, прежний HTTP fixture/old `other` route). Новые собранные JSON/SSE, replay, follow-up, mixed, tenant/typed strict и review-sink сценарии проходят. Дополнительный read-only regression set без browser-case: 52 passed / 6 failed / 1 deselected; browser-case отдельно прошёл вне sandbox. Шесть read-only красных тестов не менялись из-за allowlist, список и причины — §9 карточки. | **Draft; ожидаются независимый Checker и Cursor именно implementation diff.** Не повышать исторический PASS, не записывать verdict в diff. Commit/push только после review и отдельного решения владельца. |

## Дополнение — 2026-09-26: REC-1 сохранён, REC-2 только планируется

В active-папке на `codex/d2-stage1-contract` по отдельному разрешению владельца
создан и отправлен `f4bae9b0b292026733854ae1d8fd34e608f953d5`
(`feat(d2): add safe REC-1 diagnostics`). Ровно девять проверенных файлов;
remote branch hash подтверждён ls-remote. Checker и Cursor отчёты REC-1,
включая late-clock дополнение, получены отдельно до commit; исторический
Draft ниже отражает состояние проверяемого diff до этих завершающих действий.
В этом шаге тесты повторно не запускались. Live/provider/SMTP 0.

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-REC-2-DOC — карточка ответов и ссылок | **ACCEPTANCE:** план C01–C03 и обязательные регрессии границ; никаких новых runtime PASS. **D2 ROUTE:** существующий, без изменения кода. **LEGACY IMPACT:** старый WIP не переносится. **OWNER DECISION:** разрешены документы, не реализация. **FUTURE SCOPE:** отдельный GO REC-2, REC-3–5/live. Baseline f4bae9b; allowlist — новая Recovery Content Task, Roadmap, Ledger. Проверены code-level места отказов и действующий D2-092. Тесты не запускались, provider/live/SMTP 0. | Draft; независимый Checker и Cursor review карточки ожидаются отдельными отчётами. Карточка не stage/commit/push; чужой data/ сохранён. |

## Текущее дополнение — 2026-09-25

Активная папка: `C:\Cursor Projects\artgents-bot-active`; ветка
`codex/d2-stage1-contract`; baseline документационного diff и runtime:
`e261383515d94e7d925acc705d8a6731aa704e48`.
`origin/main` / merge-base: `141ce91fb1731cd990fcf8391550150016c73e7f`.
Это журнал evidence, не самостоятельный план. Текущий порядок — в
[Delivery Roadmap](DEMO_D2_DELIVERY_ROADMAP.md); сохранённые источники и
ограничения аудита — в [inventory](DEMO_D2_RECONCILIATION_INVENTORY.md).

| Checkpoint | Scope и evidence | Review / оставшиеся ворота |
|---|---|---|
| D2-REC-1 — безопасная диагностика | **ACCEPTANCE:** диагностический срез C01/C05/C06/C09/C10; regressions C04/C08/A12, не C03/полное демо. **D2 ROUTE:** реальные JSON/SSE, прежние adapter/common turn/parser/materializer/store; attempt-local observer, без изменения ответа/state/wire. **LEGACY IMPACT:** старый runtime не добавлен. **OWNER DECISION:** отдельный GO на REC-1 и шесть test packages получен. **FUTURE SCOPE:** REC-2–5/live отдельно. Baseline `a185b54`; точные allowlist, manifest, команды и ограничения — §9 карточки. | Draft; verdict отдельными отчётами, тестовое дополнение требует focused recheck. Existing baseline: 38 passed / 2 failed (v19 expectation, sandbox browser timeout). Исторический implementation aggregate: 64 passed / 2 failed, browser прошёл; fixture уточнено, focused recheck 26 passed. Последующий полный прогон по переданному владельцем отчёту Cursor: 65 passed / 1 failed, 111 с; прежнее ожидание v19 вместо v20 остаётся. Затем добавлены шесть late-clock случаев без production-правок: focused diagnostics 32 passed, 20.84 с; нового полного aggregate после них нет. Подробности — §9 карточки. Provider/live/SMTP 0; staging пуст, commit/push не выполнены. |
| D2-REC-DOC — план восстановления и карточка диагностики | **ACCEPTANCE:** только документы; runtime-критерии не закрываются. **D2 ROUTE / LEGACY IMPACT:** без изменений кода, данных, wire и окружения. Allowlist: этот Ledger, Delivery Roadmap, Reconciliation Inventory и Recovery Diagnostics Task. **OWNER DECISION:** разрешена фиксация документов и передача в Cursor. **FUTURE SCOPE:** отдельный GO на REC-1 и проверка тестового окружения. Проверены ссылки, 36/36 inventory и отсутствие tracked diff вне allowlist; `git diff --check` чистый. Тесты не запускались по scope; provider/live calls 0; staging пуст. | Draft — ожидается независимый Checker и завершение Cursor review исправленного diff; checkpoint не закрыт, commit/push не выполнены. Вердикты сообщаются отдельными отчётами проверяющих, не записываются внутрь проверяемого diff. |

Исторические D2-S1–S4 и CP-записи ниже не переписаны и не повышены до нового
PASS. D2-S1 остаётся с незакрытым focused review; D2-S2 PASS не подменяет
отсутствовавший в его evidence полноценный pytest. Правило exact-service
из D2-S3 позднее изменено владельцем и реализовано в `7b8554f`: ascending
без лимита и зависимости от direction, с фильтрами brand/volume; обзор
направления по-прежнему отдельный. D2-S4 PASS относится к проверенному
mixed checkpoint, не ко всем целым диалогам текущей сборки.

Результат предыдущего выбранного offline-аудита — 147 passed / 11 failed,
не новая проверка этого документационного diff и не полный CI. Тесты
запускались на другом interpreter против active-кода; ограничения и
сравнения baseline перечислены в inventory. Общая демо-приёмка открыта.
Подготовительные документы ранее получили независимый review во временной
папке; этот результат не переносится автоматически на постоянный diff.

## Историческая запись этапа 0

Обновлено: 2026-09-24 для документального этапа 0. Это не roadmap и не
план: только факты с доказательствами. Текущая точка отсчёта — сохранённый
D2 HEAD `38fdeb3`; незакоммиченный WIP в основной папке не включён и не
получает здесь задним числом статус PASS. Правила ведения — в
[DEMO_D2_EXECUTION_LOCK.md](DEMO_D2_EXECUTION_LOCK.md). В будущем новая строка
добавляется в незакоммиченный diff **до** независимого review вместе с кодом и
тестами. Она называет checkpoint; фактический hash сообщается в финальном
closeout, потому что commit не может содержать свой собственный hash.

## Текущая точка отсчёта

На `38fdeb3` `app.ask` и `app.ask_stream` вызывают `run_d2_ask_json`, который
вызывает общий `run_d2_dialogue_turn`; widget подключён к `/ask/stream`.
FullContext-подготовка присутствует. Это подтверждает активность пути, но
не устойчивость ответов, корректность ценовых кликов или прохождение новой
приёмки A13–A15/C03. Отдельный этап 0 меняет только документы; его
Checker/Cursor verdict будет указан после проверки diff. Прежняя строка
`Current local runtime` и заключительная фиксация CP5 ниже сохраняются
как исторические снимки на момент их составления, а не текущие инструкции.

Исключение ниже отмечено явно: CP1 был уже закоммичен без строки Ledger. Его
факт добавлен отдельным документным correction checkpoint и не выдаётся за
часть исходного проверенного diff.

| Checkpoint | Что реально работает | Где вызывается | Статус legacy runtime | Что не доказано | Cursor verdict | Evidence commit / closeout |
|---|---|---|---|---|---|---|
| D2 component series C2–C15 | Отдельные D2 seams/детали: расширенный D1R envelope (части, typed situation), price modes, deferral, part failure, prose realization, tenant snapshot/sources, TTL-проекция, continuation binding, plan focus, cross-topic carry | Только изолированные unit/seam-тесты (`tests/test_d2_*`); из общего маршрута и HTTP не вызываются | Не затронут: `/ask` и виджет продолжают работать через legacy path | Полный пользовательский сценарий, сборка компонентов вместе, HTTP integration, реальная модель | PASS отдельных изолированных checkpoint (по журналу задач S2); сборку и сценарии не подтверждают | `b9e0de6`–`0f8e405` |
| S2-V0 A08 | Внутренний D2 route проходит **два хода A08** целиком: raw fake provider → production D1R parser → production tenant loader → resolver/materializer → text/UI → persistent typed SQLite state, включая close/reopen store; legacy Composer/sales_fast/вторая ordinary memory не вызываются (runtime observer); сеть запрещена; tenant isolation, TTL, invalid provider output и атомарность записи проверены | `core/d2_dialogue.py::run_d2_dialogue_turn`; вызывается только из `tests/test_d2_dialogue_a08.py` | Не затронут: legacy path остаётся единственным обслуживающим `/ask`/`/ask/stream`/widget | Подключение к `/ask`, `/ask/stream`, widget; реальная модель; replay результата по request_id; lead/privacy мост; все сценарии кроме A08 | **PASS** (независимый Checker этого checkpoint) | `8e7a3b6` |
| CP1 — D1R prompt-contract (late Ledger correction) | Единственный production prompt v17 явно требует для каждого request typed `service_id`, `topic_id`, `statement_mode` и `situation`; production parser принимает корректный raw A08 envelope и отвергает неверный enum `continuity` | `core/one_call_prompt_contract.py`; production parser проверен в `tests/test_request_understanding_schema_offline.py`; внутренний A08 test использует isolated tenant copy | Не затронут: legacy path остаётся единственным обслуживающим `/ask`/`/ask/stream`/widget | Approved demo tenant data, настоящая модель, HTTP/widget, replay/lead bridge и все сценарии кроме внутреннего A08 | **PASS** для исходного CP1 по отчёту независимого Cursor; данная строка требует отдельной проверки только как поздняя документационная коррекция | Original CP1 `7a0fa7c`; 20 targeted offline tests, provider calls 0 |
| CP2 — demo tenant data для A08 | Штатный `clients/demo` tenant pack содержит direction-level данные для `implantation` и `prosthetics`: порядок существующих прайс-карточек, цена/единица/обязательные условия и authored пояснения. Внутренний двухходовый A08 читает только temporary copy этого production pack через tenant snapshot, сохраняет один зуб при переходе темы и не берёт данные из test-only fixture | `core/d2_dialogue.py::run_d2_dialogue_turn` → `load_d2_tenant_snapshot` → `build_d2_snapshot_sources`; проверка в `tests/test_d2_dialogue_a08.py` | Не затронут: legacy path остаётся единственным обслуживающим `/ask`/`/ask/stream`/widget | Настоящая модель, HTTP/widget, replay/lead bridge и все сценарии кроме внутреннего A08 | **PASS** | `c195051`; 21 targeted offline tests, provider calls 0 |
| CP3 — ограниченная live-проверка A08 | Два точных последовательных хода A08 прошли через один production D1R parser и штатный demo tenant snapshot: `implantation` показала утверждённые три offer, затем `prosthetics` показало только `implant_supported_prosthetics.default` с перенесённым extent `one_tooth`. Совпадающий legacy duplicate канонизируется внутри единственной модели `RequestUnderstanding`; отличающийся по-прежнему отвергается. D2 follow-up instruction использует только typed `D2_SESSION_CONTEXT`, не создаёт новый tenant-data/wire/parser contract. | Только явно авторизованный internal runner `scripts/run_d2_a08_live.py` → `D2Cp3LiveProvider` → `run_d2_dialogue_turn`; данные — `clients/demo` через production loader/snapshot | Не затронут: `/ask`, `/ask/stream`, widget и legacy path не вызывались | HTTP/SSE/widget, другие A01–A12, replay/lead/privacy, deployment; результат не доказывает общий live runtime. Raw provider payload и текст не сохранены. | **PASS** | `8bfaf38`; 100 targeted offline tests; qwen3.8-flash, 2 explicitly authorized calls, no automatic retries; demo data baseline `c195051` |
| CP4 — common turn completion | Внутренний D2 route резервирует один `(tenant, sid, request_id)` до model call, атомарно фиксирует typed ordinary state и точный final result в одном `D2DialogueStore`, а повтор того же payload возвращает сохранённый result без model call. Иной payload с тем же request ID отклоняется; второй параллельный request того же session не становится final. PII-safe provider input использует существующий privacy boundary без обращения к legacy `session`. Явно переданный existing lead-effect сохраняется только как effect ID/status без контактов; после commit допускается ровно одна попытка dispatcher, ambiguous outcome остаётся `unknown` без automatic retry. | Только `core/d2_dialogue.py::run_d2_dialogue_turn` и `D2DialogueStore`; тестовый dispatcher не является HTTP/widget/lead UI entry | Не затронут: `/ask`, `/ask/stream`, widget, Composer, sales_fast и legacy runtime/selectors не вызываются | HTTP/SSE delivery/replay, реальный lead UI/transport, другие A01–A12, общий runtime, deployment; CP4 не меняет правила паузы/выхода/возврата lead flow и не создаёт пользовательский сценарий | **PASS** | `b1bf1a34304874c06ca1e6ea57c5a81714cd62db`; 124 targeted offline tests, provider/live calls 0 |
| CP5-A10a — same-topic price continuation | Внутренний common D2 route собирает два хода через production parser, штатный demo tenant snapshot, materializer/renderer и единый `D2DialogueStore`: после утверждённого A08 «один зуб / имплантация» короткий typed same-topic price follow-up сохраняет тот же extent и `situation_owner_id`, показывает те же утверждённые demo offer и условия. Перенос происходит только из fresh typed `carried_situation`; текст диалога не интерпретируется. Expired context не переносится. | Только `core/d2_dialogue.py::run_d2_dialogue_turn` → `build_d2_snapshot_sources` → `resolve_d2_envelope_response`; test копирует `clients/demo`, не fixture | Не затронуты `/ask`, `/ask/stream`, HTTP/SSE, widget, Composer, sales_fast, legacy runtime/selectors и fallback | Полный A10: новая пустая сессия, смена услуги, broad overview/volume choices; все другие сценарии, общий runtime и deployment | **PASS** | `b93dfc673c6bc59582dfe2abbf1339f3525ff2a7`; 129 targeted offline tests; provider/live calls 0 |
| CP5-B13a — simple direct service price | Внутренний common D2 route собирает один прямой вопрос о цене лечения кариеса через production parser, штатный demo tenant snapshot, materializer/renderer и единый `D2DialogueStore`. Он выбирает только единственную active offer данного сервиса прямо из snapshot, без legacy selector: сохраняются опубликованные «от», единица `tooth` и условие; промо/fact refs не допускаются к показу через этот checkpoint. | Только `core/d2_dialogue.py::run_d2_dialogue_turn` → `build_d2_snapshot_sources` → `resolve_d2_envelope_response`; test копирует `clients/demo`, не fixture | Не затронуты `/ask`, `/ask/stream`, HTTP/SSE, widget, Composer, sales_fast, legacy runtime/selectors и fallback | Несколько offer одного сервиса, промо/marketing facts, цена с обязательной metadata, A02 и иные прямые услуги; все другие сценарии, общий runtime и deployment | **PASS** | `b66dc5c9d04e0ff94e9a5d1e5773d1b651e86241`; 42 targeted offline tests passed (one known unrelated baseline failure excluded); provider/live calls 0 |
| CP5 governance — scenario/marketing simplification audit | Read-only аудит сохранил доказанные A08/A10a/B13a, выявил риск service-specific веток и перекрывающихся legacy marketing authority. Зафиксирован будущий D2 contract: один fact с short/full form, один service commercial profile, не более одного пакета усилителя и одного пакета «Также» на услугу (D2-090), compatibility groups и mechanism-based checkpoint batching. D2-O4 закрыто; числовые caps «Также 1–3» / «0–5» отменены. | Только документы governance; runtime, tests и tenant data не менялись | Legacy runtime/data не изменены. Старые marketing docs явно помечены как неканоничные для D2 | CP5-M1/M2/M3, A02/A11/B08, HTTP/SSE/widget и live не доказаны | Draft — ожидает independent Cursor review | Uncommitted documentation diff including D2-090; provider/live calls 0 |
| CP5-M1 — commercial data contract | Существующий `load_d2_tenant_snapshot` / `build_d2_model_view` читает D2 commercial contract из штатного `clients/demo/target_response/d2_commercial.json`: один promo fact ID с short/full, service profile (`promo_refs` ≤2, необязательные один `price_booster_id` и один `also_list_id`), пакет = имя + готовый текст, compatibility groups с `explanation_text`. Пустые/отсутствующие пакеты валидны. Повреждённые ID, чужой tenant, два booster/also, противоречивые short/full — `D2TenantSnapshotError`, без fallback. D2 не берёт `scenario_rules` / overlapping marketing lists как authority. | Только `load_d2_tenant_snapshot` → `build_d2_model_view`; proof в `tests/test_d2_commercial_contract.py`. Не `run_d2_dialogue_turn`, не HTTP/widget/materializer commercial plan | Не затронуты `/ask`, `/ask/stream`, widget, Composer, sales_fast, legacy selectors и fallback. Legacy `/ask` не расширялся | A02/A11/B08, CP5-M2 commercial plan, HTTP/SSE/widget, live, полные тексты клиники и визуал «Также» не доказаны | **PASS** | `d0975ffb8c82aec1c3d1df9e797dc7cca44cea74`; 18 targeted offline tests, provider/live calls 0 |
| CP5-M2 — common commercial plan | Внутренний common D2 route читает commercial contract из snapshot и до freeze кладёт в plan short promo, необязательный один пакет усилителя, необязательный один пакет «Также» и compatibility block с готовым текстом. Пустой профиль не ломает опубликованную цену. Auto-promo учитывает сохранённые shown IDs. Legacy `select_target_marketing` / `scenario_rules` не вызываются. Offer `fact_refs` больше не являются D2 commercial gate. | `run_d2_dialogue_turn` → `load_d2_tenant_snapshot` → `build_d2_snapshot_sources` → `resolve_d2_commercial_plan` → `resolve_d2_envelope_response` до freeze; proof в `tests/test_d2_commercial_plan.py` | Не затронуты `/ask`, `/ask/stream`, widget, Composer, sales_fast и fallback. Legacy marketing selector недостижим из D2 route | A02/A11/B08, визуал списка «Также», полные тексты клиники, HTTP/SSE/widget и live не доказаны | **PASS** | `d36ae7d806067b5ce0fc1d23c74a7b0dfceed164`; 23 targeted offline tests, provider/live calls 0 |
| CP5-M3 — assembled A02/A11/B08 | Внутренний common D2 route собирает A02 (цена отбеливания и отдельно виниров одним price profile без service-specific кода), A11 (полный прямой ответ об акциях услуги и общий список, повтор ранее показанной акции) и B08 (price profile, пакет «Также» с гарантией, compatibility group из двух видимых альтернатив). Auto использует короткую форму, direct promotion — полную. Просроченные promo не показываются. Legacy marketing selector не вызывается. | `run_d2_dialogue_turn` → `resolve_d2_commercial_plan` → `resolve_d2_envelope_response`; proof в `tests/test_d2_commercial_scenarios.py` | Не затронуты `/ask`, `/ask/stream`, widget, Composer, sales_fast и fallback | D2-017 обычный content+short promo без цены, визуал «Также», HTTP/SSE/widget, live и остальные CP5 семьи не доказаны | **PASS** | 45 targeted offline tests, provider/live calls 0 |
| CP5-C1 — content / direct-fact lookup | Внутренний common D2 route собирает lookup материала: A03 (страх будущей боли — `model_prose` по pain.md + source UI, video/follow-up не повторяются, CTA отдельно, до 2 коротких акций без booster/«Также»), A04 (прямой вопрос о гарантии — `model_prose` по `clinic__info__warranty.md` + follow-up/CTA документа, не полная форма `implant_warranty` и не пакет «Также», D2-091), B04 только механизм сравнения D2-034 (готовое сравнение → его текст/UI; два материала → нейтральные факты без follow-up; нет стороны → честный пробел без подмены), B15 (раздел ниже korotko, материал без korotko, нерелевантная резервная цитата не подменяет нужный раздел). Typed refs → grounded answer + source UI. | `run_d2_dialogue_turn` → `build_d2_snapshot_sources` → `resolve_d2_envelope_response`; proof в `tests/test_d2_content_scenarios.py`; test копирует `clients/demo`, не fixture | Не затронуты `/ask`, `/ask/stream`, HTTP/SSE, widget, Composer, sales_fast, legacy selectors и fallback | Две независимые информационные части в одном сообщении (D2-072), continuation/choice, directory/UI, terminal текущей боли, полный T3 prose repair, HTTP/SSE/widget и live не доказаны; гибрид гарантия model+fact отложен | **PASS** | `1be27e9`; voice correction D2-091; provider/live calls 0 |
| CP5-C2a — continuation/choice slice | Внутренний common D2 route собирает срез continuation/choice: A01 (обзор направления до 3 цен + 4 кнопки объёма; reported объём; hypothetical не переписывает факт; correction переписывает), A07 («Не знаю» после обзора — ориентир по цене + CTA `price`, без повторного scope-текста/volume-кнопок и без lead; кнопка «Рассказать о ситуации» в этом срезе не собиралась), TTL (после idle ambiguous follow-up не несёт expired situation). Volume labels из `ui.yaml` scope_nav. A10a не переписан. | `run_d2_dialogue_turn` → `build_d2_snapshot_sources` → `resolve_d2_envelope_response`; proof в `tests/test_d2_continuation_scenarios.py`; demo `d2_direction_prices.json` / `ui.yaml` | Не затронуты `/ask`, `/ask/stream`, HTTP/SSE, widget, Composer, sales_fast, legacy selectors и fallback | Полный A10 (пустая сессия / смена на отбеливание), полный B11 (смена человека), secondary «Рассказать о ситуации» (D2-022), multi-part, directory/UI, terminal, HTTP/SSE/widget и live не доказаны | **PASS** | `0e134fa`; provider/live calls 0 |
| CP5-C2b — A10 empty/switch + B11 person | Внутренний common D2 route: A10 пустая сессия «Сколько стоит?» → `CLARIFY` из `ui.yaml` continuation_clarify + guided_menu (без выдуманной цены); после имплантации «А отбеливание?» → только `professional_whitening.default`, без carry имплант-situation/цен (D2-032); B11 срез — `relation=other` даже с `continuity=same` не наследует `carried_situation` / owner (новый `situation_owner_id`). Lead consent / A12 / terminal вне среза. | `run_d2_dialogue_turn` → `build_d2_focus_clarify_response` / `bind_d1r_envelope_to_d2_context` → `resolve_d2_envelope_response`; proof в `tests/test_d2_continuation_scenarios.py` | Не затронуты `/ask`, `/ask/stream`, HTTP/SSE, widget, Composer, sales_fast, legacy selectors и fallback | Lead consent (D2-031), полный B11 (активная заявка/контакты после TTL, неповтор UI), All-on-4 как отдельный кейс, multi-part, directory/UI, terminal, HTTP/SSE/widget и live не доказаны | **PASS** | `48e8245`; provider/live calls 0 |
| CP5-MP — multi-part A05/A06/B14 | Внутренний common D2 route собирает составное сообщение: A05 (обзор цен имплантации + боль `model_prose`, без follow-up/видео боли), A06 (цена виниров + гарантия md без переноса услуги между частями), B14 (два ценовых вопроса — ответ на первый ≤3 offer, второй `deferred` с notice D2-080; цена+info сохраняет info). Смежно C02: пустой direct-service прайс → `d2_no_price_candidates`, живая content-часть сохраняется. Multi-topic parts не требуют единого session focus. | `run_d2_dialogue_turn` → production parser → `build_d2_snapshot_sources` → `resolve_d2_envelope_response` → `D2DialogueStore`; proof в `tests/test_d2_multipart_scenarios.py`; temporary copy `clients/demo` | Не затронуты `/ask`, `/ask/stream`, HTTP/SSE, widget, Composer, sales_fast, legacy selectors и fallback | Полный C02/C01, availability/policy, recovery, directory/UI, terminal/lead, две независимые info-части без цены (чистый D2-072-only), HTTP/SSE/widget и live не доказаны | **PASS** | `cf79475`; provider/live calls 0 |
| CP5-AP — availability/policy B01/B10 | Внутренний common D2 route: B01 — `bone_graft` `no_public_price` (approved_text, без суммы); понятая услуга без `content_ref` → info gap (D2-024), не «не оказываем»; typed authored alternative `braces→aligners` из `clinic_policies.yaml` в snapshot; inactive без alternative → тот же gap. B10 — `clinic_policy` по typed `policy_ids` / eligibility scheme / child subject → authored answers ОМС/ДМС/дети из snapshot; пустой policy → CLARIFY; неизвестный id → gap, не yes/no. Triggers/`match_clinic_policy_key` не вызываются. | `run_d2_dialogue_turn` → `build_d2_clinic_policy_response` / `build_d2_service_availability_response` / price materializer; proof в `tests/test_d2_availability_scenarios.py`; snapshot читает `clinic_policies.yaml` | Не затронуты `/ask`, `/ask/stream`, HTTP/SSE, widget, Composer, sales_fast, legacy selectors и fallback | Recovery, directory/UI, terminal/lead, полный B01 (все price modes), booking+policy блокировки, HTTP/SSE/widget и live не доказаны | **PASS** | `8939a29`; provider/live calls 0 |
| CP5-REC — D2-native recovery B16/C02 | Внутренний common D2 route: неполный ответ внутри того же D2 plan. B16 — нет цены + живой независимый материал → стандартный price-gap, content сохранён, разрешённая CTA, без «не оказываем» и без auto-lead (D2-081). C02 — живая цена сохраняется при ошибочном `content_ref` (`d2_content_source_missing`) и при prose money (T3 unavailable/recovered); optional secondary UI сбой не скрывает цену (D2-065/D2-083). Карточка услуги только по typed ID в snapshot; чужой tenant по-прежнему fatal. Нет legacy fallback. | `run_d2_dialogue_turn` → `build_d2_snapshot_sources` → `resolve_d2_envelope_response`; proof в `tests/test_d2_recovery_scenarios.py`; soft-fail content binding в materializer | Не затронуты `/ask`, `/ask/stream`, HTTP/SSE, widget, Composer, sales_fast, legacy selectors и fallback | Terminal/lead, directory/UI, полный B17 overview, HTTP/SSE/widget и live не доказаны | **PASS** | `6d8e446`; provider/live calls 0 |
| CP5-TERM — B03 manual-contact terminal | Внутренний common D2 route: `route=ADMIN` → одна authored заглушка из `clinic_policies.yaml` (`manual_contact_template` + urgent + телефон tenant в тексте). Боль сейчас / кровь / жалоба / директор — один stub; без медсовета, цен, акций, CTA/follow-up/видео и без UI-кнопок (`canonical_contact=None`, D2-023). Контраст: страх будущей боли остаётся ordinary ANSWER (A03). `terminal_state=medical_terminal`. Нет legacy fallback. | `run_d2_dialogue_turn` → `build_d2_manual_contact_terminal_response`; proof в `tests/test_d2_terminal_scenarios.py` | Не затронуты `/ask`, `/ask/stream`, HTTP/SSE, widget, Composer, sales_fast, legacy selectors и fallback | Полный A12 lead / D2-022, spam hard-stop D2-040/071, directory/UI, HTTP/SSE/widget и live не доказаны | **PASS** | provider/live calls 0; hash в closeout |
| CP5-LEAD — A12 lead/privacy on common route | Внутренний common D2 route собирает существующий D1R lead/privacy без переписывания: adult `kind=booking` → `collecting_name` (tone name prompt, cancel QR, без подтверждения слота/времени); child booking → policy block, lead не стартует; cancel/defer выходит без CTA; имя→телефон→один `lead_effect` (`demo_stub`); pending-вопрос на PII-слоте (answer/continue) с 0 provider calls; D2-022 situation start→note→name без мед/маркетинг ответа; D2-031 после выхода `booking_intent_ever` не поднимает lead на ordinary ходе. Вход в booking только при `lead_bridge=True` и точном match bound session client = `session_key.client_id`; активный lead short-circuitится при matching bound session даже без флага; mismatch → fail-closed. PII в session mem; D2 store — только effect receipt. | `run_d2_dialogue_turn` → `core/d2_lead_bridge.py` → `clinic_policy_resolver` / `lead_turn_classifier` / session; proof в `tests/test_d2_lead_scenarios.py` | Не затронуты `/ask`, `/ask/stream`, HTTP/SSE, widget, Composer, sales_fast и fallback | HTTP lead UI/transport, реальный SMTP, pause/resume gray LLM, полный B11 lead-after-TTL, spam hard-stop, directory secondary situation button и live не доказаны | **PASS** | provider/live calls 0; hash в closeout |
| CP5-SPAM — D2-040/071 consecutive garbage | Внутренний common D2 route: детерминированный garbage gate (empty / short / link-only / obvious noise / mash) → один authored warn из `clinic_policies.yaml` (`spam_one_chance_template`), без CTA/меню/цен/мед; второй подряд мусор → `terminal_state=spam_closed` (`spam_closed_template`); третье сообщение в том же sid остаётся closed (D2-071). Нормальный dental FAQ после warn сбрасывает счётчик. Активный lead pre-provider не перехватывается spam. Phone-only остаётся `d2_provider_input_privacy_only`. Off-topic polite refuse и wrong-layout вне среза. Нет legacy anti-spam redirect. | `run_d2_dialogue_turn` → `core/d2_spam_gate.py` → DeterministicBypass `spam_warn`/`spam_closed`; proof в `tests/test_d2_spam_scenarios.py` | Не затронуты `/ask`, `/ask/stream`, HTTP/SSE, widget, Composer, sales_fast, legacy anti-spam redirect | Off-topic polite refuse (вторая ветка D2-040), wrong keyboard layout, directory/UI, HTTP/SSE/widget и live не доказаны | **PASS** | `e531cb1`; provider/live calls 0 |
| CP5-DIR-A — doctors/protocols directory | Внутренний common D2 route: typed directory без patient_text regex. Врачи услуги (`topic_id=doctors` + `service_id`) → список из `doctor_catalog.json` по явной связи service_ids, без «лучшего». Карточка врача (`content_ref=doctors__doctor__*.md`) → name/position/experience из каталога. Протоколы направления (`topic_id` + без service/content_ref) → только active `protocol`/`advanced_protocol` family (не CT/синус); до 3 options + до 2 secondary QR; без цены и без CTA. Контраст: ADMIN medical_terminal без directory. Contacts/CTA добраны в CP5-DIR-B. | `run_d2_dialogue_turn` → `core/d2_directory.py`; proof в `tests/test_d2_directory_scenarios.py` | Не затронуты `/ask`, `/ask/stream`, HTTP/SSE, widget, Composer, sales_fast | Overview команды, полный B12 UI matrix, HTTP/SSE/widget и live не доказаны | **PASS** | provider/live calls 0; hash в closeout |
| CP5-DIR-B — contacts + CTA free gate | Внутренний common D2 route: `kind=contact` → факты из `clinic_policies.yaml` contact текущего tenant (phone/address/…), call-кнопка + `canonical_contact`, `terminal_state=none` (не locks contacts). Список врачей услуги получает одну CTA; подпись «бесплатн…» только если fact `free_implant_consult` flag-active **и** в окне `active_from`/`active_until` на `as_of=now.date()` (иначе tone `doctor`/`booking`). Протоколы и medical_terminal без CTA. Не полный B12. | `run_d2_dialogue_turn` → `core/d2_contacts_cta.py` / `d2_directory.py`; proof в `tests/test_d2_directory_ui_scenarios.py` | Не затронуты `/ask`, `/ask/stream`, HTTP/SSE, widget, Composer, sales_fast | Полный B12 (source UI matrix, overview команды), HTTP/SSE/widget и live не доказаны | **PASS** | `0e0c02e`; provider/live calls 0 |
| CP5-B12 — CTA source/default/free matrix | Внутренний common D2 route: один offline набор B12. Source — md `cta_key`/`cta_action` → tone label (pain→`consult`, без «бесплатн»); secondary ≤2 (video+QR). Default — overview volume QR, затем «Не знаю» → одна CTA `price` (A07). Free — doctors list: free book_label внутри `active_until`, tone doctor после expiry. Forbid — pure CLARIFY (guided QR, 0 CTA); medical_terminal и spam_warn без CTA. Не полный click-wire виджета. | `run_d2_dialogue_turn` + existing materializer/directory/spam; proof в `tests/test_d2_ui_b12_scenarios.py` | Не затронуты `/ask`, `/ask/stream`, HTTP/SSE, widget, Composer, sales_fast | Widget click replay, HTTP/SSE/widget и live не доказаны | **PASS** | `95e81af`; provider/live calls 0 |
| CP5-OTOV — off-topic refuse + doctors overview | Внутренний common D2 route: (1) D2-040 polite refuse — typed `kind=other` без clinic ids → authored `ui.yaml` fallback_menu.offtopic (proof: unique tenant mark, не code default); `terminal_state=none`, без CTA; garbage по-прежнему spam_warn до provider; medical не offtopic. (2) Overview команды — `content_ref=doctors__doctor__overview.md` через content lookup (не directory card); текст из md/prose, CTA `booking` из frontmatter; без «лучш» и без списка имён каталога. | `run_d2_dialogue_turn` → `core/d2_offtopic.py` / content materializer; proof в `tests/test_d2_offtopic_overview_scenarios.py` | Не затронуты `/ask`, `/ask/stream`, HTTP/SSE, widget, Composer, sales_fast | Wrong keyboard layout, полный prompt offtopic live, HTTP/SSE/widget и live не доказаны | **PASS** | `66db042`; provider/live calls 0 |
| CP5-REG — общая offline регрессия assembled CP5 | В одном прогоне 16 assembled CP5-файлов: **100 passed, 0 failed**. На baseline `4f7ac07` ранее сообщалось 70 passed / 26 failed с остановкой на `session.current_session_client_id()`. CP5-LEAD требует probe tenant binding даже при `lead_bridge=False`, чтобы active lead не попал к provider; он не читает ordinary state. Восьми широким runtime sentinel разрешён только этот точный вызов `session`, любые `mem_get`/другие функции по-прежнему запрещены. После этого выявились 3 устаревших ожидания числа `project_d2_session_context`: ранний lead/spam gate и provider path делают по одной проекции на ordinary turn; ожидания уточнены без изменения остальных route counts. | Внутренний `run_d2_dialogue_turn` и `D2DialogueStore`; `tests/test_d2_dialogue_a08.py`, `test_d2_dialogue_b13.py` и 14 assembled scenario/test файлов из команды CP5-REG. Ordinary state/result принадлежит одному D2 store, PII/lead slots — существующему `session` owner | Не затронуты `/ask`, `/ask/stream`, widget; локальный legacy HTTP route остаётся активен | HTTP/SSE/widget, все полные A/B семьи, общий live provider, внешний lead transport; тесты не доказывают HTTP cutover | **PASS** — independent Cursor Checker, P0/P1 findings нет | Baseline `4f7ac07`; targeted A08/B13: 22 passed; aggregate: 100 passed, 2 `datetime.utcnow` deprecation warnings; provider/live/network calls 0; Checker report `23733e8b-f6a3-4451-bd0e-50e1e89b033f` |
| CP5-B04i — первая попытка двух информационных вопросов | Разные темы отвечались обе; классификация по различию service/topic ошибочно принимала два самостоятельных вопроса одной темы за сравнение. | Общий D2 route и materializer, без HTTP/widget | Legacy runtime не менялся | Отклонённая эвристика полностью заменена CP5-B04s | **REJECT** — Cursor Checker P1 | Content 5 passed; Checker воспроизвёл component foreign-source failure на чистом HEAD: baseline, не регрессия B04i; provider/live/network calls 0 |
| CP5-B04s — единое правило для двух материалов | Общий D2 route отвечает на оба вопроса независимо от совпадения topic/service. Materializer не классифицирует текстовый запрос как «сравнение»: любая пара content parts сохраняет оба ответа и не показывает follow-up/видео отдельных материалов; один готовый comparison md сохраняет свой UI. Отсутствующая вторая опора даёт честный пробел. | `core/d2_dialogue.py`, `core/response_plan_materialization.py`, `tests/test_d2_content_scenarios.py`, `tests/test_d2_independent_request_parts.py`, D2-042/072, B04 acceptance и target contract; raw fake provider → production parser → tenant snapshot → D2 store | `/ask`, `/ask/stream`, widget и legacy runtime не менялись | Живая модель и HTTP не проверены; точный выбор цены названного бренда B05 остаётся отдельной задачей | **PASS** — independent Cursor Checker, P0/P1 findings нет | Rejected P1 focused recheck: 6 passed; 16-файловый assembled offline набор: 105 passed; tenant/lead boundaries: 3 passed. Checker подтвердил foreign-source component failure на чистом HEAD: baseline, не регрессия. Provider/live/network calls 0; staging пуст; шесть foreign WIP файлов не затронуты. |
| CP5-B05 — бренд, страна и цена имплантации | Внутренний D2 принимает typed `brand_id`: один существующий документ объясняет Implantium/Impro/Nobel, каталог даёт страну, а price materializer фильтрует активные предложения только выбранного бренда. Общий вопрос показывает опубликованные примеры по разным объёмам; точная услуга без карточки нужного бренда даёт пробел без чужой цены и акции. Osstem получает уже утверждённый ответ из tenant policy по точному brand term; для неизвестного бренда/страны — честный пробел без утверждения «не ставим». | `run_d2_dialogue_turn` → production D1R parser → demo snapshot → materializer/renderer → один `D2DialogueStore`; fake provider в `tests/test_d2_brand_scenarios.py`; D2 provider prompt получает существующий brand catalog и implant systems md из snapshot | `/ask`, `/ask/stream`, widget и legacy runtime не менялись; новая ordinary memory не добавлена | Реальная модель не проверена: распознавание русских форм, выбор `brand_id` и качество прозы требуют отдельного разрешённого live-прогона; HTTP/widget не подключены. Сложные персональные вопросы B07 вне среза | **PASS** — независимый Cursor Checker, P0/P1 нет | B05: 9 passed; assembled CP5: 105 passed; lead/privacy: 10 passed. `tests/test_d2_demo_snapshot.py`: 7 passed, 2 известных component failure, не B05-регрессии. Provider/live/network calls 0, staging пуст; foreign WIP не затронут. |
| CP5-EDGE — короткая проверка перед `/ask` | A06: два ответа на составной вопрос, затем неоднозначная цена вызывает CLARIFY без подстановки услуги. A09: «3 зуба, обе челюсти» хранится как typed факт, цена остаётся с опубликованной единицей. B07: запрос об уже установленном в другой клинике импланте проходит через существующий общий документ о протезировании с осмотром/консультацией, без личного обещания совместимости в тестовом ответе. B02: typed неизвестный термин вызывает один вопрос о значении, повтор — честный пробел и консультацию. | `run_d2_dialogue_turn` → production parser → demo snapshot → один `D2DialogueStore`; `tests/test_d2_launch_edges.py`; B02 использует существующий `clarify_pending` без второй памяти. | HTTP/SSE/widget и legacy runtime не менялись; provider/live/network calls 0 | Fake-provider тест B07 доказывает route и опору на документ, но не гарантирует формулировку живой модели; полный B07 со стадией и всеми персональными вариантами вне среза. Общий `clarify_pending` после unrelated CLARIFY может сразу дать неизвестному термину честный gap; Checker счёл это допустимым fail-safe для узкого «дважды подряд». Для более точного поведения позже потребуется причина уточнения в том же D2 store. | **PASS** — независимый Cursor Checker, P0/P1 нет | Авторский focused: 4 passed; assembled CP5 + EDGE: 111 passed, 0 failed. Checker: focused 4 passed, tenant/lead/privacy 11 passed, независимо собранный CP5 + EDGE 109 passed. `git diff --check` чистый; staging пуст; шесть foreign WIP не затронуты. |
| CP6a — JSON `/ask` cutover | **ACCEPTANCE:** применимые C05/C07/C08/C09: настоящий POST `/ask` отдаёт сохранённые text/UI/actions одного D2 completion; replay после reopen store, payload conflict, два конкурентных хода, tenant isolation, invalid provider и отказ commit проверены. Старый ordinary context не импортируется, replay не делает повторный отбор после изменения tenant pack. Booking → name → pending question → phone остаётся у lead owner; PII нет в D2 ordinary store/provider, replay не обновляет effect receipt. Отказ commit на booking или телефон откатывает session lead state; телефон можно завершить при повторе. | **D2 ROUTE:** `app.ask` → `run_d2_ask_json` → `run_d2_dialogue_turn` → production D1R parser → tenant snapshot → один `D2DialogueStore`; fake provider, временные DB/logs/копия tenant pack и blocked network. | **LEGACY IMPACT:** `/ask` больше не вызывает Composer, sales_fast, legacy semantic selectors, старую ordinary memory или legacy finalizer; активный lead читается через узкий read-only probe. `/ask/stream` пока остаётся legacy. | **OWNER DECISION:** не требуется — это технический CP6a cutover по Execution Lock §4 и Delivery Roadmap. **FUTURE SCOPE:** CP6b SSE parity, CP6c widget action/retry wire, CP7 физическое удаление legacy. Внешняя доставка заявки не запускалась (локальный `demo_stub` receipt); live model и браузер не проверялись. | **PASS** — независимый Cursor Checker, P0/P1 нет | Focused HTTP: 10 passed; assembled HTTP + lead/tenant/A08/EDGE before added C07/freeze test: 46 passed, 0 failed. Wider D2 offline before rollback change: 330 passed, 2 unchanged component failures (`test_d2_independent_request_parts.py::test_foreign_content_source_fails_closed_without_neighbor_substitution`, `test_d2_multi_request.py::test_content_for_another_service_is_rejected`), оба повторены отдельно; их тесты и materializer не менялись от HEAD. `test_d2_demo_snapshot.py` и live-provider offline file исключены из wider run. Provider/live/network/SMTP calls 0; staging пуст. |
| CP6b — SSE `/ask/stream` cutover | **ACCEPTANCE:** применимые C05/C08/C09: настоящий SSE endpoint отдаёт тот же сохранённый D2 final text/UI/actions/state, что JSON `/ask`; replay в обе стороны без нового provider/effect. Обрыв после раннего status до работы не фиксирует ход; обрыв после commit до UI сохраняет результат для replay. Terminal выдаёт `ui`/`done`, invalid provider и отказ commit — один `error` без final UI/late write. Ошибка framing после commit возвращает `error`, сохранённый результат доступен для replay. Tenant/freeze/lead и endpoint sentinels проверены. | **D2 ROUTE:** `app.ask_stream` → `run_d2_ask_json` → `run_d2_dialogue_turn` → один `D2DialogueStore`; SSE только обрамляет сохранённый payload, не делает второго materialize/render. | **LEGACY IMPACT:** старый `orchestrate_sales_one_plus_ask_turn`, Composer/sales_fast, semantic selectors, ordinary memory и legacy finalizer больше не вызываются ни из JSON, ни из SSE normal path. Старые функции физически остаются до CP7. | **OWNER DECISION:** не требуется — техническое SSE подключение по Execution Lock §4 и Delivery Roadmap CP6b. **FUTURE SCOPE:** CP6c браузерный widget с typed action ownership/retry; CP7 удаление legacy; live model и внешняя доставка без отдельного разрешения не проверялись. | **PASS** — независимый Cursor Checker, P0/P1 нет | Focused HTTP/SSE: 19 passed; assembled HTTP/SSE + lead/tenant/A08/EDGE: 56 passed, 0 failed; временные DB/logs/tenant pack, network blocked, provider/live/SMTP calls 0; staging пуст. Известные component failures из CP6a в этом наборе не запускались. |
| CP6c — widget D2 wire и typed actions | **ACCEPTANCE:** применимые C04/C05/C08/C09/C10: настоящий `widget.js` читает сохранённые `answer`/`ui`/`revision` D2; scope и CTA клики отправляют `ref` + текущую `ui_revision`, старые/чужие/непоказанные refs отклоняются до provider/effect. Новый ход получает новый request ID; автоматический и ручной повтор после обрыва сохраняют ID и дают один bot bubble. CTA входит в существующий lead owner без provider; телефонный ход даёт один локальный `demo_stub` effect, replay не обновляет receipt. Terminal не получает CTA; быстрые ответы и видео взяты из реального D2 UI projection. | **D2 ROUTE:** `static/widget/widget.js` → `static/widget/api.js` → реальный `/ask/stream` → `run_d2_ask_json` → `run_d2_dialogue_turn` → один `D2DialogueStore`; store читает последнюю сохранённую UI projection для ownership, без второй ordinary memory или повторного render. | **LEGACY IMPACT:** widget больше не читает legacy `meta`/`quick_replies`/`cta` как authority, не посылает старые `cta_action`/`action`, не использует booking regex для маршрута и не вызывает старый `/reset`; Composer/sales_fast и fallback недостижимы из JSON/SSE normal endpoint. Физическое удаление старых helpers — CP7. | **OWNER DECISION:** не требуется: typed UI ownership и retry прямо заданы Delivery Roadmap CP6c, Execution Lock §4. **FUTURE SCOPE:** CP7 удаление legacy; CP8 итоговый regression/live evidence. Реальная модель, внешний lead delivery и браузерная проверка с живым provider не запускались. | **PASS** — независимый Cursor Checker, P0/P1 нет | Авторский assembled HTTP/widget + lead/tenant: 34 passed до TTL-кейса; финальный focused widget/HTTP/SSE/no-legacy после TTL-кейса: 22 passed. Chrome harness использует реальные D2 payload из offline Flask endpoint, page network только localhost; DB/logs/tenant pack временные, fake provider, live provider/SMTP 0. `git diff --check` чистый, staging пуст; шесть foreign WIP не затронуты. |
| CP7 — изоляция legacy semantic route | **ACCEPTANCE:** C08: из `app.py` удалены старые JSON/SSE orchestration handlers, worker, semantic imports и ordinary-memory writes; реальные `/ask` и `/ask/stream` продолжают работать только через `run_d2_ask_json`, `/lead` сохранён. Startup provenance указывает D2. Endpoint sentinels, HTTP и lead/privacy regressions проходят; прямой импорт `app` не загружает Composer, sales_fast, старый finalizer или прежний orchestration entry. | **D2 ROUTE:** `app.ask` / `app.ask_stream` → `core/d2_http_adapter.py` → общий `run_d2_dialogue_turn` и один D2 store. | **LEGACY IMPACT:** старый semantic route больше не существует как callable wiring в `app.py`. Исторические legacy модули и их unit/eval tests физически остаются в репозитории, но не загружаются и не вызываются из bot HTTP entry; это не fallback и не normal-dialogue механизм. | **OWNER DECISION:** не требуется: удаление прежнего entry wiring задано Delivery Roadmap CP7 и Execution Lock §2–3. **FUTURE SCOPE:** CP8 итоговые offline/live evidence и качество модели; merge/deploy вне D2 rebuild. Полная уборка исторических файлов вне текущего функционального удаления маршрута. | Draft — ожидает independent Cursor Checker | Авторский focused endpoint/no-legacy/lead: 29 passed, 0 failed; health/widget-config/lead transport smoke: 3 passed; `app` import legacy-loaded `[]`; provider/live/network/SMTP calls 0; staging пуст, foreign WIP не затронуты. |
| Current local runtime | JSON `/ask`, SSE `/ask/stream` и браузерный widget используют D2 result/wire; старый semantic entry wiring удалён из `app.py`. | `static/widget/widget.js` → `api.js` → `app.py` → `core/d2_http_adapter.py` → общий D2 turn | Исторические legacy файлы существуют, но normal path их не импортирует и не вызывает | CP8 итоговый evidence pack; полная уборка исторических файлов может выполняться отдельно без восстановления старого маршрута | — (сводка состояния) | CP7 uncommitted draft; независимый review ещё не проведён |
| D2-S1 — смысловой контракт | Один действительный FullContext prompt строится из полного captured MD corpus текущего tenant. Обычная живая проза живёт в `request_understanding[].content_text`: `patient_text=null`, отсутствующий либо форматно повреждённый `content_ref` не уничтожают пригодный ответ и не авторизуют source UI. Прямой typed `service_id` для цены не требует необязательный `topic_id`; session binder не выводит topic по тексту/label и D2 gate пропускает такой service к catalog-owned materializer. Пустая ordinary prose не становится completed answer. | `build_d2_d1r_messages` → raw fake provider → `parse_production_envelope_json` → `run_d2_dialogue_turn` → tenant snapshot/materializer/store; тест использует temporary tenant copy/DB/log и network block | Legacy Composer/sales_fast, semantic selectors, второй prompt/parser/state и fallback не добавлялись и не вызывались этим checkpoint | Live-понимание русских форм, UI/session memory следующего этапа, несколько цен и единый multipart plan не доказаны. Owner decision не требуется: применены T2 и C01 без нового visible rule. | Draft — ожидает focused recheck Checker | Авторский focused: `tests/test_d2_r1_contract.py` — 12 passed; provider/live/network calls 0; staging пуст до review. |
| D2-S2 — typed память и UI | Общий D2 state хранит до 3 bounded очищенных пар live model prose, typed click ref без label, отдельную typed задачу CLARIFY (`request_id`, kind, service, extent) и ordered D2 offer refs без цены/label/display text. TTL 30 минут не проецирует ordinary state и очищает D2 memory при следующем commit. | `run_d2_dialogue_turn` → один D1R prompt/parser → tenant snapshot/materializer → один `D2DialogueStore`; `core/d2_live_provider.py` передаёт context и selected ref в тот же prompt; fake provider/temporary DB/network block. | Composer/sales_fast, legacy ordinary memory, второй prompt/parser/state и fallback не добавлены. | Owner отдельно утвердил 3 пары, 1000 символов, TTL 30 минут и узкое offer state; price assembly, HTTP/SSE/widget wire, live provider и deploy вне этапа. | **PASS** — независимый Checker и Cursor review | `py_compile` и `git diff --check` проходят; полноценный pytest в текущем runtime пока недоступен (`pytest` и `yaml` отсутствуют). SQLite `data/` не тронута; staging пуст. |
| D2-S3 — exact-service prices and scope | Для точной услуги D2 materializer выбирает только ID из единственного tenant-authored direction order, отфильтрованные по typed service и extent, в исходном порядке и максимум три. All-on-4 demo order подтверждён владельцем: Impro → Implantium → Nobel. Нет или неоднозначность order дают безопасный published-price gap без catalog/legacy selector; no-public остаётся frozen row. Первая price part materialized, остальные deferred; state продолжает хранить лишь offer/service IDs и порядок. | `run_d2_dialogue_turn` → production D1R parser → temporary demo tenant copy → snapshot/materializer → один `D2DialogueStore`; raw fake provider, сеть заблокирована в тестах. | Composer/sales_fast, semantic/strategy selector, старый runtime, второй prompt/parser/state и fallback не добавлены. | HTTP/SSE/widget, mixed price+content assembly (этап 4), live provider, merge/deploy вне этапа. Полный pytest не запускался: в bundled runtime нет `pytest` и `yaml`; пакеты не устанавливались. | **PASS** — Independent Checker и Cursor recheck | `py_compile`, JSON parse и `git diff --check` проходят. `data/` и две debug SQLite не затронуты; staging пуст; commit/push не выполнялись. |

| D2-S4 — единый mixed response | Один common D2 turn сохраняет один frozen plan с FullContext prose и typed price/policy/contact parts; первая price part materialized, следующие deferred; unavailable price не стирает независимые content/contact. Exact blocks входят в pre-resolver plan, поэтому есть один final UI/render pass и нет post-freeze selection. JSON/SSE и browser widget получают сохранённые answer/UI. | production D1R parser → `run_d2_dialogue_turn` → tenant snapshot/materializer/pre-resolver → один `D2DialogueStore` → реальный `/ask`, `/ask/stream` и `d2_widget_harness.mjs`; raw fake provider, temporary tenant copy/DB/logs, сеть заблокирована. | Composer/sales_fast, legacy semantic selectors, ordinary memory, второй prompt/parser/state и fallback не добавляются. `app.py`, HTTP adapter и widget production wire не меняются. | Existing Target Contract §6–8 covers exact typed policy composition and partial unavailable price. После finding owner 2026-09-25 explicitly allowed `core/response_plan_resolver.py` only to move exact blocks before its final UI pass; any other allowlist expansion still requires owner decision. Live provider, full stage-5 matrix, merge/deploy and legacy deletion remain future scope. | **PASS** — независимый Checker и Cursor review | Targeted pytest: `test_d2_stage4_mixed_response.py`, `test_d2_http_contract.py`, `test_d2_widget_replay.py` — 14 passed. Fake provider, temporary tenant copy/DB/logs; provider/live calls 0. `git diff --check` чистый; staging был пуст до checkpoint. |

## Историческая фиксация прежних checkpoint

- Через внутренний common D2 route собраны **A08**, узкая часть **A10a**
  (same-topic price continuation), узкая часть **B13a** (одна простая
  опубликованная service price), **A02**, **A11**, **B08**, **A03**, **A04**,
  механизм сравнения **B04** и два независимых информационных вопроса B04s
  (focused recheck и Cursor PASS), **B15**, срез
  **A01/A07/TTL** (CP5-C2a), **A10 empty/switch + B11 person-change** (CP5-C2b;
  lead consent и полный B11 с заявкой не доказаны), multi-part **A05/A06/B14**
  (CP5-MP), availability/policy **B01/B10** (CP5-AP), D2-native recovery
  **B16/C02** (CP5-REC), terminal **B03** manual-contact (CP5-TERM), lead
  **A12** / D2-022 / D2-031 / D2-036 privacy bridge (CP5-LEAD; HTTP/SMTP и
  pause gray LLM не доказаны), и spam hard-stop **D2-040/071** consecutive
  garbage (CP5-SPAM; off-topic polite refuse вне среза), directory
  **B09** врачи/протоколы (CP5-DIR-A) и contacts + CTA free-gate
  (CP5-DIR-B), и UI CTA matrix **B12** source/default/free + forbid
  (CP5-B12), off-topic polite refuse и doctors overview content
  (CP5-OTOV). Это не
  означает готовность полного A10/B13 и не подключает HTTP/виджет.
- **Кроме перечисленных, никакие другие A01–A12 или B01–B17 не считаются
  собранными D2 пользовательскими сценариями.** Зелёные unit/seam-тесты
  деталей остаются доказательствами компонентов, не сценариев.
  Документационный marketing audit также не является assembled-сценарием.
- CP3 отдельно подтвердил A08 тем же внутренним entry с ограниченным live
  provider; это не HTTP и не виджет.
- CP1 доказал только prompt/parser contract для этого внутреннего A08; он не
  является live-проверкой модели и не подключил D2 к пользователю.
- Внутренние result replay и PII-free lead-effect receipt доказаны только CP4
  internal route. HTTP/SSE integration, реальный lead UI/transport и общий runtime
  **не начаты**. Live-проверка ограниченно доказана только для CP3 A08, не для
  общего runtime.
