# A9R — Patient scope authority re-audit (governance)

**Status:** governance checkpoint only · **NO LIVE / NO LLM / NO PRODUCT AUTHORITY**

**Baseline:** `codex/stage-a` @ `b35ed1c` (AC3 complete) · product HEAD `aa8e6dd`

**Related frozen artifacts (immutable — do not edit):**

- `evals/v5/demo/patient_scope_shadow_matrix.json` (v1)
- `evals/v5/demo/patient_scope_shadow_matrix_v2.json` (v2)
- `eval_patient_scope_a9_last.txt` (v1 live raw, gitignored)
- `docs/evidence/a9/PATIENT_SCOPE_SHADOW_AUDIT_A9.md`

---

## Goal (A9 product intent — not enabled in A9R)

From free text, extract **neutral patient situation facts** and feed the **same** `EffectiveScope` used by AC1–AC3. A9 **extracts only**; AC2 remains sole applicability/ranking/offers authority; AC3 remains `ResponseStage` + UI authority; medical boundary stays separate.

**Allowed fact families (explicit patient statements only):**

| Axis | Values | Notes |
|------|--------|-------|
| `extent` | `one_tooth`, `few_teeth`, `full_arch`, `unknown` | Canonical AC1 extent |
| `jaw` | `upper`, `lower`, `both`, `unknown` | In `TurnFrame.patient_scope`; **not yet** on `EffectiveScope` — A9R1 must decide projection |
| `stage` | `natural_tooth_present`, `extraction_context`, `implant_placed`, `unknown` | AC2 `PatientStage`; UI stage uses subset via `UiStageAction` |
| modifiers | `reported_bone_deficit` (optional) | Never promote to diagnosis or service choice |

**Forbidden:** service selection, treatment choice, price inference, diagnosis, regex/phrase dictionaries, client-specific disease rules, inferring scope from service name alone («Что такое All-on-4?» ≠ full_arch), treating bare «имплант» as `implant_placed`.

---

## Why A9 was paused (read-only findings)

| Date / checkpoint | Finding |
|-------------------|---------|
| v1 live audit (`PATIENT_SCOPE_SHADOW_AUDIT_A9.md`) | **0** exact positive axes on frozen live subset; composite **0/9**; infra trusted, quality red |
| Scalar bridge | **10/10** deterministic (legacy `patient_situation` → scope) |
| Native nested extraction | Positive recognition **0** on first live sample |
| AC3 governance | Free-text scope **explicitly deferred**; product must not read `TurnFrame.patient_scope` |
| STRANGLER_ROADMAP | Live re-audit + authority decision unchecked; requires owner GO + TASK + checker |

**Pause formula:** measurement exists and is honest; **quality gate failed**; **no authority wiring** until A9R gates pass.

---

## Current seam audit (post-AC3 @ `aa8e6dd`)

### Producers of `TurnFrame.patient_scope`

| Producer | Location | Role |
|----------|----------|------|
| Planner LLM JSON | `core/turn_planner_llm.py` | Requests nested `patient_scope` object in planner output |
| Native parser | `core/turn_frame_from_raw.py` | Parses sibling `patient_scope` when present |
| Scalar bridge | `core/turn_frame_from_raw.py` | Maps legacy `patient_situation` enum when native sibling absent |
| Frame publish | `core/runtime_turn_frame.py` | Publishes full `TurnFrame` to `request.ctx["runtime_turn_frame"]` |

**No second LLM call:** single `plan_turn_attempt()` → `build_turn_frame_from_raw()` per turn.

### Shadow consumers (allowed today)

| Consumer | Location |
|----------|----------|
| Eval harness v1/v2 | `evals/v5/run_patient_scope_shadow_eval*.py` |
| AST product firewall | `tests/test_turn_frame_shadow.py` |
| Contract/unit tests | `tests/test_turn_frame_from_raw.py`, `tests/test_patient_scope_*` |

### Product consumers of `TurnFrame.patient_scope`

**None.** Grep confirms no read in `core/target*.py`, `orchestration/*.py` price path. Firewall allows only `core/turn_frame_from_raw.py` in product tree for `patient_scope` writes.

### Parallel legacy (not A9 authority — out of A9R scope)

| Component | Risk |
|-----------|------|
| `core/patient_situation.py` | Legacy scalar `patient_scope` enum in product situation path |
| `core/patient_scope_cues.py` | Regex price cues — **explicitly forbidden** for A9R authority |
| `core/patient_situation_routing.py` | Soft retrieval bias from legacy scope |

A9R **does not** retire legacy paths; authority wiring must not duplicate regex routing.

### AC1 product scope path (authority today)

```
UiScopeAction / UiStageAction click
  → session patient_facts
  → resolve_effective_scope()   # core/target_effective_scope.py
  → AC2 run_target_scope_aware_selection
  → AC3 ResponseStage + UI
```

