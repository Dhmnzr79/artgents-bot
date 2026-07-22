# TASK — S48a Post-Live Offline Harness / Measurement Hardening

**Baseline:** `codex/stage-a` / `2b75e48` · **NO LIVE** · **NO LLM** · **NO product code**

**Goal:** Fix S47 eval measurement blind spots. Preserve candidate text and exact
semantic reject flags on verifier failure. Literal substring hits are diagnostic
only. Zero Composer/Verifier/runtime/UI/A9/authority changes.

## Owner decisions (binding)

1. **S48 split:** S48a (this TASK) → S48b blocked until separate owner command.
2. **fc_medical_01:** acceptable grounded general medical answer; Verifier
   `medical_boundary_ok=false` = probable FP — **not** automatic dangerous answer.
3. **fc_boundary_02 (future S48 matrix v2 gate, not S48a):** multi-topic fixture
   mismatch (implantation + treatment/pulpitis). Matrix path B — fix envelope in
   **separate subsequent gate**. Do **not** add Composer dry-defer rule for narrow
   envelope. **Frozen S47 matrix byte-identical** in S48a.
4. **S47 live artifacts:** `fullcontext_response_eval_live_raw.json` and
   `fullcontext_response_eval_live_result.json` **immutable** (byte-identical).
5. **No safe-negation phrase filter:** no template table for «не могу поставить
   диагноз» or other phrase exceptions. Literal hits may contain forbidden
   substrings inside safe negation — that is normal and diagnostic-only.

## Scope (S48a only)

### Harness exception path
1. On `TargetResponseVerificationError` with code
   `target_verifier_semantic_rejected`, preserve candidate text in `response_text`
   from `composer_raw_payload.text`.
2. Do **not** hardcode `forbidden_claim_violations=[]` while candidate text exists;
   populate `raw_literal_forbidden_hits` from candidate text + matrix
   `forbidden_claims` (diagnostic only).
3. Transport / config / malformed exceptions: **no** semantic reject flags; candidate
   text not treated as semantic rejection.

### Metric separation
4. **`raw_literal_forbidden_hits[]`** — diagnostic/audit only:
   - not a semantic violation;
   - does not block response status by itself;
   - does not auto-increment `dangerous_medical_violation_count`.
5. Preserve exact semantic reject flags (from verifier assessment when present):
   - `semantic_general_grounding_rejected`
   - `semantic_strict_commercial_grounding_rejected`
   - `semantic_topic_scope_rejected`
   - `semantic_medical_boundary_rejected`
   - `semantic_selected_facts_rejected`
6. `derive_case_automated_flags`:
   - `missing_base_external_knowledge` ← `missing_base` case_kind AND
     `semantic_general_grounding_rejected`;
   - `dangerous_medical_violation` ← **never** from literal hits or
     `semantic_medical_boundary_rejected` alone (fc_medical_01 FP rule);
   - transport/malformed flags unchanged.
7. Case `status` must not fail solely on literal hits.

### Offline replay (read-only)
8. Helper to re-derive semantic/literal metrics from **frozen S47 raw/result**
   in memory only — no artifact rewrite, no LLM calls.
9. Additive case-result schema: old S47 result rows remain readable (new fields
   optional on read paths).

## Allowlist

- `TASK.md`
- `evals/v5/run_fullcontext_response_eval.py`
- `evals/v5/fullcontext_response_eval_contract.py`
- `tests/test_fullcontext_response_eval_harness.py`
- `tests/test_fullcontext_response_eval_matrix_contract.py` (only if compatibility test needed)
- `docs/STRANGLER_ROADMAP.md` (completion status only)

## Forbidden

- Live / LLM / runtime / UI / A9 / authority changes
- `core/target_composer_executor.py`, `core/target_response_verifier.py`
- Any edit to frozen S47 live raw/result artifacts
- S47 matrix hash / matrix file changes
- Safe-negation phrase filter / template tables
- S48b implementation
- Combined governance+implementation commits

## Process

1. **Governance commit** (this TASK only) → independent PRE-CODE checker ✅
2. **Implementation commit** (allowlist code/tests) → independent COMPLETION checker ✅
3. Push `codex/stage-a` → clean/synced → **stop** (do not start S48b)

## Tests (offline)

Use unique `--basetemp` and `-p no:cacheprovider`.

Verify:
- rejected candidate preserved on `TargetResponseVerificationError`;
- semantic flags reflect verifier assessment exactly;
- literal hits diagnostic-only (no status/dangerous_medical auto-fail);
- transport/malformed do not set semantic reject flags;
- frozen S47 artifacts byte-identical;
- matrix/contract tests green.

```text
pytest tests/test_fullcontext_response_eval_harness.py tests/test_fullcontext_response_eval_matrix_contract.py -q -p no:cacheprovider --basetemp=.pytest_basetemp_s48a
```

## Acceptance

1. PRE-CODE checker ✅ on governance TASK commit.
2. Exception-path rows: candidate text + semantic flags when verifier rejected.
3. Frozen S47 raw replay (in-memory): semantic counters truthful for known rejects;
   artifacts on disk unchanged.
4. SHA-256 unchanged: live raw `0f4d4b93…`, live result `83bff177…`, matrix `14b1cbd4…`.
5. Pytest command above green.
6. COMPLETION checker ✅ → push → stop.

**Next (blocked):** S48b composer+verifier; S48 matrix v2 (fc_boundary_02 path B).
