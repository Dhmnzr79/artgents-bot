# TASK — S17 Demo Target Marketing/CTA Migration Audit

**Ветка:** `codex/stage-a`

**Baseline:** `9ae7557 data: materialize demo clinic strategy S16`

**Серия / checkpoint:** `S17` — read-only аудит current demo marketing/CTA sources до
materialization target marketing policy.

**Режим:** governance + deterministic inventory tests + audit docs only. Никаких client
data changes, target `marketing.yaml`, product consumers, ответов, routes/UI, live/LLM
или product authority.

## Owner direction

21 июля 2026 владелец подтвердил, что marketing/CTA уже были согласованы на уровне
архитектуры, и разрешил продолжить следующим безопасным шагом: сначала точный аудит
миграции, а не повторный redesign и не немедленное подключение.

В demo нет live-клиентов. S17 не обязан сохранять legacy marketing copy ради continuity:
он обязан честно определить, что source-backed переносится в target, что должно получить
нового владельца, а что можно позднее удалить без compatibility adapters/fallbacks.

## Основание

- `docs/MARKETING_SCENARIO_ARCHITECTURE.md` уже фиксирует product/design law: общий limit
  `3`, максимум `2` amplifiers и `2` scenarios, пять standard scenarios, source refs,
  no-repeat/direct-question law и стабильную CTA по semantic context.
- S1 уже реализовал frozen `TargetMarketingPolicy` models, а S2 loader требует
  `marketing.yaml`; header architecture doc про полностью отсутствующую schema устарел.
- S12 materialized шесть source-owned commercial facts.
- S16 materialized clinic strategy, но real demo target pack всё ещё не загружается S2,
  потому что target `marketing.yaml` отсутствует.
- Current `clients/demo/marketing.yaml` — active legacy combined schema с free copy,
  promo eligibility, classifier route/aspect gates и CTA keys.
- CTA keys также распределены между current MD, pricebook, patient playbook, tone/UI и
  marketing. Их нельзя механически скопировать в один target owner.

## Цель

Создать точный read-only migration audit, который:

1. инвентаризирует current marketing и все current CTA owners;
2. сопоставляет их с frozen target marketing/CTA ownership;
3. отделяет уже materialized commercial facts от legacy routing/copy;
4. проверяет, какие free marketing strings имеют exact KB source, а какие не имеют;
5. фиксирует candidate source refs для пяти scenarios без утверждения их ranking;
6. перечисляет owner decisions и contract gaps до materialization;
7. предлагает минимальный следующий data/schema checkpoint, но ничего не реализует.

## Затрагиваемые файлы

- `TASK.md`;
- `docs/MARKETING_TARGET_MIGRATION_AUDIT.md` — new exact audit;
- `tests/test_demo_target_marketing_migration_audit.py` — new read-only inventory tests;
- `docs/MARKETING_SCENARIO_ARCHITECTURE.md` — status correction only;
- `docs/STRANGLER_ROADMAP.md` — pending `[ ]`, затем `[x]` только после completion
  checker `✅`.

Любой другой файл требует остановки и отдельного решения владельца/Архитектора.

## Protected / вне scope

- весь `clients/demo/**`, включая current `marketing.yaml`, `tone.yaml`, `ui.yaml`, MD,
  patient playbook, pricebook и весь `target_response/**`;
- создание `clients/demo/target_response/marketing.yaml`;
- `contracts/**`, `core/**`, orchestration, routes/API/app/UI/config;
- изменение frozen marketing models, loader или reference validators;
- переписывание/перенос 24 legacy free marketing strings в MD;
- выбор exact initial block, scenario pool order или CTA context mapping;
- selector, cadence/session, no-repeat, direct-question override и incompatibility code;
- исправление current marketing/runtime или удаление legacy data;
- adapters, dual-read, fallback, feature flags и product wiring;
- protected golden/eval fixtures;
- A9 design/raw/frozen/harness/evidence и live re-audit;
- live/LLM, merge, `main`, другие ветки и изменение product authority.

## Frozen exact inventory

S17 tests/audit обязаны проверить, а не предположить следующие source facts.

### Current marketing

`clients/demo/marketing.yaml`:

- `version: 1`;
- global `blocked_aspects_for_promo` exact:
  `pain`, `contraindications`, `safety`, `complications`;
