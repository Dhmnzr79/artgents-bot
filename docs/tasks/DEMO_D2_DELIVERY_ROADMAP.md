# D2 — фиксированная дорожная карта до замены legacy runtime

Статус: **действующий план исполнения**. Зафиксировано: 2026-09-20 на
ветке `codex/demo-d2-service-volume`, HEAD `788450e`.

Это единственная действующая roadmap D2. Историческая
`DEMO_D2_REBUILD_ROADMAP.md` объясняет прежний план, но не задаёт порядок
работы. Доказанные факты записываются только в
[DEMO_D2_CHECKPOINT_LEDGER.md](DEMO_D2_CHECKPOINT_LEDGER.md), а жёсткие
запреты — в [DEMO_D2_EXECUTION_LOCK.md](DEMO_D2_EXECUTION_LOCK.md).

Изменить порядок, добавить продуктовый сценарий или ослабить запрет этой
карты можно только отдельным checkpoint с явным решением владельца. Новый
чат, новый исполнитель или более поздний prompt не отменяют эту карту.

## Цель и пределы

Конечный результат — один D2 runtime обычного диалога. Он получает запрос
через `/ask` и `/ask/stream`, использует один D1R prompt/parser, один owner
ordinary dialog state, typed tenant data и один финальный response/UI plan.

После переключения normal answer path не вызывает Composer, `sales_fast`,
legacy semantic selectors или старую ordinary memory. Нельзя сохранить их
как fallback, режим совместимости, обработчик «неизвестных» вопросов или
вторую ветку HTTP.

В production нет бота и нет пользователей. Поэтому локальный legacy runtime
не является тем, что надо защищать. Но сохраняются tenant isolation,
lead/privacy, заявки, typed UI ownership и transport защиты. Нельзя заменять
их самодельными упрощениями.

Объём ограничен действующими
[D2 target contract](DEMO_D2_TARGET_CONTRACT.md),
[acceptance](DEMO_D2_ACCEPTANCE.md),
[product decisions](DEMO_D2_PRODUCT_DECISIONS.md) и
[service scope](DEMO_D2_SERVICE_VOLUME.md). Если там нет правила для нового
видимого поведения, исполнитель останавливается и просит решение владельца
с двумя примерами «до/после».

## Текущее доказанное состояние

На HEAD `788450e` собран только внутренний двухходовый A08: raw fake-provider
ответ проходит production D1R parser, production tenant loader, D2
resolver/materializer, текст/UI и typed persistent state с close/reopen store.
Это вызывает `core/d2_dialogue.py::run_d2_dialogue_turn` только его
offline-тест.

Это **не** означает, что D2 подключён к HTTP, виджету или настоящей модели,
что остальные A01–A12 собраны, или что legacy перестал обслуживать локального
бота. При противоречии Ledger сильнее устного отчёта.

## Неподменяемый порядок checkpoint

| ID | Наблюдаемый результат | Границы изменения | Приёмка и доказательство | После checkpoint ещё не готово |
|---|---|---|---|---|
| R0 — governance | Lock, эта roadmap, Ledger и master prompt Cursor существуют и согласованы | Только документы процесса | Cursor читает их до каждого значимого review | Любой D2 сценарий и HTTP путь |
| CP1 — единый prompt-contract | Production parser принимает расширенный typed D1R, нужный A08; prompt описывает те же поля | Существующий prompt-contract, parser/schema и offline tests; без data, HTTP, widget, live и новых сценариев | Raw ответ проходит **production parser**, не вручную созданный envelope; нет второго prompt/parser | Реальная модель, approved data, HTTP и пользовательский маршрут |
| CP2 — approved demo tenant data | Production tenant loader читает утверждённые direction-level данные для A08 | Штатный demo tenant pack/loader и tests; без test-only data binder | Цена/единица/условия берутся из tenant snapshot; tenant isolation проверяема | Настоящая модель, HTTP, widget и остальные сценарии |
| CP3 — ограниченный live A08 | Та же внутренняя D2 entry получает два последовательных ответа настоящей модели и соблюдает D1R/continuity contract | Prompt, существующая D2 entry, изолированная harness; без HTTP/widget и новых product rules | Только после отдельного разрешения владельца: точные фразы, модель, data version, жёсткий call budget; проверяется структура/refs/continuity | Полная оценка качества, нагрузка, HTTP и готовность всего бота |
| CP4 — D2 common turn completion | Внутренний общий D2 route завершает обычный ход с одним owner state, result/replay и обязательными lead/privacy effects | D2 turn service, typed state/result store, tenant snapshot, lead/privacy bridge и offline tests; legacy не расширяется | Применимые C04–C06, C09–C10: tenant refs, атомарность, replay, isolation, один effect | HTTP/SSE cutover, widget и непокрытые пользовательские семьи |
| CP5 — D2 сценарии через общий route | A01–A12 и применимые B01–B17 проходят один внутренний D2 route, не набор helper-тестов | D2 contracts/resolvers/materializer/renderer, штатные tenant data и tests; каждая малая семья — отдельный checkpoint | У каждой семьи есть acceptance ID; второй ход берёт контекст из настоящего предыдущего D2 turn; raw-text semantic selector не добавлен | HTTP/SSE/widget и доказательство недостижимости legacy от реального входа |
| CP6 — D2 HTTP/SSE/widget cutover | Оба endpoint и widget доставляют результат одного D2 turn; legacy normal path недостижим | Ingress orchestration, transport adapters, UI projection и endpoint tests; без fallback и выбора runtime по типу вопроса | Реальные `/ask` и `/ask/stream` endpoint tests, parity, C05/C07/C08/C09; sentinels и dependency checks доказывают отсутствие legacy вызова | Физическое удаление legacy файлов и итоговый regression/live набор |
| CP7 — удаление legacy | Composer/sales_fast semantic runtime, selectors, старая ordinary memory и их тесты удалены либо отсутствуют как normal-dialogue механизм | Только явно перечисленные legacy files/imports/wiring/tests/docs; не удалять tenant/lead/privacy/transport защиты | C08: dependency check и endpoint sentinels; назначенные offline regressions проходят без legacy imports | Merge/deploy; они не входят в D2 rebuild |
| CP8 — final evidence | Есть единый evidence-pack: required offline acceptance, ограниченный live набор, Cursor PASS и актуальный Ledger | Только тесты, доказательства и документы уже сделанного D2 | A01–A12, применимые B/C, C01–C10, latency/cost facts и known limits перечислены явно | Production deployment: он не в scope и не совершается автоматически |

