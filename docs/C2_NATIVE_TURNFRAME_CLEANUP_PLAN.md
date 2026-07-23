# C2 — Native TurnFrame cleanup plan

**Status:** plan only — no C2 implementation  
**Baseline:** post-S70 / C1 (`codex/stage-a`)  
**Authority:** Owner Cleanup-series C2 (separate governance commit required before code)  
**Mode:** read-only audit of real call sites; no product changes in this document

---

## Executive summary

Today the product runs **one** turn-planner LLM call (`plan_turn_attempt`) but consumes **two** derived artifacts:

| Branch | Builder | Product use today | Storage |
|--------|---------|-------------------|---------|
| **legacy_plan** (`TurnPlan`) | `_validate_plan` → guards → `legacy_plan` | **Yes** — `run_resolver_turn` builds `DecisionFrame`, publishes `turn_plan` to ctx | `request.ctx["turn_plan"]` via `publish_turn_plan` |
| **shadow_frame** (`TurnFrame`) | `build_turn_frame_from_raw` | **Yes (target only)** — loaded by `load_runtime_turn_frame` after `record_planner_attempt_shadow` | `request.ctx["turn_frame_shadow"]` |

Target FullContext already answers from **TurnFrame** (via shadow ctx), not from `TurnPlan`. C2 flips the remaining legacy seams so **one planner call → one native TurnFrame → target pipeline**, removing `legacy_plan`, `turn_frame_adapter`, resolver fail-open, and legacy session-focus reads — without a second LLM.

```text
POST /ask
  run_pre_resolver_turn
  run_resolver_turn                    ← C2: planner → TurnFrame only; no resolver fallback
    plan_turn_attempt (1× LLM)
      ├─ build_turn_frame_from_raw     ← C2: primary product frame
      └─ [DELETE] legacy_plan branch
    record_planner_attempt_shadow      ← C2: rename → primary frame ctx (drop “shadow” naming)
  orchestrate_target_fullcontext_turn
    load_runtime_turn_frame
    hydrate_target_runtime_turn_frame_from_session
    … boundary → dispatch → composer → verifier → widget
```

---

## 1. Where `legacy_plan` is created

**Single creation site:** `core/turn_planner_llm.py` → `plan_turn_attempt()` (lines ~558–685).

Flow after one LLM JSON parse (`obj`):

1. **Shadow branch first (unchanged order):** `build_turn_frame_from_raw(obj, allowed_topics=…, allowed_service_ids=…)` → `shadow_frame` or `shadow_degraded`.
2. **Legacy branch:**  
   - `_project_legacy_turn_plan_raw(obj)` — strips only `patient_scope` key; all other raw keys preserved (`:105–107`).  
   - `_validate_plan(...)` — topic sanitize + strict `TurnPlan.model_validate` (`:366–417`).  
   - `_apply_protocol_choice_guard(plan, q, client_id, sid)` — implant protocol downgrade (`:162–211`).  
   - `_apply_focus_followup_enrichment(plan, q, sid)` — session `last_subject` + vague follow-up (`:140–160`).  
   - Result assigned to `legacy_plan` (`:664`).

**Wrapper:** `plan_turn(q, sid, client_id)` returns `plan_turn_attempt(...).legacy_plan` only (`:688–690`).

**PlannerAttempt envelope:** `contracts/planner_attempt.py` — `legacy_plan`, `shadow_frame`, `shadow_status` with invariants (`ok` requires both legacy + shadow valid; `partial` allows legacy `None` or invalid shadow metadata).

**Early exits (no LLM, no `legacy_plan`):**

| Condition | Return | File:lines |
|-----------|--------|------------|
| Empty message | `_not_available_attempt()` | `turn_planner_llm.py:565–566` |
| Empty service catalog (`build_compact_service_catalog`) | `_not_available_attempt()` | `:567–569` |
| LLM/JSON failure | `_not_available_attempt()` after log | `:608–610` |
| `_validate_plan` exception | `legacy_plan` stays `None`; shadow may still exist | `:665–666` |

**Session inputs to legacy guards (not TurnFrame today):**

- `_session_focus_service_id(sid)` → `core/dialog_focus._focus_from_last_subject(mem_get(sid))` (`:123–137`).  
- `_apply_protocol_choice_guard` → `get_pending_clarify(sid)` option list (`:194–203`).  
- `_pending_clarify_prompt_block` → planner user prompt (`:242–274`, `get_pending_clarify`).

