# FINAL_PROSTHETICS_PRICE_NAV_REACHABILITY — seam audit (read-only)

**Date:** 2026-07-26  
**Baseline:** `2b5e90d` (`codex/stage-a`) · **FINAL_PRICE_SCOPE_COVERAGE_NAV complete**  
**Scope:** Phase 1 governance only · **NO IMPLEMENTATION / NO LIVE / NO LLM**

**Canonical law:** `docs/PRICE_SERVICE_ARCHITECTURE.md` (rules 24–26, 61–62 stage clarification).

---

## Verdict

Prosthetics `one_tooth` is **incorrectly hidden** from broad scope-nav because **FINAL_PRICE_SCOPE_COVERAGE_NAV** equates **immediate AC2 anchor success** with **navigable price coverage**. Crown prices for `one_tooth` exist only after **one governed `UiStageAction`** (`natural_tooth_present` → 25 000 ₽; `implant_placed` → 31 000 ₽). The fix is a **deterministic one-stage reachability helper** over existing AC2 + `discover_stage_clarification_stages()` — **no new selector, no LLM, no regex, no new medical axis**.

---

## 1. Why `one_tooth` is hidden today

**Repro @ `2b5e90d`:**

```
run_target_scope_aware_selection(topic='prosthetics', extent=unknown)
→ anchors: full_arch (65k), few_teeth (45k partial)
→ price_confirmed_extents: ('full_arch', 'few_teeth')
→ exclusions: ('no_anchor_applicable:one_tooth',)
```

**Root cause chain:**

| Step | Behavior |
|------|----------|
| AC2 `_broad_anchor_selection` | Per extent, patient context = extent only; **stage=None** |
| `filter_applicable_services` | For `one_tooth` + prosthetics + stage unknown → **no services** (zirconia_crowns / implant_supported require stage) |
| Exclusion | `no_anchor_applicable:one_tooth` |
| AC3 scope-nav | `materialize_scope_nav_followups(confirmed_extents=selection.price_confirmed_extents)` → **no «Один зуб» button** |

**Existing stage path works when scope is already known:**

```
extent=one_tooth, stage unknown
→ discover_stage_clarification_stages() = ('implant_placed', 'natural_tooth_present')
→ AC3 stage_clarify + stage-nav buttons (existing test_ac3)
→ after stage click: zirconia 25k or implant_supported 31k
```

Gap: **reachability for nav** does not consider this one-hop stage path at broad time.

---

## 2. Immediate vs navigable coverage (mixed today)

| Concept | Definition | Current signal |
|---------|------------|----------------|
| **Immediate** | Numeric offer or `no_public_price` from AC2 with extent + known stage | `TargetPriceAnchor` in `_broad_anchor_selection` |
| **Navigable** | Immediate **OR** one governed stage descendant with confirmed offer | **Missing** — only immediate anchors feed `price_confirmed_extents` |

**Seam:** `contracts/target_scope_aware_selection.py` → `price_confirmed_extents` populated only from `anchors` tuple (`core/target_scope_aware_selection.py` L248). Stage-only paths never promote extent to navigable.

**Target:** Split signals:

- `price_immediate_extents` — direct anchor extents (broad text anchors)
- `price_navigable_extents` — immediate ∪ one-stage reachable (scope buttons)

Broad Composer evidence may use immediate anchors only; scope buttons use navigable.

---

## 3. `offer_id` inference (must remove)

**File:** `core/target_offer_extent_applicability.py` L18–24

```python
if ".one_tooth." in offer_id: return ("one_tooth",)
if ".jaw." in offer_id: return ("full_arch",)
```

Owner rule: **`offer_id` is not price/medical semantics.** Inference violates FINAL_PRICE_SCOPE_COVERAGE_NAV normative decision and must be **removed** in implementation; all rich-demo priced offers get explicit `applies_to_extents`.

**Demo gaps today:**

| Offer | Amount | `applies_to_extents` |
|-------|--------|----------------------|
| `zirconia_crowns.default` | from 25 000 | **missing** (falls back to service selection) |
| `implant_supported_prosthetics.default` | from 31 000 | **missing** |
| `removable_dentures.jaw.partial` | 45 000 | `few_teeth` ✓ |
| `removable_dentures.jaw.full` | 65 000 | `full_arch` ✓ |

Stage-specific applicability remains in **service catalog `selection.stage`**, not `offer_id`.

---

## 4. Reusable APIs (no new selector)

