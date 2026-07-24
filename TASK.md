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
- Inventing offer/group mapping not in client config
- Mixing implantation services (`all_on_4`, `all_on_6`, etc.) into `prosthetics` topic groups

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
| **Follow-up forbid** | `contracts/target_response_spec.py:101-107` | `family_price_overview_followups_forbidden` if `followup_source is not None` — **blocks menu phase**; must relax for menu-only. |
| **Follow-up policy clamp** | `core/target_response_policy.py:18-20` | `_followup_source` returns `None` whenever `family_price_overview_topic` set — **blocks menu**; must branch on menu vs drill-down. |
| **S29/S30 scope** | `core/target_response_followup_materializer.py`, `core/target_response_followup_policy.py` | Materializer builds **content/price** from MD/offers only (`_SOURCES = content|price`). Client-owned group buttons are **not** MD/offer follow-ups — **do not route menu buttons through S29/S30**. |
| **Widget merge** | `core/target_runtime_widget.py:100-110` | `_followups_to_quick_replies(content, price)` only — must accept third tuple `group` for menu phase. |
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
  → validate group exists for topic
  → resolve each group **entry** to exactly one priced offer (pinned `offer_id` or representative projection for `service_id`-only entries)
  → drill-down evidence includes **only** those offers — never sibling offers of the same service
  → no situation buttons on drill-down (v1: none)

Exact service question (service_id set) → unchanged single-service path
Payment/stages question on known service → unchanged
```

### Architecture decision: situation follow-ups bypass S29/S30

**Chosen mechanism (fixed in governance — not executor choice):**

Situation menu buttons are **client-configured navigation**, not MD-derived content follow-ups nor pricebook offer follow-ups. Therefore:

1. **Do NOT** call `materialize_target_response_followups` / `select_target_response_followups` for menu phase.
2. Build group buttons directly from `family_price_groups.yaml` in `core/target_family_price_overview.py` (`build_family_price_situation_followups`) → typed `TargetFamilyPriceGroupFollowup` (ref `target:family_price_group/{topic}/{group_id}`, label from config).
3. Extend `TargetResponseFollowupSelection` with `group: tuple[TargetFamilyPriceGroupFollowup, ...]` (`core/target_response_followup_policy.py` + contract type). S29 materializer **unchanged**.
4. Widget `_followups_to_quick_replies` renders `content` + `price` + `group` in deterministic order (menu phase: **only** `group` populated).
5. Session stores emitted group refs like existing price/content refs.

**Spec/policy relaxations (menu phase only):**

| Rule | Menu (`group_id=null`) | Drill-down (`group_id` set) |
|------|------------------------|-----------------------------|
| `family_price_overview_followups_forbidden` | **Removed** when `followup_source=="family_price_group"` | Still enforced (`followup_source` must be `null`) |
| `followup_source not in required_components` | **Exception** for `family_price_group` | N/A |
| `_followup_source()` | Returns `"family_price_group"` | Returns `None` |

`TargetFollowupSource` extended: `Literal["content", "price", "family_price_group"]`.

Drill-down reuses W1 multi-offer assembly filtered by group **entries** (explicit `offer_id` list and/or `service_id`-only representative rows) with `followup_source=None` (no situation buttons).

### Client-owned groups config (chosen after audit)

**Governance correction (2026-07-24):** group membership is **offer-aware**. `service_id`-only lists are insufficient when one service has multiple offers that belong to different patient situations (e.g. `removable_dentures.jaw.partial` vs `removable_dentures.jaw.full`).

**File:** `clients/{client}/target_response/family_price_groups.yaml`

Loaded into `ResponseSchemaBundle` via `core/response_schema_loader.py` (same pack, no parallel data layer).

**Minimal typed entry model** (`FamilyPriceGroupEntry` in `contracts/target_family_price_groups.py`):

| Field | Required | Semantics |
|-------|----------|-----------|
| `offer_id` | preferred | Pin **one** pricebook offer. Drill-down uses exactly this offer. |
| `service_id` | optional cross-check | If present with `offer_id`, must equal `bundle.offers[offer_id].service_id` — else loader **fail-closed**. |
| `option_id` | optional | If present with `offer_id`, must equal offer's `option_id` when set on the offer record — else **fail-closed**. Reserved for future option-scoped pins; demo prosthetics uses distinct `offer_id` files instead. |

**Resolution rule (runtime, deterministic):**

1. If `offer_id` set → load that offer from pricebook bundle; reject if missing, inactive, or `service_id` mismatch.
2. Else if `service_id` set (no `offer_id`) → use existing W1 `_representative_offer` projection for that service (implantation shorthand only).
3. Else → loader **fail-closed** (`family_price_group_entry_invalid`).

**Topic guard:** resolved `service_id` must be `active` and `content_ref` topic prefix must match the group's topic.

**Same `service_id`, different offers across groups:** allowed and expected — e.g. `removable_dentures` partial in `several_teeth`, full in `full_jaw`; groups never auto-expand to all offers of a service.

```yaml
version: 1
topics:
  implantation:
    groups:
      - id: one_tooth
        label: Один зуб
        entries:
          - service_id: classic
          - service_id: one_stage
      - id: several_teeth
        label: Несколько зубов
        entries:
          - service_id: classic
          - service_id: one_stage
      - id: full_jaw
        label: Вся челюсть
        entries:
          - service_id: all_on_4
          - service_id: all_on_6
          - service_id: zygomatic_implants
  prosthetics:
    groups:
      - id: one_tooth
        label: Один зуб
        entries:
          - offer_id: zirconia_crowns.default
          - offer_id: implant_supported_prosthetics.default
      - id: several_teeth
        label: Несколько зубов
        entries:
          - offer_id: zirconia_crowns.default
          - offer_id: implant_supported_prosthetics.default
          - offer_id: clasp_dentures.default
          - offer_id: removable_dentures.jaw.partial
      - id: full_jaw
        label: Вся челюсть
        entries:
          - offer_id: removable_dentures.jaw.full