---

## 2. How TurnFrame is built from planner output

### 2.1 Native path (authoritative for C2)

**`core/turn_frame_from_raw.py` → `build_turn_frame_from_raw(raw, …)`** (`:462–509`)

- Pure function; does not mutate `raw`.
- Per-field `FieldMeta` with `status` / `error` / `provenance`.
- **Intent:** `raw["route"]` → `intent` (`_intent_from_raw`, `:270–278`).  
- **Topic:** `topic` + `topic_confidence` vs `allowed_topics` (`_topic_from_raw`, `:293–334`).  
- **Aspects:** list validation; empty → invalid metadata, frame may have `aspects=[]` (`_aspects_from_raw`, `:337–365`).  
- **service_id / followup_of:** catalog allowlist (`_catalog_id_from_raw`, `:368–446`).  
- **needs_clarification:** `needs_clarify` bool (`:449–459`).  
- **patient_scope:** native `raw["patient_scope"]` if present, else scalar bridge from `patient_situation` (`_patient_scope_from_raw`, `:261–268`; bridge map `:58–68`).  
- **Not migrated in shadow:** `emotion`, `specificity` → `a7.not_migrated` (`:481–502`).

**Invocation:** `plan_turn_attempt` passes full `obj` (including `patient_scope`) to this builder **before** legacy projection (`turn_planner_llm.py:615–619`).

### 2.2 Legacy adapter path (delete in C2)

**`core/turn_frame_adapter.py` → `build_turn_frame_from_legacy(turn_plan, decision_frame?, primary_aspect?)`** (`:70–194`)

- Maps **valid** `TurnPlan` + optional `DecisionFrame` → `TurnFrame`.  
- **Empty `patient_scope`** — always defaulted (`PatientScopeFrame()`, `:164–180`).  
- **specificity** from `decision_frame.query_mode` when present (`:50–67`).  
- **No product call site on hot path** — only `core/turn_frame_shadow.record_turn_frame_shadow` (`:98–134`) and unit tests.

### 2.3 Shadow recording (ctx bridge)

**`core/turn_frame_shadow.py`**

| Function | When | Effect |
|----------|------|--------|
| `record_planner_attempt_shadow(attempt)` | `run_resolver_turn` always (`resolver_turn.py:61`) | Writes `attempt.shadow_frame` snapshot to `request.ctx["turn_frame_shadow"]`; status from `attempt.shadow_status` |
| `record_turn_frame_shadow(turn_plan, decision_frame)` | **Not called** on product path | Would use adapter — historical/test API |
| `mark_turn_frame_shadow_not_available()` | Legacy path when planner had no plan | Status `not_available`, reason `turn_plan_missing` |

**Target load:** `core/target_runtime_turn_frame_bridge.py` → `load_runtime_turn_frame()` reads ctx snapshot; accepts `ok` or `partial`; rejects `not_available` / `degraded` (`:31–45`).

### 2.4 Post-load hydration (target only)

**`core/target_runtime_turn_frame_hydration.py` → `hydrate_target_runtime_turn_frame_from_session`**

- Runs after `load_runtime_turn_frame` in `core/target_runtime_turn.py:110–115`.  
- If `service_id` missing and vague attribute follow-up → copy `session_state.last_service_id` from `target_runtime_state` (`:47–72`).  
- Does **not** read `last_subject` directly.

---

## 3. Target components reading TurnFrame

| Component | Reads TurnFrame how | Fields used |
|-----------|---------------------|-------------|
| `core/target_runtime_turn_frame_bridge.py` | `load_runtime_turn_frame()` from ctx | Full frame |
| `core/target_runtime_turn_frame_hydration.py` | Hydrate session continuity | `service_id`, `follow_up`, `followup_of`, `primary_aspect`, `aspects`, `topic` |
| `core/target_runtime_turn.py` | Orchestrates runtime turn | Passes frame to boundary, strategy, pipeline, session write |
| `core/target_turn_frame_dispatch.py` | `dispatch_target_turn_frame_response` | `intent`, `topic`, `aspects`, `primary_aspect`, `service_id`, `needs_clarification` + `field_meta` validity |
| `core/target_turn_frame_bound_response.py` | S41 materialize/terminal | Dispatch + `turn_frame.topic` |
| `core/target_boundary_enforced_fullcontext_response.py` | S46 entry | Full frame into bound response |
| `core/target_runtime_widget.py` | Widget materialization | `service_id`, `topic` |
| `core/target_runtime_session.py` | `write_target_runtime_session_after_materialized` | `service_id`, `topic`, `primary_aspect` → `target_runtime_state`; compat `set_last_subject` |

