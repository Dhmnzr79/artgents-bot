# FINAL scope/widget E2E retry2 — seam audit (post-POST_RETRY1 correction)

**Date:** 2026-07-26  
**Baseline:** `c670b96` (POST_RETRY1 product correction COMPLETION ✅)  
**Scope:** pre-live checkpoint only · **NO LIVE / NO LLM / NO PRODUCT CODE**

---

## Verdict

Retry2 is a **new isolated namespace** (`final_scope_widget_e2e_retry2_*`) for the first live attempt after POST_RETRY1 product correction. Frozen Retry1 FAIL artifacts remain byte-identical and are **not** bypassed. The same frozen 8-turn matrix (`final_scope_widget_e2e_turns.json`, hash `f4eecf75…`) is reused. Offline real-path replay re-proves 8/8 automated gates with fake providers through the **post-correction** target runtime.

---

## Lineage

| Attempt | Measurement ID | Status |
|---------|----------------|--------|
| preflight-abort #1 | `final_scope_widget_e2e` | frozen |
| retry1 live | `final_scope_widget_e2e_retry1` | official **FAIL** @ `d76870a` — frozen |
| product correction | POST_RETRY1 | COMPLETION ✅ @ `c670b96` |
| **retry2 (this)** | `final_scope_widget_e2e_retry2` | pre-live only |

Parent measurement: `final_scope_widget_e2e_retry1`.

---

## Post-correction target-only chain (unchanged)

```
POST /ask | /ask/stream
  → _orchestrate_ask_turn(data)
    → run_pre_resolver_turn (AC1 UI scope/stage/ref; neutral "продолжить" on ref-only clicks)
    → run_planner_turn (qwen3.7-plus, A9_PATIENT_SCOPE_AUTHORITY=1 before import)
    → orchestrate_target_fullcontext_turn
```

Product fixes from POST_RETRY1 (T2/T5) are in production code @ `c670b96`; retry2 live validates them end-to-end.

---

## Harness preflight order (retry2)

| Step | Action |
|------|--------|
| 1 | `configure_process_env()` — `A9_PATIENT_SCOPE_AUTHORITY=1`, Plus planner **before** `import config` |
| 2 | Frozen neighbor pins (preflight-abort, S62/S63, matrix hash) |
| 3 | **Retry1 live artifacts** SHA256 unchanged (do not modify or bypass) |
| 4 | **Retry2 artifact paths absent** |
| 5 | `validate_runtime_seams()` |
| 6 | Create `final_scope_widget_e2e_retry2_attempt.json` **only after** step 5 |
| 7 | Provider audit install |
| 8 | First HTTP turn / provider call |

---

## Retry2 artifact namespace (pre-live: all absent)

| Artifact | Path |
|----------|------|
| attempt marker | `evals/v5/artifacts/final_scope_widget_e2e_retry2_attempt.json` |
| raw/result | `final_scope_widget_e2e_retry2_{raw,result}.json` |
| manifest | `final_scope_widget_e2e_retry2_manifest.json` |
| ledger | `final_scope_widget_e2e_retry2_call_ledger.jsonl` |
| manual review | `final_scope_widget_e2e_retry2_manual_review.json` |
| audit log | `final_scope_widget_e2e_retry2_audit.log` |
| stdout log | `final_scope_widget_e2e_retry2_live_stdout.log` |

**Frozen (immutable):** all `final_scope_widget_e2e_retry1_*` live artifacts, preflight-abort attempt #1, widget matrix.

---

## Provider budget

| Constant | Value |
|----------|-------|
| `MAX_HTTP_TURNS` | 8 |
| `MAX_PROVIDER_CALLS` | 40 |
| `RETRY_COUNT_MAX` | 0 |
| Planner | `qwen3.7-plus` |
| `A9_PATIENT_SCOPE_AUTHORITY` | ON before import |

---

## Forensic stdout disposition

| File | Size | SHA256 | Disposition |
|------|------|--------|-------------|
| `evals/v5/artifacts/_retry1_live_run_stdout.txt` (untracked) | 634 914 | `d3e3f159e37e94e0f04b6e1e30a6a7675a2c093c9121f72d78248813c9c3f946` | Verified @ RETRY2 checkpoint; **removed** (UTF-16 LE duplicate; committed `final_scope_widget_e2e_retry1_live_stdout.log` remains frozen) |

No `git clean`. Committed Retry1 stdout artifact unchanged.

---

## Offline 8/8 gate (pre-live proof)

`tests/test_final_scope_widget_e2e_retry2_live_harness.py::test_fake_provider_executes_all_eight_http_turns_without_network` replays all 8 matrix turns through real `app._orchestrate_ask_turn` with fake ingress/planner/boundary/composer backends. Expect: 8/8 `automated_turn_verdict=PASS`, `all_materialized=True`, `fullcontext_build_count=1`, T2/T5 materialized (no terminal on turn 2; turn 5 has 3 scope-nav + `₽`).

---

## STOP

**NO LIVE** until separate owner GO. This checkpoint is governance + offline wiring only.
