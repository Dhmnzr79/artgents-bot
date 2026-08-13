# Архитектура маркетинговых сценариев

**Статус:** согласованный product/design-контракт; frozen schema models реализованы
offline в S1, demo target policy материализована в S20, pure deterministic selector —
в S21 (historical offline seam), one-service offline evidence package — в S22.
**Stage 5.1 ONE_CALL product path принят** (`a268878`): unified typed `PresentationResult`,
deterministic promotion selector, session-global suppression и render-proven shown-state —
current ONE_CALL runtime owner.

**Режим:** documentation-only. Документ не меняет ответы demo, client config, prompts, UI или authority A9.

**Три слоя этого документа:**

| Слой | Содержание |
|------|------------|
| **Current accepted** (Stage 5.1, `a268878`) | ONE_CALL product path: unified `PresentationResult`, promotion authority (`priority_service_promos` / `promotion_overview`), `select_stage51_marketing`, session/render state, limits **3/2**, CTA/secondary separation |
| **Historical** | S20/S21/S22 и другие offline pieces — источники/seams происхождения архитектуры; **не** current presentation owner |
| **Future target** | Stage 5.1B — availability, canonical alternatives, price gaps |

**Precedence:** для marketing contract semantics этот документ имеет приоритет над legacy promo-ограничениями в `MARKETING_EDITING_GUIDE.md` и `PRICEBOOK_V2.md`. Stage 5.1 current runtime реализует принятый promotion/presentation contract в своём scope.

Этот контракт описывает, как бот-продавец собирает ответ из утверждённой базы,
коммерческих фактов, сценарных усилителей и CTA. Он не задаёт готовые тексты ответов.
Historical S20 наполняет demo только ordered source refs/contexts и **не** подключает их
к production ответам сам по себе — current Stage 5.1 runtime использует отдельный
presentation path (`build_one_call_presentation_result`).

## Главные законы

1. Бот — продавец клиники, а не самостоятельный медицинский консультант. Цель — лид.
2. Содержание берётся только из утверждённых источников клиники. Менять числа, проценты, гарантии, обещания, отрицания, модальность и силу формулировки запрещено.
3. Порядок смысловых блоков может быть декларативным; заготовленные сценарные фразы и `scenario_openings` запрещены.
4. В ответе может быть не более трёх рекламных/маркетинговых фактов; усилителей среди них — не более двух.
5. CTA не входит в этот лимит и может повторяться после каждого содержательного коммерчески релевантного ответа.
6. Свободные слоты не заполняются нерелевантными фактами.
7. В обычном диалоге любая текущая личная боль или активное осложнение завершают ход в manual-contact boundary до marketing/retrieval/composer/UI-policy. Явно выбранный `situation_intake` является отдельным conversion state: любое стоматологическое описание сохраняется с заявкой и не уходит в FullContext.

## Режимы ответа

| Режим | Порядок | Что важно |
|---|---|---|
| Обычный первый ответ об услуге | Ответ по базе → обязательная priority service promo → до двух amplifiers primary `scenario` → CTA | Priority promo — marketing fact, не amplifier; consultation/installment не автодобавляются |
| Обычное продолжение | Ответ по базе → CTA | Нейтральный follow-up не прокручивает pool усилителей |
| Маркетинговое сомнение | `acknowledge_concern` → `answer_from_sources` → priority promo (если первый eligible service turn) → `select_marketing_facts` → CTA | Flow задаёт порядок, а не текст; лимит 3/2 общий |
| Прямой вопрос о факте | Ответ по источнику → CTA | Не подменяется сценарием; история автопоказа не может скрыть ответ |

Если первый вопрос об услуге уже содержит маркетинговое сомнение, основной ответ по
источникам остаётся вне marketing slots. Затем при первом eligible service turn
резервируется обязательная priority service promo (если применима), после чего выбираются
до двух релевантных усилителей активного primary `scenario`. Оставшиеся места общего
лимита трёх facts могут занять другие применимые commercial facts. CTA добавляется
отдельно; пустые места не заполняются нерелевантными фактами.

## Что считается marketing fact

