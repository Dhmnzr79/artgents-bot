# TASK — S69 legacy product answer path deletion (OWNER APPROVED)

**Baseline:** `codex/stage-a` / `d3313a1` · **NO LIVE / NO LLM / NO A9**

**Authority:** Owner approved per S68 inventory (`docs/S68_LEGACY_DELETION_INVENTORY.md`).

## Goal

Permanently delete legacy product answer chain (routing → RAG/source routing → chunk/composer). **FullContext is the only product authority** — no `TARGET_FULLCONTEXT_DEV`, no kill-switch, no hidden legacy fallback.

## Process

1. Governance commit: **only** `TASK.md` → push → PRE-CODE ✅
2. **Checkpoint A** — authority/seam cut → pytest → CHECKPOINT-A checker ✅ → commit + push
3. **Checkpoint B** — module/test deletion + docs → pytest/collect → COMPLETION checker ✅ → commit + push
4. Any checker ❌ → STOP → fix within allowlist → repeat checker

## Delete list (Checkpoint B — after A verified)

| File | ~LOC | Pre-delete `rg` |
|------|-----:|-----------------|
| `chunk_responder.py` | 1400 | `rg -l "chunk_responder" --glob "*.py"` |
| `orchestration/ask_turn.py` | 376 | `rg -l "ask_turn" --glob "*.py"` |
| `source_routing.py` | 330 | `rg -l "source_routing" --glob "*.py"` |
| `orchestration/composer_flow.py` | 296 | `rg -l "composer_flow" --glob "*.py"` |
| `orchestration/price_flow.py` | 473 | `rg -l "price_flow" --glob "*.py"` |
| `orchestration/catalog_flow.py` | 163 | `rg -l "catalog_flow" --glob "*.py"` |
| `orchestration/patient_playbook_flow.py` | 240 | `rg -l "patient_playbook_flow" --glob "*.py"` |

**Legacy-only tests (delete in B after module gone):**

- `tests/test_composer_flow.py`
- `tests/test_composer_wiring.py`
- `tests/test_composer_display_chunk.py`
- `tests/test_contacts_routing.py`
- `tests/test_doctor_route_order.py`
- `tests/test_source_routing_golden.py`
- `tests/test_clarify_state.py`
- `tests/test_md_clean.py`
- `tests/test_verifier_trigger.py`
- `tests/test_price_layer_parity.py`
- `tests/test_situation_price_overview.py` — imports `patient_playbook_flow` (S68 §C)
- `tests/test_answer_packet.py` — legacy answer_packet product path (S68 §C)
- `tests/test_answer_packet_composer.py` — legacy answer_packet/composer path (S68 §C)
- `tests/test_answer_packet_snapshot.py` — legacy answer_packet snapshot path (S68 §C)

**Session/plan (delete in B if no readers after `rg`):**

- `core/answer_plan_apply.py`
- `core/answer_packet.py`
- `core/answer_packet_materialize.py`
- `core/answer_packet_snapshot.py`

## Modify list

### Checkpoint A

| File | Change |
|------|--------|
| `config.py` | Remove `TARGET_FULLCONTEXT_DEV` |
| `app.py` | Unconditional target orchestration; remove lazy `orchestrate_routing_after_resolver`; remove `chunk`/`composer` dispatch + SSE helpers; simplify `_service_reply` (no legacy answer-plan) |
| `orchestration/pre_resolver_turn.py` | Remove `target_fullcontext_mode`; target ref nav only; remove legacy ref/continuation/promo/price/consult/chunk branches |
| `orchestration/lead_flow.py` | Remove `redirect_ref` → `get_chunk_by_ref` → `kind=chunk` (`redirect_ref` has **no producer** in repo — `rg redirect_ref` → only `lead_flow.py`) |
| `core/price_ref_routing.py` | Remove `orchestrate_price_widget_ref`; keep `parse_price_widget_ref` (content_linter) |
| `core/price_symptom_consult.py` | Remove `orchestrate_consult_symptom_ref` only if no shared caller after A |
| `tests/test_s69_checkpoint_a_offline.py` | **new** — Checkpoint A acceptance |
| `tests/test_s61_correction_target_runtime.py` | Remove kill-switch/OFF tests |
| `tests/test_s61_target_fullcontext_runtime.py` | Remove flag=OFF tests |
| `tests/test_s65_authority_switch_offline.py` | Remove §B kill-switch, §F; keep target authority |
| `tests/test_s67_legacy_isolation_offline.py` | Remove kill-switch F; update import firewall; no flag tests |

