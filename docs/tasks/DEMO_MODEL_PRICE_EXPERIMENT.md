# Эксперимент: ценовые ответы модели

## Единая операция на kind — owner GO 2026-10-10

Классификация: архитектурное упрощение, не исправление всех ошибок модели.
Owner явно согласовал runtime replacement после объяснения примеров и этапов.
Baseline ef6894fed3c1b8198fbb98b018ff24f2029d391c, branch codex/model-price-experiment,
root/Git top C:/Cursor Projects/artgents-bot-active; main/merge-base efa3f77.
Foreign untracked prototypes/ сохранить. Staging пуст на входе.
До: четыре пары completed/pending классов конкурируют по одинаковому kind.
После: один тип на price/content/price_detail/commercial_fact; существующая
clarification определяет незавершённость. Удаляем четыре Pending-класса,
дубли union и выбор по pending subtype. Единственный владелец допустимой формы —
runtime тип операции; §3 Target Contract остаётся единственной таблицей владельцев.
Один объект напрямую идёт parser → execution → pending storage/context;
без adapter, parallel schema, новых wire fields, памяти, retry или вызовов.
Канонический dump тех же типов не публикует неприменимые optional поля, сохраняя
roundtrip и прежние строгие запреты готового/незавершённого content.
Stored clarify slot требует clarification как раньше, без другого типа операции.
Не менять default/подбор/цену/policy precedence/KB, JSON HTTP сохраняется.
Allowlist: contracts/d2_dialogue_result.py; core/d2_dialogue.py;
tests/test_d2_sim2_contract.py; tests/test_d2_commercial_scope.py;
tests/test_d2_session_context.py; tests/test_d2_structured_output.py;
tests/test_d2_operation_unification.py; этот документ;
docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md.
Allowlist уточнён до staging: tests/test_d2_sim2_dialogues.py только для
миграции двух assertions о Pending content: content_text=None и отсутствие
поля в dump вместо отсутствия Python атрибута. Остальные assertions неизменны.
Acceptance: 9 уникальных kind в actual schema, прежние allowed/rejected комбинации
четырёх операций, canonical nested roundtrip и storage pending-only, JSON/SSE
clarification → authenticated click → reply, null-target authored policy paths,
commercial scope, one-call/replay и source binding. Targeted offline + Checker;
browser/live/provider0, новый live budget отдельно. Это не гарантирует live смысл.

Отдельный read-only log finding: 2026-10-10 13:55:00 UTC, payment methods,
trace 9c71d6e60b8146a9833b798fbae5dbc2. Root object/outcome/blocks правильные;
kind content, source clinic__info__payment_terms.md, target type clinic,
228 chars; finish stop,91 completion tokens. Explanation Target не допускает clinic;
parse invalid_envelope, completion не создан. Не truncation/root-array/карточки.
Этот checkpoint сохраняет reject; разрешение clinic target или смена prompt
не входят в упрощение, точную причину выбора полей внутри модели лог не доказывает.

Implementation evidence: удалены четыре Pending-класса и PendingOperation union;
Block — discriminated union9 уникальных kind вместо13 конкурирующих ветвей.
Service click выбирает server explanation task по сохранённому kind, не subtype.
Добавлены условные validators того же типа вместо прежнего разделения классов,
и Field exclude_if для неприменимых optional полей; это сохраняет прежние
запреты null/двух content форм и канонический roundtrip. ClarifiedOperation —
те же четыре типа плюс требование непустой clarification в прежнем storage slot.
Новые wire keys/types/state/version/adapter/provider calls не добавлялись.
Equivalence read-only сравнение git show ef6894f:150 combinations target/clarification
и четырёх kind/двух content форм;52 accepted, acceptance/dump differences0.
Contract/context/schema/probe suite146PASS14.84s:
C:/Users/denis/AppData/Local/Temp/d2-unify-contract-edzkdojn/tests.xml.
Route suite155 cases:138PASS17FAIL155.96s:
C:/Users/denis/AppData/Local/Temp/d2-unify-route-h7gb1ujr/tests.xml.
Чистый git archive ef6894f, focused17 nodes:15FAIL2PASS20.64s:
C:/Users/denis/AppData/Local/Temp/d2-unify-baseline-ccrxir4j/failed-baseline.xml.
15 совпавших baseline failures:2 mixed-doctor context,1 includes wording,
10 overview action assertions,2 missing-authored source. Они вне изменения,
не ослаблены/не объявляются закрытыми. Два remaining assertion касались
hasattr Pending content; заменены сохранением None/отсутствия поля в dump.
Финальный focused dialogue/policy/card recheck74PASS112.52s:
C:/Users/denis/AppData/Local/Temp/d2-unify-final-wvtrfnhb/tests.xml.
Это2 migrated dialogue cases,8 null-target policy JSON/SSE,64 price-card cases.
Код старше этого прогона, затем менялась только evidence документация.
Independent Checker scoped PASS:10 allowlisted files, actual removal/canonical
roundtrip/ownership подтверждены; final XML прочитан независимо. Это не global
PASS и не доказательство улучшения live-понимания. Staging пуст;
commit/push/merge/deploy не сделаны. prototypes/ исключён и сохранён.
Полный CI/live understanding не аттестованы. Provider/browser/SMTP0.

## Layered Qwen experiment — owner GO 2026-10-10

Тип: изолированный диагностический эксперимент, не runtime replacement или
архитектурное упрощение. Owner разрешил подготовку тестов и provider calls;
объявлен hard cap48: 4layers × 3questions × 2formats × 2repeats.
Root/Git top C:/Cursor Projects/artgents-bot-active; branch codex/model-price-experiment;
HEAD/baseline4be01719c8b05bff8f4496eb7607136ea2d3aec9; origin/main/merge-base efa3f773bcf10891e2997addf8bbec38c7ae1317.
Initial allowlist: scripts/check_d2_format_layers.py; tests/test_d2_format_layers.py;
этот раздел карточки. После live evidence, на основании ранее явного owner GO
«Если нужно вернуться к старому формату, то окей», объявлен минимальный возврат:
добавлены core/d2_live_provider.py и tests/test_d2_structured_output.py только для
HTTP response_format и соответствующего assertion. Также объявлены updates
DEMO_D2_INTERFACE_TASK.md/DEMO_D2_DELIVERY_ROADMAP.md только current-status pointers.
Остальной WIP, prototypes/,
KB и карточки сохранены. Возврат — bug-fix/reversion, не simplification.
Small experimental wire/schema нигде не подключаются к HTTP или storage;
ответы сравниваются только в диагностике, не конвертируются в production pipeline.

Четыре profiles: small typed schema + short instruction/catalog;
full runtime schema + short instruction/catalog;
full schema + current D2 instructions + short instruction/catalog;
full actual prompt/catalogs/corpus/context. Три synthetic fresh вопроса:
implantation overview, Nobel overview, whitening+address. В каждой паре
messages/schema/model/temperature0/1024 одинаковы, меняется только format.
Порядок formats во втором repeat противоположный. Нет SDK retries, fallback,
resume, автоматической допокупки budget, DB/session/lead effects или browser.
Transport failure останавливает весь run, parse failure фиксируется и не
повторяется; следующие независимые cases продолжаются в пределах48.
Metadata report сохраняет hashes, typed operation fields и usage, не prose/
raw prompts/provider bodies. Exact raw response остаётся только в памяти.