- exact 13 `service_marketing` keys в authored order:
  `classic`, `one_stage`, `all_on_4`, `all_on_6`, `temporary_teeth`, `benefits`,
  `what_included`, `sinus_lift`, `pterygoid_implants`, `zygomatic_implants`,
  `teeth_whitening`, `tooth_extraction`, `periodontitis`;
- 11 `clinic_proof` strings;
- 13 `consult_reasons` strings;
- exact CTA distribution: `doctor: 10`, `consult: 3`;
- 3 promo rules:
  `free_implant_consult`, `implant_same_day_discount`,
  `professional_whitening_discount`;
- exact promo fact refs совпадают с rule IDs и уже существуют в target facts;
- только `free_implant_consult` содержит legacy `cta_key: consult`.

Из 13 marketing keys ровно 10 совпадают с canonical target service IDs. Три не
совпадают:

- `benefits` и `what_included` — content topics, не services;
- `teeth_whitening` — legacy alias/name, target canonical ID
  `professional_whitening`.

Все 24 free strings (`11 + 13`) должны проверяться exact substring against current
`clients/demo/md/*.md`. Frozen observed count exact matches — `0`. S17 не объявляет
строки ложными: он доказывает только, что их нельзя механически превратить в target
`kb:` refs без отдельной source-content миграции/решения владельца.

### Commercial facts

Target `pricebook/facts.json` содержит exact шесть facts:

- `tax_deduction`;
- `installment_12`;
- `free_implant_consult`;
- `implant_warranty`;
- `implant_same_day_discount`;
- `professional_whitening_discount`.

Три current promo fact refs уже входят в эти шесть. Active/date/service eligibility и
exact text принадлежат target fact records, поэтому current `promo_rules` не являются
вторым target source для этих fields.

Для всех трёх promo rules exact `active`, optional `active_until` и **set** allowed
service IDs совпадают с target facts. Authored list order совпадает только у whitening;
у двух implant promo порядок отличается и не трактуется как priority/behavior signal.

Legacy `allowed_routes`, `allowed_aspects`, `blocked_aspects`, global blocked list и
promo-local CTA нельзя молча переносить: target architecture заменяет classifier gates
common scenario/manual-contact/semantic-context laws.

### CTA owners

- `tone.yaml` имеет exact шесть CTA variants:
  `booking`, `consult`, `callback`, `plan`, `price`, `doctor`; здесь живут visible labels
  и first lead-flow copy.
- 54 MD files имеют CTA-key distribution:
  `booking: 6`, `callback: 2`, `consult: 13`, `doctor: 6`, `plan: 25`, `price: 2`.
- все 21 current pricebook service files имеют `cta_key: price`.
- current patient playbook rules: `ct_consultation: 7`, `consult: 1`.
- current service marketing: `doctor: 10`, `consult: 3`.
- `ct_consultation` отсутствует среди tone CTA variants и требует explicit retirement
  или mapping decision; S17 mapping не выбирает.

Target `cta_contexts` materialized data отсутствует. Frozen model требует только
nonblank keys/values и `default`, но не проверяет CTA value против `tone.yaml`; это
contract/integration gap для следующего checkpoint, не разрешение менять S1 в S17.

### Target marketing boundary

- `clients/demo/target_response/marketing.yaml` отсутствует;
- S2 `load_response_schema_bundle(real_demo_target_root)` fail-closed с
  `required_path_missing` и relative path `marketing.yaml`;
- frozen target scenarios exact:
  `pain_fear`, `cost`, `time`, `doctor_trust`, `result_reliability`;
- frozen limits допускают required target law `3/2/2`;
- bundle проверяет `fact:` refs локально; exact `kb:`/`doctor:` refs требуют existing
  S3/S4/S6 external integrity boundary;
- frozen policy не содержит free amplifier text.

Architecture doc говорит, что client marketing policy хранит cadence policy, но frozen
`TargetMarketingPolicy` не имеет cadence field. Audit обязан вынести это как явный gap:
либо no-repeat/direct-question cadence является universal runtime law и удаляется из
client-data ownership, либо schema требует отдельного будущего governance change.

## Candidate map, not target data

Audit может перечислить только source-backed candidates:

- `pain_fear`: exact chunks из `implantation__faq__pain.md`;
- `cost`: `fact:` payment/promo/benefit refs и exact cost/payment chunks;
- `time`: exact duration/steps/one-day chunks;
- `doctor_trust`: exact `doctor:` refs и approved doctor/technology content;
- `result_reliability`: exact osseointegration/warranty refs.

