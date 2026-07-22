# ARCH_TARGET_DESIGN — целевая архитектура (v4)

**Статус:** v4, обновлено 2026-07-12 после трёх раундов независимой рецензии. Заменяет v1–v3.
**Честно:** ранние версии выдавали переходную форму за целевую и содержали внутренние противоречия. Исправлено. Помечено **TARGET** vs **СЕЙЧАС**. Историческая опора: [`archive/ARCH_RECON_REPORT.md`](archive/ARCH_RECON_REPORT.md).

---

## Цель №0 — мета-цель (над всем)

> **Меньше сущностей.** **Composer отвечает по умолчанию** (режим evidence — по риску и уверенности TurnFrame). Отдельная механика допустима **только по трём причинам: безопасность · необратимые действия · точные внешние контракты** — и только как **тонкий гард**, не как маршрут.

Примеры по причинам:
- **безопасность:** медзона, hard-stop;
- **необратимые действия:** booking, **создание/отправка лида**;
- **точные внешние контракты:** цена из pricebook, числа/факты из базы, **контакты клиники (адрес/сбор данных)**.

Тон и промо — надстройки по тем же правилам. 🚩 Новый гейт/классификатор/обработчик под **тему** (а не под одну из трёх причин) = скат назад.

## Owner law: FINAL_FULLCONTEXT_ONLY

**Статус:** явное architecture decision владельца (2026). Бот **не в production**; живых клиентов и
обязательства сохранять текущие legacy-ответы или widget compatibility **нет**. Цель — сразу
чистая **финальная** cached FullContext-архитектура для базы порядка **150–200 небольших MD**.
Временные response paths «на потом удалим» **не строим**.

### Смысл закона

1. **Финальный Composer** получает **весь валидированный MD-корпус клиента** через **cached FullContext**.
2. **Scoped turn-specific primary evidence** (S35→S36) **дополняет** FullContext: усиливает и
   проверяет exact facts, strict commercial facts, offer/doctor identities и grounding. Оно **не
   заменяет** FullContext, **не скрывает** остальную MD-базу от Composer и **не является**
   обязательным retriever-gate для обычных знаний.
3. **Structured selectors** разрешены там, где нужна строгая точность и управление: услуги, цены
   и этапы оплаты, врачи, marketing facts и CTA, safety policy, source provenance и verification.
4. **`medical_handoff`** выбирает **режим безопасности**, а не отдельный MD-маршрут. Модель по-
   прежнему видит **всю MD-базу**, но не может ставить диагноз, определять личную пригодность или
   выбирать лечение.
5. **`used_doc_ids` / source refs** — для аудита, follow-up и grounding verification, **не** как
   предварительный RAG-router.

### Запрещено по умолчанию

- маршрутизация ответа по **отдельным MD** или тематическим document routers;
- **vector retrieval**, **chunk retrieval** и любой retriever-gate перед Composer для обычных знаний;
- **временные product response paths** и legacy fallback ради сохранения текущих ответов;
- **shadow/runtime wiring**, создаваемый только как промежуточный мост без постоянной роли в
  финальной цепочке;
- **дублирование FullContext** отдельными таблицами тематических маршрутов или `(topic,aspect)`-
  prompt tables как альтернативным источником знаний.

### Исключения

Любое исключение требует: **отдельного явного разрешения владельца**; доказательства, что
механизм нужен именно **финальной** рабочей цепочке; описания его **постоянной** роли;
объяснения, почему cached FullContext недостаточен.

Если клиентская база **перестанет помещаться** в выбранный cached context — **СТОП** на
отдельное architecture decision. **Нельзя** молча добавлять RAG/retriever.

**Eval harness и offline checker** допустимы как измерительные инструменты, если они **не**
становятся временным product response path.

### Согласование с более ранними формулировками

- Пункт «Evidence assembly — primary evidence тематически ограничен, полная база только фон» ниже
  описывал **переходную** модель до этого решения. Под **FINAL_FULLCONTEXT_ONLY** финальный
  Composer **всегда** видит cached FullContext целиком; scoped primary evidence — **надстройка
  для точности и verifier**, не замена корпуса.
- Offline S35/S36 **не противоречат** этому закону: они materialize **selected strict identities**
  для verification и exact-fact enforcement, **не** подменяя cached FullContext как основной
  knowledge input Composer.
