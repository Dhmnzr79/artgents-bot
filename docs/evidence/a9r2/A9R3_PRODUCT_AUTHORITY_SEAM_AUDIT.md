# A9R3 product authority seam audit (read-only)

**Date:** 2026-07-25  
**Baseline:** `f1b90b8` (A9R2d live complete)  
**Scope:** read-only wiring audit · **NO IMPLEMENTATION / NO LIVE / NO LLM**

**Owner decision (2026-07-25):** stop A9 model-tuning cycles; proceed to A9R3 product authority wiring with measured risk acceptance. Official A9R2d `AUTOMATED_FAIL`/`FAIL` unchanged; no retroactive PASS.

---

## Target chain (A9R3)

```
Plus Planner (plan_turn_attempt)
  → TurnFrame.patient_scope (native provenance)
  → project_patient_scope_from_turn_frame()     [A9R1 — exists, unwired]
  → merge_effective_scope_axes()                [A9R1 — exists, unwired]
  → EffectiveScope (extent/jaw/stage authority; reported_context excluded)
  → AC2 run_target_scope_aware_selection()
  → AC3 derive_response_stage() + scope/stage UI
```

**A9 does not:** select service, offer, strategy, `ResponseStage`, or treatment.

---

## Primary wiring seam: `core/target_runtime_turn.py`

| Step | Lines | Current behavior | A9R3 change |
|------|-------|------------------|-------------|
| Load TurnFrame | 141–151 | `load_runtime_turn_frame()` | unchanged |
| Hydrate service continuity | 154–159 | `hydrate_target_runtime_turn_frame_from_session()` | unchanged |
| Topic sync | 161–162 | `sync_session_patient_facts_topic()` | unchanged |
| **EffectiveScope resolve** | **163–169** | `resolve_effective_scope()` — **UI + session only** | **project + merge with A9** |
| Publish scope | 170 | `_publish_effective_scope()` | unchanged |
| AC2 strategy bridge | 194–197 | `strategy_match_from_effective_scope()` | consumes merged scope |
| Pipeline dispatch | 200–236 | `effective_scope=` into boundary-enforced pipeline | unchanged input contract |
| Session write | 266–276 | `write_target_runtime_session_after_materialized()` — service focus only | **add A9 extent/jaw/stage persist post-materialize** |

**Critical gap:** `turn_frame` is loaded at L141 but `patient_scope` is never read before L163.

---

## Resolver seam: `core/target_effective_scope.py`

| Symbol | Lines | Status |
|--------|-------|--------|
| `SessionPatientFacts` | 16–29 | Has extent/jaw/stage/reported_context |
| `resolve_effective_scope()` | 32–92 | AC1-only priority; **no `projected_turn_scope` input** |

**A9R3:** extend resolver signature to accept `projected_turn_scope: ProjectedTurnScope | None` and delegate per-axis merge to `merge_effective_scope_axes()` from `core/target_effective_scope_merge.py`.

### Merge priority (owner-approved)

1. typed `UiScopeAction` (current turn) — extent
2. typed `UiStageAction` (current turn) — stage
3. confident current-turn A9 projection (`source=a9_turn`, native provenance)
4. fresh session `patient_facts` (same topic)
5. `unknown`

**Rules:**
- typed UI action of current turn **above** A9
- usable current-turn A9 **above** same-topic session
- current `unknown` **does not erase** session
- explicit correction **replaces** axis in session
- topic change / reset / SID isolation / freshness preserved

---

## A9R1 modules (ready, offline-tested)

| Module | Entry point | Role |
|--------|-------------|------|
| `core/target_patient_scope_projection.py` | `project_patient_scope_from_turn_frame()` | Native provenance gate; scalar bridge **not** authority |
| `core/target_effective_scope_merge.py` | `merge_effective_scope_axes()` | Per-axis merge |
| same | `simulate_session_patient_facts_after_turn()` | Offline session-write preview — **promote to product writer** |

**`reported_context`:** projected for diagnostic/shadow only; **must not** enter session or AC2 inputs in A9R3.

---

## AC1 ingress (unchanged contract)

