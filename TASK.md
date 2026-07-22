# TASK — S47 First Permitted Live Run (Owner Approved)

**Baseline:** `codex/stage-a` / `0cb22c3` · clean/synced

**Owner approval (this session):**
- automated technical outcome: 100% (`outcome_match_rate_min` 1.0)
- manual answer quality: ≥ 85%
- critical violations: 0
- Composer + Semantic Verifier: `qwen3.7-plus`
- **One** live run, max **38** LLM calls
- artifacts exclusive-create (no overwrite)

**Forbidden:** A9, runtime, UI, product authority, S42–S46 core changes, matrix question edits.

**Allowlist:**
- `TASK.md`
- `evals/v5/fullcontext_response_eval_live_backend.py` (new)
- `evals/v5/run_fullcontext_response_eval.py`

**Deliverables:**
1. Live backend module (eval-only, injected via `--live`).
2. CLI `--live` writes raw + result artifacts once; asserts ≤38 provider calls.
3. Result records owner approval metadata; final verdict stays `PENDING_MANUAL_REVIEW`.

**Gates:** PRE-CODE → governance commit → implement → run live once → COMPLETION → push.

**NO re-run if artifacts exist.**
