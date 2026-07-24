# TASK — C2 Native TurnFrame cleanup (Cleanup-series)

**Baseline:** `codex/stage-a` / `3f94e69` (C2d-D2 closeout) · **NO LIVE / NO LLM / NO A9 changes**

**Authority:** Owner-approved C2 (`OWNER APPROVED C2`, 2026-07-24).

## Goal

Make **native TurnFrame** the sole Planner product authority: one Planner LLM call → runtime TurnFrame → target FullContext. Remove `legacy_plan`, TurnFrame adapter, shadow product naming, resolver fallback (second routing LLM), legacy session dual-read, and provably dead loader fallbacks — **without** changing FullContext answer semantics, Composer/Verifier/boundary/evidence, client data, or frozen/A9 artifacts.

**Target chain after C2:**

```text
HTTP → shared guards → one Planner LLM → native TurnFrame → session hydration
→ medical boundary → FullContext → Composer → lightweight Verifier → widget/session
```

## Process (mandatory)

1. **Governance commit:** only `TASK.md` → push → **PRE-CODE checker ✅**
2. If PRE-CODE ❌: STOP, fix only `TASK.md`, governance correction, repeat PRE-CODE until ✅
3. **C2a** implementation → tests → **C2a checkpoint checker ✅** → commit + push → clean/synced
4. **C2b** → C2b checker ✅ → commit + push
5. **C2c** → C2c checker ✅ → commit + push
6. **C2c-correction** → C2c-correction checker ✅ → commit + push
7. **C2c-dead-clarify** → checker ✅ → commit + push → **STOP before C2d**
8. **C2d-D1** → D1 checker ✅ → commit + push
9. **C2d-D2** → COMPLETION checker ✅ → commit + push
10. **C2e** governance → PRE-CODE checker ✅ → **C2e** implementation → COMPLETION checker ✅ → commit + push → **CLEANUP_SERIES_COMPLETE / STOP** (no C2f)

No product WIP before PRE-CODE ✅. No checkpoint advance on checker ❌.

## Forbidden

- Second Planner/Resolver/classifier LLM on product path
- `legacy_plan` / TurnPlan as target authority
- `DecisionFrame` as target response authority
- Resolver fail-open / `resolve_with_fallback` on product path
- RAG/retrieval reintroduction
- Legacy session dual-read after C2c cutover
- `patient_scope` product authority (routing/pricing/strategy/boundary/evidence/UI)
- Composer/Verifier/boundary/evidence changes
- Client MD/structured data changes
- Live/LLM runs; A9 matrix/harness rerun
- Frozen S47/S50/S53/S55/S58/S62/S63/S66 artifact byte changes
- Protected acceptance spec/golden/target/current edits to greenwash
- Merge/push to `main`
- Files outside checkpoint allowlist without governance correction + PRE-CODE ✅

## Allowed

- Governance TASK; PRE-CODE / checkpoint / COMPLETION checkers
- Product code strictly per checkpoint allowlist
- Fake/spy offline tests; import firewall tests
- Docs updates listed below
- Push only to `origin/codex/stage-a`

---

## Read-only audit summary (baseline `5c3d3bb`)

### Current product wiring (verified call sites)

| Step | File | Active today |
|------|------|--------------|
| `/ask` orchestration | `app.py:296–322` | `run_pre_resolver_turn` → `run_resolver_turn` → `orchestrate_target_fullcontext_turn` |
| Planner + dual branch | `core/turn_planner_llm.py:558–685` | 1× LLM → `build_turn_frame_from_raw` (shadow) + `_validate_plan` → `legacy_plan` |
| Ctx publish shadow | `orchestration/resolver_turn.py:59–61` | `record_planner_attempt_shadow(attempt)` |
| Ctx publish legacy | `resolver_turn.py:62–64` | `turn_plan_to_decision_frame` + `publish_turn_plan` |
| Resolver fallback | `resolver_turn.py:96–154` | `resolve_with_fallback` when `legacy_plan is None` (2nd LLM) |
| Target load frame | `core/target_runtime_turn_frame_bridge.py:31–45` | reads `turn_frame_shadow*` ctx keys |
| Session hydration | `core/target_runtime_turn_frame_hydration.py:38–72` | `target_runtime_state.last_service_id` (not `last_subject`) |
| Session write | `core/target_runtime_session.py:95–140` | writes `target_runtime_state` + **dual-write** `set_last_subject` |
| Resolver import (product) | `orchestration/resolver_turn.py:17` | only active product importer of `resolver.py` |

### Guard parity (baseline = current target shadow_frame path)

| Guard / helper | Mutates | Target uses result? | C2 action |
|--------------|---------|---------------------|-----------|
| `_apply_protocol_choice_guard` | `legacy_plan` only | **No** — TurnFrame built from raw JSON before guard | **DELETE** with legacy branch (C2b) |
| `_apply_focus_followup_enrichment` | `legacy_plan` only | **No** — hydration uses `target_runtime_state` | **DELETE** (C2b) |
| `_session_focus_service_id` | legacy guards only | **No** | **DELETE** (C2b) |
| `_pending_clarify_prompt_block` | planner prompt | **No** — no target writer for `pending_clarify` | **DELETE** reads (C2b/C2c) |
| `hydrate_target_runtime_turn_frame_from_session` | TurnFrame | **Yes** | **KEEP** (C2c verify only) |
| `build_turn_frame_from_raw` | TurnFrame | **Yes** | **KEEP** — sole product builder |

**Do not port** legacy_plan-only guards to TurnFrame unless a **target** acceptance test proves dependency.

### Symbol disposition table

| Symbol / file | Active product callers | Offline / historical | Action |
|---------------|------------------------|-------------------|--------|
| `legacy_plan` / `TurnPlan` product path | `resolver_turn.py`, `turn_planner_llm.publish_turn_plan` | tests, `composer_flow`/`ask_turn` (not `/ask` target) | **DELETE** product use (C2b) |
| `turn_frame_shadow` ctx API | `target_runtime_turn_frame_bridge`, `resolver_turn`, `finalize_turn` telemetry | A9 eval contracts read `meta.metadata_first.turn_frame_shadow*` | **REPLACE** product with `runtime_turn_frame` (C2a); module **HISTORICAL** for evals |
| `core/turn_frame_adapter.py` | `turn_frame_shadow.record_turn_frame_shadow` only | unit tests | **DELETE** file (C2b) after product cut |
| `record_turn_frame_shadow` / adapter path | none on hot path | tests | **DELETE** (C2b) |
| `resolve_with_fallback` | `resolver_turn.py:118` | `resolver.py`, evals | **REMOVE** product call (C2b); **KEEP** `resolver.py` historical |
| `classify_intent` / `RESOLVER_OFF` path | `resolver_turn.py:105–115` | emergency bypass | **REMOVE** product path (C2b) |
| `TURN_PLANNER_ON` | `resolver_turn.py:52` | tests | **DELETE** flag — planner always on (C2b) |
| `RESOLVER_OFF` | `resolver_turn.py:30–32,105` | tests | **DELETE** product bypass (C2b) |
| `V5_RESOLVER_SHADOW_ON` | `resolver.py:19` | eval harness | **KEEP** in `resolver.py` (historical); no product reader |
| `RESOLVER_MODEL` / `config.py` | none after C2b | evals | **PRUNE** if orphan (C2b) |
| `last_subject` read | `turn_planner_llm`, `dialog_focus`, `follow_up_rewrite`, `query_selector`, `answer_planner` | tests | **REMOVE** product reads (C2c); remove dual-write (C2c) |
| `set_last_subject` write | `target_runtime_session.py:134` | tests | **DELETE** dual-write (C2c) |
| `pending_clarify` | none (legacy `ask_turn`/`composer_flow` deleted S69) | tests | **DELETE** session API + writer (C2c-dead-clarify) |
| `turn_plan_from_ctx` / `publish_turn_plan` | deleted with `ask_turn`/`composer_flow` (S69) | tests, evals | **HISTORICAL** only; no product path |
| `DecisionFrame` target authority | `resolver_turn` → `record_decision_frame_ctx` | contracts, evals | **REMOVE** product authority (C2b); contract **KEEP** |
| `prices.json` / `price_offers.json` fallback | `query_selector.py`, `core/price_offers.py`, `startup_check.py` | scripts | **AUDIT** C2d; delete only if no active target caller |
| `core/patient_playbook.py` loader fallbacks | startup / target selectors | tests | **AUDIT** C2d |
| A9 eval harness | reads `turn_frame_shadow` in response meta | frozen artifacts | **DO NOT CHANGE** A9 bytes; product may alias telemetry keys for contract tests |

