# FINAL scope/widget E2E retry3 — manual review audit (append-only)

**Date:** 2026-07-26  
**Baseline:** `341c1eb` (`codex/stage-a`)  
**Measurement:** `final_scope_widget_e2e_retry3`  
**Automated verdict:** `AUTOMATED_PASS` (8/8 HTTP, 34/34 provider calls, exit 0)  
**Owner manual verdict:** **FAIL** (quality + widget integrity)  
**Authority:** `A9_PATIENT_SCOPE_AUTHORITY` **must remain** · Retry1/2/3 live artifacts **immutable**

This document is an **append-only incident capture**. Frozen Retry3 artifacts under `evals/v5/artifacts/final_scope_widget_e2e_retry3_*` are **not edited**.

---

## Incident summary

Retry3 live proved typed UI TurnFrame authority (planner skip T2/T6/T7, no `target_fullcontext_error`). Automated gates passed. Owner manual review found **5/8 turns FAIL** on response quality and follow-up ref integrity. Primary defect: dispatch/composer path receives neutral `user_message="продолжить"` while governed UI action semantics exist only on session/request ctx — Composer generates generic welcome/clarify prose instead of scoped price answers.

| Layer | Retry2 | Retry3 live | Owner gap |
|-------|--------|-------------|-----------|
| Planner on typed click | partial frame → error | skipped ✅ | — |
| TurnFrame / EffectiveScope | broken | correct ✅ | — |
| `response_stage` / dispatch route | error or wrong | materialized ✅ | — |
| Composer `user_message` | `продолжить` | `продолжить` ❌ | meaning lost |
| Widget refs | — | `price:None/...` on T2/T4 ❌ | invalid |

---

## Frozen artifact pins (@ `341c1eb`)

| Artifact | SHA-256 |
|----------|---------|
| `final_scope_widget_e2e_retry3_attempt.json` | `c3f4fe0cab32ac0a4e94c3b140f10f415036c6f34cffc8463975be47920e66d8` |
| `final_scope_widget_e2e_retry3_call_ledger.jsonl` | `1eeed9f6682e849020e54a51db8a0502046b69993ebc8f5bf74350d6a321dbd4` |
| `final_scope_widget_e2e_retry3_live_stdout.log` | `1b74cc08844a02c540231167fe91dfac25a5f0edeee441442c550633107b7e49` |
| `final_scope_widget_e2e_retry3_result.json` | `bbab70c9e55392d037921c091a1ed75c26cf06a6673d9d3181cbe650d3c1fb81` |
| `final_scope_widget_e2e_retry3_raw.json` | `bbab70c9e55392d037921c091a1ed75c26cf06a6673d9d3181cbe650d3c1fb81` |
| `final_scope_widget_e2e_retry3_manifest.json` | `c64e4054e5107c88e0ad69478100b6310fd4ea2ea41021034e535d5caa3cb3d3` |
| `final_scope_widget_e2e_retry3_manual_review.json` | `8ebd862da11c437f74f1f1cafd491786f9a03191562a0de9fd21f651bb59d3f5` |
| `final_scope_widget_e2e_retry3_audit.log` | `f333a52f3a707f8ed8ff1249bf9075acadc34195d146ffbaddc1b81899ebbea4` |

**Ledger (completed):** ingress=5, planner=5, boundary=8, composer=8, verifier=8, total=34.  
**Matrix hash (immutable):** `f4eecf7532481a288d1db6a6ee107dd147117dae44afc991451836dd3589434f`

---

## Per-turn owner verdict

| Turn | ID | Endpoint | Owner | Issue |
|------|-----|----------|-------|-------|
| **T1** | `fsw_turn_01_implant_broad` | `/ask` | **FAIL** | Broad implantation price overview too long: payment stages, package composition, long bonus list. Expected compact 2–4 anchors + scale prompt + 3 scope buttons. |
| **T2** | `fsw_turn_02_scope_full_arch_click` | `/ask` | **FAIL** | `target:ui_scope/implantation/full_arch` → welcome stub instead of full_arch scoped prices. Dispatch `response_stage=scoped_family_price` correct; Composer got `продолжить`. Widget shows invalid `price:None/stages`, `price:None/includes`. |
| **T3** | `fsw_turn_03_extent_correction_one_tooth` | `/ask` | **PASS** | Free-text one-tooth correction → scoped implant prices. |
| **T4** | `fsw_turn_04_implant_full_arch_a9_stream` | `/ask/stream` | **FAIL (widget)** | Answer text correct (All-on-4/6 prices). Widget payload contains invalid `price:None/stages`, `price:None/includes` (no concrete `service_id`). |
| **T5** | `fsw_turn_05_prosthetics_broad` | `/ask` | **PASS** | Broad prosthetics price acceptable. |
| **T6** | `fsw_turn_06_scope_one_tooth_click` | `/ask` | **FAIL** | Stage-nav buttons correct; answer text is generic service menu, not `stage_clarify` for prosthetics one_tooth. Composer got `продолжить`. |
| **T7** | `fsw_turn_07_stage_implant_placed_click` | `/ask` | **FAIL** | `target:ui_stage/prosthetics/implant_placed` → clarify prompt instead of crown price on implant. Composer got `продолжить`. |
| **T8** | `fsw_turn_08_prosthetics_a9_implant_placed_stream` | `/ask/stream` | **PASS** | Free-text A9 crown price after implant placed. |

**Score:** PASS 3/8 · FAIL 5/8 (T4 answer OK, widget FAIL).

---

## Live evidence (representative)

### T2 — typed scope click

| Field | Value |
|-------|-------|
| `nav_ref` | `target:ui_scope/implantation/full_arch` |
| `current_ui_scope_action` | `{topic: implantation, extent: full_arch, provenance: ui_scope_ref}` ✅ |
| `typed_ui_turn_frame_used` | `true` ✅ |
| `runtime_turn_frame.intent` | `price_lookup` ✅ |
| `user_text` / Composer input | `продолжить` ❌ |
| `response_stage` | `scoped_family_price` ✅ |
| `answer_text` | Generic welcome ❌ |
| `quick_replies` | `price:None/stages`, `price:None/includes` ❌ |

Source: `evals/v5/artifacts/final_scope_widget_e2e_retry3_live_stdout.log` (`turn_number=2`, `typed_ui_turn_frame_used`).

### T4 — stream widget integrity

Answer prose matches full_arch All-on prices. `quick_replies` refs use `price:None/...` because `matched_service_id=null` and materializer emits `price:{plan.service_id}/...` without guard.

Source: `evals/v5/artifacts/final_scope_widget_e2e_retry3_result.json` (turn 4 `body.quick_replies`).

---

## Non-blocking incidents

| Item | Status |
|------|--------|
| WinError 32 log rollover | non-blocking (retry2/retry3 pattern) |
| Retry3 rerun | **blocked** without owner approval |

---

## Next milestone (governance only — implementation blocked)

**Name:** `FINAL_SCOPE_POST_RETRY3_COMPOSER_ACTION_CONTEXT`

Seam audit: `docs/evidence/final_scope/FINAL_SCOPE_POST_RETRY3_COMPOSER_ACTION_CONTEXT_SEAM_AUDIT.md`  
TASK: `TASK.md` § FINAL_SCOPE_POST_RETRY3_COMPOSER_ACTION_CONTEXT

**STOP** until owner GO on implementation.
