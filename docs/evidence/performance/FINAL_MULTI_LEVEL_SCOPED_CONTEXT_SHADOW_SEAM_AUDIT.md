# FINAL_MULTI_LEVEL_SCOPED_CONTEXT_SHADOW (PERF-6) — Phase 1 seam audit

**Baseline:** `codex/stage-a` @ `c0dfde6` (`FINAL_CLIENT_PACK_CONTENT_DEDUP_AND_TOKEN_AUDIT` complete).
**NO PRODUCT IMPLEMENTATION / NO CLIENT-PACK CHANGE / NO LIVE / NO PROVIDER / NO NETWORK.**

This is a design document. Nothing under `clients/demo/**`, `core/`, `contracts/`, or `app.py` is
changed by this milestone. It designs a multi-level Scoped FullContext resolver and its shadow
(measurement-only) integration, to be implemented in a **separately owner-approved Phase 2**.

## 0. Baseline (from FINAL_CLIENT_PACK_CONTENT_DEDUP_AND_TOKEN_AUDIT, restated exactly)

- Cached FullContext corpus: **107,980 chars ≈ 26,995 tokens** (chars/4 estimate), 55 MD docs, sha256
  `758a64eb…`.
- Composer static prefix: **116,571 chars ≈ 29,142 tokens** (includes the full corpus once + 8,591
  chars of Composer-only system policy/template overhead).
- Verifier static prefix: **114,719 chars ≈ 28,679 tokens** (includes the full corpus once + 6,739
  chars of Verifier-only overhead).
- Client-pack-internal duplication found by that audit: only **~1,609 chars (~402 tokens)** of safe
  savings (offer `package` text repeated across brand-SKU siblings) — negligible.
- **The dominant cost is architectural, not duplication**: both Composer and Verifier each
  independently receive the entire 107,980-char corpus, every turn, regardless of how narrow the
  question is. This milestone's premise is testing whether a much smaller, level-scoped corpus
  subset would have been sufficient — without touching the real request path yet.

## 1. Producer → consumer map

