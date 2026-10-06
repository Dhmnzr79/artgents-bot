# D2 — текущее состояние и куда смотреть

## Подготовка данных к отдельному model test — 2026-10-06

После checkpoint e19fd5e owner разрешил убрать явные дубли условий.
Interface §18: только 14 package.label, обязательные условия остаются полными.
Все остальные поля 33 offers сохранены; one_stage формулировки «по показаниям»
не унифицированы из-за неэквивалентности. Runtime/schema не менялись.
Это не исправляет разрывы строк в виджете; текстовая приёмка §17 ещё открыта.
Model test/script не создавался и не запускался; модель/budget ещё не выбраны.
Проверки этой data-правки и независимый review — в Interface Task §18/Ledger.

## Checkpoint перед экспериментом с модельным изложением — 2026-10-06

Owner разрешил commit/push накопленного SIM4 и Interface §14–17 в текущую
ветку codex/d2-stage1-contract. Исходный HEAD4d4b027; SHA checkpoint получать
из Git, не из исторических baseline ниже. Это фиксация текущей работы,
не merge/deploy и не общий PASS SIM4/5/REC5.

§17: offline/Checker PASS сохранности фактов и исполнения. Owner widget
приёмка текста НЕ пройдена: продолжения пунктов списка показаны отдельными
абзацами, условия «имплантация — отдельно» дублируются из package label и
required conditions с разным регистром/точкой. Оформление и исходные дубли
требуют доработки. Нового смыслового фильтра/исправления данных не добавлено.

Следующий обсуждённый шаг: отдельный эксперимент «готовые выбранные факты →
живое изложение моделью», без изменения /ask и виджета на первом шаге.
Скрипт пока не реализован; модель и hard call budget ещё не согласованы.
Live/provider вызовы этим checkpoint не разрешены. Структура offers пригодна
для эксперимента; передавать полностью price mode, единицы, состав, exclusions,
timing и утверждённые условия. Не считать дубли автоматически исправленными.
Foreign data/ и docs/tasks/DEMO_D2_SIM0_TASK.md остаются вне публикации.

## Текущее продолжение — SIM-4, 2026-10-03

Baseline 4d4b0276d83208f2043f31f6af31be35b4d496ae, ветка codex/d2-stage1-contract.
D2-119/120 и UI отмены на телефоне сохранены/pushed; их scoped PASS в Ledger.
Владелец разрешил оставшуюся приёмку SIM-4; актуальный preflight/allowlist и
результаты — [SIM4 Task](DEMO_D2_SIM4_TASK.md). Это проверка существующего
ценового механизма после изменений интерфейса, не новый подбор цен.
Админка и оптимизация базы не входят. Live/SMTP и новые commit/push не входят.
Нижние сообщения о patient state, authored/fallback, старом SHA/WIP и запрете
начала работы относятся к прежним checkpoint, а не к текущему состоянию.

## Историческая точка передачи после аудита — 2026-10-02

Дополнение: владелец разрешил commit/push SIM4/D2-116/prompt33 и документов.
Checkpoint: `chore(d2): checkpoint sim4 and audit handoff`. После успешного
push его SHA — база продолжения в этой же ветке (команда получения в карточке).
Ниже незакоммиченное состояние — исторический preflight до публикации.
Публикация не закрывает SIM4/REC5 и не разрешает новый runtime или live.

Следующее чтение: [карточка интерфейса и handoff](DEMO_D2_INTERFACE_TASK.md).
Разрешена подготовка документов; новый runtime и новые live calls не разрешены.
Root C:\Cursor Projects\artgents-bot-active; branch codex/d2-stage1-contract;
HEAD и origin branch e6756ee59df4f186e499c29ae41cda0e993d80fe;
origin/main и merge-base 141ce91fb1731cd990fcf8391550150016c73e7f.
SIM4/D2-116/prompt33 остаются незакоммиченным WIP; staging пуст, commit/push
текущего checkpoint не выполнены. Передача по текущей рабочей папке, а не только
по HEAD. Не создавать новую ветку из main поверх этого dirty checkout.

Последующие ручные запросы владельца на prompt33: 7 попыток, 6 опубликованных
ответов, 1 parse failure. Это не 6 полностью проверенных диалогов и не общий PASS.
7ca91fe2: повторяющиеся kinds/situation, raw обрывается, output1024/max1024;
finish_reason отсутствует. Провайдер ответил, таймаут не зафиксирован.
Удаление трёх зубов: корректная операция, но существующие per-tooth offers
отфильтрованы отсутствующей applicability; следующий общий вопрос показал цены.
Новые вызовы агента: 0. Старые «widget не проверен» ниже — состояние ДО этих
ручных попыток; устойчивость и полный UI gate всё ещё не закрыты.

