# SIM-4 — явный демо-обзор и кодовые финансовые факты

## Последующее состояние — независимый аудит и подготовка передачи

После prompt33 владелец вручную проверил 7 запросов: 6 ответов, 1 parse failure
с повторением структуры (trace7ca91fe2). Это не таймаут: ответ provider получен;
raw оборван при completion_tokens1024/max1024, finish_reason не сохранён.
Нельзя считать исправление примера доказанной устойчивостью. Три удаления
дали универсальный gap из-за отсутствующей applicability per-tooth offers.
Ни это наблюдение, ни аудит не разрешают автоматическое расширение всех offers.
Следующее доведение интерфейса — [отдельная карточка](DEMO_D2_INTERFACE_TASK.md).
Нижние offline/Checker PASS исторически верны в своих пределах. SIM4 не закрыт.

## Текущий bug fix — prompt33, 2026-10-02

GO владельца: начать с найденного неоднозначного примера, без изменения
архитектуры. Baseline: HEAD e6756ee + сохранённый SIM4/D2-116/prompt32 WIP.
Allowlist этого дополнения: core/one_call_prompt_contract.py,
tests/test_d2_sim2_contract.py, tests/test_d2_clarification_scope_http.py,
эта карточка, DEMO_D2_CURRENT_STATUS.md, DEMO_D2_CHECKPOINT_LEDGER.md.
Foreign data/, marketing и SIM0 Task не открывать/не менять.

До: единственный JSON-пример few_teeth/count=3 показывал service clarification.
После: известное направление с объёмом, в том числе в свежем разговоре,
показано как direct price; отдельный пример неизвестной услуги сохранён.
Это исправление инструкции для класса известных ценовых запросов с объёмом,
не удаление runtime-зависимости и не доказанное архитектурное упрощение.
Владелец понимания — модель; ценовой владелец, schema, память и кнопки прежние.
Новых полей/веток/вызовов/repair/fallback нет. Astra read-only консультация
подтвердила гипотезу влияния примера, но причинность ещё не доказана.
Offline проверяет валидность фактически отправленных примеров и сохранение
неизвестной задачи через клик/replay/следующий ход. Известные сценарии D2-116
сохраняются. Live-сравнение требует отдельного hard budget; устойчивость
модели до него не заявлять. Commit/push/live0.

Проверки prompt33: 5 отправленных примеров + 10 scope HTTP cases —
15 PASS /24.53s; 2 оставшихся adverse/personal scope cases — 2 PASS /5.51s.
Это все 12 существующих clarification_scope HTTP случаев плюс 5 примеров.
Независимый Checker PASS: собственный прогон 5 примеров — 5 PASS /3.51s.
git diff --check чист. Полный CI не запускался, прежние 13 baseline failures
ниже остаются. Качество живой модели и причинность гипотезы не подтверждены.

Дата 2026-10-02. Runtime GO: владелец делегировал выбор правдоподобного
демо-набора по существующей базе, без новых цен и без клинического назначения.
D2-114 сохраняет свободную prose с принятым риском; новых verifier/gates нет.
Тип: архитектурное упрощение подборa обзора + изменение демо-данных.
Не закрыто; live/commit/push/merge/deploy не разрешены.

## Текущее дополнение — D2-116, 2026-10-02

Владелец разрешил общий механизм трёх ответов и ранее обсуждённый обзор
восстановления. Продуктовое правило — [D2-116](DEMO_D2_PRODUCT_DECISIONS.md).
Это расширение поведения в существующем механизме, не новое архитектурное
упрощение. Baseline e6756ee и предсуществующий SIM4/prompt31 WIP сохранены.
Строки ниже про неизменность applicability/prosthetics и few_teeth gap
исторические до D2-116. Foreign data/, marketing и SIM0 Task не трогать.

Дополнение exact allowlist:

- core/d2_snapshot_sources.py — универсальный текст отсутствующей цены;
- core/one_call_prompt_contract.py — prompt32: общий обзор/точный вопрос;
- core/response_plan_materialization.py — пояснение разрешённой единичной
  цены при few_teeth в существующих frozen condition_texts;
- clients/demo/target_response/d2_direction_prices.json — общий restoration
  и расширенный prosthetics pool;
