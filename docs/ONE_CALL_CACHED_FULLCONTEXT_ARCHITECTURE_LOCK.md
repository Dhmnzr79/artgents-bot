# ONE_CALL_CACHED_FULLCONTEXT — Architecture Lock

**Статус:** нормативный TARGET-контракт + синхронизация принятого baseline (Stage 4.3 принят; Stage 5.1 — **принят**; Stage 5.1B — **принят**; Stage 5.2 — **принят**).
**Дата:** 2026-08-13.
**Модель:** `qwen3.7-flash-2026-07-15`.
**Baseline HEAD:** `984ab65a5a653576b065b692043d07a6d5daaee7`.

Этот документ фиксирует **целевую** архитектуру продукта и **контракт** принятого состояния Stage 0–5.2. Разделы §1–§16 — нормативный TARGET; § «Current implementation status» и §17 — проверяемое текущее состояние baseline и оставшиеся gaps. Закрытие gaps §17 — отдельные этапы frozen roadmap §19.

### Current implementation status (Stage 0–5.2 accepted)

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
| Stage 5.1 — Единый marketing/commercial `PresentationResult` | **Принят** (`a268878`) |
| Stage 5.1B — Service availability / alternatives / price gaps | **Принят** (`51621af`) |
| Stage 5.2 — Widget / SSE terminal idempotency | **Принят** (`490bdbb`; test EOL cleanup `984ab65`) |
| Stage 5.3 — Frozen multiclient E2E | **Не** начат |
| `SALES_ONE_PLUS_ON` | **default OFF** — без изменений |
| Alibaba LIVE после Stage 4.0 | **Запрещён** без отдельной явной команды владельца |

Stage 5.1 **считается реализованным и принятым** (`a268878`). Stage 5.1B **считается реализованным и принятым** (`51621af`). Stage 5.2 **считается реализованным и принятым** (`490bdbb`; test line-ending cleanup `984ab65`). Stage 5.3+ **не считаются реализованными**, пока соответствующий этап не принят checker. Оставшиеся gaps §17 **не объявлены исправленными**, пока этап не принят checker.

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
- общие вопросы о противопоказаниях;
- общие вопросы о хронических заболеваниях;
- другие информационные медицинские FAQ, если ответ grounded в FullContext клиники;
- любые подтверждённые бытовые и клинические microfacts из MD;
- без персонального диагноза, назначения и вердикта о пригодности.

**`ADMIN`** — немедленный handoff администратору, **без** медицинского диалога и **без** содержательного медицинского ответа перед handoff:

- **текущие** симптомы, боль, кровь, отёк, воспаление, осложнения;
- жалоба, отзыв, просьба о директоре/руководителе;
- постановка диагноза;
- персональное лечение, лекарства и медицинские назначения;
- явная просьба вынести персональный медицинский вердикт.

**Запрещено:**

- blanket-правило «любое медицинское слово → ADMIN»;
- возврат к режиму, где проблемный медицинский запрос получает содержательный медицинский ответ перед handoff;
- сомнение само по себе как основание для ADMIN;
- десятки отдельных проблемных сценариев вместо короткой high-precision границы;
- false-positive handoff, когда нормальный grounded-ответ по базе клиники возможен.

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
| `commercial_intent` | `none` \| `price` \| `payment` \| `included` \| `promotion` |
| `promotion_scope` | `none` \| `general` \| `service` \| `shown` |
| `clarify_axis` | `service` \| `extent` \| `jaw` \| `stage` \| `null` |
| clarify service options | максимум 3 `service_id` из активного client pack |
| patient answer text | narrative для пациента (без коммерческих значений — см. §11) |

### 9.1 `commercial_intent` (closed field)

| Значение | Нормативная семантика |
|----------|----------------------|
| `none` | Не открывает price / payment / included / promotion surfaces; см. bounded exception §9.1 |
| `price` | Явный интерес к цене / стоимости |
| `payment` | Явный интерес к оплате, рассрочке или способам платежа |
| `included` | Вопрос о составе или включённых услугах |
| `promotion` | Явный интерес к акции, скидке или специальному предложению; см. §9.3 |

**Правила:**