**Does not read TurnFrame (legacy DecisionFrame / TurnPlan path):**

- `orchestration/resolver_turn.py` — uses `legacy_plan` → `turn_plan_to_decision_frame` (`:63–64`).  
- `core/dialog_focus.py` — `turn_plan_from_ctx()` when planner published (`:353–364`).  
- `orchestration/composer_flow.py`, `orchestration/ask_turn.py` — `turn_plan_from_ctx()` (legacy composer path; not target `/ask`).

**Ctx keys today (telemetry + bridge):**

- `turn_frame_shadow`, `turn_frame_shadow_status`, `turn_frame_shadow_reason`  
- `turn_plan`, `turn_planner_used`, `turn_plan_*` (via `publish_turn_plan`, `turn_planner_llm.py:487–503`)

---

## 4. When resolver fallback runs

**Entry:** `orchestration/resolver_turn.py` → `run_resolver_turn()` (`:35–171`).

```text
decision = None

IF TURN_PLANNER_ON AND NOT RESOLVER_OFF:
    attempt = plan_turn_attempt(...)
    record_planner_attempt_shadow(attempt)
    IF attempt.legacy_plan IS NOT NULL:
        decision = turn_plan_to_decision_frame(plan)
        publish_turn_plan(plan)
        → planner-owned path (resolver NOT used)
    ELSE:
        log turn_planner_fail_open_to_resolver

IF decision IS NULL AND RESOLVER_OFF=1:
    intent = classify_intent(...)           # legacy v4 bypass
    maybe_start_shadow_resolver(...)        # background telemetry

ELIF decision IS NULL:
    decision, safety_net, legacy_intent = resolve_with_fallback(...)  # resolver.py
```

**`resolve_with_fallback`** (`resolver.py:181–238`):

1. `resolve_decision_frame` — Resolver LLM (`RESOLVER_MODEL`, `:199`).  
2. Safety-net vs `THRESHOLDS.resolver.min_confidence`:  
   - Low intent → `classify_intent` remaps `route_intent` (`:204–220`).  
   - Low topic → `service_topic = "unknown"` (`:224–228`).  
   - Low query_mode → `query_mode = "specific"` (`:232–236`).

**Target path note:** `app._orchestrate_ask_turn` always calls `run_resolver_turn` then `orchestrate_target_fullcontext_turn` (`app.py:309–322`). Resolver output populates `request.ctx` decision frame and `effective_intent`, but **target answer does not consume `DecisionFrame`** — only TurnFrame shadow. Resolver fallback is still a **second LLM** on planner strict failure and affects shared telemetry/focus helpers.

**Env gates:**

| Flag | Effect |
|------|--------|
| `TURN_PLANNER_ON` (default `1`, `config.py`) | Off → skip planner block; `decision` stays `None` → resolver |
| `RESOLVER_OFF=1` (`is_resolver_bypassed_env`, `resolver_turn.py:30–32`) | Skip resolver; `classify_intent` only when planner failed |
| `V5_RESOLVER_SHADOW_ON` (`resolver.py:19`) | Background shadow resolver when `RESOLVER_OFF` |

---

## 5. Invalid / missing planner output behavior

### 5.1 By layer

| Layer | Invalid/missing behavior | Fail mode |
|-------|--------------------------|-----------|
| **Shadow TurnFrame** | Per-field `invalid` / `missing`; frame still built unless builder throws | `shadow_status`: `partial` if legacy missing or `turn_frame_has_invalid_or_missing`; `degraded` if builder throws; `not_available` if no LLM/catalog |
| **legacy_plan** | Any `_validate_plan` / guard failure → `None` | Fail-open → resolver (`turn_planner_fail_open_to_resolver`) |
| **Target runtime** | `load_runtime_turn_frame` on `not_available`/`degraded`/missing snapshot | Fail-closed error widget `target_runtime_turn_frame_unavailable` (`target_runtime_turn.py:97–107`) |
| **Partial shadow + no legacy** | Shadow may be `partial` with usable fields; legacy `None` triggers resolver **and** target may still load frame if shadow recorded | **Inconsistent today:** second LLM runs while target could use partial frame |

