# FINAL_FULLCONTEXT_DIALOGUE_RUNTIME_CONVERGENCE — seam audit

**Дата:** 2026-07-27  
**Baseline:** `codex/stage-a` @ `81cf09c8d4eb01f16402690f84923d98a37705a8`  
**Режим:** governance / docs / tests only · **NO product code / NO LIVE / NO LLM**  
**Owner GO:** Phase 1 governance only; implementation blocked until PRE-CODE ✅ + separate owner GO

## Preflight

| Check | Result |
|---|---|
| Branch | `codex/stage-a` ✅ |
| `HEAD` == `origin/codex/stage-a` @ `81cf09c8` | ✅ |
| Working tree clean at governance start | ✅ |
| `logs/demo-app.jsonl` read (1334 events, last write 2026-07-27 16:59) | ✅ |
| Prior `MASS_COMPOSER_TEMPLATE_AND_DOCTORS_DISPATCH` landed @ `029c38b` | ✅ (template + doctors dispatch) |
| Widget queries still failing post-fix | ✅ (seams A–D remain) |

## Executive summary

Lower-level offline tests and the `MASS_COMPOSER` matrix gave **false confidence** because they
bypass the real widget runtime seam where `include_initial_block` is computed, skip
`build_composer_sdk_messages` via `RecordingBackend`, and force `include_initial_block=False`.

At HEAD `81cf09c8`, live widget corroboration (`logs/demo-app.jsonl`) shows:

| Query | Route @ 13:30–13:36 | Root cause class |
|---|---|---|
| «А где вы находитесь?» | `target_fullcontext_error` | **Seam A** — marketing permission vs content-only spec |
| «А что такое костная пластика?» | `target_fullcontext_verifier_blocked` | **Seam C** — deterministic Verifier (no semantic LLM) |
| «Кто ваши врачи?» | `target_fullcontext_error` | **Seam A** — marketing permission vs doctors-only spec |
| «Сколько стоит имплантация?» (same session) | `target_fullcontext_materialized` | ✅ price path works |

Composer template `KeyError: '"answer"'` (**MASS_COMPOSER A**) and clinic-wide doctors dispatch
(**MASS_COMPOSER B**) are fixed; widget failures persist on other seams.

---

## Seam A — Marketing / provisional spec capability conflict

### Mechanism (producers → consumers)

```text
Turn Planner → TurnFrame
  → target_runtime_turn.run_target_fullcontext_runtime_turn
      provisional_spec_from_turn_frame(turn_frame)          # producer (approximate)
      should_include_initial_marketing_block(frame, provisional_spec)  # → True for contacts/content/doctors
      include_initial_block = boundary.none AND should_include…
      marketing_scenarios = marketing_scenarios_from_turn_frame if include_initial_block else ()
  → run_target_offline_boundary_enforced_fullcontext_response(..., include_initial_block, marketing_scenarios)
  → dispatch_target_turn_frame_response → final TargetResponseSpec
  → assemble_target_spec_offline_response_package(spec=final, include_initial_block=True, …)
      is_fullcontext_content_only_spec / is_fullcontext_doctors_only_spec
        → if include_initial_block OR marketing_scenarios → TargetSpecOfflineResponsePackageError
  → Exception handler: target_runtime_pipeline_failed:TargetSpecOfflineResponsePackageError
  → widget route: target_fullcontext_error
```

| Layer | File | Role |
|---|---|---|
| Producer (provisional) | `core/target_presentation_turn_projection.py` | `provisional_spec_from_turn_frame`, `should_include_initial_marketing_block` |
| Consumer (runtime) | `core/target_runtime_turn.py` L223–235, L262–269 | computes `include_initial_block` **before** dispatch |
| Gate (final) | `core/target_spec_offline_response_package.py` L95–111 | content-only / doctors-only forbid marketing |
| Error wrap | `core/target_runtime_turn.py` L286–294 | loses `exc.code` |

### Offline repro (@ `81cf09c8`)

