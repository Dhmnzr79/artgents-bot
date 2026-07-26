# FINAL scope/widget E2E retry4 — seam audit (post-POST_RETRY3)

**Date:** 2026-07-26  
**Baseline:** `6b67e35` (POST_RETRY3_COMPOSER_ACTION_CONTEXT COMPLETION ✅)  
**Scope:** pre-live checkpoint only · **NO LIVE / NO LLM / NO PRODUCT CODE**

---

## Verdict

Retry4 is a **new isolated namespace** (`final_scope_widget_e2e_retry4_*`) for the first live attempt after POST_RETRY3 Composer action-context product fix. Frozen Retry1/Retry2/Retry3 artifacts remain byte-identical. Same frozen 8-turn matrix (`f4eecf75…`). Offline real-path replay re-proves 8/8 with governed action context, no `price:None/...` refs, and explicit manual rubric gates for T1/T2/T6/T7.

---

## Lineage

| Attempt | Measurement ID | Status |
|---------|----------------|--------|
| preflight-abort #1 | `final_scope_widget_e2e` | frozen |
| retry1 live | `final_scope_widget_e2e_retry1` | official **FAIL** — frozen |
| retry2 live | `final_scope_widget_e2e_retry2` | official **FAIL** — frozen |
| retry3 live | `final_scope_widget_e2e_retry3` | official **FAIL** (manual) — frozen |
| POST_RETRY3 fix | `TargetComposerActionContext` | COMPLETION ✅ @ `6b67e35` |
| **retry4 (this)** | `final_scope_widget_e2e_retry4` | pre-live only |

Parent measurement: `final_scope_widget_e2e_retry3`.

---

## Post-POST_RETRY3 target chain

```
POST /ask | /ask/stream
  → run_pre_resolver_turn (AC1 UI scope/stage; neutral "продолжить")
  → try_run_typed_ui_planner_turn  ← T2/T6/T7: native TurnFrame, planner skipped
  → run_planner_turn               ← free-text only (5 turns)
  → orchestrate_target_fullcontext_turn
       → Composer receives governed_action_context_json (typed clicks)
```

Verifier unchanged. No product code changes in this cycle.

---

## Harness preflight order (retry4)

| Step | Action |
|------|--------|
| 1 | `configure_process_env()` — `A9_PATIENT_SCOPE_AUTHORITY=1`, Plus planner before import |
| 2 | Frozen neighbors (preflight-abort, S62/S63, matrix) |
| 3 | **Retry1 + Retry2 + Retry3** live artifacts SHA256 unchanged |
| 4 | **Retry4 artifact paths absent** |
| 5 | `validate_runtime_seams()` |
| 6 | Create `final_scope_widget_e2e_retry4_attempt.json` **only after** step 5 |
| 7 | Retry4 provider audit install (budget caps below) |
| 8 | First HTTP turn / provider call |

---

## Provider budget (retry4 — hard caps)

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

## Manual review rubric (binding for live)

| Turn | Criterion | Owner expectation |
|------|-----------|-------------------|
| T1 | `compact_overview` | Broad implantation price overview: compact 2–4 anchors + scale prompt + 3 scope buttons; no payment-stage/bonus wall |
| T2 | `full_arch_prices` | Typed `target:ui_scope/implantation/full_arch` → scoped full_arch prices; Composer has `TargetComposerActionContext`; no welcome stub |
| T6 | `concise_stage_clarification` | Typed `one_tooth` prosthetics → concise `stage_clarify` text + stage buttons; governed action context in Composer |
| T7 | `crown_price` | Typed `target:ui_stage/prosthetics/implant_placed` → crown price on implant; governed `ui_stage` context |

**Global widget rule:** no `price:None/...` refs in any turn.

Offline harness asserts automated gates + rubric proxies (T1 length/verbosity, T2/T7 governed refs + ₽, T6 concise этап text).

---

## Retry4 artifact namespace (pre-live: all absent)

| Artifact | Path |
|----------|------|
| attempt marker | `evals/v5/artifacts/final_scope_widget_e2e_retry4_attempt.json` |
| raw/result | `final_scope_widget_e2e_retry4_{raw,result}.json` |
| manifest | `final_scope_widget_e2e_retry4_manifest.json` |
| ledger | `final_scope_widget_e2e_retry4_call_ledger.jsonl` |
| manual review | `final_scope_widget_e2e_retry4_manual_review.json` |
| audit log | `final_scope_widget_e2e_retry4_audit.log` |
| stdout log | `final_scope_widget_e2e_retry4_live_stdout.log` |

**Frozen (immutable):** all `final_scope_widget_e2e_retry1_*`, `retry2_*`, `retry3_*` live artifacts, preflight-abort attempt #1, widget matrix.

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
