# Response Contract — one-call architecture

**Status:** owner-approved target contract (RESPONSE-CONTRACT-1 + ONE-CALL-ARCHITECTURE-1)
**Baseline:** `14de4a9a051dbf625acbdfc35b37392a5919e623`
**Scope:** target one-call path; does not require immediate runtime cutover.
**Architecture canon:** `docs/ONE_CALL_ARCHITECTURE.md` (flow order, `ComposerInputContext` / `ComposerDecision`, authority boundaries).

---

## 1. Terminology

| Term | Meaning |
|---|---|
| **Target FullContext Product Runtime (TFC)** | Legacy multi-call product stack reachable when the old branch is active (`SALES_ONE_PLUS_ON=0` at config default). Ingress/planner + Composer + Verifier + separate widget materializer. |
| **Full Context Strategy (FC)** | Context volume strategy for one-call Composer: full prepared MD corpus passed into a single call. Compared with curated/hybrid variants in experiments. |
| **Hybrid Strategy** | Future compact-context selection with Full Context fallback. Uses the **same** lower pipeline as FC — no separate renderer. |

**Target free-text path (FC and Hybrid share lower pipeline):**

```text
ComposerInputContext
→ ONE Composer call (one provider call)
→ ComposerDecision
→ deterministic scope/session merge
→ applicability filter + clinic strategy ranking
→ response-plan materialization
→ ResolvedResponsePlan
→ TextRenderer
→ UIProjection
```

See `docs/ONE_CALL_ARCHITECTURE.md` for full flow and chicken-and-egg resolution.

**Legacy note:** current unwired WIP still names `PreComposerPlan` before Composer; that premature semantic selection is **migration debt** on free-text turns.

Separate Hybrid renderer is **forbidden**. Permanent old/new runtime fallback is **forbidden**.

---

## 2. Approved architecture decisions

### 2.1 One model call

On a normal one-call turn:

```text
exactly one Composer LLM call
```

Forbidden additional LLM calls for: classification, price check, warranty detection, sanitizer, marketing selection, final text editing.

ADMIN, contacts, and local terminal cases may finish without LLM when the route plan allows.

### 2.2 Owners

| Owner | Responsibility |
|---|---|
| **Model** | Natural `patient_text`; structured request semantics |
| **Code** | Service/offer selection; canonical price and unit; required offer conditions; commercial fact eligibility and roles; promo/amplifier limits; ordering; session delta; UI projection |

**`TextRenderer`** is the **only** owner of final visible text.

After `TextRenderer`, no code may append or change: price, warranty, installment, tax deduction, promo, service value, amplifier, commercial CTA.

**`UIProjection`** does not edit visible text and does not re-select facts.

---

## 3. PreComposerPlan (minimum contract)

Required fields/groups:

- `client_id`
- **route authority** (constraints, not preselected semantic route on free-text turns)
- session/history context (continuation only, not fact authority)
- active service / topic
- selected `service_id`
- selected offer or offers
- canonical amount / currency / unit
- closed **required offer condition IDs**
- applicable commercial fact IDs
- `explicit_only_fact_ids` (e.g. `implant_warranty`)
- promo candidates
- automatic amplifier candidates
- service value candidate
- caps (promo, amplifier, service value)
- reserved code-owned blocks
- values forbidden inside model `patient_text`
- intended block order
- context strategy metadata (FC vs Hybrid) — **no separate renderer**

### 3.1 Route authority (ROUTE-AUTHORITY-1)

On ordinary free-text turns, `PreComposerPlan` carries **route constraints**, not a preselected semantic route:

| kind | when | Composer |
|---|---|---|
| `composer_selected` | patient free-text | required once; may return any of five closed pairs |
| `deterministic_bypass` | structured UI/non-language event | forbidden (`ComposerResult=None`) |

Closed Composer-selected pairs: `ANSWER+standard`, `ANSWER+contacts`, `ADMIN+standard`, `ADMIN+medical_terminal`, `CLARIFY+standard`.

`scope` (service/topic/clinic) is independent from `route`. Code must not choose route from patient text, keywords, regex, service detection, or `last_service_id`.

No semantic regex classification of Russian text before Composer.

---

## 4. Composer contract

### 4.1 ONE-CALL-ARCHITECTURE-1 — target `ComposerDecision`