| # | Layer | File(s) | Key fields | Relevance to scoping |
|---|---|---|---|---|
| 1 | `TurnFrame` | `contracts/turn_frame.py` | `service_id`, `topic`, `aspects`, `needs_clarification`, `marketing_scenarios`, `field_meta: TurnFrameMeta` (one `FieldMeta{confidence,provenance,status,error}` per axis + nested `PatientScopeFrameMeta`) | Raw understanding signals. Built once per turn by `core/turn_frame_from_raw.py::build_turn_frame_from_raw` from the turn planner's JSON, then optionally hydrated from session (`core/target_runtime_turn_frame_hydration.py`) and typed UI actions (`core/target_typed_ui_turn_frame.py`). |
| 2 | Session hydration / stale focus | `core/target_runtime_session.py`, `core/target_runtime_turn_frame_hydration.py`, `core/dialog_focus.py` | `TargetRuntimeSessionState.last_service_id/last_topic/service_focus_set_at_turn`, `is_service_focus_fresh()`, `read_age_guarded_service_focus()` | Staleness is **implicit**: age-guarded by `THRESHOLDS.follow_up.max_service_focus_turn_age` (`core/routing_loader.py`); once the turn-age exceeds it, the reader returns `None` — no explicit "stale" flag anywhere. Hydration only fires when `turn_frame.service_id is None` **and** the message is a detected contextual follow-up **and** focus is fresh — a genuinely new standalone question is never auto-narrowed. The resolver in this design must **reuse the already-hydrated `TurnFrame.service_id`**, never re-derive its own staleness logic. |
| 3 | `EffectiveScope` | `contracts/effective_scope.py`, `core/target_effective_scope.py`, `core/target_effective_scope_merge.py` | `extent`, `jaw`, `stage`, `topic`, `source` (`ui_action\|ui_stage_action\|a9_turn\|session\|unknown`), per-axis provenance | Patient-scope axes, not content-topic axes. Not a primary scoping signal for this design (no MD content varies by `extent`/`jaw`/`stage` alone) — noted for completeness, not used by the resolver. |
| 4 | `TargetResponseSpec` / response stage | `contracts/target_response_spec.py`, `contracts/target_response_stage.py` | `response_mode`, `service_id`, `response_stage`, `allowed_topics: tuple[str,...]` (deduped, validated), `required_fact_ids`, `required_components: tuple["content"\|"price"\|"doctors",...]`, `allow_marketing_facts`, `allow_consultation_close`, `allow_cta` | **This is the cleanest resolver input, not raw `TurnFrame`.** By the time a spec exists, ambiguity is already arbitrated (clarify/defer/medical_handoff already routed away from `answer`), `allowed_topics` is already a clean deduped tuple, and `required_*` are already the ground truth for completeness checks. Built once by `core/target_response_policy.py`. |
| 5 | Service catalog / content refs | `contracts/response_schema.py::TargetService` | `content_ref: str\|None` (single MD filename), `options[*].content_ref`, `aliases`, `family`, `roles` | **No service↔service or service↔comparison cross-ref field exists.** Confirmed by direct search: `comparison__*.md` files (5 in the demo pack) are referenced from **zero** places in `service_catalog.json` or `marketing.yaml` — they exist only as free-standing MD, reachable today solely via the always-full corpus. This is an honest gap (§ 12), not invented around. |
| 6 | Offers/facts/doctors/consultation | `contracts/response_schema.py` (`TargetOffer`, `TargetCommercialFact`), `contracts/doctor_schema.py`, `contracts/service_consultation.py` | — | Already service-exact-scoped by existing S22–S36 machinery (item 8 below); this design does not re-derive their closure, it **reads** the already-materialized closure. |
| 7 | Generic FullContext | `core/target_generic_fullcontext_content.py`, `core/target_fullcontext_content_package.py` | `generic_fullcontext_content_eligible()`, `is_fullcontext_content_only_spec()` | The `service_id=None`, `required_components=("content",)` path used for ordinary FAQ/info turns with no confirmed service. `evidence_blocks` is empty or near-empty (only an optional topic-scoped consultation fact) — the Composer answers from `CACHED_FULL_CONTEXT` alone. This is exactly the case the `topic`/`full` tiers of this design target. |
| 8 | Composer Request & cached corpus | `core/target_composer_request.py::materialize_target_composer_request`, `core/target_scoped_response_evidence.py::build_target_scoped_response_evidence`, `core/target_cached_full_context.py` | `TargetComposerRequest.evidence_blocks: tuple[TargetComposerEvidenceBlock,...]` (`kind∈{content,offer,doctor,commercial_fact,external_kb,external_doctor,consultation,clinic_contact}`, `ref`, `topics`, `fact_ids`, `text`, `must_preserve_exact`) | **This is the single most important existing seam for this design.** For the exact-service path (`_exact_sources`), `evidence_blocks` is *already* the full closure this milestone needs for `service_exact`: the service's `content_ref` section(s), marketing-selected `external_kb`/`external_doctor` refs, applicable offers, required/selected commercial facts, consultation value, and (if requested) clinic contact fields. **The `service_exact` resolver tier does not need new closure-computation logic — it reads this existing structure.** |
| 9 | Composer source identity | `core/target_composer_output.py::parse_composer_backend_output`, `contracts/target_composer_source_identity.py::TargetComposerSourceIdentity`, `core/target_response_verifier.py::_resolve_validated_source_identity` | `primary_content_ref`, `used_content_refs` | Composer's **self-claimed** refs are parsed with soft warnings only (no hard rejection) at output-parse time. **Existence validation happens later**, in the Verifier stage, via `core/target_presentation_source_identity.py::validate_used_content_refs` — any ref that doesn't resolve to a real file under `md_root` is **silently dropped**, not rejected fail-closed. This design's shadow comparison must use the **post-validation** `TargetComposerSourceIdentity` (after Verifier's drop step), never the raw Composer JSON, so an invented ref can never phantom-widen a shadow candidate (brief requirement: "Invented/invalid used refs не должны расширять пакет автоматически"). |
| 10 | Verifier evidence & required facts | `core/target_response_verifier.py::TargetSemanticVerifierInvocation`, `verify_target_composed_response` | `response_spec_json`, `primary_evidence_json` (same `evidence_blocks` Composer got), `candidate_text` | **The Verifier's grounding/fact checks are fully independent of `used_content_refs`.** Numeric-claim grounding (`target_verifier_numeric_ungrounded`) and strict-fact presence (`target_verifier_strict_fact_missing`, gated on `spec.required_fact_ids`) both operate on `evidence_blocks` + raw candidate text — never on which MD documents were "used." Only the *semantic* checks (`unsupported_clinic_claim` etc.) read the full `cached_full_context`, unconditionally, regardless of any future corpus scoping. **Conclusion: corpus-size scoping only ever affects the Composer's available *prose* to write from, never the Verifier's fact/grounding correctness** — which is exactly why this milestone's shadow design can measure corpus sufficiency without ever touching the Verifier. |

## 2. `field_meta.confidence` — trustworthiness finding

Confirmed by direct trace of the sole builder, `core/turn_frame_from_raw.py`:

- The **only** axis that ever receives a real, planner-sourced confidence number is `topic`, via
  `_confidence_from_raw(raw.get("topic_confidence"))` — i.e. whatever raw float the turn-planner LLM
  self-reported, clamped to `[0,1]`.
