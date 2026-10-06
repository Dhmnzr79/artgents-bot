# D2-AF-1a — исходная ценовая задача при выборе объёма

Дата: 2026-09-30. Статус: **документальная карточка принята; отдельный GO на
реализацию AF-1a записан ниже**. Это первый узкий checkpoint после D2-AUDIT-PLAN, а не
разрешение на остальные AF-1b/1c/2 или REC-5. Действующий порядок документов:
[AGENTS.md](../../AGENTS.md) → [Execution Lock](DEMO_D2_EXECUTION_LOCK.md) →
[Delivery Roadmap](DEMO_D2_DELIVERY_ROADMAP.md) →
[Target Contract](DEMO_D2_TARGET_CONTRACT.md),
[Product Decisions](DEMO_D2_PRODUCT_DECISIONS.md),
[Acceptance](DEMO_D2_ACCEPTANCE.md).

## Implementation checkpoint — 2026-09-30

Владелец после сохранённой карточки дал GO начать AF-1a и отдельно включил
брендовый обзор: проверенный выбор объёма обязан сохранить исходный `brand_id`,
чтобы не показать цены других брендов. Это разрешение не относится к AF-1b/1c/2,
live, commit/push, merge или deploy. Astra read-only сверила минимальную
типизированную границу; её рекомендация не заменяет это решение владельца.
Первоначально владелец согласовал типизированную принадлежность исходного
ценового вопроса, но после подробного разбора отменил это расширение AF-1a:
ценовая кнопка не создаёт личный медицинский факт и не ветвится по
«о себе / другом человеке / гипотезе». По отдельному согласию после read-only
сверки Astra выбранный объём из frozen completion передаётся следующему ходу
как свежий контекст разговора, включая честный пробел в цене. Это не второй
state owner и не угадывание по label/ref; смена темы и TTL ограничивают контекст.
По уточнению владельца после выбора услуги сохраняется текущий UI: цена
показывается сразу, кнопок объёма нет. Поэтому цепочка «услуга → объём» в
текущем tenant UI не исполняется и не считается недостающим тестом AF-1a.

- Git root `C:\Cursor Projects\artgents-bot-active`, ветка
  `codex/d2-stage1-contract`; HEAD/local origin branch до правок
  `8cea81125cfc9ad8898b0e4ab43a6dc42bf15331`; `origin/main` и merge-base
  `141ce91fb1731cd990fcf8391550150016c73e7f`.
- Перед правками staging и tracked diff пусты; foreign untracked `data/` и
  `docs/MARKETING_ANSWER_SCENARIOS.md` не трогать.
- Чистый baseline адресных offline tests до кода: 33 passed / 3 failed
  (`tests/test_d2_price_presentation_http.py`,
  `tests/test_d2_rec3_memory_http.py`,
  `tests/test_d2_continuation_scenarios.py`). Три failures — ожидание прежней
  prose на overview, отсутствие live prose пары и длинный ввод, закрытый spam
  gate; сравнивать те же assertions после правки, не ослаблять их ради PASS.
  Fake provider, временные DB/tenant/log/pytest, network blocked; live 0.

**Точный write allowlist реализации:**

```text
contracts/response_plan.py
contracts/d2_session_context.py
contracts/d2_dialogue.py
core/response_plan_materialization.py
core/d2_dialogue.py
core/d2_live_provider.py
tests/test_d2_af1a_price_task_http.py
docs/tasks/DEMO_D2_AF1A_PRICE_TASK_TASK.md
docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md
```

Новый тестовый файл и эта implementation-запись входят в новый diff. Три
дополнительно разрешённых пути контракта/projection/prompt согласованы владельцем после
архитектурной сверки Astra; остальные шесть — исходный implementation allowlist.
Offline HTTP проверка после этого решения: 19 passed (цена, brand, четыре
объёма, no-price gap, следующий provider input, TTL, смена темы и replay).
Контекст следующего хода доказан на fake provider; качество живого ответа на
«А сколько это займёт?» без отдельно разрешённого live теста не объявляется.
Историческую документальную базу §1 ниже не переписывать. Если обнаружится
необходимость иного файла или нового видимого правила, назвать её до staging
и получить решение владельца по Execution Lock §4. После реализации проверить
адресные offline сценарии и baseline failures; независимый Checker и Cursor
видят весь код, тесты и Ledger draft до отдельных commit/push.

