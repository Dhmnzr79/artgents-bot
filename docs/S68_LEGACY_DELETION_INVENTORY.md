# S68 — Legacy deletion inventory (read-only)

**Baseline:** `codex/stage-a` / `3d0060d` (post-S67) · **READ-ONLY** · evidence collected 2026-07-23

---

## A. Executive summary

| Question | Answer |
|----------|--------|
| **Ready to delete legacy?** | **Yes** — default FullContext is sole live product path since S65/S67; legacy is reachable only via `TARGET_FULLCONTEXT_DEV=0` or unreachable `chunk`/`composer` dispatch leftovers. |
| **Real blockers?** | **Two MODIFY_THEN_DELETE seams**, not architecture blockers: (1) `pre_resolver_turn.py` legacy ref/continuation branches; (2) `lead_flow.py` still calls `get_chunk_by_ref` for redirect chunks. No target module imports legacy answer stack (verified S67 J). |
| **Deletion milestones** | **One S69** with 8 ordered phases (below). No second milestone required unless owner wants split authority-cut vs module purge for review granularity. |

**Counts (legacy-only product modules, ~3.3k LOC):**

| Module | Lines | Legacy-only |
|--------|------:|-------------|
| `chunk_responder.py` | 1400 | Yes |
| `orchestration/ask_turn.py` | 376 | Yes |
| `orchestration/price_flow.py` | 473 | Yes |
| `source_routing.py` | 330 | Yes |
| `orchestration/composer_flow.py` | 296 | Yes |
| `orchestration/patient_playbook_flow.py` | 240 | Yes |
| `orchestration/catalog_flow.py` | 163 | Yes |

Plus `app.py` seams (~150 LOC), `config.py` flag, `pre_resolver_turn.py` legacy branches (~120 LOC), and ~25 legacy-only test files/groups.

---

## B. Current scheme

### Default FullContext (env absent or `TARGET_FULLCONTEXT_DEV=1`)

```
HTTP /ask|/ask/stream
  → run_pre_resolver_turn(..., target_fullcontext_mode=True)
      → ingress / lead / booking / situation short-circuits (shared)
      → target ref navigation (resolve_target_followup_navigation)
  → run_resolver_turn → TurnFrame shadow (turn_planner_llm)
  → orchestrate_target_fullcontext_turn
      → target runtime → Composer/Verifier (target backends)
  → _dispatch → service_reply only
  → _service_reply (no legacy answer-plan block for target_fullcontext_*)
  → finalize_ask / UI policy / session widget
```

Evidence: `app.py:411–438`, `orchestration/pre_resolver_turn.py:283–311`, `orchestration/target_fullcontext_turn.py:32`.

### Kill-switch (`TARGET_FULLCONTEXT_DEV=0`, process restart)

```
HTTP → shared guards → TurnFrame → orchestrate_routing_after_resolver (lazy)
  → source_routing.route_source
  → price_flow / catalog_flow / patient_playbook_flow
  → composer_flow.try_composer_overlay | chunk_responder
  → dispatch kind chunk|composer|service_reply (legacy routes)
```

Evidence: `app.py:134–138`, `app.py:433–441`, `orchestration/ask_turn.py:155`.

---

## C. Files and symbols

