# FINAL_SCOPE_POST_RETRY1_PRODUCT_CORRECTION — seam audit (read-only)

**Date:** 2026-07-26  
**Baseline:** `d76870a` (`codex/stage-a`)  
**Authority:** RETRY1 live = official **FAIL** · live/rerun **blocked** · `A9_PATIENT_SCOPE_AUTHORITY` **must remain**

**Scope:** governance / read-only checkpoint · **NO LIVE / NO LLM / NO PRODUCT CODE**

---

## Verdict

Two product defects in `dispatch_target_turn_frame_response` precedence cause RETRY1 T2/T5 failures. Both are fixable by reusing existing AC1→AC2→AC3 scope-price materialize path — **no new route, selector, or legacy fallback**.

| Failure | Symptom | Root seam |
|---------|---------|-----------|
| **T2** | UI scope click `target:ui_scope/implantation/full_arch` → `terminal_medical_handoff_nonmaterializable` | Boundary + dispatch terminal precedence over governed `UiScopeAction` |
| **T5** | «Сколько стоит протезирование?» → `terminal_clarify` | `needs_clarification=true` short-circuits before `broad_family_price` |

---

## Workspace hygiene (pre-audit)

| Check | Result |
|-------|--------|
| Workspace clean | **NO** — intentional; governance does not require clean tree |
| Untracked | `evals/v5/artifacts/_retry1_live_run_stdout.txt` — **retained** until this audit capture |

### Untracked stdout forensic vs committed artifact

| File | Size (bytes) | SHA-256 | Encoding / role |
|------|-------------|---------|-----------------|
| `evals/v5/artifacts/final_scope_widget_e2e_retry1_live_stdout.log` (committed `d76870a`) | 328 159 | `5fa434921275aa649c7a63b018fd4236aa1e155218574f87062727a4b420bb31` | UTF-8 shell capture; PowerShell stderr prefix on logging errors |
| `evals/v5/artifacts/_retry1_live_run_stdout.txt` (untracked) | 634 914 | `d3e3f159e37e94e0f04b6e1e30a6a7675a2c093c9121f72d78248813c9c3f946` | UTF-16 LE BOM (`FF FE`); PowerShell `Tee-Object` / redirect duplicate |

**Byte-identical:** **NO** (size ratio ≈2×; different on-disk encoding).  
**Semantic content:** same live run session (same request_ids, routes, abort at turn 6 prep). Untracked file is **not** an alternate attempt; it is an uncommitted duplicate capture.  
**Governance action:** do **not** delete until audit committed; do **not** add to repo (not part of immutable retry1 artifact set).

### Harness evidence gap (₽ / mojibake)

| Layer | Issue | Fix surface (implementation) |
|-------|-------|------------------------------|
| `logging_setup.py` `StreamHandler(sys.stdout)` | No UTF-8 encoding → `UnicodeEncodeError` on `₽` in `turn_complete` | UTF-8 stream handler or `sys.stdout.reconfigure(encoding="utf-8")` at live runner start |
| Artifact JSON (`result.json`, `raw.json`) | T2/T4/T5 `answer_text` stored with cp1251 mojibake when sourced from log events | Capture answer from HTTP payload / `turn_complete` after UTF-8 fix; assert UTF-8 round-trip in harness tests |
| Current offline fake test | `test_fake_provider_executes_all_eight_http_turns_without_network` mocks `orchestrate_target_fullcontext_turn` — does **not** exercise real dispatch | Implementation: fake-provider replay through **real** target runtime for all 8 matrix turns |

---

## Shared runtime chain (RETRY1 T2 & T5)

```
POST /ask[/stream]
  → run_pre_resolver_turn()                    [AC1: UiScopeAction / ref ingress]
  → orchestrate_target_fullcontext_turn()
  → run_target_fullcontext_runtime_turn()      [core/target_runtime_turn.py]
       ├ load_runtime_turn_frame()             [planner TurnFrame]
       ├ resolve_effective_scope()             [AC1 merge — worked for T2]
       ├ execute_target_medical_boundary_classification()
       └ run_target_offline_boundary_enforced_fullcontext_response()
            └ dispatch_target_turn_frame_response()   ← failure choke point
                 └ (if materialize) AC2 → AC3 scope-price package
```

