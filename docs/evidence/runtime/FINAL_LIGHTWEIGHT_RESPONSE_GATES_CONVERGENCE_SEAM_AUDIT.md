# FINAL_LIGHTWEIGHT_RESPONSE_GATES_CONVERGENCE — seam audit

**Дата:** 2026-07-27  
**Baseline:** `codex/stage-a` @ `529fd02`  
**Режим:** governance / docs / tests only · **NO product code / NO LIVE / NO LLM**  
**Owner GO:** Phase 1 governance only; implementation blocked until PRE-CODE ✅ + separate owner GO

## Preflight

| Check | Result |
|---|---|
| Branch | `codex/stage-a` ✅ |
| `HEAD` == `origin/codex/stage-a` @ `529fd02` | ✅ |
| Working tree clean at governance start | ✅ |
| Prior milestones landed | `FINAL_FULLCONTEXT_DIALOGUE_RUNTIME_CONVERGENCE` @ `225ee56`; `FINAL_CONTACT_VALUE_VERIFICATION_AND_MARKETING_SCENARIO_ACTIVATION` implementation @ HEAD |
| Semantic Verifier boundary | **KEEP** — no change without reproducible defect |

## Executive summary

Product path still applies **fail-closed technical stubs** for planner frames that are **semantically sufficient** for a grounded informational answer. The canonical live defect:

| User turn | Planner output | Pipeline stop | User route |
|---|---|---|---|
| «Вдруг имплант не приживётся?» | `topic=implantation`, `marketing_scenarios=["result_reliability"]`, `aspects=[]`, `needs_clarification=false` | `dispatch_field_invalid: aspects` | `target_fullcontext_error` (~8.27s) |

Composer and Semantic Verifier were **never called**. This is **not** among the five normative fail-closed reasons.

**Architectural target:** lighten the **whole response chain** — not Semantic Verifier in isolation. Verifier keeps its boundary: invented clinic facts, diagnosis/personal eligibility/treatment choice, dangerous/absurd medical fantasy; `minor_external_detail` stays non-blocking.

**Prior fixes (do not re-litigate):** template brace escape, clinic-wide doctors `aspects_empty`, marketing-after-final-spec, typed contact subaspects, scenario decouple from initial block, contact value-only verifier.

---

## Normative fail-closed policy (binding)

Fail-closed technical stub allowed **only** for:

1. **Invented/distorted clinic facts** — prices, numbers, services, doctors, contacts, promotions, guarantees, payment, other strict commercial facts.
2. **Diagnosis or personal medical conclusion/advice** — including eligibility and treatment choice.
3. **Dangerous, absurd, or base-contradicting medical claim.**
4. **Leadflow date/time agreement** — booking must not confirm specific date or time.
5. **True technical failure** — provider/backend down, Composer unparseable output, corrupted client pack, missing mandatory schema authority.

**Not** legitimate stub reasons:

- empty optional `aspects`;
- missing `primary_aspect` when turn meaning is already determined;
- partial Planner frame with sufficient valid fields;
- auxiliary classifier uncertainty;
- missing presentation metadata;
- missing optional marketing fact;
- correct `data_gap` / `no_public_price`;
- missing source identity on valid generic FAQ (text yes, source UI hidden).

---

## Pipeline gate inventory

Normative categories: **N1** clinic facts · **N2** diagnosis/eligibility · **N3** dangerous fantasy · **N4** booking date/time · **N5** technical failure · **—** not normative (must degrade, not stub).

