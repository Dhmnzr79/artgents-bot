# FINAL_SAFE_MEDICAL_BOUNDARY_BYPASS (PERF-2) — seam audit

**Дата:** 2026-07-28
**Baseline:** `codex/stage-a` @ `aa633f2`
**Режим:** governance / docs / tests only · **NO product implementation / NO Boundary prompt/policy change /
NO Composer/Verifier policy change / NO new LLM call / NO streaming text/text_delta / NO cache/prewarm /
NO Ingress+Planner merge / NO LIVE / NO LLM / NO E2E / NO frozen artifacts / NO TSC-C / NO TSC-D**
**Owner GO:** Phase 1 governance only; implementation blocked until PRE-CODE ✅ + separate owner GO

## Governance correction (this revision, @ `bba9e9b` → correction)

The initial revision of this audit defined `TargetMedicalBoundaryRequirement` with five members
(`required`, `bypass_governed_ui`, `bypass_pure_price`, `bypass_exact_faq`,
`not_applicable_structured`), even though only `bypass_governed_ui` was ever eligible and
`not_applicable_structured` was never reachable from the resolver's own call site. The owner correctly
flagged this as over-broad: a type should not offer values the current policy forbids returning, and a
resolver's signature should not model a state its own call site can never produce. This revision:

1. Narrows the `Literal` to exactly `{"required", "bypass_governed_ui"}`. `bypass_pure_price` and
   `bypass_exact_faq` remain fully documented in narrative (§4B/§4C) as deferred future capabilities, but
   are **no longer valid return values of the type** — today the resolver always returns `required` for
   those shapes, so the type should not claim otherwise.
2. Removes `not_applicable_structured` entirely, from both the type and the resolver's signature.
   `resolve_structured_answer_capability`'s `clinic_contact`/`service_availability` short-circuits
   (`core/target_runtime_turn.py:198-320`) both `return` **before** the point in the pipeline
   (`target_runtime_turn.py:322`) where this resolver would ever be called — the resolver's production
   call site never sees a structured-capability turn at all. Modeling a value for a state the function can
   never observe was an unreachable-state smell, not a safety feature; removing it also drops the
   `structured_capability` parameter from the resolver's signature, since it was only there to detect
   this now-removed state.
3. Tightens `bypass_governed_ui` eligibility from "governed click + deterministic frame" (true but
   loosely specified) to an exact, field-by-field checklist (§4A, revised) — XOR presence of exactly one
   governed action, exact required-field values, exact `field_meta.status="valid"`, exact
   `provenance == f"governed_ui_action:{action.ref}"` per required field, and `topic == action.topic` —
   with any mismatch, conflict, or both-actions-present case falling through to `required`. This removes
   any residual ambiguity about what "deterministic frame" means operationally.

No other section's underlying conclusion changed: `bypass_governed_ui` is still the one eligible
category, for the same structural reasons (§3, §6).

## Preflight

| Check | Result |
|---|---|
| Branch `codex/stage-a` | ✅ |
| `HEAD` == `origin/codex/stage-a` @ `aa633f2` | ✅ |
| Working tree clean at governance start | ✅ |

## Goal

Determine, from typed contract and capabilities alone (never raw text, regex, phrase lists, topic/service
hardcode, or "eyeball" confidence), exactly which `/ask`-family turns can **provably** skip Medical
Boundary's single blocking LLM call, and prepare (governance only, no code) a deterministic
`resolve_target_medical_boundary_requirement(...)` pure-function contract for a future Phase 2. The
finding of this audit is narrower than the milestone brief's aspiration: **exactly one category is
provably eligible today — governed UI scope/stage clicks.** Pure free-text price lookup and exact FAQ are
both explicitly kept `required` pending typed capability that does not exist yet (see §7 and §4C/D). This
is the honest, conservative outcome of the audit, not a shortfall — the brief itself instructs "если
недостаточно — зафиксировать FAQ как required, а не угадывать," and the same discipline applies to
free-text price.

## 1. Map: producer → requirement resolver → Boundary/runtime → PERF marks → Composer → Verifier

