# TASK — AC3 Atomic runtime wiring: scope-aware price flow

**Product baseline:** `codex/stage-a` @ `57f9067` (AC2 complete) · **W1b PARKED** · **NO LIVE / NO LLM / NO A9 product read**

**Authority:** Architecture Convergence Audit (2026-07-24); канон: `docs/ARCHITECTURE_CONVERGENCE.md`, `docs/PRICE_SERVICE_ARCHITECTURE.md`.

**AC1 complete:** `72681cc` · typed `UiScopeAction` + `EffectiveScope` + session `patient_facts`.
**AC2 complete:** `5a3a2f8` · offline `run_target_scope_aware_selection` (applicability + S15 + S23/S24).

## Goal

**Атомарно** подключить AC1 + AC2 к реальным ответам и кнопкам виджета:

```text
message / UiScopeAction click
  → EffectiveScope (AC1)
  → run_target_scope_aware_selection (AC2)
  → ResponseStage (derived, not a second selector)
  → materials / evidence / Composer / Verifier / widget
```

AC3 **заменяет** product path W1 `family_price_overview` (selection без `service_catalog.selection`) на scope-aware flow.
AC3 **не** создаёт второй selector, regex/phrase routing, A9 authority или W1b restore.

**Явно вне AC3:** A9 free-text scope authority; live/LLM evals; C2 TurnFrame cleanup; W1b patch restore.

## W1b parked (do not touch)

Snapshot: `docs/artifacts/w1b_wip_checkpoint_2026-07-24/` (`MANIFEST.txt`, `checksums.sha256`, `RESTORE.md`).

- **Запрещено:** restore patch, `family_price_groups.yaml` as applicability/authority, `several_teeth`/`full_jaw` vocabulary, копирование W1b кода целиком.
- **Разрешено:** read-only изучение snapshot; REWORK идеи two-phase nav на `target:ui_scope/` refs.
- **Artifact hashes** must remain byte-identical to `checksums.sha256`.

## Baseline and tree state

**Governance commit (this checkpoint):**

- `HEAD` = `57f9067` (AC2 product + completion record).
- Dirty diff — только `TASK.md` + minimal docs sync.
- Push → **PRE-CODE checker ✅** → STOP.

**AC3 implementation preflight** (later, separate owner GO):

- `HEAD` = governance commit after this TASK.
- Working tree clean; W1b checksums match.

## Process (mandatory)

1. **Governance (this commit):** seam audit in TASK + docs delta → push → **PRE-CODE ✅** → STOP.
2. **AC3 implementation** (later): atomic runtime wiring + ResponseStage + scope/follow-up UI → **COMPLETION ✅** → product commit → STOP.

No product code before PRE-CODE ✅.

---

## Normative target behavior (AC3)

### 1. Broad price question («Сколько стоит имплантация/протезирование?»)

- Краткий обзор цен **без** этапов оплаты и длинных описаний.
- Максимум несколько ценовых ориентиров из AC2 `broad_anchors` (не полный каталог).
- Короткое уточнение масштаба в тексте.
- Кнопки масштаба: «Один зуб», «Несколько зубов», «Вся челюсть» — refs `target:ui_scope/{topic}/{extent}`; labels client-owned.

### 2. Scope button click

- AC1: typed `UiScopeAction` (ref-only; label не источник extent).
- `EffectiveScope` → AC2 `run_target_scope_aware_selection`.
- AC2 `scoped_shortlist` → materialize answer (не terminal defer).
- Planner **не** переугадывает значение кнопки.

### 3. After scope chosen or named service

- Кнопки «Один зуб / Несколько зубов / Вся челюсть» **не повторять**.
- Показывать только уместные следующие действия при наличии structured data: «Что входит», «Оплата и рассрочка» и т.п. из offer/MD sources.
- Не показывать кнопку, повторяющую уже выбранный вариант.

### 4. Finance and marketing facts

- Цены и этапы оплаты — **только** pricebook (S23/S24).
- Marketing facts и consultation/CTA — **только** structured слой (`facts.json`, `marketing.yaml`, KB).
- Не превращать каждый бонус в отдельную кнопку.
- **Максимум** 2 тематические follow-up-кнопки + 1 CTA.
- Никаких hardcoded demo `service_id` или фраз в shared core.

### 5. ResponseStage (derived)