| # | Gate | Producer → Consumer | Required fields | Blocks? | Route on block | Extra LLM | Fail mode | Normative | Degrade to |
|---|------|---------------------|-----------------|---------|----------------|-----------|-----------|-----------|------------|
| G0 | Client bootstrap | `load_target_runtime_client_context` → runtime | valid pack | Yes | `target_fullcontext_error` | No | closed | N5 | — |
| G1 | TurnFrame bridge | `load_runtime_turn_frame` → runtime | `TurnFrame` NOT_AVAILABLE/DEGRADED | Yes | `target_runtime_turn_frame_*` | No | closed | N5 | — |
| G2 | Ingress (pre-target) | `ingress_gate` → `pre_resolver_turn` | route, confidence | Yes | `ingress_*`, `booking_flow`, `rate_limited` | 0–1 | closed | urgent/manual-contact | policy text |
| G3 | Planner / typed UI | `turn_planner_llm` / `target_typed_ui_turn_frame` → bridge | intent, topic, aspects meta, scenarios | Indirect | via G1 | 1 (skip on typed UI) | closed | — | partial frame OK |
| G4 | Session hydrate | `hydrate_target_runtime_turn_frame_from_session` | service_id continuity | No | — | No | — | — | — |
| G5 | A9 EffectiveScope | `resolve_effective_scope` → dispatch/AC2/AC3 | extent, stage, jaw axes | No | — | No | unknown→broad | — | broad_family_price |
| G6 | Medical boundary (pre-Composer) | `execute_target_medical_boundary_classification` → envelope | decision, confidence | Yes | `target_fullcontext_boundary_uncertain` | 1 | closed | safety mode | defer (see §B) |
| G7 | Dispatch | `dispatch_target_turn_frame_response` → bound response | valid field_meta per rules | **Yes** | `dispatch_*` → `target_fullcontext_error` | No | **closed** | **—** | materialize/clarify/data_gap |
| G8 | Spec/package | `assemble_target_spec_offline_response_package` | permissions vs components | Yes | `spec_package_*` → error | No | closed | N5 / misclass | data_gap where expected |
| G9 | Evidence / scoped price | AC2/AC3 + `target_scoped_response_evidence` | service applicability | Yes | empty evidence → error | No | closed | — | data_gap / no_public_price |
| G10 | Composer | `execute_target_composer` | parseable JSON answer | Yes | transport/parse error | 1 | closed | N5 | technical fallback |
| G11 | Deterministic verifier | `verify_target_composed_response` (deterministic phase) | numeric/strict facts/contacts | Yes | `target_verifier_*` | No | closed | N1 | block + phone |
| G12 | Semantic verifier | same, semantic phase | evidence + corpus | Yes | `target_verifier_semantic_rejected` | 1 | closed | N2/N3 | block + phone; `minor_external_detail` OK |
| G13 | Presentation | `decide_target_presentation` → widget | caps, cadence, refs | No | drops slots | No | open text | — | hide source UI |
| G14 | Session / lead | `target_runtime_session`, `flow_handlers` | SID, lead state | Lead bypass | lead routes | varies | — | N4 | canonical phone only |

**Typical happy-path LLM count:** ingress (0–1) + planner (0–1) + boundary (1) + composer (1) + semantic (1) = **3–5 calls**, dominant latency pre-Composer.

---

## A. Planner / dispatch

### A.1 Confirmed defect — scenario-only concern + `aspects=[]`

**Files:** `core/turn_frame_from_raw.py` L345–366; `core/target_turn_frame_dispatch.py` L146–147, L384–420.

```text
Planner LLM → raw aspects=[]
  → field_meta.aspects.status=invalid, error=aspects_empty
  → dispatch _reject_invalid(aspects)  [exception: topic=doctors only]
  → TargetTurnFrameDispatchError(dispatch_field_invalid, "aspects")
  → target_runtime_turn.py except → target_fullcontext_error
  → Composer: 0 · Semantic Verifier: 0
```

**Offline repro (@ `529fd02`):**

```python
dispatch_target_turn_frame_response(
    frame(topic="implantation", aspects=[], marketing_scenarios=["result_reliability"]),
    envelope(),
)
# TargetTurnFrameDispatchError: dispatch_field_invalid: 'aspects'
```

`tests/test_target_turn_frame_dispatch.py::test_empty_aspects_for_non_doctors_topic_remains_fail_closed` **encodes current wrong behavior**.

Planner prompt (`turn_planner_llm.py`) classifies «боюсь, что имплант не приживётся» → `result_reliability` but may emit `aspects=[]` (`test_plan_turn_attempt_empty_aspects_keeps_topic_in_partial_frame`).

### A.2 Dispatch field matrix (HEAD)

