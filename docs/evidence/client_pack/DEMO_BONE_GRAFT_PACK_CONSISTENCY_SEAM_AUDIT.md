# DEMO_BONE_GRAFT_PACK_CONSISTENCY — seam audit

**Дата:** 2026-07-27  
**Baseline:** `codex/stage-a` @ `18e4d47` (`FULLCONTEXT_DIALOGUE_PRESENTATION_CONVERGENCE` complete)  
**Режим:** governance / docs / tests only · **NO product code / NO LIVE / NO LLM**  
**Owner GO:** Phase 1 governance only; implementation blocked until PRE-CODE ✅ + separate owner GO

## Preflight

| Check | Result |
|---|---|
| `HEAD` == `origin/codex/stage-a` @ `18e4d47` | ✅ |
| Working tree clean at governance start | ✅ |
| Prior milestone COMPLETION (`204da81..18e4d47`) | ✅ 24/24 (`test_fullcontext_dialogue_presentation_convergence_{governance,implementation}.py`) |
| Wide safe-offline 6 failures identical on `204da81` and `18e4d47` | ✅ pre-existing, not H–N regression |

## Context

`bone_graft` promoted to first-class demo service in prior milestone (`service_catalog.json`,
`implantation__service__bone_graft.md`, `bone_graft.default.json` with `no_public_price`,
facts applicability in `facts.json`). Six wide safe-offline tests still assume pre–bone-graft
invariants. Failures are **pack consistency gaps + stale test coupling**, not runtime regressions.

## Failure classification (Checkpoint B)

| # | Test | Assertion seam | Classification | Root cause |
|---|------|----------------|----------------|------------|
| 1 | `test_demo_doctor_catalog` | `set(services) - covered == {"tomography"}` | **actual demo-data gap** | `bone_graft` in catalog, no doctor `service_ids` link |
| 2 | `test_demo_doctor_template` | same coverage rule | **actual demo-data gap** | same |
| 3 | `test_demo_target_service_catalog` | `doctor_service_ids == services - {tomography}` | **actual demo-data gap** | same |
| 4 | `test_demo_target_price_offers` | `set(UNIT_LABELS) == set(services)` | **architectural hardcode / stale test** | hardcoded `UNIT_LABELS` dict requires every catalog service including `no_public_price` |
| 5 | `test_demo_target_marketing_policy` | `EXPECTED_CURRENT_HASHES[CURRENT_MARKETING]` | **historical fixture / stale test** | byte-hash pin on `tests/fixtures/demo_legacy_marketing.yaml` — not active authority |
| 6 | `test_demo_target_marketing_migration_audit` | `promo_rules[*].allowed_service_ids == facts[*].allowed_service_ids` | **stale test coupling** | legacy `promo_rules` mirror must not be superset-locked to canonical `facts.json` |

**Not classified as:** product runtime bug, Verifier/A9 issue, or stale bone_graft MD/offer data.

## 1. Doctor coverage

### Existing surgical / implant competence (authored)

| Doctor | ID | Authored competence relevant to bone graft |
|--------|-----|---------------------------------------------|
| Орлов Никита Владимирович | `doctors__doctor__orlov` | MD: «Синус-лифтинг, **костная и мягкотканная пластика**»; `service_ids` includes `sinus_lift`, `classic`, `one_stage` |
| Волков Александр Сергеевич | `doctors__doctor__volkov` | MD: главный врач, **стоматолог-хирург, имплантолог**; sinus-lift, скуловая/птеригоидная имплантация; `service_ids` includes `sinus_lift` |
| Кузнецов Дмитрий Андреевич | `doctors__doctor__kuznetsov` | **Ортопед**; протезирование на имплантах — **no** authored bone-graft surgery |
| Others | — | No implant/surgical profile |

### Peer pattern

`sinus_lift` is linked only to **orlov + volkov**. Bone graft is same implantology surgical family
(per orlov MD and bone_graft service MD). `tomography` remains the sole intentional uncovered service.

### Proposed mapping (owner sign-off required)

| service_id | proposed `doctor_ids` | Evidence |
|------------|----------------------|----------|
| `bone_graft` | `doctors__doctor__orlov`, `doctors__doctor__volkov` | orlov MD explicit bone graft; volkov surgical implantologist peer to sinus_lift |

**Forbidden:** invent credentials; assign kuznetsov without authored surgical bone-graft competence.

**Binding acceptance:** «Кто делает костную пластику?» → orlov + volkov (existing demo doctors only).

## 2. Price unit (`no_public_price`)

| Fact | Value |
|------|-------|
| Offer | `bone_graft.default.json` → `price.mode: no_public_price`, `approved_text` only |
| Package label | descriptive, not a billing unit |
| `UNIT_LABELS` | hardcoded in `tests/test_demo_target_price_offers.py` (~line 31–116); one entry per **catalog** service |

**Why test fails:** `test_owner_units_labels_and_followups_have_no_legacy_dead_actions` requires
`set(UNIT_LABELS) == set(service_catalog)` — treats `bone_graft` like numeric offers.

**Normative direction:**

- Numeric offers: `billing_unit` + `package.label` from authored offer/schema (existing `UNIT_LABELS` parity OK).
- `no_public_price`: **no** fictitious `billing_unit`; no `UNIT_LABELS` entry.
- Do **not** add new product hardcoded service dictionary.
- Replace catalog-wide `UNIT_LABELS` equality with schema-driven assertion scoped to numeric-price offers.
- `sinus_lift` exact prices (42000 / 68000) must not regress.

