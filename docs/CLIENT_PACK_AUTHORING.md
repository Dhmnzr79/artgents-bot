# Client pack authoring

Один canonical source на домен. Новая клиника **не создаёт** root legacy mirrors
(`service_catalog.json`, `pricebook/`, `marketing.yaml`, `price_brand_aliases.json`).

## Что меняю → какой файл

### Стартовое меню по страницам сайта

В `clients/nikadent/widget_config.json` уже настроены общее меню, All-on-4,
съёмные протезы и коронки. Это настройки внешнего вида; MD-база ответов прежняя.

- Верхние `welcomeText` и `starterPrompts` — общее приветствие и три вопроса
  на главной и всех страницах без отдельной настройки (включая врачей и цены).
- `pageMenus` — список исключений. `paths` содержит адреса страниц **после домена**,
  например `/all-on-4/`. Одному меню можно назначить несколько адресов.
- В каждом меню `welcomeText` — приветствие, `starterPrompts` — ровно три кнопки.
  `label` — короткая надпись, `q` — полный вопрос, который отправляется при клике.
- `welcomePromotion` в верхней части файла — одна акция на весь сайт. Внутри
  `pageMenus` акции не задаются. Её тексты должны соответствовать действующей базе;
  изменение карточки само по себе не меняет условия в фактах/MD.

Пример элемента `pageMenus`:

```json
{
  "paths": ["/all-on-4/"],
  "welcomeText": "Здравствуйте! Помогу разобраться в имплантации All-on-4.",
  "starterPrompts": [
    {"label": "Стоимость All-on-4", "q": "Сколько стоит All-on-4 в НикаДент?"},
    {"label": "Этапы лечения", "q": "Как проходит лечение All-on-4 в НикаДент?"},
    {"label": "Консультация", "q": "Как записаться на консультацию по имплантации?"}
  ]
}
```

Совпадение точное: `/all-on-4` и `/all-on-4/` равнозначны; UTM и `#якорь`
игнорируются. Подстраницы, похожие слова, другой регистр и маски `*` не
подбираются автоматически. Повтор одного адреса в разных меню — ошибка настройки.
При переходах с перезагрузкой страницы меню определяется заново; для сайта с
SPA-переходами без перезагрузки отдельная интеграция пока не реализована.
В новой беседе/reset адрес читается заново; активный разговор не сбрасывается.
URL/UTM в модель не отправляются. Отдельное меню влияет только на стартовый экран;
пациент по-прежнему может написать вопрос на любую тему клиники.

Проверка: локальная панель `/static/widget-test.html?client=nikadent`, поле
«Страница сайта», затем «Открыть чат». Обновить страницу после правки JSON.
На клиентском сайте адрес определяется автоматически; отдельный embed-код для
каждой страницы не нужен. До выкладки новая функция работает только локально.

Готовая инструкция для Codex: «В `clients/nikadent/widget_config.json` измени
меню для `/all-on-4/`: приветствие …; три кнопки: надпись …, вопрос …; …; … .
Общее меню и общую акцию сохрани. Проверь конфигурацию и тестовую панель.
Без merge/deploy и платных вызовов». Для нового клиента тот же формат.

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
| Приветствие, стартовые вопросы, меню по страницам, общая акция виджета | `clients/{id}/widget_config.json` |
| Разрешённые домены установки виджета | `clients/{id}/widget_integration.json` |
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

**FINAL_TOMOGRAPHY_EXISTING_SCAN_CONTENT_ROUTING:** FAQ про своё/имеющееся КТ — canonical MD
(`diagnostics__service__tomography.md`) + `content_ref` в catalog. **Не** класть текст в catalog facts,
pricebook или marketing. Availability yes/no и price 3 000 ₽ — отдельные пути (structured availability /
price-only offer).

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
- `target_response/context_groups.json` (future, not yet implemented — see
  `FINAL_MULTI_LEVEL_SCOPED_CONTEXT_SHADOW` / PERF-6 governance,
  `docs/evidence/performance/FINAL_MULTI_LEVEL_SCOPED_CONTEXT_SHADOW_SEAM_AUDIT.md` § 3). Proposed
  shape: `{"schema_version": 1, "groups": [{"group_id": "...", "topics": ["...", "..."]}]}` — an
  explicit authored cross-topic grouping (e.g. "tooth restoration" spanning `implantation` +
  `prosthetics` + `diagnostics`), used only by a future Scoped FullContext `context_group` tier.
  **Does not exist yet; no client currently has this file.**

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
