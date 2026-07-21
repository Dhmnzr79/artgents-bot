# TASK — S23 One-Service Active Offer Projection

**Ветка:** `codex/stage-a`

**Baseline:** `0448f2a feat: assemble response evidence package S22`

**Серия / checkpoint:** `S23` — pure offline-проекция реально доступных ценовых offers
внутри одной уже выбранной услуги: active/service-option filtering + S15 clinic priority.

**Режим:** governance + один новый unwired selector + synthetic/real-data unit tests +
price architecture status. Никаких client-data changes, выбора услуги, patient-scope
authority, session/runtime, ответов, routes/UI или live/LLM.

## Owner direction

После завершённого S22 владелец разрешил идти дальше. Ближайший минимальный пробел:
S22 намеренно хранит все authored offers выбранной услуги, включая их флаги, но будущая
ценовая проекция не должна показывать неактивную позицию или цену другого semantic
option. S23 добавляет только этот deterministic offline boundary и использует уже
проверенный S15 resolver для порядка клиники.

Demo не имеет live-клиентов. S23 не создаёт compatibility path для current/legacy
архитектуры и ничего не подключает к локальным ответам.

## Минимальная граница S23

Создать `core/target_offer_projection.py` с pure function, принимающей:

- `ServiceDataContext` S10 — exact уже выбранная service, все её authored offers и
  связанные doctors; doctors S23 не читает;
- `TargetClinicStrategy` S1/S15;
- explicit already-validated `TargetStrategyMatch` context;
- optional exact `selected_option_id`, уже определённый upstream;
- optional exact `explicit_offer_id`, прямо выбранный upstream.

Exact public API:

```python
@dataclass(frozen=True, slots=True)
class TargetOfferProjection:
    service_id: str
    selected_option_id: str | None
    matched_rule_id: str | None
    max_options: int
    offers: tuple[TargetOffer, ...]


def project_target_service_offers(
    service_context: ServiceDataContext,
    strategy: TargetClinicStrategy,
    strategy_context: TargetStrategyMatch,
    *,
    selected_option_id: str | None = None,
    explicit_offer_id: str | None = None,
) -> TargetOfferProjection:
    ...
```

Result имеет frozen/slots shell и tuple offers. Каждый returned `TargetOffer` — deep
copy, поэтому изменение projection не меняет S10 context или исходный bundle.

S23 не получает текст пациента, TurnFrame или A9 patient scope. Все context/option/offer
values уже выбраны upstream и передаются явно; checkpoint не даёт им product authority.

## Exact algorithm

### 1. S23-only input validation

Validation идёт в порядке signature:

1. `selected_option_id` — `None` либо exact nonblank `str`;
2. непустой option ID обязан exact существовать в `service_context.service.options`;
3. `explicit_offer_id` — `None` либо exact nonblank `str`.

IDs не strip/case-fold/normalize.

`TargetOfferProjectionError(ValueError)` хранит public `code` и `value`; message:
`f"{code}: {value!r}"`.

| Условие | `code` | `value` |
|---|---|---|
| option не `None`/`str` или blank | `offer_projection_option_id_invalid` | исходное значение |
| exact option отсутствует у выбранной service | `offer_projection_option_not_found` | exact option string |
| explicit offer не `None`/`str` или blank | `offer_projection_explicit_offer_id_invalid` | исходное значение |

Typed S10 context, strategy и strategy context остаются owner-contract inputs и не
дублируются S23 error table.

### 2. Active/service-option candidate filtering

Candidates строятся только из `service_context.offers` и сохраняют authored order до
S15 ranking.

1. Если parent `service.active is False`, candidate list пуст.
2. Offer допускается только при `offer.active is True`.
3. Offer без `option_id` допускается, если option filter не задан.
4. Offer с `option_id` допускается только если referenced option существует и effective
   active. `option.active is None` наследует active parent; `False` запрещает offer.
5. При `selected_option_id != None` остаются только offers с exact тем же `option_id`;
   generic offer с `option_id=None` не выдаётся как цена выбранного option.
6. При `selected_option_id is None` допускаются generic offers и offers всех effective
   active options.
7. Price mode, amount/min/max, currency, billing unit, package, payment stages, fact refs,
   followups и brand ID никогда не меняются и не пересчитываются.

S10/ResponseSchemaBundle уже гарантируют, что authored offer принадлежит service и его
option ref валиден. S23 не создаёт repair/fallback для forged context.

### 3. Clinic strategy order

После filtering вызвать существующий S15:

```python
resolve_target_strategy(
    strategy,
    strategy_context,
    offer_ids=eligible_offer_ids,
    explicit_offer_id=explicit_offer_id,
)
```

- first-match rule, default/override priorities, stable ties и `max_options` полностью
  принадлежат S15 и не дублируются;
- priority map не может добавить отсутствующий/inactive/other-option offer;
- exact explicit offer pin-ится первым только если он уже eligible;
- valid explicit ID вне eligible candidates получает существующий
  `TargetStrategyResolutionError("strategy_explicit_offer_not_candidate", id)` без
  переупаковки;
- result materializes deep-copied offers exact в `resolution.offer_ids` order;
- `matched_rule_id` и `max_options` копируются из S15 resolution.

Empty candidate result — нормальный deterministic output, а не повод подставлять похожую
цену, другой option/service или вычисленную сумму.

## Что S23 сознательно не делает

