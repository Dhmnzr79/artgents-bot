# FINAL scope/widget E2E — post-E2E closeout seam audit (read-only)

**Date:** 2026-07-26  
**Baseline:** `5ff9893` (`codex/stage-a`)  
**Prerequisite:** Retry4 live `AUTOMATED_PASS` + owner manual **PASS 8/8**  
**Scope:** read-only closeout design · **NO IMPLEMENTATION / NO LIVE / NO LLM / NO Retry5**

---

## Verdict

FINAL widget E2E is **complete** at product level. Closeout removes the temporary `A9_PATIENT_SCOPE_AUTHORITY` kill-switch and makes A9 patient-scope projection + per-axis merge **unconditional** — behavior proven at Retry4 live must remain byte-stable in product semantics.

Frozen Retry1–Retry4 live artifacts, A9/A9R/S-series eval artifacts, and widget matrix remain **immutable**.

---

## Checkpoint A — manual PASS (completed @ governance `5ff9893`)

| Deliverable | Status |
|-------------|--------|
| Append-only manual review audit | `FINAL_SCOPE_WIDGET_E2E_RETRY4_MANUAL_REVIEW_AUDIT.md` |
| SHA pins to frozen result/manifest/matrix | bound in audit + `final_scope_widget_e2e_retry4_live_contract.py` |
| Retry4 artifacts | **not edited** |
| `result.json` `final_verdict` | stays `PENDING_MANUAL_REVIEW` (frozen capture) |
| Canonical owner verdict | **PASS 8/8** |

---

## Checkpoint B — closeout implementation design

### 1. Remove `A9_PATIENT_SCOPE_AUTHORITY`

| Location | Action |
|----------|--------|
| `config.py` | **delete** `A9_PATIENT_SCOPE_AUTHORITY` |
| `core/target_effective_scope.py` | remove `if A9_PATIENT_SCOPE_AUTHORITY:` branch |
| `core/target_runtime_turn.py` | remove conditional projection/merge |
| `evals/v5/final_scope_widget_e2e_live_harness.py` | remove env assert for flag |
| `evals/v5/final_scope_widget_e2e_*_live_contract.py` | remove `REQUIRES_A9_*` preflight where applicable |
| `docs/FLAGS_AND_STATUS.md` | remove kill-switch row; document unconditional authority |
| tests | drop flag-enable fixtures; authority always on |

**Acceptance (implementation):** `rg` / AST — zero `A9_PATIENT_SCOPE_AUTHORITY` in product path, tests, harness preflight (except historical frozen artifact JSON/logs).

### 2. Unconditional projection + per-axis merge

```
POST /ask | /ask/stream
  → load/hydrate TurnFrame
  → project_patient_scope_from_turn_frame()     [always]
  → merge_effective_scope_axes()                [always]
  → resolve_effective_scope() → EffectiveScope
  → AC1→AC2→AC3 dispatch (unchanged)
  → materialized → session write (extent/jaw/stage only)
```

**Planner default:** `qwen3.7-plus` — **unchanged**.

### 3. Authority axes (only)

| Axis | Values |
|------|--------|
| `extent` | `one_tooth`, `few_teeth`, `full_arch`, `unknown` |
| `jaw` | `upper`, `lower`, `both`, `unknown` |
| `stage` | `natural_tooth_present`, `implant_placed`, `unknown` |

**`reported_context`:** continues **excluded** from product scope and session (`strip_reported_context_for_product`).

### 4. Merge priority (binding)

1. typed UI action (current turn) — `UiScopeAction` / `UiStageAction`
2. confident A9 current-turn projection (`source=a9_turn`, native provenance)
3. fresh session `patient_facts` (same topic)
4. `unknown`

**Rules:**
- typed UI action **>** confident A9 **>** session **>** unknown
- current-turn `unknown` / ambiguous **does not erase** session axis
- explicit correction **replaces** axis in session
- All-on-4 info/price mention **does not** set scope extent
- session write **only after materialized** response
- terminal / error / verifier block **do not** persist new scope
- topic change / reset / SID isolation / freshness — preserved

### 5. Unchanged surfaces

| Surface | Status |
|---------|--------|
| AC1→AC2→AC3 dispatch | unchanged |
| typed UI TurnFrame (`try_run_typed_ui_planner_turn`) | unchanged |
| `TargetComposerActionContext` wiring | unchanged |
| Verifier | **no changes** |
| `/ask` and `/ask/stream` parity | required |
| legacy/fallback paths | **forbidden** |

---

## Implementation acceptance matrix

| Case | Expected |
|------|----------|
| explicit `one_tooth` / `few_teeth` / `full_arch` | sets extent axis |
| jaw `upper` / `lower` / `both` | sets jaw axis |
| `natural_tooth_present` / `implant_placed` | sets stage axis |
| All-on-4 info/price | **no** scope extent write |
| correction turn | replaces session axis |
| UI scope/stage click | priority over A9 + session |
| freshness / reset / SID isolation | preserved |
| `/ask` vs `/ask/stream` | parity |
| no legacy/fallback | S69 target-only |
| `A9_PATIENT_SCOPE_AUTHORITY` | absent post-closeout |

---

## Frozen (immutable)

- `final_scope_widget_e2e_retry{1,2,3,4}_*` live artifacts
- A9/A9R live eval artifacts
- S62/S63/S66 frozen live artifacts
- `evals/v5/demo/final_scope_widget_e2e_turns.json` (matrix hash `f4eecf75…`)

---

## Forbidden (closeout implementation)

- LIVE / LLM / Retry5
- A9 prompt tuning
- Verifier changes
- regex / phrase lists for scope
- new selectors / routes
- editing frozen Retry4 (or prior) live artifacts
- admin/log implementation (WinError 32 rollover deferred)

---

## STOP

Governance checkpoint only. **No product code in this cycle.** Implementation requires separate owner GO.
