# TASK — S65 FullContext authority switch (offline) — COMPLETE

**Baseline:** `codex/stage-a` / `9dddd9f`
**Governance commit:** `b6ce887`
**Status:** **COMPLETE** · **PRODUCT AUTHORITY SWITCHED OFFLINE** · **NO LIVE / NO LLM**

## Goal (done)

Default product authority = target FullContext for `/ask` and `/ask/stream`. Legacy = manual kill-switch `TARGET_FULLCONTEXT_DEV=0` at process start. No in-turn legacy fallback.

## Changes

| File | Change |
|------|--------|
| `config.py` | `TARGET_FULLCONTEXT_DEV` default `"0"` → `"1"` |
| `tests/test_s65_authority_switch_offline.py` | new — acceptance A–H (19 tests) |
| `tests/test_s61_target_fullcontext_runtime.py` | `test_default_flag_on_in_config` |
| `docs/FLAGS_AND_STATUS.md` | default ON, kill-switch semantics |
| `docs/STRANGLER_ROADMAP.md` | S65 complete, S66 gate |

`app.py` — **not changed** (gate already sufficient).

## Acceptance (COMPLETION)

- [x] PRE-CODE checker ✅ (`b6ce887`)
- [x] `config.py` default ON
- [x] Targeted pytest: **19 passed**
- [x] S62 frozen artifacts unchanged
- [x] `git diff --check` clean
- [x] Allowlist-only diff
- [x] COMPLETION checker ✅
- [x] Completion commit + push `origin/codex/stage-a`

## Commands run

```powershell
$bt = Join-Path $env:TEMP ("s65_pytest_" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_s65_authority_switch_offline.py `
  tests/test_s61_target_fullcontext_runtime.py::test_default_flag_on_in_config `
  -q

git diff --check
python -c "from evals.v5.s63_target_runtime_live_contract import assert_frozen_s62_live_artifacts_unchanged; assert_frozen_s62_live_artifacts_unchanged(); print('S62 frozen OK')"
```

## Checker

| Checkpoint | Verdict |
|---|---|
| PRE-CODE (`b6ce887`) | ✅ |
| COMPLETION | ✅ |

**STOP — no post-switch live run. Next: S66 (owner approval).**