### Checkpoint B

| File | Change |
|------|--------|
| Delete list modules | Physical delete after `rg` clean |
| Delete list tests | Physical delete (full list above) |
| `session.py` | Remove `pending_clarify` helpers; prune `last_aspect` writers if orphaned; **investigate** `current_doc_id` / `last_catalog_service` readers — delete only after `rg` shows no target/shared reader (S68 §E) |
| `core/follow_up_rewrite.py` | Remove legacy-only functions (`persist_focus_from_service_turn` etc.) if orphaned; **keep** `focus_from_legacy_session` while `dialog_focus` reads it (S68 §C/F) |
| `core/answer_planner.py` | **KEEP_SHARED** — planner unit tests and TurnFrame shadow; remove only legacy product-only exports if orphaned after B (`rg` gate) |
| `tests/test_dialog_focus_baseline.py` | Remove `route_source` sections |
| `tests/test_turn_planner_wiring.py` | Remove `composer_flow` mock sections |
| `tests/test_price_ref_routing.py` | Keep parse tests; drop orchestrate tests |
| `tests/test_price_brand_money.py` | Remove `price_flow` imports/tests; keep shared price logic covered elsewhere (S68 §C) |
| `tests/test_s69_legacy_deleted_offline.py` | **new** — import audit + no legacy dispatch |
| `docs/FLAGS_AND_STATUS.md` | Kill-switch removed; unconditional FullContext |
| `docs/STRANGLER_ROADMAP.md` | S69 completed |
| `docs/ARCH_TARGET_DESIGN.md` | Only if still mentions legacy authority/fallback |
| `TASK.md` | Completion record |

## Keep list (must not delete)

`orchestration/resolver_turn.py`, `orchestration/target_fullcontext_turn.py`, `orchestration/lead_flow.py` (service_reply path), `orchestration/finalize_turn.py`, `orchestration/helpers.py`, `orchestration/route_guards.py`, `core/target_*`, `core/dialog_focus.py`, `core/answer_planner.py` (planner unit + shadow — not legacy product path), `core/turn_planner_llm.py`, `query_selector.py`, `core/md_chunks.py` (tooling until proven unused), `core/follow_up_rewrite.py` (partial — dialog_focus reader), `llm.py` (shared providers), `evals/v5/**` artifacts, A9 shadow, frozen pin guards.

## Checkpoint A — scope detail

1. `config.py`: delete `TARGET_FULLCONTEXT_DEV` entirely
2. `app.py`: always `orchestrate_target_fullcontext_turn`; fail-closed target errors; `service_reply`/`_sse_service_reply` only
3. `pre_resolver_turn.py`: always target ref nav; strip legacy `else` branches
4. `lead_flow.py`: remove chunk redirect branch only
5. Partial ref helpers: orchestrate functions out; parsers kept

### Checkpoint A tests (`test_s69_checkpoint_a_offline.py`)

- `/ask` and `/ask/stream` target-only
- Target error no legacy
- Target ref-click no `get_chunk_by_ref`
- Ingress hard-stop, lead flow, situation flow (if covered)
- TurnFrame planner path
- Session/CTA/follow-up
- No `TARGET_FULLCONTEXT_DEV` in config
- No product dispatch `chunk`/`composer`
- Frozen S62/S63/S66 pins

### Checkpoint A commands

```powershell
$bt = Join-Path $env:TEMP ("s69a_pytest_" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_s69_checkpoint_a_offline.py `
  tests/test_s65_authority_switch_offline.py `
  tests/test_s67_legacy_isolation_offline.py `
  tests/test_s61_correction_target_runtime.py `
  tests/test_s61_target_fullcontext_runtime.py `
  -q