- каждый non-`none` intent открывает **только** соответствующую коммерческую поверхность и **не** разрешает добавлять нерелевантные offer / facts;
- price, сумма и price offer card показываются **только** при `commercial_intent=price` и наличии validated price result из authoritative commerce result;
- `commercial_intent=payment` открывает **только** validated clinic-owned payment terms/data и **не** открывает price surface (сумму, price offer card);
- `commercial_intent=included` открывает **только** validated included items / состав и **не** открывает price surface (сумму, price offer card);
- `commercial_intent=promotion` открывает **только** validated promo facts из authoritative client data по `promotion_scope` §9.3; **не** открывает price amount, price/offer card, payment terms или included items; модель **не** генерирует процент, срок или условия акции;
- `commercial_intent=none` **не** открывает price, payment, included или promotion surfaces и **не** разрешает дополнительные случайные commercial facts;
- **единственное owner-approved bounded исключение при `commercial_intent=none` и `promotion_scope=none`:** обязательная **priority service promo** на первом допустимом `ANSWER` с authoritative non-null `service_id` (§13). Исключение **не** открывает price amount, price/offer card, payment terms или included items; при `service_id=null` автоматическая service promo **запрещена**; обычный вопрос об услуге **не** превращается в promotion request;
- модель **не придумывает** и **не вычисляет** коммерческие значения; все значения берутся **только** из authoritative commerce result и client promo data.

### 9.3 `promotion_scope` (closed field)

| Значение | Нормативная семантика |
|----------|----------------------|
| `none` | Promotion request отсутствует |
| `general` | Общий вопрос «Какие акции есть?» |
| `service` | Вопрос об акциях конкретной authoritative услуги |
| `shown` | Вопрос о ранее **фактически rendered** promo текущей session |

**Invariants:**

- если `commercial_intent != promotion`, то `promotion_scope=none`;
- если `commercial_intent=promotion`, то `promotion_scope` ∈ {`general`, `service`, `shown`};
- `service` требует authoritative non-null `service_id`;
- `general` допускает `service_id=null`;
- `shown` требует session-bound последнюю реально показанную promo; если такой promo нет — **fail closed**, факт **не** угадывается;
- `CLARIFY` и `ADMIN` принудительно **не** открывают promotion surface;
- **`promotion_ref` не добавляется** в этом amendment; arbitrary specific promo, которая ранее не была показана и не определяется service priority, **не** угадывается по тексту, regex или keyword classifier.

Невалидное значение любого closed-field → invalid envelope → neutral presentation или safe handoff по route, **не** повторный вызов.

**G4 — grounded data-gap (owner accepted):** Normal in-scope clinic/dental questions fail open to one grounded model answer. If the supplied client corpus lacks the requested fact, the model must not invent or borrow cross-client data; it gives a concise honest data-gap answer and directs the patient to the administrator. Missing corpus data alone is not route=ADMIN. No per-topic local filters.

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
3. Код **после** ответа выбирает validated commerce data по `service_id`, `extent`, `jaw`, scope **и** подтверждённому `commercial_intent` / `promotion_scope`:
   - **price surface** — только при `commercial_intent=price` и validated price offer;
   - **payment surface** — только при `commercial_intent=payment` и validated clinic-owned payment terms/data; **не** открывает сумму или price offer card;
   - **included surface** — только при `commercial_intent=included` и validated included items / состав; **не** открывает сумму или price offer card;
   - **promotion surface** — только при `commercial_intent=promotion` и validated promo facts по `promotion_scope` §9.3; **не** открывает price amount, price/offer card, payment terms или included items.
4. Текстовый блок, карточка, CTA и кнопки **соответствующей** поверхности строятся из **одного** validated authoritative commerce result для этой поверхности.
5. **Невозможна** ситуация, когда текст показывает одну цену, а карточка — другую.
6. Без `commercial_intent=price` сумма и price offer card **не показываются** и **не вычисляются**; это **не** запрещает релевантный payment- или included-ответ при соответствующем intent.
7. При `commercial_intent=none` и `promotion_scope=none` price / payment / included / promotion surfaces **не** рендерятся. **Исключение:** priority service promo §13 — единственный разрешённый commercial fact при `none`; она **не** открывает price amount, price/offer card, payment terms или included items.
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

### 11.1 Service availability, authored alternatives and price gaps (Stage 5.1B — **принят**, `51621af`)

Три **независимые** оси. Отсутствие цены **не** означает отсутствие услуги. Catalog miss **не** должен автоматически превращаться в уверенное «клиника не оказывает услугу».

#### Service availability

