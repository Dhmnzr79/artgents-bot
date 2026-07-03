# Как редактировать маркетинг клиента

Это короткая памятка для demo-клиента и будущих клиентских паков.

## Быстрая карта

| Хочу поменять | Открыть файл |
|---|---|
| Цена услуги | `clients/demo/pricebook/services/*.json` |
| Что входит в цену / этапы оплаты | `clients/demo/pricebook/services/*.json` |
| Акция, скидка, рассрочка, вычет, гарантия | `clients/demo/pricebook/facts.json` |
| Включить/выключить акцию, ограничить услугу/маршрут | `clients/demo/marketing.yaml` -> `promo_rules` |
| Мягкий аргумент "почему к нам" по услуге | `clients/demo/marketing.yaml` -> `service_marketing.*.clinic_proof` |
| Что будет на консультации по услуге | `clients/demo/marketing.yaml` -> `service_marketing.*.consult_reasons` |
| Текст CTA-кнопки и первый вопрос после клика | `clients/demo/tone.yaml` |
| Текст меню или fallback | `clients/demo/ui.yaml` |
| Услугу не оказываем / работаем не по ОМС / альтернатива | `clients/demo/clinic_policies.yaml` |
| Содержание услуги, FAQ, медицинские пояснения | `clients/demo/md/**` |

## Правило про facts и marketing

`pricebook/facts.json` отвечает на вопрос: **что правда?**

Примеры:

- "Скидка 10% до 15 июля."
- "Доступна рассрочка до 12 месяцев."
- "Можно оформить налоговый вычет 13%."

`marketing.yaml` отвечает на вопрос: **когда это можно показывать?**

Примеры:

- только для `professional_whitening`;
- только в `price_lookup`;
- не показывать на pain/safety/contraindications;
- активно до конкретной даты.

Текст акции не надо дублировать в `marketing.yaml`. Там только правила.

## Как добавить новую акцию

1. Добавить факт в `clients/demo/pricebook/facts.json`.
2. Привязать факт к услуге в `clients/demo/pricebook/services/{service_id}.json` через `fact_refs`.
3. Добавить правило в `clients/demo/marketing.yaml` -> `promo_rules`.
4. Проверить, что акция не лежит в `md/**`, `ui.yaml` или `tone.yaml`.

Мини-пример:

```json
"whitening_discount": {
  "id": "whitening_discount",
  "kind": "promo",
  "text_fact": "Сейчас на профессиональное отбеливание действует скидка 10% до 15 июля.",
  "render_mode": "strict",
  "detail_ref": null,
  "followup_label": null,
  "usable_in": ["price_answer"],
  "active_until": "2026-07-15"
}
```

```yaml
promo_rules:
  whitening_discount:
    active: true
    active_until: "2026-07-15"
    fact_ref: whitening_discount
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

`price_lookup` нужен, чтобы акция появилась в ответе про цену. `promo_overview` нужен, чтобы акция появилась на прямой вопрос "есть акции?".

## Как поменять консультационный смысл

Если нужно объяснить, что будет на консультации по услуге, редактировать:

```yaml
service_marketing:
  classic:
    consult_reasons:
      - "оценить кость и соседние зубы, сравнить системы имплантов и составить план восстановления"
```

Не надо добавлять одинаковый хвост в каждый md-файл.

## Как поменять CTA

CTA-текст и первый вопрос после клика редактировать в `clients/demo/tone.yaml`, обычно в `lead.cta_variants`.

`marketing.yaml` может выбрать `primary_cta_key`, но не должен хранить полный lead-flow.

## Чего не делать

- Не хранить цену в md.
- Не хранить текст акции в `marketing.yaml`.
- Не хранить акцию в `tone.yaml`.
- Не добавлять `promo_note` в md для новых материалов.
- Не добавлять одинаковый "запишитесь на консультацию" в каждый md.
- Не делать fallback продающим, если бот просто не понял вопрос.
- Не просить LLM самой решить, какую акцию или CTA добавить.

## Быстрая проверка после правки

Попросить Cursor прогнать:

```bash
pytest tests/test_marketing_loader.py tests/test_marketing_policy.py tests/test_answer_slots.py tests/test_pricebook_golden.py tests/test_client_config_loader.py tests/test_consult_nudge.py tests/test_llm_system_prompt.py tests/test_pricebook_contract.py tests/test_vague_doctor_followup.py
```

Если менялись только документы, тесты не обязательны.
