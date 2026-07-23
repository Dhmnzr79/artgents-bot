# TASK — S51 Correction (stale neighbor + ARCH sync)

**Baseline:** `codex/stage-a` / `3479f78` · **NO LIVE** · **NO LLM**

**Goal:** Close two confirmed post-S51 gaps without changing product Verifier behavior:
(1) migrate stale demo neighbor test off removed five-boolean contract;
(2) sync canonical ARCH with active issue-based semantic Verifier.

## Confirmed problems

1. `tests/test_demo_target_turn_frame_bound_response.py` — `ImportError`:
   `TargetSemanticVerification` removed from active product in S51 (`a2596f9`).
2. `docs/ARCH_TARGET_DESIGN.md` — S45 paragraph still names
   `TargetSemanticVerification` / `general_grounding_ok` / `strict_commercial_grounding_ok`
   as active contract without S51 replacement.

## Allowlist

- `TASK.md`
- `tests/test_demo_target_turn_frame_bound_response.py`
- `docs/ARCH_TARGET_DESIGN.md`
- `docs/STRANGLER_ROADMAP.md` (correction status only, if needed)

## Protected (must not change)

- Product Verifier code (`core/target_response_verifier.py` and neighbors)
- S47/S50 matrices and frozen live artifacts
- runtime/UI/A9/authority
- Composer / FullContext / FINAL_FULLCONTEXT_ONLY semantics

## Test file requirements

- Replace `TargetSemanticVerification` import and fake backend with
  `TargetSemanticAssessment` / `TargetSemanticIssue`.
- Happy path: `TargetSemanticAssessment()` (empty issues).
- Any rejection path: real blocking `TargetSemanticIssue` with `offending_span` from
  candidate text.
- Do not weaken assertions, delete tests, or add skip/xfail.
- Do not change product code for test convenience.

## ARCH requirements

Document explicitly (canonical, current):

- S51 **replaced** active five-boolean semantic contract;
- active semantic output = `issues[]` with `kind` + `offending_span`;
- blocking kinds: `unsupported_clinic_claim`, `personal_medical_conclusion`,
  `material_external_medical_claim`;
- `minor_external_detail` non-blocking;
- verdict derived by code; no model pass boolean;
- deterministic numeric/strict-fact layer preserved;
- old five-boolean fields **historical only** (frozen S47/S50 replay);
- FullContext, structured authority, FINAL_FULLCONTEXT_ONLY unchanged.

Update S38/S45 paragraphs that still imply five-boolean as active.

## Required tests (offline only)

```powershell
$bt = Join-Path $env:TEMP ("pytest-s51-correction-" + [guid]::NewGuid().ToString("n"))
.\.venv\codex312\Scripts\python.exe -m pytest `
  tests/test_demo_target_turn_frame_bound_response.py `
  tests/test_target_policy_bound_verified_response_pipeline.py `
  tests/test_target_verified_response_pipeline.py `
  tests/test_target_response_verifier.py `
  tests/test_target_fullcontext_content_response.py `
  tests/test_target_boundary_enforced_fullcontext_response.py `
  -p no:cacheprovider --basetemp=$bt -q
```

## Completion deliverables

- `rg` audit of residual five-boolean names; classify each as
  historical/docs/TASK or eliminated;
- confirm previously broken test file collects and passes;
- frozen artifact pins unchanged;
- NO LIVE / NO LLM.

## Process

1. Governance commit → PRE-CODE checker ✅
2. Correction (allowlist only)
3. Targeted pytest
4. COMPLETION checker ✅
5. Completion commit + push `codex/stage-a` → STOP

## Acceptance

1. `test_demo_target_turn_frame_bound_response.py` imports and passes.
2. ARCH unambiguously describes issue-based active Verifier (S51).
3. No product Verifier behavior change.
4. All required tests green; frozen S47/S50 untouched.