| Состояние | Семантика |
|-----------|-----------|
| `offered` | Canonical service существует и `active=true` |
| `known_not_offered` | Canonical service существует, но `active=false` |
| `unresolved` | Термин не разрешён в canonical service |

#### Price coverage

| Уровень | Семантика |
|---------|-----------|
| exact numeric offer | `fixed` \| `from` \| `range` для конкретной услуги |
| exact `no_public_price` | Утверждённый `approved_text` без суммы |
| explicitly applicable family-level context | Family price только при явном `applies_to_service_ids` + `approved_context`; **не** exact offer и **не** price card |
| no applicable price evidence | Без суммы; допустим controlled data-gap / CTA |

**Price precedence (нормативно):**

1. exact numeric service offer;
2. exact `no_public_price`;
3. optional family-level context with explicit applicability;
4. no amount / data-gap response.

Family-level context **никогда** не заменяет exact service offer или `no_public_price`. Даже при явной applicability family price **не** наследуется как exact offer и **не** создаёт price card конкретной услуги.

#### Alternative authority

Альтернатива существует **только** при явной clinic-authored связи. Current accepted runtime использует typed evolution `clinic_policies.yaml` → `service_alternatives`:

```yaml
service_alternatives:
  - requested_service_id: braces
    alternative_service_ids:
      - aligners
    approved_text: >-
      Брекеты мы не устанавливаем. Для выравнивания зубов
      в клинике используются элайнеры.
```

**Правила:** `requested_service_id` и каждый `alternative_service_id` существуют в catalog; alternative **active**; максимум **2** alternatives; порядок IDs = clinic priority; label, content ref и price альтернативы — из её собственных authoritative sources; **никаких** keyword/regex/fuzzy/LLM similarity; legacy `match_keywords` / `mention` / `suggest_ref` / `note` — **historical compatibility only** при `SALES_ONE_PLUS_ON=OFF`, **не** current ONE_CALL identity owner; бренды (Osstem и т.п.) — отдельный brand seam, не service alternative; unknown term без canonical match **не** получает придуманную альтернативу.

#### Обязательная матрица поведения

1. **Not-offered, без alternatives:** confirmed not-offered; **без** цены, price card, promo; **без** случайных услуг; допустим только нейтральный clinic-policy CTA/handoff, если отдельно разрешён.
2. **Not-offered, с authored alternatives:** сначала confirmed not-offered; затем 1–2 authored alternatives **отдельно**; не описывать как эквивалентные/лучшие/лично подходящие без source authority; alternative buttons → content secondary slots; CTA отдельно.
3. **Offered, `no_public_price`:** подтвердить наличие услуги; exact `approved_text`; **без** суммы/price card; **без** похожей, вычисленной, component или family price как цены услуги.
4. **Price request к unavailable service:** ответ об **отсутствии услуги**, не «цена не указана»; запрещены сумма, price card, promo отсутствующей услуги, чужая цена без явной маркировки альтернативы.
5. **Price request к unavailable + alternatives:** not-offered + authored alternatives; цена альтернативы **только** как цена явно названной другой услуги с exact name, amount, currency, billing unit, package; **никогда** как цена исходной услуги.
6. **Named service exists, только family price:** запрещено «All-on-4 стоит от 35 000 ₽», price card All-on-4 с общей ценой имплантации, вычисление из компонентов. Family price допустима **только** при `commercial_intent=price` как отдельный контекстный текст при `applies_to_service_ids` + `approved_context` + exact amount/currency + patient-facing billing unit + явное «ориентир направления, не цена конкретной услуги». При `commercial_intent=none` / `payment` / `included` / `promotion` family amount **не** протекает.
7. **Unresolved service term:** **не** утверждать уверенно, что клиника не оказывает услугу; безопасная формулировка вроде «Не вижу такой услуги в перечне клиники. Возможно, она называется иначе — уточните название»; **без** случайной альтернативы или цены.

#### Взаимодействие со Stage 5.1 promotion contract

- unavailable service **не** получает priority promo;
- promo альтернативы **не** показывается автоматически в том же ответе, пока пациент явно не выбрал альтернативу и authoritative `service_id` не переключился;
- offered service с `no_public_price` **может** получить свою priority service promo по Stage 5.1;
- offered service с family-only price coverage и `commercial_intent=none` **может** получить priority service promo; family amount при этом **не** показывается;
- promo **не** создаёт отсутствующую base price; скидка **не** вычисляется от family price; family price + promo **не** создают рассчитанную сумму;
- availability/alternative/price-gap элементы собираются единым `PresentationResult`; commercial surfaces сохраняют `commercial_intent` / `promotion_scope` gates.

