# FULLCONTEXT_PRESENTATION_PARITY — seam audit

**Дата:** 2026-07-27  
**Baseline:** `codex/stage-a` @ `50c6cf9` (`FINAL_CLIENT_PACK_DATA_CONVERGENCE B`)  
**Режим:** governance / docs / tests only · **NO product code / NO LIVE / NO LLM**  
**Owner GO:** Phase 1 governance only; implementation blocked until PRE-CODE ✅ + separate owner GO

## Preflight

| Check | Result |
|---|---|
| `HEAD` == `origin/codex/stage-a` @ `50c6cf9` | ✅ |
| Working tree clean at governance start | ✅ |
| Target FullContext product path active (S69) | ✅ |
| Legacy `policy.py` island not on target materialized path | ✅ |

## Owner decisions (binding for implementation)

### Choice menu — max 4 governed buttons

When the bot offers the patient a branch choice (scope, stage, situation variant, typed clarification/action), up to **4** governed buttons are allowed.

- Classification by **typed action/ref** (`UiScopeAction`, `UiStageAction`, other governed clarification choices), **not** button label text.
- Max 4; deterministic ordering; dedup by ref; session-bound refs only.
- Invalid/unshown ref → existing fail-closed.
- Choice menu **must not** mix with ordinary secondary navigation buttons in one response.
- CTA is separate and does **not** consume a choice slot.
- No regex/phrase lists for menu type detection.

### Secondary UI — max 2 slots

For ordinary informational, marketing, and price follow-ups:

- `suggest_h3`, FAQ/info/comparison navigation, service-detail followups, price details («Что входит», «Оплата по этапам»), video, «Рассказать о ситуации».
- Video has priority and occupies one slot.
- Remaining slots get next unshown followups.
- Situation action competes for the same two slots.
- Shown/clicked buttons do not auto-repeat.
- CTA and text marketing facts do **not** occupy slots.

**Price-detail slots:** max 2; authored service followups only; directly requested aspect answered in text (matching button not repeated); not mixed with content followups; scope/stage choice menu uses the 4-slot limit, not price-detail limit.

### Marketing / CTA / session (unchanged limits)

- Marketing facts: max 3 per turn; amplifiers max 2; scenarios 0–2 from Planner.
- CTA semantic context: `price` | `doctors` | `service` | `default` from validated turn/spec.
- Session cadence: shown/clicked followup refs, video IDs, fact IDs, amplifier refs, consultation value refs; write only after materialized response.

## Master seam table

