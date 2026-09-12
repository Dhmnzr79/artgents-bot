# FINAL_CLIENT_PACK_DATA_CONVERGENCE — Checkpoint B post-A seam audit

**Дата:** 2026-07-26  
**Baseline:** `codex/stage-a` @ `e3730ea` (Checkpoint A reader cutover ✅)  
**Режим:** governance / docs / tests only · **NO product code / NO client data delete**  
**Owner GO:** Checkpoint B получен; implementation/delete заблокированы до B PRE-CODE ✅

## Preflight (post-A)

| Check | Result |
|---|---|
| `HEAD` == `origin/codex/stage-a` @ `e3730ea` | ✅ |
| Working tree clean at governance start | ✅ |
| Checkpoint A governance + cutover + sparse tests | ✅ green |
| Legacy demo mirrors on disk, byte-identical to governance SHA pins | ✅ |
| Product readers (`core/target_client_data.py` cutover set) import only `target_response/**` | ✅ |

Post-A product path (`app.py` → ingress/planner → target FullContext) **не достигает** legacy island.
`query_selector.py` и price/marketing/patient-situation island остаются importable, но **нулевые product consumers**
после Checkpoint A.

## Post-A inventory (importers / writers / residue)

### Legacy data (DELETE in B implementation)

| Path | Product importers (post-A) | Writers | Test-only | Scripts / frozen |
|---|---|---|---|---|
| `clients/demo/service_catalog.json` | `query_selector`, `core/explicit_service`, `core/service_selector_llm`, parity tests | none (frozen) | governance SHA, cutover parity, `test_demo_doctor_*`, `test_demo_target_*` | `scripts/lint_pricebook.py` (catalog cross-ref) |
| `clients/demo/pricebook/**` (21 services + facts/manifest/README) | legacy island only (`pricebook_loader` → `price_offers` / `price_scope`) | none | `test_pricebook_*`, golden, loader | `scripts/lint_pricebook.py`, `scripts/migrate_pricebook_services.py` |
| `clients/demo/marketing.yaml` | `core/marketing_loader` (island) | none | `test_marketing_*`, `test_promo_overview` | docs references |
| `clients/demo/price_brand_aliases.json` | `core/price_offers` (island) | none | governance SHA, `test_demo_target_price_offers` parity | — |

**Dynamic / import-time:** `query_selector.py` import-time pulls entire legacy island; **no Flask startup import**
(`python -c "import app"` does not load `query_selector`). Island reachable only via explicit import or legacy tests.

### Legacy modules (DELETE in B implementation)

| Module | Product callers (post-A) | Writers | Test-only | Notes |
|---|---|---|---|---|
| `query_selector.py` | **0** | — | `test_dialog_focus_baseline`, `test_final_price_and_service_coverage_existing_paths` | root catalog + price route island |
| `core/pricebook_loader.py` | **0** | — | loader/golden tests, `scripts/lint_pricebook.py` | reads `clients/{id}/pricebook/**` |
| `contracts/pricebook.py` | **0** product; `scripts/lint_pricebook.py` | — | `test_pricebook_*` | delete **after** lint rewrite to target schema |
| `core/price_offers.py` | **0** | — | `test_price_offers`, CI | imports `price_brand_aliases` contract |
| `contracts/price_brand_aliases.py` | island only | — | — | |
| `core/price_scope.py` | **0** | — | `test_price_scope_router` | |
| `core/price_followup.py` | **0** | — | `test_vague_price_followup`, `test_attribute_followup` (re-export) | `attribute_followup` **KEEP** |
| `core/price_answer_assembler.py` | **0** | — | `test_pricebook_golden` | |
| `core/marketing_loader.py` | **0** | — | `test_marketing_loader` | |
| `core/marketing_policy.py` | island (`price_answer_assembler`) | — | `test_marketing_policy` | target policy: `test_demo_target_marketing_policy` **KEEP** |
| `core/promo_overview.py` | **0** | — | `test_promo_overview` | |
| `core/service_selector_llm.py` | **0** | — | `test_service_selector_llm`, `test_turn_planner_stage3` | |
| `contracts/service_selection.py` | `service_selector_llm` only | — | — | |
| `core/explicit_service.py` | **0** | — | `test_explicit_service` | |
| `core/clarify_state.py` | **0** | — | import-firewall negative refs only | orphan module |
| `core/patient_situation.py` | **0** | — | patient_situation tests, `test_metadata_first_observability` | detect/carry stack |
| `core/patient_situation_llm.py` | island only | — | mocked in tests | |
| `core/patient_situation_routing.py` | `query_selector`, island | — | routing tests | |
| `core/patient_situation_session.py` | `query_selector` only | session APIs | session/carry tests | |
| `core/patient_scope_cues.py` | island (`price_scope`, `explicit_service`, `patient_situation`) | — | — | regex price-scope cues |
| `scripts/migrate_pricebook_services.py` | **0** | one-shot migration | — | historical; DELETE |

### Residue to UPDATE (not orphan — no DELETE without wiring change)

