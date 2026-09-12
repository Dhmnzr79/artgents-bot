# A9R2b planner-only live attempt audit

**Date:** 2026-07-25  
**Baseline:** `8782092` (live GO) · manifest `git_head` at run time  
**Matrix v3 blob:** `8ccd9bdc140a192981fcc48ad7ed0367a40b0a84`  
**Model:** `qwen3.6-flash` via `TURN_PLANNER_LLM_MODEL`  
**Planner calls:** 17 / 17 budget · **retry:** 0  
**Authority:** not enabled · **Rerun:** blocked without new owner approval

## Automated verdict

| Field | Value |
|-------|-------|
| `automated_verdict` | `AUTOMATED_FAIL` |
| `final_verdict` (post manual review) | `FAIL` |
| `positive_axis_recall` | 0.929 (13/14) |
| `composite_exact_turn_rate` | 0.917 (11/12) |
| `correction_success_rate` | 1.0 (1/1) |
| `wrong_non_unknown_axis_count` | 0 |
| `material_false_positive_axis_count` | 5 |
| `negative/ambiguous material FP` | **0** |
| `diagnostic reported_context FP` | 0 |
| `transport_provider_error_count` | 0 |
| `malformed_projection_count` | 0 |

### Gates

| Gate | Actual | Pass |
|------|--------|------|
| wrong concrete material axis | 0 | ✅ |
| material false-positive (extent/jaw/stage) | 5 | ❌ |
| positive recall ≥ 0.85 | 0.929 | ✅ |
| correction success | 1.0 | ✅ |
| composite exact ≥ 0.85 | 0.917 | ✅ |
| malformed/transport | 0 | ✅ |
| calls ≤ 17 | 17 | ✅ |
| retry = 0 | 0 | ✅ |

## Misses (expected positive → unknown)

| Call | Axis | Expected |
|------|------|----------|
| `a9r_stage_02_natural_tooth_present` | extent | `one_tooth` |

Observed: `stage=natural_tooth_present` ✅, `extent=unknown` ❌ (v3 label expects both).

## Wrong concrete values

None.

## Material false positives (extent/jaw/stage)

| Call | Axis | Observed | Category |
|------|------|----------|----------|
| `a9r_extent_03_few_teeth_missing` | stage | `natural_tooth_present` | extent_positive |
| `a9r_jaw_01_upper` | stage | `natural_tooth_present` | jaw_positive |
| `a9r_jaw_03_both` | extent | `full_arch` | jaw_positive |
| `a9r_typo_01_chelyust` | jaw | `both` | robustness |
| `a9r_typo_02_odin_zub_colloquial` | stage | `natural_tooth_present` | robustness |

## Negative/ambiguous material false positives

**None** — All-on-4 info/price and ambiguous cases passed material gates.

## Diagnostic `reported_context`

None observed. Per owner ruling: diagnostic-only; not authority candidate for A9R3/product.

## Transport errors

None (all 17 calls `ok`).

## A9R2 comparison highlights

| Metric | A9R2 (v2) | A9R2b (v3) |
|--------|-----------|------------|
| neg/amb material FP | 3 | **0** |
| All-on-4 price | extent+stage FP | **pass** |
| transport errors | 2 (scorer partial) | **0** |
| composite exact | 0.714 (corrected) | **0.917** |
| correction turn2 | partial→fixed by scorer | **ok** |

## Immutable artifacts (SHA256)

| File | SHA256 |
|------|--------|
| `a9r2b_patient_scope_live_raw.json` | `19cad2154c9fb654cc29e7cf337ede05ee361bd266aa7509f7687b4137c876a0` |
| `a9r2b_patient_scope_live_result.json` | `9a91a66d3a23b0beb2f6936ebe9d44e431a98ee3cb09a6e3b7960e2271fd83ba` |
| `a9r2b_patient_scope_live_attempt.json` | `5616d6a4a10a9b7945c9a63a1dbb6014d7759a48cf91faa974f990f2e778baec` |
| `a9r2b_patient_scope_live_call_ledger.jsonl` | `6a69c518b6dd5b0311616c3ac22b6d0a839c4e7853c486bd1df18fd0387efddb` |

## Owner conclusion

Single A9R2b live attempt complete. Prompt calibration + v3 label fix cleared **all negative/ambiguous material gates** (including All-on-4). Remaining failure: extra material axes on positive/robustness turns + missed `one_tooth` extent on stage_02. **No A9R3 / no product wiring.** **Do not rerun** without new owner approval.
