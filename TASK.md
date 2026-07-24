# TASK — C2 Native TurnFrame cleanup (Cleanup-series)

**Baseline:** `codex/stage-a` / `5c3d3bb` (C1 closeout) · **NO LIVE / NO LLM / NO A9 changes**

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
6. **C2d** → final **COMPLETION checker ✅** → docs → push → **STOP**

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
| `pending_clarify` | read: `turn_planner_llm`, `ask_turn`; write: `composer_flow` only | tests | **DELETE** planner reads + session API if dead (C2c) |
| `turn_plan_from_ctx` / `publish_turn_plan` | `ask_turn.py`, `composer_flow.py` (not `/ask` target) | tests | **KEEP** dead legacy modules; **no** C2b edits unless import break |
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

## Checkpoint C2d — target-only loader fallback cleanup

**Prerequisite:** C2a–C2c checkpoint checkers ✅.

### C2d audit targets

| File | Legacy fallback | Action |
|------|-----------------|--------|
| `core/pricebook_loader.py` | docstring only at `5c3d3bb` | verify canonical-only load |
| `core/price_offers.py` | `price_offers.json`, append-only path `:460` | **PRUNE** if target uses pricebook only |
| `query_selector.py` | `prices.json` `:246,573,639` | **PRUNE** if startup guarantees canonical |
| `core/startup_check.py` | `prices.json` OR pricebook `:15,37,72` | require canonical pricebook for demo |
| `contracts/pricebook.py` | legacy docstring | docs only |
| `core/patient_playbook.py` | legacy schema fallback | audit call sites |
| `core/client_config_loader.py` | schema fallback | audit only |

**STOP** if any fallback is required by active target path for demo client.

### C2d allowlist

| File | Change |
|------|--------|
| `core/pricebook_loader.py` | remove dead fallback branches if any |
| `core/price_offers.py` | remove `price_offers.json` / append-only path |
| `query_selector.py` | remove `prices.json` reads |
| `core/startup_check.py` | fail-closed canonical validation |
| `core/patient_playbook.py` | prune legacy loader fallback |
| `contracts/pricebook.py` | docstring only |
| `tests/test_pricebook_golden.py` | keep green |
| `tests/test_demo_target_price_offers.py` | keep green |
| `tests/test_marketing_loader.py` | no regression |
| `tests/test_c2d_loader_canonical_offline.py` | **new** |

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
5. `C2d: loader canonical cleanup`
6. `C2 completion docs` (if not merged with C2d)

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
| C2c checker | |
| COMPLETION | |
| HEAD | |
| Planner LLM calls/turn | 1 (target) |
| Resolver fallback | removed (target) |
| pytest | |
| collect-only | |
| frozen | |
| A9 bytes | unchanged |
| NATIVE TURNFRAME ONLY | |
| NO LIVE / NO LLM | |
| NO A9 CHANGES | |

**STOP after C2 — do not start next milestone without owner decision.**
