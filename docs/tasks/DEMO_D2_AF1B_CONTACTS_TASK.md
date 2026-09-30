# D2-AF-1b — точный ответ на контактный вопрос

Дата: 2026-09-30. Статус: **документальная карточка принята; отдельный GO на
реализацию AF-1b записан ниже**.
Это следующий узкий checkpoint после сохранённого AF-1a (`4e435ce8006cc2df07930a40d058f278469a99f6`),
а не разрешение на AF-1c, AF-2 или REC-5. Действуют
[AGENTS.md](../../AGENTS.md), [Execution Lock](DEMO_D2_EXECUTION_LOCK.md),
[Delivery Roadmap](DEMO_D2_DELIVERY_ROADMAP.md),
[Target Contract](DEMO_D2_TARGET_CONTRACT.md),
[Product Decisions](DEMO_D2_PRODUCT_DECISIONS.md) и
[Acceptance](DEMO_D2_ACCEPTANCE.md).

## Implementation checkpoint — 2026-09-30

После принятия продуктовых правил и focused Checker PASS владелец отдельно
разрешил начать AF-1b. Этот GO не относится к AF-1c/2, live, commit/push,
merge или deploy. Пункт §3 ниже сохраняет историческую границу документации,
а не отменяет это более позднее разрешение.

- Git root `C:\Cursor Projects\artgents-bot-active`, ветка
  `codex/d2-stage1-contract`; baseline HEAD/local origin
  `4e435ce8006cc2df07930a40d058f278469a99f6`; локальный `origin/main` и
  merge-base `141ce91fb1731cd990fcf8391550150016c73e7f`.
- Перед runtime правкой staging пуст; tracked WIP — только Draft-строка
  Ledger, новая эта карточка — untracked WIP этой задачи. Чужие untracked
  `data/` и `docs/MARKETING_ANSWER_SCENARIOS.md` не трогать.
- Baseline адресного соседнего offline набора на этом HEAD: 9 passed,
  4 failed, 9 deselected. Три старые фикстуры doctor/protocol без нужной
  prose получают `patient_text_required`; четвёртый тест ожидает иной
  информационный пробел в mixed ответе. После runtime правки тот же набор:
  9 passed / те же 4 failed / 9 deselected; новых отказов нет.

**Точный write allowlist реализации:**

```text
contracts/request_understanding.py
contracts/response_plan.py
core/one_call_prompt_contract.py
core/d2_tenant_snapshot.py
core/d2_contacts_cta.py
core/d2_dialogue.py
core/clinic_contact_policies.py
core/d2_live_provider.py
tests/test_d2_af1b_contacts_http.py
docs/tasks/DEMO_D2_AF1B_CONTACTS_TASK.md
docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md
```

В том же typed D1R запросе добавлен необязательный `contact_branch_id`,
выбираемый моделью только при названном филиале из каталога текущего tenant;
для общего вопроса он null. Код не выбирает филиал повторно по русскому
тексту. Существующие точные контактные данные остаются в одном
`clinic_policies.yaml`. Общий `contacts` развёрнут в телефон, адрес и часы;
отсутствующая парковка получает согласованную честную фразу. Для клиники с
несколькими телефонами неоднозначная кнопка звонка не показывается. Контакт
и независимая модельная prose соединяются прежним общим D2 materializer.

**Evidence до review:** новый HTTP набор `tests/test_d2_af1b_contacts_http.py`
— 19 passed: отдельные поля, общий и составной вопросы в обеих очередностях,
JSON/SSE, replay, tenant/branch ownership, обязательный адрес и необязательная
парковка, ошибочно пустой `contact_fields`. Соседний
контактный/branch/mixed набор — 19 passed / 80 deselected.
Fake provider, временные tenant/SQLite/log, сеть заблокирована; live/provider/SMTP
0. Offline PASS не доказывает точность выбора поля живой моделью. Независимый
Checker и Cursor должны видеть весь diff до отдельного commit/push.

## 1. Preflight и граница этой подготовки

- Папка и Git root: `C:\Cursor Projects\artgents-bot-active`.
- Ветка `codex/d2-stage1-contract`; HEAD и локальная
  `origin/codex/d2-stage1-contract` до правок:
  `4e435ce8006cc2df07930a40d058f278469a99f6`.
- Локальный `origin/main` и merge-base:
  `141ce91fb1731cd990fcf8391550150016c73e7f`.
- До правок tracked diff и staging пусты. Чужие untracked `data/` и
  `docs/MARKETING_ANSWER_SCENARIOS.md` не открывать, не изменять и не stage.
  Старый зарегистрированный worktree не трогать. Нового remote fetch эта
  карточка не объявляет.

**Точный write allowlist только документальной подготовки:**

```text
docs/tasks/DEMO_D2_AF1B_CONTACTS_TASK.md
docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md
```

Код, тесты, tenant packs и остальные документы read-only. Бот, pytest,
provider/live и SMTP не запускать. Эта карточка не разрешает commit/push,
merge, deploy или очистку. Для реализации требовались новый preflight, точный
implementation allowlist и отдельный GO владельца; они зафиксированы в более
позднем checkpoint выше.

## 2. Основание и решение владельца

- **Наблюдение AF-02:** лог `633b106d` зафиксировал, что на вопрос о
  местонахождении вместе с информационным вопросом бот дал телефон. Это факт
  одного хода, не оценка частоты и не доказательство единственной причины.
- **Статическая причина на текущем HEAD:** в `core/d2_contacts_cta.py`
  общий `contacts` отображается в `phone_display`, а при пустом результате
  запрошенных полей добавляется телефон. Поэтому телефон способен заменить
  адрес или иной запрошенный контакт. Контракт модели уже знает отдельные
  `contact_address`, `contact_phone`, `contact_whatsapp`, `contact_hours`,
  `contact_parking` и `contacts`; D2 уже умеет соединять contact с независимой
  content part до одного final render.