`EffectiveScope` fields: `extent`, `stage`, `topic`, `source`, `provenance` — **no `jaw` yet**.

Priority today (`resolve_effective_scope`):

1. current `UiScopeAction`
2. current `UiStageAction` (+ extent from fresh session when needed)
3. fresh session `patient_facts` (same topic, within turn-age threshold)
4. all-unknown

**No `TurnFrame.patient_scope` input.**

Session lifecycle (`core/target_runtime_session.py`, `core/target_runtime_turn.py`):

- `sync_session_patient_facts_topic()` clears facts on topic mismatch
- `mem_reset()` clears session
- SID isolation via `session.mem_get(sid)`
- UI clicks write structured facts; free-text write **not implemented**

### Future authority attachment point (A9R3 — docs only)

Proposed merge slot in `resolve_effective_scope()` **after** typed UI actions, **before** session carry:

```text
1. current UiScopeAction
2. current UiStageAction
3. current-turn confident patient_scope projection (A9) — NEW
4. fresh session patient_facts
5. unknown
```

**Correction rule:** explicit current-turn correction with sufficient confidence **replaces** stale session fact for the same axis/topic. Uncertain or contradictory extraction → **do not** silently overwrite session.

**Projection layer (A9R1):** `PatientScopeFrame` → `EffectiveScope` subset:

| TurnFrame axis | EffectiveScope | Gap |
|----------------|----------------|-----|
| `extent` | `extent` | direct |
| `stage` (`extraction_context`, `implant_placed`) | `stage` | map 1:1 |
| `natural_tooth_present` | `stage` | **not in `PatientCareStage` today** — contract extension or merge-only projection required |
| `jaw` | — | add `jaw` to `EffectiveScope` in A9R1 or drop jaw from A9 authority until AC2 needs it |

### Planner reuse (no second LLM)

`orchestration/planner_turn.py` → `plan_turn_attempt()` already returns `patient_scope` inside `TurnFrame`. A9R authority must **consume planner output**, not add retrieval/RAG or a second scope LLM.

### Medical boundary separation

| Layer | Mechanism |
|-------|-----------|
| Design | Urgency/pain/diagnosis excluded from patient scope (`PATIENT_SCOPE_DESIGN_A9.md`) |
| Pre-planner | `ingress_manual_contact` hard-stop before planner |
| Runtime | `target_runtime_turn.py` medical boundary parallel to scope; no `patient_scope` read |
| Eval taxonomy | `not_applicable` for manual-contact cases (v2 harness) |

### Frozen v1/v2 matrix fitness

| Artifact | Fitness for A9R |
|----------|-----------------|
| v1 matrix + raw | Historical baseline; **immutable**; proved safe defaults |
| v2 matrix | 30 live + 14 deterministic; scores **shadow** `TurnFrame.patient_scope`, not `EffectiveScope` merge |
| v2 harness | Reuses planner metadata; manual-contact taxonomy; **no session merge scoring** |

**A9R matrix** (`patient_scope_a9r_matrix.json`) adds EffectiveScope/session-merge expectations required for authority prep **without modifying** v1/v2 files.

### C2b drift (documented for implementer)

- `TurnFrame` is runtime product frame, but `patient_scope` remains **policy-forbidden** for dispatch/pricing/UI.
- Legacy `TurnPlan` / `_project_legacy_turn_plan_raw` strip path removed; seam is TurnFrame-direct.
- Some native contract tests may reference removed projection helpers — A9R1 implementation must reconcile without changing frozen A9 artifacts.

---

## Gates (mandatory sequence)

| Gate | Scope | Authority |
|------|-------|-----------|
| **A9R** (this checkpoint) | Read-only audit, TASK, docs, frozen A9R matrix, PRE-CODE | forbidden |
| **A9R1** | Offline contract, `PatientScopeFrame`→`EffectiveScope` projection, merge module, eval harness for A9R matrix (deterministic fixtures only) | forbidden |
| **A9R2** | One owner-approved live eval using **existing** planner (no second LLM); raw artifact + checksum | measurement only |
| **A9R3** | Authority wiring into `resolve_effective_scope` after quality gates | owner GO required |
| **Post-authority** | Widget E2E offline + optional live proof | separate TASK |

**Explicit stops:** A9R2 without owner live permission; A9R3 without A9R2 pass; widget E2E before authority; any regex scope parser; reading `patient_scope` in AC2/AC3 selectors.

---

## A9R frozen eval matrix

Path: `evals/v5/demo/patient_scope_a9r_matrix.json`

Schema: `a9r.patient_scope_authority_prep.v1`

Covers user-mandated scenarios: extent/jaw/stage positives, corrections, typos, All-on-4 info/price without scope inference, bare «имплант», ambiguity/conflict, topic change, stale session, reset, SID isolation.

Contract test: `tests/test_patient_scope_a9r_matrix_contract.py` (schema + frozen blob hash only in A9R).