| # | Mechanism | Canonical docs | Producer | Product consumer | Session writer | Widget consumer | State |
|---|-----------|----------------|----------|------------------|----------------|-----------------|-------|
| 1 | Choice menu (≤4 typed actions) | `docs/ARCH_TARGET_DESIGN.md` AC1–AC3; `docs/MARKETING_SCENARIO_ARCHITECTURE.md` §Choice menu; `contracts/ui_scope_action.py`, `contracts/ui_stage_action.py` | `core/target_client_ui_nav.py` (`materialize_scope_nav_followups`, `materialize_stage_nav_followups`); ingress: `core/target_ui_scope_action.py`, `core/target_ui_stage_action.py` | `core/target_scope_aware_price_package.py` → `navigation_followups`; merged in `core/target_runtime_widget.py` `_merge_quick_replies` | `core/target_runtime_session.py` `write_target_runtime_session_after_materialized` → `target_runtime_followups` | `orchestration/pre_resolver_turn.py` ref gate; `static/widget/widget.js` | **Partially connected** — scope/stage nav on price path works; no max-4 cap; choice vs secondary not separated |
| 2 | Secondary UI (2 slots) | `docs/MARKETING_SCENARIO_ARCHITECTURE.md` §Content navigation; `docs/MARKETING_QUESTION_FOUNDATION.md` §Content UI slots | Content: `core/target_response_followup_materializer.py`; Price: `_price_followups`; legacy ref: `policy.py` `build_policy_decision` | `core/target_runtime_widget.py` → `quick_replies`; post: `app.py` → `normalize_policy_payload` | `target_runtime_followups` (click allowlist only) | `static/widget/widget.js`, `static/widget/followup_controls.js` | **Disconnected** for content FAQ/info; price secondary connected; video/situation disconnected on target |
| 3 | Document/source identity | `docs/ARCH_TARGET_DESIGN.md` §FINAL_FULLCONTEXT_ONLY #5; `docs/MARKETING_SCENARIO_ARCHITECTURE.md` §Target ownership | Service: `core/target_offline_response_assembly.py`; plan: `core/target_response_materialization_plan.py`; content-only: `core/target_fullcontext_content_package.py` | `core/target_response_verifier.py` `TargetVerifiedComposedResponse`; `orchestration/target_fullcontext_turn.py` | `target_runtime_state` (service focus, not used MD) | `app.py` `finalize_ask(doc_id=...)` | **Disconnected** — **Gap A** |
| 4 | Content limiter | `ux_builder.py`; `policy.py` `UI_FAMILY_MD`; `tests/test_ui_source_policy.py` | `normalize_policy_payload` caps `md_navigation` to 1 QR | `app.py` `_service_reply` / `_sse_service_reply` | none | widget | **Stale** — conflicts with 2-slot norm — **Gap B** |
| 5 | Video | `clients/demo/video_catalog.yaml`; `core/video_catalog_loader.py`; client MD `video_key` | Legacy: `policy.py` slot logic; catalog loaders | Target: `core/target_runtime_widget.py` hardcodes `video=None` | Legacy `session.mark_video_shown` — not target session | `static/widget/widget.js`; `app.py` `/api/video-catalog` | **Disconnected** on product path — **Gap C** |
| 6 | Situation action | `docs/MARKETING_QUESTION_FOUNDATION.md` §7.2; `docs/MARKETING_SCENARIO_ARCHITECTURE.md` | Legacy: `policy.py` `situation_allowed`; intake: `orchestration/pre_resolver_turn.py` | Target widget: `situation.show=False` always | `situation_pending` / lead (intake path) | `static/widget/widget.js` | Auto-offer **disconnected** — **Gap D**; intake after click connected |
| 7 | Marketing scenarios | `docs/MARKETING_SCENARIO_ARCHITECTURE.md`; `docs/MARKETING_QUESTION_TECH.md` | Selector: `core/target_marketing_selector.py`; offline assembly exists | Runtime hard-off: `core/target_runtime_client_context.py` L148–149; `core/target_runtime_turn.py` L242 `marketing_scenarios=()` | `shown_fact_ids`, `shown_amplifier_refs` after materialize | answer text (not widget slots) | **Disconnected** at runtime producer — **Gap E** |
| 8 | CTA semantic context | `docs/MARKETING_SCENARIO_ARCHITECTURE.md` §CTA; `clients/demo/target_response/marketing.yaml` | `core/target_marketing_selector.py`; `core/target_runtime_widget.py` `build_target_runtime_widget_cta` | Hardcoded `semantic_context="service"` in `core/target_runtime_client_context.py` L148 | `selected_cta_key` in meta only | `static/widget/widget.js` CTA | CTA key→label connected; context selection frozen — **Gap F** |
| 9 | Session cadence | `docs/MARKETING_SCENARIO_ARCHITECTURE.md` §Session; `core/target_runtime_session.py` | Read/write target session | `core/target_runtime_turn.py` reads `shown_*` | `target_runtime_state`, `target_runtime_followups` | pre-resolver ref gate | **Partially connected** — facts/amplifiers OK; missing video + followup no-repeat ledger — **Gap G** |
| 10 | `consultation_value` | `docs/MARKETING_SCENARIO_ARCHITECTURE.md` §consultation_value; `core/service_consultation_source.py` | `build_service_consultation_values` → runtime context | Wired when `include_consultation_close=True` + service `selected_content_ref` | `shown_consultation_value_refs` | answer text amplifier | **Connected** on service-bound path; broken for content-only FullContext; validator gap |

