# TASK — S65 FullContext authority switch (offline)

**Baseline:** `codex/stage-a` / `9dddd9f` · **OWNER APPROVED** · **NO LIVE / NO LLM**

## Goal

Make target FullContext the **default product authority** for `/ask` and `/ask/stream`. Legacy remains a **manual kill-switch** via `TARGET_FULLCONTEXT_DEV=0` at process start. **No in-turn legacy fallback.**

## Owner decisions (binding)

- Default authority = target FullContext
- Target errors = fail-closed (controlled target widget only)
- `TARGET_FULLCONTEXT_DEV=0` = explicit legacy kill-switch between requests/processes
- No legacy deletion, no rollout %, no shadow, no verifier/composer/planner changes

## Implementation

| Change | Detail |
|--------|--------|
| `config.py` | `TARGET_FULLCONTEXT_DEV` default `"0"` → `"1"`; update comment |
| `app.py` | **No change** unless PRE-CODE/code trace proves required (gate already uses imported flag) |

## Allowlist

| File | Change |
|------|--------|
| `TASK.md` | S65 governance + completion |
| `config.py` | default ON |
| `tests/test_s65_authority_switch_offline.py` | new — acceptance A–H |
| `tests/test_s61_target_fullcontext_runtime.py` | **only** `test_default_flag_off_in_config` → default ON assertion |
| `docs/FLAGS_AND_STATUS.md` | default ON, kill-switch semantics |
| `docs/STRANGLER_ROADMAP.md` | S65 complete, authority transferred |

**Forbidden:** `app.py` (unless escalated), legacy deletion, live/LLM, A9, frozen artifacts, verifier/composer/planner changes, new flags, rollout/shadow.

## Offline acceptance tests (`test_s65_authority_switch_offline.py`)

| ID | Requirement |
|----|-------------|
| A | Default (no env): target orchestrator called; legacy not; `/ask` + `/ask/stream` |
| B | `TARGET_FULLCONTEXT_DEV=0`: legacy called; target not |
| C | `TARGET_FULLCONTEXT_DEV=1`: target called; legacy not |
| D | Target failure: controlled error; legacy never called; single architecture per turn |
| E | Guards: ingress hard-stop/manual_contact; lead flow; target ref navigation |
| F | Spy: no `orchestrate_routing_after_resolver`, `route_source`, legacy composer, `get_chunk_by_ref` on target ref path |
| G | Session continuity, CTA/follow-up, JSON/SSE same authority |
| H | `assert_frozen_s62_live_artifacts_unchanged()` |

Fake/spy backends only. No live/LLM.

## Commands

```powershell
$bt = Join-Path $env:TEMP ("s65_pytest_" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_s65_authority_switch_offline.py `
  tests/test_s61_target_fullcontext_runtime.py::test_default_flag_on_in_config `
  -q

git diff --check
python -c "from evals.v5.s63_target_runtime_live_contract import assert_frozen_s62_live_artifacts_unchanged; assert_frozen_s62_live_artifacts_unchanged(); print('S62 frozen OK')"
```

## Acceptance (COMPLETION)

- [ ] PRE-CODE checker ✅
- [ ] `config.py` default ON
- [ ] Targeted pytest green
- [ ] S62 frozen artifacts byte-identical
- [ ] `git diff --check` clean
- [ ] Allowlist-only diff
- [ ] COMPLETION checker ✅
- [ ] Completion commit + push `origin/codex/stage-a`

## Checker

| Checkpoint | When |
|---|---|
| PRE-CODE | after governance commit, before code |
| COMPLETION | after pytest green |

**STOP after offline S65 — no post-switch live run.**
