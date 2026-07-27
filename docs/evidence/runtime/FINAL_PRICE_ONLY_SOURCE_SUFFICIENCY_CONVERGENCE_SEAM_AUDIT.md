# FINAL_PRICE_ONLY_SOURCE_SUFFICIENCY_CONVERGENCE — seam audit

**Дата:** 2026-07-27  
**Baseline:** `codex/stage-a` @ `c4de72c`  
**Режим:** governance / docs / tests only · **NO product code / NO LIVE / NO LLM**  
**Owner GO:** Phase 1 governance only; implementation blocked until PRE-CODE ✅ + separate owner GO

## Preflight

| Check | Result |
|---|---|
| Branch | `codex/stage-a` ✅ |
| `HEAD` == `origin/codex/stage-a` @ `c4de72c` | ✅ |
| Working tree clean at governance start | ✅ |
| Prior milestone landed | `FINAL_SERVICE_AVAILABILITY_AND_CLINIC_CAPABILITY_ROUTING` @ `c4de72c` |
| Semantic/Numeric/Contact Verifier | **KEEP** — no change without reproducible defect |

## Executive summary

Runtime defect: **price-only follow-up after availability** for `tomography` (no `content_ref`, validated offer
`tomography.default` @ 3 000 RUB) passes Scoped Evidence but fails Composer Request with
`composer_request_source_mismatch: ["content", null]`.

**Root cause:** duplicate invariant with **divergent semantics** — `target_scoped_response_evidence` @ `c4de72c` allows
`selected_content_ref=None` when `required_components==("price",)` and `offer_ids` non-empty; Composer
`_exact_sources` unconditionally requires `materials.selected_content_ref in owned_content_refs` where
`None ∉ ∅`.

**Target:** one shared pure predicate (e.g. `is_price_only_offer_source_sufficient(...)`) used by
materialization plan, scoped_evidence layer, composer request, and package validation — **not** a local Composer-only `if`.

---

## Normative concepts (binding)

### Price-only offer source sufficiency

MD `content_ref` is **not** required when **all** of:

1. exact canonical `service_id` is valid and matches materials/scoped evidence;
2. required/requested components are strictly `("price",)` — not content, not content+price;
3. plan contains ≥1 validated active offer id;
4. every offer belongs to that `service_id`;
5. each offer is present in canonical bundle, materials, and scoped evidence (triple match);
6. response spec allows price (`requested_components` includes price; not generic_fullcontext);
7. `unfulfilled_components` is empty;
8. not Generic FullContext path;
9. not content+price dual-primary response;
10. not family/broad price inheritance for named protocol (existing `target_family_price_resolution` rules).

When sufficient:

- `selected_content_ref=None` valid;
- `primary_content_ref=None` valid;
- Composer evidence = structured `offer:*` blocks only (no fake content block);
- Numeric Verifier still grounds amounts from PRIMARY_EVIDENCE offers;
- no source-driven followups / video / situation without validated MD source.

### Where content_ref remains mandatory

- content-only, content+price, FAQ/info/how-it-works, comparison with content, service description;
- consultation value, marketing claims requiring authored evidence;
- price without validated offer → `data_gap` / `no_public_price`, **not** source mismatch.

---

## Documented runtime defect

### Cross-turn dialogue

| Turn | User | Planner | Expected | Actual @ `c4de72c` |
|---|---|---|---|---|
| 1 | «Делаете 3D-диагностику?» | `service_id=tomography`, `service_availability` | deterministic availability yes | ✅ materialized |
| 2 | «А сколько стоит?» | `service_id=tomography`, `followup_of=tomography`, `price_lookup`, `aspects=["price"]` | 3 000 ₽ structured price | ❌ `composer_request_source_mismatch` |

**Pricebook:** `clients/demo/target_response/pricebook/services/tomography.default.json` — `active=true`, fixed 3 000 RUB.

