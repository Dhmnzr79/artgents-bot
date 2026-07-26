# FINAL_PRICE_AND_SERVICE_COVERAGE — seam audit (read-only)

**Date:** 2026-07-26  
**Baseline:** `696f77d` (`codex/stage-a`) · **FINAL_SCOPE_CLOSEOUT_COMPLETE**  
**Scope:** Phase 1 governance only · **NO IMPLEMENTATION / NO LIVE / NO LLM**

**Canonical law:** `docs/PRICE_SERVICE_ARCHITECTURE.md` (rules 29–30, §5 `no_public_price`, verification matrix).

---

## Verdict

Four owner situations require **orthogonal axes** (service presence, catalog detail, price detail) and a **deterministic price precedence ladder**. Rich demo pack (full service-specific offers) already works via AC1→AC2→AC3. **Gap:** no typed **family-level price** record; `broad_family_price` always assumes scope-specific anchors + scope-nav buttons. Branches 1–3 (`no_public_price`, `service_not_offered`, clinic alternatives) **mostly exist** but need seam confirmation + offline coverage; **no parallel handlers**.

---

## Owner situations — current vs target

| # | Situation | Current runtime | Target (owner) | Change scope |
|---|-----------|-----------------|----------------|--------------|
| **1** | Service exists, no public price | `no_public_price` offer mode in schema; AC2 includes offer; Composer gets offer evidence; Verifier whitelists `approved_text` only | Typed `no_public_price` + `approved_text`; no invented numbers | **Verify + test**; demo pack has **no** `no_public_price` offer today |
| **2** | Service not offered + authored alternative | Ingress `service_not_offered` → `clinic_policies.yaml` `service_alternatives` (note + `suggest_ref` QR); **pre-resolver exit** — target runtime not reached | Controlled answer + **only** clinic-authored alternative ref | **Verify + test**; bridge alternative → target `service_id` **not** wired |
| **3** | Service not offered, no alternative | Ingress template fallback | Controlled plain answer; no substitute buttons | **Verify + test** |
| **4** | Complex direction, family-only price | AC2 `broad_anchors` requires per-extent offers; AC3 always emits 3 scope-nav buttons on `broad_family_price` | Mode **A:** scope-specific prices (unchanged). Mode **B:** single family price, **no** scope buttons without finer authored prices; named protocol must **not** inherit family price | **New typed family price** + deterministic broad mode selection |

---

## Orthogonal axes (owner normative)

```
service presence     → catalog entry active / ingress not_offered
catalog detail       → detailed protocols vs umbrella service only
price detail         → service-specific offer | no_public_price | family-level | data-gap
```

**Never conflate:** family-level «от 25 000 ₽» ≠ All-on-4 protocol price.

---

## Price precedence (binding)

1. Concrete **service-specific** price (`fixed` / `from` / `range`) for applicable offer  
2. Typed **`no_public_price`** (`approved_text` only)  
3. **Family-level** price (new record; `applies_to_service_ids` scope)  
4. **Controlled data-gap** (no numbers; client-approved fallback text when added)  
5. Never: substitute another service's price; LLM-invented amounts; family price as protocol price

---

## Broad family price — two deterministic modes (from data)

| Mode | Data signal | AC3 behavior |
|------|-------------|--------------|
| **A — scope-specific** | ≥1 scope-applicable service offer with numeric price per extent used in anchors | Existing `broad_anchors` + 3 scope-nav buttons |
| **B — family-only** | Family-level price record; no finer scope-specific authored prices behind buttons | Single exact family price; **no** scope-nav; no invented breakdown |

Selection is **data-driven**, not LLM rules.

---

## Catalog models (both allowed)

| Model | Example | Notes |
|-------|---------|-------|
| **A — detailed catalog** | `classic`, `all_on_4`, `all_on_6` services; only family-level **price** | Missing protocol ≠ «не оказываем» |
| **B — umbrella only** | One `implantation` service + family price | No synthetic protocol services required |

---

## Existing mechanisms — preserve, do not duplicate

### `no_public_price`
- Contract: `contracts/response_schema.py` → `TargetNoPublicPrice`
- AC2: `core/target_offer_projection.py` — offers included if active
- Verifier: `core/target_response_verifier.py` — `_offer_claims()` for `approved_text`
- **Gap:** no demo offer; distinguish missing price record vs intentional `no_public_price`

