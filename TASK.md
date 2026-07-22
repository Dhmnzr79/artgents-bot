# TASK — S42 Provider-neutral Target Medical Boundary Detector

**Branch / baseline:** `codex/stage-a` / `7aade44 docs: fix S41 test breakdown in STRANGLER_ROADMAP`

**Goal:** add one offline provider-neutral medical-boundary classifier boundary with strict
three-way semantics, deterministic envelope enforcement, and fail-closed uncertain handling.
No runtime wiring, no live/LLM calls, no product authority.

## Owner laws

- S42 adds detector contract + executor + envelope enforcement only. No runtime `/ask` hook,
  no live backend adapter, no Composer/Verifier, no ingress/TurnFrame/A9/patient_scope changes,
  no regex phrase tables, no product routing authority.
- Detector output is exactly one of `none | medical_handoff | uncertain`. Low confidence,
  malformed backend output, backend failure, or ambiguity **never** become `none`.
- `none` is allowed only for a confident ordinary informational/commercial question.
- `medical_handoff` covers personal medical evaluation, treatment choice, personal eligibility,
  current symptoms/complications, and other medical-boundary cases per classifier policy.
- `uncertain` means insufficient confidence or unsafe classification; it must not authorize an
  ordinary commercial answer path.
- Envelope enforcement (fail-closed):
  - confident `none` → `TargetTurnFramePolicyEnvelope.boundary_decision="none"`;
  - `medical_handoff` → `boundary_decision="medical_handoff"`;
  - `uncertain` → **terminal defer enforcement** (`terminal_mode="defer"`,
    `reason_code="boundary_uncertain"`), not `boundary_decision="none"` and not silent
    downgrade to commercial answer.
- Telemetry uses canonical `reason_code` only; never store raw user medical text in detector
  result or enforcement artifacts.
- Recording test backends prove contract/call order only, not recognition quality. Detector
  quality is **not proven** until a separately governed live eval with owner permission.
- Stage order on executor path is strict `classify → validate → normalize`; no
  catch/rename/retry/fallback that turns failure into `none`.

## Contract

Add `contracts/target_medical_boundary.py` with frozen models:

```python
TargetMedicalBoundaryDecision = Literal["none", "medical_handoff", "uncertain"]

TargetMedicalBoundaryBackendLabel = Literal["none", "medical_handoff"]

class TargetMedicalBoundaryResult(BaseModel):
    decision: TargetMedicalBoundaryDecision
    confidence: float  # 0..1
    reason_code: CanonicalToken
    source: Literal["backend", "fail_closed"]

class TargetMedicalBoundaryTerminalEnforcement(BaseModel):
    kind: Literal["terminal"] = "terminal"
    terminal_mode: Literal["defer"] = "defer"
    reason_code: CanonicalToken = "boundary_uncertain"

class TargetMedicalBoundaryEnvelopeEnforcement(BaseModel):
    kind: Literal["envelope"] = "envelope"
    envelope: TargetTurnFramePolicyEnvelope
```

Add `core/target_medical_boundary.py`:

```python
@dataclass(frozen=True, slots=True)
class TargetMedicalBoundaryInvocation:
    user_message: str

class TargetMedicalBoundaryBackend(Protocol):
    def classify(self, invocation: TargetMedicalBoundaryInvocation, /) -> object: ...

class TargetMedicalBoundaryError(ValueError):
    """Typed fail-closed executor input/programmer failure only."""

def execute_target_medical_boundary_classification(
    user_message: str,
    *,
    backend: TargetMedicalBoundaryBackend,
    min_confidence_none: float = 0.0,
    min_confidence_medical_handoff: float = 0.0,
) -> TargetMedicalBoundaryResult: ...
```

**Backend return shape (validate step):** backend must return an object with exactly two
attributes accessible as mapping keys or attributes:

- `decision`: `str` in `{"none", "medical_handoff"}` only (backend never returns `uncertain`);
- `confidence`: numeric `0..1`.

Any other shape, extra labels, missing fields, non-numeric confidence, or confidence outside
`0..1` → normalize to `uncertain` + `source="fail_closed"` +
`reason_code="boundary_uncertain_malformed_output"`. Backend exceptions → `uncertain` +
`reason_code="boundary_uncertain_backend_failure"`. Never raise for backend failures; never map
to `none`.

**Normalize step:**

- validated backend label `none` with `confidence >= min_confidence_none` → result `none`,
  `reason_code="boundary_none_confident"`, `source="backend"`;
