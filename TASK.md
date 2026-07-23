# TASK — S61 test-hardening (pre-live checkpoint)

**Baseline:** `codex/stage-a` / `fdebfbb` · **OFFLINE ONLY · NO LIVE**

## Scope

Last S61 checkpoint before live. **Test hardening only** — product code changes only if new tests expose a real defect.

Not a new architecture milestone. NO LIVE / NO LLM / NO authority / NO A9.

## Gaps to close

1. **Stale CTA pipeline test** — `test_real_s34_failure_reaches_no_s39_backends` expects old forbid contract; update to owner-ratified clamp (`include_cta=True` + `allow_cta=False` → clamp, not error).
2. **Fail-closed neighbor** — separate test proving marketing/consultation widen still blocks S39 backends.
3. **Session/frequency** — concrete fact/consultation ID selection, session persistence, shown inputs on turn 2, suppression, union/dedupe, terminal/error no mutation.
4. **Legacy bypass coverage** — flag ON must not call legacy handlers for all knowledge short-circuits; unknown ref + known follow-up via HTTP.
5. **HTTP integration** — `/ask` follow-up ref click; two sequential session turns with fake backends.

## Критерии приёмки

### A. Stale CTA test (owner-ratified clamp)

- [ ] `include_cta=True` + `spec.allow_cta=False` → pipeline completes (no `spec_package_permission_forbidden`).
- [ ] `selected_cta_key is None`; CTA absent from verified response/widget path.
- [ ] Composer and Verifier receive `allow_cta=false` in directives/spec JSON.
- [ ] Adjacent test: marketing or consultation widen → `spec_package_permission_forbidden`; Composer/Verifier **not** called.

### B. Session / frequency

- [ ] Turn 1 selects a **specific** fact or consultation ref ID (not `isinstance(tuple)`).
- [ ] After materialized response, that ID is in session state.
- [ ] Turn 2 pipeline receives prior shown IDs as inputs.
- [ ] Same constrained fact **not** re-selected on turn 2.
- [ ] Stable union/dedupe across turns.
- [ ] Terminal/error response does **not** mutate session shown IDs.

### C. Legacy bypass (TARGET_FULLCONTEXT_DEV=1)

Each case: legacy handler / `get_chunk_by_ref` **not** called; urgent/manual-contact/operational guards preserved.

- [ ] price widget ref
- [ ] consult/symptom ref
- [ ] kb/chunk ref
- [ ] promo overview
- [ ] `continuation_without_context`
- [ ] `current_doc` continuation
- [ ] short contextual
- [ ] duplicate short-circuit
- [ ] unknown ref → controlled target clarify
- [ ] known follow-up ref click → label mapped (pre-resolver + HTTP)

### D. HTTP integration

- [ ] `/ask` flag ON: follow-up ref click resolves label, legacy routing not called.
- [ ] `/ask` flag ON: two sequential turns — turn 2 receives session shown IDs (fake backends).
- [ ] `/ask/stream` flag ON: batch ui+done (existing or refined).

## Затрагиваемые файлы (allowlist)

| File | Change |
|------|--------|
| `TASK.md` | S61 test-hardening governance |
| `docs/STRANGLER_ROADMAP.md` | completion note after COMPLETION ✅ |
| `tests/test_demo_target_policy_bound_verified_response_pipeline.py` | CTA clamp + fail-closed neighbor |
| `tests/test_s61_correction_target_runtime.py` | session, bypass, HTTP hardening |

**Product code:** only if a new test exposes a real defect (must be documented in commit).

## Protected / forbidden

- No LIVE / LLM / authority / A9
- No protected acceptance/golden/target/current changes
- No Verifier semantics change
- `TARGET_FULLCONTEXT_DEV` default remains OFF

## Targeted pytest

```powershell
$bt = Join-Path $env:TEMP ("s61hard_pytest_" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_s61_correction_target_runtime.py `
  tests/test_s61_target_fullcontext_runtime.py `
  tests/test_demo_target_policy_bound_verified_response_pipeline.py `
  tests/test_target_spec_offline_response_package.py `
  tests/test_demo_target_marketing_selection.py `
  tests/test_target_boundary_enforced_fullcontext_response.py `
  tests/test_s59_semantic_verifier_policy.py `
  tests/test_fullcontext_verifier_replay_s54.py `
  -q
```

## Checker process

| Checkpoint | Required |
|---|---|
| PRE-CODE | before implementation |
| COMPLETION | **✅** (`fdebfbb…83e559e`) |

Push only to `origin/codex/stage-a`.
