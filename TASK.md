# TASK — S43 First Live Eval Audit Capture

**Branch / baseline:** `codex/stage-a` / `33e2643 feat: harden S43 medical boundary eval pre-live freeze`

**Goal:** governance recovery — capture the already-executed first permitted S43 live/LLM eval
(wiring + immutable artifacts + audit manifest). **Do not run live again.**

## Owner context (honest)

- Owner **already authorized and completed** the first live run on frozen 26-case matrix.
- Eval-only live wiring appeared during that run but was **not yet committed**:
  - `evals/v5/medical_boundary_eval_live_backend.py`
  - `evals/v5/run_medical_boundary_eval.py` (`--live` path)
- Immutable first artifacts exist on disk with fixed SHA-256 (must remain **byte-identical**):
  - raw `3D32B7689262C2FCC868042CC8673D2124B790F05BEF5B7213C44A342C0DA723`
  - result `F6B33E44786C9AE3148A619025BD58D181E1E0ED387781383931B333D9E75DE1`
- Matrix git blob frozen: `7218e044b2f34b1be5c71b385d407e9ee8fb759d`
- Recorded outcome: exit 0, verdict **PASS**, exact **25/26**, sole non-exact **`mb_border_01`**
- Model **`qwen3.6-flash`** confirmed from run log (`llm_usage`); not embedded in artifacts.

## Owner laws

- **LIVE_ALREADY_RUN_ONCE / DO_NOT_RERUN** — no second live/LLM execution in this task.
- **Do not edit, recreate, or re-hash** existing `medical_boundary_eval_live_raw.json` or
  `medical_boundary_eval_live_result.json`.
- Matrix, thresholds, floors, raw/result content — **frozen**; no post-hoc tuning.
- Capture wiring + manifest + offline CLI tests honestly (wiring already exists).
- Eval-only live backend: no product runtime import; `--live` explicit only; default CLI
  fail-closed; one backend call per case; existing artifacts block backend before calls.
- A9, runtime, UI, session, product authority — untouched.
- Medical FullContext semantics — untouched.

## Deliverables

1. **Audit manifest** `evals/v5/artifacts/medical_boundary_eval_live_audit_manifest.json` with:
   matrix blob hash, baseline commit, raw/result SHA-256, 26 cases/calls, exit 0, PASS,
   25/26 exact, sole non-exact `mb_border_01`, floors 0.80/0.70, acceptance thresholds,
   model + honest provenance source, scope untouched flags, DO_NOT_RERUN.
2. **Commit byte-identical** raw/result artifacts + reviewed live wiring.
3. **Offline CLI/live wiring tests** (fake/monkeypatch only; tmp_path; never touch frozen artifacts).
4. **ARCH/ROADMAP** status update for first S43 live audit only.

## Boundaries / allowlist

- `TASK.md`
- `evals/v5/medical_boundary_eval_live_backend.py`
- `evals/v5/run_medical_boundary_eval.py`
- `evals/v5/medical_boundary_eval_contract.py` (manifest constants/validation only if needed)
- `evals/v5/artifacts/medical_boundary_eval_live_raw.json` (**add only, byte-identical**)
- `evals/v5/artifacts/medical_boundary_eval_live_result.json` (**add only, byte-identical**)
- `evals/v5/artifacts/medical_boundary_eval_live_audit_manifest.json`
- `tests/test_medical_boundary_eval_live_cli.py`
- `tests/test_medical_boundary_eval_matrix_contract.py` (manifest hash test only if needed)
- `tests/test_medical_boundary_eval_harness.py` (only if minimal shared helpers)
- `docs/ARCH_TARGET_DESIGN.md`
- `docs/STRANGLER_ROADMAP.md`

**Forbidden:** matrix/threshold/floor changes; raw/result edits; live rerun; A9/runtime/authority.

## Minimal protected acceptance

- raw/result SHA-256 match owner-fixed values after staging;
- manifest documents full audit record + DO_NOT_RERUN;
- default CLI → `LIVE_NOT_CONFIGURED` (exit 3);
- existing artifacts block `--live` before backend (exit 2);
- fake `--live` PASS → exit 0; FAIL → exit 4; exclusive-create enforced;
- offline tests green; no skip/xfail; no real LLM.

Run only:

- `tests/test_medical_boundary_eval_matrix_contract.py`
- `tests/test_medical_boundary_eval_harness.py`
- `tests/test_medical_boundary_eval_live_cli.py`
- `tests/test_target_medical_boundary.py`

Use external `--basetemp` and `-p no:cacheprovider`. **No full pytest. No live run.**

## Gates

1. Independent **PRE-COMMIT** checker on exact dirty snapshot (governance TASK only first).
2. Commit/push `docs: govern S43 first live eval audit capture` (**TASK.md only**).
3. Implement allowlist; verify SHA-256 unchanged; run targeted offline tests.
4. Independent **COMPLETION** checker.
5. One completion commit: wiring + tests + manifest + immutable artifacts + docs; push; clean/synced.
