# TASK — S15 Deterministic Target Strategy Resolution

**Ветка:** `codex/stage-a`

**Baseline:** `3bec780 docs: audit patient playbook migration S14`

**Серия / checkpoint:** `S15` — минимальный pure offline resolver для target clinic
strategy и недостающий contract baseline priorities.

**Режим:** synthetic models/logic/tests only. Никаких demo strategy data, product
consumers, ответов, routes/UI, live/LLM или product authority.

## Owner direction

21 июля 2026 владелец подтвердил желаемую client-configurable модель: если клиника хочет
свой приоритет для услуги/ситуации, он задаётся в её конфиге без изменения общего кода.
После простого объяснения small-rule approach владелец попросил продолжать.

S15 формализует этот механизм offline. Он не переносит current playbook и не делает
target strategy активной.

## Основание S14

S14 доказал:

- current `patient_playbook.yaml` активен и содержит 8 rules + fallback;
- current runtime-specificity уже расходится с одним intended extraction test;
- frozen S1 strategy models хранят priorities/rules, но не задают resolution semantics;
- architecture требует baseline priorities + редкие context overrides;
- current offer `recommended` должен позже стать strategy data;
- механическая materialization до resolver law небезопасна.

## Цель

Реализовать один pure resolver, который получает:

- уже validated `TargetClinicStrategy`;
- neutral target context (`family`, `extent`, `stage`, `jaw`, `reported_context`);
- уже отфильтрованные candidate service IDs и/или offer IDs;
- optional exact explicitly named service/offer ID.

Resolver возвращает:

- ID первого matching context rule или `None`;
- effective `max_options`;
- deterministic ordered/capped service IDs;
- deterministic ordered/capped offer IDs.

Он не читает files/client/session, не проверяет medical eligibility, не выбирает facts,
не формирует ответ и не подключается к runtime.

## Почему baseline priorities нужны в contract

Текущий `TargetClinicStrategy` хранит priorities только внутри rules. Это не выражает
зафиксированное architecture-разделение:

- постоянный базовый порядок клиники;
- редкие context overrides.

S15 добавляет в `TargetClinicStrategy`:

```python
default_service_priorities: dict[NonBlankStr, Priority] = Field(default_factory=dict)
default_offer_priorities: dict[NonBlankStr, Priority] = Field(default_factory=dict)
```

Имена explicit: это baseline, а не отдельное catch-all rule. Missing fields валидируются
как empty maps для backward-compatible synthetic payloads. Dict values остаются
`StrictInt`: bool/float/string запрещены; отрицательные, ноль и положительные значения
допустимы как относительный порядок.

`ResponseSchemaBundle` проверяет refs обоих default maps теми же stable tokens:

- unknown default service → `bundle_strategy_service_missing`;
- unknown default offer → `bundle_strategy_offer_missing`.

## Context rule contract

После появления explicit default maps rule с полностью пустым `match` не нужен и
опасен: он может случайно перехватить все contexts.

`TargetStrategyRule` обязан иметь хотя бы одно non-`None` match field. Полностью empty
match отклоняется stable token:

- `strategy_rule_match_empty`.

Existing unique rule IDs, max 2–3 and local ref validators сохраняются.

## Exact rule matching law

Для каждого rule authored order:

1. каждое non-`None` field rule match должно exact совпасть с context;
2. unspecified rule field является wildcard;
3. required rule field при `None` в context не совпадает;
4. выбирается **первое** полностью совпавшее rule;
5. последующие совпавшие rules игнорируются;
6. specificity score не рассчитывается;
7. несколько rules не merge/overlay между собой.

Клиника размещает узкие исключения выше общих. Это один небольшой ordered list, а не
правило под каждую пользовательскую фразу: language understanding сначала даёт neutral
facts, затем strategy работает только с ними.

## Baseline + selected override

Effective priorities строятся отдельно для services/offers:

1. copy соответствующего default map;
2. если найден context rule, его map обновляет значения только перечисленных IDs;
3. IDs, отсутствующие в effective map, имеют priority `0`;
4. rule value может поднять, оставить или понизить default priority;
5. input strategy/models не мутируются.

Только одно selected rule overlay применяется поверх baseline. Другие matching rules не
участвуют.

Effective max:

- selected rule `max_options`, если задан;
- иначе `strategy.default_max_options`.

## Ranking law

Для каждого входного candidate collection:

1. resolver не добавляет IDs из priority maps;
2. higher numeric priority идёт раньше;
3. equal priority сохраняет exact input order (stable tie);
4. optional explicitly named candidate pin-ится первым независимо от priority;
5. остальные candidates сохраняют priority order;
6. после ordering result обрезается effective max `2..3`;
7. empty/single candidate lists допустимы и не дополняются искусственно.

Explicit ID обязан уже присутствовать в соответствующих candidates. Иначе resolver
отклоняет input, а не возвращает недоступную сущность:

- `strategy_explicit_service_not_candidate`;
- `strategy_explicit_offer_not_candidate`.

Duplicate candidate IDs запрещены:

- `strategy_candidate_service_duplicate`;
- `strategy_candidate_offer_duplicate`.

Candidate IDs должны быть non-blank strings:

- `strategy_candidate_service_invalid`;
- `strategy_candidate_offer_invalid`.

Эти errors относятся только к offline resolver boundary. Они не являются patient-facing
fallback и не создают route.

## Public API

Новый `core/response_strategy.py` содержит только:

```python
@dataclass(frozen=True, slots=True)
class TargetStrategyResolution:
    matched_rule_id: str | None
    max_options: int
    service_ids: tuple[str, ...]
    offer_ids: tuple[str, ...]

class TargetStrategyResolutionError(ValueError):
    code: str

def resolve_target_strategy(
    strategy: TargetClinicStrategy,
    context: TargetStrategyMatch,
    *,
    service_ids: Sequence[str] = (),
    offer_ids: Sequence[str] = (),
    explicit_service_id: str | None = None,
    explicit_offer_id: str | None = None,
) -> TargetStrategyResolution:
    ...
```