Один рекламный слот занимает:

- бесплатная консультация;
- рассрочка;
- скидка или подарок;
- налоговый вычет;
- гарантия, врач, технология или другой факт, если он добавлен для убеждения.

**Priority service promo** — обязательный marketing fact первого eligible service turn; **не** amplifier.

В лимит не входят основной ответ по базе, цена и карточки услуг, CTA и follow-up-кнопки. Если пациент сам спросил о гарантии, враче или приживаемости, соответствующий факт — часть прямого ответа. Если он добавлен поверх ответа для убеждения, это усилитель и один amplifier slot.

## Priority service promo (первый ответ об услуге)

На первом допустимом содержательном ответе с authoritative non-null `service_id`,
`commercial_intent=none` и `promotion_scope=none` бот обязан показать **ровно одну** первую
active, применимую promo **конкретной** услуги. **Нет** одной «главной акции клиники» —
для каждой услуги клиника задаёт отдельный упорядоченный список в `priority_service_promos`.
Текст, процент, срок и условия — только из authoritative client data; модель не выбирает
точную акцию и не генерирует её условия.

- authority: `priority_service_promos.<service_id>.ordered_fact_refs` — первый eligible ref;
- promo другой услуги **не** подмешивается; consultation/installment **не** используются как fallback;
- priority promo — marketing fact; входит в лимит **3**, **не** в лимит **2** amplifiers;
- selector **сначала** резервирует priority promo, **затем** выбирает amplifiers;
- при `commercial_intent=none` и `promotion_scope=none` — единственное bounded automatic commercial исключение; **не** открывает price amount, price/offer card, payment terms или included items; обычный вопрос об услуге **не** превращается в promotion request;
- при `service_id=null` или отсутствии eligible promo автоматическая service promo **запрещена**;
- session-global suppression: один `fact_id` автоматически показывается **один раз** за `session_id`, даже если применим к нескольким услугам; новый session/reset очищает suppression; per-service shown-state для одного fact ID **не** вводится.

**Бесплатная консультация и рассрочка** в первом ответе **не** добавляются автоматически
сверх priority promo и усилителей. Рассрочка — при прямом вопросе об оплате (`commercial_intent=payment`) или валидном payment context. Консультация — как применимый выбранный fact или через отдельный CTA/consultation flow. Нельзя автоматически показывать promo + consultation + installment + amplifiers сверх общего лимита **3**.

## Promotion request (`commercial_intent=promotion`)

Новый closed enum: `commercial_intent=promotion` означает явный интерес пациента к акции,
скидке или специальному предложению. Он **не** открывает price amount, price/offer card,
payment terms или included items; разрешает только validated promo facts из authoritative
client data.

Closed `promotion_scope`:

| Scope | Поведение |
|-------|-----------|
| `general` | Общий вопрос «Какие акции есть?» → до **3** active clinic-authored promo facts по `promotion_overview.ordered_fact_refs`; фильтр active dates и общей применимости |
| `service` | Вопрос об акциях конкретной услуги → одна первая eligible promo из `priority_service_promos[service_id]`; authoritative `service_id` обязателен |
| `shown` | Вопрос о ранее **фактически rendered** promo → повтор последней session promo; suppression обходится; fail closed, если session-bound promo отсутствует |

Invariants: если `commercial_intent != promotion`, то `promotion_scope=none`; `CLARIFY` и `ADMIN` не открывают promotion surface; arbitrary specific promo не угадывается по тексту, regex или keyword classifier; `promotion_ref` не добавляется.

Налоговый вычет не входит в обязательный первый service promo: он используется при финансовом сценарии, прямом вопросе или как усилитель.

## Сценарии и усилители

Для текущего target достаточен небольшой стандартный набор:

- `pain_fear` — страх будущей боли/лечения;
- `cost` — возражение по цене или бюджету;
- `time` — возражение по срокам;
- `doctor_trust` — сомнение в опыте/доверии к врачу;
- `result_reliability` — сомнение в результате, приживаемости или надёжности.