Каждый candidate обязан проходить проверку своего owner boundary: `fact:` — через real
target `ResponseSchemaBundle`/local fact index, `kb:` — через S4-built KB index + S3
external validation, `doctor:` — через S6-built doctor refs + S3 external validation.
Candidate list не утверждает его включение, priority, service eligibility или automatic
display. S17 не создаёт scenario pools и не переносит free strings.

## Owner decisions after audit

Audit должен вынести владельцу отдельным коротким списком:

1. сохранить ли 24 legacy free strings через отдельную редактуру/source publication в
   MD или удалить их при retirement legacy;
2. exact semantic contexts и initial commercial blocks для demo;
3. exact source refs/order для каждого из пяти scenario pools;
4. CTA context map + clinic default и retirement/mapping `ct_consultation`;
5. cadence ownership: universal runtime law или client schema data;
6. нужен ли contract validator `cta_context value → tone CTA key` до materialization;
7. status двух content-topic keys и canonical rename `teeth_whitening`.

Ни одно решение не должно быть принято Исполнителем внутри S17 audit.

## Read-only acceptance

`tests/test_demo_target_marketing_migration_audit.py` обязан доказать:

1. exact current marketing inventory/counts/order выше;
2. exact canonical/noncanonical service-key split;
3. exact 24 free strings и zero exact MD matches;
4. exact promo rules/refs, active/date и allowed-service set parity с target facts,
   включая non-semantic list-order difference у двух implant promo;
5. exact CTA variants/distributions и unresolved `ct_consultation` mismatch;
6. target marketing absence + exact S2 fail-closed result;
7. five frozen scenarios/limits/model boundary через contract introspection/validation,
   без изменения contracts;
8. candidate refs в audit doc реально существуют через exact owner boundaries:
   `fact:` — real target bundle/local fact index, `kb:` — S4 KB index + S3 validation,
   `doctor:` — S6 doctor refs + S3 validation;
9. current/target source hashes unchanged;
10. no new product/runtime wiring/imports; existing S1/S2/S3/S4/S6 offline
    contracts/helpers may be imported for this audit; no writes, skip/xfail, live or LLM.

Tests не должны кодировать будущие выбранные pools/CTA map как approved expected data.

## Audit document

`docs/MARKETING_TARGET_MIGRATION_AUDIT.md` обязан содержать:

- простое объяснение «design/models уже есть; real target data/runtime ещё нет»;
- exact inventory и owner map;
- таблицу current field → target owner/defer/retire;
- five-scenario candidate refs с маркировкой `candidate, not approved`;
- contract/doc gaps;
- семь owner decisions выше;
- минимальный recommended next checkpoint, не materialization без решений;
- no-current/no-target-data/no-authority statement.

`docs/MARKETING_SCENARIO_ARCHITECTURE.md` меняет только status: frozen schema models
реализованы S1; demo target policy, selector/session/runtime и authority отсутствуют.
Нормативные product rules не редактируются.

## Verification

До audit/test/docs edits:

1. independent checker читает TASK, current marketing/tone/UI/MD/playbook/pricebook,
   target facts/pack, S1/S2/S3/S4/S6 contracts/helpers, architecture docs,
   checklist/guardrails;
2. checker подтверждает exact inventory, audit-only boundary, owner questions and no
   hidden materialization/authority;
3. при `❌`/`❓` TASK исправляется до audit implementation.

После реализации:

1. `.venv/codex312/Scripts/python.exe -m pytest tests/test_demo_target_marketing_migration_audit.py -q --basetemp=.pytest_tmp_s17_audit`;
2. `.venv/codex312/Scripts/python.exe -m pytest tests/test_marketing_loader.py tests/test_response_schema_contract.py tests/test_response_schema_loader.py tests/test_response_schema_refs.py -q --basetemp=.pytest_tmp_s17_neighbors`;
3. `git diff --check`, exact allowlist и independent checker repeat;
4. no full pytest, no live/LLM.

## Definition of Done

- exact current marketing/CTA inventory independently verified;
- already materialized facts separated from legacy combined schema;
- 24 free strings and zero exact KB matches visible, not silently lost or copied;
- five scenario candidate sources exist but are not falsely approved;
- CTA mismatch and cadence/cross-ref gaps explicit;
- owner receives bounded decisions before target data;
- no client data, schema/code/runtime/A9/authority changes;
- roadmap S17 independently reviewed;
- checker `✅`, governance/completion commits and push only to `codex/stage-a`, tree clean.
