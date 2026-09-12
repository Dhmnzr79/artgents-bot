# FINAL_SCOPE_WIDGET_E2E_RETRY2_POST_LIVE — seam audit (read-only)

**Date:** 2026-07-26  
**Baseline:** `cbbdb35` (`codex/stage-a`)  
**Authority:** RETRY2 live = official **FAIL** · rerun **blocked** · `A9_PATIENT_SCOPE_AUTHORITY` **must remain**

**Scope:** governance / read-only checkpoint · **NO LIVE / NO LLM / NO PRODUCT CODE**

Live attempt audit: `docs/evidence/final_scope/FINAL_SCOPE_WIDGET_E2E_RETRY2_LIVE_ATTEMPT_AUDIT.md`

---

## Verdict

POST_RETRY1 dispatch precedence fixed RETRY1 T5 (`broad_family_price` under `needs_clarify=true`) and passed offline 8/8. RETRY2 live exposes a **deeper seam**: governed UI clicks still depend on planner `TurnFrame` authority after neutral `продолжить` ingress. T2 and T6 fail with `target_fullcontext_error` because partial planner output cannot drive AC2→AC3.

| Failure | Symptom | Root seam |
|---------|---------|-----------|
| **T2** | `target:ui_scope/implantation/full_arch` → `target_fullcontext_error` | Partial planner `TurnFrame` after UI click; no authoritative commercial frame |
| **T6** | `target:ui_scope/prosthetics/one_tooth` → `target_fullcontext_error` | Same; blocks stage-nav for T7 |
| **T7 prep** | `missing stage ref implant_placed` | **Secondary** — harness abort; no buttons from T6 |

---

## Shared runtime chain (RETRY2 T2 & T6)

```
POST /ask[/stream]
  → run_pre_resolver_turn()                    [AC1: UiScopeAction; q="продолжить" on ref-only click]
  → orchestrate_target_fullcontext_turn()
  → run_target_fullcontext_runtime_turn()
       ├ load_runtime_turn_frame()             [planner LLM — partial frame on "продолжить"]
       ├ resolve_effective_scope()             [AC1 merge — UiScopeAction on ctx ✅]
       ├ execute_target_medical_boundary_classification()
       └ dispatch_target_turn_frame_response()
            └ partial frame → target_fullcontext_error ❌
```

Live evidence: `evals/v5/artifacts/final_scope_widget_e2e_retry2_live_stdout.log` (`http_request` + `turn_complete`).

### Observed on T2 (representative)

| Layer | Value |
|-------|-------|
| `nav_ref` | `target:ui_scope/implantation/full_arch` |
| `current_ui_scope_action` | `{topic: implantation, extent: full_arch, provenance: ui_scope_ref}` ✅ |
| `user_text` / planner input | `продолжить` |
| `runtime_turn_frame` | `intent=unknown`, `topic=null`, `aspects=[]`, `patient_scope.extent=unknown` ❌ |
| Route | `target_fullcontext_error` ❌ |
| Expected | scoped materialized price (AC2→AC3) |

T6 is structurally identical (`prosthetics` / `one_tooth`).

---

## Why POST_RETRY1 dispatch fix is insufficient

POST_RETRY1 added scope-price materialize precedence when `_scope_price_topic()` and effective scope are known. RETRY2 live shows planner partial frame leaves `_scope_price_topic()` unset or dispatch cannot materialize without authoritative `topic` + `price` aspect on the **commercial TurnFrame** used by dispatch.

**EffectiveScope alone is not sufficient** when dispatch/composer path requires a complete planner-owned frame. Typed UI actions must produce (or overlay) an **authoritative commercial TurnFrame** before dispatch.

---

## Next product milestone (offline — owner design)

**Name (proposed):** `FINAL_SCOPE_WIDGET_E2E_RETRY2_TYPED_UI_TURNFRAME`

### Binding semantics

| Rule | Requirement |
|------|-------------|
| UI authority | Governed `UiScopeAction` / `UiStageAction` **deterministically** set `topic`, price `intent`/`aspect`, `needs_clarification=false` |
| Planner role | LLM planner **not** authority for typed click meaning |
| Ingress | **No** button label or `продолжить` as routing source |
| Path reuse | AC1→AC2→AC3 only; **no** new selector, route, or legacy fallback |
| Forbidden | regex/phrase lists, A9 prompt tuning, service hardcodes, legacy fallback |

### Canonical implementation fork (owner must pick one at PRE-CODE)

