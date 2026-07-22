# TASK — S49 FullContext Response Re-eval v2 Offline Preparation

**Baseline:** `codex/stage-a` / `972068e` · **NO LIVE** · **NO LLM** · **NO S47 artifact edits**

**Goal:** Prepare an honest post-S48b comparative re-eval harness (matrix v2 + isolated
v2 artifacts + incident guards). No provider calls in this milestone.

## Owner decisions (binding)

1. **S47 matrix frozen:** `evals/v5/demo/fullcontext_response_eval_matrix.json` and hash
   `14b1cbd4c3a8d906e0b19adb10ffaa60849803b3` remain byte-identical and pinned.
2. **S47 live artifacts frozen:** raw/result/manual-review/manifest paths under
   `evals/v5/artifacts/fullcontext_response_eval_*` (non-v2) remain untouched.
3. **Matrix v2:** new file; **20 `user_message` unchanged**; **19 control cases
   semantically unchanged**; only **fc_boundary_02** fixture scope fix.
4. **fc_boundary_02 delta only:** add `"treatment"` to `policy_envelope.allowed_topics`
   so pulpitis/treatment FullContext is in-scope. **Do not change:**
   `user_message`, `forbidden_claims`, `medical_safety`, `expected_outcome`,
   `expected_response_mode`, `case_kind`, safety expectations (no diagnosis / personal
   eligibility / treatment choice).
5. **No expected prose tuning:** do not rewrite `offline_composer_stub`, rubrics, or
   thresholds to “fit” S48b; comparative eval comes later.
6. **S48a measurement contract:** semantic reject counters authoritative; literal hits
   diagnostic-only; `dangerous_medical_evaluation_status=NOT_EVALUATED` must not read as
   PASS; manual review only after `AUTOMATED_PASS`.
7. **Incident guard:** exclusive attempt marker **before** first provider call; crash
   leaves marker → rerun blocked without new owner decision.
8. **Future live:** separate owner approval after this offline prep milestone.

## Matrix v2 specification

### File

- **New:** `evals/v5/demo/fullcontext_response_eval_matrix_v2.json`
- **Unchanged:** `evals/v5/demo/fullcontext_response_eval_matrix.json`

### Top-level metadata (v2)

- `suite_id`: `s49_fullcontext_response_re_eval_v2_matrix`
- `frozen_before_first_live`: `true`
- Copy remaining top-level structure from v1 unless a field must reference v2 identity.
- Document parent trace in implementation commit message / roadmap (v1 hash above).

### Exact v1 → v2 delta (only permitted case edit)

| Scope | v1 | v2 |
|-------|----|----|
| Matrix file | `fullcontext_response_eval_matrix.json` | `fullcontext_response_eval_matrix_v2.json` |
| Git blob hash | `14b1cbd4c3a8d906e0b19adb10ffaa60849803b3` | **compute at implementation; pin in contract/tests** |
| Case count | 20 | 20 |
| All `user_message` | frozen | **identical** |
| Cases 1–18, 20 (all except fc_boundary_02) | frozen semantics | **deep-equal case objects** |
| `fc_boundary_02.policy_envelope.allowed_topics` | `["implantation","doctors"]` | `["implantation","doctors","treatment"]` |

**Forbidden v2 edits:** any other field on fc_boundary_02; any other case; rewriting
questions; changing expected safety flags; per-case production logic.

### Non-regression coverage (must remain in v2 matrix)

All v1 scenario kinds preserved:

- general service description (`general_information`)
- structured price / payment / doctor / marketing
- pain reassurance
- known medical topic (3)
- missing-base (2)
- medical boundaries: personal / diagnosis / treatment choice / boundary_04
- terminal uncertain

## Future artifact isolation (v2-only paths)

Implement constants and CLI defaults for v2 live prep (no writes in S49 unless tests use
tmp paths):

| Artifact | v2 path |
|----------|---------|
| Live raw | `evals/v5/artifacts/fullcontext_response_eval_v2_live_raw.json` |
| Live result | `evals/v5/artifacts/fullcontext_response_eval_v2_live_result.json` |
| Manual review | `evals/v5/artifacts/fullcontext_response_eval_v2_manual_review.json` |
| Run manifest | `evals/v5/artifacts/s49_fullcontext_response_eval_v2_manifest.json` |
| Attempt marker | `evals/v5/artifacts/fullcontext_response_eval_v2_live_attempt.json` |

Rules:

- **Never** write v2 outputs to S47 paths.
- **Exclusive-create** (`open("x")`) for raw, result, manual review, manifest, attempt marker.
- Default offline/`--dry-run` must not create v2 live artifacts.
- `--live` on v2 must refuse if attempt marker already exists (unless explicit
  owner-override flag documented and default-off).

## Attempt marker + incident guards

`fullcontext_response_eval_v2_live_attempt.json` (exclusive-create **before** first LLM call):

```json
{
  "measurement_id": "s49_fullcontext_response_re_eval_v2",
  "matrix_git_blob_hash": "<V2_MATRIX_HASH>",
  "status": "in_progress",
  "started_provider_calls": 0,
  "max_llm_calls": 38,
  "rerun_blocked_without_owner_approval": true
}
```

Required behavior (future live path; prove offline in tests with injected backend):

1. Create attempt marker with `open("x")` before first composer/semantic provider call.
2. Increment `started_provider_calls` (or equivalent audit counter) on each started call;
   persist to marker or append-only sidecar log before next call.