Acceptance: отдельные format и targeted semantic checks, expected price target,
brand, отсутствие manufactured clarification, наличие address, отсутствие
invented brand/volume/unexpected operations. Broad contacts counts as address
coverage, не минимальный ответ. Policy defaults/весь диалог не аттестуются.
Limits: small→full_schema меняет wire representation; последний шаг меняет
corpus/catalog/context и убирает short instruction одновременно. Это сравнение
пакетов факторов, не доказательство конкретного schema keyword. Два repeats
не дают надёжной частоты ошибок. Никакое экспериментальное упрощение не
авторизует изменение runtime Target Contract §3 или данных клиники.
Astra before-live consultation: design пригоден, guard blockers нет; limitations
выше сохранены. Full schema name совпадает с runtime d2_dialogue.
Offline8PASS2.47s: C:/Users/denis/AppData/Local/Temp/d2-layers-offline-final-5z0_wjpl/tests.xml.
Initial offline выявил отсутствующий jsonschema dependency; заменён одним
typed SmallReply источником schema/validation без установки зависимостей.
Provider calls в offline0.

Live completed48/48, без повторов/fallback/transport failures.
Evidence: C:/Users/denis/AppData/Local/Temp/d2-format-layers-live-65877eb8730d4bb2856f4318d577ad58/report.json.
Все24 pairs совпали по messages hash; schema одинаковая внутри каждого pair.
Все48 finish stop, length0. Input656716/output3846 tokens; стоимость не вычислялась.

| Profile | JSON targeted checks | Strict targeted checks | Strict parser accepted |
|---|---|---|---|
| small | 6/6 | 6/6 | 6/6 |
| full_schema + short instruction/catalog | 6/6 | 0/6 | 4/6 |
| full_instructions + short instruction/catalog | 6/6 | 0/6 | 3/6 |
| full actual context | 6/6 | 0/6 | 6/6 |

Итого JSON24/24 targeted checks, strict6/24; parser43/48.
Все13 parser-accepted strict replies в full-schema profiles выбирали ненужную
service clarification, без правильного target. В full_context compound один
repeat дополнительно пропустил contact. Ещё5 full-schema strict replies
отклонены OneCallEnvelopeProtocolError; exact contract code/raw тела в отчёт
не сохранялись, поэтому конкретное нарушение этих5 не установлено.
Нельзя объявлять все5 ошибками JSON Schema: Python semantic validators также
выдают этот класс. Все ответы короткие stop, truncation исключена в этом run.

Вывод: отрицательный эффект воспроизводится уже на полном runtime schema с
маленькой инструкцией/catalog, до добавления полной базы. Большая KB не является
необходимым условием воспроизведения. Сам strict format на small wire работает.
Это локализует несовместимость к комбинации текущего rich schema/wire и strict
режима Qwen, не доказывает конкретный union/default/keyword/provider bug.
24/24 JSON в этой маленькой выборке не гарантирует отсутствие исторических
root-array failures, неверных policy/defaults или ошибок остальных классов.
Полная база сохранена; менять её ради этого результата оснований нет.
Эксперимент не чинит runtime, а готовит основание для возврата HTTP json_object
и отдельного исследования меньшего producer contract. Ни переименование полей,
ни adapters, retries или новый classifier автоматически не разрешены.
HTTP response_format возвращён к json_object на основании этого эксперимента
и conditional owner approval. Ordinary/known-task HTTP используют прежний формат;
typed reply, strict helper и diagnostic evidence сохранены. Новых полей/handler/
classifier/retry/fallback/calls нет; бюджеты/model/one-call/prompt/KB прежние.
Root-array риск не объявляется устранённым. Новых live calls поверх48 не делаем.
Final offline39PASS4.55s (layer guards8 + existing structured-output31):
C:/Users/denis/AppData/Local/Temp/d2-layers-reversion-440tspu0/tests.xml.
Independent Checker: scoped PASS diagnostics, затем focused PASS HTTP reversion;
reports/XML прочитаны независимо. Full CI/все dialogue paths не аттестованы.
Staging пуст, git diff --check clean; commit/push/merge/deploy0; foreign WIP сохранён.

## Paired format comparison — owner GO 2026-10-10, 6 calls (история до layered run)

Тип: диагностический эксперимент/documentation only, не runtime bug fix.
Root/Git top C:/Cursor Projects/artgents-bot-active; branch codex/model-price-experiment;
HEAD/baseline 4be01719c8b05bff8f4496eb7607136ea2d3aec9;
origin/main/merge-base efa3f773bcf10891e2997addf8bbec38c7ae1317; staging пуст.
Allowlist этого сравнения: только этот раздел текущей карточки. Pre-existing
strict-format, four-price, panel/launcher WIP и prototypes/ сохранены.
Runtime, KB, schemas, prompts, model и активный HTTP режим не менялись.

Owner явно разрешил 6 дополнительных provider calls: 3 synthetic fresh вопроса,
каждый один раз json_object и один раз текущий json_schema strict. Snapshot/view
загружен один раз; одинаковые system/user/context в каждой паре подтверждены SHA256.
История пустая, freshness unknown, revision/turn 0; модель qwen3.8-flash,
temperature0, max_completion_tokens1024, timeout20, SDK retries0.
Порядок: overview JSON→strict; Nobel strict→JSON; compound JSON→strict.
Временный harness: C:/Users/denis/AppData/Local/Temp/d2-format-paired-981l6zm0/probe.py.
Offline fake run6: проверки сценариев/пар/budget прошли, provider0.
Live metadata: C:/Users/denis/AppData/Local/Temp/d2-format-paired-_u8x5nsp/report.json.
Hard budget6/6 исчерпан; reservations до transport; retries/fallback0.
Report содержит только hashes, operation fields и usage, без prose/raw prompts,
provider bodies, secrets или пользовательских разговоров. HTTP/session/lead/
materialization отсутствуют; browser0; commit/push/merge/deploy не выполнялись.

| Вопрос | json_object | json_schema strict |
|---|---|---|
| Сколько стоит имплантация? | price topic implantation | price clarification service classic/all_on_4/all_on_6 |
| Сколько стоит имплантация Nobel Biocare? | price topic implantation, brand nobel_biocare | price brand nobel_biocare, target отсутствует, clarification отсутствует |
| Сколько стоит отбеливание и где вы находитесь? | price service professional_whitening + contact contacts | price clarification service professional_whitening/veneers + contact contacts |

Все6 parser_accepted/finish stop, completion_tokens31/83/35/40/48/59:
не truncation. В JSON режиме3/3 ожидаемых ценовых targets; strict0/3.
Адрес в этой паре НЕ потерян: оба режима вернули общий contacts (не узкий address).
Это целевые assertions, не полная проверка смысла: лишние параметры/defaults,
точность prose, финансовая публикация и end-to-end UI в probe не аттестуются.
Strict Nobel демонстрирует существующую structural дыру PriceOperation.target=None;
по текущему коду такой блок может достигнуть d2_price_target_required после policy/
brand paths. Runtime последствия здесь не проверялись через /ask.

Вывод: controlled comparison даёт сильный сигнал ухудшения выбора ценовой задачи
при strict configuration. Один sample на режим не доказывает стабильную частоту,
детерминизм или внутреннюю причину provider/schema decoding. Не доказано, какой
keyword/union/default виноват, что увеличение prompt является причиной или что
JSON режим надёжен вообще: исторические root-array failures остаются известны.
Independent Astra review: hashes/result fields подтверждены; диагностический
вывод согласован, причинная уверенность и semantic scoring ограничены как выше.
Моих дополнительных provider calls0. git diff --check clean; staging пуст.
Рабочий strict HTTP остаётся включённым; проблема OPEN, исправление не выполнено.
Следующий предлагаемый шаг: отдельно согласовать возврат HTTP json_object для
виджета, затем упрощение producer contract с сохранением Target Contract §3;
не добавлять repair arrays, phrase heuristics, второй смысловой слой или retry.

