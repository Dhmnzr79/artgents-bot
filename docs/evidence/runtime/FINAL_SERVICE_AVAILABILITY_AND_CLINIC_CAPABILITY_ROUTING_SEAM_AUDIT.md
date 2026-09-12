# FINAL_SERVICE_AVAILABILITY_AND_CLINIC_CAPABILITY_ROUTING — seam audit

**Дата:** 2026-07-27  
**Baseline:** `codex/stage-a` @ `d8dbe93`  
**Режим:** governance / docs / tests only · **NO product code / NO LIVE / NO LLM**  
**Owner GO:** Phase 1 governance only; implementation blocked until PRE-CODE ✅ + separate owner GO

## Preflight

| Check | Result |
|---|---|
| Branch | `codex/stage-a` ✅ |
| `HEAD` == `origin/codex/stage-a` @ `d8dbe93` | ✅ |
| Working tree clean at governance start | ✅ |
| Prior milestone landed | `FINAL_GENERIC_FULLCONTEXT_CONTENT_AUTHORITY` @ `d8dbe93` |
| Semantic/Numeric/Contact Verifier | **KEEP** — no change without reproducible defect |

## Executive summary

Product path conflates **service availability** (canonical catalog authority) with **clinic capability/info**
(FullContext / safety standards). Two canonical defects:

| ID | User turn | Runtime stop | Root cause |
|---|---|---|---|
| **A** | «Вы делаете 3D-диагностику?» | `scoped_evidence_component_unfulfilled: content` → `target_fullcontext_error` | `tomography` active in catalog, Planner `service_id=tomography`, but **no** `content_ref`; service-bound package requires content component |
| **B** | «Кварцевание воздуха у вас делаете?» | `ingress_service_not_offered` — Planner/FullContext never called | Ingress treats unknown catalog object as **definitive non-service**; fact exists in `implantation__faq__safety.md` as clinic safety standard |

**Architectural target:** semantic split via typed Planner output + catalog authority + existing
`generic_fullcontext_content` — **not** regex/phrase routing, **not** second classifier, **not** MD→service
auto-creation.

---

## Normative concepts (binding)

### Service availability

Patient asks whether clinic offers a **standalone treatment/procedure** (catalog object).

**Authority:** `clients/{id}/target_response/service_catalog.json` only.

**Active (`active=true`):** deterministic structured answer — «Да, клиника оказывает услугу „…“».
No `content_ref` required for yes/no availability. No Boundary/Composer/Semantic.

**Inactive (authored record, `active=false`):** «Сейчас эта услуга в клинике не оказывается».
Category allowed — owner-authored status.

**Catalog miss:** must **not** auto-assert «не оказываем»; route to Generic FullContext for capability/info.

### Clinic capability / info

Technology, material, equipment, sterility, diagnostic approach, organizational capability, safety method.

**Authority:** Generic FullContext or other structured authority (contacts, etc.).

Found capability fact **does not** become a service; **no** price inheritance.

---

## Normative routing order (binding)

1. Pre-resolver guards  
2. Ingress (hard-stop / manual-contact / not-target — **not** catalog-miss denial)  
3. Typed UI frame or Planner  
4. Structured contacts  
5. **Typed service availability** (active / inactive)  
6. Structured price / doctors / AC1–AC3  
7. Medical Boundary  
8. Concrete service content (`service_id` + content path)  
9. **Generic FullContext** (capability/info / unknown catalog object)  
10. Deterministic + Semantic Verifier → presentation/widget/session  

---

## Phase 1 seam audit checklist

### 1. Ingress `service_not_offered` semantics

**File:** `ingress_gate.py` L45–78, L291–313, L543–549.

Current behavior:

- Ingress LLM may return `route=service_not_offered` when entity **not in offered_services** summary.
- `build_service_not_offered_answer()` renders template: «К сожалению, такую услугу … не оказываем» —
  **categorical denial** without target runtime.
- `_apply_offered_ground_truth()` can override to `normal` only if `catalog_offers_mention()` or
  `doctor_ground_truth_mention()` matches — **phrase/substring match on aliases**, not semantic capability.
- Low confidence → `fallback_low_confidence` → `normal` (L280–287).

**Defect B path:**

```text
«Кварцевание воздуха у вас делаете?»
  → ingress LLM: service_not_offered (object not in offered_services)
  → ingress_entity_offered() == false (no catalog alias match for «кварцевание»)
  → pre-resolver terminal answer
  → Planner: 0 · FullContext: 0
```