| Case | Current @ `529fd02` | Normative target |
|---|---|---|
| `aspects=[]`, `topic=doctors` | materialize doctors | **KEEP** |
| `aspects=[]`, valid topic + `marketing_scenarios` | **dispatch_field_invalid** | **materialize content** + scenario amplifiers |
| `aspects=[]`, valid topic, no scenario, `intent=unknown` | dispatch_field_invalid | materialize if topic sufficient (overview default) |
| missing `primary_aspect`, single component | OK | **KEEP** |
| missing `primary_aspect`, content+price | `dispatch_followup_ambiguous` | clarify or primary from price aspect |
| partial frame, valid topic+scenario | blocked | materialize |
| scenario-only concern (reliability/time/cost) | blocked | materialize |
| clinic-wide doctors | materialize | **KEEP** |
| typed `contact_*` aspects | materialize content | **KEEP**; target lightweight path (§E) |
| broad price + `extent=unknown` | scope-price materialize | **KEEP** |
| generic FAQ, `service_id=None` | materialize content-only | **KEEP** |
| comparison aspect | content component | **KEEP** |
| valid typed UI action | planner skip | **KEEP** |
| malformed `topic` / `service_id` | fail-closed | **KEEP** (N5) |

### A.3 Proposed capability-based TurnFrame sufficiency (implementation)

**Sufficient for materialize (deterministic, no regex):**

1. **Aspect path:** `field_meta.aspects.status=valid` and non-empty → existing `_ASPECT_TO_COMPONENT`.
2. **Doctors clinic-wide:** `topic=doctors` usable + `aspects_empty` only → doctors component (existing).
3. **Scenario concern path:** usable `topic` + valid `marketing_scenarios` (1–2) + `needs_clarification=false` + not contact-only → default `content` component; scenarios attach post-dispatch via `resolve_bound_marketing_flags`.
4. **Price intent path:** usable price intent + usable topic → price component (existing).
5. **Service-bound path:** usable `service_id` → service materialize (existing).
6. **Contact structured path:** typed `contact_*` in aspects (or valid contact aspect meta) → content + contact evidence (existing); **future:** structured answer mode (§E).
7. **Scope-price UI path:** `effective_scope.source=ui_action` + known extent → scope price (existing).

**Remain fail-closed:**

- invalid/forbidden topic, invalid service_id, empty components after rules, conflicting content+price without primary, malformed marketing list, truly empty frame (no topic, no aspects, no scenarios, no price intent).

**Forbidden:** per-phrase exceptions; second pipeline; weakening Verifier.

---

## B. Medical boundary vs Semantic Verifier

### B.1 Roles

| Layer | When | Blocks | Materialize allowed |
|---|---|---|---|
| **Pre-Composer Medical Boundary** (`target_medical_boundary.py`) | Before dispatch envelope | `decision=uncertain` → terminal defer | `none` and confident `medical_handoff` → envelope continues |
| **Post-Composer Semantic Verifier** (`target_response_verifier.py`) | After deterministic gates | semantic blocking kinds | `minor_external_detail` non-blocking |

### B.2 Overlap / duplication

| Concern | Boundary | Semantic Verifier |
|---|---|---|
| Personal diagnosis / eligibility | routes `medical_handoff` mode | `personal_medical_conclusion` block |
| Invented clinic claims | not primary role | `unsupported_clinic_claim` |
| Dangerous medical fantasy | partial (classifier) | `material_external_medical_claim` |
| General educational MD content | **allowed** in handoff mode | allowed if grounded |

**Duplication is intentional safety layering** but **`uncertain` boundary → terminal defer without phone** (`materialize_boundary_uncertain_payload` — no `fallback_answer_with_phone`) is **over-fail-closed** vs normative policy when grounded educational answer is possible.

### B.3 Normative decision (Phase 1 — document only)

- **KEEP** both layers in Phase 1.
- **`uncertain` / low confidence / malformed boundary metadata** must not auto-stub if turn is otherwise sufficient for grounded content without diagnosis.
- Target: degrade to materialize in `medical_handoff` safety mode or honest clarify — **not** phone-less defer.
- **Semantic Verifier:** no changes without reproducible defect.

---

## C. Spec / package / evidence

### C.1 Error taxonomy

| Class | Example codes | User outcome |
|---|---|---|
| **Authoring/schema corruption** | pack loader errors, missing `marketing.yaml` | N5 technical error |
| **Expected missing data** | `no_public_price`, empty scoped offers | `data_gap` answer (not stub) |
| **Optional metadata mismatch** | missing amplifier, missing source ref | warning; answer materialized |
| **Permission mismatch (fixable)** | `spec_package_permission_forbidden` when optional marketing on content-only | **was fixed** @ `225ee56`; watch regressions |
| **True safety** | verifier semantic block | N2/N3 block + phone |

### C.2 Startup vs runtime

`scripts/validate_client_pack.py` catches: broken YAML, contact duplicate in MD, marketing rule shape, presentation fields. **Runtime-only gaps:** composer output grounding, session state, planner partial frames.

