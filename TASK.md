# TASK — S34 Spec-bound Offline Package Integration

**Branch / baseline:** `codex/stage-a` / `c949571 feat: build deterministic response spec S33`

**Goal:** bind one explicit S33/S32 spec to the proven S31 offline package for the
composition fields that current contracts can enforce. Offline/unwired and not yet safe
for Composer because topic-scope/required-fact evidence enforcement is still absent.

## Owner laws

- Spec owns service ID, required components, follow-up family and permission ceilings.
- Caller explicitly requests actual inclusion of initial marketing, consultation close and
  CTA; a request may be narrower than spec permission, never wider.
- S34 calls public S31 once and passes spec-owned composition values unchanged.
- It does not pretend current evidence has topic tags or complete required-fact coverage.
- No terminal/payload-free spec is materialized through service-centric S31.

## Contract

Add `core/target_spec_offline_response_package.py`:

```python
@dataclass(frozen=True, slots=True)
class TargetSpecBoundOfflineResponsePackage:
    spec: TargetResponseSpec
    package: TargetOfflineResponsePackage
    selected_cta_key: str | None

def assemble_target_spec_offline_response_package(
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    external_index: ResponseSchemaExternalIndex,
    consultation_values: Sequence[ServiceConsultationValue],
    *,
    spec: TargetResponseSpec,
    brand_term: str | None,
    strategy_context: TargetStrategyMatch,
    semantic_context: str,
    today: date,
    md_root: Path,
    include_initial_block: bool,
    include_consultation_close: bool,
    include_cta: bool,
    marketing_scenarios: Sequence[str] = (),
    shown_fact_ids: Sequence[str] = (),
    shown_amplifier_refs: Sequence[str] = (),
    shown_consultation_value_refs: Sequence[str] = (),
) -> TargetSpecBoundOfflineResponsePackage: ...
```

Validation order, one public `TargetSpecOfflineResponsePackageError(ValueError)` with
`.code`, `.value`, exact message `f"{code}: {value!r}"`:

1. exact `TargetResponseSpec` → `spec_package_spec_invalid`, original value;
2. each include flag in signature order must be exact bool →
   `spec_package_selection_invalid`, `(field_name, original_value)`;
3. only `answer` or evidence-bearing `medical_handoff` with non-None `service_id` and
   nonempty required components is materializable → `spec_package_not_materializable`,
   `(response_mode, service_id, required_components)`;
4. initial marketing or nonempty/non-tuple marketing scenarios while
   `allow_marketing_facts=False` → `spec_package_permission_forbidden`,
   `"marketing_facts"`;
5. requested consultation while disallowed → same code, `"consultation_close"`;
6. requested CTA while disallowed → same code, `"cta"`.

Exactly four error-code strings exist. After these gates, S31 and downstream typed errors
propagate unchanged.

S31 mapping:

- `service_term=spec.service_id`;
- `required_components=spec.required_components`;
- `followup_source=spec.followup_source`;
- `include_initial_block` and `include_consultation_close` pass to S31 unchanged;
- `include_cta` is consumed only by S34 and is never forwarded to S31;
- all remaining caller inputs pass unchanged;
- result preserves exact spec/package identities;
- `selected_cta_key=package.plan.cta_key` only when `include_cta=True`, otherwise `None`.

The internal S31 package may retain a CTA candidate identity; consumers of S34 must use
only `selected_cta_key`. No facts/components/followups are rebuilt or reselected.

`package.materials` and `package.followup_candidates` remain **internal candidate evidence**
and may contain content/offers/doctors not permitted by the exact closed
`spec.required_components`. They are never an allowed response payload. The only
consumable composition view is:

- component identities from `package.plan` (`primary_content_ref`, `offer_ids`,
  `doctor_ids`) as projected by the spec-owned component tuple;
- selected marketing identities from `package.plan` (`commercial_fact_ids`,
  `external_source_refs`) only when marketing permission + requested inclusion allowed S31
  to select them;
- `package.plan.consultation_content_ref` only when consultation permission + requested
  inclusion allowed S31 to select it;
- `package.selected_followups`;
- S34 `selected_cta_key`.

`package.plan.cta_key` remains an internal candidate and is not consumable directly.

Tests must prove omitted content/price/doctors can remain inside candidate materials while
their corresponding plan identity is `None`/empty and therefore not consumable.

## Explicit incomplete safety boundary

S34 carries `allowed_topics`, `forbidden_topics` and `required_fact_ids` inside the exact
spec but **does not enforce them against evidence**: current S31 evidence lacks canonical
topic/fact coverage metadata. Therefore S34 output must not feed Composer, Verifier, UI or
product path. The next checkpoint must close this evidence-scope gap rather than add more
response-policy inference.

## Boundaries / allowlist

No TurnFrame/A9/raw inference, terminal rendering, MD/data changes, Composer/Verifier,
runtime/UI/session, authority or live/LLM. Do not edit S27–S33 or clients.

- `TASK.md`
- `core/target_spec_offline_response_package.py`
- `tests/test_target_spec_offline_response_package.py`
- `tests/test_demo_target_spec_offline_response_package.py`
- `docs/ARCH_TARGET_DESIGN.md`
- `docs/STRANGLER_ROADMAP.md`

## Minimal tests

- exact frozen shape/signature/defaults/four errors and validation precedence;
- permission requests cannot widen spec; narrower selection is accepted;
- exact spec values map once into S31 and identities/errors are preserved;
- content-only/price-only/doctors-only plans are the sole closed component view even while
  omitted candidates remain in internal materials;
- terminal, pure-medical and service-less specs fail before S31;
- real demo All-on-4 content/price/doctors/follow-ups, marketing/consultation/CTA gating;
- CTA consumers get only selected_cta_key; no client writes;
- explicit proof that topic/fact scope remains carried but unenforced/unwired;
- import firewall and no skip/xfail/live.

Run S34 target/demo plus S33, S32 and S31 target/demo neighbors only. No full suite/live.

## Gates

1. Independent governance checker `✅` before code.
2. Commit/push `docs: govern spec-bound offline package S34` only to stage-a.
3. Implement allowlist and run target + four neighbor files.
4. Independent completion checker `✅`, roadmap `[x]`.
5. Commit/push `feat: bind response spec to offline package S34`; final clean/synced.

Next checkpoint: canonical evidence topic/fact-coverage enforcement before Composer.
