# MASS_COMPOSER_TEMPLATE_AND_DOCTORS_DISPATCH — seam audit

**Дата:** 2026-07-27  
**Baseline:** `codex/stage-a` @ `f556130` (`DEMO_BONE_GRAFT_PACK_CONSISTENCY` closed)  
**Режим:** governance / docs / tests only · **NO product code / NO LIVE / NO LLM**  
**Owner GO:** Phase 1 governance only; implementation blocked until PRE-CODE ✅ + separate owner GO

## Preflight

| Check | Result |
|---|---|
| Branch | `codex/stage-a` ✅ |
| `HEAD` == `origin/codex/stage-a` @ `f556130` | ✅ |
| Working tree clean at governance start | ✅ |
| Defect A offline repro (`build_composer_sdk_messages`) | ✅ `KeyError: '"answer"'` |
| Defect B offline repro (`dispatch_target_turn_frame_response`) | ✅ `dispatch_field_invalid: aspects` |
| Live log corroboration (`logs/demo-app.jsonl`) | ✅ see §Evidence |

## Confirmed defects

### A. Mass Composer template `.format()` collision

**Introduced:** `84b2741` (`FULLCONTEXT_DIALOGUE_PRESENTATION_CONVERGENCE` gaps H–N)  
**File:** `core/target_runtime_llm_messages.py`  
**Mechanism:** `_COMPOSER_USER_TEMPLATE` contains literal JSON contract:

```text
{"answer":"<text>","source_identity":{"primary_content_ref":"<md or null>","used_content_refs":["<md filenames>"]}}
```

Template is rendered via `.format(cached_full_context=..., ...)`. Unescaped `{` / `}` in the JSON
example are interpreted as format placeholders → `KeyError: '"answer"'` before any provider call.

**Offline repro (HEAD @ `f556130`):**

```python
from core.target_composer_executor import TargetComposerInvocation
from core.target_runtime_llm_messages import build_composer_sdk_messages
build_composer_sdk_messages(TargetComposerInvocation(...))  # KeyError: '"answer"'
```

**Live evidence (`logs/demo-app.jsonl`):**

| ts | event | detail |
|---|---|---|
| `2026-07-27T12:56:20.258Z` | `llm_error` / `target_fullcontext_runtime_composer` | `error: '"answer"'` |
| `2026-07-27T12:56:20.267Z` | `bot_reply_completed` | `route: target_fullcontext_error` |
| user turn | `что такое костная пластика?` | `service_id: bone_graft`, planner OK, boundary OK, **no composer usage event** |

Earlier successful composer calls in the same log (e.g. `09:15–09:18`) predate deployment of the
broken user-template JSON line; post-`84b2741` materialization path is uniformly broken.

**Affected surface (all materialized FullContext answers using live composer backend):**

| Route class | Examples |
|---|---|
| Generic FAQ / service content | bone_graft, all-on-4 overview |
| Contacts (`clinic_contact` PRIMARY_EVIDENCE) | address, parking, hours |
| Price materialization | explicit service price, scope price |
| Doctors content component | when dispatch succeeds |
| Medical_handoff materialized content | governed corpus answers |

**Path TurnFrame → Composer provider (defect blocks at message build):**

```text
Turn Planner → TurnFrame
  → dispatch_target_turn_frame_response (if B not hit)
  → build_target_response_spec / policy envelope
  → execute_target_composer (TargetComposerInvocation)
  → TargetRuntimeLiveComposerBackend.generate
  → build_composer_sdk_messages  ← KeyError here
  → chat_completions_create  ← never reached
  → parse_composer_backend_output → Verifier → presentation
```

On failure: `TargetRuntimeBackendTransportError` → `target_fullcontext_error` fallback phone
(`core/target_runtime_widget.py`).

**Why prior focused/wide checks missed it:**