## Строгий формат D2 — HTTP activation, owner GO 2026-10-10 (история, позднее отменена)

Тип: bug fix формата, не выполненное архитектурное упрощение.
Owner согласовал типизированные схемы ordinary/known-task, offline проверку и
подготовку отдельной capability проверки, затем явно разрешил максимум 4 live calls.
Бюджет исчерпан: 4/4, без повторов. HTTP теперь использует json_schema strict.
Root/Git top C:/Cursor Projects/artgents-bot-active; branch codex/model-price-experiment;
HEAD/baseline 4be01719c8b05bff8f4496eb7607136ea2d3aec9;
origin/main и merge-base efa3f773bcf10891e2997addf8bbec38c7ae1317; staging пуст.
Allowlist: contracts/d2_dialogue_result.py; core/d2_live_provider.py;
scripts/check_d2_structured_output.py; tests/test_d2_structured_output.py;
этот файл; DEMO_D2_INTERFACE_TASK.md; DEMO_D2_DELIVERY_ROADMAP.md.
Pre-existing four-price fix, panel/launcher и untracked prototypes/ сохранить.
Накопленный diff этого документа содержит также ранее проверенный four-price fix.
Действует единственная таблица ответственности Target Contract §3.

Acceptance: typed known-task reply — один источник schema и structural validation;
сохранить exact count/order/request IDs, прежние contract codes и server-owned
target/source/brand/volume. Strict helper генерирует ordinary schema из текущих
runtime типов, known-task schema из typed wire reply; без semantic adapter,
преобразования ответов, изменения optional fields/unions или weakening.
HTTP использует strict helper; messages/model/1024/one-call прежние.
Исторический CP3 harness вне HTTP остаётся без изменений.
Python/context/tenant validators остаются. Не изменять KB, storage, UI или quotas.

Probe script по умолчанию готовит schemas/messages offline, 0 calls. Live требует
--live --max-calls 4 --output <fresh external directory>, SDK retries=0;
hard4 reservations записываются до transport, повторный запуск/возобновление
запрещены, первый отказ завершает run, fallback отсутствует. Cases: adversarial
simple schema, ordinary Nobel price, compound price/address, known explanation.
Builder/parser реальные; контекст synthetic, без DB/lead/диалогов пользователя.
Report только metadata и parser outcome, без raw provider body, prompt или secrets.
Этот probe проверяет capability/parser, не точность ответа/публикацию/весь D2.

Astra before-code consultation (историческое состояние до probe): границы подтверждены; поддержка нашего
$defs/anyOf/oneOf/discriminator/default dialect ещё не доказана. Автоматически
делать все optional fields required нельзя. Правила Python не полностью выражены
в JSON Schema; strict generation не гарантирует смысл или отсутствие truncation.
Planned tests: new focused schema/parser/probe tests и existing SIM2/known-task
HTTP suites, isolated temp DB/logs/tenant, network/provider/SMTP forbidden.
Ledger draft до probe: подготовка strict format; HTTP activation и live acceptance были открыты;
commit/push/merge/deploy не выполняются.
Final evidence: C:/Users/denis/AppData/Local/Temp/d2-strict-final-yq051xx6/tests.xml
— 112 cases, 108 passed / 4 failures, 61.80s: новые schema/parser/probe31,
SIM2 contract50 и source-followup HTTP27 прошли. Четыре старых REC2 optional-ref
кейса падают на первом ordinary ответе до changed known-task path. Все четыре
имени и first-step assertion воспроизведены на чистом git archive HEAD4be0171:
C:/Users/denis/AppData/Local/Temp/d2-strict-baseline-bxip3sf9/baseline.xml,
4 failed, 6.76s. Они не объявляются исправленными; полный CI не запускался.
Initial73/4 выявил ошибка выбора code из derivative tuple-length; исправлена,
adverse wire-order/identity/text проверки добавлены, входят в финальные31PASS.
Network/provider/live/SMTP0; browser0. git diff --check clean. Staging пуст.
Independent Checker: PASS offline preparation после focused recheck; оба XML
прочитаны независимо, four baseline failures совпали, test weakening нет.
Эта строка evidence относится к offline preparation до последующего live GO.

Live capability evidence: C:/Users/denis/AppData/Local/Temp/d2-strict-live-7a379256fb104c4791a5d27e3b7ff514/report.json.
Все четыре ответа parser_accepted, finish_reason stop: adversarial simple schema,
ordinary price, compound price/address, known explanation. Фактический endpoint
qwen3.8-flash принял неизменённые runtime schemas, включая unions/$defs/defaults.
Это проверка транспорта/schema/parser, без materialization и session commit.
Составной вопрос вернул только price, без contact: смысловой пробел НЕ закрыт.
Нельзя считать четыре результата доказательством полноты диалога или гарантией
отсутствия будущих отказов. Новые provider calls требуют отдельного бюджета.
HTTP activation удаляет json_object из рабочего пути; schema берётся из тех же
типов, что parser. Нет repair/fallback/retry, дополнительных model calls, KB edits
или изменения владельца цен. Python/context/tenant проверки сохранены.
Activation offline evidence: C:/Users/denis/AppData/Local/Temp/d2-strict-active-jt89y_m7/tests.xml,
108 passed, 49.97s (schema/parser/probe31, SIM2 contract50, source-followup HTTP27).
Provider/live в этом offline run0; суммарный live budget4/4. Browser0.
git diff --check clean; staging пуст; commit/push/merge/deploy не выполнялись.
Independent Checker activation: scoped PASS; final XML и live metadata прочитаны
независимо. PASS только для format fix, не для полноты смысла/всего D2.

## Четыре ценовых ситуации — owner GO

Bug fix отображения, не архитектурное упрощение. Baseline 4be0171,
root/Git top C:/Cursor Projects/artgents-bot-active, branch
codex/model-price-experiment, origin/main/merge-base efa3f77.
Allowlist: core/response_text_renderer.py; core/response_ui_projection.py;
static/widget/widget.js; tests/test_d2_price_cards.py;
tests/test_d2_price_cards_browser.py; этот файл.
Pre-existing panel/launcher WIP и prototypes/ сохранить вне scope.
1. Опубликованная fixed/from/range цена — карточка.
2. Не оказываемая услуга — прежний authored policy text, без чужой цены.
3. Активная услуга без прайса — прежний gap text, не отказ в услуге.
4. no_public_price — утверждённый текст без отдельной ценовой карточки.
В mixed overview сохраняется один ordered навигационный контейнер: numeric
rows оформляются ценой, no_public row обычным абзацем на прежней позиции.
Frozen rows/action pool/selection/applicability/context не меняются. Typed
price ownership сохраняется и без numeric card. Accepted exact offer click
может публиковать текст вместо nextCard, без ложной ошибки; старый ответ
остаётся историческим. Нет новых схем модели, storage, KB, семантических
эвристик, retry, provider calls или новых missing-data policies.
Astra консультация: минимальное разделение presentation rows, не фильтрация
canonical pool. Проверки существующими offline cases четырёх ситуаций;
новые вопросы в панели и новые test-case группы не добавлять.
Evidence: C:/Users/denis/AppData/Local/Temp/d2-four-price-cases-vsq7m5gh/tests.xml
— 41 passed, 0 failed/errors/skips, 57.162s; existing numeric/no-public,
missing service/price, mixed/order/replay и focused browser text-selection cases.
Node syntax PASS; git diff --check clean. Independent Checker: PASS,
финальный JUnit прочитан независимо; selection/auth/lead/privacy и содержательные
assertions сохранены. Provider/live/SMTP 0. Full CI и известные пять legacy
price_modes failures вне scope, не объявляются закрытыми. Staging пуст;
commit/push не сделаны. Panel/launcher WIP и prototypes/ сохранены.