```text
app.py: /ask, /ask/stream
  └─ _orchestrate_ask_turn(data)                          [app.py:304-336]
       ├─ run_pre_resolver_turn(...)                       [orchestration/pre_resolver_turn.py]
       │    ├─ Ingress (classify_ingress)                   — may short-circuit (manual_contact, etc.)
       │    └─ ref-click resolution — ONLY IF `not q`        [pre_resolver_turn.py:248]
       │         resolve_ui_scope_ref_click / resolve_ui_stage_ref_click
       │         → request.ctx["current_ui_scope_action" | "current_ui_stage_action"]
       │         (fail-closed: ref must match a session-bound, server-rendered followup)
       ├─ try_run_typed_ui_planner_turn(...)                [orchestration/typed_ui_planner_turn.py]
       │    if a governed UI action is present in request.ctx:
       │      build_typed_ui_turn_frame_from_scope_action / _from_stage_action
       │        [core/target_typed_ui_turn_frame.py]         — 100% deterministic TurnFrame,
       │                                                       intent/aspects/needs_clarification
       │                                                       hardcoded, ref/topic-only inputs, `q`
       │                                                       never read by the builder
       │      publish_typed_ui_turn_frame(frame)
       │      stage_skipped("planner", reason="typed_ui")    — Planner LLM already skipped (existing)
       │    else:
       │      run_planner_turn(...) → plan_turn_attempt(q,...)  — ONE LLM call, TurnFrame is
       │                                                          LLM-classified, not deterministic
       └─ orchestrate_target_fullcontext_turn(...)          [orchestration/target_fullcontext_turn.py:32-79]
            └─ run_target_fullcontext_runtime_turn(...)     [core/target_runtime_turn.py:138-480]
                 ├─ load_runtime_turn_frame() / hydrate / resolve_effective_scope
                 │
                 ├─ resolve_structured_answer_capability(turn_frame)      [core/target_structured_answer.py]
                 │    if kind == "clinic_contact" or "service_availability":
                 │      stage_skipped("boundary"/"composer"/"verifier_deterministic"/"verifier_semantic",
                 │                    reason=f"structured_capability:{kind}")     [target_runtime_turn.py:198-265]
                 │      → materialize_structured_*_turn_response(...)   — deterministic, no LLM at all
                 │      → RETURN (never reaches Boundary call below, or the resolver call below)
                 │
                 │  ═══ THIS IS WHERE resolve_target_medical_boundary_requirement(...) WOULD BE
                 │      CALLED IN PHASE 2 — a pure function reading only the already-materialized
                 │      TurnFrame + governed UI action objects at this exact point (NOT
                 │      structured_capability — by this point control flow already guarantees it was
                 │      None, since both non-None branches returned above). Not built in Phase 1. ═══
                 │
                 ├─ stage_start("boundary")                              [target_runtime_turn.py:322]
                 │    execute_target_medical_boundary_classification(user_message, backend, ...)
                 │      [core/target_medical_boundary.py:186-223]         — ONE LLM call, raw q only
                 │    normalize_boundary_for_pipeline(boundary)           [target_medical_boundary.py:226-240]
                 │  stage_end("boundary", status="completed"|"exception")
                 │
                 ├─ run_target_offline_boundary_enforced_fullcontext_response(turn_frame, boundary, ...,
                 │      forbidden_topics=("diagnosis", "personal_eligibility"), ...)  [target_runtime_turn.py:373-409]
                 │    └─ enforce_target_medical_boundary_on_envelope(boundary, ...)
                 │         [core/target_turn_frame_policy_envelope_enforcement.py:55-103]
                 │         if boundary.decision == "uncertain" (backend failure only, see §2):
                 │           → terminal, defer                            — Composer/Verifier skipped
                 │         else:
                 │           → envelope carries boundary_decision, proceeds to Composer
                 │
                 ├─ stage_start("composer") → execute_target_composer(...)   [core/target_composer_executor.py:397-447]
                 │    ONE LLM call — receives full system policy + FULL cached_full_context corpus text +
                 │    response_directives (mode/tone/allowed+forbidden topics/response_stage/price
                 │    overlays) + primary_evidence + raw user_message. No "price-only" restricted
                 │    materialization mode exists today (see §7).
                 │  stage_end("composer", ...)
                 │
                 ├─ stage_start("verifier_deterministic") → numeric grounding (regex/Decimal, no LLM)
                 │    [core/target_response_verifier.py:710-761]
                 │  stage_end(...)
                 │
                 ├─ stage_start("verifier_semantic") → ONE LLM call, blocks on
                 │    unsupported_clinic_claim / personal_medical_conclusion / material_external_medical_claim
                 │    [core/target_response_verifier.py:763-789]            — UNCONDITIONAL, always runs
                 │    whenever Composer ran (never skipped independently of Composer)
                 │  stage_end(...)
                 │
                 └─ widget_payload_from_runtime_result(...) → session write-back
```

**Steady-state cost today (non-structured turn):** 3 sequential, blocking LLM calls — Boundary →
Composer → Semantic Verifier — always in that order, never parallelized (Boundary's `try/except` at
`target_runtime_turn.py:322-341` completes and returns before Composer is even invoked at line 373).

## 2. All current Boundary outcomes

