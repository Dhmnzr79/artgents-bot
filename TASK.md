# TASK — AC2 Deterministic scope-aware service/price selection (offline component)

**Product baseline:** `codex/stage-a` @ `3144572` (AC1 complete) · **W1b PARKED** · **NO LIVE / NO LLM / NO A9 product read**

**Authority:** Architecture Convergence Audit (2026-07-24); канон: `docs/ARCHITECTURE_CONVERGENCE.md`, `docs/PRICE_SERVICE_ARCHITECTURE.md`.

**AC1 complete:** `72681cc` · `EffectiveScope` + `UiScopeAction` + session `patient_facts` in product path.

## Goal

Построить **один детерминированный offline selection-компонент** (pure, tested, unwired):

```text
EffectiveScope
  → active service_catalog entries (topic/family)
  → service_catalog.selection applicability
  → clinic_strategy ranking
  → exact pricebook offers (S23/S24)
  → typed TargetScopeAwareSelectionResult
```

**AC2 закрывает пробел applicability + composition.** Не создаёт второй offer/strategy engine.

**Явно вне AC2:** product runtime/widget wiring, Composer/Verifier, ResponseStage, marketing/CTA, follow-up UI, W1b restore, видимое изменение ответов пользователю. Полное атомарное подключение — **AC3**.

## W1b parked (do not touch)

Snapshot: `docs/artifacts/w1b_wip_checkpoint_2026-07-24/` (`MANIFEST.txt`, `checksums.sha256`, `RESTORE.md`).

- **Запрещено:** restore patch, `family_price_groups.yaml` as authority, `several_teeth`/`full_jaw` vocabulary, копирование W1b кода целиком.
- **Разрешено:** read-only изучение snapshot; классификация идей для AC3 (ref overlay, two-phase nav).
- **Artifact hashes** must remain byte-identical to `checksums.sha256`.

## Baseline and tree state

**Governance commit (this checkpoint):**

- `HEAD` = `3144572` (AC1 product + completion record).
- Dirty diff — только `TASK.md` + minimal docs sync.
- Push → **PRE-CODE checker ✅** → STOP.

**AC2 implementation preflight** (later, separate owner GO):

- `HEAD` = governance commit after this TASK.
- Working tree clean; W1b checksums match.

## Process (mandatory)

1. **Governance (this commit):** seam audit in TASK + docs delta → push → **PRE-CODE ✅** → STOP.
2. **AC2 implementation** (later): pure selection component + offline test matrix → **COMPLETION ✅** → product commit → STOP.
3. **AC3** (later): atomic runtime wiring + ResponseStage + follow-up/marketing — separate TASK.

No product code before PRE-CODE ✅.

---

## Read-only seam audit (S14–S27 + AC1)

### Reuse as-is (compose, do not rebuild)

| Layer | Module | Public API | Role |
|-------|--------|------------|------|
| Schema load | `core/response_schema_loader.py` | `load_response_schema_bundle(pack_root) -> ResponseSchemaBundle` | `service_catalog.json`, `clinic_strategy.yaml`, pricebook |
| Selection schema | `contracts/response_schema.py` | `TargetServiceSelection`, `TargetOptionSelection`, `TargetService`, `TargetServiceOption` | Authored applicability axes (`mode`, `extent`, `stage`, `jaw`, `reported_context`) |
| Strategy match key | `contracts/response_schema.py` | `TargetStrategyMatch` | Rule match context |
| Strategy rank | `core/response_strategy.py` | `resolve_target_strategy(strategy, context, *, service_ids=(), offer_ids=(), explicit_service_id=..., explicit_offer_id=...) -> TargetStrategyResolution` | Rank **only supplied** candidates; `max_options`; explicit pin |
| Service context | `core/service_data_context.py` | `build_service_data_context(bundle, doctor_catalog, service_id) -> ServiceDataContext` | Join service + offers |
| Offer projection | `core/target_offer_projection.py` | `project_target_service_offers(ctx, strategy, strategy_context, *, selected_option_id=..., explicit_offer_id=...) -> TargetOfferProjection` | Active filter, option pin, S15 on offers |
| Brand projection | `core/target_brand_offer_projection.py` | `project_target_service_brand_offers(...)` | Brand filter → delegates S23 |
| Brand resolve | `core/target_brand_resolver.py` | `resolve_target_brand_term(...)` | Explicit brand path |
| Service resolve | `core/target_service_resolver.py` | `resolve_target_service_term(services, term) -> TargetServiceResolution` | Explicit named service (S26); does **not** apply selection |
| Assembly | `core/target_offline_response_assembly.py` | `assemble_target_offline_response_materials(...)` | S27 vertical slice (AC3 wiring) |
| Topic membership | `contracts/target_service_content_topic.py` | `service_catalog_content_topic_matches(content_ref, topic) -> bool` | Topic filter **after** applicability |
| AC1 scope | `contracts/effective_scope.py` | `EffectiveScope` | extent/topic/source/provenance |
| AC1 merge | `core/target_effective_scope.py` | `resolve_effective_scope(...)`, `SessionPatientFacts` | ui_action > session > unknown |
| Runtime stub | `core/target_runtime_strategy.py` | `resolve_target_runtime_strategy_context(bundle, service_id=...)` | **Not** patient-scope-aware; AC3 replaces |