- clients/demo/target_response/pricebook/services/classic.one_tooth.implantium.json
  — только разрешение few_teeth, без изменения суммы/состава/full_arch;
- clients/demo/target_response/service_catalog.json — явный active=true у
  согласованных partial/full removable options: раньше active отсутствовал,
  direction loader требует явной активности; проверка не ослабляется;
- tests/test_d2_price_guidance_http.py — новый;
- tests/test_d2_clarification_scope_http.py и tests/test_d2_sim4_overview_http.py
  — новый утверждённый результат few_teeth вместо прежнего gap;
- tests/test_d2_af1a_price_task_http.py — разрешённый brand reference и gap
  другого бренда; tests/test_d2_snapshot_sources.py,
  tests/test_d2_availability_scenarios.py, tests/test_d2_recovery_scenarios.py
  — прежний литерал price-gap заменён утверждённым текстом, без смены fixtures;
- эта карточка, PRODUCT_DECISIONS, TARGET_CONTRACT, ACCEPTANCE,
  DELIVERY_ROADMAP, CURRENT_STATUS, CHECKPOINT_LEDGER — актуальное правило.

До: отсутствие полного расчёта давало общий отказ; обзор протезирования
содержал только коронку. После: явные данные разрешают единичный ориентир,
общий вопрос получает один обзор с разными способами, неизвестная цена
сопровождается универсальным следующим шагом. Единственный владелец
понимания — модель, выбора/цен — прежний код по данным; renderer не решает
применимость. Новых schema/состояний/вызовов/regex/fallback нет. Добавлено
одно условие представления: few_teeth + разрешённая tooth/tooth_package
строка получает пояснение, что это не итог за несколько зубов. После фильтра
кандидаты из всего каталога не добавляются. Astra проверила этот дизайн.

Проверки: обе HTTP формы, one/few и count, ориентир/нет цены/частичный
no_public_price обзор, независимая prose, replay, следующий scope, CTA без
автоматической заявки, фильтр бренда, прежний exact service и защиты соседних
тестов. Новые live/provider calls запрещены без бюджета. Widget — следующий
ручной шаг владельца после restart; offline не аттестует модель/виджет.

### Проверки D2-116

- Основной offline-прогон: price_guidance_http + clarification_scope_http +
  sim4_overview_http — 92 PASS / 118.70 s.
- Соседние http_contract + snapshot_sources + af1a_price_task_http +
  sim1_known_actions_http — 49 PASS, 3 FAIL / 78.19 s.
- availability_scenarios + recovery_scenarios — 10 FAIL / 21.38 s.
- Все 13 последних failure IDs воспроизведены на чистом tracked HEAD
  e6756ee в изолированной копии: эти три старых файла дают 13 FAIL,
  1 PASS / 24.30 s. Это существующий долг fixtures/ожиданий, не зелёный CI.
  Старые route-envelope fixtures не соответствуют активному D2 контракту;
  snapshot_sources также содержит прежние ожидания authored content/binding.
- Первый новый прогон обнаружил отсутствие explicit active у partial/full
  options; исправлены только demo-данные в allowlist, loader не ослаблен.
- HTTP fixtures блокируют сеть и используют временные tenant/DB/logs.
  Provider/live/SMTP: 0.
- Независимый Checker D2-116: PASS, собственный price_guidance_http —
  36 PASS /55.68s. Подтверждены прежний владелец цены, отсутствие новых
  schema/вызовов/памяти, frozen условия, units/count/replay/next projection.
  Это PASS продуктового дополнения, не закрытие SIM4 и не runtime live PASS.
  Fake provider не доказывает выбор restoration живой моделью; длина и
  естественность ответа в widget ещё не проверены. D2-114 риск prose остаётся.
  Cursor gate и ручной widget остаются; commit/push не выполнялись.

## Baseline / allowlist

Root C:\Cursor Projects\artgents-bot-active; branch codex/d2-stage1-contract;
HEAD/origin e6756ee59df4f186e499c29ae41cda0e993d80fe;
main/merge-base 141ce91fb1731cd990fcf8391550150016c73e7f. Staging пуст.
Восемь документов D2-114 — свой pre-existing WIP, сохраняется в checkpoint.
Foreign data/, docs/MARKETING_ANSWER_SCENARIOS.md и отдельный SIM0 Task
не открывать, не stage. Продолжение существующей D2-задачи, не новая ветка.

