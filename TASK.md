# TASK — S61 target FullContext runtime path (dev flag OFF by default)

**Baseline:** `codex/stage-a` / `8f98cc2` · **OFFLINE ONLY · NO LIVE**

## Owner decision

Wire S39–S59 target FullContext chain into real `/ask` runtime behind one off-by-default dev flag. Flag ON = target-only (no legacy RAG, no fallback). Flag OFF = unchanged legacy path. No product authority flip in S61.

## Scope

- `TARGET_FULLCONTEXT_DEV=0` default in `config.py`
- Product runtime bootstrap (client pack + cached FullContext, once per client/process)
- TurnFrame bridge from planner shadow ctx (no second planner call)
- Medical boundary + S46 entry point with injected backends
- Product LLM backend module (promoted from eval pattern; no `evals/` import in product)
- Widget materializer + minimal session bridge
- `/ask` + `/ask/stream` routing when flag ON (batch final payload for stream)
- Fail-closed controlled responses on block/error (no legacy fallback)

## Do NOT

- LIVE / LLM in S61 tests or process
- Enable dev flag in real local server
- Product authority ON
- A9 authority / frozen A9 artifacts
- Runtime logging / admin UI
- Parallel target+legacy execution
- Legacy fallback after target selected
- New Verifier milestone / RAG / retriever / per-MD routing
- Change frozen S47/S50/S53/S55/S58 artifacts

## Затрагиваемые файлы (allowlist)

| File | Change |
|------|--------|
| `TASK.md` | S61 governance |
| `docs/STRANGLER_ROADMAP.md` | S61 checkpoint |
| `docs/FLAGS_AND_STATUS.md` | flag doc |
| `config.py` | `TARGET_FULLCONTEXT_DEV` |
| `core/target_runtime_client_context.py` | **new** bootstrap |
| `core/target_runtime_turn_frame_bridge.py` | **new** TurnFrame from ctx |
| `core/target_runtime_llm_messages.py` | **new** shared prompt builders |
| `core/target_runtime_llm_backends.py` | **new** product Composer/Verifier/Boundary backends |
| `core/target_runtime_turn.py` | **new** S46 runtime entry |
| `core/target_runtime_widget.py` | **new** widget payload mapper |
| `core/target_runtime_session.py` | **new** session bridge |
| `core/turn_frame_shadow.py` | runtime TurnFrame getter |
| `orchestration/target_fullcontext_turn.py` | **new** ask orchestration hook |
| `app.py` | flag branch in `_orchestrate_ask_turn` |
| `tests/test_s61_target_fullcontext_runtime.py` | **new** acceptance tests |

## Protected / forbidden

- Frozen eval artifacts unchanged
- Verifier S59 semantics unchanged
- No import of `evals/` from product modules

## Targeted pytest

```powershell
$bt = Join-Path $env:TEMP ("s61_pytest_" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_s61_target_fullcontext_runtime.py `
  tests/test_target_boundary_enforced_fullcontext_response.py `
  tests/test_s56_missing_base_composer_guard.py `
  tests/test_s59_semantic_verifier_policy.py `
  tests/test_target_turn_frame_dispatch.py `
  -q
```

## Commits

1. Governance: TASK.md, STRANGLER, FLAGS
2. Implementation: runtime modules + app wiring + tests

Push only to `origin/codex/stage-a`.

## PRE-CODE / COMPLETION checker

Required before/after implementation.
