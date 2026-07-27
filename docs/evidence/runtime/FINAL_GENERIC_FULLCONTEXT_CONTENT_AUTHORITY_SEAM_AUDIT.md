# FINAL_GENERIC_FULLCONTEXT_CONTENT_AUTHORITY — seam audit

**Дата:** 2026-07-27  
**Baseline:** `codex/stage-a` @ `525474c`  
**Режим:** governance / docs / tests only · **NO product code / NO LIVE / NO LLM**  
**Owner GO:** Phase 1 governance only; implementation blocked until PRE-CODE ✅ + separate owner GO

## Preflight

| Check | Result |
|---|---|
| Branch | `codex/stage-a` ✅ |
| `HEAD` == `origin/codex/stage-a` @ `525474c` | ✅ |
| Working tree clean at governance start | ✅ |
| Prior milestone landed | `FINAL_LIGHTWEIGHT_RESPONSE_GATES_CONVERGENCE` implementation @ `525474c` |
| Semantic Verifier boundary | **KEEP** — no change without reproducible defect |

## Executive summary

Planner metadata still **gates** whether Composer receives cached FullContext for ordinary FAQ/info turns.
`FINAL_LIGHTWEIGHT_RESPONSE_GATES_CONVERGENCE` fixed scenario-only `aspects=[]` when `topic` + `marketing_scenarios`
are valid, but **did not** introduce a planner-independent generic content authority.

| ID | User turn | Base fact | Planner | Pipeline stop | Composer |
|---|---|---|---|---|---|
| **A** | «А за сколько приёмов можно поставить новый зуб?» | `implantation__service__benefits.md` — «Новый зуб за 2 приёма» | `intent=content`, `topic=implantation`, `aspects=["duration","stages"]`, `needs_clarification=true` | `target_fullcontext_terminal_clarify` | **0** |
| **B** | «А вы используете одноразовые материалы в работе?» | `implantation__faq__safety.md` — «Только одноразовые материалы…» | `intent=unknown`, `topic=null`, `aspects=[]`, `needs_clarification=false` | `dispatch_field_invalid: aspects` | **0** |

**Architectural target:** introduce **`generic_fullcontext_content`** — not a new pipeline, not legacy fallback.
Reuse cached FullContext, existing content-only bound package (`service_id=None`), Composer, source identity sidecar,
deterministic + Semantic Verifiers, presentation/widget/session. Planner helps structured routes; it must **not**
decide whether the bot may search FullContext for a normal informational answer.

---

## Normative pipeline order (binding)

Chronological product order after Phase 2 implementation:

1. Pre-resolver guards  
2. Ingress  
3. Typed UI frame **or** Planner  
4. Structured deterministic capabilities (contacts, governed UI, structured price, doctors, other proven structured routes)  
5. Medical Boundary  
6. On `medical_handoff` — handoff path **before** generic  
7. Concrete service content when `service_id` usable  
8. **`generic_fullcontext_content`** when no structured capability selected  
9. Composer  
10. Deterministic Verifier  
11. Semantic Verifier  
12. Presentation / widget / session  

Structured contacts keep the fast path: **0** Boundary / Composer / Semantic (landed @ `525474c`).

Medical Boundary **must** run before generic. Generic is **not** a price route (`allow_price=false` normatively;
price intent → structured pricebook or price data-gap).

---

## Planner authority split (binding)

| Capability class | Planner fields | Authority |
|---|---|---|
| Structured: price, concrete service lookup, doctors, contacts, typed UI action, AC1–AC3 scope/stage, Leadflow | intent, topic, aspects, service_id, scope axes, needs_clarification where structurally required | **authority** — missing required param → structured clarify/data-gap |
| Ordinary FAQ / info / comparison grounded in MD | topic, aspects, service_id, primary_aspect, needs_clarification | **advisory** — may be absent/partial; must not terminal-block generic |

