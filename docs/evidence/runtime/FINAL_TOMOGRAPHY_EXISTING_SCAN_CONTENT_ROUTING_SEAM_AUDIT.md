# FINAL_TOMOGRAPHY_EXISTING_SCAN_CONTENT_ROUTING — seam audit

**Дата:** 2026-07-27  
**Baseline:** `codex/stage-a` @ `a1dc4f2`  
**Режим:** governance / docs / tests only · **NO product code / NO LIVE / NO LLM**  
**Owner GO:** Phase 1 governance only; implementation blocked until PRE-CODE ✅ + separate owner GO

## Preflight

| Check | Result |
|---|---|
| Branch | `codex/stage-a` ✅ |
| `HEAD` == `origin/codex/stage-a` @ `a1dc4f2` | ✅ |
| Working tree clean at governance start | ✅ |
| Prior milestone landed | `FINAL_PRICE_ONLY_SOURCE_SUFFICIENCY_CONVERGENCE` @ `a1dc4f2` |
| Semantic/Numeric/Contact Verifier | **KEEP** — no change without reproducible defect |

## Executive summary

**Migration loss:** в legacy `clients/demo/service_catalog.json` (до Checkpoint B) был согласованный demo-факт
про готовое КТ до одного месяца. При удалении legacy-каталога факт **не перенесли** в `target_response/**`
или `md/`.

**Runtime defect:** вопрос «а если у меня есть своё КТ» после availability/price continuity классифицируется
Planner как `service_availability` → deterministic short-circuit повторяет «Да, клиника оказывает услугу КТ»
вместо FAQ/content про уже имеющееся исследование.

**Request ID (live repro):** `61efdc17-b6d0-42b8-b287-d4858527bbb9`

**Target:** canonical MD для `tomography` + `content_ref` в catalog + уточнение semantic rules Turn Planner
(без нового aspect/route/handler/regex). Availability yes/no и price-only 3 000 ₽ **не регрессируют**.

---

## Normative concepts (binding)

### Agreed demo fact (owner-confirmed)

> При наличии свежего КТ (до 1 месяца) врач может использовать уже готовое исследование.

- «Свежее» = давность **до одного месяца** (owner decision).
- **Не придумывать:** требования к диску, флешке, DICOM, месту выполнения, качеству снимка.
- **Не дублировать** в `service_catalog.json` facts, pricebook, marketing.
- Цена КТ **3 000 ₽** остаётся только в `pricebook/services/tomography.default.json`.

### Service availability (unchanged)

Прямой вопрос «Делаете КТ?» / «Проводите КТ?» → typed `service_availability` →
`structured_service_availability` (0 Boundary/Composer/Semantic). `content_ref` **не обязателен**
для yes/no.

### Existing-scan / own-scan FAQ (new binding)

Вопросы про **уже имеющееся**, **своё**, **актуальность**, **повторное КТ**, **нужно ли новое** —
это **content/overview FAQ**, не availability.

- Planner: `aspects=["overview"]` (или эквивалентный content aspect), **не** `service_availability`.
- `service_id=tomography` и `followup_of=tomography` **допустимы** (continuity).
- Runtime: service-bound content via `tomography.content_ref` → FullContext Composer → existing Verifiers.

### Catalog vs content store

`service_catalog.json` — authority для availability и `service_id` binding only.
Текст фактов — **только** в `md/{content_ref}`.

---

## Documented migration loss

### Legacy source (pre–Checkpoint B)

```bash
git grep -n "при наличии свежего КТ" "50c6cf9^" -- clients/demo
# 50c6cf9^:clients/demo/service_catalog.json:21:
#   "при наличии свежего КТ (до 1 месяца) врач может использовать уже готовое исследование"
```

Legacy `tomography` entry stored the fact in a **`facts` array** inside `clients/demo/service_catalog.json`
(alongside title/aliases/price_key). File removed @ Checkpoint B; `target_response/service_catalog.json`
gained `tomography` **without** `content_ref` and **without** the fact anywhere in MD.

### Current target catalog @ `a1dc4f2`

`clients/demo/target_response/service_catalog.json` — `tomography.active=true`, **no `content_ref`**,
price-only offer `tomography.default` @ 3 000 RUB. Agreed existing-scan rule **absent** from corpus.

---

## Documented runtime defect

### Cross-turn repro (owner report)