## 1. Preflight и точный allowlist этой подготовки

- Папка и Git root: `C:\Cursor Projects\artgents-bot-active`.
- Ветка: `codex/d2-stage1-contract`.
- HEAD и локальная `origin/codex/d2-stage1-contract`:
  `fb81a9af2e1c4e654d9040013c3c6f528d89b5d4` (принятый D2-AUDIT-PLAN).
- `origin/main` и merge-base:
  `141ce91fb1731cd990fcf8391550150016c73e7f`.
- Перед правкой staging и tracked diff пусты. Чужие untracked `data/` и
  `docs/MARKETING_ANSWER_SCENARIOS.md` сохранены. Права на пользовательский
  Git ignore/`.pytest_cache` ограничивают просмотр ignored-окружения, но не
  показывают tracked diff. Remote refs здесь локальные; нового fetch или
  `ls-remote` эта подготовка не объявляет.

**Write allowlist только этого документального checkpoint:**

```text
docs/tasks/DEMO_D2_AF1A_PRICE_TASK_TASK.md
docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md
```

Код, тесты, tenant packs, остальные документы, рабочие БД/логи и старые
репозитории read-only. Бот, pytest, provider/live и SMTP не запускаются.
Commit/push, merge/deploy и очистка требуют отдельных решений. Этот allowlist
не переносится автоматически на будущую реализацию.

## 2. Найденный дефект и утверждённое поведение

- **Подтверждено прежним логом AF-01:** trace prefix `a07cab18` — после вопроса
  о цене имплантации проверенный клик «Один зуб» дал описание без цены. UI ref
  попал в provider input, но исходная price task не была закреплена. Это факт
  конкретного хода, не частота ошибки и не доказательство её единственной причины.
- **Статическая сверка на этом baseline:** `core/d2_dialogue.py` проверяет
  показанный ref и revision, передаёт `selected_ui_ref`, но явно привязывает
  исходный `price` request только в service-clarify click. Для volume-click
  нет соответствующей обязательной price-task binding. Источник четырёх
  volume refs — `core/d2_snapshot_sources.py`. Существующие
  `tests/test_d2_price_presentation_http.py` и
  `tests/test_d2_continuation_scenarios.py` проверяют удачный модельный
  `kind=price`; этого недостаточно для AF-01.
- **Принятое правило:** D2-094 и Target Contract §5 требуют, чтобы проверенный
  выбор услуги/объёма после ценового уточнения сохранял исходный ценовой
  вопрос. A14 требует цену либо честно названный её пробел, а не одно описание;
  «Не знаю» не зацикливает уточнение. D2-092 сохраняет пригодную живую prose,
  tenant/UI/lead/privacy остаются строгими.

Никакой новый смысл кнопки здесь не утверждается. `volume:…` — проверенный
выбор объёма для исходного вопроса, а его label не становится новым
самостоятельным вопросом пациента. Ответ на исходный price request берёт цену
только из текущего tenant snapshot через существующий code-owned путь.

## 3. Граница будущей реализации — требуется отдельный GO

На следующем preflight от принятого SHA карточки исполнитель фиксирует **точный
implementation allowlist** до кода. Если понадобится поле нового контракта или
изменение видимого поведения за пределами D2-094/A14, сначала отдельная
архитектурная сверка с Astra и решение владельца. Эта карточка не выбирает
такое расширение заранее.

Результат ограничен чистым проверенным volume-click после ценового обзора или
незавершённого ценового уточнения. Источник задачи и выбор привязаны к тому же
tenant, session, последнему показанному completion и UI revision. Известный
объём не угадывается повторно по подписи, prose или regex. Неправильные
`kind`/service/topic/extent в модельном envelope проверяются относительно
этой привязки; недостоверная разметка не превращает ценовой клик в
информационный ответ без цены и не разрешает чужую цену. При отсутствии
опубликованной подходящей цены — честный пробел по действующим правилам.
Пригодная prose обрабатывается по D2-092; нельзя вводить новый semantic
sanitizer или отказ только из-за её неточности.