| Path | Function | Lines |
|------|----------|-------|
| `orchestration/pre_resolver_turn.py` | UI scope/stage action → session + `request.ctx` | 242–301 |
| `core/target_runtime_turn.py` | `_current_ui_scope_action_from_request()` | 76–103 |

UI click priority over planner inference is already AC1 law; A9R3 merge must preserve it.

---

## AC2 / AC3 consumers (no change expected)

| Layer | Path | Entry |
|-------|------|-------|
| AC2 selection | `core/target_scope_aware_selection.py` | `run_target_scope_aware_selection(..., effective_scope=)` |
| AC2 strategy | `core/target_strategy_context.py` | `strategy_match_from_effective_scope()` |
| AC3 stage | `core/target_response_stage.py` | `derive_response_stage(..., effective_scope=)` |
| AC3 price package | `core/target_scope_aware_price_package.py` | `assemble_scope_aware_price_package()` |
| Dispatch | `core/target_turn_frame_dispatch.py` | `_initial_scope_price_stage(effective_scope)` |

AC2 remains sole selector; AC3 remains response/UI owner.

---

## Session persistence seam: `core/target_runtime_session.py`

| Function | Lines | A9R3 |
|----------|-------|------|
| `read_session_patient_facts` | via `read_target_runtime_session` | unchanged |
| `write_session_patient_facts_from_ui_action` | 212–226 | unchanged |
| `write_session_patient_facts_from_ui_stage_action` | 229–251 | unchanged |
| `write_target_runtime_session_after_materialized` | 284–338 | **add verified A9 write (extent/jaw/stage only)** |

**Persistence rules:**
- persist only after successful **materialized** turn
- terminal/error paths must **not** overwrite prior patient facts
- corrections must persist
- no second session scope store

---

## Planner model (implementation deliverable — not in this governance commit)

| Item | Current | A9R3 target |
|------|---------|-------------|
| `config.TURN_PLANNER_LLM_MODEL` default | `qwen3.6-flash` | **`qwen3.7-plus`** |
| env override | eval pin only | ordinary model config, not architecture kill-switch |
| runtime verification | none | runtime tests must observe Plus |

Owner accepts measured A9R2d risk: one directionally plausible extent FP on «восстановить обе челюсти» (`a9r_jaw_03_both`).

---

## Measured quality context (immutable)

| Checkpoint | Verdict | Notes |
|------------|---------|-------|
| A9R2d Plus live | `AUTOMATED_FAIL` / `FAIL` | 1 material FP; `true_composite` 0.882; model verified |
| A9R2c | `A9R2C_NOT_VALID_FOR_PLUS` | model-pin incident; not Plus-valid |
| Owner | risk accepted | proceed to authority wiring; **no retroactive PASS** |

---

## Firewall / forbidden reads

- `tests/test_turn_frame_shadow.py` — product must not read `patient_scope` except through controlled A9R3 resolver path
- No `core/patient_scope_cues.py` regex routing for authority
- No legacy W1b / family-group routes
- Scalar bridge provenance must not receive authority

---

## Recommended implementation allowlist (future TASK — not this commit)

| File | Role |
|------|------|
| `core/target_effective_scope.py` | Wire merge into resolver |
| `core/target_runtime_turn.py` | Project + pass scope; post-materialize session write |
| `core/target_runtime_session.py` | Product A9 session writer |
| `config.py` | Default `TURN_PLANNER_LLM_MODEL` → Plus |
| `docs/FLAGS_AND_STATUS.md` | `A9_PATIENT_SCOPE_AUTHORITY` flag (default OFF until flip) |
| `tests/test_effective_scope_merge.py` | Regression |
| `tests/test_session_patient_facts_offline.py` | A9 persistence |
| `tests/test_ac3_scope_price_flow_offline.py` | AC1–AC3 acceptance |
| `tests/test_ui_scope_click_http_offline.py` | UI priority |
| `tests/test_turn_frame_shadow.py` | Controlled read allowance |

**Frozen (byte-identical):** A9/A9R/A9R2*/W1b/S-series artifacts and matrices.

---

## STOP

Governance audit complete. **No product code in this checkpoint.** Implementation requires separate owner GO + PRE-CODE on implementation TASK.
