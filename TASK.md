# TASK — S32 Canonical Target ResponseSpec Contract

**Branch / baseline:** `codex/stage-a` / `c14f941 feat: assemble offline response package S31`

**Goal:** define the smallest strict, immutable upstream `TargetResponseSpec` schema. This
checkpoint validates an explicit spec only; it does not derive one from TurnFrame or govern
the product response path.

## Owner laws

- ResponseSpec is a declarative safety/composition contract, never a topic prompt table.
- It owns canonical response mode, topic scope, required facts/components and permissions.
- It does not select evidence, facts, services, doctors, prices or wording.
- `required_components` is the exact closed payload set: omitted components are forbidden.
- Existing S28/S30 type aliases move to this upstream contract; behavior stays unchanged.
- `medical_handoff` is a mandatory downstream safety restriction, not a descriptive label:
  consumers may use only source-owned general facts and policy-permitted price/marketing/
  CTA, never diagnosis, differential diagnosis, personal eligibility or treatment choice.

## Contract

Add `contracts/target_response_spec.py` with canonical aliases:

```python
TargetResponseMode = Literal["answer", "clarify", "defer", "medical_handoff"]
TargetResponseComponent = Literal["content", "price", "doctors"]
TargetFollowupSource = Literal["content", "price"]

class TargetResponseSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    response_mode: TargetResponseMode
    service_id: CanonicalToken | None = None
    tone_key: CanonicalToken
    allowed_topics: tuple[CanonicalToken, ...]
    forbidden_topics: tuple[CanonicalToken, ...] = ()
    required_fact_ids: tuple[CanonicalToken, ...] = ()
    required_components: tuple[TargetResponseComponent, ...]
    followup_source: TargetFollowupSource | None = None
    allow_marketing_facts: bool = False
    allow_consultation_close: bool = False
    allow_cta: bool = False
```

`CanonicalToken` is an exact non-empty string with no leading/trailing whitespace.
Strict mode rejects coercion and list-for-tuple input. Each tuple must preserve authored
order and be unique, with exact reason tokens:

- `allowed_topic_duplicate`
- `forbidden_topic_duplicate`
- `required_fact_id_duplicate`
- `required_component_duplicate`

Cross-field validation order and exact reasons:

1. allowed/forbidden overlap → `response_topic_scope_overlap`;
2. `answer` or `medical_handoff` with empty allowed topics → `response_scope_empty`;
3. `answer` with no required components → `response_components_empty`;
4. `clarify`/`defer` with required facts/components, follow-up source or any three allow
   flags true → `terminal_response_payload_forbidden`;
5. content/price follow-up without the same required component →
   `followup_source_component_missing`;
6. `medical_handoff` with empty forbidden topics → `medical_forbidden_topics_empty`.

`medical_handoff` may be a pure safe handoff with empty `required_components`, or may allow
source-owned content/price/doctors/marketing/CTA under future policy. `forbidden_topics`
is an additional evidence-scope restriction; it is **not** the no-diagnosis mechanism.
Manual-contact cases (current personal pain, active complication, complaint) hard-stop
before ResponseSpec and cannot be represented by this sales-capable medical mode.

## Type ownership migration

- S28 imports `TargetResponseComponent` from the new contract and removes its local alias.
- S30 imports `TargetFollowupSource` from the new contract and removes its local alias.
- S31 imports `TargetFollowupSource` from the contract directly.
- Existing public imports from S28/S30 must remain compatible because imported names are
  still module attributes. No other S28–S31 code or behavior changes.

## Boundaries

No ResponsePolicy builder, TurnFrame/A9 read, manual-contact/booking handling, evidence
selection, MD/JSON/client data, Composer, Verifier, runtime/UI/session, authority or
live/LLM. No product flag. Do not edit clients or A9 artifacts.

Allowlist:

- `TASK.md`
- `contracts/target_response_spec.py`
- `core/target_response_materialization_plan.py` (import ownership only)
- `core/target_response_followup_policy.py` (import ownership only)
- `core/target_offline_response_package.py` (import ownership only)
- `tests/test_target_response_spec.py`
- `tests/test_target_response_materialization_plan.py` (protected firewall compatibility:
  add only `contracts.target_response_spec` to its allowed import set)
- `docs/ARCH_TARGET_DESIGN.md`
- `docs/STRANGLER_ROADMAP.md`

## Minimal tests

- exact fields/defaults, strict/frozen/extra-forbid model and canonical aliases;
- valid answer, medical_handoff, clarify and defer specs;
- exact token, tuple uniqueness, scope and cross-field reason tokens/order;
- medical mode is valid both as pure handoff and with source-owned sales data, always
  carrying mandatory no-diagnosis semantics plus explicit additional forbidden scope;
- terminal modes cannot leak normal response payload and their error precedes follow-up
  source/component consistency;
- source/component consistency and authored tuple order;
- S28/S30 compatibility imports and S31 canonical ownership;
- import firewall, no skip/xfail/client writes/live.

Run S32 tests plus S28, S30 and S31 target/demo neighbors only. No full suite, A9 or live.

## Gates

1. Independent governance checker `✅` before code.
2. Commit/push `docs: govern canonical response spec S32` only to `codex/stage-a`.
3. Implement allowlist and run target + six neighbor files.
4. Independent completion checker `✅`, roadmap `[x]`.
5. Commit/push `feat: define canonical response spec S32`; final clean/synced.

Next checkpoint: a separate deterministic ResponsePolicy builder from explicit non-A9
inputs into this spec; no product authority transfer.