### 5.2 `turn_frame_has_invalid_or_missing` (`contracts/planner_attempt.py:15–31`)

- Any top-level `FieldMeta.status` in `{invalid, missing}` → true.  
- Nested `patient_scope` subfields counted.  
- Used to set `shadow_status=partial` vs `ok` (`turn_planner_llm.py:676–679`).

### 5.3 Strict legacy triggers (examples)

- `aspects=[]` → Pydantic `min_length=1` on `TurnPlan` → `legacy_plan=None`, shadow may be `partial`.  
- Unknown `service_id` / `followup_of` → `ValueError` in `_validate_plan` (`:393–396`).  
- Invalid brand_filter → `ValueError` (`:413–416`).

---

## 6. Native TurnFrame as primary (without second LLM)

### 6.1 Target end state

One call, one authority:

```text
plan_turn_attempt(q, sid, client_id)
  → frame = build_turn_frame_from_raw(obj) + deterministic post-processors
  → publish_runtime_turn_frame(frame, status)   # renamed from shadow
  → NO legacy_plan, NO turn_plan_to_decision_frame, NO resolve_with_fallback
```

### 6.2 Required moves (ordered)

1. **Product branch in `run_resolver_turn`:**  
   - If `attempt.shadow_frame` and status ∈ `{ok, partial}` → treat as planner success for target.  
   - If `not_available` / `degraded` / missing frame → fail-closed target error (same as today’s `load_runtime_turn_frame` failure); **do not** call resolver.

2. **Relocate deterministic guards off `TurnPlan`:**  
   - `_apply_protocol_choice_guard` and `_apply_focus_followup_enrichment` today mutate only `legacy_plan`.  
   - C2: implement `apply_turn_frame_planner_guards(frame, q, sid, client_id)` operating on `TurnFrame` (or pre-frame raw + post-build patch) with same rules:  
     - implant protocol downgrade on `service_id`  
     - session focus enrichment for vague follow-ups  
     - `pending_clarify` option proof for protocol guard  
   - Session input: **`target_runtime_state.last_service_id`** instead of `last_subject` (`_session_focus_service_id`).

3. **Retire `turn_plan_to_decision_frame` on hot path:**  
   - Target dispatch already uses TurnFrame field_meta gates (`target_turn_frame_dispatch.py`).  
   - Shared helpers that still read `turn_plan_from_ctx()` (`dialog_focus`, `composer_flow`) must switch to runtime TurnFrame ctx or target session — or be deleted if dead post-S69.

4. **Rename shadow → runtime (ctx contract):**  
   - `turn_frame_shadow` → `runtime_turn_frame` (or similar); keep telemetry aliases one release if needed.  
   - `record_planner_attempt_shadow` → `publish_runtime_turn_frame`.  
   - Update `metadata_first_observability` allowlist keys accordingly.

5. **Partial frame policy (owner decision inside C2):**  
   - Define minimum viable fields for target materialize vs terminal clarify/defer (reuse `dispatch_target_turn_frame_response` invalid-field rejects).  
   - `partial` with valid `intent`+`topic`+`aspects` should materialize; missing `service_id` may terminal-clarify — **no resolver**.

6. **Keep single LLM:** `plan_turn_attempt` remains the only planner call; no `resolve_decision_frame` on `/ask`.

### 6.3 Explicit non-goals for C2

- No second classifier for routing.  
- No loosening of base/client MD wording or verifier.  
- No A9 `patient_scope` product authority (see §10).

---

## 7. How to remove legacy seams

### 7.1 `legacy_plan` / `TurnPlan` product path

| Item | Action |
|------|--------|
| `PlannerAttempt.legacy_plan` | Remove field; rename attempt → `PlannerOutcome` with `frame` + `status` |
| `plan_turn()` wrapper | Deprecate or make alias to frame export |
| `_validate_plan`, `_project_legacy_turn_plan_raw` | Delete after guards ported to TurnFrame |
| `publish_turn_plan`, `turn_plan_from_ctx`, ctx `turn_plan_*` | Delete; replace with `runtime_turn_frame` snapshot + typed accessors |
| `turn_plan_to_decision_frame` | Delete from hot path; keep only in historical tests until removed |
| `contracts/turn_plan.py` | Keep for migration tests, then delete in follow-up if unused |

