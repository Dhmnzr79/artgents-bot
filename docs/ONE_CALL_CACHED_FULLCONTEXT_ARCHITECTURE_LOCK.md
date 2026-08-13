# ONE_CALL_CACHED_FULLCONTEXT — Architecture Lock

**Статус:** нормативный TARGET-контракт + синхронизация принятого baseline (Stage 4.3 принят; Stage 5.1 — docs-only marketing contract sync, implementation не начата).
**Дата:** 2026-08-13.
**Модель:** `qwen3.7-flash-2026-07-15`.
**Baseline HEAD:** `6345b37eec2807bc2008e68f8a01018407af044f`.

Этот документ фиксирует **целевую** архитектуру продукта и **контракт** принятого состояния Stage 0–4.3. Разделы §1–§16 — нормативный TARGET; § «Current implementation status» и §17 — проверяемое текущее состояние baseline и оставшиеся gaps. Закрытие gaps §17 — отдельные этапы frozen roadmap §19.

### Current implementation status (Stage 0–4.3 accepted)

| Этап | Статус |
|------|--------|
| Stage 0 — Architecture Lock (docs) | **Принят** (`24a3a6f`) |
| Stage 1 — Governance + provider-call accounting | **Принят** (Stage 0–2 baseline) |
| Stage 2 — Ingress reorder + Problem Gate first + typed UI | **Принят** (Stage 0–2 baseline) |
| Stage 3A — Cached FullContext prefix + pack identity | **Принят** (`9b0c92c`) |
| Stage 3B — Flash capability JSON/streaming на точном snapshot | **Принят**; подтверждён управляемым LIVE-прогоном (`5b1b8a7`, `f2ecc8d`) |
| Stage 3C — Production-faithful speed measurement + absolute speed gates | **Принят** (`4fe1465`, `daabe2a`, `28f9c3e`, `0c18ad0`) |
| Clinic-owned price strategy + единый authoritative commerce result (text/card) | **Принят** в текущем baseline (`fce68be`) |
| Stage 4.0 — Architecture Lock sync (docs) | **Принят** (`06e3f0b`) |
| Stage 4.1 — Windows logging | **Принят** (`1d89190`) |
| Stage 4.2 — Production closed JSON envelope | **Принят** (`b833482`) |
| Stage 4.3 — Semantic ownership | **Принят** (`6345b37`) |
| `SALES_ONE_PLUS_ON` | **default OFF** — без изменений |
| Alibaba LIVE после Stage 4.0 | **Запрещён** без отдельной явной команды владельца |

Stage 5.1+ **не считаются реализованными** этим документом. Оставшиеся gaps §17 **не объявлены исправленными**, пока соответствующий этап не принят checker.

### Приоритет и supersession

Этот Lock — **новый TARGET-контракт**. При противоречии с [`ARCH_TARGET_DESIGN.md`](ARCH_TARGET_DESIGN.md) (включая `medical_handoff`, grounded-content semantics и связанные формулировки) **действует этот документ**.

Сознательно **не** принимается старая семантика `medical_handoff`, при которой проблемный медицинский вопрос мог получать содержательный медицинский ответ перед handoff. Новая нормативная граница — ниже.

Справочно (не заменяют lock): [`FLAGS_AND_STATUS.md`](FLAGS_AND_STATUS.md).

### Нормативная граница ANSWER / ADMIN

**`ANSWER`** — модель и deterministic presentation отвечают по базе, без медицинского диалога:

- вопросы об услугах и принципах их проведения;
- этапы, сроки и материалы из утверждённой базы;
- технологии и преимущества клиники;
- врачи;
- **будущие** страхи пациента: боль, цена, сроки, приживаемость, доверие;
- любые подтверждённые бытовые и клинические microfacts из MD.

**`ADMIN`** — немедленный handoff администратору, **без** медицинского диалога и **без** содержательного медицинского ответа перед handoff:

- **текущие** симптомы, боль, кровь, отёк, воспаление, осложнения;
- жалоба, отзыв, просьба о директоре/руководителе;
- постановка диагноза;
- персональное лечение, лекарства и медицинские назначения;
- персональная пригодность и противопоказания;
- сложные медицинские вопросы, не являющиеся обычным описанием услуги;
- другие проблемные неконверсионные ситуации.

**Запрещено:**

- blanket-правило «любое медицинское слово → ADMIN»;
- возврат к режиму, где проблемный медицинский запрос получает содержательный медицинский ответ перед handoff.

---

## 1. Target architecture

**Название:** `ONE_CALL_CACHED_FULLCONTEXT`

**Цепочка свободного текстового запроса:**

```
deterministic ingress
→ minimal high-precision problem gate
→ one Qwen Flash call with full client MD context
→ typed control validation
→ deterministic commercial facts and presentation (COMMERCIAL_RENDER_CONTRACT)
→ widget response
```