Exact allowlist:

- clients/demo/target_response/d2_direction_prices.json
- core/response_plan_materialization.py
- tests/test_d2_sim4_overview_http.py (новый)
- tests/test_d2_af1a_price_task_http.py
- tests/test_d2_sim1_known_actions_http.py
- tests/test_d2_sim2_dialogues.py
- docs/tasks/DEMO_D2_SIM4_TASK.md (новый)
- docs/tasks/DEMO_D2_PRODUCT_DECISIONS.md
- docs/tasks/DEMO_D2_TARGET_CONTRACT.md
- docs/tasks/DEMO_D2_ACCEPTANCE.md
- docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md
- docs/tasks/DEMO_D2_CURRENT_STATUS.md
- docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md
- docs/tasks/DEMO_D2_EXECUTION_LOCK.md (D2-114 WIP)
- docs/WORKFLOW_CHECKER.md (D2-114 WIP)

## До → после → удаляется

До: direction ordered offers, запасной поиск применимых offers по каталогу,
отдельный брендовый подбор с service rank/seen_scales и catalog projection
при отсутствии ordered pool конкурируют за состав обзора. У бренда direction
может расширяться до всего семейства, включая специализированные методы.

После: явно утверждённый tenant direction pool → общий brand/extent фильтр →
первый настроенный offer каждой методики → прежний cap 3. Exact service
сохраняет отдельную существующую ветку всех применимых offers без cap.
Удаляются catalog fallback, brand family expansion/ranking/scale selection,
implicit service projection для direction. Никакого нового owner/поля/вызова.
Единственный владелец подбора — код по данным (Contract §3).

## Делегированное решение демо

Implantation service_ids: classic, all_on_4, all_on_6, one_stage.
Ordered pool: первая четвёрка Implantium, затем Impro, затем Nobel:
classic.one_tooth.BRAND, all_on_4.jaw.BRAND, all_on_6.jaw.BRAND,
one_stage.one_tooth.BRAND. Это репрезентативный демо-порядок, не назначение.

Общий/unknown: classic + all_on_4 + all_on_6; one_tooth: classic + one_stage;
full_arch: all_on_4 + all_on_6; few_teeth: существующий честный пробел общей
цены, без умножения. Бренд фильтруется до выбора представителей методик.
Точные суммы/units/includes/excludes остаются в pricebook. Implantium:
76 200, 86 500 за один зуб; 318 000, 398 000 за челюсть.
Скуловые/птеригоидные доступны по прямому service вопросу, не в общем обзоре.
Другие direction policies не расширяются; единица цены никогда не заменяется
объёмом вопроса. Данные applicability и pricebook не редактируются.

Архитектура проверена с Astra: существующего offer_ids pool достаточно,
service-level representative rule устраняет конкурирующие paths. Внешняя
проверка назначения типов: Nobel Biocare full-arch / NobelZygoma documentation;
внешние цены в демо не добавляются.

## Проверки

JSON/SSE: fresh и после вопроса о боли → general overview → три volume clicks;
бренды, one/few/full/unknown, exact service без cap, специальный service напрямую,
mixed price+сроки и ошибочная финансовая prose без gate по D2-114.
Проверить IDs, amounts/units/conditions, отсутствие catalogue leakage, replay
0 extra calls, continuation context. Adverse fake-output не качество live модели.
Соседние проверки подлинности UI/lead/privacy не ослаблять ради новых offer IDs.
Independent Checker + Cursor до закрытия. Provider/live/SMTP 0.
Полный CI — прежний долг до merge, не закрывается этим checkpoint.

## Выполненные проверки

### Исправление параметров уточнения, 2026-10-02