- Текущий legacy path, chunk_responder и retrieval в repo — **СЕЙЧАС**, не TARGET; не оправдание
  для новых temporary bridges.

## Owner clarification: Medical question semantics

**Статус:** уточнение существующей архитектуры владельца (2026). **Не** новый параллельный
механизм. Дополняет **FINAL_FULLCONTEXT_ONLY** и не отменяет urgent/manual-contact hard-stop.

### Порядок и приоритеты

1. **Срочные обращения** — существующий **urgent / manual-contact hard-stop** **раньше**
   обычного ответа, TurnFrame, medical_handoff и Composer: связаться с администратором; при
   срочности лучше **звонить**. Текущая личная боль, активное осложнение и жалоба — **не**
   medical_handoff-content path.
2. **Общие медицинские вопросы без текущей личной боли** — `response_mode=medical_handoff`
   (**режим безопасности**, не MD-маршрут). Модель видит **cached FullContext всего корпуса**.

### Смысл `medical_handoff` (не отказ от ответа)

`medical_handoff` **не означает** автоматический отказ от ответа.

Если медицинская тема **есть** в согласованных MD клиники, бот **может** дать **общий,
нейтральный** ответ:

- **только** на основании материалов клиники (FullContext + scoped primary evidence для
  verifier);
- **без** диагноза и differential;
- **без** вывода, подходит ли лечение конкретному человеку;
- **без** самостоятельного выбора лечения за врача;
- в конце допустимо пригласить на консультацию (если policy разрешает).

Если болезнь или тема **отсутствуют** во всей утверждённой MD-базе:

- **controlled materialized response** (это **не** terminal defer);
- бот **честно** сообщает, что в материалах клиники такой информации нет;
- предлагает уточнить на консультации;
- **не** дополняет ответ медицинскими знаниями модели.

### Boundary outcomes (S42) vs materialization

| Outcome | Смысл | Product path |
|---|---|---|
| `none` | коммерческий/информационный ход без medical safety mode | materialize по policy |
| `medical_handoff` (confident) | medical safety mode; ответ **materialize**, не terminal defer | **materialize** с `response_mode=medical_handoff`: grounded content из clinic MD **или** controlled «нет в материалах клиники» + консультация |
| `uncertain` | низкая уверенность / malformed / ambiguity | **только** terminal **defer** (fail-closed) |

**Только `uncertain`** означает terminal defer. Confident `medical_handoff` **всегда
materializable** (не terminal defer):

- **тема есть в базе** — grounded neutral ответ из clinic MD + допустимое приглашение на
  консультацию;
- **темы нет во всей clinic MD-base** — controlled materialized response: «в материалах
  клиники такой информации нет» + предложение консультации; **запрещено** дополнять model
  medical knowledge.

S42/S43 **проверяют классификацию границы**; финальное медицинское содержание ответа,
FullContext integration и Verifier enforcement — **отдельные** downstream gates (ещё не product).

**S41 offline (СЕЙЧАС):** materialize при confident `medical_handoff` возможен, когда
`service_id` usable; иначе — terminal `medical_handoff_nonmaterializable` без Composer. Это
**offline wiring gap**, не финальная product-семантика: TARGET — FullContext Composer path с
safety mode независимо от узкого `service_id` gate.

### Verifier (TARGET) для медицинского ответа

Verifier будущего медицинского ответа обязан проверять:

- **при наличии темы в базе:** grounding / provenance в clinic MD; соответствие нужному
  **семейству услуг** (service/topic scope), не per-MD routing;
- **при отсутствии темы во всей базе:** controlled materialized «в материалах клиники такой
  информации нет» + предложение консультации — **не** terminal defer; **без** model medical
  knowledge;
- отсутствие диагноза и differential;
- отсутствие персонального вывода о пригодности пациента;
- отсутствие самостоятельного выбора лечения.

Offline S38 уже закладывает semantic assessment по medical boundary и selected facts; полный
checklist выше — **TARGET** для финальной medical-handoff verification.

### Организация контента: противопоказания (не routing)

Противопоказания предпочтительно хранить по **клинически различающимся семействам** топ-услуг:

- отдельный MD для семейства **имплантации**; общий документ для классической имплантации,
  All-on-4/All-on-6, если содержание **действительно общее**;
