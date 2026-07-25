# A9R2 post-live scorer correction audit (Checkpoint A)

**Date:** 2026-07-25  
**Baseline:** `2b8bd23` (A9R2 live complete)  
**Scope:** read-only diagnostic recompute on frozen live raw · **NO LIVE / NO LLM**

## Official live verdict (immutable)

| Field | Value |
|-------|-------|
| `automated_verdict` (frozen `a9r2_patient_scope_live_result.json`) | `AUTOMATED_FAIL` |
| `final_verdict` (manual review complete) | `FAIL` in audit authority; frozen artifact remains `PENDING_MANUAL_REVIEW` |
| Status | `A9R2_NOT_PASSED` |
| Retroactive PASS | **not granted** |

Frozen live artifacts are byte-identical (SHA256 pins in `evals/v5/a9r2_patient_scope_live_contract.py`).

## Scorer correction

**Bug:** `planner_status=partial` was treated as `transport_provider_error` whenever any unrelated TurnFrame meta was invalid/missing (e.g. `topic` missing, unrelated `aspects`).

**Fix:** Transport error only when `degraded`/`not_available`, missing frame, or `patient_scope` axes are not strict-valid. Scope scoring is isolated from unrelated TurnFrame axes.

## Corrected metrics (diagnostic recompute on frozen raw)

Source: `evals/v5/artifacts/a9r2_patient_scope_live_diagnostic_recompute.json`

| Metric | Official (frozen result) | Corrected (diagnostic) |
|--------|--------------------------|-------------------------|
| `transport_provider_error_count` | 2 | **0** |
| `correction_success_rate` | n/a (turn2 transport) | **1.0** (1/1) |
| `composite_exact_turn_rate` | 0.462 (6/13) | **0.714** (10/14) |
| `false_positive_axis_count` (all) | 8 | 8 |
| `false_positive` on negative/ambiguous | 3 axes / 2 cases | 3 axes / 2 cases (unchanged) |
| `wrong_non_unknown_axis_count` | 0 | 0 |
| `positive_axis_recall` | 1.0 | 1.0 |
| `diagnostic_automated_verdict` | — | `AUTOMATED_FAIL` |

### Cases fixed by scorer correction

| Call | Before | After |
|------|--------|-------|
| `a9r_correction_01:turn2` | transport error | exact `one_tooth`, correction success |
| `a9r_ambiguous_01_contradictory_extent` | transport error | exact all-unknown |

## Remaining false positives (planner, not scorer)

### Negative/ambiguous (gate-critical)

| Call | Axis | Observed |
|------|------|----------|
| `a9r_negative_02_all_on_4_price` | extent | `full_arch` |
| `a9r_negative_02_all_on_4_price` | stage | `implant_placed` |
| `a9r_ambiguous_02_vague_several` | stage | `extraction_context` |

### Positive/robustness (extra axes)

| Call | Axis | Observed |
|------|------|----------|
| `a9r_extent_03_few_teeth_missing` | stage | `natural_tooth_present` |
| `a9r_jaw_01_upper` | stage | `extraction_context` |
| `a9r_jaw_03_both` | extent | `full_arch` |
| `a9r_stage_02_natural_tooth_present` | extent | `one_tooth` |
| `a9r_typo_02_odin_zub_colloquial` | stage | `natural_tooth_present` |

## Checkpoint B (planner prompt calibration)

Semantic `_PATIENT_SCOPE_PROMPT` rules added in `core/turn_planner_llm.py` (same single LLM call). Offline blast-radius fixtures in `tests/test_a9r2_planner_prompt_calibration_offline.py`. **No live rerun in this checkpoint.**

## Owner conclusion

- Scorer/audit correction complete; official `AUTOMATED_FAIL` unchanged.
- Manual review complete; automated fail → final FAIL in audit authority, not product authority.
- Diagnostic recompute confirms transport miscount only; planner false positives remain → `A9R2_NOT_PASSED`.
- **STOP before A9R2b pre-live checkpoint.**
