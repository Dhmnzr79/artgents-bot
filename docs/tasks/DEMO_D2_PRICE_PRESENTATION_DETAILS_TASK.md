# D2-REC-4-P — компактные цены и точные детали по запросу

## Draft — реализация P2 от принятой карточки, 2026-09-29

Владелец дал отдельный GO на код P2 после Checker/Cursor PASS карточки.
Baseline реализации: Git root `C:\Cursor Projects\artgents-bot-active`, ветка
`codex/d2-stage1-contract`, HEAD и origin branch
`abcb8ee2bad72ef5d5be689cb21964e63af8dfbc`, `origin/main` и merge-base
`141ce91fb1731cd990fcf8391550150016c73e7f`. До правок tracked diff и
staging пусты. Чужие `data/` и `docs/MARKETING_ANSWER_SCENARIOS.md` не stage;
рабочую SQLite и сырые диалоги не читать. Точный write allowlist — §4 P2 ниже.
Старые строки «GO впереди» относятся к документальному checkpoint, не к
этому состоянию.

Реализация в работе: `price_detail_ids` включены в demo только у `classic`;
проверка capability и точных данных идёт по каждому frozen offer. UI хранит
внутреннюю карту reply → aspect + ordered offer IDs в том же завершённом плане;
сервер проверяет revision/tenant до исполнения чистого клика без provider.
Прямой вопрос идёт через один обычный parser и typed `price_detail` request;
отрисовка читает captured package/payment stages, называет пробелы и не
пересчитывает цену. Lead resume/cancel сохраняет своё право на навигацию.
Промежуточные offline тесты и окончательные границы — в новой Draft-строке
[Ledger](DEMO_D2_CHECKPOINT_LEDGER.md). До Checker/Cursor это не принятое P2;
commit/push, live, merge и deploy не разрешены.

## P2 — подготовка карточки от принятого checkpoint, 2026-09-29

**Статус:** документальная подготовка P2. REC-4-P1, D2-DOC-CLICK и
D2-LEAD-INTERRUPT прошли независимые Checker и Cursor review; последний
commit/push активной ветки — `71d746793ffbd3ef796ae81cd6d0eae09d8cfd69`.
Это новая точка отсчёта P2; прежние SHA и фразы «сейчас разрешён только
документальный checkpoint» ниже относятся к датам своих разделов.

**Preflight:** Git root `C:\Cursor Projects\artgents-bot-active`, ветка
`codex/d2-stage1-contract`, HEAD и `origin/codex/d2-stage1-contract`
`71d746793ffbd3ef796ae81cd6d0eae09d8cfd69`; `origin/main` и merge-base
`141ce91fb1731cd990fcf8391550150016c73e7f`. До этой подготовки tracked
diff и staging пусты. Чужие untracked `data/` и
`docs/MARKETING_ANSWER_SCENARIOS.md` не открывать для записи и не stage.
Старый `artgents-bot` и worktree 27e1 остаются историей.

**Точный write allowlist этой документальной подготовки:**

```text
docs/tasks/DEMO_D2_PRICE_PRESENTATION_DETAILS_TASK.md
docs/tasks/DEMO_D2_CURRENT_STATUS.md
docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md
docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md
```

**Утверждённое поведение P2:** D2-102, Target Contract §7, A16/B19 и §3 этой
карточки. В профиле услуги `price_detail_ids` разрешает максимум две точные
кнопки; отсутствие настройки выключает их. Кнопка появляется только при
полных данных каждого показанного offer. Клик раскрывает все показанные
варианты, точно общее — один раз с областью применимости, различия —
раздельно. Прямой вопрос работает и при выключенных кнопках: сообщает
доступные детали и явно отмечает пробелы. Контекст клика проверяется по
tenant, revision, aspect и ordered shown offers; цены, контакты и заявка
не пересчитываются. Смена услуги и TTL не используют старый набор.