| Backend result | Reason code | Pipeline-level normalization (`normalize_boundary_for_pipeline`) | Downstream effect |
|---|---|---|---|
| `none`, confidence ≥ 0.80 | `boundary_none_confident` | unchanged | Composer proceeds |
| `medical_handoff`, confidence ≥ 0.70 | `boundary_medical_handoff_confident` | unchanged | envelope carries `boundary_decision="medical_handoff"`; S41 envelope-bound response logic (out of this pipeline's scope, downstream of `enforce_target_medical_boundary_on_envelope`) decides clarify/defer/materialize |
| `none`, confidence < 0.80 | `boundary_uncertain_low_confidence` | **degraded to `none`, confident** | Composer proceeds as if confidently non-medical |
| `medical_handoff`, confidence < 0.70 | `boundary_uncertain_low_confidence` | **degraded to `none`, confident** | Composer proceeds as if confidently non-medical |
| malformed backend payload | `boundary_uncertain_malformed_output` | **degraded to `none`, confident** | Composer proceeds |
| ambiguous backend label (`both`/`unknown`/`uncertain`/`conflict*`) | `boundary_uncertain_ambiguous` | **degraded to `none`, confident** | Composer proceeds |
| backend exception (network/parse failure) | `boundary_uncertain_backend_failure` | **stays `uncertain`** — only survivor | `enforce_target_medical_boundary_on_envelope` returns `terminal`/`defer` — Composer/Verifier skipped, canned "please call the clinic" answer |
| structured `clinic_contact` capability | n/a — Boundary never called | n/a | `stage_skipped("boundary", reason="structured_capability:clinic_contact")` |
| structured `service_availability` capability | n/a — Boundary never called | n/a | `stage_skipped("boundary", reason="structured_capability:service_availability")` |

**Governance-relevant reading:** today, Boundary's own uncertainty (low confidence, malformed output,
ambiguous label) is *not* treated as a safety-relevant signal — it is silently downgraded to "confidently
non-medical" and pushed to Composer/Verifier to handle. The code comment at
`core/target_medical_boundary.py:229` states the philosophy directly: *"Degrade auxiliary uncertainty to
materialize path; semantic verifier remains gate."* Only a hard backend/transport failure halts the turn.
This existing design decision is itself evidence, from the product's own prior architecture choice, that
Semantic Verifier is already treated as a real safety backstop independent of Boundary confidence — which
is the same backstop PERF-2's bypass categories rely on (§6).

## 3. TurnFrame — the typed surface a resolver can read

Two independent producers exist:

- **Governed UI click** (`core/target_typed_ui_turn_frame.py:38-93`) — **100% deterministic.** Reads only
  `action.topic`/`action.ref` from a validated `UiScopeAction`/`UiStageAction`. Hardcodes
  `intent="price_lookup"`, `aspects=["price"]`, `primary_aspect="price"`, `needs_clarification=False`,
  `patient_scope=PatientScopeFrame()` (all-unknown, `status="defaulted"`). **Never reads `q` or any free
  text.** `field_meta` marks these fields `status="valid", confidence=1.0,
  provenance="governed_ui_action:<ref>"`.
- **Free-text turn** (`core/turn_frame_from_raw.py`, from the Planner LLM's JSON) — every field
  (`intent`, `aspects`, `patient_scope`, `needs_clarification`, `marketing_scenarios`) is an LLM
  classification of the raw message. **Critical gap (governance-blocking for any free-text bypass
  category):** the Planner's own prompt (`core/turn_planner_llm.py:78-84`) explicitly instructs the model
  **not** to set `needs_clarification=true` when the ambiguity is one "a doctor would determine (diagnosis,
  bone condition)" — i.e., `needs_clarification=False` is the *documented, intended* output for
  clinically-ambiguous messages, not a safety signal that ambiguity is absent. `patient_scope` defaults to
  all-`"unknown"` with `status="defaulted"` (not `"invalid"`) in exactly this case, so no `field_meta`
  status flags it either. **There is no field on `TurnFrame` anywhere that represents "this message may
  require clinical judgment."** This is the single fact that rules out any bypass category driven by
  free-text `TurnFrame` completeness/confidence, no matter how "complete" the frame looks.