## Текущий checkpoint C4–C6 — 2026-10-10

Функционал кодовых карточек: exact offer состав/исключения/этапы; общий
overview → volume → service → brand в одной карточке; исторический возврат
и следующий текстовый вопрос; типизированные коммерческие разделы.
База клиента неизменна. Не аттестуются live понимание, весь CI и глобальное
архитектурное упрощение. Прототипные radio/compare и финансовые расчёты вне scope.
Checker нашёл и исправлены три C5 дефекта: duplicate external volume controls,
ложная ошибка вместо принятого non-card clarification, stale overview intro.
Focused browser сравнивает authored clarification и отсутствие повторных
controls/карточек, intro replacement и accordion без API.
Evidence: d2-cards-verified-axixxn3p/tests.xml — 65 passed, 0 failed, 116.73s;
64 scoped card tests + 1 focused browser. Node syntax PASS; diff --check clean.
Independent Checker C4–C6: PASS после focused recheck трёх замечаний;
финальный XML независимо прочитан, новых blockers/test weakening нет.
Предварительные failures были неверными новыми fixture assertions: наличие
commercial additions для услуг без них и угаданная фраза уточнения. Exact
content/absence assertions сохранены. Известные 5 legacy price_modes failures
не входили в прогон и не объявляются закрытыми. Provider/live/SMTP 0.
User GO разрешает checkpoint commit/push в текущую ветку; 11 allowlisted files,
prototypes/ остаётся foreign untracked. Owner widget/design review следующий.

## C4 — состав и оплата внутри карточек, часть полного owner GO 2026-10-10

Новая UI функция по первому prototype; базу/формулировки не менять.
Baseline d9cbe8a, branch codex/model-price-experiment, root/Git top
C:/Cursor Projects/artgents-bot-active, origin/main/merge-base efa3f77;
tracked clean, prototypes/ foreign. Allowlist contracts/response_plan.py;
core/response_plan_materialization.py; static/widget/widget.js/widget.css;
tests/test_d2_price_cards.py; этот файл; DEMO_D2_DELIVERY_ROADMAP.md.
Frozen price row получает presentation-only includes/excludes/stages из
того же проверенного offer. Один formatter этапов для карточки и detail reply.
Local details не вызывает API/provider и не меняет выбранный offer/контекст;
серверные ссылки тех же данных скрываются только при наличии accordion.
Условия остаются видимыми; empty data не создаёт accordion или обещаний.
Ответы по текстовому includes/stages вопросу сохраняют существующий путь.
Нет новых model schema, storage state, semantic classifiers, KB changes.
Следующие части полного задания: overview/service/volume actions и typed
commercial grouping. C4 сам по себе не закрывает всё задание.
C4 evidence: d2-card-details-qjsogkgd/tests.xml — 16 passed, 32.71s;
Independent Checker PASS. Browser/provider/live/SMTP 0. Owner проверяет
внешний вид после функциональных частей полного задания.

## C5 — единая overview карточка с объёмом, услугой и брендом

Продолжение полного owner GO, новая UI возможность, не глобальное упрощение.
Baseline d9cbe8a плюс проверенный C4 WIP, та же branch/root. Расширение allowlist:
core/response_text_renderer.py; core/response_ui_projection.py; core/d2_dialogue.py;
остальные C4 файлы и existing card/browser tests. Client KB неизменна.
Начальный overview сохраняет прежние pool/order/cap и не выбирает первую
услугу. Для услуг опубликованного обзора исходный eligible action pool
формируется прежним exact-service selector с исходными brand/volume фильтрами.
Клик использует этот закрытый pool, не расширяет каталог. Service choices
и overview descriptor — presentation metadata исходного frozen результата.
Исторические volume actions расширяют C3 только для выбора объёма внутри
той же карточки: тот же exact receipt auth/lead/TTL/CAS, прежняя server task.
Widget хранит исходные volume controls/revision как данные карточки, не
отдельный semantic context. Выбор подтверждается completion, никаких
optimistic prices, новых model calls или обычной модели на known click.

## C6 — коммерческие разделы той же карточки

Продолжение owner GO на полный функционал карточек, новая UI функция.
Allowlist C5 неизменен; baseline d9cbe8a, root/Git top
C:/Cursor Projects/artgents-bot-active, branch codex/model-price-experiment,
origin/main/merge-base efa3f773bcf10891e2997addf8bbec38c7ae1317.
Текущий WIP C4/C5/C6; foreign untracked prototypes/ исключён.
Presentation-only price_section задаётся renderer по типу существующего
проверенного источника: conditions/promotion/compatibility/benefits/consultation.
Widget группирует эти точные тексты внутри карточки. Акции раскрываются
локально; обязательные условия и compatibility видимы сразу. Контакты и
независимые ответы остаются снаружи. Финансовые дополнения внутри карточки
визуально предшествуют независимому ответу после карточки; wire-порядок
request parts сохраняется. Это согласованная единая карточка, не новый
семантический selector и не классификация по словам.
Нет расчётов скидки/рассрочки, radio выбора финансового предложения,
новых model calls, памяти, KB формулировок или payment semantics.
Прототипные compare/radio controls не объявляются реализованными.

## C3 — возврат к историческим ценовым табам, owner GO 2026-10-10

Новая UI возможность, не архитектурное упрощение. Baseline 29aef61,
codex/model-price-experiment, C:/Cursor Projects/artgents-bot-active;
origin/main/merge-base efa3f77, tracked clean; foreign prototypes/ сохраняется.
Allowlist: core/d2_dialogue_store.py; core/d2_dialogue.py;
static/widget/widget.js; tests/test_d2_price_cards.py;
tests/test_d2_price_cards_browser.py; этот файл; DEMO_D2_DELIVERY_ROADMAP.md.
Owner согласовал: только price_select может использовать ранее опубликованный
receipt; после выбора следующий текстовый вопрос относится к выбранному offer.
Активная и paused заявка блокируют выбор без изменения заявки. Обычное
незавершённое уточнение отменяется при явном возврате к offer.
Точный источник — существующий ui_revision в tenant/sid; нет новых API полей,
storage schema, отдельной памяти/кэша, классификации или provider вызова клика.
Проверяются единственность receipt, owner/revision/linkage, опубликованный ref
и private action map. Все остальные UI actions сохраняют latest-only gate.
Исполнение использует текущий snapshot и прежний CAS/current revision;
idle TTL и fingerprint клиники прежние, новый возраст карточки не вводится.
Widget сохраняет цену до commit, положение, отсутствие ожидания и новый
контекст через completion. Даже активный таб старой карточки возвращает тему.
Проверки: JSON/SSE history→click→typed includes/stages/consultation/replay;
поддельные источники, tenant/session, latest-only detail, TTL/fingerprint,
active/paused lead без потери ПД, pending clear. Provider/live/SMTP budget 0.
Owner вручную проверяет виджет; browser suite assertion мигрирует под C3,
автоматический browser run сейчас не требуется. Commit/push не разрешены.