### C.3 PRIMARY_EVIDENCE vs MD corpus

Deterministic numeric gate uses evidence blocks **and** corpus whitelist. Risk: correct price in MD but absent from PRIMARY_EVIDENCE → `target_verifier_numeric_ungrounded`. Scope-price and explicit service paths must keep evidence assembly aligned (AC2/AC3).

---

## D. Deterministic Verifier (KEEP strict)

**Preserve:** numeric grounding, strict commercial facts, canonical contacts, required exact facts.

**Contact check (@ `529fd02`):** value-only via `canonical_contact_scalar` + normalized substring — per requested `clinic_contact` evidence blocks.

**Hardcode seam:**

```python
# core/target_response_verifier.py L744
canonical = canonical_contact_scalar(field, client_id="demo")
```

`canonical_contact_scalar` itself is client-aware (`load_clinic_contact_facts(client_id)`), but verifier **ignores** pipeline `client_id` param. **Implementation must pass runtime `client_id`** before new clinics.

**Semantic layer:** unchanged in Phase 1.

---

## E. Latency / LLM call map

| Scenario | Ingress | Planner | Boundary | Composer | Semantic | Notes |
|---|---:|---:|---:|---:|---:|---|
| Contact address | 0–1 | 1 | 1 | 1 | 1 | **Target:** structured mode — Ingress+Planner only |
| Clinic-wide doctors | 0–1 | 1 | 1 | 1 | 1 | dispatch OK @ HEAD |
| Direct structured price | 0–1 | 1 | 1 | 1 | 1 | scope UI may skip clarify |
| Generic FAQ | 0–1 | 1 | 1 | 1 | 1 | source UI fail-open |
| Marketing concern (`result_reliability`) | 0–1 | 1 | **0**¹ | **0**¹ | **0**¹ | ¹current: blocked at dispatch |
| Personal medical question | 0–1 | 1 | 1 | 0–1 | 0–1 | handoff/uncertain may skip Composer |
| Typed UI click | 0–1 | **0** | 1 | 1 | 1 | planner skip |
| Leadflow active | 0 | 0 | 0 | 0 | 0 | bypass target pipeline |

### E.1 Target: deterministic structured-answer mode (contacts)

**Capability-based, not contacts-only hack:**

1. Planner emits typed contact aspect(s).
2. Answer assembled from `clinic_policies.yaml` via `canonical_contact_scalar` / `materialize_clinic_contact_primary_evidence`.
3. **Skip** Medical Boundary, Composer, Semantic Verifier for this capability class.
4. Presentation: plain attribution, no marketing, no invented CTA.
5. Generalize pattern for other **exact external contract** domains (owner-approved list).

**Ingress optimization:** skip ingress LLM when typed UI / known structured capability — **without** weakening urgent/manual-contact hard-stop.

---

## F. Runtime fallback / routes

| Route | Text | Phone | Buttons/CTA |
|---|---|---|---|
| `target_fullcontext_materialized` | composed answer | if in answer | governed |
| `target_fullcontext_terminal_clarify` | clarify text | **no** | none |
| `target_fullcontext_terminal_defer` | consultation defer | **no** | none |
| `target_fullcontext_boundary_uncertain` | consultation defer | **no** | none — **gap** |
| `target_fullcontext_verifier_blocked` | verifier text | **yes** (`fallback_answer_with_phone`) | none |
| `target_fullcontext_error` | technical text | **yes** | none |
| `data_gap` / `no_public_price` | honest gap copy | optional | governed |

**Normative:** terminal/defer/handoff/error stub routes should include **canonical phone only** — no invented actions, buttons, or lead offer.

**Gap:** `materialize_boundary_uncertain_payload` and `materialize_s41_terminal_payload` omit phone — implementation should align with `fallback_answer_with_phone`.

---

## G. Presentation / Leadflow invariants (KEEP)

Implementation must not regress:

- choice menu ≤ 4; secondary ≤ 2; price-detail ≤ 2;
- video priority; no-repeat cadence (`shown_*_refs`);
- situation flow; CTA separate;
- source identity fail-open for generic text;
- Leadflow must not confirm date/time;
- session/SID/reset/freshness;
- `/ask` and `/ask/stream` parity.

---

## Regression matrix (implementation — 28 scenarios)

