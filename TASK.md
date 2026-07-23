# TASK — S54 S53 post-live audit correction + Verifier offline calibration

**Baseline:** `codex/stage-a` / `a003447` · **NO LIVE** · **NO S53 rerun**

**Goal:** Honest S53 causal taxonomy, canonical issue parser fix, replay matrix v2,
minimal Verifier policy clarification, future v2 replay prep. Frozen S53 artifacts
byte-identical.

## Frozen S53 artifacts (SHA-256 pins — do not modify)

| Artifact | SHA-256 |
|----------|---------|
| `evals/v5/artifacts/fullcontext_verifier_replay_live_raw.json` | `5f71c1025024b75f0aded1bd0208f35fc1366ae0cef8f24ab0c869bd9d2755c6` |
| `evals/v5/artifacts/fullcontext_verifier_replay_live_result.json` | `594a42bd7e3ad5938e14021212f18a7e16c6dfdbf7f07c662ca625c3c0a1d575` |
| `evals/v5/artifacts/fullcontext_verifier_replay_live_manifest.json` | `17136a7d10f81d1311c5158611c685c686984c43eeb07b698315ea4171d8c9fc` |
| `evals/v5/artifacts/fullcontext_verifier_replay_live_attempt.json` | `1bb1bced0f385f008851b87f1efbf8160f47247e2f0c4b1e1af0b3dbf6ab4da2` |
| `evals/v5/artifacts/fullcontext_verifier_replay_live_call_ledger.jsonl` | `06dc6322cf09c560a5e16535d4b000aabec519ff40e76e575ac54f49add33778` |
| `evals/v5/artifacts/fullcontext_verifier_replay_manual_review.json` | `0da7a024ab849d97d14a4cec89cf8254e37603895f35b468597f203ed2541e15` |

Frozen verdict: **AUTOMATED_FAIL**, final **FAIL**. No retroactive PASS.

## Parser bug (exact cause)

At S53 live scoring, `_required_blocking_kinds_satisfied()` read only
`semantic_raw_payload["issues"]`. Live capture shape is:

```json
{"model":"qwen3.7-plus","assessment":{"issues":[...]},"usage":{...}}
```

Top-level `"issues"` is **absent** (`null`). Blocking kinds live under
`assessment.issues`. Therefore `blocking_kind_match=false` for observed `block`
cases with required kinds — even when LLM returned the correct kind.

**Affected frozen rows:** `fc_medical_03`, `fc_missing_02` — both observed `block`
with `material_external_medical_claim` in `assessment.issues`, but frozen
`decision_match=false`, `missed_block=true`.

## Corrected diagnostic taxonomy (recompute only)

**A. S52 v1 labels + corrected parser:** 15/19 matches; false blocks
`fc_boundary_01`, `fc_boundary_02`, `fc_boundary_03`; missed `fc_missing_01`;
correct blocks include `fc_medical_03`, `fc_missing_02`.

**B. New v2 owner labels on same frozen S53 output:** 17/19; false block
`fc_boundary_01`; missed `fc_missing_01`; correct blocks include
`fc_medical_03`, `fc_missing_02`, `fc_boundary_02`, `fc_boundary_03`.

## Owner binding decisions

1. S53 artifacts immutable; verdict stays FAIL.
2. `fc_medical_03`, `fc_missing_02` — correct blocks (parser artifact only).
3. v2 matrix only: `fc_boundary_02` pass→block (`material_external_medical_claim`);
   `fc_boundary_03` pass→block (`unsupported_clinic_claim`).
4. True verifier errors: `fc_boundary_01` false block; `fc_missing_01` missed block.
5. No regex/disease lists/confidence thresholds/new issue kinds.

## Replay matrix v1 (protected)

`evals/v5/demo/fullcontext_verifier_replay_matrix.json` — git blob
`a273a58d96b00a76fd22b4d6fc9b97791df4f6d1` — **do not modify**.

## Replay matrix v2 (new)

`evals/v5/demo/fullcontext_verifier_replay_matrix_v2.json` — new `suite_id`.
Only `fc_boundary_02` and `fc_boundary_03` label changes; other 17 cases deep-equal v1.
**14 pass / 5 block.**

## Future v2 live paths (prep only; pending_owner_approval)

- `evals/v5/artifacts/fullcontext_verifier_replay_v2_live_raw.json`
- `evals/v5/artifacts/fullcontext_verifier_replay_v2_live_result.json`
- `evals/v5/artifacts/fullcontext_verifier_replay_v2_live_manifest.json`
- `evals/v5/artifacts/fullcontext_verifier_replay_v2_live_attempt.json`
- `evals/v5/artifacts/fullcontext_verifier_replay_v2_live_call_ledger.jsonl`
- `evals/v5/artifacts/fullcontext_verifier_replay_v2_manual_review.json`

## Allowlist

- `TASK.md`
- `core/target_response_verifier.py`
- `evals/v5/fullcontext_verifier_replay_contract.py`
- `evals/v5/run_fullcontext_verifier_replay.py`
- `evals/v5/demo/fullcontext_verifier_replay_matrix_v2.json`
- `tests/test_fullcontext_verifier_replay_matrix_contract.py`
- `tests/test_fullcontext_verifier_replay_harness.py`
- `tests/test_fullcontext_verifier_replay_s54.py`
- `tests/test_target_response_verifier.py`
- `docs/S53_VERIFIER_REPLAY_POST_LIVE_AUDIT.md`
- `evals/v5/artifacts/s53_verifier_replay_post_live_audit_manifest.json`
- `docs/ARCH_TARGET_DESIGN.md`
- `docs/STRANGLER_ROADMAP.md`

## Protected

- All S53 live artifacts (bytes above)
- S52 replay matrix v1
- S47/S50 artifacts
- Composer/runtime/product authority
- Historical five-boolean parser

## Acceptance

1. Canonical `extract_replay_semantic_issues` — one path for scoring + manual review.
2. Diagnostic recompute: 15/19 (v1), 17/19 (v2) from frozen S53 result.
3. Matrix v2 validated; v1 unchanged.
4. Policy clarifications for personal_medical_conclusion + missing-base.
5. Future v2 paths wired; `--live` for v2 returns blocked/pending (NO LIVE).
6. Audit doc + manifest with SHA pins and taxonomy.
7. Targeted pytest green; NO LIVE.

## Pytest

```powershell
$bt = Join-Path $env:TEMP ("pytest-s54-" + [guid]::NewGuid().ToString("n"))
.\.venv\codex312\Scripts\python.exe -m pytest `
  tests/test_fullcontext_verifier_replay_matrix_contract.py `
  tests/test_fullcontext_verifier_replay_harness.py `
  tests/test_fullcontext_verifier_replay_s54.py `
  tests/test_target_response_verifier.py `
  -p no:cacheprovider --basetemp=$bt -q
```

## Process

Governance commit → PRE-CODE ✅ → implementation → pytest → COMPLETION ✅ → push → STOP
