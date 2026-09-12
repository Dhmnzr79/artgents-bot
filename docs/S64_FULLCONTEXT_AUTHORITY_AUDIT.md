# S64 — FullContext authority audit (read-only)

**Baseline:** `codex/stage-a` / `520e34a` (S63 live complete)  
**Audit commit:** read-only trace of product code at `520e34a`; no product changes in S64.  
**Authority status:** **NOT transferred** — `TARGET_FULLCONTEXT_DEV` default remains **OFF** (`config.py`).

## Executive summary

| Question | Answer |
|----------|--------|
| Ready for authority switch? | **Yes, with owner approval** — target path is wired, fail-closed, no hidden legacy fallback when flag ON. |
| Real blockers? | **None in code** — only governance: owner must approve default flip / kill-switch semantics. |
| Why legacy answers today? | **`TARGET_FULLCONTEXT_DEV=0` is the sole product gate** (`app.py:421`). |
| `/ask` vs `/ask/stream` parity? | **Identical orchestration** — only response packaging differs. |
| Hidden legacy when flag ON? | **No** — `orchestrate_routing_after_resolver` skipped; pre-resolver legacy ref/chunk paths skipped. |
| Planner/resolver still runs? | **Yes** — `run_resolver_turn` always runs before branch; supplies TurnFrame shadow, not legacy routing. |

S63 live evidence (`520e34a`): 3/3 `target_fullcontext_materialized`, legacy/RAG/chunk hits = 0, 14/15 provider calls, retry = 0.

---

## A. Factual chains (OFF vs ON)

Both endpoints share one orchestrator:

```
POST /ask          → _orchestrate_ask_turn(data) → _dispatch_orchestration_json(orch_r)
POST /ask/stream   → _orchestrate_ask_turn(data) → _dispatch_orchestration_sse(orch_r)
```

Source: `app.py` (`_orchestrate_ask_turn` ~399–442, `/ask` ~508, `/ask/stream` ~753–758).

### Common prefix (both OFF and ON)

```
HTTP JSON body
  → run_pre_resolver_turn(..., target_fullcontext_mode=TARGET_FULLCONTEXT_DEV)
       → [short-circuit?] AskOrchestrationResult → dispatch (END)
       → else AskTurnContext
  → run_resolver_turn(q, sid, client_id, st)   # ALWAYS, both modes
  → branch on TARGET_FULLCONTEXT_DEV
```

### OFF (`TARGET_FULLCONTEXT_DEV=0`) — legacy product path

```
run_pre_resolver_turn (target_fullcontext_mode=False)
  → [guards: see table B]
  → AskTurnContext
run_resolver_turn
  → TURN_PLANNER_ON (default ON): plan_turn_attempt → shadow TurnFrame
  → planner miss: resolve_with_fallback (legacy resolver LLM)
orchestrate_routing_after_resolver (ask_turn.py:155)
  → patient_situation, dialog_focus
  → contacts chunk / pending_clarify
  → route_source (source_routing) + build_answer_plan
  → playbooks, doctor route, brand money, try_composer_overlay
  → try_a3_catalog_facts, try_a3_price_route
  → price_lookup_intent_fallback → composer or chunk retrieval
dispatch:
  kind=chunk     → legacy chunk/SSE stream
  kind=composer  → legacy composer/SSE stream
  kind=service_reply → widget JSON or SSE ui event
```

### ON (`TARGET_FULLCONTEXT_DEV=1`) — target-only path

```
run_pre_resolver_turn (target_fullcontext_mode=True)
  → same shared guards (ingress, flows, anti-spam, rate, reset, …)
  → SKIPS: duplicate, continuation, promo, legacy ref→chunk/price/consult
  → ref-click: resolve_target_followup_navigation (target session followups)
       → unknown ref → target_fullcontext_followup_unknown (pre-target)
       → matched ref → restores q from follow-up label
  → AskTurnContext
run_resolver_turn   # still runs — TurnFrame shadow for target bridge
orchestrate_target_fullcontext_turn (target_fullcontext_turn.py:32)
  → run_target_fullcontext_runtime_turn (target_runtime_turn.py:71)
       → load_target_runtime_client_context (cached FullContext bootstrap)
       → load_runtime_turn_frame (planner shadow → TurnFrame)
       → hydrate_target_runtime_turn_frame_from_session
       → execute_target_medical_boundary_classification
       → run_target_offline_boundary_enforced_fullcontext_response
       → widget_payload_from_runtime_result
       → write_target_runtime_session_after_materialized (materialized only)
  → AskOrchestrationResult(kind=service_reply)  # NO legacy fallback
dispatch:
  kind=service_reply only (target widget payload)
  /ask: _service_reply
  /ask/stream: _sse_service_reply (typing + ui + done, no text_delta for direct replies)
```

