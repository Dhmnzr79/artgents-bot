# Client pack authoring

Один canonical source на домен. Новая клиника **не создаёт** root legacy mirrors
(`service_catalog.json`, `pricebook/`, `marketing.yaml`, `price_brand_aliases.json`).

## Что меняю → какой файл

| Задача | Единственный файл |
|---|---|
| Название услуги, aliases, active, family | `clients/{id}/target_response/service_catalog.json` |
| Цена, billing unit, пакет, payment stages | `clients/{id}/target_response/pricebook/services/{offer_id}.json` |
| Commercial facts (акции, рассрочка, гарантия) | `clients/{id}/target_response/pricebook/facts.json` |
| Broad family price (опционально) | `clients/{id}/target_response/pricebook/family_prices.json` |
| Бренды имплантов и aliases | `clients/{id}/target_response/brand_catalog.json` |
| Marketing policy (facts/scenarios/CTA contexts) | `clients/{id}/target_response/marketing.yaml` |
| Приоритеты услуг/offers | `clients/{id}/target_response/clinic_strategy.yaml` |
| Текст услуги / FAQ (FullContext) | `clients/{id}/md/{content_ref}` |
| Врачи и привязка к услугам | `clients/{id}/doctor_catalog.json` |
| Контакты, часы, парковка, «не оказываем» | `clients/{id}/clinic_policies.yaml` → `contact:` (structured: phone, whatsapp, address, hours, parking) |
| Виджет: имя, цвета, логотип | `clients/{id}/brand.yaml` |
| CTA-формулировки | `clients/{id}/tone.yaml` |
| UI labels / fallback меню | `clients/{id}/ui.yaml` |
| Видео (опционально) | `clients/{id}/video_catalog.yaml` |
| Widget layout / origins | `clients/{id}/widget_config.json` |
| Runtime capabilities | `clients/{id}/features.yaml` |
| Lead delivery | `clients/{id}/lead_config.yaml` |

`brand.yaml` ≠ `target_response/brand_catalog.json`  
`clinic_policies.yaml` ≠ `target_response/clinic_strategy.yaml`

**FULLCONTEXT_DIALOGUE_PRESENTATION_CONVERGENCE:** canonical contact facts live **only** in
`clinic_policies.yaml` `contact:` block. **Не дублировать** телефон, адрес, часы, WhatsApp,
парковку в `md/`. Прямые контактные вопросы — typed `contacts` aspect + PRIMARY_EVIDENCE
`clinic_contact`, не regex и не MD.

**FINAL_SERVICE_AVAILABILITY_AND_CLINIC_CAPABILITY_ROUTING:** `service_catalog.json` — authority for
**service availability** (standalone treatment/procedure). `content_ref` optional for yes/no
availability answer. Clinic capability/info (materials, equipment, safety standards) — **only** in
`md/` via Generic FullContext; **не добавлять** capability facts as catalog services. Inactive
services: `active=false` in catalog (authored); not shown in planner compact list but preserved in bundle.

**FINAL_PRICE_ONLY_SOURCE_SUFFICIENCY_CONVERGENCE:** service may have **price offer without `content_ref`**
(e.g. `tomography` + `pricebook/services/tomography.default.json`). Price-only answers use structured
`offer:*` evidence — **не** добавлять MD-заглушку только ради Composer. `content_ref` остаётся обязательным
для content-only, content+price, FAQ/description, marketing claims. Missing offer → `data_gap` /
`no_public_price`, not source mismatch.

## Новая клиника (чеклист)

1. Скопировать `clients/_template/` → `clients/{new_id}/`.
2. Заменить placeholder IDs (`sample_service`, `template_brand`, …) на уникальные.
3. Добавить MD-файлы под каждый `content_ref` в `service_catalog.json`.
4. Заполнить `doctor_catalog.json` и `service_ids` врачей.
5. Прогнать offline validator:

```powershell
python scripts/validate_client_pack.py --client-id {new_id}
```

## Required files

- `target_response/service_catalog.json`
- `target_response/brand_catalog.json`
- `target_response/marketing.yaml`
- `target_response/clinic_strategy.yaml`
- `target_response/pricebook/facts.json`
- `target_response/pricebook/services/*.json` (≥1 offer)
- `doctor_catalog.json`
- `md/*.md` (≥1)
- `brand.yaml`, `clinic_policies.yaml`, `features.yaml`, `lead_config.yaml`, `tone.yaml`, `ui.yaml`, `widget_config.json`

## Optional

- `target_response/pricebook/family_prices.json`
- `video_catalog.yaml`

## ID consistency

- `service_catalog` keys = `service_id` в offers.
- `offer_id` уникален; файл `{offer_id}.json`.
- `brand_id` в offer ∈ `brand_catalog.brands`.
- `fact_refs` в offer ∈ `pricebook/facts.json`.
- `content_ref` в service → существующий `md/{content_ref}`.
- `profile_ref` врача → `kb:...md#anchor` в `md/`.

## Validator

```powershell
python scripts/validate_client_pack.py --client-id demo
python scripts/validate_client_pack.py --path clients/_template --scaffold
```

Exit code ≠ 0 при invalid pack; path-specific errors в stderr.