Независимый аудит подтвердил: нет разрешённой рекурсии; count не входит в
длительный discussion_scope; часть опубликованных code answers отсутствует
в следующем контексте; есть активные authored/fallback и price-carry ветки.
Это не blanket отмена прежних PASS. План доведения — верх Roadmap.
Foreign data/, docs/MARKETING_ANSWER_SCENARIOS.md, DEMO_D2_SIM0_TASK.md не трогать.

## Текущее дополнение — prompt33, 2026-10-02

GO на bug fix примера: известное направление + объём теперь показано прямой
ценовой задачей, а не уточнением услуги. Runtime/schema/память прежние.
Границы и проверки — [SIM4 Task](DEMO_D2_SIM4_TASK.md). Offline: 17 PASS;
независимый Checker PASS (собственные 5 PASS). Устойчивость живой модели
не подтверждена. Provider/live0; commit/push нет, Cursor gate остаётся.

## Текущий checkpoint — D2-116, WIP, 2026-10-02

GO владельца на три ценовых ответа: подходящая цена, разрешённый ориентир,
известная услуга без цены. Общий restoration overview и prosthetics pool
настроены в существующем механизме; prompt32. Правило — [D2-116](DEMO_D2_PRODUCT_DECISIONS.md),
границы и exact allowlist — [SIM4 Task](DEMO_D2_SIM4_TASK.md). Этот checkpoint
заменяет прежний few_teeth gap, не меняя исходный объём и медицинские факты.
Новых model calls/памяти/семантических проверок нет. Основной offline: 92 PASS;
соседний: 49 PASS и 3 старых FAIL; ещё 10 старых FAIL в availability/recovery.
Все 13 failure IDs повторены на чистом HEAD e6756ee; полный CI не зелёный.
Независимый Checker D2-116 PASS, собственный прогон 36 PASS /55.68s;
прежние PASS ниже предшествуют D2-116. Это не закрытие SIM4; Cursor gate остаётся.
Подробности — SIM4 Task. Live/commit/push0; widget пока не проверен.

## Исправление параметров уточнения — 2026-10-02, WIP

Владелец разрешил исправить инструкцию сохранения известного объёма внутри
clarification.operation. Prompt31; runtime/schema/память не меняются.
Known direction по-прежнему идёт напрямую к цене, не к выбору услуги.
Тесты проверяют задачу, клик без модели, пробел цены и следующий контекст;
omission модели сервер не исправляет. Exact allowlist и границы проверки —
[SIM4 Task](DEMO_D2_SIM4_TASK.md). Independent Checker PASS для этого bug fix,
собственный прогон 12 PASS / 26.09 s. Live-adherence не аттестована; Cursor
gate остаётся. Provider/live0, commit/push нет.

## Текущий checkpoint — SIM-4/D2-114–115, 2026-10-02

Runtime SIM-4 разрешён делегацией владельца по демо-набору D2-115.
Карточка: [SIM4 Task](DEMO_D2_SIM4_TASK.md). Implantation overview — один пример
на методику из explicit pool, бренд/объём фильтруются до cap3. Конкретный демо-набор
SIM-0 принят в рамках делегации; independent runtime Checker PASS,
собственный reviewer прогон 44 PASS / 48.51 s; Cursor gate ещё впереди.
Старые ниже statements о требуемом выборе владельцем — история до D2-115.

Владелец принял остаточный финансовый риск свободной prose и приоритет
спокойного связного разговора без новых смысловых проверяющих слоёв, обрезания
или шаблонной замены. Кодовые цены/условия остаются из утверждённых данных.
Решение: [D2-114](DEMO_D2_PRODUCT_DECISIONS.md); действующие T3/C03/Lock/Checker
и SIM-4 Roadmap обновлены. Идея будущей очереди «Проверить» в админке сохранена
в Roadmap, не реализуется сейчас. Старое строгое D2-108 всего ответа заменено.

