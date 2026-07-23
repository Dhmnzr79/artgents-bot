# TASK — S70 FullContext migration closeout audit (READ-ONLY)

**Baseline:** `codex/stage-a` / `cdcd79f` · **NO LIVE / NO LLM / NO A9 / NO PRODUCT CODE**

**Authority:** Owner-approved S-series final read-only closeout after S69 legacy deletion.

## Goal

Verify the real outcome of the FullContext architectural migration after legacy removal. Determine whether S-series is complete, identify mandatory technical gaps vs deferred features, and document alignment with the original product goal (sales bot, 150–200 small MD, FullContext, structured prices/doctors/facts, marketing layer, lightweight Verifier, medical boundary, no RAG/chunk routing, no legacy fallback).

## Process

1. Governance commit: **only** `TASK.md` → push → PRE-CODE ✅
2. Read-only audit → deliverable `docs/S70_FULLCONTEXT_MIGRATION_CLOSEOUT.md`
3. Minimal active docs updates (allowlist only)
4. Static verification commands (no full pytest unless targeted)
5. COMPLETION checker ✅ → docs commit + push → STOP

## Allowlist

| File | Change |
|------|--------|
| `TASK.md` | S70 governance + completion record |
| `docs/S70_FULLCONTEXT_MIGRATION_CLOSEOUT.md` | **new** — closeout audit deliverable |
| `docs/STRANGLER_ROADMAP.md` | S69 completed + S70 verdict + S-series closure if no blockers |
| `docs/FLAGS_AND_STATUS.md` | Unconditional FullContext; no kill-switch/legacy fallback |
| `docs/ARCH_TARGET_DESIGN.md` | **only** if active sections contradict actual final state |

**Forbidden:** any other file without governance correction + new PRE-CODE ✅.

## Forbidden

- Product code, new models/contracts/orchestrators
- Live/LLM runs
- Composer/Verifier/Planner/boundary policy changes
- Client data changes
- A9 changes
- Frozen artifact edits
- Legacy restoration
- Admin/logging implementation
- Streaming implementation
- Merge/push to `main`

## Audit areas (read-only)

1. Single product chain (`/ask`, `/ask/stream`, guards, TurnFrame, boundary, FullContext, Composer, Verifier, widget/session)
2. FullContext corpus build/cache vs stable provider prefix vs provider prompt caching (three distinct concepts)
3. Structured authority (prices, doctors, marketing, staged payments, multi-client)
4. FullContext content authority (MD corpus, structured evidence priority, no hidden retrieval)
5. Lightweight Verifier final policy
6. Medical boundary and guards (urgent, medical_handoff, missing-base, uncertain, A9 shadow-only)
7. Session/dialog continuity (last_subject, dialog focus, follow-up ref, pending_clarify readers)
8. UI/runtime (`/ask` vs `/ask/stream`, SSE batch, CTA/follow-up)
9. Multi-client readiness (honest assessment)
10. Post-legacy remnants classification (ACTIVE_TARGET, SHARED_RUNTIME, HISTORICAL_AUDIT, OFFLINE_TOOLING, DEFERRED_PRODUCT_FEATURE, MUST_FIX_BLOCKER, DEAD_CODE_CANDIDATE)
11. Test confidence (S69 80/80, 112/112, collect 2524, frozen pins, import audit)

## Deliverable structure

`docs/S70_FULLCONTEXT_MIGRATION_CLOSEOUT.md` sections A–J per owner spec (verdict, schema, component table, goals table, remnants table, blockers, deferred features, real-client readiness, protected boundaries, recommendation).

## Static verification commands

```powershell
git branch --show-current
git rev-parse HEAD
git rev-parse origin/codex/stage-a
git status --short
git log -3 --oneline

# Legacy absence (product)
rg -l "orchestration\.ask_turn|chunk_responder|source_routing|composer_flow|price_flow|catalog_flow|patient_playbook_flow|TARGET_FULLCONTEXT_DEV|orchestrate_routing_after_resolver" --glob "*.py" | Where-Object { $_ -notmatch '^(evals|tests|docs|archive|tools)/' }

python -c "from evals.v5.s66_default_authority_live_contract import assert_frozen_s62_live_artifacts_unchanged, assert_frozen_s63_live_artifacts_unchanged; from tests.test_s67_legacy_isolation_offline import _assert_frozen_s66_artifacts_unchanged; assert_frozen_s62_live_artifacts_unchanged(); assert_frozen_s63_live_artifacts_unchanged(); _assert_frozen_s66_artifacts_unchanged(); print('frozen OK')"

python -m pytest --collect-only -q 2>&1 | Select-Object -Last 3
```

Optional targeted (not required for full suite):

```powershell
python -m pytest -q tests/test_s69_checkpoint_a_offline.py tests/test_s69_legacy_deleted_offline.py -p no:cacheprovider
```

## Stop conditions

- PRE-CODE or COMPLETION ❌ not fixable in allowlist
- Audit requires product code change to answer a question → document as blocker/deferred, do not code
- Corpus overflow or architecture decision needed → STOP, escalate owner

## Acceptance

- [ ] PRE-CODE checker ✅
- [ ] `docs/S70_FULLCONTEXT_MIGRATION_CLOSEOUT.md` complete (sections A–J)
- [ ] Active docs updated (allowlist)
- [ ] Static verification recorded in closeout
- [ ] COMPLETION checker ✅
- [ ] Docs commit + push `origin/codex/stage-a`
- [ ] Clean tree; HEAD == origin

**STOP after S70 — do not auto-create S71.**