**Do not** auto-route into generic: completely malformed Planner output, provider failure, unknown non-null
`service_id`. Classify separately in seam audit / controlled technical behavior.

---

## Clarification policy (binding)

Terminal clarify **only** when a missing parameter blocks a **structured** action:

- choose price / price scope-stage;
- open governed menu;
- execute concrete comparison requiring scope;
- continue Leadflow;
- pick service for structured lookup.

For ordinary FAQ/info:

- `needs_clarification=true` → **advisory** (warning), not terminal;
- dispatch must **not** return `target_fullcontext_terminal_clarify` solely for advisory clarify;
- Composer receives FullContext;
- conditional answer allowed («Если речь об имплантации…»);
- at most one substantive follow-up question **after** useful grounded content if still ambiguous.

No generic stub «уточните услугу или ситуацию» when FullContext contains a matching fact.

---

## Data-gap vs technical fallback (binding)

When FullContext does not support a fact:

- answer: «В материалах клиники эта информация не указана»;
- route: content **data-gap**, not medical handoff, not phone technical stub.

Do **not** assert absence solely because Composer omitted source identity — source validity is a separate check.

---

## Phase 1 seam audit checklist

### 1. Dispatch rejects missing/invalid topic/aspects unconditionally

**Files:** `core/target_turn_frame_dispatch.py` L416–418, L175–176, L442–446, L450–452.

| Location | Behavior @ `525474c` | Normative |
|---|---|---|
| `_reject_invalid(field_meta.intent)` | fails on `status=invalid` | KEEP for malformed intent |
| `_reject_invalid(field_meta.topic)` | fails on `status=invalid` | KEEP for malformed topic; **allow missing** for generic |
| `_reject_invalid(field_meta.aspects)` inside `_components_from_turn_frame` | fails unless doctors/scenario exception | **generic bypass** when structured route not selected |
| `needs_clarification=true` + valid meta | `_terminal_spec(clarify)` **before** components | **advisory** for FAQ; terminal only for structured |
| `components==()` | `_terminal_spec(defer)` | **generic** when user text + ingress normal |

**Defect B path:**

```text
Planner → aspects=[], topic=null (missing), no marketing_scenarios
  → _aspects_empty_exception() == false
  → _reject_invalid(aspects) → dispatch_field_invalid: 'aspects'
  → target_fullcontext_error
```

**Defect A path:**

```text
Planner → needs_clarification=true, valid needs_clarification meta
  → dispatch L442–446 → _terminal_spec(clarify)
  → target_fullcontext_terminal_clarify
  → Composer: 0 (even though aspects map to content components)
```

Offline repro (@ `525474c`):

```python
# A — terminal clarify blocks Composer
dispatch_target_turn_frame_response(
    frame(intent="content", topic="implantation", aspects=["duration","stages"],
          needs_clarification=True, field_meta.needs_clarification=valid),
    envelope(),
)
# → TargetTurnFrameTerminalDispatch(response_mode="clarify")

# B — aspects gate
dispatch_target_turn_frame_response(
    frame(intent="content", topic=None, aspects=[], needs_clarification=False),
    envelope(),
)
# → TargetTurnFrameDispatchError: dispatch_field_invalid: 'aspects'
```

### 2. `needs_clarification` → terminal

**File:** `core/target_turn_frame_dispatch.py` L442–446.

Only structured clarify should terminal-block. FAQ with `needs_clarification=true` must reach generic + Composer.

### 3. Existing content-only package with `service_id=None`

**File:** `core/target_fullcontext_content_package.py`.

- `is_fullcontext_content_only_spec`: `service_id is None`, `required_components=("content",)`, `allow_marketing_facts=False`, `allow_cta=False`.
- `assemble_target_fullcontext_content_bound_package` builds minimal bound package.
- `is_fullcontext_service_optional_spec` also covers doctors-only clinic-wide path.

