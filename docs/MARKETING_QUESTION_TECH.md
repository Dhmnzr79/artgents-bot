# Технический слой маркетинговой карты

**Статус:** парный документ к [`MARKETING_QUESTION_FOUNDATION.md`](MARKETING_QUESTION_FOUNDATION.md), синхронизирован с target-контрактом 17 июля 2026 года.
**Для кого:** разработка, Cursor — маршруты, источники, операции пайплайна.
**Не является:** маркетинговым описанием экрана; текстом ответов.

Нумерация разделов совпадает с foundation. Колонка **«На экране»** там; здесь — **«Технически»**.

Target-контракт лимитов, сценариев, усилителей, CTA и session state: [`MARKETING_SCENARIO_ARCHITECTURE.md`](MARKETING_SCENARIO_ARCHITECTURE.md). Этот документ показывает места интеграции и честно отделяет требуемое поведение от текущего runtime.

## Обязательные продуктовые требования

Этот раздел описывает **требуемое поведение**, а не утверждает, что оно уже полностью реализовано в текущем runtime.

1. **Authority базы над содержанием ответа.** Согласованные md, pricebook, marketing и policies конкретной клиники определяют факты и силу утверждений. Это не связано с запрещённой product authority A9 `patient_scope`: A9 остаётся shadow-only и не управляет ответом.
2. **Запрет семантического смягчения.** Composer может добавлять только связующий текст. Числа, проценты, модальность, гарантии, обещания, отрицания и оговорки источника должны сохраняться точно; будущая проверка должна обнаруживать их ослабление, усиление или подмену.
3. **Единый marketing-fact limit.** В ответе максимум три marketing facts, из них максимум два усилителя. Основной ответ, price/service cards, CTA и follow-up не считаются слотами.
4. **Eligibility и cadence.** Селектор использует только активные и применимые source-owned facts. Session-global suppression: один `fact_id` автоматически показывается один раз за `session_id`; `shown_amplifier_ids` подавляют повтор amplifiers. Прямой promotion request (`commercial_intent=promotion`, `promotion_scope=shown`) повторяет последнюю rendered promo session (suppression bypass only).
5. **CTA cadence независима.** Одна основная CTA может появляться после каждого содержательного коммерчески релевантного ответа и не блокируется показанными marketing facts.
6. **Structured scenario (ONE_CALL).** Flash envelope несёт **один** primary `scenario` (`pain_fear` | `cost` | `time` | `doctor_trust` | `result_reliability` | `none`). Исторический `marketing_scenarios` 0–2 — legacy/offline, не текущий ONE_CALL envelope. Общий flow задаёт порядок смысловых операций, но не готовые фразы.
7. **Priority service promo и promotion intent.** Post-Flash deterministic `PresentationResult` владеет priority service promo (`priority_service_promos`), `commercial_intent=promotion`, closed `promotion_scope` (`none` \| `general` \| `service` \| `shown`) и session-global suppression; модель не придумывает точные условия акции.
8. **Manual-contact boundary.** В обычном диалоге любая текущая личная боль, активное осложнение после лечения, жалоба, спор или отзыв, требующий реакции, должны завершаться до marketing/retrieval/composer/UI-policy и возвращать только фиксированный шаблон с номером из client config. Явно выбранный `situation_intake` — отдельный conversion state: он не генерирует ответ и сохраняет любое стоматологическое описание как lead note.
9. **Отзывы разделяются по смыслу.** Обычный вопрос о том, где посмотреть отзывы, остаётся content/trust-вопросом. Негативный отзыв или претензия включают manual contact.

Точный требуемый manual-contact шаблон:

> Чтобы вам быстрее помогли, пожалуйста, свяжитесь с администратором клиники. Если вопрос срочный, лучше сразу позвоните: **[номер клиники]**.

После шаблона запрещены свободная генерация, CTA, акция, quick replies, видео, situation-кнопка и дополнительные рекомендации.

---

## Легенда

### Источник данных

| Код | Откуда |
|---|---|
| `comparison` | `comparison__*.md` (5 в demo) |
| `service` / `info` / `faq` | md-документы клиента |
| `clinic` | `clinic__info__*.md`, doctors md |
| `pricebook` | `pricebook/services/*.json` |
| `marketing` | `clients/<client_id>/target_response/marketing.yaml` |
| `clinic_policies` | `clinic_policies.yaml` |
| `policy` | ingress, playbook, lead, шаблоны |
| `fallback` | guided-меню, переспрос |

### Операции

