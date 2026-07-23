# TASK — C1 Dead legacy residue cleanup + C2 TurnFrame plan (Cleanup-series)

**Baseline:** `codex/stage-a` / `c9598ee` (S70 closeout) · **NO LIVE / NO LLM / NO A9 changes**

**Authority:** Owner-approved Cleanup-series C1 after `S_SERIES_COMPLETE` (S70).

## Goal

Remove **provably dead** post-S69 legacy residue from active product/offline code without changing FullContext behavior, Planner/TurnFrame semantics, Composer/Verifier/boundary, client data, or frozen audit history. Produce exact `docs/C2_NATIVE_TURNFRAME_CLEANUP_PLAN.md` (plan only — no C2 implementation).

## Process (mandatory)

1. **Governance commit:** only `TASK.md` → push → **PRE-CODE checker ✅**
2. If PRE-CODE ❌: STOP, fix only `TASK.md`, governance correction commit, repeat PRE-CODE until ✅
3. **Implementation** only after PRE-CODE ✅ (product WIP forbidden before)
4. Offline pytest + collect-only + frozen pins + import firewall + `rg` residue report
5. **COMPLETION checker ✅** → docs/commits → push `origin/codex/stage-a` → **STOP** (do not start C2)

## Forbidden

- Live/LLM runs
- Planner/TurnFrame semantic changes (`legacy_plan`, adapter, resolver fallback, shadow naming behavior)
- Composer/Verifier/boundary/evidence changes
- Answer/client data changes
- A9 changes
- Frozen artifact edits or pin guard weakening
- Historical evidence deletion for clean `rg`
- Merge/push to `main`
- Files outside allowlist without governance correction + new PRE-CODE ✅

---

## Read-only audit summary (baseline `c9598ee`)

### Candidate disposition table

