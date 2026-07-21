# TASK — S12 Demo Target Price Offers Materialization

**Ветка:** `codex/stage-a`

**Baseline:** `e9dcc41 data: materialize demo target service catalog S11`

**Серия / checkpoint:** `S12` — материализация полного offline target price layer для
всех 21 demo-услуг: brand catalog, 31 offer и 6 commercial facts в frozen S1 wire
shape.

**Режим:** client data materialization only. Никаких strategy/marketing files,
product consumers, routes/UI, live/LLM или product authority.

## Owner decision после первого checker-review

21 июля 2026 владелец demo явно утвердил:

- недостающие source-owned единицы для девяти current simple prices:
  - `aligners` и `periodontitis` — полный курс;
  - `caries`, `pulpitis`, `teeth_treatment`, `tooth_extraction` — один зуб;
  - `professional_whitening` и `tomography` — одна процедура/исследование;
  - `clasp_dentures` — один протез;
- `sinus_lift` 42 000/68 000 показывается как цена **от**, потому что current source
  говорит о зависимости от объёма материала и способа доступа;
- важные authored границы и состав сохраняются в package label/includes;
- legacy payment-stage breakdown 60/40 и связанные с ним кнопки не мигрируют; общая
  цена, состав и существенные ограничения сохраняются.

Это owner-authoring данных будущего demo pack, но не product authority: target pack не
подключается к ответам.

## Цель

Дополнить изолированный `clients/demo/target_response/`:

- `brand_catalog.json` — три реальных бренда имплантов;
- `pricebook/services/*.json` — ровно 31 target `TargetOffer`, по одному offer на файл;
- `pricebook/facts.json` — шесть target `TargetCommercialFact`.

Каждая из 21 target-услуг S11 получает минимум один exact price offer. Суммы, currency,
variant IDs, `includes`, fact refs и fact texts берутся из current demo pricebook.
Owner-approved units/labels закрывают неоднозначности current source без runtime guesses.

S12 не выбирает offer, не сортирует по коммерческому приоритету и не формирует ответ.

## Почему это минимальный scope

S11 создал service-side общей связи «описание → цена → врач», а S10 умеет pure собирать
service, offers и doctors по одному exact `service_id`. Но real target offers ещё нет.

Offer нельзя aggregate-валидировать без service/option/brand/fact refs. Поэтому S12
переносит ровно три взаимозависимых owner-слоя: brands, offers и facts. Clinic strategy
и target marketing остаются следующим отдельным checkpoint; persisted заглушки
запрещены.

## Incomplete target-pack boundary

`clients/demo/target_response/` остаётся неполным будущим S2 pack. После S12 в нём есть
services, brands, offers и facts, но нет `clinic_strategy.yaml` и target
`marketing.yaml`. Real S2 `load_response_schema_bundle(...)` пока намеренно fail-closed
и не вызывается.

Acceptance test проверяет real data одним frozen `ResponseSchemaBundle` только с двумя
in-memory validation shells:

```python
strategy = {"version": 1, "default_max_options": 3, "rules": []}
marketing = {
    "version": 1,
    "limits": {
        "max_marketing_facts_per_turn": 0,
        "max_amplifiers_per_turn": 0,
        "max_scenarios_per_turn": 0,
    },
    "initial_commercial_blocks": {},
    "scenario_rules": {},
    "cta_contexts": {"default": "validation_only"},
}
```

Shells не записываются, не экспортируются и запрещены как product defaults/strategy.

## Затрагиваемые файлы

- `TASK.md`;
- `clients/demo/target_response/brand_catalog.json` (new);
- `clients/demo/target_response/pricebook/facts.json` (new);
- `clients/demo/target_response/pricebook/services/*.json` (31 new files);
- `tests/test_demo_target_price_offers.py` (new);
- `docs/STRANGLER_ROADMAP.md` — pending `[ ]`, затем `[x]` только после completion
  checker `✅`.

Любой другой файл требует остановки и отдельного решения владельца/Архитектора.

## Protected / вне scope

- весь current `clients/demo/pricebook/**`, aliases, marketing, current service catalog,
  MD, doctor catalog и остальные current client files;
- S11 `clients/demo/target_response/service_catalog.json`;
- весь `clients/cesi/**` и `clients/nikadent/**`;
- frozen S1–S11 contracts/loaders/builders/tests и изменение target schema/layout;
- persisted strategy, target marketing, manifest/groups и CTA;
- adapter/converter/dual-read/fallback/runtime loader wiring;
- selection/applicability, filtering, ranking, brand comparison, promo/cadence policy;
- TurnFrame/session/follow-up focus, rendering/composer/verifier, routes/API/app/UI;
- protected acceptance/golden/eval fixtures;
- весь A9 design/raw/frozen/harness/evidence и A9 live re-audit;
- live/LLM, merge, `main`, другие ветки и изменение product authority.

## Нормативный brand catalog

`brand_catalog.json` exact:

```json
{
  "version": 1,
  "brands": {
    "implantium": {
      "canonical_name": "Implantium",
      "country": "Южная Корея",
      "aliases": ["имплантиум"]
    },
    "impro": {
      "canonical_name": "Impro",
      "country": "Германия",
      "aliases": ["импро"]
    },
    "nobel_biocare": {
      "canonical_name": "Nobel Biocare",
      "country": "Швейцария",
      "aliases": ["nobel", "нобель", "нобел"]
    }
  }
}
```

Canonical names/countries подтверждаются current variant labels. Aliases exact
проецируются из `price_brand_aliases.json`, кроме lowercase canonical name.
`partial/full/closed/open` являются S11 options и как brands запрещены.

## Offer file law

Каждый file содержит ровно один frozen `TargetOffer` mapping без wrapper:

- 15 simple services → `<service_id>.default` в `<service_id>.default.json`;
- 16 complex variants сохраняют exact current `offer_id` и filename
  `<offer_id>.json`;
- итого exact 31 unique IDs/files;
- filename/ID parity проверяется real-data test, но loader не выводит ID из filename.

Все offers:

- exact `service_id`, source amount/min_amount, `currency`, fact refs/order;
- `active: true`;
- current simple `fixed/from` → target `fixed/from`;
- complex variant total → `fixed`, кроме двух `sinus_lift` variants → `from` по owner
  decision и authored dependency statement;
- complex `package.includes` exact current list; simple includes empty;
- optional `option_id`/`brand_id` keys отсутствуют, когда model value `None`;
- только current `aspect == includes` followup сохраняется как
  `{id: includes, exact label, exact action}`.

## Exact option / brand linkage

- removable `partial/full` → одноимённые `option_id`, no brand;
- sinus `closed/open` → одноимённые `option_id`, no brand;
- `Implantium/Impro/Nobel Biocare` → `implantium/impro/nobel_biocare` brand IDs;
- simple offers имеют no option/brand.

Никакая связь не выводится из filename или human label.

## Exact billing units и owner-approved package labels

| service_id | billing_unit | exact package.label |
|---|---|---|
| `aligners` | `course` | `за полный курс лечения; зависит от сложности прикуса и количества кап` |
| `all_on_4` | `jaw` | `за одну челюсть; КТ и костная пластика по показаниям — отдельно` |
| `all_on_6` | `jaw` | `за одну челюсть; КТ и костная пластика по показаниям — отдельно` |
| `caries` | `tooth` | `за лечение одного зуба; зависит от глубины поражения и объёма пломбирования` |
| `clasp_dentures` | `unit` | `за один протез; частичное восстановление, вариант на кламмерах или замках` |
| `classic` | `tooth_package` | `за один зуб под ключ; КТ при необходимости — отдельно` |
| `implant_supported_prosthetics` | `tooth` | `за ортопедический этап для одного зуба (коронка/мост); имплантация оплачивается отдельно` |
| `one_stage` | `tooth_package` | `за один зуб под ключ; КТ и лечение воспаления до операции — по показаниям, отдельно` |
| `periodontitis` | `course` | `за полный курс лечения; точный план после диагностики дёсен` |
| `professional_whitening` | `procedure` | `за одну процедуру; точная стоимость зависит от выбранного протокола` |
| `pterygoid_implants` | `implant` | `за один имплант; коронка или протез — отдельно` |
| `pulpitis` | `tooth` | `за лечение одного зуба: лечение каналов и восстановление зуба; при необходимости коронка оплачивается отдельно` |
| `removable_dentures` | `jaw` | `за одну челюсть; имплантация — отдельно` |
| `sinus_lift` | `procedure` | `за одну область; стоимость зависит от объёма костного материала и способа доступа; имплант, коронка и КТ — отдельно` |
| `teeth_treatment` | `tooth` | `за лечение одного зуба` |
| `temporary_teeth` | `tooth` | `за одну временную коронку на период приживления; постоянная коронка — отдельно` |
| `tomography` | `procedure` | `за одно исследование` |
| `tooth_extraction` | `tooth` | `за удаление одного зуба; сложное удаление или зуб мудрости — по результатам осмотра` |
| `veneers` | `tooth` | `за один зуб; полная реставрация улыбки рассчитывается на консультации` |
| `zirconia_crowns` | `unit` | `за одну конструкцию; стоимость зависит от сложности и типа — коронка или мост` |
| `zygomatic_implants` | `jaw` | `за одну челюсть; временный и постоянный протез — по плану лечения` |

Все variants одной service используют одинаковые unit/label. `jaw` означает одну
челюсть; `tooth_package` не умножается; `unit` не переименовывается автоматически.

## Осознанно удаляемая legacy complexity

По owner decision не мигрируют `recommended`, `payment_stages`, отдельный `excludes`,
`note`, `intro_text`, `tags`, `promo`, `cta_key`, stage followups, dead pulpitis
followup и manifest/groups.

- существенные note/excludes границы сохранены в labels выше;
- exact structured includes сохранены;
- `recommended` позже принадлежит clinic strategy;
- stages не имеют target data и поэтому не создают мёртвых buttons;
- current pulpitis detail ref указывает на отсутствующий file/chunk и не переносится;
- никаких compatibility fields/fallbacks не создаётся.