---

## Checkpoint C2a — native runtime TurnFrame contract

**Goal:** Product publishes/reads TurnFrame via neutral runtime API; no shadow naming on product path.

### C2a changes

1. **New** `core/runtime_turn_frame.py`: `publish_runtime_turn_frame`, `load_runtime_turn_frame_snapshot`, `get_runtime_turn_frame_status`, constants `RUNTIME_FRAME_STATUS_*`, ctx keys `runtime_turn_frame`, `runtime_turn_frame_status`, `runtime_turn_frame_reason`.
2. `build_turn_frame_from_raw()` remains sole product builder from Planner JSON.
3. `core/target_runtime_turn_frame_bridge.py` reads **runtime** ctx keys only (not `turn_frame_shadow`).
4. `orchestration/resolver_turn.py` calls runtime publisher instead of `record_planner_attempt_shadow` (legacy_plan branch may remain until C2b).
5. `core/turn_frame_shadow.py` — **no product imports** after C2a; kept for historical eval contract imports only.
6. `partial` → target dispatch (no resolver); `not_available`/`degraded` → existing fail-closed.
7. `core/metadata_first_observability.py` — add runtime telemetry keys; **may** retain `turn_frame_shadow*` aliases in response meta for A9 offline contract tests (no A9 artifact edits).

### C2a allowlist

| File | Change |
|------|--------|
| `core/runtime_turn_frame.py` | **new** |
| `core/target_runtime_turn_frame_bridge.py` | read runtime keys |
| `orchestration/resolver_turn.py` | publish via runtime API |
| `core/turn_frame_shadow.py` | strip product hot-path; historical only |
| `core/metadata_first_observability.py` | runtime + optional alias keys |
| `orchestration/finalize_turn.py` | telemetry field names if needed |
| `tests/test_c2a_runtime_turn_frame_offline.py` | **new** |
| `tests/test_c2_import_firewall_offline.py` | **new** — no product import of `turn_frame_shadow` |
| `tests/test_s61_target_fullcontext_runtime.py` | update ctx key assertions |
| `tests/test_turn_frame_from_raw.py` | unchanged expectations |
| `tests/test_metadata_first_observability.py` | adjust only if telemetry keys change |

### C2a acceptance

- raw → runtime TurnFrame; ctx publish/load; `ok` + usable `partial`; `not_available`/`degraded` fail-closed
- target bridge uses runtime keys
- product import firewall: active product modules do not import `core.turn_frame_shadow`
- `patient_scope` not used for routing/evidence/price/UI (existing tests)

### C2a tests

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-c2a-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_c2a_runtime_turn_frame_offline.py `
  tests/test_c2_import_firewall_offline.py `
  tests/test_turn_frame_from_raw.py `
  tests/test_s61_target_fullcontext_runtime.py `
  -q