| Операция | Суть |
|---|---|
| `retrieval` → `composer` | Поиск md, сборка ответа |
| `catalog` | Fast-path через `service_catalog.json` |
| `price_route` | Матч услуги → карточка(и) pricebook |
| `price_unavailable` | Услуга без `price_key` → сниппет + шаблон |
| `group_overview` | Общий ценовой запрос → несколько карточек |
| `clarify` | `needs_clarify`, `build_clarify_payload` |
| `continuation_clarify` | Меню без контекста |
| `carry` | `dialog_focus`, `last_subject`, session |
| `playbook` | `patient_situation` |
| `comparison_route` | `query_mode=comparison`, skip catalog |
| `composite` | `is_composite_question`, 2+ аспекта |
| `not_offered` | `clinic_policies` + альтернатива |
| `marketing_scenario_policy` | Target: priority promo → scenario amplifiers → eligibility/no-repeat → общий лимит 3/2 |
| `lead_flow` | Имя → телефон → demo-msg |
| `handoff_template` | Фиксированный шаблон §10 |
| `policy_ui` | CTA, `suggest_h3`, video, situation |

**Порядок (упрощённо):** ingress / resolver → маршрут (catalog | price | composer | playbook | lead) → сборка текста → `policy_ui`.

### Контекст (как в foundation)

| Код | Значение |
|---|---|
| `standalone` | Хватает одного сообщения |
| `carry` | Нужен предыдущий ход |
| `clarify` | Переспрос по оси услуга / масштаб / этап |

---

## 1. Обычные вопросы по базе знаний

| Подтип | Технически | Контекст |
|---|---|---|
| Что это за услуга | `service`/`faq` → `retrieval` → `composer`; `policy_ui`: CTA `plan`, `suggest_h3` | `standalone` |
| Как проходит лечение | `service`/`info` → `retrieval` → `composer`; `suggest_h3`, CTA `plan` | `standalone` / `carry` |
| Вопрос о направлении | `catalog` или `retrieval` → `composer`; + `price_route` если цена | `standalone` |
| Клиника и доверие | `clinic` → `retrieval` → `composer`; CTA `booking`/`callback` | `standalone` |

---

## 2. Цены

| Подтип | Технически | Контекст |
|---|---|---|
| Простая цена | `price_route` → 1 карточка; CTA `price`; price UI без `suggest_h3` | `standalone` / `carry` |
| Сложная цена | `price_route` → N карточек; pricebook `followups` | `standalone` / `carry` |
| Слишком общий вопрос | `group_overview` или `clarify` | `standalone` |
| Цена по ситуации | `playbook`/`carry` → `price_route`; иначе `clarify` | `standalone` |
| Что дешевле | `price_route` (бренды одной услуги); иначе `clarify` | `standalone` |
| Состав цены | `faq`/`service` → `retrieval` → `composer`; pricebook `followups` | `standalone` / `carry` |
| Услуга есть, цены нет | `price_unavailable`: service-md сниппет + шаблон; `suggest_refs` опц. | `standalone` |

---

## 3. Сравнение методов

### 3.1. Три ситуации по материалу

| Ситуация | Технически |
|---|---|
| **A. Есть comparison-док** | `comparison` → `comparison_route` → `retrieval` → `composer`; CTA `consult` |
| **B. Два service-дока** | `service` ×2 → `retrieval` → `composer`; `clarify` опц. |
| **C. Одна сторона в базе** | `retrieval` 1 md → `composer`; CTA `consult`/`booking` |

### 3.2. Прочие подтипы

| Подтип | Технически |
|---|---|
| Сравнение по ситуации | `playbook` / `comparison_route` → `composer`; `clarify`/`suggest_h3` |
| Нелогичное сравнение | Шаблон + `clarify`; без `price_route` |

---

## 4. Врачи

| Подтип | Технически |
|---|---|
| Команда | `clinic`/doctors overview → `retrieval` → `composer`; CTA `booking` |
| Кто делает услугу | doctors md → `retrieval`; CTA `doctor` |
| Конкретный врач | doctors md по имени; doctor UI (без follow-up md) |

---

## 5. Акции, скидки и способы сэкономить

| Подтип | Технически |
|---|---|
| Какие акции сейчас | `commercial_intent=promotion`, `promotion_scope=general` → до 3 active promo по `promotion_overview.ordered_fact_refs`; **не** открывает price amount/card |
| Акция на услугу | `commercial_intent=promotion`, `promotion_scope=service` + authoritative `service_id` → одна promo из `priority_service_promos[service_id]` |
| Акция ещё действует | `commercial_intent=promotion`, `promotion_scope=shown` → repeat last rendered session promo; fail closed без session-bound promo |
| Как сделать дешевле | `retrieval` clinic md + `price_route`; `marketing` опц. |
| Условия оплаты | `clinic__info__payment_terms` → `composer`; `suggest_h3`, CTA `callback` |
| Скидка у врача | `marketing.yaml`; без персональных скидок |