Governance checkpoint ONE-CALL-ARCHITECTURE-1 fixes the authoritative order. Full semantics: `docs/ONE_CALL_ARCHITECTURE.md`.

**Pre-call (`ComposerInputContext`):** static instructions + current-client FullContext corpus + policy authority + normalized session context + typed recent history + current question. Must **not** preselect final scope, service, offers, price plan, requested facts, or free-text route. Policy sidecar declares `price_handling: "code_owned_after_decision"` only — no price amounts, currencies, offer IDs, or canonical price display before Composer.

**Post-call (`ComposerDecision`) — minimum fields:**

| Field | Authority |
|---|---|
| `route`, `mode` | Composer (closed pairs) |
| `patient_text` | Composer natural prose; not price/facts/contacts |
| `service_reference_kind` | Composer; closed: `none` / `explicit_current` / `active_session` |
| `option_reference_kind` | Composer; closed: `none` / `shown_options` — semantic reference to previously shown options, not a new shortlist |
| `topic_id` | Composer; allowed client topic ID or `null` (key required, value nullable) |
| `explicit_service_id` | Required when `explicit_current`; `null` for `none` / `active_session` |
| `requested_aspect_ids` | Composer; closed `contracts.answer_plan.AspectKind` values |
| `patient_situation` | Composer describes axes; code selects treatment/services |
| `requested_fact_ids` | Composer; explicit requests only |
| `source_identity` | Diagnostic attestation only; optional/nullable |

**Not in target output:** `price_text`, `recommended_service_ids`.

**`service_reference_kind`:** session follow-up («А сколько стоит?» after service discussion) uses `active_session` with `explicit_service_id=null`; code validates `active_session_service_id`. Topic switch uses `none`. Explicit name in current message uses `explicit_current` with non-null `explicit_service_id`.

**`topic_id`:** nullable; missing topic is not an error and does not alone imply CLARIFY. Scope derivation: valid `explicit_current` → service scope; validated `active_session` → service scope; else non-null `topic_id` → topic scope; else clinic scope.

**`requested_aspect_ids`:** exactly reuses closed `AspectKind` (`price`, `payment`, `warranty`, `pain`, `included`, `duration`, `comparison`, `stages`, `overview`, `contacts`, `contact_phone`, `contact_address`, `contact_parking`, `contact_hours`, `contact_whatsapp`, `service_availability`). No aliases; `composition` ≠ `included`.

**Service recommendations:** code ranks services → typed `ServiceOptionsBlock` in frozen plan (max 3 options). Composer must not list/rank in `patient_text`. Terminal routes forbid service options. No duplicate with price block variants.

**Shown-options reference:** `option_reference_kind=shown_options` refers to a code-confirmed `ShownServiceOptionsSnapshot` (finalized plan only — not ranked shortlist). Comparison/price candidates are limited to that snapshot; without a fresh snapshot the path emits diagnostics and does not invent alternatives.

**Reference vs applicability:** `reference_service_id` is conversational subject, not recommendation. `compatible` / `unknown` / `conflict` describe catalog-axis fit; `false` from applicability filter alone is not `conflict`.

**Requested fact display permission:** optional `requested_display_policy` on facts authorizes informational display without a concrete service. Resolver and post-Composer projection share `evaluate_requested_fact_display()`. Real `clients/**` metadata is not yet authored in this checkpoint.

**Price:** intent via `requested_aspect_ids` (e.g. `["price"]`); canonical price block is code-owned. `price_text` and `model_price_text` are **migration debt**.

**Facts:** single source `facts.json` with independent projections (requestable inventory, promo, automatic amplifiers). Requestable inventory does not depend on automatic marketing selection.

**Forbidden:** semantic planner before Composer; semantic verifier after Composer; analyzing `patient_text` to recover IDs, topic, service, situation, price, or session delta.

### 4.0 COMPOSER-CONTRACT-1 (historical unwired WIP — superseded, not implementation target)

> **Historical note:** isolated six-key schema from an earlier checkpoint. **Superseded** by §4.1 `ComposerDecision`. Retained for audit of existing unwired Python WIP only. Do not implement new work against this schema.

Historical unwired JSON schema — exactly six top-level keys:

```json
{
  "route": "ANSWER",
  "mode": "standard",
  "patient_text": "Естественный ответ пациенту.",
  "price_text": null,
  "requested_fact_ids": [],
  "source_identity": {
    "primary_content_ref": "clinic__info__consultation.md",
    "used_content_refs": ["clinic__info__consultation.md"]
  }
}
```