**Focus continuity:** session hydration + planner continuity work; failure is **only** Composer source validation.

### Direct

«Сколько стоит КТ?» with `service_id=tomography`, price aspect — same Composer failure if runtime reaches
Composer Request (not tested end-to-end in prior completion matrix).

---

## Phase 1 seam audit checklist

### 1. Places treating `selected_content_ref` / `primary_content_ref` as mandatory

| Layer | File | Behavior @ `c4de72c` |
|---|---|---|
| Offline assembly | `core/target_offline_response_assembly.py` L103 | sets `selected_content_ref=service.content_ref` (None for tomography) |
| Evidence package | `core/target_response_evidence.py` L138–155 | validates content_ref only when non-None |
| Materialization plan | `core/target_response_materialization_plan.py` L91–96 | content unfulfilled unless `allow_missing_content` |
| Scoped evidence | `core/target_scoped_response_evidence.py` L503–510 | **allows** price-only + offers without content |
| Composer request | `core/target_composer_request.py` L331–340 | **blocks** `None not in owned_content_refs` |
| Verifier | `core/target_response_verifier.py` L660+ | uses `primary_content_ref` when set; no mandatory MD for offer-only |
| Presentation | `core/target_presentation_decision.py` L128+ | skips source-driven UI when `primary_content_ref` absent |

### 2. required vs requested components, stage, offers, unfulfilled

| Field | Producer | Consumer | Notes |
|---|---|---|---|
| `required_components` | dispatch → spec | plan, scoped evidence | price-only = `("price",)` |
| `requested_components` | policy request | spec mirror | must align with plan |
| `response_stage` | offline package | composer overlays, scoped branches | `data_gap` / `stage_clarify` separate path |
| `offer_ids` | plan | scoped records, composer `_exact_sources` | triple validation in composer |
| `unfulfilled_components` | materialization plan | scoped evidence hard-stop | must be empty before composer |

### 3. Composer source identity contract (offer-only)

`materialize_target_composer_request` → `_exact_sources` validates service, **content**, offers, doctors, facts.
Offer branch (L342–353) already triple-checks bundle/materials/scoped. Content branch (L339–340) has **no**
price-only exception → defect.

Evidence blocks for price-only should be `kind=offer`, `ref=offer:tomography.default`, `must_preserve_exact=True`.

### 4. Verifier behavior with `primary_content_ref=None`

Numeric path uses offer PRIMARY_EVIDENCE blocks; Semantic unchanged. No Verifier change required for
Phase 2 if Composer emits offer-only evidence and source identity omits invented MD refs.

### 5. Presentation attribution without MD source

`target_presentation_decision` — no video/situation/followups from missing `primary_content_ref`.
Price-only must not surface content-driven buttons.

### 6. Direct and cross-turn price lookup

- Cross-turn: session `last_service_id=tomography` + vague price follow-up → hydration restores service (S62).
- Direct: explicit `service_id` + price aspect → same package path.
- Both hit same `_exact_sources` content check.

### 7. Services without content_ref but with numeric offer

`tomography` — catalog `active=true`, no `content_ref`, offer `tomography.default` fixed price.
Canonical Phase 2 fixture.

### 8. Services with `no_public_price`

`core/target_family_price_resolution.py` — named protocol must not inherit family price; returns `data_gap`.
Price-only sufficiency **must not** bypass missing-offer cases.

### 9. Content+price path

`required_components==("content","price")` — content_ref mandatory; shared predicate returns false.

### 10. Family / broad / scoped price paths

`core/target_scope_aware_price_package.py`, `target_family_price_overview.py` — separate specs with
`service_id=None` or scope topics. **Out of scope** for price-only offer exception; matrix rows 17–20 guard.

### 11. Named protocol family-price inheritance

`explicit_lookup_offer_extent_conflicts` + `resolve_named_service_price_stage` — existing guards; unchanged.

### 12. `/ask` and `/ask/stream` parity

