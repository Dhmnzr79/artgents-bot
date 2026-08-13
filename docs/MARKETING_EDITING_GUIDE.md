# Как редактировать маркетинг клиента

**Статус:** current demo target_response config + authoring guide; не заявляет, что Stage 5.1 runtime уже реализован.

Короткая памятка для demo-клиента и будущих паков. Канон demo target policy на дату:
`clients/demo/target_response/pricebook/facts.json` + `clients/demo/target_response/marketing.yaml`.

Текущий runtime ещё блокирует promo на `pain/safety/contraindications`. Это честное
описание старого кода, а не правило будущей архитектуры. Target-разделение находится в
[`MARKETING_SCENARIO_ARCHITECTURE.md`](MARKETING_SCENARIO_ARCHITECTURE.md) и
[`ONE_CALL_CACHED_FULLCONTEXT_ARCHITECTURE_LOCK.md`](ONE_CALL_CACHED_FULLCONTEXT_ARCHITECTURE_LOCK.md):
текущая личная боль/осложнение/жалоба дают phone-only hard-stop, а общий страх будущего
лечения или вопрос о противопоказаниях может получить source-grounded ответ и применимый
marketing layer.

**Этот docs sync не меняет actual client config.**

## Быстрая карта

| Хочу поменять | Открыть файл |
|---|---|
| Цена услуги | `clients/demo/target_response/pricebook/services/*.json` |
| Что входит в цену / этапы оплаты | `clients/demo/target_response/pricebook/services/*.json` |
| Акция, скидка, рассрочка, вычет, гарантия — **текст и условия** | `clients/demo/target_response/pricebook/facts.json` |
| Порядок, ссылки, лимиты, scenario pools, service promo mapping, overview list, CTA context keys | `clients/<client_id>/target_response/marketing.yaml` → `limits`, `priority_service_promos`, `promotion_overview`, `scenario_rules`, `cta_contexts` |
| Текст CTA-кнопки и первый вопрос после клика | `clients/demo/tone.yaml` |
| Видео | `clients/demo/video_catalog.yaml` |
| Текст меню или fallback | `clients/demo/ui.yaml` |
| Услугу не оказываем / ОМС / альтернатива | `clients/demo/clinic_policies.yaml` |
| Содержание услуги, FAQ, медицинские пояснения | `clients/demo/md/**` |

## Разделение ownership

| Слой | Что хранит |
|---|---|
| `facts.json` | Фактический текст акции/рассрочки/гарантии, active dates, `allowed_service_ids`, `incompatible_with` |
| `marketing.yaml` | `priority_service_promos` (service_id → ordered promo refs), `promotion_overview` (general list), scenario amplifier pools, лимиты **3/2**, CTA context keys; **не** дублирует текст факта |
| `tone.yaml` | Видимый copy CTA и lead-flow |
| `video_catalog.yaml` | Тематические ролики для secondary UI slot |

LLM **не** выбирает точную акцию и **не** генерирует её условия. Priority service promo
и promotion surfaces выбираются детерминированным post-Flash кодом по `priority_service_promos`
и `promotion_overview` — **не** по тексту, проценту или regex.

## Канон акций demo (2026-07-10)

| ID | Тип | Суть |
|---|---|---|
| `free_implant_consult` | promo | Бесплатная консультация (имплантация + протезирование), до 31.12.2026 |
| `implant_same_day_discount` | promo | Скидка до 15% в день обращения (все виды имплантации) |
| `professional_whitening_discount` | promo | Скидка 10% на отбеливание до 15.08.2026 |
| `installment_12` | payment | Рассрочка на имплантацию и протезирование до 12 мес. |
| `tax_deduction` | benefit | Налоговый вычет 13% |
| `implant_warranty` | warranty | Гарантии на работу и импланты |

**`marketing.yaml` target schema (future, implementation pass):** `priority_service_promos`,
`promotion_overview`, `scenario_rules`, `limits`, `cta_contexts`. Current demo still uses
historical `initial_commercial_blocks` — pre-Stage-5.1, требует migration. Старый `promo_rules` в текущем target pack **не используется**.

Известный current-runtime долг: `free_implant_consult` с `kind: promo` блокируется на pain/safety. Не исправлять это старым тематическим route; будущая реализация следует общей target policy.

## Правило про facts и marketing

`target_response/pricebook/facts.json` — **что правда?**

Примеры:

- «Скидка 10% до 15 августа.»
- «Рассрочка на имплантацию и протезирование до 12 месяцев.»
- «Можно оформить налоговый вычет 13%.»

