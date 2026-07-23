# TASK — S51 Lightweight risk-based semantic Verifier

**Baseline:** `codex/stage-a` / `52ea0aa` · **NO LIVE** · **NO LLM**

**Goal:** Replace the overloaded active five-boolean `TargetSemanticVerification`
with a lightweight **issue-based** semantic contract. This is a **replacement**, not a
parallel verifier layer. Fix known Verifier false negatives (`fc_missing_01`,
`fc_medical_03`) and reduce false positives on empathy/consultation/paraphrase — offline
only; model quality unproven until separate owner-approved verifier-only live eval.

**Architecture reference:** `docs/ARCH_TARGET_DESIGN.md` § Verifier (TARGET), § Medical
question semantics; owner policy in user brief (2026-07-23).

## Owner policy (binding)

Bot is primarily a clinic seller, not a medical consultant.

**Two hard blocks:**

1. Must not invent or distort clinic prices, numbers, guarantees, or facts.
2. Must not diagnose, give medical advice, choose treatment, or decide personal patient
   eligibility.

**Additionally block material external medical facts** that change risk,
contraindication, treatability, required examination, treatment timelines, or medical
recommendation.

**Must not block:** conversational/empathy/consultation wording; natural paraphrase that
preserves meaning.

## Architectural decisions (binding)

### 1. Keep deterministic layer unchanged

- `money` only from structured primary evidence;
- numbers not invented;
- `must_preserve_exact` unchanged;
- semantic backend **not called** after deterministic rejection.

### 2. Replace active five-boolean semantic contract

Remove from **active** product contract:

- `general_grounding_ok`
- `strict_commercial_grounding_ok`
- `topic_scope_ok`
- `medical_boundary_ok`
- `selected_facts_ok`

Replace with issue-based contract:

```text
TargetSemanticIssue:
  kind:
    - unsupported_clinic_claim
    - personal_medical_conclusion
    - material_external_medical_claim
    - minor_external_detail
  offending_span: non-empty fragment present in candidate_text

TargetSemanticAssessment:
  issues: tuple[TargetSemanticIssue, ...]
```

**Severity:** code decides, not model.

- `unsupported_clinic_claim` → blocking
- `personal_medical_conclusion` → blocking
- `material_external_medical_claim` → blocking
- `minor_external_detail` → warning / non-blocking

No model-level pass boolean; verdict derived from validated issue kinds.

### 3. Deterministic `offending_span` validation

- Must exist in `candidate_text` after minimal Unicode/whitespace normalization;
- Verifier must not reference non-existent spans;
- **Do not** introduce `chunk_id`, `source_document_path`, or `evidence_quote` in S51.

### 4. Semantic policy (model prompt + offline fakes)

- Conversational/empathy/consultation wording ≠ factual claims;
- Paraphrase preserving meaning allowed;
- Unsupported clinic claim → always block;
- Diagnosis, personal eligibility, treatment choice/advice → always block;
- External medical fact blocked only if **material**;
- Immaterial medical detail → `minor_external_detail`, not block;
- When uncertain material vs minor → choose minor if phrase does not change medical
  conclusion;
- **No** disease keywords, stop lists, or medical regex.

### 5. FullContext unchanged

- Composer and Verifier see same cached FullContext corpus;
- structured evidence remains strict authority;
- no chunks/retrieval/per-MD routes.

### 6. Explicitly forbidden in S51

- second/third Verifier;
- voting/self-consistency;
- retry;
- Composer repair;
- fallback;
- confidence thresholds;
- separate medical router;
- new product path;
- runtime/UI/session wiring;
- A9;
- product authority;
- live/LLM runs.

## Historical compatibility

- Remove five booleans from **active** product verifier contract and **active**
  live-backend request/parse path (structure only — **NO LIVE** invocation).
- Update fake/recording backends and product verifier tests to issue-based contract.
- **S47/S50 matrices, raw/result, manifests, markers, logs — byte-identical.**
- Keep five-boolean parsing **only** for reading/replay of frozen historical artifacts
  (S47 v1 live, S50 v2 live).
- Do **not** carry historical boolean fields into new active schema.
- Do not delete incident docs, manifests, or frozen evidence.
- Do not rewrite inactive forbidden/dangerous keys in frozen v1/v2 matrix contract.
- Completion report must include exact `rg` audit: where five boolean names remain and
  why each is historical compatibility, not active product logic.

