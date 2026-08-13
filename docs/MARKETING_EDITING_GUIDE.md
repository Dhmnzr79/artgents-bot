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
| Порядок, ссылки, лимиты, scenario pools, CTA context keys | `clients/demo/target_response/marketing.yaml` → `limits`, `initial_commercial_blocks`, `scenario_rules`, `cta_contexts` |
| Текст CTA-кнопки и первый вопрос после клика | `clients/demo/tone.yaml` |
| Видео | `clients/demo/video_catalog.yaml` |
| Текст меню или fallback | `clients/demo/ui.yaml` |
| Услугу не оказываем / ОМС / альтернатива | `clients/demo/clinic_policies.yaml` |
| Содержание услуги, FAQ, медицинские пояснения | `clients/demo/md/**` |

## Разделение ownership

| Слой | Что хранит |
|---|---|
| `facts.json` | Фактический текст акции/рассрочки/гарантии, active dates, `allowed_service_ids`, `incompatible_with` |
| `marketing.yaml` | Порядок refs, scenario amplifier pools, лимиты **3/2**, CTA context keys; **не** дублирует текст факта |
| `tone.yaml` | Видимый copy CTA и lead-flow |
| `video_catalog.yaml` | Тематические ролики для secondary UI slot |

LLM **не** выбирает точную акцию и **не** генерирует её условия. Priority service promo
выбирается и рендерится детерминированным post-Flash кодом по clinic-authored priority.

## Канон акций demo (2026-07-10)

| ID | Тип | Суть |
|---|---|---|
| `free_implant_consult` | promo | Бесплатная консультация (имплантация + протезирование), до 31.12.2026 |
| `implant_same_day_discount` | promo | Скидка до 15% в день обращения (все виды имплантации) |
| `professional_whitening_discount` | promo | Скидка 10% на отбеливание до 15.08.2026 |
| `installment_12` | payment | Рассрочка на имплантацию и протезирование до 12 мес. |
| `tax_deduction` | benefit | Налоговый вычет 13% |
| `implant_warranty` | warranty | Гарантии на работу и импланты |

**`marketing.yaml` schema (актуальная):** `initial_commercial_blocks`, `scenario_rules`,
`limits`, `cta_contexts`. Старый `promo_rules` в текущем target pack **не используется**.

Известный current-runtime долг: `free_implant_consult` с `kind: promo` блокируется на pain/safety. Не исправлять это старым тематическим route; будущая реализация следует общей target policy.

## Правило про facts и marketing

`target_response/pricebook/facts.json` — **что правда?**

Примеры:

- «Скидка 10% до 15 августа.»
- «Рассрочка на имплантацию и протезирование до 12 месяцев.»
- «Можно оформить налоговый вычет 13%.»

`target_response/marketing.yaml` — **когда и в каком порядке это можно показывать?**

Примеры:

- `initial_commercial_blocks.service.ordered_fact_refs` — clinic priority для commercial facts;
- `scenario_rules.<scenario>.ordered_amplifier_refs` — pool усилителей;
- `limits.max_marketing_facts_per_turn: 3`, `max_amplifiers_per_turn: 2`;
- `cta_contexts` — выбор CTA key по semantic context.

Текст акции **не** дублировать в `marketing.yaml` — только правила, порядок и ссылки.

## Как добавить новую акцию

1. Факт в `clients/demo/target_response/pricebook/facts.json`.
2. `fact_refs` в `clients/demo/target_response/pricebook/services/{service_id}.json`.
3. Ссылку и порядок в `clients/demo/target_response/marketing.yaml` → `initial_commercial_blocks` и/или `scenario_rules`.
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
initial_commercial_blocks:
  service:
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

**Config migration seam / priority authority:** в current demo `target_response/marketing.yaml`:

- `initial_commercial_blocks.service.ordered_fact_refs` ставит `free_implant_consult` и
  `installment_12` **раньше** discount facts;
- `implant_same_day_discount` и `professional_whitening_discount` также в
  `scenario_rules.cost.ordered_amplifier_refs`;
- несколько facts имеют `kind=promo`, но **нет** однозначного authored поля «главная
  priority service promo».

Docs sync **не** меняет actual `marketing.yaml`. Stage 5.1 seam audit должен найти
однозначный authored authority или доказать необходимость минимального schema/config
изменения. **Нельзя** выбирать главную акцию по тексту, слову «скидка», проценту, fact ID,
regex или Python hardcode. Бесплатная консультация **не** считается главной скидкой без
явной client authority.

Прямой вопрос об **уже показанной конкретной** акции получает ответ повторно (suppression
bypass only). Общий вопрос «есть акции?» — unresolved semantic seam Stage 5.1; точное
количество promo facts **не** определяется в этом docs pass.

Первый service turn показывает **одну** priority service promo, не весь block сразу.

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
- Не ссылаться на несуществующие пути `clients/demo/pricebook/...` или `clients/demo/marketing.yaml` без `target_response/`.

**Про `ui.yaml`:** шаблоны вроде `price_symptom_consult` — служебный UI-текст, не замена `facts.json`.

## Проверка после правки

```bash
pytest tests/test_marketing_loader.py tests/test_marketing_policy.py tests/test_promo_overview.py tests/test_pricebook_golden.py tests/test_pricebook_contract.py tests/test_consult_nudge.py -q
```

Список совпадает с тем, что реально есть в репо (см. `.github/workflows/ci.yml` — marketing-тесты пока локально).
