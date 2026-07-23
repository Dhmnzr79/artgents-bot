# TASK — S62 offline runtime/harness correction (Checkpoint B)

**Baseline:** `codex/stage-a` / `396a226` · **NO LIVE / NO LLM / NO RERUN**

## Scope

Offline correction after S62 post-live audit (`S62_NOT_PASSED`). Frozen live artifacts remain immutable.

## B1 — doctors/session continuity

- Root cause: planner shadow frame built from raw LLM output before focus enrichment; target runtime read shadow without `service_id`.
- Fix: `hydrate_target_runtime_turn_frame_from_session` in target runtime path using `last_service_id` for vague contextual follow-ups only.

## B2 — CTA widget mapping

- Map `selected_cta_key` → authored client CTA via `lead_cta_dict_from_meta` with `cta_action=lead`.
- Fail-closed on unknown keys.

## B3 — follow-up click criterion

- Harness uses any displayed target quick reply (not price-only).

## B4 — harness accounting/verdict

- Provider audit rebinds module-level `chat_completions_create` imports.
- Corrected gates: follow-up ref, doctors materialized, CTA widget, ledger ingress/planner completeness.
- Read-only frozen recompute → `AUTOMATED_FAIL`.

## Allowlist

| File | Change |
|------|--------|
| `TASK.md` | Checkpoint B governance |
| `core/target_runtime_turn_frame_hydration.py` | session hydration |
| `core/target_runtime_turn.py` | wire hydration |
| `core/target_runtime_widget.py` | CTA mapping |
| `evals/v5/s62_target_runtime_live_provider_audit.py` | audit rebind |
| `evals/v5/s62_target_runtime_live_harness.py` | gates/follow-up |
| `evals/v5/s62_target_runtime_live_recompute.py` | frozen recompute |
| `tests/test_s62_correction_offline.py` | correction tests |
| `tests/test_s62_target_runtime_live_harness.py` | harness test updates |
| `docs/STRANGLER_ROADMAP.md` | completion note |

**Forbidden:** live/LLM, frozen S62 live artifact edits, Verifier changes, authority/A9.

## Commands

```powershell
$bt = Join-Path $env:TEMP ("s62b_pytest_" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_s62_correction_offline.py `
  tests/test_s62_target_runtime_live_harness.py `
  -q
```

## Checker

| Checkpoint | When |
|---|---|
| PRE-CODE | before implementation |
| COMPLETION | after pytest green |