**Target:** catalog miss + possible capability/info → `normal`; categorical denial only for
**exact inactive authored record** or explicit hard non-target — not unknown dental wording.

### 2. Catalog miss as proof of absence

**Files:** `ingress_gate.py` L229–241 (`_offered_services_summary` — **active only**);
`core/target_client_data.py` L149–167 (`build_compact_service_catalog` — **skips inactive**).

Ingress offered list excludes inactive services → LLM cannot distinguish inactive vs absent.
**Catalog miss ≠ proof of non-offering.**

### 3. Compact / planner catalog — active vs inactive

| Source | Active | Inactive |
|---|---|---|
| `build_compact_service_catalog` | ✅ in planner prompt | ❌ omitted |
| `_offered_services_summary` (ingress) | ✅ | ❌ omitted |
| `service_catalog.json` loader | ✅ loaded | ✅ preserved in bundle if authored |

**Gap:** inactive records exist in schema but demo pack has **no** `active=false` fixture @ `d8dbe93`.
Phase 2 needs test fixture (governance-only note, not product change in Phase 1).

### 4. Planner: availability vs info vs price

**File:** `core/turn_planner_llm.py` L49–96.

Current `AspectKind` (`contracts/answer_plan.py` L7–23): price, payment, warranty, pain, included,
duration, comparison, stages, overview, contacts, contact_* — **no** `service_availability`.

Planner can set `service_id` from compact catalog but has **no typed availability intent**.
«Делаете КТ?» → may set `service_id=tomography`, `aspects=["overview"]` — indistinguishable from
informational overview vs availability yes/no.

**Target (minimal contract extension):** new aspect e.g. `service_availability` **or** dedicated
`route`/sub-intent in same single planner call — **not** second LLM.

### 5. Existing aspect suitability

| Aspect | Availability? | Info/capability? |
|---|---|---|
| `overview` | ambiguous | yes |
| `comparison` | no | partial |
| `duration` / `stages` | no | yes |
| contact_* | no | structured contacts path |

**Conclusion:** need new typed signal; do not overload `overview`.

### 6. Defect A — `tomography` without `content_ref`

**Files:**

- `clients/demo/target_response/service_catalog.json` — `tomography`: `active=true`, **no** `content_ref`
- `core/target_response_materialization_plan.py` L90–93 — content unfulfilled when `primary_content_ref is None`
- `core/target_scoped_response_evidence.py` L470–475 — `scoped_evidence_component_unfulfilled`

```text
Planner → service_id=tomography, aspects=[overview]
  → dispatch materialize service-bound content
  → assemble materials: selected_content_ref=None
  → plan.unfulfilled_components=('content',)
  → scoped_evidence_component_unfulfilled
  → target_fullcontext_error
  → Composer: 0
```

**Target:** availability question + active catalog match → `structured_service_availability`
**before** service-bound content assembly; skip content component requirement.

### 7. Deterministic service-availability capability seam

**File:** `core/target_structured_answer.py` — pattern for `clinic_contact` (0 Boundary/Composer/Semantic).

**Target:** extend `StructuredAnswerCapability` with `service_availability`:

```python
@dataclass(frozen=True)
class TargetStructuredServiceAvailabilityAnswer:
    client_id: str
    service_id: str
    service_name: str          # canonical catalog name
    active: bool
    provenance: Literal["target_response.service_catalog"]
    attribution_kind: str      # e.g. structured_service_availability
    content_ref: str | None    # only if authored + valid
```

Runtime hook: `core/target_runtime_turn.py` after contacts, before boundary — same short-circuit pattern.

### 8. Human-readable name and aliases

**Authority:** `service_catalog.json` → `name`, `aliases[]`.

Structured answer uses `name` field; aliases remain planner/ingress **hint only**, not runtime phrase lists.

### 9. Generic FullContext for unknown catalog object

**File:** `core/target_generic_fullcontext_content.py` + dispatch @ `d8dbe93`.

When Planner does **not** emit structured availability + catalog has no exact match:

- Ingress must not terminal-deny;
- Generic FullContext answers capability fact if present in MD;
- Data-gap: «В материалах клиники такая услуга или возможность не указана»;
- **No** new service_id; **no** price.

### 10. FAQ fact must not become service

Pack inconsistency rule: if FullContext text describes capability, runtime must not auto-promote to
catalog service or offer price. Validator may flag MD phrases implying standalone service without
catalog entry — **structural** check only, no semantic inference validator.

### 11. Source identity / attribution

Structured availability answer:

- `provenance=target_response.service_catalog`
- `attribution_kind=structured_service_availability`
- optional `content_ref` only when authored; missing `content_ref` on active service is **valid**
- presentation: no price followups, no marketing scenarios, no consultation_value bleed

### 12. Session focus

**File:** `core/target_runtime_turn_frame_hydration.py` + `should_skip_session_service_hydration`.

Availability/capability questions must not inherit stale `last_service_id` for routing decision.
Extend hydration guard for typed `service_availability` turns.

### 13. `/ask` and `/ask/stream` parity

Same ingress + runtime path via `_orchestrate_ask_turn` — no stream-only regression.

### 14. Sparse / new client packs

`build_compact_service_catalog` and structured availability must use runtime `client_id` bundle only —
no demo hardcodes. `scripts/validate_client_pack.py` — extend for inactive record + optional content_ref rules.

### 15. Ingress regex (existing — do not extend)

**File:** `ingress_gate.py` L115–128 — `_INGRESS_AVAILABILITY_VERB_RE` used only to decide whether to
**attach catalog to ingress prompt**, not target routing.

**Governance ban:** no **new** regex/phrase lists for availability vs capability routing.
Phase 2 typed Planner aspect replaces semantic dependence on ingress verb detection for **routing**.

---

## Pipeline gate inventory (delta)

| Gate | @ `d8dbe93` | Target |
|---|---|---|
| G2 Ingress | catalog miss → `service_not_offered` terminal | miss → `normal`; inactive exact → structured inactive |
| G3 Planner | no availability aspect | typed `service_availability` in same call |
| G4 Structured | contacts only | + `structured_service_availability` |
| G7 Dispatch | service_id → content package | availability bypasses content_ref requirement |
| G9 Evidence | content required for service-bound | availability spec: no content component |
| G9b Generic | capability FAQ | unchanged; receives catalog-miss turns |

---

## Proposed typed contract (Phase 2)

### Planner extension (minimal)

Add to `AspectKind`:

- `service_availability` — patient asks whether clinic offers catalog service X (yes/no presence).

Planner rules (prompt-owned, single call):

- Set `service_availability` when question is about **presence** of named/resolved service.
- Set `overview` / `duration` / etc. when question is **informational** about known service.
- `service_id` must match canonical catalog when availability aspect set.
- Do **not** set `service_availability` for capability/info («используете одноразовые материалы»).

### Runtime resolution

```text
if aspect service_availability and service_id valid:
    lookup catalog[service_id]
    if active: structured_service_availability_yes
    elif inactive record: structured_service_availability_no
    else: fall through to generic (should not happen if planner valid)
elif service_id valid and content question:
    existing service-bound content path
elif catalog miss or capability phrasing:
    generic_fullcontext_content
```

### Price / marketing boundary

`structured_service_availability` spec:

- `required_components=()` or dedicated component without price
- `allow_marketing_facts=false`, `allow_cta=false`, `allow_price=false`
- no family price, no MD money extraction

---

## Forbidden solutions (Phase 1)

- NO regex/phrase lists for availability vs capability routing  
- NO second classifier / selector / pipeline  
- NO adding capability facts to `service_catalog.json`  
- NO auto-creating services from MD  
- NO price inheritance on availability answer  
- NO Semantic/Numeric/Contact Verifier changes  
- NO RAG / legacy fallback  
- NO frozen artifact changes  
- NO A9 / prompt tuning loops in governance  

---

## Implementation seams (Phase 2 allowlist pointer)

See `TASK.md` § Allowlist (implementation). Key files:

| Seam | File(s) |
|---|---|
| Ingress catalog-miss policy | `ingress_gate.py` |
| Planner aspect | `contracts/answer_plan.py`, `core/turn_planner_llm.py`, `core/turn_frame_from_raw.py` |
| Dispatch / evidence | `core/target_turn_frame_dispatch.py`, `core/target_scoped_response_evidence.py`, `core/target_response_materialization_plan.py` |
| Structured capability | `core/target_structured_service_availability.py` (**NEW**), `core/target_structured_answer.py`, `core/target_runtime_turn.py` |
| Session | `core/target_runtime_turn_frame_hydration.py` |
| Pack validator | `scripts/validate_client_pack.py`, `docs/CLIENT_PACK_AUTHORING.md` |
| Tests | 30-scenario offline matrix |

**KEEP:** Generic FullContext @ `d8dbe93`, structured contacts fast path, AC1–AC3 price, verifiers.

---

## STOP

Phase 1 ends at governance commit + PRE-CODE PASS. No product implementation until separate owner GO.
