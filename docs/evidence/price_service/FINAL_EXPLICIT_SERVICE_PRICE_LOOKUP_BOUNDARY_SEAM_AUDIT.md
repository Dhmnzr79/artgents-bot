# FINAL_EXPLICIT_SERVICE_PRICE_LOOKUP_BOUNDARY — seam audit (read-only)

**Date:** 2026-07-26  
**Baseline:** `19297fc` (`codex/stage-a`) · **FINAL_PROSTHETICS_PRICE_NAV_REACHABILITY complete**  
**Scope:** Phase 1 governance only · **NO IMPLEMENTATION / NO LIVE / NO LLM**

**Canonical law:** `docs/PRICE_SERVICE_ARCHITECTURE.md` (AC2 applicability vs commercial lookup).

---

## Verdict

Cross-turn **explicit named-service price lookup** is incorrectly gated by **inherited session patient applicability**. When `TurnFrame.service_id` is confidently set and price is requested, AC2/S23 still filter through `SelectionPatientContext` built from merged `EffectiveScope` — including **session** `extent=full_arch`. That drops services like `one_stage` (authored `one_tooth|few_teeth` + `extraction_context`) and yields **empty structured evidence** → `scoped_evidence_component_unfulfilled` → `target_fullcontext_error`.

Fix: **deterministic boundary** inside existing AC2/AC3 — separate **commercial catalog lookup** (explicit service + price) from **patient applicability** (broad/scoped recommendation). **No second pipeline, no new selector, no session reset.**

---

## 1. Repro chain @ `19297fc`

**Scenario:**

1. Session stores `patient_facts.extent=full_arch` (prior jaw-scope price turn).
2. User: «А сколько стоит одномоментная имплантация?»
3. Planner sets `service_id=one_stage`, `intent=price_lookup`, `topic=implantation`.

**Observed failure path:**

| Step | File | Behavior |
|------|------|----------|
| AC1 merge | `core/target_effective_scope_merge.py` | `extent_axis.source=session`, `extent=full_arch` (topic-fresh session facts) |
| Dispatch | `core/target_turn_frame_dispatch.py` L295–296 | `_service_id_is_usable` → **named-service path** (scope-price preempted) |
| S27 assembly | `core/target_offline_response_assembly.py` L112–116 | `project_target_service_offers(..., strategy_context)` |
| S23 extent filter | `core/target_offer_projection.py` L82–90 | `filter_offers_for_extent(..., patient_extent=full_arch)` |
| Offer data | `one_stage.*.json` | `applies_to_extents: ["one_tooth"]` only |
| Result | — | **zero offers** |
| S28 plan | `core/target_response_materialization_plan.py` L94–95 | `unfulfilled_components=("price",)` |
| S35 evidence | `core/target_scoped_response_evidence.py` L395–396 | `scoped_evidence_component_unfulfilled` |
| Runtime | `core/target_runtime_widget.py` L280 | `target_fullcontext_error` |

Parallel AC2 path (scope-aware explicit service) has the same root cause:

| Step | File | Behavior |
|------|------|----------|
| AC2 gate | `core/target_service_applicability.py` L86–94 | `one_stage` mode `context` + constraints → `_selection_matches(selection, patient)` with `extent=full_arch` → **False** |
| Selection | `core/target_scope_aware_selection.py` L77–94 | `filter_applicable_services` → `no_applicable_services` |

User question is valid: asking a **public catalog price** must not require prior patient applicability proof.

---

## 2. Two operations conflated today

| Operation | When | Patient axes | Output |
|-----------|------|--------------|--------|
| **Commercial catalog lookup** | Confident `service_id` + price intent/aspect | Should **not** use inherited session axes to block | Canonical target pricebook offers |
| **Patient applicability** | Broad/scoped family price, recommendations | extent/stage/jaw/reported_context from merged scope | Filtered service shortlist |

Today both use the same `SelectionPatientContext` / `TargetStrategyMatch.extent` derived from **full merged** `EffectiveScope` (`core/target_strategy_context.py` L27–44, L57–59).

---

## 3. Unknown stage on explicit lookup

`one_stage` authored `selection.stage: [extraction_context]`. Session stage is usually unknown.

- **Applicability path:** `_selection_matches` fails on missing stage → service excluded.
- **Offer projection path:** stage not filtered in S23 (only extent) — but extent already removed all offers.

For explicit lookup, **missing stage must not block** catalog price display. Stage remains relevant only for **recommendation** paths (scoped family, broad anchors).

---

## 4. Where empty evidence forms

```
materials.offers == ()
  → plan.offer_ids == ()
  → plan.unfulfilled_components contains "price"
  → build_target_scoped_response_evidence() fail-closed
  → materialize_target_composer_request() never runs with offer blocks
  → composer_executor_request_invalid OR upstream verification error
  → widget route target_fullcontext_error
```

No fallback to family price (correct — must not invent jaw totals for named protocol).

---

## 5. Minimal fix seam (no second pipeline)

### 5.1 Detection signal (existing, no regex)

Explicit service price lookup when **all** hold:

- `TurnFrame.service_id` valid + confidence threshold (`target_turn_frame_dispatch._service_id_is_usable`)
- Price component requested (`_price_component_requested` / `required_components` contains `price`)
- Service active in client catalog

Reuse existing `spec.service_id` / `explicit_service_id` — **not** a new route.

### 5.2 Lookup patient context vs applicability context

`EffectiveScope` already carries per-axis provenance (`extent_axis`, `stage_axis`, `jaw_axis` — `contracts/effective_scope.py`).

| Axis source | Role in explicit lookup |
|-------------|-------------------------|
| `ui_action`, `ui_stage_action`, `a9_turn` | **Current-turn** — may constrain offer extent filter / incompatible-scope data_gap |
| `session` | **Inherited** — must **not** filter explicit named-service catalog lookup |
| `unknown` | Neutral lookup — show authored public offers |

New pure helper (proposed): `core/target_explicit_service_price_lookup.py`

- `is_explicit_service_price_lookup(...)`
- `lookup_patient_context_for_explicit_price(effective_scope)` — session axes stripped
- `explicit_lookup_extent_conflicts(service, offers, lookup_context)` — fail-closed data_gap when current-turn axis incompatible with all offer `applies_to_extents`

### 5.3 Wire points (implementation allowlist)

| File | Change |
|------|--------|
| `core/target_explicit_service_price_lookup.py` | **new** — boundary helpers |
| `core/target_service_applicability.py` | explicit lookup bypasses inherited session axis gate |
| `core/target_offer_projection.py` | extent filter uses lookup context, not merged session extent |
| `core/target_offline_response_assembly.py` | pass lookup mode into S23 |
| `core/target_scope_aware_selection.py` | explicit `explicit_service_id` path uses lookup context |
| `core/target_response_stage.py` | incompatible current-turn scope → `data_gap` for explicit lookup |
| `core/target_strategy_context.py` | optional: `lookup_patient_context_from_effective_scope` |

**Not required:** `target_runtime_turn.py`, `target_effective_scope_merge.py`, `target_turn_frame_dispatch.py`, Planner, A9 merge, session schema, Verifier redesign.

### 5.4 Incompatible current-turn scope (case 6)

«Сколько стоит одномоментная имплантация **всей челюсти**?»

- Current-turn extent from `a9_turn` or typed UI may be `full_arch`.
- Offers are per-tooth (`applies_to_extents: one_tooth`).
- **Must not** multiply or substitute jaw family price.
- Fail-closed: existing `data_gap` / controlled clarification with billing unit honesty.

Distinguish using **axis provenance**, not phrase regex.

---

## 6. Session semantics (unchanged)

- Do **not** clear session or `patient_facts` for lookup.
- Do **not** write service name as patient fact.
- Vague follow-up «А сколько?» without new `service_id` keeps existing session focus rules.
- Materialized answer may update ordinary service focus (existing session selection path).

---

## 7. Regression surfaces to preserve

| Surface | Expectation |
|---------|-------------|
| Broad «Сколько стоит имплантация?» | AC2/AC3 overview + scope buttons unchanged |
| Typed `UiScopeAction` / `UiStageAction` | Planner skip, stage clarify unchanged |
| Offer reachability (`price_navigable_extents`) | Unchanged |
| Informational content-only turns | No accidental price lookup |
| Frozen Retry/A9/W1b/S-series artifacts | Byte-identical |

---

## 8. Acceptance matrix (binding, 18 + cross-turn matrix)

| ID | Case |
|----|------|
| 1 | Session `full_arch` → explicit `one_stage` price materialized |
| 2 | Session `one_tooth` → explicit `all_on_4` jaw prices shown |
| 3 | Session `full_arch` → explicit zirconia from 25 000 ₽ |
| 4 | Explicit `one_stage`, stage unknown — price shown, no eligibility claim |
| 5 | Explicit service + compatible current-turn scope — correct offers/units |
| 6 | Explicit service + incompatible current-turn scope — data_gap, no jaw math |
| 7 | Named service, no public price — existing no_public_price/data_gap |
| 8 | Named service absent — existing not-offered path |
| 9 | Vague «А сколько?» without new service_id — session continuity |
| 10 | Broad implantation overview unchanged |
| 11 | Typed scope/stage clicks unchanged |
| 12 | Informational question without price — no lookup |
| 13 | No personal eligibility / treatment choice in response |
| 14 | Exact prices, brands, billing units preserved |
| 15 | `/ask` + `/ask/stream` parity |
| 16 | SID isolation / reset / terminal rules unchanged |
| 17 | Sparse multiclient fixture — no demo service IDs in core |
| 18 | Frozen artifacts byte-identical |

**Cross-turn regression matrix (offline):** for each authored session extent × each active priced service explicit ask — no generic error; exact offer applicability and billing unit preserved.

---

## 9. Forbidden

- regex / phrase lists for lookup detection
- session clear as workaround
- `one_stage` hardcode
- demo client IDs in shared core
- new pricing route / selector
- family price fallback for named protocol
- eligibility claims
- LIVE / LLM / Planner / A9 tuning / Verifier redesign

---

## STOP

Governance checkpoint only. Implementation after PRE-CODE ✅ and separate owner GO.