Для ONE_CALL target Flash возвращает **один** primary `scenario` из закрытого enum
(§ ONE_CALL Architecture Lock §9). Один primary scenario может дать до двух релевантных
amplifiers. Прямой вопрос «кто у вас ставит импланты?» не означает `doctor_trust`;
сценарий нужен при выраженном сомнении/недоверии.

Исторический offline/legacy контракт `marketing_scenarios` 0–2 и `TurnFrame` multi-scenario
**не** являются текущим ONE_CALL Stage 5.1 envelope. Их нельзя выдавать за принятый
ONE_CALL target contract.

Усилители — ссылки на уже утверждённый факт из KB, commercial facts или профиля врача. В `marketing.yaml` хранятся правила, ограничения scenario/pool context, порядок и ссылки, а не source-fact eligibility или дубли текста. Обычно клинике достаточно 2–4 усилителей на сценарий, но сама schema не ограничивает размер pool. Порядок ссылок задаёт приоритет; нейтральный follow-up не прокручивает pool.

Ненормативный target-пример:

```yaml
response_limits:
  max_marketing_facts_per_turn: 3
  max_amplifiers_per_turn: 2

scenario_rules:
  pain_fear:
    amplifiers:
      - ref: "kb:content_doc.md#approved_chunk"
      - ref: "doctor:doctor_id"
```

Пример показывает только форму ссылок. Он не предписывает demo конкретные факты или врача.

## Отбор и повторы

Целевой селектор (post-Flash deterministic presentation):

1. уважает прямой запрошенный fact, если есть;
2. на первом eligible service turn с authoritative `service_id` резервирует обязательную priority service promo;
3. выбирает до двух релевантных amplifiers одного primary `scenario`;
4. заполняет оставшиеся из трёх marketing slots только применимыми commercial facts по порядку клиники;
5. отбрасывает неактивные, неприменимые к услуге/теме, просроченные и уже показанные автоматически факты;
6. в остальных режимах сохраняет предусмотренный режимом порядок клиники;
7. всегда берёт не более трёх marketing facts, из них не более двух amplifiers;
8. не дополняет ответ нерелевантными фактами ради лимита;
9. добавляет CTA отдельно.

Priority promo **не** может быть вытеснена amplifiers. Amplifiers **не** занимают promo slot.

`shown_fact_ids` и `shown_amplifier_ids` хранятся в текущем `session_id`. Новый диалог/сброс чата создаёт новую сессию; TTL пока не вводится. **Session-global suppression:** один и тот же `fact_id` автоматически показывается **один раз** за весь `session_id`, даже если применим к нескольким услугам (например, скидка показана для All-on-4, затем пациент спрашивает о classic — тот же `fact_id` автоматически не повторяется). Новый fact с другим ID может быть показан. Прямой promotion request (`commercial_intent=promotion`, `promotion_scope=shown`) может повторно открыть факт, если он active и applicable; per-service shown-state для одного fact ID **не** вводится.

## Несовместимые предложения

Коммерческий факт может ссылаться на другие `fact_id` через `incompatible_with`. Точное условие хранится в утверждённых данных клиники. Если два таких предложения показаны вместе, бот описывает их как альтернативы и не выбирает за пациента.

Нет универсального правила «скидка всегда не суммируется с рассрочкой». Оно нельзя зашивать в код без данных конкретной клиники.

## CTA

CTA и marketing-fact cadence независимы. Одна основная CTA может показываться после каждого содержательного ответа по коммерчески релевантной теме, даже если пациент задал пять вопросов подряд. CTA настраивается один раз для смыслового контекста, а не для каждого документа/ответа: внутри контекста она стабильна, при явной смене контекста выбирается другая настроенная CTA. Например, общий разговор об имплантации и вопросы о врачах могут иметь разные CTA. Если специальной CTA нет, используется clinic default; модель не придумывает кнопку.

CTA не показывается:

- в manual-contact hard-stop;
- в spam/off-topic;
- после явного отказа от записи/звонка;
- во время уже начатого lead-flow;
- в узком clarify, где бот ещё не дал содержательного ответа.

Видимая подпись CTA и первая lead-flow реакция остаются в CTA/tone config. Это UI/lead copy, а не заготовка сценарного ответа.