- отдельный — для **протезирования**;
- отдельный — для **виниров**, если клиническое содержание **действительно отличается**.

Это **организация client pack**, не runtime routing и **не** требование MD на каждую
микроуслугу. Composer по-прежнему получает **весь корпус** через cached FullContext.

---

## Цели → где живут

| Цель | Где |
|---|---|
| Точные ответы по базе | Composer + дословность |
| Эмпатичные/продающие по конверсии | Политика: флажок `emotion` → тон + фокус (надстройка, НЕ маршрут) |
| Даже если понимание не сработало — хороший ответ по базе | Сквозной закон: сбой → безопасный дефолт, уважающий жёсткие сигналы |
| Цена (бренды/зуб/челюсть) | Boundary: детерминированный ценовой слой (pricebook) |
| Маркетинг (акции) | Политика-надстройка (промо-гейт) |
| Не диагностировать/не выдумывать | Медзона boundary + числовой Verifier + дословность |
| Точные факты и цифры | Verifier (числа) |
| Контекст, уточняющие | TurnFrame: оси specificity/follow-up + история |

---

## Целевая цепочка (TARGET)

```
Boundary detection → TurnFrame → Boundary enforcement + Response policy → Evidence assembly → Composer → Verifier
```

1. **Boundary detection** — дешёвая ранняя детекция. **Полностью коротко замыкают до TurnFrame только** hard-stop, contacts, однозначный booking. **Цена и медзона здесь только детектятся** и ставят **обязательный флаг, который LLM не может отменить** — услугу/объём/форму часто видно лишь после TurnFrame.
2. **TurnFrame** — **один логический контракт**: `topic`, `intent`, **`aspects[]` + `primary_aspect`**, `emotion`, `specificity`, `patient_scope`, **`service_id`**, `follow_up` + **confidence/provenance по каждому полю**. Один контракт ≠ обязательно один физический вызов; для серой зоны допустим узкий доп-resolver. (Составные вопросы — через `aspects[]`, без обходного слоя.)
3. **Boundary enforcement + Response policy** — применяет обязательные флаги (цена→детерминированная price policy, медзона→`response_mode=medical_handoff`) и формирует **декларативный `ResponseSpec`**: тон, `allowed_topics`, `forbidden_topics`, обязательные факты, hand-off?, допустимые deterministic cards. **НЕ таблица тематических промптов.**
4. **Evidence assembly** — под **FINAL_FULLCONTEXT_ONLY** (см. выше): **cached FullContext всего
   валидированного MD-корпуса** — основной knowledge input финального Composer. **Scoped primary
   evidence** для хода **дополняет** FullContext: selected strict identities, exact facts,
   offers/doctors/commercial facts для verifier и grounding — **не заменяет** корпус и **не**
   скрывает остальную базу. Structured selectors (услуги, pricebook, doctors, marketing, policy)
   управляют точными данными и safety; они **не** являются thematic document routers.
   - **Fail-safe:** низкая уверенность в **boundary** → только **`uncertain` → terminal defer**
     (S42); низкая уверенность в policy/turn understanding → clarify/defer по policy.
     Confident `medical_handoff` **не** равен terminal defer. **Запрещено** молча подменять
     FullContext chunk-retrieval или «только один MD» как product path.
   - *(Переходная формулировка v4 до owner decision: «primary evidence тематически ограничен,
     полная база только фон» — **снята** для финальной цепочки.)*
5. **Composer** — только формулирует по spec + evidence.
6. **Verifier** — числа, медзона-граница, тема, запрещённые/обязательные факты; для
   `medical_handoff` — grounding в базе, service-family scope, no-diagnosis, no personal
   eligibility, no treatment choice, honest «нет в материалах клиники» при отсутствии темы
   (см. § Medical question semantics).
   - **Первый target-рантайм:** deterministic digit-number provenance + одна компактная
     semantic assessment на каждый ответ. Accuracy-first решение владельца закрывает
     numbers-as-words, grounding, topic/medzone и selected facts до накопления live-данных.
   - **Будущая оптимизация:** high-risk/sampling вместо каждого semantic check допустимы
     только отдельным governance-решением после измерений качества, задержки и стоимости.

## Сквозные законы

