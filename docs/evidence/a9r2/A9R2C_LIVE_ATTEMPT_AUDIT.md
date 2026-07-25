# A9R2c planner-only live attempt audit

**Date:** 2026-07-25  
**Baseline:** `dae92a4` (live GO) · manifest `git_head` at run time  
**Matrix v3 blob:** `8ccd9bdc140a192981fcc48ad7ed0367a40b0a84`  
**Contract model:** `qwen3.7-plus`  
**Planner calls:** 17 / 17 budget · **retry:** 0  
**Authority:** not enabled · **Rerun:** blocked without new owner approval

## Provider model wiring incident

Manifest/attempt marker record `qwen3.7-plus`, but `llm_usage` logs during the run show **`qwen3.6-flash`** for all 17 provider calls. Root cause: `config.TURN_PLANNER_LLM_MODEL` is bound at first `config` import; `configure_live_env()` sets `os.environ` too late if `config` was already imported.

**Impact:** this attempt does **not** validly test `qwen3.7-plus`. Flash-vs-Plus comparison below is **A9R2b Flash (frozen) vs this run (also Flash per logs)**, not Flash vs Plus. Owner decision required before any Plus re-attempt.

## Automated verdict

| Field | Value |
|-------|-------|
| `automated_verdict` | `AUTOMATED_FAIL` |
| `final_verdict` (post manual review) | `FAIL` |
| `positive_axis_recall` | 1.0 (14/14) |
| `true_composite_exact_turn_rate` | 0.647 (11/17) |
| `correction_success_rate` | 1.0 (1/1) |
| `wrong_non_unknown_axis_count` | 0 |
| `material_false_positive_axis_count` | 6 |
| `negative/ambiguous material FP` | **0** |
| `diagnostic reported_context FP` | 0 |
| `transport_provider_error_count` | 0 |
| `malformed_projection_count` | 0 |

### Gates

| Gate | Actual | Pass |
|------|--------|------|
| wrong concrete material axis | 0 | ✅ |
| material false-positive (extent/jaw/stage) | 6 | ❌ |
| positive recall ≥ 0.85 | 1.0 | ✅ |
| correction success | 1.0 | ✅ |
| `true_composite_exact_turn_rate` ≥ 0.85 | 0.647 | ❌ |
| malformed/transport | 0 | ✅ |
| calls ≤ 17 | 17 | ✅ |
| retry = 0 | 0 | ✅ |

### Per-axis material diagnostic

| Axis | Correct | Miss | False positive |
|------|---------|------|----------------|
| extent | 9 | 0 | 1 |
| jaw | 3 | 0 | 2 |
| stage | 2 | 0 | 3 |

## Misses (expected positive → unknown)

**None.**

## Wrong concrete values

**None.**

## Material false positives (extent/jaw/stage)

| Call | Axis | Observed | Category |
|------|------|----------|----------|
| `a9r_extent_01_full_arch_price_question` | jaw | `both` | extent_positive |
| `a9r_extent_03_few_teeth_missing` | stage | `natural_tooth_present` | extent_positive |
| `a9r_jaw_01_upper` | stage | `natural_tooth_present` | jaw_positive |
| `a9r_jaw_03_both` | extent | `full_arch` | jaw_positive |
| `a9r_typo_01_chelyust` | jaw | `both` | robustness |
| `a9r_typo_02_odin_zub_colloquial` | stage | `natural_tooth_present` | robustness |

## Negative/ambiguous material false positives

**None.**

## Diagnostic `reported_context`

None observed. Diagnostic-only; not authority candidate for A9R3/product.

## A9R2b Flash vs this attempt (extent/jaw/stage)

| Call | Axis | A9R2b Flash | This attempt | Delta |
|------|------|-------------|--------------|-------|
| `a9r_extent_01_full_arch_price_question` | extent | `full_arch` ✅ | `full_arch` ✅ | — |
| | jaw | `unknown` ✅ | `both` ❌ FP | **regression** |
| `a9r_stage_02_natural_tooth_present` | extent | `unknown` ❌ miss | `one_tooth` ✅ | **improved** |
| | stage | `natural_tooth_present` ✅ | `natural_tooth_present` ✅ | — |
| All other calls | — | same material axes | same material axes | unchanged |

**Net vs A9R2b (corrected 11/17):** same composite rate (0.647) but different error mix — fixed `stage_02` extent miss, added `extent_01` jaw FP (+1 material FP total: 5→6).

## Transport errors

None (all 17 calls `ok`).

## Immutable artifacts (SHA256)

| File | SHA256 |
|------|--------|
| `a9r2c_patient_scope_live_raw.json` | `b476dd2aab06af6be2dcfbfacabed88c1ab9a1d42dd06f8bed0c742d5345d5c5` |
| `a9r2c_patient_scope_live_result.json` | `f5ddf7945c4c04d7d64496143c022601f82689b0bfe36e9c0e34567b66f28707` |
| `a9r2c_patient_scope_live_attempt.json` | `8027190e23d060d4ce01dafdc6b42e34a9f956c47ad05860598bfaa28f8882b0` |
| `a9r2c_patient_scope_live_call_ledger.jsonl` | `9c174dc3650503e3429f934570057268d066d54c84cb26f9693c618f9a8c72e2` |
| `a9r2c_patient_scope_live_manual_review.json` | `eb00f8832345849c912e4f4d42490122bd677dca87c07c6b92b25ca30723d907` |

Frozen A9/A9R/A9R2/A9R2b/W1b/S-series artifacts verified byte-identical post-live.

## Owner conclusion

Single A9R2c live attempt consumed. **AUTOMATED_FAIL** → **FAIL** after manual review (17/17 turns). Model wiring incident invalidates Plus hypothesis; gates not met (`material FP=6`, `true_composite=0.647`). **No A9R3 / no product wiring.** **Do not rerun** without new owner approval and model-pin fix.