- Выводить детерминированно из: текущий запрос, `EffectiveScope`, AC2 result, explicit `service_id`/follow-up ref.
- **Не** создавать persistent session state, если stage выводится из этих данных.
- Минимально различать: `broad_family_price` vs `scoped_family_price` vs `concrete_service_price` vs `stage_clarify` (prosthetics stage unknown when catalog requires).
- Stage управляет составом ответа и follow-up; **не** выбирает услуги и цены (это AC2).

### 6. Prosthetics — same mechanism

- Тот же pipeline для `topic=prosthetics`; отдельный имплантационный маршрут **запрещён**.
- Stage axis (`natural_tooth_present`, `implant_placed`, …) — через authored `service_catalog.selection` + deterministic inputs; при data-gap — typed stop + owner data fix, не временный парсер.

### 7. UI contract

- Один канонический канал follow-up → `quick_replies`.
- Dedup по `ref`; session-bound refs (AC1 security).
- Корректный `attribution_kind` per PRICE_SERVICE.
- `/ask` и `/ask/stream` — **идентичная** семантика scope/price flow.

### 8. Free-text scope (explicitly deferred)

- Фразы «вся челюсть», «один зуб» в свободном тексте **не** решаются в AC3 через regex/словари.
- Канонический scope из free text — **отдельный A9 authority checkpoint** после AC3.

---

## Read-only seam audit (AC1 + AC2 + S27 runtime)

### Current product gap (verified @ `57f9067`)

| Observation | Location | Impact |
|-------------|----------|--------|
| `effective_scope` computed then discarded | `core/target_runtime_turn.py` L146–153 `_ = effective_scope` | Scope has zero effect on price answers |
| Strategy context not scope-aware | `resolve_target_runtime_strategy_context(bundle, service_id=...)` | Ignores extent/jaw/stage |
| Price-without-service → W1 overview | `core/target_turn_frame_dispatch.py` `_family_price_overview_topic` → `family_price_overview_topic` spec | Bypasses `service_catalog.selection` |
| W1 selector ignores selection | `core/target_family_price_overview.py` `select_family_price_overview_services` | topic + active + role_rank only |
| S34 materialization gate | `core/target_spec_offline_response_package.py` L103–166 | Calls W1 selector, not AC2 |
| Family overview strips marketing | `core/target_policy_bound_verified_response_pipeline.py` | `is_family_price_overview_spec` → no CTA/marketing |
| No scope button emitter | `build_ui_scope_ref` used in tests only | Scale menu never appears in widget |
| AC1 click path works | `orchestration/pre_resolver_turn.py` → `resolve_ui_scope_ref_click` | Consume-only; no matching emit |
| Follow-up policy | `core/target_response_followup_policy.py` | `content`/`price` only; no `ui_scope` family |
| Widget merge | `core/target_runtime_widget.py` `_followups_to_quick_replies` | Single quick_replies list |
| `ResponseStage` | docs only | Not in code |

### Reuse as-is (compose, do not rebuild)

| Layer | Module | Role in AC3 |
|-------|--------|-------------|
| AC1 scope | `contracts/effective_scope.py`, `contracts/ui_scope_action.py`, `core/target_effective_scope.py`, `core/target_ui_scope_action.py`, `core/target_runtime_session.py` | Scope facts + click security |
| AC1 pre-resolver | `orchestration/pre_resolver_turn.py` | Ref-only scope click hydration |
| AC2 selection | `core/target_scope_aware_selection.py`, `core/target_service_applicability.py`, `core/target_strategy_context.py` | Applicability + offers |
| S15/S23/S24 | `core/response_strategy.py`, `core/target_offer_projection.py`, `core/target_brand_offer_projection.py` | Rank + exact offers (via AC2) |
| Pipeline skeleton | `target_turn_frame_dispatch` → `target_policy_bound_verified_response_pipeline` → `target_scoped_response_evidence` → `target_composer_request` → Verifier → `target_runtime_widget` | Atomic cut replaces W1 branch only |
| Materials assembly pattern | `core/target_family_price_overview.py` `assemble_family_price_overview_materials` | Multi-offer package shape |
| Follow-up materializer | `core/target_response_followup_materializer.py` | MD anchors + offer followups |
| Marketing selector | `core/target_marketing_selector.py` | Facts/CTA when stage allows |
| Session write | `write_target_runtime_session_after_materialized` | Followups for next ref validation |

### Primary runtime call site (AC3)

```
core/target_runtime_turn.py
  resolve_effective_scope(...)           # already exists — THREAD downstream
  strategy_match_from_effective_scope()  # replace runtime_strategy stub for price path

core/target_spec_offline_response_package.py::assemble_target_spec_offline_response_package
  run_target_scope_aware_selection(...)  # NEW call — replaces select_family_price_overview_services
  adapter → TargetOfflineResponseMaterials
```

