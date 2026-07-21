# TASK — S14 Patient Playbook Target Migration Audit

**Ветка:** `codex/stage-a`

**Baseline:** `6f1c615 data: preserve target payment stages S13`

**Серия / checkpoint:** `S14` — read-only decomposition audit действующего
`clients/demo/patient_playbook.yaml` перед переносом приоритетов в target architecture.

**Режим:** documentation/audit only. Никаких client-data, schema/runtime, ответов,
routes/UI, live/LLM или product authority.

## Контекст и решение владельца

21 июля 2026 владелец остановил предположение, что приоритетов клиники нет, и указал на
`clients/demo/patient_playbook.yaml`. Проверка подтвердила: это действующий current
config старой архитектуры, который сейчас управляет demo options overview. Он не
является пустым архивом и не должен заменяться новым файлом вслепую.

В target architecture его обязанности разделены между:

- `service_catalog.json` — применимость услуги;
- будущим `clinic_strategy.yaml` — коммерческий порядок уже допустимых услуг/offers;
- будущим target `marketing.yaml` — CTA и marketing policy;
- dialog/session facts — известные признаки ситуации пациента;
- общими product guardrails — запрет медицинского обещания и одиночного «победителя».

До материализации target strategy нужен exact audit: что уже перенесено, что имеет
однозначного target-owner, что дублируется и какие части требуют отдельного решения.

## Цель

Создать `docs/PATIENT_PLAYBOOK_MIGRATION_AUDIT.md`, который простым языком и технически
точно:

1. подтверждает, что current playbook активен и пока остаётся неизменным;
2. инвентаризирует все восемь `rules` и один `patient_situations` fallback;
3. раскладывает каждое поле current playbook по target-owner или отмечает unresolved;
4. сверяет уже материализованные S11 selection facts с current `show_when`/match;
5. отделяет service priority от CTA, marketing copy, eligibility и runtime matching;
6. фиксирует неоднозначности, которые запрещено решать механическим копированием;
7. предлагает минимальный следующий governance checkpoint, но не создаёт target data.

## Почему S14 audit-only

Механический перенос сейчас опасен:

- current rules используют `problem`, `kind`, `intent`, `modifiers`, а frozen target
  strategy match использует `family`, `extent`, `stage`, `jaw`, `reported_context`;
- current overlap выбирается runtime-specificity, а target resolver ещё не реализован;
- четыре current rules и fallback допускают четыре options, target product decision — 2–3;
- `primary_cta`, `answer_style`, `role`, `positioning`, `show_when` не принадлежат
  одному target strategy файлу;
- current pricebook `recommended` для offers должен жить в strategy, но не входит в
  `patient_playbook.yaml` и требует отдельной source projection;
- target `clinic_strategy.yaml` ещё отсутствует, а target marketing policy не
  материализована.

S14 не выбирает между first-match, specificity или rule overlay и не объявляет
lossy mapping эквивалентным current behavior.

## Затрагиваемые файлы

- `TASK.md`;
- `docs/PATIENT_PLAYBOOK_MIGRATION_AUDIT.md` — новый audit artifact;
- `docs/STRANGLER_ROADMAP.md` — pending `[ ]`, затем `[x]` только после completion
  checker `✅`.

Любой другой файл требует остановки и отдельного решения владельца/Архитектора.

## Protected / вне scope

- `clients/demo/patient_playbook.yaml` и весь `clients/**`;
- `contracts/**`, `core/**`, `orchestration/**`, routes/API/app/UI;
- весь `clients/demo/target_response/**`;
- tests/evals/golden/fixtures и существующие docs architecture contracts;
- создание `clinic_strategy.yaml` или target `marketing.yaml`;
- изменение S1 strategy/marketing models, S2 loader или S10 context;
- выбор runtime rule precedence/merge algorithm;
- перенос/удаление current playbook, adapters, dual-read или feature flags;
- A9 design/raw/frozen/harness/evidence и live re-audit;
- live/LLM, merge, `main`, другие ветки и изменение product authority.

## Exact source inventory

Audit обязан перечислить exact current `rules` IDs и не объединять их:

1. `one_tooth_restore`;
2. `extraction_then_implant_restore`;
3. `few_teeth_restore`;
4. `existing_implant_prosthetic_stage`;
5. `full_arch_restore`;
6. `upper_full_arch_with_bone_deficit`;
7. `upper_full_arch_restore`;
8. `bone_deficit_solution`.

Отдельно фиксируется единственный fallback key:

- `patient_situations.full_arch_missing`.

Audit показывает, что fallback дублирует основную full-arch конфигурацию по strategy,
options и priorities, но не объявляет его удаляемым до runtime retirement checkpoint.

## Field ownership matrix

Audit обязан разобрать каждое семейство полей:

| Current field | Target disposition |
|---|---|
| `rules[].id` | кандидат на stable target rule id |
| `match.extent`, `match.jaw` | прямые neutral target axes, после проверки semantics |
| `match.kind`, `match.problem` | current classifier concepts; не копировать как target field |
| `match.modifiers: bone_deficit` | кандидат `reported_context: reported_bone_deficit`, не автоматическая эквивалентность |
| `match.intent` | planner/dialog concern, не strategy eligibility |
| `max_options` | target strategy, но current `4` требует approved cap `3` и explicit acceptance |
| `primary_cta` | target marketing/CTA policy, не clinic strategy |
| `strategy` string | current runtime/telemetry label; нет автоматического target field |
| `answer_style.max_options` | duplicate current limit, не второй target source |
| `mention_consult_ct` | marketing/CTA/content policy, не ordering |
| `avoid_single_winner`, `avoid_medical_promise` | общие product guardrails, не per-rule priority data |
| `options[].service_id/priority` | кандидат target `service_priorities`, только после applicability filtering |
| `options[].show_when` | target service/option selection owner; сверить с S11 |
| `options[].role/positioning` | нет frozen target owner; запрещено молча терять или класть в strategy |

## Per-rule audit requirements

Для каждого из восьми rules документ содержит одну строку/секцию с:

- exact current match;
- exact ordered `service_id: priority`;
- current `max_options`, CTA и strategy label;
- какие eligibility facts уже представлены в S11 target service catalog;
- candidate target match без утверждения runtime equivalence;
- loss/risk/unresolved boundary.

Особо отметить:

- `one_stage.show_when=extraction_context` уже выражен через service selection stage;
- `zygomatic_implants.show_when=bone_deficit_or_upper_jaw` заменён более строгими
  target selection axes: full arch + upper jaw + reported bone deficit;
- `existing_implant_prosthetic_stage` соответствует product-law «не продавать установку
  повторно», но mapping `kind -> stage=implant_placed` должен проверяться отдельно;
- `few_teeth_restore`, `full_arch_restore`, `upper_full_arch_restore`,
  `upper_full_arch_with_bone_deficit` и fallback содержат четыре options, а target
  primary result ограничен тремя;
- `bone_deficit_solution` смешивает modifier и intent и не должен становиться
  отдельным medical classifier/route.

## Already migrated / not yet migrated

Audit явно разделяет:

### Уже материализовано offline

- canonical service IDs, family/roles, active and coarse selection (S11);
- offers, units, exact prices, brands/facts (S12);
- payment stages (S13);
- doctors and service links (S7/S9);
- pure exact-service common data context (S10).

### Ещё не материализовано

- demo target clinic strategy data;
- target marketing policy data;
- deterministic target strategy resolver and overlap law;
- dialog-focus/product wiring and any authority;
- explicit target ownership of current role/positioning signals;
- current offer `recommended` projection into target strategy.

## Required conclusions

Audit не должен давать ложный вывод «можно просто скопировать YAML». Он обязан
зафиксировать минимальный следующий шаг:

1. отдельный governance TASK для frozen target strategy resolution semantics
   (default vs context rule, specificity/order/overlay, missing priority, stable tie);
2. только после этого — materialization demo `clinic_strategy.yaml` из audited source;
3. marketing/CTA migration остаётся отдельной задачей;
4. current playbook остаётся единственным product consumer до отдельного wiring/authority
   checkpoint.

Если audit обнаружит, что frozen S1 contract уже однозначно задаёт resolution semantics,
он должен привести точное доказательство из code/docs; иначе ambiguity остаётся явной.

## Verification

До audit artifact:

1. independent checker читает TASK, current playbook, current consumer/contracts/tests,
   S1 strategy models, S11 target catalog, architecture docs, checklist и guardrails;
2. checker подтверждает exact inventory, audit-only scope и отсутствие скрытого решения
   strategy semantics;
3. при `❌`/`❓` TASK исправляется до completion work.

После audit artifact:

1. `.venv/codex312/Scripts/python.exe -m pytest tests/test_patient_playbook.py -q --basetemp=.pytest_tmp_s14_current`;
2. `.venv/codex312/Scripts/python.exe -m pytest tests/test_demo_target_service_catalog.py -q --basetemp=.pytest_tmp_s14_target`;
3. `git diff --check`, exact allowlist status и independent checker review;
4. no live/LLM и no full pytest.

Тесты read-only подтверждают, что current behavior и S11 data не менялись; они не
доказывают target parity и не разрешают wiring.

## Definition of Done

- владелец получает честный ответ, где находятся current priorities и почему это ещё
  не target strategy file;
- все восемь rules и fallback полностью учтены без выдуманных mappings;
- уже перенесённые selection facts отделены от strategy/marketing/runtime debt;
- спорные потери и rule-resolution gap явно зафиксированы;
- client data, code, tests, answers, UI, A9 и authority не изменены;
- roadmap S14 audit status независимо проверен;
- checker `✅`, governance/completion commits и push только в `codex/stage-a`, дерево
  чистое.
