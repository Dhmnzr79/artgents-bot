# FINAL_ADAPTIVE_RESPONSE_LENGTH_BUDGETS (PERF-5) — seam audit

**Дата:** 2026-07-30
**Baseline:** `codex/stage-a` @ `2fe7437`
**Режим:** Phase 1 — governance / read-only seam audit / docs / tests only · **NO PRODUCT
IMPLEMENTATION / NO LIVE / NO PROVIDER CALLS / NO NETWORK / NO HARD TRUNCATION / NO RETRY-FOR-
LENGTH / NO VERIFIER POLICY CHANGE / NO PRICE-RULE CHANGE / NO SCOPED FULLCONTEXT / NO TOKEN
STREAMING / NO MODEL CHANGE / NO INGRESS+PLANNER CHANGES / NO BOUNDARY BYPASS / NO ANSWER-
CACHE/PREWARM / NO CLIENT-PACK/FROZEN ARTIFACTS / NO TSC-C / NO TSC-D / NO UNRELATED CLEANUP**
**Owner GO:** Phase 1 governance only; product implementation (the length-budget producer and
its Composer/observability wiring) is blocked until PRE-CODE ✅ + a separate, later owner GO —
the same two-gate pattern already used for PERF-3/PERF-4.

## 0. Offline baseline aggregate (existing local logs, no LIVE call made for this milestone)

Read-only aggregation over the three local rotated log files (`logs/demo-app.jsonl`,
`logs/demo-app.jsonl.1`, `logs/demo-app.jsonl.5` — dev/test-fixture traffic, local Windows dev
box; see [[local-dev-test-data]] — not real customer PII, not necessarily production-
representative). No new record was produced; nothing was replayed or re-run.

```
turn_complete.details.answer_chars (all intents, n=2058):
  min=8  p50=97  p90=159  max=1029  mean=107.7
  by intent: content n=2001 (min27/p50=97/p90=159/max=1029); unknown n=57 (min8/p50=15/max=16)

turn_complete.details.composer_ms (n=981 records carry the field; 970 are 0 — Composer stage
skipped/not reached on that turn; 11 nonzero — the FullContext runtime Composer actually ran):
  nonzero only: min=4085  p50=6861  p90=7820  max=8082  mean=6605 (ms)

llm_usage completion_tokens, call_type="target_fullcontext_runtime_composer" (REAL runtime
Composer calls only, n=21):
  min=113  p50=234  p90=339  max=367  mean=233.6

llm_usage completion_tokens, call_type="target_fullcontext_prewarm_composer" (PERF-3 CLI
fixture calls, NOT real traffic — excluded from the "real runtime" numbers above per the
instruction not to mix fake usage records with real ones, n=154):
  min=4  p50=4  p90=4  max=16  mean=4.1
```