### AC2 result → evidence / Composer path

```
TargetResponsePolicyRequest (+ response_stage)
  → build_target_response_spec → TargetResponseSpec
  → assemble_target_spec_offline_response_package
      AC2 result → materials adapter (NEW)
  → build_target_scoped_response_evidence
      scope-aware spec branch (extend beyond is_family_price_overview_spec)
  → materialize_target_composer_request
  → execute_target_composer → verify
  → target_runtime_widget (quick_replies + cta)
```

### Scope buttons source (AC3 NEW)

| Step | Mechanism |
|------|-----------|
| Emit | When `ResponseStage=broad_family_price` and AC2 `kind=broad_anchors`: materialize 3 `target:ui_scope/{topic}/{extent}` followups |
| Labels | Client-owned extent-keyed config (REWORK W1b label idea; **not** `family_price_groups.yaml` applicability) |
| Consume | Existing AC1 `resolve_ui_scope_ref_click` (session-bound ref) |
| Suppress | When `effective_scope.extent != unknown` OR `kind=scoped_shortlist` OR explicit `service_id` — **no** scope buttons |

### ResponseStage derivation (proposed, AC3 implementation)

| Stage | Deterministic inputs | AC2 `kind` | UI |
|-------|---------------------|------------|-----|
| `broad_family_price` | price intent + topic + `extent=unknown` | `broad_anchors` | scope buttons + brief anchors text |
| `scoped_family_price` | price intent + known extent + no explicit service | `scoped_shortlist` | 2–3 services; no scope buttons |
| `concrete_service_price` | explicit `service_id` or single-service collapse | scoped or S26 path | price followups from offer |
| `prosthetics_stage_clarify` | prosthetics + extent known + required stage unknown | applicability empty / stage gate | stage buttons or clarify (authored only) |
| `data_gap` | AC2 exclusions / missing authored data | any | honest stop; no invented price |

**No persistent `response_stage` session key** when derivable from above.

### Follow-up and marketing (AC3)

| Rule | Source |
|------|--------|
| Scope nav buttons | NEW materializer; refs `target:ui_scope/` |
| Price followups («Что входит», «Оплата») | `offer.followups` via S29/S30 when `followup_source=price` |
| Content followups | MD `suggest_h3` when `followup_source=content` |
| Marketing facts | `target_marketing_selector` when stage allows |
| CTA | ≤1; replaces generic CTA when promo CTA exists (PRICE_SERVICE §18) |
| Slot budget | ≤2 thematic follow-ups + 1 CTA; no mixing nav+price+CTA overload |

### Why scale menu disappears after scoped answer

1. Click → AC1 writes `patient_facts.extent` for topic.
2. Next turn: `resolve_effective_scope` → known extent (not `unknown`).
3. AC2 → `kind=scoped_shortlist` (not `broad_anchors`).
4. `ResponseStage=scoped_family_price` → emitter **skips** `build_ui_scope_ref` buttons.
5. Only offer/MD followups shown; never repeat current extent button.

### W1 / W1b classification

| Verdict | Item |
|---------|------|
| **REUSE** | AC1 + AC2 stacks; pipeline skeleton; multi-offer materials pattern; two-phase nav concept |
| **REWORK** | W1b situation menu labels → extent-keyed client config + `target:ui_scope/` refs |
| **MODIFY** | `target_spec_offline_response_package.py`, `target_runtime_turn.py`, dispatch, evidence, composer, widget |
| **DEMOTE** | `select_family_price_overview_services` — remove from product path; keep helper/tests until AC3 cutover |
| **REJECT** | W1b patch restore; `family_price_groups.yaml` authority; `target:family_price_group/` refs; regex scope parsing; A9 read |

### Implantation + prosthetics coverage

| Topic | AC2 offline matrix | AC3 runtime expectation |
|-------|-------------------|------------------------|
| Implantation | unknown→anchors; one_tooth/few_teeth/full_arch scoped; explicit all_on_4 pin | Same via unified pipeline |
| Prosthetics | stage-gated services; partial/full dentures by extent | Same pipeline; stage clarify when catalog requires unknown stage |
| Data gap | typed exclusions | `data_gap` stage; STOP until client pack fix |

---

## Proposed AC3 runtime flow

