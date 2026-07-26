# FINAL_PRICE_SCOPE_COVERAGE_NAV — seam audit (read-only)

**Date:** 2026-07-26  
**Baseline:** `f5c5c96` (`codex/stage-a`) · **FINAL_PRICE_AND_SERVICE_COVERAGE complete**  
**Scope:** Phase 1 governance only · **NO IMPLEMENTATION / NO LIVE / NO LLM**

**Canonical law:** `docs/PRICE_SERVICE_ARCHITECTURE.md` (rules 24–30, 27–29 few_teeth semantics).

---

## Verdict

UiScopeAction / EffectiveScope / session `patient_facts` correctly persist `few_teeth`. **Bug is in AC2+AC3:** service-level applicability is used as offer-level price applicability. Service `classic` applies to `one_tooth` and `few_teeth`, but published offers (`classic.one_tooth.*`) are priced only for `one_tooth`. Broad anchors and scoped `few_teeth` paths therefore emit one-tooth evidence; Composer may adapt numbers; numeric Verifier blocks; user sees fallback stub.

**Fix axis:** separate **service situational applicability** from **offer price-route applicability** via typed `TargetOffer.applies_to_extents`, then filter anchors, scoped selection, and scope-nav buttons to **confirmed price routes only**.

---

## Repro seam (binding)

| Layer | Current behavior | Expected |
|-------|------------------|----------|
| UI click `target:ui_scope/implantation/few_teeth` | ✅ `UiScopeAction.extent=few_teeth` | unchanged |
| `EffectiveScope` / session | ✅ `few_teeth` persisted | unchanged |
| `filter_applicable_services` | ✅ `classic` in shortlist for `few_teeth` | unchanged (service applicability) |
| `project_target_service_offers` | ❌ returns `classic.one_tooth.*` for `few_teeth` strategy context | filter by `applies_to_extents` |
| `_broad_anchor_selection` | ❌ may anchor `few_teeth` via service match without offer route | anchor only if numeric offer confirms extent |
| `materialize_scope_nav_followups` | ❌ always 3 buttons when labels exist | emit only extents with confirmed price routes |
| scoped `few_teeth` without route | ❌ one-tooth price evidence | `data_gap` (no digits) or family-level with disclaimer |

---

## Root cause

```
service applicability (catalog.selection)  ≠  offer price applicability (offer.applies_to_extents)
```

AC2 `_project_offers_for_service` → `project_target_service_offers` ranks by strategy but **does not** check whether an offer is authored for the patient extent. Strategy context carries `extent=few_teeth` for ranking rules, not offer filtering.

Demo evidence: `clients/demo/target_response/pricebook/services/classic.one_tooth.*.json` — package label «за один зуб под ключ»; no `few_teeth` offers for `classic`.

---

## Owner normative behavior (binding)

### Broad (extent unknown)

| Confirmed price routes | Text anchors | Scope buttons |
|------------------------|--------------|-----------------|
| `one_tooth` + `full_arch` | both | «Один зуб», «Все зубы на челюсти» |
| `one_tooth` only | one-tooth | «Один зуб» only |
| `one_tooth` + `few_teeth` + `full_arch` | all three | all three |
| family-only (`family_only_broad`) | single family price | **no** scope buttons (existing FPS) |

### Scoped `few_teeth` without dedicated route

- Do **not** use one-tooth price as final answer
- Do **not** multiply price
- Do **not** substitute another protocol
- `data_gap` without invented digits **or** existing family-level price with explicit disclaimer
- No system stub from missing offer

### Out of scope (do not add)

- «Зубы рядом» / «В разных местах» / «Не знаю» clarification
- New patient axis or nested menu

---

## Minimal typed contract (implementation)

Extend `TargetOffer` (optional field, backward-compatible default):