### 7.2 `turn_frame_adapter.py`

| Item | Action |
|------|--------|
| `build_turn_frame_from_legacy` | Delete module |
| `record_turn_frame_shadow(turn_plan, decision_frame)` | Delete |
| Tests importing adapter | Rewrite to `build_turn_frame_from_raw` fixtures only |

### 7.3 Shadow naming

| Old | New |
|-----|-----|
| `turn_frame_shadow` ctx key | `runtime_turn_frame` |
| `turn_frame_shadow_status` | `runtime_turn_frame_status` |
| `SHADOW_STATUS_*` constants | `RUNTIME_FRAME_STATUS_*` |
| `core/turn_frame_shadow.py` | Rename to `core/runtime_turn_frame.py` (or merge into bridge) |
| Log event `turn_frame_shadow` | `runtime_turn_frame` |

### 7.4 Resolver fallback

| Item | Action |
|------|--------|
| `resolve_with_fallback` call in `resolver_turn.py` | Remove for `/ask` path |
| `resolver.py` `resolve_decision_frame` | Keep for eval/harness only, or move to `evals/` |
| `classify_intent` safety-net | Remove from turn routing when planner frame authoritative |
| `maybe_start_shadow_resolver` | Optional keep for `RESOLVER_OFF` dev telemetry only |
| `request.ctx["resolver_used"]`, `legacy_intent` | Trim or map to planner-only telemetry |

### 7.5 Legacy session focus

| Legacy | Replacement |
|--------|-------------|
| `session.last_subject` + `subject_turn_age` reads in planner guards | `target_runtime_state.last_service_id` + new `last_service_turn_age` (or reuse turn counter) |
| `core/dialog_focus._focus_from_last_subject` in planner | `read_target_runtime_session(sid).last_service_id` |
| `write_target_runtime_session_after_materialized` → `set_last_subject` shim | Remove shim once no shared reader needs `last_subject` |
| `core/dialog_focus.build_dialog_focus_from_turn_plan` | Replace with `build_dialog_focus_from_turn_frame` or delete if telemetry-only |
| `core/follow_up_rewrite.focus_from_legacy_session` | Delete or gate to tests |
| `query_selector` `st.get("last_subject")` (`:258`) | Migrate to `target_runtime_state` for any remaining active selector |

**Keep until explicit delete milestone:** `pending_clarify` API — still read by planner prompt/guards; C2 should add `target_runtime_state.pending_clarify` mirror before removing session field.

---

## 8. Session fields → `target_runtime_state`

### 8.1 Current `target_runtime_state` shape

**Writer:** `core/target_runtime_session.py` → `write_target_runtime_session_after_materialized` (`:95–140`)

```python
{
  "last_service_id": turn_frame.service_id,
  "last_topic": turn_frame.topic,
  "last_primary_aspect": turn_frame.primary_aspect,
  "shown_fact_ids": [...],
  "shown_amplifier_refs": [...],
  "shown_consultation_value_refs": [...],
}
# Plus separate key target_runtime_followups
```

**Reader:** `read_target_runtime_session` → `TargetRuntimeSessionState` (`:53–92`).  
**Hydration consumer:** `hydrate_target_runtime_turn_frame_from_session` (`last_service_id` only).  
**Pre-resolver ref nav:** `orchestration/pre_resolver_turn.py:232–237` reads `followups`.

### 8.2 Migration map

| Legacy session field | Used by (active) | C2 target field | Notes |
|---------------------|------------------|-----------------|-------|
| `last_subject` | `turn_planner_llm` guards, `dialog_focus`, `follow_up_rewrite`, `query_selector` | `target_runtime_state.last_service_id` + `last_topic` + `last_service_label?` | Writer already mirrors via `set_last_subject` shim |
| `subject_turn_age` | `dialog_focus._focus_from_last_subject`, `mem_add_user` increment | `target_runtime_state.service_turn_age` | New field; increment on user turn in target session bridge |
| `pending_clarify` | `turn_planner_llm` prompt + protocol guard | `target_runtime_state.pending_clarify` | Same dict shape; target clarify terminal should write here |
| `last_aspect` | `clear_focus_context`, legacy tests | `last_primary_aspect` (already written) | Drop `last_aspect` reads |
| `last_patient_situation` | `dialog_focus`, patient playbook legacy | **Not product authority** — optional shadow telemetry only | Do not route target responses from this |
| `last_catalog_service_id` | `query_selector`, tests | Prefer `last_service_id` | Audit remaining callers |
| `target_runtime_followups` | `pre_resolver_turn` ref nav | Keep separate key | Already target-owned |

