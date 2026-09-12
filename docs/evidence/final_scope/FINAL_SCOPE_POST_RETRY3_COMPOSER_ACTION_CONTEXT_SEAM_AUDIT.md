# FINAL_SCOPE_POST_RETRY3 — Composer action context seam audit (read-only)

**Date:** 2026-07-26  
**Baseline:** `341c1eb` (`codex/stage-a`)  
**Authority:** Retry3 live `AUTOMATED_PASS` · owner manual **FAIL** · `A9_PATIENT_SCOPE_AUTHORITY` **must remain**

**Scope:** governance / read-only checkpoint · **NO LIVE / NO LLM / NO PRODUCT CODE / NO Retry4**

Manual incident: `docs/evidence/final_scope/FINAL_SCOPE_WIDGET_E2E_RETRY3_MANUAL_REVIEW_AUDIT.md`

---

## Verdict

TYPED_UI_TURNFRAME fixed RETRY2's planner partial-frame crash. Retry3 live proves typed UI authority through dispatch (`response_stage`, `scope_price_topic`, planner=0 on T2/T6/T7). Owner manual review exposes the **next seam**: Composer still receives neutral `user_message="продолжить"` and has **no structured governed-action context**. Dispatch routes correctly; generated prose and some widget refs do not.

| Failure class | Turns | Symptom | Root seam |
|---------------|-------|---------|-----------|
| Composer meaning loss | T2, T6, T7 | Welcome/menu/clarify instead of scoped price or stage_clarify | `user_message` only; governed click not in Composer invocation |
| Broad-family verbosity | T1 | Long overview with stages/bonuses | `broad_family_price` directives lack compact policy |
| Invalid price refs | T2, T4 | `price:None/stages`, `price:None/includes` | Service-specific followups emitted with `plan.service_id=None` |

---

## Shared runtime chain (Retry3 typed click — T2 representative)

```
POST /ask
  → run_pre_resolver_turn()
       AC1: UiScopeAction on ctx ✅
       q := "продолжить" when ref-only click (ingress neutralization)
  → try_run_typed_ui_planner_turn()     [T2/T6/T7: planner skipped ✅]
       publish_typed_ui_turn_frame()     [authoritative commercial TurnFrame ✅]
  → orchestrate_target_fullcontext_turn()
  → run_target_fullcontext_runtime_turn()
       ├ load_runtime_turn_frame()       [typed frame ✅]
       ├ resolve_effective_scope()       [UiScopeAction merge ✅]
       ├ execute_target_medical_boundary_classification(user_message="продолжить")
       └ dispatch_target_turn_frame_response()
            └ response_stage=scoped_family_price ✅
            └ run_target_offline_boundary_enforced_fullcontext_response(
                   user_message="продолжить"  ❌  → Composer
               )
```

Free-text path (T1,T3,T4,T5,T8): unchanged; planner runs; same Composer boundary.

---

## Observed on T2 (live @ `341c1eb`)

| Layer | Value |
|-------|-------|
| `nav_ref` | `target:ui_scope/implantation/full_arch` |
| `current_ui_scope_action` | `{topic: implantation, extent: full_arch, provenance: ui_scope_ref}` ✅ |
| `typed_ui_turn_frame_used` | `true` ✅ |
| `runtime_turn_frame` | `intent=price_lookup`, `topic=implantation`, `aspects=["price"]` ✅ |
| `user_text` / boundary / Composer | `продолжить` ❌ |
| `response_stage` | `scoped_family_price` ✅ |
| `meta.intent` | `content` (Composer output) ❌ |
| `answer_text` | Generic welcome ❌ |
| `quick_replies` | `price:None/stages`, `price:None/includes` ❌ |

T6/T7 structurally identical: correct stage buttons or dispatch stage, Composer prose irrelevant because `user_message` carries no click semantics.

---

## Why TYPED_UI_TURNFRAME is insufficient

Typed UI TurnFrame fixes **planner authority** and enables dispatch to `scoped_family_price` / `stage_clarify`. It does **not** pass governed action into:

1. `TargetComposerRequest.user_message` (still ingress-neutralized `продолжить`)
2. `TargetComposerInvocation` / SDK message template (no action context block)
3. `response_directives_json` (stage known to dispatch but not as Composer-primary signal)

Composer system policy treats `USER_MESSAGE` as the patient's question. With `продолжить`, model defaults to generic greeting/clarify despite `PRIMARY_EVIDENCE` and `response_stage` on the spec side.