Offline via widget-faithful harness (`_orchestrate_ask_turn`); fakes at provider boundary only; **NO LIVE / NO LLM**.

| # | Scenario | Expected |
|---|----------|----------|
| 1 | `result_reliability` + `aspects=[]` | materialized + amplifier |
| 2 | `time` concern + partial frame | materialized |
| 3 | direct duration question | materialized; `marketing_scenarios=[]` |
| 4 | direct warranty question | materialized; no `result_reliability` |
| 5 | generic FAQ + missing source identity | text yes; source UI hidden |
| 6 | contacts: address | materialized; canonical address |
| 7 | contacts: parking | materialized |
| 8 | contacts: phone | materialized |
| 9 | contacts: hours | materialized |
| 10 | contacts: address+parking | both fields |
| 11 | clinic-wide doctors | materialized |
| 12 | broad implantation price | materialized / scope price |
| 13 | named-service price after old session scope | materialized or honest data_gap |
| 14 | malformed topic/service_id | fail-closed (N5) |
| 15 | Medical Boundary low confidence | grounded answer or clarify — not silent stub |
| 16 | Medical Boundary backend failure | technical fallback + phone |
| 17 | numeric distortion | verifier block (N1) |
| 18 | invented promotion | verifier block (N1) |
| 19 | diagnosis/personal eligibility | semantic block (N2) |
| 20 | dangerous fantasy | semantic block (N3) |
| 21 | harmless general detail | non-blocking `minor_external_detail` |
| 22 | typed UI click | planner skip |
| 23 | technical Composer failure | technical fallback + phone |
| 24 | expected missing price | data_gap / no_public_price |
| 25 | Leadflow date/time agreement | forbidden |
| 26 | buttons/video/situation/cadence | unchanged caps |
| 27 | `/ask` and `/ask/stream` parity | same route class |
| 28 | new client contacts | never `client_id="demo"` in verifier |

---

## Forbidden solutions

1. Per-phrase / per-query patches
2. Regex / phrase lists for routing
3. Second selector / pipeline / RAG
4. Legacy fallback restore
5. Semantic Verifier weakening or prompt tuning loops
6. Frozen artifact edits for green
7. LIVE / LLM in governance or implementation tests
8. Global allow-any-malformed-planner

---

## Allowlist (governance commit only)

| File | Action |
|------|--------|
| `TASK.md` | UPDATE — this checkpoint |
| `docs/evidence/runtime/FINAL_LIGHTWEIGHT_RESPONSE_GATES_CONVERGENCE_SEAM_AUDIT.md` | CREATE |
| `tests/test_final_lightweight_response_gates_convergence_governance.py` | CREATE — PRE-CODE |
| `docs/ARCHITECTURE_CONVERGENCE.md` | UPDATE — status pointer |
| `docs/FLAGS_AND_STATUS.md` | UPDATE — milestone status |
| `docs/STRANGLER_ROADMAP.md` | UPDATE — milestone pointer |
| `docs/ARCH_TARGET_DESIGN.md` | UPDATE — owner decision pointer |

## Allowlist (implementation — blocked)

| File | Action |
|------|--------|
| `core/target_turn_frame_dispatch.py` | UPDATE — TurnFrame sufficiency / scenario-only path |
| `core/turn_frame_from_raw.py` | UPDATE — optional: partial-frame warning vs fatal |
| `core/target_runtime_turn.py` | UPDATE — structured-answer short-circuit; boundary defer phone |
| `core/target_runtime_widget.py` | UPDATE — terminal/boundary phone alignment |
| `core/target_response_verifier.py` | UPDATE — `client_id` pass-through only |
| `core/target_structured_answer.py` | CREATE — deterministic structured-answer mode (contacts first) |
| `core/target_medical_boundary.py` | UPDATE — uncertain degrade policy (if owner-approved) |
| `tests/test_final_lightweight_response_gates_convergence_implementation.py` | CREATE — 28-scenario matrix |
| `tests/test_final_lightweight_response_gates_convergence_harness.py` | CREATE — shared widget harness |
| `tests/test_target_turn_frame_dispatch.py` | UPDATE — scenario-only sufficiency cases |

**KEEP unchanged:** Semantic Verifier policy (unless reproducible defect), numeric grounding, AC1–AC3, frozen pins, presentation limits.

---

## STOP

Phase 1 governance PRE-CODE PASS does **not** authorize implementation.
**STOP after governance commit + push** — await owner GO.