Нельзя считать CP5 готовым по unit/seam-тестам, нельзя перейти к CP6 с
legacy fallback, нельзя удалить runtime до того, как его заменяет D2 endpoint
route. Внутри CP4–CP5 разрешены малые checkpoint, но каждый имеет
ACCEPTANCE, D2 ROUTE, LEGACY IMPACT и Cursor PASS.

## Правила доказательства

| Формулировка в отчёте | Разрешена, только если |
|---|---|
| «компонент реализован» | Есть код и focused offline test; это не означает сценарий |
| «внутренний маршрут проверен» | Тест идёт через общий D2 entry; состояние второго хода записано первым, не подставлено вручную |
| «подключено к входу бота» | Реальные `/ask` и `/ask/stream` вызывают D2 route; legacy fallback отсутствует |
| «проверено с настоящей моделью» | Есть разрешение владельца, call budget и зафиксированные результаты |
| «готово к закрытию D2» | Выполнены CP7 и CP8; это нельзя вывести из числа зелёных unit-тестов |

Fake provider допустим только как raw provider response, который разбирает
production parser. Он доказывает wiring, parser, state и deterministic data
resolution. Он не доказывает, что модель понимает русский вопрос, стабильно
выдаёт расширенный D1R или соблюдает refs; это назначение CP3.

## Контроль на каждом checkpoint

Перед записью Terra объявляет baseline, точный allowlist, ACCEPTANCE, D2
ROUTE, LEGACY IMPACT, OWNER DECISION, FUTURE SCOPE и точную команду offline
теста с временной БД, `BOT_LOG_DIR` и temporary tenant pack. Вне allowlist
не пишется ничего.

Terra останавливается только при конфликте требований, новом видимом
пользовательском правиле или двух допустимых реализациях с разным видимым
поведением. Уже решённое contract/acceptance правило он применяет сам и
ссылается на него. Нельзя незаметно добавить strict refusal/gate, который
может скрыть нормальный ответ, или semantic inference из `patient_text`,
`assistant_text`, `patient_message`, `dialogue`, regex или возраста turn.

После изменений Terra запускает только assigned offline tests в изолированной
среде и **не commitит**. Cursor независимо читает незакоммиченный diff по
master prompt и выносит PASS/REJECT. После REJECT исправляется находка и
проверяется именно она с необходимой регрессией. Один Cursor review нужен на
законченный значимый checkpoint, а не на каждую строку документации или
мелкое исправление его замечания.

Только после Cursor PASS: exact staging, staged diff/stat/`diff --check`,
commit и push. Строка фактов в Ledger входит в тот же проверенный checkpoint,
а не добавляется задним числом. Cursor не перепроектирует D2 и не отклоняет
работу за честно указанный FUTURE SCOPE.

## Следующий шаг

Следующий разрешённый checkpoint — **CP1**. Он меняет единый D1R
prompt-contract и parser/schema offline только настолько, насколько нужно
для typed A08. Он не начинает CP2–CP8 и не делает provider/HTTP/widget
вызовов. После его Cursor PASS следующий шаг определяется этой таблицей:
CP2, а не произвольная новая архитектурная задача.