- **Нет тихих fail-open, меняющих смысл** (включая слой evidence — см. его fail-safe). Сбой → безопасный дефолт, **уважающий жёсткие сигналы** (цена/contacts/booking/медзона). Лог **`degraded`**, не `ok`.
- **Field-level валидация:** битое необязательное поле → `field_errors`, не крашит весь план.
- **База — истина**, дословность, числовой Verifier.

---

## Что СЕЙЧАС (переходное — честно)

- Понимание **размазано**: planner + resolver + patient_situation + dialog_focus + aspect_planner + regex-гейты.
- `topic` — **не ось**, выводится после planner из `service_id` + regex в адаптере; `ServiceTopic` без `whitening`.
- `emotion_policy` — **таблица** `(topic,aspect)→инструкция` (риск тематических маршрутов).
- Медзона — **поздний** soft-suppress в композере, не boundary; hand-off не гарантирован.
- Eval — **маршрутный, не семантический** → ложное зелёное на протечке.
- Safe-default — слишком общий, логируется как `ok`.
- Композеру отдаётся **вся база без выделенного evidence** → он сам выбирает факты (источник протечек).

## A0 — зафиксированный baseline и target contract

A0 не является задачей «сначала сделать legacy зелёным». Бот не находится в production, поэтому нет продуктовой причины временно ремонтировать удаляемую маршрутизацию.

- frozen suite `preservation` фиксирует **желаемое продуктовое поведение**, а не старую реализацию и не дословные ответы;
- live baseline на старой архитектуре: `3/6`, существующий `smoke`: `24/24`;
- уже зелёные кейсы — защита от регрессии во время strangler-миграции;
- красные кейсы — известный архитектурный долг и target для нового backbone;
- frozen ожидания нельзя ослаблять ради зелёного legacy baseline;
- отдельные ремонты старых router/resolver/composer допустимы только при самостоятельной продуктовой необходимости, но не как предусловие удаления legacy.

Целевой `6/6` должен быть достигнут по мере подключения `TurnFrame → ResponseSpec → scoped evidence → Composer → Verifier`. Формулировка ответа может меняться; сохраняются факты, границы, provenance, деньги и нужный пользователю UI-контракт.

## Текущий strangler-checkpoint

Канонический актуальный статус A-series (чекбоксы A1–A9, последний/следующий checkpoint, authority) — **только** в [`docs/STRANGLER_ROADMAP.md`](STRANGLER_ROADMAP.md). Этот файл на текущий checkpoint не дублирует.

Переход ownership на `TurnFrame` разрешён только отдельными последующими задачами после проверки telemetry; сам факт появления frame в ctx не означает переключение архитектуры.

### Offline S28 downstream boundary

S28 не реализует и не переопределяет канонический `ResponseSpec` из шага 3 target
цепочки. Настоящий ResponsePolicy/ResponseSpec остаётся **до** evidence assembly и будет
владеть tone, allowed/forbidden topics, required facts, handoff и допустимыми
deterministic cards.

Отдельный S28 `TargetResponseMaterializationPlan` находится **после** проверенной S27
offline assembly. Он только проецирует identity уже выбранных материалов для будущего
materializer: exact content ref, projected offer IDs, linked doctor IDs и уже выбранные
marketing/consultation/CTA identities. Missing required component отмечается явно без
fallback; S28 не решает clarify/defer, не читает MD/followups, не формирует текст и не
подключён к product path. Такое разделение не меняет порядок target chain и не создаёт
второго смысла для имени `ResponseSpec`.

S29 materializes follow-up candidates только из уже выбранных S28/S27 sources. Content
candidates берутся из `suggest_h3` одного selected MD и разрешаются в explicit H3 того
же документа; price candidates — только из projected offers с сохранением provenance.
Два tuple не смешиваются. S29 не выбирает UI source, не применяет session suppression и
не подключён к product path; эти решения остаются следующей отдельной policy boundary.

S30 принимает явно заданный будущим ResponseSpec/caller source `content`, `price` или
`None` и пропускает соответствующий S29 tuple целиком. Policy не выводит фокус из порядка
components, не смешивает, не ранжирует, не обрезает и не подставляет другую family при
пустом результате. Widget/session/runtime и product path по-прежнему не подключены.

S31 объединяет proven S27→S30 segment одним прозрачным offline facade и возвращает exact
materials, plan, follow-up candidates и selected follow-ups. Он не меняет решений и не
перехватывает ошибки стадий. Это проверка сквозной совместимости текущего downstream
участка, а не финальный target path и не замена upstream ResponseSpec.