### `service_not_offered` + alternatives
- Ingress: `ingress_gate.py` → `classify_ingress()`, `build_service_not_offered_answer()`
- Policies: `clients/demo/clinic_policies.yaml` + `core/clinic_policies_loader.py`
- Pre-resolver: `orchestration/pre_resolver_turn.py` early return
- **Gap:** ingress uses legacy `clients/demo/service_catalog.json`, not `target_response/service_catalog.json`

### AC2 selection
- `core/target_scope_aware_selection.py` — `run_target_scope_aware_selection()`
- `kind=broad_anchors` when `extent==unknown`; exclusions `no_public_or_missing_offers:*`

### AC3 package + scope nav
- `core/target_response_stage.py` — `derive_response_stage()`
- `core/target_scope_aware_price_package.py` — `assemble_scope_aware_price_package()`
- `core/target_client_ui_nav.py` — `materialize_scope_nav_followups()` (always 3 buttons on broad)
- `core/target_turn_frame_dispatch.py` — `broad_family_price` when extent unknown

### Verifier
- `core/target_response_verifier.py` — commercial whitelist; `data_gap` / `stage_clarify` empty evidence allowed
- **No redesign** in this milestone

### HTTP parity
- `app.py` — `/ask` and `/ask/stream` share `_orchestrate_ask_turn()` → target FullContext

---

## Proposed minimal data contract (implementation)

**New file (per client pack):**

```
clients/<client_id>/target_response/pricebook/family_prices.json
```

**Shape (illustrative):**

```json
{
  "version": 1,
  "records": [
    {
      "family_price_id": "implantation_family_from",
      "topic": "implantation",
      "price": {
        "mode": "from",
        "min_amount": 25000,
        "currency": "RUB",
        "billing_unit": "treatment"
      },
      "applies_to_service_ids": ["classic", "one_stage", "all_on_4", "all_on_6"],
      "approved_context": "Общая начальная стоимость направления; не является ценой отдельного протокола"
    }
  ]
}
```

**Loader:** extend `ResponseSchemaBundle` + `core/response_schema_loader.py` — **no synthetic family service**.

**Alternative rejected:** third parallel YAML in `clinic_policies.yaml` for prices (dual-source seam).

---

## Implementation seams (Phase 2 allowlist targets)

| Seam | File | Change |
|------|------|--------|
| Bundle contract | `contracts/response_schema.py` | `TargetFamilyPrice` + bundle field |
| Loader | `core/response_schema_loader.py` | load `family_prices.json` |
| Price resolution | `core/target_family_price_resolution.py` (new) | precedence + broad mode A/B |
| AC2 | `core/target_scope_aware_selection.py` | family-only anchor path |
| AC3 | `core/target_scope_aware_price_package.py` | suppress scope-nav in mode B |
| Stage | `core/target_response_stage.py` | optional `family_only_broad` signal if needed |
| Composer policy | `core/target_response_policy.py` | family-only compact directive (deterministic) |
| Ingress/alternatives | **tests only** unless proven gap | no new handler |

**Forbidden:** regex lists, second selector, thresholds, new LLM calls, feature flags, parallel price authority, implantation/prosthetics hardcode in shared core.

---

## Acceptance matrix (binding)

| ID | Case |
|----|------|
| A | Rich demo — byte/semantic equivalent |
| B | Service price beats family price |
| C | `no_public_price` beats family fallback |
| D | Detailed services + family-only price — broad shows family; protocol not falsely priced |
| E | Umbrella + family-only — broad family price; no scope buttons; protocol «not confirmed separately» |
| F | Not offered + authored alternative — controlled + approved ref only |
| G | Not offered, no alternative — plain controlled; no substitute buttons |
| H | Exists + typed `no_public_price` — `approved_text`; no invented numbers |
| I | Exists, price record missing — data-gap; no cross-service price |
| J | `/ask` + `/ask/stream` parity |
| K | Full rich pricebook — broad/scoped/concrete unchanged; scope buttons work |
| L | No `price:None/...`, false scope refs, legacy routes |

Sparse-data cases: **in-memory / synthetic fixtures** in tests only.

---

## Frozen artifact guards

Immutable: Retry1–4 live artifacts, A9/A9R/S-series eval artifacts, W1b checksum pins, widget matrix `f4eecf75…`.

---

## STOP

Governance checkpoint only. Implementation requires PRE-CODE ✅ then separate owner GO continuation within same milestone.