**Reading these numbers honestly, not as proven causation:** the bulk of `answer_chars` records
(n=2058) come predominantly from turns where `composer_ms=0` — i.e. most logged turns in this
fixture set never reached the FullContext runtime Composer at all (structured capabilities,
legacy pipeline, or skipped stages), so the overall `answer_chars` distribution is **not** a
clean per-Composer-profile baseline. The only number that is cleanly "real FullContext Composer,
real runtime, no fixture noise" is the 21-call `completion_tokens` sample (mean 234, max 367,
well under the fixed `max_completion_tokens=1024` cap, §5) and the 11-sample nonzero
`composer_ms` (mean 6.6s — consistent with PERF-4 §0's own motivating example, "Composer 7.8s").
Nothing in today's logs is segmented by `response_stage`/a length profile, because that signal
does not exist yet — Phase 2 should add the new observability fields (§19) specifically so a
real, profile-segmented baseline becomes possible after rollout, rather than estimating one now
from a signal that isn't logged.

## 1. Existing length/structure controls — full inventory (confirmed by reading the code)

| Symbol | Location | What it actually controls |
|---|---|---|
| `answer_chars` | `app.py:404,808`; `orchestration/finalize_turn.py:126,171` | Telemetry only — `len(answer_text)` logged into turn metadata/eval slices. **Observed, never enforced.** |
| `INPUT_MAX_CHARS` (`=600`) | `config.py:114`, `orchestration/route_guards.py:38-40`, `orchestration/pre_resolver_turn.py:84-95` | Caps the **incoming user message**, not the answer. |
| `min_answer_chars_after_remove` | `core/routing_loader.py:153` (`Field(ge=0, le=2000)`), `core/routing.yaml:99` (`= 80`) | Declared config with **zero consuming call sites** found — the same class of dead-config debt already flagged in `docs/FLAGS_AND_STATUS.md:232` for the `limits:` block. Not a working length control today. |
| `PREBUFFER_MIN_CHARS`/`PREBUFFER_MAX_CHARS`/`PREBUFFER_LIST_MIN_CHARS` | `core/content_linter.py:12-14` (80/250/32); `core/stream_answer_text.py:13,47` (`=250`) | **Streaming display** buffering thresholds (when the widget releases its first chunk) — a UX/latency knob, not an answer-length cap. |
| `max_price_anchors` (1 or 4) | `core/target_response_policy.py` (`broad_family_price_directive_overlay`, ~lines 41-60) | Stage-conditional cap on the **number** of price anchors shown in a compact family-price overview — the closest existing precedent for a "content volume" budget, but it counts anchors, not characters. |
| `max_completion_tokens` (fixed per call site) | Composer `1024`, Verifier(semantic) `512`, Boundary `64` (`core/target_runtime_llm_backends.py:83,131,190`); Planner `700` (`core/turn_planner_llm.py:23`); prewarm `16` (`core/target_prompt_cache_prewarm.py:93`); legacy Resolver `250` (`resolver.py:116`); legacy shadow Verifier `400` (`verifier.py:183`) | Hard provider-side upper bounds, one literal per call site. **None is adaptive** — none is conditioned on `response_stage`, `EffectiveScope`, or turn complexity. |
| `CHOICE_MENU_MAX=4` / `SECONDARY_CONTENT_MAX=2` / `PRICE_DETAIL_MAX=2` | `core/target_presentation_decision.py:25-27` | Existing **count-based** UI-affordance budgets (buttons), not text length — but the best style precedent for how a new budget constant should be declared and named. |
| Qualitative brevity instructions | `core/target_composer_executor.py` Rule 3 ("...concisely...", no bound); `core/llm_system_prompt.py:6-20` `_SYSTEM_STYLE` (live pipeline, "отвечай коротко и по делу", no bound) | Prose-only guidance, no measurable budget anywhere today. |
| Stage-conditional structural directives | `core/target_response_policy.py`: `broad_family_price_directive_overlay` (`omit_sections`, `include_scale_clarify`), `stage_clarify_directive_overlay` (`answer_mode: short_stage_question_only`), `data_gap_protocol_unconfirmed_directive_overlay` | **The one existing precedent for stage-conditional response-shape control** — an additive dict merged into `response_directives_json`, keyed off `response_stage`. This is the shape PERF-5's own producer should copy (§15). |

**Conclusion:** there is no dedicated `ANSWER_MAX_CHARS`/length-budget mechanism anywhere in the
codebase today, and no dedicated char/length/compact guard test file exists (`tests/test_*char*`,
`tests/test_*length*`, `tests/test_*compact*` all return nothing beyond incidental `compact`
JSON/flag mentions). A PERF-5 implementation phase would be creating this class of control and
this class of test from scratch — not adjusting an existing one.

## 2. `TurnFrame`, `response_stage`, `EffectiveScope` — the structured signals available

- **`TurnFrame`** (`contracts/turn_frame.py`, 169 lines, docstring: "A1 shadow-only; not wired to
  runtime") carries `intent` (`RouteIntent = "content"|"price_lookup"|"price_concern"|"unknown"`,
  `contracts/decision_frame.py:8`), `aspects: list[AspectKind]` / `primary_aspect`
  (`AspectKind` — 16-value literal including `"comparison"`, `"included"`, `"pain"`, `"warranty"`,
  `"duration"`, `"stages"`, `"overview"`, `contracts/answer_plan.py:7-24`), `emotion`,
  `specificity`, `needs_clarification: bool`, `marketing_scenarios: list[MarketingScenarioKind]`
  (capped to 2, `_cap_marketing_scenarios`, lines 145-160), and `field_meta`. **No length/stage/
  scope field exists directly on `TurnFrame`** — those live in separate sibling contracts.
- **`response_stage`** (`contracts/target_response_stage.py`, 35 lines):
  `ResponseStage = Literal["broad_family_price","scoped_family_price","concrete_service_price",
  "stage_clarify","data_gap"]`. Set on `TargetResponseSpec.response_stage` (optional field,
  produced by `core/target_response_policy.py::build_target_response_spec`). This is the single
  strongest existing axis for a length profile to key off — it is already the seam the one
  existing structural directive (§1's `broad_family_price_directive_overlay`) uses.
- **`EffectiveScope`** (`contracts/effective_scope.py`, 56 lines) — merged patient/product scope
  (`extent`, `jaw`, `stage`, `reported_context`, each with its own provenance axis). Docstring:
  "does not select treatment or service." Carries **no length information** — purely a semantic
  merge that feeds *into* `response_stage`/price resolution upstream, not a response-shape
  contract itself.

## 3. Materialization/spec package — where a length signal would attach

- **`contracts/target_response_spec.py`** (`TargetResponseSpec`, 130 lines) is the canonical "what
  may this answer contain" declaration: `response_mode` (`answer`/`clarify`/`defer`/
  `medical_handoff`), `service_id`, `response_stage`, `required_fact_ids`, `required_components`
  (`content`/`price`/`doctors`), `followup_source`, `allow_marketing_facts`,
  `allow_consultation_close`, `allow_cta` — heavy cross-field validation (lines 85-129, e.g.
  `stage_clarify` forbids CTA/marketing/followups). **No length field exists here today** — this
  is the natural typed home for the axes a length-profile selector reads, but the profile's own
  *output* is deliberately kept **out** of this frozen, strictly-validated model (§15) rather than
  added as a new field on it.
- **`core/target_response_materialization_plan.py`** (`TargetResponseMaterializationPlan`, 150
  lines) — `required_components`, `unfulfilled_components`, `offer_ids`, `doctor_ids`,
  `commercial_fact_ids`, `cta_key`. No length field.
- **`core/target_composer_request.py`** (721 lines) — `materialize_target_composer_request()`
  turns a spec-bound package into a `TargetComposerRequest` (evidence blocks + spec + followups +
  CTA + action context); branches on `stage in {"stage_clarify","data_gap"}` (line 641) to skip
  evidence materialization. This is the "materialization → Composer input" seam a length-profile
  directive would be threaded alongside, the same way `response_stage` already is.

## 4. Composer prompt / directives — existing precedent for stage-conditional shape control

`core/target_composer_executor.py`, `TARGET_COMPOSER_SYSTEM_POLICY` (lines 37-47, 11 numbered
rules): Rule 3 is the only general brevity instruction ("Answer the user's actual question
directly, concisely, and naturally" — no bound). Rule 10 is the **only existing stage-conditional
structural directive**: when `response_directives_json` includes `broad_family_price_compact`,
give a compact overview capped by `max_price_anchors`, omitting payment-stage breakdowns/package-
composition lists/long bonus lists, ending with a short scale-clarify phrase. Rule 11 fixes the
strict output JSON shape (`{"answer":..., "source_identity":{...}}`) — no length field in the
output schema itself.

`_invocation()` (lines 350-394) assembles `response_directives_json` — `response_mode`,
`tone_key`, `allowed_topics`/`forbidden_topics`, `required_fact_ids`, `allow_marketing_facts`,
`allow_consultation_close`, `allow_cta`, `response_stage`, the overlay dicts from
`core/target_response_policy.py`, and `governed_action` if present. **This is exactly the
injection point a length-profile directive would use** (an additive key, same shape as the
existing overlays), not a new prompt path.

Legacy/live equivalent: `core/llm_system_prompt.py` — `_SYSTEM_STYLE` (lines 6-20) has the live
pipeline's own brevity line ("отвечай коротко и по делу... начинай сразу с сути ответа"),
`_NO_CONTINUE` (lines 27-31) forbids prose-based "want me to continue?" — continuation must be a
UI button, never text. Same "structure vs. prose" separation principle PERF-5's own progressive-
disclosure requirement (§12) already assumes.

## 5. Composer SDK messages & token caps — fixed, not adaptive

`core/target_runtime_llm_messages.py::build_composer_sdk_messages()` (lines 43-60) builds
`[{"role":"system",...},{"role":"user", content: _COMPOSER_USER_TEMPLATE.format(...)}]` —
`_COMPOSER_USER_TEMPLATE` interpolates `CACHED_FULL_CONTEXT`, `RESPONSE_DIRECTIVES_JSON`,
`GOVERNED_ACTION_CONTEXT_JSON`, `PRIMARY_EVIDENCE_JSON`, `USER_MESSAGE`. `max_completion_tokens`
is a fixed literal per call site (§1's table) — `1024` for Composer today. `execute_target_
composer()` (`core/target_composer_executor.py:397-447`) is a single blocking call, no
`stream=True`, no retry (a PERF-0 comment at lines 416-419 already notes first-token timing is
not measurable here because the call is not streamed). **`max_tokens` cannot be used as a
precise answer-size dial** — set it too low and a JSON response or a required fact can be cut
mid-token; that is exactly why the owner's brief rules out Variant B as the sole mechanism (§15).

## 6. Action context directives — an orthogonal signal, not a length input

`contracts/target_composer_action_context.py` (`TargetComposerActionContext`: `action_kind:
"ui_scope"|"ui_stage"`, `governed_ref`, `response_stage`, `extent`/`stage`) and `core/target_
composer_action_context.py` (`ContextVar`-bound, session-scoped, threads a validated governed UI
click into the Composer as an intent override — never free text). This signals *what the user
clicked*, feeding Composer's intent resolution; it is a legitimate input to the length-profile
selector only insofar as it correlates with `response_stage` (already covered there) — it carries
no length information of its own and must not become a second, independent length signal.

## 7. Marketing scenarios — selection & existing volume limits

`MarketingScenario`/`MarketingScenarioKind` (5-value literal: `pain_fear`, `cost`, `time`,
`doctor_trust`, `result_reliability` — duplicated in `contracts/response_schema.py:101-107` and
`contracts/target_composer_source_identity.py:8-24`). `core/target_marketing_selector.py`
(320 lines, "S21, offline and unwired") — `select_target_marketing()` (lines 160-319) respects
`policy.limits.max_scenarios_per_turn` / `max_marketing_facts_per_turn` (≤3,
`contracts/response_schema.py:405`) / `max_amplifiers_per_turn` (≤2, line 406). Live production of
the scenario labels: `core/turn_planner_llm.py` lines 94-103 (Planner LLM returns 0-2 scenarios,
gated on explicit fear/doubt/objection). `docs/MARKETING_SCENARIO_ARCHITECTURE.md` states the
product contract precisely (≤3 marketing facts, of which ≤2 amplifiers; CTA doesn't count toward
this limit). **A non-empty `marketing_scenarios`/`applied_scenarios` set is a legitimate,
existing, structured signal for the `marketing_concern` profile (§16)** — it already caps its own
fact volume; the length profile only needs to give that volume room to breathe (350-650 chars),
not invent a new cap.

## 8. Required facts / `must_preserve_exact` — the load-bearing invariant

`required_fact_ids: tuple[CanonicalToken,...]` on `TargetResponseSpec` (cross-validated against
`required_components`/mode, lines 91-101). `must_preserve_exact: bool` on `TargetComposerEvidence
Block` (`core/target_composer_request.py:66-73`), set per-block in `_block()` (lines 470-535):
`offer`→`True`, `doctor`/`external_doctor`→`True`, `commercial_fact`→`fact.render_mode=="strict"`,
`content`/`external_kb`/`consultation`→`False`. Enforced twice: `core/target_composer_executor.py
::_validate_blocks()` (lines 196-250, every `required_fact_id` must appear as a `commercial_fact`
block, `must_preserve_exact` must match the expected flag per kind) and, decisively, `core/
target_response_verifier.py::verify_target_composed_response()` (lines 727-732): for every
`must_preserve_exact` commercial-fact block whose `fact_id ∈ spec.required_fact_ids`, asserts
`block.text in response.text` (a **verbatim substring check**) → error
`target_verifier_strict_fact_missing` if it fails. **The verifier already assumes the full,
unabridged fact text appears byte-for-byte.** This is the single most important existing
constraint on the whole PERF-5 design: any adaptive shortening must never cause the Composer to
omit, paraphrase, or truncate text backing a `required_fact_id` — the soft budget must yield to
this, not the other way around (per the owner's own "correctness over budget" rule, §17-18).

## 9. Offers / numeric grounding — full-answer-text scope

`contracts/response_schema.py` defines the price union (`TargetFixedPrice`/`TargetFromPrice`/
`TargetRangePrice`/`TargetNoPublicPrice`, discriminated by `mode`) and `TargetOffer`/`TargetPrice
Package`/`TargetPaymentStage`. `core/target_response_verifier.py::_offer_claims()` (lines 372-465)
parses every offer's structured evidence into `TargetNumericClaim`s; `_numeric_claims(text)`
(lines 297-334) extracts **all** numbers/ranges from the **entire candidate answer text** via
regex (money/percent/day/month/year suffixes, lines 233-264); `verify_target_composed_response()`
(lines 717-726) requires every numeric claim in the answer to be in the structured or general
whitelist, else `target_verifier_numeric_ungrounded`. **This check runs over the full final
answer text, unconditionally.** A length budget that clips a number mid-digit, or drops the
evidence block a surviving number depends on while leaving the number itself in place, would
directly trip this existing check — another reason hard truncation (Variant C) is rejected
outright, not just discouraged (§15).

## 10. `no_public_price` — the `approved_text` invariant

`TargetNoPublicPrice(mode="no_public_price", approved_text: NonBlankStr)`
(`contracts/response_schema.py:245-247`) is a canned, pre-approved commercial disclosure ("price
on request" style copy). `core/target_family_price_resolution.py:253,263` treats it as a
"confirmed" price mode (not a data gap) in the family-price precedence order (specific >
no_public_price > family > gap). `core/target_response_verifier.py::_offer_claims()` special-
cases it: requires exact keys `("mode","approved_text")` and extracts numeric claims **from
within `approved_text` itself** (line 434) so any numbers baked into the approved copy stay
whitelisted. When `no_public_price` backs a `required_fact_id`/offer evidence block, `must_
preserve_exact` (§8) applies to it exactly the same way — the length budget must never truncate
`approved_text` mid-sentence, full stop.

## 11. Verifier — confirmed length-blind today (the gap this milestone must not close by accident)

`core/target_response_verifier.py` (810 lines) runs two phases: **deterministic**
(`verifier_deterministic` — numeric grounding §9, strict-fact verbatim §8, clinic-contact
canonical-scalar presence) and **semantic** (`verifier_semantic` — an LLM call checking
`unsupported_clinic_claim`/`personal_medical_conclusion`/`material_external_medical_claim`/
`minor_external_detail`, blocking on the first three). A targeted grep across this file for
`len(`, `char`, `token`, `max_tokens`, `truncat` returns zero length-policy hits (the only `len(`
occurrences are unrelated list-count checks, e.g. `len(refs)`). **The Verifier has no length
awareness of any kind today, by design or by omission — either way, it is a hard fact, not an
assumption.** This is exactly why the owner's brief says the length policy is not a safety verifier (§18) rather than "extends the Verifier" — introducing a soft budget must not be read as adding new Verifier coverage; it is a separate, non-blocking layer, is not a new verifier policy, and the existing grounding/strict-fact checks (§8-9) remain the only hard gates on content correctness.

Legacy/live shadow verifier (`verifier.py`, 478 lines, best-effort, runs **after** the answer is
already sent) is similarly length-blind — not touched by this milestone either.

## 12. Presentation decision / progressive disclosure — a separate downstream decision, must stay uncoupled

`core/target_presentation_decision.py` (334 lines): `CHOICE_MENU_MAX=4`, `SECONDARY_CONTENT_MAX=
2`, `PRICE_DETAIL_MAX=2` (existing count budgets, §1); `FollowupChannel = "choice"|"price"|
"content"|"none"`; `TargetPresentationCadenceState`/`Update` (no-repeat cadence: `shown_video_ids`,
`shown_content_followup_refs`, `shown_price_followup_refs`, `situation_offered`); `TargetPresent
ationDecision` (`quick_replies`, `video`, `situation`, `dropped` audit trail, `channel`).
`decide_target_presentation()` (lines 247-333) picks exactly one navigation channel
(choice > price > content) and only offers video/situation inside the `content` branch. **This
module has zero visibility into or control over answer text length today** — it operates purely
on top of an already-composed answer. The length-budget design must keep this true: a soft length
budget is a **sibling** decision (made when the answer text is composed), never a trigger that
changes button counts, channel choice, or cadence state. Coupling them would violate the explicit
"sokraщение текста не должно увеличивать число кнопок или смешивать UI-каналы" requirement.

## 13. Follow-up/price/choice channels

`core/target_response_followup_policy.py::select_target_response_followups()` (83 lines, lines
49-82) picks **exactly one family** (`content` or `price`, never both) from `TargetResponseSpec.
followup_source`, guarded by `_valid_price_followup_ref`. "Choice" is a distinct concept
(`TargetNavigationFollowup`/governed UI scope-stage buttons), capped separately
(`_cap_choice_items`, `target_presentation_decision.py:71-94`). None of this carries or is
affected by answer-text length — confirmed structurally separate, same conclusion as §12.

## 14. CTA — architecturally separate from answer prose, confirmed unaffected

`TargetResponseSpec.allow_cta` is a boolean gate; `TargetComposerRequest.selected_cta_key` is a
**key**, never text. Composer system-policy explicitly forbids CTA/button/contact-detail leakage
into prose (`core/target_composer_executor.py`, one of the numbered rules) and the Verifier's
semantic phase (§11) treats such leakage as a blocking `unsupported_clinic_claim`-adjacent defect
when `allow_cta` is false. `core/target_verified_primary_content_cta_projection.py` projects a
soft CTA key **post-verification**, from validated frontmatter only, strictly gated to content-
only answers where `spec.allow_cta` is already `False` — again a key attached to the response
object, never concatenated into `.text`. **Conclusion: CTA never counts against a length budget
computed over `answer` text, and a length profile must never read or write `allow_cta`/
`selected_cta_key`** — this is a hard architectural fact, not a new design choice PERF-5 invents.

## 15. Variant comparison and selected design

| Variant | Verdict |
|---|---|
| **A — Soft budget carried as a Composer instruction, chosen by existing governed signals** | **Selected (combined with E).** Mirrors the one existing precedent (`broad_family_price_directive_overlay`, §1/§4) exactly — an additive dict key in `response_directives_json`, never a hard cutoff. Composer is free to exceed it when correctness requires (§8-10). |
| B — Hard provider `max_tokens` set to a small, precise value | **Rejected as the sole mechanism.** `max_tokens` truncates at the token boundary, not the sentence/fact boundary — it can cut a JSON response mid-structure or a `must_preserve_exact` block mid-word (§5, §8). Usable only as the existing, already-generous, fixed **ceiling** (`1024`) it already is — not as the actual size dial. |
| C — Truncate the finished answer text after generation | **Rejected outright.** Post-hoc truncation cannot know which characters are load-bearing (a price, a payment-stage condition, an `approved_text`, mid-sentence context for a numeric claim the Verifier will check, §8-10) — the owner's brief explicitly forbids this, and §8-10 show concretely why: it would either break the Verifier's own existing checks or silently drop a fact those checks don't happen to catch. |
| D — Regenerate (retry) when the answer exceeds budget | **Rejected for the normal path.** A retry doubles Composer latency and cost on every over-budget turn — directly opposed to this milestone's own "faster generation" goal, and the owner's brief explicitly forbids using retry for length. (A future, separate, explicitly-gated path could still exist for a different reason — not part of this milestone.) |
| **E — Structured answer outline (direct answer → 2-4 key facts → material conditions → next step, with CTA separate)** | **Selected (combined with A).** This is a *shape* instruction (like Rule 10's existing `broad_family_price_compact` omit-sections list, §4), not a size instruction — it is what actually makes a shorter answer read as complete rather than clipped, and composes naturally with a soft char budget rather than fighting it. |

**Selected: A + E**, exactly as the owner's brief prefers. Concretely: a new soft-budget +
outline-shape directive, injected into `response_directives_json` at the same point the existing
stage overlays are injected (§4), governed entirely by existing structured signals (§16), with
zero new hard cutoff, zero retry, and zero post-hoc truncation anywhere in the design.

## 16. Typed contract, canonical producer, and target length profiles

**Typed contract (planned, Phase 2 — not created in this Phase 1 milestone):**
`TargetResponseLengthProfile`, a 7-value `Literal`, declared next to the existing sibling
contract `contracts/target_response_stage.py` (same file-family precedent):

```python
TargetResponseLengthProfile = Literal[
    "clarification_concise",
    "simple_faq",
    "standard_information",
    "marketing_concern",
    "broad_price_overview",
    "scoped_price",
    "comparison_or_complex",
]
```

Companion soft-budget mapping (chars, over the `answer` text alone — no UI buttons, no CTA key,
no `source_identity` metadata counted, matching the owner's exact instruction):

| Profile | Soft range (chars) |
|---|---|
| `clarification_concise` | up to 250 |
| `simple_faq` | 250-450 |
| `standard_information` | 400-700 |
| `marketing_concern` | 350-650 |
| `broad_price_overview` | 450-750 |
| `scoped_price` | 350-650 |
| `comparison_or_complex` | 700-1000 |

These are **soft** targets, not a new fallback trigger and not a new Verifier block (§11, §18).

**Single canonical producer (planned, Phase 2):** one new pure function,
`select_target_response_length_profile(...)`, placed **in `core/target_response_policy.py`**
alongside the existing stage-overlay functions (§1, §4) — the file that already owns every other
stage-conditional response-shape decision. It reads only already-existing structured fields (no
new classifier, no regex, no phrase list, no second router, no signal derived from the user's raw
question length) and returns exactly one `TargetResponseLengthProfile`. Its result is injected
into `response_directives_json` at the same call site the existing overlays already use
(`core/target_composer_executor.py::_invocation()`, §4) as an additive key (e.g.
`response_length_profile` + `response_length_soft_max`) — **not** as a new field on the frozen,
strictly-validated `TargetResponseSpec` (§3), keeping that model's existing validation surface
untouched.

## 17. Profile-selection map (existing structured signals only)

| Priority | Condition (all fields already exist in the contracts read above) | Profile |
|---|---|---|
| 1 | `spec.response_mode == "clarify"` OR `spec.response_stage == "stage_clarify"` OR `turn_frame.needs_clarification is True` | `clarification_concise` |
| 2 | `spec.response_stage == "broad_family_price"` | `broad_price_overview` |
| 3 | `spec.response_stage == "scoped_family_price"` | `scoped_price` |
| 4 | `spec.response_stage == "concrete_service_price"` AND `"comparison" in turn_frame.aspects` | `comparison_or_complex` |
| 5 | `spec.response_stage == "concrete_service_price"` (no comparison aspect) | `scoped_price` |
| 6 | `"comparison" in turn_frame.aspects` (any stage, e.g. a prosthetics-protocol comparison outside a priced stage) | `comparison_or_complex` |
| 7 | `applied_scenarios` (from `TargetMarketingSelection`/`turn_frame.marketing_scenarios`) non-empty AND `spec.required_components == ("content",)` | `marketing_concern` |
| 8 | `spec.required_components == ("content",)` AND `spec.allow_marketing_facts is False` AND a narrow-topic signal (e.g. `len(spec.allowed_topics) <= 1`) | `simple_faq` |
| 9 | Everything else (multi-topic content, `content`+`doctors` combinations, `data_gap` stage, missing/invalid spec) | `standard_information` (safe default, §18) |

**Open point flagged honestly for Phase 2, not resolved here:** priority 8's "narrow-topic
signal" is the one boundary in this map that is not yet crisply pinned to a single existing field
— `simple_faq` vs. `standard_information` both describe a plain content answer with no marketing/
comparison signal, and the cleanest existing discriminator (`len(spec.allowed_topics)` or
`len(spec.required_fact_ids)`) is a reasonable proxy but not independently verified against real
traffic yet. This is exactly the kind of thing PERF-4 §16 flagged as "small-but-not-precisely-
known" rather than overclaiming precision — Phase 2 should pick one concrete existing field for
this boundary and test it against the acceptance matrix scenarios 1/2/5/6/13 (§21), not invent a
new signal to resolve it.

Governed UI action context (§6) and `data_gap` are deliberately **not** separate rows: an action-
context click only ever changes which branch of the table above applies (via the `response_stage`
it already carries), never a parallel length decision; `data_gap` falls through to priority 9
(`standard_information`) since it has no dedicated profile of its own — it is a data-availability
state, not a content-shape state.

## 18. Invariants the length budget must never override (never-touch list, cross-referenced)

- Prices and all other numbers, currency, and units (§9) — full-answer-text numeric grounding.
- `approved_text` / `no_public_price` (§10) — verbatim when backing a `required_fact_id`.
- `required_fact_ids` / `must_preserve_exact` evidence text (§8) — verbatim substring check today.
- Canonical contacts (clinic-contact canonical-scalar check, §11, deterministic verifier phase).
- Material price conditions, inclusions/exclusions when directly asked (§8-9 — these are exactly
  the kind of content that becomes a `required_fact_id`/offer evidence block).
- Protocol differences in a comparison (§17 priority 4/6 — `comparison_or_complex`'s wider budget
  exists specifically so this content is never the first thing trimmed).
- Any existing strong/marketing wording chosen by a governed scenario (§7) — the length profile
  gives it room (350-650 chars for `marketing_concern`), never edits or softens it.
- `source_identity`, CTA key, UI button/channel state (§12-14) — architecturally outside `answer`
  text; the budget is computed over `answer` text alone and must never touch these.
- **When a required fact cannot fit inside the soft budget, correctness wins — the budget is
  exceeded, not the fact dropped, no retry, no fallback** (matches the owner's explicit
  instruction and §8's existing verbatim-check reality).

## 19. Observability fields (planned, Phase 2 — anonymized, no q/answer/sid/contact values, no PII)

| Field | Status |
|---|---|
| `response_length_profile` | **New** — the selected `TargetResponseLengthProfile`. |
| `response_length_soft_max` | **New** — the resolved soft-max char count for that turn's profile. |
| `answer_chars` | **Existing**, reused (`app.py:404,808`, `orchestration/finalize_turn.py:126,171`) — not duplicated. |
| `completion_tokens` | **Existing**, reused — already logged per LLM call by `logging_setup.py::log_llm_usage` (`_USAGE_TOKEN_KEYS`, line 21; Composer's own usage row already carries it, confirmed in §0's real 21-call sample). |
| `over_soft_budget` | **New** — boolean, `answer_chars > response_length_soft_max`. |
| `required_content_override` | **New** — boolean/reason, set when §18's "correctness wins" path actually fired for this turn. |
| `composer_ms` | **Existing**, reused — already produced by PERF-0's `turn_timing.stage_start("composer")`/`stage_end("composer", ...)` marks (`core/target_composer_executor.py:415,437,439`); confirmed present and non-zero for real Composer calls in §0's aggregate. |

No new field duplicates an existing one; no fake/test-fixture record (prewarm calls, §0) should
ever be mixed into whatever future dashboard/query reads these fields as "real runtime" — the
same test-log-isolation caution PERF-4 §15 already flagged for a different field, now explicitly
extended to this milestone's own new fields.

## 20. Implementation allowlist (Phase 2 — NOT started in this Phase 1 milestone)

| Path | Change |
|---|---|
| New: `contracts/target_response_length_profile.py` | The `TargetResponseLengthProfile` literal + the soft-budget mapping (§16) |
| `core/target_response_policy.py` | New pure function `select_target_response_length_profile(...)`, alongside the existing stage-overlay functions — the single canonical producer |
| `core/target_composer_executor.py` (`_invocation()`) | Inject `response_length_profile`/soft-max into `response_directives_json`; add one new Composer system-policy rule describing the direct-answer → 2-4 facts → conditions → next-step outline shape (§4, §15's Variant E) |
| Wherever `answer_chars`/`composer_ms` are already logged (`app.py`, `orchestration/finalize_turn.py`) | Add the new observability fields (§19) as siblings, not replacements |
| Explicitly NOT in this allowlist | `core/target_response_verifier.py` (no Verifier policy change, §11/§18); `core/target_presentation_decision.py` (no coupling, §12); any price/offer resolution module (§9-10); Boundary; Ingress/Planner; any prompt/model/schema beyond the one additive Composer rule above; token streaming; Scoped FullContext; answer-cache/prewarm |

## 21. Acceptance matrix (Phase 2 — governance defines it now, does not implement it)

| # | Scenario | Expected profile / invariant |
|---|---|---|
| 1 | Simple FAQ (single narrow topic, no marketing, no price) | `simple_faq`; answer stays within 250-450 soft range in the common case |
| 2 | Generic FullContext micro-fact (e.g. one-line clinic fact) | `simple_faq`; short answer, no forced padding to hit a minimum |
| 3 | All-on-4 protocol overview | `standard_information`; protocol description not cut mid-explanation |
| 4 | All-on-6 protocol overview | `standard_information`; same as #3 |
| 5 | Bone graft FAQ | `standard_information` or `simple_faq` depending on topic breadth (§17 priority 8/9); no required fact dropped |
| 6 | Tomography own-scan FAQ | `simple_faq`; narrow factual answer |
| 7 | Direct price for one named service | `scoped_price` (`concrete_service_price`, no comparison aspect) |
| 8 | Broad implantation family price overview | `broad_price_overview` (`broad_family_price`); `max_price_anchors` overlay and the length soft-max coexist without conflict |
| 9 | Scoped one-tooth price | `scoped_price` (`scoped_family_price`) |
| 10 | Full-arch price | `scoped_price` (`scoped_family_price`, jaw=full scope) |
| 11 | Prosthetics comparison | `comparison_or_complex` (`"comparison" in aspects`); protocol differences preserved in full even if over soft-max |
| 12 | `no_public_price` answer | Profile per stage as usual; `approved_text` preserved verbatim regardless of budget (§10, §18) |
| 13 | Direct included/excluded question | `standard_information` if the inclusion/exclusion list is multi-item; list never truncated mid-item |
| 14 | Marketing `pain_fear` scenario | `marketing_concern`; selected marketing fact(s) preserved verbatim, budget yields if needed |
| 15 | Marketing `result_reliability` scenario | `marketing_concern` |
| 16 | Marketing `time` scenario | `marketing_concern` |
| 17 | Consultation-value bleed on an exact-service path (`allow_consultation_close=True`) | Profile selection reads `allow_consultation_close` but never writes it; consultation-close content unaffected by budget |
| 18 | Generic FAQ without consultation-value bleed | `allow_consultation_close` stays `False`; length-profile selection does not itself flip this flag in either direction |
| 19 | Scope choice menu (governed UI scope buttons alongside the answer) | Button count (`CHOICE_MENU_MAX=4`) unaffected by the answer's length profile (§12) |
| 20 | Stage clarification | `clarification_concise`; ≤250 chars soft target, `stage_clarify_concise`/`answer_mode` overlay (§1) coexists cleanly |
| 21 | Typed UI click (governed action context present) | Action context only routes via `response_stage` (§6/§17); no separate length path for typed-UI turns |
| 22 | Contacts structured-capability path (bypasses Composer/Verifier per PERF-2 precedent) | No length profile applies — structured capability answers are untouched by this milestone entirely |
| 23 | Service-availability structured-capability path | Same as #22 — untouched |
| 24 | A required exact fact's text alone exceeds the profile's soft-max | Correctness wins (§18); `over_soft_budget=True`, `required_content_override` recorded; no retry, no fallback, no route change |
| 25 | Multiple required numeric offers in one answer | Likely over soft-max; all offers' numeric claims still verified by the existing grounding check (§9) unchanged |
| 26 | Valid `source_identity` and follow-up selection | Unaffected by length-profile selection or budget overage — orthogonal (§13-14) |
| 27 | CTA | Unaffected by length-profile selection or budget overage — architecturally separate (§14) |
| 28 | Missing/invalid profile input (e.g. spec fields absent) | Safe default `standard_information`, logged, never raises, never blocks (§18) |
| 29 | A valid, correct, over-soft-budget answer | Still materialized and returned to the user exactly as composed — over-budget is observability-only, never a block/discard (§18) |
| 30 | `/ask` vs. `/ask/stream` parity | Same profile and same soft-max computed for the same input regardless of transport — the producer reads only `TargetResponseSpec`/`TurnFrame` fields already identical on both paths, no SSE-worker-specific state involved |

## 22. PRE-CODE summary

- Governance-only Phase 1: this seam audit, `TASK.md` normative design, one new governance
  checker, and minimal doc syncs (`docs/FLAGS_AND_STATUS.md`, `docs/STRANGLER_ROADMAP.md`). No
  product code changed — nothing in `contracts/`, `core/`, or `app.py` has been modified.
- Confirmed by direct code reading, not assumed: today's Verifier is entirely length-blind (§11);
  today's only stage-conditional shape control is the `broad_family_price_compact`/`max_price_
  anchors` overlay pair (§1, §4); no dedicated answer-length mechanism or test exists anywhere
  (§1); CTA/presentation/followup channels are already architecturally decoupled from answer text
  (§12-14).
- Selected design: **Variant A (soft budget as a Composer directive) + Variant E (structured
  outline shape)** — never B alone, never C, never D on the normal path (§15).
- Single typed contract (`TargetResponseLengthProfile`, 7 values) and single canonical producer
  (`select_target_response_length_profile`, planned for `core/target_response_policy.py`,
  alongside its existing sibling overlay functions) — no second router, no new classifier, no
  regex/phrase list, no signal derived from the user's question length (§16-17).
- Profile-selection map defined entirely from existing structured fields (§17), with one boundary
  (`simple_faq` vs. `standard_information`) honestly flagged as needing a Phase 2 decision, not
  silently resolved here.
- Full never-touch invariant list cross-referenced to the exact existing enforcement mechanism
  for each (§18) — correctness always wins over budget, with zero retry/fallback/route-change.
- Fail-open semantics fully specified (§18, §21 rows 24/28/29): over-budget never blocks, missing
  profile defaults safely, this is explicitly **not** a new Verifier policy.
- Observability fields specified, reusing three already-existing fields (`answer_chars`,
  `completion_tokens`, `composer_ms`) and adding three new ones, with an explicit warning against
  mixing prewarm/fixture usage rows into future real-runtime aggregates (§0, §19).
- Offline baseline computed from existing local logs only, no LIVE call made for this milestone,
  with explicit honesty about what the current logs can and cannot show (§0).
- Exact Phase 2 implementation allowlist enumerated (§20) — narrow, four items plus explicit
  exclusions (Verifier, presentation decision, price/offer resolution, Boundary, Ingress/Planner,
  streaming, Scoped FullContext, prewarm — none touched).
- 30-scenario acceptance matrix (§21) covering every profile, every invariant, both structured-
  capability bypass paths, both transports, and the fail-open paths explicitly.