### Exists but bypasses selection (do not copy pattern)

| Module | Issue |
|--------|-------|
| `core/target_family_price_overview.py` | `select_family_price_overview_services` — topic + active + representative offer + role_rank; **ignores `service_catalog.selection`** |
| W1b snapshot | `family_price_groups.yaml` entries as parallel applicability — **REJECT** |

### Real gap AC2 closes

1. **Runtime interpreter for `service_catalog.selection`** — types + demo data exist; no `filter_applicable_*` in `core/`.
2. **`EffectiveScope` → `TargetStrategyMatch` bridge** — extent/jaw/stage/modifiers from effective context; unknown fails closed on required axes.
3. **Service-level `resolve_target_strategy(service_ids=...)` composition** — tested offline only (`test_target_strategy_resolution.py`, `test_demo_target_clinic_strategy.py`).
4. **Option-level `TargetOptionSelection`** — schema exists; not applied before offer projection.
5. **Typed end-to-end offline result** — scope-aware shortlist/anchors + exact offer IDs without UI text.

### Why this is not a second selector

- **Applicability** = new pure gate on authored `TargetServiceSelection` / `TargetOptionSelection`.
- **Ranking** = existing `resolve_target_strategy` (S15).
- **Offers** = existing `project_target_service_offers` / brand path (S23/S24).
- AC2 adds **composition + one result contract**, not parallel price/strategy logic.

### W1b snapshot classification (read-only)

| Verdict | Item |
|---------|------|
| REUSE (AC3) | `target:family_price_group/...` ref pattern; two-phase situation nav |
| REWORK (AC3) | Group labels keyed by canonical extent; run **after** selection gate |
| REJECT | Hardcoded group `entries` as applicability; `several_teeth`/`full_jaw`; full patch restore |

---

## Normative laws (AC2)

### Source ownership

- `EffectiveScope` owns known extent (+ future jaw/stage/modifiers when present in session).
- `service_catalog.selection` — **sole** service applicability owner.
- `clinic_strategy` — order/cap on **already applicable** services/offers.
- Pricebook — money/units/modes only.
- UI labels/config — not applicability.
- Marketing/facts/CTA — out of scope.

### Scope semantics

Canonical extent: `one_tooth | few_teeth | full_arch | unknown`.

Scope **does not** choose All-on-4/6, classic implant, diagnosis, or `service_id`.

### Applicability

- All known required selection fields must match.
- `unknown` does **not** satisfy required `extent`, `stage`, `jaw`, or `reported_context`.
- Unknown optional field does not block.
- `one_stage` requires authored extraction context when catalog requires it.
- `implant_supported_prosthetics` requires `implant_placed` when catalog requires it.
- `full_arch` ≠ All-on-4 medically; only commercial eligibility.
- `reported_bone_deficit` does not auto-select sinus/zygomatic protocol.

### Strategy order

1. explicit active service (when truly named and active)
2. applicable active catalog entries
3. matching `clinic_strategy` rule
4. offer priorities (within S23)
5. stable catalog/offer order tie-break
6. `max_options` cap