### Choice menu (governed branch selection)

Когда бот предлагает пациенту **выбрать ветку диалога** (объём лечения, этап, вариант
ситуации, typed clarification/action), допускается до **четырёх** governed-кнопок в одном
ответе.

- Классификация — по **типу typed action/ref** (`UiScopeAction`, `UiStageAction`, другие
  governed clarification choices), **не** по тексту кнопки.
- Максимум 4; deterministic ordering; dedup по ref; только валидные session-bound refs.
- Invalid/unshown ref → существующий fail-closed.
- Choice menu **не смешивается** в одном ответе с обычными secondary navigation buttons.
- CTA остаётся отдельным элементом и **не занимает** choice slot.
- Regex/phrase lists для определения типа меню запрещены.

Owner decision: `FULLCONTEXT_PRESENTATION_PARITY` @ `50c6cf9` (2026-07-27).

### Content navigation slots (secondary UI)

CTA не занимает secondary UI slots. Pure clarify использует только свои уточняющие
кнопки и не добавляет content follow-up/video. Содержательный content-ответ имеет **два**
secondary slots: video показывается один раз с приоритетом на первом ответе по материалу,
остальные места получают следующие ещё не показанные follow-up; **затем** «Рассказать о
ситуации», если остался слот. Sliding-window повторов
нет; новый материал создаёт новый набор кандидатов. «Рассказать о ситуации» — после video
и обычных follow-up, только если остался слот. Текстовые усилители к UI slots не относятся.

**Важно:** secondary slots (max 2) и choice menu (max 4) — **разные каналы**. Scope/stage
choice menu относится к лимиту 4, а не к price-detail или content secondary slots.

**Channel mutex (`FULLCONTEXT_DIALOGUE_PRESENTATION_CONVERGENCE` @ `7c716df`):** один ответ —
ровно один navigation channel: choice **или** content secondary **или** price-detail.
Запрещено `choice+price` и `secondary+price` в одном `quick_replies`. CTA отдельно.

**Marketing scenario projection (ONE_CALL target):** Flash envelope несёт **один** primary
`scenario` (`pain_fear` | `cost` | `time` | `doctor_trust` | `result_reliability` | `none`).
Post-model deterministic presentation владеет priority promo и amplifier selection.
Direct informational questions do **not** create scenarios (duration ≠ time, warranty ≠
result_reliability, doctors info ≠ doctor_trust). Исторический `TurnFrame.marketing_scenarios`
0–2 — legacy/offline projection, не текущий ONE_CALL envelope.

Price-ответ имеет отдельные два navigation slots и не смешивается с content follow-up.
Кнопками становятся только элементы из `service.followups`; `fact_refs` добавляют
source-owned facts текстом и не создают автоматические кнопки. Прямо запрошенный аспект
отвечается сразу, а совпадающая кнопка повторно не показывается. В обычном первом
price-ответе demo приоритет при наличии в `followups`: «Что входит», затем «Оплата по
этапам». Показанные/нажатые price follow-up автоматически не повторяются. CTA существует
отдельно.

## Service availability, alternatives and price gaps (Stage 5.1B)

**Статус:** docs-only owner decision; implementation **не** начата. Канон: Architecture Lock §11.1.

Единый post-Flash `PresentationResult` владеет **всеми** commercial и navigation surfaces, включая:

- service availability (`offered` / `known_not_offered` / `unresolved`);
- not-offered + authored alternatives (max 2; buttons → content secondary slots);
- `no_public_price` и family-level context (explicit applicability only);
- price cards только при exact numeric offer и `commercial_intent=price`;
- CTA отдельно от secondary slots.

**Promotion interaction (Stage 5.1):**

- unavailable service: **no** priority promo;
- alternative promo: **not** automatic in same turn until patient selects alternative and `service_id` switches;
- offered + `no_public_price`: may receive priority promo per Stage 5.1;
- promo never invents base price; no discount from family price.

**Current seams (pre-Stage-5.1B):** keyword `service_alternatives` in `clinic_policies.yaml`; `target_family_price_resolution` safe `data_gap` for named service + family-only price; inconsistent unavailable/price-gap presentation.