**Модель:** `qwen3.7-flash-2026-07-15`

**Неизменяемая архитектурная основа:**

- один вызов `qwen3.7-flash-2026-07-15` **либо 0 вызовов** на HTTP-запрос;
- **никаких** OpenAI-вызовов;
- полный cached MD-корпус **конкретной** клиники;
- Flash понимает свободный язык;
- **нет** RAG / selected-context replacement;
- **нет** Planner / Composer / Verifier / отдельного classifier;
- **нет** clinic-specific business regex и больших словарей синонимов;
- цены, акции, рассрочка, гарантии, marketing facts, CTA и кнопки принадлежат коду и данным клиники;
- глобальный Python **не содержит** clinic-specific фактов;
- продукт — sales-бот / аналог лендинга, **не** медицинская энциклопедия;
- **текущие** симптомы / problem / complaint / diagnosis / personal medical → сразу **`ADMIN`** без медицинского диалога;
- **будущие** страхи боли, цены, сроков и приживаемости → нормальный продающий **`ANSWER`**.

---

## 2. Provider-call invariant

На **весь HTTP-запрос:**

```
provider_calls ∈ {0, 1}
```

Считаются **все** provider calls, включая ingress, classifier, planner, composer, verifier, retry и fallback.

При включённой новой архитектуре **запрещены:**

- ingress LLM;
- speculative Planner;
- Planner;
- Composer как отдельный вызов;
- Verifier;
- semantic classifier как отдельный вызов;
- retry;
- old LLM fallback;
- второй вызов после tool/function call;
- скрытый retry или второй классификатор в том же HTTP-запросе.

**Разрешённые 0-call пути:**

- spam/noise;
- obvious high-precision Problem Gate;
- complaint/director;
- urgent;
- typed UI terminal;
- exact contacts;
- active booking/lead state machine;
- deterministic response, если модели не требуется писать narrative.

---

## 3. Active runtime

**До Stage 6 activation (текущее production routing):**

- legacy runtime (Planner + Boundary + Composer + Verifier) остаётся **рабочим control** при `SALES_ONE_PLUS_ON=OFF`;
- candidate path (`SALES_ONE_PLUS_ON`) **выключен** по умолчанию;
- принятые Stage 0–3 изменения существуют в baseline, но **не активированы** как единственный product path.

**При feature flag ON (переходный режим):**

- ordinary free text **и** governed typed UI должны идти в новый TARGET-контур;
- в **том же** HTTP-запросе **не** запускаются legacy Planner, Verifier, ingress LLM, speculative Planner или иной второй provider call;
- `provider_calls ∈ {0, 1}` на весь запрос.

**После Stage 6 (целевое состояние):**

- legacy runtime удаляется или становится **недоступным** для production routing;
- единственный product path — `ONE_CALL_CACHED_FULLCONTEXT`.

---

## 4. Free-language ownership

Flash отвечает за понимание свободных формулировок:

- услуги;
- технологии;
- врачи;
- опыт;
- страхи;
- сроки;
- clinic microfacts;
- нестандартные и разговорные запросы.

Не требуется составлять разговорные словари синонимов для каждой клиники.

**Semantic ownership (нормативно):**

- подтверждённый microfact из полного MD **может** получать `service_id=null`;
- неизвестная заранее тема / microfact **не должна** принудительно default-иться в implantation или другую услугу;
- слабый catalog match — **только подсказка** модели, **не** authoritative selection;
- generic service / topic **нельзя** самовольно сужать до конкретной технологии, бренда, материала или offer;
- bare service / question **не обязан** приводить к `CLARIFY`;
- `CLARIFY` допустим **только** когда корректный ответ действительно зависит от `service`, `extent`, `jaw` или `stage`;
- **нельзя** добавлять APRF-, whitening-, parking- или иные clinic-specific regex.

---

## 5. Regex policy

**Разрешены** только компактные общие high-precision правила:

- obvious urgent symptoms;
- complaint/director;
- explicit diagnosis/treatment request;
- obvious spam;
- exact contacts/booking commands;
- очевидные scope-маркеры, если их ошибка **не** выбирает услугу или цену.

**Запрещены** разрастающиеся business-regex для:

- всех способов спросить о сроках;
- страхов;
- технологий;
- врачей;
- парковки;
- clinic microfacts;
- маркетинговых сценариев;
- семантического выбора услуги;
- APRF / отбеливания / биоматериала / parking и прочих clinic-specific тем.

Любое расширение разрешённого regex-класса требует изменения Architecture Lock и явного согласования владельца продукта.

---

## 6. FullContext and structured facts

### 6.1 Full corpus (обязательно)

Каждый обычный модельный запрос получает **полный** утверждённый MD-корпус конкретного `client_id`.

**Постоянный префикс (cacheable):**

- system policy;
- полный client MD corpus;
- компактный каталог canonical `service_id` / name;
- стабильные клиентские правила.