```text
contacts TurnFrame: topic=clinic, aspects=['contacts']
  provisional required_components=('content',)
  include_initial_block=True
  → TargetSpecOfflineResponsePackageError(spec_package_permission_forbidden, 'marketing_facts')
  composer calls: 0

doctors TurnFrame: topic=doctors, aspects=[]
  provisional required_components=('doctors',)
  include_initial_block=True
  → TargetSpecOfflineResponsePackageError(spec_package_permission_forbidden, 'marketing_facts')
  composer calls: 0
```

Generic FAQ without `service_id` with `required_components=('content',)` hits the same gate when
`include_initial_block=True`.

### Live evidence

| ts | user | route | planner | composer event |
|---|---|---|---|---|
| `2026-07-27T13:30:57Z` | «А где вы находитесь?» | `target_fullcontext_error` | `topic=clinic`, `aspects=['contacts']` | **none** |
| `2026-07-27T13:36:14Z` | «Кто ваши врачи?» | `target_fullcontext_error` | `topic=doctors`, `aspects=[]` | **none** |

Earlier @ `12:56` same queries failed with `KeyError: '"answer"'` (fixed); post-`029c38b` failure
mode shifted to package permission.

### Status map

| Link | Status |
|---|---|
| provisional spec → `include_initial_block` | **Broken** — uses approximate spec |
| final bound spec marketing permissions | **Connected** — correct fail-closed |
| runtime ordering (marketing before final spec) | **Disconnected** — root cause |
| optional marketing must not break primary answer | **Violated** |

### Target architecture (no second pipeline)

1. Compute `include_initial_block` / `marketing_scenarios` **only after** final bound
   `TargetResponseSpec` is known (post-dispatch or post-`build_target_response_spec`).
2. Intersect runtime marketing flags with `spec.allow_marketing_facts` and content/doctors-only
   package rules.
3. Contacts, clinic-wide doctors, generic content-only paths materialize with
   `include_initial_block=False`, `marketing_scenarios=()`, `brand_term=None` — **without**
   losing CTA/marketing on price/service paths where final spec allows it.
4. Do **not** add per-route patches or a parallel marketing pipeline.

---

## Seam B — Structured contacts

### Canonical authority

`clients/{id}/clinic_policies.yaml` → `contact:` — phone, WhatsApp, address, hours, parking.
MD must not duplicate these facts (`docs/CLIENT_PACK_AUTHORING.md`, `scripts/validate_client_pack.py`
duplicate check on `clinic__info__contacts.md`).

### Current implementation

| Component | File | Behavior |
|---|---|---|
| Loader | `core/target_contact_authority.py` | `load_clinic_contact_facts`, `materialize_clinic_contact_primary_evidence` |
| Planner aspect | `core/turn_planner_llm.py` | single `contacts` aspect (no sub-aspects) |
| Projection | `core/target_presentation_turn_projection.py` | `contact_aspect_from_turn_frame` → `"contacts"` only |
| Evidence inject | `core/target_composer_request.py` | `_prepend_contact_evidence` on direct contact questions |
| Verifier | `core/target_response_verifier.py` L729–735 | requires **entire** `clinic_contact` block text in answer |

### Offline repro — coarse block (@ `81cf09c8`)

```python
materialize_clinic_contact_primary_evidence('demo', aspect='address')
# includes: phone + WhatsApp + address (NOT address-only)

materialize_clinic_contact_primary_evidence('demo', aspect='parking')
# includes: phone + WhatsApp + parking (NOT parking-only)
```

Verifier `target_verifier_clinic_contact_missing` fires if the full concatenated block is absent,
even when the patient asked only for address.

### Status map

| Capability | Status |
|---|---|
| Phone / address / hours / parking / WhatsApp in policies | **Connected** |
| Typed planner subaspect (no regex) | **Missing** |
| Per-field PRIMARY_EVIDENCE blocks | **Missing** |
| Composer receives only requested fields | **Missing** |
| Deterministic verify used fields only | **Missing** |
| Direct contact → PRIMARY_EVIDENCE `clinic_contact` | **Partial** (coarse block) |
| No marketing hooks on contact path | **Broken** (Seam A blocks before Composer) |