| Turn | User | Planner (actual) | Runtime (actual) | Expected |
|---|---|---|---|---|
| 1 | «Делаете 3D-диагностику?» | `service_availability`, `tomography` | deterministic yes | ✅ |
| 2 | «А сколько стоит?» | `price_lookup`, `tomography` | 3 000 ₽ materialized | ✅ @ `a1dc4f2` |
| 3 | «А если у меня есть своё КТ?» | `service_availability`, `tomography`, `followup_of=tomography` | «Да, клиника оказывает услугу КТ» | ❌ FAQ: fresh scan ≤1 month rule |

**Root cause:** Planner `service_availability` rule is triggered by service mention + continuity, not by
whether patient asks **if clinic performs** the procedure vs **whether own scan is acceptable**.

**Consumer path:** `service_availability_requested()` → `target_turn_frame_dispatch` L448 →
`materialize_structured_service_availability_turn_response` — **hard short-circuit** before Composer.

---

## Phase 1 seam audit checklist

### 1. Producer — Turn Planner `service_availability`

| Item | File | Finding @ `a1dc4f2` |
|---|---|---|
| Aspect definition | `core/turn_planner_llm.py` L59–63 | `service_availability` = «делаете/есть ли/проводите + услуга»; excludes technology/materials but **not** own-scan / existing-scan / freshness |
| Continuity | L72–74 | `followup_of` preserves `tomography` — correct for price, **misleading** for availability misclass |
| No second call | single `_SYSTEM` prompt | Target fix = **semantic boundary text only** — no new LLM invocation |

### 2. Deterministic availability short-circuit (consumer)

| Step | File | Behavior |
|---|---|---|
| Gate | `core/turn_frame_from_raw.py` `service_availability_requested()` L541–562 | True when sole aspect is `service_availability` + valid `service_id` |
| Dispatch | `core/target_turn_frame_dispatch.py` L448–473 | materialize structured availability policy |
| Runtime | `core/target_runtime_turn.py` L254+ | `materialize_structured_service_availability_turn_response` — 0 Composer |
| Text | `core/target_structured_service_availability.py` L92–98 | fixed yes/no template from catalog name/active |

**Implication:** any Planner `service_availability` for `tomography` **cannot** reach MD content path.
Fix is **Planner classification**, not bypassing short-circuit for this case.

### 3. Service-bound content package

| Layer | File | @ `a1dc4f2` | Phase 2 target |
|---|---|---|---|
| Catalog | `target_response/service_catalog.json` | no `content_ref` | `content_ref: diagnostics__service__tomography.md` |
| MD corpus | `clients/demo/md/` | **missing** tomography doc | CREATE `diagnostics__service__tomography.md` |
| Assembly | `core/target_offline_response_assembly.py` | binds `service.content_ref` | will select new MD |
| Generic guard | `core/target_generic_fullcontext_content.py` L196 | skips generic when availability | unchanged |

### 4. Composer source ownership

When `overview` + `service_id=tomography` + `content_ref` set:

`Planner → dispatch materialize → offline package → scoped evidence → composer request → FullContext Composer`.

Composer `_exact_sources` requires `selected_content_ref in owned_content_refs` — satisfied once catalog
links MD. **No Verifier change.**

### 5. Source identity and follow-up projection

| Concern | Owner | Notes |
|---|---|---|
| `primary_content_ref` | Composer output + verifier | must be valid MD ref from new doc |
| MD follow-ups | `suggest_h3` in frontmatter | ≤2 authored follow-ups; no duplicates |
| Price follow-ups | offer JSON | unchanged; price-only path separate |
| Presentation | `core/target_presentation_decision.py` L123+ | source-driven buttons when `primary_content_ref` set |

### 6. Session continuity

Paths to preserve @ implementation:

1. availability → price → existing-scan FAQ  
2. direct existing-scan question with fresh SID  
3. `followup_of=tomography` after price turn  

**No session reset.** SID isolation unchanged (`test_sid_isolation_for_patient_facts` regression).

### 7. `/ask` and `/ask/stream`

Widget-faithful harness: `orchestrate_via_app` in
`tests/test_final_fullcontext_dialogue_runtime_convergence_harness.py` — fakes at LLM backend boundary only.
Parity required for FAQ turns (scenarios 9, 16).

### 8. Validator and authoring