**Граница настройки demo:** сейчас ни у одной услуги нет
`price_detail_ids`. Владелец выбрал обе кнопки для классической имплантации
(`service_id=classic`) **при полных данных всех показанных вариантов**;
остальные услуги оставить выключенными. Read-only инвентаризация трёх
текущих `classic.one_tooth.*` offer-файлов показала у каждого четыре
`package.includes`, два `payment_stages` и followup IDs `includes`/`stages`.
Это не заменяет проверку captured offer-набора в реализации: если любой
показанный вариант не проходит точную проверку соответствующего detail,
скрыть только эту кнопку по D2-102, не дописывая данные и не меняя цену.
Менять `clients/demo/target_response/d2_commercial.json` только в отдельном
P2 code checkpoint после GO. Не включать кнопки у других услуг автоматически
по наличию данных или предположению о «сильном» офере.

**Implementation gate:** §4 ниже содержит предполагаемый технический P2
allowlist, но этот документальный GO не разрешает код. Перед реализацией
сверить новый baseline после принятия карточки, точный allowlist и чистый
baseline назначенных offline тестов. Если существующие refs/plan не позволяют
связать клик с конкретным набором offers или нужен файл вне списка —
остановиться и согласовать отклонение. P2 не меняет P1 формат цены, B14,
lead/privacy, один parser/runtime или wire; `tests/test_d2_lead_interrupt_http.py`
читать и запускать как соседнюю регрессию без правок. Без отдельного GO нет
live/provider, запуска бота, merge и deploy. После реализации нужны
независимый Checker и Cursor review, затем отдельное разрешение на commit/push.

**ACCEPTANCE:** A16/B19 и затронутые A02/A05/B12/B14/B18/C01/C03–C05/C07/C09/C10
по JSON/SSE, replay и widget; это не полный REC-5. **D2 ROUTE:** существующие
`/ask` и `/ask/stream` → tenant snapshot → один parser/plan → frozen detail
и UI → store/replay; чистый проверенный клик без модели. **LEGACY IMPACT:**
старый price_aspect selector и normal runtime не подключаются. **OWNER
DECISION:** D2-102 и поведение нескольких/частичных offers утверждены;
владелец выбрал `classic` с обеими кнопками при полном наборе данных,
GO на код ещё впереди. **TEST ISOLATION:**
fake provider, временные tenant/DB/log, сеть и SMTP заблокированы;
рабочую SQLite и сырой журнал не использовать. **FUTURE SCOPE:** REC-5,
ручное качество widget/live только с отдельным бюджетом, админка и каталог
с большим числом позиций.

Актуальное дополнение 2026-09-28: P1 принят Checker/Cursor и сохранён в
`a930ed70df9d2d709cc36b9076be55659485c582`. Перед P2 владелец разрешил
[D2-DOC-CLICK](DEMO_D2_DOCUMENT_CLICK_TASK.md). После этой коррекции P2 требует
отдельного GO и нового preflight от точного SHA принятой коррекции; это уточняет
будущий baseline ниже. Исходный текст карточки и его статусы — история на `b02db8e`.

Дата: 2026-09-28. **Сейчас разрешён только документальный checkpoint.**
Правила показа согласованы владельцем; эта карточка не даёт GO на код,
запуск бота, provider/live, commit/push, merge или deploy. Реализация — после
review карточки и отдельного GO. Это ограниченное продолжение REC-4 перед
REC-5, не повтор REC-3 и не новая архитектура диалога.

Приоритет: AGENTS.md → [Execution Lock](DEMO_D2_EXECUTION_LOCK.md) →
[Roadmap](DEMO_D2_DELIVERY_ROADMAP.md) → [Target Contract](DEMO_D2_TARGET_CONTRACT.md),
[Decisions](DEMO_D2_PRODUCT_DECISIONS.md), [Acceptance](DEMO_D2_ACCEPTANCE.md).

## 1. Preflight и документальный allowlist

- Папка и Git root: `C:\Cursor Projects\artgents-bot-active`.
- Ветка: `codex/d2-stage1-contract`.
- HEAD и локальный `origin/codex/d2-stage1-contract`:
  `b02db8ee010b3431ab24f6e3ef98e5392a591673` — сохранённый REC-4.
- `origin/main` и merge-base: `141ce91fb1731cd990fcf8391550150016c73e7f`.
  Fetch/проверка сервера origin в этом doc checkpoint не выполнялись.