C3 evidence: d2-history-y7ni6rvc/tests.xml — 41 passed, 1 старое ожидание
отказа историческому price_select failed, 73.38s. Runtime после прогона не
менялся; ожидание мигрировано в проверку точного возврата к classic/Impro.
d2-history-final-otmdmjug/tests.xml — 5 passed, 7.95s: мигрированный случай,
3 проверки reader identity/duplicate/linkage и усиленный historical closed-pool
guard. Всего 45 distinct scoped cases, не полный CI. JSON/SSE continuation
через fake provider, не подтверждение живого понимания. Старые 5 failures
price_modes этим этапом не закрыты. Node syntax PASS, diff --check clean;
browser/provider/live/SMTP 0; staging пуст; prototypes/ сохранён.
Independent Checker C3 PASS: семь файлов allowlist и оба XML прочитаны;
historical source/auth, current CAS/TTL/fingerprint, lead/pending и continuation
подтверждены в scoped offline границах. Owner-widget остаётся следующим шагом.

## Карточки C2 — первый вариант и переключение на месте, owner GO 2026-10-10

Owner выбрал первый вариант после сравнения двух макетов: карточка сразу
открывает первый конкретный offer в существующем порядке каталога. Этот offer
становится опубликованным и текущим для уточнений. Цена/brand/volume и
коммерческая финализация вычисляются по нему, альтернативы — только UI actions.
Это новая UI функция, не глобальное архитектурное упрощение. §3 не меняется.
Runtime baseline HEAD 0391420, branch codex/model-price-experiment;
root/Git top C:/Cursor Projects/artgents-bot-active;
origin/main/merge-base efa3f77; tracked tree/staging были чистыми.
Foreign WIP prototypes/ сохраняется, макеты в Git не добавляются.

Exact allowlist: contracts/response_plan.py; core/response_plan_materialization.py;
core/d2_dialogue.py; core/response_text_renderer.py; core/response_ui_projection.py;
static/widget/widget.js; static/widget/widget.css; tests/test_d2_price_cards.py;
tests/test_d2_price_cards_browser.py; этот файл; DEMO_D2_DELIVERY_ROADMAP.md.
Необходимое расширение после guard run: tests/test_d2_demo_audit_fixes.py,
только expectation price→detail click: initial-first означает один открытый
offer. Прямой detail без предшествующей цены продолжает проверять все три.
Добавлены точный finalized ID и наличие исходных трёх authenticated choices.

Точный исходный eligible pool живёт в прежнем ui_plan.price_select_actions
latest completion. При клике наследуется только этот закрытый набор с повторной
проверкой источников; явный brand/volume не расширяется каталогом. Новый результат
публикует только выбранный offer, без отдельной selected-offer памяти, новых
ordinary-model полей, provider calls или retry. Detail относится к этому offer.
Автоматические финансовые дополнения пересчитываются прежним resolver для
обновляемой карточки; подавление повторного показа по истории здесь не скрывает
части этой же карточки. Обычные ходы сохраняют прежнее подавление.

Presentation-only price_owned на text part обозначает принадлежность ценовому
фрагменту по typed renderer источнику. При замене карточки widget обновляет этот
фрагмент и controls/revision, сохраняет независимый адрес/прозу на их местах.
Клик не добавляет bubbles; до server commit старый вариант остаётся видимым.
Временная UI привязка request_id к исходному message переживает manual retry,
не уходит в API и не хранит финансовый выбор. Reset очищает её.
Серверный replay, TTL, forged/stale/foreign и lead/privacy остаются обязательными.

Acceptance: initial-first context/detail; A→B→A без модели; точный ID при двух
offers одного brand; фильтры не расширяются; JSON/SSE/replay; mixed price/address
в обоих порядках и замена финансовых дополнений; error/manual retry без нового
пузыря или optimistic цены; 360/390 layout, шрифты 16/14/30, stale/lead guards.
Клиентские цены/данные/формулировки не менять. Overview и новый marketing/detail
дизайн сюда не входят. Offline → независимый Checker → owner widget.
Provider/live/SMTP 0; commit/push/merge/deploy не разрешены.

### C2 evidence — 2026-10-10

Owner widget follow-up: brand switch caused an up/down scroll jump. This is a
presentation bug fix, not architecture simplification. Follow-up allowlist:
static/widget/widget.js, tests/test_d2_price_cards_browser.py, this task.
Preserve the current scroll position while the existing priceUpdate request is
pending and when its confirmed result/error replaces the card. New ordinary
turns keep their existing scrolling. No backend/KB/action contract changes.
Browser regression samples card position each animation frame across a delayed
offline selection response, rather than checking only the final position.
Offline browser: d2-tabs-scroll-97bcr0xc/tests.xml — 1 passed, 11.22s;
node --check PASS, git diff --check clean. Provider/live/SMTP 0.
Independent focused Checker PASS: pending/final/error preserve viewport;
ordinary turns retain auto-scroll. XML independently read, no blockers.

Owner follow-up: no loading text or indicator during brand switches; retain
only the shared answer attribution above the card. Presentation bug fix in
the same three-file follow-up allowlist. Existing server-authenticated selection
and next-turn scope stay unchanged, no preloading/new cache. The existing
priceUpdate binding suppresses the ordinary typing display and cosmetic timers
only during in-place selection (including manual retry). Ordinary questions
retain waiting labels. Browser observes a four-second fake response across
all three cosmetic phase deadlines, requiring no visible waiting indicator.
Evidence: d2-tabs-silent-ql2ri23c/tests.xml — 1 passed, 13.35s; node syntax
PASS, diff --check clean; provider/live/SMTP 0. No commit or push.
Independent focused Checker PASS for silent switching/manual retry; ordinary
waiting behavior unchanged. Owner confirmed widget behavior and authorized
checkpoint commit/push of C2 before historical-card work, 2026-10-10.
Owner verification preference: do not run browser tests for routine minor
visual changes; owner checks those in widget. Reserve automated browser runs
for complex interaction behavior, use only necessary internal checks.

- C2 заменяет brand click→новый user/bot bubble на обновление финансового
  фрагмента исходного message после подтверждения. Default-first применяется
  до detail/compatibility/finalized IDs; нет скрытых published offers.
- Добавлены candidate validation, сохранение существующей private action map,
  presentation-only text ownership, transient request→message binding и табы.
  Ordinary model schema, provider/prompt, KB, storage schema и backend replay
  не менялись. Client не вычисляет цены и не хранит отдельный selected offer.
- `d2-tabs-final-hn1_sa75/tests.xml`: **23 passed**, 35.864s — JSON/SSE,
  exact offer/replay/next context, закрытый explicit-brand pool, оба порядка
  price/address, real browser 360/390, A→B→A без bubbles, failed transport
  (оба прежних attempts)→manual retry same ID, no optimistic price, отсутствие
  transient typed price и неактивные исторические вкладки.
- `d2-tabs-guards-mvidov2_/tests.xml`: **58 passed, 2 failed**, 76.78s —
  UI authenticity/volume/doc actions, child/payment policy, limits, lead/privacy,
  CTA replay. Два failures — ожидание всех brands в price→detail из прошлого
  UI; изменён только этот expectation с сохранением direct detail all-offers.