**Gap:** dispatch only reaches this path when `_components_from_turn_frame` yields `content` **and**
`not _service_id_is_usable`. Empty/partial planner frames never arrive.

**Target:** `generic_fullcontext_content` materializes the **same** spec shape; distinguish via explicit
`response_capability` / audit tag, not a second selector.

### 4. Pass generic user message + FullContext without second selector

**Files:** `core/target_composer_request.py` L564–580; `core/target_composer_executor.py` L183–201, L388.

Content-only / service-optional specs already:

- pass `user_message` verbatim;
- pass **empty** `evidence_blocks` when `scope_records` empty;
- inject `cached_full_context.corpus_text` in Composer SDK messages (`_fullcontext_content_only_request`).

Generic must reuse this wiring — **no** retriever, **no** topic-scoped MD subset as primary evidence.

### 5. Spec forbids price/CTA/marketing when inapplicable

**Files:** `core/target_turn_frame_dispatch.py` `_materialize_fullcontext_content_policy_request` L260–281;
`contracts/target_response_spec.py`.

Content-only policy request sets `allow_marketing_facts=False`, `allow_cta=False`, `required_components=("content",)`.
Scoped price sets `response_stage` / `scope_price_topic`.

**Normative generic:** explicit `allow_price=false` (no money extraction from MD as public price);
any recognized price intent → structured price route **before** generic.

### 6. Composer reports no confirmation

Composer JSON `{ answer, source_identity }`. Missing-base honest wording is prompt-owned; verifier checks
grounding separately. Data-gap stage exists in scoped evidence (`response_stage == "data_gap"`).

### 7. Numeric Verifier

**File:** `core/target_response_verifier.py` L500–520, L709–720.

| Claim kind | Rule @ `525474c` | Generic impact |
|---|---|---|
| `money` | PRIMARY_EVIDENCE / offer blocks | **KEEP** — generic must not mint money |
| `percent` | strict evidence | **KEEP** |
| general integer (e.g. «2» for «2 приёма») | `_claim_in_corpus` against `validated_context.corpus_text` | **KEEP** — «2 приёма» whitelisted when in corpus |
| service-optional spec | skips some service-bound checks | generic uses same path |

**Do not weaken** Numeric Verifier. Unusual price phrasing missed by Planner must not produce invented sums via generic.

### 8. Source identity for small fact inside large MD

**Files:** `core/target_composer_executor.py` (JSON sidecar); `core/target_presentation_turn_projection.py` L77+.

Valid answer + valid source → source-driven UI. Valid answer + missing/invalid source → text retained, UI hidden + warning.
Invented refs dropped. Generic must not auto-expand `consultation_value` from neighboring service.

### 9. Medical Boundary before generic

**File:** `core/target_runtime_turn.py` L193–297.

Order today: structured contacts short-circuit → boundary → `run_target_offline_boundary_enforced_fullcontext_response`.
Generic insertion point: **after** boundary normalization, **before** service-bound dispatch-only content.

`medical_handoff` uses same FullContext composer path with safety mode — not generic FAQ.

### 10. Edge cases

| Case | @ `525474c` | Target |
|---|---|---|
| Partial planner frame (topic null, aspects empty, valid user text) | dispatch error or defer | **generic** |
| Completely malformed frame (invalid intent/topic/service_id) | `dispatch_field_invalid` | controlled technical — **no** generic |
| Planner provider failure | bridge NOT_AVAILABLE/DEGRADED | technical — **no** generic |
| Unknown non-null `service_id` | `dispatch_field_invalid` or service lookup fail | technical/data-gap — **no** generic |
| Forbidden/not-offered topic | ingress / `dispatch_topic_scope_incompatible` | ingress policy — **no** generic |

### 11. Marketing scenarios and amplifiers in generic

**Files:** `core/target_presentation_turn_projection.py`; `core/target_marketing_selector.py`.