**Динамическая часть после префикса:**

- session facts;
- typed UI facts;
- user message;
- другие текущие управляющие данные.

### 6.2 Запрещено vs разрешено (selected context)

**Запрещено:**

- RAG / retriever / chunk selector, определяющий, **какую часть** знаний увидит модель;
- selected context как **замена** полного корпуса.

**Разрешено:**

- обязательный полный cached MD corpus для модели;
- code-owned structured facts, offer IDs и exact resolution для цен, UI и deterministic marketing;
- эти структуры **не фильтруют** знания модели и **не заменяют** FullContext.

RAG допускается только после отдельного Architecture Lock amendment, если повторяемые измерения покажут нарушение SLO (см. §15).

### 6.3 Cache identity and invalidation

Кэшировать по составному ключу:

```
client_id
+ immutable client_pack_version/hash
+ prompt_contract_version
+ model_snapshot
```

**Запрещён** кэш только по `client_id` без проверки версии pack.

После атомарной активации нового client pack следующий запрос **не должен** получать старый corpus.

**Stage 3A (принято):** cached FullContext prefix и pack identity реализованы и приняты в baseline.

---

## 7. Multiclient contract

Все данные клиники находятся только в:

- `clients/<client_id>/md`;
- service catalog;
- pricebook;
- facts;
- doctor catalog;
- client marketing/presentation config.

Глобальный Python-код **не содержит** clinic-specific услуг, фактов, цен, врачей, акций, CTA или разговорных синонимов.

Контекст и cache разделены по ключу из §6.3.

---

## 8. Typed UI

Governed UI `service_id` / ref / scope / stage action **не интерпретируется моделью** — это авторитетный typed input.

Модель **никогда** не переопределяет `service_id`, extent, jaw или stage из governed UI.

**Routing typed UI:**

- 0 LLM для routing;
- terminal response может быть полностью 0-call;
- если нужен narrative, допускается один Flash call с уже зафиксированными typed facts;
- typed UI **не** обходит candidate path при flag ON.

**0-call без модели:** exact contacts, booking terminal actions, obvious urgent hard-stop.

---

## 9. Typed model contract

Flash возвращает валидируемый **control envelope**. Все перечисленные поля — **закрытые** значения; свободные строки там, где код принимает решение, **запрещены**.

| Поле | Допустимые значения |
|------|---------------------|
| `route` | `ANSWER` \| `ADMIN` \| `CLARIFY` |
| `service_id` | ID из **активного** client pack **или** `null` |
| `extent` | `one_tooth` \| `few_teeth` \| `full_arch` \| `null` |
| `jaw` | `upper` \| `lower` \| `both` \| `null` |
| `stage` | значение из client-authored allowlist **или** `null` |
| `scenario` | `pain_fear` \| `cost` \| `time` \| `doctor_trust` \| `result_reliability` \| `none` |
| `commercial_intent` | `none` \| `price` \| `payment` \| `included` |
| `clarify_axis` | `service` \| `extent` \| `jaw` \| `stage` \| `null` |
| clarify service options | максимум 3 `service_id` из активного client pack |
| patient answer text | narrative для пациента (без коммерческих значений — см. §11) |

### 9.1 `commercial_intent` (closed field)

| Значение | Нормативная семантика |
|----------|----------------------|
| `none` | Не открывает price / payment / included surfaces; см. bounded exception §9.1 |
| `price` | Явный интерес к цене / стоимости |
| `payment` | Явный интерес к оплате, рассрочке или способам платежа |
| `included` | Вопрос о составе или включённых услугах |

**Правила:**

- каждый non-`none` intent открывает **только** соответствующую коммерческую поверхность и **не** разрешает добавлять нерелевантные offer / facts;
- price, сумма и price offer card показываются **только** при `commercial_intent=price` и наличии validated price result из authoritative commerce result;
- `commercial_intent=payment` открывает **только** validated clinic-owned payment terms/data и **не** открывает price surface (сумму, price offer card);
- `commercial_intent=included` открывает **только** validated included items / состав и **не** открывает price surface (сумму, price offer card);
- `commercial_intent=none` **не** открывает price, payment или included surfaces и **не** разрешает дополнительные случайные commercial facts;
- **единственное owner-approved bounded исключение при `commercial_intent=none`:** обязательная **priority service promo** на первом допустимом `ANSWER` с authoritative non-null `service_id` (§13). Исключение **не** открывает price amount, price/offer card, payment terms или included items; при `service_id=null` автоматическая service promo **запрещена**;
- модель **не придумывает** и **не вычисляет** коммерческие значения; все значения берутся **только** из authoritative commerce result.

Невалидное значение любого closed-field → invalid envelope → neutral presentation или safe handoff по route, **не** повторный вызов.

### 9.2 Structured output transport

**Stage 3B (принято):** capability JSON/streaming на точном Flash snapshot подтверждён управляемым LIVE-прогоном.

