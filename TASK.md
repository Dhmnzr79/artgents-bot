# TASK — S64 FullContext authority audit (read-only)

**Baseline:** `codex/stage-a` / `520e34a` · **NO LIVE / NO LLM / NO AUTHORITY SWITCH**

## Goal

Read-only audit of both HTTP entry points (`POST /ask`, `POST /ask/stream`) to determine the **minimal safe path** for transferring product authority to the target FullContext chain. Produce governance docs and S65 milestone plan only — **no product code changes**.

## Preconditions (verified at start)

- Branch `codex/stage-a`, HEAD `520e34a`
- Working tree clean; HEAD == `origin/codex/stage-a`
- S63 complete: AUTOMATED_PASS, manual PASS, 3/3 materialized, legacy/RAG/chunk = 0, 14/15 provider calls, retry = 0, FullContext build = 1, RERUN_BLOCKED

## Deliverables

| # | File | Action |
|---|------|--------|
| 1 | `docs/S64_FULLCONTEXT_AUTHORITY_AUDIT.md` | Create — sections A–G (chains, short-circuits, legacy table, blockers, S65, rollback, post-switch plan) |
| 2 | `docs/STRANGLER_ROADMAP.md` | Update — S63 confirmed, S64 audit status, S65 gate, authority not transferred |
| 3 | `docs/FLAGS_AND_STATUS.md` | Optional minimal clarification only; **do not change `TARGET_FULLCONTEXT_DEV` default** |
| 4 | `TASK.md` | Close with audit results |

## Allowlist

| File | Change |
|------|--------|
| `TASK.md` | S64 governance + completion |
| `docs/S64_FULLCONTEXT_AUTHORITY_AUDIT.md` | new audit |
| `docs/STRANGLER_ROADMAP.md` | S63/S64/S65 status |
| `docs/FLAGS_AND_STATUS.md` | optional clarification |
| `drafts/checker_last.md` | checker reports (PRE-CODE + COMPLETION) |

**Forbidden:** product code (`*.py` outside drafts), `TARGET_FULLCONTEXT_DEV` default flip, authority switch, legacy deletion, live/LLM, frozen S62/S63 artifact edits, A9 changes, merge/push to main.

## Audit scope (code-traced, both endpoints)

Trace `_orchestrate_ask_turn` → pre-resolver → resolver → target vs legacy branch for:

- `TARGET_FULLCONTEXT_DEV=0` and `=1`
- normal message, ref-click, terminal/defer, target pipeline error

Verify: authority selection point, pre-target short-circuits, hidden legacy/RAG/chunk/resolver/composer fallback, `/ask` vs `/ask/stream` parity, session fields, failure modes, target-only responses without legacy rollback.

Key files to read (read-only):

- `app.py` — `_orchestrate_ask_turn`, `_dispatch_orchestration_json`, `_dispatch_orchestration_sse`
- `orchestration/pre_resolver_turn.py`
- `orchestration/resolver_turn.py`
- `orchestration/target_fullcontext_turn.py`
- `orchestration/ask_turn.py` (legacy routing only)
- `core/target_runtime_turn.py`, `core/target_runtime_widget.py`, `core/target_runtime_session.py`
- `core/target_runtime_turn_frame_bridge.py`
- `flow_handlers.py`, `ingress_gate.py`

## S62/S63 frozen artifact guard

Must remain byte-identical (SHA-256 from `evals/v5/s63_target_runtime_live_contract.py` `FROZEN_S62_LIVE_ARTIFACT_SHA256` + S63 artifacts at `520e34a`). No edits to `evals/v5/artifacts/s62_*` or `evals/v5/artifacts/s63_*`.

## Commands

```powershell
git diff --check

# Optional static: verify no product .py in diff
git diff --name-only HEAD

# S62 pin (read-only, no pytest required unless checker requests)
python -c "from evals.v5.s63_target_runtime_live_contract import assert_frozen_s62_live_artifacts_unchanged; assert_frozen_s62_live_artifacts_unchanged(); print('S62 frozen OK')"
```

## Acceptance (COMPLETION)

- [ ] PRE-CODE checker ✅
- [ ] `docs/S64_FULLCONTEXT_AUTHORITY_AUDIT.md` complete (A–G), conclusions backed by real functions/files
- [ ] Both `/ask` and `/ask/stream` covered; legacy fallback explicitly checked
- [ ] S65 milestone minimal with exact allowlist
- [ ] No product code, no live, no authority switch, no A9, no frozen artifact changes
- [ ] `git diff --check` clean
- [ ] COMPLETION checker ✅
- [ ] Two commits: governance + completion/docs; push `origin/codex/stage-a`

## Checker

| Checkpoint | When |
|---|---|
| PRE-CODE | after governance TASK commit, before audit docs |
| COMPLETION | after all deliverables |