## Confirmed gaps A–G

### Gap A — Document/source identity

| Layer | Finding | Reference |
|-------|---------|-----------|
| Verified response | No `used_doc_ids` / source refs on `TargetVerifiedComposedResponse` | `core/target_response_verifier.py` |
| Content-only package | `primary_content_ref=None`, empty followups | `core/target_fullcontext_content_package.py` |
| Orchestration | `service_doc_id=None` always | `orchestration/target_fullcontext_turn.py` L62–68 |
| Effect | All-on-4 followups cut to 1; bone-graft FAQ may get 0 buttons; `suggest_h3`/video/situation cannot bind to used MD | `core/target_response_followup_materializer.py` |
| **State** | **Disconnected** |

**Required design:** one governed source-identity path — Composer returns validated `doc_id`/`content_ref`; strict MD index validation; Verifier passes only validated refs; presentation layer uses them; model cannot invent refs; FAQ/info stays MD document, not service entity; no retriever, no second LLM.

### Gap B — Content limiter conflict

| Layer | Finding | Reference |
|-------|---------|-----------|
| Normative | 2 secondary content slots | owner decision; `docs/MARKETING_SCENARIO_ARCHITECTURE.md` |
| Limiter | `md_navigation` → max **1** `quick_reply` | `ux_builder.py` L50–53 |
| Test encodes stale limit | `test_md_navigation_still_limits_suggest_refs_to_one` | `tests/test_ui_source_policy.py` |
| Applied on target | After widget, JSON + SSE | `app.py` L114–115, L441–443 |
| **State** | **Stale** |

### Gap C — Video

| Layer | Finding | Reference |
|-------|---------|-----------|
| Data | `video_key` in MD; `video_catalog.yaml` | client pack |
| Target | `video=None` on all materialized/terminal/error payloads | `core/target_runtime_widget.py` L201, L218, L254, L285 |
| Session | `shown_video_ids` documented, not in target session | docs vs `core/target_runtime_session.py` |
| **State** | **Disconnected** |

### Gap D — Situation action

| Layer | Finding | Reference |
|-------|---------|-----------|
| Normative | `situation_allowed` competes for 2 content slots | `docs/MARKETING_QUESTION_FOUNDATION.md` |
| Target | `situation.show=False` always | `core/target_runtime_widget.py` L202 |
| Intake post-click | `handle_flows` / `situation_pending` still alive | `orchestration/pre_resolver_turn.py` |
| **State** | Auto-offer **disconnected** |

### Gap E — Marketing scenarios

| Layer | Finding | Reference |
|-------|---------|-----------|
| Schema/selector | Full offline pipeline | `core/target_marketing_selector.py` |
| Runtime bootstrap | `include_initial_block=False`, `semantic_context="service"` | `core/target_runtime_client_context.py` L148–149 |
| Runtime turn | `marketing_scenarios=()` hardcoded | `core/target_runtime_turn.py` L242 |
| TurnFrame | No `marketing_scenarios` field in contract | `contracts/turn_frame.py` |
| **State** | **Disconnected** |

### Gap F — CTA semantic context

| Layer | Finding | Reference |
|-------|---------|-----------|
| Normative | price→`price`, doctors→`doctors`, else `service`/`default` | owner decision; `marketing.yaml` |
| Runtime | Always `"service"` | `core/target_runtime_client_context.py` L148 |
| **State** | Context selection **disconnected** |

### Gap G — Session cadence

| Layer | Finding | Reference |
|-------|---------|-----------|
| Implemented | `shown_fact_ids`, `shown_amplifier_refs`, `shown_consultation_value_refs`; `target_runtime_followups` as click allowlist | `core/target_runtime_session.py` |
| Missing | `shown_video_ids`; shown/clicked content and price followup refs; semantic context / CTA persistence | docs vs code |
| Terminal guard | Session write only on `TargetTurnFrameBoundMaterializeResponse` | `core/target_runtime_turn.py` L280–291 |
| **State** | **Partially connected** |