### Scenario matrix (target ON)

| Scenario | Where handled | Route / outcome | Legacy fallback? |
|----------|---------------|-----------------|------------------|
| Normal message | target pipeline | `target_fullcontext_materialized` | No |
| Ref-click (valid) | pre_resolver nav + target pipeline | materialized with restored `q` | No |
| Ref-click (unknown, empty q) | pre_resolver | `target_fullcontext_followup_unknown` | No |
| Boundary `uncertain` | `widget_payload_from_runtime_result` | `target_fullcontext_boundary_uncertain` | No |
| S41 terminal (clarify/defer) | `materialize_s41_terminal_payload` | `target_fullcontext_terminal_{mode}` | No |
| Verifier block | `materialize_target_error_payload` | `target_fullcontext_verifier_blocked` | No |
| Missing/bad TurnFrame | `load_runtime_turn_frame` | `target_fullcontext_error` (`target_runtime_turn_frame_*`) | No |
| Provider/pipeline exception | `target_runtime_turn.py` except blocks | `target_fullcontext_error` | No |
| Ingress manual_contact / hard_stop | pre_resolver (before resolver) | `ingress_*` service routes | No (shared guard) |
| Lead / situation flows | pre_resolver `handle_flows` | lead/situation service routes | No (shared guard) |

### Authority selection point

Single gate in `app.py`:

```python
if TARGET_FULLCONTEXT_DEV:
    return orchestrate_target_fullcontext_turn(...)
return orchestrate_routing_after_resolver(...)
```

`orchestrate_target_fullcontext_turn` docstring: *"never falls back to legacy routing"* (`target_fullcontext_turn.py:42`).

---

## B. Pre-target short-circuits

| Mechanism | Location | Fires before target branch | Keep / move / remove | Why |
|-----------|----------|---------------------------|----------------------|-----|
| Unknown client | `pre_resolver_turn.py:74` | Yes | **Keep** | Shared HTTP guard |
| `/reset` | `pre_resolver_turn.py:86` | Yes | **Keep** | Session lifecycle |
| Rate limit | `pre_resolver_turn.py:110` | Yes | **Keep** | Abuse protection |
| Obvious noise | `pre_resolver_turn.py:129` | Yes | **Keep** | Deterministic ingress hard-stop |
| Ingress LLM gate | `pre_resolver_turn.py:152` (`classify_ingress`) | Yes | **Keep** | manual_contact, hard_stop, not_offered, urgent |
| Lead / booking / situation flows | `flow_handlers.py:761` via pre_resolver | Yes | **Keep** | Conversion + situation intake; not RAG |
| Anti-spam burst / soft redirect | `pre_resolver_turn.py:213–253` | Yes | **Keep** | Session safety |
| Duplicate question replay | `pre_resolver_turn.py:197` | Only when OFF | **Move (optional)** | Disabled in target mode; target has no equivalent replay — product decision for S65+ |
| Legacy ref → price/consult/chunk | `pre_resolver_turn.py:313–343` | Only when OFF | **Remove from product path** | Replaced by `resolve_target_followup_navigation` when ON |
| Empty question (no ref) | `pre_resolver_turn.py:345` | Yes | **Keep** | Shared validation |
| Continuation without context | `pre_resolver_turn.py:358` | Only when OFF | **Remove from target path** | Legacy session/chunk coupling |
| Promo overview | `pre_resolver_turn.py:372` | Only when OFF | **Remove from target path** | Legacy marketing shortcut; FullContext handles in pipeline |
| Continuation topic / short_contextual chunk | `pre_resolver_turn.py:387–417` | Only when OFF | **Remove from target path** | Legacy RAG/chunk runtime |
| Target unknown ref clarify | `pre_resolver_turn.py:283–308` | Yes (ON only) | **Keep** | Target-native ref safety |
| `run_resolver_turn` | `app.py:413` | Yes (before branch) | **Keep (refine)** | Supplies TurnFrame shadow; legacy resolver runs only on planner miss — not routing when ON |
| `orchestrate_routing_after_resolver` | `app.py:429` | N/A when ON | **Bypass (already)** | Entire legacy stack — delete only post-isolation milestone |

---

## C. Legacy components vs target ON