Baseline HEAD/origin branch e6756ee59df4f186e499c29ae41cda0e993d80fe,
branch codex/d2-stage1-contract; main/merge-base 141ce91.
Предыдущий DOC-only шаг D2-114 получил Checker PASS и 94 валидные ссылки.
Теперь runtime подбор изменён по SIM4 Task; публикация prose прежняя.
Прежний SIM4 Checker проверял prompt30; поздний prompt31 описан выше.
Демо-набор по D2-115 и карточка удаления готовы. Targeted offline:
126 соседних PASS + 43 новых PASS + focused 1 PASS. Independent runtime Checker
PASS, Cursor gate ещё впереди; SIM-4 не закрыт. Ссылки: 98, diff check чистый.
Live/provider/SMTP0, stage/commit/push/merge/deploy не выполнялись.
Нижние состояния «SIM-4 не разрешён» — история до нынешнего решения.

## Текущий checkpoint — SIM-3 закрыт, 2026-10-02

Владелец начал SIM-3 и принял сохранение обсуждаемой услуги/объёма через более
трёх контактных отвлечений до смены темы/услуги либо TTL. Карточка и точные границы:
[SIM3 Task](DEMO_D2_SIM3_TASK.md). Baseline HEAD/origin branch
5cb58d5629bb78b07736246e12d951844bbe6c55; branch codex/d2-stage1-contract.
Реализация проверена offline: receipt index → completion.response.resolved →
существующая projection; отдельный recent_price_scope удалён. Prompt30,
local session schema3 без миграции. Старый SID может быть отклонён; заявка остаётся
у lead owner, новый SID не переносит её. Проверки: 176 PASS и итоговые 56 PASS;
independent Checker PASS после focused recheck двух замечаний. Cursor PASS
предоставлен владельцем: 221 PASS, 0 FAIL в собственных offline прогонах reviewer.
Владелец «Делаем» согласовал фиксацию результатов и закрытие проверенного объёма.
Ручная/live проверка и качество живой модели не аттестованы; полный CI — прежний долг.
Владелец «Давай комит и пуш» разрешил публикацию SIM-3 в текущую ветку;
Git-результат подтверждается после выполнения. Новых live/provider/SMTP0;
merge/deploy не разрешены. Общий CI-долг,
SIM-0/4/5 и REC-5 открыты. Нижние снимки — история прежнего checkpoint.
Следующий этап по действующему порядку — SIM-4; его реализация этим закрытием
не разрешена. Неподтверждённая финансовая prose остаётся отдельным вопросом SIM-4.


## Действующий указатель — SIM-1/2 закрыты, 2026-10-02

Owner согласовал закрытие проверенного объёма SIM-1/2, учёт известных ошибок
общего CI как отдельного долга и commit/push. Основание: Cursor142 PASS,
independent Checker, widget3 PASS и узкий live4/4 PASS. Код после review/live
не менялся. Общий CI не зелёный и остаётся gate до merge; merge/deploy не разрешены.
Следующий этап — SIM-3 по Roadmap, без новой реализации в этом checkpoint.
SIM-0/4/5 и REC-5 открыты. Детали closure/CI debt — верх SIM2 Task/Ledger.
Нижние промежуточные заявления «SIM-1/2 не закрыты» — история до решения owner.

Repo C:\Cursor Projects\artgents-bot-active; branch codex/d2-stage1-contract.
HEAD4d240430c2ce056dc306c50e215dbb09843c6b8f; origin/main и merge-base
141ce91fb1731cd990fcf8391550150016c73e7f. Это baseline до согласованной публикации.
Точная карточка и границы — [SIM2 Task](DEMO_D2_SIM2_TASK.md), результаты
по времени — верх [Ledger](DEMO_D2_CHECKPOINT_LEDGER.md).

Актуальный Cursor review получен: PASS,142 теста прошли за202.88s, exit0
(contract/dialogues/B12/continuation). Это предоставленный владельцем результат,
Codex этот запуск не повторял. Удаления повторных решений подтверждены по коду;
live и полный CI этим PASS не подтверждены. Старые запреты операции врачей
ниже описывают исторический checkpoint: операция уже согласована и реализована.

Согласованный live prompt29: PASS в двух новых диалогах (fresh duration и
fear → price → one_tooth → duration),4/4 model calls,0 retries,0 calls на
кнопке. Оба объяснения содержат сроки из корпуса:20–30 минут и3–6 месяцев,
не описание задания. JSON/SSE200, lead не запрошен. Бюджет исчерпан.
Evidence и границы — верх Ledger; код и рабочие данные не менялись.