Strategy cannot resurrect ineligible service.

### Price integrity

Reuse S23 invariants: fixed/from/range/no_public_price verbatim; no tooth-count multiplication; no dual-jaw doubling; distinct billing units; option pin; inactive excluded; missing offer fail-closed.

### Broad unknown scope (offline preparation only)

When extent unknown and offers exist: prepare compact anchors covering `one_tooth` + `full_arch` (`few_teeth` optional per strategy/data). Anchor = scope price orientation, not treatment recommendation. **No user text or buttons in AC2.**

### Known scope

Return only applicable services/offers; no broad menu; no repeated clarification; no-public → typed empty result.

---

## Minimal public contract (AC2 implementation)

New file `contracts/target_scope_aware_selection.py` (name fixed at implementation):

```python
SelectionKind = Literal["broad_anchors", "scoped_shortlist"]

class TargetPriceAnchor:  # broad_anchors only
    extent: ScopeExtent          # anchor axis, not medical recommendation
    service_id: str
    offer_id: str
    provenance: str

class TargetScopeAwareSelectionResult:
    topic: str
    effective_scope: EffectiveScope      # snapshot
    kind: SelectionKind
    strategy_context: TargetStrategyMatch  # REUSE
    matched_rule_id: str | None
    service_ids: tuple[str, ...]         # deterministic ranked order
    offers_by_service_id: dict[str, tuple[TargetOffer, ...]]  # exact IDs from S23
    anchors: tuple[TargetPriceAnchor, ...]  # empty when scoped_shortlist
    exclusions: tuple[str, ...]          # minimal typed codes only
```

**Reuse:** `EffectiveScope`, `TargetStrategyMatch`, `TargetOffer`, `TargetStrategyResolution`, `TargetOfferProjection`.

**Forbidden in result:** answer text, quick_replies, CTA, marketing copy, `ResponseStage`.

### Composition entrypoint (AC2 implementation)

```python
# core/target_scope_aware_selection.py
def run_target_scope_aware_selection(
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    *,
    effective_scope: EffectiveScope,
    topic: str,
    explicit_service_id: str | None = None,
    explicit_offer_id: str | None = None,
    selected_option_id: str | None = None,
    selected_brand_id: str | None = None,
) -> TargetScopeAwareSelectionResult: ...
```

Supporting pure functions:

- `core/target_strategy_context.py` — `strategy_match_from_effective_scope(scope, *, service_family=None) -> TargetStrategyMatch`
- `core/target_service_applicability.py` — `filter_applicable_services(bundle, *, topic, strategy_context, explicit_service_id=None) -> tuple[TargetApplicableService, ...]`

---

## Forbidden (AC2)

- Live/LLM; A9 harness/authority; `TurnFrame.patient_scope` product read
- W1b restore; `family_price_groups` as applicability
- Product runtime/widget behavior changes (orchestration, `target_runtime_turn`, dispatch, Composer, Verifier)
- `ResponseStage`; marketing runtime; temporary user-visible fallback
- Regex/classifier patient situation; RAG/per-MD routing
- Files outside allowlist
- Hardcoded demo `service_id` lists in shared core
- Cross-client data leakage in tests

## Allowlist

### Governance commit (this checkpoint only)

| File |
|------|
| `TASK.md` |
| `docs/ARCHITECTURE_CONVERGENCE.md` |
| `docs/PRICE_SERVICE_ARCHITECTURE.md` |
| `docs/STRANGLER_ROADMAP.md` |
| `docs/ARCH_TARGET_DESIGN.md` |

### New (AC2 implementation only)

| File |
|------|
| `contracts/target_scope_aware_selection.py` |
| `contracts/target_service_applicability.py` |
| `core/target_strategy_context.py` |
| `core/target_service_applicability.py` |
| `core/target_scope_aware_selection.py` |
| `tests/test_target_strategy_context.py` |
| `tests/test_target_service_applicability.py` |
| `tests/test_target_scope_aware_selection_offline.py` |

### Modify (AC2 implementation only)

| File | Condition |
|------|-----------|
| `contracts/response_schema.py` | Only if minimal shared literals needed; prefer new contract file |

### Explicitly forbidden in AC2 implementation

