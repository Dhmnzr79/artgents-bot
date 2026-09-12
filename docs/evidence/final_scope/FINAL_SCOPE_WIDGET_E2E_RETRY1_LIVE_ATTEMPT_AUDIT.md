# FINAL_SCOPE_WIDGET_E2E_RETRY1 live attempt audit

**Date:** 2026-07-26  
**Baseline:** `0b10b00`  
**Matrix blob:** `f4eecf7532481a288d1db6a6ee107dd147117dae44afc991451836dd3589434f`  
**Owner GO:** one RETRY1 live attempt · owner override **forbidden**

---

## Verdict

| Field | Value |
|-------|-------|
| **Status** | `LIVE_ABORT_MID_RUN` |
| **Automated verdict** | `AUTOMATED_FAIL` |
| **Final verdict** | **FAIL** |
| **Valid live attempt** | **PARTIAL** — 5/8 HTTP turns, aborted before turn 6 HTTP |
| **Rerun** | **BLOCKED** |

---

## Preflight (passed)

| Check | Result |
|-------|-------|
| HEAD | `0b10b00b6e5a32d0caaf7c9396bba77c042e1f49` |
| Working tree | clean/synced |
| Matrix hash | `f4eecf75…` ✅ |
| Retry1 artifacts before run | absent ✅ |
| Preflight-abort attempt #1 | unchanged ✅ |
| Attempt marker | created after seam validation ✅ |

---

## Abort

**Command:** `python evals/v5/run_final_scope_widget_e2e_retry1_live.py --live`  
**Exit code:** 5  
**Error:** `HarnessConfigError: missing scope ref from_turn=5 extent=one_tooth`

**Root cause:** Turn 5 returned `target_fullcontext_terminal_clarify` instead of broad prosthetics materialized with 3 scope-nav buttons. Harness could not resolve turn 6 UI scope ref from turn 5 `quick_replies`.

**Secondary product failures (turns 1–5):**

| Turn | Expected | Observed route | Gate |
|------|----------|----------------|------|
| 2 | materialized scoped full_arch | `target_fullcontext_terminal_medical_handoff_nonmaterializable` | FAIL |
| 5 | broad + 3 scope buttons | `target_fullcontext_terminal_clarify` | FAIL |

Turns 1, 3, 4 materialized on target path. Turns 6–8 not reached.

---

## Provider calls (ledger)

| Role | Calls |
|------|-------|
| ingress | 4 |
| planner | 5 |
| medical_boundary | 5 |
| composer | 3 |
| semantic_verifier | 3 |
| **Total started** | **20** / 40 budget |

**Planner models observed:** all `qwen3.7-plus` (5/5) ✅  
**Retries:** 0 ✅  
**Legacy hits:** 0 ✅  
**Ledger:** balanced ✅, incomplete (abort mid-turn-5 pipeline)

---

## Artifacts (immutable)

| Artifact | Status |
|----------|--------|
| `final_scope_widget_e2e_retry1_attempt.json` | ✅ `attempt_aborted_mid_run` |
| `final_scope_widget_e2e_retry1_call_ledger.jsonl` | ✅ 20 call pairs |
| `final_scope_widget_e2e_retry1_raw.json` | ✅ |
| `final_scope_widget_e2e_retry1_result.json` | ✅ |
| `final_scope_widget_e2e_retry1_manifest.json` | ✅ |
| `final_scope_widget_e2e_retry1_manual_review.json` | ✅ |
| `final_scope_widget_e2e_retry1_audit.log` | ✅ |
| `final_scope_widget_e2e_retry1_live_stdout.log` | ✅ |

**Note:** Turn 1/3 full answer text not in `turn_complete` events — Windows `UnicodeEncodeError` on `₽` during logging (`logging_setup.py`). Route/char counts captured via `bot_reply_completed`.

---

## Frozen neighbors

| Suite | Pin check |
|-------|-----------|
| Preflight-abort attempt #1 + audit | ✅ unchanged |
| S62 / S63 | ✅ |

---

## STOP

- **No rerun** without new owner GO.
- **No harness/product fix** in this cycle.
- **No post-E2E closeout** (flag removal blocked).
- **A9_PATIENT_SCOPE_AUTHORITY** remains until owner review after PASS.
