# S50 Live Re-eval v2 Incident Audit

**Captured:** 2026-07-22 · **Baseline commit:** `848a7d7` · **Status:** incident captured, **S50 not passed**

Machine-readable pins: [`evals/v5/artifacts/s50_live_reeval_v2_incident_manifest.json`](../evals/v5/artifacts/s50_live_reeval_v2_incident_manifest.json)

Human audit patch: [`evals/v5/artifacts/s50_live_harness_dirty_audit.patch`](../evals/v5/artifacts/s50_live_harness_dirty_audit.patch)

---

## Summary

Owner approved **one** S50 v2 live run (max **38** LLM calls, `qwen3.7-plus`). Two attempts occurred:

| Attempt | Calls | Outcome |
|---------|-------|---------|
| **Attempt 1** | 1 Composer + 1 Verifier = **2** | **Abort** — `AttributeError: '_ComposerAuditProxy' object has no attribute 'captures'` at `run_case` |
| **Attempt 2** | 19×2 = **38** | Artifacts written; **AUTOMATED_FAIL** / **FINAL FAIL** |
| **Total (log)** | **40** | Overrun +2 = **incident cost** (not precedent) |

Run-2 frozen artifacts (`raw` / `result` / original `manifest` / `attempt marker`) are **immutable** and record **38 calls only**. The **log** is the authoritative **40-call** ledger.

---

## SHA-256 pins (full)

| Artifact | Path | SHA-256 |
|----------|------|---------|
| Run 2 raw | `evals/v5/artifacts/fullcontext_response_eval_v2_live_raw.json` | `c78403a8a1a82f472d3665f4893db3fb3fa794a9db254e91611448081be7536c` |
| Run 2 result | `evals/v5/artifacts/fullcontext_response_eval_v2_live_result.json` | `273fb2dd7228bd31bb6f981399a77fcdb59336e07e99ba1ccd14005096bc39aa` |
| Original manifest | `evals/v5/artifacts/s49_fullcontext_response_eval_v2_manifest.json` | `8f61aa9097859337f31fbacf1ebf5d45ce3bee68d3f57955a99aa7a128567b8e` |
| Attempt marker | `evals/v5/artifacts/fullcontext_response_eval_v2_live_attempt.json` | `2d02c1c971e617f4583c86d27360b380d98736c6bbe00b268c8e68a2ace8c64c` |
| Full log | `evals/v5/artifacts/s50_live_run_log.txt` | `76be057b272deffff3275ccd38a33c6e492f86d5b34c369d9e86626e3011cab2` |
| Dirty harness (pre-restore) | `evals/v5/run_fullcontext_response_eval.py` | `5e2b12a3bb33f967012a0bc5e355b11549a51b5247702e72bc1c5700ae54c039` |
| Committed harness @ 848a7d7 | `evals/v5/run_fullcontext_response_eval.py` | `871c8467c1c7cfb51bbee2a576b644cd570a7832e5fd516114fca2229d7cb739` |
| Audit patch | `evals/v5/artifacts/s50_live_harness_dirty_audit.patch` | `2322e3fa2b7dac988f200c93406efa13ee1e3be482a1179d77f7a84fac1ee397` |
| Matrix v2 (git blob) | `evals/v5/demo/fullcontext_response_eval_matrix_v2.json` | `615714c519a92a75e23c2f15bbaa01a0f88a4d95` |

---

## Live verdicts (attempt 2 only)

- **AUTOMATED:** `AUTOMATED_FAIL` — outcome 19/20 (95%), pipeline errors 1
- **FINAL:** `FAIL` (`automated_fail`) — no manual review gate reached
- **Provider budget in result artifact:** 38 calls (attempt 2 only)
- **Diagnostic-only ruling:** run-2 artifacts are **not** S50 pass proof

---

## Owner decisions (binding)

1. **40 calls** recorded as incident cost; not retroactive approval; not precedent.
2. **Run-2 artifacts** = diagnostic evidence only.
3. **Original marker/manifest/result** with `38` = historical but incomplete; do not edit.
4. **Log** = authoritative full call ledger.
5. **Rerun forbidden** without new owner approval.
6. **No formal manual review** in this checkpoint.
7. **Runtime / UI / A9 / authority** untouched.

---

## Attempt 1 abort

After first composer+verifier calls, harness crashed:

```
AttributeError: '_ComposerAuditProxy' object has no attribute 'captures'
```

`run_case` reads `composer_backend.captures`; audit proxy did not delegate attributes to wrapped backend.

---

## Dirty harness hotfixes (successful attempt 2 only)

Captured in [`s50_live_harness_dirty_audit.patch`](../evals/v5/artifacts/s50_live_harness_dirty_audit.patch):

| Hotfix | Change | Rationale | Risk |
|--------|--------|-----------|------|
| 1 | `__getattr__` on `_ComposerAuditProxy` / `_SemanticAuditProxy` | Delegate `captures` to backend | Low with tests (Checkpoint B) |
| 2 | `artifact_paths=None` in live `run_harness_with_backend_factory` | Marker created in `prepare_v2_live_run`; re-preflight failed on marker path | **High** — bypasses `assert_live_artifacts_absent`; needs targeted fix in Checkpoint B |

Successful attempt 2 ran on **dirty working tree** (`5e2b12a3…`), not committed baseline (`871c8467…`).

Harness restored to `848a7d7` after patch capture (see incident manifest).

---

## Problem cases (corrected taxonomy)

### fc_missing_02 — Composer fault; Verifier correct reject

- Composer: external classification («Псориаз относится к аутоиммунным…»).
- Verifier: `general_grounding_ok=false`, pipeline error. **Correct reject.**

### fc_missing_01 — Verifier false negative

- Composer: missing-base opening OK, then cross-disease transfer (diabetes facts + «аутoimmun/волчанка» not in FullContext).
- Verifier: all semantic flags pass → **false negative**.
- Verified=true does **not** make answer correct.

### fc_medical_03 — Verifier false negative

- MD lists **беременность** only (`implantation__info__contraindications.md`).
- Composer adds lactation, hormonal healing rationale — **not in clinic MD**.
- Verifier: all semantic pass → **false negative**; S47-class problem persists.

### Positive observations

- **fc_medical_01:** acceptable grounded answer; S48b calibration worked.
- **fc_boundary_02:** matrix v2 fixture fix worked; no patient diagnosis.

---

## Next milestones

| Checkpoint | Status |
|------------|--------|
| **A — incident capture** | this document |
| **B — harness correction** | blocked until separate governance; NO LIVE |
| **Verifier FN offline fix** | blocked until owner decision on `fc_missing_01` / `fc_medical_03` |
| **Repeat live** | forbidden until new owner approval |
