# S17 — аудит миграции marketing/CTA в target

## Итог простыми словами

Маркетинговую архитектуру уже обсуждали и формализовали. Модели новой схемы тоже есть.
Но реального `clients/demo/target_response/marketing.yaml` пока нет, поэтому target pack
ещё не загружается целиком и ничем не управляет.

Current `clients/demo/marketing.yaml` нельзя просто скопировать. В нём одновременно
смешаны готовые продающие фразы, CTA, применимость акций и старые route/aspect gates.
Target разделяет эти ответственности между commercial facts, KB/MD, doctor layer,
marketing policy, tone/UI и общим runtime law.

S17 ничего не переносит и не подключает. Он показывает точный состав источников и
решения, которые нужны до target data.

## Что уже существует

| Часть | Статус |
|---|---|
| Product/design law | Согласован в `MARKETING_SCENARIO_ARCHITECTURE.md` |
| `TargetMarketingPolicy` models | Реализованы offline в S1 |
| Strict target-pack loader | Реализован в S2 и требует `marketing.yaml` |
| External `kb:`/`doctor:` integrity | Реализована S3/S4/S6 |
| Шесть commercial facts demo | Materialized в S12 |
| Clinic strategy | Materialized в S16 |
| Demo target marketing policy | Отсутствует |
| Selector, session cadence, UI/product wiring | Отсутствуют |
| Marketing/A9 authority | Отсутствует |

## Exact current inventory

### Current marketing

`clients/demo/marketing.yaml` имеет `version: 1` и четыре global blocked aspects:

- `pain`;
- `contraindications`;
- `safety`;
- `complications`.

В `service_marketing` ровно 13 authored keys:

1. `classic`;
2. `one_stage`;
3. `all_on_4`;
4. `all_on_6`;
5. `temporary_teeth`;
6. `benefits`;
7. `what_included`;
8. `sinus_lift`;
9. `pterygoid_implants`;
10. `zygomatic_implants`;
11. `teeth_whitening`;
12. `tooth_extraction`;
13. `periodontitis`.

Внутри них:

- 11 готовых `clinic_proof` strings;
- 13 готовых `consult_reasons` strings;
- CTA: `doctor` — 10, `consult` — 3.

Ровно 10 keys совпадают с canonical target service IDs. Остальные три:

- `benefits` и `what_included` — content topics, а не услуги;
- `teeth_whitening` — legacy имя для canonical `professional_whitening`.

### Почему 24 строки нельзя перенести автоматически

Все 24 free strings (`11 clinic_proof + 13 consult_reasons`) проверены как exact
substring по всем current demo MD. Exact matches: **0**.

Это не означает, что строки неверны. Это означает, что у них нет exact `kb:` source ref,
а target marketing policy не разрешает хранить свободный amplifier text. Возможны только
два честных будущих решения:

1. отдельно отредактировать/утвердить нужные строки и опубликовать их в MD как source;
2. не переносить их и удалить вместе с legacy marketing после retirement.

Создавать похожие MD-ссылки или переписывать смысл автоматически нельзя.

### Promo rules и уже перенесённые facts

Current marketing содержит три promo rules:

| Rule / fact ref | Target fact | Active/date/services |
|---|---|---|
| `free_implant_consult` | существует | exact value/set parity |
| `implant_same_day_discount` | существует | exact value/set parity |
| `professional_whitening_discount` | существует | exact value/set parity |

У первых двух отличается только authored order списка услуг; set IDs совпадает. Этот
порядок не является priority signal. У whitening совпадает и список.

Target facts уже владеют точным текстом, active/date и service eligibility. Поэтому эти
поля не должны повторно жить в target marketing policy.

Current-only поля `allowed_routes`, `allowed_aspects`, `blocked_aspects`, global blocked
list и promo-local CTA принадлежат старому combined runtime. Их нельзя копировать как
скрытый classifier. Target использует common scenarios, manual-contact boundary и
semantic CTA context.

## Exact CTA inventory

| Current owner | Exact результат |
|---|---|
| `tone.yaml` | 6 variants: `booking`, `consult`, `callback`, `plan`, `price`, `doctor` |
| 54 MD files | `booking: 6`, `callback: 2`, `consult: 13`, `doctor: 6`, `plan: 25`, `price: 2` |
| 21 current pricebook service files | все `price` |
| 8 patient-playbook rules | `ct_consultation: 7`, `consult: 1` |
| 13 service-marketing entries | `doctor: 10`, `consult: 3` |

`tone.yaml` уже является естественным владельцем visible label и первой lead-flow
фразы. Target `marketing.yaml` должен хранить только semantic context → CTA key.

`ct_consultation` отсутствует среди шести tone variants. Это legacy key, для которого
нужно отдельное решение: retire или explicit mapping. S17 не приравнивает его к
`consult`, `plan` или `price` по догадке.

## Current field → target owner

