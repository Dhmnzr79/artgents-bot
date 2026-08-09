# ONE_CALL_CACHED_FULLCONTEXT — Architecture Lock

**Статус:** нормативный TARGET-контракт (Stage 0, docs-only).  
**Дата:** 2026-08-09.  
**Модель:** `qwen3.7-flash-2026-07-15`.

Этот документ фиксирует **целевую** архитектуру продукта. Это не описание текущей реализации. Фактические расхождения Stage 8 перечислены в §16 как **gaps**; их закрытие — отдельные этапы roadmap §19.

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

**До активации (текущее состояние):**

- legacy runtime (Planner + Boundary + Composer + Verifier) является **рабочим control**;
- candidate path (`SALES_ONE_PLUS_ON`) **выключен** по умолчанию;
- существуют **два** runtime-пути; это gap, не целевое состояние.

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
- семантического выбора услуги.

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
- typed UI **не** обходит candidate path при flag ON (gap §16 — пока может).

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
| `clarify_axis` | `service` \| `extent` \| `jaw` \| `stage` \| `null` |
| clarify service options | максимум 3 `service_id` из активного client pack |
| patient answer text | narrative для пациента (без коммерческих значений — см. §11) |

Невалидное значение любого closed-field → invalid envelope → neutral presentation или safe handoff по route, **не** повторный вызов.

### 9.1 Structured output transport

**Не утверждается**, что официальный JSON Schema / function calling уже поддержан `qwen3.7-flash-2026-07-15`.

Зафиксировано:

- **предпочтителен** provider-supported schema-constrained output;
- **сначала** capability test на точном snapshot модели;
- если не поддержан — versioned typed envelope с **единым** blocking/streaming parser;
- старый хрупкий `@ANSWER` line protocol **не является** целевым контрактом;
- control должен завершиться **до** streaming patient text;
- medical/route protocol не должен утекать пациенту.

---

## 10. CLARIFY

**Разрешённые `clarify_axis`:** `service`, `extent`, `jaw`, `stage` (см. §9).

Только **2–3** client-authored UI options (`service_id` из активного pack).

**Запрещены** медицинские уточнения: симптомы, диагноз, анамнез, противопоказания, выбор лечения, дозировки.

Medical/problematic request → `ADMIN`, без диалога.

---

## 11. COMMERCIAL_RENDER_CONTRACT

**Единственный нормативный механизм** коммерческих данных в widget — `COMMERCIAL_RENDER_CONTRACT`.

Он означает:

1. Модель **не является** источником цен, скидок, рассрочки и коммерческой гарантии.
2. Модель возвращает narrative **без** таких коммерческих значений.
3. Код **после** ответа выбирает validated offer/fact по `service_id`, `extent`, `jaw` и scope.
4. Текстовый коммерческий блок, карточка, CTA и кнопки строятся из **одного и того же** validated result.
5. **Невозможна** ситуация, когда текст показывает одну цену, а карточка — другую.
6. Если подтверждённого offer нет — сумма **не показывается** и **не вычисляется**.
7. Медицинские и некоммерческие числа из утверждённого MD **не запрещаются**.

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
- не `ADMIN`.

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

Flash выбирает только `scenario` из закрытого enum (§9). Flash **не** придумывает offer/fact/CTA.

**Deterministic presentation** (через `COMMERCIAL_RENDER_CONTRACT` и marketing layer):

- выбирает только active client-authored service-linked facts;
- добавляет выбранный fact в patient text;
- не дублирует уже показанное;
- direct request обходит suppression;
- shown-state записывается только после фактического render;
- сохраняет follow-up;
- сохраняет два button slots;
- сохраняет CTA;
- neutral/general запрос не получает случайный implantation marketing;
- marketing supplement и offer card **не** меняют presentation независимо друг от друга (gap §16 — пока могут).

---

## 14. Activation quality gates

До включения обязательны frozen E2E matrices:

| Область | Критерий |
|---------|----------|
| Medical/problematic | 0 false `ANSWER` на protected cases (§ ANSWER/ADMIN) |
| Sales fears | 0 false `ADMIN` на protected fear cases |
| Price | `COMMERCIAL_RENDER_CONTRACT`: один validated result; 0 invented/computed amounts; ambiguous scope без суммы |
| Microfacts | вопросы по всему MD-корпусу, включая неизвестные заранее темы |
| Multiclient | минимум два client packs; отсутствие cross-client data leakage |
| Calls | `provider_calls` 0 или 1 на всём HTTP-запросе |
| Streaming | control metadata не показывается пользователю; один provider call; корректный final widget; production-faithful SSE |

---

## 15. Performance contract

### 15.1 Измерять

- patient TTFT p50/p95;
- total p50/p95;
- prompt/completion/cached tokens;
- cache hit rate;
- provider call count.

### 15.2 Activation performance gate

**Не задаются** неподтверждённые абсолютные секунды до калибровки.

Измеримый gate для activation:

1. Один и тот же frozen production-faithful corpus и case matrix.
2. Сравнение нового пути с frozen legacy baseline.
3. Новый путь: **не менее 20%** улучшения patient TTFT p50.
4. patient TTFT p95 и total p95 **не должны ухудшиться**.
5. quality / protected / medical gates (§14) — без послабления.
6. Отдельно фиксируются cache hit/miss.
7. При cache miss SLO оценивается **отдельно**.
8. Численные абсолютные SLO могут быть добавлены **только** после Stage 3 calibration и owner approval.
9. **Без** выполнения п. 1–8 activation **запрещена**.

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
- clinic-specific regex;
- разговорный словарь всех пользовательских формулировок;
- вычисление цен моделью;
- `@ANSWER` line protocol как целевой transport;
- старая `medical_handoff`-семантика с содержательным ответом перед handoff.

---

## 17. Current known gaps (Stage 8)

Фактические расхождения текущего Stage 8 и dual-runtime состояния. **Не исправлены** этим документом:

1. **Ingress classifier может вызвать LLM** (`pre_resolver` / ingress path).
2. **Затем sales-fast path вызывает Flash** — при flag ON на одном HTTP-запросе возможно **2 provider calls**.
3. **Speculative Planner** может запуститься до выбора нового пути.
4. **Существуют два runtime-пути:** legacy (Planner + Boundary + Composer + Verifier) и candidate (sales-fast); legacy — рабочий control по умолчанию.
5. **Typed UI** пока может обходить candidate и уходить в старый FullContext path.
6. **Problem Gate** расположен не абсолютным первым шагом после ingress.
7. **Scope/aspect/service recognition** частично зависит от regex и catalog aliases; слабый catalog match может стать authoritative `service_id`; unknown topic defaults to implantation.
8. **Marketing supplement и offer card** могут независимо менять presentation.
9. **Model narrative и offer card** могут показать разные цены (нарушение `COMMERCIAL_RENDER_CONTRACT`).
10. **Cache prefix** построен не оптимально; prompt order мешает full-corpus prefix caching; provider-call governance считает не весь HTTP request.
11. **Official structured-output support** для `qwen3.7-flash-2026-07-15` не доказан.
12. **Production-faithful SSE/streaming** и полный marketing parity ещё не доказаны checker.
13. **Multiclient E2E** ещё не приняты checker.

---

## 18. Change control

Architecture Lock изменяется только:

- отдельным review;
- с перечислением trade-offs;
- после явного согласования владельца продукта.

Обычная реализация **не может** молча менять архитектуру.

---

## 19. Implementation roadmap (Stage 1–6)

Roadmap закрывает gaps §17. **Gaps не считаются исправленными**, пока этап не принят checker.

### Stage 0 — Architecture Lock (этот документ)

- Нормативный TARGET-контракт; supersession § в шапке.
- Gaps перечислены; код не меняется.

### Stage 1 — Governance + provider-call accounting

- HTTP-scoped `provider_calls` на весь запрос; запрет 2-call сценария (gaps 1–2).
- Import/wiring ban legacy LLM на active path при flag ON.
- Observability без patient text.

### Stage 2 — Ingress reorder + Problem Gate first + typed UI

- Gate — абсолютный первый этап; убрать ingress LLM и speculative Planner (gaps 3, 6).
- Typed UI только в candidate path (gaps 4–5).

### Stage 3 — Cached FullContext prefix + Flash capability

- Cache key §6.3; оптимальный prefix order (gap 10).
- Capability test structured output; единый parser (gap 11).
- Stage 3 calibration → owner approval для абсолютных SLO (§15.2).

### Stage 4 — Control ownership + COMMERCIAL_RENDER_CONTRACT

- Closed envelope §9; catalog validation (gap 7).
- Единый validated result для text + card (gaps 8–9).

### Stage 5 — Marketing + streaming + multiclient E2E

- Production-faithful SSE; marketing parity (gap 12).
- Multiclient matrix (gap 13).

### Stage 6 — Activation + legacy removal

- §14–§15 gates; single runtime (§3).
- Legacy недоступен для production routing.

---

## Checker scoped allowlist (Stage 0 revision)

| Разрешено | Запрещено |
|-----------|-----------|
| `docs/ONE_CALL_CACHED_FULLCONTEXT_ARCHITECTURE_LOCK.md` (MODIFY) | Код, тесты, `TASK.md`, env, другие docs |
| | Alibaba / LIVE |
| | Коммит без явной команды владельца |

**Критерии повторного review:**

- [ ] Supersession `ARCH_TARGET_DESIGN.md` и новая ANSWER/ADMIN граница (без blanket medical → ADMIN; без старого medical_handoff content-before-handoff).
- [ ] §17 — полный перечень Stage 8 gaps, без «исправлено».
- [ ] §9 — closed envelope; `scenario` enum; uppercase `route`.
- [ ] §11 — `COMMERCIAL_RENDER_CONTRACT`.
- [ ] §6 — FullContext vs selected context; cache key §6.3.
- [ ] §3 — active runtime до/при flag ON/после Stage 6.
- [ ] §15.2 — измеримый performance gate без неподтверждённых абсолютных секунд.
- [ ] §9.1 — structured output без утверждения уже поддержанного JSON Schema.
- [ ] §8 — typed UI не интерпретируется моделью; 0-call contacts/booking/urgent.
- [ ] Изменён **ровно один** docs-файл.