### Target architecture

- Planner emits typed contact subaspect in the **same** Turn Planner call:
  `phone` | `address` | `parking` | `hours` | `whatsapp` | `contacts` (general) | multi-field
  combinations (e.g. address+parking).
- `materialize_clinic_contact_primary_evidence` returns **separate** evidence blocks per field.
- Verifier checks only blocks present in evidence, not the full canonical dump.
- Fallback/handoff: canonical phone only (`fallback_answer_with_phone` — already partial).

---

## Seam C — `bone_graft` and light Verifier

### Live evidence (`logs/demo-app.jsonl`, request `59b3ddb7…`)

| Step | Event |
|---|---|
| Planner | `service_id=bone_graft`, content route |
| Boundary | `target_fullcontext_runtime_boundary` ✅ |
| Composer | `target_fullcontext_runtime_composer` ✅ |
| Semantic Verifier LLM | **absent** |
| Widget route | `target_fullcontext_verifier_blocked` |

Deterministic Verifier blocked the answer; semantic assessor never called.

### Offline (@ `81cf09c8`)

With `RecordingBackend` and grounded short answers, `bone_graft` overview **materializes** even with
`include_initial_block=True` and `marketing_scenarios=('pain_fear',)`. Live failure is therefore
**composer-output-specific** (ungrounded numeric, `target_verifier_strict_fact_missing` on optional
marketing `commercial_fact` with `must_preserve_exact`, or `target_verifier_numeric_ungrounded`).

Exact `exc.code` is **not** in runtime events for this turn — only aggregate route
`target_fullcontext_verifier_blocked` via `meta.target_error_code` when surfaced.

### Observability gap (proven)

| Exception | Logged `error_code` | Exact `exc.code` preserved? |
|---|---|---|
| `TargetResponseVerificationError` | `target_verifier_*` | ✅ in `meta.target_error_code` |
| `TargetSpecOfflineResponsePackageError` | `target_runtime_pipeline_failed:TargetSpecOfflineResponsePackageError` | ❌ |
| Other pipeline exceptions | `target_runtime_pipeline_failed:{TypeName}` | ❌ |

### Verifier policy (unchanged — normative)

| Must block | Must NOT block |
|---|---|
| Diagnosis / personal eligibility / treatment choice | Plausible general medical detail outside base |
| Ungrounded prices, doctors, contacts, promotions | Approved corpus informational numbers |
| Contradiction to base | Optional marketing evidence as mandatory verbatim paragraph |
| Invented dangerous claims | Whole useful answer for missing optional marketing fact |

### Target fix

1. Classify `commercial_fact` evidence: **required** (`required_fact_ids` / plan-bound) vs
   **optional supporting** — only required strict facts are verbatim-gated.
2. Expand approved numeric whitelist for informational corpus numbers (`bone_graft` MD, comparison
   docs).
3. Add structured runtime `bot_event` `target_pipeline_failure` with `{stage, code, value}` for
   package, assembly, composer transport, and verifier deterministic codes — **operational
   observability**, not admin/log-viewer.

---

## Seam D — Test contour (false confidence)

### Why prior matrix lied

| Gap | Evidence |
|---|---|
| Lower-level entry | `run_target_offline_turn_frame_bound_response` — not `_orchestrate_ask_turn` |
| Forced `include_initial_block=False` | `test_mass_composer_template_and_doctors_dispatch_implementation.py` `_pipeline_inputs` L155; `core/target_runtime_client_context.py` bootstrap default |
| Skips message builder | `RecordingBackend` returns JSON without `build_composer_sdk_messages` |
| Eval harness duplicate template | `evals/v5/fullcontext_response_eval_live_backend.py` — no JSON brace bug |
| No HTTP session | Missing `/ask`, `/ask/stream`, reset, SID isolation |
| Widget presentation | Presentation decision not exercised end-to-end |