| API | Role in reachability |
|-----|---------------------|
| `run_target_scope_aware_selection()` | AC2 per (extent, stage?) trial |
| `discover_stage_clarification_stages()` | Governed stage candidates (max depth 1) |
| `filter_offers_for_extent()` | After inference removal — explicit `applies_to_extents` only |
| `project_target_service_offers()` | Unchanged ranking; extent filter stays |
| `materialize_scope_nav_followups(confirmed_extents=...)` | Wire to **navigable** extents |
| `materialize_stage_nav_followups()` | Unchanged post scope-click |
| `UiScopeAction` / `UiStageAction` | AC1 governed refs — no Planner re-guess on click |
| `assemble_scope_aware_price_package()` | Broad vs stage_clarify vs scoped — extend signals only |

**New helper (minimal):** e.g. `core/target_offer_price_reachability.py` — pure function over bundle + AC2 calls; **not** a parallel selector.

---

## 5. Why no new selector / medical axis

- Stage axis **already exists** (`natural_tooth_present`, `implant_placed`, `extraction_context`).
- `discover_stage_clarification_stages()` already computes which stages change applicability.
- Reachability = **deterministic enumeration** of existing stage values (depth ≤ 1), not treatment choice.
- Bot does not pick stage for patient — only exposes buttons for **authored** paths.

---

## Demo prosthetics — expected navigable extents @ implementation

| Extent | Immediate | One-stage path | Navigable |
|--------|-----------|----------------|-----------|
| `one_tooth` | ✗ (stage required) | `natural_tooth_present` → zirconia 25k; `implant_placed` → implant_supported 31k | **✓** |
| `few_teeth` | ✓ partial denture 45k | clasp optional — not required for nav if immediate exists | **✓** |
| `full_arch` | ✓ full denture 65k | — | **✓** |

**Broad text anchors (immediate only):** crown paths via stage-specific services are **not** immediate broad anchors; broad overview should show confirmed prices per owner list (25k / 31k / 45k / 65k) without veneers unless authored as broad anchor.

**Veneers:** aesthetics service — exclude from prosthetics broad commercial overview unless explicitly tagged as broad anchor in data/strategy.

---

## Implantation regression (must preserve)

| Extent | @ `2b5e90d` | After change |
|--------|-------------|--------------|
| `few_teeth` | hidden (no offer, no stage path) | **stay hidden** |
| `one_tooth` | shown | **stay shown** |
| `full_arch` | shown | **stay shown** |

---

## Implementation seams (Phase 2 allowlist)

| File | Change |
|------|--------|
| `core/target_offer_price_reachability.py` | **new** — immediate + one-stage navigable algorithm |
| `core/target_offer_extent_applicability.py` | remove `offer_id` inference; explicit data only |
| `core/target_scope_aware_selection.py` | navigable extents; broad anchor policy |
| `core/target_scope_aware_price_package.py` | scope-nav from navigable; broad preview policy |
| `contracts/target_scope_aware_selection.py` | `price_navigable_extents` field (keep `price_confirmed_extents` for immediate or alias) |
| `clients/demo/target_response/pricebook/services/*.json` | explicit `applies_to_extents` on prosthetics offers |
| `tests/test_final_prosthetics_price_nav_reachability_*.py` | acceptance 1–16 |

**Forbidden:** LIVE/LLM, A9 tuning, Planner prompt, Verifier redesign, regex lists, recursive stage tree, frozen artifact edits, second selector.

---

## Acceptance matrix (binding, 16 cases)

| ID | Case |
|----|------|
| 1 | Prosthetics broad → `one_tooth` navigable via stage |
| 2 | `one_tooth + natural_tooth_present` → 25 000 ₽ |
| 3 | `one_tooth + implant_placed` → 31 000 ₽ |
| 4 | Prosthetics broad → partial denture 45 000 ₽ |
| 5 | Prosthetics broad → full denture 65 000 ₽ |
| 6 | Scope buttons without duplicates |
| 7 | Stage click — planner not called |
| 8 | Invalid/unshown ref — fail-closed |
| 9 | Implantation `few_teeth` stays hidden |
| 10 | Implantation one tooth / full arch unchanged |
| 11 | Offer without explicit applicability not classified by `offer_id` |
| 12 | Sparse: only one-tooth route → one scope button |
| 13 | Sparse: no immediate, one valid stage descendant → button shown |
| 14 | Sparse: stage descendants without prices → button hidden |
| 15 | `/ask` + `/ask/stream` parity |
| 16 | Rich pricebook + frozen artifacts unchanged |

Sparse fixtures: in-memory only.

---

## Frozen artifact guards

Immutable: Retry1–4 live artifacts, A9/A9R/S-series, W1b checksum pins, widget matrix.

---

## STOP

Governance checkpoint only. Implementation after PRE-CODE ✅.