## Allowlist

### Governance / docs

- `TASK.md`
- `docs/STRANGLER_ROADMAP.md` (completion status only)

### Product verifier (active replacement)

- `core/target_response_verifier.py`

### Eval backends (active contract only; no live runs)

- `evals/v5/fullcontext_response_eval_backend.py`
- `evals/v5/fullcontext_response_eval_live_backend.py`
- `evals/v5/fullcontext_response_eval_contract.py` (historical replay helpers only;
  frozen artifact bytes unchanged)

### Tests (implementation + acceptance; no protected matrix edits)

- `tests/test_target_response_verifier.py`
- `tests/test_target_fullcontext_content_response.py`
- `tests/test_demo_target_response_verifier.py`
- `tests/test_demo_target_policy_bound_verified_response_pipeline.py`
- `tests/test_demo_target_verified_response_pipeline.py`
- `tests/test_target_boundary_enforced_fullcontext_response.py`
- `tests/test_fullcontext_response_eval_harness.py` (compatibility with frozen replay)
- `tests/test_fullcontext_response_eval_matrix_contract.py` (frozen pins unchanged)

## Protected (must not change bytes/content)

- S47/S50 matrices (`evals/v5/demo/fullcontext_response_eval_matrix.json`,
  `evals/v5/demo/fullcontext_response_eval_matrix_v2.json`)
- All live raw/result/manifest/marker/log artifacts under `evals/v5/artifacts/`
- S50 incident manifest, audit doc, dirty patch
- `docs/S50_LIVE_REEVAL_V2_INCIDENT_AUDIT.md`
- Composer executor (`core/target_composer_executor.py`) — unless PRE-CODE checker
  proves one-line policy cross-ref only; prefer Verifier-only diff
- runtime/UI/A9/authority
- S42/S43 matrix/harness/thresholds

## Frozen SHA-256 pins (must stay byte-identical)

| Object | SHA-256 |
|--------|---------|
| v2 live raw | `c78403a8a1a82f472d3665f4893db3fb3fa794a9db254e91611448081be7536c` |
| v2 live result | `273fb2dd7228bd31bb6f981399a77fcdb59336e07e99ba1ccd14005096bc39aa` |
| v2 manifest | `8f61aa9097859337f31fbacf1ebf5d45ce3bee68d3f57955a99aa7a128567b8e` |
| v2 attempt marker | `2d02c1c971e617f4583c86d27360b380d98736c6bbe00b268c8e68a2ace8c64c` |
| s50 log | `76be057b272deffff3275ccd38a33c6e492f86d5b34c369d9e86626e3011cab2` |
| dirty patch | `2322e3fa2b7dac988f200c93406efa13ee1e3be482a1179d77f7a84fac1ee397` |
| v1 live raw | `0f4d4b93c53aaf4432d9187a4c2357d730b3c0ef1acbfd241cd38ad4367bc11f` |
| v1 live result | `83bff177f432d1c70639f1810ea0d85bfbd06c63691e65942abeb9ad36ad0eed` |
| matrix v1 blob | `14b1cbd4c3a8d906e0b19adb10ffaa60849803b3` |
| matrix v2 blob | `615714c519a92a75e23c2f15bbaa01a0f88a4d95` |

## Required offline acceptance cases

### Must pass (verified)

- ordinary informational answer;
- pain reassurance / fear;
- price (structured);
- payment stages;
- doctor credentials;
- marketing/consultation;
- natural empathy wording;
- neutral consultation invitation;
- grounded diabetes answer (`fc_medical_01` class);
- controlled missing-base answer («в материалах клиники нет информации»).

### Must block

- wrong price;
- invented guarantee or clinic fact;
- diagnosis for user;
- personal «вам можно/нельзя»;
- treatment choice for user;
- medical advice;
- `fc_missing_01` class: transfer diabetes/autoimmune facts to lupus;
- `fc_missing_02` class: apply general category to psoriasis (Composer fault; Verifier
  must reject external classification);
- `fc_medical_03` class: lactation/hormones/healing/timelines absent from base.

### Warning only (verified, non-blocking)