- У demo фактические адрес, телефон, часы и парковка находятся в
  `clients/demo/clinic_policies.yaml`. Текущий
  `clients/demo/md/clinic__info__contacts.md` не содержит сам адрес. Перенос
  данных в MD не выбран как исправление: владелец безразличен к формату
  хранения, если бот просто и правильно отвечает. Действующий tenant source
  контактов остаётся одним; ручную вторую копию адреса не создавать.
- **Принято владельцем в обсуждении:** конкретный вопрос получает конкретный
  контакт: телефон → телефон, местонахождение/адрес → адрес, время работы →
  часы, парковка → сведения о парковке. Несколько явно запрошенных контактов
  сохраняются вместе. Вопрос «Где вы и как проходит имплантация?» получает
  адрес и независимое объяснение. Общий «Ваши контакты?» даёт компактно
  телефон, адрес и часы; WhatsApp и парковка добавляются по явному запросу.
  Адрес клиники обязателен в данных; при нарушении этого условия нельзя
  подменять его телефоном или выдавать успешный ответ с неверным полем.
- **Дополнительно принято владельцем:** если у tenant нет сведений о
  запрошенной парковке, ответить «В материалах клиники нет информации о
  парковке», не подставляя телефон или чужую парковку. Для другого
  отсутствующего необязательного контактного поля действует тот же принцип:
  коротко назвать именно отсутствующие сведения, не выдавать иной контакт
  за ответ. Если у клиники два филиала, на общее «Где вы находитесь?» показать
  оба адреса с названиями филиалов; на вопрос об указанном филиале — только
  его адрес. Не выбирать один филиал по догадке.
- **Граница достоверности:** код выдаёт точные значения выбранных полей из
  текущего tenant, но модель выбирает поля по смыслу вопроса. Offline PASS
  проверит сборку заданных typed запросов, а не качество живого распознавания.

## 3. Граница будущей реализации — отдельный GO

Опираться на существующие typed `contact_fields`, tenant contact facts и
общий D2 ответ. Убрать подмену общего `contacts` одним телефоном и fallback
на телефон при отсутствии запрошенного поля. Сохранить независимую prose
в составном вопросе и точную строку каждого доступного контакта. Не вводить
regex/словарь для адресных формулировок, второй parser/prompt, новое состояние
памяти, новый tenant-data contract или per-request fallback на старый runtime.
Телефонная кнопка и вход в заявку остаются под существующими UI/lead/privacy
правилами; новая CTA администратора в AF-1b не входит.

Текущий formatter одиночных полей ещё не покрывает
`clients/nikadent/clinic_policies.yaml` с двумя филиалами. При отсутствии
необязательного поля ответ остаётся честным пробелом именно для этого поля;
отсутствие обязательного адреса — ошибка данных, не штатный разговорный
пробел. До реализации исполнитель на свежем preflight перечисляет точные пути
implementation allowlist. Предполагаемые места сверки: `core/d2_contacts_cta.py`,
`core/one_call_prompt_contract.py`, контракт/валидация контактных данных,
общий D2 route и адресные HTTP-тесты. Это **не** разрешённый write allowlist.
Если решение потребует иного сценария, правила UI или расширения scope,
остановиться и обсудить его с владельцем до кода.

## 4. Приёмка будущей реализации

**ACCEPTANCE:** узкая часть B09 и D2-095/C02 для контактов, AF-02; смежные
lead/privacy, tenant, JSON/SSE/replay без заявления о полной REC-5 matrix.
**D2 ROUTE:** настоящие offline `/ask` и `/ask/stream` → один D1R provider/parser
→ точные tenant contact facts и независимая prose → один frozen answer/UI/state
→ replay. **LEGACY IMPACT:** старый semantic selector/fallback не подключать.
**OWNER DECISION:** правила конкретных и общих контактов, двух филиалов и
честного ответа при отсутствии необязательного поля согласованы;
implementation GO отсутствует. **FUTURE SCOPE:** AF-1c, AF-2,
оставшиеся риски, REC-5 и отдельно разрешённый live quality check.

Перед кодом записать clean baseline targeted tests и известные failures.
Минимальный offline набор с fake provider и временными tenant/SQLite/log:

1. Отдельные телефон, адрес, часы и парковка; несколько полей в одном вопросе;
   общий `contacts`; точные значения и отсутствие лишнего поля.
2. Адрес + независимое объяснение в обеих очередностях; contact part не
   уничтожает content prose, а неверный/пустой `contact_fields` не подменяет
   ответ телефоном. Проверять итоговый текст и frozen parts, не только parser.
3. Отсутствующее необязательное поле и повреждённые обязательные данные в
   изолированной копии tenant; ни чужих фактов, ни ложного success.
4. Tenant isolation, оба адреса / один названный филиал, кнопка звонка,
   активная заявка/PII и запрет автоматического lead.
5. JSON/SSE parity, replay без второго provider call и сохранённый UI.

Provider/live budget пока 0. Перед принятием реализации нужен независимый
Checker; после REJECT — focused recheck. Отдельный Cursor review проводится
по согласованной карточке. После PASS reviewed diff не дописывать ради hash;
exact staging, commit/push — лишь по отдельному разрешению.

## 5. Проверка этой карточки

Сверить ссылки, Git baseline, AF-02, решения владельца о филиалах и пробеле,
документальный allowlist и `git diff --check`. Pytest для doc-only правки
не нужен. Checker и Cursor могут проверить карточку и Ledger read-only;
их PASS не даёт GO на runtime, live, commit/push, merge или deploy.