`target_response/marketing.yaml` — **когда, для какой услуги и в каком порядке это можно показывать?**

Примеры (target, после migration):

- `priority_service_promos.all_on_4.ordered_fact_refs` — promo и порядок для конкретной услуги;
- `promotion_overview.ordered_fact_refs` — порядок общего списка «Какие акции есть?» (до 3);
- `scenario_rules.<scenario>.ordered_amplifier_refs` — pool усилителей;
- `limits.max_marketing_facts_per_turn: 3`, `max_amplifiers_per_turn: 2`;
- `cta_contexts` — выбор CTA key по semantic context.

Один и тот же fact может присутствовать в service mapping и overview. `initial_commercial_blocks` **не** является новым promo authority.

Текст акции **не** дублировать в `marketing.yaml` — только правила, порядок и ссылки.

## Как добавить новую акцию

1. Факт в `clients/<client_id>/target_response/pricebook/facts.json`.
2. `fact_refs` в `clients/<client_id>/target_response/pricebook/services/{service_id}.json`.
3. Ссылку и порядок в `clients/<client_id>/target_response/marketing.yaml` → `priority_service_promos.<service_id>` и/или `promotion_overview` и/или `scenario_rules`.
4. Не дублировать текст акции в `md/**` (кроме нейтральных условий оплаты в `payment_terms`).

Мини-пример (отбеливание):

```json
"professional_whitening_discount": {
  "id": "professional_whitening_discount",
  "kind": "promo",
  "text_fact": "Сейчас на профессиональное отбеливание действует скидка 10% до 15 августа.",
  "render_mode": "strict",
  "active": true,
  "allowed_service_ids": ["professional_whitening"],
  "incompatible_with": [],
  "active_until": "2026-08-15"
}
```

```yaml
priority_service_promos:
  professional_whitening:
    ordered_fact_refs:
      - fact:professional_whitening_discount

scenario_rules:
  cost:
    ordered_amplifier_refs:
      - kb:clinic__info__payment_terms.md#korotko
```

Priority promo (`professional_whitening_discount` в примере выше) — **marketing fact**,
не amplifier. В `scenario_rules` для усилителей используются source-backed KB/doctor/fact
refs, которые действительно являются amplifiers.

**Config migration (current demo — pre-Stage-5.1):** в current `target_response/marketing.yaml`:

- historical `initial_commercial_blocks.service.ordered_fact_refs` ставит `free_implant_consult` и
  `installment_12` **раньше** discount facts;
- discount facts также в `scenario_rules.cost.ordered_amplifier_refs`;
- **нет** `priority_service_promos` / `promotion_overview`.

Docs amendment **не** меняет actual `marketing.yaml`. Stage 5.1 implementation должна
мигрировать на service-id mapping. **Нельзя** выбирать акцию по тексту, слову «скидка», проценту, fact ID,
regex или Python hardcode. Consultation/installment **не** являются fallback для automatic promo.

Session-global suppression: один `fact_id` автоматически показывается один раз за `session_id`.
Прямой promotion request (`promotion_scope=shown`) повторяет последнюю rendered promo session.

Первый service turn при `commercial_intent=none`, `promotion_scope=none` показывает **одну** priority service promo, не весь block сразу.

## Консультационный смысл и CTA

Service `consultation_value` (optional frontmatter service MD) и amplifier pools — см.
[`MARKETING_SCENARIO_ARCHITECTURE.md`](MARKETING_SCENARIO_ARCHITECTURE.md). CTA copy —
в `tone.yaml`. `marketing.yaml` задаёт только `cta_contexts` keys.

## Чего не делать

- Не хранить цену и текст акций в md.
- Не хранить текст акции в `marketing.yaml` (только правила и refs).
- Не добавлять `promo_note` в md (слоты сняты с runtime).
- Не дублировать «запишитесь на консультацию» в каждый md.
- Не просить LLM выбирать акцию, priority promo или CTA.
- Не ссылаться на несуществующие пути `clients/<client_id>/pricebook/...` или `clients/<client_id>/marketing.yaml` без `target_response/`.

**Про `ui.yaml`:** шаблоны вроде `price_symptom_consult` — служебный UI-текст, не замена `facts.json`.

## Проверка после правки

```bash
pytest tests/test_marketing_loader.py tests/test_marketing_policy.py tests/test_promo_overview.py tests/test_pricebook_golden.py tests/test_pricebook_contract.py tests/test_consult_nudge.py -q
```

Список совпадает с тем, что реально есть в репо (см. `.github/workflows/ci.yml` — marketing-тесты пока локально).
