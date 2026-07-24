# TASK — W1 Family price overview + widget contract fixes

**Baseline:** `codex/stage-a` / `b09cb45` (C2e CLEANUP_SERIES_COMPLETE closeout) · **NO LIVE / NO LLM / NO A9 changes**

**Authority:** Owner-approved W1 (`OWNER APPROVED: начать W1`, 2026-07-24).

## Goal

Fix three confirmed user-facing defects **systemically** (no implantation-only hacks, no RAG):

1. **A — Family price overview:** vague family price questions (`topic` + price intent + `service_id=null`) materialize a multi-service price overview instead of terminal defer.
2. **B — Single follow-up channel:** target runtime exposes follow-up controls only via `payload.quick_replies`; widget fail-safe deduplicates by `ref`.
3. **C — Terminal/error attribution:** terminal/defer/error/verifier-block/unknown-ref responses show plain bot name only; materialized content/price/doctors keep «по материалам клиники».

**Target chain (unchanged architecture):**

```text
HTTP → shared guards → one Planner LLM → native TurnFrame → session hydration
→ medical boundary → FullContext → Composer → lightweight Verifier → widget/session
```

## Process (mandatory)

1. **Verify baseline:** clean tree; `HEAD == origin/codex/stage-a` @ `b09cb45`.
2. **Read:** `TASK.md`, `docs/ARCH_TARGET_DESIGN.md`, `docs/STRANGLER_ROADMAP.md`, `REVIEW_CHECKLIST.md`, `.cursor/rules/00-guardrails.mdc`.
3. **Read-only seam audit** (below) — completed in governance commit.
4. **Governance commit:** only `TASK.md` → push → **PRE-CODE checker ✅**
5. If PRE-CODE ❌: STOP, fix only `TASK.md`, repeat PRE-CODE until ✅.
6. **W1 implementation** → focused + neighbor + wide offline tests → **COMPLETION checker ✅** → commit + push → clean/synced → **STOP** (no live widget re-test without owner).

No product WIP before PRE-CODE ✅. No advance on checker ❌.

## Forbidden

- Live/LLM runs; A9 matrix/harness rerun; frozen A9 artifact edits
- Merge/push to `main`; product authority changes
- Hardcode имплантации/протезирования or demo-specific phrases in shared `core/`
- Зашитые готовые тексты ответов по отдельным услугам (Composer writes freely from evidence)
- New retriever/RAG/per-document routing; per-MD thematic routers
- Changing existing exact price amounts, doctors, marketing/CTA semantics
- Weakening Verifier or numeric grounding; ослабление acceptance tests
- Temporary compatibility fallback; duplicate follow-up channel restoration
- Files outside allowlist without governance correction + PRE-CODE ✅
- Protected acceptance spec/golden/target/current edits to greenwash

## Allowed

- Governance `TASK.md`; PRE-CODE / COMPLETION checkers (read-only)
- Product code and offline tests per allowlist below
- Synthetic temporary client fixture (non-demo service IDs/tags/prices)
- Push only to `origin/codex/stage-a`

---

## Read-only seam audit (baseline `b09cb45`)

### A. Family price overview — confirmed gap

| Seam | File | Finding |
|------|------|---------|
| Planner intent | `core/turn_planner_llm.py:45–58` | Prompt instructs `service_id=null` for vague implantation price → «обзор протоколов». |
| Dispatch gate | `core/target_turn_frame_dispatch.py:263–275` | `service_id=null` + price component → `terminal defer`; exception only for content-only (`_is_fullcontext_content_only_components`). |
| Regression test | `tests/test_target_turn_frame_dispatch.py:127–134` | `test_missing_service_id_returns_terminal_defer` encodes current (wrong for family price) behavior — **update** to new contract. |
| Runtime wiring | `core/target_runtime_turn.py:135–175` | `strategy_context` from `resolve_target_runtime_strategy_context(service_id=turn_frame.service_id)` → empty when `service_id=null`. |
| Evidence path | `core/target_offline_response_assembly.py`, `core/service_data_context.py` | **Single-service** only (`service_term` → one `service_id`). No multi-service family evidence. |
| Price authority | `clients/demo/target_response/pricebook/` | Canonical structured offers; loaded via `ResponseSchemaBundle`. |
| Membership data | `clients/demo/target_response/service_catalog.json` | Each service has `family`, `roles`, `content_ref`. Topic derivable as `content_ref.split("__")[0]` (e.g. `implantation`, `prosthetics`). |
| Topic taxonomy | `core/topic_taxonomy.py` | MD-derived allowed topics for planner; **not** family membership. |
| Legacy planner catalog | `clients/demo/service_catalog.json` | Planner guards only; **not** price overview authority. |
| Ordering | `clients/demo/target_response/clinic_strategy.yaml` | `default_service_priorities: {}`; rules have `service_priorities` per patient match — usable for tie-break, not required for v1 if catalog order + `roles` suffice. |
| Catalog order | `core/response_schema_loader.py` | JSON key order preserved in `bundle.services` dict insertion order. |