| File / symbol | Current callers/importers | Target/shared use | Legacy-only | Action | Order | Tests affected |
|---------------|---------------------------|-------------------|-------------|--------|------:|----------------|
| `config.TARGET_FULLCONTEXT_DEV` | `app.py`, `pre_resolver_turn`, harnesses | Mode gate | Kill-switch only | **DELETE** | 1 | S65/S67 kill-switch tests; S61 OFF tests |
| `app.orchestrate_routing_after_resolver` (lazy wrapper) | `_orchestrate_ask_turn` when flag=0 | No (default) | Yes | **DELETE** | 1 | S65 B/F, S67 F |
| `app._orchestrate_ask_turn` legacy branch | `app.py:433–441` | No | Yes | **MODIFY_THEN_DELETE** | 1 | S65, S67, S61 |
| `app._dispatch_*` `chunk`/`composer` kinds | `app.py:475–507`, `716–729` | No | Yes | **DELETE** | 2 | composer/chunk tests |
| `app._sse_chunk_response`, `_sse_composer_reply` | SSE dispatch | No | Yes | **DELETE** | 2 | test_composer_wiring |
| `app._service_reply` legacy plan block | `app.py:169–222` | Skipped for target | Legacy routes only | **DELETE** | 2 | test_focus_context (legacy path) |
| `orchestration/ask_turn.py` | lazy via `app.py` | No | Yes | **DELETE** | 4 | test_contacts_routing, test_doctor_route_order, test_clarify_state |
| `orchestration/composer_flow.py` | `ask_turn.py` | No | Yes | **DELETE** | 4 | test_composer_flow.py (entire file) |
| `orchestration/price_flow.py` | `ask_turn.py`, `core/price_ref_routing.py` | No | Yes | **DELETE** | 4 | test_price_brand_money, test_price_layer_parity |
| `orchestration/catalog_flow.py` | `ask_turn.py` | No | Yes | **DELETE** | 4 | — |
| `orchestration/patient_playbook_flow.py` | `ask_turn.py` | No | Yes | **DELETE** | 4 | test_situation_price_overview.py |
| `source_routing.py` | `ask_turn.py` | No | Yes | **DELETE** | 4 | test_source_routing_golden.py, test_dialog_focus_baseline.py |
| `chunk_responder.py` | lazy `app.py` dispatch | No | Yes | **DELETE** | 4 | test_composer_wiring, test_md_clean, test_verifier_trigger |
| `core/price_ref_routing.orchestrate_price_widget_ref` | `pre_resolver_turn.py:313` (legacy `else`) | No | Yes | **MODIFY_THEN_DELETE** | 3 | test_price_ref_routing.py |
| `core/price_ref_routing.parse_price_widget_ref` | `content_linter.py` | Tooling | Partial | **KEEP_SHARED** | — | test_price_ref_routing (parse only) |
| `core/price_symptom_consult.orchestrate_consult_symptom_ref` | `pre_resolver_turn.py:322` (legacy `else`) | No | Yes | **DELETE** | 3 | S61 ref tests (legacy branch) |
| `pre_resolver_turn` legacy branches | `get_chunk_by_ref`, continuation, promo, price/consult ref | Target branches at `:283+` | Legacy `else` blocks | **MODIFY_THEN_DELETE** | 3 | S61, S63, S67 E |
| `core/md_chunks.get_chunk_by_ref` | legacy flows + **lead_flow** | **lead_flow redirect** | Mostly legacy | **KEEP_SHARED** | 5 | test_md_chunks, lead tests |
| `core/md_chunks` chunk index/loader | `build_index.py`, legacy | Target uses separate loader | Partial | **INVESTIGATE_BLOCKER** | 5 | — |
| `core/target_*` runtime modules | target path | Yes | No | **KEEP_SHARED** | — | S61–S67 |
| `orchestration/pre_resolver_turn` (shared) | `app.py` | Yes | — | **KEEP_SHARED** | — | ingress/lead tests |
| `orchestration/resolver_turn` | `app.py` | Yes (TurnFrame) | No | **KEEP_SHARED** | — | planner tests |
| `orchestration/target_fullcontext_turn` | `app.py` | Yes | No | **KEEP_SHARED** | — | S61–S67 |
| `orchestration/lead_flow` | `app.py` pre-resolver | Yes | No | **KEEP_SHARED** | — | S65 G |
| `orchestration/finalize_turn` | `app.py` | Yes | No | **KEEP_SHARED** | — | — |
| `orchestration/helpers` | app, pre_resolver, lead | Yes | No | **KEEP_SHARED** | — | — |
| `query_selector.py` | resolver_turn, dialog_focus, ux_builder, many core | **Shared** (not legacy-only) | No | **KEEP_SHARED** | — | many price tests |
| `core/dialog_focus.py` | turn_planner_llm, resolver path | Yes | No | **KEEP_SHARED** | — | test_dialog_focus_* |
| `core/answer_planner.py` | ask_turn, chunk_responder, llm | Shadow/planner tests | Product legacy | **MODIFY_THEN_DELETE** | 6 | test_answer_planner (keep planner unit tests) |
| `core/answer_plan_apply.py` | app legacy `_service_reply` | No on target | Yes | **DELETE** | 6 | test_answer_packet_* |
| `core/answer_packet*.py` | composer_flow, chunk_responder | No on target | Yes | **DELETE** | 6 | test_answer_packet_composer |
| `core/follow_up_rewrite.py` | app legacy, chunk_responder, dialog_focus | dialog_focus uses `focus_from_legacy_session` | Partial | **MODIFY_THEN_DELETE** | 6 | test_follow_up_rewrite |
| `session.last_subject` | target_runtime_session write; dialog_focus/turn_planner read | **Yes** | Compatibility write | **KEEP_SHARED** | — | test_follow_up_session |
| `session.current_doc_id` | pre_resolver legacy continuation; llm.py | llm context (legacy gen?) | Partial | **MODIFY_THEN_DELETE** | 6 | — |
| `session.pending_clarify` | pre_resolver, ask_turn, composer_flow | CLARIFY_STATE_OFF default | Legacy clarify | **DELETE** | 6 | test_clarify_state |
| `llm.py` `find_chunk_by_topic_aspect` | chunk path | No target import | Legacy gen | **MODIFY_THEN_DELETE** | 6 | — |
| `evals/v5/s62|s63|s66_*_harness.py` | live harness legacy guards | Measurement | Historical | **KEEP_HISTORICAL** | — | frozen replay |
| `tools/gen_orch_slice.py` | dev tool referencing chunk dispatch | Tooling | — | **KEEP_HISTORICAL** | — | — |

