# FINAL scope/widget E2E retry1 — seam audit (post-S69 target-only)

**Date:** 2026-07-26  
**Baseline:** `0f645cc` (preflight-abort audit)  
**Scope:** harness correction only · **NO LIVE / NO LLM / NO PRODUCT CODE**

---

## Verdict

Retry1 harness removes stale `orchestration.ask_turn` wiring deleted in S69. Live path uses **post-S69 target-only** `app._orchestrate_ask_turn` only. Retry1 artifacts are isolated under `final_scope_widget_e2e_retry1_*`. Frozen preflight-abort marker/audit from attempt #1 remain byte-identical.

---

## Post-S69 target-only chain

```
POST /ask
  → _orchestrate_ask_turn(data)
    → run_pre_resolver_turn (AC1 UI scope/stage/ref)
    → run_planner_turn (Plus, A9_PATIENT_SCOPE_AUTHORITY=1 in harness)
    → orchestrate_target_fullcontext_turn (target FullContext only)

POST /ask/stream
  → _orchestrate_ask_turn(data)   # same orchestration
  → _dispatch_orchestration_sse   # batch SSE ui + done
```

**Deleted / forbidden:** `orchestration.ask_turn`, `orchestrate_routing_after_resolver`, `TARGET_FULLCONTEXT_DEV`, chunk/price/catalog legacy flows.

---

## Harness preflight order (retry1)

| Step | Action |
|------|--------|
| 1 | `configure_process_env()` — `A9_PATIENT_SCOPE_AUTHORITY=1`, Plus planner **before** `import config` |
| 2 | Frozen neighbor pins (S62/S63 + preflight-abort attempt/audit SHA) |
| 3 | Matrix hash verify |
| 4 | Retry1 artifact paths absent |
| 5 | `validate_runtime_seams()` — import config/app, legacy guards, TestClient |
| 6 | Create `final_scope_widget_e2e_retry1_attempt.json` **only after** step 5 |
| 7 | Install provider audit |
| 8 | First HTTP turn / provider call |

**Preflight failure:** 0 provider calls, retry1 marker **not** created.

---

## Backend injection / audit seams

| Seam | Role |
|------|------|
| `llm.chat_completions_create` | provider audit wrapper (ledger + budget) |
| `ingress_gate.chat_completions_create` | ingress role rebind |
| `core.turn_planner_llm._planner_chat_completions_create` | planner role rebind |
| `core.target_cached_full_context.build_target_cached_full_context` | FullContext build counter (expect 1) |
| Legacy guards on surviving modules | `pre_resolver_turn`, `md_chunks`, `price_ref_routing`, etc. |

No `orchestrate_routing_after_resolver` setattr. No legacy module imports.

---

## Retry1 artifact namespace

| Artifact | Path |
|----------|------|
| attempt marker | `evals/v5/artifacts/final_scope_widget_e2e_retry1_attempt.json` |
| raw/result | `final_scope_widget_e2e_retry1_{raw,result}.json` |
| manifest | `final_scope_widget_e2e_retry1_manifest.json` |
| ledger | `final_scope_widget_e2e_retry1_call_ledger.jsonl` |
| manual review | `final_scope_widget_e2e_retry1_manual_review.json` |
| audit log | `final_scope_widget_e2e_retry1_audit.log` |

**Frozen (immutable):** `final_scope_widget_e2e_attempt.json`, `FINAL_SCOPE_WIDGET_E2E_LIVE_ATTEMPT_AUDIT.md`.

---

## Provider budget (unchanged)

| Role | Budget |
|------|--------|
| ingress | 5 |
| planner | 8 |
| medical_boundary | 8 |
| composer | 8 |
| semantic_verifier | 8 |
| **total** | **40** |

`RETRY_COUNT_MAX = 0`. FullContext build = 1.

---

## STOP

Harness correction complete. **Retry1 live blocked** until separate owner GO.
