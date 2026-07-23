# TASK — S67 legacy answer path isolation

**Baseline:** `codex/stage-a` / `d558efb` · **NO LIVE / NO LEGACY DELETE**

## Goal

Isolate legacy RAG/chunk/composer answer-production stack from default FullContext path loading/execution. Legacy remains available **only** via manual kill-switch `TARGET_FULLCONTEXT_DEV=0` (process restart). **Isolation, not deletion.**

## Seam audit (read-only, `app.py` @ `d558efb`)

| Seam | Current | S67 change |
|------|---------|------------|
| Top-level `from orchestration.ask_turn import orchestrate_routing_after_resolver` | Eager; pulls `source_routing`, `composer_flow`, `answer_planner`, `md_chunks` | **Lazy** inside `TARGET_FULLCONTEXT_DEV=0` branch only |
| Top-level `from chunk_responder import ...` | Eager | **Lazy** inside `chunk`/`composer` dispatch only |
| `_orchestrate_ask_turn` | Target branch before legacy | **Unchanged** semantics |
| `_service_reply` | `answer_plan_from_ctx` + plan append for `price_lookup`/`catalog_facts` routes | **Skip** legacy plan block for `target_fullcontext_*` routes |
| `_sse_service_reply` | No answer-plan block | **Unchanged** (already target-safe) |
| Shared: ingress, flows, resolver, target turn, finalize_ask, UI policy | Pre-target / delivery | **Keep** |

**Shared (not legacy):** `pre_resolver_turn`, `resolver_turn`, `target_fullcontext_turn`, `lead_flow`, `finalize_ask`, `apply_ui_source_policy`, `policy_compat`.

## Allowlist

| File | Change |
|------|--------|
| `TASK.md` | governance + completion |
| `app.py` | lazy legacy imports; target `_service_reply` guard |
| `tests/test_s67_legacy_isolation_offline.py` | acceptance A–J |
| `docs/STRANGLER_ROADMAP.md` | S67 status |
| `docs/FLAGS_AND_STATUS.md` | kill-switch lazy legacy note |

**Forbidden:** legacy file deletion, kill-switch removal, fallback, FullContext policy changes, S66 counter fix, frozen artifact edits, A9, live/LLM.

## Legacy modules (import firewall check list)

Eager load **forbidden** on default `import app`:

- `orchestration.ask_turn`
- `chunk_responder`
- `source_routing`
- `orchestration.composer_flow`

## Offline tests (`test_s67_legacy_isolation_offline.py`)

| ID | Requirement |
|----|-------------|
| A | Subprocess import app; legacy modules not in `sys.modules` |
| B | Default `/ask` — target only; legacy spies = 0 |
| C | Default `/ask/stream` — same + SSE |
| D | Target error — no legacy activation |
| E | Target ref-click — no `get_chunk_by_ref` |
| F | Kill-switch subprocess `=0` — legacy orchestrator called; target not |
| G | Ingress hard-stop; lead flow; planner path |
| H | Session/CTA; no legacy post-processing on target route |
| I | S62+S63+S66 frozen byte-identical |
| J | Target modules don't import legacy stack |

Also run: `tests/test_s65_authority_switch_offline.py` (subset), `tests/test_s61_correction_target_runtime.py` HTTP tests if green.

## Commands

```powershell
$bt = Join-Path $env:TEMP ("s67_pytest_" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_s67_legacy_isolation_offline.py `
  tests/test_s65_authority_switch_offline.py `
  -q

git diff --check
python -c "from evals.v5.s66_default_authority_live_contract import assert_frozen_s62_live_artifacts_unchanged, assert_frozen_s63_live_artifacts_unchanged; from tests.test_s67_legacy_isolation_offline import _assert_frozen_s66_artifacts_unchanged; assert_frozen_s62_live_artifacts_unchanged(); assert_frozen_s63_live_artifacts_unchanged(); _assert_frozen_s66_artifacts_unchanged(); print('frozen OK')"
```

## Acceptance

- [x] PRE-CODE checker ❌ on governance (`e38eefe`) — frozen command gap in TASK; implementation adds S66 pins in test I
- [x] Default path lazy isolation
- [x] Kill-switch `=0` works
- [x] Targeted pytest green (35 S67+S65; 61 with S61 neighbor)
- [x] Frozen artifacts unchanged (S62+S63+S66)
- [ ] COMPLETION checker
- [ ] Push `origin/codex/stage-a`

**STOP after S67 — deletion inventory is separate milestone.**
