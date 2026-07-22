# TASK — S40 Policy-bound Offline Verified Response Pipeline

**Branch / baseline:** `codex/stage-a` / `8fe1fc3 feat: compose offline verified response pipeline S39`

**Goal:** compose the proven S33 ResponsePolicy builder, S34 spec-bound package assembly and
S39 verified response pipeline into one minimal provider-neutral offline entry point that
returns only an exact verified response from an explicit policy request. No runtime/UI/live
wiring.

## Owner laws

- S40 adds orchestration only. It does not select services/facts/doctors, rebuild evidence,
  duplicate validators, parse model text, infer policy fields, or create another policy layer.
- Call public S33 exactly once with the exact supplied `TargetResponsePolicyRequest`.
- Call public S34 exactly once with that exact spec and the exact supplied assembly inputs.
- Call public S39 exactly once with that exact bound package and the exact supplied pipeline
  inputs/backends. Return that exact verified result unchanged.
- Stage order is strict `S33 → S34 → S39`. No downstream call occurs after an upstream
  failure.
- Every existing typed error propagates unchanged. S40 adds no error type, catch, rename,
  retry, repair, fallback, partial response, logging/session/cache write or side effect.
- Follow-ups/CTA remain exact sidecars through S39 law; S40 neither renders nor reselects them.
- Recording Composer/semantic backends prove orchestration only. S40 does not prove answer
  wording, semantic verifier quality, latency/cost, or product readiness.
- S40 is still offline/unwired. Provider/live/LLM, TurnFrame/A9 authority, routes/UI/session
  and product authority require later explicit decisions.

## Contract

Add `core/target_policy_bound_verified_response_pipeline.py`:

```python
def run_target_offline_policy_bound_verified_response_pipeline(
    policy_request: TargetResponsePolicyRequest,
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    external_index: ResponseSchemaExternalIndex,
    consultation_values: Sequence[ServiceConsultationValue],
    *,
    brand_term: str | None,
    strategy_context: TargetStrategyMatch,
    semantic_context: str,
    today: date,
    md_root: Path,
    include_initial_block: bool,
    include_consultation_close: bool,
    include_cta: bool,
    user_message: str,
    tone: TargetComposerTone,
    composer_backend: TargetComposerBackend,
    semantic_backend: TargetSemanticVerifierBackend,
    marketing_scenarios: Sequence[str] = (),
    shown_fact_ids: Sequence[str] = (),
    shown_amplifier_refs: Sequence[str] = (),
    shown_consultation_value_refs: Sequence[str] = (),
) -> TargetVerifiedComposedResponse: ...
```

Exact implementation sequence:

```python
spec = build_target_response_spec(policy_request)
bound_package = assemble_target_spec_offline_response_package(
    bundle,
    doctor_catalog,
    external_index,
    consultation_values,
    spec=spec,
    brand_term=brand_term,
    strategy_context=strategy_context,
    semantic_context=semantic_context,
    today=today,
    md_root=md_root,
    include_initial_block=include_initial_block,
    include_consultation_close=include_consultation_close,
    include_cta=include_cta,
    marketing_scenarios=marketing_scenarios,
    shown_fact_ids=shown_fact_ids,
    shown_amplifier_refs=shown_amplifier_refs,
    shown_consultation_value_refs=shown_consultation_value_refs,
)
return run_target_offline_verified_response_pipeline(
    bound_package,
    bundle,
    doctor_catalog,
    consultation_values,
    user_message=user_message,
    md_root=md_root,
    tone=tone,
    composer_backend=composer_backend,
    semantic_backend=semantic_backend,
)
```

No conditional branch or exception handler is allowed in the pipeline function.

## Boundaries / allowlist

No client data edits, old RAG/composer/verifier, live/LLM/provider SDK, A9/TurnFrame/patient
scope, runtime/routes/UI/session/cache, product authority, new data model/policy/error, or
full suite. Do not edit S27–S39 code/contracts/tests.

- `TASK.md`
- `core/target_policy_bound_verified_response_pipeline.py`
- `tests/test_target_policy_bound_verified_response_pipeline.py`
- `tests/test_demo_target_policy_bound_verified_response_pipeline.py`
- `docs/ARCH_TARGET_DESIGN.md`
- `docs/STRANGLER_ROADMAP.md`

## Minimal protected acceptance

- exact public signature/return annotation and source-level straight-line sequence;
- S33, S34 and S39 each reached exactly once on success, in order;
- exact S33 spec is passed to S34; exact S34 bound package is passed to S39;
- verified result/text/spec/follow-up/CTA identities returned unchanged;
- S33 request failure calls neither S34 nor S39 and propagates exact error;
- S34 permission/material failure calls no S39 backend and propagates exact error;
- S39 downstream failures propagate unchanged with S39 short-circuit semantics;
- real demo All-on-4 crosses S33→S34→S39 with exact price/doctor/natural fact, one recording
  Composer and one recording semantic backend, verified sidecars and no client writes;
- recording outputs are explicitly orchestration fixtures, not answer-quality mocks;
- import firewall proves no legacy/provider/live/runtime/cache/search, skip or xfail.

Run only S40 target/demo plus S39, S34 and S33 target/demo neighbors. No full suite.

## Gates

1. Independent governance checker before code.
2. Commit/push `docs: govern policy-bound offline verified response pipeline S40` only to
   stage-a.
3. Implement only the allowlist and run minimal offline tests.
4. Independent completion checker, then roadmap `[x]`.
5. Commit/push `feat: compose policy-bound offline verified response pipeline S40`; final
   clean/synced.

After S40, the target response-generation vertical is structurally complete offline from an
explicit policy request through verified response. Live provider quality, upstream
TurnFrame/authority and product wiring remain separate governed work.