Сохраняются один production parser, один обычный provider call, существующий
owner ordinary state и точные tenant/UI/replay границы. Нет fallback на старый
runtime, второго prompt/parser, semantic regex, нового owner state, скрытого
retry или автоматического lead. Не переносить сюда AF-1b (контакты), AF-1c
(полнота history projection), AF-2 (составные вопросы), оформление, CTA или
общее recovery inflight.

## 4. Приёмка и проверки реализации

**ACCEPTANCE:** узкий срез A01/A14 и регрессии A06/A08/B11/B14,
C01/C04–C05/C07/C09–C10; не полный REC-5. **D2 ROUTE:** реальные offline
`/ask` и `/ask/stream` → проверенный captured UI → единый D2 provider/parser
→ tenant price materialization → frozen answer/UI/state → replay.
**LEGACY IMPACT:** старые semantic selectors и fallback не вызываются;
полное C08 proof остаётся REC-5. **OWNER DECISION:** документальная подготовка
разрешена; implementation GO и exact code allowlist впереди.
**FUTURE SCOPE:** AF-1b/1c/2, оставшиеся риски, REC-5 и отдельно разрешённое
live-качество.

Перед кодом выполнить чистый baseline назначенных offline тестов на точном
SHA и записать известные failures. Новые адресные HTTP-тесты должны покрыть:

1. Обзор имплантации → каждый из четырёх показанных вариантов объёма.
   «Один зуб», «Несколько зубов» и «Вся челюсть» продолжают исходный price
   request и дают подходящую точную цену либо честный пробел; «Не знаю» даёт
   разрешённый ориентир и не повторяет меню/не запускает заявку.
2. Fake-provider envelopes: правильный `price`, неправильный `content/other`,
   неполные поля, противоречивые service/topic/extent. Проверить полный
   результат и сохранённое состояние, не только наличие ref в prompt.
   Недостоверные обязательные поля не чинить догадкой из label.
3. Исходный вопрос о цене → выбор объёма → короткое следующее «А сколько?»;
   отдельно существующий выбор услуги с немедленной ценой, явная смена
   услуги, correction, hypothetical, TTL. Не
   превращать гипотезу или «Не знаю» в сообщённый медицинский факт.
4. JSON/SSE и idempotent replay: одинаковые frozen answer/UI/state без нового
   provider call; stale, forged, foreign-tenant и непоказанный ref отклоняются
   до provider. Lead UI/активная заявка не превращаются в volume action.
5. Соседний price+information и B14: ценовой выбор не стирает независимый
   вопрос и не выдаёт все цены разных услуг. Проверить отсутствие копии
   code-owned суммы и ПД в ordinary prose history.

Тесты используют fake provider, временные tenant/SQLite/log, блокировку сети
и отдельный pytest temp/cache; рабочие БД/сырые разговоры не открываются.
Offline PASS доказывает обработку заданного envelope, а не качество распознавания
реальной модели. Live/provider budget сейчас 0.

После реализации — независимый Checker PASS, затем отдельный Cursor review
перед принятием checkpoint. После REJECT — focused recheck находок. До review
Ledger draft заполняется доказанными фактами; после требуемых PASS reviewed
diff не меняется ради статуса или SHA. Exact staging, staged diff/stat/check,
commit/push — только по отдельному разрешению.

## 5. Проверка этой карточки

Сверить ссылки, Git baseline, D2-094/A14 и AF-01, документальный allowlist,
отсутствие runtime GO и `git diff --check`. Pytest не нужен: код и тесты не
меняются. Независимый Checker читает карточку и Ledger read-only; Cursor
проверяет этот документальный рубеж отдельно. Ни один их PASS не разрешает
runtime, live, commit/push, merge или deploy.