---

## D. Runtime branches / dispatch kinds

| Branch / dispatch kind | Where | Target uses | Reachable default | Action |
|------------------------|-------|-------------|-------------------|--------|
| `TARGET_FULLCONTEXT_DEV` branch | `app.py:433` | Yes (True arm) | Yes | DELETE false arm + flag |
| `service_reply` + `target_fullcontext_*` | target turn | Yes | Yes | **KEEP** |
| `service_reply` + `price_lookup`/`catalog_facts`/ingress | pre_resolver / legacy | No | Only kill-switch | DELETE with legacy |
| `kind=chunk` | `pre_resolver` ref, `ask_turn` routing | No | Only kill-switch / unreachable after pre_resolver cleanup | DELETE |
| `kind=composer` | `ask_turn` → composer_flow | No | Only kill-switch | DELETE |
| `_sse_typing_phase` `chunk`/`composer` | `app.py:558–561` | No | Legacy SSE | DELETE cases |
| Ingress `manual_contact` | `pre_resolver_turn` | Yes | Yes | **KEEP** |
| Lead `cta_action=lead` | `pre_resolver_turn` | Yes | Yes | **KEEP** |
| Target ref `resolve_target_followup_navigation` | `pre_resolver_turn:283` | Yes | Yes | **KEEP** |
| Legacy ref `get_chunk_by_ref` | `pre_resolver_turn:331` | No | kill-switch only | DELETE |
| Legacy price ref `orchestrate_price_widget_ref` | `pre_resolver_turn:313` | No | kill-switch only | DELETE |

---

## E. Session compatibility

| Field / helper | Writer | Readers | Target need | Action |
|----------------|--------|---------|-------------|--------|
| `target_runtime_state` | `core/target_runtime_session.py` | target turn | Yes | **KEEP** |
| `target_runtime_followups` | target session | target ref nav | Yes | **KEEP** |
| `last_subject` | target session (`set_last_subject`), chunk_responder | `dialog_focus`, `turn_planner_llm`, source_routing (legacy) | Yes (read via dialog_focus) | **KEEP** field; remove legacy-only readers |
| `last_aspect` | legacy answer-plan | legacy | No on target | **MODIFY_THEN_DELETE** |
| `current_doc_id` | chunk_responder, session | pre_resolver continuation (legacy), llm | Unclear for target | **MODIFY_THEN_DELETE** after pre_resolver legacy removal |
| `pending_clarify` | composer_flow, session | pre_resolver, ask_turn | No (CLARIFY_STATE_OFF) | **DELETE** |
| `last_catalog_service` | legacy flows | query_selector, source_routing | Partial | **INVESTIGATE_BLOCKER** |
| `patient_situation` | situation flow | planner, guards | Yes | **KEEP** |

