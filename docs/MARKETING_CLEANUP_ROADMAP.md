# Roadmap уборки маркетинга в ответах

Статус: документ для Cursor, без изменений runtime.

Цель: сделать маркетинг в ответах простым и управляемым. Бот должен отвечать как грамотный администратор клиники, а не как медицинский справочник и не как рекламный скрипт.

Главное правило:

```text
route/source -> главный источник текста -> главный источник кнопок-ссылок -> CTA отдельно -> максимум один текстовый marketing-смысл
```

LLM не решает, какой маркетинг добавить. LLM может только живо сформулировать уже выбранный факт/ингредиент.

## Термины

- **Текст ответа** - поле `answer`.
- **Кнопки-ссылки после ответа** - навигация под ответом. Технически сейчас это `quick_replies` и `meta.followups`.
- **`quick_replies`** - кнопки-ссылки в payload. Туда попадают md `suggest_refs`, PriceBook followups, patient options buttons, guided menu и alternatives.
- **`meta.followups`** - followup-кандидаты внутри текущей md-темы. Обычно собираются из md `suggest_h3`.
- **CTA-кнопка** - отдельная кнопка заявки/записи. Технически `payload.cta`.
- **Текстовый marketing-смысл** - короткий proof / consult reason / promo внутри `answer`.

## Что уже есть в коде

### 1. Content / база знаний

Путь для обычных md-ответов:

```text
LLM answer
  -> answer_slots
  -> answer_plan append
  -> numeric_fact_gate
  -> build_ask_response
  -> patient_playbook UI override
  -> policy
  -> normalize
```

Сверено с кодом:

- `chunk_responder.respond_from_chunk`
- `chunk_responder._apply_answer_slots_and_price_append`
- `core.answer_slots.assemble_answer_slots`
- `ux_builder.build_ask_response`
- `policy.apply_response_policy`
- `ux_builder.normalize_policy_payload`

Важно:

- `clinic_note`, `consult_value`, `promo_note` сейчас пришиваются как literal append.
- `consult_value` глушит только `consult_nudge` на md-chunk пути, но не весь consult-маркетинг.
- UI policy сейчас ограничивает кнопки, но не является полной source-priority policy.

### 2. Price / цены

Ценовой ответ не равен md-ответу с пришитой ценой.

Сверено с кодом:

- `ux_builder.build_price_lookup_payload`
- `core.price_offers.build_price_answer_for_lookup`
- `core.price_answer_assembler.assemble_price_answer`
- `core.price_answer_assembler.merge_price_quick_replies`
- `orchestration.price_flow`

Важно:

- На прямом вопросе про цену главным источником должен быть PriceBook.
- Price route может быть deterministic service reply или chunk через `price_ref` / `concern_ref`.
- Price-кнопки должны идти из PriceBook, а не из md.

### 3. Doctors / врачи

Сверено с кодом:

- `doctors_lookup.build_doctors_list_llm_question`
- `doctors_lookup.build_synthetic_doctors_list_chunk`
- `orchestration.catalog_flow.try_a3_doctor_route`

Важно:

- Врачебные md есть.
- Отдельных doctor followups в md сейчас нет.
- Doctor route может стать конверсионным мостом к цене услуги.

### 4. Patient options / "что мне подойдёт"

Сверено с кодом:

- `clients/{id}/patient_playbook.yaml`
- `core.patient_playbook`
- `orchestration.patient_playbook_flow`
- `chunk_responder._apply_patient_playbook_ui`

Важно:

- Этот слой уже есть.
- Не нужно создавать новый patient-options layer.
- Нужно только встроить его в общую policy: свои кнопки, свой CTA, без лишних consult-хвостов сверху.

### 5. Fallback / ingress

Сверено с кодом:

- `clients/{id}/ui.yaml`
- `core.clinic_policies_loader`
- `orchestration.pre_resolver_turn`
- `ux_builder.low_score_response`
- `ux_builder.no_candidates_response`