- Tracked diff и staging до работы пусты; чужие untracked `data/` и
  `docs/MARKETING_ANSWER_SCENARIOS.md` сохраняются без записи/staging.
  Git предупредил о недоступности global ignore и `.pytest_cache/`;
  полнота перечисления внутри последней не подтверждена.
- Старый `artgents-bot`, worktree 27e1, `b8b28d3` и backup — история;
  не запускать, не править, не переносить автоматически.
- Исторические Draft/PASS относятся к своим датам и SHA. REC-4 ранее
  получил Checker и Cursor PASS; это не PASS новой доработки.

Точный write allowlist **сейчас — только семь документов**:

```text
docs/tasks/DEMO_D2_PRICE_PRESENTATION_DETAILS_TASK.md
docs/tasks/DEMO_D2_PRODUCT_DECISIONS.md
docs/tasks/DEMO_D2_TARGET_CONTRACT.md
docs/tasks/DEMO_D2_ACCEPTANCE.md
docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md
docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md
docs/WIDGET_ANSWER_FORMAT.md
```

Перед каждым подшагом повторить preflight. Будущий baseline — точный SHA
принятого документального checkpoint, затем точный SHA принятого подшага P1;
его нужно назвать до правок, не молча использовать `HEAD`. При расхождении
папки/ветки/SHA/allowlist или чужом WIP — остановиться.

## 2. Что подтверждено обследованием

- `core/response_plan_materialization.py::_d2_frozen_price_row` сохраняет
  цену, вариант, scope и условия. `core/response_text_renderer.py` печатает
  каждую строку и каждое условие отдельным абзацем; общий scope/КТ повторяется.
- Виджет уже поддерживает Markdown-списки и bold. Новый public wire или
  отдельная система карточек для компактного списка не нужны.
- `d2_direction_prices.json` содержит фиксированную вводную. Её не следует
  путать с самостоятельной информационной частью смешанного вопроса.
- `TargetOffer` уже хранит package/includes/excludes, payment_stages и
  followups. Сохранение данных в captured offer **не доказывает** работающий
  exact-detail ответ. Текущему D2 нужны typed intent/result и binding клика.
- `D2ServiceCommercialProfile` — существующий owner настройки услуги;
  `D2ShownPriceOfferRef` — существующие ordered refs показанных предложений.
  Второй каталог или копия деталей в обычной памяти не нужны.
- Read-only заключение Astra использовано при выборе этих границ;
  согласование владельца требуется отдельно от заключения модели.

## 3. Согласованный результат — D2-101–103

### P1. Компактная цена и необязательная живая вводная

1. Одна конкретная услуга: все подходящие published offers по прежним
   фильтрам и порядку D2-100. Обзор направления до трёх и B14 не менять.
2. Название услуги и общий scope — один раз. Два и более варианта —
   компактный список с круглыми маркерами; одна цена — обычная строка.
   В каждой позиции остаются отличающий вариант, сумма/режим и её условия.
   Разные услуги обзора всегда имеют собственные подписи.
3. Только точно совпадающие у **всех показанных** вариантов scope/условия
   выносятся в общий блок; частные остаются у своей позиции. Никаких
   semantic regex, fuzzy dedup, разбора готового display_text или вывода
   эквивалентности по похожим словам. Разные authored тексты не сокращать.
4. Fixed/from/range/no_public_price, approved_text и обязательные оговорки
   сохраняются. RUB: `20 000 ₽`, `от 20 000 ₽`, `20 000–30 000 ₽`;
   U+00A0 внутри разрядов и перед ₽. Не подменять иную валюту рублями.
   Формат относится к code-owned числам, в том числе этапам оплаты P2;
   свободную prose и approved_text regex-переписыванием не исправлять.
5. 0–1 живая вводная из **того же** вызова модели; ноль — нормальный
   результат, особенно для простой/повторной цены и уточняющего клика.
   Нет обязательного «Понимаю…», банков заготовок, веток под фразы или
   отдельного LLM-редактора. Отсутствие вводной не вызывает отказ/CLARIFY.
