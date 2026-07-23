# TASK — S59 final semantic Verifier medical policy simplification

**Baseline:** `codex/stage-a` / `269885f` · **OFFLINE ONLY · NO LIVE**

## Owner decision

Lightweight Verifier — not heavy medical guardrails.

Semantic Verifier blocks only:
1. diagnosis in bot's name;
2. personal medical conclusion, eligibility, treatment choice or advice;
3. clearly dangerous, absurd, or corpus-contradicting medical fantasy.

Plausible general medical additions absent from base:
- do **not** block;
- may return non-blocking `minor_external_detail`;
- missing grounding alone is **not** a block reason.

No runtime logging system now (future admin stage). Non-blocking issues stay in assessment output.

Deterministic price/number/doctor/strict clinic fact checks **unchanged**.

## Scope

Minimal change to `TARGET_SEMANTIC_VERIFIER_SYSTEM_POLICY` in `core/target_response_verifier.py` only.
Four existing issue kinds preserved; blocking kinds unchanged in code.

## Boundaries

| Kind | S59 boundary |
|------|----------------|
| `personal_medical_conclusion` | blocking |
| `unsupported_clinic_claim` | blocking (unchanged) |
| `material_external_medical_claim` | blocking only dangerous/absurd/corpus-contradicting |
| `minor_external_detail` | non-blocking plausible general addition |

## Do NOT add

New issue kinds, confidence thresholds, disease lists, medical regex, voting, retry/repair, second Verifier, fallback, runtime logging, new live matrices.

## S58 historical note

Frozen S58 verdict/artifacts stay FAIL under old policy. Offline tests confirm S58 blocked classes would be non-blocking under S59 policy text + simulator.

## Затрагиваемые файлы (allowlist)

| File | Change |
|------|--------|
| `TASK.md` | S59 governance |
| `docs/STRANGLER_ROADMAP.md` | S59 checkpoint |
| `core/target_response_verifier.py` | semantic policy text only |
| `tests/s59_semantic_policy_backend.py` | **new** offline S59 policy simulator |
| `tests/test_s59_semantic_verifier_policy.py` | **new** acceptance tests |
| `tests/test_target_fullcontext_content_response.py` | update RuleBasedSemanticBackend + neighbor tests |
| `tests/test_target_boundary_enforced_fullcontext_response.py` | missing_ok S59 alignment |
| `tests/test_s56_missing_base_composer_guard.py` | S59 expectation |
| `tests/test_fullcontext_quality_eval_harness.py` | S59 S58-class expectations |
| `tests/test_target_response_verifier.py` | policy assertion update |

## Protected / forbidden

- Do **not** change frozen S47/S50/S53/S55/S58 artifacts or matrices
- Do **not** change numeric/strict-fact verifier logic
- NO LIVE / NO LLM / NO runtime / NO authority / NO A9

## Offline acceptance tests

PASS / non-blocking: lupus+immune general, pregnancy/hormones/lactation general, pain, diabetes grounded, price/payment/doctors/info, S56 free consult, S58 two previously blocked classes.

BLOCK: personal diagnosis/eligibility/treatment choice, absurd/dangerous claim, corpus contradiction, invented clinic facts (semantic + numeric).

## Targeted pytest

```powershell
$bt = Join-Path $env:TEMP ("s59_pytest_" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_s59_semantic_verifier_policy.py `
  tests/test_target_response_verifier.py `
  tests/test_target_fullcontext_content_response.py `
  tests/test_s56_topic_scoped_consultation_facts.py `
  tests/test_s56_missing_base_composer_guard.py `
  tests/test_fullcontext_quality_eval_harness.py `
  tests/test_fullcontext_quality_eval_matrix_contract.py `
  tests/test_fullcontext_verifier_replay_harness.py::test_blast_radius_summary_covers_mass_selling_groups `
  -q
```

## Commits

1. Governance: TASK.md, STRANGLER
2. Implementation: policy + tests

Push only to `origin/codex/stage-a`.

## PRE-CODE / COMPLETION checker

Required before/after implementation respectively.