**Текущий долг / Stage 5.1 (implementation не начата):** частичные selector/schema/session pieces существуют,
но единый `PresentationResult` **ещё не создан** и current selector/presentation **не
объявлены принятыми** Stage 5.1. Historical offline S21 **does not satisfy** accepted
target order (amplifiers before initial block; no priority promo reservation). Runtime
ещё не реализует полный contract: `commercial_intent=promotion`, `promotion_scope`,
`priority_service_promos` / `promotion_overview`, session-global suppression, priority service promo на первом eligible service turn,
лимит 3/2 с promo в **3** не в **2**, `shown_amplifier_ids`, incompatibility,
render-proven shown-state и один primary `scenario` из ONE_CALL envelope.

**Stage 5.1 implementation потребует (docs amendment зафиксировал target, код ещё нет):**

1. Envelope contract/version update: `commercial_intent` → 5 значений; новое поле `promotion_scope`;
2. Parser/schema/prompt update; cached-prefix identity/invalidation review;
3. Client config migration: `priority_service_promos`, `promotion_overview` (current `initial_commercial_blocks` — pre-Stage-5.1);
4. Offline regression + отдельный Checker acceptance;
5. **Без** regex/keyword classifier, **без** второго provider call, **без** `promotion_ref`.

**Performance invariant (Stage 5.1):** 0/1 provider calls; selector/`PresentationResult`
локально после Flash; без marketing LLM/retry/второй materialization/сетевого re-read
marketing data на каждом turn; один локальный presentation pass; gates 8s/10s/6s не
ослабляются; diagnostics OK, новый hard ms-SLO — только по owner decision.

Это меняется только отдельной code/runtime-задачей с тестами.

---

## 6. Запись и контакт

| Подтип | Технически |
|---|---|
| Простая запись | booking-intent → `lead_flow`; CTA `booking` |
| Запись на дату/время | Полное пожелание в session; `lead_flow`; мягкий defer-шаблон передаёт его администратору, без намёка на принятый/согласованный слот |
| Запись к врачу | Врач в session → `lead_flow`; CTA `doctor` |
| Обратный звонок | contacts md или `lead_flow` `callback` |
| Передумал | Сброс lead-state |

---

## 7. Ситуация пациента

| Механизм | Технически |
|---|---|
| Playbook | `playbook` → опции; + `price_route` |
| «Рассказать о ситуации» | `situation_allowed` + `policy_ui` → `lead_flow` |

### 7.1. Playbook

| Подтип | Технически |
|---|---|
| Отсутствующие зубы | `playbook` + `price_route` |
| Вся челюсть | `playbook` + `retrieval`; CTA `consult`/`plan` |
| Имплант уже стоит | `carry`/`catalog` → `price_route` |
| Мало кости | `info`/`comparison` → `composer`; CTA `consult` |

### 7.2. «Рассказать о ситуации»

| Условие | Технически |
|---|---|
| Материал разрешает, есть слот | `situation_allowed` + `policy_ui` |
| Клик | Отдельный `situation_intake` state до FullContext → заметка в session → `lead_flow` |
| Любое стоматологическое описание внутри intake | Сохранить user-authored note → `lead_flow`; не вызывать retrieval/composer, не генерировать content-ответ и не переразбирать медицинскую тему |
| Минимальный anti-spam | Детерминированно: длина, empty/short, link-only, очевидный мусор, общий rate limit; один retry |
| Выход | До note — `situation_action=back`; после note — обычный cancel lead-flow |
| Конкуренция слота | video / `suggest_h3` приоритет |

**Target contract:** `situation_intake` не является разновидностью FullContext и не
должен отправлять введённый текст в composer. Это явный conversion state после диалога,
поэтому ситуация, страх, боль, цена, жалоба и прошлый опыт внутри него идут в lead note,
а не возвращаются в тематический routing. Вне этого state продолжают действовать обычные
hard-stop и marketing rules. Реализация и parity текущего runtime принимаются только
отдельным code/runtime TASK; этот документ сам по себе поведение не переключает.

---

## 8. Страх, боль и восстановление