6. Технический слот: существующий `patient_text` у ANSWER с проверенным
   ценовым блоком — необязательная вводная к этому блоку. Ordinary content
   остаётся в `requests[].content_text`, CLARIFY/ADMIN сохраняют договор.
   Нельзя считать первый content_text вводной, удалять его или переставлять
   независимые части. Вводная идёт перед ценой на её месте в порядке requests.
   Не дублировать её в хвосте; ordinary history сохраняет всю живую prose
   (вводную и самостоятельные model_prose части) в показанном порядке, в прежних
   bounded/sanitized границах. Code-owned суммы/условия в ordinary prose memory
   не копируются; для них остаются shown offer refs, для replay — полный commit.
   Prompt, parser, materializer, resolver, renderer и history consumer
   проверяются вместе. Второго поля prose/контракта не вводить.
7. Prompt просит одну короткую уместную фразу без повторения суммы/условий.
   Это не гарантия отсутствия повторов модели: D2-092 сохраняет пригодную
   prose целиком; семантического вырезания/нового strict gate нет.
8. У overview остаётся один утверждённый факт зависимости стоимости от
   протокола/объёма и существующее уточнение. В direction config сокращается
   только вводный authored текст; offer order, выбор и кнопки не меняются.
   При точном выборе объёма не повторять обзорную эмпатическую заготовку.
9. Первый ответ не разворачивает includes/payment_stages. Новые marketing
   boosters/акции не добавляются; текущие правила их показа не расширяются.

Пример формы (суммы — иллюстрация, тест берёт их из tenant fixture):

> **Классическая имплантация**
>
> За восстановление одного зуба: имплант и постоянная коронка.
>
> - Implantium — **76 200 ₽**
> - Impro — **85 200 ₽**
> - Nobel Biocare — **101 200 ₽**
>
> КТ при необходимости и временная коронка — отдельно.

### P2. «Что входит» и «Этапы оплаты»

1. В существующем service commercial profile — ordered `price_detail_ids`:
   уникальные `includes`/`stages`, максимум два; отсутствие/`[]` выключает
   кнопки. Никаких списков service_id в коде или новой настройки в другом
   каталоге. Подписи D2: «Что входит», «Этапы оплаты».
2. Единственный переключатель видимости — профиль услуги. Offer followups
   задают capability/reference, package/payment_stages — точные данные.
   Старый price_aspect materializer/selector не подключается. В demo по
   умолчанию выключено; включение конкретных услуг — явная настройка владельца,
   не автоматическое включение всех услуг с заполненным offer. Тесты включают
   настройку в временной копии tenant; live админка вне задачи.
3. Кнопка возможна только при наличии соответствующих проверенных данных
   у **каждого** показанного offer. Нет данных хотя бы у одного — скрыть эту
   кнопку, сохранив цену, другой доступный detail и допустимую CTA.
4. В одном ответе один канал навигации: overview/clarify choices **или**
   до двух price-detail **или** обычный content UI. Цена подавляет content
   follow-up/video. CTA отдельна; её приоритет/запреты D2-012/023/099 прежние.
5. Клик связан с tenant/revision, aspect и конкретным ordered набором offers
   завершённого ответа. Нельзя выбирать первую услугу из active_topic или
   доверять присланным клиентом offer IDs. Проверенный чистый клик — без LLM;
   свободный вопрос — максимум один обычный model call, тот же parser.
6. Владелец выбрал: по кнопке раскрыть **все показанные варианты** с подписями.
   Точно одинаковые детали указать один раз с явной областью применимости.
   Различающиеся составы/платежи — отдельные группы. Не объединять графики
   платежей разных offers, не суммировать их, не пересчитывать цену лечения.
7. Прямой вопрос работает и с выключенными кнопками. Модель выдаёт typed
   aspect и проверяемую ссылку на услугу/вариант в том же envelope; сервер
   разрешает по captured catalog и ordered shown refs. «Во втором» привязан
   к порядку показанного набора, «А что входит?» — к действующему набору;
   без однозначного контекста действует одно уточнение, не угадывание.
   При частичных данных ответить по доступным вариантам и назвать пробел
   у остальных. Не выдавать отсутствие данных за отсутствие услуги.
