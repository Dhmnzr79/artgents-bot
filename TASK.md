# TASK — S20 Demo Target Marketing Policy Materialization

**Ветка:** `codex/stage-a`

**Baseline:** `3c578cf data: add demo consultation values S19`

**Серия / checkpoint:** `S20` — минимальная offline-материализация target marketing
policy для demo и проверка CTA/source references.

**Режим:** governance + один target YAML + isolated CTA-reference contract + narrow
synthetic/real-data acceptance + architecture status docs. Никаких selector/session,
ответов, routes/UI, live/LLM или product authority.

## Owner direction

21 июля 2026 владелец разрешил продолжить S-series после S19 и ранее подтвердил:

1. пять standard marketing scenarios из frozen target schema используются как общие
   стоматологические ситуации, но конкретные refs/порядок остаются client data;
2. clinic-specific приоритет задаётся простым ordered rule/pool, без ручного сценария
   под каждый возможный вопрос;
3. продающие акценты должны быть source-backed meanings, а не зашитые готовые ответы;
4. три demo `consultation_value` S19 остаются отдельным same-MD источником и не
   дублируются в target marketing policy;
5. `consultation_value` cadence уже является universal law S18 и не добавляется в
   client schema;
6. следующий минимальный шаг — заполнить target marketing data и проверить его
   offline, не подключая к ответам бота.

Demo не имеет live-клиентов. S20 не сохраняет старые combined-механизмы ради
совместимости и не создаёт adapter/dual-read.

## Архитектурное решение

### Что материализуется

Создать `clients/demo/target_response/marketing.yaml`, который проходит frozen S1
`TargetMarketingPolicy` и содержит только:

- универсальные лимиты `3 marketing facts / 2 amplifiers / 2 scenarios`;
- один initial commercial block для semantic context `service`;
- пять frozen scenario pools с exact ordered `fact:`/`kb:`/`doctor:` refs;
- четыре semantic CTA contexts: `service`, `price`, `doctors`, `default`.

YAML хранит только порядок, refs, contexts и CTA keys. В нём запрещены готовые фразы,
копии source facts, eligibility, route/aspect gates, labels и lead-flow copy.

### Exact target data

```yaml
version: 1
limits:
  max_marketing_facts_per_turn: 3
  max_amplifiers_per_turn: 2
  max_scenarios_per_turn: 2

initial_commercial_blocks:
  service:
    ordered_fact_refs:
      - fact:free_implant_consult
      - fact:installment_12
      - fact:implant_same_day_discount
      - fact:professional_whitening_discount

scenario_rules:
  pain_fear:
    ordered_amplifier_refs:
      - kb:implantation__faq__pain.md#korotko
      - kb:implantation__faq__pain.md#kakuyu-anesteziyu-ispolzuyut
    allowed_semantic_contexts:
      - service
  cost:
    ordered_amplifier_refs:
      - fact:installment_12
      - fact:implant_same_day_discount
      - fact:tax_deduction
      - kb:implantation__faq__cost.md#kak-sdelat-implantatsiyu-dostupnee
      - kb:clinic__info__payment_terms.md#korotko
    allowed_semantic_contexts:
      - service
      - price
  time:
    ordered_amplifier_refs:
      - kb:implantation__faq__duration.md#korotko
      - kb:implantation__faq__duration.md#mozhno-li-uskorit-implantatsiyu
      - kb:implantation__faq__tooth_one_day.md#korotko
      - kb:implantation__info__steps.md#korotko
    allowed_semantic_contexts:
      - service
  doctor_trust:
    ordered_amplifier_refs:
      - doctor:doctors__doctor__volkov
      - doctor:doctors__doctor__orlov
      - kb:doctors__doctor__overview.md#korotko
      - kb:clinic__info__technology.md#korotko
    allowed_semantic_contexts:
      - service
      - doctors
  result_reliability:
    ordered_amplifier_refs:
      - fact:implant_warranty
      - kb:implantation__faq__osseointegration.md#korotko
      - kb:implantation__faq__osseointegration.md#ot-chego-zavisit-prizhivlenie
      - kb:clinic__info__warranty.md#korotko
    allowed_semantic_contexts:
      - service

cta_contexts:
  service: plan
  price: price
  doctors: doctor
  default: callback
```