**Governed-UI-click structural guarantee (the load-bearing fact for §4A):**
`orchestration/pre_resolver_turn.py:240-248` — the entire ref-resolution branch (which produces the
`UiScopeAction`/`UiStageAction` that becomes the deterministic TurnFrame) is gated `if ref: ... if not
q:`. **A governed click can only ever be resolved when the accompanying free text is empty.** If a
request carries both a `ref` and non-empty `q`, this branch is skipped entirely and the turn falls back
to ordinary free-text Planner handling — the governed, deterministic TurnFrame is never built. This means
a governed UI click cannot smuggle arbitrary medical free text alongside it; the code path that would need
to change for that to become possible is a change to this exact `if not q:` gate, which PERF-2
Phase 2 must not touch (added to the allowlist's KEEP list, §9).

Additional whitelist enforcement: `resolve_ui_scope_ref_click`/`resolve_ui_stage_ref_click`
(`core/target_ui_scope_action.py`, `core/target_ui_stage_action.py`) only accept a `ref` that exactly
matches an entry in `session_state.followups` — i.e., a ref the **server itself rendered and displayed**
earlier in this session. Any unparseable, malformed, or not-previously-shown ref returns
`kind="clarify"` and the action is discarded (`pre_resolver_turn.py:269-282`, `295-308`) — fail-closed.

## 4. Eligibility analysis per candidate (A–D from the milestone brief)

### A. Governed typed UI navigation — **ELIGIBLE for Phase 2 implementation**

**Structural reasons this category is safe** (unchanged from the original audit):

- `UiScopeAction`/`UiStageAction` validated against a session-bound, server-rendered-followup whitelist
  (fail-closed).
- TurnFrame construction is deterministic code, not an LLM guess (`core/target_typed_ui_turn_frame.py`).
- `intent="price_lookup"`, `aspects=["price"]`, `needs_clarification=False` are hardcoded constants of
  the builder, never inferred.
- Cannot coexist with free text (`if not q:` gate, §3) — structurally impossible to attach a medical
  question to a governed click.
- Planner LLM is *already* skipped for this path (existing `stage_skipped("planner", reason="typed_ui")`
  precedent) — Boundary-skip for the same click is the direct extension of an already-shipped,
  already-tested pattern, not a new kind of decision.
- Composer's `forbidden_topics=("diagnosis", "personal_eligibility")` (`target_runtime_turn.py:382`) is
  already passed unconditionally regardless of Boundary's decision — an existing content-level guard
  that remains in force whether or not Boundary ran.
- Deterministic + Semantic Verifier remain unconditional after Composer (§6) — the last-line defense
  is untouched.

**Exact eligibility checklist (governance correction — binding for the Phase 2 resolver):** the above
structural reasons only hold if `resolve_target_medical_boundary_requirement(...)` verifies **every**
one of the following, not just "a governed action is present." Any failure of any check below falls
through to `required` — there is no partial-credit bypass.

1. **Exactly one** governed action is present: `(current_ui_scope_action is not None) XOR
   (current_ui_stage_action is not None)`. Both present, or neither present, → `required`. (Neither
   present is already the common case for ordinary free text; both present is not a state the current
   pre-resolver can produce today, but the resolver must not assume that invariant — it must check.)
2. That action was already session-validated by the existing pre-resolver whitelist check
   (`resolve_ui_scope_ref_click`/`resolve_ui_stage_ref_click`, §3) — the resolver does not re-validate
   this itself; it trusts the action object's mere presence in `request.ctx`/the passed-in parameter as
   proof the existing fail-closed check already ran and passed. It performs no *additional* session
   lookup of its own (rule 4 below).
3. `turn_frame.intent == "price_lookup"` exactly.
4. `tuple(turn_frame.aspects) == ("price",)` — or the frame's canonical equivalent single-element
   price-only form; any additional aspect present, or a different aspect, → `required`.
5. `turn_frame.primary_aspect == "price"` exactly.
6. `turn_frame.needs_clarification is False` exactly.
7. `turn_frame.field_meta.intent.status == "valid"`, `turn_frame.field_meta.aspects.status == "valid"`,
   `turn_frame.field_meta.primary_aspect.status == "valid"`,
   `turn_frame.field_meta.needs_clarification.status == "valid"` — all four, not merely "not invalid."
8. Each of those same four `field_meta` entries' `provenance` string equals exactly
   `f"governed_ui_action:{action.ref}"` for the one action identified in step 1 — not merely
   "starts with `governed_ui_action:`," and not the topic's or any other field's provenance; the `ref`
   suffix must match the actual action's `ref` value.
9. `turn_frame.topic == action.topic` for that same action.
10. Any exception, missing attribute, type mismatch, or any single check above failing → `required`.
    `required` is the resolver's only fallback value; there is no secondary/degraded bypass tier.

This is a direct, checkable restatement of what `core/target_typed_ui_turn_frame.py`'s builder already
guarantees by construction (§3) — the checklist exists so the *resolver* verifies those guarantees
explicitly at its own call site, rather than assuming "if a governed action object exists in scope, the
frame must be the deterministic one," which would be true only as long as no other code path is ever
allowed to set those same fields a different way in the future.

### B. Pure commercial price lookup (free-text, non-click) — **NOT eligible yet; stays `required`**

The brief's own conditional applies here and is not satisfied: *"Pure price lookup можно bypass только
если Composer получает ограниченный price-materialization contract."* Today Composer's invocation
(`core/target_composer_executor.py:350-394`) **always** receives the full `TARGET_COMPOSER_SYSTEM_POLICY`
and the **entire** `cached_full_context.corpus_text` regardless of whether the resolved `TargetResponseSpec`
is price-only — there is a `price_only_offer_source_sufficiency` check
(`contracts/price_only_source_sufficiency.py`) that governs whether upstream evidence assembly may skip
requiring MD-content grounding, but it does not shrink what Composer itself is given. No restricted
price-materialization contract exists to build this category on. Additionally, per §3, a free-text
`price_lookup` intent is LLM-classified, not deterministic, and can coexist with medical/suitability
signals elsewhere in the same LLM-produced frame (no mutual-exclusivity constraint exists on `TurnFrame`
— confirmed: the only two field validators on `TurnFrame` are `primary_aspect ∈ aspects` and
marketing-scenario capping, `contracts/turn_frame.py:145-168`). **Decision: kept `required`, explicitly
deferred pending (a) a real Composer price-materialization contract and (b) a decision on how a
planner-classified (non-click) frame could ever certify absence of clinical signal — neither exists
today.**

### C. Exact factual FAQ — **NOT eligible yet; stays `required`, per the brief's own fallback rule**

There is no dedicated "exact validated content authority" TurnFrame capability distinguishing a
provably-factual definitional question ("What is All-on-4?") from one that merely *looks* factual but
edges into suitability ("Is All-on-4 right for me?" can share the same `topic`/`service_id` and even the
same `intent="content"` classification as a pure definitional question — nothing on `TurnFrame`
structurally separates them; both are subject to the same `needs_clarification` blind spot as §3). Per
the milestone brief's explicit instruction: *"Если недостаточно — зафиксировать FAQ как required до
отдельного typed capability, а не угадывать."* Applying that instruction: **FAQ stays `required` in
Phase 2.** A future capability (e.g. a curated, explicitly-tagged "safe definitional content" registry
with its own typed provenance, analogous to the governed-UI-click whitelist) would be a separate,
later milestone with its own seam audit — not guessed here.

### D. Structured contacts / service availability — **already bypassed; not modeled in the resolver's type at all**

`resolve_structured_answer_capability(turn_frame).kind ∈ {"clinic_contact", "service_availability"}`
already short-circuits Boundary (and Composer and both Verifier stages) today
(`core/target_runtime_turn.py:198-265`), and both branches `return` **before** the point in the pipeline
(line 322) where `resolve_target_medical_boundary_requirement(...)` would ever be called. **The resolver's
production call site never observes a structured-capability turn — this is not a state the function's own
type needs to represent.** (Governance correction: the original revision of this audit modeled this as a
fifth Literal value, `not_applicable_structured`, and passed `structured_capability` into the resolver's
signature so it could detect this state. Both are removed — see "Governance correction" above.) PERF-2
does not add a second bypass mechanism on top of this existing short-circuit; this section documents the
existing behavior for completeness only, not as something the resolver's contract needs to know about.

## 5. Hard exclusions (Boundary stays `required`)

Per the milestone brief, and confirmed against the actual code in this audit, Boundary is `required`
whenever any of the following holds — none of these can be overridden by a "the frame looks complete"
heuristic, because §3 established that TurnFrame completeness does not capture clinical ambiguity:

- Free-text turns of any kind that are not a governed UI click (covers suitability, diagnosis, symptoms,
  complications, contraindications, personal medical recommendation, post-op problems — all of §B/§C
  above collapse into this).
- `medical_handoff` scenario signals of any kind.
- Ambiguous or invalid `TurnFrame` (`field_meta.status ∈ {"invalid", "missing"}` on any axis).
- `needs_clarification=True` on a free-text frame that is not an already-resolved advisory FAQ path (no
  such path exists yet per §4C, so in practice this condition is currently vacuous — everything free-text
  stays required regardless).
- `marketing_scenarios` containing `pain_fear` or `result_reliability` — these are emotional-objection
  markers (§3: LLM-produced, no clinical-risk semantics), not proof of safety; per the brief they must not
  be used as the *sole* basis for a bypass decision, and per §4B/§4C no free-text path is eligible at all
  right now, so this exclusion is currently subsumed by "free-text stays required."
- Generic topic/content without a dedicated typed authority capability (§4C).
- Conflicting typed signals on the same frame.
- Backend/pipeline uncertainty outside the one proven-safe bypass (`bypass_governed_ui`).

## 6. False-bypass risk assessment

**Residual risk for the one eligible category (`bypass_governed_ui`):** structurally near-zero by
construction, not by inference:

1. The click itself can only exist if the ref matches a session-bound whitelist of refs the *server*
   rendered (fail-closed on mismatch).
2. The click cannot coexist with free text (`if not q:` gate) — there is no code path today by which a
   governed click's turn carries user-authored content of any kind.
3. The resulting TurnFrame's safety-relevant fields (`intent`, `aspects`, `needs_clarification`) are
   compile-time constants of the builder function, not values a model produced.
4. Composer is still bound by `forbidden_topics=("diagnosis", "personal_eligibility")` regardless.
5. Deterministic Verifier (regex/Decimal numeric grounding, no LLM, cannot be "convinced") and Semantic
   Verifier (LLM, blocks `unsupported_clinic_claim`/`personal_medical_conclusion`/
   `material_external_medical_claim`, **unconditional** whenever Composer ran — §7) both still execute
   after Composer, exactly as they do today for every turn. Nothing about skipping Boundary changes
   whether these run.
6. Even in the pathological case where Composer's own generation (not the user's input) somehow drifts
   into medical-advice-shaped language despite `forbidden_topics`, that is caught by (5) — the identical
   backstop that already catches the *majority* of Boundary's own "uncertain" outcomes today (§2), since
   those are silently downgraded to "confident none" and reach Composer/Verifier anyway.

