# FINAL_SCOPE_WIDGET_E2E_RETRY2 live attempt audit

**Date:** 2026-07-26  
**Baseline (live):** `4fc9c6b` (pre-live checkpoint)  
**Artifacts commit:** `cbbdb35`  
**Matrix blob:** `f4eecf7532481a288d1db6a6ee107dd147117dae44afc991451836dd3589434f`  
**Owner GO:** one RETRY2 live attempt · owner override **forbidden** · retry=0

---

## Verdict

| Field | Value |
|-------|-------|
| **Status** | `LIVE_ABORT_MID_RUN` |
| **Automated verdict** | `AUTOMATED_FAIL` |
| **Final verdict** | **FAIL** (official, immutable) |
| **Valid live attempt** | **PARTIAL** — 6/8 HTTP turns, harness abort before turn 7 HTTP |
| **Rerun** | **BLOCKED** |

---

## Preflight (passed)

| Check | Result |
|-------|-------|
| HEAD @ live start | `4fc9c6b540a28ee4204eda82d42e734fa30f20e8` |
| Retry1 frozen artifacts | unchanged ✅ |
| Preflight-abort attempt #1 | unchanged ✅ |
| Matrix hash | `f4eecf75…` ✅ |
| `A9_PATIENT_SCOPE_AUTHORITY` | `1` before import ✅ |
| Planner model | `qwen3.7-plus` ✅ |

---

## Abort

**Command:** `python evals/v5/run_final_scope_widget_e2e_retry2_live.py --live`  
**Exit code:** 5  
**Harness error:** `HarnessConfigError: missing stage ref from_turn=6 stage=implant_placed`

**Secondary effect:** Turn 6 (`fsw_turn_06_scope_one_tooth_click`) returned `target_fullcontext_error` instead of materialized scoped price with stage-nav buttons. Harness could not resolve turn 7 UI stage ref `implant_placed` from turn 6 `quick_replies`.

Turns 7–8 not reached.

---

## Turn outcomes (matrix)

| Turn | `turn_id` | Route (observed) | Gate |
|------|-----------|------------------|------|
| 1 | `fsw_turn_01_implant_broad` | materialized `broad_family_price` | PASS |
| 2 | `fsw_turn_02_scope_full_arch_click` | **`target_fullcontext_error`** | **FAIL** |
| 3 | `fsw_turn_03_extent_correction_one_tooth` | materialized scoped | PASS |
| 4 | `fsw_turn_04_implant_full_arch_a9_stream` | materialized scoped (`/ask/stream`) | PASS |
| 5 | `fsw_turn_05_prosthetics_broad` | materialized `broad_family_price` | PASS |
| 6 | `fsw_turn_06_scope_one_tooth_click` | **`target_fullcontext_error`** | **FAIL** |
| 7 | `fsw_turn_07_stage_implant_placed_click` | not reached (harness prep abort) | — |
| 8 | `fsw_turn_08_prosthetics_a9_implant_placed_stream` | not reached | — |

POST_RETRY1 dispatch correction improved T5 vs RETRY1; T2/T6 UI-click failures persist under live planner.

---

## Primary cause (owner ruling)

Neutral governed continuation **`продолжить`** (POST_RETRY1 `pre_resolver_turn` fix) replaces button label for planner/boundary input. Live planner returns a **partial `TurnFrame`** on UI scope clicks:

| Field | Observed on T2/T6 |
|-------|-------------------|
| `intent` | `unknown` |
| `topic` | `null` |
| `aspects` | `[]` |
| `patient_scope.extent` | `unknown` (planner) |

Meanwhile **typed `UiScopeAction` is correct** on request ctx (`current_ui_scope_action`: topic + extent + `provenance=ui_scope_ref`) and **EffectiveScope** may reflect UI action. The runtime still dispatches on the **planner-owned partial frame**, which cannot drive AC2→AC3 commercial materialization → `target_fullcontext_error`.

**LLM Planner is not authority for typed click semantics.** Label text and neutral `продолжить` must not be routing sources.

`missing implant_placed` ref and harness abort are **secondary effects** of T6 error route (no stage-nav buttons).

---

## Provider calls (ledger — corrected)

| Role | Calls |
|------|-------|
| ingress | 4 |
| planner | 6 |
| medical_boundary | 6 |
| composer | 4 |
| semantic_verifier | 4 |
| **Total started** | **24** / 40 budget |

**Planner models observed:** all `qwen3.7-plus` (6/6) ✅  
**Retries:** 0 ✅  
**Legacy hits:** 0 ✅  
**Ledger:** balanced ✅, incomplete (abort mid-run)

Attempt marker `role_counts` matches ledger ✅ (ingress 4, planner 6, boundary 6, composer 4, verifier 4).

---

## Artifacts (immutable @ `cbbdb35`)

| Artifact | SHA-256 | Notes |
|----------|---------|-------|
| `final_scope_widget_e2e_retry2_attempt.json` | `deb0e00b0fccc0d3ab6f5e65a67caaacf90677231898e10dc3e9f3893e160671` | `status=attempt_started` — **do not rewrite** |
| `final_scope_widget_e2e_retry2_call_ledger.jsonl` | `db430edc71ff8e3954a83e8d8f1ee9db610755a7549b5e105986940444f460ea` | 24 call starts |
| `final_scope_widget_e2e_retry2_live_stdout.log` | `32b6a1f45660deb171b882bcc568807a5bec6a0c2479917f10e04a48439a00aa` | 386 867 bytes |

**Not created (harness abort before finalization):** `raw.json`, `result.json`, `manifest.json`, `manual_review.json`, `audit.log`.

---

## Non-blocking incident (separate)

**WinError 32** — `PermissionError` on `logs/demo-app.jsonl` `RotatingFileHandler.doRollover` (file locked by another process). Repeated logging errors in stdout capture; **not** abort cause. Route/evidence captured via `bot_reply_completed` / `http_request` events.

Track as ops/logging hygiene; not in scope of RETRY2 product milestone.

---

## Frozen neighbors

| Suite | Pin check |
|-------|-----------|
| RETRY1 live artifacts + audit | ✅ unchanged |
| Preflight-abort attempt #1 + audit | ✅ unchanged |
| S62 / S63 | ✅ unchanged |
| Widget matrix | ✅ `f4eecf75…` |

---

## STOP

- **No rerun** without new owner GO.
- **No product code** in this audit checkpoint.
- **Retry2 artifacts @ `cbbdb35` byte-identical** — governance pins only.
- **`A9_PATIENT_SCOPE_AUTHORITY`** remains until post-E2E closeout after live PASS.