8. Exact details freeze в том же плане с offer identity. Replay использует
   сохранённый ответ/UI без модели и нового чтения каталога. Переключение
   услуги/TTL не позволяет применять старый набор, stale/forged/foreign
   action остаются строгими. Заявку/контакты детали не меняют.

## 4. Предлагаемый точный allowlist реализации после GO

Ниже разрешаемая область будущего подшага, не требование менять каждый файл.
Иной необходимый файл — остановка и согласование до правки. Tenant authoring
ограничен указанными полями; offer prices/условия, MD-корпус и чужой WIP read-only.

**P1:**

```text
contracts/response_plan.py
core/response_plan_materialization.py
core/response_plan_resolver.py
core/response_text_renderer.py
core/one_call_prompt_contract.py
core/one_call_envelope_protocol.py
core/d2_live_provider.py
core/d2_dialogue.py
clients/demo/target_response/d2_direction_prices.json
static/widget/answer_format.js
static/widget/widget.css
tests/test_response_text_renderer.py
tests/test_d2_price_modes.py
tests/test_d2_rec4_price_ui_http.py
tests/test_d2_price_presentation_http.py
tests/test_d2_envelope_correction.py
tests/js/d2_widget_harness.mjs
docs/tasks/DEMO_D2_PRICE_PRESENTATION_DETAILS_TASK.md
docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md
docs/WIDGET_ANSWER_FORMAT.md
```

`tests/test_d2_price_presentation_http.py` — новый. JS/CSS только оформление
этого блока и проверки; transport/SSE lifecycle не менять.

**P2 (после принятого P1 и отдельного GO):**

```text
contracts/d2_tenant_snapshot.py
contracts/request_understanding.py
contracts/response_plan.py
contracts/response_plan_materialization.py
core/d2_tenant_snapshot.py
core/d2_snapshot_sources.py
core/d2_dialogue.py
core/one_call_envelope_protocol.py
core/one_call_prompt_contract.py
core/d2_live_provider.py
core/response_plan_materialization.py
core/response_plan_resolver.py
core/response_text_renderer.py
core/response_ui_projection.py
clients/demo/target_response/d2_commercial.json
tests/test_d2_price_details_http.py
tests/test_request_understanding_schema_offline.py
tests/test_d2_snapshot_sources.py
tests/test_response_text_renderer.py
tests/test_response_ui_projection.py
tests/js/d2_widget_harness.mjs
docs/tasks/DEMO_D2_PRICE_PRESENTATION_DETAILS_TASK.md
docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md
docs/WIDGET_ANSWER_FORMAT.md
```

`tests/test_d2_price_details_http.py` — новый. `d2_commercial.json` только
price_detail_ids; promo/booster и other tenant facts не менять. Session/store
schema и lead owner read-only: использовать существующие refs/plan ownership;
если их недостаточно — запросить конкретное расширение, не новый state owner.

## 5. Приёмка и минимальные offline проверки

**ACCEPTANCE:** A02/A05/A16, B12/B14/B18/B19 и затронутые C01/C03–C05/C07/C09/C10.
Это срез, не закрытие полного A15/REC-5.

| Подшаг | Обязательное доказательство |
|---|---|
| P1 | Exact-service 1/2/3/4 offers, fixed/from/range/no_public_price; общий и отличающийся scope/условия; сортировка/фильтры прежние; один источник сумм; список и ₽ без лишних абзацев |
| P1 | Intro null/empty/есть, простой вопрос, повтор, choice click; смешанный «приживаемость + цена» сохраняет content и порядок; history содержит все prose части без копирования code-owned цен; exact duplicate не повторён; unavailable price не заменена intro; CLARIFY/ADMIN прежние; B14 оба порядка и deferred без изменений; нет нового strict gate из-за intro |
| P1 | Общий обзор сохраняет обязательное пояснение и choices; live-empathy не обязателен; renderer/widget проверены на узком и широком viewport, длинном бренде и диапазоне; Markdown не превращается в сырой текст/HTML |
| P2 | []/одна/две кнопки; запрет третьей/дублей/чужого ref в конфигурации; частично отсутствующие данные скрывают только недоступную кнопку, цены остаются |
| P2 | Цена → detail click → другой detail/короткий вопрос → новая услуга; одинаковые и разные packages/stages, прямой вопрос при выключенной кнопке, «во втором», missing data, TTL |
| Оба | JSON и SSE через реальные parser/resolver/materializer/render/store; replay идентичен, без повторного provider/effect; tenant A/B, stale/forged, CTA/lead/privacy, sentinel запрета legacy |

