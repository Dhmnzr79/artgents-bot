# TASK — S47 FullContext Response Quality Eval Preparation

**Branch / baseline:** `codex/stage-a` / `d5a8557 feat: S46 boundary-enforced FullContext verified response`

**Goal:** frozen ~20-case matrix + provider-neutral offline harness for one future permitted
live eval of the full response chain:

```
ready TurnFrame + frozen TargetMedicalBoundaryResult
→ S46 → Composer → Semantic Verifier → verified | terminal
→ automatic metrics + manual quality review
```

Eval instrument only — **not** product path. **No live/LLM in S47.**

**Read-only seam (confirmed):** S46 exists; no response-quality eval matrix/harness; S43 pattern
is boundary-only (not full chain). No duplicate — proceed.

## Matrix (~20 cases)

- fresh session per case (harness state reset);
- explicit serialized `turn_frame_raw` + `TargetMedicalBoundaryResult` + `policy_envelope`;
- detector/planner/A9 **not** called;
- natural user questions; real demo base/services;
- **no verbatim expected prose** — semantic rubric only;
- `audit_source_refs` for review only — **not** document routing (S46 still gets full corpus).

### Required coverage

1. **General info:** implantation overview; All-on-4; pain reassurance.
2. **Structured commercial:** price; payment stages; doctor-by-service; consultation/marketing;
   structured authority over FullContext.
3. **Known medical:** diabetes/contraindications from approved MD; neutral + consultation; no
   diagnosis/personal eligibility.
4. **Missing-base (2):** topics absent from entire demo MD; controlled no-info + consultation;
   no model medical knowledge.
5. **Medical boundary:** personal eligibility; diagnosis; treatment choice — general MD only +
   doctor referral.
6. **Terminal (≥1):** frozen `boundary=uncertain` → S46 terminal defer; 0 Composer/Verifier calls.

### Per-case fields (minimum)

`case_id`, `case_kind`, `user_message`, `turn_frame_raw`, `boundary_result`, `policy_envelope`,
`expected_outcome`, `expected_response_mode`, `expected_structured_values` (optional),
`forbidden_claims`, `medical_safety`, `consultation_expectation`, `cta_followup_expectation`,
`manual_review_rubric`, `audit_source_refs`, `rationale`.

## Harness

1. Provider-neutral: injected Composer + Semantic Verifier backends; S47 **fake/recording only**.
2. Calls: materializable → Composer×1 + Verifier×1 max; terminal → 0 provider calls; no
   retry/repair/fallback.
3. Capture per case: outcome kind, response_mode, response text (if any), composer/verifier call
   counts, verifier status, pipeline errors, raw backend payloads (for future live).
4. CLI: `--dry-run` (matrix validate only); default exits `LIVE_NOT_CONFIGURED`; `--live` stub
   reserved for future gate (blocked in S47 — no live backend module).
5. Reuse `run_target_offline_boundary_enforced_fullcontext_response` — no parallel pipeline.

## Deliverables

1. `evals/v5/fullcontext_response_eval_contract.py` — frozen hash, schema validation.
2. `evals/v5/demo/fullcontext_response_eval_matrix.json` — ~20 frozen cases.
3. `evals/v5/fullcontext_response_eval_backend.py` — recording adapters, live-not-configured.
4. `evals/v5/run_fullcontext_response_eval.py` — offline harness runner + CLI.
5. `tests/test_fullcontext_response_eval_matrix_contract.py`
6. `tests/test_fullcontext_response_eval_harness.py`
7. ARCH/ROADMAP S47 status.

## Boundaries / allowlist

- `TASK.md`
- `evals/v5/fullcontext_response_eval_contract.py`
- `evals/v5/fullcontext_response_eval_backend.py`
- `evals/v5/run_fullcontext_response_eval.py`
- `evals/v5/demo/fullcontext_response_eval_matrix.json`
- `tests/test_fullcontext_response_eval_matrix_contract.py`
- `tests/test_fullcontext_response_eval_harness.py`
- `docs/ARCH_TARGET_DESIGN.md`
- `docs/STRANGLER_ROADMAP.md`

**Forbidden:** live run; live backend module; S43 matrix/artifacts changes; A9; runtime/UI/session;
product authority; message→TurnFrame; changes to S42–S46 core; RAG/routing; provider imports in
default harness path; retry/repair/fallback; weakening Verifier; new situation phrase tables.

## Minimal protected acceptance (offline)

1. Frozen matrix hash validates; ~20 cases; required kinds present; no observed/pass fields in source.
2. Harness dry-run loads matrix; reports case count.
3. Terminal uncertain case: outcome terminal; Composer×0; Verifier×0.
4. Materialize case (e.g. price): S46 path; Composer×1; Verifier×1; outcome materialize_verified
   with fake backends configured for offline pass.
5. Pain reassurance case: medical_handoff + service_id=None path materializes.
6. Missing-base case: materialize expected; forbidden external medical terms in rubric.
7. Neighbor: S46 orchestrator tests still green (targeted, no full pytest).
8. No live imports in harness default path; `--live` blocked or live-not-configured.

Run targeted tests with external `--basetemp` and `-p no:cacheprovider`. **No full pytest. No live.**

## Gates

1. Independent **PRE-CODE** checker on governance TASK.
2. Commit `docs: govern S47 FullContext response quality eval preparation` (**TASK.md only**).
3. Implement allowlist; run targeted offline tests.
4. Independent **COMPLETION** checker.
5. One completion commit; push; clean/synced.

## Explicitly out of scope

- First live eval run
- Model selection
- Multi-turn session memory eval
- S43 re-run
- Runtime wiring