Five core response fields (`route`, `mode`, `patient_text`, `price_text`, `requested_fact_ids`) are mandatory without defaults. `source_identity` is mandatory in the published schema but fail-open at runtime: missing/invalid identity becomes `None` with a typed provenance warning; core response continues.

`source_identity` is model-reported provenance attestation only. It does not choose FullContext/Hybrid (`PreComposerPlan.context_strategy` is code-selected), does not prove which corpus was passed, and is not fact authority.

Policy sidecar from `PreComposerPlan` is **not** a complete Composer prompt. Future full input composition:

```text
static Composer instructions
+ selected model corpus/context
+ current user message
+ recent dialogue history
+ serialized plan-derived policy sidecar
```

Isolated chain (not production-wired):

```text
raw JSON
→ parse_response_plan_composer_json
→ ParsedComposerEnvelope
→ adapt_composer_envelope_to_plan
→ AdaptedComposerOutput
   ├─ ComposerResult  → resolve_response_plan
   ├─ TargetComposerSourceIdentity | None  (not passed to resolver)
   └─ provenance warnings
```

Parser is plan-agnostic. Adapter enforces route authority and plan `allowed_route_modes`. Resolver receives only `ComposerResult`.

**Material authority boundary (COMPOSER-CONTRACT-1 correction pass 2):** `ResponsePlanAdapterMaterialAuthority.bound_package` is a contract-owned structural view (`ResponsePlanAdapterBoundPackage`), not `Any` or unchecked `object`. Runtime validation requires:

```text
bound_package
├── spec
├── package
│   ├── materials
│   ├── plan
│   ├── selected_followups
│   └── navigation_followups (tuple; empty when absent)
└── selected_cta_key (str | None)
```

`_validate_package_coherence()` in production adapter remains authority for semantic spec/materials/plan coherence. The contract boundary rejects invalid shape before coherence checks.

**Policy sidecar strictness:** public sidecar types use `extra="forbid"`, `frozen=True`, `strict=True`. `RequestableFactDescriptor` enforces applicability matrix (clinic_wide / topic_scoped / service_scoped). `RoutePolicyEntry` purpose and `code_owned_visible_response` must match the closed route/mode matrix. `route_policy_entry()` is the canonical builder for route policy entries.

**Builder integration note:** structural contract fixtures may validate adapter boundaries offline. Actual concrete bound-package builders (`assemble_target_fullcontext_*`, etc.) remain an integration boundary when import chains require `config.py`; shim tests must not be named or reported as real builder integration.

Canonical requested-facts field:

```text
requested_fact_ids
```

(`direct_fact_ids` exists in legacy runtime only; target contract replaces it. No permanent compatibility layer.)

**Target (§4.1)** Composer returns: `route`, `mode`, `patient_text`, `service_reference_kind`, `topic_id` (nullable), `explicit_service_id`, `requested_aspect_ids` (`AspectKind`), `patient_situation`, `requested_fact_ids`, optional `source_identity`. No `price_text`.

**Historical WIP (§4.0)** documents superseded six-key schema including `price_text` — not an implementation target.

Rules:

- `patient_text` = natural explanation only
- code-owned exact commercial blocks are **not** duplicated in `patient_text`
- `requested_fact_ids` = facts the patient **directly asked about**
- catalog presence alone does **not** make a fact requested
- price intent via `requested_aspect_ids` (e.g. `["price"]`); canonical price is code-owned (§4.1). Legacy `price_text` / `model_price_text` — migration debt only
- ADMIN: no selling `patient_text`
- CLARIFY: no commercial catalog
- Composer does **not** choose automatic promo/amplifiers
- Composer does **not** assign final visible role

**Explicitness:** structured `requested_fact_ids` from Composer. Code validates ID eligibility and role; it does **not** add language regex. Wrong requested ID = **model-contract violation**, not automatic promo/amplifier role.

---

## 5. ResolvedResponsePlan (minimum contract)

After Composer, code must:

- validate route/mode
- validate `requested_fact_ids` (catalog, client, dates, service applicability, offer scope)
- allow `explicit_only` facts only as `requested_fact`
- assign exactly **one** final role per fact
- resolve role conflicts
- choose exactly **one** final price block
- form final order
- freeze **finalized visible commercial IDs** — `ResolvedResponsePlan` is the **sole owner** of these IDs
- contain exact rendered IDs **before** rendering (only IDs that survived validation and optional resolution)
- contain session delta (finalized IDs only)
- contain visible text plan and separate UI plan
- record diagnostics / model-contract violations
- **not** analyze final text to recover provenance

Optional selection/materialization may fail **before** the plan is frozen. On optional failure: remove the broken block from the plan; its ID must **not** appear in finalized visible IDs or session delta. `TextRenderer` then renders the frozen plan deterministically and does **not** silently select or drop facts.

---

## 6. Price lane

```text
PRICE LANE: exact_price — sole owner of amount / currency / unit
```

At most **one** visible price block per plan.

**Target (ONE-CALL-ARCHITECTURE-1):** Composer does not output price. Price request = `requested_aspect_ids` containing `price`; Resolver/Renderer insert the single canonical block. Multi-price is fully code-owned.

| Situation | Decision |
|---|---|
| price aspect requested | code selects applicable offer(s); canonical block from code |
| multiple offers | canonical multi block from code |
| inactive / inapplicable / unsafe offer | its price not shown; `patient_text` preserved |

**Migration debt:** legacy paths may still accept `price_text` / `model_price_text` with exact-string match — remove in implementation checkpoint.

**Required offer conditions** — closed target-contract enum. Initial approved set (no arbitrary string IDs):

- `per_jaw`
- `per_tooth`
- `package_includes`
- `mandatory_exclusion`
- `ct_separate`
- `bone_grafting_separate`

Rules:

- this is a **closed enum** in the target contract; arbitrary string condition IDs are **forbidden**
- extending the enum requires an explicit response-contract change
- each plan item contains a condition ID plus canonical text/data from the selected offer
- required conditions must **not** carry warranty, installment, tax deduction, discount, or optional benefit

### 6.1 Response-plan materialization rules (isolated path)

The isolated post-Composer materialization path applies the following **current** rules. These describe present behavior and limits, not a permanent ban on future price modes.

#### Supported price modes

- Current materialization supports **`TargetFixedPrice`** offers only.
- `from`, `range`, and `no_public_price` price modes:
  - are **not** converted to a fixed amount;
  - emit diagnostic `materialization_unsupported_price_mode`;
  - exclude the corresponding offer from the price block;
  - preserve independent valid parts of the response (`patient_text`, unrelated materials).

#### Required condition completeness (`OfferConditionEvidence`)

Trusted `OfferConditionEvidence.completeness` governs whether an offer may enter the price block:

| `completeness` | Condition set | Effect |
|---|---|---|
| `complete` | empty | source attests there are no additional required conditions; price may be shown |
| `complete` | non-empty | price is shown together with **all** required conditions |
| `unknown` | any | offer excluded from price block with diagnostic; useful `patient_text` and independent materials preserved |
| `incomplete` | any | offer excluded from price block with diagnostic; useful `patient_text` and independent materials preserved |

Empty conditions with `complete` mean **confirmed absence** of required conditions — not the same as unknown completeness.

#### Legacy condition compatibility (Resolver)

- Single-offer `display_text`-only condition blocks remain valid.
- Multi-offer condition blocks with explicit offer-linked `entries` remain valid.
- Multi-offer `display_text`-only blocks **without** proven linkage are rejected: `legacy_multi_condition_ambiguous`.
- `applies_to_all_offers=true` is an **explicit source attestation** that the condition applies to all selected offers — not an inference from free text.
- When a shared form is valid, Resolver expands it per existing linkage rules.

Do not extend compatibility or relax source requirements.

#### Frozen price provenance

The new path freezes typed **`FrozenPriceOfferRow`** for each finally shown offer (`offer_id`, `service_id`, distinguishing `offer_label`, amount/currency/billing_unit, optional `option_id`/`brand_id`).

**`FinalizedOfferTrace`** is a projection of these frozen rows. After freeze, the trace does **not** re-read the catalog bundle for amount, currency, unit, offer/service identity, or offer label.

---

## 7. Foreign amount / code-owned value in `patient_text`

If model inserts foreign amount or code-owned commercial value into `patient_text`:

- record `model_contract_violation`
- do **not** delete Russian sentences by regex
- do **not** run extra LLM
- do **not** apply complex sanitizer
- do **not** treat value as controlled price
- canonical price block remains the only code-owned price block
- useful `patient_text` is preserved
- count as **model error**, not assembler error

