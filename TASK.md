# TASK — W1b Family price situation menu + grouped drill-down

**Baseline:** `codex/stage-a` / `73de39a` (W1 COMPLETE) · **NO LIVE / NO LLM / NO A9 changes**

**Authority:** Owner decision (2026-07-24) — situation buttons for vague family price questions.

## Goal

Extend W1 family price overview with a **two-phase** patient-friendly flow:

1. **Situation menu (first screen):** vague topic price question (`topic` + price + `service_id=null`) → **compact** price overview + **client-owned situation buttons** (not protocol names).
2. **Group drill-down (second screen):** after button click → prices **only** for services in the selected group; topic continuity preserved.

**Owner example (implantation):**

Patient: «Сколько стоит имплантация?»

First response: short overview (2–4 price anchors max) + buttons:
- Один зуб
- Несколько зубов
- Вся челюсть

**Must NOT** show on first screen: Классическая имплантация, Одномоментная, All-on-4, All-on-6.

After group selection → show only that group's services and prices.

**Unchanged architecture:**

```text
HTTP → guards → Planner LLM → TurnFrame → session hydration
→ medical boundary → FullContext → Composer → Verifier → widget/session
```

Group selection is **structured client data + target navigation**, not RAG/per-MD routing.

## Process (mandatory)

1. **Verify baseline:** clean tree; `HEAD == origin/codex/stage-a` @ `73de39a`.
2. **Read:** `TASK.md`, `docs/ARCH_TARGET_DESIGN.md`, `REVIEW_CHECKLIST.md`, `.cursor/rules/00-guardrails.mdc`.
3. **Read-only seam audit** (below).
4. **Governance commit:** only `TASK.md` → push → **PRE-CODE checker ✅**
5. If PRE-CODE ❌: STOP, fix only `TASK.md`, repeat PRE-CODE until ✅.
6. **W1b implementation** → focused + neighbor + wide offline → frozen pins → **COMPLETION checker ✅** → commit + push → clean/synced → **STOP**.

No product WIP before PRE-CODE ✅.

## Forbidden

- Live/LLM runs; A9 matrix/harness rerun; frozen A9 artifact edits
- Hardcode in shared `core/`: `implantation`, `all_on_4`, `all_on_6`, clinic button labels, demo service_ids
- RAG/per-MD routing; legacy chunk navigation for group buttons
- `meta.followups` restoration; duplicate quick_reply channels
- Payment stages / marketing / CTA / doctors in **situation menu** phase
- Changing existing pricebook amounts or offer IDs
- Weakening Verifier or numeric grounding; ослабление acceptance tests
- Files outside allowlist without governance correction + PRE-CODE ✅
- Writing `prosthetics` groups to client data **without owner sign-off** on table below (§ Prosthetics owner checkpoint)
- Inventing prosthetics service→group mapping when ambiguous

## Allowed

- Governance `TASK.md`; PRE-CODE / COMPLETION checkers (read-only)
- Product code + offline tests per allowlist
- **New client-owned config** in `clients/demo/target_response/` (groups YAML/JSON + loader); **no price amount edits**
- Synthetic non-demo fixtures in tests
- Push only to `origin/codex/stage-a`

---

## Read-only seam audit (baseline `73de39a`)

### W1 current behavior (gap vs owner decision)

| Seam | File | Finding |
|------|------|---------|
| Family selection | `core/target_family_price_overview.py` | Selects up to 4 **protocol-named** services by `content_ref` topic prefix + role rank. Shows classic/one_stage/all_on_4 on first screen — **violates** owner UX. |
| Follow-ups v1 | `assemble_family_price_overview_package` | `followup_source=None`; **no situation buttons**. |
| Spec gate | `is_family_price_overview_spec` | Requires `followup_source is None` — must extend for menu phase. |
| Dispatch | `core/target_turn_frame_dispatch.py` | `_materialize_family_price_overview_policy_request` — single phase only. |
| Navigation | `core/target_runtime_followup_nav.py` | Ref → label text; session stores `quick_replies` refs. No structured group ref parsing. |
| Session | `core/target_runtime_session.py` | Stores followups; no `family_price_group` continuity field yet. |
| Hydration | `core/target_runtime_turn_frame_hydration.py` | Restores `service_id` for vague attribute follow-ups only — not group selection. |
| Evidence | `core/target_composer_request.py` `_family_overview_sources` | Full offer JSON incl. `payment_stages`, `package` — too heavy for compact menu. |
| Exact path | `service_id` + price aspects | Unchanged; All-on-4 exact + payment questions must stay on single-service path. |
| Widget | `core/target_runtime_widget.py` | Single `quick_replies` channel ✅ (W1). `ui_source_family` for family overview uses `price_navigation`. |
| Membership | `contracts/target_service_content_topic.py` | Topic from `content_ref` prefix — reuse for validating group `service_ids` belong to topic. |