| Symbol / file | Active product callers | Offline tooling callers | Historical callers | Action |
|---------------|------------------------|-------------------------|-------------------|--------|
| `core/md_chunks.py` | none on target path | `build_index.split_md_to_chunks`; tests `get_chunk_by_ref` | deleted `price_flow`/`catalog_flow`/`answer_packet_*` | **PRUNE_SYMBOLS** `find_chunk_by_topic_aspect`; **KEEP** `split_md_to_chunks`, `get_chunk_by_ref`, `CONTACTS_CHUNK_REF` |
| `core/catalog_resolution.py` | `clarify_state._md_korotko_ref` only | `tests/test_price_resolution.py` | deleted `catalog_flow`; dead `ux_builder.build_price_resolution_payload` | **DELETE_NOW** file; **MOVE** `_md_korotko_ref` → `core/clarify_state.py`; **PRUNE** `ux_builder.build_price_resolution_payload` + `fallback_reason_to_resolution`/`service_content_snippet` chain; **DELETE** `tests/test_price_resolution.py` |
| `llm.py` retrieval rewrite | none (no callers) | `tests/test_rewrite_*` | deleted chunk path | **PRUNE_SYMBOLS** `rewrite_query_for_retrieval`, `validated_retrieval_rewrite`, `_REWRITE_SYSTEM`, `_norm_rewrite_compare` |
| `llm.py` packet/chunk composer | none | deleted tests (already removed) | deleted `composer_flow` | **PRUNE_SYMBOLS** `build_messages_for_packet_composer*`, `generate_answer_from_packet*`, `generate_answer_stream`, `build_messages_for_gpt`, `generate_answer`, `generate_facts_card_answer`, `_format_composer_card_blocks`, `_consult_nudge_addon` usage in dead paths |
| `core/rewrite_policy.py` | none | `tests/test_rewrite_policy.py` | `llm.rewrite_query_for_retrieval` | **DELETE_NOW** |
| `contracts/ask_orchestration.py` | `kind=service_reply` only in product | — | deleted chunk/composer dispatch | **PRUNE_SYMBOLS** remove `chunk`/`composer` kinds and orphan fields; drop `MaterializedCard` import |
| `contracts/answer_packet.py` | none after prune | deleted legacy tests | deleted packet stack | **DELETE_NOW** entire contract module |
| `config.py` `COMPOSER_ON`/`FULLCTX_ON`/`ANSWER_PACKET_ASSEMBLER_ON` | none (orphan) | deleted tests | deleted `composer_flow`/`llm` packet | **DELETE_NOW** symbols + env docs |
| `config.py` `QUERY_REWRITE_*` | none after llm prune | deleted tests | retrieval rewrite | **DELETE_NOW** symbols |
| `config.py` `LIVING_OVERVIEW_ON`/`SITUATION_PRICE_ON`/`PRICE_SYMPTOM_CONSULT_ON` | none on target path | legacy tests | deleted `patient_playbook_flow`/`price_flow` | **DELETE_NOW** symbols |
| `app.py` `/__debug/retrieval` | none (returns 410) | — | retired embed debug | **DELETE_NOW** endpoint |
| `app.py` `retrieval_scope_*` ctx init + error telemetry | set null only; never populated on target | — | deleted `apply_content_retrieval_scope_ctx` | **PRUNE_SYMBOLS** remove init + error payload keys where dead |
| `app.py` `legacy_intent` | **active** resolver fallback telemetry | tests | — | **KEEP_ACTIVE** (C2) |
| `orchestration/helpers.py` retrieval helpers | none | — | deleted `ask_turn`/chunk arbiter | **PRUNE_SYMBOLS** `apply_content_retrieval_scope_ctx`, `apply_metadata_first_after_content_route`, `log_selection`, `chunk_info`, `ref_from_chunk`, `canonical_ref`, `guided_menu_payload`, `service_price_line_for_content`, `ru_doctor_count_word`; drop dead imports |
| `orchestration/finalize_turn.py` | active finalize | — | — | **PRUNE_SYMBOLS** only dead `retrieval_scope_*` log fields if removed from ctx; **KEEP** `metadata_first_turn_details`, `legacy_intent` logging |
| `query_selector.compute_retrieval_scope_with_conflict_guard` | none after helpers prune | tests | deleted retrieval scope | **PRUNE_SYMBOLS** |
| `core/metadata_first_observability.py` | `record_decision_frame_ctx` (resolver), `metadata_first_turn_details` (finalize) | tests | `merge_retrieval_debug_meta` via deleted helpers | **PRUNE_SYMBOLS** retrieval-only merge helpers if unreferenced; **KEEP** decision-frame + turn details |
| `core/knowledge_base.py` | none | `tests/test_knowledge_base.py` | deleted `composer_flow`, `living_frame` | **DELETE_NOW** |
| `core/living_frame.py` | none | tests | deleted `patient_playbook_flow` | **DELETE_NOW** |
| `core/price_brand_money.py` | none | `tests/test_price_brand_money.py` | deleted `price_flow`/`ask_turn` | **DELETE_NOW** |
| `core/price_symptom_consult.py` | none | `tests/test_price_symptom_consult.py`; dead import in `tests/test_s61_correction_target_runtime.py` | deleted `price_flow`/`composer_flow` | **DELETE_NOW**; remove unused `CONSULT_SYMPTOM_DETAILS_REF` import from `test_s61_correction_target_runtime.py` |
| `core/price_group_overview.py` | none (answer builder) | `tests/test_price_group_overview.py`; `tests/test_pricebook_golden.py` (overview sections); `tests/test_price_ref_routing.py` (quick replies); `core/price_offers.py` unit-clarify helpers | deleted `price_flow`/`ux_builder` payloads | **DELETE_NOW** module; **PRUNE** `price_offers` unit-clarify helpers + related tests; **KEEP** `query_selector` `group_overview` *routing mode* only |
| `core/consult_nudge.py` | `app._service_reply`/`_sse_service_reply` `reset_consult_nudge_on_route` | tests | dead `ux_builder` catalog_facts writer | **KEEP_ACTIVE** |
| `core/clarify_state.py` | `turn_planner_llm`, planner tests | tests | deleted composer clarify writer | **KEEP_ACTIVE**; absorb `_md_korotko_ref` |
| `core/answer_planner.py` | `attribute_followup.detect_aspects` | tests | deleted `ask_turn` plan publish | **KEEP_ACTIVE** (shared selector; not C2 TurnFrame adapter) |
| `core/turn_planner_llm.py` `legacy_plan`/shadow | **active** resolver path | tests | — | **MOVE_TO_C2** map only — **do not change** |
| `core/turn_frame_adapter.py` | shadow/planner tests | tests | — | **MOVE_TO_C2** map only — **do not change** |
| `resolver.resolve_with_fallback` | **active** when planner returns no plan | tests | — | **MOVE_TO_C2** map only — **do not change** |
| `session.last_subject`/`pending_clarify` | planner/focus readers | tests | deleted writers | **MOVE_TO_C2** map only — **do not change** |
| `core/dialog_focus.py` legacy compat | shared selectors/focus | tests | — | **MOVE_TO_C2** map only — **do not change** |
| `core/routing_loader.py` / `core/turn_timing.py` | ingress/resolver/finalize/app | eval harness | — | **KEEP_ACTIVE** |
| `ux_builder.py` legacy payloads | none on target path | tests | deleted orchestration | **PRUNE_SYMBOLS** dead builders (`build_service_facts_card_payload`, `build_clarify_payload`, `build_price_resolution_payload`, `build_price_symptom_consult_*`, `build_price_group_overview_payload`, `build_price_unit_clarify_payload`, `build_price_concern_payload` chain); **KEEP** app/pre_resolver helpers (`empty_question_response`, `normalize_policy_payload`, `reset_session_response`, `internal_error_response`, `format_price_answer_from_item` if still referenced) |

