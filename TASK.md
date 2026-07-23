# TASK — S64 FullContext authority audit (read-only) — COMPLETE

**Baseline:** `codex/stage-a` / `520e34a`
**Governance commit:** `e7c57a2`
**Status:** **COMPLETE** · **NO LIVE / NO LLM / NO AUTHORITY SWITCH**

## Goal (done)

Read-only audit of `POST /ask` and `POST /ask/stream` to define minimal safe authority transfer to target FullContext chain.

## Deliverables

| # | File | Status |
|---|------|--------|
| 1 | `docs/S64_FULLCONTEXT_AUTHORITY_AUDIT.md` | ✅ sections A–G (+ session/failure/post-switch) |
| 2 | `docs/STRANGLER_ROADMAP.md` | ✅ S63 confirmed, S64 complete, S65 gate |
| 3 | `docs/FLAGS_AND_STATUS.md` | ✅ clarified; default unchanged |
| 4 | `TASK.md` | ✅ closed |

## Audit conclusions (summary)

| Finding | Result |
|---------|--------|
| Authority gate | `app.py` — `TARGET_FULLCONTEXT_DEV` branch only |
| Why legacy answers | Default OFF (`config.py`) — sole product reason |
| `/ask` vs `/ask/stream` | Identical `_orchestrate_ask_turn`; packaging only differs |
| Hidden legacy when ON | **None** — `orchestrate_routing_after_resolver` skipped |
| Pre-target guards kept | ingress, flows, rate, reset, anti-spam, target ref nav |
| Legacy skipped when ON | duplicate, continuation, promo, chunk/price ref handlers |
| Target failure modes | All fail-closed target widget routes; no legacy fallback |
| Code blockers | **None** — owner approval for S65 default flip |
| S65 scope | Default ON + offline spy tests + kill-switch docs; no legacy delete |

## Allowlist (actual diff)

| File | Change |
|------|--------|
| `TASK.md` | governance + completion |
| `docs/S64_FULLCONTEXT_AUTHORITY_AUDIT.md` | new |
| `docs/STRANGLER_ROADMAP.md` | S63/S64/S65 |
| `docs/FLAGS_AND_STATUS.md` | clarification |
| `drafts/checker_last.md` | PRE-CODE + COMPLETION reports |

## Commands run

```powershell
git diff --check
python -c "from evals.v5.s63_target_runtime_live_contract import assert_frozen_s62_live_artifacts_unchanged; assert_frozen_s62_live_artifacts_unchanged(); print('S62 frozen OK')"
git diff 520e34a -- evals/v5/artifacts/s62_* evals/v5/artifacts/s63_*
```

## Acceptance (COMPLETION)

- [x] PRE-CODE checker ✅ (`e7c57a2`)
- [x] Audit doc complete, code-traced
- [x] Both endpoints covered; legacy fallback checked
- [x] S65 minimal with allowlist
- [x] No product code, no live, no authority, no A9
- [x] S62 frozen artifacts unchanged
- [x] `git diff --check` clean
- [x] COMPLETION checker ✅
- [x] Completion commit + push `origin/codex/stage-a` (`0e9d98b`)

## Checker

| Checkpoint | Verdict |
|---|---|
| PRE-CODE (`e7c57a2`) | ✅ |
| COMPLETION | ✅ |

**STOP — await owner decision on S65 authority switch.**