| Gap | Reason |
|---|---|
| `test_fullcontext_response_eval_harness.py::test_live_backend_invocation_payloads_are_json_serializable` | imports `build_composer_sdk_messages` from **`evals/v5/fullcontext_response_eval_live_backend.py`** — eval copy has **no** JSON literal in user template |
| Most Composer unit tests | `RecordingBackend` returns JSON directly; never calls `build_composer_sdk_messages` |
| `test_target_composer_action_context.py` | **does** call product `build_composer_sdk_messages` — **currently RED** but **not** in wide safe-offline command |
| Wide safe-offline @ `f556130` | 263/263 — does not include `test_target_composer_action_context.py` |
| LIVE eval harness | separate eval template; product path untested end-to-end offline |

**Note:** `_VERIFIER_USER_TEMPLATE` already uses `{{` / `}}` escaping correctly (lines 29–31).
Composer user template does not.

### B. Clinic-wide doctors dispatch order

**File:** `core/target_turn_frame_dispatch.py`  
**Mechanism:** `_components_from_turn_frame` calls `_reject_invalid(field_meta.aspects)` **before**
the existing `topic == "doctors"` → `selected.add("doctors")` rule (lines 128–143).

For clinic-wide query «Кто ваши врачи?» Planner returns:

- `topic=doctors` (valid, confident)
- `aspects=[]` → `field_meta.aspects.status=invalid`, `error=aspects_empty` (`turn_frame_from_raw.py`)

Dispatch raises `TargetTurnFrameDispatchError(dispatch_field_invalid, "aspects")` before doctors
component is selected. Composer is never invoked.

**Offline repro (HEAD @ `f556130`):**

```text
frame: route=content, topic=doctors, topic_confidence=0.95, aspects=[]
→ dispatch_field_invalid: aspects
```

**Live evidence (`logs/demo-app.jsonl`):**

| ts | planner | runtime |
|---|---|---|
| `2026-07-27T12:56:55.946Z` | `topic=doctors`, `aspects=[]` | — |
| `2026-07-27T12:56:57.318Z` | boundary LLM usage only | **no** `target_fullcontext_runtime_composer` |
| `2026-07-27T12:56:57.342Z` | — | `route: target_fullcontext_error`, user: `кто ваши врачи?` |

**Existing partial coverage:** `test_doctors_topic_with_overview_requests_doctors_only` covers
`aspects=["overview"]` but **not** `aspects=[]`. `test_topic_shadow_attempt_eval_contract.py`
treats partial doctors+empty aspects as scoreable shadow — dispatch semantics not aligned.

## Proposed fix (implementation — blocked)

### A. Composer template (minimal, reliable)

**Preferred:** escape literal braces in `_COMPOSER_USER_TEMPLATE` JSON example (`{{` / `}}`),
matching verifier template pattern.

**Alternative:** static `_COMPOSER_OUTPUT_CONTRACT_EXAMPLE` constant concatenated outside `.format()`.

**Forbidden:**

- global `str.replace` on rendered prompt
- try/except around `KeyError`
- second Composer pipeline / retry / bypass
- changing `answer + source_identity` contract

### B. Doctors dispatch (typed topic semantics)

**Preferred:** in `_components_from_turn_frame`, allow governed clinic-wide doctors when:

- `topic == "doctors"` is usable (valid + confident + allowed), **and**
- `aspects` meta is invalid **only** with `error == "aspects_empty"`

Then apply existing `selected.add("doctors")` without requiring invented `service_id` or aspects.

**Preserve fail-closed:**

- `aspects=[]` for non-doctors topics → still `dispatch_field_invalid`
- invalid aspects with other errors → still fail-closed
- `topic=doctors` + `aspects=["overview"]` → existing doctors-only behavior unchanged
- service-scoped doctors continuity (overview skip + doctors component) unchanged

## Forbidden solutions

