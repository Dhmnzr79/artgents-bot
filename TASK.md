# TASK — S47 First-Live Failure / Incident Audit Capture

**Baseline:** `codex/stage-a` / `5b2bf32` · NO LIVE · NO product code

**Goal:** governance-only capture of S47 first live incident, owner decisions,
corrected causal taxonomy, audit SHA pins. **Frozen raw/result byte-identical.**

## Owner decisions (binding for this checkpoint)

1. **Run-2 artifacts:** diagnostic evidence + manual inspection material only;
   **not** S47 pass proof, **not** AUTOMATED_PASS input. Full manual quality
   verdict not required (automated stage = FAIL).
2. **76-call overrun:** incident cost, **not** retroactive approval, **not**
   precedent. Any re-run needs new owner approval.
3. **fc_medical_01:** owner manual ruling — acceptable grounded general medical
   answer; Verifier reject = probable FP for offline investigation.

## Non-regression principle (for future offline milestone — document only)

- No disease-name / case_id / exact-question special-casing.
- Universal rules: grounded+consultation | missing-base honest | no personal med verdict.
- Blast-radius before each change; compact regression set + S45–S47 neighbors green.
- No dry-refusal regression on commercial/informational paths.

## Deliverables (governance/docs only)

1. `docs/S47_FIRST_LIVE_INCIDENT_AUDIT.md` — full incident report.
2. `evals/v5/artifacts/s47_first_live_incident_manifest.json` — SHA pins, verdicts, taxonomy.
3. `evals/v5/artifacts/s47_first_live_run1_audit.log` — copy of run-1 log (append-only capture).
4. `docs/STRANGLER_ROADMAP.md` — S47 live status note (incident captured, not passed).

## Forbidden

- Live / LLM calls; product/runtime/UI/A9 changes.
- **Any modification** to `fullcontext_response_eval_live_raw.json`,
  `fullcontext_response_eval_live_result.json` (byte-identical).
- Matrix hash / harness / verifier / composer code changes.
- Offline-fix milestone implementation.

## Acceptance

1. PRE-CODE ✅ → governance commit (TASK only).
2. Incident docs + manifest + run1 log capture committed.
3. SHA-256 verification: raw `0f4d4b93…`, result `83bff177…`, matrix `14b1cbd4…` unchanged.
4. `pytest tests/test_fullcontext_response_eval_matrix_contract.py -q` green.
5. COMPLETION ✅ → push `codex/stage-a` → clean/synced.

**Stop after push. Do not start offline-fix milestone.**