## Commercial facts law

Target `facts.json` — plain mapping шести current IDs в exact current order. Для каждого:

- exact `id/kind/text_fact/render_mode`;
- `active: true`;
- `allowed_service_ids` — target service-catalog order services, где current price file
  содержит fact ref;
- `incompatible_with: []`, no `active_from` key;
- non-null `detail_ref` exact current; при current null key отсутствует и validated
  model имеет `detail_ref is None`;
- `active_until` key есть только при source-owned дате: current fact date или exact
  `2026-12-31` из promo rule для `implant_same_day_discount`; иначе key отсутствует и
  validated model имеет `active_until is None`.

Для трёх promo facts test отдельно требует set-parity `allowed_service_ids`, exact
`active: true` и `active_until` с current `marketing.yaml/promo_rules`; authored target
order при этом остаётся service-catalog order.

Legacy `usable_in`, `followup_label`, routes/aspects/CTA не мигрируют: они принадлежат
будущему target marketing. Все non-null detail refs существуют как `kb:<detail_ref>`.

## Aggregate / common-context law

Test собирает frozen `ResponseSchemaBundle` из real target data и validation-only shells,
доказывая service/option/brand/fact refs без нового validator-а.

Для каждого 21 service S10 с real bundle + S9 doctor catalog возвращает:

- exact service и все/только его offers, минимум один;
- exact doctors по S9 links;
- у `tomography` один offer и empty doctors;
- без sorting/filtering/rendering.

## Protected tests / честность

- new test читает real target/current sources, MD и doctor catalog только read-only;
- strict JSON helper запрещает duplicate keys на любом уровне;
- frozen S1 models/bundle/S10 используются напрямую; converter/schema не создаётся;
- expected units/labels/link maps независимы от target output;
- exact source amounts/currency/includes/fact refs сравниваются с current;
- before/after hashes идентичны;
- no current runtime loader/routes/session imports, writes, skip/xfail или mocks.

## Минимальные acceptance tests

1. Exact 3 brands, 6 facts, 31 sorted offer files/IDs; strict duplicate rejection.
2. Frozen S1 validation и `model_dump(exclude_none=True) == raw` для каждого record.
3. Exact 15 simple + 16 complex source projection, включая sinus `from` exception.
4. Exact owner-approved unit/label table, source amounts, RUB, includes, refs/links.
5. Только valid includes followups; stages/dead pulpitis/unknown actions отсутствуют.
6. Brand aliases/countries exact; pseudo-brands отсутствуют.
7. Facts exact, optional keys omitted, promo-rule parity и KB detail integrity.
8. Real aggregate valid; каждый service проходит S10 с offer и exact doctors.
9. No multiplication/strategy/ranking/runtime fields или persisted shells.
10. Read-only hashes и AST/source no-product-wiring audit.

## Verification

До data edits:

1. independent checker читает revised TASK, owner decision, all current price/fact/
   alias/promo sources, target catalogs, frozen S1/S2/S4/S8/S10, architecture docs,
   checklist и guardrails;
2. checker подтверждает устранение previous ❌: nine units, sinus from, corrected labels,
   optional fact keys, promo parity и exact validation shells;
3. при `❌`/`❓` TASK снова исправляется до data edits.

После реализации:

1. `.venv/codex312/Scripts/python.exe -m pytest tests/test_demo_target_price_offers.py -q --basetemp=.pytest_tmp_s12`;
2. `.venv/codex312/Scripts/python.exe -m pytest tests/test_response_schema_contract.py tests/test_response_schema_loader.py tests/test_service_data_context.py -q --basetemp=.pytest_tmp_s12_contracts`;
3. `.venv/codex312/Scripts/python.exe -m pytest tests/test_demo_target_service_catalog.py tests/test_demo_doctor_catalog.py -q --basetemp=.pytest_tmp_s12_neighbors`;
4. `.venv/codex312/Scripts/python.exe -m pytest tests/test_pricebook_contract.py tests/test_pricebook_loader.py -q --basetemp=.pytest_tmp_s12_legacy`;
5. `.venv/codex312/Scripts/python.exe scripts/lint_content.py --client demo` и
   `.venv/codex312/Scripts/python.exe scripts/lint_pricebook.py --client demo`;
6. `git diff --check`, clean allowlist diff; independent checker повторяет review/runs;
7. live/LLM и полный pytest не запускаются.

## Definition of Done

- all 21 services имеют минимум один target offer; всего exact 31;
- brands/options/facts/services связаны stable IDs и aggregate valid;
- source amounts/currency/includes/facts exact, owner units/labels explicit;
- S10 real common context offline собирает description pointer + prices + doctors;
- incomplete pack и удалённая legacy complexity описаны честно;
- runtime/answers/UI/session/A9/authority не изменены;
- roadmap S12 offline status независимо проверен;
- checker `✅`, отдельные governance/completion commits и push только в stage-a,
  рабочее дерево чистое.
