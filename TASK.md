# TASK — S27 First Vertical Offline Response Materials Assembly

**Ветка:** `codex/stage-a`

**Baseline:** `8bd8fe8 feat: resolve target service terms S26`

**Серия / checkpoint:** `S27` — первая vertical offline end-to-end сборка уже готовых
target-компонентов: service/optional brand terms → exact identity → S22 evidence →
S23/S24 eligible offers → один безопасный пакет материалов перед ResponseSpec/Composer.

**Режим:** governance + один new pure unwired facade + synthetic/real-data unit tests +
architecture status. Никаких новых data/selector semantics, client changes,
patient-scope authority, ResponseSpec, Composer/runtime/routes/UI или live/LLM.

## Owner direction

После S26 владелец подтвердил движение дальше и потребовал не скатываться в
переусложнение. Поэтому S27 не добавляет очередной resolver. Он соединяет существующие
S10/S21/S22/S23/S24/S25/S26 в первый вертикальный deterministic path и скрывает от
следующего слоя все authored offers, которые ещё не прошли eligibility/brand projection.

Вертикаль S27 начинается не с raw patient message, а с уже выделенных exact terms и
явных context snapshots. Заканчивается готовыми factual materials до естественного
текста. Это offline integration boundary, а не product wiring.

## Exact public API

Создать `core/target_offline_response_assembly.py`:

```python
@dataclass(frozen=True, slots=True)
class TargetOfflineResponseMaterials:
    service_id: str
    service: TargetService
    selected_brand_id: str | None
    brand: TargetBrand | None
    matched_rule_id: str | None
    max_options: int
    offers: tuple[TargetOffer, ...]
    doctors: tuple[ServiceDoctorContext, ...]
    selected_content_ref: str | None
    marketing_selection: TargetMarketingSelection
    commercial_facts: tuple[TargetCommercialFact, ...]
    external_source_refs: tuple[str, ...]
    consultation_close: ServiceConsultationValue | None
    marketing_slots_used: int
    amplifier_slots_used: int


def assemble_target_offline_response_materials(
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    external_index: ResponseSchemaExternalIndex,
    consultation_values: Sequence[ServiceConsultationValue],
    *,
    service_term: str,
    brand_term: str | None,
    strategy_context: TargetStrategyMatch,
    semantic_context: str,
    today: date,
    include_initial_block: bool,
    include_consultation_close: bool,
    marketing_scenarios: Sequence[str] = (),
    shown_fact_ids: Sequence[str] = (),
    shown_amplifier_refs: Sequence[str] = (),
    shown_consultation_value_refs: Sequence[str] = (),
) -> TargetOfflineResponseMaterials:
    ...
```

Typed bundle/catalog/index/strategy context remain validated owner inputs. S27 validates
only its own no-match boundary; downstream validators retain all existing errors.

## Exact algorithm and ownership

Order is fixed:

1. Call S26 `resolve_target_service_term(bundle.services, service_term)`.
   - invalid/ambiguous errors propagate unchanged;
   - `None` → `TargetOfflineResponseAssemblyError(
     "offline_assembly_service_not_found", service_term)`.
2. If `brand_term is None`, no brand resolution/filter.
3. Otherwise call S25 `resolve_target_brand_term(bundle.brands, brand_term)`.
   - invalid/ambiguous errors propagate unchanged;
   - `None` → `TargetOfflineResponseAssemblyError(
     "offline_assembly_brand_not_found", brand_term)`.
4. Call S22 `build_target_response_evidence_package` with resolved service ID and
   `selected_content_ref=service_resolution.service.content_ref`; pass all marketing,
   date, shown-state and consultation inputs exact unchanged.
5. Without brand call S23 `project_target_service_offers` on S22 service context with
   `selected_option_id=None`, `explicit_offer_id=None`.
6. With brand call S24 `project_target_service_brand_offers` with resolved brand ID and
   the same explicit `strategy_context`; option/explicit offer remain `None`.
7. Materialize one flat detached result only from S22 evidence plus S23/S24 projection.

`TargetOfflineResponseAssemblyError(ValueError)` stores `code`, `value`; exact message
`f"{code}: {value!r}"`. It introduces only the two not-found codes above and never wraps
S21–S26 errors.

## Final-material safety law

- output `offers` contains only S23/S24 projected offers in clinic-strategy order/cap;
- S22 all-authored `service_context.offers` is internal and is not exposed in result;
- inactive/other-service/other-brand offers cannot be recovered from output;
- no brand means eligible offers across brands/unbranded according to S23, not a guessed
  brand;
- known brand with no offer for service returns empty offers, no generic/other-brand
  fallback;
- service, brand, offers, commercial facts and consultation are detached/deep-copied;
- doctors are frozen S10 value records in authored catalog order; S27 does not rank a
  “best doctor”;
- marketing selection/limits/CTA remain exact S21/S22 output;
- price mode/amount/currency/unit/package/payment stages/fact refs/followups never change
  or recalculate;
- selected content ref is exact service-owned `content_ref`; S27 does not read MD body.

## Deliberate first-vertical limits

S27 intentionally does not accept/select `selected_option_id` or `explicit_offer_id`.
Those lower-level capabilities remain in S23/S24 but are not needed to prove the first
named-service vertical slice. This prevents widening the facade before integration
evidence exists.

S27 also does not:

- parse raw patient text or repair typos;
- apply patient scope/selection modes, diagnose or recommend treatment;
- build a general service shortlist;
- select/rank one doctor;
- invent marketing copy or consultation text;
- create ResponseSpec, prompt, natural-language answer, cards/buttons/UI;
- read client files/session/clock or write shown state;
- connect to planner/legacy matcher/Composer/routes/API/app/config;
- change S1–S26 contracts/code/data or product authority;
- touch/re-run A9 artifacts or live/LLM.