- `d2-tabs-repeat-xz7axwlp/tests.xml`: **8 passed**, 17.14s — два migrated
  guards JSON/SSE + шесть новых owner-requested free-text continuation tests:
  includes/stages/consultation после выбора Impro и повтор вопроса новым ID.
  Ответ текстовый; targetless details используют receipt exact offer, direct
  free-consult повторяет утверждённые квалифицированные условия. Replay бесплатен.
  Это offline fake provider, не доказательство live языкового распознавания.
- Совокупно **89 scoped cases прошли** на неизменённом финальном runtime;
  три XML — раздельные прогоны, не единый full CI. Ранний runtime `model_copy`
  на dataclass trace исправлен на существующий dataclasses.replace. Ранние
  fixture ожидания HTTP400 для SSE и одной сетевой попытки исправлены под
  штатные error frames и ранее существовавший двухпопытный transport.
- Independent Checker PASS C2 по runtime и первому final XML; focused recheck
  новых continuation tests и миграции guard тоже PASS, XML 8 PASS прочитан
  независимо. Node syntax и git diff --check чисты.
- HEAD 0391420, staging пуст, 12 changed tracked files с описанным расширением;
  prototypes/ остаётся untracked. Provider/live/SMTP 0. Commit/push/merge/deploy
  не делались. Пять legacy failures test_d2_price_modes.py из R1 не проверялись
  повторно и здесь не закрываются. Full CI и owner widget acceptance впереди.

## Pause checkpoint — owner commit/push GO 2026-10-10

Владелец завершает работу на сегодня и разрешил commit/push: «Делай».
Название checkpoint: `checkpoint(widget): restore code prices and price cards C1`.
Сохраняется R1 + проверенный C1 + presentation fix без промежуточного typed текста.
Это не завершение всех карточек. Следующий согласованный UI шаг — переключать
три бренда внутри одной карточки без нового пузыря; затем overview, лёгкие
иконки, состав/оплата в аккордеонах и маркетинговая компоновка. Пока эти шаги
не реализованы. Клиентскую базу можно менять только по отдельному согласованию.

Preflight root/Git top C:/Cursor Projects/artgents-bot-active; branch
codex/model-price-experiment, HEAD c22845c; origin/main/merge-base efa3f77.
Baseline checkpoint — текущий проверенный R1+C1 working tree. Staging пуст.
Точный staging allowlist (включая R1 пути без substantive diff):
contracts/d2_dialogue.py; contracts/d2_dialogue_result.py;
contracts/d2_tenant_snapshot.py; contracts/response_plan.py;
core/d2_dialogue.py; core/d2_live_provider.py; core/d2_tenant_snapshot.py;
core/one_call_prompt_contract.py; core/response_plan_materialization.py;
core/response_plan_resolver.py; core/response_text_renderer.py;
core/response_ui_projection.py; static/widget/widget.js; static/widget/widget.css;
tests/test_d2_price_catalog_input.py (удаление experimental-only test);
tests/test_d2_price_cards.py; tests/test_d2_price_cards_browser.py;
docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md; этот файл.
prototypes/price-chat/index.html остаётся local untracked и не включается.
Никаких secrets/.env/logs/DB/raw provider conversations/данных клиентов в commit.
Проверки и независимые Checker PASS приведены ниже; пять старых legacy failures
R1 остаются baseline debt. Full CI не запускался, live/provider/SMTP 0.

## Карточки C1 — owner GO 2026-10-10

Владелец «Давай»: первый checkpoint в реальном виджете — цена конкретной
услуги и проверенный выбор предложения/бренда, шрифт 16/14. Тип: новая UI
функция, не глобальное архитектурное упрощение. Один frozen финансовый
результат материализатора → упорядоченные text/card части → widget. Цена
карточки не дублируется видимым текстовым форматтером; plain answer остаётся
текстовым представлением тех же частей для транспорта/receipt. Никакого
разбора строки answer, второго выбора прайса или отдельной памяти бренда.
Выбор опубликованного offer через существующие ref/revision создаёт известную
price-задачу без модели; только выбранный offer публикуется в новом completion.
Первоначально все варианты видны, без неявного выбора первого. После выбора
карточка одного варианта; прежние кнопки устаревают по обычной revision.
Обзоры остаются прежними. Аккордеоны/новая компоновка маркетинга — следующий этап.
Клиентские строки/данные не менять. Astra consult выполнен, §3 сохраняется.

Preflight: C:/Cursor Projects/artgents-bot-active, branch codex/model-price-experiment,
HEAD c22845c; origin/main/merge-base efa3f77. Baseline — проверенный R1 runtime
3932989 в текущем working tree. Staging пуст. R1 docs и prototypes/ сохраняются.
Exact allowlist C1: contracts/response_plan.py; core/response_plan_materialization.py;
core/response_plan_resolver.py; core/response_ui_projection.py;
core/response_text_renderer.py; core/d2_dialogue.py; static/widget/widget.js;
static/widget/widget.css; tests/test_d2_price_cards.py;
tests/test_d2_price_cards_browser.py; этот документ; DEMO_D2_DELIVERY_ROADMAP.md.
Resolver добавлен к рекомендованному списку: он переносит авторизованные UI
действия из materialized в resolved plan. Другие R1 файлы не менять.
Acceptance: точные frozen цены/условия, порядок mixed ответа, выбор точного
offer и следующий detail/context, zero-provider click/replay, forged/stale/foreign
отказ, child/policy boundaries, мобильный DOM и шрифт. Offline → Checker → widget.
Provider/live/SMTP 0, commit/push/merge/deploy запрещены в этом checkpoint.

C1 implementation/evidence — 2026-10-10:
- C1 presentation follow-up: owner увидел typed plain price перед карточкой.
  Bug fix, не архитектурное упрощение: готовый price_card пропускает старую
  pseudo-typing анимацию текста answer и сразу commit/render карточки. Обычная
  prose сохраняет прежнюю анимацию. Actual D2 SSE публикует готовый UI без deltas.
  Allowlist только static/widget/widget.js, tests/test_d2_price_cards_browser.py
  и этот report; baseline — C1 working tree после scoped Checker PASS.
  MutationObserver проверяет отсутствие transient live bubble у карточек и
  сохранение такой bubble у обычного текста. Backend/KB не менять.
  Final browser XML d2-cards-direct-display-final-5s5p36g8/tests.xml — 1 PASS,
  7.47s, provider/live/SMTP 0. Mismatch guard текста сохранён. Node syntax и
  diff --check clean; independent focused Checker подтверждает scoped fix.
  Один ранний fixture run получил Chrome ERR_UNSAFE_PORT на случайном порту:
  harness разрешает только свой локальный ephemeral port, runtime не меняет.
  Branch/HEAD/staging/push и весь foreign WIP прежние; commit/push не делались.
- Добавлены ordered text/card projection и private authorized offer-select map.
  Видимый price-text для direct service заменён card, plain answer сериализует
  те же части. Карточка не выбирает источники и не разбирает строку answer.
  Порядок mixed сохранён; no-card ответы не дублируются в body_parts.
- Подтверждённый клик использует frozen scope + exact offer ID внутри прежнего
  materializer selector. Завершённый результат содержит один row. Independent
  brand state/новых schema для ordinary model/новых model calls нет.
  Lead pause убирает обе private финансовые action maps до projection.
- Eight runtime/UI files плюс два новых теста и два existing docs; точный
  allowlist выше. Клиентский каталог не менялся, prototype и R1 сохранены.
  Числовая цена крупная; no_public authored текст 16px; основные данные 16px,
  условия/brand controls 14px. Overview/detail/marketing пока прежние.