## 3. Marketing policy

### Canonical authority

| Artifact | Role |
|----------|------|
| `clients/demo/target_response/marketing.yaml` | Active scenario rules, limits, initial commercial blocks |
| `clients/demo/target_response/pricebook/facts.json` | Active facts + `allowed_service_ids` |
| `tests/fixtures/demo_legacy_marketing.yaml` | **Historical** pre-convergence mirror (`service_marketing` + `promo_rules`) |

### Why tests fail

1. **Hash pin** (`test_demo_target_marketing_policy`): `EXPECTED_CURRENT_HASHES` expects
   `e958fcd…` but fixture bytes are `92c64e49…` (encoding/content drift in frozen legacy YAML).
2. **Promo mirror** (`test_demo_target_marketing_migration_audit`): `bone_graft` added to
   `facts.json` `allowed_service_ids` for cross-cutting facts (`installment_12`, `free_implant_consult`,
   `implant_same_day_discount`) — **not** a new dedicated promotion.

### Applicability (no cross-service leak)

| fact_id | bone_graft in `allowed_service_ids` | Dedicated promo? |
|---------|-------------------------------------|------------------|
| `installment_12` | yes | no — payment benefit for implant family |
| `free_implant_consult` | yes | no — consult CTA for implant/prosthetics topics |
| `implant_same_day_discount` | yes | no — implant payment promo |
| `implant_warranty` | **no** | — |
| `professional_whitening_discount` | **no** | — |
| `tax_deduction` | **no** | — |

**Normative:** service may have approved facts without `promo_rules` row in legacy fixture;
absence of bone_graft-specific promotion is **correct**. Marketing tests must validate
refs/applicability, not mandatory promotion per service.

**Forbidden:** invent bone_graft promo; mechanical hash update on legacy fixture.

## 4. Legacy marketing hash fixture

| Question | Answer |
|----------|--------|
| Active authority? | **No** — canonical is `target_response/marketing.yaml` + `facts.json` |
| Historical frozen fixture? | **Yes** — migration audit artifact; `docs/MARKETING_TARGET_MIGRATION_AUDIT.md` |
| Stale mirror after convergence? | **Yes** — byte-hash active pin is obsolete |

**Proposed implementation:**

- Remove `demo_legacy_marketing.yaml` from `EXPECTED_CURRENT_HASHES` active pin; or delete/isolate fixture from active assertions.
- Keep migration audit doc references; do **not** create mandatory mirror of canonical `marketing.yaml`.
- Do **not** touch frozen live eval pins.

## 5. TASK drift

| Issue | Correction |
|-------|------------|
| `tests/test_turn_plan_protocol_guard.py` in wide command | **Missing file** — remove from command |
| All other wide paths @ `18e4d47` | 26/27 exist |

## Proposed changes table (implementation — blocked)

| File | Action | Rationale |
|------|--------|-----------|
| `clients/demo/doctor_catalog.json` | UPDATE | Add `bone_graft` to orlov + volkov `service_ids` |
| `tests/test_demo_target_price_offers.py` | UPDATE | Scope `UNIT_LABELS` to numeric-price offers only |
| `tests/test_demo_target_marketing_policy.py` | UPDATE | Drop legacy fixture byte-hash from active pin |
| `tests/test_demo_target_marketing_migration_audit.py` | UPDATE | Facts↔promo parity without legacy superset lock |
| `tests/fixtures/demo_legacy_marketing.yaml` | DELETE or historical isolate | Stop active hash/mirror enforcement |
| `tests/test_demo_bone_graft_pack_consistency_implementation.py` | CREATE | COMPLETION checker (doctor query, no_public_price, no promo invent) |
| `TASK.md` wide command | UPDATE | Remove missing test path |

**Explicitly unchanged in implementation:**

- `bone_graft.default.json` `no_public_price` text
- `sinus_lift` offer amounts
- `facts.json` applicability (already correct)
- No new `promo_rules` / marketing.yaml service block for bone_graft
- Frozen pins, Verifier, A9, AC1–AC3

## Owner sign-off table

| Decision | Proposed | Owner | Status |
|----------|----------|-------|--------|
| `bone_graft` → `doctors__doctor__orlov` | yes — MD lists костная пластика | — | **PENDING** |
| `bone_graft` → `doctors__doctor__volkov` | yes — surgical implantologist, sinus_lift peer | — | **PENDING** |
| `bone_graft` → `doctors__doctor__kuznetsov` | **no** — orthopedist only | — | **PENDING** |
| No bone_graft-specific promotion | facts applicability only | — | **PENDING** |
| Remove legacy marketing hash active pin | yes | — | **PENDING** |
| `UNIT_LABELS` numeric-only scope | yes | — | **PENDING** |

## STOP conditions

- Owner rejects doctor mapping without alternative authored linkage.
- Implementation requires fictitious price unit, promotion, or doctor credentials.
- Fix requires Verifier/A9/AC1–AC3 change or frozen pin edit.
- File outside implementation allowlist required.
- Wide green attempted by mechanical legacy hash update only.

## STOP

Phase 1 governance PRE-CODE PASS does **not** authorize implementation.
**STOP after governance commit + push** — await owner GO.