**Root cause:** dispatch treats `service_id=null` + price as unmaterializable → terminal defer, despite planner promising family overview.

**Proposed mechanism (v1):**

```text
price intent + usable topic + service_id=null
→ resolve family services by topic prefix on content_ref (canonical membership)
→ filter: active, ≥1 priced offer in target pricebook bundle
→ deterministic order: role rank (protocol > advanced_protocol > supporting > none),
  then catalog order; cap at 4
→ assemble multi-service structured price evidence
→ Composer (FullContext + evidence) → Verifier (multi-offer grounding) → materialize
```

**Canonical membership source (owner decision in audit):** `clients/{client}/target_response/service_catalog.json` — filter services where `content_ref` topic prefix matches `turn_frame.topic`. Use `family` for consistency checks only; **no** demo hardcoded topic→family table in `core/`.

**Ordering v1:** role rank + catalog JSON key order. If a future client cannot determine honest order from these two alone → **STOP** and propose minimal `family_price_overview_priorities` config field (governance amendment) before schema change.

### B. Follow-up duplication — confirmed gap

| Seam | File | Finding |
|------|------|---------|
| Payload writer | `core/target_runtime_widget.py:117–127` | `quick_replies` built from followups; **same list** copied to `meta.followups`. |
| UI family | `core/target_runtime_widget.py:73` | `ui_source_family: "target_fullcontext"` — **not** in `policy._UI_FAMILIES` → falls through to `md_navigation`. |
| Screen limits | `ux_builder.normalize_policy_payload:45–53` | `md_navigation` → max 1 quick_reply + up to 2 meta followups = **3 visible buttons**. |
| Widget merge | `static/widget/widget.js:1394–1399` | `renderInlineLinks` concatenates `meta.followups` + `quickReplies` without dedup. |
| Session storage | `core/target_runtime_turn.py:57–68` | Reads **only** `quick_replies` for session — correct canonical channel once duplication removed. |

**Root cause:** dual channel (`quick_replies` + `meta.followups`) + unknown UI family → policy keeps both lists; widget renders both.

### C. Terminal attribution — confirmed gap

| Seam | File | Finding |
|------|------|---------|
| Widget resolver | `static/widget/widget.js:411–419` | `resolveTurnAttributionKind` → `"content"` unless route in `PLAIN_ATTRIBUTION_ROUTES` or lead flow. |
| Target terminal routes | `core/target_runtime_widget.py:197,213,227` | `target_fullcontext_terminal_*`, `target_fullcontext_error`, `target_fullcontext_verifier_blocked` **not** in plain set → show «по материалам клиники». |
| Unknown ref | `core/target_runtime_followup_nav.py:74` | Same `target_fullcontext` family; should be plain. |

**Preferred fix:** server sets explicit `meta.attribution_kind: content | plain | lead`; widget prefers it; route-based fallback retained for shared guards.

### D. Blast-radius map (must stay green)

- Planner/TurnFrame generic price (`tests/test_turn_planner_llm.py`, `tests/test_turn_frame_from_raw.py`)
- `target_turn_frame_dispatch` + bound response pipeline
- Family evidence assembly (new)
- Composer request/evidence + numeric/semantic Verifier
- Exact service price + payment stages (All-on-4 regression)
- Target runtime/session/ref navigation (`tests/test_s61_*`, `tests/test_s62_*`, `tests/test_s63_*`)
- Widget payload + `policy.py` / `ux_builder.normalize_policy_payload`
- `/ask` + `/ask/stream` offline fake backends
- Import firewall; frozen S47/S50/S53/S55/S58/S62/S63/S66 byte-identical

---

## Workstream A — Family price overview

### A. Requirements

