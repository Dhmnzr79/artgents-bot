# Marketing Hooks Audit

Статус: актуальная карта после cleanup-этапов. Часть рекомендаций уже внедрена.

Цель: видеть все места, где бот может добавить маркетинг, CTA, consult-текст, промо, price facts, quick replies или deterministic append.

## Короткий итог

Маркетинг больше не должен жить в десяти равноправных местах. Основная схема сейчас такая:

```text
md -> знания об услуге
PriceBook services -> цены и состав услуги
PriceBook facts -> коммерческие факты
marketing.yaml -> правила показа и service-level marketing ingredients
tone.yaml -> CTA-тексты и lead-flow
ui.yaml -> нейтральные fallback/menu тексты
clinic_policies.yaml -> бизнес-ограничения клиники
```

## Активные источники

| Источник | Где лежит | Как используется | Риск дубля | Статус |
|---|---|---|---|---|
| MD body | `clients/{id}/md/**` | основной контент для LLM | низкий | оставить |
| MD CTA fields | frontmatter `cta_key`, `cta_action`, `cta_text` | отдельная CTA-кнопка | средний | оставить, CTA отдельно от текста |
| MD quick refs | `suggest_h3`, `suggest_refs` | кнопки-ссылки | средний | оставить, policy ограничивает |
| Answer slots | `core/answer_slots.py` | добавляет максимум один text ingredient | средний | оставить как совместимость |
| Marketing service config | `marketing.yaml/service_marketing` | proof/consult reason вместо md-хвостов | средний | основной путь для service marketing |
| Promo rules | `marketing.yaml/promo_rules` | разрешает/запрещает promo facts | низкий | основной путь для promo policy |
| Promo overview | `core/promo_overview.py` | прямой ответ на "есть акции/скидки?" | низкий | deterministic из facts + promo rules |
| PriceBook services | `pricebook/services/*.json` | цены, варианты, includes/stages, price followups | низкий | основной путь для price |
| PriceBook facts | `pricebook/facts.json` | рассрочка, вычет, гарантия, акции, consult facts | средний | основной путь для commercial facts |
| Tone CTA registry | `tone.yaml/lead.cta_variants` | CTA label + первый lead prompt | низкий | источник CTA-текстов |
| UI fallback/menu | `ui.yaml` | нейтральные fallback/menu тексты | низкий | не хранить тяжелый маркетинг |
| Clinic policies | `clinic_policies.yaml` | hard-stop, услуги не оказываем, альтернативы | низкий | не хранить акции/общие consult rules |
| Patient playbook | `patient_playbook.yaml` | стратегия выбора вариантов, не готовый copy | средний | проверить consult budget отдельно |
| Doctors route bridge | `doctors_lookup.py` + `chunk_responder.py` | мягкое объяснение консультации по врачам | средний | оставить, не добавлять цены пачкой |
| Consult nudge | `ui.yaml/consult_nudge` + `core/consult_nudge.py` | нейтральный LLM-addon при исчерпании темы | средний | не должен продавать |
| Legacy price append | `answer_plan`, `price_offers` | fallback price/payment append | средний | держать suppress-логику |
| Numeric fact gate fallback | `numeric_fact_gate.py` | safety fallback при сомнительных цифрах | низкий | safety, не marketing policy |

## Уже выключено или снижено

| Старый хук | Что было | Что сейчас |
|---|---|---|
| Global free consult prompt | LLM могла сама добавлять бесплатную консультацию | убрано из `core/llm_system_prompt.py` |
| PriceBook closer | каждый price-answer мог закончиться консультацией | `_template_closer` не добавляет хвост |
| `service.promo` | промо могло лежать прямо в услуге | assembler больше не рендерит `service.promo` |
| Demo fallback marketing | `low_score` продавал бесплатную консультацию/вычет | `ui.yaml` смягчен |
| Clinic policy consult push | hard-stop мог сразу вести в консультацию | demo `clinic_policies.yaml` смягчен |
| MD marketing tails в demo | `clinic_note`, `consult_value`, `promo_note` были в md | demo md очищены, fallback оставлен для совместимости |

## Что еще проверить

### Прямой promo route

Вопросы "есть акции?", "какие скидки сейчас?" обрабатывает `core/promo_overview.py`.

Поведение:

- общий вопрос показывает активные разрешенные промо;
- вопрос про скидки отсекает не-скидочные промо, например бесплатную консультацию;
- вопрос по конкретной услуге фильтрует промо по `allowed_service_ids`;
- кнопки ведут в `price:{service_id}`;
- CTA не добавляется автоматически.

### Patient playbook

Маршрут `patient_options_overview` может мягко вести к КТ/консультации через LLM-инструкцию. Нужно проверить, что он не добавляет второй consult-смысл поверх `marketing.yaml` или CTA.

### Legacy fields

Для совместимости остаются:

- `clinic_note`;
- `consult_value`;
- `promo_note`;
- `h3_overrides`;
- `service.promo`;
- legacy alias `promos`.

Они не должны использоваться в новых demo-данных. Удаление из кода лучше делать отдельным этапом.

### Legacy price append

`price_offers` и `answer_plan` еще могут добавлять price/payment append в chunk-ответах. Нужно сохранять suppress, чтобы `installment_12` и `payment_terms` не появлялись одновременно.

## Human review checklist

Перед релизом нового клиента проверить:

- нет ли promo/consult хвостов в `md/**`;
- все акции есть в `pricebook/facts.json`;
- для каждой акции есть правило в `marketing.yaml/promo_rules`;
- CTA labels и lead prompts лежат в `tone.yaml`;
- fallback в `ui.yaml` нейтральный;
- clinic policies не продают общие акции;
- direct promo question отвечает только активными разрешенными фактами;
- в одном ответе не появляется больше одного текстового marketing-смысла.