---

## F. Tests classification

| Test file / group | Class | Action | Replacement coverage |
|-------------------|-------|--------|----------------------|
| `test_s67_legacy_isolation_offline.py` | target + kill-switch | **MODIFY** — drop F kill-switch; keep A–E,G–J | S69 regression |
| `test_s65_authority_switch_offline.py` | target + kill-switch | **MODIFY** — remove §B kill-switch, §F hidden legacy | S67/S69 |
| `test_s61_*`, `test_s62_*`, `test_s63_*` | target/protected | **KEEP** | — |
| `test_s66_default_authority_live_harness.py` | historical harness | **KEEP_HISTORICAL** | frozen S66 |
| `test_composer_flow.py` | legacy | **DELETE** | none needed |
| `test_composer_wiring.py` | legacy | **DELETE** | — |
| `test_composer_display_chunk.py` | legacy | **DELETE** | — |
| `test_contacts_routing.py` | legacy (ask_turn) | **DELETE** | — |
| `test_doctor_route_order.py` | legacy (ask_turn) | **DELETE** | — |
| `test_source_routing_golden.py` | legacy | **DELETE** | — |
| `test_clarify_state.py` | legacy clarify | **DELETE** | — |
| `test_md_clean.py` | legacy chunk | **DELETE** | — |
| `test_verifier_trigger.py` | legacy chunk | **DELETE** | — |
| `test_price_layer_parity.py` | legacy composer/price | **DELETE** | target price via FullContext evals |
| `test_dialog_focus_baseline.py` | mixed (route_source) | **MODIFY** — remove route_source calls | test_dialog_focus_contract |
| `test_turn_planner_wiring.py` | mixed (composer_flow mocks) | **MODIFY** — drop composer_flow sections | planner unit tests |
| `test_answer_planner.py` | planner unit | **KEEP** | — |
| `test_dialog_focus_*.py` | shared | **KEEP** | — |
| `test_follow_up_session.py` | shared session | **KEEP** | — |
| `test_price_ref_routing.py` | mixed | **MODIFY** — keep parse tests, drop orchestrate | — |
| `evals/v5/**` frozen contracts | historical | **KEEP_HISTORICAL** | pin guards |

---

## G. Frozen protection (do not delete or rewrite)

| Artifact family | Paths | Guard |
|-----------------|-------|-------|
| S47 live | `evals/v5/artifacts/fullcontext_response_eval_live_*` | `fullcontext_response_eval_contract.py` |
| S50 | `evals/v5/artifacts/s50_live_reeval_v2_incident_manifest.json` | prior artifacts pin |
| S53 verifier replay | `evals/v5/artifacts/fullcontext_verifier_replay_*`, `s53_*` | `fullcontext_verifier_replay_contract.py` |
| S55/S58 | quality eval matrices + live artifacts | `fullcontext_quality_eval_contract.py` |
| S62 live | `evals/v5/artifacts/s62_target_runtime_live_*` | `s63_target_runtime_live_contract.assert_frozen_s62_*` |
| S63 live | `evals/v5/artifacts/s63_target_runtime_live_*` | `s66_default_authority_live_contract.assert_frozen_s63_*` |
| S66 live | `evals/v5/artifacts/s66_default_authority_live_*` | `test_s67._assert_frozen_s66_*` |
| A9 patient scope | `evals/v5/demo/patient_scope_shadow_matrix_v2.json` etc. | shadow eval contracts |
| Audit manifests | `evals/v5/artifacts/*_audit_manifest.json`, `*_post_live_audit*` | historical record |

S69 must not modify artifact bytes or weaken pin guards.

---

## H. Minimal S69 deletion milestone (proposed)

**Owner decision required before S69.** Single milestone, ordered phases:

### S69 allowlist (product + tests + docs)