### C2 mapping obligation (docs only)

`docs/C2_NATIVE_TURNFRAME_CLEANUP_PLAN.md` must answer owner Cleanup-series C2 spec sections 1–13 (legacy_plan → TurnFrame wiring, resolver fallback, session field migration, C2 allowlist/stop conditions) using **real call sites** from: `core/turn_planner_llm.py`, `core/turn_frame_from_raw.py`, `core/turn_frame_adapter.py`, `core/turn_frame_shadow.py`, `orchestration/resolver_turn.py`, `resolver.py`, `core/target_runtime_turn_frame_hydration.py`, `session.py`, `core/dialog_focus.py`, pricebook/patient playbook loaders — **no C2 code**.

---

## Allowlist (implementation)

| File | Change |
|------|--------|
| `TASK.md` | governance + completion record |
| `core/catalog_resolution.py` | **delete** |
| `core/knowledge_base.py` | **delete** |
| `core/living_frame.py` | **delete** |
| `core/price_brand_money.py` | **delete** |
| `core/price_symptom_consult.py` | **delete** |
| `core/price_group_overview.py` | **delete** |
| `core/rewrite_policy.py` | **delete** |
| `core/md_chunks.py` | prune dead symbols only |
| `core/clarify_state.py` | inline `_md_korotko_ref`; fix import |
| `core/client_config_loader.py` | remove dead `PRICE_SYMPTOM_CONSULT_ON` gate in `price_symptom_consult_enabled()` (knock-on after `config.py` flag deletion) |
| `contracts/answer_packet.py` | **delete** |
| `contracts/ask_orchestration.py` | prune chunk/composer contract |
| `config.py` | remove orphan flags |
| `llm.py` | prune dead legacy helpers/imports |
| `app.py` | remove debug endpoint; prune dead telemetry fields |
| `orchestration/helpers.py` | prune dead retrieval/chunk helpers |
| `orchestration/finalize_turn.py` | prune dead retrieval telemetry fields (if unreferenced) |
| `orchestration/pre_resolver_turn.py` | prune dead `retrieval_scope_*` ctx init if safe |
| `query_selector.py` | prune `compute_retrieval_scope_with_conflict_guard` |
| `core/metadata_first_observability.py` | prune unreferenced retrieval-only helpers |
| `core/price_offers.py` | prune `build_unit_clarify_answer` / `unit_clarify_quick_replies` / `should_offer_unit_clarify` if only dead callers |
| `ux_builder.py` | prune dead legacy payload builders + imports |
| `tests/test_c1_import_firewall_offline.py` | **new** — product import firewall (A) |
| `tests/test_knowledge_base.py` | **delete** |
| `tests/test_price_brand_money.py` | **delete** |
| `tests/test_price_symptom_consult.py` | **delete** |
| `tests/test_price_group_overview.py` | **delete** (routing covered by `test_price_scope_router.py`) |
| `tests/test_rewrite_policy.py` | **delete** |
| `tests/test_rewrite_validation.py` | **delete** |
| `tests/test_s69_legacy_deleted_offline.py` | extend `DELETED_MODULES` + forbidden imports for C1 deletions (`catalog_resolution`, `knowledge_base`, `living_frame`, `price_brand_money`, `price_symptom_consult`, `price_group_overview`, `rewrite_policy`, `contracts.answer_packet`) |
| `tests/test_s69_checkpoint_a_offline.py` | update if import assertions reference pruned symbols |
| `tests/test_metadata_first_observability.py` | adjust only if pruned symbols removed |
| `tests/test_price_offers.py` | remove tests for pruned unit-clarify/group-overview helpers only |
| `tests/test_price_resolution.py` | **delete** (legacy price resolution payload) |
| `tests/test_price_scope_router.py` | remove `build_price_resolution_payload` case only; keep routing tests |
| `tests/test_price_ref_routing.py` | remove `group_overview_quick_replies` case; keep ref-routing tests |
| `tests/test_pricebook_golden.py` | remove `test_s3_group_overview_from_manifest` and jaw overview sections only |
| `tests/test_s61_correction_target_runtime.py` | remove unused `CONSULT_SYMPTOM_DETAILS_REF` import only |
| `tests/test_finalize_metadata_first_hook.py` | adjust only if hook signatures change |
| `docs/C2_NATIVE_TURNFRAME_CLEANUP_PLAN.md` | **new** — C2 plan deliverable |
| `docs/C1_LEGACY_RESIDUE_REPORT.md` | **new** — post-`rg` classification report |
| `docs/STRANGLER_ROADMAP.md` | C1 checkpoint + C2 plan pointer |
| `docs/FLAGS_AND_STATUS.md` | remove orphan flag rows |
| `docs/S70_FULLCONTEXT_MIGRATION_CLOSEOUT.md` | optional addendum: C1 hygiene done |