- guards-k3vl4jel/tests.xml: 192 passed, 0 failed/skipped, 198.68s;
  final-ljp79rix/tests.xml: 16 passed, 0 failed/skipped, 20.43s;
  browser-final-216a_y_4/tests.xml: 1 passed, 0 failed/skipped, 10.69s.
  Все каталоги с префиксом d2-cards-c1- в C:/Users/denis/AppData/Local/Temp.
  Earlier browser-current-79w5rfmp: 11 passed incl real DOM/browser.
  Первая ошибка запуска — sandbox temp permission; ранние mixed fixtures имели
  invalid operation request IDs/contact_fields. Исправлены сами новые fixtures,
  substantive assertions сохранены. No runtime failures в final scoped sets.
- Independent Astra Checker PASS C1, без weakening/blockers; финальный focused
  recheck no_public font/browser delta тоже PASS. git diff --check и node --check
  clean. Full CI не запускался. R1 пять legacy content_realization failures из
  test_d2_price_modes.py остаются известным baseline debt вне этих наборов.
- Branch codex/model-price-experiment, HEAD c22845c unchanged, staging пуст;
  commit/push/PR/merge/deploy не делались. Provider/live/SMTP 0. Сохранённый R1
  rollback и prototypes/ — оставшаяся отдельная работа, не объявлена committed.
  Owner widget acceptance ещё предстоит после restart + новой беседы.

## Owner decision — 2026-10-10: эксперимент прекращён, кодовые финансовые блоки

Владелец: «Однозначно откат от модельных ответов и делаем вот это» — после
просмотра отдельного интерактивного прототипа. Это замена направления, не
разрешение оставить model financial prose как fallback или параллельный режим.

Checkpoint R1: технический откат эксперимента, не внедрение нового интерфейса.
Root/Git top C:/Cursor Projects/artgents-bot-active; существующая ветка
codex/model-price-experiment, HEAD c22845c; origin/main и merge-base efa3f77.
Восстановление только финансового runtime к 3932989. Ранее согласованные
чистка KB, commercial scope, privacy/lead и спокойное оформление ошибок остаются.
Новых веток, commit/push, live/provider/SMTP, merge/deploy нет.

Exact allowlist R1: contracts/d2_dialogue.py; contracts/d2_dialogue_result.py;
contracts/response_plan.py; contracts/d2_tenant_snapshot.py; core/d2_dialogue.py;
core/d2_live_provider.py; core/d2_tenant_snapshot.py; core/one_call_prompt_contract.py;
core/response_plan_materialization.py; core/response_text_renderer.py;
tests/test_d2_model_financial_prose.py; tests/test_d2_price_catalog_input.py;
этот документ; docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md.
Перед изменением сохранена точная копия этих 14 файлов с SHA256 manifest во
временной папке C:/Users/denis/AppData/Local/Temp/d2-model-price-archive-r301bn5i.
Два тестовых файла относятся только к удаляемому экспериментальному контракту;
проверки действующих цен/политик/tenant/pending/replay не изменяются и не ослабляются.
prototypes/price-chat/index.html — отдельный пользовательский макет вне allowlist.
Клиентские данные, runtime UI/HTTP, квоты, заявки и состояние Git не изменяются.

Удаляются financial_text, D2FinancialTask, source declarations/free financial
prose admission/numeric gate и полная передача финансового каталога в prompt.
Возвращается прежний единственный владелец финансового результата — код,
понимание обычного вопроса и объяснения по базе остаются у модели (§3).
Текстовая сборка временно прежняя; новый интерактивный финансовый результат
ещё не внедрён. Исторические 3A/3B PASS ниже не подтверждают новый этап.

Следующий checkpoint — единый кодовый финансовый результат для виджета:
цена/бренд/единица/«от»/обязательные исключения связаны с конкретным offer;
обзор, состав, stages и условия оплаты отображаются готовыми компонентами.
Один вызов для свободного вопроса; проверенные финансовые UI действия не
должны повторно классифицироваться моделью. Нет произвольной арифметики,
скидка «до 15%» не превращается в гарантированные 15%, рассрочка не даёт
выдуманный месячный платёж. Клиентский каталог меняется только после отдельного
согласования. Выбор бренда/метода должен сохранять server-authorized identity
для следующего вопроса; нельзя просто переключить цену локально и оставить
серверу прежний контекст. Реализация следующего checkpoint фиксируется отдельно.

R1 verification: все 10 runtime-файлов побайтово восстановлены из 3932989;
git diff 3932989 по ним пуст. Поиск в contracts/core не обнаружил FinancialText,
D2FinancialTask, approved_price_catalog_json или _d2_financial_text. Действующие
тесты не менялись. rollback.xml: 157 passed, 5 failed, 152.25s; пять падений
test_d2_price_modes.py воспроизведены в отдельной чистой копии 3932989
(baseline.xml: те же 5 failed, 2.84s). Старая fixture передаёт удалённое поле
content_realization; это baseline debt, не новый runtime отказ. Новых failures
нет. Проверены tenant snapshot/KB2, compact price copy, known actions, локальные
price gaps, commercial applicability/compatibility/replay, completion context
и stale/foreign/forged UI/CTA. Проверки сети заблокированы, provider/live/SMTP 0.
Артефакты в временной папке архивирования; git diff --check чист. Full CI не
запускался, widget/live качество не аттестовано. Старые сессии не мигрировались
и не удалялись: после restart для проверки нужна «Новая беседа».


## Один выбор финансовых источников — checkpoint 3B, owner GO 2026-10-10

Owner «Делай» после независимого аудита Astra варианта B. Baseline c22845c
+ сохранённый незакоммиченный 3A (10 файлов); root/branch/main/merge-base
совпадают с 3A; staging пуст, foreign WIP нет. Exact allowlist прежние 10
файлов 3A. Данные клиентов, автоматические promo/packages/compatibility,
HTTP/widget/lead/privacy и новые поля памяти не менять. Provider/live/SMTP 0.

Тип: архитектурное упрощение + согласование producer-контракта. Before → after
→ removed dependency: модель предугадывает code-selected ordered subset →
модель выбирает источники и порядок ordinary финансовой речи, код проверяет
каждый источник по captured pool/brand/volume/activity/applicability → удалить
ordinary sort/first-per-service/top-three selection и необходимость равенства
двух независимо выбранных списков. Владелец relevance/coverage/order — модель,
owner точных данных/допустимости/UI/compatibility — код. Полнота обзора больше
не гарантируется прежним алгоритмом. Условия/единицы/смысл prose остаются
экспериментальным риском; exact monetary literal gate сохраняется.

Known financial click: существующая серверная задача получает refs до call
в своём ephemeral financial_text draft (пустой text); это не ordinary ответ
и не запись состояния. Model reply меняет только текст; parser bind refs
из исходной задачи. Старый selection разрешён только для server-owned known
price scope, не для ordinary. Проверенный detail action сохраняет exact IDs.
Новая схема/память/второй вызов/repair/fallback не вводятся.

Согласовать ВСЕ финансовые инструкции, completed/pending примеры и отправляемую
producer schema; убрать старые обещания code-written price/detail prose.
Runtime missing/empty financial part остаётся local gap, не whole-turn reject.
Подготовка known sources не является новым ранним policy/reference gate.
Acceptance: arbitrary eligible subset/order, brand/extent/inactive/foreign,
known price/detail/service source binding before call, refs optional in known
reply, current detail vs stale source, direct/negative/promotion applicability,
JSON/SSE, compound/gap, exact amount, next projection, replay и single call.
Offline → независимый Checker → owner widget. 3A PASS не доказывает 3B.