| Check | File | Notes |
|---|---|---|
| Pack validator | `scripts/validate_client_pack.py` | `content_ref` → existing `md/` file |
| Authoring law | `docs/CLIENT_PACK_AUTHORING.md` | catalog ≠ content store; price in pricebook only |
| Legacy mirrors | — | **do not restore** `clients/demo/service_catalog.json` |

---

## Proposed Phase 2 target (binding for implementation)

### Canonical content

Create `clients/demo/md/diagnostics__service__tomography.md`:

- frontmatter: `doc_type: service`, `topic: diagnostics` (or agreed topic), aliases for own-scan phrasing;
- body: agreed fact **дословно**; section on freshness ≤1 month;
- `suggest_h3`: ≤2 follow-ups (e.g. need new scan, preparation) — authored, no invention beyond owner law.

Link in catalog:

```json
"content_ref": "diagnostics__service__tomography.md"
```

**Do not** add catalog `facts`, pricebook text, or marketing amplifiers for this rule.

### Routing (Planner semantic boundary only)

Extend `core/turn_planner_llm.py` `_SYSTEM` `service_availability` paragraph:

- **Use** `service_availability` only when patient asks whether clinic **performs/offers** the procedure.
- **Do not use** for: own/existing scan, bringing prior CT, scan age/freshness, whether repeat CT needed,
  preparation — return `overview` (or content aspect) with `service_id=tomography` when continuity applies.

**Forbidden:** regex lists, phrase routers, new aspect, new handler, new pipeline, session reset.

### Target runtime path (existing-scan FAQ)

```text
Planner(overview + tomography)
  → service content_ref (diagnostics__service__tomography.md)
  → FullContext Composer
  → existing Semantic/Numeric/Contact Verifiers
  → presentation / MD follow-ups (≤2)
```

---

## Acceptance matrix (Phase 2 — 16 scenarios)

Offline widget-faithful via `_orchestrate_ask_turn`; fakes at provider boundary; **NO LIVE / NO LLM**.

| # | Scenario | Expected |
|---|----------|----------|
| 1 | «Делаете КТ?» | deterministic yes, Composer=0 |
| 2 | «Сколько стоит КТ?» | 3 000 ₽ from pricebook |
| 3 | availability → price → «А если у меня есть своё КТ?» | content materialized, **not** availability |
| 4 | Direct «Можно прийти со своим свежим КТ?» | fact ≤1 month materialized |
| 5 | «Моему КТ два месяца» | do not claim it qualifies |
| 6 | «Нужно ли делать новое КТ?» | ≤1 month rule, no diagnosis |
| 7 | `primary_content_ref` valid on FAQ answer | grounded MD ref |
| 8 | ≤2 MD follow-ups, no duplicates | from `suggest_h3` |
| 9 | `/ask` parity | matches stream meta |
| 10 | `/ask/stream` parity | matches ask meta |
| 11 | KT price path unchanged | 3 000 ₽, offer evidence |
| 12 | KT availability unchanged | Composer=0 yes/no |
| 13 | Other availability services unchanged | e.g. whitening, all_on_4 |
| 14 | Generic FullContext unchanged | capability gaps still generic |
| 15 | No invented DICOM/disk/quality requirements | text audit |
| 16 | `validate_client_pack demo` passes | offline validator |

---

## Forbidden solutions

- Restore legacy `clients/demo/service_catalog.json` or mirror files
- Put FAQ text in catalog facts, pricebook, or marketing.yaml
- Regex / phrase-list routing for own-scan detection
- New handler, selector, route, or second pipeline
- Bypass availability short-circuit with runtime `if` on user text
- Session reset to fix continuity
- Semantic/Numeric/Contact Verifier changes
- Fake `content_ref` stub without real MD body
- LIVE / LLM / E2E in implementation milestone
- Weaken protected acceptance / frozen artifacts

---

## Related milestones (regression anchors)

| Milestone | Relevance |
|---|---|
| `FINAL_SERVICE_AVAILABILITY_AND_CLINIC_CAPABILITY_ROUTING` | availability short-circuit — **keep** |
| `FINAL_PRICE_ONLY_SOURCE_SUFFICIENCY_CONVERGENCE` | tomography price-only @ 3 000 ₽ — **keep** |
| `FINAL_GENERIC_FULLCONTEXT_CONTENT_AUTHORITY` | generic capability path — **keep** |

---

## STOP (Phase 1)

After governance commit + PRE-CODE PASS — **stop**. No product/demo-data changes until owner GO for Phase 2.