S32 вводит канонический immutable `TargetResponseSpec`: response mode, tone key,
allowed/forbidden topic scope, required facts/components, follow-up family и permissions
для marketing/consultation/CTA. `medical_handoff` сам является обязательной downstream
границей no-diagnosis/differential/personal-eligibility/treatment-choice; forbidden topics
лишь дополнительно сужают evidence. Manual-contact hard-stop происходит до ResponseSpec.
S32 валидирует explicit spec offline, но ещё не строит его из TurnFrame и не имеет authority.

S33 строит S32 spec из strict explicit non-A9 request и принимает только одно policy-
решение: выбирает content/price/no follow-up по requested + primary component. Mode,
topic scope, facts, components, tone и sales permissions остаются явными входами.
Terminal request-only focus не отбрасывается молча; S32 safety errors не оборачиваются.
TurnFrame/patient_scope, product authority и runtime не подключены.

S34 связывает explicit spec с S31 composition offline. Raw materials и follow-up
candidates остаются внутренними: потребителю разрешены только spec-projected plan
identities, selected follow-ups и отдельно gated `selected_cta_key`; plan CTA — кандидат.
Permission ceilings нельзя расширять inclusion-запросом. Topic allow/forbid и required-fact
coverage пока не доказаны metadata текущего evidence, поэтому Composer/product wiring
запрещены до следующего evidence-scope checkpoint.

S35 строит из S34 отдельный закрытый identity-only **scoped primary evidence** view. Он
**дополняет** cached FullContext (см. **FINAL_FULLCONTEXT_ONLY**), а не заменяет его как
knowledge input Composer. Topic scope применяется к **уже выбранным** service/doctor/KB
identities, без document retrieval или ranking. Service-linked offers и commercial facts
наследуют topic услуги; врачи сохраняют topic услуги и своего profile MD. Каждый factual
ref обязан пересекаться с allowed topics и не пересекаться с forbidden topics. Required
fact считается покрытым только выбранным commercial fact, а не его наличием среди raw
candidates или offer fact_refs. Missing scope/fact/component завершается явной ошибкой без
whole-base fallback. Composer/Verifier/product wiring всё ещё отсутствуют; medical_handoff
prose safety остаётся их отдельной обязательной границей.

S36 является последним offline-адаптером перед будущим Composer call: exact S35 identities
дословно разворачиваются в immutable request blocks **поверх** cached FullContext, не
вместо него. Content получает только выбранное MD body без frontmatter; anchored KB/doctor
refs — только точную секцию; offers — цену, package и payment stages без candidate
fact_refs/follow-ups; doctors — только имя, должность, стаж и выбранный profile section;
commercial fact/consultation копируются из точного source object. S36 **не** перестраивает и
**не** ищет FullContext cache — он materialize strict blocks для verifier/exact-fact layer.
S36 ещё не вызывает модель и не создаёт ответ: Composer execution, live quality proof,
Verifier и product wiring остаются отдельными gates.

S37 добавляет минимальную provider-neutral границу Composer execution. Она проверяет
закрытую форму S36 request, детерминированно сериализует response directives и primary
evidence, передаёт их одному injected backend ровно один раз и возвращает только явно
`unverified` текст. Stable policy запрещает user prompt расширять evidence, использовать
невыбранные FullContext-факты, придумывать маркетинг или выводить UI-sidecars; для
`medical_handoff` отдельно запрещены diagnosis/differential/personal eligibility/treatment
choice. Follow-ups и CTA не передаются модели. Retry, repair, fallback, provider wiring,
live quality proof, Verifier и product authority в S37 отсутствуют.

S38 добавляет fail-closed target Verifier. Digit-form numeric claims сверяются по типу и
значению только с exact selected evidence; structured offer/doctor JSON раскрывает цены,
этапы, package/profile text без сканирования IDs, а lexical names вроде `All-on-4` уходят в
semantic grounding. Каждый selected strict commercial fact обязан присутствовать verbatim.
После deterministic checks каждый ответ получает ровно одну provider-neutral semantic
assessment: grounding (включая числа словами и unit/context), topic scope, medical boundary
и все selected facts. Verifier не чинит и не сокращает текст: mismatch/failure блокирует,
success сохраняет exact S37 text и sidecars. Provider/live quality proof, runtime/UI и
product authority всё ещё отсутствуют.