Live evidence: `evals/v5/artifacts/final_scope_widget_e2e_retry1_result.json`, `final_scope_widget_e2e_retry1_live_stdout.log`.

---

## T2 — typed UI scope click (`fsw_turn_02_scope_full_arch_click`)

### Observed (RETRY1 live)

| Field | Value |
|-------|-------|
| `nav_ref` | `target:ui_scope/implantation/full_arch` |
| `current_ui_scope_action` | `{extent: full_arch, topic: implantation, provenance: ui_scope_ref}` |
| `effective_scope` | `extent=full_arch`, `source=ui_action` ✅ |
| Planner | `needs_clarification=true`, `route=price_lookup` |
| Boundary | called; **composer not called** |
| Route | `target_fullcontext_terminal_medical_handoff_nonmaterializable` ❌ |
| Expected | materialized scoped full_arch price (AC2→AC3) |

### Seam trace

| Step | File : function | Finding |
|------|-----------------|---------|
| AC1 ingress | `orchestration/pre_resolver_turn.py` : `run_pre_resolver_turn` | `resolve_ui_scope_ref_click` OK; `request.ctx["current_ui_scope_action"]` set |
| Label → planner | `core/target_ui_scope_action.py` : `resolve_ui_scope_ref_click` | `planner_message = shown.label` → **«Вся челюсть»** sent as `user_message` |
| EffectiveScope | `core/target_effective_scope.py` : `resolve_effective_scope` | `full_arch` from `ui_action` ✅ |
| Planner | `core/turn_planner_llm.py` → `core/turn_frame_from_raw.py` | `needs_clarify=true` on short label |
| Boundary | `core/target_medical_boundary.py` : `execute_target_medical_boundary_classification` | Classifies button label; envelope `boundary_decision=medical_handoff` |
| **Dispatch** | `core/target_turn_frame_dispatch.py` : `dispatch_target_turn_frame_response` L315–316 | `medical_handoff` wins **before** scope-price branch L339–350 |
| Terminal | `core/target_runtime_widget.py` : `materialize_s41_terminal_payload` | nonmaterializable terminal |

### Target semantics (owner)

**Governed `UiScopeAction` is a typed price-drill-down continuation command**, not free-text medical input. AC1 already resolved extent/topic; planner/boundary must **not** reinterpret the button label as ambiguous medical text.

### Minimal fix surface (implementation — no new route)

1. **Primary:** `dispatch_target_turn_frame_response` — when `_scope_price_topic()` is set and `effective_scope.source == "ui_action"` with known extent → **force** `_materialize_scope_price_policy_request(response_mode="answer", …)` before terminal medical_handoff/clarify.
2. **Defense (optional, same TASK):** `pre_resolver_turn` — use neutral governed continuation token instead of raw scope label for boundary input when `UiScopeAction` is on ctx.
3. **Forbidden:** new `service_route`, per-service hardcode, regex/phrase lists, prompt tuning A9, legacy fallback.

---

## T5 — broad prosthetics price (`fsw_turn_05_prosthetics_broad`)

### Observed (RETRY1 live)

| Field | Value |
|-------|-------|
| Input | «Сколько стоит протезирование?» |
| Planner | `topic=prosthetics`, `aspects=[price]`, `extent=unknown`, `needs_clarification=true` |
| Boundary | `none` (not uncertain / not medical_handoff) |
| Route | `target_fullcontext_terminal_clarify` ❌ |
| Expected | `broad_family_price` + **3 scope-nav buttons** (AC2→AC3) |

### Seam trace

| Step | File : function | Finding |
|------|-----------------|---------|
| Planner | `core/turn_planner_llm.py` | `needs_clarify=true` for prosthetics price (extent unknown) |
| **Dispatch** | `dispatch_target_turn_frame_response` L317–321 | `needs_clarification` → immediate `_terminal_spec(clarify)` |
| Never reached | L114–119 `_initial_scope_price_stage` | Would return `broad_family_price` when `extent==unknown` |
| Never reached | `core/target_scope_aware_price_package.py` | `materialize_scope_nav_followups` for 3 buttons |