| Component | Called when target ON? | Needed after authority switch? | When can delete |
|-----------|------------------------|-------------------------------|-----------------|
| `orchestrate_routing_after_resolver` | **No** | **No** | After isolation period (S66+) |
| `source_routing.route_source` | **No** | **No** | Post-isolation |
| `get_chunk_by_ref` (product path) | **No** (pre_resolver skipped) | **No** | Post-isolation |
| `try_composer_overlay` / legacy composer | **No** | **No** | Post-isolation |
| `resolve_with_fallback` / v5 resolver | **Yes** (planner fail-open) | **Refine** — planner-only path possible | After planner-only refactor |
| `plan_turn_attempt` + shadow TurnFrame | **Yes** | **Yes** | Required until TurnFrame source decoupled from planner |
| `classify_ingress` | **Yes** | **Yes** | Shared safety |
| `handle_flows` | **Yes** | **Yes** | Lead/situation/booking |
| `load_target_runtime_client_context` / cached FullContext | **Yes** | **Yes** | Core product path |
| `run_target_offline_boundary_enforced_fullcontext_response` | **Yes** | **Yes** | Core product path |
| `write_target_runtime_session_after_materialized` | **Yes** (materialized) | **Yes** | Target session continuity |
| `set_last_subject` (legacy field) | **Yes** (side effect) | **Temporary** | After legacy session consumers removed |

---

## D. Blockers and non-blockers

### Real blockers (authority switch)

**None in runtime wiring.** S63 proved target-only materialization under flag ON with zero legacy hits.

**Governance blockers (owner decisions, not code defects):**

1. Approve flipping `TARGET_FULLCONTEXT_DEV` default to ON (or successor product flag).
2. Approve fail-closed behavior when TurnFrame unavailable (no silent legacy fallback).
3. Approve emergency rollback semantics (env flip **between** requests, not mid-turn).

### Non-blocking improvements (do not delay switch)

| Item | Notes |
|------|-------|
| Planner fail-open still invokes legacy resolver LLM | Extra cost; routing unaffected when flag ON |
| Target mode skips duplicate_short_circuit, promo_overview | Parity gaps vs legacy; acceptable under FINAL_FULLCONTEXT_ONLY |
| `situation_back` restores `get_last_content_ui_payload` (legacy snap) | Edge case; rare in target-first UX |
| `set_last_subject` dual-write to legacy session | Compatibility shim; safe to keep temporarily |
| `CLARIFY_STATE_ON` pending_clarify reask in `ask_turn.py` | Legacy-path only; inactive when target ON |

---

## E. Failure modes (target ON, no legacy escape)

| Condition | Code path | User-facing route | Legacy fallback? |
|-----------|-----------|-------------------|------------------|
| Missing TurnFrame (`shadow not_available/degraded`) | `target_runtime_turn_frame_bridge.py:31–45` | `target_fullcontext_error` | No |
| Client bootstrap failure | `target_runtime_turn.py:85–94` | `target_fullcontext_error` | No |
| Boundary backend exception | `target_runtime_turn.py:124–133` | `target_fullcontext_error` | No |
| Boundary `uncertain` | `target_turn_frame_policy_envelope_enforcement` → `materialize_boundary_uncertain_payload` | `target_fullcontext_boundary_uncertain` | No |
| Verifier block | `TargetResponseVerificationError` → `materialize_target_error_payload` | `target_fullcontext_verifier_blocked` | No |
| Pipeline exception | `target_runtime_turn.py:186–195` | `target_fullcontext_error` | No |
| Unknown CTA key | `build_target_runtime_widget_cta` returns `None` | materialized without CTA button | No |
| Invalid/unknown ref (empty q) | `pre_resolver_turn.py:296–308` | `target_fullcontext_followup_unknown` | No |
| Unhandled exception in `/ask/stream` | `app.py:759–793` | generic `internal_error_response` | No legacy routing |

**Controlled target-only responses exist for all traced failure modes** — none re-enter `orchestrate_routing_after_resolver`.

---

## F. Session fields

### Legacy fields still touched (compatibility)

| Field | Writer in target path | Still needed after switch? |
|-------|----------------------|---------------------------|
| `hist` | resolver (read) | Until resolver removed |
| `lead_intent`, `pending_lead_offer`, `situation_pending` | `handle_flows` | **Yes** — lead/situation |
| `last_subject` | `write_target_runtime_session_after_materialized` → `set_last_subject` | Temporary shim |
| `current_doc_id`, `pending_clarify` | Not updated on target materialized | Legacy-only consumers |

### Target fields (sufficient for continuity)

| Field | Purpose |
|-------|---------|
| `target_runtime_state` | `last_service_id`, `last_topic`, `last_primary_aspect`, shown fact/amplifier/consultation IDs |
| `target_runtime_followups` | ref-click navigation (S63 Turn 2 validated) |

S63 Turn 3 confirmed hydration: `last_service_id=all_on_4` drives doctors materialization without legacy `current_doc_id`.

---

## G. Imports / branches unreachable after authority switch

When default ON and legacy branch removed:

| Unreachable in normal dialog | Module / symbol |
|------------------------------|-----------------|
| `orchestrate_routing_after_resolver` body | `orchestration/ask_turn.py` |
| `route_source`, `build_answer_plan` product calls | `source_routing`, `core/answer_planner` |
| Legacy chunk dispatch (`kind=chunk`) | `app.py` `_dispatch_orchestration_*` |
| Legacy composer dispatch (`kind=composer`) | `app.py`, `orchestration/composer_flow.py` |
| Pre-resolver legacy ref handlers | `orchestrate_price_widget_ref`, `get_chunk_by_ref` in ref path |

