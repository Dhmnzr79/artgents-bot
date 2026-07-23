# TASK — S53 Verifier-only live replay on frozen S50 candidates

**Baseline:** `codex/stage-a` / `297767c` · **ONE LIVE RUN AUTHORIZED**

**Owner approval (2026-07-23):**
- Model: `qwen3.7-plus` (semantic verifier only)
- Budget: **19** Verifier provider calls, **0** Composer provider calls
- No retry / repair / voting / second pass / rerun
- Automated gates from S52 — **approved**
- Full S50 rerun — **forbidden**

**Goal:** Execute one S53 verifier-only live eval on 19 frozen S50 v2 candidate texts via S52 replay harness; persist immutable artifacts; produce manual review artifact.

## Frozen sources (unchanged)

| Object | Path | Pin |
|--------|------|-----|
| S50 v2 result | `evals/v5/artifacts/fullcontext_response_eval_v2_live_result.json` | SHA-256 `273fb2dd7228bd31bb6f981399a77fcdb59336e07e99ba1ccd14005096bc39aa` |
| Matrix v2 | `evals/v5/demo/fullcontext_response_eval_matrix_v2.json` | git blob `615714c519a92a75e23c2f15bbaa01a0f88a4d95` |
| Replay matrix | `evals/v5/demo/fullcontext_verifier_replay_matrix.json` | git blob `a273a58d96b00a76fd22b4d6fc9b97791df4f6d1` |

S47/S50 artifacts — protected, no bytes changed.

## Live wiring

1. Frozen candidate Composer backend (0 provider calls).
2. Live semantic backend only — reuse S47 verifier SDK path, isolated in `fullcontext_verifier_replay_live_backend.py`.
3. Attempt marker exclusive-create before first provider call.
4. Append-only call ledger entry **before** each verifier provider call.
5. raw/result/manifest exclusive-create; JSON serialized in memory before `open("x")`.
6. `fc_terminal_01`: 0 provider calls.

## Automated gates (owner-approved)

Same as S52 `AUTOMATED_ACCEPTANCE_GATES`; live run must satisfy all gates.
Even on automated pass: **FINAL = PENDING_MANUAL_REVIEW** until manual review artifact appended.

## Allowlist

- `TASK.md`
- `evals/v5/fullcontext_verifier_replay_live_backend.py`
- `evals/v5/fullcontext_verifier_replay_contract.py`
- `evals/v5/run_fullcontext_verifier_replay.py`
- `tests/test_fullcontext_verifier_replay_harness.py`
- `evals/v5/artifacts/fullcontext_verifier_replay_live_*`
- `evals/v5/artifacts/fullcontext_verifier_replay_manual_review.json`
- `docs/STRANGLER_ROADMAP.md` (completion only)

## Protected

- S47/S50 frozen matrices/artifacts/logs
- Product Verifier/Composer/runtime
- `evals/v5/run_fullcontext_response_eval.py` (no rework)

## Process

1. Governance commit → PRE-CODE ✅
2. Live wiring (allowlist)
3. Targeted pytest (mock LLM; no live in tests)
4. **One** `--live` run (19 verifier calls max)
5. Manual review artifact
6. COMPLETION checker ✅
7. Completion commit + push → STOP

## Acceptance

1. Immutable live artifacts written once; attempt marker blocks rerun.
2. Automated gates evaluated; manual review artifact for 19 cases.
3. No Composer provider calls; no S50 rerun.
4. Blast-radius summary in result.
