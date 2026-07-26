# FINAL scope/widget E2E retry4 — manual review audit (append-only)

**Date:** 2026-07-26  
**Baseline:** `5ff9893` (`codex/stage-a`)  
**Live baseline commit (frozen capture):** `084203e51581c8074cbaf519fffb530de1685037`  
**Measurement:** `final_scope_widget_e2e_retry4`  
**Automated verdict:** `AUTOMATED_PASS` (8/8 HTTP, 34/34 provider calls, exit 0)  
**Owner manual verdict:** **PASS** (8/8)  
**Canonical owner/product verdict:** **PASS**  
**Frozen artifact `final_verdict` field:** `PENDING_MANUAL_REVIEW` (immutable live capture — **not edited**)

This document is an **append-only owner manual review capture**. Frozen Retry4 artifacts under `evals/v5/artifacts/final_scope_widget_e2e_retry4_*` are **not edited**.

---

## Verdict summary

| Layer | Retry3 (manual) | Retry4 live | Owner closeout |
|-------|-----------------|-------------|----------------|
| Typed UI TurnFrame / planner skip T2/T6/T7 | ✅ | ✅ | PASS |
| Composer governed action context | ❌ | ✅ | PASS |
| `price:None/...` widget refs | ❌ | ✅ none | PASS |
| Broad-family T1 compact overview | ❌ too long | ✅ accepted | PASS |
| T2 full_arch scoped prices | ❌ | ✅ | PASS |
| T6 stage clarification | ❌ | ✅ concise | PASS |
| T7 crown price on implant_placed | ❌ | ✅ | PASS |

**Score:** PASS **8/8**.

---

## Frozen artifact pins (@ `5ff9893`)

| Artifact | SHA-256 |
|----------|---------|
| `final_scope_widget_e2e_retry4_attempt.json` | `3459868df40d47c841ad2ef4eacb38a69be7bb73b42694af30279940dfabc0df` |
| `final_scope_widget_e2e_retry4_call_ledger.jsonl` | `1028f978742ed84480a9f6d22c0b86110bbcecfd3115ccfd55d19c4d9c7112ae` |
| `final_scope_widget_e2e_retry4_live_stdout.log` | `4e140d20b4ffee4abdcf23998e9391ae6e2bf4ac23a1082b20c8a483ddac60eb` |
| `final_scope_widget_e2e_retry4_result.json` | `8778278802f4f4f474cfe8dbb4118f684208a1605aec5cc40b5b3bf003207a03` |
| `final_scope_widget_e2e_retry4_raw.json` | `8778278802f4f4f474cfe8dbb4118f684208a1605aec5cc40b5b3bf003207a03` |
| `final_scope_widget_e2e_retry4_manifest.json` | `46f5ea55537e3514dd8b40d44f37d08f60a4324646aabbecc74d444acc1fba90` |
| `final_scope_widget_e2e_retry4_manual_review.json` | `4bd76e3eb73d25b2002fcb078ce536b7b4acf7ffade8098e86bb0dc570bb2459` |
| `final_scope_widget_e2e_retry4_audit.log` | `2f55b8991b2775e02f798daf948057bd8d7f73208a66993be18d772a43a0ac2a` |

**Matrix hash (immutable):** `f4eecf7532481a288d1db6a6ee107dd147117dae44afc991451836dd3589434f`  
**Ledger (completed):** ingress=5, planner=5, boundary=8, composer=8, verifier=8, total=34.

---

## Per-turn owner verdict (binding manual rubric)

| Turn | ID | Rubric | Owner | Notes |
|------|-----|--------|-------|-------|
| **T1** | `fsw_turn_01_implant_broad` | `compact_overview` | **PASS** | 704 chars accepted as compact; 2 anchors + scale + 3 scope buttons |
| **T2** | `fsw_turn_02_scope_full_arch_click` | `full_arch_prices` | **PASS** | All-on-4/6 by brand; governed scoped_family_price |
| **T3** | `fsw_turn_03_extent_correction_one_tooth` | — | **PASS** | Free-text one-tooth correction |
| **T4** | `fsw_turn_04_implant_full_arch_a9_stream` | — | **PASS** | Stream All-on prices; no invalid widget refs |
| **T5** | `fsw_turn_05_prosthetics_broad` | — | **PASS** | Broad prosthetics acceptable |
| **T6** | `fsw_turn_06_scope_one_tooth_click` | `concise_stage_clarification` | **PASS** | Concise clarify; wording can be refined later (non-blocking) |
| **T7** | `fsw_turn_07_stage_implant_placed_click` | `crown_price` | **PASS** | Crown price present; 25 000 ₽ and 31 000 ₽ grounded in different structured offers — distinction can be explained more clearly later (non-blocking) |
| **T8** | `fsw_turn_08_prosthetics_a9_implant_placed_stream` | — | **PASS** | Free-text A9 crown price stream |

---

## Non-blocking notes (deferred)

| ID | Topic | Disposition |
|----|-------|-------------|
| NB-1 | T1 length (704 chars) | Accepted as compact for E2E closeout |
| NB-2 | T6 wording precision | Future copy polish; not a product blocker |
| NB-3 | T7 dual price anchors (25k vs 31k) | Both grounded in structured offers; clearer explanation deferred |
| NB-4 | WinError 32 logging rollover on Windows | Harness/env artifact; deferred; not a product blocker |

---

## Authority / lineage

- `A9_PATIENT_SCOPE_AUTHORITY=1` during live run — **flag retained** until closeout implementation (separate owner GO).
- Retry1/Retry2/Retry3 live artifacts remain **immutable**.
- No Retry5. No re-run of Retry4 live.

---

## STOP

Owner manual **PASS** captured. Proceed to **FINAL_SCOPE_WIDGET_E2E_CLOSEOUT** governance → implementation (flag removal) only on separate owner GO.