```text
/ask | /ask/stream
  → pre_resolver_turn (ui_scope ref? → AC1 click)
  → target_runtime_turn
      effective_scope = resolve_effective_scope(...)
      strategy_context = strategy_match_from_effective_scope(effective_scope, stage?, jaw?, ...)
      response_stage = derive_response_stage(turn_frame, effective_scope, ...)  # NEW
  → dispatch_target_turn_frame_response
      price + no service_id → scope-aware spec (not W1 family_price_overview_topic alone)
  → assemble_target_spec_offline_response_package
      selection = run_target_scope_aware_selection(...)
      materials = adapt_ac2_to_materials(selection)
      followups += materialize_ui_scope_buttons(...)  # only broad_family_price
  → evidence → composer → verifier → widget
      quick_replies: scope | price | content (deduped, session-bound)
      cta: ≤1
  → write_target_runtime_session_after_materialized
```

---

## Forbidden (AC3)

- Live/LLM; A9 harness/authority; `TurnFrame.patient_scope` product read
- W1b restore; `family_price_groups` as applicability
- Regex/phrase routing for «один зуб» / «вся челюсть» in free text
- Temporary scope parser or synonym dictionaries
- Second selector parallel to AC2
- Per-topic implantation-only routes (prosthetics must share mechanism)
- Hardcoded demo service IDs / Russian labels in shared core
- Files outside allowlist
- Changing W1b artifact bytes
- Protected acceptance / golden / live harness edits to green-wash

## Allowlist

### Governance commit (this checkpoint only)

| File |
|------|
| `TASK.md` |
| `docs/ARCHITECTURE_CONVERGENCE.md` |
| `docs/PRICE_SERVICE_ARCHITECTURE.md` |
| `docs/STRANGLER_ROADMAP.md` |
| `docs/ARCH_TARGET_DESIGN.md` |

### New (AC3 implementation only — tentative, owner may narrow at PRE-CODE)

| File | Purpose |
|------|---------|
| `contracts/target_response_stage.py` | `ResponseStage` enum + derivation contract |
| `core/target_response_stage.py` | `derive_response_stage(...)` pure function |
| `core/target_scope_nav_materializer.py` | Emit `target:ui_scope/` followups from client labels |
| `core/target_scope_aware_materials.py` | AC2 result → `TargetOfflineResponseMaterials` adapter |
| `tests/test_target_response_stage.py` | Stage derivation unit tests |
| `tests/test_target_scope_nav_materializer.py` | Scope button materializer tests |
| `tests/test_ac3_scope_price_flow_offline.py` | End-to-end offline matrix (below) |
| `tests/test_ac3_scope_price_flow_http_offline.py` | `/ask` + `/ask/stream` parity |

Client pack (if needed for scope labels only):

| File | Condition |
|------|-----------|
| `clients/demo/target_response/scope_nav.yaml` | Extent-keyed labels; not applicability |

### Modify (AC3 implementation only — tentative)

| File | Change |
|------|--------|
| `core/target_runtime_turn.py` | Thread `effective_scope`; scope-aware strategy |
| `core/target_turn_frame_dispatch.py` | Scope-aware price dispatch + `response_stage` |
| `core/target_spec_offline_response_package.py` | AC2 call; retire W1 selector in product path |
| `core/target_policy_bound_verified_response_pipeline.py` | Stage-aware marketing/CTA guards |
| `core/target_scoped_response_evidence.py` | Scope-aware evidence branch |
| `core/target_composer_request.py` | Scope-aware composer sources |
| `core/target_runtime_widget.py` | Scope + follow-up merge; attribution |
| `contracts/target_response_spec.py` | `response_stage` field (or replace `family_price_overview_topic`) |
| `contracts/target_response_policy.py` | Policy request fields for stage |
| `core/target_family_price_overview.py` | Demote selector; keep materials helper |

### Explicitly forbidden in AC3 implementation

| Area |
|------|
| `core/target_scope_aware_selection.py` logic changes (unless AC2 bugfix with owner OK) |
| A9 modules; `TurnFrame.patient_scope` product read |
| `docs/artifacts/w1b_wip_checkpoint_2026-07-24/**` |
| Protected acceptance / golden / live harnesses |

---

## Acceptance (AC3 implementation)

### A. Runtime wiring

1. `effective_scope` reaches AC2 call; not discarded.
2. W1 `select_family_price_overview_services` **not** used in product price path.
3. `/ask` and `/ask/stream` produce identical scope/price semantics for same inputs.

### B. Broad price question

4. Unknown extent + price intent → brief anchor overview + scope buttons (3 extents).
5. No payment stages or long descriptions in broad answer.
6. Anchors from AC2 `broad_anchors` only; prices verbatim from pricebook.