**Stage 4.2 (принято):** production closed JSON envelope — provider-supported schema-constrained output; versioned typed envelope с **единым** blocking/streaming parser; `@ANSWER` line protocol **не** является целевым transport.

**Нормативно:**

- **предпочтителен** provider-supported schema-constrained output;
- versioned typed envelope с **единым** blocking/streaming parser;
- старый хрупкий `@ANSWER` line protocol **не является** целевым контрактом;
- control должен завершиться **до** streaming patient text;
- medical/route protocol **не должен** утекать пациенту.

---

## 10. CLARIFY

**Разрешённые `clarify_axis`:** `service`, `extent`, `jaw`, `stage` (см. §9).

Только **2–3** client-authored UI options (`service_id` из активного pack).

**Запрещены** медицинские уточнения: симптомы, диагноз, анамнез, противопоказания, выбор лечения, дозировки.

Medical/problematic request → `ADMIN`, без диалога.

**Semantic ownership для CLARIFY:**

- bare service / generic topic **не требует** обязательного `CLARIFY`;
- `CLARIFY` допустим **только** если без уточнения по `service` / `extent` / `jaw` / `stage` корректный ответ невозможен;
- подтверждённый microfact может отвечаться с `service_id=null` без принудительного выбора услуги;
- слабый catalog match **не** становится authoritative `service_id`.

---

## 11. COMMERCIAL_RENDER_CONTRACT

**Единственный нормативный механизм** коммерческих данных в widget — `COMMERCIAL_RENDER_CONTRACT`.

Он означает:

1. Модель **не является** источником цен, скидок, рассрочки и коммерческой гарантии.
2. Модель возвращает narrative **без** таких коммерческих значений.
3. Код **после** ответа выбирает validated commerce data по `service_id`, `extent`, `jaw`, scope **и** подтверждённому `commercial_intent`:
   - **price surface** — только при `commercial_intent=price` и validated price offer;
   - **payment surface** — только при `commercial_intent=payment` и validated clinic-owned payment terms/data; **не** открывает сумму или price offer card;
   - **included surface** — только при `commercial_intent=included` и validated included items / состав; **не** открывает сумму или price offer card.
4. Текстовый блок, карточка, CTA и кнопки **соответствующей** поверхности строятся из **одного** validated authoritative commerce result для этой поверхности.
5. **Невозможна** ситуация, когда текст показывает одну цену, а карточка — другую.
6. Без `commercial_intent=price` сумма и price offer card **не показываются** и **не вычисляются**; это **не** запрещает релевантный payment- или included-ответ при соответствующем intent.
7. При `commercial_intent=none` price / payment / included surfaces **не** рендерятся. **Исключение:** priority service promo §13 — единственный разрешённый commercial fact при `none`; она **не** открывает price amount, price/offer card, payment terms или included items.
8. Медицинские и некоммерческие числа из утверждённого MD **не запрещаются**.
9. Priority service promo, marketing facts и amplifiers выбираются и рендерятся **детерминированным кодом после Flash**; Flash не придумывает и не пересказывает точные условия акции.

**Clinic-owned price strategy (принято в baseline `fce68be`):**

- стратегия показа цены принадлежит client pack / clinic-owned policy;
- text и card используют **единый** authoritative commerce result.

При ambiguous/invalid service or scope:

- никакой суммы;
- `ANSWER` / `CLARIFY` без `ADMIN`;
- максимум 3 client-authored options.

**Не вводить** общий deny-by-default numeric gate и **не возвращать** строгий LLM Verifier.

---

## 12. Contacts, booking, urgent

**Exact contacts:**

- deterministic client data;
- 0 LLM;
- не `ADMIN`;
- specific contact question (например parking) **должен** возвращать **только** требуемое поле, не весь contacts payload (принято Stage 4.3).

**Booking:**

- deterministic lead state machine;
- никогда не подтверждать доступность слота;
- предпочтение даты передаётся администратору;
- не эхоить дату как подтверждённую запись.

**Obvious urgent/problem:**

- immediate `ADMIN`;
- 0 LLM.

**Неочевидный** medical/problem request:

- Flash обязан вернуть `ADMIN` в том же единственном вызове;
- никаких последующих вопросов;
- **без** содержательного медицинского ответа перед handoff.

---

## 13. Marketing contract

Flash выбирает только один primary `scenario` из закрытого enum (§9). Flash **не** придумывает offer/fact/CTA и **не** пересказывает точные условия акции. Flash возвращает `commercial_intent`; код решает, какая коммерческая поверхность допустима.

### 13.1 Priority service promo (первый ответ об услуге)

На первом допустимом содержательном `ANSWER` с authoritative non-null `service_id` бот обязан показать **ровно одну** главную active, непросроченную, service-linked акцию этой услуги:

- выбирается детерминированным кодом **после Flash** по clinic-authored priority из client data;
- текст, процент, срок и условия — **только** из authoritative client data; Flash не придумывает и не пересказывает;
- правило действует для первого допустимого ответа о конкретной услуге, а не только для «что это?» / «делаете ли вы?»;
- priority promo — **marketing fact**, **не** amplifier; входит в общий лимит **3** marketing facts, но **не** занимает лимит **2** amplifiers;
- при `commercial_intent=none` — **единственное** разрешённое commercial исключение (§9.1, §11); **не** открывает price amount, price/offer card, payment terms или included items;
- при `service_id=null` автоматическая service promo **запрещена**;
- показывается **один раз** после фактического render; прямой вопрос об **уже показанной конкретной** акции получает ответ повторно — suppression повтора обходится, eligibility/active dates/service applicability **не** обходятся; общий вопрос «Какие акции есть?» — unresolved semantic seam Stage 5.1 (без отдельного promo intent в envelope).

### 13.2 Лимиты marketing facts и amplifiers

Для demo/client policy:

- максимум **3** marketing facts в ответе;
- максимум **2** textual amplifiers;
- priority promo входит в **3**, но **не** в **2**;
- selector **сначала** резервирует priority promo (если eligible), **затем** выбирает до двух релевантных amplifiers одного primary `scenario`;
- остальные применимые facts — только в оставшихся местах общего лимита **3**;
- пустые места **не** заполняются нерелевантными фактами;
- бесплатная консультация и рассрочка **не** добавляются автоматически в первом ответе сверх priority promo и усилителей; рассрочка — при прямом вопросе об оплате или валидном cost/payment context; консультация — как применимый выбранный fact или через отдельный CTA/consultation flow.

Историческая формулировка «максимум один hook» согласована с client config **3/2**: один обязательный priority promo + до двух amplifiers **не** противоречат друг другу.

### 13.3 CTA и navigation slots

**CTA** существует отдельно:

- не занимает marketing-fact limit **3**;
- не занимает amplifier slots **2**;
- не занимает два secondary UI slots;
- выбирается из client-authored CTA config; Flash не придумывает CTA;
- запрещена в hard-stop / `ADMIN` / жалобе / urgent / manual-contact и там, где текущий контракт её подавляет.

**Content secondary slots (max 2):** video (если существует, применимо и ещё не показано) → следующие ещё не показанные content follow-up → «Рассказать о ситуации», если разрешено и остался слот.

**Channel mutex:** choice menu (max 4), content secondary (max 2), price-detail (max 2) — отдельные каналы; один ответ использует **только один** navigation channel.

### 13.4 Исключения и shown-state

Автоматическая priority promo и остальные marketing facts **запрещены** в: `CLARIFY`, `ADMIN`, current personal pain / urgent medical, active complication, complaint/dispute/reaction-required review, manual-contact hard-stop, spam/off-topic, provider/error fallback, turn без authoritative `service_id`.

**Shown-state:**

- записывается **только** после фактического materialized render;
- выбранный, но не отображённый факт **не** считается показанным;
- marketing facts, amplifiers, video, content follow-up, price follow-up и situation имеют соответствующий cadence/shown-state;
- price follow-up после реального показа **всегда** фиксируется как shown;
- прямой вопрос об already-shown fact должен получить ответ повторно.

**Deterministic presentation** (через `COMMERCIAL_RENDER_CONTRACT` и marketing layer):

- порядок отбора: (1) direct requested fact, если есть; (2) обязательная priority service promo первого eligible service turn; (3) до двух релевантных amplifiers primary `scenario`; (4) остальные применимые facts в оставшихся местах лимита **3**; (5) CTA отдельно;
- direct request обходит только suppression повтора;
- neutral/general запрос / `commercial_intent=none` **не** получает случайный implantation marketing или цену, кроме bounded priority service promo §13.1;
- marketing supplement и offer card **не** меняют presentation независимо друг от друга.

### 13.5 Performance invariant (Stage 5.1)

Stage 5.1 **не** добавляет provider call; invariant `provider_calls ∈ {0, 1}` на HTTP-запрос
сохраняется.

**Запрещено в Stage 5.1:**

- отдельный marketing LLM, retry или model repair;
- второй provider call ради marketing/presentation;
- сетевое чтение marketing/client data на каждом turn;
- вторая полная сборка package/materialization.

**Разрешено:**

- selector и `PresentationResult` работают **локально после Flash**;
- **один** локальный presentation pass на turn;
- диагностика локального времени selector/presentation (без нового hard SLO без owner decision).

Абсолютные speed gates §15.2 (8s / 10s / 6s) **не ослабляются**. Конкретные миллисекунды
(например 20–50 ms) **не** фиксируются как обязательный нормативный gate — владелец их
отдельно не утверждал.

---

## 14. Activation quality gates

До включения обязательны frozen E2E matrices:

| Область | Критерий |
|---------|----------|
| Medical/problematic | 0 false `ANSWER` на protected cases (§ ANSWER/ADMIN) |
| Sales fears | 0 false `ADMIN` на protected fear cases |
| Price | `COMMERCIAL_RENDER_CONTRACT`: один validated result; 0 invented/computed amounts; price/sum/price card **только** при `commercial_intent=price`; ambiguous scope без суммы |
| Commercial intent | closed enum §9.1; каждый intent открывает только соответствующую поверхность; `payment` и `included` **не** открывают price surface; `none` не открывает price/payment/included, кроме bounded priority service promo §13.1 |
| Marketing | лимит 3/2; priority promo в **3**, не в **2**; первый eligible service turn с `service_id` обязан показать одну priority promo; CTA и navigation slots отдельны; shown-state только после render; price follow-up always shown |
| Microfacts | вопросы по всему MD-корпусу, включая неизвестные заранее темы; допустим `service_id=null` |
| Semantic ownership | без implantation default; без сужения generic topic; `CLARIFY` только при реальной зависимости |
| Multiclient | минимум два client packs; отсутствие cross-client data leakage |
| Calls | `provider_calls` 0 или 1 на всём HTTP-запросе |
| Streaming | control metadata не показывается пользователю; один provider call; корректный final widget; production-faithful SSE |
| Performance | абсолютные speed gates §15.2 — без послабления |

Quality, medical, multiclient и `0/1 calls` gates **не ослабляются** ради скорости.

---

## 15. Performance contract

### 15.1 Измерять (обязательно сохранять)

- patient TTFT p50/p95;
- total p50/p95;
- prompt / completion / cached tokens;
- cache hit / miss rate;
- provider call count.

Замеры выполняются на **frozen production-faithful matrix** (Stage 3C принято).

### 15.2 Activation performance gate (absolute — принято Stage 3C)

**Supersedes** прежние формулировки §15.2, требовавшие обязательного относительного улучшения над legacy и откладывавшие абсолютные секунды «до Stage 3 calibration».

**Принятые абсолютные gates (activation):**

| Метрика | Порог |
|---------|-------|
| normal NEW warm total p50 | ≤ **8** секунд |
| каждый normal NEW case total | ≤ **10** секунд |
| warm patient TTFT p95 | ≤ **6** секунд |

**Дополнительные правила:**

1. Один и тот же frozen production-faithful corpus и case matrix.
2. Сохраняются метрики из §15.1 на каждом прогоне.
3. Новая схема **не обязана** быть быстрее legacy на **каждом** отдельном вопросе.
4. Quality / medical / multiclient / `0/1 calls` gates (§14) — **без послабления**.
5. **Глобально менять архитектуру** ради дальнейшего ускорения **запрещено**.
6. **Stage 5.4** допускает **только** небольшую доказательную полировку (§19).
7. **Никаких** RAG, новых моделей или новых provider calls ради скорости.
8. Отдельно фиксируются cache hit/miss; при cache miss SLO оценивается отдельно.
9. **Без** выполнения абсолютных gates activation **запрещена**.

Относительное сравнение с legacy может сохраняться **только как diagnostic**, не как blocking activation gate.

Изменение архитектуры **запрещено** на основании одного запуска.

Переход к RAG требует: повторяемого превышения SLO; отдельного Architecture Lock amendment; явного согласования владельца продукта.

---

## 16. Explicit non-goals

Не входят:

- RAG / retriever как filter знаний модели;
- selected context как замена FullContext;
- второй classifier;
- Planner;
- Verifier;
- агентная цепочка;
- clinic-specific regex (APRF, whitening, parking и т.д.);
- разговорный словарь всех пользовательских формулировок;
- вычисление цен моделью;
- `@ANSWER` line protocol как целевой transport;
- старая `medical_handoff`-семантика с содержательным ответом перед handoff;
- глобальная перестройка или новые модели **ради скорости**; Stage 5.4 разрешает только перечисленную в §19 небольшую полировку без архитектурных изменений.

---

## 17. Current known gaps (post Stage 4.3 baseline)

Проверяемые расхождения **после** принятого Stage 4.3 baseline (`6345b37`). Ниже — только **оставшиеся** gaps; закрытые Stage 4.1–4.3 перечислены отдельно с commit mapping.

### 17.1 Оставшиеся gaps