### 8.3 C2 session rules

- **Read path:** target pipeline and planner guards read **only** `read_target_runtime_session`.  
- **Write path:** only after successful materialized target response (unchanged).  
- **Compat:** one-release dual-write to `last_subject` optional; dual-read forbidden after cutover.  
- **Reset:** `mem_reset` / `clear_focus_context` must clear `target_runtime_state` + followups.

---

## 9. Loader fallbacks removable (no old clients)

Post-S70 product is **demo-only** on target path; no multi-legacy client packs in production.

| Loader / path | “Fallback” today | C2 action |
|---------------|------------------|-----------|
| `core/pricebook_loader.py` | Docstring mentions legacy; **code is v2-only** (`pricebook/manifest.json`, `facts.json`, `services/*.json`) | Remove stale docstring; no code fallback to delete |
| `contracts/pricebook.py` | Documents `price_offers.json` / `prices.json` fallback via `price_answer_assembler` | Update contract doc; remove dead fallback references |
| `core/price_offers.py` | `price_offers.json` path (`:60`); “else legacy append-only” (`:460`) | Audit target path — target uses `pricebook` via `response_schema_loader`; prune legacy JSON path if no caller |
| `query_selector.py` | Reads `prices.json` (`:246`, `:573`, `:639`) | Remove `prices.json` branches when catalog+pricebook cover demo |
| `core/service_selector_llm.py` | `service_catalog.json` only | Keep — canonical catalog for planner |
| `core/patient_playbook.py` | `_service_available`: catalog then `load_pricebook_service` (`:62–72`) | Keep pricebook check; drop catalog-only fallback if catalog is always complete |
| `core/patient_playbook._read_service_catalog` | Duplicate of service_selector pattern | OK shared pattern |
| `startup_check.py` | Accepts `prices.json` OR pricebook (`:72`) | Require pricebook only |

**Planner catalog source:** `build_compact_service_catalog` → `service_catalog.json` (`service_selector_llm.py:49–68`), **not** pricebook loader. C2 should document that planner allowlist is catalog-driven; pricebook validates `service_id` in guards/loaders.

**Not in C2 without owner exception:** changing demo client pack files.

---

## 10. A9 shadow-only — no `patient_scope` authority

Per `docs/PATIENT_SCOPE_NATIVE_EXTRACTION_DESIGN_A9.md` and guardrails:

- `patient_scope` is extracted in **`build_turn_frame_from_raw`** only (`turn_frame_from_raw.py:261–268`).  
- **`_project_legacy_turn_plan_raw` strips `patient_scope`** before `TurnPlan` validation (`turn_planner_llm.py:105–107`) — product `legacy_plan` never sees it.  
- **No target module** reads `turn_frame.patient_scope` for dispatch/composer/verifier.  
- A9 eval harness (`evals/v5/run_patient_scope_shadow_eval_v2.py`) is measurement only.

**C2 law:**

1. `patient_scope` remains **telemetry / offline eval** only.  
2. No routing, evidence, pricing, or UI may branch on `patient_scope` without separate owner authority gate.  
3. Native TurnFrame primary **does not** change this — flipping authority to TurnFrame must not implicitly promote `patient_scope`.  
4. Scalar `patient_situation` bridge in `turn_frame_from_raw` stays for shadow completeness until a later authority task.

---

## 11. Offline tests / evals needed

### 11.1 Protected (must pass unchanged through C2 unless test is explicitly in allowlist)

- `tests/test_turn_planner_llm.py`  
- `tests/test_turn_frame_shadow.py` (rewrite to runtime naming)  
- `tests/test_turn_frame_from_raw.py`  
- `tests/test_s61_target_fullcontext_runtime.py`  
- `tests/test_target_fullcontext_content_response.py`  
- `tests/test_s67_legacy_isolation_offline.py`  
- `tests/test_s62_correction_offline.py`, `tests/test_s63_correction_offline.py`  
- Frozen pin guards (S62/S63/S66) — byte-identical