## Затрагиваемые файлы

- `TASK.md`;
- `core/target_offline_response_assembly.py` — new pure facade;
- `tests/test_target_offline_response_assembly.py` — new synthetic vertical contract;
- `tests/test_demo_target_offline_response_assembly.py` — new real demo vertical acceptance;
- `docs/PRICE_SERVICE_ARCHITECTURE.md` — S27 boundary;
- `docs/STRANGLER_ROADMAP.md` — pending `[ ]`, then `[x]` only after completion checker `✅`.

Любой другой файл — стоп и отдельное owner/architect decision.

## Protected / вне scope

- весь `clients/**`, contracts и existing core modules S1–S26;
- current/legacy planner, service matcher, price/marketing/composer/runtime paths;
- option/explicit-offer facade expansion, service shortlist, doctor ranking;
- ResponseSpec/materializer/Verifier/Composer/FullContext/session/routes/API/UI/config;
- golden/live/eval fixtures;
- A9 design/raw/frozen/harness/evidence/re-audit;
- live/LLM, merge, `main`, other branches, product authority.

## Acceptance tests

### Synthetic vertical contract

`tests/test_target_offline_response_assembly.py` proves:

1. exact API/result fields, frozen/slots shell, tuple outputs and detached nested models;
2. service ID/name/alias enters via S26; unknown gets S27 not-found; invalid/ambiguous S26
   errors propagate unchanged;
3. `brand_term=None` uses S23, preserves eligible multi-brand/unbranded ordering/cap;
4. brand ID/canonical/alias enters via S25 then S24; unknown gets S27 not-found;
5. invalid/ambiguous S25 errors propagate unchanged;
6. other-brand/unbranded/inactive offers never leak in branded result;
7. known brand without service offer returns empty, no fallback;
8. inactive parent service cannot resolve; inactive offers filtered;
9. S15 first rule/priority/cap metadata preserved;
10. exact service content ref drives S22 consultation close/cadence;
11. marketing refs/facts/CTA/limits/shown snapshots preserved exact;
12. linked doctors carried in authored order without ranking;
13. fixed/from/range/no-public money/package/stages/followups unchanged;
14. result exposes no S10 context/all-authored offer collection;
15. repeated calls stateless/no input mutation;
16. fixed error precedence is proven across boundaries:
    - service invalid/ambiguous/not-found happens before any brand or S22 validation;
    - once service is valid, brand invalid/ambiguous/not-found happens before S22;
    - only after both identities are valid may evidence/marketing validation run;
17. with valid identities, at least one representative S21 validation error and one
    representative S22-only validation error propagate unchanged in exact exception
    type, `code`, `value` and message; S27 never wraps them;
18. source/API inspection proves S27 introduces/raises only
    `offline_assembly_service_not_found` and `offline_assembly_brand_not_found`, has no
    broad exception translation, and cannot invent other assembly error codes;
19. imports only stdlib/contracts + pure S21–S26 facade dependencies; no IO/client/runtime.

### Real demo vertical acceptance

`tests/test_demo_target_offline_response_assembly.py` proves read-only:

1. real bundle/doctors/external index/consultations loaded through existing frozen tools;
2. `All-on-4`, no brand, service semantic context returns exact service/content ref,
   linked doctors, S16 order Impro→Implantium→Nobel, consultation close and limits;
3. `All-on-4` + `нобель` returns only Nobel 428000 RUB/jaw with package/stages/followups;
4. price/cost marketing selects exact commercial facts and blocks consultation when
   S21/S22 amplifier limit is full;
5. doctor-trust scenario carries exact doctor refs + initial fact, without doctor ranking;
6. `caries`, no brand, returns its generic eligible offer and linked doctors/data;
7. known demo brand with no caries offer returns empty, not caries generic price;
8. unknown service/brand fail closed;
9. source files unchanged; no product imports/writes/skip/xfail/live/LLM.

### Minimal neighbors

- S22: `tests/test_target_response_evidence.py`, `tests/test_demo_target_response_evidence.py`;
- S23/S24: `tests/test_target_offer_projection.py`,
  `tests/test_demo_target_offer_projection.py`,
  `tests/test_target_brand_offer_projection.py`,
  `tests/test_demo_target_brand_offer_projection.py`;
- S25/S26: `tests/test_target_brand_resolver.py`,
  `tests/test_demo_target_brand_resolver.py`,
  `tests/test_target_service_resolver.py`,
  `tests/test_demo_target_service_resolver.py`.

No full suite, legacy runtime tests, A9 or live/LLM.

## Checker and git gates

1. Governance TASK + roadmap pending; independent read-only checker `✅` before code.
2. Commit `docs: govern vertical offline response assembly S27`; push only stage-a.
3. Implement only allowlist; target then minimal neighbors.
4. Independent completion checker `✅`; then roadmap `[x]`.
5. Commit `feat: assemble vertical offline response materials S27`; push stage-a.
6. Final clean/synced.

## Definition of Done

- S27 composes existing target components without duplicating their decisions;
- final output hides all unprojected offers and preserves exact facts/money/limits;
- both checker gates `✅`, target/neighbors green, no skip/xfail;
- no client/contracts/runtime/authority/A9/live changes;
- two commits pushed only stage-a, clean/synced;
- next checkpoint evaluates minimal ResponseSpec over this proven material boundary,
  not another data/lookup layer.