1. **Universal:** works for `implantation`, `prosthetics`, `treatment`, and other families with multiple priced services in client pack — no demo phrase lists in shared core.
2. **Membership:** `target_response/service_catalog.json` + topic prefix on `content_ref`; sums from `target_response/pricebook` only.
3. **No treatment choice:** overview lists multiple methods with structured «от …»; does not pick `classic`/All-on-4 for patient.
4. **v1 cap:** ≤4 priced services per family; deterministic order (role rank → catalog order); no LLM ranking.
5. **Composer text:** free-form from evidence (not hardcoded templates).
6. **Prosthetics:** only prosthetics-topic services per catalog (коронки, съёмное, имплант-поддерживаемое — per demo data).
7. **Strict grounding:** all amounts in structured evidence; Verifier receives same multi-offer evidence; FullContext for explanation only.
8. **Edge cases:**
   - 1 priced service in family → normal single-service materialized price path
   - 0 priced services → honest controlled response, no invented prices
   - exact `service_id` → unchanged existing path
   - brand-filter without exact service → no wrong price
   - medical boundary semantics unchanged
9. **No new follow-up routing protocol** for family overview in v1 — text overview only; preserve exact-service follow-ups on precise price path.

### A. Implementation seams (allowlist targets)

| Area | Action |
|------|--------|
| `core/target_turn_frame_dispatch.py` | New branch: price + usable topic + `service_id=null` → materialize family overview (not defer). |
| `core/target_family_price_overview.py` | **new** — resolve services, order, build multi-offer evidence package (pure, offline-testable). |
| `contracts/target_family_price_overview.py` | **new** — typed contracts for family overview selection/evidence. |
| `core/target_offline_response_assembly.py` / `core/target_spec_offline_response_package.py` | Wire family overview into assembly when spec indicates multi-service price. |
| `core/target_composer_request.py` | Multi-service offer evidence blocks for Composer + Verifier. |
| `core/target_scoped_response_evidence.py` | Scope records for multiple offers (if needed for verifier). |
| `core/target_response_verifier.py` | Accept multi-offer family evidence; block foreign amounts. |
| `core/target_response_policy.py` / `contracts/target_response_spec.py` | Spec flag or mode for `family_price_overview` (no per-service `service_id`). |
| `tests/test_w1_family_price_overview_offline.py` | **new** — focused acceptance + synthetic client fixture. |
| `tests/test_target_turn_frame_dispatch.py` | Update defer test → family materialize for price+topic null service. |
| Neighbor tests | `test_demo_target_turn_frame_bound_response.py`, `test_vague_price_followup.py`, `test_demo_target_price_offers.py` — keep green. |

### A. Demo acceptance cases

| Case | Expect |
|------|--------|
| «Сколько стоит имплантация?» | materialized; ≥2 implantation-topic priced variants; no method chosen for patient; no irrelevant services; not terminal/defer |
| «Сколько стоит протезирование?» | materialized; multiple prosthetics-topic variants; structured sums only |
| «Сколько стоит All-on-4?» | exact single-service price path unchanged (green) |
| «А сколько стоит?» after All-on-4 focus | session hydration + exact price path unchanged (green) |
| Synthetic temp client fixture | different service IDs/tags/prices; overview without demo hardcode |

---

## Workstream B — Single follow-up channel

### B. Requirements

1. **Canonical channel:** `payload.quick_replies` only for target runtime user controls.
2. **No duplicate in meta:** remove `meta.followups` copy; observability may keep `followup_count` / `followup_source: quick_replies`.
3. **Widget dedup:** fail-safe deduplicate merged controls by `ref` in `renderInlineLinks` (or shared helper).
4. **UI source family:** map target materialized price → `price_navigation`; content → `md_navigation`; doctors → `doctor_navigation`; terminal/error → `guided_fallback` or plain (no nav buttons). Remove unrecognized `target_fullcontext` as UI family.
5. **Session/ref-click:** continue via `quick_replies`; screen limits apply once.

### B. Acceptance

- All-on-4 price: exactly **two unique** buttons: «Оплата по этапам» and «Что входит»; neither duplicated; ref-click on target path.
- Content follow-ups unchanged.
- Session stores full canonical list.
- `normalize_policy_payload` screen limits applied once.

### B. Implementation seams

| File | Change |
|------|--------|
| `core/target_runtime_widget.py` | Stop writing `meta.followups`; set correct `ui_source_family` + `attribution_kind` per response kind. |
| `core/target_runtime_followup_nav.py` | Plain attribution + guided UI family on unknown ref payload. |
| `policy.py` | Recognize target price/content/doctor routes if needed for inference fallback. |
| `static/widget/widget.js` | Dedup by `ref`; honor `meta.attribution_kind` first. |
| `static/widget/followup_controls.js` | **new** (optional) — pure merge+dedup helper for testability. |
| `tests/test_w1_widget_followup_contract_offline.py` | **new** — behavior-level: payload contract + dedup (Node subprocess or DOM fixture; not substring-only). |
| `tests/test_ui_source_policy.py` | Target price payload → `price_navigation`, no followups in meta. |
| `tests/test_s61_correction_target_runtime.py`, `tests/test_s62_correction_offline.py`, `tests/test_s63_correction_offline.py` | All-on-4 two-button regression. |