Renderer does **not** promise to fix model meaning errors.

---

## 8. Fact lane and roles

Priority:

```text
requested_fact
> required_offer_condition
> promo
> automatic_amplifier
```

Price does not compete in fact-lane.

One fact ID → at most one visible role.

If fact is `requested_fact`, remove it from promo, automatic amplifiers, and other optional roles.

Requested facts:

- do **not** consume automatic amplifier cap
- need not appear as a list block
- may appear as normal paragraph
- receive plan-derived shown IDs

---

## 9. Warranty (`implant_warranty`)

```text
implant_warranty.visibility = explicit_only
```

| Case | Behavior |
|---|---|
| Explicit warranty/reliability question | Composer puts `implant_warranty` in `requested_fact_ids` → resolver allows `requested_fact` → shown once |
| Ordinary implant/price question | not requested → no automatic/promo/service-value role → **not shown** |

No regex for «гарантия» / «надёжность».

**Current runtime note:** automatic warranty is off. Warranty may appear via model-controlled `direct_fact_ids` (legacy) / target `requested_fact_ids`. Code validates ID applicability; explicitness depends on Composer contract, not independent code classification.

**Legacy config:** `scenario_rules.result_reliability` is misleading — do not activate; remove after proven cutover unless Hybrid needs it.

---

## 10. Visible order and caps

### Normal answer (with service options)

When `ServiceOptionsBlock` is materialized:

```text
patient_text
→ ServiceOptionsBlock
→ requested facts
→ up to 1 service_value
→ up to 2 promo
→ one list, max 2 automatic amplifiers
→ CTA
```

### Normal answer (without service options)

```text
patient_text + requested facts
→ up to 1 service_value
→ up to 2 promo
→ one list, max 2 automatic amplifiers
→ CTA
```

### Price answer

```text
canonical price + required offer conditions
→ patient_text + requested facts
→ up to 2 promo
→ one list, max 4 automatic amplifiers
→ CTA
```

If canonical price block already shows selected variants, separate `ServiceOptionsBlock` is **forbidden** as duplicate.

No automatic `service_value` on price answer.

Amplifier list header:

```text
Также мы предлагаем:
- ...
- ...
```

Rules: at most one list; no header without amplifiers; empty list forbidden; one fact not repeated across blocks.

Automatic list usually forbidden for: ADMIN, contacts, current medical problem, strict terminal, narrow direct answer, cost objection when list would become a catalog.

---

## 11. Promo, service value, optional failure

Promo and amplifiers have independent caps.

Directly requested promo gets one role by resolver priority; no duplicate.

Optional selection/materialization failure is allowed **only before** the final `ResolvedResponsePlan` is frozen. On failure:

- drop **only** the broken optional block from the plan
- its ID is absent from finalized visible IDs and session delta
- preserve useful `patient_text`

Affected optional parts: promo, amplifier, service value, CTA, video, quick replies, optional UI, telemetry, optional evidence.

Legacy promotion fail-closed is **not** target behavior.

---

## 12. Fail-open vs strict errors

### Fail-open / canonical correction

- invalid/missing `price_text`
- invalid optional promo, amplifier, service value
- CTA / video / UI optional parts
- post-Composer telemetry
- optional evidence reporting
- inactive/inapplicable optional offer
- optional commercial block error

### Strict error (only)

- client mismatch / cross-client data
- broken mandatory envelope
- invalid route/mode
- structural conflict of controlled values
- another clinic's contacts
- cannot safely determine terminal mode

ADMIN and medical terminal mode are normal ResponsePlan types, not technical errors.

---

## 13. Session state

New session:

- namespaced by `client_id + sid`
- session writer stores **finalized IDs from `ResolvedResponsePlan` only**
- no final-answer text scan; no ID recovery from visible text
- active service/topic/history in new contract
- same `sid` across clients isolated
- optional failure does not erase useful state; failed optional IDs are not written
- blocking and streaming share one plan/session path

### 13.1 Opt-in typed session continuity (RESPONSE-SESSION-CONTINUITY-1)

Separate from legacy `session.py` and `/ask` wiring:

- **Read:** `ResponsePlanSessionStore.read(SessionKey)` → immutable snapshot; missing row returns empty state without INSERT.
- **Bridge:** `build_turn_read_bundle()` → `ComposerSessionContext`, `recent_dialogue`, `confirmed_shown_options`, `active_session_service_id`, typed `prior_situation_state`, `current_turn_index`, `expected_revision`.
- **Write boundary:** `prepare_session_update()` after Resolver/Renderer; `commit_session_update()` only after explicit `SessionCompletionReceipt` matching full prepared fingerprint (not rendered text alone).
- **Committed-turn numbering:** `current_turn_index = last_committed_turn_index + 1`; history pair count ≠ turn index; Composer receives ≤ `MAX_COMPOSER_HISTORY_TURNS` messages.
- **Freshness:** explicit `SessionContinuityPolicy` (`active_service_max_age_turns`, `active_topic_max_age_turns`, `situation_max_age_turns`, `shown_options_max_age_turns`, `history_pair_limit`); stale values are not model-visible; future `set_at_turn` is a typed error.
- **Distinction:** active service (one focus link) ≠ shown service options snapshot ≠ historical frozen price rows (`finalized_plan_price_offers` provenance).
- **Idempotency:** `(client_id, sid, request_id)` checked before `expected_revision`; same fingerprint → no-op; different fingerprint → conflict.
- **SQLite:** injected connection/factory only; no import-time DB open; no legacy migration.
- **Request binding (correction pass):** `create_turn_request_binding()` / `begin_bound_session_turn()` freeze `SessionKey`, `request_id`, `expected_revision`, `current_turn_index`, `patient_message`, and `SessionSnapshotIdentity` **before** Composer. `TurnPipelineOutcome` carries the same binding through post-Composer selection, materialization, Renderer, and UIProjection; `prepare_session_update()` rejects cross-request or mismatched render/UI mixes.
- **Prepared response coherence:** `validate_prepared_response_coherence()` is the single pure check that selection, frozen `resolved_plan`, rendered text, UI projection, and situation delta agree (including price-row `service_id` ⊆ `price_candidate_service_ids`) before delivery at prepare and again at commit intrinsic validation.
- **Fingerprint v3:** SHA-256 over `format_version`, full `request_binding`, `snapshot_identity`, `patient_message`, full typed `resolved_plan` dump, full `ui_projection`, `selection` decision metadata, and `proposed_state`. Store recomputes before commit; receipt must match recalculated hash; intrinsic validation also checks `render_response_text()` / `project_response_ui()` against prepared fields. State-dependent transition validation runs only for new `request_id` commits inside the transaction.
- **Freshness split:** read bridge and post-Composer each take explicit limits — `situation_max_age_turns` via `SituationContinuityPolicy`, `shown_options_max_age_turns` via `ShownOptionsFreshnessPolicy` (optional on legacy post-Composer callers; session bridge always passes both). Restored snapshot topics/services keep source `set_at_turn`; read/replay/idempotent keep do not re-age context. Snapshot-only topic restoration requires a **catalog-eligible** shown-options snapshot for the current request (`validate_shown_options_snapshot()` via read bridge → `validated_shown_options` / `topic_restoration_shown_snapshot` on prepare/commit); stale, catalog-rejected, or incompatible raw `prior.shown_options_snapshot` is not used. Partial eligibility keeps the validated eligible subset per existing post-Composer policy; an empty eligible set is not a restoration basis. Non-null `topic_restoration_shown_snapshot` must equal the source session's stored `shown_options_snapshot` (`validate_topic_restoration_shown_snapshot_binding()` at prepare and on new commit after idempotency).
- **Shown memory → materialization:** `materialization_sources_for_bound_turn()` copies typed `accumulated_shown_ids` from the read bundle into `shown_*_fact_ids` on `ResponsePlanMaterializationSources` for the same request.

Old session: may be reset; no migration; no compatibility schema; no permanent fallback; old fields removed after cutover.

---

## 14. TextRenderer and UIProjection

**TextRenderer** input: frozen `ResolvedResponsePlan` only.

Renders deterministically: price block; required offer conditions; `patient_text`; requested facts; service value; promo; single amplifier list; textual CTA if planned.

Must not: select facts; silently drop facts; classify language; recover provenance from text; regex-delete sentences; call providers.

**UIProjection** creates: buttons; quick replies; widget offer; video; CTA button; metadata.

**UIProjection** projects/exposes **plan-owned** rendered/service/fact IDs only.