#### Performance / ownership (Stage 5.1B)

- **не** добавляет provider call;
- **не** добавляет classifier / marketing LLM / retry;
- **не** использует regex или keyword routing;
- работает локально после authoritative semantic result;
- входит в единый presentation pass;
- **не** ослабляет gates 8s / 10s / 6s.

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

Flash выбирает только один primary `scenario` из закрытого enum (§9). Flash **не** придумывает offer/fact/CTA и **не** пересказывает точные условия акции. Flash возвращает `commercial_intent` и `promotion_scope`; код решает, какая коммерческая поверхность допустима.

### 13.1 Priority service promo (первый ответ об услуге)

На первом допустимом содержательном `ANSWER` с authoritative non-null `service_id` и `commercial_intent=none`, `promotion_scope=none` бот обязан показать **ровно одну** первую active, применимую promo этой услуги:

- authority: client-authored **`priority_service_promos`** mapping `service_id → ordered_fact_refs` (§13.6); **нет** одной «главной акции клиники»;
- выбирается детерминированным кодом **после Flash**; первый eligible ref из списка **конкретной** услуги;
- promo другой услуги **не** подмешивается; consultation/installment **не** используются как fallback;
- текст, процент, срок и условия — **только** из authoritative client data; Flash не придумывает и не пересказывает;
- правило действует для первого допустимого ответа о конкретной услуге, а не только для «что это?» / «делаете ли вы?»;
- priority promo — **marketing fact**, **не** amplifier; входит в общий лимит **3** marketing facts, но **не** занимает лимит **2** amplifiers;
- при `commercial_intent=none` и `promotion_scope=none` — **единственное** bounded automatic commercial исключение (§9.1, §11); **не** открывает price amount, price/offer card, payment terms или included items;
- при `service_id=null` или отсутствии eligible promo автоматическая service promo **запрещена**;
- session-global suppression: один `fact_id` автоматически показывается **один раз** за `session_id`, даже если применим к нескольким услугам; новый session/reset очищает suppression; прямой promotion request может повторно открыть факт, если он active и applicable (§13.5).

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

### 13.5 Promotion request (`commercial_intent=promotion`)

| `promotion_scope` | Поведение |
|-------------------|-----------|
| `general` | До **3** active clinic-authored promo facts по `promotion_overview.ordered_fact_refs`; фильтр active dates и общей применимости; отсутствие promo → никакой выдуманной акции |
| `service` | Authoritative `service_id` обязателен; одна первая eligible promo из `priority_service_promos[service_id]`; promo других услуг **не** подмешиваются |
| `shown` | Повторяется последняя **фактически rendered** promo текущей session; только если active и applicable; suppression обходится; выбор по словам пользователя **не** выполняется; если session-bound promo отсутствует — fail closed |

`commercial_intent=promotion` **не** открывает price amount, price/offer card, payment terms или included items.

### 13.6 Client-owned promo authority (accepted schema)

Нормативная семантика — **service-id mapping**, не общий context block. Принятые имена полей:

```yaml
priority_service_promos:
  <service_id>:
    ordered_fact_refs:
      - fact:...

promotion_overview:
  ordered_fact_refs:
    - fact:...
```

- `priority_service_promos` управляет automatic first-service promo и `promotion_scope=service`;
- `promotion_overview` управляет **только** `promotion_scope=general`;
- оба списка содержат refs на authoritative facts; тексты и условия — в `facts.json`;
- один fact может присутствовать в service mapping и overview;
- `initial_commercial_blocks` **не** является promo authority Stage 5.1 (legacy compatibility data);
- **нет** одной «главной акции клиники»; service mapping и general overview — разные authorities;
- **нельзя** выбирать акцию по тексту, проценту, ID, regex или Python hardcode.

**Pack-load validation** (при загрузке client pack): service IDs; fact refs; `kind=promo` для priority mapping; duplicates; priority mapping applicability.

**Runtime eligibility** (post-Flash selector/presentation): active dates; current applicability; session-global suppression; `incompatible_with`.