### Target test architecture

```text
POST /ask | POST /ask/stream
  → app._orchestrate_ask_turn (real)
  → pre-resolver / ingress (fake LLM at network boundary only)
  → Turn Planner (fake JSON plan per scenario)
  → target_runtime_turn (real include_initial_block computation)
  → boundary (fake)
  → dispatch → final spec → package → evidence (real)
  → Composer: MessageBuildingBackend → build_composer_sdk_messages (real) → strict JSON envelope
  → parse_composer_backend_output (real)
  → deterministic + semantic Verifier (semantic fake)
  → presentation decision → widget payload (real)
  → session read/write (isolated test DB / tmp)
```

**Fakes allowed:** provider/network (planner, boundary, composer LLM, semantic LLM).  
**Forbidden:** substituting dispatch, spec binding, evidence, message builder, verifier policy,
presentation caps, or `include_initial_block` computation.

### Test coverage map (current)

| Area | Files | Widget-faithful? |
|---|---|---|
| Turn-frame bound pipeline | `test_mass_composer_template_and_doctors_dispatch_implementation.py` | ❌ |
| Presentation | `test_fullcontext_dialogue_presentation_convergence_implementation.py` | ❌ |
| HTTP offline | `test_ac3_scope_price_flow_http_offline.py`, `test_typed_ui_turn_frame_offline.py` | Partial |
| Widget E2E frozen live | `evals/v5/final_scope_widget_e2e_*.py` | Live / frozen — not offline runtime matrix |
| Composer messages | `test_target_runtime_llm_messages.py` | Unit only |
| Verifier | `test_target_response_verifier.py` | RecordingBackend |

---

## Seam E — Presentation invariants (KEEP — no change in Phase 1)

Binding owner decisions from `FULLCONTEXT_PRESENTATION_PARITY` + `FULLCONTEXT_DIALOGUE_PRESENTATION_CONVERGENCE`:

| Invariant | Limit |
|---|---|
| Choice menu | ≤4 typed choice buttons |
| Content secondary | ≤2 slots; priority video → follow-up → situation |
| Price-detail | ≤2 buttons |
| Navigation channels | one of choice OR secondary OR price per response |
| CTA | separate channel |
| Session cadence | no repeat refs/video/situation offer |
| Source identity | valid answer + bad source → text + warning, UI suppressed |
| `consultation_value` | exact service/option only; generic FAQ N/A |
| `bone_graft` | standalone demo service, `no_public_price` |
| `bone_graft` doctors | orlov + volkov |

---

## Seam F — Client-pack readiness

### Validator (`scripts/validate_client_pack.py`)

| Check | demo | `_template` |
|---|---|---|
| `contact.phone_display` required | ✅ | ✅ |
| MD contact duplication ban | ✅ | ✅ |
| `consultation_value` frontmatter | ❌ not validated | ❌ |
| `suggest_h3` | ❌ | ❌ |
| `situation_allowed` | ❌ | ❌ |
| `video_key` + catalog existence | ❌ | ❌ |
| Authored follow-up refs | ❌ | ❌ |
| Source identity refs | ❌ | ❌ |
| Marketing applicability per service | ❌ | ❌ |
| Typed presentation metadata | ❌ | ❌ |

Authoring doc (`docs/CLIENT_PACK_AUTHORING.md`) states contact non-duplication; presentation fields
documented in convergence audits but not enforced in validator.

### Residual config classification

| Artifact | Location | Active consumers | Phase 1 class |
|---|---|---|---|
| `consult_nudge` | `clients/demo/features.yaml`, `ui.yaml` | **0** — module deleted @ C2e (`core.consult_nudge` in import firewall) | **DELETE** (implementation) |
| `guide_router` | `clients/demo/features.yaml`, `clients/_template/features.yaml` | **0** product code references (config only, `enabled: false`) | **DELETE** (implementation) |

Do not remove in Phase 1 governance commit.

---

## Master seam table