Порядок является приоритетом для будущего selector, но S20 selector не реализует.
Eligibility конкретного commercial fact остаётся только в target facts/offers; наличие
ref в block/pool само по себе не разрешает показать неприменимый факт.

### CTA ownership and integrity

- target policy хранит semantic context → CTA key;
- видимый label и lead-flow copy продолжают принадлежать `clients/demo/tone.yaml`;
- `service → plan`, `price → price`, `doctors → doctor`, fallback `default → callback`;
- legacy `ct_consultation` не переносится и не приравнивается к `consult`;
- все четыре target keys обязаны существовать в tone CTA index;
- pure validator возвращает один deterministic sorted typed error для всех missing keys;
- validator только проверяет уже переданные модели/index и ничего не читает сам.

### Legacy marketing decisions

- три S19 `consultation_value` — единственные отдельно опубликованные source meanings
  из этого migration thread;
- остальные 21 legacy free strings не копируются в target marketing policy и уходят
  вместе со старой combined-архитектурой, если отдельно не опубликованы в source MD;
- current `benefits` и `what_included` не являются target service IDs и не получают
  marketing-key mapping;
- current `teeth_whitening` не переносится как alias-key: target service уже называется
  `professional_whitening`, а применимый promo принадлежит commercial fact;
- current `clients/demo/marketing.yaml` и `patient_playbook.yaml` в S20 не меняются.

### Historical S17 acceptance

S17 корректно доказывал, что **на момент S17** target `marketing.yaml` отсутствовал.
После осознанной S20 materialization его acceptance test меняется только так, чтобы
проверять историческую запись в audit doc и frozen contract boundary, а не требовать
текущее отсутствие файла. Inventory, 24-string audit и все прочие protected
expectations не ослабляются.

## Цель

1. До data/code зафиксировать exact policy и границы в governance commit.
2. Добавить pure strict/frozen CTA key index и fail-closed reference validation.
3. Создать ровно один target `marketing.yaml` с exact data выше.
4. Доказать, что полный real demo target pack загружается S2 loader.
5. Доказать local `fact:` refs, external `kb:`/`doctor:` refs и CTA refs.
6. Сохранить runtime/answer/authority полностью unwired.

## Затрагиваемые файлы

- `TASK.md`;
- `contracts/marketing_cta_refs.py` — new pure CTA index/error/validator;
- `tests/test_marketing_cta_refs.py` — new synthetic contract tests;
- `clients/demo/target_response/marketing.yaml` — new exact target policy;
- `tests/test_demo_target_marketing_policy.py` — new read-only real-data acceptance;
- `tests/test_demo_target_marketing_migration_audit.py` — только замена obsolete
  current-absence assertion на historical-audit assertion;
- `docs/MARKETING_TARGET_MIGRATION_AUDIT.md` — S20 decision/status addendum;
- `docs/MARKETING_SCENARIO_ARCHITECTURE.md` — demo materialization status only;
- `docs/STRANGLER_ROADMAP.md` — pending `[ ]`, затем `[x]` только после completion
  checker `✅`.

Любой другой файл требует остановки и отдельного решения владельца/Архитектора.

## Protected / вне scope

- frozen `contracts/response_schema.py` и S1 model semantics;
- S2/S3/S4/S5/S6/S8 loaders/index builders/validators;
- current `clients/demo/marketing.yaml`, `patient_playbook.yaml`, `tone.yaml`, MD,
  current/target pricebook, service/brand/doctor catalogs и clinic strategy;
- новые/изменённые commercial facts, offers, doctors, services или source content;
- перенос оставшихся legacy free strings и изменение S19 consultation values;
- selector, matching, rotation, eligibility filtering, no-repeat/session state;
- ResponseSpec/evidence/composer/FullContext/prompt/cache;
- ответы, routes, API/app/UI/config, lead-flow и product authority;
- adapters, dual-read, fallback, feature flags и product wiring;
- protected golden/eval fixtures, кроме exact obsolete S17 absence assertion,
  явно разрешённого выше;