- Every other axis (`intent`, `aspects`, `service_id`, `followup_of`, `patient_scope.*`,
  `marketing_scenarios`, `needs_clarification`) gets a **hardcoded `confidence=0.0`** regardless of
  whether its `status` is `valid`/`defaulted`/`missing`/`invalid` — this is a placeholder, not a
  score.
- Session/UI-hydrated fields (`core/target_runtime_turn_frame_hydration.py`,
  `core/target_typed_ui_turn_frame.py`) hardcode `confidence=1.0` or `0.0` as constants tied to
  provenance, not to any measured accuracy.
- `core/dialog_focus.py`'s own `confidence` values (0.6–0.9) are likewise inline heuristic constants
  per source type, not calibrated against outcomes.
- No audit anywhere in this repo (A6/A7 topic-shadow audits included) measured *calibration*
  (does confidence=0.8 actually mean ~80% correct?) — those audits measured *coverage* (was the
  field populated at all), a different question.

**Decision (per task brief instruction):** this design does **not** introduce a numeric
`field_meta.confidence` threshold anywhere in the level-selection or widening rules. It uses only
the **categorical** `status` (`valid`/`defaulted`/`missing`/`invalid`) and structural presence
(`service_id is not None`, `allowed_topics` non-empty and taxonomy-valid), which are boolean/enum
facts already validated by existing Pydantic contracts, not self-reported scores.

## 3. Context-group data model comparison

| Option | Description | Verdict |
|---|---|---|
| **A — `target_response/context_groups.json`** | Explicit authored file: `{schema_version, groups: [{group_id, topics: [...], ...}]}` (example shape only; see brief). Validated per-client by `scripts/validate_client_pack.py` like every other `target_response/*` file. | **Selected (for a future Phase 2)** — explicit, client-portable, matches the existing `docs/CLIENT_PACK_AUTHORING.md` "one canonical file per concern" convention (`service_catalog.json`, `marketing.yaml`, `clinic_strategy.yaml`, …), and is the only option that gives an *auditable, versioned* authority for what belongs in a group. |
| B — group membership inside `service_catalog.json` | Add a `context_group_id`/`context_group_ids` field per service. | Rejected as the *sole* mechanism — a service can plausibly belong to more than one cross-cutting group (e.g. "tooth restoration" and "same-day protocols"), and groups may need topic-level members that are not 1:1 with a service (comparison docs, clinic-wide FAQ) — a flat per-service field can't express that cleanly. Could be a secondary index derived from A, not a replacement. |
| C — automatic neighboring by shared `topic`/refs only | No authored file; infer "groups" purely from MD `topic:` frontmatter co-occurrence or from marketing `ordered_amplifier_refs` overlap. | Rejected as the primary mechanism — confirmed by § 1 item 5 that **zero** authored cross-topic links exist today (comparison MD topic tags are single-topic, not group tags), so "automatic" inference would either produce nothing (honest, but then it's not really a `context_group` tier — it's just `topic`) or require inventing a similarity heuristic not asked for and not owner-approved. Explicitly out of scope: this milestone forbids embeddings/heuristic inference as a `context_groups.json` substitute. |
| D — hardcoded Python graph | A literal dict of `service_id -> [related_service_id, ...]` in code. | **Rejected**, as instructed — violates `docs/CLIENT_PACK_AUTHORING.md`'s single-canonical-file-per-client principle, is not portable to a new client, and duplicates data that belongs in the client pack. |

**Selected data model: A**, an explicit authored `target_response/context_groups.json`, validated
like every other target_response file, with `group_id`, `topics: tuple[str,...]`, and (future,
not decided here) possibly explicit `service_ids`/`content_refs` overrides. **Not created in
Phase 1** — this section only records the decision for a future, separately-owned milestone.

## 4. `TargetContextScopeDecision` — typed immutable contract (design only, not implemented)

```python
ContextScopeLevel = Literal["service_exact", "topic", "context_group", "full"]

class TargetContextScopeDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    level: ContextScopeLevel
    reason: str                                   # canonical short code, e.g. "service_exact_complete"
    service_id: str | None
    topic: str | None
    context_group_id: str | None
    included_content_refs: tuple[str, ...]         # whole MD document filenames (corpus swap unit)
    included_offer_ids: tuple[str, ...]
    included_fact_ids: tuple[str, ...]
    included_doctor_ids: tuple[str, ...]
    included_policy_sections: tuple[str, ...]       # e.g. ("contact.phone_display",)
    estimated_chars: int
    estimated_tokens: int                           # explicit chars//4 estimate, labelled as such
    package_fingerprint: str                         # sha256 hex, see § 10
    completeness_status: Literal["complete", "insufficient_widened", "full_required"]
    widening_reason: str | None                      # canonical code, e.g. "comparison_aspect_no_service_closure_ref"
```