P1 целевой pytest: `tests/test_d2_price_presentation_http.py`,
`tests/test_response_text_renderer.py`, `tests/test_d2_price_modes.py`,
`tests/test_d2_rec4_price_ui_http.py`, `tests/test_d2_envelope_correction.py`.
P2 целевой pytest: `tests/test_d2_price_details_http.py`,
`tests/test_request_understanding_schema_offline.py`,
`tests/test_d2_snapshot_sources.py`, `tests/test_response_ui_projection.py`,
`tests/test_response_text_renderer.py`.
Регрессии читать/запускать без правок: `tests/test_d2_independent_request_parts.py`,
`tests/test_d2_content_source_ui.py`, `tests/test_d2_rec3_memory_http.py`,
`tests/test_d2_price_scope_selection.py`; выбирать затронутые cases по IDs.
Widget: существующий `tests/js/d2_widget_harness.mjs`, offline fake endpoints;
до закрытия P1 визуально проверить 360 и 768 px, переносы/отступы/маркер/сумму.

**Test isolation:** fake provider, временные tenant copy/DB/logs, внешняя сеть и
SMTP заблокированы. Реальные provider calls: 0. Не запускать рабочий бот,
не открывать рабочий SQLite, не включать полный журнал без отдельного задания.
Offline tests проверяют сборку, но не доказывают живость/устойчивость модели;
ручной widget/live прогон — отдельное разрешение и бюджет.

Исторический Cursor REC-4: 75 passed / 10 failed; не свежий результат этого
checkpoint. Известные IDs: `test_free_cta_on_doctors_only_while_fact_window_open`,
`test_stage2_bounds_live_prose_pairs_and_expires_them_with_context`,
`test_real_content_below_korotko`, оба `test_real_price_and_section_are_ordered`,
`test_overview_readiness_is_not_optional_ui`,
`test_unavailable_price_defaults_keep_content_and_cta`,
`test_optional_ui_does_not_block_answer`, `test_tenant_view_and_source_binding`,
`test_price_content_price_preserves_independent_content_and_request_order`.
До реализации записать результат назначенного набора на её чистом baseline;
падение сравнивать с этим SHA, не объявлять старым только по нетронутой строке.
Тесты не ослаблять/skip ради зелёного результата. Обновлять старое ожидание
только в пределах нового явно утверждённого поведения и allowlist.

## 6. Ворота и отчёт

1. Сейчас: только согласование документов, проверка ссылок/diff, read-only
   Checker, затем отдельный Cursor review карточки. Pytest для docs не нужен.
2. После GO: P1, smallest offline tests → независимый Checker → Cursor.
   Затем P2 с новым baseline и отдельным GO/проверкой целых диалогов.
3. Ledger draft каждого checkpoint **до** review. После PASS его не дописывать
   ради статуса/hash. После REJECT — исправление в границах и focused recheck.
4. Commit/push только после явного разрешения; exact stage, staged names/stat/
   diff/check; никогда `git add .`/`-A`. Никаких сырых переписок/ПД/БД/секретов.

**D2 ROUTE:** существующие `/ask`, `/ask/stream` → единое понимание/captured
snapshot → frozen plan → renderer/UI → state/store/replay. Проверенные клики
идут в тот же plan path без модели. **LEGACY IMPACT:** старые assembler,
price_aspect selector, answer_lead и второй parser не подключаются.
**OWNER DECISION:** D2-101–103 и два уточнения P2 приняты; кодовый GO впереди.
**FUTURE SCOPE:** REC-5/A15 целиком, старые красные тесты вне этой задачи,
админка, большой каталог/пагинация, новая модель/второй вызов, live/merge/deploy.
