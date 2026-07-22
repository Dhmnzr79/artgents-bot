# TASK — S33 Minimal Deterministic ResponsePolicy Builder

**Branch / baseline:** `codex/stage-a` / `644226d feat: define canonical response spec S32`

**Goal:** build one valid S32 `TargetResponseSpec` from a strict explicit non-A9 request.
This first policy slice owns only follow-up family choice from exact component focus; all
other policy decisions remain explicit inputs.

## Owner laws

- No raw text, TurnFrame object, patient_scope, inference, taxonomy or product authority.
- Upstream explicitly supplies mode, scope, facts, requested components and permissions.
- Builder derives only `followup_source` using the owner-approved component-focus rule.
- Terminal normal payload and medical safety remain enforced by canonical S32 validation;
  request-only terminal primary focus is rejected before S32.
- Never catch/wrap S32 `ValidationError`, add fallback or silently repair invalid payload.

## Contract

Add `contracts/target_response_policy.py`:

```python
class TargetResponsePolicyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    response_mode: TargetResponseMode
    service_id: CanonicalToken | None = None
    tone_key: CanonicalToken
    allowed_topics: tuple[CanonicalToken, ...]
    forbidden_topics: tuple[CanonicalToken, ...] = ()
    required_fact_ids: tuple[CanonicalToken, ...] = ()
    requested_components: tuple[TargetResponseComponent, ...]
    primary_component: TargetResponseComponent | None = None
    allow_marketing_facts: bool = False
    allow_consultation_close: bool = False
    allow_cta: bool = False
```

Request cross-validation order:

1. `clarify`/`defer` with non-`None` `primary_component` →
   `terminal_primary_component_forbidden`. This request-only field cannot be silently
   discarded; this reason wins over any other terminal payload error.
2. For terminal requests with no primary, skip remaining focus validation so canonical
   S32 `terminal_response_payload_forbidden` remains owner of facts/components/allow flags.
3. Non-terminal `primary_component` absent from `requested_components` →
   `policy_primary_component_missing`.
4. Non-terminal content+price with `primary_component=None` →
   `policy_followup_source_ambiguous`.

Add `core/target_response_policy.py`:

```python
class TargetResponsePolicyBuildError(ValueError):
    # stores code/value; exact message f"{code}: {value!r}"

def build_target_response_spec(
    request: TargetResponsePolicyRequest,
) -> TargetResponseSpec: ...
```

Wrong exact request type raises `response_policy_request_invalid`, value = original
request. This is the only builder error code.

Follow-up derivation for non-terminal requests:

- primary `content`/`price` → same source;
- primary `doctors` → `None`;
- no primary and only content-capable family present → `content`;
- no primary and only price-capable family present → `price`;
- neither → `None`; content+price/no primary is rejected by request validation.

For terminal requests builder passes `followup_source=None`; any requested facts,
components or allow flags are then rejected by S32 with
`terminal_response_payload_forbidden`. All request fields otherwise pass exactly into S32,
with `requested_components` renamed to `required_components` and authored order preserved.

Request-model focus validation necessarily precedes S32 construction. Therefore on a
combined-invalid non-terminal request (including `medical_handoff`), primary-missing or
ambiguous-focus reasons win over S32 scope/medical reasons. This is explicit fail-closed
precedence; canonical S32 reasons propagate unchanged once request focus is valid.

## Boundaries

This does not decide response mode, topic scope, components, facts, tone or sales
permissions. Manual-contact/booking still terminate before ResponseSpec. No evidence,
selectors, S31 wiring, MD/JSON/client reads, Composer, Verifier, runtime/UI/session,
authority or live/LLM. A9 remains shadow-only and is neither imported nor read.

Allowlist:

- `TASK.md`
- `contracts/target_response_policy.py`
- `core/target_response_policy.py`
- `tests/test_target_response_policy.py`
- `docs/ARCH_TARGET_DESIGN.md`
- `docs/STRANGLER_ROADMAP.md`

## Minimal tests

- exact request fields/defaults and strict/frozen/extra-forbid shape;
- exact builder signature/error class/message and sole code;
- single content, single price, doctor-only and no-component focus;
- composite content+price requires explicit primary; doctor primary selects no follow-up;
- authored component/fact/topic order passes unchanged;
- terminal primary focus has its exact request error; with no primary, terminal S32 error
  wins over remaining focus ambiguity and no payload is repaired;
- pure and sales-capable medical specs preserve mandatory S32 boundary;
- combined-invalid medical focus proves request-focus precedence; focus-valid S32 reasons
  propagate unchanged; input unchanged;
- import firewall: no TurnFrame/patient_scope/A9/client/runtime/live, no skip/xfail.

Run S33 target plus S32 target and S30/S31 target+demo neighbors only. No full suite/live.

## Gates

1. Independent governance checker `✅` before code.
2. Commit/push `docs: govern deterministic response policy S33` only to stage-a.
3. Implement allowlist and run target + five neighbor files.
4. Independent completion checker `✅`, roadmap `[x]`.
5. Commit/push `feat: build deterministic response spec S33`; final clean/synced.

Next checkpoint: integrate explicit S33 spec into the S31 offline package boundary. Do not
add topic/aspect inference until that integration proves an exact missing contract.