```

---

## Checkpoint C2b — remove legacy_plan and resolver fallback

**Goal:** One Planner LLM call; frame-first `PlannerAttempt`; no resolver/DecisionFrame on product path.

### C2b changes

1. `core/turn_planner_llm.py` — frame-only outcome; delete `_validate_plan` product path, `_project_legacy_turn_plan_raw`, legacy guards, `publish_turn_plan`, `turn_plan_to_decision_frame`, `plan_turn` legacy wrapper.
2. `contracts/planner_attempt.py` — remove `legacy_plan`; frame-first status invariants (`ok`/`partial`/`not_available`/`degraded`).
3. `orchestration/resolver_turn.py` → **`orchestration/planner_turn.py`**; `run_resolver_turn` → `run_planner_turn`; publish runtime frame; **no** `resolve_with_fallback`, **no** `classify_intent`, **no** DecisionFrame authority.
4. `app.py` — import `run_planner_turn`; remove resolver terminology on product path.
5. `core/turn_frame_adapter.py` — **delete** file.
6. `config.py` — remove `TURN_PLANNER_ON`, `RESOLVER_OFF`, orphan `RESOLVER_MODEL` if unreferenced.
7. `resolver.py` — **no** active product import; classify as historical/offline.

### C2b allowlist

| File | Change |
|------|--------|
| `core/turn_planner_llm.py` | frame-only planner |
| `contracts/planner_attempt.py` | frame-first contract |
| `contracts/turn_plan.py` | **KEEP** (historical/tests); no product import |
| `orchestration/planner_turn.py` | **new** (from resolver_turn) |
| `orchestration/resolver_turn.py` | **delete** after rename |
| `app.py` | planner_turn wiring |
| `config.py` | flag prune |
| `core/turn_frame_adapter.py` | **delete** |
| `core/metadata_first_observability.py` | remove DecisionFrame product hooks if dead |
| `tests/test_c2b_no_resolver_offline.py` | **new** — spy: 1 planner call, 0 resolver |
| `tests/test_turn_planner_llm.py` | frame-first assertions (update expectations) |
| `tests/test_planner_attempt_contract.py` | frame-first contract |
| `tests/test_turn_frame_shadow.py` | historical-only scope / rename tests |
| `tests/test_s69_checkpoint_a_offline.py` | no resolver on planner failure |
| `tests/test_s65_authority_switch_offline.py` | update mocks (`run_planner_turn`) |
| `tests/test_s67_legacy_isolation_offline.py` | update if imports reference resolver_turn |
| `tests/test_s61_correction_target_runtime.py` | update `resolver_turn` → `planner_turn` mocks/imports |
| `tests/test_s62_correction_offline.py` | update `resolver_turn` → `planner_turn` imports if broken by rename |
| `tests/test_s63_correction_offline.py` | update `resolver_turn` → `planner_turn` imports if broken by rename |
| `tests/test_turn_plan_protocol_guard.py` | **delete** or move to historical — guards removed |

### C2b hard gates

- Normal turn: exactly **one** Planner backend call (fake/spy)
- Planner malformed/failure: **zero** resolver calls; controlled fail-closed
- Partial frame: **zero** resolver calls
- Target never uses DecisionFrame authority
- Composer/Verifier call counts unchanged for materialized turn

### C2b tests

```powershell
$bt = Join-Path $env:TEMP ("demo-bot-c2b-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_c2b_no_resolver_offline.py `
  tests/test_c2_import_firewall_offline.py `
  tests/test_turn_planner_llm.py `
  tests/test_planner_attempt_contract.py `
  tests/test_turn_frame_from_raw.py `
  tests/test_s61_target_fullcontext_runtime.py `
  tests/test_s69_checkpoint_a_offline.py `
  tests/test_s67_legacy_isolation_offline.py `
  -q
```

---

## Checkpoint C2c — session compatibility cleanup

**Goal:** Planner + target use `target_runtime_state` only; no `last_subject` product reads/dual-write.

### C2c changes

1. `core/target_runtime_session.py` — remove `set_last_subject` dual-write (`:134–140`).
2. `core/turn_planner_llm.py` — remove `_session_focus_service_id`, pending_clarify prompt (already deleted guards in C2b).
3. `session.py` — stop exporting `last_subject`/`pending_clarify` for product (remove or deprecate helpers after last reader gone).
4. `core/dialog_focus.py` — remove `turn_plan_from_ctx`, `_focus_from_last_subject` product paths; keep observability if still used by `finalize_turn`.
5. `core/follow_up_rewrite.py` — remove `last_subject` reads (`focus_from_legacy_session` chain).
6. `query_selector.py` — remove `last_subject` read in price routing (`:258–259`) if still present.
7. `orchestration/pre_resolver_turn.py` — verify `/reset` clears target state (full `mem_reset` already deletes session).
8. **Do not** add `target_runtime_state.pending_clarify` — field is dead (writer only in legacy `composer_flow`).

### C2c allowlist

| File | Change |
|------|--------|
| `core/turn_planner_llm.py` | remove residual `_session_focus_service_id`, `_pending_clarify_prompt_block` if any remain after C2b |
| `core/target_runtime_session.py` | remove dual-write |
| `core/target_runtime_turn_frame_hydration.py` | verify session-only inputs |
| `session.py` | prune legacy focus/clarify product API |
| `core/dialog_focus.py` | remove legacy session/plan readers |
| `core/follow_up_rewrite.py` | remove legacy session reads |
| `query_selector.py` | remove `last_subject` read |
| `core/answer_planner.py` | remove `get_last_subject` if still referenced |
| `tests/test_c2c_session_migration_offline.py` | **new** |
| `tests/test_s62_correction_offline.py` | session continuity |
| `tests/test_s63_correction_offline.py` | session continuity |
| `tests/test_vague_price_followup.py` | offline/unit only (no live) |
| `tests/test_vague_doctor_followup.py` | offline/unit only |
| `tests/test_focus_context.py` | update if product API removed |
| `tests/test_follow_up_rewrite.py` | update legacy expectations |

### C2c acceptance

- «All-on-4?» → «сколько стоит?»; «кто делает?»; payment follow-up; ref-click
- Fresh clinic-wide doctors question without invented `service_id`
- Session continuity via `target_runtime_state` only
- Reset clears target state; terminal/error does not corrupt valid focus

---

## Checkpoint C2c-correction — service focus age + legacy API cleanup

**Prerequisite:** C2c checkpoint checker ✅ (`70b5aa3`).

**Goal:** Canonical `service_focus_age` from `target_runtime_state.service_focus_set_at_turn` + `session_turn_count`; unified age guard for all product consumers; remove dead `last_subject` / `subject_turn_age` API; rename telemetry source; update stale tests.

### C2c-correction audit (read-only, confirmed)

| Gap | Action |
|-----|--------|
| No target-owned focus age | Add `service_focus_set_at_turn`; compute `service_focus_age` |
| `subject_turn_age` not synced with target writer | Remove; use target timestamp only |
| Consumers use different freshness semantics | Single `read_age_guarded_service_focus()` helper |
| `pending_clarify` no **product** writer/reader | Legacy modules deleted (S69); **DELETE** session API + writer (C2c-dead-clarify) |
| Stale tests use `set_last_subject` | Migrate to `target_runtime_state` seed helpers |

### C2c-correction changes

1. `target_runtime_state.service_focus_set_at_turn` — set to `session_turn_count` on materialized response **with** `service_id`.
2. `read_age_guarded_service_focus(st)` — canonical helper; returns `None` when age > `max_service_focus_turn_age` (4).
3. Rename threshold: `max_subject_turn_age` → `max_service_focus_turn_age` in `routing.yaml` / `routing_loader.py`.
4. All product consumers (`dialog_focus`, `follow_up_rewrite`, `query_selector`, `answer_planner`, hydration) use canonical helper.
5. Terminal/error: no write to `target_runtime_state` (unchanged); focus ages on user turns.
6. Remove `last_subject` / `subject_turn_age` session API and field after last product reader gone.
7. `pending_clarify` API: superseded by **C2c-dead-clarify** (legacy modules deleted S69).
8. Telemetry: `DialogFocusSource` `"last_subject"` → `"target_runtime_state"`.
9. Update `test_answer_planner.py`, `test_dialog_focus_baseline.py`, related stale tests.

### C2c-correction allowlist

| File | Change |
|------|--------|
| `TASK.md` | governance + completion record |
| `core/target_runtime_session.py` | age field, canonical helper, clear focus |
| `core/target_runtime_turn_frame_hydration.py` | age guard on hydrate |
| `session.py` | remove `last_subject`/`subject_turn_age`; `clear_focus_context` uses target clear |
| `core/routing.yaml` | rename threshold |
| `core/routing_loader.py` | rename threshold field |
| `core/dialog_focus.py` | canonical helper + telemetry source |
| `core/follow_up_rewrite.py` | canonical helper; topic-change clear |
| `query_selector.py` | canonical helper |
| `core/answer_planner.py` | canonical helper |
| `contracts/dialog_focus.py` | source literal rename |
| `tests/test_c2c_service_focus_age_offline.py` | **new** |
| `tests/test_c2c_session_migration_offline.py` | age scenarios + seed updates |
| `tests/test_c2_import_firewall_offline.py` | extend firewall |
| `tests/test_answer_planner.py` | target_runtime_state seeds |
| `tests/test_dialog_focus_baseline.py` | target_runtime_state seeds |
| `tests/test_focus_context.py` | target focus clear |
| `tests/test_follow_up_session.py` | service focus age tests |
| `tests/test_follow_up_rewrite.py` | seed updates |
| `tests/test_vague_price_followup.py` | seed updates |
| `tests/test_vague_doctor_followup.py` | seed updates |
| `tests/test_s61_correction_target_runtime.py` | `_seed_target_runtime_state` helper |
| `tests/test_s62_correction_offline.py` | seed updates if needed |
| `tests/test_s63_correction_offline.py` | seed updates if needed |
| `tests/test_dialog_focus_contract.py` | threshold rename + target seeds |

### C2c-correction tests

```powershell
$bt = Join-Path $env:TEMP ("demo-bot-c2cc-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_c2c_service_focus_age_offline.py `
  tests/test_c2c_session_migration_offline.py `
  tests/test_c2_import_firewall_offline.py `
  tests/test_turn_planner_llm.py `
  tests/test_s62_correction_offline.py `
  tests/test_s63_correction_offline.py `
  tests/test_vague_price_followup.py `
  tests/test_vague_doctor_followup.py `
  tests/test_focus_context.py `
  tests/test_follow_up_rewrite.py `
  tests/test_follow_up_session.py `
  tests/test_answer_planner.py `
  tests/test_dialog_focus_baseline.py `
  tests/test_dialog_focus_contract.py `
  -q
```

### C2c-correction acceptance

- Age 0 after materialized service; increments per user turn; works until limit 4; stale focus ignored
- New materialized service turn resets timestamp; terminal/error do not rejuvenate
- Price/doctors/payment share same freshness helper
- Reset/sid isolation; no product `last_subject`/`subject_turn_age`/`pending_clarify` reads

---

## Checkpoint C2c-dead-clarify — remove orphaned pending_clarify session state

**Prerequisite:** C2c-correction checker ✅ (`13067dc`).

**Goal:** Remove dead `pending_clarify` session API/writer and orphaned `CLARIFY_STATE_ON`. Legacy `orchestration/ask_turn.py` and `orchestration/composer_flow.py` are deleted (S69, not importable). Preserve target terminal clarify/defer, `needs_clarification` in TurnFrame/ResponseSpec, and ordinary clarify answer text. **Do not** add new persistent clarify session state.

### C2c-dead-clarify audit (read-only, confirmed)

| Item | Status |
|------|--------|
| `orchestration/ask_turn.py`, `orchestration/composer_flow.py` | Deleted; not importable (S69) |
| Product readers of `pending_clarify` | None |
| `session.py` | Still has API + inline writer in `record_last_bot_payload` |
| `CLARIFY_STATE_ON` in `config.py` | Orphaned |

### C2c-dead-clarify changes

1. Remove `pending_clarify` from `_fresh_defaults`; strip legacy key on deserialize.
2. Remove `get_pending_clarify`, `set_pending_clarify`, `clear_pending_clarify`, `increment_pending_clarify_reask`, `pending_clarify_age`.
3. Remove inline `pending_clarify` write from `record_last_bot_payload` (even when `meta.clarify` present).
4. Remove `CLARIFY_STATE_ON` from `config.py`.
5. Update `docs/FLAGS_AND_STATUS.md` — remove claims that clarify-state flag works.
6. Delete `tests/test_clarify_state.py` (legacy-only; no shared semantics with target terminal clarify).
7. Fix TASK audit lines — do not reference `ask_turn`/`composer_flow` as active `pending_clarify` readers.

### Preserve

- Target terminal clarify/defer response path
- `needs_clarification` in TurnFrame / ResponseSpec
- Ordinary clarify answer text in responses
- No new persistent clarify session state

### C2c-dead-clarify allowlist

| File | Change |
|------|--------|
| `TASK.md` | governance + completion record |
| `session.py` | remove pending_clarify defaults/API/writer; strip on load |
| `config.py` | remove `CLARIFY_STATE_ON` |
| `docs/FLAGS_AND_STATUS.md` | remove dead clarify-state flag/docs |
| `tests/test_c2c_dead_clarify_offline.py` | **new** |
| `tests/test_c2_import_firewall_offline.py` | extend firewall if needed |
| `tests/test_clarify_state.py` | **delete** |

### C2c-dead-clarify tests

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-c2cdc-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_c2c_dead_clarify_offline.py `
  tests/test_c2c_session_migration_offline.py `
  tests/test_c2c_service_focus_age_offline.py `
  tests/test_c2_import_firewall_offline.py `
  tests/test_target_turn_frame_dispatch.py `
  tests/test_demo_target_turn_frame_bound_response.py `
  tests/test_s61_target_fullcontext_runtime.py `
  tests/test_s62_correction_offline.py `
  tests/test_s63_correction_offline.py `
  tests/test_turn_planner_llm.py `
  -q
python -m pytest -p no:cacheprovider --collect-only -q 2>&1 | Select-Object -Last 3
python -c "from evals.v5.s66_default_authority_live_contract import assert_frozen_s62_live_artifacts_unchanged, assert_frozen_s63_live_artifacts_unchanged; from tests.test_s67_legacy_isolation_offline import _assert_frozen_s66_artifacts_unchanged; assert_frozen_s62_live_artifacts_unchanged(); assert_frozen_s63_live_artifacts_unchanged(); _assert_frozen_s66_artifacts_unchanged(); print('frozen OK')"
```

### C2c-dead-clarify acceptance

- Target terminal clarify/defer still returned (`needs_clarification` / missing service)
- Fresh session state has no `pending_clarify` key
- `record_last_bot_payload` does not create `pending_clarify` even with `meta.clarify`
- Product/config import firewall holds
- Session/reset/lead/target runtime regression green
- `collect-only` succeeds; frozen S62/S63/S66 byte-identical
- A9 unchanged; **no harness**; **NO LIVE / NO LLM**

**STOP before C2d** after checkpoint checker ✅, commit, push, clean/synced.

---

## Checkpoint C2d — canonical client packs + legacy loader purge

**Owner approval:** 2026-07-24 — delete `clients/cesi` / `clients/nikadent` (no migration); FullContext-only demo; no compatibility layers.

**Prerequisite:** C2a–C2c-dead-clarify checkpoint checkers ✅ (`b31d21e`).

**Goal:** Clean FullContext-only architecture: one active runtime client (`demo`), canonical `target_response/*` data, no `prices.json` / `price_offers.json` fallbacks, no `patient_playbook` product path. **Do not** change target prices, payment stages, doctors, marketing, CTA semantics, or merge `clients/demo/pricebook` with `clients/demo/target_response/pricebook` without separate owner decision.

### Forbidden (C2d)

- Live/LLM runs; A9 harness; frozen A9 artifact edits
- Product authority / Composer / Verifier / boundary changes
- Merge to `main`
- cesi/nikadent migration or compatibility shims
- Consolidating dual demo pricebook trees without proof + owner decision
- Changing target price amounts, doctors, marketing, CTA behavior

### Read-only inventory (baseline `b31d21e`)

| Area | Finding | D1/D2 action |
|------|---------|--------------|
| Active product path | `app.py` → `planner_turn` → `target_fullcontext_turn`; **no** `patient_playbook` / `price_offers` / `prices.json` on hot path | D2 purge orphans |
| `clients/cesi`, `clients/nikadent` | 56+59 tracked files; `ALLOWED_CLIENTS` includes both; ~14 test files reference cesi | **D1 DELETE** packs + update config/tests |
| `clients/_template` | 6 scaffold files; excluded from build (`_` prefix); not in runtime | **KEEP** |
| `clients/demo/patient_playbook.yaml` | 7 approved rules + `bone_deficit_solution` + `patient_situations` fallback | **D1 DELETE** after proof in `clinic_strategy.yaml` |
| `clients/demo/target_response/clinic_strategy.yaml` | 7 rules materialized; priorities/caps verified by `test_demo_target_clinic_strategy.py` | **KEEP** (canonical strategy) |
| Dual demo pricebook | `target_response/pricebook` → target runtime (`response_schema_loader`); `clients/demo/pricebook` → `pricebook_loader` / `turn_planner_llm` guards | **KEEP both** (no consolidation in C2d) |
| `prices.json` / `price_offers.json` | Absent in demo; fallback code in `query_selector.py:246,574,640`, `core/price_offers.py:60-78`, `startup_check.py:15,37,72` | **D2 PRUNE** |
| `core/patient_playbook.py` | Callers: `answer_lens`, `service_node` only (legacy flows deleted S69) | **D2 DELETE** |
| `core/answer_lens.py`, `core/service_node.py` | Only deleted `patient_playbook_flow` consumer | **D2 DELETE** after `service_node` catalog rewire if needed |
| `core/price_answer_assembler.py` | Only `price_offers.build_price_answer_for_lookup` (orphan) | **D2 DELETE** if no caller after prune |
| `core/numeric_fact_gate.py` | Only deleted `price_brand_money`; target verifier checks meta key name only | **D2 DELETE** if no caller after prune |
| `core/price_offers.py` | Query heuristics used by `query_selector`; JSON loader orphan on target path | **D2 PRUNE** JSON paths; **KEEP** query helpers or extract |
| Legacy orchestration | `ask_turn`, `composer_flow`, `patient_playbook_flow`, `price_flow` — deleted, not importable (S69) | Already gone |
| A9 ties | `evals/v5` references playbook shadow matrix + price_offers eval scripts (offline); no cesi/nikadent | **DO NOT CHANGE** A9 bytes |

### Canonical data sources after C2d

| Domain | Canonical path / module |
|--------|-------------------------|
| Runtime client | `demo` only (`ALLOWED_CLIENTS`) |
| MD corpus | `clients/demo/md/` |
| Target prices/offers/facts | `clients/demo/target_response/pricebook/` |
| Service catalog (planner) | `clients/demo/service_catalog.json` |
| Clinic strategy | `clients/demo/target_response/clinic_strategy.yaml` |
| Marketing/CTA | `clients/demo/target_response/marketing.yaml` + `clients/demo/marketing.yaml` (unchanged split) |
| Planner pricebook guards | `clients/demo/pricebook/` (legacy tree; **not** merged in C2d) |

---

## Checkpoint C2d-D1 — canonical client packs

**Goal:** Remove inactive client packs; delete `patient_playbook.yaml` after 7-rule proof; retarget discovery/startup tests to demo + temp fixtures.

### D1 proof (patient_playbook → clinic_strategy)

Before deleting `clients/demo/patient_playbook.yaml`:

1. `tests/test_demo_target_clinic_strategy.py::test_seven_rules_preserve_current_priorities_and_approved_caps` must pass (7 rules: priorities + approved max_options caps).
2. Add/keep `tests/test_c2d_playbook_strategy_parity_offline.py` — frozen EXPECTED_RULES snapshot **without** reading deleted YAML at runtime (embed from audit or read only `clinic_strategy.yaml`).
3. `bone_deficit_solution` and `patient_situations` are **not** migrated — intentionally dropped (current-only).

### D1 delete-list

| Path | Action |
|------|--------|
| `clients/cesi/` | **DELETE** entire tree |
| `clients/nikadent/` | **DELETE** entire tree |
| `clients/demo/patient_playbook.yaml` | **DELETE** after proof |

### D1 allowlist

| File | Change |
|------|--------|
| `TASK.md` | governance (this section) |
| `config.py` | `ALLOWED_CLIENTS` → `demo` only (DEFAULT_CLIENT_ID unchanged) |
| `admin_dashboard/app.py` | default client → `demo` |
| `admin_dashboard/static/dashboard.js` | `defaultClientId` → `demo` |
| `build_index.py` | help text: demo only |
| `static/multiclient/index.html` | remove cesi/nikadent cards (demo-only landing) |
| `static/multiclient/cesi.html` | **DELETE** |
| `static/multiclient/nikadent.html` | **DELETE** |
| `docs/MULTICLIENT.md` | note demo-only runtime |
| `tests/test_c2d_playbook_strategy_parity_offline.py` | **new** — 7-rule proof without deleted YAML |
| `tests/test_demo_target_clinic_strategy.py` | remove `CURRENT_PLAYBOOK` reads after delete; keep green |
| `tests/test_demo_target_marketing_migration_audit.py` | drop playbook path refs |
| `tests/test_demo_target_marketing_policy.py` | drop playbook path refs |
| `tests/test_client_host.py` | demo-only or temp fixture hosts |
| `tests/test_client_config_loader.py` | demo-only |
| `tests/test_clinic_hours.py` | demo hours or remove cesi/nikadent cases |
| `tests/test_lead_service.py` | demo client_id |
| `tests/test_lead_cta_variants.py` | demo |
| `tests/test_widget_embed_cors.py` | demo |
| `tests/test_llm_system_prompt.py` | demo |
| `tests/test_dialog_segments.py` | demo |
| `tests/test_numeric_fact_gate.py` | demo |
| `tests/test_price_offers.py` | demo |
| `tests/test_price_resolution.py` | demo |
| `tests/test_purge_session.py` | demo |
| `tests/test_md_clean.py` | remove cesi/nikadent if referenced |
| `tests/test_demo_target_price_offers.py` | keep green |
| `tests/test_s61_target_fullcontext_runtime.py` | bootstrap regression |
| `tests/test_target_fullcontext_content_response.py` | prices/marketing regression |

### D1 acceptance

- `clients/cesi`, `clients/nikadent` absent; `_template` present and not runtime
- `patient_playbook.yaml` absent; 7 approved rules proven in `clinic_strategy.yaml`
- Demo FullContext bootstrap, strategy, prices, payment stages, doctors, marketing green
- No copy of old playbook retained in product data
- NO LIVE / NO LLM; A9 harness not run

### D1 tests

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-c2d1-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_c2d_playbook_strategy_parity_offline.py `
  tests/test_demo_target_clinic_strategy.py `
  tests/test_demo_target_price_offers.py `
  tests/test_demo_target_marketing_policy.py `
  tests/test_demo_target_marketing_migration_audit.py `
  tests/test_client_config_loader.py `
  tests/test_client_host.py `
  tests/test_clinic_hours.py `
  tests/test_lead_service.py `
  tests/test_lead_cta_variants.py `
  tests/test_widget_embed_cors.py `
  tests/test_llm_system_prompt.py `
  tests/test_dialog_segments.py `
  tests/test_numeric_fact_gate.py `
  tests/test_price_offers.py `
  tests/test_price_resolution.py `
  tests/test_purge_session.py `
  tests/test_md_clean.py `
  tests/test_s61_target_fullcontext_runtime.py `
  tests/test_target_fullcontext_content_response.py `
  -q
```

**D1:** CHECKPOINT-D1 checker ✅ → commit `C2d-D1: canonical client packs` → push → clean/synced.

---

## Checkpoint C2d-D2 — legacy loader/code purge

**Prerequisite:** C2d-D1 checker ✅.

**Goal:** Remove `prices.json` / `price_offers.json` fallback paths; delete orphan playbook/price-assembler modules; rewire `service_node` catalog to `service_selector_llm._read_service_catalog`; clean stale labels.

### D2 allowlist — modify

| File | Change |
|------|--------|
| `core/startup_check.py` | pricebook-only for demo; no `prices.json` OR branch |
| `query_selector.py` | remove `prices.json` fallback branches only; keep service matching / follow-up |
| `core/price_offers.py` | remove `price_offers.json` load/append paths; keep query heuristics if still imported |
| `core/pricebook_loader.py` | remove stale legacy docstring only (code already v2) |
| `contracts/pricebook.py` | docstring — canonical only |
| `core/service_node.py` | catalog via `service_selector_llm._read_service_catalog` (if kept) |
| `tests/test_c2d_loader_canonical_offline.py` | **new** — no prices.json/price_offers.json product reads |
| `tests/test_c2_import_firewall_offline.py` | extend — banned imports for deleted modules |
| `tests/test_pricebook_golden.py` | update if assembler removed |
| `tests/test_price_offers.py` | prune JSON tests; keep heuristics |
| `tests/test_turn_planner_llm.py` | keep green |
| `tests/test_c2c_session_migration_offline.py` | session regression |
| `tests/test_vague_price_followup.py` | price follow-up regression |
| `docs/FLAGS_AND_STATUS.md` | remove legacy fallback notes |
| `docs/PRICEBOOK_V2.md` | canonical-only note |
| `clients/demo/pricebook/README.md` | remove prices.json fallback claim |

### D2 allowlist — delete (only if zero active product callers after audit)

| File | Condition |
|------|-----------|
| `core/patient_playbook.py` | no product importer |
| `contracts/patient_playbook.py` | no product importer after core module delete |
| `core/answer_lens.py` | no product importer |
| `core/service_node.py` | no product importer after rewire |
| `core/price_answer_assembler.py` | no caller after price_offers prune |
| `core/numeric_fact_gate.py` | no caller after audit |
| `tests/test_patient_playbook.py` | with patient_playbook module |
| `tests/test_answer_lens.py` | with answer_lens |
| `tests/test_service_node.py` | with service_node if deleted |
| `tests/test_situation_view.py` | with answer_lens |
| `tests/test_situation_price_overview.py` | legacy flow only |
| `tests/test_numeric_fact_gate.py` | if module deleted |

**STOP** before deleting any file still imported from `app.py`, `orchestration/planner_turn.py`, `orchestration/target_fullcontext_turn.py`, `core/target_runtime*.py`, shared guards, or A9 contract loaders.

### D2 acceptance

- No active product read of `prices.json` or `price_offers.json`
- `rg` audit: no `get_pending_clarify`-class dead APIs; no `prices_json` route labels on target path
- Target runtime startup, catalog, prices, payment stages, doctors, marketing, TurnFrame planner, session/hydration green
- `/ask` + `/ask/stream` offline (fake backends) green
- Import firewall: product path does not import deleted modules
- `collect-only` succeeds; frozen S47/S50/S53/S55/S58/S62/S63/S66 byte-identical
- A9 unchanged; NO LIVE / NO LLM

### D2 tests

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-c2d2-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_c2d_loader_canonical_offline.py `
  tests/test_c2d_playbook_strategy_parity_offline.py `
  tests/test_c2_import_firewall_offline.py `
  tests/test_pricebook_golden.py `
  tests/test_demo_target_price_offers.py `
  tests/test_turn_planner_llm.py `
  tests/test_c2c_session_migration_offline.py `
  tests/test_vague_price_followup.py `
  tests/test_s61_target_fullcontext_runtime.py `
  tests/test_target_fullcontext_content_response.py `
  tests/test_demo_target_turn_frame_bound_response.py `
  tests/test_s62_correction_offline.py `
  tests/test_s63_correction_offline.py `
  -q
python -m pytest -p no:cacheprovider --collect-only -q 2>&1 | Select-Object -Last 3
python -c "from evals.v5.fullcontext_quality_eval_contract import assert_frozen_prior_artifacts_unchanged; from evals.v5.s66_default_authority_live_contract import assert_frozen_s62_live_artifacts_unchanged, assert_frozen_s63_live_artifacts_unchanged; from tests.test_s67_legacy_isolation_offline import _assert_frozen_s66_artifacts_unchanged; assert_frozen_prior_artifacts_unchanged(); assert_frozen_s62_live_artifacts_unchanged(); assert_frozen_s63_live_artifacts_unchanged(); _assert_frozen_s66_artifacts_unchanged(); print('frozen OK')"
git diff --check
```

**D2:** COMPLETION checker ✅ → commit `C2d-D2: legacy loader purge` → push → update completion record.

### C2d STOP conditions

STOP and escalate to owner if:

1. Target runtime requires `prices.json` / `price_offers.json` / `patient_playbook.yaml` on product path
2. Deleting cesi/nikadent breaks non-test production wiring that cannot move to demo
3. Dual demo pricebook consolidation required for green tests (needs separate owner decision)
4. Semantic conflict between `clients/demo/pricebook` and `target_response/pricebook` surfaces in tests
5. Any deletion changes target prices, doctors, marketing, or response behavior
6. A9 artifact change required
7. Live/LLM required to validate

---

## Checkpoint C2e — final legacy residue cleanup

**Prerequisite:** C2d-D2 COMPLETION checker ✅ (`3f94e69`). Owner-approved C2e (2026-07-24).

**Goal:** Permanently remove provably dead RAG/legacy answer-chain residue still on disk after C1/C2. Close cleanup-series. **No** product authority change, **no** new compatibility layer, **no** behavior change on target FullContext path.

**Boundary (owner law):** Do **not** delete a symbol only because it contains `chunk` / `retrieval` / `legacy`. Allowed modern meanings:

| Term | Keep when |
|------|-----------|
| `chunk` | Markdown section atom, `kb_ref` evidence, HTTP stream byte chunk |
| `retrieval` | Telemetry vocabulary (`metadata_first` pool keys), historical eval field names |
| `legacy` | Historical audit docs, frozen artifact comparison fields |

### C2e read-only inventory (baseline `3f94e69` / `fe20219`)

**Snapshot note:** S69 checkpoint-B deletions are **already applied** @ `3f94e69`. `tests/test_s69_legacy_deleted_offline.py` is **green** (5 passed). The DELETE table below is **cumulative audit history** + **remaining C2e work**. Executor must **baseline-audit** (`importlib.util.find_spec`) before each `git rm` — do not fail on already-absent paths.

#### REMAINING @ baseline — DELETE (still importable)

| Object | Evidence | Classification |
|--------|----------|----------------|
| `core/aspect_arbitration.py` | `filter_compact_for_facet_arbitration` — zero importers | orphan |
| `core/consult_nudge.py` | `app.py` calls `reset_consult_nudge_on_route` only; `record_consult_nudge_after_answer` never called on product path | orphan (vestigial reset) |
| `contracts/retrieval_candidate.py` | `contracts/__init__.py` re-export only; never constructed | orphan |
| `tests/test_consult_nudge.py` | tests deleted `consult_nudge` module | tests-only |

#### ALREADY DELETED @ baseline (S69-B / C1 — do not re-delete)

`chunk_responder`, `source_routing`, `orchestration.ask_turn`, `orchestration.composer_flow`, `orchestration.price_flow`, `orchestration.catalog_flow`, `orchestration.patient_playbook_flow`, `orchestration.resolver_turn`, `core.answer_plan_apply`, `core.answer_packet`, `core.answer_packet_materialize`, `core.answer_packet_snapshot`, `core.catalog_resolution`, `core.knowledge_base`, `core.living_frame`, `core.rewrite_policy`, `core.price_brand_money`, `core.price_symptom_consult`, `core.price_group_overview`, `contracts.answer_packet`, `core.turn_frame_adapter` — **not importable** @ `3f94e69`.

Stale tests already absent @ baseline: `test_composer_flow`, `test_answer_packet*`, `test_knowledge_base`, `test_price_brand_money`, `test_price_group_overview`, `test_turn_frame_contract`, `test_contacts_routing`, etc.

#### PRUNE — keep module/file, remove dead surface only

| Object | Active callers | Action |
|--------|----------------|--------|
| `core/answer_planner.py` | **Target:** `detect_aspects` via `attribute_followup` → `target_runtime_turn_frame_hydration` | **KEEP** `detect_aspects*`, `pick_primary_aspect`, refs; **DELETE** `build_answer_plan`, `publish_answer_plan`, `answer_plan_from_ctx` and helpers used only by them |
| `core/consult_nudge.py` | `app.py` calls `reset_consult_nudge_on_route` only; `record_consult_nudge_after_answer` never called on product path | **DELETE** module + vestigial `app.py` imports/calls; prune `consult_nudge_*` from `client_config_loader` only if zero readers after delete |
| `app.py` | `retrieval_candidates: []` in log row template; `legacy_intent` in pre-resolver ctx | **DELETE** dead fields after reader audit (`pg_sink` schema column may **KEEP** as historical DB shape — no migration) |
| `orchestration/finalize_turn.py` | Active (`finalize_ask`) | **KEEP**; trim `legacy_intent` telemetry only if no downstream reader |
| `core/md_chunks.py` | `build_index.split_md_to_chunks`; **not** called on target `/ask` path (`S69`/`S67` prove `get_chunk_by_ref` blocked) | **KEEP** file; optional docstring de-RAG wording only |
| `contracts/__init__.py` | `RetrievalCandidate` re-export | Remove orphan export when contract deleted |

#### KEEP — active FullContext / shared guards / modern evidence

| Object | Why kept |
|--------|----------|
| `contracts/answer_plan.py` | Canonical `AspectKind` / `AnswerPlan` types for TurnFrame (`turn_frame_from_raw`, `target_turn_frame_dispatch`) |
| `core/metadata_first_observability.py` | Active in `planner_turn`, `finalize_turn`; `turn_frame_shadow*` keys = **historical A9 comparison aliases** — do not rename |
| `core/routing.yaml` + `core/routing_loader.py` | Active thresholds (`scope_topic_min_confidence`, guards, verifier, session) |
| `core/aspect_metadata.py` | Used by `md_chunks.infer_chunk_aspect` (index/tooling) |
| `core/price_ref_routing.py` | `content_linter` / `build_index` widget ref parsing |
| `orchestration/finalize_turn.py` | Active product finalizer |
| `orchestration/pre_resolver_turn.py`, `planner_turn.py`, `target_fullcontext_turn.py` | Active `/ask` chain |
| `core/target_runtime*.py`, TurnFrame planner stack | Target product authority |
| `resolver.py` | **Historical** eval harness (`V5_RESOLVER_SHADOW_ON`); not product path — **KEEP file**, no product import |
| `config.ASPECT_PLANNER_LLM_ON` | Still gates optional LLM aspect detection inside `detect_aspects` — **KEEP** unless prune proves regex-only path sufficient without behavior change |

#### KEEP — historical / frozen (not product code)

| Object | Why kept |
|--------|----------|
| `evals/v5/*` harness replay fields (`metadata_first`, `turn_frame_shadow`, `retrieval_candidates` in pinned JSON) | Frozen A9 comparison vocabulary |
| `docs/C1_LEGACY_RESIDUE_REPORT.md`, `docs/S68_LEGACY_DELETION_INVENTORY.md`, `docs/C2_NATIVE_TURNFRAME_CLEANUP_PLAN.md` | Honest audit history |
| `pg_sink.retrieval_candidates` column | DB historical shape; no product read required |

#### STALE tests — delete with modules (not protected acceptance)

| Test file | Reason |
|-----------|--------|
| `tests/test_consult_nudge.py` | `consult_nudge` deleted |

#### STALE tests — already absent @ baseline (no action)

`test_composer_flow`, `test_composer_wiring`, `test_answer_packet*`, `test_knowledge_base`, `test_price_brand_money`, `test_price_group_overview`, `test_price_symptom_consult`, `test_contacts_routing`, `test_turn_frame_contract`, `test_aspect_arbitration` (if absent).

#### STALE tests — update (not delete) if they assert deleted modules

| Test file | Action |
|-----------|--------|
| `tests/test_answer_planner.py` | Keep `detect_aspects` cases; drop `build_answer_plan` cases |
| `tests/test_attribute_followup.py` | Drop `build_answer_plan` imports |
| `tests/test_turn_planner_wiring.py` | Drop legacy `build_answer_plan` cases |
| `tests/test_c1_import_firewall_offline.py` | Extend banned list for C2e orphans |
| `tests/test_c2_import_firewall_offline.py` | Extend — no resurrected legacy imports |

#### STALE tests — **KEEP** (still validate target product)

| Test file | Why |
|-----------|-----|
| `tests/test_s61_*`, `tests/test_s62_*`, `tests/test_s63_*` | Target runtime corrections |
| `tests/test_s65_authority_switch_offline.py` | Default FullContext authority (not kill-switch) |
| `tests/test_s67_legacy_isolation_offline.py` | Proves target does not load legacy modules |
| `tests/test_s69_checkpoint_a_offline.py` | Pre-S69-B wiring guards |
| `tests/test_s69_legacy_deleted_offline.py` | **Must turn green** after C2e deletions |
| `tests/test_metadata_first_observability.py` | Active telemetry; historical `turn_frame_shadow` key names |
| `tests/test_md_chunks.py` | Modern kb_ref reader + index split (not RAG path) |

### C2e allowlist — delete (after audit confirms zero product callers)

`core/aspect_arbitration.py`, `core/consult_nudge.py`, `contracts/retrieval_candidate.py`, `tests/test_consult_nudge.py`.

### C2e allowlist — modify

| File | Change |
|------|--------|
| `core/answer_planner.py` | prune legacy plan API; keep `detect_aspects` stack |
| `contracts/__init__.py` | drop `RetrievalCandidate` export |
| `app.py` | remove vestigial `consult_nudge` imports; trim dead `request.ctx` fields if zero readers |
| `orchestration/finalize_turn.py` | trim `legacy_intent` from telemetry if safe |
| `orchestration/pre_resolver_turn.py` | trim `legacy_intent` init if safe |
| `orchestration/planner_turn.py` | trim `legacy_intent`/`resolver_used` stubs if safe |
| `core/md_chunks.py` | docstring only (optional) |
| `tests/test_c2e_legacy_deleted_offline.py` | **new** — extends S69 module list + rg audit needles |
| `tests/test_c2_import_firewall_offline.py` | extend banned imports |
| `tests/test_c1_import_firewall_offline.py` | sync with S69 deletions |
| `core/client_config_loader.py` | remove dead `consult_nudge_*` after module delete |
| `tests/test_client_config_loader.py` | update if consult_nudge bundle fields removed |
| `tests/test_answer_planner.py` | prune legacy plan tests |
| `tests/test_attribute_followup.py` | drop legacy plan usage |
| `tests/test_turn_planner_wiring.py` | drop legacy plan usage |
| `docs/FLAGS_AND_STATUS.md` | C2e closeout note |
| `docs/C2_NATIVE_TURNFRAME_CLEANUP_PLAN.md` | C2e completion addendum |
| `docs/C1_LEGACY_RESIDUE_REPORT.md` | post-C2e residue table (audit doc only) |

### C2e allowlist — explicit KEEP (do not delete)

`core/md_chunks.py`, `contracts/answer_plan.py`, pruned `core/answer_planner.py`, `core/metadata_first_observability.py`, `core/routing.yaml`, `core/routing_loader.py`, `core/aspect_metadata.py`, `core/price_ref_routing.py`, `orchestration/finalize_turn.py`, target FullContext stack, both demo pricebooks, `clients/demo/target_response/**`, `clients/_template/**`, `resolver.py` (historical), A9/frozen artifacts.

### C2e acceptance

- No active `/ask` import of deleted legacy answer-chain modules (`test_s69_legacy_deleted_offline` green)
- `rg` audit: no product import of deleted modules; no `orchestrate_routing_after_resolver`; no `get_chunk_by_ref` on target path (existing S67/S69 tests)
- Target runtime bootstrap, Planner/TurnFrame, guards, session continuity/hydration/ref-click green
- Prices/payment/doctors/marketing/CTA offline tests green
- `/ask` + `/ask/stream` offline (fake backends) green
- Import firewall extended and green
- `pytest --collect-only` succeeds
- Wide safe offline pytest (exclude live/LLM-only files) green
- Frozen S47/S50/S53/S55/S58/S62/S63/S66 byte-identical
- A9 artifacts unchanged; **NO LIVE / NO LLM / NO A9 harness**
- `git diff --check` clean

### C2e tests

**Focused block:**

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-c2e-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_c2e_legacy_deleted_offline.py `
  tests/test_c2_import_firewall_offline.py `
  tests/test_c1_import_firewall_offline.py `
  tests/test_s69_legacy_deleted_offline.py `
  tests/test_s69_checkpoint_a_offline.py `
  tests/test_s67_legacy_isolation_offline.py `
  tests/test_s61_target_fullcontext_runtime.py `
  tests/test_s65_authority_switch_offline.py `
  tests/test_s62_correction_offline.py `
  tests/test_s63_correction_offline.py `
  tests/test_c2a_runtime_turn_frame_offline.py `
  tests/test_c2b_no_resolver_offline.py `
  tests/test_c2c_session_migration_offline.py `
  tests/test_turn_planner_llm.py `
  tests/test_turn_frame_from_raw.py `
  tests/test_answer_planner.py `
  tests/test_attribute_followup.py `
  tests/test_target_fullcontext_content_response.py `
  tests/test_demo_target_turn_frame_bound_response.py `
  tests/test_vague_price_followup.py `
  tests/test_pricebook_golden.py `
  tests/test_demo_target_price_offers.py `
  tests/test_metadata_first_observability.py `
  tests/test_md_chunks.py `
  -q
```

**Wide safe offline (no A9/live):**

```powershell
python -m pytest -p no:cacheprovider --basetemp $bt tests/ `
  --ignore=tests/test_composer_live_eval.py `
  --ignore=tests/test_emotion_route_matrix.py `
  --ignore=tests/test_medical_boundary_eval_live_cli.py `
  -q
```

**Integrity:**

```powershell
python -m pytest -p no:cacheprovider --collect-only -q 2>&1 | Select-Object -Last 3
python -c "from evals.v5.fullcontext_quality_eval_contract import assert_frozen_prior_artifacts_unchanged; from evals.v5.s66_default_authority_live_contract import assert_frozen_s62_live_artifacts_unchanged, assert_frozen_s63_live_artifacts_unchanged; from tests.test_s67_legacy_isolation_offline import _assert_frozen_s66_artifacts_unchanged; assert_frozen_prior_artifacts_unchanged(); assert_frozen_s62_live_artifacts_unchanged(); assert_frozen_s63_live_artifacts_unchanged(); _assert_frozen_s66_artifacts_unchanged(); print('frozen OK')"
git diff --check
```

**C2e:** COMPLETION checker ✅ → commit `C2e: final legacy residue cleanup` → push → update completion record → **CLEANUP_SERIES_COMPLETE / STOP** (no C2f).

### C2e STOP conditions

STOP and escalate to owner if:

1. Candidate has active FullContext or shared-guard caller not listed in KEEP table
2. Deletion requires target data / `target_response/**` format change
3. A9 or frozen artifact byte change required
4. Planner/TurnFrame semantic change required to delete residue
5. Unclear whether `chunk` is evidence-model (`kb_ref`) vs old RAG retrieval path
6. `detect_aspects` removal would break target hydration follow-ups
7. Live/LLM or A9 harness required to validate
8. Wide pytest failure indicates target behavior regression (not stale test only)

### C2e final report (mandatory)

Split remaining residue into three groups:

1. **Deleted** — dead legacy/RAG answer chain
2. **Kept** — used by modern FullContext chain or shared guards
3. **Historical/frozen** — audit docs, eval comparison fields, DB columns

Answer plainly: old RAG on active path? compatibility fallbacks left? provably dead code remains? cleanup-series complete?

---

## Full C2 acceptance (COMPLETION)

### A. Product import firewall

Active product must not import/read: `TurnPlan` authority, `legacy_plan`, `turn_frame_adapter`, `turn_frame_shadow` (product), `resolve_with_fallback`, resolver LLM, `DecisionFrame` as response authority, `last_subject`, legacy `pending_clarify`, `prices.json` fallback.

### B–H. Runtime (unchanged semantics)

`/ask`, `/ask/stream`, follow-up/session, guards, structured data, medical boundary — existing target offline tests green.

### I. Integrity

- `pytest --collect-only -q` succeeds
- Frozen S62/S63/S66 pins byte-identical
- A9 artifacts byte-identical; **do not run** A9 harness
- `git diff --check` clean

### COMPLETION test block

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-c2-final-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_c2a_runtime_turn_frame_offline.py `
  tests/test_c2b_no_resolver_offline.py `
  tests/test_c2c_session_migration_offline.py `
  tests/test_c2_import_firewall_offline.py `
  tests/test_turn_planner_llm.py `
  tests/test_turn_frame_from_raw.py `
  tests/test_s61_target_fullcontext_runtime.py `
  tests/test_s62_correction_offline.py `
  tests/test_s63_correction_offline.py `
  tests/test_s67_legacy_isolation_offline.py `
  tests/test_s69_checkpoint_a_offline.py `
  tests/test_target_fullcontext_content_response.py `
  -q
python -m pytest -p no:cacheprovider --collect-only -q 2>&1 | Select-Object -Last 3
python -c "from evals.v5.s66_default_authority_live_contract import assert_frozen_s62_live_artifacts_unchanged, assert_frozen_s63_live_artifacts_unchanged; from tests.test_s67_legacy_isolation_offline import _assert_frozen_s66_artifacts_unchanged; assert_frozen_s62_live_artifacts_unchanged(); assert_frozen_s63_live_artifacts_unchanged(); _assert_frozen_s66_artifacts_unchanged(); print('frozen OK')"
```

---

## Docs (completion)

| File | Change |
|------|--------|
| `docs/C2_NATIVE_TURNFRAME_CLEANUP_PLAN.md` | completion addendum |
| `docs/ARCH_TARGET_DESIGN.md` | native TurnFrame authority |
| `docs/STRANGLER_ROADMAP.md` | C2 checkpoints |
| `docs/FLAGS_AND_STATUS.md` | removed resolver/planner flags |
| `docs/S70_FULLCONTEXT_MIGRATION_CLOSEOUT.md` | C2 addendum |
| `TASK.md` | completion record |

---

## Commits (minimum)

1. `C2 governance TASK` (this commit)
2. `C2a: native runtime TurnFrame contract`
3. `C2b: remove legacy_plan and resolver fallback`
4. `C2c: session migration to target_runtime_state`
5. `C2c-dead-clarify: remove pending_clarify session state`
6. `C2d-D1: canonical client packs`
7. `C2d-D2: legacy loader purge`
8. `C2e governance TASK` (this checkpoint)
9. `C2e: final legacy residue cleanup`
10. `C2 cleanup-series closeout docs` (optional; may merge with C2e)

Each checkpoint: tests → checker ✅ → commit → push → clean/synced.

---

## Stop conditions

STOP and escalate to owner if:

1. Second LLM call required on product path
2. Partial frame routed to resolver
3. `patient_scope` authority needed
4. Composer/Verifier/boundary/evidence change required
5. Client data change required
6. Live/LLM or A9 artifact change required
7. Target behavior cannot be preserved without `legacy_plan`
8. Loader fallback required by demo target client
9. Checker ❌ requires scope beyond allowlist
10. Unaccounted DecisionFrame/TurnPlan consumer on product path

---

## Completion record (fill after COMPLETION ✅)

| Field | Value |
|-------|-------|
| PRE-CODE | ✅ (`0103316` governance correction) |
| C2a checker | ✅ |
| C2b checker | ✅ |
| C2c checker | ✅ (`70b5aa3`) |
| C2c-correction checker | ✅ (`13067dc`) |
| C2c-dead-clarify checker | ✅ (`b31d21e`) |
| C2d PRE-CODE | ✅ (governance corrected F1–F3) |
| C2d-D1 checker | ✅ (`cdc4853`) |
| C2d-D2 checker | ✅ (`3f94e69`) |
| C2e PRE-CODE | pending |
| C2e / CLEANUP_SERIES COMPLETION checker | pending |
| HEAD | `3f94e69` |
| Planner LLM calls/turn | 1 (target) |
| Resolver fallback | removed (target) |
| pytest | 152 passed (C2d-D2 block) |
| collect-only | 2276 |
| frozen | S62/S63/S66 OK |
| A9 bytes | unchanged |
| NATIVE TURNFRAME ONLY | |
| NO LIVE / NO LLM | |
| NO A9 CHANGES | |

**STOP after C2e — CLEANUP_SERIES_COMPLETE. Do not start C2f without owner decision.**