| Current field | Target owner / решение |
|---|---|
| `service_marketing.*.clinic_proof` | Только exact KB/doctor/fact source после отдельного решения; free text не копируется |
| `service_marketing.*.consult_reasons` | Не поле target policy; source-content либо retire |
| `primary_cta_key` | Candidate input для будущего semantic `cta_contexts`, не per-service law |
| `promo_rules.*.fact_ref` | `target_response/pricebook/facts.json` + marketing ordered ref |
| promo active/date/services | Только target fact record |
| `allowed_routes`, `allowed_aspects` | Legacy classifier wiring; не переносится |
| blocked aspects | Common scenario/manual-contact product law; не client duplicate |
| promo `cta_key` | Future semantic CTA mapping, не promo-local copy |
| visible CTA label / first lead phrase | `tone.yaml` |
| shown histories | Session state, не policy copy |

## Target boundary и найденные gaps

Target marketing model поддерживает:

- exact limits `3/2/2`;
- initial commercial blocks из ordered `fact:` refs;
- пять scenario rules;
- ordered `kb:`/`doctor:`/`fact:` amplifier refs;
- allowed semantic contexts;
- semantic `cta_contexts` с обязательным `default`.

S2 real demo load сейчас fail-closed:

```text
required_path_missing marketing.yaml
```

Это ожидаемо: target pack пока offline и неполон.

До materialization остаются два contract/ownership gap:

1. `cta_contexts` проверяет nonblank/default, но не проверяет value против CTA keys из
   `tone.yaml`.
2. Architecture ownership относит cadence policy к client marketing data, но frozen
   `TargetMarketingPolicy` не имеет cadence field. Нужно выбрать: cadence — единый
   universal runtime law или future client-schema field.

Документ до S17 неточно говорил, что schema полностью не реализована. S1 models уже
существуют; отсутствуют demo target policy, selector/session/runtime и authority.

## Candidate source map — не утверждённые pools

Следующие refs существуют и показывают, что для каждого standard scenario есть
source-backed основа. Они **не утверждены** как состав, порядок или автоматический показ.

### `pain_fear`

- `kb:implantation__faq__pain.md#korotko`;
- `kb:implantation__faq__pain.md#kakuyu-anesteziyu-ispolzuyut`.

### `cost`

- `fact:installment_12`;
- `fact:implant_same_day_discount`;
- `fact:tax_deduction`;
- `kb:implantation__faq__cost.md#kak-sdelat-implantatsiyu-dostupnee`;
- `kb:clinic__info__payment_terms.md#korotko`.

### `time`

- `kb:implantation__faq__duration.md#korotko`;
- `kb:implantation__faq__duration.md#mozhno-li-uskorit-implantatsiyu`;
- `kb:implantation__faq__tooth_one_day.md#korotko`;
- `kb:implantation__info__steps.md#korotko`.

### `doctor_trust`

- `doctor:doctors__doctor__volkov`;
- `doctor:doctors__doctor__orlov`;
- `kb:doctors__doctor__overview.md#korotko`;
- `kb:clinic__info__technology.md#korotko`.

### `result_reliability`

- `fact:implant_warranty`;
- `kb:implantation__faq__osseointegration.md#korotko`;
- `kb:implantation__faq__osseointegration.md#ot-chego-zavisit-prizhivlenie`;
- `kb:clinic__info__warranty.md#korotko`.

Проверка границ:

- `fact:` — real target bundle/local fact index;
- `kb:` — S4 KB index + S3 external validation;
- `doctor:` — S6 doctor refs + S3 external validation.

Service applicability, source order и automatic-display decision здесь не заданы.

## Решения владельца до target data

1. Какие из 24 legacy free strings сохранять через отдельную публикацию в MD, а какие
   удалить вместе с legacy.
2. Exact semantic contexts и initial commercial blocks для demo.
3. Exact source refs и order для каждого из пяти scenario pools.
4. CTA context map, clinic default и судьба `ct_consultation`.
5. Cadence/no-repeat — universal runtime law или client schema data.
6. Нужна ли до materialization contract-проверка CTA key против `tone.yaml`.
7. Retire/mapping для `benefits`, `what_included`, `teeth_whitening`.

## Рекомендованный следующий checkpoint

Сначала отдельный owner-decision/governance checkpoint должен закрыть семь вопросов
выше и заморозить минимальные exact data. Только после checker-review можно создавать
real target `marketing.yaml` и real bundle acceptance.

Selector, session cadence, response/UI wiring и authority должны оставаться отдельными
последующими checkpoint-ами. A9 остаётся на паузе; live/LLM не требуется.

## Verification

Independent completion review `✅`:

- S17 audit acceptance: `7 passed`;
- legacy loader + frozen schema/loader/ref neighbors: `112 passed`;
- skip/xfail: нет;
- client/target data, contracts/code/runtime и authority не менялись.
