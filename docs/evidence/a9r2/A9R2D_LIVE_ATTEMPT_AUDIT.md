# A9R2d planner-only live attempt audit

**Date:** 2026-07-25  
**Baseline:** `e50647c` (model-pin wiring COMPLETION ✅)  
**Matrix v3 blob:** `8ccd9bdc140a192981fcc48ad7ed0367a40b0a84`  
**Planner calls:** 17 / 17 budget · **retry:** 0  
**Authority:** not enabled · **Rerun:** blocked without new owner approval

## Model provenance (verified)

| Field | Value |
|-------|-------|
| `owner_requested_model` | `qwen3.7-plus` |
| `configured_model` | `qwen3.7-plus` |
| `provider_observed_models` | `qwen3.7-plus` × 17 |
| `provider_model_verified` | **true** |

Model-pin wiring succeeded; no `MODEL_MISMATCH` incident.

## Automated verdict

| Field | Value |
|-------|-------|
| `automated_verdict` | `AUTOMATED_FAIL` |
| `final_verdict` (post manual review) | `FAIL` |
| `positive_axis_recall` | 0.929 (13/14) |
| `true_composite_exact_turn_rate` | **0.882** (15/17) |
| `correction_success_rate` | 1.0 (1/1) |
| `wrong_non_unknown_axis_count` | 0 |
| `material_false_positive_axis_count` | **1** |
| `negative/ambiguous material FP` | **0** |
| `transport_provider_error_count` | 0 |
| `malformed_projection_count` | 0 |

### Gates

| Gate | Actual | Pass |
|------|--------|------|
| wrong concrete material axis | 0 | ✅ |
| material false-positive (extent/jaw/stage) | 1 | ❌ |
| positive recall ≥ 0.85 | 0.929 | ✅ |
| correction success | 1.0 | ✅ |
| `true_composite_exact_turn_rate` ≥ 0.85 | 0.882 | ✅ |
| malformed/transport | 0 | ✅ |
| calls ≤ 17 | 17 | ✅ |
| retry = 0 | 0 | ✅ |

### Per-axis material diagnostic

| Axis | Correct | Miss | False positive |
|------|---------|------|----------------|
| extent | 8 | 1 | 1 |
| jaw | 3 | 0 | 0 |
| stage | 2 | 0 | 0 |

## Misses (expected positive → unknown)

| Call | Axis | Expected |
|------|------|----------|
| `a9r_stage_02_natural_tooth_present` | extent | `one_tooth` |

## Wrong concrete values

**None.**

## Material false positives (extent/jaw/stage)

| Call | Axis | Observed | Category |
|------|------|----------|----------|
| `a9r_jaw_03_both` | extent | `full_arch` | jaw_positive |

## Negative/ambiguous material false positives

**None.**

## Plus vs Flash comparison (extent/jaw/stage)

| Call | Flash (A9R2b) | Plus (A9R2d) | Delta |
|------|---------------|--------------|-------|
| `a9r_extent_01` | extent ✅ jaw ✅ | extent ✅ jaw ✅ | — |
| `a9r_extent_03` | stage FP | stage ✅ | **Plus fixed** |
| `a9r_jaw_01` | stage FP | stage ✅ | **Plus fixed** |
| `a9r_jaw_03` | extent FP | extent FP | unchanged |
| `a9r_stage_02` | extent miss | extent miss | unchanged |
| `a9r_typo_01` | jaw FP | jaw ✅ | **Plus fixed** |
| `a9r_typo_02` | stage FP | stage ✅ | **Plus fixed** |

**Net vs Flash (A9R2b):** material FP 5 → **1**; `true_composite` 0.647 → **0.882**; same remaining miss (`stage_02` extent) and same `jaw_03` extent FP.

## Immutable artifacts (SHA256)

| File | SHA256 |
|------|--------|
| `a9r2d_patient_scope_live_raw.json` | `1dcac8378e3096fdc83f96a6be561c1bd2fa120566237bf723531f7857a0f3b2` |
| `a9r2d_patient_scope_live_result.json` | `073d2143d9c606ff84008a4d2081b90feb33d019939de1c59756411cd3c2c423` |
| `a9r2d_patient_scope_live_attempt.json` | `ce58abcaef2a8c6864758d93dd6412cb15df29ef273efbe2e910f750d790b495` |
| `a9r2d_patient_scope_live_call_ledger.jsonl` | `eec8b8fefbfc3bbff573a49327d32e3b0b5c3b92da5c7297fc650cfaf6aacfe6` |
| `a9r2d_patient_scope_live_manual_review.json` | `f2f533b5c9afb2757c626ddb9e505f7f8a81c681511d6b2dce5d56f92b582415` |

## Owner conclusion

Single valid Plus live attempt complete. Model-pin verified on all 17 calls. Gates fail on **1 material FP** (`jaw_03` extent) + **1 extent miss** (`stage_02`). Composite gate passes (0.882). **No A9R3 / no product wiring.** **STOP** — owner decision required before any authority action. **Do not rerun** without new owner approval.