**Performance:** 0/1 provider calls; local presentation pass; no regex/keyword classifier; no marketing LLM.

## Manual-contact boundary

В обычном диалоге в ручной контакт до основного ответа переходят:

- любая текущая личная боль;
- активное осложнение или текущее ухудшение после лечения;
- жалоба, спор или негативный отзыв, требующий реакции.

После согласованной человечной заглушки с номером клиники запрещены свободная генерация, marketing facts, CTA, quick replies, video и другой UI. Общий вопрос о будущей боли или страхе лечения остаётся `pain_fear`. После явного входа в `situation_intake` действует отдельный conversion contract из `MARKETING_QUESTION_FOUNDATION.md` §7.2.

## Target ownership

| Владелец | Что хранит |
|---|---|
| `clients/<client_id>/target_response/marketing.yaml` | Лимиты, `priority_service_promos`, `promotion_overview`, scenario rules, упорядоченные amplifier refs, ограничения scenario/pool context, CTA key selection и fact/scenario cadence policy; без дублей текста и без source-fact eligibility |
| Pricebook/commercial facts | Консультация, рассрочка, скидка/подарок, вычет, гарантия как commercial fact, даты, точные условия и `incompatible_with` |
| KB/md | Содержательный утверждённый контент и факты клиники; optional `consultation_value` в frontmatter того же service-документа |
| Doctor layer | Имя, должность, стаж и связи с услугами; общий продающий профиль хранится в exact MD chunk |
| CTA/tone config | Подписи CTA и lead-flow copy; не готовые вступления сценарных ответов |
| `clients/<client_id>/clinic_policies.yaml` | Target `service_alternatives` (`requested_service_id`, `alternative_service_ids`, `approved_text`); not-offered / OMS policy |
| Session state | `shown_fact_ids`, `shown_amplifier_ids`, `shown_consultation_value_refs`, текущая тема/услуга, lead/refusal state |
| ONE_CALL Flash envelope | один primary `scenario`; `commercial_intent` и `promotion_scope`; конкретные facts и priority promo выбирает post-Flash deterministic code |

Полная target ownership услуг, offers, брендов и client strategy находится в
[`PRICE_SERVICE_ARCHITECTURE.md`](PRICE_SERVICE_ARCHITECTURE.md). Marketing schema ниже
ссылается на этих владельцев по ID/ref и не копирует их текст или деньги.

## Нормативная target-схема marketing policy

Имена полей и форма ниже нормативны; значения ID/ref намеренно условны и не описывают
demo или другую конкретную клинику.

```yaml
version: 1

limits:
  max_marketing_facts_per_turn: 3
  max_amplifiers_per_turn: 2

priority_service_promos:
  all_on_4:
    ordered_fact_refs:
      - fact:all_on_4_discount
  professional_whitening:
    ordered_fact_refs:
      - fact:professional_whitening_discount

promotion_overview:
  ordered_fact_refs:
    - fact:...

scenario_rules:
  pain_fear:
    ordered_amplifier_refs:
      - kb:content_doc.md#approved_chunk
      - doctor:doctor_id
      - fact:warranty_fact_id
    allowed_semantic_contexts: [service_family_context]

cta_contexts:
  service_family_context: consult
  doctors: doctor
  default: callback
```

- `priority_service_promos` управляет automatic first-service promo и `promotion_scope=service`;
- `promotion_overview` управляет **только** `promotion_scope=general` (до 3 active promo);
- оба списка содержат refs на authoritative facts; тексты и условия — в `facts.json`;
- один fact может присутствовать в service mapping и overview;
- `initial_commercial_blocks` остаётся legacy compatibility data в demo config; **не** является current Stage 5.1 promo authority;

Это схема ссылок и порядка, а не готовых фраз. В одном scenario pool может быть сколько
угодно проверяемых refs конкретной клиники; selector берёт максимум два усилителя на ход и
максимум три marketing facts суммарно. Demo не нужно наполнять большим числом сценариев.

### Допустимые source refs

