# A9R2b independent label review (A9R matrix v2)

**Date:** 2026-07-25  
**Reviewer:** implementation agent (independent of A9R2 live model output)  
**Baseline:** `74e6820`  
**Method:** semantic patient-fact analysis per checkpoint B rules; no fitting to qwen3.6-flash outputs

## Principles applied

- `patient_scope` = facts **directly stated** about the patient's situation
- Service/protocol names (All-on-4) ≠ patient facts
- `jaw` alone ≠ `extent` unless explicit scale language («вся», «нет зубов», …)
- `natural_tooth_present` only when preservation/explicit presence stated
- `implant_placed` only when patient says implant already installed
- Broken/missing tooth ≠ preserved natural tooth

## Live-case review (16 cases / 17 calls)

| Case | Question (summary) | v2 label | Verdict | v3 action |
|------|-------------------|----------|---------|-----------|
| `a9r_extent_01` | имплантация всей челюсти | extent=full_arch | ✅ Correct | none |
| `a9r_extent_02` | восстановить один зуб | extent=one_tooth | ✅ Correct | none |
| `a9r_extent_03` | нет нескольких зубов | extent=few_teeth | ✅ Correct | none |
| `a9r_jaw_01` | нет зубов на верхней челюсти | extent=full_arch, jaw=upper | ✅ Correct | none — «нет зубов» is explicit toothlessness scale |
| `a9r_jaw_02` | восстановление на нижней челюсти | jaw=lower, extent=unknown | ✅ Correct | none — jaw only, no scale |
| `a9r_jaw_03` | восстановить обе челюсти | jaw=both, extent=unknown | ✅ Correct | none — both jaws ≠ per-jaw tooth count |
| `a9r_stage_01` | имплант уже установлен | stage=implant_placed | ✅ Correct | none |
| `a9r_stage_02` | свой зуб ещё сохранился… коронка? | stage=natural_tooth_present, extent=unknown | ❌ **Label gap** | **extent→one_tooth** — «свой зуб» is explicit singular-tooth fact |
| `a9r_correction_01` | full_arch then one_tooth correction | two-turn correction | ✅ Correct | none |
| `a9r_typo_01` | чилюсти (typo full arch) | extent=full_arch | ✅ Correct | none |
| `a9r_typo_02` | один зубик сломался | extent=one_tooth, stage=unknown | ✅ Correct | none — broken ≠ preserved; natural_tooth_present must NOT be expected |
| `a9r_negative_01` | что такое All-on-4 | all unknown | ✅ Correct | none |
| `a9r_negative_02` | сколько стоит All-on-4 | all unknown | ✅ Correct | none |
| `a9r_negative_03` | расскажите про имплант | all unknown | ✅ Correct | none |
| `a9r_ambiguous_01` | один зуб или вся челюсть | all unknown | ✅ Correct | none |
| `a9r_ambiguous_02` | зубов не хватает | all unknown | ✅ Correct | none |

## v2 → v3 delta (single change)

**Case:** `a9r_stage_02_natural_tooth_present`

```diff
  "expected_effective_scope": {
-   "extent": "unknown",
+   "extent": "one_tooth",
    "jaw": "unknown",
    "stage": "natural_tooth_present",
    "modifiers": []
  }
```

**Rationale update:** explicit singular natural tooth («свой зуб») states `one_tooth` extent in addition to `natural_tooth_present` stage for AC2.

All other 21 matrix cases: deep-equal to v2 (modulo schema metadata, `phase` rename `a9r2_live`→`a9r2b_live` for live cases, and `immutable_prior_artifacts`).

## Cases explicitly NOT relabeled

| Observation | Decision |
|-------------|----------|
| A9R2 live model output `extent=one_tooth` on stage_02 | Was scorer FP under v2; becomes correct under v3 — **not** the reason for the fix |
| A9R2 live `natural_tooth_present` on typo_02 | Remains FP under v3 (label stays stage=unknown) |
| jaw_01 full_arch | Justified by «нет зубов», not jaw axis alone |
| All-on-4 price/info | Service name; patient scope stays unknown |

## Matrix versioning

- v2 frozen (blob `6a9cc6f7…`) — **do not edit**
- v3 new file `patient_scope_a9r_matrix_v3.json` — only independently justified delta above
