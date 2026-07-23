# TASK — S62 post-live audit capture (Checkpoint A)

**Baseline:** `codex/stage-a` / `0a43da1` · **NO LIVE / NO LLM / NO RERUN**

## Scope

Append-only governance capture after S62 live attempt. Official ruling: **`S62_NOT_PASSED`** (diagnostic evidence only). Frozen live artifacts **must not be edited**.

## Deliverables

- [ ] `docs/S62_TARGET_RUNTIME_POST_LIVE_AUDIT.md`
- [ ] `evals/v5/artifacts/s62_target_runtime_post_live_audit_manifest.json`
- [ ] `evals/v5/artifacts/s62_live_stdout_capture.txt` (preserved; SHA pinned)
- [ ] `TASK.md` governance update
- [ ] `docs/STRANGLER_ROADMAP.md` note (audit capture only)

## Immutable (do not modify)

- `evals/v5/artifacts/s62_target_runtime_live_{raw,result,manifest,attempt,call_ledger,manual_review}.json|jsonl`
- `evals/v5/artifacts/s62_target_runtime_live_audit.log`

## Stdout capture

- SHA-256: `3CA6A7EBB971FEDAFD5A3507442A49BE660CB56B96BD862CB11528C9D15D7AFC`
- Unique evidence for ingress/planner calls (18 total actual)

## Checker

| Checkpoint | When |
|---|---|
| PRE-CODE | before commit |
| POST-CODE audit | after commit |

## Commands

```powershell
python -c "from pathlib import Path; from evals.v5.fullcontext_response_eval_contract import sha256_file_hex; print(sha256_file_hex(Path('evals/v5/artifacts/s62_live_stdout_capture.txt')).upper())"
python -c "from evals.v5.fullcontext_quality_eval_contract import assert_frozen_prior_artifacts_unchanged; assert_frozen_prior_artifacts_unchanged()"
```

Push to `origin/codex/stage-a` only.
