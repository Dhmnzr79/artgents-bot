# Как редактировать маркетинг клиента

Короткая памятка для demo-клиента и будущих паков. Канон demo на дату: `clients/demo/pricebook/facts.json` + `clients/demo/marketing.yaml`.

## Быстрая карта

| Хочу поменять | Открыть файл |
|---|---|
| Цена услуги | `clients/demo/pricebook/services/*.json` |
| Что входит в цену / этапы оплаты | `clients/demo/pricebook/services/*.json` |
| Акция, скидка, рассрочка, вычет, гарантия | `clients/demo/pricebook/facts.json` |
| Включить/выключить акцию, ограничить услугу/маршрут | `clients/demo/marketing.yaml` → `promo_rules` |
| Мягкий аргумент «почему к нам» по услуге | `clients/demo/marketing.yaml` → `service_marketing.*.clinic_proof` |
| Что будет на консультации по услуге | `clients/demo/marketing.yaml` → `service_marketing.*.consult_reasons` |
| Текст CTA-кнопки и первый вопрос после клика | `clients/demo/tone.yaml` |
| Текст меню или fallback | `clients/demo/ui.yaml` |
| Услугу не оказываем / ОМС / альтернатива | `clients/demo/clinic_policies.yaml` |
| Содержание услуги, FAQ, медицинские пояснения | `clients/demo/md/**` |

## Канон акций demo (2026-07-10)

| ID | Тип | Суть |
|---|---|---|
| `free_implant_consult` | promo | Бесплатная консультация (имплантация + протезирование), до 31.12.2026 |
| `implant_same_day_discount` | promo | Скидка до 15% в день обращения (все виды имплантации) |
| `professional_whitening_discount` | promo | Скидка 10% на отбеливание до 15.08.2026 |
| `installment_12` | payment | Рассрочка на имплантацию и протезирование до 12 мес. |
| `tax_deduction` | benefit | Налоговый вычет 13% |
| `implant_warranty` | warranty | Гарантии на работу и импланты |

**promo_rules:** те же три promo (`free_implant_consult`, `implant_same_day_discount`, `professional_whitening_discount`).

Известный долг: `free_implant_consult` с `kind: promo` блокируется на pain/safety — планируется `promo` → `benefit` (см. `FULLCONTEXT_ROADMAP.md` Этап 7).

## Правило про facts и marketing

`pricebook/facts.json` — **что правда?**

Примеры:

- «Скидка 10% до 15 августа.»
- «Рассрочка на имплантацию и протезирование до 12 месяцев.»
- «Можно оформить налоговый вычет 13%.»

`marketing.yaml` — **когда это можно показывать?**

Примеры:

- только для `professional_whitening`;
- только в `price_lookup` и `promo_overview`;
- не показывать на pain/safety/contraindications;
- `active_until` на уровне правила.

Текст акции не дублировать в `marketing.yaml` — только правила.

## Как добавить новую акцию

1. Факт в `clients/demo/pricebook/facts.json`.
2. `fact_refs` в `clients/demo/pricebook/services/{service_id}.json`.
3. Правило в `clients/demo/marketing.yaml` → `promo_rules`.
4. Не дублировать текст акции в `md/**` (кроме нейтральных условий оплаты в `payment_terms`).

Мини-пример (отбеливание):

```json
"professional_whitening_discount": {
  "id": "professional_whitening_discount",
  "kind": "promo",
  "text_fact": "Сейчас на профессиональное отбеливание действует скидка 10% до 15 августа.",
  "render_mode": "strict",
  "detail_ref": null,
  "followup_label": null,
  "usable_in": ["price_answer"],
  "active_until": "2026-08-15"
}
```

```yaml
promo_rules:
  professional_whitening_discount:
    active: true
    active_until: "2026-08-15"
    fact_ref: professional_whitening_discount
    allowed_service_ids:
      - professional_whitening
    allowed_routes:
      - price_lookup
      - promo_overview
    allowed_aspects:
      - overview
    blocked_aspects:
      - pain
      - contraindications
      - safety
      - complications
```

`price_lookup` — акция в ответе про цену. `promo_overview` — на вопрос «есть акции?».

## Консультационный смысл и CTA

`consult_reasons` / `clinic_proof` — в `marketing.yaml` → `service_marketing`, не одинаковый хвост в каждом md.

CTA и lead-flow — в `tone.yaml`. `marketing.yaml` может задать только `primary_cta_key`.

## Чего не делать

- Не хранить цену и текст акций в md.
- Не хранить текст акции в `marketing.yaml` (только правила).
- Не добавлять `promo_note` в md (слоты сняты с runtime).
- Не дублировать «запишитесь на консультацию» в каждый md.
- Не просить LLM выбирать акцию или CTA.

**Про `ui.yaml`:** шаблоны вроде `price_symptom_consult` — служебный UI-текст, не замена `facts.json`.

## Проверка после правки

```bash
pytest tests/test_marketing_loader.py tests/test_marketing_policy.py tests/test_promo_overview.py tests/test_pricebook_golden.py tests/test_pricebook_contract.py tests/test_consult_nudge.py -q
```

Список совпадает с тем, что реально есть в репо (см. `.github/workflows/ci.yml` — marketing-тесты пока локально).
