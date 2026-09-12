# A9R2b post-live composite metric correction audit (Checkpoint A)

**Date:** 2026-07-25  
**Baseline:** `5cd5015` (A9R2b live complete)  
**Scope:** read-only diagnostic recompute on frozen A9R2b live raw · **NO LIVE / NO LLM**

## Official live verdict (immutable)

| Field | Value |
|-------|-------|
| `automated_verdict` (frozen `a9r2b_patient_scope_live_result.json`) | `AUTOMATED_FAIL` |
| `final_verdict` (manual review complete) | `FAIL` |
| Status | `A9R2B_NOT_PASSED` |
| Retroactive PASS | **not granted** |

Frozen A9R2/A9R2b live artifacts remain byte-identical (SHA256 pins in `evals/v5/a9r2b_patient_scope_live_contract.py`).

## Scorer correction

**Bug:** `composite_exact_turn_rate` numerator and denominator had mismatched eligibility. The denominator excluded five non-transport turns where all material axes were correctly `unknown` (exact all-unknown negative/ambiguous cases). Those turns were scored as exact in the numerator but omitted from the denominator, inflating the rate from **0.647** to **0.917** (11/12).

**Fix:** `composite_eligible_turns` = all non-transport turns (17). Numerator and denominator now share the same eligibility. `true_composite_exact_turn_rate` is the authority metric for future gates (A9R2c).

## Corrected metrics (diagnostic recompute on frozen raw)

Source: `evals/v5/artifacts/a9r2b_patient_scope_live_diagnostic_recompute.json`

| Metric | Official (frozen result) | Corrected (diagnostic) |
|--------|--------------------------|-------------------------|
| `composite_exact_turn_rate` | **0.917** (11/12) | **0.647** (11/17) |
| `composite_eligible_turns` | 12 (inflated) | **17** |
| `transport_provider_error_count` | 0 | 0 |
| `correction_success_rate` | 1.0 | 1.0 |
| `positive_axis_recall` | 0.929 | 0.929 |
| `wrong_non_unknown_axis_count` | 0 | 0 |
| `material_false_positive_axis_count` | 5 | 5 |
| `negative/ambiguous material FP` | 0 | 0 |
| `diagnostic_automated_verdict` | — | `AUTOMATED_FAIL` |

### Per-axis material diagnostic (corrected)

| Axis | Correct | Miss | False positive |
|------|---------|------|----------------|
| extent | 8 | 1 | 1 |
| jaw | 3 | 0 | 1 |
| stage | 2 | 0 | 3 |

### Exact all-unknown turns restored to denominator (5)

These turns were exact (all material axes `unknown` as expected) but were wrongly excluded from the official composite denominator:

- `a9r_negative_01_all_on_4_info`
- `a9r_negative_02_all_on_4_price`
- `a9r_ambiguous_01_contradictory_extent`
- `a9r_ambiguous_02_vague_several`
- `a9r_robustness_01_empty_turn`

## Remaining planner failures (unchanged by metric fix)

Material false positives and the single extent miss on `a9r_stage_02_natural_tooth_present` are unchanged from `A9R2B_LIVE_ATTEMPT_AUDIT.md`. The metric correction does not alter planner behavior or gate outcomes beyond composite rate reporting.

## Checkpoint B (A9R2c pre-live)

Isolated `a9r2c_*` harness on the same frozen matrix v3 and calibrated prompt. Proposed model: `qwen3.7-plus`. Gates use `true_composite_exact_turn_rate` ≥ 0.85 over all 17 non-transport turns. **No live run in this checkpoint.**

## Owner conclusion

- Composite denominator inflation corrected; official `AUTOMATED_FAIL` / `FAIL` unchanged.
- Corrected true composite: **11/17 = 0.647**.
- Regression test `tests/test_a9r2b_metric_correction_offline.py` guards against re-inflation.
- **STOP before A9R2c live.**