### 13.7 Performance invariant (Stage 5.1)

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
| Commercial intent | closed enum §9.1 (`none` \| `price` \| `payment` \| `included` \| `promotion`); `promotion_scope` §9.3; каждый intent открывает только соответствующую поверхность; `payment` и `included` **не** открывают price surface; `promotion` **не** открывает price amount, price/offer card, payment terms или included items; `none` + `promotion_scope=none` не открывает price/payment/included/promotion, кроме bounded priority service promo §13.1 |
| Promotion | `commercial_intent=promotion` + closed `promotion_scope`; `general` → до 3 по `promotion_overview`; `service` → одна promo услуги по `priority_service_promos`; `shown` → последняя rendered promo session (fail closed без session-bound promo); arbitrary promo guessing запрещён; `CLARIFY`/`ADMIN` не открывают promotion surface |
| Marketing | лимит 3/2; priority promo в **3**, не в **2**; первый eligible service turn с `service_id` обязан показать одну priority promo по service-id mapping; session-global suppression по `fact_id`; CTA и navigation slots отдельны; shown-state только после render; price follow-up always shown |
| Service availability / price gaps (Stage 5.1B) | три оси availability / price coverage / alternative authority §11.1; price precedence; not-offered / unresolved / no_public_price / family-context / alternative-price labelling; no invented/computed amount; no promo leakage from unavailable service; `0/1` calls |
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

## 17. Current known gaps (post Stage 5.2 baseline)

Проверяемые расхождения **после** принятого Stage 5.2 baseline (`984ab65`). Ниже — только **оставшиеся** material gaps; закрытые Stage 4.1–5.2 перечислены отдельно с commit mapping.

### 17.1 Оставшиеся material gaps

1. **Survivability answer overload/quality gap:** нейтральный вопрос о приживаемости имплантов после корректного факта 99,8% может получить нерелевантные сведения о птеригоидных имплантах, консультации, гарантии и цене. Informational 99,8% sanitizer regression **протестирован** в Stage 5.1 — это **не** закрывает overload/quality gap.

### 17.2 Закрыто принятыми Stage 4.1–5.2 (не перечислять как gaps)

| Gap | Закрыт этапом | Evidence |
|-----|---------------|----------|
| Dual prompt protocol (`@ANSWER` сосуществует с typed envelope) | Stage 4.2 | `b833482e1cf6f00637fbfa7525df5d29e5f79a57` |
| Windows logging / SSE diagnostics path | Stage 4.1 | `1d89190ea0bb334e57fe782f8f121458fa3c329e` |
| Specific contact question возвращает весь contacts payload | Stage 4.3 | `6345b37eec2807bc2008e68f8a01018407af044f` |
| APRF / биоматериал → лишний `CLARIFY` или цена | Stage 4.3 | `6345b37eec2807bc2008e68f8a01018407af044f` |
| Generic topic narrowing до brand / technology / offer | Stage 4.3 | `6345b37eec2807bc2008e68f8a01018407af044f` |
| Price without подтверждённого `commercial_intent` | Stage 4.3 | `6345b37eec2807bc2008e68f8a01018407af044f` |
| Marketing overload / unified `PresentationResult` / promotion intent | Stage 5.1 | `a2688781d43534605664a3d11217c51dd1576d1c` |
| `commercial_intent=promotion`, `promotion_scope`, `priority_service_promos`, `promotion_overview` | Stage 5.1 | `a2688781d43534605664a3d11217c51dd1576d1c` |
| Session-global suppression, rendered promo state, `last_rendered_promo_fact_id` | Stage 5.1 | `a2688781d43534605664a3d11217c51dd1576d1c` |
| Price-follow-up shown-state | Stage 5.1 | `a2688781d43534605664a3d11217c51dd1576d1c` |
| Service availability / alternatives / price gaps | Stage 5.1B | `51621af40c873c728f3f5bc01141dc8d2440a6ce` |
| Widget/SSE terminal idempotency (parser + widget finalize-once; duplicate `ui`/`done`; live→final replacement; safe EOF/reader-error after accepted UI) | Stage 5.2 | `490bdbb0f1b456eb5d2fe0d7689bcfe90244b739` |
| Stage 5.2 test line-ending normalization (LF-only committed blobs) | Stage 5.2 cleanup | `984ab65a5a653576b065b692043d07a6d5daaee7` |

### 17.3 Informational / historical (не material gaps)