Из реализации: ordinary _d2_price_block только проверяет объявленные IDs в
eligible pool и материализует их в модельном порядке. Старый selector доступен
только prepare known price до provider. Detail identity общий для подготовки
known и последующего допустимого model subset; commercial active/applicability
pool общий, negative source не становится показанной положительной выгодой.
Новых wire/state полей нет: known-task draft используется только в этом call,
parser берет из reply text и связывает с серверными refs, не с модельными.
Producer schema требует completed financial key и поля text/offer_ids/fact_ids,
но runtime defaults оставлены ради local gap; transport JSON_object не строгая
schema enforcement и не гарантия live-compliance. Prompt v44 удаляет старые
completed price/detail examples без текста и code-written overview instruction.

Checker первоначально REJECT: known detail-service binding использовал price
selector вместо detail identity; known commercial включал unavailable fact.
Обе причины удалены общими identity/eligibility helper, а не сценарным catch.
3b-checker-fixes.xml: 11 passed (15.97s), focused independent recheck подтвердил
закрытие P1. 3b-final.xml: 109 passed ДО этих extraction-правок; это промежуточное
свидетельство. Финальный coherent прогон и итоговый Checker ниже после завершения.
Новый inactive fixture сначала нарушил authored direction: loader корректно
отказал до provider; это дополнительно проверено как strict snapshot fault,
а eligibility inactive source проверяется отдельно на captured catalog.

Финальное дерево: 3b-final-verified.xml — 130 passed, 0 failed, 2 deselected,
119.70s. Включены 99 финансовых tests, 5 captured input, 10 clinic policy и
16 guard tests. Две deselected старые tenant fake-envelope проверки без
financial_text уже несовместимы с 3A; это contract migration, не baseline
failure. Их содержательные гарантии отдельно покрыты новыми-format тестами
legacy policy edit, exact price, replay, unchanged view, next scope/refs.
Все runtime/tests старше финального прогона. Provider/live/SMTP 0; полного CI
не было; git diff --check чист. Staging пуст; client data/foreign WIP нет;
commit/push/PR/merge/deploy в 3B не выполнялись. Живое качество не аттестовано.
Independent Checker Astra focused recheck: PASS 3B, 2026-10-10. Оба P1
закрыты общими identity/eligibility helper; финальный XML независимо прочитан,
сам Checker tests не запускал. SAFE_TO_WIDGET_TEST=YES. Смысловая точность
prose, live compliance и автоматические дополнения этим PASS не закрываются.


## Модельная финансовая речь — checkpoint 3A, owner GO 2026-10-09

Owner GO: «Давай» после сохранения 2B и предложения подключить модельные цены.
Baseline c22845cb5599d4b3b21edb62e90b025795d933e5; repository/Git top
C:/Cursor Projects/artgents-bot-active; branch codex/model-price-experiment;
origin/main/merge-base efa3f77. Working tree/staging пусты, foreign WIP нет.
Точный allowlist: contracts/d2_dialogue_result.py; contracts/response_plan.py;
contracts/d2_dialogue.py; core/one_call_prompt_contract.py;
core/response_plan_materialization.py; core/response_text_renderer.py;
core/d2_dialogue.py; core/d2_live_provider.py;
tests/test_d2_model_financial_prose.py; этот документ.
Клиентские данные, selection policy, HTTP/widget, lead/privacy и новая память
не входят. Provider/live/SMTP budget 0; commit/push после самостоятельного PASS.

Тип: смена владельца финансовой формулировки в эксперименте с удалением
кодовой сборки прямой financial prose. Before → after → removed dependency:
price/detail/direct commercial описывает formatter/approved text → единственный
model call возвращает prose + source declaration → D2 renderer больше не
собирает эти ответы по строкам/стадиям и не подставляет кодовый текст при отказе.
§3 code-owned selection/applicability/точные данные неизменны; experimental
owner формулировки — модель. Ее refs не выбирают окончательные offers/facts.
Сверка происходит после code selection и до final UI/compatibility/shown IDs.

Combined ordinary + verified financial clicks, по консультации Astra: не вводить
временный mode discriminator для старого formatter. Проверенный клик передаёт
серверную задачу и exact selected detail identity единственному known-task call;
reply меняет только финансовую речь/декларацию источников, не задачу. Document
known-task по-прежнему explanation-only. Replay без provider.

Непустая prose с точными ordered source refs сохраняется в прежних frozen
price/detail blocks и commercial exact block; не patient_text/ordinary prose.
Нет второго вызова, retry, code-prose fallback, semantic regex/classifier.
Пустая/слишком длинная речь либо mismatched refs дают существующий calm gap
для этой части; независимые части сохраняются. JSON/operation/security shape
по-прежнему strict. Candidates для detail привязываются до publication gate,
чтобы отказ price не заставлял detail взять чужую старую цену.
Узкий scanner денежных литералов сверяет выбранные суммы/валюту, требует цены
и запрошенные payment-stage суммы; неподдерживаемая запись даёт local gap.
Не переиспользует legacy semantic verifier. Структурная и числовая сверка
НЕ доказывает правильность единицы/слов «от»,
отрицаний и условий в произвольной речи; это явно принятый экспериментальный
риск, а не гарантия смыслового verifier. Проверять такой риск живыми сценариями
после отдельного бюджета. Client-approved факты не сглаживать.

Полный финансовый переход НЕ закрывается 3A: автоматические promo additions,
booster/also packages и compatibility пояснения пока сохраняют прежнюю кодовую
формулировку и selection. Следующий участок охватывает их, включая content-only
ходы. Не отключать их молча и не объявлять весь answer полностью модельным.

Acceptance: JSON/SSE точная модельная формулировка, code-selected IDs/порядок,
цена/detail/direct/negative commercial, compound + gap, без ложных shown/UI,
next context без financial prose, replay, verified detail/volume/service click
один call и запрет изменения задачи, forged/stale/foreign UI до provider.
Adverse correct refs + wrong amount даёт local gap; correct amount + wrong
unit остаётся явно непокрытым смысловым риском. Старые runtime financial assertions сравнивать с baseline;
не превращать их в status-only. Offline → independent Checker → owner widget.
Финальный 3a-final-verified.xml: 75 passed, 0 failed (69.00s), включая input.
3a-policy.xml: 10 passed. Guards: 16 passed; два старых fake-envelope без
financial_text ожидают кодовую цену и падают — это migration текущего contract,
не baseline failure и не регрессия tenant isolation. Их смысл отдельно покрыт
двумя новым-format JSON/SSE тестами legacy policy edit/replay/next context.
3a-clicks.xml: 17 passed. Provider/live/SMTP 0; full CI не запускался.
Foreign-currency markers USD/$ и основные валюты отвергаются, поскольку
канонический scanner поддерживает RUB. Все нестандартные денежные записи и
смысловые условия не считаются гарантированно распознаваемыми.
Для widget нужна новая беседа: старый frozen result не содержит model_text.
Commit/push пока не выполнялись; 3A не закрывает автоматические дополнения.
Independent Checker Astra: PASS только 3A, 2026-10-10. Проверены все 10
файлов, фактический call path, удаления formatter и adverse outputs.
USD/$ finding исправлен и закрыт; blocking findings нет. Checker прочитал
финальные XML, сам pytest не запускал. SAFE_TO_WIDGET_TEST=YES; живое
качество, весь этап и полный financial switch этим PASS не аттестуются.

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