| Area |
|------|
| `orchestration/*`, `app.py` |
| `core/target_runtime_turn.py`, `core/target_turn_frame_dispatch.py` |
| `core/target_family_price_overview.py` (product path unchanged until AC3) |
| Composer/Verifier/widget/materializer paths |
| `docs/artifacts/w1b_wip_checkpoint_2026-07-24/**` |
| Protected acceptance / golden / live harnesses |

---

## Acceptance (offline, AC2 implementation)

### A. Composition

1. Pipeline composes existing S15 + S23 (+ optional S24) without duplicating offer filter logic.
2. No new ranking algorithm beyond applicability gate + existing `resolve_target_strategy`.

### B. Applicability

3. `filter_applicable_services` honors `selection.mode` (`scope`/`context`/`direct`) per `PRICE_SERVICE_ARCHITECTURE.md`.
4. Unknown extent does not satisfy required selection extent list.
5. Option-level selection intersects parent service eligibility.

### C. Strategy

6. `resolve_target_strategy` receives only applicable `service_ids`; ineligible never ranked.
7. Explicit service pin wins over default priority when active and applicable.
8. `max_options` and stable tie-break respected.

### D. Broad unknown

9. Unknown extent + available offers → `kind=broad_anchors` with `one_tooth` + `full_arch` coverage when catalog/strategy allow.
10. Anchors carry extent + commercial `service_id`/`offer_id` only.

### E. Known scope

11. Known extent → `kind=scoped_shortlist`; no anchor menu.
12. No applicable public offer → typed empty/no-public path in result metadata (no invented price).

### F. Price integrity

13. Projected offers preserve price modes and billing units; matrix cases 15–22 pass.

### G. Isolation

14. Two synthetic client strategies → same applicability, different order only (case 23–26).
15. No demo service IDs hardcoded in shared core (case 27–28).

### H. Neighbors / firewalls

16. AC1 tests unchanged and green.
17. S34/S40/S46 single-service projection tests unchanged.
18. A9 product firewall unchanged.
19. W1b `checksums.sha256` byte-identical (case 32).
20. No marketing/CTA/Composer/Verifier invocation in AC2 tests (case 34).

---

## Offline test matrix (AC2 implementation)

Implantation (1–8), prosthetics (9–14), price integrity (15–22), strategy/isolation (23–28), neighbors (29–34) — as specified in owner AC2 brief. Implement as parametrized cases in `test_target_scope_aware_selection_offline.py` + unit tests in applicability/strategy_context files.

## Tests (focused, AC2 implementation)

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-ac2-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_target_strategy_context.py `
  tests/test_target_service_applicability.py `
  tests/test_target_scope_aware_selection_offline.py `
  -q
```

### Relevant neighbors (must stay green)

```powershell
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_effective_scope_contract.py `
  tests/test_ui_scope_action_contract.py `
  tests/test_session_patient_facts_offline.py `
  tests/test_ui_scope_click_http_offline.py `
  tests/test_target_strategy_resolution.py `
  tests/test_target_offer_projection.py `
  tests/test_demo_target_clinic_strategy.py `
  tests/test_demo_target_offer_projection.py `
  -q
```

Safe wider offline (no live, no A9 harness): above + `tests/test_w1_family_price_overview_offline.py` (unchanged behavior).

## STOP conditions

1. AC2 requires product runtime wiring, widget change, or visible answer change
2. Requires W1b restore or `family_price_groups` authority
3. Requires new offer ranking engine duplicating S15/S23
4. Requires `TurnFrame.patient_scope` or A9 authority
5. Requires `ResponseStage`, marketing runtime, or Composer/Verifier changes
6. PRE-CODE or COMPLETION checker ❌ without fix path

## Completion record

| Field | Value |
|-------|-------|
| AC1 product HEAD | `72681cc` |
| W1b artifact | `docs/artifacts/w1b_wip_checkpoint_2026-07-24/` |
| Governance baseline | `3144572` |
| AC2 governance HEAD | `47be537` |
| PRE-CODE | ✅ |
| COMPLETION | |
| AC2 product HEAD | |

**STOP after governance PRE-CODE ✅. AC2 implementation starts only after separate owner GO.**