- validated backend label `medical_handoff` with
  `confidence >= min_confidence_medical_handoff` → result `medical_handoff`,
  `reason_code="boundary_medical_handoff_confident"`, `source="backend"`;
- validated label below its floor → `uncertain`, `reason_code="boundary_uncertain_low_confidence"`,
  `source="fail_closed"`;
- if backend payload contains conflicting duplicate decisions when coerced to mapping →
  `uncertain`, `reason_code="boundary_uncertain_ambiguous"`, `source="fail_closed"`.

**`TargetMedicalBoundaryError` raise only for** invalid executor inputs before backend call
(empty/non-string `user_message`, non-numeric confidence floors outside `0..1`). Never raise
for backend/runtime classification outcomes.

Add `core/target_turn_frame_policy_envelope_enforcement.py`:

```python
class TargetMedicalBoundaryEnforcementError(ValueError): ...

def enforce_target_medical_boundary_on_envelope(
    boundary: TargetMedicalBoundaryResult,
    *,
    tone_key: CanonicalToken,
    allowed_topics: tuple[CanonicalToken, ...],
    forbidden_topics: tuple[CanonicalToken, ...] = (),
    required_fact_ids: tuple[CanonicalToken, ...] = (),
    allow_marketing_facts: bool = False,
    allow_consultation_close: bool = False,
    allow_cta: bool = False,
    min_topic_confidence: float = 0.0,
    min_service_confidence: float = 0.0,
    min_intent_confidence: float = 0.0,
) -> TargetMedicalBoundaryEnvelopeEnforcement | TargetMedicalBoundaryTerminalEnforcement: ...
```

Canonical reason codes (allowlist):

- `boundary_none_confident`
- `boundary_medical_handoff_confident`
- `boundary_uncertain` (aggregate terminal enforcement only)
- `boundary_uncertain_low_confidence`
- `boundary_uncertain_malformed_output`
- `boundary_uncertain_backend_failure`
- `boundary_uncertain_ambiguous`

Detector `TargetMedicalBoundaryResult` uses granular codes only. Terminal enforcement for any
`uncertain` result always uses aggregate `reason_code="boundary_uncertain"`.

## Boundaries / allowlist

No runtime wiring, live/LLM/provider SDK calls, ingress contract edits, TurnFrame/A9 edits,
patient_scope reads, frozen artifact changes, client data edits, S27–S41 code changes except
docs, or full suite.

- `TASK.md`
- `contracts/target_medical_boundary.py`
- `core/target_medical_boundary.py`
- `core/target_turn_frame_policy_envelope_enforcement.py`
- `tests/test_target_medical_boundary.py`
- `tests/test_target_turn_frame_policy_envelope_enforcement.py`
- `docs/ARCH_TARGET_DESIGN.md`
- `docs/STRANGLER_ROADMAP.md`

## Minimal protected acceptance

- backend returns confident `none` → result `none` with `boundary_none_confident`;
- backend returns confident `medical_handoff` → result `medical_handoff` with
  `boundary_medical_handoff_confident`;
- low confidence on either label → `uncertain`, never `none`;
- malformed backend payload / backend exception → `uncertain` with typed reason, never `none`;
- ambiguous/conflicting backend labels → `uncertain`;
- enforcement: confident `none` → envelope `boundary_decision="none"`;
- enforcement: `medical_handoff` → envelope `boundary_decision="medical_handoff"`;
- enforcement: `uncertain` → terminal defer enforcement, not envelope with `none`;
- telemetry carries only canonical reason codes;
- import firewall: no legacy/runtime/live/patient_scope/ingress/TurnFrame reads.

Run only S42 tests plus S41 dispatch neighbor:

- `tests/test_target_medical_boundary.py`
- `tests/test_target_turn_frame_policy_envelope_enforcement.py`
- `tests/test_target_turn_frame_dispatch.py`

## Gates

1. Independent governance checker before code.
2. Commit/push `docs: govern provider-neutral target medical boundary detector S42` only to stage-a.
3. Implement only the allowlist and run minimal offline tests.
4. Independent completion checker, then roadmap `[x]`.
5. Commit/push `feat: add provider-neutral target medical boundary detector S42`; final clean/synced.

## Docs draft (roadmap / ARCH)

- S42 adds offline provider-neutral medical boundary detector with three-way semantics
  (`none | medical_handoff | uncertain`), envelope enforcement, and explicit note that
  recognition quality is unproven until separately permitted live eval.
