# TASK — S66 default FullContext authority live verification

**Baseline:** `codex/stage-a` / `04ad2f7` · **OWNER APPROVED — ONE LIVE ATTEMPT**

## Goal

Single live HTTP turn proving S65 default authority: **no `TARGET_FULLCONTEXT_DEV` env**, config default ON, target materialized, legacy/RAG/chunk = 0, ≤5 provider calls.

**Not** S62/S63 repeat. **Not** quality eval.

## Live constraints

| Rule | Value |
|------|-------|
| Env `TARGET_FULLCONTEXT_DEV` | **must be absent** (fail if set to any value) |
| Setting `=1` or `=0` | **forbidden** |
| HTTP turns | 1 (`POST /ask`, new sid) |
| Question | `Что такое All-on-4?` |
| Provider budget | ≤5 total; ≤1 per role; retry=0; hard stop before 6th |
| Models | ingress/planner `qwen3.6-flash`; boundary/composer/verifier `qwen3.7-plus` |
| Rerun | **blocked** after first provider call |

## Authority proof (artifact fields)

- `env_present=false`
- `config_default_resolved=true`
- `authority_source="config_default"`

## S66 artifacts (exclusive paths)

| Artifact | Path |
|----------|------|
| Attempt | `evals/v5/artifacts/s66_default_authority_live_attempt.json` |
| Ledger | `evals/v5/artifacts/s66_default_authority_live_call_ledger.jsonl` |
| Raw | `evals/v5/artifacts/s66_default_authority_live_raw.json` |
| Result | `evals/v5/artifacts/s66_default_authority_live_result.json` |
| Manifest | `evals/v5/artifacts/s66_default_authority_live_manifest.json` |
| Manual review | `evals/v5/artifacts/s66_default_authority_live_manual_review.json` |
| Audit log | `evals/v5/artifacts/s66_default_authority_live_audit.log` |

## Allowlist — prep (offline)

| File | Change |
|------|--------|
| `TASK.md` | governance + completion |
| `evals/v5/s66_default_authority_live_contract.py` | contract + S62/S63 pin guards |
| `evals/v5/s66_default_authority_live_provider_audit.py` | 5-call budget audit |
| `evals/v5/s66_default_authority_live_harness.py` | HTTP harness |
| `evals/v5/run_s66_default_authority_live.py` | CLI |
| `tests/test_s66_default_authority_live_harness.py` | offline tests |
| `docs/STRANGLER_ROADMAP.md` | S66 status |
| `docs/FLAGS_AND_STATUS.md` | optional note |

## Allowlist — post-live (second commit)

| File | Change |
|------|--------|
| `evals/v5/artifacts/s66_*` | live artifacts (7 files) |
| `TASK.md`, `docs/*` | closeout |

**Forbidden:** `TARGET_FULLCONTEXT_DEV` env in live, default authority change, second live attempt, retry, S62/S63 artifact edits, product code changes, A9, legacy delete, merge to main.

## Automated gates (18)

1. env absent 2. config default authority 3. single HTTP response 4. materialized route 5. verified materialized 6. authored CTA 7. target widget 8–11. no legacy orchestrator/routing/chunk/composer 12. FC build=1 13. ledger complete 14. calls≤5 15. retry=0 16. errors=0 17. fail→AUTOMATED_FAIL 18. pass→PENDING_MANUAL_REVIEW

## Commands

```powershell
# Prep (NO LIVE)
$bt = Join-Path $env:TEMP ("s66_pytest_" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt tests/test_s66_default_authority_live_harness.py -q
python evals/v5/run_s66_default_authority_live.py --dry-run

# Live (ONE attempt; env must not contain TARGET_FULLCONTEXT_DEV)
python evals/v5/run_s66_default_authority_live.py --live
```

## Acceptance

- [ ] PRE-CODE ✅
- [ ] Offline pytest green
- [ ] `--dry-run` exits 0
- [ ] S62+S63 frozen unchanged (pre/post live)
- [ ] ONE live attempt
- [ ] Manual review artifact
- [ ] POST-LIVE checker ✅
- [ ] Commits + push `origin/codex/stage-a`

**STOP after S66 — no legacy isolation without owner decision.**
