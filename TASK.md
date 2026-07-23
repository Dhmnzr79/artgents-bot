# TASK — S55 verifier-only live replay v2

**Baseline:** `codex/stage-a` / `6427088` · **ONE LIVE RUN AUTHORIZED**

**Goal:** One owner-approved verifier-only live replay on matrix v2 (19 frozen S50
candidates, updated owner labels). Immutable artifacts + manual review seed.

## Owner approval (binding)

- Model: `qwen3.7-plus`
- Max Verifier provider calls: **19** (materializable cases)
- Composer provider calls: **0**
- Retry/repair/rerun: **forbidden**
- Matrix v2 git blob hash: `009977fca3a3e2a37b5c865f74c55c49c00de669`
- Automated gates: **owner_approved** (same thresholds as S53 contract constants)
- Expected block cases (v2): fc_medical_03, fc_missing_01, fc_missing_02, fc_boundary_02, fc_boundary_03

## Protected (do not rerun / modify)

- S53 live artifacts (frozen SHA pins in S54 TASK)
- S50/S47 live artifacts
- Matrix v1 `a273a58d96b00a76fd22b4d6fc9b97791df4f6d1`
- Matrix v2 content (hash pinned — no file edits)

## V2 live artifact paths (exclusive write)

- `evals/v5/artifacts/fullcontext_verifier_replay_v2_live_raw.json`
- `evals/v5/artifacts/fullcontext_verifier_replay_v2_live_result.json`
- `evals/v5/artifacts/fullcontext_verifier_replay_v2_live_manifest.json`
- `evals/v5/artifacts/fullcontext_verifier_replay_v2_live_attempt.json`
- `evals/v5/artifacts/fullcontext_verifier_replay_v2_live_call_ledger.jsonl`
- `evals/v5/artifacts/fullcontext_verifier_replay_v2_manual_review.json`

## Allowlist

- `TASK.md`
- `evals/v5/fullcontext_verifier_replay_contract.py`
- `evals/v5/fullcontext_verifier_replay_live_backend.py`
- `evals/v5/run_fullcontext_verifier_replay.py`
- `tests/test_fullcontext_verifier_replay_s54.py`
- `docs/STRANGLER_ROADMAP.md`

## Acceptance

1. `--matrix-v2 --live` runs once; v2 artifact guards isolated from S53 marker.
2. 19 verifier / 0 composer provider calls; canonical issue parser for scoring.
3. Immutable artifacts written exclusively; manual review seeded from matrix v2.
4. S53/S50 artifacts byte-identical after run.
5. Targeted offline pytest green.

## Live command

```powershell
.\.venv\codex312\Scripts\python.exe evals/v5/run_fullcontext_verifier_replay.py --matrix-v2 --live
```

## Process

Governance commit → wire v2 live → run once → artifact commit → push → STOP
