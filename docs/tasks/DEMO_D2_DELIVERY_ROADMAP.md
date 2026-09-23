# D2 — фиксированная дорожная карта до замены legacy runtime

Статус: **действующий план исполнения**, обновлён 2026-09-23 на ветке
`codex/demo-d2-service-volume` от baseline `4f7ac07`. Подтверждённые
внутренние CP5-сценарии перечислены в Ledger; общий агрегированный offline
CP5-REG прогон дал **100 passed**, независимый Cursor Checker — **PASS**.
Первая локальная правка CP5-B04i получила Cursor **REJECT** и заменена
упрощённым CP5-B04s по решению владельца: focused recheck **6 passed**, общий
offline-набор **105 passed**, независимый Cursor Checker — **PASS**. HTTP и виджет пока
обслуживает локальный legacy route.

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

Запрещён только **legacy fallback**: передать вопрос Composer / `sales_fast`
или выбрать runtime по ошибке D2. Разрешён **неполный ответ внутри того же
D2 plan**: сохранить проверенные части из текущего tenant snapshot; показать
карточку услуги или направления только если модель уже вернула typed ID и
запись есть в снимке; иначе утверждённый пробел, одно уточнение или
консультация по правилам CTA — без угадывания услуги «на всякий случай».
Это не второй runtime и не обход ошибки.

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

На baseline `4f7ac07` внутренний `run_d2_dialogue_turn` содержит CP5
commercial, content, continuation, multipart, availability, recovery,
terminal, lead/privacy, spam, directory, CTA и off-topic checkpoint из Ledger.
Их fake provider проходит production D1R parser; ordinary state/result
записывается только в `D2DialogueStore`, а PII/активная заявка остаются у
существующего lead-owner. Точный client-binding probe через
`session.current_session_client_id()` нужен для active-lead short-circuit
даже без `lead_bridge`; он не читает ordinary memory. Агрегированный CP5-REG
проверил 100 тестов вместе, но не доказывает HTTP, браузерный widget,
общую live-модель или все полные A/B семьи. Конкретные доказанные срезы и
оставшиеся пробелы ведутся в Ledger.

CP5-B04s добавляет сквозные offline-тесты двух информационных вопросов как
на разные темы, так и на разные услуги одной темы. Общий D2 route принимает
обе части без единого topic focus. Для любых двух отдельных md действует одно
правило: оба ответа сохраняются, follow-up и видео отдельных документов не
показываются; один готовый comparison md сохраняет свой UI. Различать
«сравнение» и «два вопроса» отдельным полем или эвристикой не нужно (D2-072).
Это локальное доказательство с fake provider, не live проверка распознавания
моделью и не HTTP cutover; Cursor Checker подтвердил CP5-B04s без P0/P1,
включая tenant/lead границы (3 passed). B05 не требует новых ценовых данных: в demo
pricebook уже есть предложения Implantium, Impro и Nobel Biocare. Локальный
CP5-B05 связал typed brand ID с активными ценами этого бренда,
существующим каталогом стран и документом об имплантах; Osstem берётся из
утверждённой tenant policy, неизвестный бренд получает честный пробел.
Независимый Cursor Checker подтвердил B05: P0/P1 нет, B05 9 passed,
assembled CP5 105 passed, lead/privacy 10 passed. Два известных component
failure в `test_d2_demo_snapshot.py` не являются B05-регрессиями.
Это пока не доказательство распознавания бренда настоящей моделью и не HTTP
cutover. Launch-edge checkpoint перед CP6a проверил A06 (составной вопрос,
затем неоднозначное «сколько это?»), A09 (три зуба на обеих челюстях с
опубликованной единицей цены), B07 (общая информация по документу и осмотр
для личной совместимости), B02 (неизвестный термин дважды). Для B02 внутри
одного D2 route добавлен узкий typed fail-closed: одно уточнение, затем
честный пробел и консультация через существующий `clarify_pending`; второй
ordinary state и специальные правила по терминам не добавлены. Focused
offline: 4 passed; общий assembled CP5 вместе с этим файлом: 111 passed.
Это fake-provider proof внутреннего route, не live распознавание модели и
не полный персональный B07. Независимый Cursor Checker подтвердил CP5-EDGE:
P0/P1 нет, focused 4 passed, tenant/lead/privacy 11 passed, независимо
собранный CP5 + EDGE 109 passed. Общий `clarify_pending` может дать честный
gap после unrelated CLARIFY; для узкого сценария это принято как fail-safe.
Следующий checkpoint — CP6a `/ask`.