| Option | Seam | Trade-off |
|--------|------|-----------|
| **A — Native typed TurnFrame producer** | Before or instead of planner on `provenance in {ui_scope_ref, ui_stage_ref}`, synthesize full `TurnFrame` from governed action + session | Cleanest authority; planner skipped or short-circuited on typed clicks |
| **B — Validated typed overlay** | After planner returns, overlay governed fields from `current_ui_scope_action` / `current_ui_stage_action` when provenance is UI; reject partial frame for commercial path | Smaller diff; must guard against planner contradicting overlay |

Both options must preserve free-text planner path unchanged.

**Recommended audit position:** Option A at `load_runtime_turn_frame` / `run_target_fullcontext_runtime_turn` boundary — typed producer runs when AC1 ctx carries governed UI action; planner runs only when no authoritative typed frame exists.

### Data contract (typed commercial frame)

When `current_ui_scope_action` or `current_ui_stage_action` is present:

```
topic        ← from governed action (implantation | prosthetics)
aspects      ← ["price"]  (or primary_aspect price)
intent       ← price_lookup (existing commercial intent)
needs_clarification ← false
patient_scope.extent ← from UiScopeAction when applicable
patient_scope.stage  ← from UiStageAction when applicable
field_meta.*.provenance ← ui_action (audit)
```

Dispatch then reuses existing `_scope_price_topic()` + AC2→AC3 without terminal shortcuts.

---

## Acceptance matrix (protected — implementation)

Matrix blob: `f4eecf7532481a288d1db6a6ee107dd147117dae44afc991451836dd3589434f` (**immutable**)

| ID | Scenario | Expected |
|----|----------|----------|
| AM-1 | broad implantation price | `broad_family_price` + 3 scope buttons |
| AM-2 | broad prosthetics price + planner `needs_clarify=true` | `broad_family_price` + 3 scope buttons (POST_RETRY1 — retain) |
| AM-3 | typed scope click `full_arch` (implantation) | scoped materialized; session `full_arch`; **planner partial frame must not win** |
| AM-4 | typed scope click `one_tooth` (prosthetics) | scoped materialized or `stage_clarify` + stage nav per AC3 |
| AM-5 | typed stage click `implant_placed` | scoped offers; no repeat nav |
| AM-6 | free-text full_arch / implant_placed | A9 scope → scoped price (planner path unchanged) |
| AM-7 | ordinary medical free-text | boundary `medical_handoff` behavior **unchanged** |
| AM-8 | ambiguous non-price | `terminal_clarify` **preserved** |
| AM-9 | invalid / unshown ref click | fail-closed unknown-ref clarify |
| AM-10 | `/ask` vs `/ask/stream` | same EffectiveScope + route class |
| AM-11 | terminal/error turn | **no** session `patient_facts` overwrite |
| AM-12 | 8-turn widget matrix offline replay | 8/8 HTTP; automated gates pass |
| AM-13 | **partial planner fixture on UI click** | typed overlay/producer wins → materialized (new) |

RETRY2 live turns 1–8 remain canonical E2E oracle (`final_scope_widget_e2e_turns.json`).

---

## Blast-radius tests (implementation allowlist — future owner GO)

| File | Extend for |
|------|------------|
| `core/target_runtime_turn.py` | typed TurnFrame producer or overlay hook |
| `core/target_turn_frame_dispatch.py` | retain POST_RETRY1 precedence; no regression |
| `orchestration/pre_resolver_turn.py` | keep neutral `продолжить`; no label routing |
| `tests/test_final_scope_widget_e2e_retry2_live_harness.py` | fake planner returns **partial frame** on UI clicks; assert materialized |
| `tests/test_ui_scope_click_http_offline.py` | scope clicks T2/T6 paths |
| `tests/test_ac3_scope_price_flow_http_offline.py` | stage click T7; `/ask` + `/ask/stream` |
| `tests/test_a9r3_product_authority_offline.py` | free-text A9 unchanged |
| `tests/test_session_patient_facts_offline.py` | error turn no session overwrite |
| `tests/test_final_scope_widget_e2e_retry2_post_live_audit_governance.py` | frozen RETRY2 pins |

**Mandatory test pattern:** UI-click cases must install planner fake that returns `intent=unknown`, `topic=null`, `needs_clarification=false` (or true) — product must still materialize via typed authority.

---

## Frozen neighbors (must stay byte-identical)

| Artifact | Pin |
|----------|-----|
| RETRY2 attempt + ledger + stdout @ `cbbdb35` | governance test SHAs |
| RETRY1 live artifacts + audit | retry1 contract pins |
| Preflight-abort attempt #1 + audit | contract pins |
| S62 / S63 / A9 / A9R* / W1b | existing pins |
| Widget E2E turn matrix | `f4eecf75…` |

---

## STOP

Governance audit complete. **No product code in this checkpoint.** Typed UI TurnFrame implementation requires separate owner GO + PRE-CODE on implementation TASK.
