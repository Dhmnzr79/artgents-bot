# TASK — S56 topic-scoped consultation facts + missing-base Composer guard

**Baseline:** `codex/stage-a` / `d686ef6` · **OFFLINE ONLY · NO LIVE**

## Goal

Close two confirmed S55 verifier FN root causes without live/LLM, without Verifier expansion, and without frozen S47/S50/S53/S55 artifact changes:

**A.** `fc_boundary_03` — «бесплатная консультация» in corpus but **0 PRIMARY_EVIDENCE** when `service_id=None`.

**B.** `fc_missing_01` — missing-base transfer of diabetes/immune facts onto absent lupus topic (Composer policy gap).

## Owner principle

Bot is a seller. False blocks worse than rare misses except serious violations (invented clinic facts/numbers, medical conclusions, substantial external medical claims). Verifier stays light — **no Verifier changes in S56 unless audit proves mandatory** (audit: not mandatory; structured evidence + existing Composer/semantic checks suffice).

## Read-only audit summary (pre-code)

| Area | Finding |
|------|---------|
| `TargetCommercialFact` | `allowed_service_ids` only; **no `allowed_topics`** |
| `target_marketing_selector._fact_is_eligible` | `service_id=None` + fact with `allowed_service_ids` → rejected (`None not in list`) — correct for marketing path; topic-only facts with empty `allowed_service_ids` would wrongly pass when `service_id` set — needs guard |
| `assemble_target_fullcontext_content_bound_package` | Always `commercial_facts=()`, `commercial_fact_ids=()` — root cause of 0 PRIMARY_EVIDENCE for FullContext content-only |
| `TARGET_COMPOSER_SYSTEM_POLICY` rule 7 | Has missing-base language; needs minimal strengthen (no transfer/classification of absent disease) |
| Demo `free_implant_consult` | Active until 2026-12-31; text covers implantation+prosthetics; needs client `allowed_topics`, not core hardcode |
| Verifier | Existing `unsupported_clinic_claim` + semantic backend sufficient for ungrounded «бесплатная» when no structured fact |

## Scope A — topic-scoped consultation facts

Universal client-pack mechanism (no demo hardcode in shared core):

1. Add optional `allowed_topics: list[NonBlankStr]` to `TargetCommercialFact` (+ duplicate validation).
2. New `core/target_topic_scoped_commercial_fact.py`: `select_topic_scoped_consultation_fact()` — deterministic, max 1 fact.
3. Eligibility when `service_id=None` only:
   - fact has non-empty `allowed_topics`;
   - `turn_topic` in `allowed_topics`;
   - `active=true`, valid date range;
   - not shown (respect `shown_fact_ids` if passed).
4. When `service_id` set: existing `allowed_service_ids` marketing path **unchanged**; topic-only facts (`allowed_topics` non-empty, `allowed_service_ids` empty) **not** eligible via marketing selector.
5. Wire selected fact into FullContext content-only package: `commercial_facts`, `commercial_fact_ids`, PRIMARY_EVIDENCE block — **only** when `include_consultation_close` and `spec.allow_consultation_close`.
6. Do **not** enable full marketing dump for `service_id=None`; do **not** weaken CTA/contact rules.
7. Demo client: add `allowed_topics: ["implantation", "prosthetics"]` to `free_implant_consult` per fact text and topic taxonomy.

## Scope B — missing-base Composer guard

Minimal strengthen `TARGET_COMPOSER_SYSTEM_POLICY` rule 7 (add explicit bans on top of existing transfer/general-category text):

- If specific condition/topic absent from CACHED_FULL_CONTEXT: honest «нет в материалах» + neutral consultation invite when allowed.
- **Add explicitly forbidden:** naming or classifying the absent condition; applying contraindications, immune-system properties, or medical conclusions documented for other conditions (e.g. diabetes) onto the absent topic.
- Known grounded medical topics unchanged.

**Do NOT:** new Verifier issue kinds, thresholds, retry/repair, disease regex, RAG, new selector engine, frozen matrix/live artifact changes.

## Затрагиваемые файлы (allowlist)

| File | Change |
|------|--------|
| `TASK.md` | S56 governance |
| `contracts/response_schema.py` | `allowed_topics` on `TargetCommercialFact` |
| `core/target_topic_scoped_commercial_fact.py` | **new** selector |
| `core/target_marketing_selector.py` | topic-only fact guard when `service_id` set |
| `core/target_fullcontext_content_package.py` | wire topic-scoped fact into package |
| `core/target_scoped_response_evidence.py` | FullContext content-only: pass topic-scoped fact into `commercial_fact_ids` / PRIMARY_EVIDENCE |
| `core/target_composer_request.py` | FullContext content-only: build `commercial_fact` evidence blocks from scoped fact |
| `core/target_spec_offline_response_package.py` | pass bundle/topic/today/shown/`include_consultation_close` |
| `core/target_policy_bound_verified_response_pipeline.py` | pass `turn_topic` |
| `core/target_turn_frame_bound_response.py` | pass `turn_frame.topic` |
| `core/target_composer_executor.py` | policy rule 7 minimal strengthen |
| `clients/demo/target_response/pricebook/facts.json` | `allowed_topics` on `free_implant_consult` |
| `tests/test_s56_topic_scoped_consultation_facts.py` | **new** acceptance tests 1–5, 9 |
| `tests/test_s56_missing_base_composer_guard.py` | **new** acceptance tests 6–8 |
| `docs/STRANGLER_ROADMAP.md` | S56 checkpoint row |

## Protected / forbidden

- **Do not change:** frozen S47/S50/S53/S55 eval artifacts; `evals/v5/demo/fullcontext_response_eval_matrix*.json`; S55 replay harness behavior; `core/target_response_verifier.py` (unless STOP — not expected).
- **Do not run:** live/LLM; S55/S53/S50 rerun.
- **No:** runtime/UI/session wiring; product authority; A9; merge/push to main.

## Acceptance criteria (offline)

1. `service_id=None` + implantation topic + active demo fact → structured PRIMARY_EVIDENCE contains free consult fact.
2. Multiclient prosthetics-only fact → **not** selected for implantation topic.
3. Same prosthetics-only fact → selected for prosthetics topic.
4. inactive/expired/mismatched topic fact → not selected.
5. «бесплатная» without confirmed structured fact → not allowed as clinic claim (verifier path or zero evidence + semantic reject).
6. Missing-base lupus/unknown path → no diabetes/immune transfer (Composer policy + existing semantic tests).
7. Known grounded medical topic (diabetes) stays green.
8. Mass-selling scenarios green: general info, pain reassurance, price, payment, doctors, marketing, commercial answer (neighbor tests).
9. Service-specific price/doctor/marketing paths unchanged.
10. No live/LLM calls.

## Tests (targeted pytest only)

```powershell
$bt = Join-Path $env:TEMP ("s56_pytest_" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_s56_topic_scoped_consultation_facts.py `
  tests/test_s56_missing_base_composer_guard.py `
  tests/test_target_fullcontext_content_response.py `
  tests/test_target_marketing_selector.py `
  tests/test_demo_target_offline_response_assembly.py `
  tests/test_demo_target_scoped_response_evidence.py `
  tests/test_response_schema_contract.py `
  -q
```

Remove `$bt` from workspace after run if created under repo.

## Commits (after PRE-CODE ✅)

1. Governance: `TASK.md`, `docs/STRANGLER_ROADMAP.md`
2. Implementation: code + tests

Push only to `origin/codex/stage-a`.

## PRE-CODE checker

Run read-only checker subagent on governance commit before any implementation.

## COMPLETION checker

Run read-only checker on full diff after targeted pytest green.
