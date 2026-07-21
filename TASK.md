# TASK — S16 Demo Target Clinic Strategy Materialization

**Ветка:** `codex/stage-a`

**Baseline:** `2795e0e feat: resolve target clinic strategy S15`

**Серия / checkpoint:** `S16` — materialization проверенных current demo priorities в
offline target `clinic_strategy.yaml`.

**Режим:** demo target data/tests/docs only. Никаких current client-data changes,
product consumers, ответов, routes/UI, live/LLM или product authority.

## Owner direction

21 июля 2026 владелец подтвердил:

- current `patient_playbook.yaml` действительно является источником приоритетов;
- клиника должна задавать свои приоритеты конфигом без изменения общего кода;
- правила нужны только для нескольких значимых ситуаций, а не под каждую фразу;
- после завершения S15 владелец разрешил продолжать materialization;
- после checker `❓` владелец отдельно одобрил перенос **семи** универсальных
  стоматологических ситуаций и безопасное defer общего `bone_deficit_solution`.

S16 переносит existing demo decisions. Новые медицинские/коммерческие предпочтения не
придумываются.

## Основание

- S14 exact audit учёл 8 current rules + один duplicate fallback, разложил ownership и
  зафиксировал шесть current `recommended=true` offers.
- S15 добавил explicit baseline priorities и pure ordered first-match resolver.
- S11 selection уже владеет applicability: stage/jaw/reported context/show_when не
  должны дублироваться как medical logic в strategy.
- Target strategy ещё не материализована; target marketing тоже отсутствует, поэтому
  real target pack остаётся неполным и не подключённым.

## Цель

Создать:

- `clients/demo/target_response/clinic_strategy.yaml`;
- `tests/test_demo_target_clinic_strategy.py`.

Data обязана:

1. пройти `TargetClinicStrategy` и `ResponseSchemaBundle` cross-refs;
2. сохранить exact current ordered service priorities семи owner-approved rules;
3. заменить current classifier match только audited neutral target axes;
4. расположить specific exceptions выше general rules для S15 first-match;
5. перенести шесть positive offer recommendation signals в baseline;
6. ограничить current `max_options: 4` до approved target `3`, не удаляя services;
7. не переносить CTA, answer style, roles, positioning, strategy labels или fallback;
8. остаться offline/unwired.

## Затрагиваемые файлы

- `TASK.md`;
- `clients/demo/target_response/clinic_strategy.yaml` — new target data;
- `tests/test_demo_target_clinic_strategy.py` — new real-data acceptance;
- `docs/PATIENT_PLAYBOOK_MIGRATION_AUDIT.md` — materialization status;
- `docs/PRICE_SERVICE_ARCHITECTURE.md` — demo status only, no semantic redesign;
- `docs/STRANGLER_ROADMAP.md` — pending `[ ]`, затем `[x]` только после completion
  checker `✅`.

Любой другой файл требует остановки и отдельного решения владельца/Архитектора.

## Protected / вне scope

- current `clients/demo/patient_playbook.yaml`, current pricebook/marketing/catalog/MD;
- остальные `clients/demo/target_response/**` files;
- `contracts/**`, `core/**`, orchestration, routes/API/app/UI;
- S15 resolver/contract/tests;
- создание target `marketing.yaml` или перенос CTA/copy;
- исправление двух current S14 test mismatches;
- role/positioning ownership, current fallback retirement;
- eligibility filtering, dialog focus/session, planner/TurnFrame;
- response composition, price/doctor rendering, buttons;
- adapters, dual-read, fallback, feature flags и product wiring;
- protected golden/eval fixtures;
- A9 design/raw/frozen/harness/evidence и live re-audit;
- live/LLM, merge, `main`, другие ветки и изменение product authority.

## Exact target top-level data

```yaml
version: 1
default_max_options: 3
default_service_priorities: {}
default_offer_priorities:
  all_on_4.jaw.impro: 1
  all_on_6.jaw.impro: 1
  classic.one_tooth.impro: 1
  one_stage.one_tooth.impro: 1
  removable_dentures.jaw.partial: 1
  sinus_lift.one_site.closed: 1
rules: ...
```

