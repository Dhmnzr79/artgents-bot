# A9R2 planner-only live attempt audit

**Date:** 2026-07-25  
**Baseline:** `6b75214` (pre-live) + live delegate unlock (uncommitted at run)  
**Matrix v2 blob:** `6a9cc6f7a964d0ab3ead79e5dd2cf0a64d743f57`  
**Model:** `qwen3.6-flash` via `TURN_PLANNER_LLM_MODEL`  
**Planner calls:** 17 / 17 budget · **retry:** 0  
**Authority:** not enabled · **Rerun:** blocked without new owner approval

## Automated verdict

| Field | Value |
|-------|-------|
| `automated_verdict` | `AUTOMATED_FAIL` |
| `final_verdict` (post manual review) | `PENDING_MANUAL_REVIEW` |
| `positive_axis_recall` | 1.0 (12/12) |
| `composite_exact_turn_rate` | 0.462 (6/13 scored turns) |
| `wrong_non_unknown_axis_count` | 0 |
| `false_positive_axis_count` (all) | 8 |
| `false_positive` on negative/ambiguous only | 3 axes on 2 cases |
| `transport_provider_error_count` | 2 (`partial` planner status) |
| `malformed_projection_count` | 0 |

### Gates

| Gate | Actual | Pass |
|------|--------|------|
| wrong non-unknown | 0 | ✅ |
| false-positive (negative/ambiguous) | 3* | ❌ |
| correction success | n/a (turn2 transport error) | ❌ |
| positive recall ≥ 0.85 | 1.0 | ✅ |
| composite exact ≥ 0.85 | 0.462 | ❌ |
| malformed | 0 | ✅ |
| transport errors | 2 | ❌ |
| calls ≤ 17 | 17 | ✅ |
| retry = 0 | 0 | ✅ |

\*Harness totals count 8 FP axes globally; on negative/ambiguous cases only: `a9r_negative_02_all_on_4_price` (extent+stage), `a9r_ambiguous_02_vague_several` (stage).

## Misses (expected positive → unknown)

None.

## Wrong concrete values (expected X → wrong non-unknown)

None.

## False positives (observed non-unknown where expected unknown)

### On negative/ambiguous cases (critical for gates)

| Call | Axis | Observed |
|------|------|----------|
| `a9r_negative_02_all_on_4_price` | extent | `full_arch` |
| `a9r_negative_02_all_on_4_price` | stage | `implant_placed` |
| `a9r_ambiguous_02_vague_several` | stage | `extraction_context` |

### On positive/robustness cases (extra axes; not gate-scoped but material)

| Call | Axis | Observed |
|------|------|----------|
| `a9r_extent_03_few_teeth_missing` | stage | `natural_tooth_present` |
| `a9r_jaw_01_upper` | stage | `extraction_context` |
| `a9r_jaw_03_both` | extent | `full_arch` |
| `a9r_stage_02_natural_tooth_present` | extent | `one_tooth` |
| `a9r_typo_02_odin_zub_colloquial` | stage | `natural_tooth_present` |

## Transport / partial planner failures

| Call | Status | Note |
|------|--------|------|
| `a9r_correction_01:turn2` | `partial` | Correction «Нет, речь об одном зубе» — not scored |
| `a9r_ambiguous_01_contradictory_extent` | `partial` | Contradictory extent — not scored |

## Typo robustness

`a9r_typo_01_chelyust` with «…всей **чилюсти**?» → `full_arch` ✅ (distinct from extent_01 orthography).

## Artifacts (immutable)

- `evals/v5/artifacts/a9r2_patient_scope_live_raw.json`
- `evals/v5/artifacts/a9r2_patient_scope_live_result.json`
- `evals/v5/artifacts/a9r2_patient_scope_live_manifest.json`
- `evals/v5/artifacts/a9r2_patient_scope_live_attempt.json`
- `evals/v5/artifacts/a9r2_patient_scope_live_call_ledger.jsonl`
- `evals/v5/artifacts/a9r2_patient_scope_live_manual_review.json`

## Owner conclusion

Single live attempt complete. **No A9R3 / no product wiring.** Planner extracts positive extent/jaw/stage well on explicit statements, but over-extracts stage/extent on several turns and fails All-on-4 price negative gate. Correction turn2 returned `partial`. **Do not rerun** without new owner approval.