### 11.2 New / extended C2 tests (recommended allowlist)

| Test file | Covers |
|-----------|--------|
| `tests/test_c2_native_turnframe_offline.py` (new) | Planner failure does **not** invoke `resolve_with_fallback`; no second LLM mock |
| `tests/test_c2_runtime_turn_frame_ctx_offline.py` (new) | ctx publish/load; `partial` frame loads; `degraded` fail-closed |
| `tests/test_c2_session_migration_offline.py` (new) | Guards read `target_runtime_state`; `last_subject` not consulted |
| `tests/test_c2_import_firewall_offline.py` (new) | Product path does not import `turn_frame_adapter`, `turn_plan_to_decision_frame` |
| Extend `tests/test_turn_plan_protocol_guard.py` | Frame-level guard parity |
| Extend `tests/test_s69_checkpoint_a_offline.py` | No resolver on planner partial |

### 11.3 Evals (offline)

- A9 patient_scope shadow matrix — rerun for regression; **no authority change**.  
- A6/A7 topic shadow attempt contract — update event names if shadow renamed.  
- **No new live eval requirement** (§12).

### 11.4 Commands (offline, from C1 TASK pattern)

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$basetemp = Join-Path $env:TEMP ("demo-bot-c2-" + [guid]::NewGuid().ToString("n"))

python -m pytest -p no:cacheprovider --basetemp $basetemp `
  tests/test_turn_planner_llm.py `
  tests/test_turn_frame_from_raw.py `
  tests/test_c2_native_turnframe_offline.py `
  tests/test_s61_target_fullcontext_runtime.py `
  tests/test_s67_legacy_isolation_offline.py `
  -q
