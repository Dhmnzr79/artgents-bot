# TASK — S46 Boundary-enforced FullContext Verified Response

**Branch / baseline:** `codex/stage-a` / `ab2fc69 feat: S45 FullContext service-optional verified response`

**Read-only seam confirmation (pre-governance):**

- `enforce_target_medical_boundary_on_envelope(...)` вызывается **только** в
  `tests/test_target_turn_frame_policy_envelope_enforcement.py` (S42 unit), **не** в demo/S45
  chain.
- Demo/S45 (`test_demo_target_turn_frame_bound_response.py`,
  `test_target_fullcontext_content_response.py`) вызывают
  `run_target_offline_turn_frame_bound_response(...)` с **вручную собранным**
  `TargetTurnFramePolicyEnvelope` (`boundary_decision="none"|"medical_handoff"`), **минуя**
  S42 enforcement.
- Единого public entry `TurnFrame + TargetMedicalBoundaryResult → verified|terminal` **нет**.
- Дубликата orchestrator в codebase нет → S46 **не STOP**.

**Goal:** один thin straight-line offline orchestrator над существующими public APIs:

```
TurnFrame + TargetMedicalBoundaryResult + explicit policy inputs + prebuilt FullContext
→ enforce_target_medical_boundary_on_envelope (×1)
→ terminal uncertain | run_target_offline_turn_frame_bound_response (×1)
→ verified | terminal (existing unions)
```

**No live/LLM. No new inference/classifier/detector. No runtime/UI/session/authority. No A9.
No S43 changes. No change to S45 FullContext vs structured authority.**

## Required behavior

### Input

- готовый `TurnFrame`;
- готовый `TargetMedicalBoundaryResult` (detector **не** вызывается);
- explicit envelope policy kwargs (tone, topics, marketing permissions, confidence floors — as
  S42 enforcement API);
- все существующие S41/S45 assembly inputs (`bundle`, `doctor_catalog`, …,
  `cached_full_context`, backends);
- injected Composer + Verifier backends.

### Sequence (strict)

1. `enforce_target_medical_boundary_on_envelope(boundary, ...)` — **ровно один раз**.
2. If `TargetMedicalBoundaryTerminalEnforcement` (`uncertain`):
   - return as-is;
   - **не** вызывать S41, Composer, Verifier.
3. If `TargetMedicalBoundaryEnvelopeEnforcement`:
   - `run_target_offline_turn_frame_bound_response(turn_frame, result.envelope, ...)` —
     **ровно один раз**;
   - return existing `TargetTurnFrameBoundMaterializeResponse |
     TargetTurnFrameBoundTerminalResponse` без переписывания.

### Errors

- Typed errors S42/S41/S40/S39/S37/S38 propagate unchanged; no catch/retry/fallback/repair.
- Inconsistent boundary → existing `medical_boundary_result_inconsistent`.
- Invalid policy inputs → existing S42 typed errors.

### Semantics preserved

- `none` → ordinary answer path through S41/S45.
- confident `medical_handoff` → safety mode + full grounded FullContext response (incl.
  service_id=None pain path from S45).
- `uncertain` → S42 terminal defer only.
- urgent/manual-contact → upstream; **not** implemented in S46.

## Public API

**Name:** `run_target_offline_boundary_enforced_fullcontext_response(...)`

**Module:** `core/target_boundary_enforced_fullcontext_response.py`

**Return union (no new heavy result model):**

```python
TargetMedicalBoundaryTerminalEnforcement
| TargetTurnFrameBoundMaterializeResponse
| TargetTurnFrameBoundTerminalResponse
```

Straight-line function: no branches beyond enforce → early return | S41 passthrough.

## Deliverables

1. Thin orchestrator module (reuse S42 + S41 only; no duplicated S33–S45 logic).
2. Offline acceptance tests per criteria below + neighbor regression.
3. ARCH/ROADMAP S46 status only.

## Boundaries / allowlist

- `TASK.md`
- `core/target_boundary_enforced_fullcontext_response.py` (new)
- `tests/test_target_boundary_enforced_fullcontext_response.py` (new)
- `docs/ARCH_TARGET_DESIGN.md`
- `docs/STRANGLER_ROADMAP.md`

**Forbidden:** изменение `core/target_turn_frame_policy_envelope_enforcement.py`,
`core/target_turn_frame_bound_response.py`, S45 core, S42 detector, A9, S43 artifacts,
runtime/UI/session, live/LLM, new result contracts unless STOP escalation, RAG/routing,
fallback/retry/repair, Verifier/authority weakening.

## Minimal protected acceptance (offline, no live)

1. `boundary=none` + service-specific price: enforce×1, S41×1, Composer×1, Verifier×1 →
   verified structured price.
2. confident `medical_handoff` + `service_id=None` + pain: materialize, Composer×1,
   Verifier×1, grounded reassurance, not terminal.
3. confident `medical_handoff` + missing-base synthetic: controlled materialized response,
   consultation, not defer; external medical fact rejected.
4. `boundary=uncertain`: terminal defer; S41/Composer/Verifier not called.
5. inconsistent boundary: typed fail-closed; downstream not called.
6. topic/policy incompatibility: existing S41 typed error unchanged.
7. same prebuilt `TargetCachedFullContext` for Composer + Verifier; no builder/FS in S46.
8. Neighbor regression: targeted S42 enforcement, S41 dispatch/bound, S45 content response,
   necessary S40/S39 neighbors; no skip/xfail.

Run only listed targeted tests with external `--basetemp` and `-p no:cacheprovider`. **No full
pytest. No live.**

## Gates

1. Independent **PRE-CODE** checker on governance TASK.
2. Commit/push `docs: govern S46 boundary-enforced FullContext verified response` (**TASK.md
   only**).
3. Implement allowlist; run targeted offline tests.
4. Independent **COMPLETION** checker.
5. One completion commit; push; clean/synced.

## Explicitly out of scope

- Medical boundary detector / live classifier
- message→TurnFrame planner (A9)
- Runtime wiring / UI / session / product authority
- Changes to FullContext vs structured authority (S45)
- Provider prompt caching / legacy bridge