### C. Scope click

7. Ref click → `UiScopeAction` → session → scoped materialized answer (not defer).
8. Planner does not re-parse button label for extent.

### D. Scoped / concrete

9. Known extent → no scope buttons repeated.
10. ≤2 thematic follow-ups + ≤1 CTA; no duplicate-of-selected button.
11. Price followups only when offer/MD structured data exists.

### E. ResponseStage

12. Stage derived deterministically; no redundant session persistence.
13. Stage controls answer shape/follow-ups; does not select services.

### F. Prosthetics parity

14. Same pipeline for `prosthetics` topic.
15. Missing authored stage/data → `data_gap` honest stop (no temp parser).

### G. Integrity / firewalls

16. No hardcoded demo service IDs in shared core.
17. W1b checksums byte-identical.
18. AC1 + AC2 offline tests unchanged and green.
19. A9 product firewall unchanged.
20. No regex free-text scope parsing added.

---

## Offline test matrix (AC3 implementation)

Implement in `tests/test_ac3_scope_price_flow_offline.py` + HTTP parity test.

| # | Flow | Assert |
|---|------|--------|
| 1 | Broad implantation price question | `broad_family_price`; anchors; 3 scope buttons; no payment stages |
| 2 | Click «Один зуб» | scoped answer; `classic` or applicable; no scope buttons |
| 3 | Click «Вся челюсть» | scoped; all_on_4/6 eligible; no scope buttons |
| 4 | Broad prosthetics price question | same mechanism; prosthetics services |
| 5 | Prosthetics one_tooth + stage clarify | stage buttons or clarify when required; then scoped |
| 6 | Named service (all_on_4) | concrete path; S26 not broken |
| 7 | Finance follow-up click | «Оплата»/payment content from structured source |
| 8 | `/ask` vs `/ask/stream` click | same effective_scope + same offers |
| 9 | Unshown ui_scope ref | fail-closed (AC1 security preserved) |
| 10 | Topic change | session cleared; scope buttons return on new broad price |
| 11 | Marketing on broad answer | per PRICE_SERVICE; ≤1 CTA |
| 12 | Data gap prosthetics | typed stop when catalog incomplete |

---

## Tests (focused, AC3 implementation)

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-ac3-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_ac3_scope_price_flow_offline.py `
  tests/test_ac3_scope_price_flow_http_offline.py `
  tests/test_target_response_stage.py `
  tests/test_target_scope_nav_materializer.py `
  -q
```

### Relevant neighbors (must stay green)

```powershell
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_effective_scope_contract.py `
  tests/test_ui_scope_action_contract.py `
  tests/test_session_patient_facts_offline.py `
  tests/test_ui_scope_click_http_offline.py `
  tests/test_target_scope_aware_selection_offline.py `
  tests/test_target_strategy_context.py `
  tests/test_target_service_applicability.py `
  tests/test_target_turn_frame_dispatch.py `
  tests/test_demo_target_offline_response_assembly.py `
  -q
```

## STOP conditions

1. AC3 requires A9 authority or free-text scope parser
2. Requires W1b restore or `family_price_groups` applicability
3. Requires second selector duplicating AC2
4. Requires changing protected acceptance/golden/live harness expectations
5. Prosthetics data-gap needs client pack change **and** no owner approval for data fix path
6. PRE-CODE or COMPLETION checker ❌ without fix path

## Open questions (owner decisions before / during implementation)

1. **Spec shape:** add `response_stage` to `TargetResponseSpec` vs retire `family_price_overview_topic` flag?
2. **Scope labels config path:** new `scope_nav.yaml` vs extend existing client pack file?
3. **Prosthetics stage UI:** typed stage refs (`target:ui_stage/...`) vs text clarify only in AC3?
4. **Marketing on broad answer:** re-enable per PRICE_SERVICE rule 1 — confirm CTA slot with 3 scope buttons?
5. **Single-service collapse:** keep when scoped shortlist has exactly one service?
6. **Feature flag:** atomic cutover vs `TARGET_SCOPE_AWARE_PRICE=1` default OFF?

## Completion record

| Field | Value |
|-------|-------|
| AC2 product HEAD | `5a3a2f8` |
| W1b artifact | `docs/artifacts/w1b_wip_checkpoint_2026-07-24/` |
| Governance baseline | `57f9067` |
| AC3 governance HEAD | |
| PRE-CODE | |
| COMPLETION | |
| AC3 product HEAD | |

**STOP after governance PRE-CODE ✅. AC3 implementation starts only after separate owner GO.**
