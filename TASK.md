# TASK — S50 Live Re-eval v2 Incident Audit Capture (Checkpoint A)

**Baseline:** `codex/stage-a` / `848a7d7` · **NO LIVE** · **NO LLM** · **NO harness fix** · **NO manual review**

**Goal:** Append-only governance capture of S50 live incident: 40-call overrun,
diagnostic-only run-2 artifacts, corrected taxonomy, dirty harness provenance,
restore `run_fullcontext_response_eval.py` to committed `848a7d7` state.

## Owner decisions (binding)

1. **Actual cost:** 40 provider calls — attempt 1: 2 + abort; attempt 2: 38.
2. **40 calls** = incident cost, **not** authorized precedent.
3. **Run-2 artifacts** = diagnostic evidence only; **not** S50 pass.
4. **Original marker/manifest/result** (`total_llm_calls: 38`) = historical but
   **incomplete** accounting; **do not edit**; incident manifest explains gap.
5. **Log** = authoritative full call ledger (40 `llm_usage` events).
6. **Rerun forbidden** without new owner approval.
7. **fc_missing_01**, **fc_medical_03** = confirmed Verifier false negatives.
8. **No formal manual review** artifact in this checkpoint.

## Allowlist

- `TASK.md`
- `docs/S50_LIVE_REEVAL_V2_INCIDENT_AUDIT.md`
- `docs/STRANGLER_ROADMAP.md` (completion status only)
- `evals/v5/artifacts/fullcontext_response_eval_v2_live_raw.json` (add frozen; immutable)
- `evals/v5/artifacts/fullcontext_response_eval_v2_live_result.json` (add frozen; immutable)
- `evals/v5/artifacts/s49_fullcontext_response_eval_v2_manifest.json` (add frozen; immutable)
- `evals/v5/artifacts/fullcontext_response_eval_v2_live_attempt.json` (add frozen; immutable)
- `evals/v5/artifacts/s50_live_run_log.txt` (add frozen; immutable)
- `evals/v5/artifacts/s50_live_reeval_v2_incident_manifest.json` (new append-only)
- `evals/v5/artifacts/s50_live_harness_dirty_audit.patch` (new exact dirty diff)
- `evals/v5/run_fullcontext_response_eval.py` (**restore-only** to `848a7d7`; completion commit **zero diff**)

## Forbidden

- live / LLM / provider calls
- edit bytes of run-2 raw/result/original manifest/attempt marker/log
- harness implementation (Checkpoint B)
- manual review JSON
- product Composer/Verifier/runtime/UI/A9/authority changes
- `git checkout` / `git reset` for harness restore (use apply_patch only)
- Checkpoint B start
- pytest unless required for manifest schema (prefer none)

## SHA-256 pins (pre-capture, full)

| Object | SHA-256 |
|--------|---------|
| raw | `c78403a8a1a82f472d3665f4893db3fb3fa794a9db254e91611448081be7536c` |
| result | `273fb2dd7228bd31bb6f981399a77fcdb59336e07e99ba1ccd14005096bc39aa` |
| original manifest | `8f61aa9097859337f31fbacf1ebf5d45ce3bee68d3f57955a99aa7a128567b8e` |
| attempt marker | `2d02c1c971e617f4583c86d27360b380d98736c6bbe00b268c8e68a2ace8c64c` |
| log | `76be057b272deffff3275ccd38a33c6e492f86d5b34c369d9e86626e3011cab2` |
| dirty harness (pre-restore) | `5e2b12a3bb33f967012a0bc5e355b11549a51b5247702e72bc1c5700ae54c039` |
| committed harness @ 848a7d7 | `871c8467c1c7cfb51bbee2a576b644cd570a7832e5fd516114fca2229d7cb739` |
| matrix v2 (git blob) | `615714c519a92a75e23c2f15bbaa01a0f88a4d95` |

## Incident manifest required fields

- `baseline_commit`: `848a7d7`
- `matrix_v2_git_blob_hash`: `615714c519a92a75e23c2f15bbaa01a0f88a4d95`
- `attempt_1_calls`: 2 (composer + verifier) + abort (`AttributeError: captures`)
- `attempt_2_calls`: 38
- `actual_total_provider_calls`: 40
- `log_authoritative_call_ledger`: `s50_live_run_log.txt` (40× `llm_usage`)
- `incomplete_historical_artifacts`: original manifest/marker/result record 38 only
- All full SHA-256 pins (six evidence objects + patch + committed harness)
- `automated_verdict`: `AUTOMATED_FAIL`
- `diagnostic_only_ruling`: run-2 artifacts not S50 pass
- `problem_cases_taxonomy`:
  - `fc_missing_02`: Composer external knowledge; Verifier **correct reject**
  - `fc_missing_01`: Verifier **false negative**; cross-disease transfer
  - `fc_medical_03`: Verifier **false negative**; ungrounded lactation/hormones/healing
- `rerun_forbidden`: true
- `runtime_ui_a9_authority_untouched`: true

## Audit doc (`docs/S50_LIVE_REEVAL_V2_INCIDENT_AUDIT.md`) must cover

- Attempt 1 abort root cause (`_ComposerAuditProxy` missing `captures`)
- Dirty hotfix 1: `__getattr__` delegation rationale
- Dirty hotfix 2: `artifact_paths=None` rationale and **risk** (bypasses absent-check)
- Successful run-2 executed on dirty tree, not committed `848a7d7`
- Link to patch file and incident manifest

## Harness restore procedure

1. Save exact dirty diff to `s50_live_harness_dirty_audit.patch`.
2. Pin patch file SHA-256 in incident manifest.
3. Restore `evals/v5/run_fullcontext_response_eval.py` via apply_patch (reverse diff).
4. Verify restored SHA-256 == `871c8467…`.
5. Completion commit must have **no diff** on harness file.

## Process

1. Governance TASK commit → PRE-CODE checker ✅
2. Capture docs/manifest/patch/artifacts + harness restore
3. Verify live artifact SHA-256 unchanged
4. COMPLETION checker ✅
5. Completion commit → push `codex/stage-a` → stop

## Acceptance

1. Incident manifest documents 40 calls, log authority, incomplete marker/manifest/result.
2. All six evidence SHA-256 + patch SHA pinned.
3. Harness restored to `871c8467…`; no harness diff in completion commit.
4. Run-2 artifacts byte-identical to pre-capture pins.
5. AUTOMATED_FAIL + diagnostic-only ruling documented.
6. Three problem cases taxonomy captured.
7. Checkpoint B **not** started.