S39 замыкает response-generation vertical от exact S34 upstream package до verified
response одной straight-line композицией `S36 → S37 → S38`. Он не добавляет новую policy,
validation или error semantics: materializer, Composer и Verifier вызываются по одному разу,
а любая typed failure без catch/fallback прекращает downstream. Verified text и sidecars
возвращаются без пересборки. Это structural offline milestone для handoff, а не готовый бот:
TurnFrame/A9 authority, provider/live quality, routes/UI/session и product wiring остаются
отдельными governed этапами.

S40 замыкает offline response-generation vertical от explicit `TargetResponsePolicyRequest`
до verified response одной straight-line композицией `S33 → S34 → S39`. Он не добавляет
новую policy, inference, validation или error semantics: spec builder, spec-bound package
assembly и verified pipeline вызываются по одному разу, а любая typed failure без
catch/fallback прекращает downstream. Verified text и sidecars возвращаются без пересборки.
Это structural offline entry point, а не готовый бот: TurnFrame/A9 authority, provider/live
quality, routes/UI/session и product wiring остаются отдельными governed этапами.

S41 добавляет deterministic TurnFrame dispatch boundary перед S40. Explicit envelope owns
tone, topic scope, required facts, marketing permissions and `boundary_decision`; TurnFrame
contributes only intent/aspects/topic/clarify/service_id mapping. Invalid metadata raises
typed dispatch errors; successful dispatch returns only `materialize | terminal`. Materialize
calls S40 once. **Только `uncertain` (S42) → terminal defer.** Confident `medical_handoff`
**materialize**, когда offline dispatch имеет usable `service_id` и components **или** confident
`medical_handoff` / `answer` с content-only components без `service_id` (S45 FullContext path).
Иначе S41 возвращает terminal defer / `medical_handoff_nonmaterializable`. Clarify/defer — отдельные terminal modes.
`patient_scope` is not read.

S42 adds an offline provider-neutral medical boundary detector with three-way semantics
(`none | medical_handoff | uncertain`), structured-output validation, canonical reason codes,
and deterministic envelope enforcement. Low confidence, malformed backend output, backend
failure, or ambiguity never become `none`; **`uncertain` only** maps to terminal defer
enforcement, not commercial `boundary_decision="none"`. Confident `medical_handoff` sets
safety mode and **allows** grounded content answers from clinic MD (see § Medical question
semantics); S42/S43 do **not** implement response content or FullContext integration.
Recognition quality is **not proven** until a separately governed live eval with owner
permission. No runtime wiring or live LLM calls.

S43 prepares a separate frozen live-eval matrix and offline harness for the S42 medical
boundary detector. Matrix expectations (`none | medical_handoff`) are frozen before the
first live run; `uncertain` is tracked as technical only. Owner-approved confidence floors
(`none` 0.80, `medical_handoff` 0.70) and acceptance thresholds are frozen in contract/matrix
before first live; harness passes floors explicitly and evaluates deterministic PASS/FAIL
gates with correct rate denominators. Harness scores exact, uncertain, dangerous false-none,
excessive false-medical-handoff (among expected=none), malformed/backend failures, and
transport separately. First live raw/result artifacts require absent-before-run check and
exclusive-create writes. **First live audit (2026):** owner-authorized run captured with
immutable artifacts and audit manifest; verdict **PASS** 25/26, sole non-exact `mb_border_01`;
model `qwen3.6-flash` provenance from run log only; **LIVE_ALREADY_RUN_ONCE / DO_NOT_RERUN**.
**Scope:** boundary classification only — not medical answer content, Verifier, or FullContext
integration.

S44 adds deterministic cached FullContext as the **primary knowledge input** for target
Composer (offline/unwired). `build_target_cached_full_context(md_root)` runs once as bootstrap
and returns immutable `TargetCachedFullContext`: all valid `.md` under explicit client
`md_root` (including doctors MD), stable relative-path order, explicit document boundaries,
SHA-256 of `corpus_text`. The same prebuilt object is injected through S39/S40/S41 into
S37; pipelines **do not** rescan `md_root` or rebuild corpus per turn. `TargetComposerInvocation`
separately carries `cached_full_context`, turn-specific directives, and scoped
`primary_evidence_json`. Provider prompt caching is **not** implemented — only a stable
corpus/prefix candidate for a future live gate. **S34/S41 `service_id` gate unchanged:**
after S44 Composer sees the full corpus, but service_id-free general/medical answer is still
not end-to-end. Next offline focus: one vertical slice for service-optional FullContext
materialization, missing-base response, and medical grounding verification.