Must not: re-select commercial facts; create commercial IDs; recover IDs from visible text; change visible text.

---

## 15. Blocking / streaming parity

**Target path:**

```text
/ask and /ask/stream
→ one ComposerInputContext
→ one ComposerDecision
→ one ResolvedResponsePlan
→ one TextRenderer
→ one UIProjection
→ one session delta semantics
```

Transport differs only.

```text
/ask visible text == fully assembled /ask/stream visible text
```

**Legacy note:** older diagrams referencing `PreComposerPlan` describe migration-debt wiring, not the target free-text path (see §1).

---

## 16. Terminal response plans

ADMIN, contacts, CLARIFY, and medical terminal are typed plans. No keyword/regex medical classifier.

**Medical terminal** = ADMIN plan/subtype under the approved route contract. It inherits ADMIN prohibitions below. Urgency may change the deterministic wording only; it does **not** create a regex/keyword route or a second LLM.

| Plan | `patient_text` | Price | Requested facts | Promo / amplifier / service value | Selling CTA | Contacts / UI | Session delta |
|---|---|---|---|---|---|---|---|
| **ADMIN** | Composer `patient_text=null`; visible text is code-owned deterministic message | forbidden | forbidden | forbidden | forbidden | canonical phone of current client only | history/terminal result; **no** commercial shown IDs |
| **CONTACTS** | built from canonical contacts of current client | forbidden | forbidden | forbidden | forbidden | contact UI/actions allowed | **no** commercial shown IDs |
| **CLARIFY** | short clarification text only | forbidden | forbidden | forbidden | forbidden | relevant clarification quick replies only | clarification/dialogue state; **no** commercial shown IDs |
| **MEDICAL TERMINAL** | same as ADMIN: no model selling prose; deterministic safe message | forbidden | forbidden | forbidden | forbidden | canonical phone of current client only | same as ADMIN |

CONTACTS: no fallback to another clinic's contacts.

---

## 17. Replay and acceptance

### Assembler errors (target: 0)

Wrong controlled price; wrong unit; duplicate controlled fact; automatic warranty; cap violation; multiple amplifier lists; empty amplifier list; ordering violation; optional failure destroying `patient_text`; session IDs from text; commercial append after renderer; requested fact duplicated automatically.

### Model errors (count separately)

Unsupported medical claim; unsupported duration; missed doctor; misunderstood question; foreign amount in `patient_text`; bad style; unrequested fact marked requested.

Missing replay field → `not_captured`. Do not reconstruct provenance from visible answer.

---

## 18. Examples

### 1. Single price (explicit service)

**Пациент:** «Сколько стоит имплант Implantium?»
**Composer:** `route=ANSWER`, `service_reference_kind=explicit_current`, `explicit_service_id=implantium`, `requested_aspect_ids=["price"]`, `requested_fact_ids=[]`
**Resolved roles:** one `exact_price` block from code; optional promo/amplifiers within caps
**Visible:** canonical price + conditions → patient_text → optional commercial blocks → CTA
**Запрещено:** second price block; warranty without request; model-owned price text

### 2. Session follow-up price

**Ранее:** обсуждение All-on-4
**Пациент:** «А сколько стоит?»
**Composer:** `service_reference_kind=active_session`, `explicit_service_id=null`, `requested_aspect_ids=["price"]`
**Resolved:** code validates session service → canonical price block for validated service
**Visible:** canonical price + conditions → patient_text → …
**Запрещено:** fake `explicit_service_id` copied from session

### 3. Multi price

**Пациент:** «Какие варианты имплантации по цене?»
**Composer:** `requested_aspect_ids=["price"]`, `service_reference_kind=none`
**Resolved:** canonical multi block from code
**Visible:** multi block → patient_text → promo/amplifiers (no service_value; no duplicate ServiceOptionsBlock)
**Запрещено:** model multi-price prose as authority

### 4. Direct installment question

**Пациент:** «Есть рассрочка?»
**Composer:** `requested_fact_ids=["installment_12"]`, `requested_aspect_ids=["payment"]`
**Resolved:** `installment_12` → `requested_fact` only
**Visible:** patient_text + requested fact paragraph
**Запрещено:** same fact again as automatic amplifier; cap consumption

### 5. Explicit warranty question