python -m pytest --collect-only -q tests/test_s61_correction_target_runtime.py tests/test_s65_authority_switch_offline.py

git diff --check
python -c "from evals.v5.s66_default_authority_live_contract import assert_frozen_s62_live_artifacts_unchanged, assert_frozen_s63_live_artifacts_unchanged; from tests.test_s67_legacy_isolation_offline import _assert_frozen_s66_artifacts_unchanged; assert_frozen_s62_live_artifacts_unchanged(); assert_frozen_s63_live_artifacts_unchanged(); _assert_frozen_s66_artifacts_unchanged(); print('frozen OK')"

rg -n "TARGET_FULLCONTEXT_DEV|orchestrate_routing_after_resolver|kind=.chunk|kind=.composer" app.py config.py orchestration/pre_resolver_turn.py orchestration/lead_flow.py
```

## Checkpoint B — scope detail

1. Delete 7 legacy modules (delete list) — `rg` before each
2. Session/plan cleanup per S68 §E/H phase 5: `pending_clarify`, `answer_plan_apply`, `answer_packet*` if orphaned; partial `follow_up_rewrite`; session field prune per `rg`
3. Delete legacy-only tests; modify mixed tests
4. Product import audit — **zero** imports/calls of deleted stack in active product `.py` (excl. `evals/`, `tests/`, `docs/`, `archive/`)

### Checkpoint B commands

```powershell
$bt = Join-Path $env:TEMP ("s69b_pytest_" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_s69_checkpoint_a_offline.py `
  tests/test_s69_legacy_deleted_offline.py `
  tests/test_s65_authority_switch_offline.py `
  tests/test_s67_legacy_isolation_offline.py `
  tests/test_s61_correction_target_runtime.py `
  tests/test_s61_target_fullcontext_runtime.py `
  tests/test_s62_correction_offline.py `
  tests/test_s63_correction_offline.py `
  -q

python -m pytest --collect-only -q 2>&1 | Select-Object -Last 5

rg -l "orchestration\.ask_turn|chunk_responder|source_routing|composer_flow|price_flow|catalog_flow|patient_playbook_flow|TARGET_FULLCONTEXT_DEV|orchestrate_routing_after_resolver" --glob "*.py" | Where-Object { $_ -notmatch '^(evals|tests|docs|archive|tools)/' }

git diff --check
python -c "from evals.v5.s66_default_authority_live_contract import assert_frozen_s62_live_artifacts_unchanged, assert_frozen_s63_live_artifacts_unchanged; from tests.test_s67_legacy_isolation_offline import _assert_frozen_s66_artifacts_unchanged; assert_frozen_s62_live_artifacts_unchanged(); assert_frozen_s63_live_artifacts_unchanged(); _assert_frozen_s66_artifacts_unchanged(); print('frozen OK')"
```

## Legacy absence criteria (post-B)

Active product code must have **no**:
- `import`/`from` of delete-list modules
- `TARGET_FULLCONTEXT_DEV`
- `orchestrate_routing_after_resolver`
- `AskOrchestrationResult(kind="chunk"|kind="composer")` on product path
- Automatic fallback to legacy on target error

## Stop conditions

- Target/shared runtime caller on delete candidate → STOP that file
- `redirect_ref` producer found outside lead_flow → STOP, escalate owner
- Planner/TurnFrame/lead/booking regression requiring semantics change
- Frozen artifact rewrite required
- PRE-CODE or CHECKPOINT-A ❌ not fixable in TASK allowlist
- Live/LLM needed

## Forbidden

Live/LLM, FullContext/Planner/Composer/Verifier/boundary policy changes, frozen artifact edits, A9 changes, new flags, legacy fallback, merge/push to `main`.

## Acceptance

- [ ] PRE-CODE checker ✅ (retry after governance correction `6d43f2e` → …)
- [ ] Checkpoint A complete + CHECKPOINT-A ✅
- [ ] Checkpoint B complete + COMPLETION ✅
- [ ] Legacy import audit clean
- [ ] Frozen pins unchanged
- [ ] Push `origin/codex/stage-a`

**STOP after S69 — no further tooling/history cleanup without owner decision.**
