# Response Contract — one-call architecture

**Status:** owner-approved target contract (CHECKPOINT 2 — RESPONSE-CONTRACT-1)  
**Baseline:** `1cf8bbd200bddf5732b5723d25dc34fcc1545ac0`  
**Scope:** target one-call path; does not require immediate runtime cutover.

---

## 1. Terminology

| Term | Meaning |
|---|---|
| **Target FullContext Product Runtime (TFC)** | Legacy multi-call product stack reachable when the old branch is active (`SALES_ONE_PLUS_ON=0` at config default). Ingress/planner + Composer + Verifier + separate widget materializer. |
| **Full Context Strategy (FC)** | Context volume strategy for one-call Composer: full prepared MD corpus passed into a single call. Compared with curated/hybrid variants in experiments. |
| **Hybrid Strategy** | Future compact-context selection with Full Context fallback. Uses the **same** lower pipeline as FC — no separate renderer. |

**Shared lower path (FC and Hybrid):**

```text
PreComposerPlan
→ Composer
→ ResolvedResponsePlan
→ TextRenderer
→ UIProjection
```

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
- route/mode constraints
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

No semantic regex classification of Russian text before Composer.

---

## 4. Composer contract

Canonical requested-facts field:

```text
requested_fact_ids
```

(`direct_fact_ids` exists in legacy runtime only; target contract replaces it. No permanent compatibility layer.)

Composer returns at minimum:

- `route`
- `mode` (if separate closed field)
- `patient_text`
- `price_text` (only when allowed)
- `requested_fact_ids`
- service reference fields
- other necessary closed semantic fields

Rules:

- `patient_text` = natural explanation only
- code-owned exact commercial blocks are **not** duplicated in `patient_text`
- `requested_fact_ids` = facts the patient **directly asked about**
- catalog presence alone does **not** make a fact requested
- `price_text` only on allowed price turn
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

| Situation | Decision |
|---|---|
| valid model `price_text` | usable only after exact match with canonical offer data |
| missing/invalid model `price_text` | canonical fallback |
| multiple offers | canonical multi block from code |
| inactive / inapplicable / unsafe offer | its price not shown; `patient_text` preserved |

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

### Normal answer

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

```text
/ask and /ask/stream
→ one PreComposerPlan
→ one Composer contract
→ one ResolvedResponsePlan
→ one TextRenderer
→ one UIProjection
→ one session delta semantics
```

Transport differs only.

```text
/ask visible text == fully assembled /ask/stream visible text
```

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

### 1. Single price

**Пациент:** «Сколько стоит имплант Implantium?»  
**Composer:** `route=ANSWER`, `price_text` (if exact match) or empty, `requested_fact_ids=[]`  
**Resolved roles:** one `exact_price` block; optional promo/amplifiers within caps  
**Visible:** canonical price + conditions → patient_text → optional commercial blocks → CTA  
**Запрещено:** second price block; warranty without request

### 2. Multi price

**Пациент:** «Какие варианты имплантации по цене?»  
**Composer:** `price_text` ignored for multi  
**Resolved:** canonical multi from code  
**Visible:** multi block → patient_text → promo/amplifiers (no service_value)  
**Запрещено:** model multi-price prose as authority

### 3. Direct installment question

**Пациент:** «Есть рассрочка?»  
**Composer:** `requested_fact_ids=["installment_12"]`  
**Resolved:** `installment_12` → `requested_fact` only  
**Visible:** patient_text + requested fact paragraph  
**Запрещено:** same fact again as automatic amplifier; cap consumption

### 4. Explicit warranty question

**Пациент:** «Какая гарантия на импланты?»  
**Composer:** `requested_fact_ids=["implant_warranty"]`  
**Resolved:** `requested_fact` once  
**Visible:** patient_text + warranty text once  
**Запрещено:** automatic warranty; promo duplicate

### 5. Ordinary implant question (no warranty)

**Пациент:** «Расскажите про имплантацию»  
**Composer:** `requested_fact_ids=[]`  
**Resolved:** no warranty role  
**Visible:** patient_text + optional promo/amplifiers only  
**Запрещено:** `implant_warranty` in any automatic role

### 6. Promotion optional failure

**Пациент:** «Есть акции на имплантацию?»  
**Composer:** valid `patient_text`, promotion intent  
**Resolved:** promo selection fails optionally  
**Visible:** patient_text preserved; broken promo skipped  
**Запрещено:** fail-closed replacement of entire answer

### 7. ADMIN / current medical problem

**Пациент:** «После имплантации стало хуже»  
**Composer:** `route=ADMIN`, `patient_text=null`  
**Resolved:** static admin plan; no commercial blocks  
**Visible:** deterministic admin text + clinic phone only  
**Запрещено:** promo, amplifiers, service value, selling CTA, model prose

---

## 19. Implementation checkpoints (out of scope here)

Deferred to later checkpoints:

- exact schema types for plans
- renderer module cutover from `one_call_presentation_pass`
- TFC runtime decommission timing
- Hybrid context decision
- replay field capture completeness
- deployment env for feature activation