## consultation_value — preserve checklist

| Check | Status @ `50c6cf9` |
|-------|-------------------|
| Value from exact `content_ref` frontmatter only | ✅ offline |
| Frontmatter excluded from FullContext body (S36) | ✅ by design |
| Only under matching service answer | ✅ |
| 1 marketing slot + 1 amplifier slot | ✅ selector |
| Max one automatic show per session per exact ref | ✅ session |
| Shown-state only after materialized inclusion | ✅ |
| Terminal/error do not update shown-state | ✅ |
| Direct consultation question = primary content | ✅ |
| `validate_client_pack.py` checks | ❌ missing |
| Content-only FullContext path | ❌ no `selected_content_ref` |

Demo consultation values: `classic`, `one_stage`, `all_on_4` service MDs.

## Superseded / not product path

| Surface | Decision |
|---------|----------|
| `policy.py` `build_policy_decision` video/situation/slot logic | **Superseded** for target materialized path — reference only for slot semantics |
| `normalize_policy_payload` 1-QR `md_navigation` cap | **Stale** — must align to 2-slot + separate choice menu in implementation |
| Per-MD routing / retriever | **Forbidden** per FINAL_FULLCONTEXT_ONLY |

## Acceptance matrix (implementation)

| # | Criterion |
|---|---|
| 1 | All-on-4 info → 1–2 relevant secondary buttons, not artificially 1 |
| 2 | Bone graft info → validated used document → up to 2 its followups |
| 3 | FAQ document does not become service entity |
| 4 | Invalid invented `used_doc_id` → rejected/omitted deterministically |
| 5 | Content with video + followups → video + max 1 followup |
| 6 | Content without video → max 2 followups |
| 7 | Situation action uses one of two content slots |
| 8 | Choice scope menu with 3 options → all 3 shown |
| 9 | Choice menu fixture with 4 options → all 4 shown |
| 10 | Choice menu with 5 options → deterministic first 4 + audit/drop reason |
| 11 | Choice menu not mixed with secondary navigation |
| 12 | Price details → max 2 |
| 13 | Scope/stage menu not cut by price-detail limiter |
| 14 | JSON/SSE parity |
| 15 | Previously shown/clicked followup does not auto-repeat |
| 16 | Video shown automatically once per session cadence |
| 17 | Reset/SID isolation clear cadence |
| 18 | Marketing scenarios 0–2 reach Planner → selector |
| 19 | Marketing limits 3/2 enforced in runtime |
| 20 | price/doctors/service get matching CTA keys |
| 21 | CTA suppression boundaries preserved |
| 22 | consultation_value first show / no repeat / exact ownership |
| 23 | terminal/error do not write shown-state |
| 24 | New sparse client pack passes without video/consultation_value |
| 25 | Invalid consultation_value client pack fails validator |
| 26 | Invalid video key client pack fails validator or documented optional-policy |
| 27 | Existing rich pricebook, A9, AC1–AC3, typed UI flows without regression |
| 28 | Frozen S-series/A9R/final-scope/W1b artifacts byte-identical |

## Implementation seam (target — not in this commit)

```text
Planner/TurnFrame (marketing_scenarios 0–2)
  → validated source identity (used doc refs from Composer)
  → ResponseSpec + presentation decision (choice ≤4 | secondary ≤2 | price ≤2)
  → target_marketing_selector (semantic_context from turn)
  → target_runtime_widget (video, situation, quick_replies, CTA)
  → normalize_policy_payload (aligned, not truncating to 1)
  → session cadence write (materialized only)
```

## STOP

This audit + TASK governance authorize **governance PRE-CODE only**.
Implementation begins only after independent PRE-CODE checker ✅ and explicit owner GO.
**NO PRODUCT CHANGE / NO LIVE / NO LLM** in governance commit.