Важно:

- На fallback нельзя компенсировать слабый матч тяжёлым маркетингом.
- `low_score` сейчас маркетингово перегружен и требует cleanup.

## Целевая схема по ситуациям

### 1. Вопрос по базе знаний

Примеры:

- "Что такое All-on-4?"
- "Как проходит имплантация?"
- "Кому подходит?"

Текст:

- источник: md;
- LLM отвечает живо по фактам из md;
- это не готовая заготовка.

Где лежит:

- `clients/{id}/md/*.md`

Кнопки-ссылки:

- по умолчанию из md: `suggest_h3` / `suggest_refs`;
- если `suggest_refs` ведёт в price-ref, клик запускает price-сценарий.

CTA:

- md задаёт `cta_key`;
- текст кнопки и первый текст после клика берутся из `tone.yaml` / CTA registry;
- CTA выбирается отдельно от кнопок-ссылок.

Marketing:

- можно добавить 0-1 смысл из `marketing.yaml`: proof / consult reason / promo;
- LLM не выбирает этот смысл сама.

### 2. Вопрос "сколько стоит услуга?"

Текст:

- главный источник: PriceBook;
- цены, варианты, что входит, этапы оплаты, рассрочка/вычет/гарантия берутся из PriceBook/facts;
- обычно deterministic answer.

Где лежит:

- `clients/{id}/pricebook/services/*.json`
- `clients/{id}/pricebook/facts.json`

Кнопки-ссылки:

- из PriceBook;
- md followups не показывать.

CTA:

- отдельно по policy;
- не должен дублировать consult-хвост в тексте.

Если есть акция:

- цена + максимум одна акция;
- акция берётся из PriceBook/facts или `marketing.yaml`;
- акция показывается только если разрешена для `service_id` и route.

### 3. Вопрос "делаете ли услугу и сколько стоит?"

Пример:

- "Делаете All-on-4 и сколько стоит?"

Главный сценарий:

- Price.

Текст:

- коротко подтвердить услугу;
- дальше цена и состав из PriceBook.

Кнопки-ссылки:

- из PriceBook.

CTA:

- отдельно по policy.

Не делать:

- не смешивать md followups и price followups.

### 4. Вопрос по врачам

Примеры:

- "Кто делает импланты?"
- "Есть ли у вас имплантолог?"
- "Какой опыт у врачей?"

Текст:

- источник: doctor md / synthetic doctors JSON;
- LLM формулирует ответ по фактам;
- стаж, специализации и услуги не придумывать.

Где лежит:

- `clients/{id}/md/doctors__doctor__*.md`

Кнопки-ссылки:

- doctor md не обязан хранить followups;
- будущая policy может добавить 0-1 service-related ссылку, если понятен `service_id` / topic.

Пример:

```text
Вопрос: "Кто делает All-on-4?"
Кнопка-ссылка: "Стоимость All-on-4"
Клик -> price_lookup по service_id=all_on_4
```

CTA:

- "Записаться к специалисту" / "Записаться на консультацию";
- текст после клика берётся из `tone.yaml`.

Не делать:

- не добавлять второй consult closer из global prompt / consult_nudge;
- не показывать пачку md/price кнопок.

### 5. Вопрос "нет зуба / нет всех зубов / что посоветуете?"

Главный сценарий:

- Patient options.

Текст:

- варианты выбираются deterministic из `patient_playbook.yaml`;
- LLM формулирует живой обзор вариантов;
- бот не ставит диагноз и не выбирает "единственно правильное" лечение.

Где лежит:

- `clients/{id}/patient_playbook.yaml`
- `service_catalog.json`
- PriceBook/facts для кратких фактов по вариантам

Кнопки-ссылки:

- из patient options;
- например "Стоимость All-on-4", "Стоимость All-on-6", "Съёмные протезы";
- клик по цене запускает price-сценарий.

CTA:

- отдельно по policy;
- например "Подобрать вариант на консультации".

Не делать:

- не добавлять сверху отдельный `consult_nudge`;
- не показывать md followups параллельно.

### 6. Вопрос-сравнение

Примеры:

- "Чем All-on-4 отличается от All-on-6?"
- "Имплант или мост?"
- "Классическая или одномоментная имплантация?"

Главный сценарий:

- Content.

Текст:

- источник: comparison md;
- LLM отвечает по фактам сравнения.

Где лежит:

- `clients/{id}/md/comparison__*.md`

Кнопки-ссылки:

- из comparison md;
- если есть ссылка на цену, клик запускает price-сценарий.

CTA:

- отдельно по policy.

Не делать:

- не превращать сравнение в ценовой ответ, если цену не спрашивали.

### 7. Прямой вопрос про акции

Примеры:

- "Есть акции?"
- "Есть скидка на All-on-4?"

Статус:

- важная тема;
- сейчас разрозненно: md `promo_note`, PriceBook promo, facts.

Нужно:

- единый promo-сценарий через `marketing.yaml`;
- показывать только активные акции;
- привязка к `service_id`;
- запреты на чувствительные темы.

Кнопки-ссылки:

- если акция про конкретную услугу, можно дать price-ссылку по этой услуге.

CTA:

- отдельно по policy.

## Что уже закрыто, частично закрыто, нужно добавить

### Уже закрыто. Не усложнять.

- Обычные вопросы по услугам: md.
- Сравнения: comparison md.
- Боль / страх / безопасность / противопоказания: md. Promo тут запрещать.
- Врачи: doctor md есть, сложную doctor-систему не делать.
- Patient options: слой уже есть через `patient_playbook.yaml`.
- Плюсы клиники / "почему выбрать вас": пока через md, отдельный proof-layer сейчас не раздувать.

### Есть частично

- Цены и "что входит": PriceBook есть, но нужно жёстче отделить price кнопки от md кнопок.
- Рассрочка / вычет / гарантия: есть в facts и md; главный источник лучше PriceBook/facts.
- CTA: есть через `cta_key` + `tone.yaml`; нужна policy, чтобы не дублировал consult в тексте.
- Fallback тексты: есть, но `low_score` нужно смягчить.
- Акции: есть кусками, нужен единый управляемый слой.

### Реально добавить сейчас

1. **Promo-сценарий / акции**
   - через `marketing.yaml`;
   - по `service_id`;
   - можно показывать в content и price, если разрешено;
   - не показывать на pain/safety/contraindications/fallback;
   - не повторять каждый ход.

2. **Doctor -> price мост**
   - если вопрос про врачей связан с услугой, добавить 0-1 кнопку-ссылку на цену;
   - пример: "Стоимость All-on-4";
   - клик запускает price-сценарий.

3. **Единая UI-policy**
   - content -> md кнопки;
   - price -> PriceBook кнопки;
   - doctors -> 0-1 service-related ссылка + CTA;
   - patient options -> options кнопки;
   - fallback -> минимум навигации.

4. **Лимит текстового маркетинга**
   - максимум один proof / consult reason / promo в `answer`;
   - не несколько консультационных хвостов.

5. **`marketing.yaml`**
   - активные акции;
   - разрешённые `service_id`;
   - запреты по aspect/route;
   - clinic proof / consult reasons как сырьё;
   - cooldown.

### Не добавлять сейчас

- Синхронизацию с расписанием / ближайшие слоты.
- Отзывы, кейсы, фото работ.
- Большой отдельный proof-layer поверх md.
- Сложную модель "готовности к заявке" или эмоциональный скоринг.

## Где что должно храниться