**Explicitly NOT in allowlist (C2):** `core/turn_planner_llm.py`, `core/turn_frame_adapter.py`, `resolver.py`, `session.py` semantic fields, `core/dialog_focus.py`, target runtime modules, frozen artifacts, client packs, A9 evals.

---

## Acceptance criteria

### A. Product import firewall
New/extended offline test: active product modules (`app.py`, `orchestration/*.py` except deleted ghosts, `core/target*.py`, `ingress_gate.py`, `flow_handlers.py`, `resolver.py`, `llm.py` shared surface) do **not** import deleted modules/symbols.

### B. `/ask`
FullContext materialized; price/doctors/payment/info; target error fail-closed (existing target tests).

### C. `/ask/stream`
Target batch SSE (`typing` → `ui` → `done`).

### D. Follow-up/session
Ref navigation; vague price/doctors follow-up; session continuity (existing tests).

### E. Guards
Ingress urgent/manual contact; lead/booking; situation; reset/rate/noise representative tests.

### F. Planner protection
`tests/test_turn_planner_llm.py`, `tests/test_turn_frame_shadow.py`, `tests/test_turn_frame_from_raw.py` pass **without expectation changes**.

### G. Structured data
Pricebook; staged payments; doctors; marketing/CTA; consultation values (existing target tests).

### H. Medical
Boundary; lightweight Verifier; missing-base; no A9 authority.

### I. Collection/imports
Targeted pytest green; `pytest --collect-only -q` succeeds; no stale imports.

### J. Frozen
S62/S63/S66 pin guards byte-identical; commands unchanged from S70.

---

## Test commands (offline only)

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$basetemp = Join-Path $env:TEMP ("demo-bot-c1-" + [guid]::NewGuid().ToString("n"))

python -m pytest -p no:cacheprovider --basetemp $basetemp `
  tests/test_c1_import_firewall_offline.py `
  tests/test_s69_legacy_deleted_offline.py `
  tests/test_s69_checkpoint_a_offline.py `
  tests/test_turn_planner_llm.py `
  tests/test_turn_frame_shadow.py `
  tests/test_turn_frame_from_raw.py `
  tests/test_s61_target_fullcontext_runtime.py `
  tests/test_target_fullcontext_content_response.py `
  tests/test_s67_legacy_isolation_offline.py `
  -q

python -m pytest -p no:cacheprovider --collect-only -q 2>&1 | Select-Object -Last 3

python -c "from evals.v5.s66_default_authority_live_contract import assert_frozen_s62_live_artifacts_unchanged, assert_frozen_s63_live_artifacts_unchanged; from tests.test_s67_legacy_isolation_offline import _assert_frozen_s66_artifacts_unchanged; assert_frozen_s62_live_artifacts_unchanged(); assert_frozen_s63_live_artifacts_unchanged(); _assert_frozen_s66_artifacts_unchanged(); print('frozen OK')"
```

Post-implementation `rg` report (classify each hit: active / shared / historical / planned C2 / false positive) for: `retrieval`, `chunk`, `legacy`, `composer`, `RAG`, `fallback`, `shadow` — document in `docs/C1_LEGACY_RESIDUE_REPORT.md`.

---

## Commits (minimum)

1. `C1 governance TASK` (this commit)
2. `C1 implementation: dead legacy residue cleanup + import firewall tests`
3. `C1 completion: C2 plan + residue report + docs` (may merge 2+3 if checker prefers single completion commit)

Push only to `origin/codex/stage-a`.

---

## Completion record (fill after COMPLETION ✅)

| Field | Value |
|-------|-------|
| PRE-CODE | ✅ (`e7ce017` governance correction) |
| COMPLETION | ✅ (after allowlist correction `HEAD`) |
| HEAD | `75a6295` |
| pytest | 267/267 targeted C1 set |
| collect-only | 2451 |
| frozen | OK |
| lines/files removed | ~5201 lines, 23 files deleted/pruned heavily |
| DEAD LEGACY RESIDUE CLEANED | yes (see `docs/C1_LEGACY_RESIDUE_REPORT.md`) |
| FULLCONTEXT BEHAVIOR UNCHANGED | yes |
| PLANNER COMPATIBILITY NOT YET REMOVED | yes — C2 plan only |
| NO LIVE / NO LLM | yes |
| NO A9 CHANGES | yes |

**STOP after C1 — C2 requires separate owner decision.**
