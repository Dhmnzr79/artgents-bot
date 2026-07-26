# FINAL scope/widget E2E retry3 — seam audit (post-TYPED_UI_TURNFRAME)

**Date:** 2026-07-26  
**Baseline:** `b4b47bc` (TYPED_UI_TURNFRAME COMPLETION ✅)  
**Scope:** pre-live checkpoint only · **NO LIVE / NO LLM / NO PRODUCT CODE**

---

## Verdict

Retry3 is a **new isolated namespace** (`final_scope_widget_e2e_retry3_*`) for the first live attempt after typed UI TurnFrame product fix. Frozen Retry1/Retry2 artifacts remain byte-identical. Same frozen 8-turn matrix (`f4eecf75…`). Offline real-path replay re-proves 8/8 with **tighter provider budget** reflecting planner skip on typed UI clicks T2/T6/T7.

---

## Lineage

| Attempt | Measurement ID | Status |
|---------|----------------|--------|
| preflight-abort #1 | `final_scope_widget_e2e` | frozen |
| retry1 live | `final_scope_widget_e2e_retry1` | official **FAIL** — frozen |
| retry2 live | `final_scope_widget_e2e_retry2` | official **FAIL** — frozen |
| typed UI fix | TYPED_UI_TURNFRAME | COMPLETION ✅ @ `b4b47bc` |
| **retry3 (this)** | `final_scope_widget_e2e_retry3` | pre-live only |

Parent measurement: `final_scope_widget_e2e_retry2`.

---

## Post-typed-UI target chain

```
POST /ask | /ask/stream
  → run_pre_resolver_turn (AC1 UI scope/stage; neutral "продолжить")
  → try_run_typed_ui_planner_turn  ← T2/T6/T7: native TurnFrame, planner skipped
  → run_planner_turn               ← free-text only (5 turns)
  → orchestrate_target_fullcontext_turn
```

---

## Harness preflight order (retry3)

| Step | Action |
|------|--------|
| 1 | `configure_process_env()` — `A9_PATIENT_SCOPE_AUTHORITY=1`, Plus planner before import |
| 2 | Frozen neighbors (preflight-abort, S62/S63, matrix) |
| 3 | **Retry1 + Retry2** live artifacts SHA256 unchanged |
| 4 | **Retry3 artifact paths absent** |
| 5 | `validate_runtime_seams()` |
| 6 | Create `final_scope_widget_e2e_retry3_attempt.json` **only after** step 5 |
| 7 | Retry3 provider audit install (budget caps below) |
| 8 | First HTTP turn / provider call |

---

## Provider budget (retry3 — hard caps)

| Role | Max calls |
|------|-----------|
| ingress | 5 |
| planner | 5 |
| medical_boundary | 8 |
| composer | 8 |
| semantic_verifier | 8 |
| **Total** | **34** |

**Planner expectation:** 5 free-text turns (1,3,4,5,8); **0** on typed UI clicks T2/T6/T7.

---

## Retry3 artifact namespace (pre-live: all absent)

| Artifact | Path |
|----------|------|
| attempt marker | `evals/v5/artifacts/final_scope_widget_e2e_retry3_attempt.json` |
| raw/result | `final_scope_widget_e2e_retry3_{raw,result}.json` |
| manifest | `final_scope_widget_e2e_retry3_manifest.json` |
| ledger | `final_scope_widget_e2e_retry3_call_ledger.jsonl` |
| manual review | `final_scope_widget_e2e_retry3_manual_review.json` |
| audit log | `final_scope_widget_e2e_retry3_audit.log` |
| stdout log | `final_scope_widget_e2e_retry3_live_stdout.log` |

**Frozen (immutable):** all `final_scope_widget_e2e_retry1_*` and `final_scope_widget_e2e_retry2_*` live artifacts, preflight-abort attempt #1, widget matrix.

---

## Live governance

| Rule | Value |
|------|-------|
| `RETRY_COUNT_MAX` | 0 |
| Owner override | **forbidden** |
| Manual review | **required** after full live run |
| Rerun | blocked without new owner GO |

---

## STOP

Pre-live checkpoint only. **No live run in this cycle.**