`default_service_priorities` empty, потому что current playbook не содержит одного
универсального service order вне ситуации.

Positive current `recommended=true` проецируется в relative priority `1`; отсутствующий
priority по S15 равен `0`. Это сохраняет только boolean order signal и не выдумывает
дополнительный ranking между false offers. Все шесть target offer IDs обязаны существовать.

Другие current variants с `recommended=false`/missing не добавляются в baseline map.

## Exact rules and authored order

S16 materializes ровно семь rules в следующем owner-approved S15 first-match order:

### 1. `existing_implant_prosthetic_stage`

```yaml
match:
  stage: implant_placed
max_options: 3
service_priorities:
  implant_supported_prosthetics: 100
  zirconia_crowns: 60
  temporary_teeth: 40
offer_priorities: {}
```

Installed-implant stage идёт первым: strategy не должна ставить новые implant protocols
выше протезирования на уже установленном импланте. Это ordering law, не eligibility
filter: до будущего product wiring caller всё равно обязан передать candidates одного
актуального treatment focus.

### 2. `extraction_then_implant_restore`

```yaml
match:
  extent: one_tooth
  stage: extraction_context
max_options: 3
service_priorities:
  one_stage: 100
  classic: 80
  tooth_extraction: 40
offer_priorities: {}
```

Правило intentionally сужено до owner-approved ситуации одного зуба. Оно стоит выше
`one_tooth_restore` и закрывает обнаруженный S14 precedence gap только в target data.
Current code/test не меняются. Full-arch context не удовлетворяет этому match.

### 3. `upper_full_arch_with_bone_deficit`

```yaml
match:
  extent: full_arch
  jaw: upper
  reported_context: reported_bone_deficit
max_options: 3
service_priorities:
  zygomatic_implants: 100
  all_on_4: 90
  all_on_6: 80
  removable_dentures: 40
offer_priorities: {}
```

Current max `4` становится target `3`.

### 4. `upper_full_arch_restore`

```yaml
match:
  extent: full_arch
  jaw: upper
max_options: 3
service_priorities:
  all_on_4: 100
  all_on_6: 90
  zygomatic_implants: 70
  removable_dentures: 40
offer_priorities: {}
```

Current max `4` становится target `3`. Без reported deficit S11 не допускает zygomatic
service; strategy map сама её не добавляет.

### 5. `full_arch_restore`

```yaml
match:
  extent: full_arch
max_options: 3
service_priorities:
  all_on_4: 100
  all_on_6: 90
  removable_dentures: 50
  zygomatic_implants: 40
offer_priorities: {}
```

Current max `4` становится target `3`.

### 6. `one_tooth_restore`

```yaml
match:
  extent: one_tooth
max_options: 2
service_priorities:
  classic: 100
  one_stage: 80
offer_priorities: {}
```

S11 `one_stage` applicability продолжает требовать extraction context; strategy не
ослабляет это условие.

### 7. `few_teeth_restore`

```yaml
match:
  extent: few_teeth
max_options: 3
service_priorities:
  implant_supported_prosthetics: 100
  classic: 80
  clasp_dentures: 50
  removable_dentures: 40
offer_priorities: {}
```

Current max `4` становится target `3`.

## Deliberately not migrated

- `match.problem`, `match.kind`, `match.intent`, current `modifiers` wire;
- `primary_cta`;
- current `strategy` labels;
- `answer_style`;
- option `role` and `positioning`;
- `show_when` (owned by S11 selection);
- duplicate `patient_situations.full_arch_missing` fallback;
- generic `bone_deficit_solution`: current rule требует одновременно reported deficit
  и `intent=choose_solution`, а frozen target strategy не получает intent;
- negative/false offer recommendation entries.

Отсутствие этих fields в strategy file является audited ownership split, а не потерей
данных по невнимательности. Role/positioning и CTA остаются отдельно unresolved/deferred.

## Real-data acceptance

`tests/test_demo_target_clinic_strategy.py` обязан доказать:

1. YAML top-level exact mapping, no duplicate keys and no unexpected files touched;
2. `TargetClinicStrategy.model_validate(raw).model_dump(exclude_none=True) == raw`;
3. exact rule count/order/IDs/matches/max/priorities равны frozen seven-rule target выше;
4. exact service-priority numbers/order проецируют seven approved current rules;
5. ровно четыре current rules с max `4` стали target `3`; other three preserve `2/3`;
6. fallback и generic `bone_deficit_solution` не материализованы отдельными rules;
7. exact six default offer keys равны variants с current `recommended=true` и имеют `1`;
8. false/missing recommendations отсутствуют;
9. all default/rule refs exist in target services/offers through a real
   `ResponseSchemaBundle` with validation-only synthetic marketing;
10. S15 resolver on real target IDs proves:
    - implant placed + full arch + upper + reported deficit selects installed-implant
      rule and puts implant-supported prosthetics first;
    - extraction + one tooth selects extraction rule before one-tooth rule, including
      when reported deficit is also present;
    - extraction + full arch does not match one-tooth extraction rule;
    - upper full arch + reported deficit selects upper-bone rule and orders
      zygomatic → All-on-4 → All-on-6;
    - few teeth caps exact top three while fourth remains a valid input candidate;
    - selected recommended offer moves first without adding offers;
11. client/current/target source hashes outside new strategy stay unchanged;
12. AST/no-product-wiring audit stays read-only.

Expected real context results prove target data + already checked S15 resolver only. Они
не доказывают current parity, language understanding или product behavior.

## Documentation

- S14 audit отмечает, что seven approved priorities и six recommendation signals
  materialized, а generic bone rule safely deferred;
- architecture doc отмечает demo strategy data exists offline, target marketing/wiring
  still absent;
- roadmap S16 pending/completed preserves known current `15 passed, 2 failed` and no
  authority.

## Verification

До data/test/docs edits:

1. independent checker читает TASK, S14 audit, current playbook/price recommendations,
   target services/offers, S15 contract/resolver, architecture docs, checklist/guardrails;
2. checker подтверждает exact seven-rule mapping, owner-approved overlap precedence,
   generic bone defer, neutral axes, max 4→3, boolean recommendation projection and no
   hidden product authority;
3. при `❌`/`❓` TASK исправляется до data.

После реализации:

1. `.venv/codex312/Scripts/python.exe -m pytest tests/test_demo_target_clinic_strategy.py -q --basetemp=.pytest_tmp_s16_data`;
2. `.venv/codex312/Scripts/python.exe -m pytest tests/test_target_strategy_resolution.py tests/test_response_schema_contract.py -q --basetemp=.pytest_tmp_s16_unit`;
3. `.venv/codex312/Scripts/python.exe -m pytest tests/test_response_schema_loader.py tests/test_service_data_context.py -q --basetemp=.pytest_tmp_s16_neighbors`;
4. `.venv/codex312/Scripts/python.exe -m pytest tests/test_demo_target_service_catalog.py tests/test_demo_target_price_offers.py -q --basetemp=.pytest_tmp_s16_existing_data`;
5. `git diff --check`, exact allowlist and independent checker repeat;
6. no live/LLM and no full pytest.

Known S14 current playbook result (`15 passed, 2 failed`) остаётся documented и не
используется как green gate. S16 не меняет current files/tests и не заявляет current fix.

## Definition of Done

- demo target clinic strategy materializes seven owner-approved audited situations;
- specific-first order resolves target extraction precedence without current edits;
- installed-implant rule wins overlap ordering, while eligibility/focus remains outside
  strategy and product wiring;
- generic bone rule remains audited/deferred until exact choose-solution invocation exists;
- four max-4 lists become approved max-3 without deleting services;
- exact six offer recommendations preserved as relative baseline order;
- all refs and representative real resolutions validated offline;
- target marketing/product wiring/A9/authority absent;
- known current mismatches visible and untouched;
- roadmap S16 independently reviewed;
- checker `✅`, governance/completion commits and push only to `codex/stage-a`, tree clean.