**Residual risk for the deferred categories (`bypass_pure_price`, `bypass_exact_faq`):** left explicitly
`required` (§4B/§4C) precisely because no equivalent structural guarantee exists for them today — this
audit does not attempt to quantify a risk score for a bypass that is not being implemented.

## 7. Estimated savings (structural, offline — no LIVE measurement)

Boundary, Composer, and Semantic Verifier are three **sequential**, blocking LLM calls in every non
structured, non-bypassed turn (§1) — Boundary must return before Composer is invoked
(`target_runtime_turn.py:322` completes before line 373 runs). Removing Boundary removes exactly one of
these three calls, and its full round-trip latency (not just its own inference time — network + queueing
+ provider overhead per call, which for a `max_completion_tokens=64` classification call is
disproportionately dominated by fixed round-trip cost rather than generation time) from the sequential
critical path, on eligible turns only.

This audit does not produce a measured percentage: Phase 1 is explicitly offline/no-LIVE, and PERF-0's
seam audit already recorded (from `docs/STRANGLER_ROADMAP.md`'s own prior framing) that a full turn can
run **≈12–15s end-to-end** across the whole chain including three sequential LLM calls plus retrieval and
widget assembly — removing one of three sequential LLM round-trips from that chain, on the subset of
turns that are governed UI clicks, is a structural, verifiable-by-telemetry reduction (the exact
`stage_skipped("boundary", reason=...)` mechanism already proves, today, for the `clinic_contact`/
`service_availability` paths, that this telemetry can and does report "boundary not run" accurately —
Phase 2 would add one more `reason` value to that same, already-shipped mechanism, not build new
instrumentation).

**Scope of the saving:** governed UI scope/stage clicks only — a subset of AC2/AC3 traffic. This is not
"once per session" but every governed click turn (typically several per multi-step price/scope
conversation), since each click is currently a full pipeline turn.

## 8. Decision: which paths enter PERF-2 implementation

| Category | In the `TargetMedicalBoundaryRequirement` type? | Decision |
|---|---|---|
| `bypass_governed_ui` (§4A) | **Yes** — the only bypass value | **Enters Phase 2 implementation** (pending owner GO) |
| `bypass_pure_price` (§4B) | **No** (governance correction — removed from the Literal) | **Resolver always returns `required`** for this shape — explicitly deferred in narrative only, prerequisite (Composer price-materialization contract) not yet built |
| `bypass_exact_faq` (§4C) | **No** (governance correction — removed from the Literal) | **Resolver always returns `required`** for this shape — explicitly deferred in narrative only, no typed content-authority capability exists |
| Structured contacts/service availability (§4D) | **No** — not modeled at all (governance correction — `not_applicable_structured` removed; resolver's call site never observes this state) | **No new work** — already bypassed via existing `structured_capability` mechanism, entirely outside this resolver's concern |
| Everything else (§5) | `required` (the type's default/only other member) | **Stays `required`**, unconditionally |

## 9. Proof this is not a new router/selector

`resolve_target_medical_boundary_requirement(...)` (Phase 2, not built in this governance phase) would be
a **pure function** called from exactly one place — immediately before the existing
`turn_timing.stage_start("boundary")` call at `core/target_runtime_turn.py:322` — reading only the
already-materialized `turn_frame` and the already-resolved governed UI action objects
(`_current_ui_scope_action_from_request()`/`_current_ui_stage_action_from_request()`, already called at
lines 188-189 for `resolve_effective_scope`). **Governance correction:** the original revision also passed
in `structured_capability`; that parameter is removed (§4D, §8) because by the time this resolver would
run at line 322, `structured_capability` being `None` is already a control-flow guarantee (both non-`None`
branches return at lines 198-320, strictly before line 322) — passing it in would have been a dead
parameter the resolver could never usefully branch on. The resolver introduces **no new inputs**, **no new
classification**, and **no new call site for routing** — it only decides, from data the pipeline has
already deterministically computed by this point, whether to execute or skip the *existing*
`execute_target_medical_boundary_classification` call, using exactly the same `stage_skipped(...)`
mechanism already used for `clinic_contact`/`service_availability`/`typed_ui`. There is no second
`orchestrate_*`/`dispatch_*` entry point, no second `TurnFrame` producer, and no new persisted state. This
mirrors the existing `structured_capability` skip precedent (§1, §4D) exactly — it is one more `if`
branch guarding one existing call, not a parallel decision system.

## 10. Composer/Verifier remain the backstop (confirmed, not assumed)

- `verify_target_composed_response()` (`core/target_response_verifier.py:692-809`) runs
  `verifier_deterministic` then `verifier_semantic` **unconditionally** whenever Composer produced a
  response — the only two conditions under which `verifier_semantic` is skipped are (a) the deterministic
  check itself already raised (`reason="deterministic_block"`) or (b) Composer itself never ran (structured
  capability or terminal-before-composer) — never "Boundary was skipped."
- The semantic verifier's own policy is described, in this codebase's own test naming, as a **"lightweight
  boundary"** (`tests/test_s59_semantic_verifier_policy.py::test_policy_text_describes_s59_lightweight_boundary`)
  — i.e. the product's own prior design already treats it as a real (if lighter-weight) safety gate in its
  own right, not merely a grammar/fact checker.
- No test or comment in the codebase currently frames Verifier as a *substitute* for Boundary in an
  explicit bypass scenario (none existed before this milestone) — this audit is the first to state that
  relationship explicitly, and does so narrowly (§6), not as a general claim that Verifier alone always
  suffices for arbitrary free text.
- Semantic Verifier failure does not trigger a retry/re-composition LLM call — on rejection the pipeline
  returns an error payload directly (`core/target_runtime_turn.py:410-422`). Steady-state LLM count per
  answered, eligible turn: **2** (Composer + Semantic Verifier) instead of **3** (Boundary + Composer +
  Semantic Verifier) — exactly one fewer, never more, never a variable amount.

## 11. Typed contract (governance correction — minimal; names may be adjusted in Phase 2, shape is final)

**Governance correction:** the Literal now has exactly two members. `bypass_pure_price` and
`bypass_exact_faq` are deliberately **not** members of the type — they remain documented, narrative-only
future capabilities (§4B/§4C) that the resolver always resolves to `required` today; a type should not
offer a return value that current policy forbids ever returning. `not_applicable_structured` is removed
entirely, not renamed — it modeled a state the resolver's own call site can never observe (§4D, §8, §9).

```python
# contracts/target_medical_boundary_requirement.py  (Phase 2 — NOT created in this governance phase)

TargetMedicalBoundaryRequirement = Literal[
    "required",             # Boundary must run — the default, and the fail-safe fallback for any
                             # missing/mismatched/ambiguous input, exception, or anything not
                             # explicitly proven safe by every rule in §4A's checklist
    "bypass_governed_ui",   # governed UiScopeAction XOR UiStageAction click, exact field/provenance
                             # match per §4A's checklist — the ONLY eligible bypass, §4A
]
```

```python
# Phase 2 signature sketch — NOT implemented in this governance phase
def resolve_target_medical_boundary_requirement(
    *,
    turn_frame: TurnFrame,
    current_ui_scope_action: UiScopeAction | None,
    current_ui_stage_action: UiStageAction | None,
) -> TargetMedicalBoundaryRequirement:
    """Pure. No I/O, no LLM call. Reads only turn_frame and the two governed-action parameters —
    never raw user text, never request data, never session state directly (the action parameters'
    mere presence is the caller's proof that session.py's existing ref-whitelist check already ran
    and passed — see §4A rule 2), never a service/topic-specific ID, never confidence as
    standalone proof, never regex/phrase-list matching of any field.

    Returns "bypass_governed_ui" only if ALL of the following hold (§4A's exact checklist; any
    single failure -> "required", no partial-credit bypass):
      1. exactly one of current_ui_scope_action / current_ui_stage_action is not None (XOR) --
         both-present or neither-present both fall through to "required";
      2. turn_frame.intent == "price_lookup";
      3. tuple(turn_frame.aspects) == ("price",) (or the frame's canonical single-price-aspect form);
      4. turn_frame.primary_aspect == "price";
      5. turn_frame.needs_clarification is False;
      6. field_meta.status == "valid" for each of: intent, aspects, primary_aspect,
         needs_clarification;
      7. field_meta.provenance == f"governed_ui_action:{action.ref}" for each of those same four
         fields, where `action` is the one action identified in step 1;
      8. turn_frame.topic == action.topic.

    Returns "required" for every other shape, including bypass_pure_price/bypass_exact_faq-looking
    free-text turns (§4B/§4C — recognized in narrative as future capabilities, not returnable
    values of this function today) and any turn where resolve_structured_answer_capability would
    have matched (§4D — this function's production call site never actually observes that case,
    since both structured branches return before line 322; it is not modeled here, only noted)."""
```

## 12. Implementation allowlist (Phase 2 — blocked until owner GO)

| File | Action |
|---|---|
| `contracts/target_medical_boundary_requirement.py` | CREATE — the `TargetMedicalBoundaryRequirement` literal + any small supporting dataclass |
| `core/target_medical_boundary_requirement.py` | CREATE — the pure `resolve_target_medical_boundary_requirement(...)` resolver, §11 |
| `core/target_runtime_turn.py` | UPDATE — call the resolver immediately before `turn_timing.stage_start("boundary")` (line 322 today); on `bypass_governed_ui`, skip Boundary via `stage_skipped("boundary", reason="bypass_governed_ui")` and proceed directly to the Composer/Verifier chain with `boundary` set to the existing confident-`none` result shape (no new terminal/envelope branch) |
| `core/turn_timing.py` | **KEEP unchanged** — reuse existing `stage_skipped` exactly as-is; no new marks/timing system |
| `tests/test_final_safe_medical_boundary_bypass_implementation.py` | CREATE — acceptance matrix (§13) |

**KEEP unchanged:** Boundary/Composer/Verifier prompts and policy; `forbidden_topics` argument; the
`if not q:` gate at `orchestration/pre_resolver_turn.py:248`; the ref-whitelist check
(`resolve_ui_scope_ref_click`/`resolve_ui_stage_ref_click`); `core/target_typed_ui_turn_frame.py`'s
deterministic construction; the `structured_capability` skip mechanism (§4D, untouched, not layered);
`bypass_pure_price`/`bypass_exact_faq` remain unimplemented — recognized in the type vocabulary (§11) for
forward-compatibility, but the resolver must return `required` for both today; session write-back logic;
`/ask`/`/ask/stream` route parity; LLM call count for every non-`bypass_governed_ui` path.

## 13. Acceptance matrix (Phase 2 implementation — minimum coverage, 23 scenarios)

| # | Scenario | Expected |
|---|---|---|
| 1 | Governed scope click (`UiScopeAction`, ref in session followups, `q=""`) | Boundary bypassed (`stage_skipped("boundary", reason="bypass_governed_ui")`); LLM call count −1 vs. today |
| 2 | Governed stage click (`UiStageAction`, ref in session followups, `q=""`) | Boundary bypassed, same as #1 |
| 3 | Invalid/unshown ref (not in session followups) | `target_fullcontext_followup_unknown` clarify path — Boundary never reached at all (pre-resolver short-circuit, unrelated to this resolver) |
| 4 | Direct exact known-service price (free text, e.g. "сколько стоит консультация?") | `bypass_pure_price` candidate shape, but resolver returns `required` — Boundary still runs |
| 5 | Broad family price (free text, ambiguous which service) | `required` — explicit, not silently guessed |
| 6 | Cross-turn price follow-up (governed click referencing a prior turn's shown followup) | Boundary bypassed, same as #1/#2 |
| 7 | "Что такое All-on-4?" (free-text definitional) | `required` — FAQ not eligible (§4C) |
| 8 | "Подойдёт ли мне All-on-4?" | `required` — suitability |
| 9 | "Вдруг имплант не приживётся?" | `required` — complication concern |
| 10 | "После имплантации болит" | `required` — post-op problem |
| 11 | Contraindication / diabetes question | `required` |
| 12 | Ambiguous/ill-formed `TurnFrame` (`field_meta.status` invalid/missing on any axis) | `required` |
| 13 | Generic microfact question (free text, looks simple) | `required` — conservative default, no confidence-based override |
| 14 | Structured `clinic_contact` short path | Unaffected — bypassed via the existing `structured_capability` mechanism entirely; the resolver's production call site never runs for this turn at all (control flow returns before reaching it — §4D, §9), so there is nothing for it to return |
| 15 | Structured `service_availability` short path | Same as #14 |
| 16 | Boundary backend failure on a `required` path | Unaffected — terminal/defer behavior identical to today (resolver never called for `required` paths in a way that changes this) |
| 17 | Numeric Verifier after a `bypass_governed_ui` turn | Still runs, still enforces grounding exactly as today |
| 18 | Semantic Verifier blocks a personal-diagnosis-shaped Composer output after a `bypass_governed_ui` turn (adversarial Composer-output test, mocked backend) | Verifier still blocks — `target_verifier_semantic_rejected`, identical to a non-bypassed turn |
| 19 | `/ask` vs `/ask/stream` parity for a governed-click turn | Identical `service_route`/payload/LLM-call-count on both endpoints |
| 20 | PERF-0 trace for a bypassed turn | `boundary` stage shows `status="skipped", reason="bypass_governed_ui"` in `turn_complete` |
| 21 | PERF-1 SSE status stream for a bypassed turn | No Boundary-phase status event shown (skipped stages never enqueue — existing PERF-1 rule, unchanged) |
| 22 | Both `current_ui_scope_action` and `current_ui_stage_action` present simultaneously (constructed test fixture — not reachable via the real pre-resolver today, but the resolver must not assume that) | `required` — XOR violation, §4A rule 1 |
| 23 | Governed click TurnFrame whose `field_meta.provenance` for a required field does not exactly equal `f"governed_ui_action:{action.ref}"` (e.g. mismatched ref, or a provenance string that only starts with the right prefix) | `required` — provenance mismatch, §4A rules 7-8 |

**Cross-cutting requirement across all 23 rows:** LLM call count decreases by exactly one **only** on
rows 1/2/6/19 (and 20/21 as their telemetry/SSE counterparts) — every other row's LLM call count,
route, final payload, and session write must be byte-identical to `aa633f2` behavior. This is the
acceptance criterion referenced by the milestone brief's "число LLM-вызовов уменьшается ровно на один
только на eligible paths" and "routes/final payload/session write не меняются." Rows 22-23 additionally
confirm the resolver's `required` fallback triggers on structural/provenance mismatch, not only on
"no governed action present."

## Test commands (governance)

```powershell
python -m pytest tests/test_final_safe_medical_boundary_bypass_governance.py -q
python -m pytest tests/test_final_response_latency_observability_governance.py tests/test_final_early_sse_status_streaming_governance.py -q
git diff --check
```

## STOP

After PRE-CODE ✅ — **STOP**. Implementation only after a separate owner GO.