Same `_orchestrate_ask_turn` path; widget-faithful offline harness required in Phase 2.

### 13. Session / SID / reset / freshness

Cross-turn matrix rows 2, 28–29: SID isolation, fresh SID direct price, service focus age.

### 14. Client-aware sparse fixture

No demo hardcodes; use `test_final_client_pack_data_convergence_sparse_pack` pattern.

### 15. Why prior completion test missed Composer Request

`tests/test_final_service_availability_and_clinic_capability_routing_implementation.py`:

- Scenario 17 «Сколько стоит КТ?» tested **dispatch only** (`dispatch_target_turn_frame_response`), not
  `materialize_target_composer_request` / full runtime turn.
- No cross-turn availability → price dialogue scenario.
- No assertion on `composer.invocations` or `offer:tomography.default` evidence blocks.
- Prior Phase 2 STOP condition avoided Composer changes outside allowlist.

Phase 2 matrix **must** include real Composer Request validation and cross-turn widget-faithful paths.

---

## Proposed shared contract (Phase 2)

### Canonical API (minimal)

```python
# contracts/price_only_source_sufficiency.py (proposed)

@dataclass(frozen=True)
class PriceOnlySourceContext:
    service_id: str
    required_components: tuple[str, ...]
    requested_components: tuple[str, ...]
    offer_ids: tuple[str, ...]
    selected_content_ref: str | None
    primary_content_ref: str | None
    unfulfilled_components: tuple[str, ...]
    response_stage: str | None
    is_generic_fullcontext: bool
    allow_price: bool  # derived from spec / path

def is_price_only_offer_source_sufficient(ctx: PriceOnlySourceContext) -> bool:
    ...
```

**Consumers (implementation allowlist):**

| Seam | File |
|---|---|
| Shared predicate | `contracts/price_only_source_sufficiency.py` CREATE |
| Materialization plan | `core/target_response_materialization_plan.py` UPDATE |
| Scoped evidence | `core/target_scoped_response_evidence.py` UPDATE — replace ad-hoc `if` |
| Composer request | `core/target_composer_request.py` UPDATE — `_exact_sources` |
| Evidence package (if needed) | `core/target_response_evidence.py` UPDATE |
| Offline package validation (if needed) | `core/target_offline_response_package.py` UPDATE |
| Tests | `tests/test_final_price_only_source_sufficiency_convergence_implementation.py` CREATE |
| Harness | `tests/test_final_price_only_source_sufficiency_convergence_harness.py` CREATE |
| Unit | `tests/test_target_composer_request.py` UPDATE — tomography price-only fixture |

**KEEP unchanged:** Semantic/Numeric/Contact Verifier policy, Generic FullContext, structured availability,
AC1–AC3 price routes, family price paths, frozen pins.

---

## Pipeline gate inventory (delta)

| Gate | @ `c4de72c` | Target |
|---|---|---|
| G28 Materialization plan | `allow_missing_content` marker only for structured availability | shared price-only predicate |
| G35 Scoped evidence | local price-only `if` | shared predicate |
| G36 Composer request | content_ref always required for service-bound | shared predicate → offer-only evidence |
| G37 Verifier | offer grounding OK | unchanged |
| G38 Presentation | no MD → no source UI | unchanged |

---

## Forbidden solutions (Phase 1)

- NO local Composer-only `if` without shared predicate  
- NO Verifier / Numeric grounding weakening  
- NO fake `content_ref` or MD stub files  
- NO family-price inheritance expansion  
- NO Generic FullContext prices  
- NO regex/phrase routing  
- NO second pipeline / selector  
- NO RAG / legacy fallback  
- NO frozen artifact changes  
- NO LIVE / LLM / E2E in governance  

---

## STOP (Phase 1)

After governance commit + PRE-CODE PASS — **остановиться**. Implementation, LIVE, E2E и Verifier changes
запрещены до отдельного owner GO.
