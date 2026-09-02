# One-Call Architecture — target contract

**Status:** owner-approved governance checkpoint (ONE-CALL-ARCHITECTURE-1 + correction pass)
**Baseline:** `14de4a9a051dbf625acbdfc35b37392a5919e623`
**Scope:** target one-call free-text path; does not require immediate runtime cutover or Composer implementation.

This document fixes the authoritative order of the one-call pipeline and resolves the chicken-and-egg between pre-Composer semantic selection and post-Composer materialization. Implementation checkpoints follow this contract; code may lag until explicitly migrated.

Related: `docs/RESPONSE_CONTRACT.md` (materialization, price lane, fact roles, terminal plans).

---

## 1. Problem solved: chicken-and-egg

### 1.1 Contradiction in current WIP

The unwired COMPOSER-CONTRACT-1 schema returns only:

- `route`, `mode`, `patient_text`, `price_text`, `requested_fact_ids`, `source_identity`

It does **not** return topic, explicitly named service, request aspects, or patient situation.

At the same time, the existing `PreComposerPlan` already carries pre-Composer selections:

- `response_scope`, `selected_service_id`, `selected_topic_id`, `price_plan`, commercial materials

For free-text turns this creates an impossible loop:

1. Composer must be the **single** LLM call that understands the question.
2. But service, scope, and materials are already chosen **before** Composer.
3. Composer output does not expose structured fields to drive post-Composer selection.
4. Fixing this by parsing `patient_text`, a second LLM, or a legacy semantic planner is **forbidden**.

### 1.2 Resolution

Split **pre-call input** from **post-call decision**:

| Phase | Entity | Role |
|---|---|---|
| Before model | `ComposerInputContext` / `ComposerPolicyContext` | Everything the model may see; no final semantic plan |
| After model | `ComposerDecision` | Structured semantics from the one call |
| After merge | `EffectiveScope` → applicability → strategy → materialization | Code-owned selection and ranking |

No final plan based on unrecognized free-text meaning may exist before Composer.

---

## 2. Target one-call flow (free-text)

```text
request + recent history + session + current-client FullContext
                         ↓
              ComposerInputContext
                         ↓
                 ONE Composer call
                    (one provider call)
                         ↓
                ComposerDecision
                         ↓
        deterministic scope/session merge
                         ↓
    applicability filter + clinic strategy ranking
                         ↓
 canonical offers/facts/conditions/terminal/UI candidates
                         ↓
            response-plan materialization
                         ↓
          Resolver → frozen ResolvedResponsePlan
                         ↓
             Renderer + UIProjection
                         ↓
                   session writer
                         ↓
              /ask and /ask/stream
```

### 2.1 Non-negotiable rules

| Rule | Meaning |
|---|---|
| **One provider call** | Ordinary free-text turn = exactly one Composer LLM call |
| **No semantic planner before Composer** | Legacy planner, regex/keyword route/service/situation authority forbidden |
| **No semantic verifier after Composer** | No second LLM to re-check meaning |
| **Deterministic typed UI bypass** | Structured UI events = zero LLM calls |
| **No text recovery** | `patient_text` must not be analyzed to recover IDs, topic, service, situation, price, or session delta |
| **FullContext corpus** | Current-client validated MD corpus remains primary knowledge source |
| **Legacy runtime** | Legacy multi-call FullContext product runtime may be disabled later; not in this checkpoint |
| **No Hybrid RAG** | Hybrid compact-context strategy is out of scope here |

Blocking and streaming share this path; transport differs only.

---

## 3. Pre-call contract: `ComposerInputContext`

Everything assembled **before** the single model call. Python class names may vary; semantics are fixed.

### 3.1 Contains

- current user message
- recent dialogue history
- current-client **FullContext** corpus (cached validated MD)
- session context with **provenance** per field
- allowed route/mode policy (closed matrix)
- current-client topic taxonomy
- service descriptors (catalog metadata, not a preselected answer service)
- requestable fact descriptors (from `facts.json` projection)
- allowed aspect IDs (closed set)
- static Composer instructions
- code-owned policy metadata

### 3.2 Must NOT contain as semantic fact

These are **outputs** of Composer or post-Composer code, not pre-call assumptions on free-text turns:

- final response scope
- recommended service
- final offer IDs
- final price plan
- requested facts (final list)
- final route/mode for free-text (only **constraints** allowed)

### 3.3 Session service in input context

Code-owned `active_session_service_id` may appear in `ComposerInputContext` with explicit provenance and freshness. It informs the model about dialogue continuation but is **not** copied into `ComposerDecision.explicit_service_id`.

Session follow-up uses `service_reference_kind=active_session` (see §4.3). Current-turn `explicit_current` evidence overrides session.

### 3.4 Deterministic bypass

Structured UI / non-language events use `deterministic_bypass`: zero LLM calls, no `ComposerDecision`. Route and materials are code-selected from the event payload.

---

## 4. Post-call contract: `ComposerDecision`

Minimum target output from the **single** Composer call.

### 4.1 Fields

| Field | Required | Meaning |
|---|---|---|
| `route` | yes | `ANSWER` / `ADMIN` / `CLARIFY` (+ closed `mode`) |
| `mode` | yes | Closed pair with `route` |
| `patient_text` | yes* | Natural prose; `null` on ADMIN/contacts per route matrix |
| `service_reference_kind` | yes | Closed: `none` / `explicit_current` / `active_session` |
| `option_reference_kind` | yes | Closed: `none` / `shown_options` |
| `topic_id` | yes** | Allowed current-client topic ID or `null` |
| `explicit_service_id` | yes | Named-by-patient service ID or `null` |
| `requested_aspect_ids` | yes | Closed `AspectKind` values (see §4.5) |
| `patient_situation` | yes | Composable situation axes (see §4.6) |
| `requested_fact_ids` | yes | Explicitly requested fact IDs only |
| `source_identity` | optional | Diagnostic attestation only; may be `null` |

\* `patient_text` mandatory in schema; `null` where route policy requires code-owned visible text.

\*\* JSON key required; value nullable.

### 4.2 Absent from target contract

| Removed / forbidden | Reason |
|---|---|
| `price_text` | Price is code-owned; price intent via `requested_aspect_ids` |
| `recommended_service_ids` | Service ranking is post-Composer, code-owned |

### 4.3 `service_reference_kind` and `explicit_service_id`

Closed field `service_reference_kind` declares how the current turn relates to a service. Invariants:

```text
service_reference_kind = explicit_current  ↔  explicit_service_id != null
service_reference_kind in {none, active_session}  →  explicit_service_id = null
```

#### `none`

- current turn does not refer to a specific service
- `explicit_service_id = null`
- stale session service is **not** carried forward

#### `explicit_current`

- patient **explicitly named** a service in the **current** message
- `explicit_service_id` is required and must belong to current-client service catalog
- not a model recommendation or inferred treatment choice

**Example:**

«Сколько стоит All-on-4?» → `explicit_current` + `explicit_service_id=all_on_4`

#### `active_session`

- current turn semantically continues the active session service discussion
- `explicit_service_id = null` — Composer does **not** copy session service ID into output
- post-Composer code validates: `active_session_service_id` exists; provenance/freshness acceptable; topic compatible
- if session service is missing, stale, or incompatible: code does **not** silently substitute it; allows topic/clinic flow or clarification per structured decision

**Example — session follow-up:**

Previously: All-on-4 discussion
«А сколько стоит?» → `active_session` + `explicit_service_id=null`

**Example — topic switch:**

Previously: All-on-4
«Как вы стерилизуете инструменты?» → `none` + `explicit_service_id=null`

`active_session` is a semantic reference to dialogue context, not model-owned treatment selection.

**Example — situation without named service:**

Patient: «У меня нет всех зубов сверху»

```text
service_reference_kind = none
explicit_service_id = null
patient_situation.extent = full_arch
patient_situation.jaw = upper
```

Matching services are selected by code **after** Composer.

### 4.4 `topic_id`

```text
topic_id: allowed current-client topic ID | null
```

- JSON key is **required**; value is **nullable**
- arbitrary strings forbidden
- missing topic is **not** an error
- missing service/topic alone does **not** imply `CLARIFY`
- no default implantation topic

Post-Composer scope derivation:

```text
valid explicit_current service
→ service scope

valid active_session reference (validated session service)
→ service scope using validated active_session_service_id

else topic_id != null
→ topic scope

else
→ clinic scope
```

Route may additionally yield terminal/clarify plan per closed route/mode matrix.

### 4.5 `requested_aspect_ids`

Reuses the existing closed `contracts.answer_plan.AspectKind` — no new taxonomy:

```text
price
payment
warranty
pain
included
duration
comparison
stages
overview
contacts
contact_phone
contact_address
contact_parking
contact_hours
contact_whatsapp
service_availability
```

Rules:

- JSON field required; value is a unique list/tuple (may be empty)
- unknown values forbidden by structural parser
- silent normalization/aliasing forbidden
- `composition` is **not** an alias for `included`
- taxonomy changes require a separate contract change
- price intent = presence of `price`
- payment intent = presence of `payment`
- package composition intent = presence of `included`
- requested fact IDs remain a separate channel

**Warranty example:**

```text
requested_aspect_ids = ["warranty"]
requested_fact_ids = ["implant_warranty"]   # only if explicitly requested and available
```

Aspect describes the question type. Fact ID requests a specific canonical block.

### 4.6 `patient_situation`

Composable axes (existing conventions):

| Axis | Values |
|---|---|
| `extent` | `unknown` / `one_tooth` / `few_teeth` / `full_arch` |
| `jaw` | `unknown` / `upper` / `lower` / `both` |
| `stage` | `unknown` / `natural_tooth_present` / `extraction_context` / `implant_placed` |
| `modifiers` | closed set of approved modifiers |

Model describes situation; it does **not** choose treatment.

### 4.7 `requested_fact_ids`

- only IDs from model-visible requestable fact descriptors
- only when patient explicitly asked
- applicability validated by code after Composer
- unknown/inapplicable ID does not destroy safe `patient_text`
- `explicit_only` facts cannot become automatic promo/amplifier

### 4.8 `source_identity`

Diagnostic / eval attestation only:

- not client authority
- does not choose FullContext/Hybrid
- does not control CTA/UI
- does not prove document usage
- does not affect price or session
- may be `null`
- refs must be subset of actually passed current-client corpus

---

## 5. Post-Composer pipeline

```text
ComposerDecision
+ session context (provenance-aware)
        ↓
EffectiveScope (deterministic merge)
        ↓
applicability filter
        ↓
clinic strategy ranking
        ↓
ranked service/offer IDs
        ↓
response-plan materialization
        ↓
Resolver → ResolvedResponsePlan
        ↓
TextRenderer + UIProjection
```

### 5.1 Service recommendations — code-owned `ServiceOptionsBlock`

Composer must **not** form or rank recommended services in `patient_text`.

```text
ComposerDecision.patient_situation
+ service_reference_kind
+ explicit_service_id
+ topic_id
+ session context
→ EffectiveScope
→ applicability filter
→ clinic strategy
→ ranked service IDs
→ typed ServiceOptionsBlock
→ frozen ResolvedResponsePlan
→ deterministic TextRenderer
→ UIProjection
```

#### Target `ServiceOptionsBlock` (implementation in later checkpoint)

```text
ServiceOptionsBlock
- source_client_id
- ordered options (max 3)
  - service_id
  - canonical display name
  - optional approved short description
- strategy rule/reference
```

Rules:

- order belongs to clinic strategy; Composer does not create or reorder options
- all service IDs must belong to current client
- option must be applicable to `EffectiveScope`
- exact price, promo, warranty, and CTA do **not** belong inside a service option
- `UIProjection` displays the same plan-owned IDs only
- visible/session IDs are not recovered from text
- finalized/session delta includes typed `shown_service_option_ids` (or equivalent separate group)
- one service ID must not appear twice in options
- max options determined by clinic strategy; target ceiling = 3

#### When lane applies

Primary case:

- `explicit_service_id = null` (i.e. `none` or `active_session`)
- situation sufficient for multiple suitable directions
- clinic strategy returned ranked services
- `route = ANSWER + standard`

Do **not** apply for: ADMIN, CONTACTS, CLARIFY, medical terminal, or when no provably applicable services exist.