3. If run crashes after marker creation → subsequent v2 `--live` exits non-zero with
   clear `ATTEMPT_MARKER_EXISTS` (or equivalent) unless owner override.
4. **Fully serialize** raw/result JSON payloads in memory (`json.dumps` / dict) **before**
   opening final artifact files.
5. **No automatic retry** on composer/semantic transport failure (preserve S47 scoring
   contract).
6. Enforce call budget: `max_llm_calls = 38` (= 19 materializable × 2); exceed → fail
   before silent continuation.
7. Live log/audit trail records started call count even on crash (test with simulated
   mid-run failure).

## Measurement identity

- `MEASUREMENT_ID` (v2): `s49_fullcontext_response_re_eval_v2`
- Expected call budget (future live): **38** LLM calls (composer + semantic per
  materializable case); **0** for terminal case `fc_terminal_01`.

## S48a measurement (v2 harness must reuse)

- `semantic_*_rejected` flags from verifier assessment (null when not evaluated)
- `semantic_assessment_evaluated_case_count` / `_not_evaluated_case_count`
- `raw_literal_forbidden_hits` diagnostic-only (not active automated gate)
- `dangerous_medical_evaluation_status = NOT_EVALUATED` — never treated as PASS
- `evaluate_final_verdict`: manual review only when automated verdict is `AUTOMATED_PASS`

## Scope (implementation)

### Contract (`fullcontext_response_eval_contract.py`)

- Add v2 matrix path + `V2_MATRIX_HASH` constant (pinned after matrix creation).
- Add v2 artifact path constants (table above).
- Add `load_v2_matrix()` / `validate_v2_matrix_hash()` or parameterized loader; **keep
  S47 `FROZEN_MATRIX_HASH` and S47 paths unchanged**.
- Add v1→v2 diff helper or test-visible assertion for single-case delta.
- Attempt-marker validation helpers (exists / blocks live).

### Harness (`run_fullcontext_response_eval.py` or dedicated v2 entry)

- `--matrix` default remains S47 for backward compatibility OR explicit v2 subcommand;
  v2 live prep must target v2 matrix + v2 artifact paths only.
- Wire attempt marker lifecycle (pre-call block).
- In-memory serialization before artifact write.
- v2 `--dry-run` prints measurement id, case count, call budget, matrix hash.

### Live backend (`fullcontext_response_eval_live_backend.py`)

- Ensure request payloads serialized to plain JSON-serializable structures before SDK call
  (offline unit test; no network).

### Tests

- v2 matrix hash + 20 cases + required kinds
- all 20 user_messages match v1
- 19 cases deep-equal to v1 except fc_boundary_02 allowed_topics delta
- fc_boundary_02 has `treatment` in allowed_topics; safety flags unchanged
- S47 matrix hash test still passes (regression)
- S47 frozen live artifact SHA pins unchanged
- attempt marker blocks second live start (tmp paths)
- attempt marker created before mocked provider call
- JSON payload built in memory before exclusive artifact write (mock `open`)
- SDK serialization test for live backend invocation payloads
- v2 `--dry-run` smoke
- S48a semantic counters still aggregate correctly on v2 offline replay stub

## Allowlist

- `TASK.md`
- `evals/v5/demo/fullcontext_response_eval_matrix_v2.json` (new)
- `evals/v5/fullcontext_response_eval_contract.py`
- `evals/v5/run_fullcontext_response_eval.py`
- `evals/v5/fullcontext_response_eval_live_backend.py` (only if serialization helpers needed)
- `tests/test_fullcontext_response_eval_matrix_contract.py`
- `tests/test_fullcontext_response_eval_harness.py`
- `docs/STRANGLER_ROADMAP.md` (completion status only)

## Forbidden

- live / LLM / provider calls (including in tests)
- edits to S47 matrix / S47 live raw / S47 live result / S47 manual review
- Composer / Verifier product code (`core/target_*`)
- runtime / UI / session / A9 / authority
- new questions or expected prose tuning
- per-case production logic / disease-name rules in product code
- combined governance + implementation commits
- writing any v2 live artifact bytes into repo workspace (tests use tmp paths only)

## Non-regression pytest

S47 pins must stay green; add v2 tests alongside:

```text
pytest tests/test_fullcontext_response_eval_matrix_contract.py tests/test_fullcontext_response_eval_harness.py tests/test_target_composer_executor.py tests/test_target_response_verifier.py tests/test_target_fullcontext_content_response.py -q -p no:cacheprovider --basetemp=$env:TEMP\pytest_basetemp_s49_<runid>
```

## Process

1. Governance TASK commit → **PRE-CODE checker ✅** (this step)
2. Implementation commit → COMPLETION checker ✅
3. Push `codex/stage-a` → clean/synced → **stop (NO LIVE)**

## Acceptance (implementation)

1. PRE-CODE ✅ on governance TASK.
2. v2 matrix exists; v1 matrix byte-identical; v1→v2 delta exactly as specified.
3. `V2_MATRIX_HASH` pinned; documented delta vs `14b1cbd4…`.
4. v2 artifact paths defined; S47 paths not reused for v2 output.
5. Attempt-marker pre-call block proven offline.
6. In-memory JSON serialization + SDK payload serialization tested offline.
7. S48a semantic measurement contract preserved for v2.
8. Targeted offline pytest green; S47 frozen SHA pins unchanged.
9. COMPLETION ✅ → push → stop.

**Completion report must include:** exact v1→v2 delta table, new matrix hash, v2 artifact
paths, attempt-marker block proof, expected call budget (38), and explicit **NO LIVE**.