## Неподменяемый порядок checkpoint

| ID | Наблюдаемый результат | Границы изменения | Приёмка и доказательство | После checkpoint ещё не готово |
|---|---|---|---|---|
| R0 — governance | Lock, эта roadmap, Ledger и master prompt Cursor существуют и согласованы | Только документы процесса | Cursor читает их до каждого значимого review | Любой D2 сценарий и HTTP путь |
| CP1 — единый prompt-contract | Production parser принимает расширенный typed D1R, нужный A08; prompt описывает те же поля | Существующий prompt-contract, parser/schema и offline tests; без data, HTTP, widget, live и новых сценариев | Raw ответ проходит **production parser**, не вручную созданный envelope; нет второго prompt/parser | Реальная модель, approved data, HTTP и пользовательский маршрут |
| CP2 — approved demo tenant data | Production tenant loader читает утверждённые direction-level данные для A08 | Штатный demo tenant pack/loader и tests; без test-only data binder | Цена/единица/условия берутся из tenant snapshot; tenant isolation проверяема | Настоящая модель, HTTP, widget и остальные сценарии |
| CP3 — ограниченный live A08 | Та же внутренняя D2 entry получает два последовательных ответа настоящей модели и соблюдает D1R/continuity contract | Prompt, существующая D2 entry, изолированная harness; без HTTP/widget и новых product rules | Только после отдельного разрешения владельца: точные фразы, модель, data version, жёсткий call budget; проверяется структура/refs/continuity | Полная оценка качества, нагрузка, HTTP и готовность всего бота |
| CP4 — D2 common turn completion | Внутренний общий D2 route завершает обычный ход с одним owner state, result/replay и обязательными lead/privacy effects | D2 turn service, typed state/result store, tenant snapshot, lead/privacy bridge и offline tests; legacy не расширяется | Применимые C04–C06, C09–C10: tenant refs, атомарность, replay, isolation, один effect | HTTP/SSE cutover, widget и непокрытые пользовательские семьи |
| CP5 — D2 сценарии через общий route | A01–A12 и применимые B01–B17 проходят один внутренний D2 route, не набор helper-тестов | D2 contracts/resolvers/materializer/renderer, штатные tenant data и tests; checkpoint определяется новым механизмом, а не названием услуги или комбинацией блоков | У каждой семьи есть acceptance ID; 2–3 сценария можно собрать вместе только на одном уже очерченном механизме; второй ход берёт контекст из настоящего предыдущего D2 turn; raw-text semantic selector не добавлен | HTTP/SSE/widget и доказательство недостижимости legacy от реального входа |
| CP6a — `/ask` | Реальный JSON endpoint вызывает общий D2 turn и отдаёт сохранённый final result/UI | Ingress, request identity, lead/privacy, JSON adapter и offline endpoint tests; без fallback | Raw fake D1R → production parser → D2 store; repeat/conflict/concurrency, tenant isolation, active lead/privacy/effect и invalid provider; C05/C07/C08/C09 sentinels и dependency check на `/ask` | SSE, браузерный widget, удаление legacy файлов |
| CP6b — `/ask/stream` | Реальный SSE endpoint использует тот же D2 turn и тот же final result | SSE transport и offline parity/replay tests поверх CP6a; без второго semantic route | JSON↔SSE parity по text/UI/actions/state, disconnect/replay с тем же request ID без provider/effect, terminal/error events и no post-freeze writes; C05/C08/C09 sentinels на `/ask/stream` | Браузерный widget, удаление legacy файлов |
| CP6c — widget | Существующий браузерный клиент отправляет D2 actions и показывает один сохранённый результат | Widget request identity, pure UI wire projection, JS/offline browser harness; без old presentation decision | Реальный widget/api код: current typed click работает, stale/foreign/forged отклоняются; повтор после обрыва до/после UI сохраняет ID и даёт один bubble/lead effect; новый ход получает новый ID; обе endpoint sentinel-проверки остаются зелёными | Физическое удаление legacy файлов и итоговый regression/live набор |
| CP7 — удаление legacy | Composer/sales_fast semantic runtime, selectors, старая ordinary memory и их тесты удалены либо отсутствуют как normal-dialogue механизм | Только явно перечисленные legacy files/imports/wiring/tests/docs; не удалять tenant/lead/privacy/transport защиты | C08: dependency check и endpoint sentinels; назначенные offline regressions проходят без legacy imports | Merge/deploy; они не входят в D2 rebuild |
| CP8 — final evidence | Есть единый evidence-pack: required offline acceptance, ограниченный live набор, Cursor PASS и актуальный Ledger | Только тесты, доказательства и документы уже сделанного D2 | A01–A12, применимые B/C, C01–C10, latency/cost facts и known limits перечислены явно | Production deployment: он не в scope и не совершается автоматически |