**Пациент:** «Какая гарантия на импланты?»
**Composer:** `requested_aspect_ids=["warranty"]`, `requested_fact_ids=["implant_warranty"]`
**Resolved:** `requested_fact` once
**Visible:** patient_text + warranty text once
**Запрещено:** automatic warranty; promo duplicate

### 6. Ordinary implant question (no warranty)

**Пациент:** «Расскажите про имплантацию»
**Composer:** `requested_aspect_ids=["overview"]`, `requested_fact_ids=[]`
**Resolved:** no warranty role
**Visible:** patient_text + optional promo/amplifiers only
**Запрещено:** `implant_warranty` in any automatic role

### 7. Situation with service options

**Пациент:** «У меня нет всех зубов сверху»
**Composer:** `service_reference_kind=none`, `explicit_service_id=null`, `patient_situation.extent=full_arch`, `patient_situation.jaw=upper`
**Resolved:** clinic strategy ranks services → `ServiceOptionsBlock` (max 3)
**Visible:** patient_text → ServiceOptionsBlock → …
**Запрещено:** Composer listing/ranking services in `patient_text`

### 8. Promotion optional failure

**Пациент:** «Есть акции на имплантацию?»
**Composer:** valid `patient_text`, promotion intent
**Resolved:** promo selection fails optionally
**Visible:** patient_text preserved; broken promo skipped
**Запрещено:** fail-closed replacement of entire answer

### 9. ADMIN / current medical problem

**Пациент:** «После имплантации стало хуже»
**Composer:** `route=ADMIN`, `patient_text=null`
**Resolved:** static admin plan; no commercial blocks; no ServiceOptionsBlock
**Visible:** deterministic admin text + clinic phone only
**Запрещено:** promo, amplifiers, service value, selling CTA, model prose

---

## 19. Implementation status (ONE-CALL-ARCHITECTURE-1)

### 19.1 Implemented in the isolated new path (unwired from production `/ask`)

- `ComposerDecision` strict parser + fail-open semantic adapter with full published field set (`service_reference_kind`, `option_reference_kind`, nullable `topic_id`, closed `AspectKind` aspects, `patient_situation`)
- deterministic `ComposerInputContext` assembly, static instructions, policy sidecar, cached FullContext corpus, session/history/current message
- provider-neutral executor with one injected backend call per free-text turn
- post-Composer situation continuity merge, applicability filter, clinic strategy ranking, service/offer selection
- `ServiceOptionsBlock` lane in Response Plan resolver/renderer/materialization (isolated path)
- response-plan price materialization per §6.1 (supported modes, condition completeness, legacy compatibility, frozen provenance)
- selected promo/amplifier IDs merged into `commercial_facts` before freeze
- catalog-reference price lookup separate from situation-based selection
- typed session continuity store + read/prepare/commit bridge (opt-in; offline multi-turn integration)

**Order note:** `PreComposerPlan` in the new chain is materialized **after** Composer. The name is historical; it does not restore legacy pre-Composer semantic selection on free-text turns.

**Price note:** target Composer output has no `price_text`; legacy paths may still accept `price_text` / `model_price_text`.

**FullContext vs runtime:** FullContext corpus strategy for Composer input is not the legacy multi-call FullContext product runtime (TFC).

**Hybrid:** future compact-context strategy shares the same lower pipeline; no separate Hybrid renderer.

**Flag note:** `SALES_ONE_PLUS_ON=0` selects legacy TFC runtime, not this isolated response-plan core.

### 19.2 Not yet complete

- end-to-end acceptance on the target path
- verification against a real provider/model
- production `/ask` and `/ask/stream` cutover
- provider/transport wiring and deployment env for feature activation
- legacy multi-call FullContext runtime decommission (still default at flag=0)
- requestable facts still coupled to `PreComposerPlan.commercial_facts` in some legacy bridges
- real `clients/**` requested-display metadata not fully authored for every fact

### 19.3 Superseded historical notes

§4.0 COMPOSER-CONTRACT-1 six-key schema — **superseded** by §4.1 `ComposerDecision`; retained for audit only.

Historical gap list items that claimed unwired Composer WIP lacked `patient_situation`, aspects, or `service_reference_kind` — **superseded** by §19.1 parser/adapter implementation.

Deferred items that remain open:

- renderer module cutover from `one_call_presentation_pass` in production wiring
- TFC runtime decommission timing
- Hybrid context decision
- replay field capture completeness