```

**Validation rules (contract):**
- Each `group.id` unique per topic; `label` non-blank (client-owned text).
- Each group has ≥1 `entries` row; no duplicate `offer_id` within a group.
- Pinned `offer_id` must exist in loaded pricebook and belong to the topic via service `content_ref`.
- Unknown `offer_id`, wrong `service_id` cross-check, or wrong `option_id` → loader **fail-closed** (no silent drop).
- Services/offers not listed in any group are excluded from family flows (not auto-inferred).
- **`veneers` excluded** from `prosthetics` family overview — exact veneers questions use normal single-service path.

**Excluded from implantation groups (adjunct / not patient situation bucket):** `sinus_lift`, `pterygoid_implants`, `temporary_teeth`, `tomography` — remain reachable via exact/context paths only.

**Excluded from prosthetics family overview:** `veneers` (separate aesthetic service); all `implantation` topic services including `all_on_4` / `all_on_6`.

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

| Group | Label | entries (`service_id` → representative offer) |
|-------|-------|-----------------------------------------------|
| `one_tooth` | Один зуб | `classic`, `one_stage` |
| `several_teeth` | Несколько зубов | `classic`, `one_stage` |
| `full_jaw` | Вся челюсть | `all_on_4`, `all_on_6`, `zygomatic_implants` |

Implantation uses `service_id`-only entries (W1 representative projection). Drill-down must not pull sibling brand offers beyond the projected representative per service.

---

## Demo prosthetics mapping (owner-approved 2026-07-24)

Menu labels (same patient-facing trio as implantation — client-owned, not hardcoded in core):

| Group | Label | Pinned `offer_id` entries |
|-------|-------|---------------------------|
| `one_tooth` | Один зуб | `zirconia_crowns.default`, `implant_supported_prosthetics.default` |
| `several_teeth` | Несколько зубов | `zirconia_crowns.default`, `implant_supported_prosthetics.default`, `clasp_dentures.default`, `removable_dentures.jaw.partial` |
| `full_jaw` | Вся челюсть | `removable_dentures.jaw.full` |

**Owner exclusions:** `veneers` not in prosthetics family overview. `all_on_4` / `all_on_6` never in `prosthetics` topic. Exact per-service / per-offer questions unchanged.

**Regression guard:** `several_teeth` must **not** surface `removable_dentures.jaw.full`; `full_jaw` must **not** surface partial/pinned one-tooth offers from other groups.

---

## Workstreams

### A — Client groups config + loader

- `family_price_groups.yaml` schema contract + loader integration in `ResponseSchemaBundle`
- Typed `FamilyPriceGroupEntry` (`offer_id` pin / `service_id` representative shorthand)
- Validators: topic membership via `content_ref`; offer_id fail-closed cross-checks

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
| `contracts/target_family_price_group_followup.py` (typed group button + ref builder) |
| `clients/demo/target_response/family_price_groups.yaml` (implantation + prosthetics per § demo mappings) |
| `tests/test_w1b_family_price_situation_menu_offline.py` |
| `tests/test_w1b_family_price_group_drilldown_offline.py` |

### Modify

| File |
|------|
| `contracts/response_schema.py` |
| `core/response_schema_loader.py` |
| `contracts/target_response_spec.py` |
| `contracts/target_response_policy.py` |
| `core/target_response_followup_policy.py` (extend `TargetResponseFollowupSelection.group` only; S30 selector unchanged) |
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
| `tests/test_target_response_followup_policy.py` (frozen shape: `group` field on Selection) |
| `tests/test_demo_target_response_followup_policy.py` (if Selection shape asserted) |

### Explicit KEEP (do not change)

- `core/target_response_followup_materializer.py` (S29 — MD/offer follow-ups only; menu buttons bypass this path)
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
7. «Сколько стоит протезирование?» → situation menu (3 labels); **no** implantation buttons; **no** veneers; drill-down «Несколько зубов» includes `removable_dentures.jaw.partial` only (not `.jaw.full`); «Вся челюсть» includes `removable_dentures.jaw.full` only (not partial / not one-tooth pinned offers).
8. Terminal/error → plain attribution.
9. Frozen artifacts byte-identical.

---

## STOP conditions

1. Honest group price anchor impossible without inventing amounts
2. Implementation requires per-MD routing or RAG
3. Verifier weakening or frozen artifact change required
4. Scope beyond allowlist without governance correction
5. Drill-down would auto-include sibling offers not listed in group `entries`

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
| Prosthetics owner sign-off | ✅ (offer-pinned mapping 2026-07-24) |
| HEAD | |
| NO LIVE / NO LLM / NO A9 | |

**STOP after W1b COMPLETION.**