### Приёмка CP6 по порядку доставки

1. **CP6a `/ask`:** offline endpoint test посылает raw fake D1R через
   настоящий parser, tenant snapshot и `run_d2_dialogue_turn`, затем сверяет
   response/UI и сохранённый result/state. Проверяет idempotent replay того же
   `(tenant, sid, request_id, payload)` после reopen store, конфликт и два
   конкурентных хода, разные tenant с одним sid, invalid provider и отказ
   commit. Отдельный путь проверяет booking→имя→pending-вопрос→телефон,
   отсутствие PII в provider input/ordinary store и не более одного effect;
   active lead не попадает в provider. Fail-on-call sentinels для legacy
   semantic функций и transitive dependency check действуют на успешный,
   ошибочный и lead/typed-action запрос. Proof: `test_d2_http_contract.py`,
   `test_d2_http_scenarios.py`, `test_d2_no_legacy_path.py` и назначенные
   lead/privacy/tenant offline regressions.
2. **CP6b `/ask/stream`:** те же входные payload и request ID дают после
   завершения одинаковые final text/UI/actions и одинаковую
   ревизию памяти с `/ask`; SSE отличается только transport framing. Обрыв
   до/после final с повтором через любой endpoint возвращает сохранённый
   result с 0 новых provider/effect calls. Invalid provider и transport error
   имеют один final/error outcome без late mutation; C08 sentinels и
   dependency check применяются к реальному SSE пути. Proof: те же HTTP
   contract/scenario/no-legacy tests с параметрами JSON↔SSE.
3. **CP6c widget:** JS harness использует настоящий `static/widget/api.js` и
   `widget.js`, а не мок UI projection. Проверяет один logical request ID
   для retry при обрыве до UI и после UI, новый ID для нового хода с тем же
   текстом, один bubble и отсутствие повторной заявки. Typed scope/lead
   action допускается только из сохранённой актуальной D2 UI projection;
   чужой, устаревший и forged action отклоняются. Text, CTA и secondary UI
   совпадают с сохранённым plan, включая terminal без CTA. Proof:
   `test_d2_widget_replay.py`, JS harness, оба HTTP contract/no-legacy набора.

Каждый шаг получает собственный review и Ledger evidence. CP6b начинается
после CP6a PASS, CP6c — после CP6b PASS. Текущий checkpoint CP5-REG не
выполняет HTTP cutover.

Нельзя считать CP5 готовым по unit/seam-тестам, нельзя перейти к CP6 с
legacy fallback, нельзя удалить runtime до того, как его заменяет D2 endpoint
route. Внутри CP4–CP5 разрешены малые checkpoint, но каждый имеет
ACCEPTANCE, D2 ROUTE, LEGACY IMPACT и Cursor PASS.

### Фиксированный порядок внутри оставшегося CP5

Аудит [DEMO_D2_SCENARIO_MARKETING_AUDIT.md](DEMO_D2_SCENARIO_MARKETING_AUDIT.md)
зафиксировал, что продолжать по одной услуге нельзя: acceptance-пример не должен
становиться production-веткой. Следующий порядок обязателен:

1. **CP5-M1 — commercial data contract:** две authored-формы одного promo fact,
   один service commercial profile (promo_refs ≤2, необязательный один пакет
   усилителя, необязательный один пакет «Также») и compatibility groups с
   готовым текстом. Используется существующий tenant loader/snapshot; второй
   data contract запрещён. Старые scenario rules не переносятся.