Текущий prompt29, session schema2. Владелец согласовал восстановление врачей
для услуги: операция doctors с одним service target напрямую вызывает
существующий каталог; его CTA проходит через общий selector, а service scope —
через общий расчёт контекста. Contract/dialogues/B12:128 PASS/2 FAIL из-за
не scoped prose в новых тестовых входах; после разделения scoped/unscoped
focused8 PASS. Независимый Checker новой операции и focused review финальной
коррекции теста: PASS. Общий CI не повторён. Подробности — верх Ledger.
D2-113: известная ценовая задача исполняется
прямо, модельное price-parameter уточнение исключено. Prompt28 — отдельное
исправление инструкции: прямой content_text содержит готовое объяснение,
pending question допустим только в clarification.operation. Offline107 и
независимый Checker prompt28 PASS; живое качество ими не аттестовано.
Владелец после ручного теста сообщил «Работает»: это подтверждение конкретного
диалога о сроках, без известного числа вызовов и без общего live-gate PASS.

Предыдущий checkpoint перевёл устаревшие D2 fixtures на действующий контракт,
проверил widget и получил актуальный Cursor review.
Схема и продуктовые решения этим checkpoint не меняются. Найден и исправлен
B11: удалена новая self-only проверка сохранения явно reported/correction
ситуации, восстановлено прежнее правило нового owner для другого человека.
Также восстановлено D2-012: чистое уточнение не получает общую CTA записи;
независимый ответ и телефонная кнопка сохраняются. Добавлены один внутренний
аргумент UI selector и условие по готовым частям; новых wire-полей/памяти/вызовов нет.
Фокусная проверка:9 PASS,1 FAIL. Итог шести обновлённых файлов:64 PASS,1 FAIL,
143.43s; единственный отказ — документированный blocker врачей.
Независимый Checker этого узкого checkpoint: PASS по коду и результатам;
SIM-1/2 не закрыты; актуальный Cursor review получен (результат выше).
Test session
context:58 PASS; widget:3 PASS, включая настоящий headless browser с fake HTTP
payloads. Прежний CDP timeout в этом запуске не повторился; причина прежнего
timeout не установлена. Итог остальных проверок и baseline comparison — Ledger.

Общий CI не объявлен зелёным. Два offline pytest-набора ci.yml (49 уникальных
файлов):672 PASS,149 FAIL,5 skipped; чистый HEAD дал те же количества.
148 failure node IDs совпали. Разница: local dotenv влияет на тест ключа,
а archive без Git index даёт лишний отказ executable-mode. Это ограничения
сравнения, не доказательство полной эквивалентности CI. PostgreSQL qualification,
Linux lint/dependency/secret-scan jobs этим локальным запуском не выполнены.
Исторические sales/D1R HTTP harnesses не подменяют новый D2 provider; не чинить
их восстановлением старого runtime, fallback или ослаблением защит.

SIM-1/2 закрыты: живой критерий выполнен, владелец принял учёт незелёного CI
как отдельного долга. Live4/4 завершён,
дополнительных вызовов не разрешено. Прежний blocker
«врачи для услуги» получил отдельное согласование 2026-10-02 и реализован
узкой операцией; тест B12 сохранён, каталог/CTA renderer подключён напрямую.
Результаты прежнего запуска64 PASS/1 FAIL выше исторические, до этого исправления.
SIM-3 память completion → projection, SIM-0/4 обзор/финансовая публикация и
SIM-5 остаются по Roadmap. В текущем live provider4,SMTP0; старый prompt26 gate
остаётся исторически остановленным. Commit/push разрешены, merge/deploy нет. Foreign data/ и
docs/MARKETING_ANSWER_SCENARIOS.md вне scope.

## Исторический WIP-снимок — 2026-10-01 (не текущая инструкция)

- Repo C:\Cursor Projects\artgents-bot-active; branch codex/d2-stage1-contract.
  HEAD и локальный tracking ref: 4d240430c2ce056dc306c50e215dbb09843c6b8f.
  origin/main и merge-base: 141ce91fb1731cd990fcf8391550150016c73e7f.
  Новый fetch не выполнялся.
- Владелец согласовал общий checkpoint: остаток SIM-1 и необходимое ядро SIM-2.
  Разрешение, runtime allowlist и критерии — [SIM2 Task](DEMO_D2_SIM2_TASK.md).
  Новый D2 получает узкие операции напрямую, без восстановления старого envelope.
  Service/volume/detail выполняются сервером; пояснение известной задачи
  получает ограниченный ответ модели. D2-111 и B14 включены.
