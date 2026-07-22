# TASK — S41 TurnFrame-bound Offline Response Dispatch

**Branch / baseline:** `codex/stage-a` / `04e3dac feat: compose policy-bound offline verified response pipeline S40`

**Goal:** add one deterministic TurnFrame dispatch boundary and a thin orchestrator that
materializes `TargetResponsePolicyRequest` from `TurnFrame` + explicit envelope, calls S40
only on the materialize path, and returns separate terminal decisions for
clarify/defer/non-materializable medical handoff. No runtime/UI/live wiring.

## Owner laws

- S41 adds dispatch + orchestration only. It does not read `patient_scope`, infer
  medical_handoff from TurnFrame axes, load demo packs in core, parse model text, or create
  another evidence/policy layer.
- `medical_handoff` comes only from `envelope.boundary_decision == "medical_handoff"`.
- Aspect mapping is fixed: `payment → price`; `stages → content` always; never map `stages`
  to `price` by intent or other aspects. `price + stages → (content, price)`.
- For `topic == "doctors"`, do not add `content` from `overview` alone. Valid confident
  `topic` used in dispatch must intersect `envelope.allowed_topics` and not intersect
  `envelope.forbidden_topics`; incompatibility is a typed fail-closed error.
- Invalid input/metadata raises `TargetTurnFrameDispatchError`. Successful dispatch returns
  only `materialize | terminal`; no `failed` union member and no optional verified field.
- Terminal `clarify | defer | medical_handoff_nonmaterializable` stops before S34/S40.
  Materializable `answer | medical_handoff` calls public S40 exactly once and returns exact
  verified response unchanged.
- Stage order on materialize path is strict `dispatch → S40`. No catch/rename/retry/fallback.
- S41 is offline/unwired. Loaders facade in core, TurnFrame/A9 authority, routes/UI/session,
  live/LLM and product authority require later explicit decisions.

## Contract

Add `contracts/target_turn_frame_policy_envelope.py`:

```python
class TargetTurnFramePolicyEnvelope(BaseModel):
    boundary_decision: Literal["none", "medical_handoff"]
    tone_key: CanonicalToken
    allowed_topics: tuple[CanonicalToken, ...]
    forbidden_topics: tuple[CanonicalToken, ...] = ()
    required_fact_ids: tuple[CanonicalToken, ...] = ()
    allow_marketing_facts: bool = False
    allow_consultation_close: bool = False
    allow_cta: bool = False
    min_topic_confidence: float = 0.0
    min_service_confidence: float = 0.0
    min_intent_confidence: float = 0.0
```

Add `contracts/target_turn_frame_dispatch.py` with frozen dataclasses:

- `TargetTurnFrameMaterializeDispatch(kind="materialize", policy_request=...)`
- `TargetTurnFrameTerminalDispatch(kind="terminal", terminal_mode=..., spec=...)`
- `TargetTurnFrameBoundMaterializeResponse(kind="materialize", dispatch=..., verified=...)`
- `TargetTurnFrameBoundTerminalResponse(kind="terminal", dispatch=...)`

Add `core/target_turn_frame_dispatch.py`:

```python
class TargetTurnFrameDispatchError(ValueError): ...

def dispatch_target_turn_frame_response(
    turn_frame: TurnFrame,
    envelope: TargetTurnFramePolicyEnvelope,
) -> TargetTurnFrameMaterializeDispatch | TargetTurnFrameTerminalDispatch: ...
```

Add `core/target_turn_frame_bound_response.py`:

```python
def run_target_offline_turn_frame_bound_response(
    turn_frame: TurnFrame,
    envelope: TargetTurnFramePolicyEnvelope,
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
) -> TargetTurnFrameBoundMaterializeResponse | TargetTurnFrameBoundTerminalResponse: ...
```

Exact orchestrator sequence:

```python
dispatch = dispatch_target_turn_frame_response(turn_frame, envelope)
if dispatch.kind == "terminal":
    return TargetTurnFrameBoundTerminalResponse(kind="terminal", dispatch=dispatch)
return TargetTurnFrameBoundMaterializeResponse(
    kind="materialize",
    dispatch=dispatch,
    verified=run_target_offline_policy_bound_verified_response_pipeline(
        dispatch.policy_request,
        ...,
    ),
)
```

No conditional branch beyond the dispatch kind check and no exception handler in the
orchestrator function.

## Boundaries / allowlist

No client data edits, loaders facade in core, old runtime path, live/LLM/provider SDK,
A9/TurnFrame shadow wiring, routes/UI/session/cache, product authority, changes to S27–S40
code/contracts/tests, or full suite.

- `TASK.md`
- `contracts/target_turn_frame_policy_envelope.py`
- `contracts/target_turn_frame_dispatch.py`
- `core/target_turn_frame_dispatch.py`
- `core/target_turn_frame_bound_response.py`
- `tests/test_target_turn_frame_dispatch.py`
- `tests/test_demo_target_turn_frame_bound_response.py`
- `docs/ARCH_TARGET_DESIGN.md`
- `docs/STRANGLER_ROADMAP.md`

## Minimal protected acceptance

- fixed aspect mapping including owner correction: `payment → price`, `stages → content`
  always; `price + stages → (content, price)`;
- doctors-only path: valid confident `topic=doctors` with `overview` yields `(doctors,)`
  without content;
- valid confident topic used in dispatch must be envelope-compatible; incompatible topic
  raises typed error;
- `topic.field_meta.status == "invalid"` raises typed error;
- `needs_clarification` valid → terminal `clarify` spec, S40 not called;
- missing `service_id` on materialize path → terminal `defer`, S40 not called;
- `boundary_decision=medical_handoff` with materializable inputs → S40 once with
  `medical_handoff`; pure non-materializable handoff → terminal without S40;
- orchestrator union forbids impossible combinations (`verified` only on materialize branch);
- import firewall: no legacy/provider/live/runtime/cache/search/patient_scope reads, skip or
  xfail.

Run only S41 target/demo plus S40 and S33 target/demo neighbors. No full suite.

## Gates

1. Independent governance checker before code.
2. Commit/push `docs: govern TurnFrame-bound offline response dispatch S41` only to stage-a.
3. Implement only the allowlist and run minimal offline tests.
4. Independent completion checker, then roadmap `[x]`.
5. Commit/push `feat: dispatch TurnFrame-bound offline response S41`; final clean/synced.