No raw question/answer/SID/contact values anywhere in this contract — every field is either an
enum, a count, a hash, or a **reference/ID** (never the referenced text itself). One canonical
resolver function, e.g. `resolve_target_context_scope(spec, evidence_blocks, turn_frame, ...) ->
TargetContextScopeDecision` — never a second producer, mirroring the PERF-5
`select_target_response_length_profile` single-producer pattern already established in this repo.

## 5. Level selection rules

### `service_exact`

**Eligible only when** `spec.service_id is not None` (i.e. the already-arbitrated
`TargetResponseSpec`, not raw `TurnFrame.service_id` — this automatically excludes stale-session
narrowing, since `spec.service_id` is only ever set from a `TurnFrame.service_id` that already
passed the existing hydration/freshness gates in § 1 item 2).

**Closure = read directly from `TargetComposerRequest.evidence_blocks`** (§ 1 item 8), grouped by
`kind`:

- `content` / `external_kb` → document filename (strip `#anchor`) → `included_content_refs`
- `offer` → `included_offer_ids`
- `doctor` / `external_doctor` → `included_doctor_ids` (+ their `profile_ref` document)
- `commercial_fact` → `included_fact_ids`
- `consultation` → the consultation's own `content_ref` (already the service's MD, no new doc)
- `clinic_contact` → `included_policy_sections` (field names only, never values)

**"Связанные процедуры только по явным authored refs"**: today this closure only ever contains
refs that `evidence_blocks` already contains (marketing-selected `kb:`/`doctor:` amplifiers). It
**never** contains a sibling/comparison service's content, because no authored ref for that exists
(§ 1 item 5, § 12 gap). This is intentional per the brief's own instruction not to invent links.

### `topic`

**Eligible when** `service_exact` is unavailable or incomplete, and `spec.allowed_topics` is
non-empty and every member is a member of `load_client_topic_taxonomy(client_id)` (the existing,
already-deterministic, frontmatter-derived topic set — § "topic taxonomy" below). **Never derived
from raw text or regex** — `allowed_topics` is already a validated `TargetResponseSpec` field.

**Closure** = every MD document whose frontmatter `topic:` is in `spec.allowed_topics`, plus the
services whose `content_ref` document has that topic, plus their offers/facts/doctors (same
extraction as `service_exact`, applied per matched service), plus clinic-wide policy sections if
`"contacts"` is in `turn_frame.aspects`.

### `context_group`

**Eligible only when all of:** (a) a `context_groups.json` exists for the client (§ 3, not
created in Phase 1), (b) `topic` closure was attempted and flagged `insufficient_widened`, (c) a
structured signal indicates single-topic insufficiency — the only such signal identified in the
current architecture is **`"comparison" in turn_frame.aspects`** combined with the Composer's
(validated) `used_content_refs` containing a document outside the `topic` closure just computed.
**No new LLM call, no second router** — this is a pure post-hoc set-membership check against
already-computed data.

**Honest gap:** on the current demo pack, condition (a) is never true — `context_groups.json` does
not exist and this Phase 1 does not create it. **The shadow will therefore record zero
`context_group` activations on the demo pack until a future, separately-approved milestone
authors that file.** This is stated here rather than silently omitted, per the brief.

### `full`

**Safe fallback**, used whenever: `spec.service_id` and `spec.allowed_topics` are both
absent/invalid; more than one unrelated topic is structurally implicated with no group data to
resolve it; `context_group` is not determinable; package completeness (§ 6) cannot be proven;
a required source (offer/fact/doctor/content) is missing from every narrower closure; the resolver
raises any exception (fail-closed to `full`, never to an error the user could see); or any
ambiguity that cannot be resolved by the structural rules above. **`full` is not an error — it is
the same content the real Composer/Verifier already receive today**, so a shadow decision of `full`
is definitionally always `shadow_hit` (the real corpus is by definition ⊇ any narrower one).

## 6. Deterministic completeness check (pre-Composer, no product effect)

Before the (design-only, future) resolver would hand a level to a shadow candidate, it checks,
using only data already computed for the real turn (never a second Composer/Planner call):

1. Every `spec.required_fact_ids` has a matching `commercial_fact` block in the candidate closure.
2. Every `spec.required_components` (`content`/`price`/`doctors`) has ≥1 matching block kind.
3. `spec.service_id`'s `content_ref` (if `service_id` set) resolves inside `included_content_refs`.
4. If `turn_frame.aspects` contains a `contact_*` aspect, the relevant `clinic_policies.yaml`
   field is in `included_policy_sections`.