| Ref | Владелец факта | Проверка |
|---|---|---|
| `fact:<fact_id>` | `pricebook/facts.json` | fact существует, active, применим, не просрочен |
| `kb:<doc>#<chunk>` | KB/md | точный doc/chunk существует в client pack |
| `doctor:<doctor_id>` | doctor layer | врач существует и связан с темой/услугой |

Policy не содержит свободный amplifier text. Если source ref исчез или не проходит
eligibility, он отбрасывается; модель не заменяет его похожим утверждением.

### Service consultation close

У нужного service Markdown допускается одно optional поле `consultation_value` в YAML
frontmatter того же файла. Оно хранит утверждённый смысл пользы консультации по этой
услуге, а не готовую фразу, CTA или follow-up. Основное тело MD может быть естественно
продающим и clinic-specific без отдельной карточки приоритетных фактов.

Frontmatter исключён из общего FullContext body. После exact выбора service/option
будущий evidence assembly может получить значение только прямым lookup по его
`content_ref` и передать composer с ролью `consultation_close`. Значения других
документов не становятся selectable consultation material; отдельный retriever,
`service_accents` или H3 `#consultation-value` не создаются.

При автоматическом использовании `consultation_value`:

1. он ставится только в заключение подходящего содержательного service-ответа;
2. занимает один из трёх marketing-fact slots и один из двух amplifier slots;
3. при заполнении любого лимита пропускается без записи shown-state;
4. exact document ref показывается автоматически максимум один раз в текущем
   `client_id + session_id`, независимо от H3/chunk/follow-up clicks;
5. ref записывается только после фактического включения в ответ;
6. manual-contact, spam/off-topic, pure clarify, active lead-flow и явный отказ от
   консультации/контакта подавляют автопоказ.

Прямой вопрос о консультации является основным source-backed content и не занимает
automatic marketing/amplifier slots. Он обходит только repeat suppression: exact
selected `content_ref`, применимость, source fidelity и safety boundaries обязательны.
Новый session/reset очищает suppression; TTL и per-client cadence setting не вводятся.

### Минимальный doctor layer

Doctor record содержит только стабильный ID, имя, должность, стаж, service links и
exact ссылку на общий продающий MD-профиль. Полей `active`, образования, сертификатов,
фото, расписания, слотов, рейтинга, priority и отдельной UI-card schema нет. Наличие
врача в каталоге означает, что его утверждённую информацию можно показать; вопросы
доступности и записи остаются у администратора, синхронизации с расписанием нет.

Будущее product-поведение должно отвечать на запросы «кто делает услугу», «кто сильный
специалист по услуге» и «какие врачи и какой опыт» через service links и MD-профили.
При нескольких совпадениях бот показывает релевантных врачей без выдуманного рейтинга
«лучший». Это описание target behavior, а не разрешение подключать doctor schema к
ответам до отдельного authority checkpoint.

Service link — простая связь врача с услугой. В target нет отдельных ролей врача,
этапов комплексной услуги или скрытого ranking: все связанные врачи релевантны запросу
по этой услуге. При любом показе врача answer context обязан включать его имя, должность
и стаж; вопрос «какой опыт?» для этого не требуется. MD-профиль добавляет продающее
описание, но не является единственным источником стажа.

Описание услуги, её цена и врачи используют один и тот же canonical `service_id`.
После явного вопроса про All-on-4 semantic dialog focus сохраняет `all_on_4`; следующие
«сколько стоит?» и «а кто делает?» разрешаются через тот же ID соответственно в
pricebook и doctor catalog, а не через независимое угадывание темы. Это future common
context law; его runtime wiring и authority требуют отдельного checkpoint.

Offline boundary S10 материализует этот общий data context только из уже проверенных
target-моделей: exact service record с `content_ref`, все authored offers той же услуги
и всех связанных doctors с обязательными именем, должностью, стажем и `profile_ref`.
Он сохраняет authored order и флаги, но не фильтрует `active`, не применяет eligibility,
не ранжирует врачей, не читает source text и не формирует ответ. Подключение builder к
dialog focus/product path и любая authority остаются отдельным checkpoint.