```

---

## 12. Live needed? Default **NO**

| Activity | Default for C2 |
|----------|----------------|
| Offline pytest | **Required** |
| `pytest --collect-only` | **Required** |
| Frozen artifact pin checks | **Required** |
| Live `/ask` LLM eval | **No** — unless owner explicit exception |
| A9 live shadow re-audit | **No** — offline replay sufficient for rename/authority flip |
| Resolver shadow (`V5_RESOLVER_SHADOW_ON`) | **Off** for C2 validation |

Rationale: C2 is wiring/authority cleanup; behavior claims must be provable from deterministic tests + existing target offline corpus. Live runs risk false reds from provider drift and violate C1/C2 governance default.

---

## 13. Exact C2 allowlist and stop conditions

### 13.1 C2 implementation allowlist (proposed)

| File | Change |
|------|--------|
| `TASK.md` | C2 governance + completion record |
| `core/turn_planner_llm.py` | Drop legacy branch; frame guards; attempt envelope |
| `contracts/planner_attempt.py` | Remove `legacy_plan`; rename status semantics |
| `core/turn_frame_from_raw.py` | Post-build guard hooks if needed |
| `core/turn_frame_shadow.py` | Rename/rehome → runtime frame publisher |
| `core/target_runtime_turn_frame_bridge.py` | Read new ctx keys |
| `orchestration/resolver_turn.py` | Remove resolver fallback; planner→frame only |
| `core/target_runtime_turn_frame_hydration.py` | Session guard inputs from `target_runtime_state` only |
| `core/target_runtime_session.py` | Extended state; remove `set_last_subject` shim when safe |
| `core/dialog_focus.py` | TurnFrame-based focus; remove `turn_plan_from_ctx` |
| `session.py` | Deprecate/clear legacy focus fields on reset |
| `core/metadata_first_observability.py` | Telemetry key renames |
| `orchestration/pre_resolver_turn.py` | Reset clears target state |
| `query_selector.py` | `last_subject` → `target_runtime_state` (if still active) |
| `config.py` | Document `TURN_PLANNER_ON`; resolver flags dev-only |
| `tests/test_turn_frame_shadow.py` | Rename + update contracts |
| `tests/test_turn_planner_llm.py` | Frame-first assertions |
| `tests/test_c2_*_offline.py` | New firewall / no-resolver tests |
| `docs/C2_NATIVE_TURNFRAME_CLEANUP_PLAN.md` | This plan |
| `docs/STRANGLER_ROADMAP.md` | C2 checkpoint |
| `docs/FLAGS_AND_STATUS.md` | Resolver fallback removed from product path |
| `docs/S70_FULLCONTEXT_MIGRATION_CLOSEOUT.md` | C2 addendum |

### 13.2 Explicitly **NOT** in C2 allowlist (STOP if needed)

- `core/turn_frame_adapter.py` — **delete only** (no extend)  
- `resolver.py` semantic changes beyond gating product call — needs owner decision  
- `contracts/turn_plan.py` deletion — optional follow-up  
- Client packs / MD / pricebook data  
- Composer, Verifier, medical boundary logic  
- A9 eval matrix / frozen live artifacts  
- Protected acceptance spec/golden/target/current  
- `evals/v5/*_live_*` changes  
- Per-MD routing, RAG, retrieval reintroduction  

### 13.3 STOP conditions (owner / Architect required)

Stop and escalate if C2 implementation requires:

1. **Second LLM** on `/ask` for routing (resolver, classify_intent safety-net, service_select duplicate).  
2. **Partial TurnFrame → resolver** hybrid (fail-open contradicts native primary).  
3. **`patient_scope` product authority** (pricing, medzone, clarify, evidence).  
4. **Files outside §13.1** without governance correction + PRE-CODE ✅.  
5. **Changing protected tests** expectations to greenwash.  
6. **`TurnPlan` strict relax** (e.g. `aspects` min_length) instead of frame authority.  
7. **Session dual-read** indefinitely (legacy + target without migration end).  
8. **Live eval / frozen artifact** edits to mask regressions.  
9. **Behavior change** in FullContext composer/verifier/boundary masked as “cleanup”.  
10. **Corpus overflow** prompt to add RAG/retriever (FINAL_FULLCONTEXT_ONLY violation).

### 13.4 Suggested C2 phases (for TASK splitting)

| Phase | Scope | Exit criterion |
|-------|-------|----------------|
| **C2a** | Runtime frame rename + bridge; remove adapter; tests | Target offline green; no adapter imports on product path |
| **C2b** | `run_resolver_turn` no `resolve_with_fallback`; frame guards | Test: planner fail does not call resolver mock |
| **C2c** | Session migration; drop `last_subject` reads in planner/focus | Hydration + clarify use `target_runtime_state` only |
| **C2d** | Loader/doc fallback prune (`prices.json`, stale docstrings) | `startup_check` pricebook-only |

---

## Appendix A — Call-site index (audit anchors)

| Symbol | Location |
|--------|----------|
| `plan_turn_attempt` | `core/turn_planner_llm.py:558` |
| `legacy_plan =` | `core/turn_planner_llm.py:634–664` |
| `build_turn_frame_from_raw` | `core/turn_frame_from_raw.py:462` |
| `build_turn_frame_from_legacy` | `core/turn_frame_adapter.py:70` |
| `record_planner_attempt_shadow` | `core/turn_frame_shadow.py:66` |
| `run_resolver_turn` | `orchestration/resolver_turn.py:35` |
| `resolve_with_fallback` | `resolver.py:181` |
| `load_runtime_turn_frame` | `core/target_runtime_turn_frame_bridge.py:31` |
| `hydrate_target_runtime_turn_frame_from_session` | `core/target_runtime_turn_frame_hydration.py:38` |
| `run_target_fullcontext_runtime_turn` | `core/target_runtime_turn.py:71` |
| `read_target_runtime_session` | `core/target_runtime_session.py:53` |
| `get_pending_clarify` | `session.py:283` |
| `get_last_subject` / `set_last_subject` | `session.py:492` / `:500` |
| `_focus_from_last_subject` | `core/dialog_focus.py:45` |
| `build_compact_service_catalog` | `core/service_selector_llm.py:49` |
| `load_pricebook_service` | `core/pricebook_loader.py:338` |

---

## Appendix B — Related docs

- `docs/S70_FULLCONTEXT_MIGRATION_CLOSEOUT.md` — current product diagram  
- `docs/evidence/a_series/FIELD_LEVEL_PLANNER_OUTCOME_A7.md` — dual-branch law  
- `docs/PATIENT_SCOPE_NATIVE_EXTRACTION_DESIGN_A9.md` — shadow-only patient_scope  
- `TASK.md` (C1) — explicit NOT in C1 allowlist = C2 scope

**STOP after plan — C2 code requires separate owner governance commit.**