**EffectiveScope + TurnFrame alone do not substitute** for explicit Composer action context on typed clicks.

---

## Follow-up integrity seam (`price:None`)

`core/target_response_followup_materializer.py` builds price followup refs as:

```
ref = f"price:{plan.service_id}/{followup_id}"
```

When `plan.service_id` is `None` (multi-offer family overview / scoped family without single service), refs become `price:None/stages` etc. Automated gates do not reject these strings today.

**Policy (owner):**

- Never emit `price:None/...`
- Service-specific price refs only when concrete `service_id` is bound
- Multi-service family answers: use existing valid authored refs **or** omit service-specific price buttons
- No temporary family route without architecture decision

---

## Target product fix (offline — owner design)

**Name:** `FINAL_SCOPE_POST_RETRY3_COMPOSER_ACTION_CONTEXT`

### `TargetComposerActionContext` (optional, typed)

Built **only** from validated session-bound UI action (`current_ui_scope_action` / `current_ui_stage_action` on request ctx). Fields:

| Field | Source |
|-------|--------|
| `action_kind` | `ui_scope` \| `ui_stage` |
| `topic` | governed action topic |
| `extent` | `UiScopeAction.extent` when scope click |
| `stage` | `UiStageAction.stage` when stage click |
| `governed_ref` | full ref string (`target:ui_scope/...` or `target:ui_stage/...`) |
| `response_stage` | dispatch-resolved stage (`scoped_family_price`, `stage_clarify`, …) |

### Wiring rules

| Rule | Requirement |
|------|-------------|
| Priority | Governed `TargetComposerActionContext` **overrides** neutral `user_message` for Composer meaning |
| Ingress | Keep `q="продолжить"` for logging/ingress if needed; **not** Composer authority |
| Forbidden sources | Button label, `продолжить`, free-text echo |
| Scoped click | Directives → direct scoped price answer (full_arch, implant_placed crown, etc.) |
| `stage_clarify` | Directives → short question about shown stage buttons only |
| Free-text | Unchanged — no action context unless real user text |
| Verifier | **Do not change** light semantic verifier |
| Parity | `/ask` and `/ask/stream` identical Composer wiring |

### Broad-family response policy (T1)

| Rule | Requirement |
|------|-------------|
| Mode | `broad_family_price` compact overview |
| Price anchors | 2–4 only |
| Omit | payment stages, package composition, long bonus lists |
| Close | Short scale-clarify phrase |
| Widget | 3 typed `target:ui_scope/{topic}/{extent}` buttons |

---

## Acceptance matrix (protected — implementation)

Matrix blob: `f4eecf7532481a288d1db6a6ee107dd147117dae44afc991451836dd3589434f` (**immutable**)

| ID | Scenario | Expected |
|----|----------|----------|
| AM-1 | T1 broad implantation price | Compact overview; 2–4 anchors; scale prompt; 3 scope buttons; no payment-stage/bonus wall |
| AM-2 | T2 typed `full_arch` click | Scoped full_arch prices; Composer invocation has `TargetComposerActionContext`; no welcome stub |
| AM-3 | T3 free-text one-tooth correction | Scoped implant prices (unchanged) |
| AM-4 | T4 stream full_arch A9 | Correct prices; **no** `price:None/...` in widget |
| AM-5 | T5 broad prosthetics | Acceptable broad answer (unchanged PASS bar) |
| AM-6 | T6 typed `one_tooth` prosthetics | `stage_clarify` concise text; stage buttons; action context in Composer |
| AM-7 | T7 typed `implant_placed` stage | Crown price on implant; action context in Composer |
| AM-8 | T8 free-text A9 crown | Crown price stream (unchanged) |
| AM-9 | Invalid ref guard | `price:None/...` fail-closed at materialization or policy |
| AM-10 | Free-text regression | Ordinary medical / clarify paths unchanged |
| AM-11 | Endpoint parity | T4/T8 stream ≡ non-stream Composer action wiring |

Offline proof: real-runtime replay T1–T8 without LIVE/LLM.

---

## Forbidden (this milestone)

- LIVE / Retry4 rerun
- Verifier changes
- Regex / phrase lists
- A9 prompt tuning
- New selectors or legacy fallback routes
- `A9_PATIENT_SCOPE_AUTHORITY` removal
- Edit frozen Retry1/2/3 live artifacts

---

## STOP

Product implementation blocked until owner **GO** on `FINAL_SCOPE_POST_RETRY3_COMPOSER_ACTION_CONTEXT` allowlist in `TASK.md`.