For `explicit_current`: usually no recommendation list. Alternatives only under explicit `comparison`/alternatives policy in materialization contract.

For price flow: canonical single/multi price block owns priced choices. **Forbidden:** separate `ServiceOptionsBlock` that duplicates the same variants already shown in the price block.

#### Visible order

**Situation/recommendation answer (with service options):**

```text
patient_text
→ ServiceOptionsBlock
→ requested facts
→ service value
→ promo
→ one amplifier list
→ CTA
```

**Answer without service options:** existing order (patient_text → requested facts → …).

**Price answer:**

```text
canonical price block
→ required offer conditions
→ patient_text
→ requested facts
→ promo
→ one amplifier list
→ CTA
```

If price block already shows selected variants, separate `ServiceOptionsBlock` is forbidden as duplicate.

### 5.2 Price — code-owned (no `price_text`)

| Layer | Owner |
|---|---|
| Price intent | `requested_aspect_ids` |
| Offer selection | code after Composer |
| Visible amount/unit | Resolver → single canonical price block |
| Multi-price | fully code-owned |

Composer must **not**:

- repeat sums in output
- embed price in `patient_text`

`model_price_text` and exact-string price comparison in legacy paths are **migration debt** — remove in next implementation checkpoint.

---

## 6. Facts and claims

### 6.1 Single source of truth

No second physical requestable-facts catalog. Current-client `facts.json` is authoritative.

Independent projections:

```text
facts.json
├── requestable facts inventory
├── promo candidates
└── automatic amplifier candidates
```

Requestable inventory does **not** depend on whether marketing selector auto-chose a fact.

### 6.2 Target fact descriptor semantics

| Property | Meaning |
|---|---|
| ID | stable fact identifier |
| model-visible meaning/label | what Composer may request |
| canonical text | authoritative wording |
| applicability | clinic/topic/service matrix |
| allowed topics/services | scope gates |
| `explicit_only` | never automatic promo/amplifier |
| allowed roles | resolver role ceiling |
| render mode | `strict` (exact) or `natural` (faithful paraphrase) |

`approved_by`, `approved_at`, full risk registry — optional future extensions, not required for first cutover.

### 6.3 Text ownership classes

| Class | Examples | Rule |
|---|---|---|
| **Exact / code-owned** | price, promo amounts/dates, warranty terms, contacts, legal claims, high-risk claims | Renderer inserts verbatim from canonical sources |
| **Faithful paraphrase** | general medical info, technology, stages, contraindications (no personal conclusion), consultation description without exact commercial terms | Model may paraphrase without new medical meaning |
| **Free model prose** | empathy, connectors, neutral intro | Stylistic deviation does not invalidate `patient_text` |

---

## 7. Session semantics (target)

- session stores topic, active service, extent, jaw, stage, shown IDs
- each value has source/provenance and freshness
- current-turn explicit evidence > session
- session facts apply only to compatible topic
- new topic does not inherit stale service/situation
- terminal/error turn does not overwrite useful situation
- session writer receives only finalized typed delta — **never** analyzes visible text

Detailed wiring is a later situation/executor checkpoint.

---

## 8. Failure policy and observability boundary

### 8.1 Runtime can detect (deterministic)

- malformed schema
- invalid route/mode
- unknown ID
- inapplicable fact
- wrong client ownership
- invalid/nonexistent canonical price
- forbidden commerce on terminal route
- inconsistent frozen plan

### 8.2 Runtime cannot guarantee (without second LLM)

Automatic semantic blocking of dangerous meaning hidden in free `patient_text`.

Free semantic errors are controlled by:

- static Composer instructions
- limited approved corpus
- offline dialogue eval
- controlled local provider tests
- regression cases after discovered failures

Do not promise automatic semantic safety for arbitrary model prose.

---

## 9. Relationship to legacy and experiments

| Concept | Status in this checkpoint |
|---|---|
| **FullContext corpus** | Target primary knowledge input to Composer |
| **Legacy multi-call FullContext runtime** | Remains default when local flag=0; decommission later |
| **TFC Product Runtime** | Legacy stack; not target path |
| **Hybrid Strategy** | Future; same lower pipeline, no separate renderer |
| **COMPOSER-CONTRACT-1 six-key schema** | Historical unwired WIP; **superseded**, not implementation target |
| **COMPOSER-INPUT-EXECUTOR-1** | Implemented from baseline `0f5000792acf164e12d886ff053c7badd8f584e2` as isolated/unwired provider-neutral input + executor; **not** wired to production `/ask` |

