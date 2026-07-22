# TASK — S48b FullContext Medical Response Semantic Hardening

**Baseline:** `codex/stage-a` / `12c039c` · **NO LIVE** · **NO LLM** · **NO matrix/artifact edits**

**Goal:** Universal Composer/Verifier policy wiring fixes from S47 offline audit.
Improve medical_handoff grounding, missing-base honesty, and CTA/consultation
boundaries without dry refusals on known topics or regression on commercial paths.

## Owner decisions (binding)

1. **fc_medical_01:** owner-approved etalon — general grounded conditional fact from
   FullContext + personal decision deferred to doctor; **not** dry refusal.
2. **fc_medical_01 Verifier:** historical live reject = probable **false positive**;
   manual review catches Verifier **FP and FN**.
3. **Missing-base:** honest «нет в материалах клиники» for absent specific topic;
   no cross-disease transfer; no external medical knowledge.
4. **Grounding:** no causes/timelines/diagnostics/recommendations absent from FullContext
   (fc_medical_03 class forbidden).
5. **CTA:** phones/WhatsApp/contacts only via structured PRIMARY_EVIDENCE when
   `allow_cta=true`; consultation close without contacts OK when
   `allow_consultation_close=true`.
6. **fc_boundary_02 / matrix v2:** **out of scope** — no production fix for narrow
   fixture; frozen S47 matrix unchanged.
7. **Model quality:** offline tests prove **policy/directive wiring only**; real
   model behavior requires separate owner-approved live re-eval.

## Scope (policy + wiring only)

### Composer (`TARGET_COMPOSER_SYSTEM_POLICY` + directives)
- Known medical: grounded general conditional facts from FullContext; defer personal
  decision to doctor; keep useful content (fc_medical_01 semantics).
- Missing-base: absent specific topic → controlled no-information + consultation if
  allowed; no similar-disease transfer; no external knowledge.
- Grounding: forbid medical additions not in FullContext.
- Directives JSON: add `allow_cta`, `allow_consultation_close`, `allow_marketing_facts`
  from `TargetResponseSpec`.
- CTA prose ban when `allow_cta=false` even if contacts appear in corpus.

### Verifier (`TARGET_SEMANTIC_VERIFIER_SYSTEM_POLICY` + spec payload)
- `medical_boundary_ok=true` for general grounded conditional answers without
  personal verdict/diagnosis/treatment choice.
- `medical_boundary_ok=false` for diagnosis, personal eligibility, treatment choice.
- `general_grounding_ok=false` for any ungrounded medical claim vs FullContext.
- Consultation invitation ≠ personal eligibility decision.
- CTA/contact in prose = strict commercial; must match PRIMARY_EVIDENCE + allow_cta.
- No repair/retry/fallback.
- Verifier `response_spec_json`: include `allow_cta`, `allow_consultation_close`.

## Blast-radius

| Area | Risk | Mitigation |
|------|------|------------|
| medical_handoff content | Dry refusal / over-pruning | Explicit allow grounded general + doctor defer |
| missing-base | False «нет информации» on known topics | Only when topic absent from entire corpus |
| commercial/price/doctor | CTA rule bleed | Rules scoped to medical_handoff + allow_cta flag |
| pain/general info | Policy length drift | No new routes/detectors; prompt-only |

## Allowlist

- `TASK.md`
- `core/target_composer_executor.py`
- `core/target_response_verifier.py`
- `tests/test_target_composer_executor.py`
- `tests/test_target_response_verifier.py`
- `tests/test_target_fullcontext_content_response.py`
- `docs/STRANGLER_ROADMAP.md` (completion status only)

## Forbidden

- case_id / disease names / eval phrases in production rules
- regex / phrase tables / classifiers
- per-MD routing, retriever, RAG, new detectors
- matrix / frozen live raw/result edits
- runtime / UI / session / A9 / authority
- live / LLM calls
- matrix v2 / fc_boundary_02 fixture fix
- combined governance+implementation commits

## Non-regression (offline pytest)

- ordinary service description, price, payment stages, doctor-by-service
- pain reassurance, known MD contraindication from FullContext
- missing-base controlled response, consultation close
- CTA allowed=true vs allowed=false
- ordinary non-medical answer
- S45–S48a harness neighbors green

```text
pytest tests/test_target_composer_executor.py tests/test_target_response_verifier.py tests/test_target_fullcontext_content_response.py tests/test_fullcontext_response_eval_harness.py tests/test_fullcontext_response_eval_matrix_contract.py -q -p no:cacheprovider --basetemp=$env:TEMP\pytest_basetemp_s48b_<runid>
```

## Process

1. Governance TASK commit → PRE-CODE checker ✅
2. Implementation commit → COMPLETION checker ✅
3. Push `codex/stage-a` → clean/synced → **stop (NO LIVE)**

## Acceptance

1. PRE-CODE ✅ on governance TASK.
2. Composer directives include allow_cta / allow_consultation_close / allow_marketing_facts.
3. Policy strings encode known-medical, missing-base, grounding, CTA rules (universal).
4. Verifier spec payload includes allow_cta / allow_consultation_close.
5. Targeted offline pytest green; frozen artifact SHA pins unchanged.
6. COMPLETION ✅ → push → stop.

**Completion report must state:** offline tests confirm contract/prompt wiring only;
model quality not proven until separate approved live re-eval.
