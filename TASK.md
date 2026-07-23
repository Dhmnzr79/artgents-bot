# TASK — S52 Issue-based Verifier-only replay preparation

**Baseline:** `codex/stage-a` / `9fc4009` · **NO LIVE** · **NO LLM**

**Goal:** Prepare isolated offline harness for future **Verifier-only** live eval of S51
issue-based semantic Verifier on **19 frozen S50 v2 candidate responses**. Do **not**
generate new Composer answers. Do **not** run live.

## Frozen sources (byte-identical)

| Object | Path | Pin |
|--------|------|-----|
| S50 v2 result | `evals/v5/artifacts/fullcontext_response_eval_v2_live_result.json` | SHA-256 `273fb2dd7228bd31bb6f981399a77fcdb59336e07e99ba1ccd14005096bc39aa` |
| Matrix v2 | `evals/v5/demo/fullcontext_response_eval_matrix_v2.json` | git blob `615714c519a92a75e23c2f15bbaa01a0f88a4d95` |

S50 raw/manifest/marker/log and S47/S50 incident artifacts — **protected, no bytes changed**.

## Architecture

1. Load `response_text` for 19 materializable cases from frozen S50 result; verify SHA per case.
2. Replay matrix stores metadata only (no long candidate texts).
3. Reconstruct request/spec/evidence from matrix v2 + existing public loaders/S46 wiring.
4. **Frozen candidate Composer backend** returns saved text — offline, **not** a provider call.
5. Reuse S46→S51 pipeline; **no** parallel response pipeline.
6. Future live: **19 Semantic Verifier provider calls only**; Composer provider calls **0**.
7. Live semantic backend seam prepared but **not invoked** in S52.

## Owner labels (19 materializable)

**BLOCK (3):** `fc_medical_03`, `fc_missing_01`, `fc_missing_02` —
`required_blocking_issue_kinds`: [`material_external_medical_claim`]

**PASS (16):** all other materializable cases listed in user brief.

**Terminal control:** `fc_terminal_01` — 0 Composer + 0 Verifier provider calls.

`minor_external_detail` = warning only; does not flip PASS→BLOCK.

## Future live budget (pending_owner_approval — do NOT run)

- Model recommendation: `qwen3.7-plus`
- Exactly **19** Semantic Verifier LLM calls; **0** Composer LLM calls
- No retry/repair/voting/second pass
- Attempt marker exclusive-create before first provider call
- Append-only call ledger; exclusive-create raw/result/manifest
- FINAL = `PENDING_MANUAL_REVIEW` until append-only manual review artifact

## Allowlist

- `TASK.md`
- `evals/v5/demo/fullcontext_verifier_replay_matrix.json`
- `evals/v5/fullcontext_verifier_replay_contract.py`
- `evals/v5/fullcontext_verifier_replay_backend.py`
- `evals/v5/run_fullcontext_verifier_replay.py`
- `tests/test_fullcontext_verifier_replay_matrix_contract.py`
- `tests/test_fullcontext_verifier_replay_harness.py`
- `docs/STRANGLER_ROADMAP.md` (completion status only)

## Protected

- S47/S50 matrices, live raw/result/manifest/marker/log, incident artifacts
- `core/target_response_verifier.py`, `core/target_composer_executor.py` (product)
- `evals/v5/run_fullcontext_response_eval.py`, S47/S50 harness contract (no rework)
- runtime/UI/A9/authority

## Isolated future-live artifact paths

- `evals/v5/artifacts/fullcontext_verifier_replay_live_raw.json`
- `evals/v5/artifacts/fullcontext_verifier_replay_live_result.json`
- `evals/v5/artifacts/fullcontext_verifier_replay_live_attempt.json`
- `evals/v5/artifacts/fullcontext_verifier_replay_live_call_ledger.jsonl`
- `evals/v5/artifacts/fullcontext_verifier_replay_live_manifest.json`
- `evals/v5/artifacts/fullcontext_verifier_replay_manual_review.json`

Must not overlap S47/S50 default artifact paths.

## Offline acceptance

1. Frozen S50 result SHA verified before candidate load.
2. Exactly 19 materializable case IDs; 16 pass / 3 block labels.
3. All `candidate_text_sha256` match frozen result.
4. `fc_terminal_01` terminal control: 0 provider calls.
5. Fake issue-based semantic backend: pass/block/minor/wrong-kind/malformed/span validation.
6. Frozen Composer backend cannot invoke live provider (import/call firewall).
7. Default CLI → `LIVE_NOT_CONFIGURED`; `--dry-run` validates only.
8. Existing attempt marker or output artifact blocks backend factory.
9. Frozen S47/S50 SHA pins unchanged.
10. Blast-radius summary covers mass-selling groups, not only 3 medical blocks.
11. No five-boolean metrics in active S52 contract.

## Required tests

```powershell
$bt = Join-Path $env:TEMP ("pytest-s52-" + [guid]::NewGuid().ToString("n"))
.\.venv\codex312\Scripts\python.exe -m pytest `
  tests/test_fullcontext_verifier_replay_matrix_contract.py `
  tests/test_fullcontext_verifier_replay_harness.py `
  -p no:cacheprovider --basetemp=$bt -q
```

## Process

1. Governance commit → PRE-CODE checker ✅
2. Implementation (allowlist only)
3. Targeted pytest (NO LIVE)
4. COMPLETION checker ✅
5. Completion commit + push `codex/stage-a` → STOP

## Acceptance

1. New replay zone complete; S47/S50 harness untouched.
2. Matrix hash pinned; source/result SHA verified.
3. All offline acceptance cases pass.
4. NO LIVE / NO LLM / NO Composer provider calls.