---

## Workstream C — Terminal/error attribution

### C. Requirements

1. **Materialized** content/price/doctors → `attribution_kind: content` → «Надежда · по материалам клиники».
2. **Lead flow** → `attribution_kind: lead` → «Запись на консультацию».
3. **Plain only** (bot name): `target_fullcontext_terminal_clarify`, `target_fullcontext_terminal_defer`, `target_fullcontext_boundary_uncertain`, `target_fullcontext_error`, `target_fullcontext_verifier_blocked`, unknown follow-up/ref controlled response.
4. Terminal payloads: no follow-up/CTA.
5. `/ask` and `/ask/stream` identical attribution.

### C. Implementation seams

| File | Change |
|------|--------|
| `core/target_runtime_widget.py` | Set `meta.attribution_kind` on all payload kinds. |
| `core/target_runtime_followup_nav.py` | `attribution_kind: plain` on unknown ref. |
| `static/widget/widget.js` | `resolveTurnAttributionKind` checks `meta.attribution_kind` first; extend route fallback for target terminal routes. |
| `tests/test_w1_attribution_contract_offline.py` | **new** — materialized vs terminal/error matrix via fake backends (`/ask` + `/ask/stream`). |

---

## W1 allowlist (implementation)

**Governance correction (2026-07-24, post-implementation):** расширение allowlist для обязательных companion-файлов и frozen-shape тестов, вытекающих из `family_price_overview_topic` / `content_ref` membership / pipeline assembly clamp. Без изменения продуктовой семантики W1.

### New files

| File |
|------|
| `core/target_family_price_overview.py` |
| `contracts/target_family_price_overview.py` |
| `contracts/target_service_content_topic.py` |
| `tests/test_w1_family_price_overview_offline.py` |
| `tests/test_w1_widget_followup_contract_offline.py` |
| `tests/test_w1_attribution_contract_offline.py` |
| `static/widget/followup_controls.js` (if extracted for behavior test) |

### Modify

| File |
|------|
| `core/target_turn_frame_dispatch.py` |
| `core/target_offline_response_assembly.py` |
| `core/target_spec_offline_response_package.py` |
| `core/target_offline_response_package.py` |
| `core/target_response_materialization_plan.py` |
| `core/target_composer_request.py` |
| `core/target_scoped_response_evidence.py` |
| `core/target_response_verifier.py` |
| `core/target_response_policy.py` |
| `core/target_policy_bound_verified_response_pipeline.py` (clamp marketing/CTA/consultation_close for family overview) |
| `contracts/target_response_spec.py` |
| `contracts/target_response_policy.py` |
| `contracts/target_turn_frame_dispatch.py` (only if dispatch result type needs extension) |
| `core/target_runtime_widget.py` |
| `core/target_runtime_followup_nav.py` |
| `policy.py` |
| `static/widget/widget.js` |
| `tests/test_target_turn_frame_dispatch.py` |
| `tests/test_ui_source_policy.py` |
| `tests/test_demo_target_turn_frame_bound_response.py` |
| `tests/test_vague_price_followup.py` |
| `tests/test_s61_correction_target_runtime.py` |
| `tests/test_s61_target_fullcontext_runtime.py` |
| `tests/test_s62_correction_offline.py` |
| `tests/test_s63_correction_offline.py` |
| `tests/test_s65_authority_switch_offline.py` |
| `tests/test_target_fullcontext_content_response.py` |
| `tests/test_demo_target_price_offers.py` |
| `tests/test_turn_planner_llm.py` (only if dispatch integration mocks need update) |
| `tests/test_c2_import_firewall_offline.py` (extend if new public surface) |
| `tests/test_c2c_dead_clarify_offline.py` (defer regression: low `topic_confidence` after family overview) |
| `tests/test_target_offline_response_assembly.py` (frozen shape: `family_service_ids`) |
| `tests/test_target_response_policy.py` (frozen shape: `family_price_overview_topic`) |
| `tests/test_target_response_spec.py` (frozen shape: `family_price_overview_topic`) |

### Explicit KEEP (do not change)