| # | Seam | Producer | Consumer | Session | Status |
|---|---|---|---|---|---|
| A1 | provisional → `include_initial_block` | `target_presentation_turn_projection` | `target_runtime_turn` | — | **Broken** |
| A2 | final spec marketing gate | `target_spec_offline_response_package` | package assembly | — | **Connected** (too strict vs A1) |
| A3 | pipeline error code | exceptions | `target_runtime_turn` handler | meta | **Partial** |
| B1 | contact authority YAML | `target_contact_authority` | Composer evidence | — | **Partial** |
| B2 | contact subaspect | Turn Planner | evidence materializer | — | **Missing** |
| B3 | contact verifier | `target_response_verifier` | answer gate | — | **Broken** (whole-block) |
| C1 | numeric grounding | Verifier | bone_graft live | — | **Suspected** (live-only) |
| C2 | strict optional marketing | evidence + Verifier | bone_graft live | — | **Suspected** |
| C3 | failure observability | runtime | logs | — | **Missing** |
| D1 | widget-faithful tests | — | acceptance | — | **Missing** |
| E* | presentation caps | `target_presentation_decision` | widget | cadence | **Partial** (prior milestone) |
| F1 | pack validator gaps | `validate_client_pack` | authoring | — | **Partial** |

---

## What works (@ `81cf09c8`)

- Target FullContext product path wiring (S69): `/ask`, `/ask/stream` → `run_target_fullcontext_runtime_turn`
- `build_composer_sdk_messages` brace escape (post-`029c38b`)
- Clinic-wide doctors dispatch (post-`029c38b`) — blocked by Seam A before Composer in widget
- Scope-aware price materialization (live implant price @ 13:35:27)
- Cached FullContext, Composer JSON `answer + source_identity` contract
- Presentation decision layer (caps, cadence) — when materialization succeeds
- `validate_client_pack` contact phone + MD duplication checks

## What is broken (proven)

1. **Seam A** — contacts, clinic-wide doctors, generic content-only paths → `spec_package_permission_forbidden`
2. **Seam B** — coarse contact evidence + whole-block verifier (address-only cannot pass with minimal answer)
3. **Seam C observability** — package/assembly failures lose exact code in events
4. **Seam D** — no widget-faithful offline matrix; prior green runs are not representative

## What is not proven (honest)

- Exact deterministic Verifier `code` for live `bone_graft` turn (composer output not logged)
- Whether live `bone_graft` failure is numeric vs strict marketing vs other deterministic gate
- Full presentation channel-mutex regressions under widget path (not in scope of log sample)

## Why prior matrix gave false confidence

1. `include_initial_block=False` hardcoded in implementation matrix inputs
2. `RecordingBackend` skipped `build_composer_sdk_messages` (fixed for template, but pattern remains)
3. No `_orchestrate_ask_turn` — runtime marketing computation never executed in “runtime matrix”
4. `TargetSpecOfflineResponsePackageError` not asserted — generic `materialized` vs `error` only
5. Wide safe-offline green (263+) does not include widget-faithful convergence matrix

## Implementation allowlist sufficiency

Proposed allowlist in `TASK.md` is **sufficient** if implementation:

- fixes A before re-running matrix (marketing gate ordering)
- adds B subaspect + evidence split in existing planner/composer/verifier files
- adds C observability event + optional/required fact classification in verifier only
- adds D as new harness/tests — no changes to frozen live eval artifacts

**STOP** if fix requires per-question routes, regex lists, second pipeline, or frozen artifact edits.

---

## Forbidden solutions

1. Per-query patches (contacts-only, bone_graft-only)
2. Second Composer/Verifier pipeline or voting/retries
3. Regex / phrase lists for routing
4. Weakening exact commercial/numeric/contact gates
5. `include_initial_block=False` as global test hack
6. LIVE/LLM for governance or offline matrix
7. Admin log viewer
8. Frozen eval artifact edits

## NO PRODUCT CHANGE

Phase 1 deliverable only. Implementation blocked until PRE-CODE ✅ + owner GO.
