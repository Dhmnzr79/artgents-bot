# TASK — S55 verifier-only live replay v2 (COMPLETE)

**Baseline:** `codex/stage-a` / `6427088` · **ONE LIVE RUN EXECUTED**

## Result

| Field | Value |
|-------|-------|
| Measurement | `s55_fullcontext_verifier_replay_v2_live` |
| Matrix v2 hash | `009977fca3a3e2a37b5c865f74c55c49c00de669` |
| Verifier calls | 19 |
| Composer calls | 0 |
| Decision match | **17/19** |
| False blocks | 0 |
| Missed blocks | 2 (`fc_missing_01`, `fc_boundary_03`) |
| Automated verdict | **AUTOMATED_FAIL** |
| Final verdict | **FAIL** (pending manual review) |

## S55 artifact SHA-256 pins (immutable)

| Artifact | SHA-256 |
|----------|---------|
| `fullcontext_verifier_replay_v2_live_raw.json` | `0f599bd7e01d7574d1ffd8c4a4dda04e2f3b21eb868e6a09d2ba37c1ebb4a081` |
| `fullcontext_verifier_replay_v2_live_result.json` | `2af56925e4ea8c21cd4ef287933929af54baf8981c4ddd17464674ed418b3fc1` |
| `fullcontext_verifier_replay_v2_live_manifest.json` | `1bd78abc9446c87a0f000d8b6de8489895bb0b99f694e145e364d09b96313bcf` |
| `fullcontext_verifier_replay_v2_live_attempt.json` | `ffdb0b8f079e82070021e630c6229091c51c1c01ffaa9aa4642019544324305b` |
| `fullcontext_verifier_replay_v2_live_call_ledger.jsonl` | `c1d3c7582de09da90420a6c6632b45ce2125b83ff3a1742a1ed91f3a3dd50bd8` |
| `fullcontext_verifier_replay_v2_manual_review.json` | `4c2d0306630056758d3ceffd4d101638f18f15c6321ddeb0c0f89f236cb9311f` |

## Protected unchanged

S53 frozen SHA pins verified post-run. S50/S47 artifacts not touched.

## STOP

No rerun. Manual review pending.