1. Per-route patches (contacts only, bone_graft only, FAQ only)
2. Fallback/retry/second pipeline around Composer
3. Catching or swallowing `KeyError`
4. Regex / phrase lists for doctors routing
5. Verifier / AC1–AC3 / A9 / presentation limit changes
6. Composer JSON contract change
7. LIVE / LLM for governance or implementation tests

## Acceptance matrix (implementation)

| # | Criterion |
|---|-----------|
| 1 | `build_composer_sdk_messages()` does not raise |
| 2 | Rendered user message contains exact JSON output contract text |
| 3 | All `.format` placeholders substituted |
| 4 | Input values containing `{` / `}` not corrupted |
| 5 | Contacts offline runtime → materialized (not `target_fullcontext_error`) |
| 6 | bone_graft FAQ offline → materialized |
| 7 | Ordinary price answer offline → materialized |
| 8 | Generic FAQ offline → materialized |
| 9 | Each materialized case: Composer called exactly once |
| 10 | Each materialized case: Verifier called exactly once |
| 11 | No `target_fullcontext_error` in matrix cases |
| 12 | `topic=doctors` + `aspects=[]` → doctors materialization |
| 13 | Clinic-wide doctors query needs no invented `service_id` |
| 14 | Service-scoped doctors continuity preserved |
| 15 | `aspects=[]` for non-doctors remains fail-closed |
| 16 | Terminal / lead / booking guards unchanged |
| 17 | Composer `answer + source_identity` contract unchanged |
| 18 | Contacts use validated `clinic_contact` PRIMARY_EVIDENCE |
| 19 | Frozen artifacts byte-identical |
| 20 | NO LIVE / NO LLM |

## Regression test requirements (implementation)

Must exercise real chain:

`TargetComposerInvocation` → `build_composer_sdk_messages` → SDK messages

Not only `RecordingBackend` that skips message builder.

**Offline runtime matrix (minimum):**

| Case | Query / frame |
|---|---|
| Contacts | address + parking |
| bone_graft FAQ | «Что такое костная пластика?» |
| Clinic doctors | «Кто ваши врачи?» (`topic=doctors`, `aspects=[]`) |
| Price | ordinary explicit price lookup |
| Generic FAQ | corpus-grounded info question |

## Allowlist (governance commit only)

| File | Action |
|------|--------|
| `TASK.md` | UPDATE — this checkpoint |
| `docs/evidence/runtime/MASS_COMPOSER_TEMPLATE_AND_DOCTORS_DISPATCH_SEAM_AUDIT.md` | CREATE |
| `tests/test_mass_composer_template_and_doctors_dispatch_governance.py` | CREATE — PRE-CODE |

## Allowlist (implementation — blocked)

| File | Action |
|------|--------|
| `core/target_runtime_llm_messages.py` | UPDATE — safe JSON example in template |
| `core/target_turn_frame_dispatch.py` | UPDATE — doctors `aspects_empty` typed exception |
| `tests/test_mass_composer_template_and_doctors_dispatch_implementation.py` | CREATE — COMPLETION + message builder tests |
| `tests/test_target_turn_frame_dispatch.py` | UPDATE — clinic-wide doctors `aspects=[]` |
| `tests/test_target_runtime_llm_messages.py` | CREATE — direct `build_composer_sdk_messages` unit tests |
| `tests/test_target_composer_action_context.py` | no logic change; should go green via A fix |

Optional if matrix needs dedicated module:

- `tests/test_mass_composer_template_hotfix_runtime_offline.py`

**KEEP unchanged:** Verifier policy, AC1–AC3, A9, frozen pins, marketing, lead flow, presentation limits.

## STOP conditions

- Fix requires Composer contract change or Verifier tuning
- Fix requires per-service/route hardcode
- Fix requires LIVE/LLM to prove green
- File outside allowlist required
- Frozen artifact edit for green

## STOP

Phase 1 governance PRE-CODE PASS does **not** authorize implementation.
**STOP after governance commit + push** — await owner GO.