- не выбирает service/family и не применяет `TargetServiceSelection` к patient facts;
- не определяет option/offer/brand из natural language;
- не использует A9 patient scope, не меняет его shadow-only/authority статус;
- не проверяет медицинскую применимость и не рекомендует лечение;
- не фильтрует по цене/billing unit и не умножает/складывает деньги;
- не выбирает doctor, marketing, consultation close или CTA;
- не создаёт content/price cards, ResponseSpec, prompt или natural-language reply;
- не читает files/Markdown/client/session/clock и не меняет shown state;
- не подключается к composer/routes/API/app/UI/config;
- не меняет S1/S10/S15/S22, target/current client data или product authority;
- не меняет/не перезапускает A9 artifacts и не запускает live/LLM.

Brand-specific filtering и общий service shortlist остаются отдельными future
checkpoints. S23 принимает только explicit offer ID как уже разрешённый точный выбор.

## Затрагиваемые файлы

- `TASK.md`;
- `core/target_offer_projection.py` — new pure offline selector;
- `tests/test_target_offer_projection.py` — new synthetic unit contract;
- `tests/test_demo_target_offer_projection.py` — new read-only real-data acceptance;
- `docs/PRICE_SERVICE_ARCHITECTURE.md` — S23 projection/status boundary;
- `docs/STRANGLER_ROADMAP.md` — pending `[ ]`, затем `[x]` только после completion
  checker `✅`.

Любой другой файл требует остановки и отдельного решения владельца/Архитектора.

## Protected / вне scope

- весь `clients/**`, включая current/target service/price/strategy/marketing/MD/doctors;
- весь `contracts/**`, включая frozen S1/S5/S18/S20 models/validators;
- existing `core/service_data_context.py`, `response_strategy.py`,
  `target_response_evidence.py`, loaders и current runtime paths;
- изменение S10 all-authored law, S15 ordering/limits или S22 evidence/slot math;
- service/option recognition, general shortlist и brand resolver;
- patient scope, dialog focus, session persistence/TTL/shown-state mutation;
- ResponseSpec/composer/prompt/FullContext/routes/API/app/UI/config;
- protected golden/eval fixtures;
- A9 design/raw/frozen/harness/evidence и live re-audit;
- live/LLM, merge, `main`, другие ветки и product authority.

## Acceptance tests

### Synthetic projection contract

`tests/test_target_offer_projection.py` обязан доказать:

1. exact API/result fields, frozen+slots shell, tuple/deep copies;
2. active service возвращает только active authored offers, inactive service — empty;
3. inactive offer всегда исключён;
4. option `active=None` наследует parent, `False` исключает его offers;
5. no option filter сохраняет generic + all active-option candidates;
6. exact option filter оставляет только его offers и не подставляет generic/other option;
7. invalid/unknown option и invalid explicit offer дают stable exact errors;
8. explicit eligible offer pin-ится первым; inactive/other-option explicit offer получает
   existing S15 not-candidate error;
9. first matching rule, priority override, cap и stable ties совпадают с S15;
10. strategy priority IDs не добавляют non-candidates;
11. fixed/from/range/no-public-price records, units, packages, payment stages и followups
    возвращаются без изменения;
12. empty result не создаёт fallback;
13. repeated calls stateless, context/strategy/lists/models не мутируются;
14. imports только stdlib + target contracts + pure S10/S15; нет IO/client/session/runtime.

### Real demo acceptance

`tests/test_demo_target_offer_projection.py` обязан read-only доказать:

1. real S2/S5/S10/S15 inputs строятся через frozen boundaries;
2. All-on-4 default projection использует demo offer priority: Impro первым, затем
   Implantium/Nobel в stable authored order, exact amounts/`jaw` preserved;
3. explicit Nobel offer pin-ится первым без изменения суммы/package/stages;
4. removable dentures exact `partial` option возвращает только partial offer, `full` —
   только full;
5. sinus-lift exact `open`/`closed` options не смешиваются;
6. structured All-on-4 payment stages остаются exact и не пересчитываются;
7. source/current/target files не меняются;
8. no product imports/writes/skip/xfail/live/LLM.

## Verification

До implementation:

1. этот TASK + roadmap pending коммитятся отдельно и push только в `codex/stage-a`;
2. independent read-only checker читает TASK, S10/S12/S13/S15/S16/S22 code/data/tests,
   price architecture, checklist/guardrails;
3. checker подтверждает active/option inheritance, S15 delegation, no-price-math,
   no-service-selection и no-runtime/no-authority boundary;
4. при `❌`/`❓` governance исправляется и проверяется повторно до code.

После implementation:

1. `.venv/codex312/Scripts/python.exe -m pytest tests/test_target_offer_projection.py tests/test_demo_target_offer_projection.py -q --basetemp=<temp>/s23-target`;
2. `.venv/codex312/Scripts/python.exe -m pytest tests/test_service_data_context.py tests/test_target_strategy_resolution.py tests/test_target_response_evidence.py tests/test_demo_target_response_evidence.py -q --basetemp=<temp>/s23-neighbors`;
3. `git diff --check`, exact allowlist, no skip/xfail, no full pytest;
4. independent completion checker повторяет review/tests;
5. roadmap `[x]`, completion commit/push only `codex/stage-a`, tree clean/synced.

## Definition of Done

- pure S23 projection возвращает только active offers выбранной service/option;
- S15 priorities/cap/explicit pin применены без добавления кандидатов;
- exact money/unit/package/payment stages сохранены без вычислений;
- no service/brand/doctor/marketing selection, IO, session/runtime/product wiring;
- current/target client data, frozen contracts, A9 и authority не меняются;
- independent governance и completion reviews `✅`;
- commits/push only `codex/stage-a`, working tree clean и HEAD synced with origin.