| Phase | Files |
|-------|-------|
| 1 Authority cut | `config.py`, `app.py`, `TASK.md` |
| 2 Pre-resolver legacy refs | `orchestration/pre_resolver_turn.py` |
| 3 Legacy ref helpers | `core/price_ref_routing.py`, `core/price_symptom_consult.py` (partial) |
| 4 Module delete | `orchestration/ask_turn.py`, `chunk_responder.py`, `source_routing.py`, `orchestration/composer_flow.py`, `orchestration/price_flow.py`, `orchestration/catalog_flow.py`, `orchestration/patient_playbook_flow.py` |
| 5 Session/plan cleanup | `session.py` (pending_clarify), `core/answer_plan_apply.py`, `core/answer_packet*.py`, `core/follow_up_rewrite.py` (partial), `app.py` `_service_reply` |
| 6 Tests | delete/modify per section F |
| 7 Docs | `docs/STRANGLER_ROADMAP.md`, `docs/FLAGS_AND_STATUS.md`, remove kill-switch sections |
| 8 Regression | `tests/test_s67_*`, `tests/test_s65_*`, `tests/test_s61_*`, frozen pin script |

### Order

1. Remove `TARGET_FULLCONTEXT_DEV` + legacy branch in `app.py` (always target)
2. Remove `chunk`/`composer` dispatch + SSE helpers from `app.py`
3. Remove legacy ref/continuation/promo branches in `pre_resolver_turn.py` (`else` of `target_fullcontext_mode`)
4. Delete legacy orchestration modules (table C)
5. Delete `chunk_responder.py`, `source_routing.py`
6. Prune session fields after last reader gone (`pending_clarify`, legacy plan path)
7. Delete legacy-only tests; update S65/S67/S61 kill-switch tests
8. Update docs; run target regression + frozen pins

**Not in S69:** `query_selector.py` (shared), `core/dialog_focus.py`, `core/md_chunks.py` (lead_flow), `evals/**` artifacts, A9.

---

## I. S69 stop conditions

Stop and escalate if:

- Any candidate has a **target runtime importer** not listed in this inventory
- Deletion requires changing **TurnFrame planner** semantics (`orchestration/resolver_turn.py`, `core/turn_planner_llm.py`)
- **lead_flow** breaks without `get_chunk_by_ref` — migrate redirect first
- **Frozen artifact** bytes would need rewriting
- **Live/LLM** required to prove deletion safety
- Owner has not approved S69 TASK

---

## J. Evidence commands

```powershell
# Authority
rg -n "TARGET_FULLCONTEXT_DEV|orchestrate_routing_after_resolver" app.py config.py orchestration/

# Legacy importers
rg -l "orchestration.ask_turn|chunk_responder|source_routing|composer_flow|price_flow|catalog_flow" --glob "*.py"

# Pre-resolver legacy vs target
rg -n "target_fullcontext_mode|get_chunk_by_ref|orchestrate_price_widget_ref" orchestration/pre_resolver_turn.py

# Target isolation (S67)
rg "ask_turn|chunk_responder|source_routing|composer_flow" core/target*.py orchestration/target_fullcontext_turn.py

# Session fields
rg -n "last_subject|current_doc_id|pending_clarify" session.py orchestration/ core/

# Kill-switch tests
rg -l "TARGET_FULLCONTEXT_DEV.*0|kill.switch" tests/

# Frozen sanity
python -c "from evals.v5.s66_default_authority_live_contract import assert_frozen_s62_live_artifacts_unchanged, assert_frozen_s63_live_artifacts_unchanged; from tests.test_s67_legacy_isolation_offline import _assert_frozen_s66_artifacts_unchanged; assert_frozen_s62_live_artifacts_unchanged(); assert_frozen_s63_live_artifacts_unchanged(); _assert_frozen_s66_artifacts_unchanged(); print('frozen OK')"
```

**Key file references:**

- Kill-switch gate: `app.py:433–441`
- Lazy legacy wrapper: `app.py:134–138`
- Target ref nav: `pre_resolver_turn.py:283–311`
- Legacy chunk ref: `pre_resolver_turn.py:331–343`
- Target session write: `core/target_runtime_session.py:106–140`
- S67 import firewall: `tests/test_s67_legacy_isolation_offline.py:519–538`

---

**S68 status:** inventory complete. **Do not start S69 without owner-approved TASK.**