| Подтип | Технически |
|---|---|
| Страх перед лечением | `faq` pain → `composer`; video; CTA `consult` |
| Страх неприживления | `faq` osseointegration, `empathy_enabled`; `suggest_h3` |
| Общее/будущее восстановление | `info` aftercare → `composer`; `suggest_h3` |
| Текущая личная боль | `manual_contact` boundary до marketing/retrieval/composer |
| Сравнение боли | `faq`/`service` → `composer` |

Требование: общий вопрос о будущей боли/страх лечения может дать `pain_fear`; любая текущая личная боль не оценивается по срочности и уходит в manual contact. Для marketing scenario действует общий selector 3/2, а не отдельный тематический promo-route.

---

## 9. Безопасность и противопоказания

| Подтип | Технически |
|---|---|
| Заболевания | `info` contraindications → `composer`; по требованию релевантное промо разрешено |
| Возраст, курение | `info`/`faq` → `composer` |
| Факт приживаемости | `faq` osseointegration → `composer` |
| Риск и гарантии | `faq` + `clinic` warranty; CTA `consult` |
| Гарантия клиники | `clinic__info__warranty` → `composer` |

Один md `osseointegration` для факта и страха — разные chunk/H3 по retrieval.

---

## 10. Срочный вопрос, жалоба и ручной контакт

Этот boundary применяется к обычному диалогу. После явного входа в `situation_intake`
действует отдельный conversion contract §7.2.

| Подтип | Технически |
|---|---|
| Любая текущая личная боль / активное осложнение после лечения / жалоба / спор / негативный отзыв в обычном диалоге | Boundary до marketing/retrieval/composer; только фиксированный шаблон и телефон из `clinic` config; без любого UI |
| Вопрос «где посмотреть отзывы?» | Обычный content/trust path; не `manual_contact` |

Текущий runtime уже использует `manual_contact` до основного ответа и не добавляет CTA, но текст шаблона отличается от согласованного. Замена шаблона и проверка классификации — отдельная code/runtime-задача.

---

## 11. Услуги, бренды и условия, которых нет (Stage 5.1B target)

Канон: [`ONE_CALL_CACHED_FULLCONTEXT_ARCHITECTURE_LOCK.md`](ONE_CALL_CACHED_FULLCONTEXT_ARCHITECTURE_LOCK.md) §11.1, [`PRICE_SERVICE_ARCHITECTURE.md`](PRICE_SERVICE_ARCHITECTURE.md). Implementation **не** начата.

| Подтип | Технически |
|---|---|
| Not-offered, no alt | `known_not_offered` (`active=false`); `approved_text` / policy; **no** price_route, price card, promo |
| Not-offered + authored alt | `service_alternatives[requested_service_id].alternative_service_ids`; alt content/price from own sources; alt buttons → secondary slots |
| Price → unavailable | availability answer, not `no_public_price` mask |
| Price → unavailable + alt | not-offered + alt offers; alt price labelled as other service |
| Offered + `no_public_price` | `price_route` → `approved_text` only; no amount/card; family price forbidden as service price |
| Named service + family-only | `target_family_price_resolution` data_gap today; target: optional explicit family context only |
| Unresolved term | `unresolved`; safe clarify; no confident not-offered |
| Нет бренда | brand seam (S24/S25); **not** service alternative |
| Политика клиники | `clients/<client_id>/clinic_policies.yaml` template |

**Current legacy seam:** `clinic_policies.yaml` → `service_alternatives` with `match_keywords` / `mention` / `suggest_ref` / `note` — keyword-based, pre-Stage-5.1B.

**Price precedence:** exact offer → `no_public_price` → explicit family context → data-gap.

**Promotion interaction:** unavailable: no priority promo; alt promo not automatic; `commercial_intent` / `promotion_scope` gates preserved.

≠ §2 `price_unavailable`: там `offered` service без публичной цены.

---

## 12. Непонятный запрос, off-topic и spam

| Подтип | Технически |
|---|---|
| Пустой / короткий | policy шаблон + меню |
| Ничего не найдено | `fallback` guided-меню |
| Off-topic | ingress off-topic шаблон |
| Повтор / spam | policy шаблон |

---

## 13. Многоходовые цепочки

| Сценарий | Технически | Контекст |
|---|---|---|
| Услуга → цена | `carry` → `price_route` | `carry` |
| Услуга → сроки | `carry` → `retrieval` service-md | `carry` |
| Общий → цена | `group_overview` / `clarify` | `clarify` |
| Цена без контекста | `continuation_clarify` | `clarify` |
| Ситуация → цена | session → `price_route` | `carry` |
| Короткое продолжение | `carry` → `dialog_focus` | `carry` |

