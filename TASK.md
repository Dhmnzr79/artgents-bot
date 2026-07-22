# TASK — S26 Deterministic Active Service Term Resolution

**Ветка:** `codex/stage-a`

**Baseline:** `c7baf96 feat: resolve target brand terms S25`

**Серия / checkpoint:** `S26` — последний минимальный dictionary lookup перед первой
end-to-end сборкой: один уже выделенный service term → exact active target `service_id`.

**Режим:** governance + один new pure unwired resolver + synthetic/real-data unit tests +
price/service architecture status. Никаких client-data changes, patient-scope selection,
лечебных рекомендаций, runtime/ответов/routes/UI/authority или live/LLM.

## Owner direction

После S25 владелец разрешил двигаться дальше и отдельно потребовал не наращивать
архитектурные слои бесконечно. S26 закрывает только необходимый identity lookup услуги,
чтобы уже готовые S10/S22/S23–S25 могли получить exact service ID без legacy catalog
matcher. После S26 следующий рекомендуемый checkpoint — первая вертикальная offline
end-to-end сборка существующих компонентов, а не новый справочник «на всякий случай».

## Минимальная граница S26

Создать `core/target_service_resolver.py`:

```python
@dataclass(frozen=True, slots=True)
class TargetServiceResolution:
    service_id: str
    service: TargetService


def resolve_target_service_term(
    services: dict[str, TargetService],
    service_term: str,
) -> TargetServiceResolution | None:
    ...
```

`services` — already validated `ResponseSchemaBundle.services`. `service_term` — одна
уже выделенная upstream строка. Resolver не получает TurnFrame, patient facts, полное
сообщение как отдельную семантическую сущность или service family.

Result содержит exact dictionary key и deep-copied service record. Unknown или exact
term только неактивной услуги возвращает `None` без похожей/активной подстановки.

## Exact laws

### 1. Input validation

- `services` обязан быть exact `dict`; иначе
  `TargetServiceResolutionError("service_resolution_catalog_invalid", services)`;
- каждый key обязан быть nonblank `str`, каждое value — `TargetService`; forged input
  даёт `service_resolution_catalog_invalid` с offending key/value;
- `service_term` обязан быть nonblank `str`; иначе
  `TargetServiceResolutionError("service_resolution_term_invalid", original)`.

Error наследует `ValueError`, хранит `code`, `value`,
`candidate_service_ids: tuple[str, ...] = ()`; message exact
`f"{code}: {value!r}"`.

Typed catalog records не revalidate/repair и не мутируются.

### 2. Normalization and lookup

Единственная normalization input и authored labels:

```python
value.strip().casefold()
```

Для каждой `service.active is True` lookup values в authored order:

1. dictionary `service_id`;
2. `service.name`;
3. `service.aliases`.

Не выполняются punctuation removal, word splitting, substring/regex search, stemming,
fuzzy/typo correction, transliteration, keyboard repair или LLM inference.

Некоторые demo aliases намеренно имеют форму полного вопроса (`сколько стоит ...`). Они
могут match только при exact совпадении всей переданной строки после
`strip().casefold()`; произвольное сообщение не сканируется на содержащийся alias.

### 3. Active/no-match/collision

- inactive service labels не кандидаты;
- ноль active candidates → `None`, без fallback на inactive, похожую, generic или другую
  service;
- несколько совпавших labels одного active service deduplicate;
- два и более distinct active services → fail-closed error:
  `code="service_resolution_ambiguous"`, original term в `value`, distinct IDs в
  `candidate_service_ids` в catalog insertion order;
- первый service, ID precedence или client strategy не разрешают collision.

### 4. Result and composition

- один active candidate → frozen/slots resolution;
- `service_id` — exact authored key;
- `service` — deep copy exact record вместе с aliases, selection, options/content refs;
- repeated calls stateless, inputs/nested lists не мутируются.

Caller может явно передать `resolution.service_id` в S10
`build_service_data_context`, затем использовать S22/S23/S24. S26 сам ничего из них не
импортирует/не вызывает и не выбирает brand/option/offer/doctor/marketing.

## Что S26 сознательно не делает

- не анализирует симптомы и не превращает их в диагноз/service;
- не применяет `TargetServiceSelection` к extent/stage/jaw/reported_context;
- не строит general shortlist и не ранжирует S15 strategy;
- не разрешает service option и не выбирает метод лечения;
- не исправляет опечатки; language layer сможет предложить canonical term позже, а
  resolver только подтвердит catalog identity;
- не читает files/client/session/clock и не пишет state;
- не подключается к planner/legacy matcher/composer/routes/API/app/UI;
- не меняет contracts, target/current client data или product authority;
- не меняет/не перезапускает A9 artifacts и не запускает live/LLM.