2. **CP5-M2 — common commercial plan:** один D2-native resolver формирует
   short promo, необязательный один пакет усилителя, необязательный один пакет
   «Также» и compatibility blocks до freeze. Legacy marketing selector
   недостижим из D2 route.
3. **CP5-M3 — assembled A02/A11/B08:** цена использует короткие additions,
   прямой запрос об акции — полную форму, несовместимость — authored alternatives.
   Пакет допустим только если M2 остаётся одним механизмом без разных state/rules;
   иначе он делится до реализации.
4. **CP5 content / direct-fact lookup:** утверждённые информационные
   материалы, гарантия как прямой факт, сравнение без самостоятельного
   медицинского вывода (A03/A04/B04/B15). Не растворять в multi-part и не
   подменять directory.
5. **CP5 continuation/choice:** обзор направления, кнопки объёма, same-topic
   и cross-topic carry, TTL, гипотеза ≠ факт.
6. **CP5 multi-part:** несколько независимых частей в одном сообщении;
   отложенный второй прайс; сломанная часть не убивает живые.
7. **CP5 availability/policy:** нет публичной цены, нет материала, явный
   отказ, ОМС/ДМС/дети — только authored policy.
8. **CP5 D2-native recovery:** неполный ответ внутри того же D2 plan:
   сохранить проверенные части снимка; карточку услуги/направления только при
   typed ID в данных. Это не продающий обход «всегда что-то показать» и не
   legacy fallback.
9. **CP5 terminal/lead/hard-stop:** заявка и текущая боль/жалоба; будущий
   страх боли сюда не входит.
10. **CP5 directory/UI:** врачи, протоколы, контакты, CTA/кнопки как правило
    сборки, не отдельный сюжет услуги.

    Пункты 4–10 — технические семейства checkpoint, не новые пользовательские
    сценарии. Дополнительные услуги уже доказанного механизма проверяются
    пакетно как data-driven cases, а не отдельным кодом.

D2-O4 закрыто D2-090: к услуге 0 или 1 пакет усилителя и 0 или 1 пакет
«Также». Перед CP5-M1 больше не требуется отдельное число усилителей. Старый
технический cap `4` не переносится.

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
не пишется ничего. Постоянный шаблон исполнителя —
[DEMO_D2_CODEX_EXECUTOR_PROMPT.md](DEMO_D2_CODEX_EXECUTOR_PROMPT.md).

Terra останавливается только при конфликте требований, новом видимом
пользовательском правиле или двух допустимых реализациях с разным видимым
поведением. Уже решённое contract/acceptance правило он применяет сам и
ссылается на него. Нельзя незаметно добавить strict refusal/gate, который
может скрыть нормальный ответ, или semantic inference из `patient_text`,
`assistant_text`, `patient_message`, `dialogue`, regex или возраста turn.

После изменений Terra запускает только assigned offline tests в изолированной
среде и добавляет в этот же незакоммиченный diff черновую строку Ledger с
доказанными фактами checkpoint. В строке указывается устойчивое имя
checkpoint, а не hash ещё не созданного commit. Cursor независимо читает весь
diff — код, tests и Ledger — по master prompt и выносит PASS/REJECT. После
REJECT исправляется находка и проверяется именно она с необходимой регрессией.
Один Cursor review нужен на законченный значимый checkpoint, а не на каждую
строку документации или мелкое исправление его замечания.

Только после Cursor PASS: exact staging, staged diff/stat/`diff --check`,
commit и push. Финальный отчёт сообщает фактический hash и готовый prompt
следующего checkpoint; он не меняет Ledger после PASS. Cursor не
перепроектирует D2 и не отклоняет работу за честно указанный FUTURE SCOPE.

## Следующий шаг

CP1–CP4, CP5-A10a и CP5-B13a завершены с доказательствами из Ledger. После
Cursor PASS документационного аудита следующий разрешённый code checkpoint —
**CP5-M1: единый commercial data contract**. Он не подключает HTTP/widget,
не делает provider calls и не объявляет A02/A11/B08 собранными. Следующий шаг
определяется этой таблицей и Ledger, а не новой услугой или комбинацией
маркетинговых блоков.