- `clients/demo/target_response/pricebook/**` amounts and offer IDs
- `clients/demo/target_response/marketing.yaml`, doctor catalog
- A9 / frozen eval artifacts
- Planner prompt semantics for `service_id=null` on vague price (already correct)
- Medical boundary / urgent hard-stop ordering

---

## STOP conditions

STOP and escalate to owner if:

1. Family membership requires new complex data schema beyond `service_catalog.json` topic prefix + `family`
2. Honest deterministic service order impossible with role rank + catalog order (propose config field first)
3. Implementation requires changing existing price amounts or marketing/CTA
4. New follow-up routing protocol needed for family overview buttons
5. A9 or frozen artifact byte change required
6. Live/LLM required to validate
7. Checker ❌ requires scope beyond allowlist

---

## Tests (mandatory)

### Focused W1 block

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-w1-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_w1_family_price_overview_offline.py `
  tests/test_w1_widget_followup_contract_offline.py `
  tests/test_w1_attribution_contract_offline.py `
  tests/test_target_turn_frame_dispatch.py `
  tests/test_ui_source_policy.py `
  tests/test_demo_target_turn_frame_bound_response.py `
  tests/test_vague_price_followup.py `
  tests/test_demo_target_price_offers.py `
  -q
```

### Neighbor target tests (S45/S46/S56/S61/S63/S65)

```powershell
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_s61_target_fullcontext_runtime.py `
  tests/test_s61_correction_target_runtime.py `
  tests/test_s62_correction_offline.py `
  tests/test_s63_correction_offline.py `
  tests/test_s65_authority_switch_offline.py `
  tests/test_target_fullcontext_content_response.py `
  tests/test_s56_missing_base_composer_guard.py `
  tests/test_turn_planner_llm.py `
  tests/test_turn_frame_from_raw.py `
  -q
```

### Wide safe-offline (corrected C2e command; no live, no A9 harness)

```powershell
python -m pytest -p no:cacheprovider --basetemp $bt tests/ `
  --ignore=tests/test_composer_live_eval.py `
  --ignore=tests/test_emotion_route_matrix.py `
  --ignore=tests/test_medical_boundary_eval_live_cli.py `
  --ignore=tests/test_fullcontext_quality_eval_live_wiring.py `
  --ignore=tests/test_s62_target_runtime_live_harness.py `
  --ignore=tests/test_s63_target_runtime_live_harness.py `
  --ignore=tests/test_s66_default_authority_live_harness.py `
  --ignore=tests/test_patient_scope_shadow_eval_contract.py `
  --ignore=tests/test_patient_scope_shadow_eval_v2_contract.py `
  --ignore=tests/test_patient_scope_native_contract_spec.py `
  --ignore=tests/test_topic_shadow_eval_contract.py `
  --ignore=tests/test_topic_shadow_attempt_eval_contract.py `
  -q
```

### Integrity

```powershell
python -m pytest -p no:cacheprovider --collect-only -q 2>&1 | Select-Object -Last 3
python -c "from evals.v5.fullcontext_quality_eval_contract import assert_frozen_prior_artifacts_unchanged; from evals.v5.s66_default_authority_live_contract import assert_frozen_s62_live_artifacts_unchanged, assert_frozen_s63_live_artifacts_unchanged; from tests.test_s67_legacy_isolation_offline import _assert_frozen_s66_artifacts_unchanged; assert_frozen_prior_artifacts_unchanged(); assert_frozen_s62_live_artifacts_unchanged(); assert_frozen_s63_live_artifacts_unchanged(); _assert_frozen_s66_artifacts_unchanged(); print('frozen OK')"
git diff --check
```

---

## Commits (minimum)

1. `W1 governance TASK` (this commit)
2. `W1: family price overview + widget contract fixes` (after COMPLETION checker ✅)

Each: tests → checker ✅ → commit → push → clean/synced.

---

## Completion record (fill after COMPLETION ✅)

| Field | Value |
|-------|-------|
| PRE-CODE | ✅ (governance commit `3c21237`) |
| Baseline | `b09cb45` |
| COMPLETION checker | pending re-run after governance correction |
| HEAD | (uncommitted WIP) |
| pytest focused W1 + neighbors | 278 passed, 1 skipped |
| pytest wide safe-offline | 2084 passed, 2 skipped |
| collect-only | 2283 collected |
| frozen S47/S50/S53/S55/S58/S62/S63/S66 | frozen OK |
| git diff --check | clean (CRLF warnings only) |
| NO LIVE / NO LLM / NO A9 | |

**STOP after W1 COMPLETION — live widget re-test only with separate owner approval.**