1. **Historical «Отбеливание» double-response incident:** root cause остаётся **`NOT PROVEN`**. Production-faithful offline Chrome harness: normal и partial whitening scenarios дают **один** bot bubble. Generic terminal-idempotency vulnerability (duplicate `ui`/`done`, missing finalize after accepted UI) **доказана и исправлена** в Stage 5.2. При повторении исторического инцидента использовать существующую PII-free SSE diagnostics для корреляции server event counts (`ui≤1`, `done≤1`) и DOM behavior. **Не** утверждать, что historical whitening root cause найден или что сервер отправлял duplicate terminal events.
2. **I1 (informational, non-blocking):** `reader.read()` с одновременными `value` и `done:true` — pre-existing low-risk seam; Stage 5.2 не менял этот transport edge.
3. **I2 (informational, non-blocking):** отдельный harness E7→next normal turn не входил в принятый Stage 5.2 scope; pending guard E8 задокументирован отдельно.

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

### Stage 5.1 — Единый marketing/commercial `PresentationResult` (**принят**, `a268878`)

**Принятый результат (offline Checker bundle 247 tests, `provider_calls ∈ {0, 1}`):**

- envelope v3: `commercial_intent` (`none` \| `price` \| `payment` \| `included` \| `promotion`) + closed `promotion_scope` (`none` \| `general` \| `service` \| `shown`);
- prompt contract / cache identity **p3**;
- typed `OneCallPresentationResult` и **один** post-Flash presentation pass;
- deterministic promotion authority/selector: `priority_service_promos`, `promotion_overview`, automatic/general/service/shown paths;
- authoritative promo text rendering; commercial-claim vs informational-percent firewall;
- limits **3/2**; CTA/secondary separation;
- render-proven shown-state; session `last_rendered_promo_fact_id`; price-follow-up shown-state fix;
- commerce/promotion fail-closed gates;
- **0/1** provider calls; absolute gates §15.2 не ослаблены.

Evidence: `a2688781d43534605664a3d11217c51dd1576d1c`.

### Stage 5.1B — Service availability, authored alternatives and price gaps (**принят**, `51621af`)

**Принятый результат (offline Checker bundle 313 tests, `provider_calls ∈ {0, 1}`):**

- envelope/prompt contract **v4**, prefix cache identity **p4**;
- authoritative `service_reference`: `service_reference_status`, `requested_service_id`; `service_id` — active offered service only;
- три состояния availability: `offered` / `known_not_offered` / `unresolved`;
- unavailable/unresolved **не** используют свободный model patient body;
- canonical ID-based authored alternatives в `clinic_policies.yaml` (`requested_service_id`, `alternative_service_ids`, `approved_text`);
- максимум **2** alternatives в clinic-authored order; labels из records альтернативных услуг;
- cross-client references fail closed; UI service actions (`target:ui_service/{service_id}`) с session-bound `client_id`;
- price precedence: exact offer → `no_public_price` → family context (только при `commercial_intent=price`) → data-gap;
- family context: amount/range + currency + patient-facing billing unit + disclaimer; **не** exact service price; **не** price/offer card; **не** discount computation;
- intent gating family price surface: открывается только при `commercial_intent=price`; при `none` / `payment` / `included` / `promotion` family amount **не** протекает;
- unavailable service **не** получает promo; offered service + family-only coverage + `commercial_intent=none` сохраняет одну priority service promo;
- **0/1** provider calls; без keyword/regex service classifier; без второго LLM call.

Evidence: `51621af40c873c728f3f5bc01141dc8d2440a6ce`.

**Дополнительное E2E coverage (не production defect):** two-alternative full-widget E2E покрыт lower-level regression (slot builder + single-alternative widget path); отдельный full-widget E2E с двумя alternatives — optional future coverage, не незавершённая Stage 5.1B архитектура.

**Historical compatibility:** legacy `match_keywords` rows в `clinic_policies.yaml` остаются для `SALES_ONE_PLUS_ON=OFF` path; current ONE_CALL owner — canonical ID-based rows only.

### Stage 5.2 — Widget / SSE terminal idempotency (принят)

**Evidence:** implementation `490bdbb0f1b456eb5d2fe0d7689bcfe90244b739`; test line-ending cleanup `984ab65a5a653576b065b692043d07a6d5daaee7`.

**Parser (`static/widget/api.js`):** per-`streamAsk()` state; первый valid `ui` (`answer` или `meta`) — authoritative final payload; invalid/malformed `ui` не занимает slot; duplicate/late `ui` игнорируется; `onUi`/`onDone` максимум один раз; duplicate `done` игнорируется; EOF после accepted UI безопасно завершает turn; reader/network error после accepted UI вызывает `finalizeOnce()` без второго error lifecycle; transport error до UI — обычный error path; JSON fallback — тот же exactly-once lifecycle.