### Offline vs live gap

`tests/test_ac3_scope_price_flow_offline.py` passes prosthetics broad with `needs_clarification=false` in fixtures. Live planner sets `needs_clarify=true` → exposes dispatch precedence bug.

### Target semantics (owner)

```
known topic + requested price + service_id=null + extent=unknown
  → AC2/AC3 broad_family_price + 3 scope-nav buttons
```

`needs_clarification` remains valid for **non-price** ambiguity and **service_id** ambiguity (existing `stage_clarify` / typed fail-closed). Extent ambiguity on family price is owned by **AC3 scope nav**, not terminal clarify.

### Minimal fix surface (implementation)

**Primary:** `dispatch_target_turn_frame_response` — when `_scope_price_topic()` is set, `service_id` not usable, `effective_scope.extent == "unknown"` → materialize `broad_family_price` **even if** `needs_clarification=true`.

---

## Dispatch precedence today (why AC2/AC3 loses)

`core/target_turn_frame_dispatch.py` : `dispatch_target_turn_frame_response`:

1. `boundary_decision == "medical_handoff"` → `response_mode=medical_handoff` (L315–316)
2. `needs_clarification` + valid meta → **return terminal clarify** (L317–321)
3. Scope-price materialize only when `response_mode=="answer"` AND `_scope_price_topic()` (L339–350)

`effective_scope` and `UiScopeAction` are passed in but **not** used to guard terminal shortcuts.

---

## Blast-radius test map (implementation)

| # | Scenario | Expected | Primary test file |
|---|----------|----------|-------------------|
| BR-1 | broad implantation price | `broad_family_price` + 3 scope buttons | `test_ac3_scope_price_flow_offline.py` |
| BR-2 | broad prosthetics price + `needs_clarify=true` | same as BR-1 | `test_target_turn_frame_dispatch.py` (new) |
| BR-3 | typed `full_arch` scope click + `needs_clarify=true` | scoped materialized; no terminal | `test_ui_scope_click_http_offline.py` |
| BR-4 | typed `one_tooth` / `few_teeth` clicks | scoped or stage_clarify per AC3 | `test_ac3_scope_price_flow_http_offline.py` |
| BR-5 | prosthetics `stage_clarify` + stage click | stage path materialized | `test_ac3_scope_price_flow_offline.py` |
| BR-6 | free-text full_arch / implant_placed | A9 scope → scoped price | `test_a9r3_product_authority_offline.py` |
| BR-7 | ordinary medical free-text | boundary `medical_handoff` still terminal/materialize per policy | `test_demo_target_turn_frame_bound_response.py` |
| BR-8 | ambiguous **non-price** | terminal clarify preserved | `test_c2c_dead_clarify_offline.py` (neighbor) |
| BR-9 | invalid / unshown refs | fail-closed clarify | `test_ui_scope_click_http_offline.py` |
| BR-10 | `/ask` vs `/ask/stream` | same EffectiveScope + route class | `test_ac3_scope_price_flow_http_offline.py` |
| BR-11 | terminal/error turn | no session patient_facts overwrite | `test_session_patient_facts_offline.py` |
| BR-12 | frozen 8-turn matrix fake-provider replay | 8/8 HTTP, all gates, UTF-8 ₽ | `test_final_scope_widget_e2e_retry1_live_harness.py` (extend) |

Protected matrix: `evals/v5/demo/final_scope_widget_e2e_turns.json` blob `f4eecf7532481a288d1db6a6ee107dd147117dae44afc991451836dd3589434f` — **immutable**.

---

## Frozen neighbors (must stay byte-identical)

| Artifact | Pin |
|----------|-----|
| RETRY1 live attempt + ledger + result + audit | `d76870a` SHAs in governance test |
| Preflight-abort attempt #1 + audit | retry1 contract pins |
| S62 / S63 / A9 / A9R* / W1b | existing contract pins |
| Widget E2E turn matrix | `f4eecf75…` |

---

## STOP

Governance audit complete. **No product code in this checkpoint.** Implementation requires separate owner GO + PRE-CODE on implementation TASK.
