# TASK — S68 legacy deletion inventory (READ-ONLY)

**Baseline:** `codex/stage-a` / `3d0060d` · **NO PRODUCT CODE / NO LEGACY DELETE / NO LIVE**

## Goal

Produce an evidence-backed map of what can be **mechanically deleted** after S67 isolation, without touching FullContext, shared guards, TurnFrame/planner, lead/booking flows, or frozen artifacts.

**S68 changes no product code.** Output is audit doc + minimal roadmap/docs notes only.

## Process (mandatory)

1. Governance commit: **only** `TASK.md`
2. PRE-CODE checker ✅ **before** any audit work
3. If PRE-CODE ❌ → STOP → fix **only** `TASK.md` → governance correction commit → repeat PRE-CODE
4. **No** WIP audit doc until PRE-CODE ✅
5. After audit → COMPLETION checker → docs commit → push `origin/codex/stage-a` → STOP

## Allowlist

| File | Change |
|------|--------|
| `TASK.md` | governance + completion |
| `docs/S68_LEGACY_DELETION_INVENTORY.md` | **new** deliverable (sections A–J) |
| `docs/STRANGLER_ROADMAP.md` | S68 status; pointer to inventory |
| `docs/FLAGS_AND_STATUS.md` | future kill-switch removal note only if needed; **no flag change now** |

**Forbidden:** any product `.py` change, legacy file deletion, kill-switch removal/change, live/LLM, FullContext/Composer/Verifier/planner/boundary/session changes, A9 changes, frozen artifact edits, git history rewrite, merge/push to `main`.

## Mandatory read-only analysis (10 areas)

1. **Authority & kill-switch** — `TARGET_FULLCONTEXT_DEV`, `_orchestrate_ask_turn`, lazy `orchestrate_routing_after_resolver`; what to remove for unconditional FullContext; tests/docs depending on `=0`
2. **Legacy orchestration** — `orchestration.ask_turn`, `orchestrate_routing_after_resolver`, continuation/promo/clarify/fallback; direct + transitive importers
3. **RAG/source routing** — `source_routing`, legacy answer planning, retrieval/chunk selection, MD chunk loaders **only** for legacy responder vs FullContext MD loader
4. **Legacy response generation** — `chunk_responder`, `orchestration.composer_flow`, legacy Composer overlay, dispatch kinds `chunk`/`composer`, `_sse_chunk_response` / `_sse_composer_reply` / JSON analogs; shared delivery helpers to **KEEP**
5. **Legacy ref handling** — `get_chunk_by_ref`, legacy price/chunk/consult ref handlers vs target ref navigation (S63)
6. **Session compatibility** — `last_subject`, `current_doc_id`, `pending_clarify`, legacy history/focus fields; readers in shared guards/planner vs target-only
7. **Shared code — KEEP** (verify real importers): ingress, rate limit/reset/noise, lead/booking/situation, resolver/planner/TurnFrame shadow, target runtime, target FullContext loader, target session, CTA/follow-up widget, HTTP/SSE delivery, shared observability
8. **Tests** — target/protected, shared guard, legacy-only, mixed, frozen pin, historical eval replay
9. **Docs/config/dependencies** — stale flags, legacy-only env, RAG-only requirements, historical vs active docs
10. **Reachability** — per candidate: importers, callers, reachable on default FullContext, reachable only on `=0`, shared with target, direct delete vs seam change first

**Rule:** do not classify as legacy by name alone; prove with `rg` / import graph.

## Deliverable: `docs/S68_LEGACY_DELETION_INVENTORY.md`

| Section | Content |
|---------|---------|
| A | Executive summary: ready to delete? blockers? how many deletion milestones |
| B | Current diagrams: default FullContext path vs kill-switch legacy path |
| C | Files/symbols table: File/symbol · callers/importers · target/shared · legacy-only · Action · removal order · tests affected. Actions: `DELETE`, `KEEP_SHARED`, `MODIFY_THEN_DELETE`, `KEEP_HISTORICAL`, `INVESTIGATE_BLOCKER` |
| D | Runtime branches / dispatch kinds table |
| E | Session compatibility table |
| F | Tests classification table |
| G | Frozen protection list (S47/S50/S53/S55/S58/S62/S63/S66 artifacts, A9, audit manifests, pin guards) |
| H | Minimal S69 deletion milestone: exact allowlist + preferred order (or two milestones with concrete blocker) |
| I | S69 stop conditions |
| J | Evidence: real file/function refs + `rg` commands used |

### Preferred S69 order (default proposal; override only with blocker proof)

1. Remove kill-switch + legacy authority branch
2. Remove legacy dispatch kinds from `app.py`
3. Remove legacy ref answer paths
4. Delete orchestration/source routing/chunk/composer modules if no shared callers
5. Remove legacy session compatibility after last reader gone
6. Delete legacy-only tests
7. Update active docs/config
8. Run target/shared regression suite

## Read-only commands

```powershell
git diff --check

# Authority / orchestration
rg -n "TARGET_FULLCONTEXT_DEV|orchestrate_routing_after_resolver|orchestrate_target_fullcontext" app.py config.py orchestration/
rg -l "from orchestration.ask_turn|import orchestration.ask_turn|from chunk_responder|import chunk_responder|source_routing|composer_flow" --glob "*.py"

# Refs / session
rg -n "get_chunk_by_ref|last_subject|current_doc_id|pending_clarify" --glob "*.py"

# Tests
rg -l "TARGET_FULLCONTEXT_DEV.*0|kill.switch|legacy" tests/ --glob "*.py"

# Frozen pin sanity (no artifact writes)
python -c "from evals.v5.s66_default_authority_live_contract import assert_frozen_s62_live_artifacts_unchanged, assert_frozen_s63_live_artifacts_unchanged; from tests.test_s67_legacy_isolation_offline import _assert_frozen_s66_artifacts_unchanged; assert_frozen_s62_live_artifacts_unchanged(); assert_frozen_s63_live_artifacts_unchanged(); _assert_frozen_s66_artifacts_unchanged(); print('frozen OK')"
```

**No pytest required** unless product code changes (none expected).

## Acceptance

- [ ] PRE-CODE checker ✅ before audit
- [ ] `S68_LEGACY_DELETION_INVENTORY.md` sections A–J complete with evidence
- [ ] Target/shared dependencies not marked DELETE
- [ ] Tests classified; frozen/A9 protected
- [ ] S69 scope minimal and allowlisted
- [ ] No product code changed
- [ ] COMPLETION checker ✅
- [ ] Push `origin/codex/stage-a`

**STOP after S68 — do not start S69 without separate owner decision.**