**Root cause:** W1 v1 optimized for multi-protocol evidence, not patient situation grouping.

### Proposed mechanism (W1b)

```text
Phase A — situation menu
  price + usable topic + service_id=null + no group ref in session/nav
  → load client topic groups from family_price_groups config
  → build COMPACT price hints (group-level anchors, max 2–4 lines total)
  → emit situation quick_replies with opaque target refs
  → Composer + Verifier on compact evidence only

Phase B — group drill-down
  nav ref target:family_price_group/{topic}/{group_id} OR session-hydrated group
  → validate group exists for topic; service_ids ⊆ catalog; priced offers exist
  → multi-service price overview LIMITED to group service_ids (W1 assembly reuse)
  → no situation buttons on drill-down (or only if config allows — v1: none)

Exact service question (service_id set) → unchanged single-service path
Payment/stages question on known service → unchanged
```

### Client-owned groups config (chosen after audit)

**File:** `clients/{client}/target_response/family_price_groups.yaml`

Loaded into `ResponseSchemaBundle` via `core/response_schema_loader.py` (same pack, no parallel data layer).

```yaml
version: 1
topics:
  implantation:
    groups:
      - id: one_tooth
        label: Один зуб
        service_ids: [classic, one_stage]
      - id: several_teeth
        label: Несколько зубов
        service_ids: [classic, one_stage]
      - id: full_jaw
        label: Вся челюсть
        service_ids: [all_on_4, all_on_6, zygomatic_implants]
  # prosthetics: see § Prosthetics owner checkpoint — not written until sign-off
```

**Validation rules (contract):**
- Each `group.id` unique per topic; `label` non-blank (client-owned text).
- Each `service_id` exists in `service_catalog.json`, `active`, and `content_ref` topic prefix matches topic.
- Groups may share a service_id across situations (explicit in data).
- Services not in any group are excluded from family flows (not auto-inferred).
- Loader fail-closed on unknown service_id or topic/group shape errors.

**Excluded from implantation groups (adjunct / not patient situation bucket):** `sinus_lift`, `pterygoid_implants`, `temporary_teeth`, `tomography` — not in owner menu; remain reachable via exact/context paths only.

### Target navigation ref contract

```text
target:family_price_group/{topic}/{group_id}
```

- Emitted only in situation menu `quick_replies`.
- Session-bound via existing `target_runtime_followups` storage.
- On ref click (`ref` set, `q` empty): parse ref **before** planner; hydrate TurnFrame/dispatch with `family_price_group_id` + `family_price_overview_topic`; **do not** use MD chunk refs.
- Unknown ref → existing plain `target_fullcontext_followup_unknown` path.
- Dedup by `ref` (W1 widget contract preserved).

### Compact first-screen evidence (owner compactness)

**Forbidden in menu-phase evidence/response:** payment_stages, package breakdown, installment, tax deduction, warranty/contract promos, consultation promos/deadlines, doctors, long medical copy, booking CTA.

**Allowed:** one short intro; max 2–4 brief price anchors derived from **group-level** structured projection (min fixed / proven min-from / range per group); one clarifying sentence; situation buttons.

**Price semantics:** use «от» only when value is proven minimum among allowed variants in that anchor; fixed offer → name + exact price; multiple variants → short range or 2–4 lines. All amounts from pricebook only.

**Verifier:** no new medical regex/blocklists. Existing numeric grounding + semantic backend; menu-phase evidence must not include fields that would permit forbidden commercial details (strip `payment_stages` from menu offer projection). Optional typed check: menu spec forbids `payment` aspect components.

### Spec / policy extensions

Add to `TargetResponsePolicyRequest` / `TargetResponseSpec` (frozen-shape tests updated):