FullContext **corpus strategy** must not be confused with legacy **multi-call runtime**.

### 9.1 COMPOSER-INPUT-EXECUTOR-1 (isolated, unwired)

Implemented from baseline `0f5000792acf164e12d886ff053c7badd8f584e2` as an isolated/unwired checkpoint. Provider-neutral input path:

```text
current user message
+ recent typed dialogue history (≤6 turns)
+ normalized session context with provenance
+ current-client cached FullContext corpus
+ independent ComposerDecisionAuthority (source_client_id)
+ static Composer instructions
→ one deterministic Composer invocation
→ exactly one injected backend call
→ strict parser
→ fail-open semantic adapter
→ AdaptedComposerDecision
```

**Stable system prompt:** static instructions + current-client validated model FullContext corpus + document index only.

**Dynamic user prompt:** deterministic JSON with `policy_control`, `session_context`, `recent_dialogue`, `current_user_message`.

**No pre-Composer price/offer data:** policy sidecar exposes only `price_handling: "code_owned_after_decision"`; no amounts, currencies, offer IDs, or canonical price display text before Composer.

**Source refs:** safe corpus-relative POSIX `.md` paths (nested paths allowed; traversal/absolute/backslash/URI forbidden).

**Hash authorities:** `source_corpus_sha256` is the SHA-256 of full validated `corpus_text`; `model_corpus_sha256` is the SHA-256 of the exact model-visible corpus text included in the system prompt. They differ when `prompt_corpus_text` is present.

**Prompt corpus pair matrix:** `prompt_corpus_text` and `prompt_sha256` must both be absent or both present; whitespace-only prompt corpus is forbidden; mismatched pair or wrong `prompt_sha256` rejects input before backend.

**Session provenance/freshness:** closed runtime validation in `ComposerSessionContext`; arbitrary values rejected before prompt builder/backend. Invalid input → zero provider calls.

**Not in this checkpoint:** production wiring, `session.py`, `/ask` cutover, LIVE/provider network. Post-Composer materialization (`RESPONSE-MATERIALIZATION-1`) is implemented as an isolated unwired path only.

---

## 10. Implementation gaps (expected)

These gaps are **expected** for a governance-only checkpoint and are not grounds for REJECT:

| Gap | Current state |
|---|---|
| `PreComposerPlan` premature semantics | Still carries final scope, service, price plan, commercial materials before Composer on free-text path |
| Composer schema incomplete | **COMPOSER-CONTRACT-1 committed** on `0f5000792acf164e12d886ff053c7badd8f584e2`; parser/adapter for full `ComposerDecision` implemented |
| Composer input/executor | **COMPOSER-INPUT-EXECUTOR-1** implemented isolated/unwired from baseline `0f5000792acf164e12d886ff053c7badd8f584e2`; production `/ask` not connected |
| `price_text` / `model_price_text` | Still present in legacy code paths; removed from Composer policy sidecar; price intent via `requested_aspect_ids` only |
| Requestable facts coupling | Still tied to `PreComposerPlan.commercial_facts` in places |
| Situation → strategy → materialization | **RESPONSE-MATERIALIZATION-1** isolated path: materialization → Resolver/Renderer/UI; frozen `FrozenPriceOfferRow`, marketing fact merge, legacy condition policy — see `RESPONSE_CONTRACT.md` §19; not wired to `/ask` |
| Target executor | Absent |
| `/ask` / `/ask/stream` | Not switched to target path |
| Legacy runtime | Default at flag=0 |

**Next checkpoint:** session writer cutover, optional marketing materialization breadth, `/ask` integration — not started here.

---

## 11. Checker gates (cadence)

Mandatory independent checker runs:

1. final architecture contract (this checkpoint)
2. complete executor implementation
3. production cutover
4. legacy removal

Checker is **not** required after every micro-step. Re-check only after REJECT or material post-checker changes.