---

## 14. Составные вопросы в одном сообщении

| Подтип | Технически |
|---|---|
| Услуга + цена | `composite`: catalog/`retrieval` + `price_route` |
| Цена + боль | `composite`; по требованию релевантное промо разрешено с общей session-cadence |
| Два факта | `composite`: 2 md-chunk |
| Сравнение + цена | `composite` + `comparison_route` + price |

Риск: `is_composite_question` не ловит все формулировки.

---

## 15. Редкие вопросы (edge FAQ)

| Пример | Технически |
|---|---|
| «Может ли имплант повредить нерв?» | `retrieval` miss → §12 `fallback` |
| «Второе мнение с чужим планом?» | Нет md → `fallback` |
| «Удалять или лечить — кому верить?» | miss → `composer`/fallback |

План базы: `clinic__faq__edge_cases.md` — пока не в demo.

---

## Текущее состояние и обязательные расхождения

1. `retrieval` / `composer` / `price_route` — основные пути контента.
2. `policy_ui` решает, показать ли CTA и follow-up.
3. `clarify` — только услуга / масштаб / этап.
4. Текущий promo-блок требуется заменить единым `PresentationResult` и source-owned selector из `MARKETING_SCENARIO_ARCHITECTURE.md`: priority service promo, eligibility, лимит 3/2 (promo в **3**, не в **2**), no-repeat, direct-question override, incompatibility, render-proven shown-state.
5. Текущий composer/verifier требуется отдельно проверить на точное сохранение силы согласованных утверждений.
6. Demo: `lead_flow` не шлёт в CRM.
7. `handoff_template` (§10) уже исключает retrieval и CTA, но должен получить новый согласованный текст и строгую границу для любой текущей личной боли.
8. `comparison_route` — catalog fast-path не перебивает comparison-md.
9. **Stage 5.1 не реализован:** docs-only promotion intent amendment зафиксировал contract; implementation unit ещё должна создать `PresentationResult`, обновить envelope/parser/prompt и принять post-Flash deterministic presentation.
10. **Stage 5.1B не реализован:** docs-only service availability / alternatives / price gaps amendment зафиксировал contract §11.1; implementation должна мигрировать `service_alternatives` на canonical IDs, реализовать price precedence и 7-case matrix в `PresentationResult`; current keyword legacy и safe `data_gap` — pre-target seams.

### Target service consultation close

S18 добавляет только offline source contract. Optional `consultation_value` находится в
frontmatter того же service MD, исключён из общего FullContext body и разрешается exact
lookup по выбранному service/option `content_ref`. Он не является H3, CTA, готовой
репликой, новым retriever или отдельным тематическим route.

Будущий runtime передаёт выбранное значение как `consultation_close`, автоматически
использует exact document ref максимум один раз на `client_id + session_id` и отмечает
shown-state только после фактического вывода. Автопоказ занимает один marketing slot и
один amplifier slot; при заполнении любого лимита пропускается. Прямой вопрос о
консультации остаётся основным content вне automatic slots. S18 не реализует selection,
session, composer placement или authority.

---

## Что дальше

1. Target schema услуг/цен и marketing policy зафиксирована в
   [`PRICE_SERVICE_ARCHITECTURE.md`](PRICE_SERVICE_ARCHITECTURE.md) и
   [`MARKETING_SCENARIO_ARCHITECTURE.md`](MARKETING_SCENARIO_ARCHITECTURE.md); runtime
   пока не мигрирован на принятый Stage 5.1 `PresentationResult` и promotion intent.
2. Stage 5.1 implementation: envelope/parser/prompt/cache migration для `commercial_intent=promotion` и `promotion_scope`; client config migration на `priority_service_promos` / `promotion_overview`. Без regex/keyword classifier, без второго provider call.
3. Stage 5.1B implementation: `service_alternatives` ID migration; availability/price-gap matrix §11.1; family price explicit-context only; unified `PresentationResult`. Без regex/keyword classifier, без второго provider call.
4. Performance invariant §13.7: 0/1 calls, local presentation pass, no marketing LLM.
5. S18 отдельно материализует offline source contract для `consultation_value`; demo
   content, session/runtime wiring и authority остаются будущими checkpoint-ами.
6. Сверить с foundation «На экране» в виджете и отметить расхождения маршрут ↔ UI.
7. Regression будущей реализации должен доказать priority promo, promotion scopes, session-global suppression,
   Stage 5.1B availability/price-gap matrix, direct-question override, межклиентскую изоляцию, hard-stop и точность source-owned facts.