1. **«Отбеливание» — двойной ответ:** наблюдается двойной ответ; **причина не утверждается** без доказанной SSE-трассы (Stage 5.2).
2. **Survivability microfact:** нейтральный вопрос о приживаемости имплантов после корректного факта 99,8% может получить нерелевантные сведения о птеригоидных имплантах, консультации, гарантии и цене.
3. **Marketing overload / priority promo / `PresentationResult`:** marketing layer может добавлять слишком много фактов; обязательная priority service promo на первом service turn и единый `PresentationResult` **не реализованы** (Stage 5.1).
4. **Direct promo overview seam:** общий вопрос «Какие акции есть?» не имеет отдельного promo intent в closed envelope; точное количество promo facts для overview **не** определено до owner decision и read-only Stage 5.1 seam audit.
5. **Price-follow-up shown-state:** основная price-follow-up ветка может не записывать реально показанные кнопки в cadence / shown-state.
6. **Priority promo authority unresolved:** в current demo data нет однозначного authored authority для главной priority service promo (`kind=promo` недостаточно; consultation/installment стоят раньше discount в order; discount также в amplifier pool). Требуется read-only Stage 5.1 seam audit (§13, `MARKETING_SCENARIO_ARCHITECTURE.md`).

### 17.2 Закрыто принятыми Stage 4.1–4.3 (не перечислять как gaps)

| Gap | Закрыт этапом | Evidence |
|-----|---------------|----------|
| Dual prompt protocol (`@ANSWER` сосуществует с typed envelope) | Stage 4.2 | `b833482e1cf6f00637fbfa7525df5d29e5f79a57` |
| Windows logging / SSE diagnostics path | Stage 4.1 | `1d89190ea0bb334e57fe782f8f121458fa3c329e` |
| Specific contact question возвращает весь contacts payload | Stage 4.3 | `6345b37eec2807bc2008e68f8a01018407af044f` |
| APRF / биоматериал → лишний `CLARIFY` или цена | Stage 4.3 | `6345b37eec2807bc2008e68f8a01018407af044f` |
| Generic topic narrowing до brand / technology / offer | Stage 4.3 | `6345b37eec2807bc2008e68f8a01018407af044f` |
| Price without подтверждённого `commercial_intent` | Stage 4.3 | `6345b37eec2807bc2008e68f8a01018407af044f` |

**Закрыто в Stage 0–3 (не перечислять как gaps):** HTTP-scoped provider-call governance; Problem Gate first; typed UI в candidate path; cached FullContext prefix + pack identity; Flash capability JSON/streaming; production-faithful speed measurement; absolute speed gates; clinic-owned price strategy + единый authoritative commerce result для text/card.

---

## 18. Change control

Architecture Lock изменяется только:

- отдельным review;
- с перечислением trade-offs;
- после явного согласования владельца продукта.

Обычная реализация **не может** молча менять архитектуру.

**Stage 4.0:** docs-only синхронизация; код не меняется; Alibaba LIVE запрещён без явной команды владельца.

---

## 19. Frozen implementation roadmap (Stage 4.0–6)

Roadmap **заморожен** после Stage 4.0. Этапы разделены; gaps §17 **не считаются исправленными**, пока этап не принят checker.

### Stage 4.0 — Architecture Lock sync (принят, docs-only)

- статусы Stage 0–3;
- абсолютные speed gates §15.2;
- closed `commercial_intent` §9.1;
- `service_id=null` для microfacts §4;
- bare service не требует обязательного `CLARIFY` §10;
- актуальные gaps §17;
- **никаких** изменений кода; **никакого** LIVE.

### Stage 4.1 — Windows logging (принят)

- абсолютный log path от корня проекта;
- Windows-safe single writer;
- startup event с фактическим log path;
- PII-free route / timings / provider / SSE diagnostics;
- streamed / final length + hash для диагностики дублей.

### Stage 4.2 — Production closed JSON envelope (принят)

- убрать `@ANSWER` line protocol;
- closed `route` / `service_id` / scope / `scenario` / `commercial_intent` / clarify fields + `patient_text`;
- единый blocking / streaming parser;
- пациент видит **только** `patient_text`;
- invalid envelope → safe result без retry;
- `0/1` provider calls.

### Stage 4.3 — Semantic ownership (принят)

- свободный язык понимает Flash;
- убрать authoritative implantation default;
- слабый catalog match — только подсказка;
- microfacts могут отвечать с `service_id=null`;
- `CLARIFY` только при реальной зависимости ответа от service / extent / jaw / stage;
- generic question не сужается до brand / technology;
- `commercial_intent=none` запрещает цену;
- specific contact question возвращает только нужное поле;
- **никаких** APRF / whitening-specific regex.

### Stage 5.1 — Единый marketing/commercial `PresentationResult` (docs-only contract synchronization; implementation **не** начата)

**Нормативный marketing contract (§13) зафиксирован docs-only.** Реализация ещё должна создать единый `PresentationResult`:

- один источник final text, offer/card, marketing facts, CTA, follow-up, двух secondary button slots, cadence и shown-state;
- priority service promo на первом eligible `ANSWER` с authoritative `service_id` — детерминированный post-Flash selector; один active service-linked promo по clinic priority; входит в лимит **3**, не в **2**; при `commercial_intent=none` — единственное bounded commercial исключение без price/payment/included surfaces;
- selector: direct requested fact → priority promo → до двух amplifiers primary `scenario` → остальные facts в оставшихся местах **3**; CTA отдельно;
- consultation/installment **не** автодобавляются в первом ответе сверх priority promo и amplifiers;
- marketing fact реально включается в текст; нет дублирования;
- direct request об **уже показанной конкретной** акции обходит suppression повтора; eligibility/active dates/service applicability — нет; общий promo overview — unresolved seam (read-only audit);
- shown-state только после фактического render; price follow-up **всегда** фиксируется как shown;
- один primary `scenario` из envelope; конкретные facts выбирает код;
- neutral microfact / `service_id=null` не получает автоматическую service promo;
- read-only seam audits: (a) direct promo overview semantic seam; (b) priority promo authority in current client data — **без** regex/keyword classifier и **без** второго provider call;
- **performance invariant §13.5:** 0/1 provider calls; один локальный presentation pass после Flash; без marketing LLM/retry/network re-read; absolute gates §15.2 не ослабляются; без нового hard ms-SLO без owner decision.

### Stage 5.2 — Widget / SSE

- один user turn → один bot bubble;
- final UI атомарно заменяет live bubble;
- control fields не видны пациенту;
- двойной ответ «Отбеливание» исправляется **только** по доказанной реальной SSE-трассе.

### Stage 5.3 — Frozen multiclient E2E

- услуги, свободные формулировки, цены и scopes;
- APRF, технологии, parking, стерильность и произвольные строки полного MD;
- врачи, страхи, medical ADMIN;
- contacts и booking;
- marketing / CTA / buttons / cadence;
- минимум два разных client packs;
- отсутствие cross-client leakage;
- `0/1` calls и абсолютные speed gates §15.2.

### Stage 5.4 — Только небольшая полировка скорости

- completion-token profile;
- снижение `max_completion_tokens` **только** при доказанном отсутствии truncation;
- убрать повторную materialization / render;
- проверить существующие client / prefix caches;
- **никаких** RAG, новых моделей или глобальной перестройки.

### Stage 6 — Activation

- local / staging flag ON;
- ручная проверка владельца;
- Checker acceptance;
- default ON **только** после явного согласия владельца;
- legacy временно сохраняется как rollback, затем удаляется;
- clean branch переносится отдельно от dirty `demo-bot-local`.

---

## Checker scoped allowlist (historical — Stage 4.0 revision)

> **Исторический checklist.** Не является текущим acceptance gate. Актуальный baseline — Stage 4.3 (`6345b37`); Stage 5.1 docs sync ожидает отдельного Checker review.

| Разрешено | Запрещено |
|-----------|-----------|
| `docs/ONE_CALL_CACHED_FULLCONTEXT_ARCHITECTURE_LOCK.md` (MODIFY) | Код, тесты, `TASK.md`, env, другие docs |
| | Alibaba LIVE / provider calls |
| | Commit без явной команды владельца |

**Критерии повторного review (Stage 4.0):**

- [ ] Изменён **ровно один** docs-файл; нет кода и тестовых изменений; нет LIVE; нет commit.
- [ ] Current implementation status: Stage 0–2 приняты; Stage 3A/3B/3C приняты; clinic-owned price + authoritative commerce приняты; `SALES_ONE_PLUS_ON` default OFF; Alibaba LIVE запрещён после Stage 4.0.
- [ ] Неизменяемая архитектурная основа §1 сохранена без ослабления.
- [ ] §9 — closed envelope incl. `commercial_intent` (`none` \| `price` \| `payment` \| `included`); `scenario` enum; uppercase `route`.
- [ ] §9.1, §11, §13, §14 — согласованная семантика `commercial_intent`.
- [ ] §4, §10 — `service_id=null`, semantic ownership, bare service без обязательного `CLARIFY`.
- [ ] §11 — `COMMERCIAL_RENDER_CONTRACT` + clinic-owned authoritative commerce result.
- [ ] §6 — FullContext vs selected context; cache key §6.3; Stage 3A accepted noted.
- [ ] §3 — active runtime до/при flag ON/после Stage 6.
- [ ] §15.2 — абсолютные gates (8s / 10s / 6s); superseded relative-only activation; diagnostic-only legacy comparison allowed.
- [ ] §17 — актуальные gaps; принятые Stage 0–3 **не** перечислены как незакрытые; будущие Stage 4.1+ **не** названы исправленными.
- [ ] §19 — frozen roadmap Stage 4.0, 4.1, 4.2, 4.3, 5.1, 5.2, 5.3, 5.4, 6 раздельно.
- [ ] Supersession `ARCH_TARGET_DESIGN.md` и ANSWER/ADMIN граница сохранены.
- [ ] §9.2 — structured output; Stage 3B accepted; `@ANSWER` не целевой transport.
- [ ] §8 — typed UI не интерпретируется моделью; 0-call contacts/booking/urgent.
