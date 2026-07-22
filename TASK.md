# TASK — S39 Minimal Offline Verified Response Pipeline

**Branch / baseline:** `codex/stage-a` / `96510b1 feat: verify target composed response S38`

**Goal:** compose the proven S36 request materializer, S37 Composer executor and S38
Verifier into one minimal provider-neutral offline pipeline that returns only an exact
verified response. This is the target response vertical slice; no runtime/UI/live wiring.

## Owner laws

- S39 adds orchestration only. It does not select services/facts/doctors, rebuild evidence,
  duplicate validators, parse model text, or create another policy layer.
- Call public S36 exactly once with the exact supplied upstream package/sources/message/root.
- Call public S37 exactly once with that exact request, supplied tone and Composer backend.
- Call public S38 exactly once with the same exact request, exact S37 response and supplied
  semantic backend. Return that exact verified result unchanged.
- Stage order is strict `S36 → S37 → S38`. No downstream call occurs after an upstream
  failure. S38 deterministic rejection occurs before its semantic backend by S38 law.
- Every existing typed error propagates unchanged. S39 adds no error type, catch, rename,
  retry, repair, fallback, partial response, logging/session/cache write or side effect.
- Follow-ups/CTA remain exact sidecars: S37 does not send them to Composer; S38 preserves
  them; S39 neither renders nor reselects them.
- Recording Composer/semantic backends prove orchestration only. S39 does not prove answer
  wording, semantic verifier quality, latency/cost, or product readiness.
- S39 is still offline/unwired. Provider/live/LLM, TurnFrame/A9 authority, routes/UI/session
  and product authority require later explicit decisions.

## Contract

Add `core/target_verified_response_pipeline.py`:

```python
def run_target_offline_verified_response_pipeline(
    bound_package: TargetSpecBoundOfflineResponsePackage,
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    consultation_values: Sequence[ServiceConsultationValue],
    *,
    user_message: str,
    md_root: Path,
    tone: TargetComposerTone,
    composer_backend: TargetComposerBackend,
    semantic_backend: TargetSemanticVerifierBackend,
) -> TargetVerifiedComposedResponse: ...
```

Exact implementation sequence:

```python
request = materialize_target_composer_request(
    bound_package,
    bundle,
    doctor_catalog,
    consultation_values,
    user_message=user_message,
    md_root=md_root,
)
unverified = execute_target_composer(
    request,
    composer_backend,
    tone=tone,
)
return verify_target_composed_response(
    request,
    unverified,
    semantic_backend=semantic_backend,
)
```

No conditional branch or exception handler is allowed in the pipeline function.

## Boundaries / allowlist

No client data, old RAG/composer/verifier, live/LLM/provider SDK, A9/TurnFrame/patient
scope, runtime/routes/UI/session/cache, product authority, new data model/policy/error, or
full suite. Do not edit S27–S38 code/contracts/tests.

- `TASK.md`
- `core/target_verified_response_pipeline.py`
- `tests/test_target_verified_response_pipeline.py`
- `tests/test_demo_target_verified_response_pipeline.py`
- `docs/ARCH_TARGET_DESIGN.md`
- `docs/STRANGLER_ROADMAP.md`

## Minimal protected acceptance

- exact public signature/return annotation and source-level straight-line sequence;
- S36, Composer and semantic backend each reached exactly once on success, in order;
- exact S36 request is shared by S37 and S38; exact S37 response is supplied to S38;
- verified result/text/spec/follow-up/CTA identities returned unchanged;
- S36 source/material failure calls neither backend and propagates exact error;
- S37 validation/backend/output failure calls no semantic backend and propagates exact error;
- S38 numeric/strict rejection calls no semantic backend and propagates exact error;
- S38 semantic failure/rejection calls once, returns no partial result and propagates exact
  error;
- real demo All-on-4 crosses S36→S37→S38 with exact price/doctor/natural fact, one recording
  Composer and one recording semantic backend, verified sidecars and no client writes;
- recording outputs are explicitly orchestration fixtures, not answer-quality mocks;
- import firewall proves no legacy/provider/live/runtime/cache/search, skip or xfail.

Run only S39 target/demo plus S38, S37 and S36 target/demo neighbors. No full suite.

## Gates

1. Independent governance checker before code.
2. Commit/push `docs: govern offline verified response pipeline S39` only to stage-a.
3. Implement only the allowlist and run minimal offline tests.
4. Independent completion checker, then roadmap `[x]`.
5. Commit/push `feat: compose offline verified response pipeline S39`; final clean/synced.

After S39, the target response-generation vertical is structurally complete offline from an
exact upstream S34 package through verified response. Live provider quality, upstream
TurnFrame/authority and product wiring remain separate governed work; this is the intended
handoff checkpoint for Cursor-led implementation with Codex governance/review.
