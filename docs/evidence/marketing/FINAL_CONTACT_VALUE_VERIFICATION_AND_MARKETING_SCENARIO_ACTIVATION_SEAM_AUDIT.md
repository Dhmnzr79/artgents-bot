# FINAL_CONTACT_VALUE_VERIFICATION_AND_MARKETING_SCENARIO_ACTIVATION — seam audit

**Дата:** 2026-07-27  
**Baseline:** `codex/stage-a` @ `225ee56e1823f4b72ff87de691655a008de06369`  
**Режим:** governance / docs / tests only · **NO product code / NO LIVE / NO LLM**  
**Owner GO:** Phase 1 governance only; implementation blocked until PRE-CODE ✅ + separate owner GO

## Preflight

| Check | Result |
|---|---|
| Branch | `codex/stage-a` ✅ |
| `HEAD` == `origin` @ `225ee56` | ✅ (governance start) |
| Prior milestone `FINAL_FULLCONTEXT_DIALOGUE_RUNTIME_CONVERGENCE` | COMPLETE @ `225ee56` |
| Typed contact subaspects + per-field evidence | ✅ landed Phase 2 |
| Live contacts still verifier-blocked on natural wrappers | ✅ proven |
| Live scenario amplifiers never written to session | ✅ proven |

## Executive summary

Phase 2 (`225ee56`) fixed marketing-vs-final-spec permission conflict and introduced typed
contact evidence blocks, but two production seams remain:

| Seam | Symptom (live) | Root cause class |
|---|---|---|
| **A** | «Где вы находитесь?» → `target_verifier_clinic_contact_missing` `clinic_contact:address` | Verifier requires **full rendered evidence line** substring, not canonical scalar |
| **B** | `shown_fact_ids` populated; `shown_amplifier_refs=[]` after scenario turns | `resolve_bound_marketing_flags()` zeroes scenarios when `include_initial_block=False` |
| **C** | `service_id=None` + valid topic cannot select topic-scoped amplifiers | Selector eligibility + scenario rule schema gap (`allowed_topics`) |
| **D** | Planner mislabels some turns (producer) | Planner prompt / classification — **not** runtime selector; document only |

Lower-level tests that copy evidence text verbatim into Composer fakes **overstate** contact pass rate.

---

## Seam A — Contact value verification (not label matching)

### Proven live path

```text
Planner → contact_address aspect
  → materialize_clinic_contact_primary_evidence(fields=("address",))
      block.text = "Адрес: г. Москва, ул. Тверская, 12, стр. 1 (м. «Пушкинская», 5 мин пешком)"
      authority = clinic_policies.yaml → contact.address_display
  → Composer (natural wrapper, e.g. «Мы находимся по адресу …»)
  → Verifier L733–735: block.text not in response.text
  → target_verifier_clinic_contact_missing / clinic_contact:address
```

### Current code (read-only @ `225ee56`)

| Layer | File | Behavior |
|---|---|---|
| Authority | `core/target_contact_authority.py` | `load_clinic_contact_facts` ← `clinic_policies.yaml` only |
| Evidence | `core/target_contact_authority.py` L132–181 | Per-field `clinic_contact:{field}` blocks with label prefix |
| Verifier | `core/target_response_verifier.py` L728–735 | `block.text not in response.text` — **entire line** required |
| Fallback | `core/target_contact_authority.py` `fallback_answer_with_phone` | phone only ✅ |

### Target semantics (owner normative)

- Authority remains `clinic_policies.yaml → contact` only.
- Evidence stays typed and granular (`clinic_contact:phone`, `:address`, …).
- Verifier checks **canonical scalar value** for each requested field.
- Label prefixes (`Адрес:`, `Телефон:`), word order, Markdown wrappers — **not** compared.
- Allowed: technical Unicode/whitespace normalization only — **no fuzzy matching**.
- Phone/address/hours/parking/WhatsApp values must not be altered or shortened.
- Mixed address+parking requires both canonical values present.
- Unrequested contact fields must not be required.
- Missing requested value → governed data-gap (not invented contact).
- Required strict commercial facts unchanged in this milestone.

### Mandatory live-like test contour (implementation)

Composer fake must **not** echo evidence lines. Example pass case:

```text
Мы находимся по адресу {canonical_address_display}
```

Changed or truncated scalar must block.

### Seam A verdict

| Item | Status |
|---|---|
| Typed evidence blocks | **Connected** (Phase 2) |
| Canonical authority source | **Connected** |
| Value-only verification | **Disconnected** — substring on full rendered line |
| Natural-language wrappers | **Broken** |

---

## Seam B — Marketing scenarios coupled to initial block

### Proven live observation

Persisted session after scenario-bearing turns:

- `shown_fact_ids` — contains initial commercial facts (initial block path works).
- `shown_amplifier_refs` — `[]` after all scenario turns (amplifiers never applied).

### Mechanism (read-only @ `225ee56`)