## Затрагиваемые файлы

- `TASK.md`;
- `core/target_service_resolver.py` — new pure offline resolver;
- `tests/test_target_service_resolver.py` — new synthetic contract;
- `tests/test_demo_target_service_resolver.py` — new real-data/composition acceptance;
- `docs/PRICE_SERVICE_ARCHITECTURE.md` — S26 boundary;
- `docs/STRANGLER_ROADMAP.md` — pending `[ ]`, затем `[x]` только после completion checker `✅`.

Любой другой файл требует остановки и отдельного решения владельца/Архитектора.

## Protected / вне scope

- весь `clients/**`, включая target/current service catalogs/aliases/MD;
- весь `contracts/**` и frozen S1 schema;
- existing S10/S15/S21–S25 core modules/loaders;
- legacy/current `query_selector.py`, `core/catalog_match.py`,
  `core/service_selector_llm.py`, planner/service matching и tests;
- patient scope, selection-mode logic, options, family shortlist, dialog/session;
- ResponseSpec/composer/Verifier/FullContext/routes/API/app/UI/config;
- protected golden/eval fixtures;
- A9 design/raw/frozen/harness/evidence/live re-audit;
- live/LLM, merge, `main`, другие ветки и product authority.

## Acceptance tests

### Synthetic

`tests/test_target_service_resolver.py` обязан доказать:

1. exact API/result fields, frozen/slots shell, detached `TargetService` nested data;
2. invalid catalog/keys/values/term дают stable exact errors;
3. active ID, canonical name и каждый alias resolve exact ID;
4. только outer whitespace + Unicode casefold нормализуются;
5. phrase substring, punctuation, typo, morphology, transliteration и unknown → `None`;
6. inactive exact ID/name/alias → `None`, без active fallback;
7. same-service ID/name/alias collision deduplicates;
8. cross-active-service collision fail-closed с stable catalog-order candidates;
9. inactive colliding record не создаёт active ambiguity;
10. selection/options/content refs возвращаются exact без применения;
11. repeated calls stateless, inputs не мутируются;
12. imports только stdlib + target service contract; нет IO/client/S10/runtime.

### Real demo

`tests/test_demo_target_service_resolver.py` обязан read-only доказать:

1. real S2 bundle/services грузятся через frozen boundary;
2. все authored ID/name/aliases всех 21 active demo services разрешаются в свой exact ID;
3. каталог содержит 199 lookup labels и ноль normalized cross-service collisions;
4. case/outer whitespace работают для representative Cyrillic/Latin labels;
5. unknown/typo/morphology/arbitrary containing phrase не match;
6. exact authored full-question alias match допустим только целиком;
7. explicit chain `All-on-4` → S26 service ID → S10 context → `нобель` через S25 →
   S24 projection возвращает только `all_on_4.jaw.nobel`, exact 428000 RUB/jaw и stages;
8. client files unchanged; no product imports/writes/skip/xfail/live/LLM.

### Минимальные neighbors

- `tests/test_target_brand_resolver.py`;
- `tests/test_demo_target_brand_resolver.py`;
- `tests/test_service_data_context.py`;
- `tests/test_target_brand_offer_projection.py`;
- `tests/test_demo_target_brand_offer_projection.py`;
- `tests/test_response_schema_contract.py`;
- `tests/test_response_schema_loader.py`;
- `tests/test_demo_target_service_catalog.py`.

Не запускать full suite, legacy service matcher tests, live/LLM или A9.

## Checker gates

До кода read-only checker должен подтвердить minimal exact-term scope, active/collision
laws, отсутствие patient-scope/diagnosis/fuzzy semantics, прямую совместимость с S10 и
что после S26 roadmap переводит фокус на vertical end-to-end assembly.

После реализации checker повторяет target/neighbors и проверяет allowlist, честность
tests, no mutation/wiring/authority/live.

## Git protocol

1. TASK + pending roadmap; checker `✅` до code/data.
2. Commit `docs: govern target service resolution S26`; push only `codex/stage-a`.
3. Implement allowlist; target + listed neighbor tests.
4. Completion checker `✅`; roadmap `[x]` с next focus end-to-end assembly.
5. Commit `feat: resolve target service terms S26`; push only `codex/stage-a`.
6. Финал: clean tree, HEAD == origin.

## Definition of Done

- оба checker gate `✅`;
- exact active service term resolver реализован и проверен;
- target/neighbor tests green, no skip/xfail;
- no client/contracts/runtime/authority/A9/live changes;
- два commits pushed only `codex/stage-a`, tree clean/synced;
- следующий roadmap focus — первая end-to-end offline assembly, не новый lookup layer.