**Widget (`static/widget/widget.js`):** один user turn → максимум один final bot message; один `state.messages.push`, один terminal `renderFeed`, один `endPendingRequest`; live `text_delta` bubble временный; final UI заменяет live bubble одним state-backed bubble; streamed-only fallback один раз; duplicate terminal events идемпотентны; поздние delta/ui/done/error не меняют final answer; guards одного stream не протекают в следующий turn; control metadata пациенту не показывается.

**Scope (не менялось):** server SSE schema/order; `app.py` diagnostics; provider budget **0/1**; Stage 5.1/5.1B semantic/commercial contracts; `SALES_ONE_PLUS_ON` default OFF; speed gates 8s/10s/6s; whitening-specific regex/branch не добавлялись.

**Offline evidence (не LIVE/frozen E2E):** production-faithful Chrome/CDP harness (`tests/js/stage52_widget_sse_harness.mjs`); targeted **29 passed ×2**; Checker regression **218 passed, 1 skipped**; provider/external network attempts **0**.

**Historical whitening:** incident **не воспроизведён** offline; root cause **`NOT PROVEN`** (см. §17.3).

### Stage 5.3 — Frozen multiclient E2E (не начат)

- услуги, свободные формулировки, цены и scopes;
- **обязательная frozen matrix Stage 5.1B:** `offered` / `known_not_offered` / `unresolved`; not-offered без alternatives; not-offered с 1–2 alternatives; price request к unavailable service; exact `no_public_price`; exact service + explicitly applicable family context; exact service + non-applicable family price; alternative price clearly labelled; no promo leakage from unavailable/alternative service; no invented/computed amount; client isolation;
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

> **Исторический checklist.** Не является текущим acceptance gate. Актуальный baseline — Stage 5.1B (`51621af`).

| Разрешено | Запрещено |
|-----------|-----------|
| `docs/ONE_CALL_CACHED_FULLCONTEXT_ARCHITECTURE_LOCK.md` (MODIFY) | Код, тесты, `TASK.md`, env, другие docs |
| | Alibaba LIVE / provider calls |
| | Commit без явной команды владельца |

**Критерии повторного review (Stage 4.0):**

- [ ] Изменён **ровно один** docs-файл; нет кода и тестовых изменений; нет LIVE; нет commit.
- [ ] Current implementation status: Stage 0–2 приняты; Stage 3A/3B/3C приняты; clinic-owned price + authoritative commerce приняты; `SALES_ONE_PLUS_ON` default OFF; Alibaba LIVE запрещён после Stage 4.0.
- [ ] Неизменяемая архитектурная основа §1 сохранена без ослабления.
- [ ] §9 — closed envelope incl. `commercial_intent` (`none` \| `price` \| `payment` \| `included` \| `promotion`); `promotion_scope` (`none` \| `general` \| `service` \| `shown`); `scenario` enum; uppercase `route`.
- [ ] §9.1, §9.3, §11, §13, §14 — согласованная семантика `commercial_intent` и `promotion_scope`.
- [ ] §4, §10 — `service_id=null`, semantic ownership, bare service без обязательного `CLARIFY`.
- [ ] §11 — `COMMERCIAL_RENDER_CONTRACT` + clinic-owned authoritative commerce result.
- [ ] §6 — FullContext vs selected context; cache key §6.3; Stage 3A accepted noted.
- [ ] §3 — active runtime до/при flag ON/после Stage 6.
- [ ] §15.2 — абсолютные gates (8s / 10s / 6s); superseded relative-only activation; diagnostic-only legacy comparison allowed.
- [ ] §17 — актуальные gaps; принятые Stage 0–3 **не** перечислены как незакрытые; будущие Stage 4.1+ **не** названы исправленными.
- [ ] §19 — frozen roadmap Stage 4.0, 4.1, 4.2, 4.3, 5.1, 5.1B, 5.2, 5.3, 5.4, 6 раздельно.
- [ ] Supersession `ARCH_TARGET_DESIGN.md` и ANSWER/ADMIN граница сохранены.
- [ ] §9.2 — structured output; Stage 3B accepted; `@ANSWER` не целевой transport.
- [ ] §8 — typed UI не интерпретируется моделью; 0-call contacts/booking/urgent.