S45 closes the offline vertical slice for **service-optional content-only** responses
(offline/unwired). Dual source authority: **cached FullContext** is the primary knowledge
input for general clinic MD (informational, reassuring, approved medical facts); **structured
primary evidence** remains strict authority for prices, payment stages, promotions,
marketing/consultation values, CTA, and exact doctor credentials. On conflict structured
exact facts win; Verifier fail-closes. Dispatch sanitizes envelope for content-only path
(`required_fact_ids=()`, no marketing/CTA). `TargetSemanticVerification` replaces misleading
`grounded_in_primary_evidence` with `general_grounding_ok` + `strict_commercial_grounding_ok`.
Verifier receives the same prebuilt `TargetCachedFullContext` as Composer. **S34/S40/S41
service-specific paths unchanged in meaning.** No live/LLM. Governance `e7c312c`.

S46 closes the last manual seam in the offline response chain (offline/unwired). Public API
`run_target_offline_boundary_enforced_fullcontext_response` accepts ready `TurnFrame` +
`TargetMedicalBoundaryResult` (detector **not** called), runs S42
`enforce_target_medical_boundary_on_envelope` once, returns
`TargetMedicalBoundaryTerminalEnforcement` for `uncertain` without S41/Composer/Verifier, else
delegates to S41 `run_target_offline_turn_frame_bound_response` once. Return union uses
existing types only. **No new inference, package builder, or authority change.** Governance
`9ad4614`. No live/LLM.

---

## Порядок работ — strangler, две кучи

### Куча A — must-fix ПЕРЕД тем как доверять пилоту (безопасность + честность + **самосогласованность**)

A должна быть **самодостаточной**: её собственные критерии требуют **минимальных** версий пары вещей из B — вносим сюда (минимум, не полный каркас).

1. **Медзона → boundary до генерации** (детект-флаг + enforcement), `response_mode=medical_handoff`.
2. **Минимальная настоящая ось `topic`** (включая `whitening`) + **снос врачебного regex** из topic-адаптера. Иначе `expected_topic` в eval не на чём проверять.
3. **Field-level санитизация всех текущих полей `TurnPlan`** (`brand_filter/service_id/needs_clarify`) → `field_errors`, не крашить весь план.
4. **Семантические ассерты в emotion eval:** `expected_topic`, `expected_emotion`, `required_signals`, `forbidden_signals`, `must_handoff`, `must_not_discuss`, groundedness.
5. **Safe-default уважает жёсткие сигналы** + лог `degraded`.
6. **Фикс протечки через scoped primary evidence** для reassurance (**минимальная** версия слоя evidence, **с fail-safe** из п.4 цепочки). `(topic,aspect)`-таблицу **не растить**.

→ После A пилот **честный, безопасный, самосогласованный**, семантический eval зелёный. **Только тогда коммит.**

### Куча B — структурная стройка, по кирпичу (НЕ в пилот)

1. `topic` — **конфигурируемая taxonomy** по client pack (не хардкод enum).
2. Единый `TurnFrame` + декларативный `ResponseSpec` как контракт (снять `(topic,aspect)`-таблицу целиком).
3. **Каркас `Evidence assembly`** (общий, с полным fail-safe).
4. Field-level валидация — **общий механизм** с provenance по полям.
5. `Verifier` как **компонент** (первый target-рантайм: deterministic digits + semantic
   assessment каждого ответа; сужение до high-risk/sampling — только после измерений).
6. Перенос ownership по осям (aspects → dialog_focus → patient_scope), затем удаление legacy. **Метрики:** per-axis accuracy, semantic pass rate, planner degraded rate, число LLM-вызовов, p50/p95, стоимость хода.
7. **Trust/P3 — только после** общего evidence/policy механизма.

---

## Статус пилота (emotion)

**P0/P1 НЕ завершён.** Ось `emotion` + убийство price-fail-open — сделано и ценно. До коммита — **Куча A** целиком. Не отмечать «готово», пока A не закрыта.