Exact parameter types may use `collections.abc.Sequence`; semantic API and frozen result
fields above are required.

Resolver may order both lists in one call. Caller is responsible for passing only the
offers relevant to its already selected context/service. S15 does not join offers to
services and does not reinterpret S10.

## Затрагиваемые файлы

- `TASK.md`;
- `contracts/response_schema.py`;
- `core/response_strategy.py` — new pure offline module;
- `tests/test_response_schema_contract.py`;
- `tests/test_target_strategy_resolution.py` — new synthetic tests;
- `docs/PRICE_SERVICE_ARCHITECTURE.md`;
- `docs/PATIENT_PLAYBOOK_MIGRATION_AUDIT.md` — отметить resolution law после completion;
- `docs/STRANGLER_ROADMAP.md` — pending `[ ]`, затем `[x]` только после completion
  checker `✅`.

Любой другой файл требует остановки и отдельного решения владельца/Архитектора.

## Protected / вне scope

- весь `clients/**`, включая current playbook/pricebook и `target_response/**`;
- current `contracts/patient_playbook.py`, `core/patient_playbook.py` и их tests;
- S2 loader behavior, S10 context builder и doctor/KB loaders;
- materialization `clinic_strategy.yaml`/target marketing;
- eligibility filtering, service/offer availability, medical applicability;
- natural-language understanding, planner, TurnFrame, dialog focus/session;
- response composition, price/doctor rendering, CTA, UI/buttons/routes/app;
- adapters, dual-read, fallback, feature flags и product wiring;
- protected golden/eval fixtures;
- два pre-existing S14 current test mismatches не исправляются и не скрываются;
- A9 design/raw/frozen/harness/evidence и live re-audit;
- live/LLM, merge, `main`, другие ветки и изменение product authority.

## Contract tests

`tests/test_response_schema_contract.py` минимально доказывает:

1. missing default maps дают empty maps;
2. valid strict integer default priorities сохраняются;
3. bool/float/string default priority запрещены;
4. unknown default service/offer refs получают existing bundle tokens;
5. empty rule match получает exact `strategy_rule_match_empty`;
6. existing rule IDs/max/ref validation не ослаблены;
7. imports boundary остаётся прежней.

## Resolver tests

`tests/test_target_strategy_resolution.py` synthetic-only доказывает:

1. first matching rule wins; later matching rule не merge-ится;
2. non-matching required field и missing context field не выбирают rule;
3. defaults всегда действуют, selected rule overrides только свои IDs;
4. missing priority = `0`, negative/zero/positive sort correctly;
5. equal priorities preserve exact input order;
6. selected rule max overrides default, otherwise default applies;
7. service and offer lists both sort/cap independently;
8. explicit service/offer pin first;
9. explicit non-candidate exact errors;
10. duplicates and invalid candidate IDs exact errors;
11. priority maps cannot add non-candidate IDs;
12. empty/single lists valid;
13. input models/maps/sequences are not mutated;
14. resolver imports no current runtime/client/session/A9 modules.

No test may encode demo service IDs as resolver logic; demo-like IDs are allowed only as
opaque synthetic strings.

## Architecture doc update

`docs/PRICE_SERVICE_ARCHITECTURE.md` фиксирует простым языком:

- defaults + ordered first-match context overrides;
- specific rules above general rules;
- exact matching only on neutral target axes;
- no rule per phrase/service required;
- missing priority 0 and stable ties;
- explicit named candidate precedence;
- resolver only ranks prefiltered candidates and cannot make service eligible;
- no current/runtime authority.

S14 audit получает короткий status addendum: gap resolution semantics закрыт S15, но
demo strategy materialization, current mismatch fixes and wiring всё ещё не выполнены.

## Verification

До code/docs edits:

1. independent checker читает TASK, S14 audit/current findings, S1 models/tests, S2/S10,
   architecture docs, checklist и guardrails;
2. checker подтверждает baseline fields, first-match law, no rule explosion, stable
   ranking/direct precedence и offline boundary;
3. при `❌`/`❓` TASK исправляется до кода.

После реализации:

1. `.venv/codex312/Scripts/python.exe -m pytest tests/test_target_strategy_resolution.py tests/test_response_schema_contract.py -q --basetemp=.pytest_tmp_s15_unit`;
2. `.venv/codex312/Scripts/python.exe -m pytest tests/test_response_schema_loader.py tests/test_service_data_context.py -q --basetemp=.pytest_tmp_s15_neighbors`;
3. `.venv/codex312/Scripts/python.exe -m pytest tests/test_demo_target_service_catalog.py tests/test_demo_target_price_offers.py -q --basetemp=.pytest_tmp_s15_data`;
4. `git diff --check`, exact allowlist and independent checker repeat;
5. no live/LLM and no full pytest.

Known S14 current playbook result (`15 passed, 2 failed`) is documented and outside this
allowlist. S15 не запускает его как green gate и не заявляет, что он исправлен.

## Definition of Done

- target strategy имеет explicit baseline priorities и safe non-empty context rules;
- deterministic first-match + baseline override semantics frozen tests/docs;
- stable ranking/cap/direct candidate precedence verified on synthetic data;
- resolver cannot add or make candidates eligible;
- no demo rules/data/current playbook/runtime consumers изменены;
- S14 current mismatches remain visible and untouched;
- roadmap S15 status independently reviewed;
- checker `✅`, governance/completion commits and push only to `codex/stage-a`, tree clean.