5. If `spec.allow_consultation_close`, the exact service/option's consultation value (if any) is
   included.
6. If `spec.allow_marketing_facts`, the marketing-selected fact/amplifier refs are included (they
   already are, by construction, since they come from the same `evidence_blocks`).
7. If `"comparison" in turn_frame.aspects`, at least one comparison-shaped source is included (see
   § 5 `context_group` gap — today this can only be satisfied by widening to `full`).
8. Governed UI action sources (`action_context`) are included when `action_context is not None`.

**Widening** on any failed check is deterministic and local:
`service_exact → topic → context_group → full`, evaluated once, in order, with **no repeated
Composer call at any step** — the real Composer is called exactly once, exactly as today; only the
*shadow candidate's level* changes as checks fail.

## 7. Shadow behavior (design; not implemented in Phase 1)

1. **Collect locally.** After the real `TargetComposerRequest` is materialized (§ 1 item 8) — i.e.
   after `spec`/`evidence_blocks` already exist for the real turn — a shadow-only function computes
   a `TargetContextScopeDecision` using §§ 5–6. This runs as an **additive, side-effect-free call**
   in the same place PERF-4's speculative Planner hook was added (`on_llm_path`-style additive hook)
   — never replacing an argument the real Composer/Verifier invocation receives.
2. **Never touch the real request.** `TargetComposerInvocation.cached_full_context` and
   `TargetSemanticVerifierInvocation.cached_full_context` remain the full corpus, unconditionally,
   in Phase 2 shadow mode. The shadow decision is computed **and discarded from the request path**
   — it only ever reaches a log/observability sink (§ 9).
3. **Compare after verification** (not before — this needs the real, validated output):
   - `primary_content_ref`/`used_content_refs` from the **post-validation**
     `TargetComposerSourceIdentity` (§ 1 item 9);
   - the offers/facts/doctors actually present as `must_preserve_exact` blocks the Verifier checked
     (`evidence_blocks` again — same source, so this is definitionally always available, not a new
     lookup);
   - `spec.required_fact_ids`/`required_components` (the ground truth for "was it complete").
4. **Record**, never gate or retry:
   - `shadow_hit` — every validated `used_content_ref` document falls inside
     `included_content_refs`, and all required facts/components were present.
   - `shadow_miss` — at least one validated used ref or required source falls outside the
     candidate closure.
   - `shadow_would_widen` — the deterministic algorithm (§ 6) itself already decided to widen
     before the real answer was even known (a *predicted* insufficiency, independent of the
     post-hoc `shadow_miss` comparison — the two are logged as separate booleans since they answer
     different questions: "did our rule pre-emptively widen" vs. "would it have been right not to").
   - `missing_source_classes` — which of `content`/`offer`/`fact`/`doctor`/`policy` caused a miss.
   - `estimated_reduction_tokens` — `full_context_estimated_tokens − candidate.estimated_tokens`.

**Shadow miss semantics (exactly as specified):** never blocks the response, never triggers a
retry, never changes the route, never changes the UI/buttons. It is a **log-only** signal. No
second LLM/Composer/Verifier call exists anywhere in this design — the shadow candidate is built
entirely from data the real turn already produced.

## 8. Source comparison — four distinct sets, never conflated

| Set | Source | Used for |
|---|---|---|
| **Sent to model** | `TargetComposerInvocation.cached_full_context` (always the full 107,980-char corpus, unconditionally, in shadow mode) | Sizing the "no scoping" baseline (`full_context_estimated_tokens`) |
| **Composer sidecar claim** | Raw `source_identity.used_content_refs` from `parse_composer_backend_output`, **before** validation | Never used directly for shadow comparison (see § 1 item 9) — an invented ref here must never count toward "sufficiency" |
| **Required (ground truth)** | `spec.required_fact_ids`, `spec.required_components`, `evidence_blocks` `must_preserve_exact` blocks | The actual completeness bar — a package is not "complete" merely because `primary_content_ref` is inside it; every required structured fact must be too |
| **Verifier-checked** | The same `evidence_blocks` the Verifier's deterministic stage validated against (`target_verifier_strict_fact_missing`/`target_verifier_numeric_ungrounded` outcomes) | Cross-check that the "required" set in this design matches what the existing Verifier already enforces — no new correctness bar is invented |

A package is only ever marked `shadow_hit` when the **post-validation, Verifier-consistent** sets
(columns 3 and 4) are both satisfied — never column 2 alone.

## 9. Shadow observability (design; anonymized, no content)

Fields (all counts/enums/hashes/durations — never document text, `question`, `answer`, `SID`, or
contact values):