| Location | Residue | Action in B |
|---|---|---|
| `config.py` | `SERVICE_SELECT_LLM_ON`, `SERVICE_SELECT_LLM_MODEL`, `BRAND_FILTER_ON`, `PRICE_STRICT_SERVICE_ON` | remove dead flags (island-only consumers) |
| `session.py` | `last_patient_situation`, `patient_situation_turn_age`, get/set/clear APIs | remove island session carry |
| `core/routing.yaml` | `patient_situation:` thresholds block | remove stale thresholds |
| `core/metadata_first_observability.py` | `patient_situation_*` telemetry keys | remove island observability fields |
| `scripts/lint_pricebook.py` | validates root catalog + `pricebook/**` via `contracts/pricebook.py` | rewrite to `target_response/**` + response schema |
| `.github/workflows/ci.yml` | runs legacy price tests + `lint_pricebook` on old paths | swap to validator + target lint; drop deleted tests |
| `evals/v5/run_patient_scope_shadow_eval.py` | reads `get_last_patient_situation` | remove/stub legacy carry simulation |

### KEEP firewall (do not delete in B)

**Client data**

- `clients/demo/target_response/**` (canonical authority)
- `clients/demo/md/**`
- `clients/demo/doctor_catalog.json`
- `clients/demo/brand.yaml` (clinic/widget identity — **not** implant brands)
- `clients/demo/clinic_policies.yaml`
- `clients/demo/features.yaml`
- `clients/demo/lead_config.yaml`
- `clients/demo/tone.yaml`
- `clients/demo/ui.yaml`
- `clients/demo/video_catalog.yaml`
- `clients/demo/widget_config.json`

**Product core (target path)**

- `core/target_client_data.py`, `core/target_query_cues.py`
- `core/catalog_match.py`
- `core/target_family_price_resolution.py`
- `core/target_scope_aware_selection.py`
- `core/target_scope_aware_price_package.py`
- `core/target_offer_projection.py`
- `core/target_offer_price_reachability.py`
- `core/target_explicit_service_price_lookup.py`
- `core/attribute_followup.py` (vague-attribute / explicit-object helpers; not legacy price island)
- `core/price_ref_routing.py` — **KEEP** (`core/content_linter.py`, `scripts/lint_content.py`)
- `core/response_schema_loader.py`, `core/target_runtime_client_context.py`
- AC1→AC3, A9 authority, typed UI `TurnFrame`, Composer, Verifier stacks
- frozen S/A9/Retry/W1b artifacts

**Contracts (A9 / TurnFrame — not legacy island)**

- `contracts/patient_situation.py` — **HISTORICAL COMPATIBILITY KEEP** (scalar kinds for planner bridge)

## Historical A9 boundary (binding)

| Surface | Decision | Rationale |
|---|---|---|
| Legacy detect/carry stack (`patient_situation*.py`, `patient_scope_cues.py`, session carry APIs, `query_selector` price-scope merge) | **DELETE NOW** in B | zero product consumers post-A; not frozen acceptance authority |
| Scalar `patient_situation` bridge in `core/turn_frame_from_raw.py` + planner prompt enum in `core/turn_planner_llm.py` | **HISTORICAL COMPATIBILITY KEEP** in B | live planner/TurnFrame path; frozen A9 contracts reference scalar kind projection |
| Removing scalar bridge / retuning A9 matrices | **Future checkpoint (NOT B)** | explicit owner scope; NO A9 tuning in this milestone |

## Data-retention proof (canonical target schema)

**Preserved in `target_response/**` (verified @ Checkpoint A governance):**

- all 21 service IDs; `name`, aliases, `active`, `content_ref`
- 31 offers: exact prices/ranges, billing units, package composition, payment stages
- 6 commercial facts with dates and applicability
- brand catalog + aliases (supersedes `price_brand_aliases.json`)
- doctor service links via `doctor_catalog.json` + content refs
- marketing governed refs in `target_response/marketing.yaml`

**Conscious retire (do not migrate into new schema):**

- `price_key`, `price_ref`, `price_display`, `response_mode`, legacy route/aspect mechanics
- root service `facts` as second content store
- 24 ungrounded `clinic_proof` / `consult_reasons` strings from root `marketing.yaml`

## Authoring closeout design (B implementation — blocked)

1. `docs/CLIENT_PACK_AUTHORING.md` — one edit → one file table; new-clinic checklist; ID consistency; no legacy mirrors.
2. `scripts/validate_client_pack.py` — offline, no network/LLM, `client_id`/path arg, strict schema + duplicate keys, MD/doctor/offer/fact/brand/marketing refs, path-specific errors, exit ≠ 0 on invalid.
3. `clients/_template/` — structural parity with canonical pack; placeholder data validates (or explicit scaffold mode); no demo-specific IDs/brands.
4. Non-demo sparse fixture — distinct service IDs/brands/topics; **no** root legacy mirrors; passes validator (`tests/test_final_client_pack_data_convergence_sparse_pack.py` extended + dedicated validator tests).

## Exact classification counts

| Class | Count |
|---|---|
| **DELETE** legacy data files | **27** |
| **DELETE** legacy modules/scripts/contracts | **21** |
| **DELETE** legacy-only tests | **16** |
| **UPDATE** product/config/CI/scripts/tests | **18** |
| **CREATE** authoring/validator/template/tests | **6** |
| **KEEP** firewall paths | **see TASK.md KEEP list** |

## STOP law

This audit + TASK Checkpoint B governance authorize **governance PRE-CODE only**.
Implementation/delete begin only after independent B PRE-CODE checker ✅ and explicit implementation GO.