- A9 design/raw/frozen/harness/evidence и live re-audit;
- live/LLM, merge, `main`, другие ветки и изменение product authority.

## Exact CTA-reference contract

### `MarketingCtaIndex`

Frozen strict Pydantic model:

- `cta_keys`: immutable tuple of exact nonblank strings;
- duplicate keys fail validation deterministically;
- extra fields forbidden;
- order preserved; validator never treats the first key as default.

### `validate_marketing_cta_refs(policy, index)`

- принимает validated `TargetMarketingPolicy` и `MarketingCtaIndex`;
- проверяет every value из `policy.cta_contexts` against exact index keys;
- unknown keys собираются без дублей в один lexical sorted tuple;
- при missing бросает typed `MarketingCtaReferenceError` с stable code
  `marketing_cta_refs_missing` и field `missing_cta_keys`;
- при полном index возвращает `None`;
- stateless, не мутирует inputs, не читает files/env/config и не импортирует runtime.

S20 не создаёт общий tone loader. Real-data test извлекает CTA keys из существующего
`tone.yaml` read-only и передаёт их в pure index.

## Acceptance tests

### Synthetic CTA contract

`tests/test_marketing_cta_refs.py` доказывает:

1. все CTA refs принимаются, unused index key разрешён;
2. missing refs дают один typed sorted/deduplicated error;
3. exact case-sensitive matching;
4. strict/frozen/extra-forbid/nonblank/duplicate invariants index;
5. deterministic repeated calls, no mutation/writes;
6. AST/import boundary без clients, file IO, runtime/session/network/LLM.

### Real demo target policy

`tests/test_demo_target_marketing_policy.py` доказывает:

1. S2 loader загружает весь real `clients/demo/target_response` bundle;
2. exact limits, block order, five scenario order/refs/contexts и CTA map равны TASK;
3. S3/S4/S6 validators подтверждают все external KB/doctor refs;
4. все fact refs существуют локально и проходят bundle validation;
5. CTA keys, прочитанные из real tone config, unique и покрывают target policy;
6. current marketing/tone/playbook и все pre-existing target files не меняются;
7. никакого runtime wiring/import, skip/xfail, live/LLM или writes.

S17 audit acceptance сохраняет все inventory assertions и меняет только obsolete
утверждение о текущем отсутствии target file.

## Verification

До implementation:

1. governance TASK + roadmap pending коммитятся отдельно и push только в
   `codex/stage-a`;
2. independent read-only checker читает TASK, S17 audit/tests, frozen schema/loader/ref
   boundaries, exact facts/KB/doctors/tone и architecture/checklist/guardrails;
3. checker подтверждает exact policy, source existence, CTA ownership, legacy decisions,
   obsolete-test transition и no-runtime/no-authority boundary;
4. при `❌`/`❓` governance исправляется и проверяется повторно до code/data.

После implementation:

1. `.venv/codex312/Scripts/python.exe -m pytest tests/test_marketing_cta_refs.py tests/test_demo_target_marketing_policy.py tests/test_demo_target_marketing_migration_audit.py -q --basetemp=.pytest_tmp_s20_policy`;
2. `.venv/codex312/Scripts/python.exe -m pytest tests/test_response_schema_contract.py tests/test_response_schema_loader.py tests/test_response_schema_refs.py tests/test_response_schema_kb_index.py tests/test_doctor_schema_refs.py -q --basetemp=.pytest_tmp_s20_neighbors`;
3. `git diff --check`, exact allowlist, no skip/xfail, no full pytest;
4. independent completion checker повторяет review и команды;
5. roadmap `[x]`, completion commit/push only `codex/stage-a`, tree clean/synced.

## Definition of Done

- real demo target pack впервые полностью загружается offline;
- policy содержит ровно approved limits/block/five pools/four CTA contexts;
- все fact/KB/doctor/CTA refs fail-closed проверены через owner boundaries;
- 21 legacy free strings и legacy alias keys не продублированы;
- frozen S1/S2/S3 contracts не изменены;
- selector/session/answer/UI/runtime/A9/authority не подключены;
- independent governance и completion reviews `✅`;
- commits/push только `codex/stage-a`, working tree clean и HEAD synced с origin.