| Field | Menu phase | Drill-down phase |
|-------|------------|------------------|
| `family_price_overview_topic` | set | set |
| `family_price_group_id` | `null` | set |
| `followup_source` | `"family_price_group"` (new enum value) | `null` |
| `required_components` | `("price",)` | `("price",)` |

`is_family_price_overview_spec` splits into:
- `is_family_price_situation_menu_spec` — topic set, group null, followup_source family_price_group
- `is_family_price_group_overview_spec` — topic + group set, followup_source null

Exact `service_id` path unchanged.

---

## Demo implantation mapping (owner-approved)

| Group | Label | service_ids |
|-------|-------|-------------|
| `one_tooth` | Один зуб | `classic`, `one_stage` |
| `several_teeth` | Несколько зубов | `classic`, `one_stage` |
| `full_jaw` | Вся челюсть | `all_on_4`, `all_on_6`, `zygomatic_implants` |

---

## Prosthetics owner checkpoint (STOP before client write)

Acceptance test #7 requires prosthetics groups. **Do not commit `family_price_groups.yaml` prosthetics section until owner signs one row below.**

| service_id | name | selection notes |
|------------|------|-----------------|
| `zirconia_crowns` | Коронки из диоксида циркония | extent: one_tooth, few_teeth |
| `clasp_dentures` | Бюгельные протезы | extent: few_teeth |
| `removable_dentures` | Съёмное протезирование | extent: few_teeth, full_arch; options partial/full |
| `implant_supported_prosthetics` | Протезирование на имплантах | extent: one_tooth, few_teeth, full_arch |
| `veneers` | Виниры E-max | context only, no extent — **ambiguous** |

**Proposed draft (NOT approved — executor STOP if implementing without owner OK):**

| Group id | Label | Proposed service_ids | Ambiguity |
|----------|-------|----------------------|-----------|
| `one_tooth` | Один зуб | `zirconia_crowns` | veneers omitted — confirm |
| `several_teeth` | Несколько зубов | `zirconia_crowns`, `clasp_dentures`, `removable_dentures` | removable spans full/partial |
| `full_jaw` | Вся челюсть | `implant_supported_prosthetics`, `removable_dentures` | implant_supported also lists one_tooth/few_teeth |

**Executor rule:** at prosthetics checkpoint, if owner has not approved table → **СТОП** with this table in report; implantation-only delivery still allowed if tests 1–6 + 8–9 green and test 7 explicitly skipped with documented owner pending (not `xfail` — split test or conditional only with TASK amendment).

---

## Workstreams

### A — Client groups config + loader

- `family_price_groups.yaml` schema contract + loader integration in `ResponseSchemaBundle`
- Validators: topic/service membership via `content_ref` prefix

### B — Situation menu phase

- Dispatch: menu vs drill-down vs exact service
- Compact evidence builder (group anchors, no payment_stages)
- Situation follow-ups with `target:family_price_group/...` refs
- `followup_source: family_price_group`

### C — Group drill-down phase

- Nav/session hydration from structured ref
- Reuse W1 multi-offer assembly filtered by group `service_ids`
- Cap services per group (reuse `FAMILY_PRICE_OVERVIEW_MAX_SERVICES` or per-group limit = all priced in group)

### D — Widget / session / attribution

- Single `quick_replies` channel; dedup preserved
- `ui_source_family` appropriate for menu (`price_navigation` or new `family_price_navigation` if policy requires — prefer existing families)
- Terminal/error: `attribution_kind: plain` (W1 contract preserved)

### E — Verifier compactness

- Menu-phase evidence shape excludes commercial detail fields
- Numeric grounding unchanged; no new regex blocklists

---

## W1b allowlist (implementation)

### New files

| File |
|------|
| `contracts/target_family_price_groups.py` |
| `clients/demo/target_response/family_price_groups.yaml` (implantation only until prosthetics sign-off) |
| `tests/test_w1b_family_price_situation_menu_offline.py` |
| `tests/test_w1b_family_price_group_drilldown_offline.py` |

### Modify