```json
{
  "offer_id": "classic.one_tooth.implantium",
  "service_id": "classic",
  "applies_to_extents": ["one_tooth"],
  "price": { "mode": "fixed", "amount": 76200, "currency": "RUB", "billing_unit": "tooth_package" }
}
```

**Default rule (when field absent):** derive from `service.selection.extent` if present; else treat as applicable to all extents the service supports (migration safety for sparse fixtures). Demo rich pack: **explicit** `applies_to_extents` on all priced offers.

**Validation:** each value ∈ `one_tooth | few_teeth | full_arch`; non-empty; subset of parent service selection extents when service declares extent list.

---

## Existing mechanisms — preserve

| Mechanism | File | Role |
|-----------|------|------|
| Service applicability | `core/target_service_applicability.py` | unchanged |
| Offer projection / strategy | `core/target_offer_projection.py`, `core/response_strategy.py` | add extent filter after eligibility |
| AC2 broad anchors | `core/target_scope_aware_selection.py` | anchor only confirmed extents |
| AC3 scope nav | `core/target_client_ui_nav.py` | filter buttons by confirmed extents |
| AC3 package | `core/target_scope_aware_price_package.py` | pass confirmed extents; scoped data_gap |
| Family-only broad | `core/target_family_price_resolution.py` | unchanged (no scope buttons) |
| Verifier | `core/target_response_verifier.py` | **no redesign** |
| Frozen live artifacts | Retry1–4, A9/A9R/S-series, W1b | byte-identical |

---

## Implementation seams (Phase 2 allowlist)

| Seam | File | Change |
|------|------|--------|
| Contract | `contracts/response_schema.py` | `applies_to_extents` on `TargetOffer` |
| Offer extent gate | `core/target_offer_extent_applicability.py` (new) | filter + default inference |
| Projection | `core/target_offer_projection.py` | apply extent filter |
| AC2 | `core/target_scope_aware_selection.py` | anchors + scoped few_teeth gap |
| AC3 nav | `core/target_client_ui_nav.py` | `materialize_scope_nav_followups(confirmed_extents=...)` |
| AC3 package | `core/target_scope_aware_price_package.py` | wire confirmed extents |
| Selection result | `contracts/target_scope_aware_selection.py` | optional `price_confirmed_extents` tuple |
| Demo data | `clients/demo/target_response/pricebook/services/*.json` | explicit `applies_to_extents` |
| Tests | `tests/test_final_price_scope_coverage_nav_*.py` | acceptance + fixtures |

**Forbidden:** LIVE/LLM, new patient axes, quantity clarification UI, Verifier redesign, regex stop-lists, feature flags, per-MD routing, W1b restore, frozen artifact edits.

---

## Acceptance matrix (binding)

| ID | Case |
|----|------|
| A | Rich demo broad implantation — anchors for `one_tooth` + `full_arch`; buttons only for confirmed routes (not 3 if `few_teeth` has no route) |
| B | Broad with only `one_tooth` priced — single anchor + single «Один зуб» button |
| C | Broad with `one_tooth` + `few_teeth` + `full_arch` priced — three anchors + three buttons |
| D | UI click `few_teeth` when no few_teeth route — `data_gap` or family disclaimer; **no** one-tooth price evidence |
| E | UI click `one_tooth` — unchanged concrete/scoped price path |
| F | `family_only_broad` — still no scope buttons (FPS regression) |
| G | Full rich pricebook scoped/full_arch paths — byte/semantic equivalent |
| H | No invented multiplication / cross-extent price substitution |
| I | `/ask` + `/ask/stream` parity (existing harness smoke) |
| J | Frozen Retry4 / W1b / widget matrix unchanged |

Sparse fixtures: in-memory only.

---

## Frozen artifact guards

Immutable: Retry1–4 live artifacts, A9/A9R/S-series, W1b checksum pins, widget matrix `f4eecf75…`.

---

## STOP

Governance checkpoint only. Implementation requires PRE-CODE ✅ then owner continuation in same milestone.