Direct duration question → **not** a marketing scenario. Concern + generic content may attach authored amplifier
when `marketing_scenarios` valid — advisory, not dispatch gate. `allow_marketing_facts=False` on base generic spec;
amplifiers via presentation policy after Composer.

### 12. `/ask` and `/ask/stream` parity

**Files:** `core/target_runtime_turn.py`, HTTP handlers wiring `_orchestrate_ask_turn`.

Both routes must share `generic_fullcontext_content` decision — no stream-only regression.

### 13. Session focus must not narrow generic FAQ

**File:** `core/target_runtime_turn_frame_hydration.py`.

Hydration injects `service_id` only for vague price/payment/doctor follow-ups when focus fresh.
Fresh SID + implantation FAQ must not inherit `sinus_lift` focus. Generic path must ignore stale focus
unless explicit structured follow-up.

---

## Pipeline gate inventory (delta vs LIGHTWEIGHT)

| Gate | Producer → Consumer | @ `525474c` | Target |
|---|---|---|---|
| G7 Dispatch | `dispatch_target_turn_frame_response` | clarify terminal on advisory `needs_clarification`; aspects/topic gate FAQ | **generic_fullcontext_content** materialize |
| G7b Generic authority | runtime after boundary | **missing** | explicit capability; reuses content-only package |
| G8 Spec | `assemble_target_fullcontext_content_bound_package` | exists, unwired for partial frames | wire via generic dispatch |
| G10 Composer | `execute_target_composer` + cached FullContext | reachable only after dispatch materialize | FAQ turns must reach |
| G11 Numeric | `verify_target_composed_response` | strict | **KEEP** |
| G12 Semantic | semantic phase | unchanged policy | **KEEP** |

Typical generic happy path LLM count: ingress (0–1) + planner (0–1) + boundary (1) + composer (1) + semantic (1) = **3–5**.

---

## Forbidden solutions (Phase 1)

- NO second selector / pipeline / RAG / retriever  
- NO regex / phrase lists for price or FAQ routing  
- NO legacy fallback path  
- NO Semantic Verifier prompt/policy change  
- NO Numeric / Contact / clinic-fact weakening  
- NO frozen artifact changes  
- NO per-fact service_catalog entries for small MD facts  
- NO prompt-tuning loops in governance  

---

## Implementation seams (for Phase 2 allowlist)

| Seam | File(s) | Change |
|---|---|---|
| Generic dispatch decision | `core/target_turn_frame_dispatch.py` | advisory clarify; generic materialize when structured not selected |
| Runtime ordering | `core/target_runtime_turn.py` | invoke generic after boundary, before service-bound only path |
| Generic capability tag | `core/target_generic_fullcontext_content.py` (**NEW**) | explicit `generic_fullcontext_content` policy request builder |
| Content-only package | `core/target_fullcontext_content_package.py` | optional `response_capability` metadata; `allow_price` explicit |
| Composer wiring | `core/target_composer_request.py`, `core/target_composer_executor.py` | ensure generic uses cached FullContext only |
| Presentation | `core/target_presentation_turn_projection.py` | marketing amplifiers for generic concern turns |
| Session | `core/target_runtime_turn_frame_hydration.py` | do not narrow generic FAQ via stale service focus |
| Tests | `tests/test_final_generic_fullcontext_content_authority_implementation.py` (**NEW**), harness, dispatch unit updates | 30-scenario matrix |

**KEEP unchanged:** Semantic Verifier policy, Numeric Verifier strictness, structured contacts fast path,
AC1–AC3 price routes, frozen pins, presentation caps (choice≤4, secondary≤2, price≤2).

---

## Acceptance matrix pointer

30-scenario offline matrix defined in `TASK.md` § Acceptance matrix (implementation — 30 scenarios).
Widget-faithful via `_orchestrate_ask_turn`; fakes at provider boundary; **NO LIVE / NO LLM**.

---

## STOP

Phase 1 ends at governance commit + PRE-CODE PASS. No product implementation until separate owner GO.