### Structured scenario (ONE_CALL)

ONE_CALL Flash envelope возвращает **один** primary `scenario`. Значение означает
потребность применить общий порядок операций, но не выбирает готовую реплику:

1. ответить по релевантному source content;
2. зарезервировать priority service promo на первом eligible service turn (если применимо);
3. выбрать до двух source-backed amplifiers этого сценария;
4. заполнить оставшиеся из трёх marketing slots применимыми commercial facts;
5. добавить одну CTA отдельно.

Отдельные regex/classifier paths для боли, цены, врача и приживаемости запрещены.
Stage 5.1 **не** расширяет envelope до массива сценариев.

### Session и cadence

Target session изолирован по `client_id + session_id` и хранит:

- `shown_fact_ids`, `shown_amplifier_ids`;
- `shown_consultation_value_refs` для реально использованных automatic service closes;
- показанные/нажатые content follow-up IDs;
- показанные/нажатые price follow-up IDs;
- `shown_video_ids`;
- текущий semantic context/услугу и выбранный CTA key;
- lead/refusal state.

Тот же fact/amplifier автоматически не повторяется в session. Новый диалог/сброс создаёт
новую session; TTL пока нет. Прямой вопрос об **уже показанной конкретной** акции/факте
обходит только suppression повтора, но не active dates, eligibility, source fidelity,
incompatibility или manual-contact boundary.

### CTA selector

CTA key берётся один раз для semantic context. Context-specific key имеет приоритет,
иначе используется clinic default; видимая подпись берётся из CTA/tone config. CTA не
занимает marketing или navigation slots и не показывается в manual contact, spam/off-topic,
pure clarify, после явного отказа или внутри активного lead-flow.

### Offline selector S21 (historical)

S21 — **offline pure selector** из already-validated target models. Он **не** является
current ONE_CALL Stage 5.1 product path и **не** реализует accepted target order.

#### Historical S21 behavior (offline legacy)

**Does not satisfy accepted target.** Сохранено как честное описание historical offline
реализации; current Stage 5.1 runtime использует `build_one_call_presentation_result` /
`select_stage51_marketing`, а не S21.

Явные inputs: semantic context, optional already-selected service, ordered scenarios,
explicit date, флаг initial block и read-only shown snapshots. Результат — immutable
tuples refs/scenarios и CTA key; selector не читает client files, clock или session и
не формирует текст.

Historical exact order:

1. scenarios фильтруются по exact allowed context, затем ограничиваются policy cap;
2. до двух pools объединяются round-robin: по одному eligible ref на scenario за круг;
3. каждый scenario ref занимает один общий marketing slot и один amplifier slot;
4. оставшиеся из максимум трёх marketing slots заполняются только exact initial block
   текущего context;
5. fact проходит active/inclusive-date/service/shown и incompatibility gates;
6. CTA выбирается exact context → required default.

Direct fact question и automatic `consultation_value` **не входят** в S21.

Historical demo examples (pre-Stage-5.1):

- `cost + price + all_on_4` → два ценовых amplifiers и CTA `price`; initial block
  `service` **не** подмешивается;
- context `service` → после двух amplifiers может добавиться `fact:free_implant_consult`,
  CTA `plan`.

Это **не** резервирует priority service promo до amplifiers и **не** соответствует
accepted Stage 5.1 contract.

#### Accepted Stage 5.1 behavior (current ONE_CALL runtime, `a268878`)

Post-Flash deterministic presentation / unified `PresentationResult` **реализуют**
**один** target order в production ONE_CALL path:

1. конкретный direct requested fact — **только** когда semantic seam достоверно доступен
   (не regex/keyword; без второго provider call);
2. обязательная priority service promo первого eligible service turn;
3. до двух amplifiers primary `scenario`;
4. остальные применимые facts в свободных местах общего лимита **3**;
5. CTA отдельно.

Priority promo резервируется **до** amplifiers и **не** вытесняется ими. Historical S21
**не** является current runtime owner; Stage 5.1 path заменил S21 для ONE_CALL sales-fast.