- Типы модели protocol/prompt 27, session schema 2. Исторический local state
  не мигрирован; новая проверка работает на изолированных новых сессиях.
- SIM-1/2 ещё не закрыты. Пользователь передал Cursor PASS по prompt 25:
  161 тест одним запуском, включая D2-112; browser и общий CI остаются открытыми.
  До D2-112 было 185 offline PASS; focused D2-112 Checker также PASS.
  Текущая проверка: 161 непересекающийся offline PASS (подробности в карточке);
  browser acceptance заблокирован прежним CDP timeout.
  Результаты и ограничения — верх [Ledger](DEMO_D2_CHECKPOINT_LEDGER.md).
- D2-112 согласован после разбора PASS: одно активное уточнение, понятные части
  сразу, остальные требующие уточнения вопросы явно отложены без очереди.
  Исправление реализовано: понятные части сохранены, один pending/UI.
  Schema 1 проверена synthetic offline: тот же SID получает d2_invalid_turn,
  dialogue и активная заявка не стираются; новый SID — отдельный разговор
  без автоматического переноса заявки. Migration/reset не добавлены.
  Cursor подтвердил прямые/косвенные/error paths на прежнем checkpoint.
- После ручного теста выявлен malformed clarification.operation и
  необоснованное сужение направления до classic. Выполняется исправление
  инструкции (prompt 26), примеров и текста меню по SIM2 Task. Offline:
  79 PASS; независимый Checker текущего исправления PASS. Предыдущий PASS
  не доказывает качество новой генерации. Затем владелец разрешил live ≤8.
  Gate остановлен: 4 live calls +1 sandbox-blocked attempt; после страха боли
  общий вопрос о цене дал валидное уточнение объёма вместо обзора, без цен
  и кнопок. Формат не упал, semantic gate FAIL. Остаток не расходуется.
- После разбора liveFAIL владелец согласовал D2-113: прямое исполнение
  известной ценовой задачи и удаление model price parameter clarification.
  Реализация в текущем WIP, prompt27: 125 offline PASS, независимый Checker D2-113 PASS.
  Allowlist/результаты — верх SIM2 Task.
  Shared task types ограничивают wire и pending; legacy pending без migration
  может отказать, нужен отдельный новый тестовый чат. Новый live не разрешён.
- [Roadmap](DEMO_D2_DELIVERY_ROADMAP.md) сохраняет SIM-0 offers и SIM-3/4/5,
  затем REC-5. Полная память completion → projection и контроль всей
  финансовой prose этим checkpoint не выполнены.
- Последний агентский gate: provider/live 4, плюс 1 заблокированная сетевая
  попытка, SMTP0. Предшествующий пользовательский тест учитывается отдельно.
  Staging пуст; новых commit/push/PR нет.
  Foreign data/ и docs/MARKETING_ANSWER_SCENARIOS.md сохранены и не открывались.
  Старые test fixtures с envelope не являются подтверждением нового протокола;
  полный CI ещё не заявляется.

## Исторический снимок — 2026-09-29 (не текущая инструкция)

Снимок на 2026-09-29 для `C:\Cursor Projects\artgents-bot-active`, ветка
`codex/d2-stage1-contract`. Последний принятый Checker/Cursor и отправленный
runtime checkpoint: **REC-4-P2
`f4a08ea75b284cb51291fd7fe6ca64d842d8e2d0`**; карточка — `abcb8ee`,
предыдущий runtime checkpoint — D2-LEAD-INTERRUPT `71d7467`.
GitHub branch проверена read-only `ls-remote` 2026-09-29 и совпадает с HEAD;
main и merge-base — `141ce91fb1731cd990fcf8391550150016c73e7f`.
Текущая документальная работа — [D2-AUDIT-PLAN](DEMO_D2_AUDIT_FOLLOWUP_TASK.md):
сверка после аудита и проект дальнейшего порядка, **без GO на runtime**.
Это локальный демо-бот; production-развёртывания и пользователей нет. Перед
работой сверяйте текущие Git HEAD, origin и status: этот файл — указатель на
момент записи, не замена preflight.

## Порядок работы с документами

1. [AGENTS.md](../../AGENTS.md) и [Execution Lock](DEMO_D2_EXECUTION_LOCK.md)
   задают процесс и запреты.