`scope_level`, `scope_reason`, `context_group_id` (usually `null` — § 5 gap), `included_doc_count`,
`included_offer_count`, `included_fact_count`, `included_doctor_count`, `estimated_tokens`,
`full_context_estimated_tokens`, `estimated_reduction_tokens`, `completeness_status`,
`widening_steps` (ordered list of levels attempted, e.g. `["service_exact", "topic"]`),
`shadow_hit` (bool), `shadow_would_widen` (bool), `missing_source_classes` (list of the four class
names in § 8), `resolver_ms`, `package_fingerprint`.

**Timing:** reuses the existing `core/turn_timing.py::timed_stage` context manager exactly as
`resolver.py`'s legacy `with timed_stage("resolver_ms"):` already does (§ "PERF-0" below) — a
future shadow resolver would use a **distinct** mark name, `scoped_context_shadow_ms`, so it never
collides with the legacy resolver's own `resolver_ms` key in the same per-request timing bucket.
No `stage_start`/`stage_end` wiring needed (that vocabulary is reserved for real pipeline stages);
`timed_stage` alone, exactly like the two existing side-timer precedents (`resolver.py`,
`ingress_gate.py`), is sufficient and request-`ctx`-scoped, so it is safe to add without touching
the real stage-status contract.

## 10. Context caching preparation — `package_fingerprint` identity (design only, no caching)

`package_fingerprint = sha256("|".join([client_id, client_pack_content_hash, schema_version,
level, service_id_or_topic_or_group_id, sorted(included_content_refs + included_offer_ids +
included_fact_ids + included_doctor_ids), context_schema_version]))`.

- `client_pack_content_hash` — reuses the existing `TargetCachedFullContext.sha256` (already
  computed, already proven stable/deterministic by the PERF-6 baseline audit's arithmetic checks)
  as the pack-version component, exactly the same pattern `core/target_prompt_cache_prewarm.py`
  already uses for its own `corpus_sha256` fingerprint component — no second hashing scheme
  invented.
- **Nothing is cached in Phase 1.** This section only specifies what a stable identity *would* look
  like for a future caching milestone, per the brief's explicit "только спроектировать stable
  identity" instruction.

## 11. Estimated package sizes on the current demo pack (real data, no product change)

Computed directly from the committed `docs/evidence/client_pack/demo_content_token_inventory.json`
per-doc sizes and each MD file's `topic:` frontmatter (deterministic, reproducible from files
already in the repo):

| Level example | Docs | Chars (incl. corpus markers) | ~Tokens (chars/4) | vs. full (107,980 / ~26,995) |
|---|---:|---:|---:|---|
| `service_exact` — one service content doc alone (e.g. `implantation__service__classic.md`) | 1 | ~1,788 | ~447 | ~98% smaller |
| `service_exact` — with 1–2 marketing-selected amplifiers + doctor profile (typical `cost`/`pain_fear` scenario) | 3–5 | ~4,000–8,000 | ~1,000–2,000 | ~92–96% smaller |
| `topic=implantation` (28 of 55 docs — the dominant topic) | 28 | 54,137 | 13,534 | ~50% smaller |
| `topic=prosthetics` | 6 | 14,388 | 3,597 | ~87% smaller |
| `topic=clinic` | 7 | 8,196 | 2,049 | ~92% smaller |
| `topic=doctors` | 7 | 7,270 | 1,817 | ~93% smaller |
| `topic=treatment` | 3 | 4,151 | 1,037 | ~96% smaller |
| `topic=extraction`/`periodontology`/`whitening`/`orthodontics` (1 doc each) | 1 | ~1,650–2,900 | ~410–720 | ~97–98% smaller |
| `full` | 55 | 107,980 | 26,995 | baseline |

**Reading:** for the ~28/55 (51%) of the demo pack's own content mass that is `implantation`
topic, `topic`-level scoping alone only halves the corpus; for every other topic it is a much
larger win (87–98%). `service_exact` is dramatically smaller than either — the real opportunity is
concentrated there, **if** the completeness checks in § 6 hold up in practice, which Phase 2's
shadow measurement (not this design) must prove before any real switch.

## 12. Honest gaps in the current architecture (not fixed here)

1. **No authored service↔service or service↔comparison cross-refs.** Confirmed zero references
   from `service_catalog.json`/`marketing.yaml` to any `comparison__*.md` file. `service_exact`
   structurally cannot include comparison content today; the only paths to it are `topic` (if the
   compared services share one topic, as they do in the demo pack) or `full`.
2. **`context_group` has no usable signal today.** No `context_groups.json` exists, and no proxy
   signal (shared aliases, marketing scenario overlap) reliably substitutes for authored group
   membership without inventing a similarity heuristic this milestone forbids. The shadow will
   observe **zero** `context_group` activations until a future milestone authors that file.