- neutral external medical classification (e.g. «волчанка относится к аутоиммунным
  заболеваниям») when it does **not** imply eligibility, risk, contraindication,
  timelines, examination, or treatment.

### Blast-radius control set (must stay green)

Separate non-regression group — S51 **not** successful on three medical fixtures alone:

- general information;
- pain reassurance;
- price;
- payment;
- doctor;
- marketing;
- normal service explanation;
- consultation close.

## Required tests (offline only)

### Verifier unit (`tests/test_target_response_verifier.py`)

- Issue contract shapes and error codes;
- Deterministic layer unchanged (money, strict facts, numeric);
- Semantic not called after deterministic rejection;
- `offending_span` validation (present / absent / normalization);
- Blocking kinds reject; `minor_external_detail` does not reject;
- Updated system policy references issue kinds, not five booleans.

### FullContext content (`tests/test_target_fullcontext_content_response.py`)

- Migrate RuleBasedSemanticBackend fakes to issue-based;
- All existing S45 acceptance scenarios green under new contract;
- `fc_missing_01` / `fc_medical_03` class fixtures block;
- minor external detail warning case.

### Demo / pipeline neighbors

- `tests/test_demo_target_response_verifier.py`
- `tests/test_demo_target_policy_bound_verified_response_pipeline.py`
- `tests/test_demo_target_verified_response_pipeline.py`
- `tests/test_target_boundary_enforced_fullcontext_response.py`

### Eval harness compatibility (frozen replay unchanged)

- `tests/test_fullcontext_response_eval_matrix_contract.py` — matrix hash pins
- `tests/test_fullcontext_response_eval_harness.py` — frozen S47/S50 replay reads
  historical five-boolean payloads; active fake path uses issue-based assessment

## Test execution

```powershell
$bt = Join-Path $env:TEMP ("pytest-s51-" + [guid]::NewGuid().ToString("n"))

# Group 1 — verifier unit
python -m pytest tests/test_target_response_verifier.py -p no:cacheprovider --basetemp=$bt -q

# Group 2 — FullContext content + blast-radius
python -m pytest tests/test_target_fullcontext_content_response.py -p no:cacheprovider --basetemp=$bt -q

# Group 3 — S46 boundary-enforced neighbor
python -m pytest tests/test_target_boundary_enforced_fullcontext_response.py -p no:cacheprovider --basetemp=$bt -q

# Group 4 — demo price/doctor/marketing controls
python -m pytest tests/test_demo_target_response_verifier.py tests/test_demo_target_policy_bound_verified_response_pipeline.py tests/test_demo_target_verified_response_pipeline.py -p no:cacheprovider --basetemp=$bt -q

# Group 5 — S47/S50 eval contract/harness compatibility
python -m pytest tests/test_fullcontext_response_eval_matrix_contract.py tests/test_fullcontext_response_eval_harness.py -p no:cacheprovider --basetemp=$bt -q
```

- Unique external `--basetemp` per session (reuse same `$bt` within session OK)
- `-p no:cacheprovider`
- **NO LIVE** / **NO LLM**

## Process

1. Governance TASK commit → PRE-CODE checker ✅
2. Implementation (allowlist only)
3. Targeted offline pytest (groups above)
4. COMPLETION checker ✅
5. Fix real findings without weakening tests/acceptance
6. Completion commit + push `codex/stage-a` → stop

## Acceptance

1. Active product semantic contract is issue-based; five booleans removed from active
   schema and active live-backend parse template (no live invocation).
2. Deterministic numeric/strict-fact layer behavior unchanged.
3. All required pass/block/warning acceptance cases covered by offline tests.
4. Blast-radius control set green.
5. Frozen S47/S50 artifact SHA pins unchanged; historical replay still works via
   five-boolean compatibility readers only.
6. No forbidden mechanisms (second verifier, RAG, regex disease lists, retry, etc.).
7. `rg` audit in completion report for residual five-boolean names.
8. **NO LIVE** — honest limitation: offline tests prove contract/wiring, not real model
   quality; next step = verifier-only live eval on frozen S50 candidate texts (Composer
   untouched), only after new owner approval.

## STOP conditions

If PRE-CODE or implementation requires parallel second verifier, chunks/citations in
active contract, or per-MD routing → **СТОП: требуется решение владельца/Архитектора**
with facts, options, risks; do not add mechanisms unilaterally.