```text
TurnFrame.marketing_scenarios (0–2, planner-owned)
  → target_turn_frame_bound_response.run_target_offline_turn_frame_bound_response
      resolve_bound_marketing_flags(turn_frame, bound_spec, …)
        include_initial_block = should_include_initial_marketing_block(...)
        if not include_initial_block:
            return False, (), None          # ← scenarios zeroed
        scenarios = marketing_scenarios
  → select_target_marketing(..., include_initial_block, marketing_scenarios)
```

`should_include_initial_marketing_block` returns `False` for:

- contact paths (`contact_fields_from_turn_frame` not None)
- content-only / doctors-only / service-optional specs
- price-primary answers
- clarify turns

Therefore **any** turn where initial block is forbidden also drops scenario amplifiers — even when
planner correctly emitted `pain_fear`, `cost`, etc.

### Normative architecture (owner decision)

| Mechanism | Role | Independence |
|---|---|---|
| `include_initial_block` | Proactive initial commercial close | Independent |
| `marketing_scenarios` | Reactive amplifier on expressed concern | Must survive `include_initial_block=False` |

Safety gates (unchanged):

- scenarios only when boundary `none`
- contacts, terminal, clarify, handoff, verifier-block → no marketing hooks
- no eligible amplifier → main answer only, no invented hook
- limits: scenarios ≤2, amplifiers ≤2, marketing facts ≤3, cadence via `shown_amplifier_refs`

### Seam B verdict

| Item | Status |
|---|---|
| Planner produces scenarios | **Partial** (live observations mixed) |
| Runtime preserves scenarios | **Broken** — coupled to initial block |
| Selector `select_target_marketing` | **Connected** but receives `()` |
| Session `shown_amplifier_refs` | **Never written** for scenarios |

---

## Seam C — Scenario applicability schema gap

### Current `TargetScenarioRule` (@ `contracts/response_schema.py` L427–437)

```yaml
ordered_amplifier_refs: [...]
allowed_semantic_contexts: [service | price | doctors | default]
```

No `allowed_topics` on scenario rules. Topic/family applicability today is indirect:

- `TargetCommercialFact.allowed_topics` in `facts.json` (e.g. `free_implant_consult`)
- `_fact_is_eligible` L93–96: `service_id is None and fact.allowed_topics` → **False** (blocks topic-only facts)
- KB/doctor refs: no topic gate on scenario rules

Demo `marketing.yaml` scenario pools use `allowed_semantic_contexts: [service]` only — no
`default` / topic-broad path for `service_id=None` implantation FAQ with concern.

### Minimal schema extension (recommended — implementation)

Extend existing `TargetScenarioRule` (no new selector):

```yaml
TargetScenarioRule:
  ordered_amplifier_refs: [...]
  allowed_semantic_contexts: [...]
  allowed_topics: [...]   # NEW — empty = no topic gate; non-empty = turn topic must match
```

Wire in `select_target_marketing` scenario applicability loop (L205–211) and
`_fact_is_eligible` for `service_id=None` + `allowed_topics` on facts.

**Forbidden:** new selector, regex lists, second classifier, retry/voting/thresholds.

### Seam C verdict

| Item | Status |
|---|---|
| Authored scenario pools | **Present** (`clients/demo/target_response/marketing.yaml`) |
| Topic applicability on rules | **Missing** |
| Topic-only fact eligibility | **Broken** for amplifiers when `service_id=None` |
| Demo hardcode | **Forbidden** — use client data only |

---

## Seam D — Planner scenario labeling (producer only)

Live planner observations (not fixed in this milestone's runtime scope):

| User message | Observed scenario | Expected |
|---|---|---|
| «боюсь боли» | `pain_fear` | ✅ |
| «боюсь, что имплант не приживётся» | `pain_fear` | `result_reliability` |
| «переживаю, что имплантация дорогая» | `cost` | ✅ label; amplifier still blocked (Seam B) |
| «сколько стоит All-on-4?» | `cost` | **none** (direct question) |
| «кто делать будет?» | `doctor_trust` | **none** without expressed doubt |

Planner prompt already states direct-question ≠ scenario (`core/turn_planner_llm.py` L86–89).
Implementation may refine prompt examples; **no regex routing**.

---

## Cross-seam session write path

```text
materialized turn
  → write_target_runtime_session_after_materialized
      shown_fact_ids ← commercial facts from selection
      shown_amplifier_refs ← amplifier_refs from marketing selection
```

When `marketing_scenarios=()` at selector input, `amplifier_refs` stays empty → session never
accumulates amplifier cadence.

---

## Proposed implementation surface (governance allowlist — not executed here)

| Area | Files (candidate) |
|---|---|
| Contact value verify | `core/target_contact_authority.py`, `core/target_response_verifier.py` |
| Decouple scenarios | `core/target_presentation_turn_projection.py` (`resolve_bound_marketing_flags`) |
| Selector applicability | `core/target_marketing_selector.py`, `contracts/response_schema.py` |
| Demo policy data | `clients/demo/target_response/marketing.yaml`, `pricebook/facts.json` (if needed) |
| Planner prompt | `core/turn_planner_llm.py` (label examples only) |
| Tests | harness + implementation checker (30 scenarios) |

---

## STOP

This audit authorizes **governance commit only**. No product code until PRE-CODE ✅ + owner GO.