**Keep reachable:** ingress, flows, resolver/planner (TurnFrame), target runtime stack.

**Delete only after separate verification period** — not in same commit as switch: `source_routing`, chunk retrieval paths, legacy composer overlay, `orchestrate_routing_after_resolver` and dependents.

---

## H. Minimal S65 milestone (proposed)

**Goal:** Transfer product authority — make target FullContext the default answer path without adding parallel layers or in-turn legacy fallback.

### Allowlist (proposed)

| File | Change |
|------|--------|
| `config.py` | Flip `TARGET_FULLCONTEXT_DEV` default to `ON` **or** add `TARGET_FULLCONTEXT_AUTHORITY` (owner picks one name) |
| `app.py` | Wire authority flag if renamed; no new orchestration layer |
| `docs/FLAGS_AND_STATUS.md` | Document authority ON + emergency kill-switch |
| `docs/STRANGLER_ROADMAP.md` | S65 authority gate |
| `TASK.md` | S65 governance |
| `tests/test_s65_authority_switch_offline.py` | New — default-ON process test: legacy routing spy never called; target widget returned |

### Minimal code changes

1. **Default flip** (owner-approved): `TARGET_FULLCONTEXT_DEV` default `"1"` in `config.py`.
2. **Assert no legacy branch** when authority ON (extend S61 spy pattern).
3. **Document kill-switch**: `TARGET_FULLCONTEXT_DEV=0` in env = full legacy path for emergency; must be process-level, not per-turn auto-fallback.

### Tests

- Offline: monkeypatch/spy on `orchestrate_routing_after_resolver` — not called when authority ON.
- Offline: both `/ask` and `/ask/stream` return `answer_path=target_fullcontext` for normal turn (fake backends).
- Re-run S62 pin guard + S63 harness `--dry-run` unchanged.

### Intentionally NOT in S65

- Legacy code deletion
- Resolver/planner removal
- Percentage rollout / shadow dual responses
- New verifier logic
- Admin / runtime logging
- A9 changes
- Live re-run of S62/S63

---

## I. Rollback / kill-switch semantics (docs only)

| Flag state | Semantics |
|------------|-----------|
| `TARGET_FULLCONTEXT_DEV=1` (authority ON) | All normal dialog → target pipeline; guards unchanged |
| `TARGET_FULLCONTEXT_DEV=0` (emergency) | Full legacy product path; target bootstrap not called for answers |

**Rules:**

- Kill-switch applies on **next HTTP request** after env change.
- **Forbidden:** catching target error inside one turn and calling `orchestrate_routing_after_resolver`.
- Optional future: `TARGET_FULLCONTEXT_DEV=0` + explicit `TARGET_LEGACY_DISABLED=1` → controlled 503 for non-guard turns (not implemented in S64/S65 unless owner requests).

---

## J. Post-switch plan (milestones)

1. **S65 — authority switch** — default ON, tests, FLAGS docs, owner sign-off.
2. **S65 verification** — limited local/product check under authority ON (not full S62/S63 rerun unless owner orders).
3. **S66 — legacy isolation** — dead-code marking, remove unreachable dispatch kinds from hot path, stop importing legacy routing in `app.py`.
4. **S67+ — legacy deletion** — delete `orchestrate_routing_after_resolver`, `source_routing` product calls, chunk/composer product paths after soak period.

---

## K. Code references (authority gate)

```399:442:app.py
def _orchestrate_ask_turn(data: dict):
    pre = run_pre_resolver_turn(
        ...
        target_fullcontext_mode=TARGET_FULLCONTEXT_DEV,
    )
    if isinstance(pre, AskOrchestrationResult):
        return pre

    resolver = run_resolver_turn(...)

    if TARGET_FULLCONTEXT_DEV:
        return orchestrate_target_fullcontext_turn(...)
    return orchestrate_routing_after_resolver(...)
```

```32:71:orchestration/target_fullcontext_turn.py
def orchestrate_target_fullcontext_turn(...):
    """Run target-only FullContext path; never falls back to legacy routing."""
    ...
    outcome = run_target_fullcontext_runtime_turn(...)
    ...
    return AskOrchestrationResult(kind="service_reply", ...)
```

```96:100:config.py
TARGET_FULLCONTEXT_DEV = os.getenv("TARGET_FULLCONTEXT_DEV", "0").lower() in (
    "1", "true", "yes",
)
```

---

**S64 audit status:** complete (read-only).  
**Authority transferred:** NO.  
**Next gate:** S65 (owner approval required).