3. **`field_meta.confidence` is not usable as a threshold** (§ 2) — only `topic` gets a real
   planner-sourced number, and it is uncalibrated; every other axis is a hardcoded constant. This
   design uses only categorical `status`, never a confidence cutoff.
4. **Session staleness is implicit**, not an explicit signal (§ 1 item 2) — this design relies on
   the existing age-guard already having run by the time `spec.service_id` exists, rather than
   re-implementing staleness detection, which would be a second, possibly divergent, staleness
   policy.
5. **Cross-topic multi-aspect questions** (acceptance scenario 27/28) have no structural
   resolution today beyond falling to `full` — this is the correct, safe behavior per § 5, not a
   defect to silently paper over.

## 13. Governance acceptance matrix (50 scenarios, design-only — no live harness built yet)

Each row states the **expected shadow-only outcome** a future Phase 2 implementation must reproduce
under the rules in §§ 5–8. None of these are run in Phase 1; this is the acceptance contract for
Phase 2's own offline test matrix.

| # | Scenario | Expected level | Expected `completeness_status` |
|---|---|---|---|
| 1 | Exact service FAQ (`service_id` set, plain content question) | `service_exact` | `complete` |
| 2 | Exact service price (`required_components=("price",)`) | `service_exact` | `complete` |
| 3 | Exact service comparison (`"comparison" in aspects`, same-topic comparison doc exists) | `topic` (widened from `service_exact`) | `insufficient_widened` |
| 4 | Broad implantation (`service_id=None`, `allowed_topics=("implantation",)`) | `topic` | `complete` |
| 5 | Broad prosthetics | `topic` | `complete` |
| 6 | Broad whitening (1-doc topic) | `topic` | `complete` |
| 7 | All-on-4 exact | `service_exact` | `complete` |
| 8 | All-on-6 exact | `service_exact` | `complete` |
| 9 | One-stage implantation exact | `service_exact` | `complete` |
| 10 | Bone graft exact | `service_exact` | `complete` |
| 11 | Sinus lift exact | `service_exact` | `complete` |
| 12 | Tomography availability (structured, `service_id` set) | `service_exact` | `complete` |
| 13 | Tomography price (price-only offer, no `content_ref` required per `FINAL_PRICE_ONLY_SOURCE_SUFFICIENCY_CONVERGENCE`) | `service_exact` | `complete` |
| 14 | Tomography own-scan FAQ (`diagnostics__service__tomography.md` content) | `service_exact` | `complete` |
| 15 | `no_public_price` service (`bone_graft`) | `service_exact` | `complete` |
| 16 | Marketing `pain_fear` concern (implantation) | `service_exact` (amplifiers already in `evidence_blocks`) | `complete` |
| 17 | Marketing `time` concern | `service_exact` | `complete` |
| 18 | Marketing `result_reliability` concern | `service_exact` | `complete` |
| 19 | Consultation-value exact service/option | `service_exact` | `complete` |
| 20 | Generic FAQ without consultation bleed (`service_id=None`, no service match) | `topic` if `allowed_topics` usable, else `full` | `complete` / `full_required` |
| 21 | Clinic contacts (`contacts` aspect) | `service_exact` or `topic` + `included_policy_sections` non-empty | `complete` |
| 22 | Clinic-wide doctors (no exact service) | `topic=doctors` | `complete` |
| 23 | Service-specific doctors | `service_exact` | `complete` |
| 24 | Scope UI click (`action_context` governed) | `service_exact` (action context source included) | `complete` |
| 25 | Stage UI click | `service_exact` | `complete` |
| 26 | Broad price with scope choices (`broad_family_price`/`scoped_family_price` stage) | `topic` | `complete` |
| 27 | Multi-aspect question (e.g. price + pain, same service) | `service_exact` | `complete` |
| 28 | Cross-topic comparison (implantation vs. prosthetics option) | `full` (§ 12 gap #1) | `full_required` |
| 29 | "Хочу восстановить зубы, но не знаю как" (no service, ambiguous) | `full` (no confirmed topic/group) | `full_required` |
| 30 | Missing service + usable topic | `topic` | `complete` |
| 31 | Missing service and topic | `full` | `full_required` |
| 32 | Invalid `service_id` (fails catalog lookup) | `full` (fail-closed, never trust an invalid id) | `full_required` |
| 33 | Stale session service + new standalone topic | `topic` (session service never inherited — § 1 item 2) | `complete` |
| 34 | Missing required content ref (offer-only service, e.g. tomography price path) | `service_exact` still valid — content not required per `required_components` | `complete` |
| 35 | Missing required offer (offer expected but absent from bundle) | `full` (fail-closed) | `full_required` |
| 36 | Missing required fact (`required_fact_ids` has an id not in `evidence_blocks`) | `full` (fail-closed) | `full_required` |
| 37 | Unknown context group id referenced (future-proofing; not reachable today, § 5 gap) | `full` | `full_required` |
| 38 | Resolver exception (any unexpected structural error) | `full` (fail-closed, never surfaced to the user) | `full_required` |
| 39 | Generic FullContext fallback path (§ 1 item 7) | `topic` if `allowed_topics` usable, else `full` | `complete` / `full_required` |
| 40 | Lead/situation/terminal route (`clarify`/`defer`) | resolver not invoked (shadow only applies to `answer`/`medical_handoff`) | n/a |
| 41 | Source identity `primary_content_ref` inside candidate closure | `shadow_hit=true` | n/a (comparison outcome, not level) |
| 42 | Used secondary source absent from candidate closure | `shadow_miss=true`, `missing_source_classes=["content"]` | n/a |
| 43 | Required numeric source (offer) absent from candidate closure | `shadow_miss=true`, `missing_source_classes=["offer"]` | n/a |
| 44 | Invalid/invented ref in Composer's raw claim, dropped by Verifier validation | ignored — never counted in `shadow_miss` (§ 1 item 9, § 8) | n/a |
| 45 | Zero additional LLM calls made anywhere in the shadow path | asserted structurally (design has no LLM call in §§ 5–9) | n/a |
| 46 | `/ask` and `/ask/stream` output byte-identical with/without shadow enabled | asserted by design (§ 7.2 — shadow never touches the real request) | n/a |
| 47 | Existing buttons/CTA unchanged | asserted by design (shadow never reaches presentation layer) | n/a |
| 48 | PERF-5 response-length profile unchanged | asserted by design (shadow reads, never writes, `TargetComposerRequest`) | n/a |
| 49 | Token reduction estimate arithmetic (`full_context_estimated_tokens − candidate.estimated_tokens == estimated_reduction_tokens`) | arithmetic identity, testable offline | n/a |
| 50 | `package_fingerprint` stability (same inputs → same hash across two resolver calls) | deterministic, testable offline | n/a |

## 14. Phase 2 implementation allowlist (not started; for a future, separately owner-approved milestone)

- `contracts/target_context_scope_decision.py` — the typed contract in § 4. **Does not exist.**
- `core/target_context_scope_resolver.py` — the single canonical resolver (§§ 5–6). **Does not exist.**
- `core/target_context_scope_shadow.py` — the shadow comparison/observability producer (§§ 7–9).
  **Does not exist.**
- An additive hook point in `core/target_composer_executor.py`/`core/target_response_verifier.py`
  call sites that invokes the shadow resolver **after** the real invocation is built, discarding its
  result from the real request (mirrors PERF-4's `on_llm_path` additive-hook pattern — never
  replacing an existing argument). **Does not exist.**
- `clients/demo/target_response/context_groups.json` (§ 3) — a **separate**, even-later milestone;
  not part of the Phase 2 scoped-context-resolver allowlist above.
- Explicitly **NOT** in this allowlist: any change to `core/target_composer_request.py`'s real
  `cached_full_context` argument; any change to `core/target_response_verifier.py`'s invocation;
  any caching implementation (§ 10 is identity-design only); any embeddings/vector/RAG code.

## 15. Test commands (for the PRE-CODE gate of this Phase 1 commit)

```powershell
python -m pytest tests/test_final_multi_level_scoped_context_shadow_governance.py -q
python -m pytest tests/test_final_client_pack_content_dedup_and_token_audit_governance.py -q
python scripts/validate_client_pack.py --client-id demo
python scripts/validate_client_pack.py --path clients/_template --scaffold
python -m pytest tests/test_target_cached_full_context.py tests/test_target_composer_request.py tests/test_target_composer_executor.py tests/test_target_response_verifier.py -q
git diff --check
python -m pytest tests/ --collect-only -q
```

## 16. STOP conditions

**STOP before any Phase 2 implementation** — nothing in §§ 4, 5–9, 10, 14 is created by this
commit. Required before Phase 2 starts:

- owner GO on this design (contract shapes, level rules, widening algorithm);
- a separate governance TASK for the shadow resolver implementation itself;
- a separate, later governance TASK for `context_groups.json` (§ 3), authored and validated per
  client before any `context_group` tier can ever activate;
- no real switch of Composer/Verifier onto a scoped corpus is authorized by this document at all —
  that would be a **third**, still-later milestone, contingent on the shadow measurement (once
  implemented and run) actually proving high `shadow_hit` rates.