2. [Delivery Roadmap](DEMO_D2_DELIVERY_ROADMAP.md) задаёт порядок этапов.
3. Карточка текущего checkpoint задаёт baseline, точный allowlist и приёмку.
4. [Target Contract](DEMO_D2_TARGET_CONTRACT.md),
   [Product Decisions](DEMO_D2_PRODUCT_DECISIONS.md) и
   [Acceptance](DEMO_D2_ACCEPTANCE.md) задают согласованное поведение.
5. [Ledger](DEMO_D2_CHECKPOINT_LEDGER.md) хранит доказательства по времени и SHA.
   Его прежние `Draft` и «текущий» описывают состояние **на дату строки**;
   их не следует принимать за текущий Git-status.

## Историческая последовательность — до SIM (не текущая инструкция)

| Шаг | Состояние на этом снимке | Где детали |
|---|---|---|
| D2-DOC-CLICK | Checker и Cursor PASS, commit/push `e246f1e`; исправлены передача выбранного раздела модели и omitted mode ordinary prose. Качество реальной генерации отдельно не доказано | [Карточка](DEMO_D2_DOCUMENT_CLICK_TASK.md) |
| Вопрос при активной записи | Реализация прошла Checker/Cursor, сохранена и отправлена в `71d7467`; ответ, resume/cancel и replay проверены offline, живое качество генерации отдельно не доказано | [Карточка lead-прерывания](DEMO_D2_LEAD_INTERRUPT_TASK.md) |
| REC-4-P2 | Checker/Cursor PASS, commit/push `f4a08ea`. `classic`: обе detail-кнопки при полных данных всех показанных offers; клики читают captured набор, прямой вопрос доступен без кнопки. Это ограниченный A16/B19, не весь REC-5 | [Карточка цен](DEMO_D2_PRICE_PRESENTATION_DETAILS_TASK.md) |
| D2-AUDIT-PLAN | Разрешены сверка документов и проект плана. Карточка фиксирует находки и вопросы; изменения бота не начаты | [Текущая карточка](DEMO_D2_AUDIT_FOLLOWUP_TASK.md) |
| Исправления после аудита | Предложены малые checkpoint: задача volume-кнопки, контакты, полнота контекста, независимые части. Порядок и кодовые карточки ещё требуют принятия; цитаты владельца не равны GO | [Проект в Roadmap](DEMO_D2_DELIVERY_ROADMAP.md) |
| REC-5 | Общая приёмка открыта. Существующие PASS её не закрывают; ни один новый live call не разрешён | [Acceptance](DEMO_D2_ACCEPTANCE.md) |

## Исторические ограничения и evidence — до SIM

- Cursor P2: 20 passed / 1 browser deselected; browser отдельно 1 passed;
  широкий адресный набор 118 passed / 1 deselected. Четыре назначенных файла:
  65 passed / 15 известных baseline failed. Это сведения из переданного
  отчёта review, не новый прогон. Старые падения не скрыты и не исправлены
  документальным checkpoint.
- В поздних widget-логах обнаружены потеря price task после «Один зуб» и
  телефон вместо адреса в mixed вопросе. Остальные риски и уровень evidence —
  AF-01–10 текущей карточки. Технический PASS не гарантирует качество понимания.
- `authored` removal, широкий redesign памяти/envelope, MD-only и два model
  calls — не принятый план реализации. Новые правила оформления, рекламы,
  повторных кнопок, missing-data copy и CTA администратора тоже только кандидаты.
- Прежние Draft в P2-карточке, Ledger и «впереди» в dated Product Decisions
  описывают их baseline. Read-only ревью P2, включая поздний browser PASS,
  не переписывает прошлые evidence строки задним числом.
- Foreign маркетинговая памятка расходится с D2-100/D2-102; до отдельной сверки
  не использовать её как спецификацию. Действуют Contract/Decisions/Acceptance.
- Старые runtime-файлы не удалялись. Наличие файла не доказывает его вызов;
  полная проверка недостижимости остаётся C08 в REC-5.

Для нового чата передать этот путь, фактический HEAD и текущую карточку,
затем повторить preflight. Лучше переходить после Checker/Cursor и отдельно
разрешённых commit/push документального checkpoint. Новый чат не означает
новую ветку или разрешение на реализацию.

Старый `C:\Cursor Projects\artgents-bot` и worktree 27e1 — сохранённая
история, не активная папка. Чужие локальные `data/` и
`docs/MARKETING_ANSWER_SCENARIOS.md` не входят в текущую задачу.