GO: владелец разрешил исправить потерю объёма при уточнении услуги после
ручного теста. Тип: bug fix инструкции модели, не архитектурное упрощение.
База — тот же e6756ee и предсуществующий SIM4 WIP; staging пуст.
Дополнение exact allowlist: core/one_call_prompt_contract.py и
tests/test_d2_clarification_scope_http.py. Из существующего allowlist меняются
эта карточка, Current Status и Checkpoint Ledger. Остальной WIP сохраняется.
Также tests/test_d2_sim2_contract.py: новый пятый prompt example проверяется
прежним parser-тестом; ожидаемое число примеров меняется с 4 на 5.

До: prompt явно требовал situation для прямой цены, но показывал вложенную
ценовую задачу уточнения без примера сохранения известного объёма. Реальная
модель опустила объём; сервер исполнил неполную сохранённую задачу.
После: prompt31 требует сохранять известные параметры той же операции,
даже когда её услуга неизвестна; известное направление остаётся прямой ценой.
Используются прежние поля и правила situation. Новых состояний, парсеров,
проверяющих слоёв, regex, retry или вызовов нет. Runtime не меняется.
Свободный вопрос понимает модель; клик исполняет сервер; цены и пробел данных
определяет прежний ценовой механизм. Astra подтвердила сохранение supplied
situation на пути pending → click. Удаление зависимости этим fix не заявлено.

Проверки: actual prompt example → оба endpoint → persisted operation → service
click без модели → объём/бренд и допустимые offers либо data gap → replay →
контекст следующего хода. One/few/full, hypothetical price scenario,
независимая prose и известное направление после информационного хода.
Старый adverse output без situation остаётся допустимым: отдельный тест
показывает, что сервер не восстанавливает пропущенный смысл.
Offline PASS не подтверждает, что живая модель больше не опускает параметр.
Новая живая проверка требует отдельного бюджета; в этом исправлении calls0.
Первый запуск не получил доступ к стандартной tmp-папке и выявил устаревшее
ожидание четырёх prompt examples. Изолированный запуск: 44 PASS / 6 FAIL,
36.23 s; 6 FAIL показали, что unknown commitment не применяет extent. Пример
исправлен на существующий hypothetical для явно заданного ценового сценария
без утверждения личного состояния; правило уже применяется к volume clicks.
Astra отдельно сверила это с действующими документами. Runtime не менялся.
Следующий запуск: 48 PASS / 2 FAIL, 35.06 s; информационный test fixture
не содержал topic target, хотя проверял его сохранение. Добавлен правильный
target исходной информации, assert контекста сохранён. Финальный запуск:
tests/test_d2_clarification_scope_http.py + tests/test_d2_sim2_contract.py +
tests/test_d2_sim1_known_actions_http.py — 70 PASS / 67.59 s. Новые tests
также проверяют сохранность прежнего reported patient scope при ценовом
гипотетическом сценарии. Socket блокируется, DB/logs изолированы в tmp;
provider/live/SMTP0. Полный CI и live-model/widget этим запуском не проверены.
Independent Checker PASS: собственные 12 PASS / 26.09 s; actual call path,
отсутствие нового runtime-механизма, сохранность reported scope и честный предел
omission подтверждены. Cursor gate остаётся; live-adherence не аттестована.

Первый объединённый прогон: 155 PASS / 14 FAIL, 252.23 s. Все 14 FAIL
в новом test file: fixture использовал brand_id=nobel вместо nobel_biocare
и tooth_count=1 для few_teeth; исправлены входные fixtures, runtime и gates
не ослаблялись. Три соседних AF1a/SIM1/SIM2 набора в этом запуске: 126 PASS.
Исправленный новый набор: 43 PASS / 48.65 s. Добавлен отдельный реальный
четвёртый offer: exact service видит 4, обзор не заимствует его; 1 PASS / 3.54 s.
Все актуальные 44 SIM4 cases прошли. Independent Checker PASS, собственный
прогон reviewer: 44 PASS / 48.51 s. Проверен actual call path обоих endpoint;
удалённые paths не перемещены в новый слой. 98 локальных ссылок разрешаются,
diff --check чистый. Cursor gate, widget/live и общий CI не аттестованы;
этап не закрыт, Git-публикация не разрешена.
Прогон использовал fake provider, socket блокировку и временные DB/logs.
Browser, live model и полный CI не запускались; тест не гарантирует качество prose.