Missing optional external amplifier пропускается, но pack acceptance S3/S6 остаётся
обязательной. Missing local `fact:` по-прежнему fail-closed отклоняет bundle до
selector. Selector принимает shown snapshots, но не изменяет их.

### Priority promo authority (Stage 5.1 — принят)

**Принято:** нет одной «главной акции клиники»; authority — service-id mapping `priority_service_promos.<service_id>.ordered_fact_refs` + `promotion_overview.ordered_fact_refs` для general overview. Demo `marketing.yaml` уже содержит эти поля; runtime selector (`select_stage51_marketing`) использует target order.

**Historical S21/legacy config (не current Stage 5.1 authority):**

- `kind=promo` **недостаточно** для определения priority service promo;
- в demo `free_implant_consult` и discount facts одновременно имеют `kind=promo`;
- `initial_commercial_blocks.service.ordered_fact_refs` ставит consultation/installment **раньше** discount;
- discount fact также в `scenario_rules.cost.ordered_amplifier_refs`.

**Stage 5.1 runtime (принят):**

1. использует `priority_service_promos` service-id mapping и `promotion_overview`;
2. **не** определяет акцию по тексту, словам «скидка», проценту, fact ID, regex или Python hardcode;
3. сохраняет multiclient ownership;
4. **не** считает consultation/installment fallback для automatic promo;
5. validator проверяет refs, service IDs, применимость и отсутствие дублей.

### Offline evidence package S22

S22 связывает pure S10/S18/S21 boundaries для одной exact услуги. Builder сам вызывает
S10 и S21 с одним `service_id`, возвращает service со всеми authored offers и связанными
doctors, exact marketing selection, deep-detached selected commercial facts и отдельные
`kb:`/`doctor:` refs. Он не читает тела MD и не формирует текст ответа.

Automatic `consultation_value` ищется только по exact `selected_content_ref`, который
обязан принадлежать service или его option. Close добавляется отдельным полем только
когда ref ещё не показан и после S21 свободны одновременно marketing и amplifier slot;
он занимает ровно один slot каждого вида. Если любой лимит заполнен, value отсутствует,
ref показан или не выбран, close пропускается без замены данными другого документа.

Пакет имеет immutable shell/tuples и не меняет snapshots. Он не отмечает material
показанным, не применяет manual-contact/lead/refusal gates и не выбирает offers/doctors.
Все authored offers в S10 context сохраняют `active` и selection metadata; future
eligibility/strategy projection обязана выполняться отдельно до показа пациенту.

## Что не нужно делать сейчас

- наполнять demo десятками усилителей;
- создавать отдельную схему для каждой услуги и информационного подтопика;
- ротировать усилители на нейтральных follow-up ходах;
- добавлять готовые сценарные ответы или списки вступительных фраз;
- передавать product authority единому `PresentationResult` — **выполнено** Stage 5.1 (`a268878`);
- менять или перезапускать A9 raw/harness/live.

## Runtime status (post Stage 5.1)

Schema governance зафиксирован этим документом и
[`PRICE_SERVICE_ARCHITECTURE.md`](PRICE_SERVICE_ARCHITECTURE.md), demo policy
материализована offline в S20, pure selector — в S21 (historical offline), one-service
evidence package — в S22. **Stage 5.1 ONE_CALL product path принят:** unified typed
`PresentationResult`, `select_stage51_marketing`, session-global suppression, render-proven
shown-state, promotion scopes и authoritative promo rendering (`a268878`). Stage 5.1B
implementation **не** начата.

**Accepted evidence (Stage 5.1, `a268878`):** limits **3/2**; session-global suppression;
direct promotion scopes; authoritative promo rendering; render-proven shown-state;
`last_rendered_promo_fact_id`; price-follow-up shown fix; **0/1** provider calls.

**Remaining proof scope (не Stage 5.1):**

- Stage 5.1B availability/alternatives/price-gap matrix;
- Stage 5.2 Widget/SSE (double-response trace);
- Stage 5.3 frozen multiclient E2E;
- межклиентская изоляция и manual-contact boundary на полном E2E corpus.