| Место | Что хранит | Что не должно хранить |
|---|---|---|
| `md/` | суть услуги, FAQ, сравнения, врачи, контакты | одинаковые consult/promo хвосты в каждом документе |
| `service_catalog.json` | aliases, `service_id`, связь с md/pricebook | длинный маркетинг |
| `pricebook/services/*.json` | суммы, варианты, что входит/не входит, price followups | объяснения услуги как в md |
| `pricebook/facts.json` | рассрочка, вычет, гарантия, финансовые/коммерческие факты | длинные рекламные абзацы |
| `tone.yaml` | CTA registry и тексты lead-flow | route-level marketing policy |
| `ui.yaml` | guided/fallback тексты | тяжёлый маркетинг на failure path |
| `clinic_policies.yaml` | что клиника не делает, альтернативы, hard stops | общие акции и consult rules |
| `marketing.yaml` | promo rules, limits, cooldown, proof/reason сырьё | медицинскую базу знаний и цены |

## Черновая структура `marketing.yaml`

Это ориентир, не финальный контракт.

```yaml
version: 1

limits:
  max_text_ingredients: 1
  max_cta: 1
  promo_cooldown_turns: 3
  proof_cooldown_turns: 3

blocked_aspects_for_promo:
  - pain
  - contraindications
  - safety
  - complications

service_marketing:
  all_on_4:
    clinic_proof:
      - "3D-планирование по КТ"
      - "временный протез в день операции"
    consult_reasons:
      - "оценить объём кости по КТ"
      - "сравнить All-on-4 и All-on-6"
    primary_cta_key: plan

promos:
  free_implant_consult:
    active: true
    active_until: "2026-12-31"
    fact_ref: free_implant_consult
    allowed_service_ids:
      - all_on_4
      - all_on_6
      - classic
    allowed_routes:
      - retrieval_chunk
      - catalog_md_first
      - price_lookup
    allowed_aspects:
      - overview
      - benefits
      - comparison
    blocked_aspects:
      - pain
      - contraindications
      - safety
    cta_key: consult
```

## Порядок внедрения без большого взрыва

### Шаг 1. Наблюдение и telemetry

Не менять поведение. Сначала фиксировать:

- route/source;
- выбранный источник текста;
- источники `quick_replies`;
- источники `meta.followups`;
- CTA source;
- какие текстовые хвосты были добавлены.

### Шаг 2. Единая UI-policy

Цель: один route -> один главный источник кнопок-ссылок.

Применять и к chunk payload, и к service_reply payload.

### Шаг 3. Loader для `marketing.yaml`

Добавить чтение файла, но пока использовать мягко:

- promo rules;
- blocked aspects;
- service-level ingredients;
- cooldown.

### Шаг 4. Лимит текстового маркетинга

Ввести turn-level решение:

```text
0-1 text ingredient: clinic_proof / consult_reason / promo_fact
```

Записывать в telemetry, что добавлено и что подавлено.

### Шаг 5. Promo-сценарий

Первый реально полезный новый слой:

- прямой вопрос про акции;
- promo на content-ответах по разрешённым `service_id`;
- promo на price-ответах;
- запреты на чувствительных темах.

### Шаг 6. Doctor -> price мост

Если doctor route связан с услугой:

- добавить 0-1 price-ссылку;
- клик запускает price route;
- не смешивать с пачкой md/price кнопок.

### Шаг 7. Мягкая миграция старых хвостов

Постепенно:

- `clinic_note` -> `clinic_proof`;
- `consult_value` -> `consult_reason`;
- `promo_note` -> promo rule;
- PriceBook closer -> price policy / facts;
- consult_nudge -> подчинить единому consult bridge.

### Шаг 8. Cleanup fallback

Смягчить:

- `low_score`;
- `no_candidates`;
- service_not_offered, если там лишний consult push.

## Итоговое решение

Новый слой нужен не для новых ответов. Он нужен, чтобы уже существующие ответы не спорили друг с другом.

Фокус текущего cleanup:

1. акции как управляемый сценарий;
2. doctor -> price мост;
3. единая policy для кнопок;
4. лимит текстового маркетинга;
5. постепенная миграция старых literal-хвостов.

Не фокус сейчас:

- расписание;
- отзывы/кейсы;
- сложный proof-layer;
- эмоциональный lead scoring.