| File |
|------|
| `contracts/response_schema.py` |
| `core/response_schema_loader.py` |
| `contracts/target_response_spec.py` |
| `contracts/target_response_policy.py` |
| `core/target_response_policy.py` |
| `core/target_family_price_overview.py` |
| `core/target_turn_frame_dispatch.py` |
| `core/target_spec_offline_response_package.py` |
| `core/target_composer_request.py` |
| `core/target_scoped_response_evidence.py` |
| `core/target_policy_bound_verified_response_pipeline.py` |
| `core/target_runtime_followup_nav.py` |
| `core/target_runtime_turn_frame_hydration.py` |
| `core/target_runtime_session.py` |
| `core/target_runtime_widget.py` |
| `orchestration/pre_resolver_turn.py` (only if nav_ref must pass to runtime — prefer ctx already set) |
| `tests/test_w1_family_price_overview_offline.py` (behavior update for two-phase) |
| `tests/test_w1_widget_followup_contract_offline.py` |
| `tests/test_target_turn_frame_dispatch.py` |
| `tests/test_target_response_spec.py` |
| `tests/test_target_response_policy.py` |
| `tests/test_demo_target_turn_frame_bound_response.py` |
| `tests/test_vague_price_followup.py` |
| `tests/test_demo_target_price_offers.py` |
| `tests/test_s61_correction_target_runtime.py` |
| `tests/test_s62_correction_offline.py` |
| `tests/test_s63_correction_offline.py` |
| `tests/test_w1_attribution_contract_offline.py` |
| `tests/test_response_schema_loader.py` |
| `tests/test_c2_import_firewall_offline.py` (if new public surface) |

### Explicit KEEP

- `clients/demo/target_response/pricebook/**` amounts and offer IDs
- Frozen S47/S50/S53/S55/S58/S62/S63/S66 artifacts (byte-identical)
- Exact All-on-4 payment/stages path
- W1 widget single-channel + plain terminal attribution

---

## Acceptance tests (offline, mandatory)

1. «Сколько стоит имплантация?» → materialized; compact answer; **no** payment stages/installment/tax promo/consultation promo; buttons exactly «Один зуб», «Несколько зубов», «Вся челюсть»; no duplicates; **no** protocol names as buttons.
2. Select «Один зуб» → only one-tooth services/prices; no All-on-4/6.
3. Select «Вся челюсть» → All-on-4/6 (+ zygomatic if priced) when in group; no one-tooth protocols.
4. Select «Несколько зубов» → only configured services; honest short answer if none priced.
5. «Сколько стоит All-on-4?» → exact service path; **no** situation menu.
6. «Как оплатить All-on-4?» / payment stages → unchanged.
7. Prosthetics family overview → **owner sign-off required** (§ checkpoint); own groups; no implantation buttons.
8. Terminal/error → plain attribution.
9. Frozen artifacts byte-identical.

---

## STOP conditions

1. Prosthetics grouping ambiguous and owner has not signed proposed table
2. Honest group price anchor impossible without inventing amounts
3. Implementation requires per-MD routing or RAG
4. Verifier weakening or frozen artifact change required
5. Scope beyond allowlist without governance correction

---

## Tests (mandatory commands)

### Focused W1b

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-w1b-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_w1b_family_price_situation_menu_offline.py `
  tests/test_w1b_family_price_group_drilldown_offline.py `
  tests/test_w1_family_price_overview_offline.py `
  tests/test_w1_widget_followup_contract_offline.py `
  tests/test_w1_attribution_contract_offline.py `
  tests/test_target_turn_frame_dispatch.py `
  -q
```

### Neighbors

```powershell
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_demo_target_turn_frame_bound_response.py `
  tests/test_vague_price_followup.py `
  tests/test_demo_target_price_offers.py `
  tests/test_s61_correction_target_runtime.py `
  tests/test_s62_correction_offline.py `
  tests/test_s63_correction_offline.py `
  tests/test_response_schema_loader.py `
  -q
```

### Wide safe-offline + integrity

Same ignores as W1 (`TASK.md` W1 wide block). Frozen pin script unchanged.

---

## Commits (minimum)

1. `W1b governance TASK` (this commit)
2. `W1b: family price situation menu + group drill-down` (after COMPLETION ✅)

---

## Completion record (fill after COMPLETION ✅)

| Field | Value |
|-------|-------|
| PRE-CODE | |
| Baseline | `73de39a` |
| COMPLETION checker | |
| Prosthetics owner sign-off | pending |
| HEAD | |
| NO LIVE / NO LLM / NO A9 | |

**STOP after W1b COMPLETION.**
