# TASK — S61 correction (target-only ingress, CTA, session, strategy)

**Baseline:** `codex/stage-a` / `8d7463f` · **OFFLINE ONLY · NO LIVE**

## Owner decision

Fix four S61 runtime gaps before any live test. No new architecture, no Verifier semantics change, no authority flip.

## Gaps to fix

1. **Target-only precedence** — flag ON must not hit legacy knowledge short-circuits in pre-resolver (price/consult ref, chunks, promo, continuation).
2. **CTA permissions** — remove global `include_cta=False`; effective CTA = client capability ∧ spec.allow_cta at spec-bound boundary.
3. **Session frequency** — persist actually selected fact/amplifier/consultation IDs after materialized response.
4. **Strategy context** — remove hardcoded `implantology/full_arch`; derive family from service catalog only; extent only if explicitly authored.

Plus: HTTP integration tests for `/ask` and `/ask/stream`.

## Do NOT

- LIVE / LLM / authority / A9
- New Verifier milestone / issue kinds
- Change frozen S47/S50/S53/S55/S58 artifacts
- RAG / per-MD routing / shadow branch
- Enable dev flag in running server

## Затрагиваемые файлы (allowlist)

| File | Change |
|------|--------|
| `TASK.md` | S61 correction governance |
| `docs/STRANGLER_ROADMAP.md` | correction note |
| `contracts/target_turn_frame_dispatch.py` | session selection sidecar |
| `core/target_spec_offline_response_package.py` | effective_include_cta |
| `core/target_session_selection.py` | **new** extract selection from bound package |
| `core/target_policy_bound_verified_response_pipeline.py` | internal bound+verify helper |
| `core/target_turn_frame_bound_response.py` | attach session sidecar |
| `core/target_runtime_strategy.py` | **new** service-derived strategy match |
| `core/target_runtime_client_context.py` | cta_capability; remove hardcoded strategy |
| `core/target_runtime_turn.py` | dynamic strategy + cta_capability |
| `core/target_runtime_session.py` | merge shown IDs; store follow-ups |
| `core/target_runtime_followup_nav.py` | **new** target ref→q bridge |
| `orchestration/pre_resolver_turn.py` | target_fullcontext_mode skips legacy knowledge |
| `orchestration/target_fullcontext_turn.py` | resolve ref before target turn |
| `app.py` | pass target mode to pre-resolver |
| `tests/test_s61_correction_target_runtime.py` | **new** correction acceptance |
| `tests/test_s61_target_fullcontext_runtime.py` | update for corrections |

## Protected / forbidden

- Frozen eval artifacts unchanged
- Verifier S59 semantics unchanged
- S47/S50/S53/S55/S58 byte-identical

## Targeted pytest

```powershell
$bt = Join-Path $env:TEMP ("s61corr_pytest_" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_s61_correction_target_runtime.py `
  tests/test_s61_target_fullcontext_runtime.py `
  tests/test_target_spec_offline_response_package.py `
  tests/test_demo_target_marketing_selection.py `
  tests/test_target_boundary_enforced_fullcontext_response.py `
  tests/test_s59_semantic_verifier_policy.py `
  tests/test_fullcontext_verifier_replay_s54.py `
  -q
```

## Commits

1. Governance: TASK.md, STRANGLER note
2. Implementation: correction modules + tests

Push only to `origin/codex/stage-a`.

## PRE-CODE / COMPLETION checker

Required before/after implementation.
