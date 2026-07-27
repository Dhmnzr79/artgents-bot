# TASK — A9R Patient scope authority re-audit (governance)

**Status:** governance checkpoint only · **NO LIVE / NO LLM / NO PRODUCT AUTHORITY**

**Product baseline:** `codex/stage-a` @ `b35ed1c` (AC3 complete) · AC3 product HEAD `aa8e6dd`

**Authority:** `docs/A9R_GOVERNANCE.md`; канон scope pipeline: `docs/ARCHITECTURE_CONVERGENCE.md`, `docs/ARCH_TARGET_DESIGN.md`.

**AC3 complete:** `aa8e6dd` — scope-aware price runtime wired; free-text scope deferred here.

---

## Goal (A9 — not enabled in A9R)

Extract **neutral patient situation facts** from free text via existing planner `TurnFrame.patient_scope`, project into the **same** `EffectiveScope` used by AC1–AC3. **No second scope mechanism.**

| Layer | Role |
|-------|------|
| A9 | Extract facts only (extent, jaw, stage, modifiers) |
| AC1 | Typed UI + session `patient_facts` + `resolve_effective_scope` |
| AC2 | Sole applicability / ranking / offers |
| AC3 | `ResponseStage` + scope/stage UI |
| Medical boundary | Separate; not patient scope |

**Allowed facts (explicit patient statements only):**

- `extent`: `one_tooth | few_teeth | full_arch | unknown`
- `jaw`: `upper | lower | both | unknown` (planner/shadow today; `EffectiveScope.jaw` — A9R1 decision)
- `stage`: `natural_tooth_present | extraction_context | implant_placed | unknown`
- modifiers: `reported_bone_deficit` when explicitly reported

**Hard negatives:**

- No scope from service name alone («Что такое All-on-4?», «Сколько стоит All-on-4?»)
- No `implant_placed` from bare «имплант»
- No regex / phrase dictionaries / client disease rules
- No diagnosis, treatment choice, price, or service_id inference

---

## Source priority (target merge — A9R3 only)

1. typed `UiScopeAction` (current turn)
2. typed `UiStageAction` (current turn)
3. confident current-turn `TurnFrame.patient_scope` projection (A9)
4. fresh session `patient_facts` (same topic)
5. unknown

**Correction:** explicit current-turn correction replaces prior session fact for the axis. Uncertain/conflicting extraction **must not** silently overwrite session.

---

## Read-only seam audit summary

See `docs/A9R_GOVERNANCE.md` for full audit. Headlines @ `aa8e6dd`:

| Finding | Detail |
|---------|--------|
| Producers | Planner LLM → `build_turn_frame_from_raw` (native + scalar bridge) |
| Shadow consumers | v1/v2 eval harnesses, firewall tests |
| Product consumers | **None** — `TurnFrame.patient_scope` not read in target runtime |
| AC1 path | `resolve_effective_scope` — UI + session only |
| Planner | Single `plan_turn_attempt()` — **reuse, no second LLM** |
| Pause reason | v1 live 0 positive axes; authority forbidden; AC3 deferred free-text |
| v1/v2 matrices | Fit shadow measurement; **immutable**; do not edit |
| Jaw gap | `PatientScopeFrame.jaw` exists; `EffectiveScope` has no `jaw` yet |
| Stage gap | `natural_tooth_present` in AC2 `PatientStage` but not in `PatientCareStage` — A9R1 projection decision |

**Future wiring point:** `core/target_effective_scope.py::resolve_effective_scope` — slot after UI actions, before session (A9R3).

---

## Gates (mandatory sequence)

| Gate | Deliverable | Authority |
|------|-------------|-----------|
| **A9R** (this) | Audit, TASK, docs, frozen A9R matrix, PRE-CODE | forbidden |
| **A9R1** | Offline projection + merge module + deterministic harness for A9R matrix | forbidden |
| **A9R2** | One owner-approved live eval via existing planner; new raw artifact | measurement only |
| **A9R3** | `resolve_effective_scope` authority wiring | **owner GO (2026-07-25)** — measured risk accepted; model-tuning stopped |
| Post-authority | Widget E2E offline (+ optional live) | separate TASK |

---

## A9R frozen eval matrix

**New file (does not modify v1/v2):** `evals/v5/demo/patient_scope_a9r_matrix.json`

Schema: `a9r.patient_scope_authority_prep.v1` · frozen blob `36d137112007a3fb0a96ad0759aa111af6115a35`

**Mandatory scenarios covered:**

| # | Scenario |
|---|----------|
| 1 | «Сколько стоит имплантация всей челюсти?» → `full_arch` |
| 2 | «Нужно восстановить один зуб» → `one_tooth` |
| 3 | «Нет нескольких зубов» → `few_teeth` |
| 4 | upper / lower / both jaw |
| 5 | «Имплант уже установлен» |
| 6 | «Свой зуб ещё сохранился» → `natural_tooth_present` |
| 7 | Correction «Нет, речь об одном зубе» after prior scope |
| 8 | Typos / colloquial phrasing |
| 9 | All-on-4 info — no scope |
| 10 | All-on-4 price — no invented scope |
| 11 | «имплант» word — no stage inference |
| 12 | Ambiguous / conflicting messages |
| 13 | Topic change, stale session, reset, SID isolation |
| 14 | UI click priority over free-text |

Contract: `tests/test_patient_scope_a9r_matrix_contract.py`

---

## Allowlist (A9R governance commit only)

| File | Purpose |
|------|---------|
| `TASK.md` | This checkpoint |
| `docs/A9R_GOVERNANCE.md` | Full read-only audit |
| `docs/STRANGLER_ROADMAP.md` | A9R checkpoint + gate sync |
| `docs/ARCH_TARGET_DESIGN.md` | EffectiveScope priority + A9 slot |
| `docs/ARCHITECTURE_CONVERGENCE.md` | AC3 done + A9R next |
| `evals/v5/demo/patient_scope_a9r_matrix.json` | New frozen matrix |
| `tests/test_patient_scope_a9r_matrix_contract.py` | Matrix schema + hash |

**Forbidden in A9R:**

- Product code (`core/target*.py`, `orchestration/*.py`, runtime wiring)
- Live / LLM eval runs
- Editing v1/v2 shadow matrices, v1 audit, `eval_patient_scope_a9_last.txt`
- `TurnFrame.patient_scope` product read
- Regex scope parsers; A9 harness wired into product path
- AC1–AC3 bypass or W1b restore

---

## Tests (A9R governance)

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-a9r-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_patient_scope_a9r_matrix_contract.py -q
```

---

## STOP conditions

1. A9R requires product authority or live eval in same commit
2. Requires modifying frozen v1/v2 A9 artifacts
3. Requires regex/phrase scope parser in governance deliverable
4. PRE-CODE checker ❌ without fix path
5. Introduces second scope mechanism parallel to `EffectiveScope`

---

## Process (mandatory)

1. **A9R governance (this commit):** audit + TASK + docs + frozen matrix → PRE-CODE ✅ → STOP
2. **A9R1:** offline contract/merge/eval — separate owner GO
3. **A9R2:** one live planner eval — separate owner GO + live permission
4. **A9R3:** authority wiring — after quality gates

No implementation before PRE-CODE ✅ on this governance commit.

---

## Completion record

| Field | Value |
|-------|-------|
| AC3 product HEAD | `aa8e6dd` |
| Governance baseline | `b35ed1c` |
| A9R governance HEAD | `02eeee6` |
| A9R matrix blob | `36d137112007a3fb0a96ad0759aa111af6115a35` |
| PRE-CODE | ✅ |
| COMPLETION | N/A (governance only) |

**STOP after governance PRE-CODE ✅. No A9R1 work without separate owner GO.**

---

# TASK — A9R1 Offline projection + per-axis merge (implementation)

**Status:** implementation · **NO LIVE / NO LLM / NO PRODUCT AUTHORITY**

**Governance baseline:** `6c4cac9` (A9R PRE-CODE ✅)

**Owner GO:** A9R1 implementation authorized from governance HEAD `6c4cac9`.

## Goal (A9R1)

Pure offline contract/projection/merge/harness for A9 patient scope. **No product authority.** A9R3 will wire `merge_effective_scope_axes` into `resolve_effective_scope`; A9R1 does **not** read `TurnFrame.patient_scope` in `target_runtime_turn.py`.

| Deliverable | Role |
|-------------|------|
| Extended `EffectiveScope` | `extent`, `jaw`, `stage`, `reported_context`, `topic`, `provenance`, per-axis provenance |
| `PatientCareStage` + planner prompt | add `natural_tooth_present` (same planner call) |
| `project_patient_scope_from_turn_frame` | pure projection; native provenance only; scalar bridge not usable |
| `merge_effective_scope_axes` | per-axis merge: UI scope→extent, UI stage→stage, usable A9→other axes, session fills unknowns |
| `simulate_session_patient_facts_after_turn` | offline session-write preview only |
| Harness | frozen `patient_scope_a9r_matrix.json` + deterministic fake planner payloads |

**Merge rules:** unknown current-turn axis must not erase session; explicit A9 correction replaces same axis; `jaw=both` preserved; `reported_bone_deficit` → `reported_context`; no confidence thresholds.

## Allowlist (A9R1 implementation)

| File | Purpose |
|------|---------|
| `contracts/effective_scope.py` | Extended scope + axis provenance |
| `contracts/patient_scope_projection.py` | Projection types |
| `contracts/turn_frame.py` | `natural_tooth_present` in `PatientCareStage` |
| `core/target_patient_scope_projection.py` | Pure projection API |
| `core/target_effective_scope_merge.py` | Pure merge + offline session simulate |
| `core/target_effective_scope.py` | `SessionPatientFacts` jaw/reported_context read/write |
| `core/target_strategy_context.py` | `jaw=both` → `None` for AC2 applicability |
| `core/turn_planner_llm.py` | Planner prompt `natural_tooth_present` |
| `tests/test_patient_scope_projection.py` | Projection unit tests |
| `tests/test_effective_scope_merge.py` | Per-axis merge unit tests |
| `tests/test_a9r1_offline_harness.py` | Matrix harness |
| `TASK.md` | Completion record |

**Forbidden in A9R1:** `target_runtime_turn.py` wiring; product session writer; live/LLM eval; regex scope parser; editing frozen A9 v1/v2/A9R matrices or W1b/S-series artifacts.

## Tests (A9R1)

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-a9r1-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_patient_scope_projection.py `
  tests/test_effective_scope_merge.py `
  tests/test_a9r1_offline_harness.py `
  tests/test_turn_frame_shadow.py `
  tests/test_patient_scope_a9r_matrix_contract.py `
  tests/test_effective_scope_contract.py `
  tests/test_ac3_scope_price_flow_offline.py `
  tests/test_target_strategy_context.py `
  tests/test_target_scope_aware_selection_offline.py `
  tests/test_ui_scope_click_http_offline.py `
  tests/test_session_patient_facts_offline.py -q
```

## STOP conditions (A9R1)

1. Requires wiring A9 into product runtime or `resolve_effective_scope`
2. Requires modifying frozen v1/v2/A9R matrices, W1b snapshot, S-series artifacts
3. Requires live eval or second LLM
4. Scalar bridge becomes merge authority

**STOP after A9R1 COMPLETION ✅. A9R2 starts only after separate owner GO.**

## Completion record (A9R1)

| Field | Value |
|-------|-------|
| Governance HEAD | `6c4cac9` |
| PRE-CODE | ✅ (A9R governance) |
| COMPLETION | ✅ |
| A9R1 product HEAD | `f6cb0b6` |
| Tests | 129 passed (focused A9R1 + AC1–AC3 neighbors) |
| Matrix blob | `36d137112007a3fb0a96ad0759aa111af6115a35` (unchanged) |
| Import firewall | `test_product_sources_do_not_read_a9_nested_shadow_scope` ✅ |

---

# TASK — A9R2 Patient scope planner live eval (pre-live checkpoint)

**Status:** pre-live governance + offline harness · **NO LIVE / NO LLM / NO PRODUCT AUTHORITY**

**Baseline:** `075722f` (A9R1 COMPLETION ✅)

## Goal (A9R2)

One owner-approved live measurement of existing `plan_turn_attempt()` patient_scope extraction via A9R2 v2 matrix. **Does not enable authority.** Even `AUTOMATED_PASS` → `PENDING_MANUAL_REVIEW` only.

| Deliverable | Role |
|-------------|------|
| `patient_scope_a9r_matrix_v2.json` | Typo fix for `a9r_typo_01_chelyust`; v1 frozen |
| Live harness | Planner-only; 16 cases / 17 calls; retry=0; budget=17 |
| Scoring | Miss vs wrong vs false-positive vs malformed vs correction vs session safety |
| Artifacts | raw, result, manifest, attempt marker, call ledger, manual review |

**Matrix defect fix:** v1 `a9r_typo_01_chelyust` duplicated extent_01 question. v2 question: «Сколько стоит имплантация всей чилюсти?»; expected `full_arch` unchanged.

## Proposed gates (owner approval for live run)

| Gate | Threshold |
|------|-----------|
| wrong non-unknown axis | 0 |
| false-positive on negative/ambiguous | 0 |
| correction success | 100% |
| positive-axis recall | ≥ 0.85 |
| composite exact turn rate | ≥ 0.85 |
| malformed/transport errors | 0 |
| planner calls | ≤ 17 |
| retry | 0 |

## Allowlist (A9R2 pre-live)

| File | Purpose |
|------|---------|
| `evals/v5/demo/patient_scope_a9r_matrix_v2.json` | New frozen v2 matrix |
| `evals/v5/a9r2_patient_scope_live_contract.py` | Artifact paths, budget, gates |
| `evals/v5/a9r2_patient_scope_live_scoring.py` | Miss/wrong/FP/malformed scoring |
| `evals/v5/a9r2_patient_scope_live_harness.py` | Planner harness (injectable) |
| `evals/v5/run_a9r2_patient_scope_live.py` | CLI dry-run only until owner GO |
| `tests/test_patient_scope_a9r_matrix_v2_contract.py` | v2 blob + v1 regression |
| `tests/test_a9r2_patient_scope_live_offline.py` | Offline harness tests |
| `TASK.md` | This checkpoint |

**Forbidden:** live run in this checkpoint; `resolve_effective_scope` wiring; editing v1 A9R matrix; editing A9 shadow v1/v2, W1b, S-series artifacts.

## Tests (A9R2 pre-live)

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-a9r2-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_patient_scope_a9r_matrix_v2_contract.py `
  tests/test_a9r2_patient_scope_live_offline.py `
  tests/test_patient_scope_a9r_matrix_contract.py `
  tests/test_a9r1_offline_harness.py `
  tests/test_patient_scope_projection.py `
  tests/test_effective_scope_merge.py `
  tests/test_turn_frame_shadow.py `
  tests/test_ac3_scope_price_flow_offline.py -q
python evals/v5/run_a9r2_patient_scope_live.py --dry-run
```

## STOP conditions (A9R2)

1. Live LLM invoked in pre-live commit
2. Product authority wiring
3. Modifying frozen v1 A9R matrix or historical artifacts
4. `--live` enabled without separate owner GO

**STOP after PRE-CODE ✅ + offline COMPLETION ✅. Live run is separate owner GO.**

## Completion record (A9R2 pre-live)

| Field | Value |
|-------|-------|
| Baseline HEAD | `075722f` |
| PRE-CODE | ✅ |
| COMPLETION | ✅ |
| A9R2 pre-live HEAD | `82a9829` |
| Matrix v1 blob | `36d137112007a3fb0a96ad0759aa111af6115a35` (unchanged) |
| Matrix v2 blob | `6a9cc6f7a964d0ab3ead79e5dd2cf0a64d743f57` |
| Live blocked | `--live` executed once (owner GO 2026-07-25); **rerun blocked** |
| Live attempt | `AUTOMATED_FAIL` → manual review `PENDING_MANUAL_REVIEW` |
| Planner calls (live) | 17 |
| Audit | `docs/evidence/a9r2/A9R2_LIVE_ATTEMPT_AUDIT.md` |

---

## Completion record (A9R2 live)

| Field | Value |
|-------|-------|
| Baseline HEAD | `6b75214` |
| Live delegate HEAD | `5107a17` |
| Live artifacts HEAD | `5107a17` |
| COMPLETION | ✅ |
| `automated_verdict` | `AUTOMATED_FAIL` |
| `final_verdict` | `PENDING_MANUAL_REVIEW` |
| Authority | not enabled |

---

# TASK — A9R2 post-live offline correction (Checkpoint A + B)

**Status:** governance → implementation · **NO LIVE / NO LLM / NO A9R3**

**Baseline:** `2b8bd23` (A9R2 live complete)

**Frozen live artifacts (byte-identical, do not modify):**
- `evals/v5/artifacts/a9r2_patient_scope_live_raw.json`
- `evals/v5/artifacts/a9r2_patient_scope_live_result.json`
- `evals/v5/artifacts/a9r2_patient_scope_live_attempt.json`
- `evals/v5/artifacts/a9r2_patient_scope_live_call_ledger.jsonl`

Official `AUTOMATED_FAIL` on frozen result is immutable. Diagnostic recompute is read-only; no retroactive PASS.

## Checkpoint A — scorer/audit correction

| Deliverable | Role |
|-------------|------|
| `evals/v5/a9r2_patient_scope_live_scoring.py` | `partial` ≠ transport when patient_scope strict-valid; scope scoring isolated from unrelated axes |
| `evals/v5/a9r2_patient_scope_live_diagnostic_recompute.py` | Read-only recompute from frozen raw |
| `docs/evidence/a9r2/A9R2_POST_LIVE_SCORER_CORRECTION_AUDIT.md` | Corrected metrics + `A9R2_NOT_PASSED` |
| `evals/v5/artifacts/a9r2_patient_scope_live_diagnostic_recompute.json` | New diagnostic artifact (not frozen live) |
| `tests/test_a9r2_scorer_correction_offline.py` | Scorer + frozen raw recompute tests |

**Corrected expectations on frozen raw:** `correction:turn2` → exact `one_tooth`; `ambiguous_01` → all-unknown.

## Checkpoint B — minimal planner prompt calibration

| Deliverable | Role |
|-------------|------|
| `core/turn_planner_llm.py` | Semantic `_PATIENT_SCOPE_PROMPT` only (same single LLM call) |
| `tests/test_a9r2_planner_prompt_calibration_offline.py` | Blast-radius offline fixtures |

**Forbidden:** filters, regex, dictionaries, second classifier, new LLM call, A9R3 wiring, live rerun, editing frozen live artifacts.

## Allowlist (A9R2 post-live)

| File | Checkpoint |
|------|------------|
| `TASK.md` | governance + completion |
| `evals/v5/a9r2_patient_scope_live_scoring.py` | A |
| `evals/v5/a9r2_patient_scope_live_contract.py` | A (frozen SHA pins) |
| `evals/v5/a9r2_patient_scope_live_diagnostic_recompute.py` | A |
| `docs/evidence/a9r2/A9R2_POST_LIVE_SCORER_CORRECTION_AUDIT.md` | A |
| `evals/v5/artifacts/a9r2_patient_scope_live_diagnostic_recompute.json` | A (new) |
| `core/turn_planner_llm.py` | B |
| `tests/test_a9r2_scorer_correction_offline.py` | A |
| `tests/test_a9r2_planner_prompt_calibration_offline.py` | B |
| `tests/test_a9r2_patient_scope_live_offline.py` | A (partial scoring tests) |

## Tests

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-a9r2-post-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_a9r2_scorer_correction_offline.py `
  tests/test_a9r2_planner_prompt_calibration_offline.py `
  tests/test_a9r2_patient_scope_live_offline.py `
  tests/test_patient_scope_projection.py `
  tests/test_ac3_scope_price_flow_offline.py -q
```

**STOP after COMPLETION ✅. A9R2b pre-live is separate owner GO.**

## Completion record (A9R2 post-live)

| Field | Value |
|-------|-------|
| Baseline HEAD | `2b8bd23` |
| Governance HEAD | `1ad3683` |
| PRE-CODE | ✅ (governance) |
| COMPLETION | ✅ |
| Tests | 51 passed, 0 skipped |
| Official live verdict | `AUTOMATED_FAIL` (immutable) |
| Diagnostic status | `A9R2_NOT_PASSED` |
| Corrected transport count | 0 (was 2) |
| Corrected correction success | 1.0 |
| Corrected composite rate | 0.714 (10/14) |
| Remaining neg/amb FP | 3 axes / 2 cases |

---

# TASK — A9R2b patient scope planner live eval (pre-live checkpoint)

**Status:** governance → implementation · **NO LIVE / NO LLM / NO A9R3 / NO PRODUCT AUTHORITY**

**Baseline:** `74e6820` (A9R2 post-live COMPLETION ✅)

**Frozen (byte-identical, do not modify):**
- A9R v2 matrix blob `6a9cc6f7…`
- All `a9r2_patient_scope_live_*` artifacts (SHA256 pins in contract)

## Goal (A9R2b)

Second owner-approved live measurement after independent label review and calibrated planner prompt. Reuses existing A9R2 runner/scorer/planner backend with isolated artifact namespace and matrix v3 (if label fix warranted).

| Deliverable | Role |
|-------------|------|
| `docs/evidence/a9r2/A9R2B_LABEL_REVIEW_AUDIT.md` | Independent semantic label review (no model-output fitting) |
| `patient_scope_a9r_matrix_v3.json` | v3 matrix only if independently justified label fix; v2 frozen |
| `a9r2b_patient_scope_live_contract.py` | Isolated suite/artifact namespace + authority-readiness gates |
| `run_a9r2b_patient_scope_live.py` | CLI dry-run only until owner GO |
| Harness/scorer reuse | Parameterized A9R2 harness; material vs diagnostic FP split |

**Label review outcome (governance):** one v3 fix — `a9r_stage_02_natural_tooth_present` extent `unknown` → `one_tooth` («свой зуб» = explicit singular tooth). All other live-case labels confirmed.

## Proposed authority-readiness gates (A9R2b)

| Gate | Threshold |
|------|-----------|
| wrong concrete axis | 0 |
| material false-positive axis | 0 |
| positive-axis recall | ≥ 0.85 |
| correction success | 100% |
| composite exact turn rate | ≥ 0.85 |
| malformed/transport/provider errors | 0 |
| planner calls | ≤ 17 |
| retry | 0 |

Material axis = extent/jaw/stage (AC2 applicability). `reported_context` FP tracked as diagnostic only.

## Live parameters (future run, not in this checkpoint)

- Planner: existing `plan_turn_attempt()`
- Model: `qwen3.6-flash`
- 16 cases / 17 planner calls
- Composer/Verifier/boundary/runtime = 0
- retry = 0; hard budget 17
- Attempt marker before first provider call; abort after first call blocks rerun
- Manual review required for all turns; `AUTOMATED_PASS` → `PENDING_MANUAL_REVIEW` only

## Artifact namespace (A9R2b)

| Artifact | Path |
|----------|------|
| raw | `a9r2b_patient_scope_live_raw.json` |
| result | `a9r2b_patient_scope_live_result.json` |
| manifest | `a9r2b_patient_scope_live_manifest.json` |
| attempt marker | `a9r2b_patient_scope_live_attempt.json` |
| call ledger | `a9r2b_patient_scope_live_call_ledger.jsonl` |
| manual review | `a9r2b_patient_scope_live_manual_review.json` |

## Allowlist (A9R2b pre-live)

| File | Purpose |
|------|---------|
| `TASK.md` | governance + completion |
| `docs/evidence/a9r2/A9R2B_LABEL_REVIEW_AUDIT.md` | label review |
| `evals/v5/demo/patient_scope_a9r_matrix_v3.json` | frozen v3 matrix |
| `evals/v5/a9r2b_patient_scope_live_contract.py` | A9R2b contract |
| `evals/v5/a9r2_patient_scope_live_harness.py` | parameterized suite reuse |
| `evals/v5/a9r2_patient_scope_live_scoring.py` | material FP + gate param |
| `evals/v5/run_a9r2b_patient_scope_live.py` | CLI |
| `tests/test_patient_scope_a9r_matrix_v3_contract.py` | v3 blob + v2 deep-equality |
| `tests/test_a9r2b_patient_scope_live_offline.py` | offline harness tests |
| `tests/test_a9r2_scorer_correction_offline.py` | frozen A9R2 artifact pins |
| `tests/test_a9r2_planner_prompt_calibration_offline.py` | prompt blast-radius |
| `tests/test_a9r2_patient_scope_live_offline.py` | A9R2 regression |
| `tests/test_patient_scope_a9r_matrix_v2_contract.py` | v2 frozen |
| `tests/test_a9r1_offline_harness.py` | A9R1 neighbor |
| `tests/test_patient_scope_projection.py` | projection |
| `tests/test_ac3_scope_price_flow_offline.py` | AC1–AC3 neighbor |

**Forbidden:** live run; LLM calls; A9R3 wiring; product authority; editing v2 matrix or A9R2 frozen live artifacts; label changes not independently justified.

## Tests

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-a9r2b-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_patient_scope_a9r_matrix_v3_contract.py `
  tests/test_a9r2b_patient_scope_live_offline.py `
  tests/test_a9r2_scorer_correction_offline.py `
  tests/test_a9r2_planner_prompt_calibration_offline.py `
  tests/test_a9r2_patient_scope_live_offline.py `
  tests/test_patient_scope_a9r_matrix_v2_contract.py `
  tests/test_a9r1_offline_harness.py `
  tests/test_patient_scope_projection.py `
  tests/test_ac3_scope_price_flow_offline.py -q
python evals/v5/run_a9r2b_patient_scope_live.py --dry-run
```

**STOP after COMPLETION ✅. A9R2b live is separate owner GO.**

## Completion record (A9R2b pre-live)

| Field | Value |
|-------|-------|
| Baseline HEAD | `74e6820` |
| Governance HEAD | `17a0cd6` |
| PRE-CODE | ✅ (governance) |
| COMPLETION | ✅ |
| Tests | 103 passed, 0 skipped |
| Matrix v2 blob | `6a9cc6f7a964d0ab3ead79e5dd2cf0a64d743f57` (unchanged) |
| Matrix v3 blob | `8ccd9bdc140a192981fcc48ad7ed0367a40b0a84` |
| v3 label delta | `a9r_stage_02` extent `unknown`→`one_tooth` |
| Live blocked | `--live` not enabled |
| A9R2 artifacts | byte-identical |

---

# TASK — A9R2b planner-only live eval (owner GO)

**Status:** owner-approved live · **ONE ATTEMPT ONLY**

**Baseline:** `83709c5` (A9R2b pre-live COMPLETION ✅)

**Owner GO (2026-07-25):** exactly one planner-only live attempt. No owner override. No rerun.

## Frozen inputs

| Item | Value |
|------|-------|
| Matrix v3 blob | `8ccd9bdc140a192981fcc48ad7ed0367a40b0a84` |
| Model | `qwen3.6-flash` |
| Planner calls | ≤ 17 |
| Composer/Verifier/boundary/runtime | 0 |
| Product authority | not enabled |

## Owner ruling: `reported_context`

- **A9R2b:** diagnostic-only axis; not a material gate axis
- **A9R3:** does **not** receive authority from A9
- **Product:** do not write `reported_context` from A9 into session; do not pass to AC2
- Separate authority only after dedicated eval
- `extent` / `jaw` / `stage` remain authority-candidate axes

## Approved gates

| Gate | Threshold |
|------|-----------|
| wrong concrete material axis | 0 |
| material false-positive (extent/jaw/stage) | 0 |
| positive-axis recall | ≥ 0.85 |
| correction success | 100% |
| composite exact rate | ≥ 0.85 |
| malformed/transport/provider errors | 0 |
| calls | ≤ 17 |
| retry | 0 |

Official PASS only when automated gates pass **and** manual review complete for all 17 turns.

## Allowlist (A9R2b live)

| File | Purpose |
|------|---------|
| `TASK.md` | live completion record |
| `evals/v5/a9r2b_patient_scope_live_contract.py` | frozen SHA pins post-live |
| `evals/v5/run_a9r2b_patient_scope_live.py` | live delegate (if needed) |
| `evals/v5/a9r2b_patient_scope_live_manual_review_builder.py` | manual review from result |
| `docs/evidence/a9r2/A9R2B_LIVE_ATTEMPT_AUDIT.md` | audit |
| `evals/v5/artifacts/a9r2b_patient_scope_live_*` | immutable live artifacts |
| `tests/test_a9r2b_patient_scope_live_offline.py` | rerun-block + frozen pins |

**Forbidden:** rerun; owner override; A9R3 wiring; product authority; editing A9R2/v2 frozen artifacts.

## Completion record (A9R2b live)

| Field | Value |
|-------|-------|
| Baseline HEAD | `83709c5` |
| Live GO HEAD | `8782092` |
| PRE-CODE | ✅ (live GO) |
| Live HEAD | |
| `automated_verdict` | `AUTOMATED_FAIL` |
| `final_verdict` | `FAIL` (manual review complete) |
| Manual review | ✅ 17/17 turns |
| Material FP (neg/amb) | 0 |
| Rerun | blocked |

---

# TASK — A9R2b post-live metric correction + A9R2c pre-live

**Status:** COMPLETION ✅ · **NO LIVE / NO LLM / NO A9R3**

**Baseline:** `5cd5015` (A9R2b live complete)

**Frozen (byte-identical):** A9R2/A9R2b live artifacts; matrix v3 blob `8ccd9bdc…`

## Checkpoint A — composite denominator correction

| Deliverable | Role |
|-------------|------|
| `a9r2_patient_scope_live_scoring.py` | Fix composite eligibility: all non-transport turns in numerator/denominator |
| `a9r2b_patient_scope_live_diagnostic_recompute.py` | Read-only recompute from frozen A9R2b raw |
| `A9R2B_POST_LIVE_METRIC_CORRECTION_AUDIT.md` | Official 0.917 inflated vs corrected 0.647; per-axis diagnostic |
| `tests/test_a9r2b_metric_correction_offline.py` | Regression anti-inflation |

**Expected corrected A9R2b:** 11 exact / 17 eligible = 0.647. Per-axis: extent 8/1/1, jaw 3/1 FP, stage 2/3 FP. Official `AUTOMATED_FAIL`/`FAIL` immutable.

## Checkpoint B — A9R2c pre-live

| Deliverable | Role |
|-------------|------|
| `a9r2c_patient_scope_live_contract.py` | Isolated `a9r2c_*` namespace; model `qwen3.7-plus` |
| `run_a9r2c_patient_scope_live.py` | CLI dry-run only |
| `a9r2c_patient_scope_live_manual_review_builder.py` | Manual review builder |
| `tests/test_a9r2c_patient_scope_live_offline.py` | Harness offline |
| `tests/test_a9r2c_planner_blast_radius_offline.py` | Full planner blast-radius |

**A9R2c gates:** `true_composite_exact_turn_rate` ≥ 0.85 (all non-transport turns); material FP = 0; reported_context diagnostic-only.

**Forbidden:** live; LLM; matrix edit; A9R3; product authority; changing frozen A9R2/A9R2b artifacts.

## Allowlist

| File | Checkpoint |
|------|------------|
| `TASK.md` | governance + completion |
| `evals/v5/a9r2_patient_scope_live_scoring.py` | A |
| `evals/v5/a9r2b_patient_scope_live_contract.py` | A (diagnostic path) |
| `evals/v5/a9r2b_patient_scope_live_diagnostic_recompute.py` | A |
| `docs/evidence/a9r2/A9R2B_POST_LIVE_METRIC_CORRECTION_AUDIT.md` | A |
| `evals/v5/artifacts/a9r2b_patient_scope_live_diagnostic_recompute.json` | A (new) |
| `evals/v5/a9r2c_patient_scope_live_contract.py` | B |
| `evals/v5/run_a9r2c_patient_scope_live.py` | B |
| `evals/v5/a9r2c_patient_scope_live_manual_review_builder.py` | B |
| `tests/test_a9r2b_metric_correction_offline.py` | A |
| `tests/test_a9r2c_patient_scope_live_offline.py` | B |
| `tests/test_a9r2c_planner_blast_radius_offline.py` | B |
| `tests/test_a9r2b_patient_scope_live_offline.py` | A/B regression |
| `tests/test_a9r2c_*` neighbors per TASK tests block | B |

## Tests

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-a9r2bc-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_a9r2b_metric_correction_offline.py `
  tests/test_a9r2c_patient_scope_live_offline.py `
  tests/test_a9r2c_planner_blast_radius_offline.py `
  tests/test_a9r2b_patient_scope_live_offline.py `
  tests/test_a9r2_scorer_correction_offline.py `
  tests/test_patient_scope_a9r_matrix_v3_contract.py `
  tests/test_ac3_scope_price_flow_offline.py -q
python evals/v5/run_a9r2c_patient_scope_live.py --dry-run
```

**STOP after COMPLETION ✅. A9R2c live is separate owner GO.**

## Completion record (A9R2b metric + A9R2c pre-live)

| Field | Value |
|-------|-------|
| Baseline HEAD | `5cd5015` |
| PRE-CODE | ✅ (governance `8ea1f34`) |
| COMPLETION | ✅ |
| Corrected A9R2b composite | 11/17 = 0.647 |
| A9R2c live blocked | `--live` not enabled |

---

# TASK — A9R2c planner-only live eval (owner GO)

**Status:** owner-approved live · **ONE ATTEMPT ONLY**

**Baseline:** `c22f948` (A9R2c pre-live COMPLETION ✅)

**Owner GO (2026-07-25):** exactly one planner-only live attempt. No owner override. No rerun.

## Frozen inputs

| Item | Value |
|------|-------|
| Matrix v3 blob | `8ccd9bdc140a192981fcc48ad7ed0367a40b0a84` |
| Model | `qwen3.7-plus` |
| Planner calls | ≤ 17 |
| Composer/Verifier/boundary/runtime | 0 |
| Product authority | not enabled |

## Owner ruling: `reported_context`

- Diagnostic-only axis; not a material gate axis
- **A9R3:** does **not** receive authority from A9
- **Product:** do not write `reported_context` from A9 into session; do not pass to AC2
- `extent` / `jaw` / `stage` remain authority-candidate axes

## Approved gates

| Gate | Threshold |
|------|-----------|
| wrong concrete material axis | 0 |
| material false-positive (extent/jaw/stage) | 0 |
| positive-axis recall | ≥ 0.85 |
| correction success | 100% |
| `true_composite_exact_turn_rate` (all non-transport turns) | ≥ 0.85 |
| malformed/transport/provider errors | 0 |
| calls | ≤ 17 |
| retry | 0 |

Official PASS only when automated gates pass **and** manual review complete for all 17 turns. Even on PASS, show result to owner before any authority decision.

## Allowlist (A9R2c live)

| File | Purpose |
|------|---------|
| `TASK.md` | live completion record |
| `evals/v5/a9r2c_patient_scope_live_contract.py` | frozen SHA pins post-live |
| `evals/v5/a9r2c_patient_scope_live_manual_review_builder.py` | manual review from result |
| `docs/evidence/a9r2/A9R2C_LIVE_ATTEMPT_AUDIT.md` | audit |
| `evals/v5/artifacts/a9r2c_patient_scope_live_*` | immutable live artifacts |
| `tests/test_a9r2c_patient_scope_live_offline.py` | rerun-block + frozen pins |

**Forbidden:** rerun; owner override; A9R3 wiring; product authority; editing A9/A9R/A9R2/A9R2b/W1b/S-series frozen artifacts.

## Completion record (A9R2c live)

| Field | Value |
|-------|-------|
| Baseline HEAD | `c22f948` |
| Live GO HEAD | `dae92a4` |
| PRE-CODE | ✅ (live GO) |
| Live HEAD | `a87c9d1` |
| `automated_verdict` | `AUTOMATED_FAIL` |
| `final_verdict` | `FAIL` (manual review complete) |
| Manual review | ✅ 17/17 turns |
| Provider model incident | logs show `qwen3.6-flash` not `qwen3.7-plus` |
| Rerun | blocked |

---

# TASK — A9R2c model-pin incident capture + A9R2d wiring correction

**Status:** COMPLETION ✅ · **NO LIVE / NO LLM / NO A9R3**

**Baseline:** `c519dd4` (A9R2c live complete)

## Checkpoint A — A9R2c incident capture

| Deliverable | Role |
|-------------|------|
| `A9R2C_MODEL_PIN_INCIDENT_CAPTURE.md` | 17 Flash calls; `A9R2C_NOT_VALID_FOR_PLUS`; frozen artifacts unchanged |
| `a9r2c_patient_scope_live_contract.py` | Incident status constants only (no artifact rewrite) |

**Frozen A9R2c artifacts byte-identical.** Rerun A9R2c blocked.

## Checkpoint B — A9R2d model-pin wiring

| Deliverable | Role |
|-------------|------|
| `patient_scope_live_model_pin.py` | Bootstrap + pre-marker assert + provider model tracking |
| `a9r2_patient_scope_live_harness.py` | Model-pin path; `MODEL_MISMATCH` abort after 1st observed response |
| `a9r2d_patient_scope_live_contract.py` | Isolated `a9r2d_*`; `REQUIRES_PLANNER_MODEL_PIN` |
| `run_a9r2d_patient_scope_live.py` | Subprocess inner runner; env before import |
| `a9r2d_patient_scope_live_inner.py` | Clean-process live entry |
| `tests/test_a9r2d_model_pin_subprocess_offline.py` | Subprocess pin tests |
| `tests/test_a9r2d_patient_scope_live_offline.py` | Harness offline + mismatch abort |

Manifest uses `model_provenance` (not owner config alone). Matrix v3 and prompt unchanged.

## Allowlist

| File | Checkpoint |
|------|------------|
| `TASK.md` | governance + completion |
| `docs/evidence/a9r2/A9R2C_MODEL_PIN_INCIDENT_CAPTURE.md` | A |
| `evals/v5/a9r2c_patient_scope_live_contract.py` | A (status constants) |
| `evals/v5/patient_scope_live_model_pin.py` | B |
| `evals/v5/a9r2_patient_scope_live_harness.py` | B |
| `evals/v5/a9r2d_patient_scope_live_contract.py` | B |
| `evals/v5/run_a9r2d_patient_scope_live.py` | B |
| `evals/v5/a9r2d_patient_scope_live_inner.py` | B |
| `evals/v5/a9r2d_patient_scope_live_manual_review_builder.py` | B |
| `tests/test_a9r2d_model_pin_subprocess_offline.py` | B |
| `tests/test_a9r2d_patient_scope_live_offline.py` | B |
| `tests/test_a9r2c_patient_scope_live_offline.py` | A/B regression |

## Tests

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-a9r2d-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_a9r2d_model_pin_subprocess_offline.py `
  tests/test_a9r2d_patient_scope_live_offline.py `
  tests/test_a9r2c_patient_scope_live_offline.py `
  tests/test_a9r2b_patient_scope_live_offline.py `
  tests/test_a9r2c_planner_blast_radius_offline.py `
  tests/test_ac3_scope_price_flow_offline.py -q
python evals/v5/run_a9r2d_patient_scope_live.py --dry-run
```

**STOP after COMPLETION ✅. A9R2d live is separate owner GO.**

## Completion record (A9R2c incident + A9R2d wiring)

| Field | Value |
|-------|-------|
| Baseline HEAD | `c519dd4` |
| PRE-CODE | ✅ (governance `9fd94a3`) |
| COMPLETION | ✅ |
| A9R2c status | `A9R2C_NOT_VALID_FOR_PLUS` |
| A9R2d live blocked | `--live` subprocess only; no provider calls in checkpoint |

---

# TASK — A9R2d planner-only live eval (owner GO)

**Status:** owner-approved live · **ONE ATTEMPT ONLY**

**Baseline:** `e50647c` (A9R2d wiring COMPLETION ✅)

**Owner GO (2026-07-25):** exactly one planner-only live attempt with model-pin verified Plus. No owner override. No rerun.

## Frozen inputs

| Item | Value |
|------|-------|
| Matrix v3 blob | `8ccd9bdc140a192981fcc48ad7ed0367a40b0a84` |
| Model | `qwen3.7-plus` (requested/configured/observed) |
| Planner calls | ≤ 17 |
| Composer/Verifier/boundary/runtime | 0 |

## Approved gates

Same as A9R2c: `true_composite_exact_turn_rate` ≥ 0.85; material FP = 0; etc.

## Allowlist (A9R2d live)

| File | Purpose |
|------|---------|
| `TASK.md` | live completion record |
| `evals/v5/a9r2d_patient_scope_live_contract.py` | frozen SHA pins post-live |
| `docs/evidence/a9r2/A9R2D_LIVE_ATTEMPT_AUDIT.md` | audit |
| `evals/v5/artifacts/a9r2d_patient_scope_live_*` | immutable live artifacts |
| `tests/test_a9r2d_patient_scope_live_offline.py` | rerun-block + frozen pins |

## Completion record (A9R2d live)

| Field | Value |
|-------|-------|
| Baseline HEAD | `e50647c` |
| Live HEAD | `f1b90b8` |
| `automated_verdict` | `AUTOMATED_FAIL` |
| `final_verdict` | `FAIL` (manual review 17/17) |
| `provider_model_verified` | true (`qwen3.7-plus` × 17) |
| `true_composite_exact_turn_rate` | 0.882 (15/17) |
| Material FP | 1 |
| Rerun | blocked |

---

# TASK — A9R3 product authority wiring (governance)

**Status:** governance COMPLETION ✅ · **NO IMPLEMENTATION / NO LIVE / NO LLM / NO A9R4**

**Baseline:** `f1b90b8` (A9R2d live complete)

**Owner decision (2026-07-25):** **stop A9 model-tuning cycles** (no A9R2e, no further live eval loops, no prompt/regex/filter tuning). Proceed to A9R3 product authority wiring with measured risk acceptance.

## Owner rulings (binding)

| Ruling | Value |
|--------|-------|
| Runtime planner model | **`qwen3.7-plus`** (accepted) |
| Measured risk accepted | one directionally plausible extent FP on «восстановить обе челюсти» (`a9r_jaw_03_both`) |
| A9R2d official verdict | **`AUTOMATED_FAIL` / `FAIL` immutable** — no retroactive PASS |
| Authority axes | **`extent`, `jaw`, `stage` only** |
| `reported_context` | **diagnostic/shadow-only** — not session, not AC2 |
| Forbidden now | prompt tuning, live eval loops, filters, regex, synonym tables, extra LLM calls |

## Target chain

```
Plus Planner → TurnFrame.patient_scope → A9R1 projection → per-axis EffectiveScope merge → AC2 → AC3
```

## Merge / persistence rules

1. typed UI action (current turn) **above** A9
2. usable current-turn A9 **above** same-topic session
3. current `unknown` **does not erase** session
4. explicit correction **replaces** axis
5. topic change / reset / SID isolation / freshness **preserved**
6. **valid native planner provenance only** — scalar bridge not authority
7. persist extent/jaw/stage **only after materialized turn**; terminal/error **must not** overwrite prior facts
8. no second session scope store

## Seam audit

`docs/evidence/a9r2/A9R3_PRODUCT_AUTHORITY_SEAM_AUDIT.md` — read-only wiring points in `target_runtime_turn.py`, `resolve_effective_scope`, session write, AC2/AC3 handoff.

## Acceptance matrix (A9R3 implementation — protected)

| # | Input / action | Expected A9 | Expected AC2/AC3 |
|---|----------------|-------------|------------------|
| AC3-1 | «Сколько стоит имплантация всей челюсти?» | `extent=full_arch` | scoped price answer; **no scope nav buttons** |
| AC3-2 | «Сколько стоит имплантация?» | all unknown | broad anchors + **scope buttons** |
| AC3-3 | «Сколько стоит All-on-4?» | no invented patient scope | concrete **service** path; no extent/jaw/stage FP from protocol name |
| AC3-4 | «Имплант уже установлен, сколько коронка?» | `stage=implant_placed`, topic prosthetics | scoped prosthetics price path |
| AC3-5 | follow-up «Нет, речь об одном зубе» | correction `extent=one_tooth` | **replaces** session `full_arch` |
| AC3-6 | UI scope click | — | UI extent **wins** over planner inference |
| AC3-7 | ambiguous/vague input | unknown axes | **does not overwrite** session |
| AC3-8 | terminal/error turn | — | **no A9 session write** |
| AC3-9 | `/ask` and `/ask/stream` | parity | same EffectiveScope path |
| AC3-10 | price amounts/units | — | **pricebook only** — no LLM prices |
| AC3-11 | routing | — | **no** legacy/W1b/family-group routes |

## Planner (implementation deliverable)

| Item | Target |
|------|--------|
| `TURN_PLANNER_LLM_MODEL` default | `qwen3.7-plus` |
| env override | ordinary model config only — not architecture kill-switch |
| verification | runtime tests confirm Plus in product path |

## Allowlist (A9R3 governance — this commit)

| File | Role |
|------|------|
| `TASK.md` | A9R3 governance + acceptance matrix |
| `docs/evidence/a9r2/A9R3_PRODUCT_AUTHORITY_SEAM_AUDIT.md` | seam audit |

## Allowlist (A9R3 implementation — future owner GO)

| File | Role |
|------|------|
| `core/target_effective_scope.py` | merge-aware resolver |
| `core/target_runtime_turn.py` | project + wire + session persist |
| `core/target_runtime_session.py` | A9 session writer (extent/jaw/stage) |
| `config.py` | default Plus |
| `docs/FLAGS_AND_STATUS.md` | `A9_PATIENT_SCOPE_AUTHORITY` (default OFF until flip) |
| `tests/test_effective_scope_merge.py` | regression |
| `tests/test_session_patient_facts_offline.py` | persistence |
| `tests/test_ac3_scope_price_flow_offline.py` | acceptance |
| `tests/test_ui_scope_click_http_offline.py` | UI priority |
| `tests/test_turn_frame_shadow.py` | controlled read |
| `tests/test_a9r3_*` | new implementation tests per TASK |

**Frozen (byte-identical):** A9/A9R/A9R2*/W1b/S-series artifacts and matrices.

## Forbidden

- Implementation in this governance commit
- Live / LLM eval loops
- Prompt tuning, filters, regex, synonym tables, second classifier
- `reported_context` authority
- A9 service/offer/strategy/ResponseStage selection
- Editing frozen eval/live artifacts
- Retroactive A9R2d PASS

## Gate sequence (updated)

| Gate | Status |
|------|--------|
| A9R2d Plus live + model-pin | complete (`f1b90b8`) |
| **A9R3 governance (this)** | in progress |
| A9R3 implementation | **blocked** until separate owner GO |
| Widget E2E | after A9R3 implementation |

**STOP after governance PRE-CODE ✅. No A9R3 implementation without separate owner GO.**

## Completion record (A9R3 governance)

| Field | Value |
|-------|-------|
| Baseline HEAD | `f1b90b8` |
| PRE-CODE | ✅ (governance `059569f`) |
| COMPLETION | ✅ (governance only) |
| Implementation | blocked |
| Model-tuning cycles | **stopped** |

---

# TASK — FINAL_SCOPE_WIDGET_E2E (governance + offline pre-live)

**Status:** governance COMPLETION ✅ · **NO LIVE / NO LLM**

**Baseline:** `70a96c1` (A9R3 implementation complete)

**Owner sequence:** FINAL live widget E2E (one attempt) → on PASS remove `A9_PATIENT_SCOPE_AUTHORITY` kill-switch → unconditional A9 authority.

## Goal

One terminal runtime/widget E2E covering implantation + prosthetics scope/price flows:

- `A9_PATIENT_SCOPE_AUTHORITY=1` set **before** config import (harness only until closeout)
- Planner **`qwen3.7-plus`** (requested/configured/observed)
- Real `/ask` and `/ask/stream`
- AC1 → A9R3 → AC2 → AC3 end-to-end
- Actual widget payload, session, refs, CTA
- No legacy/fallback routes

## Frozen turn matrix (protected)

`evals/v5/demo/final_scope_widget_e2e_turns.json`
**Blob:** `f4eecf7532481a288d1db6a6ee107dd147117dae44afc991451836dd3589434f`

| # | Session | Endpoint | Action | Expected |
|---|---------|----------|--------|----------|
| 1 | A | `/ask` | «Сколько стоит имплантация?» | broad; 3 scope buttons; no payment stages |
| 2 | A | `/ask` | click «Вся челюсть» | scoped offers; no scope nav; session `full_arch` |
| 3 | A | `/ask` | «Нет, речь об одном зубе» | A9 correction → `one_tooth` |
| 4 | B fresh | `/ask/stream` | «Сколько стоит имплантация всей челюсти?» | A9 `full_arch`; scoped; no scope nav |
| 5 | C fresh | `/ask` | «Сколько стоит протезирование?» | broad prosthetics + scope buttons |
| 6 | C | `/ask` | click «Один зуб» | stage clarification when required |
| 7 | C | `/ask` | click «Имплант установлен» | scoped offers; no repeat scope/stage nav |
| 8 | D fresh | `/ask/stream` | «Имплант уже установлен, сколько будет коронка?» | A9 `implant_placed`; prosthetics scoped |

## Provider call budget

| Role | Budget |
|------|--------|
| ingress | 5 (text turns only) |
| planner | 8 |
| medical_boundary | 8 |
| composer | 8 |
| semantic_verifier | 8 |
| **total hard stop** | **40** |

`RETRY_COUNT_MAX = 0`. FullContext build once. Manual review of all user answers mandatory.

Seam audit: `docs/evidence/final_scope/FINAL_SCOPE_WIDGET_E2E_SEAM_AUDIT.md`

## Allowlist (this checkpoint)

| File | Role |
|------|------|
| `TASK.md` | governance + completion |
| `docs/evidence/final_scope/FINAL_SCOPE_WIDGET_E2E_SEAM_AUDIT.md` | seam audit + call budget |
| `docs/FLAGS_AND_STATUS.md` | E2E note |
| `evals/v5/demo/final_scope_widget_e2e_turns.json` | frozen turns |
| `evals/v5/final_scope_widget_e2e_live_contract.py` | contract |
| `evals/v5/final_scope_widget_e2e_live_harness.py` | HTTP harness |
| `evals/v5/final_scope_widget_e2e_live_provider_audit.py` | provider ledger |
| `evals/v5/run_final_scope_widget_e2e_live.py` | CLI |
| `tests/test_final_scope_widget_e2e_live_harness.py` | offline tests |

**Frozen (byte-identical):** S62/S63/S66/A9/A9R* artifacts and matrices.

## Forbidden

- Live run in this checkpoint
- LLM / provider calls
- Product code changes (incl. removing `A9_PATIENT_SCOPE_AUTHORITY` — post-E2E closeout only)
- Editing frozen prior live artifacts

## Tests

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-fsw-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_final_scope_widget_e2e_live_harness.py `
  tests/test_a9r3_completion_offline.py -q
python evals/v5/run_final_scope_widget_e2e_live.py --dry-run
git diff --check
```

**STOP after COMPLETION ✅. Live E2E is separate owner GO.**

## Post-E2E closeout (future — blocked)

| Deliverable | Action |
|-------------|--------|
| `config.A9_PATIENT_SCOPE_AUTHORITY` | **delete** flag |
| `core/target_effective_scope.py` | unconditional A9 merge |
| `core/target_runtime_turn.py` | always project + merge |
| `docs/FLAGS_AND_STATUS.md` | remove kill-switch row |
| tests | drop flag-enable fixtures; authority always on |

## Completion record (FINAL_SCOPE_WIDGET_E2E governance)

| Field | Value |
|-------|-------|
| Baseline HEAD | `70a96c1` |
| PRE-CODE | ✅ (this commit) |
| COMPLETION | ✅ (governance + offline pre-live only) |
| Live | **blocked** until owner GO |
| Post-E2E flag removal | **blocked** until live PASS |

---

# TASK — FINAL_SCOPE_WIDGET_E2E_RETRY1 (harness correction only)

**Status:** governance + implementation · **NO LIVE / NO LLM / NO PRODUCT CODE**

**Baseline:** `0f645cc` (preflight-abort audit)

**Owner GO:** offline checkpoint RETRY1 — harness correction only; frozen preflight-abort marker/audit byte-identical; new isolated namespace `final_scope_widget_e2e_retry1_*`.

## Goal

Fix post-S69 harness preflight: remove stale `orchestration.ask_turn` import; validate `app._orchestrate_ask_turn` target-only path; create retry1 attempt marker **after** seam validation, **before** first provider call.

## Allowlist

| File | Role |
|------|------|
| `TASK.md` | governance + completion |
| `docs/evidence/final_scope/FINAL_SCOPE_WIDGET_E2E_RETRY1_SEAM_AUDIT.md` | post-S69 seam audit |
| `docs/FLAGS_AND_STATUS.md` | retry1 note |
| `evals/v5/final_scope_widget_e2e_live_harness.py` | preflight fix (no stale import) |
| `evals/v5/final_scope_widget_e2e_retry1_live_contract.py` | retry1 namespace + frozen pins |
| `evals/v5/final_scope_widget_e2e_retry1_live_harness.py` | retry1 harness wrapper |
| `evals/v5/run_final_scope_widget_e2e_retry1_live.py` | retry1 CLI |
| `tests/test_final_scope_widget_e2e_retry1_live_harness.py` | offline tests |

**Frozen (byte-identical):** `final_scope_widget_e2e_attempt.json`, `FINAL_SCOPE_WIDGET_E2E_LIVE_ATTEMPT_AUDIT.md`, S62/S63/S66/A9/A9R* artifacts.

## Forbidden

- Live / LLM / provider calls
- Product code changes
- Reclaim/rename/delete preflight-abort attempt #1 artifacts
- Retry1 live without new owner GO

## Tests

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-fsw-r1-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_final_scope_widget_e2e_retry1_live_harness.py `
  tests/test_final_scope_widget_e2e_live_harness.py -q
python evals/v5/run_final_scope_widget_e2e_retry1_live.py --dry-run
git diff --check
```

**STOP after COMPLETION ✅. Retry1 live is separate owner GO.**

## Completion record (FINAL_SCOPE_WIDGET_E2E_RETRY1)

| Field | Value |
|-------|-------|
| Baseline HEAD | `0f645cc` |
| PRE-CODE | ✅ |
| COMPLETION | ✅ (harness correction only) |
| Retry1 live | **blocked** (official FAIL @ `d76870a`) |

---

# TASK — FINAL_SCOPE_POST_RETRY1_PRODUCT_CORRECTION (governance)

**Status:** implementation COMPLETION ✅ · **NO LIVE / NO LLM / NO Retry2**

**Baseline:** `d76870a` (`codex/stage-a`) · RETRY1 live = official **FAIL** · live/rerun **blocked**

**Owner rulings (binding):**

| Ruling | Value |
|--------|-------|
| `A9_PATIENT_SCOPE_AUTHORITY` | **do not remove** until post-E2E closeout after live PASS |
| RETRY1 artifacts | **frozen** byte-identical (`d76870a` SHAs) |
| Untracked `_retry1_live_run_stdout.txt` | forensic capture only — **not** committed; retain until audit |
| Fix approach | reuse AC1→AC2→AC3; **no** new route/selector/legacy fallback |
| Forbidden now | LIVE, Retry2, A9 prompt tuning, regex/phrase lists, service hardcodes |

Seam audit: `docs/evidence/final_scope/FINAL_SCOPE_POST_RETRY1_PRODUCT_CORRECTION_SEAM_AUDIT.md`

---

## Goal (two product defects from RETRY1)

### T2 — typed UI scope click

**Observed:** ref `target:ui_scope/implantation/full_arch` valid; `EffectiveScope` = `full_arch` / `ui_action`; planner `needs_clarification=true`; boundary on button label; route `terminal_medical_handoff_nonmaterializable`.

**Target semantics:** Governed `UiScopeAction` = typed price-drill-down continuation. Planner/boundary must not override scope resolved by AC1. Materialize scoped price via existing AC2→AC3 path.

### T5 — broad prosthetics price

**Observed:** `topic=prosthetics`, `aspect=price`, `extent=unknown`, `needs_clarification=true` → `terminal_clarify`.

**Target semantics:**

```
known topic + price aspect + service_id=null + extent=unknown
  → broad_family_price + 3 scope-nav buttons
```

`needs_clarification` preserved for non-price ambiguity and service_id ambiguity. Data-gap → existing typed fail-closed / `stage_clarify`.

### Harness evidence correction (implementation deliverable)

| Item | Requirement |
|------|-------------|
| UTF-8 capture | `₽` in logs/artifacts without `UnicodeEncodeError` or cp1251 mojibake |
| Fake-provider replay | all **8** matrix HTTP turns through **real** target runtime (not mocked orchestrate) |
| Gates | T2/T5 routes materialized; scope buttons present when matrix expects |

---

## Acceptance matrix (protected — implementation)

Matrix blob: `f4eecf7532481a288d1db6a6ee107dd147117dae44afc991451836dd3589434f` (**immutable**)

| ID | Scenario | Route / UI expectation |
|----|----------|------------------------|
| AM-1 | broad implantation «Сколько стоит имплантация?» | `materialized` · `broad_family_price` · 3 scope buttons |
| AM-2 | broad prosthetics «Сколько стоит протезирование?» (planner `needs_clarify=true` OK) | same · prosthetics topic |
| AM-3 | typed scope click `full_arch` (implantation) | scoped materialized · no scope nav · session `full_arch` |
| AM-4 | typed scope click `one_tooth` / `few_teeth` | scoped or `stage_clarify` per AC3 |
| AM-5 | prosthetics stage_clarify + stage click `implant_placed` | scoped offers · no repeat nav |
| AM-6 | free-text full_arch implantation | A9 `full_arch` · scoped materialized |
| AM-7 | free-text `implant_placed` prosthetics crown | A9 stage · scoped materialized |
| AM-8 | ordinary medical free-text (non-UI) | boundary `medical_handoff` behavior **unchanged** |
| AM-9 | ambiguous non-price question | `terminal_clarify` **preserved** |
| AM-10 | invalid / unshown ref click | fail-closed unknown-ref clarify |
| AM-11 | `/ask` and `/ask/stream` | EffectiveScope + route class parity |
| AM-12 | terminal/error turn | **no** session `patient_facts` overwrite |
| AM-13 | 8-turn widget matrix offline replay | 8/8 HTTP completed · automated gates pass |
| AM-14 | price amounts/units | pricebook only · no LLM prices |

RETRY1 live turns 1–8 remain the canonical E2E oracle (`final_scope_widget_e2e_turns.json`).

---

## Blast-radius tests (implementation allowlist)

| File | Extend for |
|------|------------|
| `tests/test_target_turn_frame_dispatch.py` | T2/T5 dispatch precedence with `needs_clarify=true` |
| `tests/test_ac3_scope_price_flow_offline.py` | prosthetics broad + scope clicks under clarify flag |
| `tests/test_a9r3_product_authority_offline.py` | UI click beats planner + boundary handoff |
| `tests/test_ac3_scope_price_flow_http_offline.py` | HTTP + stream parity |
| `tests/test_ui_scope_click_http_offline.py` | ref-only clicks |
| `tests/test_demo_target_turn_frame_bound_response.py` | clarify vs scope-price split |
| `tests/test_session_patient_facts_offline.py` | terminal/error no write |
| `tests/test_final_scope_widget_e2e_retry1_live_harness.py` | real-path 8-turn fake-provider replay + UTF-8 |
| `tests/test_final_scope_post_retry1_product_correction_governance.py` | frozen pins regression |

---

## Allowlist (governance — this commit)

| File | Role |
|------|------|
| `TASK.md` | this checkpoint |
| `docs/evidence/final_scope/FINAL_SCOPE_POST_RETRY1_PRODUCT_CORRECTION_SEAM_AUDIT.md` | read-only seam audit |
| `docs/FLAGS_AND_STATUS.md` | POST_RETRY1 status note |
| `tests/test_final_scope_post_retry1_product_correction_governance.py` | PRE-CODE checker |

## Allowlist (implementation — future owner GO)

| File | Role |
|------|------|
| `core/target_turn_frame_dispatch.py` | primary: scope-price materialize precedence |
| `core/target_runtime_turn.py` | pass governed UI context to dispatch if needed |
| `orchestration/pre_resolver_turn.py` | optional: neutral continuation token vs raw label |
| `logging_setup.py` | UTF-8 stream capture for ₽ |
| `evals/v5/final_scope_widget_e2e_live_harness.py` | harness UTF-8 + answer capture from HTTP payload |
| `evals/v5/final_scope_widget_e2e_retry1_live_harness.py` | retry1 harness parity if needed |
| `tests/test_target_turn_frame_dispatch.py` | dispatch blast-radius |
| `tests/test_ac3_scope_price_flow_offline.py` | AC2/AC3 blast-radius |
| `tests/test_a9r3_product_authority_offline.py` | A9R3 + UI priority |
| `tests/test_ac3_scope_price_flow_http_offline.py` | HTTP/stream parity |
| `tests/test_ui_scope_click_http_offline.py` | UI click HTTP |
| `tests/test_demo_target_turn_frame_bound_response.py` | boundary/clarify neighbor |
| `tests/test_session_patient_facts_offline.py` | session write guard |
| `tests/test_final_scope_widget_e2e_retry1_live_harness.py` | 8-turn real-path replay |
| `tests/test_final_scope_post_retry1_product_correction_governance.py` | frozen pins |
| `TASK.md` | implementation completion record |

**Frozen (byte-identical):** all RETRY1 live artifacts, preflight-abort attempt #1, widget matrix, S62/S63/A9/A9R*/W1b.

## Forbidden (governance + implementation)

- LIVE / LLM / Retry2 live
- A9 planner prompt tuning
- regex, phrase lists, service hardcodes
- new selector, temporary route, legacy fallback
- editing frozen RETRY1 artifacts or committed `final_scope_widget_e2e_retry1_live_stdout.log`
- deleting `A9_PATIENT_SCOPE_AUTHORITY` flag
- committing `_retry1_live_run_stdout.txt`

## Tests (governance PRE-CODE)

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-fsw-pc-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_final_scope_post_retry1_product_correction_governance.py -q
git diff --check
```

**Note:** `test_retry1_dry_run_cli` fails when retry1 live artifacts exist (rerun blocked) — expected post-`d76870a`; not a governance regression.

## STOP conditions

1. Governance commit touches product code
2. Frozen RETRY1 artifacts modified
3. PRE-CODE ❌ without fix path
4. Implementation started without separate owner GO

**STOP after governance PRE-CODE ✅. Implementation blocked until owner GO.**

## Completion record (POST_RETRY1 governance)

| Field | Value |
|-------|-------|
| Baseline HEAD | `d76870a` |
| PRE-CODE | ✅ |
| COMPLETION | N/A (governance only) |
| Implementation | **blocked** |
| Untracked stdout forensic | captured in seam audit |

## Completion record (POST_RETRY1 implementation)

| Field | Value |
|-------|-------|
| Baseline HEAD | `f480670` (governance) |
| PRE-CODE | ✅ (governance checker unchanged) |
| COMPLETION | ✅ |
| Pytest | 87 passed, 1 skipped (`test_retry1_dry_run_cli` — live artifacts present) |
| Fake-provider 8/8 | ✅ `test_fake_provider_executes_all_eight_http_turns_without_network` |
| T2 fix | `UiScopeAction` + scope-price dispatch preempts `needs_clarification` / `medical_handoff` on typed click |
| T5 fix | broad prosthetics price materializes via `broad_family_price` despite planner `needs_clarify` |
| UTF-8 | `logging_setup.py` + harness `configure_process_env()` reconfigure stdout/stderr |
| Live | **STOP** — separate owner GO for Retry1 re-run |

---

# TASK — FINAL_SCOPE_WIDGET_E2E_RETRY2 (pre-live checkpoint)

**Status:** governance + offline wiring COMPLETION ✅ · **NO LIVE / NO LLM**

**Baseline:** `c670b96` (POST_RETRY1 product correction COMPLETION ✅)

**Owner GO:** isolated namespace `final_scope_widget_e2e_retry2_*`; same frozen 8-turn matrix; Retry1 FAIL artifacts immutable; forensic UTF-16 stdout verified and removed.

Seam audit: `docs/evidence/final_scope/FINAL_SCOPE_WIDGET_E2E_RETRY2_SEAM_AUDIT.md`

## Goal

Wire retry2 live harness namespace for first post-correction live attempt. Re-prove offline real-path 8/8 through post-correction target runtime. Do **not** modify or bypass Retry1 frozen artifacts.

## Allowlist

| File | Role |
|------|------|
| `TASK.md` | governance + completion |
| `docs/evidence/final_scope/FINAL_SCOPE_WIDGET_E2E_RETRY2_SEAM_AUDIT.md` | seam audit |
| `docs/FLAGS_AND_STATUS.md` | retry2 status note |
| `evals/v5/final_scope_widget_e2e_retry2_live_contract.py` | retry2 namespace + frozen pins |
| `evals/v5/final_scope_widget_e2e_retry2_live_harness.py` | retry2 harness wrapper |
| `evals/v5/run_final_scope_widget_e2e_retry2_live.py` | retry2 CLI |
| `tests/test_final_scope_widget_e2e_retry2_governance.py` | PRE-CODE / COMPLETION checker |
| `tests/test_final_scope_widget_e2e_retry2_live_harness.py` | offline 8/8 + dry-run |
| `tests/test_final_scope_post_retry1_product_correction_governance.py` | forensic removal pin update |

**Frozen (byte-identical):** all `final_scope_widget_e2e_retry1_*` live artifacts, preflight-abort attempt #1, widget matrix, S62/S63.

## Forbidden

- LIVE / LLM / provider calls
- Product code changes
- Modify/delete/rename Retry1 frozen artifacts
- Bypass Retry1 attempt marker (use new retry2 namespace)
- `git clean` for forensic removal
- Committing removed forensic file

## Constants (binding)

| Constant | Value |
|----------|-------|
| `MAX_HTTP_TURNS` | 8 |
| `MAX_PROVIDER_CALLS` | 40 |
| `RETRY_COUNT_MAX` | 0 |
| Planner | `qwen3.7-plus` |
| `A9_PATIENT_SCOPE_AUTHORITY` | ON before import |

## Tests (PRE-CODE + COMPLETION)

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-fsw-r2-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_final_scope_widget_e2e_retry2_governance.py `
  tests/test_final_scope_widget_e2e_retry2_live_harness.py `
  tests/test_final_scope_post_retry1_product_correction_governance.py -q
python evals/v5/run_final_scope_widget_e2e_retry2_live.py --dry-run
git diff --check
```

**STOP after COMPLETION ✅. Retry2 live is separate owner GO.**

## Completion record (FINAL_SCOPE_WIDGET_E2E_RETRY2 pre-live)

| Field | Value |
|-------|-------|
| Baseline HEAD | `c670b96` |
| PRE-CODE | ✅ |
| COMPLETION | ✅ |
| Offline 8/8 | ✅ `test_fake_provider_executes_all_eight_http_turns_without_network` |
| Dry-run CLI | ✅ `run_final_scope_widget_e2e_retry2_live.py --dry-run` |
| Forensic stdout | verified SHA `d3e3f159…` then removed (no `git clean`) |
| Live | **STOP** — separate owner GO |

---

# TASK — FINAL_SCOPE_WIDGET_E2E_RETRY2_POST_LIVE_AUDIT (governance)

**Status:** governance COMPLETION ✅ · **NO LIVE / NO LLM / NO PRODUCT CODE**

**Baseline:** `cbbdb35` (`codex/stage-a`) · RETRY2 live = official **FAIL** · rerun **blocked**

**Owner rulings (binding):**

| Ruling | Value |
|--------|-------|
| `A9_PATIENT_SCOPE_AUTHORITY` | **do not remove** until post-E2E closeout after live PASS |
| RETRY2 artifacts @ `cbbdb35` | **frozen** byte-identical (attempt + ledger + stdout) — **do not rewrite** attempt marker |
| RETRY1 artifacts | **frozen** byte-identical |
| Primary cause | neutral `продолжить` → partial planner `TurnFrame`; typed `UiScopeAction` on ctx but no authoritative commercial frame |
| Secondary | `missing implant_placed` harness abort; WinError 32 logging rollover (non-blocking, separate) |
| Next milestone | typed UI TurnFrame producer or validated overlay; AC1→AC2→AC3 only |
| Forbidden now | LIVE, rerun, product code, regex/phrase lists, A9 tuning, legacy fallback |

Audits:

- `docs/evidence/final_scope/FINAL_SCOPE_WIDGET_E2E_RETRY2_LIVE_ATTEMPT_AUDIT.md`
- `docs/evidence/final_scope/FINAL_SCOPE_WIDGET_E2E_RETRY2_POST_LIVE_SEAM_AUDIT.md`

## Goal

Capture immutable RETRY2 live FAIL evidence; pin attempt/ledger/stdout SHA-256; document corrected ledger counts; design next offline product milestone for governed typed UI `TurnFrame` authority.

## Allowlist

| File | Role |
|------|------|
| `TASK.md` | governance + completion |
| `docs/evidence/final_scope/FINAL_SCOPE_WIDGET_E2E_RETRY2_LIVE_ATTEMPT_AUDIT.md` | live attempt audit |
| `docs/evidence/final_scope/FINAL_SCOPE_WIDGET_E2E_RETRY2_POST_LIVE_SEAM_AUDIT.md` | next milestone seam audit |
| `docs/FLAGS_AND_STATUS.md` | status note |
| `evals/v5/final_scope_widget_e2e_retry2_live_contract.py` | frozen retry2 SHA pins + assert |
| `tests/test_final_scope_widget_e2e_retry2_post_live_audit_governance.py` | PRE-CODE checker |
| `tests/test_final_scope_widget_e2e_retry2_governance.py` | post-live artifact presence pin |

**Frozen (byte-identical):** all `final_scope_widget_e2e_retry2_*` live artifacts @ `cbbdb35`, all retry1 artifacts, preflight-abort attempt #1, widget matrix, S62/S63.

## Forbidden

- LIVE / LLM / provider calls
- Product code changes
- Modify/delete/rename frozen retry2 attempt/ledger/stdout
- Rerun retry2 live
- `A9_PATIENT_SCOPE_AUTHORITY` removal

## Immutable SHA pins (retry2 @ `cbbdb35`)

| Artifact | SHA-256 |
|----------|---------|
| `final_scope_widget_e2e_retry2_attempt.json` | `deb0e00b0fccc0d3ab6f5e65a67caaacf90677231898e10dc3e9f3893e160671` |
| `final_scope_widget_e2e_retry2_call_ledger.jsonl` | `db430edc71ff8e3954a83e8d8f1ee9db610755a7549b5e105986940444f460ea` |
| `final_scope_widget_e2e_retry2_live_stdout.log` | `32b6a1f45660deb171b882bcc568807a5bec6a0c2479917f10e04a48439a00aa` |

**Corrected ledger:** ingress=4, planner=6, boundary=6, composer=4, verifier=4, total=24.

## Tests (PRE-CODE + COMPLETION)

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-fsw-r2pl-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_final_scope_widget_e2e_retry2_post_live_audit_governance.py `
  tests/test_final_scope_widget_e2e_retry2_governance.py `
  tests/test_final_scope_post_retry1_product_correction_governance.py -q
git diff --check
```

**Note:** `run_final_scope_widget_e2e_retry2_live.py --dry-run` exits 2 when retry2 artifacts exist (rerun blocked) — expected post-live.

**STOP after COMPLETION ✅. Typed UI TurnFrame product implementation blocked until separate owner GO.**

## Completion record (RETRY2 POST_LIVE_AUDIT governance)

| Field | Value |
|-------|-------|
| Baseline HEAD | `cbbdb35` |
| PRE-CODE | ✅ |
| COMPLETION | ✅ |
| Official verdict | **FAIL** (immutable) |
| Product implementation | **blocked** |

---

# TASK — FINAL_SCOPE_WIDGET_E2E_RETRY2_TYPED_UI_TURNFRAME (implementation)

**Status:** implementation COMPLETION ✅ · **NO LIVE / NO LLM / NO Retry3**

**Baseline:** `e3eb534` (POST_LIVE audit) · RETRY2 live FAIL artifacts **frozen**

## Goal

Governed `UiScopeAction` / `UiStageAction` produce native deterministic `TurnFrame`; LLM planner skipped on valid session-bound UI clicks; free-text unchanged.

## Allowlist

| File | Role |
|------|------|
| `core/target_typed_ui_turn_frame.py` | pure typed UI TurnFrame builder |
| `core/runtime_turn_frame.py` | `publish_typed_ui_turn_frame` + observability |
| `orchestration/typed_ui_planner_turn.py` | planner bypass ingress |
| `app.py` | typed UI before `run_planner_turn` |
| `tests/test_typed_ui_turn_frame_offline.py` | builder + HTTP parity + planner-not-called |
| `tests/test_final_scope_widget_e2e_retry2_live_harness.py` | post-live dry-run expectation |
| `TASK.md` | completion record |
| `docs/FLAGS_AND_STATUS.md` | status note |

**Frozen:** all `final_scope_widget_e2e_retry2_*` artifacts @ `cbbdb35`, retry1 artifacts, widget matrix.

## Tests

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:A9_PATIENT_SCOPE_AUTHORITY = "1"
python -m pytest tests/test_typed_ui_turn_frame_offline.py `
  tests/test_final_scope_widget_e2e_retry2_live_harness.py `
  tests/test_final_scope_widget_e2e_retry2_post_live_audit_governance.py -q
```

## Completion record (TYPED_UI_TURNFRAME implementation)

| Field | Value |
|-------|-------|
| Baseline HEAD | `e3eb534` |
| COMPLETION | ✅ |
| Offline 8/8 | ✅ retry2 harness |
| Planner bypass | ✅ scope + stage clicks; free-text unchanged |
| Retry3 pre-live | **STOP** — separate owner GO |

---

# TASK — FINAL_SCOPE_WIDGET_E2E_RETRY3 (pre-live checkpoint)

**Status:** governance + offline wiring COMPLETION ✅ · **NO LIVE / NO LLM**

**Baseline:** `b4b47bc` (TYPED_UI_TURNFRAME COMPLETION ✅)

**Owner GO:** isolated namespace `final_scope_widget_e2e_retry3_*`; same frozen 8-turn matrix; Retry1/Retry2 artifacts immutable.

Seam audit: `docs/evidence/final_scope/FINAL_SCOPE_WIDGET_E2E_RETRY3_SEAM_AUDIT.md`

## Goal

Wire retry3 live harness for first post-typed-UI live attempt. Re-prove offline real-path 8/8 with planner skip on T2/T6/T7 and tighter provider budget (34 total).

## Allowlist

| File | Role |
|------|------|
| `TASK.md` | governance + completion |
| `docs/evidence/final_scope/FINAL_SCOPE_WIDGET_E2E_RETRY3_SEAM_AUDIT.md` | seam audit |
| `docs/FLAGS_AND_STATUS.md` | retry3 status note |
| `evals/v5/final_scope_widget_e2e_retry3_live_contract.py` | retry3 namespace + frozen pins + budget caps |
| `evals/v5/final_scope_widget_e2e_retry3_live_provider_audit.py` | retry3 provider audit |
| `evals/v5/final_scope_widget_e2e_retry3_live_harness.py` | retry3 harness wrapper |
| `evals/v5/run_final_scope_widget_e2e_retry3_live.py` | retry3 CLI |
| `tests/test_final_scope_widget_e2e_retry3_governance.py` | PRE-CODE / COMPLETION checker |
| `tests/test_final_scope_widget_e2e_retry3_live_harness.py` | offline 8/8 + planner budget proof |

**Frozen (byte-identical):** all `final_scope_widget_e2e_retry1_*` and `final_scope_widget_e2e_retry2_*` live artifacts, preflight-abort attempt #1, widget matrix.

## Forbidden

- LIVE / LLM / provider calls
- Product code changes
- Modify/delete/rename Retry1/Retry2 frozen artifacts
- Owner override attempt marker
- Retry3 live before separate owner GO

## Constants (binding)

| Constant | Value |
|----------|-------|
| `MAX_HTTP_TURNS` | 8 |
| `MAX_PROVIDER_CALLS` | 34 |
| ingress / planner / boundary / composer / verifier | 5 / 5 / 8 / 8 / 8 |
| `RETRY_COUNT_MAX` | 0 |
| Planner | `qwen3.7-plus` |
| `A9_PATIENT_SCOPE_AUTHORITY` | ON before import |
| Free-text planner calls | 5 |
| Typed UI turns (no planner) | T2, T6, T7 |

## Tests (PRE-CODE + COMPLETION)

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:A9_PATIENT_SCOPE_AUTHORITY = "1"
$bt = Join-Path $env:TEMP ("demo-bot-fsw-r3-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_final_scope_widget_e2e_retry3_governance.py `
  tests/test_final_scope_widget_e2e_retry3_live_harness.py `
  tests/test_final_scope_widget_e2e_retry2_post_live_audit_governance.py `
  tests/test_final_scope_post_retry1_product_correction_governance.py -q
python evals/v5/run_final_scope_widget_e2e_retry3_live.py --dry-run
git diff --check
```

**STOP after COMPLETION ✅. Retry3 live is separate owner GO.**

## Completion record (FINAL_SCOPE_WIDGET_E2E_RETRY3 pre-live)

| Field | Value |
|-------|-------|
| Baseline HEAD | `b4b47bc` |
| PRE-CODE | ✅ |
| COMPLETION | ✅ |
| Offline 8/8 | ✅ `test_fake_provider_executes_all_eight_http_turns_without_network` |
| Planner skip T2/T6/T7 | ✅ 0 calls; free-text 5 calls |
| Dry-run CLI | ✅ `run_final_scope_widget_e2e_retry3_live.py --dry-run` |
| Live | **STOP** — separate owner GO |

---

# TASK — FINAL_SCOPE_POST_RETRY3_COMPOSER_ACTION_CONTEXT (governance)

**Status:** governance PRE-CODE only · **NO LIVE / NO LLM / NO PRODUCT CODE / NO Retry4**

**Baseline:** `341c1eb` (Retry3 live AUTOMATED_PASS) · owner manual verdict **FAIL** · Retry3 artifacts **frozen**

## Summary

| Item | Value |
|------|-------|
| Automated | `AUTOMATED_PASS` 8/8 HTTP, 34/34 provider calls |
| Owner manual | **FAIL** 5/8 (T1,T2,T4 widget,T6,T7) |
| Primary defect | Typed UI sets TurnFrame/EffectiveScope/`response_stage` ✅; Composer gets `user_message="продолжить"` ❌ |
| Secondary | `price:None/...` widget refs; T1 broad overview too long |
| Next product | optional `TargetComposerActionContext` + compact `broad_family_price` policy |
| Forbidden now | LIVE, Retry4, Verifier changes, regex/phrase lists, A9 tuning, new selectors, A9 flag removal |

Audits:

- `docs/evidence/final_scope/FINAL_SCOPE_WIDGET_E2E_RETRY3_MANUAL_REVIEW_AUDIT.md`
- `docs/evidence/final_scope/FINAL_SCOPE_POST_RETRY3_COMPOSER_ACTION_CONTEXT_SEAM_AUDIT.md`

## Goal

Capture immutable Retry3 manual FAIL evidence; pin Retry3 live artifact SHA-256; document Composer action-context seam and follow-up integrity policy; define implementation allowlist + acceptance matrix AM-1..AM-11.

## Allowlist (this governance checkpoint)

| File | Role |
|------|------|
| `TASK.md` | governance + completion |
| `docs/evidence/final_scope/FINAL_SCOPE_WIDGET_E2E_RETRY3_MANUAL_REVIEW_AUDIT.md` | append-only manual incident |
| `docs/evidence/final_scope/FINAL_SCOPE_POST_RETRY3_COMPOSER_ACTION_CONTEXT_SEAM_AUDIT.md` | read-only seam audit |
| `docs/FLAGS_AND_STATUS.md` | status note |
| `evals/v5/final_scope_widget_e2e_retry3_live_contract.py` | frozen retry3 SHA pins + assert |
| `tests/test_final_scope_post_retry3_composer_action_context_governance.py` | PRE-CODE checker |
| `tests/test_final_scope_widget_e2e_retry3_governance.py` | post-live artifact presence pin |

**Frozen (byte-identical):** all `final_scope_widget_e2e_retry3_*` live artifacts @ `341c1eb`, all retry1/2 artifacts, preflight-abort attempt #1, widget matrix, S62/S63.

## Forbidden (governance)

- LIVE / LLM / provider calls / Retry4
- Product code changes
- Modify/delete/rename frozen retry3 live artifacts
- Rerun retry3 live
- `A9_PATIENT_SCOPE_AUTHORITY` removal

## Immutable SHA pins (retry3 @ `341c1eb`)

| Artifact | SHA-256 |
|----------|---------|
| `final_scope_widget_e2e_retry3_attempt.json` | `c3f4fe0cab32ac0a4e94c3b140f10f415036c6f34cffc8463975be47920e66d8` |
| `final_scope_widget_e2e_retry3_call_ledger.jsonl` | `1eeed9f6682e849020e54a51db8a0502046b69993ebc8f5bf74350d6a321dbd4` |
| `final_scope_widget_e2e_retry3_live_stdout.log` | `1b74cc08844a02c540231167fe91dfac25a5f0edeee441442c550633107b7e49` |
| `final_scope_widget_e2e_retry3_result.json` | `bbab70c9e55392d037921c091a1ed75c26cf06a6673d9d3181cbe650d3c1fb81` |
| `final_scope_widget_e2e_retry3_manifest.json` | `c64e4054e5107c88e0ad69478100b6310fd4ea2ea41021034e535d5caa3cb3d3` |

**Ledger (completed):** ingress=5, planner=5, boundary=8, composer=8, verifier=8, total=34.

## Tests (PRE-CODE + COMPLETION)

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-fsw-r3pl-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_final_scope_post_retry3_composer_action_context_governance.py `
  tests/test_final_scope_widget_e2e_retry3_governance.py `
  tests/test_final_scope_widget_e2e_retry2_post_live_audit_governance.py `
  tests/test_final_scope_post_retry1_product_correction_governance.py -q
git diff --check
```

**Note:** `run_final_scope_widget_e2e_retry3_live.py --dry-run` exits 2 when retry3 artifacts exist (rerun blocked) — expected post-live.

**STOP after COMPLETION ✅. Product implementation blocked until separate owner GO.**

## Completion record (POST_RETRY3 governance)

| Field | Value |
|-------|-------|
| Baseline HEAD | `341c1eb` |
| PRE-CODE | ✅ |
| COMPLETION | ✅ |
| Official automated verdict | **AUTOMATED_PASS** (immutable) |
| Owner manual verdict | **FAIL** (immutable) |
| Product implementation | **blocked** |

---

# TASK — FINAL_SCOPE_POST_RETRY3_COMPOSER_ACTION_CONTEXT (implementation)

**Status:** implementation COMPLETION ✅ · **NO LIVE / NO LLM / NO Retry4**

**Baseline:** POST_RETRY3 governance COMPLETION @ `341c1eb` · Retry3 live artifacts **frozen**

## Goal

Pass governed UI click semantics to Composer via optional typed `TargetComposerActionContext`; compact `broad_family_price` responses; eliminate `price:None/...` follow-up refs; preserve free-text and verifier paths.

## Allowlist (implementation — owner GO required)

| File | Role |
|------|------|
| `contracts/target_composer_action_context.py` | typed action context contract |
| `core/target_composer_action_context.py` | builder from validated session-bound UI action |
| `core/target_composer_request.py` | optional action context on request |
| `core/target_composer_executor.py` | invocation + directive wiring |
| `core/target_runtime_llm_messages.py` | structured action context in Composer SDK template |
| `core/target_boundary_enforced_fullcontext_response.py` | pass-through to pipeline |
| `core/target_policy_bound_verified_response_pipeline.py` | action context threading |
| `core/target_runtime_turn.py` | build context from request ctx UI action |
| `core/target_response_followup_materializer.py` | fail-closed: no `price:None/...` |
| `core/target_response_followup_policy.py` | multi-service family ref policy |
| `core/target_response_policy.py` | compact `broad_family_price` directives |
| `core/target_spec_offline_response_package.py` | broad-family response directives |
| `core/target_turn_frame_dispatch.py` | stage/directive hints if needed |
| `tests/test_target_composer_action_context.py` | unit: builder + request/invocation |
| `tests/test_final_scope_post_retry3_composer_action_context_offline.py` | T1–T8 offline real-runtime replay |
| `tests/test_final_scope_widget_e2e_retry3_live_harness.py` | harness expectation updates |
| `TASK.md` | completion record |

**Frozen (do not edit):** Retry1/2/3 live artifacts, widget matrix `f4eecf75…`, protected acceptance targets.

## Forbidden

- LIVE / Retry4
- Verifier changes (`core/target_response_verifier.py`, semantic verifier policy)
- Regex / phrase lists
- A9 prompt tuning
- New selectors or legacy fallback routes
- Temporary family route without architecture decision
- `A9_PATIENT_SCOPE_AUTHORITY` removal

## Acceptance matrix (AM-1..AM-11)

See `docs/evidence/final_scope/FINAL_SCOPE_POST_RETRY3_COMPOSER_ACTION_CONTEXT_SEAM_AUDIT.md`.

| ID | Key check |
|----|-----------|
| AM-1 | T1 compact broad implantation overview + 3 scope buttons |
| AM-2 | T2 scoped full_arch prices; Composer has typed action context |
| AM-3 | T3 one-tooth correction unchanged |
| AM-4 | T4 stream prices; no `price:None/...` |
| AM-5 | T5 broad prosthetics unchanged PASS bar |
| AM-6 | T6 `stage_clarify` concise; action context present |
| AM-7 | T7 crown on implant; action context present |
| AM-8 | T8 A9 crown stream unchanged |
| AM-9 | `price:None/...` fail-closed |
| AM-10 | Free-text medical/clarify regression unchanged |
| AM-11 | `/ask` ≡ `/ask/stream` Composer action wiring |

## Tests (implementation COMPLETION)

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:A9_PATIENT_SCOPE_AUTHORITY = "1"
$bt = Join-Path $env:TEMP ("demo-bot-fsw-r3impl-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_target_composer_action_context.py `
  tests/test_final_scope_post_retry3_composer_action_context_offline.py `
  tests/test_final_scope_widget_e2e_retry3_live_harness.py `
  tests/test_final_scope_post_retry3_composer_action_context_governance.py `
  tests/test_final_scope_widget_e2e_retry3_governance.py -q
git diff --check
```

**STOP after COMPLETION ✅. No LIVE without separate owner GO.**

## Completion record (POST_RETRY3 implementation)

| Field | Value |
|-------|-------|
| Baseline HEAD | `2f41fdb` |
| PRE-CODE | ✅ |
| COMPLETION | ✅ |
| Offline T1–T8 | ✅ `test_offline_t1_t8_action_context_and_widget_integrity` |
| Typed UI governed context | ✅ T2 `scoped_family_price`, T7 `ui_stage`; stage_clarify directive |
| `price:None/...` | ✅ fail-closed materializer + policy + spec package |
| `broad_family_price` compact | ✅ directive overlay in Composer |
| Live / Retry4 | **STOP** — separate owner GO |

---

# TASK — FINAL_SCOPE_WIDGET_E2E_RETRY4 (pre-live checkpoint)

**Status:** governance + offline wiring COMPLETION ✅ · **NO LIVE / NO LLM**

**Baseline:** `6b67e35` (POST_RETRY3_COMPOSER_ACTION_CONTEXT COMPLETION ✅)

**Owner GO:** isolated namespace `final_scope_widget_e2e_retry4_*`; same frozen 8-turn matrix; Retry1/Retry2/Retry3 artifacts immutable.

Seam audit: `docs/evidence/final_scope/FINAL_SCOPE_WIDGET_E2E_RETRY4_SEAM_AUDIT.md`

## Goal

Wire retry4 live harness for first post-POST_RETRY3 live attempt. Re-prove offline real-path 8/8 with governed Composer action context, no `price:None/...` refs, planner skip on T2/T6/T7, and explicit manual rubric gates (T1 compact overview, T2 full_arch prices, T6 concise stage clarification, T7 crown price).

## Allowlist

| File | Role |
|------|------|
| `TASK.md` | governance + completion |
| `docs/evidence/final_scope/FINAL_SCOPE_WIDGET_E2E_RETRY4_SEAM_AUDIT.md` | seam audit |
| `docs/FLAGS_AND_STATUS.md` | retry4 status note |
| `evals/v5/final_scope_widget_e2e_retry4_live_contract.py` | retry4 namespace + budget caps |
| `evals/v5/final_scope_widget_e2e_retry4_live_provider_audit.py` | retry4 provider audit |
| `evals/v5/final_scope_widget_e2e_retry4_live_harness.py` | retry4 harness wrapper |
| `evals/v5/run_final_scope_widget_e2e_retry4_live.py` | retry4 CLI |
| `tests/test_final_scope_widget_e2e_retry4_governance.py` | PRE-CODE / COMPLETION checker |
| `tests/test_final_scope_widget_e2e_retry4_live_harness.py` | offline 8/8 + action context + manual rubric |

**Frozen (byte-identical):** all `final_scope_widget_e2e_retry1_*`, `retry2_*`, `retry3_*` live artifacts, preflight-abort attempt #1, widget matrix.

## Forbidden

- LIVE / LLM / provider calls
- Product code changes
- Verifier changes
- Modify/delete/rename Retry1/Retry2/Retry3 frozen artifacts
- Owner override attempt marker
- Retry4 live before separate owner GO

## Constants (binding)

| Constant | Value |
|----------|-------|
| `MAX_HTTP_TURNS` | 8 |
| `MAX_PROVIDER_CALLS` | 34 |
| ingress / planner / boundary / composer / verifier | 5 / 5 / 8 / 8 / 8 |
| `RETRY_COUNT_MAX` | 0 |
| Planner | `qwen3.7-plus` |
| `A9_PATIENT_SCOPE_AUTHORITY` | ON before import |
| Free-text planner calls | 5 |
| Typed UI turns (no planner) | T2, T6, T7 |
| Manual rubric T1 | compact_overview |
| Manual rubric T2 | full_arch_prices |
| Manual rubric T6 | concise_stage_clarification |
| Manual rubric T7 | crown_price |

## Tests (PRE-CODE + COMPLETION)

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:A9_PATIENT_SCOPE_AUTHORITY = "1"
$bt = Join-Path $env:TEMP ("demo-bot-fsw-r4-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_final_scope_widget_e2e_retry4_governance.py `
  tests/test_final_scope_widget_e2e_retry4_live_harness.py `
  tests/test_final_scope_post_retry3_composer_action_context_governance.py `
  tests/test_final_scope_widget_e2e_retry3_governance.py -q
python evals/v5/run_final_scope_widget_e2e_retry4_live.py --dry-run
git diff --check
```

**STOP after COMPLETION ✅. Retry4 live is separate owner GO.**

## Completion record (FINAL_SCOPE_WIDGET_E2E_RETRY4 pre-live)

| Field | Value |
|-------|-------|
| Baseline HEAD | `6b67e35` |
| PRE-CODE | ✅ |
| COMPLETION | ✅ |
| Offline 8/8 | ✅ `test_fake_provider_executes_all_eight_http_turns_without_network` |
| Manual rubric gates | ✅ T1 compact / T2 full_arch / T6 concise / T7 crown |
| Action context + no price:None | ✅ governed refs T2/T7; all turns ref scan |
| Dry-run CLI | ✅ `run_final_scope_widget_e2e_retry4_live.py --dry-run` |
| Live | ✅ see live record below |

## Completion record (FINAL_SCOPE_WIDGET_E2E_RETRY4 live)

| Field | Value |
|-------|-------|
| Baseline HEAD | `084203e` |
| Live run | ✅ `run_final_scope_widget_e2e_retry4_live.py --live` |
| Automated verdict | **AUTOMATED_PASS** (8/8) |
| Final verdict | `PENDING_MANUAL_REVIEW` |
| Provider budget | 34/34 (retry=0) |
| Planner | 5 calls on turns 1,3,4,5,8 — `qwen3.7-plus` |
| Typed UI planner skip | ✅ T2/T6/T7 |
| `price:None/...` | ✅ none observed |
| Manual review artifact | `final_scope_widget_e2e_retry4_manual_review.json` |
| Rerun | **BLOCKED** without new owner GO |
| A9 flag | **kept** (not auto-removed) |

### Immutable SHA pins (retry4 live @ `084203e`)

| Artifact | SHA256 |
|----------|--------|
| `final_scope_widget_e2e_retry4_attempt.json` | `3459868df40d47c841ad2ef4eacb38a69be7bb73b42694af30279940dfabc0df` |
| `final_scope_widget_e2e_retry4_call_ledger.jsonl` | `1028f978742ed84480a9f6d22c0b86110bbcecfd3115ccfd55d19c4d9c7112ae` |
| `final_scope_widget_e2e_retry4_live_stdout.log` | `4e140d20b4ffee4abdcf23998e9391ae6e2bf4ac23a1082b20c8a483ddac60eb` |
| `final_scope_widget_e2e_retry4_result.json` | `8778278802f4f4f474cfe8dbb4118f684208a1605aec5cc40b5b3bf003207a03` |
| `final_scope_widget_e2e_retry4_manifest.json` | `46f5ea55537e3514dd8b40d44f37d08f60a4324646aabbecc74d444acc1fba90` |

**STOP.** Owner manual review required before closeout.

---

# TASK — FINAL_SCOPE_WIDGET_E2E_CLOSEOUT (governance)

**Status:** governance COMPLETION ✅ · **NO LIVE / NO LLM / NO Retry5 / NO product code**

**Baseline:** `5ff9893` (`codex/stage-a`)

**Prerequisites:**
- Retry4 live `AUTOMATED_PASS` 8/8 @ `084203e` (artifacts frozen @ `5ff9893`)
- Owner manual verdict: **PASS 8/8** (canonical product verdict)

Seam audits:
- `docs/evidence/final_scope/FINAL_SCOPE_WIDGET_E2E_RETRY4_MANUAL_REVIEW_AUDIT.md` (Checkpoint A)
- `docs/evidence/final_scope/FINAL_SCOPE_WIDGET_E2E_CLOSEOUT_SEAM_AUDIT.md` (Checkpoint B design)

## Goal

Capture owner manual PASS as append-only audit with SHA pins to frozen Retry4 result/manifest/matrix. Design post-E2E closeout (A9 flag removal, unconditional projection/merge) without implementation.

## Allowlist

| File | Role |
|------|------|
| `TASK.md` | governance + completion |
| `docs/evidence/final_scope/FINAL_SCOPE_WIDGET_E2E_RETRY4_MANUAL_REVIEW_AUDIT.md` | Checkpoint A — owner manual PASS |
| `docs/evidence/final_scope/FINAL_SCOPE_WIDGET_E2E_CLOSEOUT_SEAM_AUDIT.md` | Checkpoint B — read-only closeout design |
| `docs/FLAGS_AND_STATUS.md` | closeout governance status |
| `tests/test_final_scope_widget_e2e_closeout_governance.py` | PRE-CODE checker |

**Frozen (byte-identical):** all Retry1–Retry4 live artifacts, A9/A9R/S-series eval artifacts, widget matrix, Retry4 `result.json` (`PENDING_MANUAL_REVIEW` capture).

## Forbidden

- LIVE / LLM / Retry5
- Product code changes (incl. removing `A9_PATIENT_SCOPE_AUTHORITY` — **implementation** phase only)
- Verifier changes
- A9 prompt tuning
- regex/phrase lists
- new selectors/routes
- Editing frozen Retry4 (or prior) live artifacts
- admin/log implementation

## Checkpoint A — manual PASS capture (binding)

| Rule | Value |
|------|-------|
| Canonical owner verdict | **PASS 8/8** |
| Frozen `result.json` `final_verdict` | `PENDING_MANUAL_REVIEW` (not edited) |
| T1 compact | 704 chars accepted |
| T6 wording | non-blocking defer |
| T7 25k vs 31k | grounded; clearer explanation deferred |
| WinError 32 rollover | deferred; not product blocker |

## Checkpoint B — closeout design (implementation blocked)

1. Remove `A9_PATIENT_SCOPE_AUTHORITY` from config, env, docs, tests, harness.
2. Unconditional `project_patient_scope_from_turn_frame` + `merge_effective_scope_axes`.
3. Planner default `qwen3.7-plus` unchanged.
4. Authority axes: extent / jaw / stage only; `reported_context` excluded from product/session.
5. Priority: typed UI > confident A9 current turn > fresh session > unknown.
6. Unknown/ambiguous does not erase session.
7. Session write only after materialized response.
8. Terminal/error/verifier block do not persist scope.
9. AC1→AC2→AC3 + typed UI TurnFrame unchanged.
10. Acceptance: explicit axes, All-on-4 no scope, correction replaces axis, UI priority, freshness/SID, `/ask`+`/ask/stream` parity, no legacy, `rg` zero `A9_PATIENT_SCOPE_AUTHORITY`.

## Tests (PRE-CODE)

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-fsw-closeout-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_final_scope_widget_e2e_closeout_governance.py `
  tests/test_final_scope_widget_e2e_retry4_governance.py `
  tests/test_final_scope_post_retry3_composer_action_context_governance.py `
  tests/test_final_scope_widget_e2e_retry3_governance.py -q
git diff --check
```

**STOP after COMPLETION ✅. Closeout implementation is separate owner GO.**

## Completion record (FINAL_SCOPE_WIDGET_E2E_CLOSEOUT governance)

| Field | Value |
|-------|-------|
| Baseline HEAD | `5ff9893` |
| PRE-CODE | ✅ |
| Checkpoint A manual PASS audit | ✅ `FINAL_SCOPE_WIDGET_E2E_RETRY4_MANUAL_REVIEW_AUDIT.md` |
| Checkpoint B closeout seam audit | ✅ `FINAL_SCOPE_WIDGET_E2E_CLOSEOUT_SEAM_AUDIT.md` |
| Retry4 artifacts | frozen unchanged (`PENDING_MANUAL_REVIEW` capture) |
| Canonical owner verdict | **PASS 8/8** |
| A9 flag | **kept** until implementation GO |
| Closeout implementation | **STOP** |

---

# TASK — FINAL_SCOPE_WIDGET_E2E_CLOSEOUT (implementation)

**Status:** implementation COMPLETION ✅ · **FINAL_SCOPE_CLOSEOUT_COMPLETE**

**Baseline:** `3adc0e7` (governance COMPLETION ✅)

**Owner GO:** remove `A9_PATIENT_SCOPE_AUTHORITY`; unconditional A9 projection + per-axis merge; frozen Retry1–4 artifacts immutable.

Seam audit: `docs/evidence/final_scope/FINAL_SCOPE_WIDGET_E2E_CLOSEOUT_SEAM_AUDIT.md`

## Allowlist

| File | Role |
|------|------|
| `TASK.md` | completion |
| `config.py` | remove A9 flag |
| `core/target_effective_scope.py` | unconditional merge |
| `core/target_runtime_turn.py` | unconditional projection |
| `core/target_runtime_session.py` | unconditional session write path |
| `evals/v5/final_scope_widget_e2e_live_contract.py` | drop A9 preflight |
| `evals/v5/final_scope_widget_e2e_live_harness.py` | drop A9 env/checks |
| `evals/v5/final_scope_widget_e2e_retry{1,2,3,4}_live_contract.py` | drop REQUIRES_A9 export |
| `evals/v5/run_final_scope_widget_e2e*.py` | drop dry-run A9 field |
| `docs/FLAGS_AND_STATUS.md` | unconditional authority note |
| `tests/test_final_scope_widget_e2e_closeout_implementation.py` | COMPLETION checker |
| `tests/test_final_scope_widget_e2e_closeout_governance.py` | flag-absent gate |
| `tests/test_a9r3_{completion,product_authority}_offline.py` | drop flag fixtures |
| `tests/test_session_patient_facts_offline.py` | drop flag fixture |
| `tests/test_final_scope_*_live_harness.py` | drop A9 env fixtures |
| `tests/test_final_scope_post_retry3_composer_action_context_offline.py` | drop A9 env |

**Frozen (byte-identical):** all Retry1–Retry4 live artifacts, A9/A9R/S-series eval artifacts, widget matrix, historical evidence docs.

## Forbidden

- LIVE / LLM / Retry5
- Verifier / Planner prompt changes
- A9 prompt tuning
- regex/phrase lists
- new selectors/routes
- AC1→AC3 / typed UI TurnFrame changes
- editing frozen live artifacts or historical seam audits

## Tests (COMPLETION)

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-fsw-closeout-impl-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_final_scope_widget_e2e_closeout_implementation.py `
  tests/test_final_scope_widget_e2e_closeout_governance.py `
  tests/test_a9r3_product_authority_offline.py `
  tests/test_a9r3_completion_offline.py `
  tests/test_session_patient_facts_offline.py `
  tests/test_final_scope_widget_e2e_retry4_live_harness.py `
  tests/test_final_scope_post_retry3_composer_action_context_offline.py `
  tests/test_final_scope_widget_e2e_retry4_governance.py `
  tests/test_final_scope_post_retry3_composer_action_context_governance.py `
  tests/test_final_scope_widget_e2e_retry3_governance.py -q
git diff --check
```

## Completion record (FINAL_SCOPE_WIDGET_E2E_CLOSEOUT implementation)

| Field | Value |
|-------|-------|
| Baseline HEAD | `3adc0e7` |
| COMPLETION | ✅ |
| A9 flag removed | ✅ `config.py` + product/harness/tests |
| Unconditional merge | ✅ `resolve_effective_scope` always merges |
| Unconditional projection | ✅ `target_runtime_turn` always projects |
| Session write | ✅ unconditional `_apply_a9_patient_facts_to_state` |
| Frozen Retry4 artifacts | ✅ unchanged (`PENDING_MANUAL_REVIEW` capture) |
| Offline pytest | ✅ 74 passed |
| **FINAL_SCOPE_CLOSEOUT_COMPLETE** | ✅ |

---

# TASK — FINAL_PRICE_AND_SERVICE_COVERAGE (governance)

**Status:** implementation COMPLETE · **NO LIVE / NO LLM / NO Retry5**

**Baseline:** `bc4679b` governance · implementation @ `codex/stage-a`

**Owner GO:** Phase 2 implementation + COMPLETION checker + commit/push.

Seam audit: `docs/evidence/price_service/FINAL_PRICE_AND_SERVICE_COVERAGE_SEAM_AUDIT.md`
Canonical law: `docs/PRICE_SERVICE_ARCHITECTURE.md`

## Goal

Architecturally close four price/service coverage situations without breaking rich demo pricebook paths. Separate service presence, catalog detail, and price detail. Add typed **family-level price** for limited-data packs; verify existing `no_public_price`, `service_not_offered`, and clinic-authored alternatives through FullContext runtime — fix product code only on proven gap.

## Four situations (binding)

| # | Situation | Approach |
|---|-----------|----------|
| 1 | Service exists, no public price | Preserve `no_public_price` + `approved_text`; verify + offline coverage |
| 2 | Not offered + authored alternative | Preserve ingress + `clinic_policies.yaml`; verify + offline coverage |
| 3 | Not offered, no alternative | Preserve ingress template; verify + offline coverage |
| 4 | Family-only price (detailed or umbrella catalog) | New `pricebook/family_prices.json` + deterministic broad mode A/B |

## Price precedence (binding)

1. Service-specific price
2. Typed `no_public_price`
3. Family-level price
4. Controlled data-gap (no numbers)

Family price **never** becomes a named protocol price.

## Broad family price modes (data-driven)

| Mode | Signal | Behavior |
|------|--------|----------|
| A | Scope-specific authored prices exist | Existing AC2/AC3 + scope-nav buttons |
| B | Only family-level price | Single family price; no scope-nav without finer prices |

## Canonical data contract (implementation)

```
clients/<client_id>/target_response/pricebook/family_prices.json
```

Fields: `topic`, `price` (`from`/`fixed`/`range`), `applies_to_service_ids`, `approved_context`. Loaded into `ResponseSchemaBundle` — **no synthetic family service**.

## Allowlist (governance)

| File | Role |
|------|------|
| `TASK.md` | governance + completion |
| `docs/evidence/price_service/FINAL_PRICE_AND_SERVICE_COVERAGE_SEAM_AUDIT.md` | read-only seam audit |
| `docs/FLAGS_AND_STATUS.md` | milestone status note |
| `tests/test_final_price_and_service_coverage_governance.py` | PRE-CODE checker |

## Allowlist (implementation — blocked until PRE-CODE ✅)

| File | Role |
|------|------|
| `contracts/response_schema.py` | `TargetFamilyPrice` + bundle field |
| `core/response_schema_loader.py` | load `family_prices.json` |
| `core/target_family_price_resolution.py` | precedence + broad mode A/B |
| `core/target_scope_aware_selection.py` | family-only anchor path |
| `core/target_scope_aware_price_package.py` | suppress scope-nav mode B |
| `core/target_response_stage.py` | stage signals if needed |
| `core/target_response_policy.py` | family-only composer directive |
| `tests/test_final_price_and_service_coverage_implementation.py` | focused acceptance A–L |
| `tests/test_final_price_and_service_coverage_sparse_fixtures.py` | in-memory sparse packs |
| `tests/test_final_price_and_service_coverage_existing_paths.py` | branches 1–3 verify |

**Frozen (byte-identical):** Retry1–4 live artifacts, A9/A9R/S-series, W1b checksums, widget matrix.

## Forbidden

- LIVE / LLM / Retry5
- A9 / Planner prompt tuning
- Verifier redesign
- regex/phrase stop-lists
- second selector, thresholds, voting, retry
- new LLM calls, feature flags, parallel price authority
- hardcode implantation/prosthetics in shared core
- new parallel handlers for branches 1–3
- editing frozen live artifacts
- W1b restore
- fictional runtime client packs (sparse data = in-memory test fixtures only)

## Acceptance matrix (implementation)

| ID | Case |
|----|------|
| A | Rich demo — existing behavior equivalent |
| B | Service-specific price beats family price |
| C | `no_public_price` beats family fallback |
| D | Detailed catalog + family-only price — broad family; no false protocol price |
| E | Umbrella service + family-only — family price; no scope buttons; protocol not confirmed separately |
| F | Not offered + authored alternative — controlled + approved ref only |
| G | Not offered, no alternative — plain controlled; no substitute buttons |
| H | Exists + typed `no_public_price` — `approved_text`; no invented numbers |
| I | Exists, price record missing — data-gap; no cross-service price |
| J | `/ask` + `/ask/stream` parity |
| K | Full rich pricebook — broad/scoped/concrete unchanged |
| L | No `price:None/...`, false scope refs, legacy routes |

## Tests (PRE-CODE)

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-fpsc-gov-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_final_price_and_service_coverage_governance.py `
  tests/test_final_scope_widget_e2e_closeout_implementation.py `
  tests/test_final_scope_widget_e2e_retry4_governance.py -q
git diff --check
```

**STOP after PRE-CODE ✅. Implementation is separate step in same milestone.**

## Completion record (FINAL_PRICE_AND_SERVICE_COVERAGE governance)

| Field | Value |
|-------|-------|
| Baseline HEAD | `696f77d` |
| PRE-CODE | ✅ @ `bc4679b` |
| Seam audit | ✅ |
| Implementation | ✅ COMPLETE |

---

# TASK — FINAL_PRICE_AND_SERVICE_COVERAGE (implementation)

**Status:** COMPLETE

**Baseline:** governance `bc4679b` · implementation pending commit

## Tests (COMPLETION — after implementation)

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-fpsc-impl-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_final_price_and_service_coverage_implementation.py `
  tests/test_final_price_and_service_coverage_sparse_fixtures.py `
  tests/test_final_price_and_service_coverage_existing_paths.py `
  tests/test_final_price_and_service_coverage_governance.py `
  tests/test_ac3_scope_price_flow_offline.py `
  tests/test_target_scope_aware_selection_offline.py `
  tests/test_w1_family_price_overview_offline.py `
  tests/test_a9r3_product_authority_offline.py `
  tests/test_final_scope_widget_e2e_retry4_live_harness.py `
  tests/test_final_scope_widget_e2e_closeout_implementation.py `
  tests/test_final_scope_widget_e2e_retry4_governance.py -q
python -m pytest --collect-only -q
git diff --check
```

## Completion record (FINAL_PRICE_AND_SERVICE_COVERAGE implementation)

| Field | Value |
|-------|-------|
| Baseline HEAD | `bc4679b` |
| COMPLETION | ✅ 125 passed (focused + safe-wide offline) |
| Acceptance A–L | ✅ |
| Frozen artifacts | ✅ unchanged |

---

# TASK — FINAL_PRICE_SCOPE_COVERAGE_NAV (governance)

**Status:** governance COMPLETION pending · **NO LIVE / NO LLM / NO product code**

**Baseline:** `f5c5c96` (`codex/stage-a`) · **FINAL_PRICE_AND_SERVICE_COVERAGE complete**

**Owner GO:** Phase 1 governance + PRE-CODE only. Implementation blocked until PRE-CODE ✅.

Seam audit: `docs/evidence/price_service/FINAL_PRICE_SCOPE_COVERAGE_NAV_SEAM_AUDIT.md`
Canonical law: `docs/PRICE_SERVICE_ARCHITECTURE.md`

## Goal

Separate service situational applicability from offer price-route applicability. Scope anchors and scope-nav buttons appear only for extents with a confirmed authored price route. Scoped `few_teeth` without a dedicated route must not inherit one-tooth price evidence.

## Problem (binding)

`target:ui_scope/implantation/few_teeth` is recognized correctly through AC1, but AC2 treats service applicability as price applicability (`classic` + `few_teeth` → `classic.one_tooth.*` offers).

## Minimal contract

`TargetOffer.applies_to_extents: list[PatientExtent]` (optional; explicit on demo rich offers).

## Normative broad / nav behavior (binding)

| Confirmed routes | Anchors | Buttons |
|------------------|---------|---------|
| `one_tooth` + `full_arch` | both | «Один зуб», «Все зубы на челюсти» |
| `one_tooth` only | one-tooth | «Один зуб» only |
| all three extents priced | three | three |
| `family_only_broad` | family price | none |

Scoped `few_teeth` without route: `data_gap` (no digits) or family-level with disclaimer — never one-tooth price as final.

**Out of scope:** adjacent/teeth-location clarification, new patient axis, nested menus.

## Allowlist (governance)

| File | Role |
|------|------|
| `TASK.md` | governance + completion |
| `docs/evidence/price_service/FINAL_PRICE_SCOPE_COVERAGE_NAV_SEAM_AUDIT.md` | seam audit |
| `docs/FLAGS_AND_STATUS.md` | milestone note |
| `tests/test_final_price_scope_coverage_nav_governance.py` | PRE-CODE checker |

## Allowlist (implementation — blocked until PRE-CODE ✅)

| File | Role |
|------|------|
| `contracts/response_schema.py` | `applies_to_extents` on `TargetOffer` |
| `contracts/target_scope_aware_selection.py` | `price_confirmed_extents` on result |
| `core/target_offer_extent_applicability.py` | filter + default inference |
| `core/target_offer_projection.py` | extent filter in projection |
| `core/target_scope_aware_selection.py` | anchors + scoped gap |
| `core/target_client_ui_nav.py` | filtered scope-nav |
| `core/target_scope_aware_price_package.py` | wire confirmed extents |
| `clients/demo/target_response/pricebook/services/*.json` | explicit extents on offers |
| `tests/test_final_price_scope_coverage_nav_implementation.py` | acceptance A–J |
| `tests/test_final_price_scope_coverage_nav_sparse_fixtures.py` | in-memory packs |

**Frozen (byte-identical):** Retry1–4 live artifacts, A9/A9R/S-series, W1b checksums, widget matrix.

## Forbidden

- LIVE / LLM
- Verifier redesign
- new patient axes / quantity clarification UI
- regex stop-lists, feature flags, second selector
- frozen live artifact edits
- W1b restore

## Acceptance matrix (implementation)

| ID | Case |
|----|------|
| A | Rich demo broad — anchors `one_tooth`+`full_arch`; buttons only for confirmed routes |
| B | Only `one_tooth` priced — single anchor + single button |
| C | All three extents priced — three anchors + three buttons |
| D | `few_teeth` click without route — data_gap/family; no one-tooth evidence |
| E | `one_tooth` click — scoped price unchanged |
| F | `family_only_broad` — no scope buttons (FPS regression) |
| G | Rich pricebook full_arch / concrete paths unchanged |
| H | No multiply / cross-extent substitution |
| I | `/ask` + `/ask/stream` parity smoke |
| J | Frozen artifacts unchanged |

## Tests (PRE-CODE)

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-pscn-gov-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_final_price_scope_coverage_nav_governance.py `
  tests/test_final_price_and_service_coverage_implementation.py `
  tests/test_final_scope_widget_e2e_closeout_implementation.py `
  tests/test_final_scope_widget_e2e_retry4_governance.py -q
git diff --check
```

**STOP after PRE-CODE ✅. Implementation is separate step.**

## Completion record (FINAL_PRICE_SCOPE_COVERAGE_NAV governance)

| Field | Value |
|-------|-------|
| Baseline HEAD | `f5c5c96` |
| PRE-CODE | ✅ @ `031d766` |
| Seam audit | ✅ |
| Implementation | ✅ COMPLETE |

---

# TASK — FINAL_PRICE_SCOPE_COVERAGE_NAV (implementation)

**Status:** COMPLETE

**Baseline:** governance `031d766`

## Tests (COMPLETION — after implementation)

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-pscn-impl-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_final_price_scope_coverage_nav_implementation.py `
  tests/test_final_price_scope_coverage_nav_sparse_fixtures.py `
  tests/test_final_price_scope_coverage_nav_governance.py `
  tests/test_final_price_and_service_coverage_implementation.py `
  tests/test_ac3_scope_price_flow_offline.py `
  tests/test_target_scope_aware_selection_offline.py `
  tests/test_target_client_ui_nav.py `
  tests/test_final_scope_widget_e2e_retry4_live_harness.py `
  tests/test_final_scope_widget_e2e_closeout_implementation.py `
  tests/test_final_scope_widget_e2e_retry4_governance.py -q
python -m pytest --collect-only -q
git diff --check
```

## Completion record (FINAL_PRICE_SCOPE_COVERAGE_NAV implementation)

| Field | Value |
|-------|-------|
| Baseline HEAD | `031d766` |
| COMPLETION | ✅ 105 passed (focused + safe-wide offline) |
| Acceptance A–J | ✅ |
| Frozen artifacts | ✅ unchanged |

---

# TASK — FINAL_PROSTHETICS_PRICE_NAV_REACHABILITY (governance)

**Status:** governance COMPLETION pending · **NO LIVE / NO LLM / NO A9 tuning / NO product code**

**Baseline:** `2b5e90d` (`codex/stage-a`) · **FINAL_PRICE_SCOPE_COVERAGE_NAV complete**

**Owner GO:** Phase 1 governance + PRE-CODE only. Implementation blocked until PRE-CODE ✅.

Seam audit: `docs/evidence/price_service/FINAL_PROSTHETICS_PRICE_NAV_REACHABILITY_SEAM_AUDIT.md`
Canonical law: `docs/PRICE_SERVICE_ARCHITECTURE.md`

## Goal

Fix prosthetics price navigation: `one_tooth` must be **navigable** when price is reachable via exactly one existing governed `UiStageAction`, without breaking implantation scope-nav or full pricebook paths.

## Problem (binding)

`price_confirmed_extents` today = immediate AC2 anchors only. Prosthetics `one_tooth` needs stage (`natural_tooth_present` → 25k; `implant_placed` → 31k) but broad nav hides the button.

## Concepts (binding)

| Term | Meaning |
|------|---------|
| **Immediate coverage** | Direct AC2 numeric offer or `no_public_price` for extent + known stage |
| **Navigable coverage** | Immediate OR one-hop `discover_stage_clarification_stages()` + AC2 confirmed offer |

Scope buttons use **navigable**; broad text anchors use **immediate** (owner demo price list).

## Reachability algorithm (binding)

Per authored extent:

1. AC2 with extent + current stage → immediate if offer/`no_public_price`
2. Else `discover_stage_clarification_stages()` → for each stage, AC2 trial
3. If any stage path confirmed → navigable
4. Max depth: **one** stage; no recursion; no LLM

## Rules (binding)

- Remove `offer_id` inference from `target_offer_extent_applicability.py`
- Explicit `applies_to_extents` on rich-demo priced offers
- No regex / phrase lists / new medical axes / second selector
- Reuse AC1→AC2→AC3, `UiScopeAction`, `UiStageAction`, existing stage clarify
- Implantation `few_teeth` stays hidden without confirmed path

## Allowlist (governance)

| File | Role |
|------|------|
| `TASK.md` | governance + completion |
| `docs/evidence/price_service/FINAL_PROSTHETICS_PRICE_NAV_REACHABILITY_SEAM_AUDIT.md` | seam audit |
| `docs/FLAGS_AND_STATUS.md` | milestone note |
| `tests/test_final_prosthetics_price_nav_reachability_governance.py` | PRE-CODE checker |

## Allowlist (implementation — blocked until PRE-CODE ✅)

| File | Role |
|------|------|
| `core/target_offer_price_reachability.py` | immediate + navigable helper |
| `core/target_offer_extent_applicability.py` | remove offer_id inference |
| `contracts/target_scope_aware_selection.py` | `price_navigable_extents` |
| `core/target_scope_aware_selection.py` | reachability integration |
| `core/target_scope_aware_price_package.py` | navigable scope-nav |
| `clients/demo/target_response/pricebook/services/zirconia_crowns.default.json` | explicit extents |
| `clients/demo/target_response/pricebook/services/implant_supported_prosthetics.default.json` | explicit extents |
| `clients/demo/target_response/pricebook/services/*.json` | remaining explicit `applies_to_extents` as needed |
| `tests/test_final_prosthetics_price_nav_reachability_implementation.py` | acceptance 1–16 |
| `tests/test_final_prosthetics_price_nav_reachability_sparse_fixtures.py` | in-memory sparse packs |

**Frozen (byte-identical):** Retry1–4, A9/A9R/S-series, W1b, widget matrix.

## Forbidden

- LIVE / LLM / A9 tuning / Planner prompt changes
- Verifier redesign
- regex / phrase stop-lists
- recursive stage tree / new medical axes / second selector
- frozen live artifact edits
- W1b restore

## Acceptance matrix (implementation)

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
| 11 | No `offer_id` inference for applicability |
| 12 | Sparse: only one-tooth route → one button |
| 13 | Sparse: stage-only path → button shown |
| 14 | Sparse: stage paths without prices → hidden |
| 15 | `/ask` + `/ask/stream` parity |
| 16 | Rich pricebook + frozen artifacts unchanged |

## Tests (PRE-CODE)

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-ppr-gov-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_final_prosthetics_price_nav_reachability_governance.py `
  tests/test_final_price_scope_coverage_nav_implementation.py `
  tests/test_final_scope_widget_e2e_closeout_implementation.py `
  tests/test_final_scope_widget_e2e_retry4_governance.py -q
git diff --check
```

**STOP after PRE-CODE ✅.**

## Completion record (FINAL_PROSTHETICS_PRICE_NAV_REACHABILITY governance)

| Field | Value |
|-------|-------|
| Baseline HEAD | `2b5e90d` |
| PRE-CODE | pending |
| Seam audit | pending |
| Implementation | **STOP** |

---

# TASK — FINAL_PROSTHETICS_PRICE_NAV_REACHABILITY (implementation)

**Status:** blocked until governance PRE-CODE ✅

**Baseline:** governance COMPLETION @ `2b5e90d`

## Tests (COMPLETION — after implementation)

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-ppr-impl-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_final_prosthetics_price_nav_reachability_implementation.py `
  tests/test_final_prosthetics_price_nav_reachability_sparse_fixtures.py `
  tests/test_final_prosthetics_price_nav_reachability_governance.py `
  tests/test_final_price_scope_coverage_nav_implementation.py `
  tests/test_final_price_and_service_coverage_implementation.py `
  tests/test_ac3_scope_price_flow_offline.py `
  tests/test_target_scope_aware_selection_offline.py `
  tests/test_final_scope_widget_e2e_closeout_implementation.py `
  tests/test_final_scope_widget_e2e_retry4_governance.py -q
python -m pytest --collect-only -q
git diff --check
```

## Completion record (FINAL_PROSTHETICS_PRICE_NAV_REACHABILITY implementation)

| Field | Value |
|-------|-------|
| Baseline HEAD | `2b5e90d` |
| Implementation HEAD | `19297fc` |
| COMPLETION | ✅ |
| Acceptance 1–16 | ✅ |
| Frozen artifacts | ✅ |

---

# TASK — FINAL_EXPLICIT_SERVICE_PRICE_LOOKUP_BOUNDARY (governance)

**Status:** governance COMPLETION pending · **NO LIVE / NO LLM / NO A9 tuning / NO product code**

**Baseline:** `19297fc` (`codex/stage-a`) · **FINAL_PROSTHETICS_PRICE_NAV_REACHABILITY complete**

**Owner GO:** Phase 1 governance + PRE-CODE only. Implementation blocked until PRE-CODE ✅.

Seam audit: `docs/evidence/price_service/FINAL_EXPLICIT_SERVICE_PRICE_LOOKUP_BOUNDARY_SEAM_AUDIT.md`
Canonical law: `docs/PRICE_SERVICE_ARCHITECTURE.md`

## Goal

Separate **commercial catalog lookup** (user explicitly names a service and asks price) from **patient applicability** (broad/scoped recommendation) inside existing AC2/AC3 — without a second pipeline, session reset, or eligibility claims.

## Problem (binding)

Cross-turn: session `extent=full_arch` → user asks «А сколько стоит одномоментная имплантация?» with `service_id=one_stage`. Inherited session scope filters out the service (`one_stage` requires `one_tooth|few_teeth` + `extraction_context`) → empty evidence → `target_fullcontext_error`.

## Normative rule (binding)

When **all** hold:

- `service_id` explicitly and confidently set on current turn;
- intent/aspect includes price;
- service active in client catalog;

execute **explicit service price lookup**:

- target via existing `explicit_service_id` / `spec.service_id`;
- inherited session patient scope **must not block** structured price lookup;
- missing `extraction_context` **must not block** `one_stage` catalog price;
- offers only from canonical target pricebook;
- `applies_to_extents` + billing unit remain authoritative for value/unit;
- response **must not** claim patient eligibility;
- optional brief note that applicability is determined after diagnostics.

**Current-turn incompatible scope** (e.g. named per-tooth service + current-turn `full_arch`): fail-closed `data_gap`/clarification — no jaw math, no family fallback.

Distinguish axes by existing provenance (`extent_axis.source`: `session` vs `a9_turn` / `ui_action` / `ui_stage_action`). **No regex.**

## Session semantics (binding)

- Do not clear session or `patient_facts`.
- Do not write service name as patient fact.
- Vague follow-up without new `service_id` keeps existing session focus.
- Materialized answer may update ordinary service focus.

## Unchanged (binding)

AC1 typed UI · AC2 broad applicability · AC3 broad/scoped family price · offer reachability · Planner · A9 · Verifier · medical boundary · session schema · service similarity · logging · frozen artifacts.

## Allowlist (governance)

| File | Role |
|------|------|
| `TASK.md` | governance + completion |
| `docs/evidence/price_service/FINAL_EXPLICIT_SERVICE_PRICE_LOOKUP_BOUNDARY_SEAM_AUDIT.md` | seam audit |
| `docs/FLAGS_AND_STATUS.md` | milestone note |
| `tests/test_final_explicit_service_price_lookup_boundary_governance.py` | PRE-CODE checker |

## Allowlist (implementation — blocked until PRE-CODE ✅)

| File | Role |
|------|------|
| `core/target_explicit_service_price_lookup.py` | lookup vs applicability boundary helpers |
| `core/target_service_applicability.py` | explicit lookup bypass inherited session gate |
| `core/target_offer_projection.py` | lookup context for extent filter |
| `core/target_offline_response_assembly.py` | wire lookup into S23 |
| `core/target_scope_aware_selection.py` | explicit_service_id lookup path |
| `core/target_response_stage.py` | incompatible current-turn → data_gap |
| `core/target_strategy_context.py` | lookup patient context from axis provenance |
| `tests/test_final_explicit_service_price_lookup_boundary_implementation.py` | acceptance 1–18 |
| `tests/test_final_explicit_service_price_lookup_boundary_sparse_fixtures.py` | in-memory multiclient packs |
| `tests/test_final_explicit_service_price_lookup_boundary_cross_turn_matrix.py` | parameterized cross-turn regression |

**Frozen (byte-identical):** Retry1–4, A9/A9R/S-series, W1b, widget matrix.

## Forbidden

- LIVE / LLM / A9 tuning / Planner prompt changes
- Verifier redesign
- regex / phrase stop-lists
- session clear workaround
- `one_stage` hardcode
- demo client IDs in shared core
- new pricing route / selector
- family price fallback for named protocol
- eligibility claims
- frozen live artifact edits

## Acceptance matrix (implementation)

| ID | Case |
|----|------|
| 1 | Session `full_arch` → explicit `one_stage` price materialized |
| 2 | Session `one_tooth` → explicit `all_on_4` jaw prices |
| 3 | Session `full_arch` → explicit zirconia from 25 000 ₽ |
| 4 | Explicit `one_stage`, stage unknown — price shown |
| 5 | Explicit service + compatible current-turn scope |
| 6 | Explicit service + incompatible current-turn scope → data_gap |
| 7 | Named service, no public price → existing path |
| 8 | Named service absent → not-offered path |
| 9 | Vague follow-up without new `service_id` — session continuity |
| 10 | Broad implantation overview unchanged |
| 11 | Typed scope/stage clicks unchanged |
| 12 | Informational turn without price — no lookup |
| 13 | No eligibility / treatment choice claims |
| 14 | Exact prices, brands, billing units preserved |
| 15 | `/ask` + `/ask/stream` parity |
| 16 | SID isolation / reset / terminal rules unchanged |
| 17 | Sparse multiclient fixture — no demo IDs in core |
| 18 | Frozen artifacts byte-identical |

**Cross-turn matrix (offline):** each authored session extent × each active priced service explicit ask — no generic error; exact applicability + billing unit.

## Tests (PRE-CODE)

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-espl-gov-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_final_explicit_service_price_lookup_boundary_governance.py `
  tests/test_final_prosthetics_price_nav_reachability_implementation.py `
  tests/test_final_price_scope_coverage_nav_implementation.py `
  tests/test_final_scope_widget_e2e_closeout_implementation.py `
  tests/test_final_scope_widget_e2e_retry4_governance.py -q
git diff --check
```

**STOP after PRE-CODE ✅.**

## Completion record (FINAL_EXPLICIT_SERVICE_PRICE_LOOKUP_BOUNDARY governance)

| Field | Value |
|-------|-------|
| Baseline HEAD | `19297fc` |
| PRE-CODE | ✅ |
| Seam audit | ✅ |
| Implementation | ✅ |

---

# TASK — FINAL_EXPLICIT_SERVICE_PRICE_LOOKUP_BOUNDARY (implementation)

**Status:** blocked until governance PRE-CODE ✅

**Baseline:** governance COMPLETION @ `19297fc`

## Tests (COMPLETION — after implementation)

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-espl-impl-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_final_explicit_service_price_lookup_boundary_implementation.py `
  tests/test_final_explicit_service_price_lookup_boundary_sparse_fixtures.py `
  tests/test_final_explicit_service_price_lookup_boundary_cross_turn_matrix.py `
  tests/test_final_explicit_service_price_lookup_boundary_governance.py `
  tests/test_final_prosthetics_price_nav_reachability_implementation.py `
  tests/test_final_price_scope_coverage_nav_implementation.py `
  tests/test_ac3_scope_price_flow_offline.py `
  tests/test_target_scope_aware_selection_offline.py `
  tests/test_final_scope_widget_e2e_closeout_implementation.py `
  tests/test_final_scope_widget_e2e_retry4_governance.py -q
python -m pytest --collect-only -q
git diff --check
```

## Completion record (FINAL_EXPLICIT_SERVICE_PRICE_LOOKUP_BOUNDARY implementation)

| Field | Value |
|-------|-------|
| Baseline HEAD | `10e6926` |
| Implementation HEAD | `836250f` |
| COMPLETION | ✅ |
| Acceptance 1–18 | ✅ |
| Cross-turn matrix | ✅ |
| Frozen artifacts | ✅ |

---

# TASK — FINAL_CLIENT_PACK_DATA_CONVERGENCE (governance)

**Status:** Checkpoint A ✅ @ `e3730ea`; Checkpoint B governance PRE-CODE (implementation blocked)
**Baseline:** `e3730ea` (`codex/stage-a`)
**Mode:** governance/docs/tests only · **NO LIVE / NO LLM / NO A9 tuning**

## Goal

Свести `clients/demo` к одному FullContext authoring source на каждый домен до
добавления двух новых клиник. Demo становится reference pack; новая клиника не должна
создавать или синхронизировать legacy mirror-файлы.

Canonical seam audit:
`docs/evidence/client_pack/FINAL_CLIENT_PACK_DATA_CONVERGENCE_SEAM_AUDIT.md`.

## Canonical ownership

| Данные | Единственный целевой источник |
|---|---|
| Services, aliases, applicability, options | `target_response/service_catalog.json` |
| Offers, amounts, packages, billing units, payment | `target_response/pricebook/services/*.json` |
| Promotions, installment, warranty, consultation facts | `target_response/pricebook/facts.json` |
| Optional broad family price | `target_response/pricebook/family_prices.json` |
| Product brands and aliases | `target_response/brand_catalog.json` |
| Marketing source policy | `target_response/marketing.yaml` |
| Service/offer priorities | `target_response/clinic_strategy.yaml` |
| Clinic content | `md/*.md` |
| Doctors | `doctor_catalog.json` |
| Operational clinic restrictions/hours/contacts | `clinic_policies.yaml` |
| Widget clinic identity | `brand.yaml` |
| Visible UI labels | `ui.yaml` / `tone.yaml` |

`brand.yaml` ≠ `target_response/brand_catalog.json`;
`clinic_policies.yaml` ≠ `target_response/clinic_strategy.yaml`.

## Checkpoint A — canonical reader convergence

Implementation is blocked until PRE-CODE ✅ and separate owner GO.

Required behavior:

1. One client-aware cached loader exposes the target response bundle to Planner and
   response runtime.
2. Planner compact services use target `name`, aliases, family/selection metadata.
   Legacy free-form service `facts` are not copied into Planner.
3. Planner allowed brand/group values derive from target brands/offers.
4. Catalog matching, follow-up labels and doctor topic availability use target services.
5. Startup validates canonical MD + target response schema + doctors + external refs.
6. Product modules have zero reads/import dependency on root legacy catalog/pricebook/
   marketing/brand aliases.
7. Old sources remain byte-identical during A only for parity/delta proof.
8. Rich demo behavior and sparse second-client fixtures remain green.

### Checkpoint A implementation allowlist

- `core/target_client_data.py` (new)
- `core/target_query_cues.py` (new)
- `core/response_schema_loader.py`
- `core/target_runtime_client_context.py`
- `core/catalog_match.py`
- `core/turn_planner_llm.py`
- `core/follow_up_rewrite.py`
- `core/dialog_focus.py`
- `core/startup_check.py`
- `orchestration/planner_turn.py`
- `doctors_lookup.py`
- `ingress_gate.py`
- `tests/test_final_client_pack_data_convergence_reader_cutover.py` (new)
- `tests/test_final_client_pack_data_convergence_sparse_pack.py` (new)
- `tests/test_final_client_pack_data_convergence_governance.py`
- `tests/test_turn_planner_llm.py`
- `tests/test_catalog_match.py`
- `tests/test_follow_up_rewrite.py`
- `tests/test_dialog_focus_baseline.py`
- `tests/test_demo_doctor_catalog.py`
- `tests/test_demo_doctor_template.py`
- `tests/test_response_schema_loader.py`
- `tests/test_c2_import_firewall_offline.py`
- `tests/test_demo_target_service_catalog.py`
- `tests/test_demo_target_price_offers.py`
- `TASK.md`, seam/status docs

**STOP after A checker → commit/push. Checkpoint B requires separate owner GO.**

Post-A seam audit:
`docs/evidence/client_pack/FINAL_CLIENT_PACK_DATA_CONVERGENCE_B_SEAM_AUDIT.md`.

## Checkpoint B — governance (PRE-CODE only)

**Owner GO:** received. **Implementation/delete:** blocked until B PRE-CODE ✅.

### DELETE list — legacy data (27 files)

- `clients/demo/service_catalog.json`
- `clients/demo/marketing.yaml`
- `clients/demo/price_brand_aliases.json`
- `clients/demo/pricebook/facts.json`
- `clients/demo/pricebook/manifest.json`
- `clients/demo/pricebook/README.md`
- `clients/demo/pricebook/services/all_on_4.json`
- `clients/demo/pricebook/services/all_on_6.json`
- `clients/demo/pricebook/services/aligners.json`
- `clients/demo/pricebook/services/caries.json`
- `clients/demo/pricebook/services/clasp_dentures.json`
- `clients/demo/pricebook/services/classic.json`
- `clients/demo/pricebook/services/implant_supported_prosthetics.json`
- `clients/demo/pricebook/services/one_stage.json`
- `clients/demo/pricebook/services/periodontitis.json`
- `clients/demo/pricebook/services/professional_whitening.json`
- `clients/demo/pricebook/services/pterygoid_implants.json`
- `clients/demo/pricebook/services/pulpitis.json`
- `clients/demo/pricebook/services/removable_dentures.json`
- `clients/demo/pricebook/services/sinus_lift.json`
- `clients/demo/pricebook/services/teeth_treatment.json`
- `clients/demo/pricebook/services/temporary_teeth.json`
- `clients/demo/pricebook/services/tomography.json`
- `clients/demo/pricebook/services/tooth_extraction.json`
- `clients/demo/pricebook/services/veneers.json`
- `clients/demo/pricebook/services/zygomatic_implants.json`
- `clients/demo/pricebook/services/zirconia_crowns.json`

### DELETE list — legacy modules / scripts / contracts (21 files)

- `query_selector.py`
- `core/pricebook_loader.py`
- `core/price_offers.py`
- `core/price_scope.py`
- `core/price_followup.py`
- `core/price_answer_assembler.py`
- `core/marketing_loader.py`
- `core/marketing_policy.py`
- `core/promo_overview.py`
- `core/service_selector_llm.py`
- `core/explicit_service.py`
- `core/clarify_state.py`
- `core/patient_situation.py`
- `core/patient_situation_llm.py`
- `core/patient_situation_routing.py`
- `core/patient_situation_session.py`
- `core/patient_scope_cues.py`
- `contracts/price_brand_aliases.py`
- `contracts/service_selection.py`
- `contracts/pricebook.py` (after `scripts/lint_pricebook.py` target rewrite)
- `scripts/migrate_pricebook_services.py`

### DELETE list — legacy-only tests (16 files)

- `tests/test_catalog_typo_match.py`
- `tests/test_explicit_service.py`
- `tests/test_marketing_loader.py`
- `tests/test_marketing_policy.py`
- `tests/test_patient_situation.py`
- `tests/test_patient_situation_routing.py`
- `tests/test_patient_situation_session.py`
- `tests/test_price_offers.py`
- `tests/test_price_scope_router.py`
- `tests/test_pricebook_golden.py`
- `tests/test_pricebook_loader.py`
- `tests/test_promo_overview.py`
- `tests/test_service_selector_llm.py`
- `tests/test_turn_planner_stage3.py`
- `tests/test_vague_price_followup.py`
- `tests/test_final_price_and_service_coverage_existing_paths.py`

### UPDATE list (18 files)

- `config.py` — remove `SERVICE_SELECT_LLM_ON`, `SERVICE_SELECT_LLM_MODEL`, `BRAND_FILTER_ON`, `PRICE_STRICT_SERVICE_ON`
- `session.py` — remove `last_patient_situation` / `patient_situation_turn_age` APIs
- `core/routing.yaml` — remove `patient_situation` thresholds block
- `core/metadata_first_observability.py` — remove island `patient_situation_*` telemetry keys
- `scripts/lint_pricebook.py` — validate `target_response/**` only
- `.github/workflows/ci.yml` — drop deleted legacy tests; add validator + target lint
- `evals/v5/run_patient_scope_shadow_eval.py` — remove legacy session carry simulation
- `tests/test_dialog_focus_baseline.py` — migrate off `query_selector` / `pricebook_loader`
- `tests/test_c2c_service_focus_age_offline.py` — migrate off legacy island
- `tests/test_c2c_session_migration_offline.py` — migrate off legacy island
- `tests/test_demo_doctor_catalog.py` — target catalog cross-ref only
- `tests/test_demo_doctor_template.py` — target catalog cross-ref only
- `tests/test_demo_target_service_catalog.py` — drop legacy CURRENT_PATH parity after delete
- `tests/test_demo_target_price_offers.py` — drop legacy alias parity reads
- `tests/test_metadata_first_observability.py` — remove `core.patient_situation` imports
- `tests/test_final_client_pack_data_convergence_governance.py` — retire legacy SHA pins post-delete
- `tests/test_final_client_pack_data_convergence_reader_cutover.py` — post-delete firewall (no legacy paths)
- `tests/test_final_client_pack_data_convergence_sparse_pack.py` — extend validator coverage

### KEEP list (firewall — do not delete in B)

**Client data:** `clients/demo/target_response/**`, `clients/demo/md/**`,
`clients/demo/doctor_catalog.json`, `clients/demo/brand.yaml`, `clients/demo/clinic_policies.yaml`,
`clients/demo/features.yaml`, `clients/demo/lead_config.yaml`, `clients/demo/tone.yaml`,
`clients/demo/ui.yaml`, `clients/demo/video_catalog.yaml`, `clients/demo/widget_config.json`.

**Product core:** `core/target_client_data.py`, `core/target_query_cues.py`, `core/catalog_match.py`,
`core/target_family_price_resolution.py`, `core/target_scope_aware_selection.py`,
`core/target_scope_aware_price_package.py`, `core/target_offer_projection.py`,
`core/target_offer_price_reachability.py`, `core/target_explicit_service_price_lookup.py`,
`core/attribute_followup.py`, `core/price_ref_routing.py`, `core/response_schema_loader.py`,
`core/target_runtime_client_context.py`, `core/turn_frame_from_raw.py` (scalar `patient_situation` bridge),
`core/turn_planner_llm.py`, AC1→AC3 / A9 / Composer / Verifier modules, frozen eval artifacts.

**Contracts:** `contracts/patient_situation.py` (HISTORICAL COMPATIBILITY KEEP for A9 scalar bridge).

### A9 boundary (binding)

| Surface | B decision |
|---|---|
| Legacy detect/carry island (`patient_situation*.py`, `patient_scope_cues.py`, session carry, `query_selector`) | DELETE NOW |
| Scalar `patient_situation` in `turn_frame_from_raw` + planner enum | HISTORICAL COMPATIBILITY KEEP |
| Remove scalar bridge / retune frozen A9 matrices | Future checkpoint — **NOT B** |

### CREATE list (B implementation — blocked until PRE-CODE ✅)

- `docs/CLIENT_PACK_AUTHORING.md`
- `scripts/validate_client_pack.py`
- `clients/_template/target_response/service_catalog.json`
- `clients/_template/target_response/brand_catalog.json`
- `clients/_template/target_response/marketing.yaml`
- `clients/_template/target_response/clinic_strategy.yaml`
- `clients/_template/target_response/pricebook/facts.json`
- `clients/_template/target_response/pricebook/services/.gitkeep` (or minimal valid offer scaffold)
- `clients/_template/doctor_catalog.json`
- `clients/_template/clinic_policies.yaml`
- `clients/_template/ui.yaml`
- `tests/test_validate_client_pack.py`
- `tests/test_client_pack_template_scaffold.py`

### Implementation allowlist (exact union — blocked until B PRE-CODE ✅)

All paths in DELETE, UPDATE, and CREATE lists above, plus:

- `docs/FLAGS_AND_STATUS.md`
- `tests/test_final_client_pack_data_convergence_b_governance.py`
- `tests/test_c2_import_firewall_offline.py` (post-delete import graph)
- `tests/test_price_ref_routing.py` (KEEP module regression)

### Acceptance matrix (B implementation)

| # | Criterion |
|---|---|
| 1 | Legacy data paths absent; demo loads only via `target_response/**` |
| 2 | Legacy island modules absent; `import app` smoke green |
| 3 | `scripts/validate_client_pack.py` passes on `clients/demo` and sparse non-demo fixture |
| 4 | `clients/_template` validates (scaffold mode OK) without demo IDs/brands |
| 5 | `docs/CLIENT_PACK_AUTHORING.md` maps each edit to exactly one canonical file |
| 6 | `scripts/lint_pricebook.py` lints target pricebook only |
| 7 | CI workflow runs validator + target tests; no deleted legacy tests |
| 8 | Dead config flags removed; session carry APIs removed |
| 9 | All 21 service IDs, 31 offers, 6 facts, brands preserved in target schema |
| 10 | Checkpoint A cutover + sparse pack tests remain green |
| 11 | AC1→AC3, A9 scalar bridge, Composer, Verifier unchanged |
| 12 | Frozen S/A9/Retry/W1b pins unchanged |
| 13 | Import firewall: product modules do not reference deleted paths |
| 14 | `test_final_client_pack_data_convergence_b_governance.py` post-implementation mode green |
| 15 | Wide safe-offline + collect-only green |
| 16 | No new selector / second pipeline / demo hardcodes in shared core |

### Authoring deliverables (implementation)

1. `docs/CLIENT_PACK_AUTHORING.md` with a one-question → one-path edit map.
2. `scripts/validate_client_pack.py` (offline/local only, no network/LLM).
3. `clients/_template` structural parity with canonical required files.
4. Validation fixture for a non-demo client with different IDs/brands/topics.
5. Import/read firewall proving deleted mirrors cannot return.

## Data-retention decisions

- Target service identity, aliases, active flags and content refs must preserve old values.
- Target offers/facts/brands must preserve exact price and product identity.
- Old `price_key`, `price_ref`, `price_display`, `response_mode`, route/aspect policy fields
  are retired mechanics, not migrated schema.
- 24 ungrounded `clinic_proof` / `consult_reasons` strings from root marketing are retired.
  A future clinic claim must be authored as KB, doctor or typed fact source.
- Root service `facts` are not copied to target service records; Planner is a classifier,
  not a second content store.

## Global acceptance

- One authority per domain; no duplicate files with the same clinic fact.
- AC1→AC2→AC3, A9 authority, typed UI TurnFrame, Composer and light Verifier unchanged.
- Exact prices/units/packages/brands/fact dates/doctor links preserved.
- No new selector, regex list, fallback response path or demo hardcode.
- Existing demo full-price paths remain green.
- A sparse second-client pack validates without creating legacy mirrors.
- Focused + wide safe-offline + `tests/` collect-only + frozen pins all green.
- NO LIVE / NO LLM / NO A9 tuning.

## Governance allowlist (Checkpoint B PRE-CODE commit)

- `TASK.md`
- `docs/evidence/client_pack/FINAL_CLIENT_PACK_DATA_CONVERGENCE_B_SEAM_AUDIT.md`
- `docs/FLAGS_AND_STATUS.md`
- `tests/test_final_client_pack_data_convergence_b_governance.py`

Prior Checkpoint A governance files remain frozen except where B implementation explicitly updates them.

## PRE-CODE command (Checkpoint B governance)

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-client-pack-b-gov-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_final_client_pack_data_convergence_b_governance.py `
  tests/test_final_client_pack_data_convergence_governance.py `
  tests/test_final_client_pack_data_convergence_reader_cutover.py `
  tests/test_final_client_pack_data_convergence_sparse_pack.py `
  tests/test_demo_target_service_catalog.py `
  tests/test_demo_target_price_offers.py `
  tests/test_demo_target_marketing_migration_audit.py `
  tests/test_response_schema_loader.py -q
git diff --check
```

## PRE-CODE command (Checkpoint A — historical)

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-client-pack-gov-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_final_client_pack_data_convergence_governance.py `
  tests/test_demo_target_service_catalog.py `
  tests/test_demo_target_price_offers.py `
  tests/test_demo_target_marketing_migration_audit.py `
  tests/test_response_schema_loader.py -q
git diff --check
```

## Focused command (B implementation COMPLETION)

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-client-pack-b-impl-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_final_client_pack_data_convergence_b_governance.py `
  tests/test_final_client_pack_data_convergence_governance.py `
  tests/test_final_client_pack_data_convergence_reader_cutover.py `
  tests/test_final_client_pack_data_convergence_sparse_pack.py `
  tests/test_validate_client_pack.py `
  tests/test_client_pack_template_scaffold.py `
  tests/test_demo_target_service_catalog.py `
  tests/test_demo_target_price_offers.py `
  tests/test_demo_target_marketing_migration_audit.py `
  tests/test_response_schema_loader.py `
  tests/test_c2_import_firewall_offline.py `
  tests/test_price_ref_routing.py -q
git diff --check
```

## Wide safe-offline command (B implementation COMPLETION)

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-client-pack-b-wide-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_final_client_pack_data_convergence_b_governance.py `
  tests/test_final_client_pack_data_convergence_governance.py `
  tests/test_final_client_pack_data_convergence_reader_cutover.py `
  tests/test_final_client_pack_data_convergence_sparse_pack.py `
  tests/test_validate_client_pack.py `
  tests/test_client_pack_template_scaffold.py `
  tests/test_turn_planner_llm.py `
  tests/test_turn_planner_wiring.py `
  tests/test_turn_plan_protocol_guard.py `
  tests/test_catalog_match.py `
  tests/test_follow_up_rewrite.py `
  tests/test_dialog_focus_baseline.py `
  tests/test_dialog_focus_contract.py `
  tests/test_demo_doctor_catalog.py `
  tests/test_demo_doctor_template.py `
  tests/test_demo_target_service_catalog.py `
  tests/test_demo_target_price_offers.py `
  tests/test_demo_target_marketing_policy.py `
  tests/test_demo_target_marketing_migration_audit.py `
  tests/test_response_schema_loader.py `
  tests/test_target_scope_aware_selection_offline.py `
  tests/test_final_price_and_service_coverage_implementation.py `
  tests/test_final_price_scope_coverage_nav_implementation.py `
  tests/test_final_explicit_service_price_lookup_boundary_implementation.py `
  tests/test_c2_import_firewall_offline.py `
  tests/test_price_ref_routing.py `
  tests/test_content_linter.py -q
python -m pytest --collect-only -q
```

## Frozen pin command (B implementation COMPLETION)

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-client-pack-b-frozen-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_final_scope_widget_e2e_closeout_governance.py `
  tests/test_final_explicit_service_price_lookup_boundary_governance.py `
  tests/test_final_price_scope_coverage_nav_governance.py `
  tests/test_ac3_scope_price_flow_offline.py::test_w1b_snapshot_checksums_unchanged -q
```

## STOP conditions (Checkpoint B)

- Legacy mirror missing or byte-changed before implementation delete commit.
- Any DELETE path still has a product importer after fresh audit.
- Scalar A9 bridge removal attempted in B (future checkpoint only).
- Frozen A9 matrices / evidence edited for green tests.
- Implementation artifact created before B PRE-CODE ✅.
- File outside implementation allowlist required.
- `import app` fails after delete.
- Validator passes demo but fails sparse non-demo fixture.
- LIVE / LLM / Composer / Verifier changes required for green.

## STOP

Checkpoint B governance PRE-CODE PASS does not authorize implementation/delete.
**STOP after B PRE-CODE ✅** before any DELETE/CREATE/UPDATE from implementation allowlist.

---

# TASK — FULLCONTEXT_PRESENTATION_PARITY (governance)

**Status:** governance checkpoint only · **NO PRODUCT CHANGE / NO LIVE / NO LLM**

**Baseline:** `codex/stage-a` @ `50c6cf9` (`FINAL_CLIENT_PACK_DATA_CONVERGENCE B complete`)

**Authority:** owner decisions on UI slots (choice menu max 4, secondary max 2); seam audit
`docs/evidence/presentation/FULLCONTEXT_PRESENTATION_PARITY_SEAM_AUDIT.md`.

## Goal

Восстановить механизмы представления и маркетинга, потерянные при переходе на
FullContext-only, не возвращая legacy policy/RAG и не создавая второй pipeline.

Лёгкий typed presentation layer поверх существующих: ResponseSpec, validated source
identity, selected followups, governed UI actions, marketing selection, target session.

## Owner decisions (binding)

### 1. Choice menu — до 4 кнопок

Governed branch selection по typed action/ref (`UiScopeAction`, `UiStageAction`, другие
governed clarification choices). Max 4; deterministic ordering; dedup по ref;
session-bound refs only; fail-closed on invalid ref. Не смешивается с secondary navigation.
CTA не занимает choice slot. Без regex/phrase lists.

### 2. Secondary UI — максимум 2 слота

Content: `suggest_h3`, FAQ/info, service-detail, video (приоритет, 1 sidecar), situation.
Price-detail: max 2 authored service followups; не смешивать с content; scope/stage menu —
лимит 4, не price slots. Shown/clicked не повторяются. CTA и marketing facts слоты не занимают.

## Confirmed gaps (read-only audit)

| Gap | Summary |
|-----|---------|
| **A** | No validated `used_doc_ids`/`content_ref` on verified response → followups/video/situation disconnected |
| **B** | `normalize_policy_payload` caps `md_navigation` to 1 QR vs normative 2 secondary slots |
| **C** | Target widget hardcodes `video=None` despite MD `video_key` + catalog |
| **D** | Target widget hardcodes `situation.show=False` |
| **E** | Runtime passes `marketing_scenarios=()`, `include_initial_block=False` |
| **F** | `semantic_context="service"` hardcoded |
| **G** | Session cadence incomplete (video, followup no-repeat ledger) |

`consultation_value` — preserve on exact service/option path; **intentionally not applicable**
to generic content-only FullContext. Validator checks in implementation phase.

### consultation_value (normative)

- Automatic `consultation_value` — только после exact выбора service/option.
- Generic FAQ/info/comparison content-only ответ **не должен** получать `consultation_value` соседней услуги.
- Прямой вопрос о консультации — основной content из MD/structured commercial fact; это не automatic consultation close; не занимает automatic marketing/amplifier slots.
- Source identity implementation (Gap A) **не должна** расширять applicability `consultation_value` на произвольные `used_doc_ids`.

## Allowlist (governance commit only)

| File | Action |
|------|--------|
| `TASK.md` | UPDATE — this checkpoint |
| `docs/evidence/presentation/FULLCONTEXT_PRESENTATION_PARITY_SEAM_AUDIT.md` | CREATE |
| `docs/MARKETING_SCENARIO_ARCHITECTURE.md` | UPDATE — choice menu 4 + slot clarity |
| `docs/MARKETING_QUESTION_FOUNDATION.md` | UPDATE — choice menu 4 + slot clarity |
| `docs/ARCH_TARGET_DESIGN.md` | UPDATE — owner decision §presentation slots |
| `docs/ARCHITECTURE_CONVERGENCE.md` | UPDATE — gap row + checkpoint |
| `docs/STRANGLER_ROADMAP.md` | UPDATE — checkpoint entry |
| `docs/FLAGS_AND_STATUS.md` | UPDATE — status entry |
| `tests/test_fullcontext_presentation_parity_governance.py` | CREATE — PRE-CODE checker |

**Forbidden in governance commit:**

- Product code (`core/target*.py`, `orchestration/*.py`, `ux_builder.py`, `app.py`, widget)
- Live / LLM eval runs
- Composer / Verifier medical policy changes
- Frozen S-series/A9R/final-scope/W1b artifact edits
- Implementation tests or presentation modules

## Allowlist (implementation — blocked until PRE-CODE ✅ + owner GO)

### CREATE (expected)

- `core/target_presentation_decision.py` (or equivalent typed presentation layer)
- `tests/test_fullcontext_presentation_parity_implementation.py`
- `tests/test_fullcontext_presentation_parity_sparse_fixtures.py` (if needed)
- `tests/test_fullcontext_presentation_parity_bone_graft_demo_data.py` (demo data correction checks)
- `clients/demo/target_response/pricebook/services/bone_graft.default.json`
- Validator extensions in `scripts/validate_client_pack.py` (consultation_value, video_key)
- `clients/_template/md/sample__service__example.md` consultation_value example (neutral)
- `docs/CLIENT_PACK_AUTHORING.md` consultation_value + video_key sections

### Demo data correction — `bone_graft` (Phase 2 implementation)

**Goal:** promote bone graft from orphaned info MD to a first-class demo service with
`no_public_price`, while keeping `sinus_lift` as the separate narrow priced procedure.

| Action | Path |
|--------|------|
| CREATE service | `clients/demo/target_response/service_catalog.json` — add `bone_graft` |
| RENAME MD | `clients/demo/md/implantation__info__bone_graft.md` → `implantation__service__bone_graft.md` |
| CREATE offer | `clients/demo/target_response/pricebook/services/bone_graft.default.json` |

**Service record (`bone_graft`):**

- `name`: «Костная пластика»
- `family`: `implantology` (catalog schema); MD `topic`: `implantation`
- `aliases`: from existing MD frontmatter (not invented)
- `content_ref`: `implantation__service__bone_graft.md`
- `active`: `true`
- `selection`: existing schema only — no core hardcode; owner picks applicable `mode`/axes at implementation start

**Offer price (exact):**

```json
{
  "mode": "no_public_price",
  "approved_text": "Стоимость костной пластики рассчитывается после КТ и зависит от необходимого объёма и выбранной методики."
}
```

**Binding constraints:**

- `sinus_lift` remains a separate narrow service with existing closed/open offers and exact prices unchanged.
- Update all authored refs from `implantation__info__bone_graft` → `implantation__service__bone_graft` / new `doc_id`.
- Renamed MD: `doc_type: service`, `doc_id: implantation__service__bone_graft`; preserve body and `suggest_h3` followup anchors.
- Service count becomes **22** (was 21); offer count **32** (was 31) — update non-frozen catalog/offer tests only.
- No `consultation_value` on `bone_graft` unless explicitly authored later; comparison/FAQ docs must not trigger automatic consultation close.

**Authored ref updates (implementation):**

- `clients/demo/md/implantation__info__bone_graft.md` → rename + frontmatter
- `evals/v5/demo/golden.json`
- `evals/v5/metadata_first_golden.json`
- `evals/v5/arbiter_golden.json`
- `evals/routing_smoke.md`
- `clients/demo/target_response/pricebook/facts.json` — add `bone_graft` to applicable `allowed_service_ids` where implant-adjacent facts apply (same policy as peer implant services)
- `tests/test_demo_target_service_catalog.py`, `tests/test_demo_target_price_offers.py`, `tests/test_validate_client_pack.py` — counts and bone_graft fixtures

**Frozen artifacts:** S-series/A9R/final-scope/W1b pins remain byte-identical; do not edit frozen eval matrices for this correction.

### UPDATE (expected — exact list finalized at implementation start)

- `core/target_response_verifier.py` — validated source refs on verified response
- `core/target_fullcontext_content_package.py` — source identity path
- `orchestration/target_fullcontext_turn.py` — propagate validated doc refs
- `core/target_runtime_widget.py` — video, situation, slot separation
- `core/target_runtime_turn.py` — marketing_scenarios, semantic_context
- `core/target_runtime_client_context.py` — remove hardcoded marketing off-switch
- `core/target_runtime_session.py` — full session cadence fields
- `ux_builder.py` — align limiter to 4/2 presentation decision
- `tests/test_ui_source_policy.py` — replace stale 1-QR test
- `contracts/turn_frame.py` — `marketing_scenarios` field (if Planner wire required)
- `core/turn_frame_from_raw.py` / planner bridge (if TurnFrame field added)

**KEEP:** `consultation_value` mechanism, AC1–AC3, A9 authority, Composer/Verifier medical policy,
frozen artifacts, existing pricebook/marketing data.

**DELETE:** none in this milestone (no legacy restore).

## Acceptance matrix (implementation)

| # | Criterion |
|---|---|
| 1 | All-on-4 info → 1–2 relevant secondary buttons, not artificially 1 |
| 2 | Bone graft (`bone_graft` service) → validated used service MD → up to 2 its followups |
| 3 | Unrelated FAQ/info/comparison documents remain MD entities, not catalog services |
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
| 22 | consultation_value first show / no repeat / exact service/option ownership only |
| 23 | terminal/error do not write shown-state |
| 24 | New sparse client pack passes without video/consultation_value |
| 25 | Invalid consultation_value client pack fails validator |
| 26 | Invalid video key client pack fails validator or documented optional-policy |
| 27 | Existing rich pricebook, A9, AC1–AC3, typed UI flows without regression |
| 28 | Frozen S-series/A9R/final-scope/W1b artifacts byte-identical |
| 29 | «Что такое костная пластика?» → explicit `bone_graft` service (not orphaned info doc) |
| 30 | `bone_graft` followups from its service MD (`suggest_h3`), up to 2 secondary slots |
| 31 | «Сколько стоит костная пластика?» → typed `no_public_price` + exact `approved_text`; no family-price inheritance |
| 32 | «Сколько стоит синус-лифтинг?» → existing closed/open exact prices unchanged |
| 33 | FAQ/info/comparison source identity for bone-graft topic does not extend `consultation_value` applicability |

## Tests (governance PRE-CODE)

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-pres-gov-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_fullcontext_presentation_parity_governance.py `
  tests/test_final_client_pack_data_convergence_b_governance.py `
  tests/test_final_scope_widget_e2e_closeout_governance.py `
  tests/test_final_explicit_service_price_lookup_boundary_governance.py `
  tests/test_final_price_scope_coverage_nav_governance.py -q
git diff --check
```

## Tests (implementation COMPLETION — future)

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-pres-impl-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_fullcontext_presentation_parity_governance.py `
  tests/test_fullcontext_presentation_parity_implementation.py `
  tests/test_validate_client_pack.py `
  tests/test_ui_source_policy.py `
  tests/test_w1_widget_followup_contract_offline.py `
  tests/test_target_response_followup_materializer.py `
  tests/test_demo_target_marketing_selection.py `
  tests/test_s61_correction_target_runtime.py -q
git diff --check
```

## STOP conditions

1. Governance requires product code in same commit
2. Need file outside governance allowlist
3. Must edit frozen acceptance artifacts for green governance
4. Retriever / legacy policy restore / second pipeline introduced
5. Composer / Verifier medical policy change required
6. LIVE / LLM / prompt tuning required for governance green
7. Implementation artifact before PRE-CODE ✅

## STOP

Governance PRE-CODE PASS does **not** authorize implementation.
**STOP after PRE-CODE ✅** — request separate owner GO before Phase 2.

## Governance completion record

| Field | Value |
|-------|-------|
| Baseline HEAD | `50c6cf9` |
| Governance HEAD (Phase 1) | `e312ff7` |
| Governance correction HEAD | `079de09` |
| Demo data correction HEAD | pending commit |
| PRE-CODE | pending |
| Product change | **none** |
| LIVE / LLM | **none** |

## Governance correction — consultation_value applicability

**Mode:** docs/governance only · **NO product code**

Clarify that generic content-only FullContext intentionally does not receive automatic
`consultation_value`; only exact service/option selection triggers automatic close.

### Allowlist (correction commit)

- `docs/evidence/presentation/FULLCONTEXT_PRESENTATION_PARITY_SEAM_AUDIT.md`
- `TASK.md`
- `tests/test_fullcontext_presentation_parity_governance.py`

**STOP after correction PRE-CODE ✅** — Phase 2 implementation still requires separate owner GO.

## Governance correction — `bone_graft` demo data (Phase 2 allowlist)

**Mode:** docs/governance/tests only · **NO product code / NO demo data change in this commit**

Adds Phase 2 implementation allowlist and acceptance rows 29–33 for promoting
`implantation__info__bone_graft` to catalog service `bone_graft` with `no_public_price`,
while preserving `sinus_lift` as separate priced procedure.

### Allowlist (this correction commit)

- `docs/evidence/presentation/FULLCONTEXT_PRESENTATION_PARITY_SEAM_AUDIT.md`
- `TASK.md`
- `tests/test_fullcontext_presentation_parity_governance.py`

**STOP after correction PRE-CODE ✅** — demo data + product implementation require separate owner GO.

---

# TASK — FULLCONTEXT_DIALOGUE_PRESENTATION_CONVERGENCE (governance)

**Status:** governance checkpoint only · **NO PRODUCT CHANGE / NO LIVE / NO LLM**

**Baseline:** `codex/stage-a` @ `7c716df` (`FULLCONTEXT_PRESENTATION_PARITY` Phase 2 complete)

**Authority:** owner decisions §1–7; seam audit
`docs/evidence/presentation/FULLCONTEXT_DIALOGUE_PRESENTATION_CONVERGENCE_SEAM_AUDIT.md`.

## Goal

Архитектурно закрыть оставшиеся после FullContext-перехода разрывы в FAQ source identity,
контактах, UI-каналах, situation, marketing hooks и fallback — без RAG и без временных костылей.

Phase 2 `FULLCONTEXT_PRESENTATION_PARITY` (@ `7c716df`) подключил presentation decision,
частичную source validation, marketing runtime и bone_graft demo data. Этот milestone закрывает
оставшиеся gaps **H–N** (см. audit).

## Owner decisions (binding)

### 1. Source identity (generic FAQ)

Strict Composer JSON contract (live backend update required):

```json
{
  "answer": "...",
  "source_identity": {
    "primary_content_ref": "...",
    "used_content_refs": ["..."]
  }
}
```

- `primary_content_ref` must be in `used_content_refs` when present.
- Invented refs never used (dropped at validation).
- **Generic FAQ/info/comparison semantics:**
  - valid answer + valid source → answer + source-based UI;
  - valid answer + missing/invalid source → answer shown, follow-up/video/situation suppressed, warning logged;
  - **do not** verifier-block whole response solely for bad/missing `source_identity`.
- Presentation metadata from validated primary only; exact-service paths unchanged.

**Verifier blocking (unchanged):** missing/unparseable answer; exact clinic/commercial claims without PRIMARY_EVIDENCE; contacts without `clinic_contact` evidence; existing blocking semantic issues.

### 2. Authoritative contact data

**Only** `clients/{id}/clinic_policies.yaml` → structured `contact:` (phone, WhatsApp, address,
hours, parking). **Do not duplicate** phone/address/hours in MD.

Direct contact questions: TurnFrame typed **`contacts` aspect** from Turn Planner (same LLM call,
no regex) → PRIMARY_EVIDENCE `kind=clinic_contact` (not `commercial_fact`).

### 3. UI channel separation

Choice ≤4 | content secondary ≤2 (video → follow-up → situation) | price-detail ≤2 | CTA separate.
**One response = one navigation channel** — no `choice+price`, no `secondary+price`.

### 4. Situation

`situation_allowed` on validated primary; after video + follow-up; session no-repeat.
Intake: situation → name → phone → demo_stub. HTTP tests required.

### 5. Marketing hooks

Canonical `TurnFrame.marketing_scenarios: list[pain_fear|cost|time|doctor_trust|result_reliability]`
(0–2), from Turn Planner **same LLM call** — no extra classifiers, no regex.

Rules:

- Direct informational question ≠ scenario («Сколько длится?» ≠ `time`; «Какая гарантия?` ≠
  `result_reliability`; «Кто врач?» ≠ `doctor_trust`).
- Scenario only on expressed fear/doubt/objection.
- Runtime uses only validated `TurnFrame.marketing_scenarios`; remove `derive_marketing_scenarios`
  after cutover; malformed → empty list.
- Max 0–2 scenarios; 3/2 limits preserved; marketing facts ≠ UI slots.
- `consultation_value` rules unchanged.

### 6. Fallback / handoff

Fixed text + canonical phone only; no CTA/QR/video/situation/marketing; `attribution_kind=plain`.
Composer must not invent phone. Internal error/reset — plain attribution, not clinic-material.

### 7. Regression coverage

Restore stale multi-turn tests (vague doctors/price, payment follow-up, hydration, clinic-wide
doctors, terminal/error focus preservation).

## Confirmed gaps (read-only audit @ `7c716df`)

| Gap | Summary |
|-----|---------|
| **H** | No Composer source identity sidecar; FAQ `primary_content_ref=None`; evidence-inferred refs insufficient |
| **I** | Contact data split; no PRIMARY_EVIDENCE contact path; free Composer generation |
| **J** | Situation priority before content follow-ups (should be after video + follow-up) |
| **K** | `choice_qr + price_qr` and `secondary_qr + price_qr` channel mixing |
| **L** | Situation HTTP offline tests missing (start/back/submit/SID/PII) |
| **M** | `TurnFrame.marketing_scenarios` missing; heuristic `derive_marketing_scenarios` wrong for time/result_reliability |
| **N** | Fallback/error without canonical phone; `internal_error_response` missing plain attribution |

Prior gaps A–G: **partially addressed** in Phase 2; residual risks in H–N and post-widget limiter.

## Allowlist (governance commit only)

| File | Action |
|------|--------|
| `TASK.md` | UPDATE — this checkpoint |
| `docs/evidence/presentation/FULLCONTEXT_DIALOGUE_PRESENTATION_CONVERGENCE_SEAM_AUDIT.md` | CREATE |
| `docs/MARKETING_SCENARIO_ARCHITECTURE.md` | UPDATE — channel mutex + time/result_reliability projection |
| `docs/MARKETING_QUESTION_FOUNDATION.md` | UPDATE — situation priority + fallback phone |
| `docs/ARCH_TARGET_DESIGN.md` | UPDATE — source identity sidecar + contact authority + channel mutex |
| `docs/ARCHITECTURE_CONVERGENCE.md` | UPDATE — checkpoint row |
| `docs/STRANGLER_ROADMAP.md` | UPDATE — checkpoint entry |
| `docs/FLAGS_AND_STATUS.md` | UPDATE — status entry |
| `docs/CLIENT_PACK_AUTHORING.md` | UPDATE — canonical contact authority |
| `tests/test_fullcontext_dialogue_presentation_convergence_governance.py` | CREATE — PRE-CODE checker |

**Forbidden in governance commit:**

- Product code changes
- Data migration
- LIVE / LLM eval runs
- RAG/retriever, regex blocklists, Verifier policy tuning, A9 tuning
- Frozen S-series/A9R/final-scope/W1b artifact edits
- New answer pipeline

## Allowlist (implementation — blocked until PRE-CODE ✅ + owner GO)

### CREATE (expected)

- `contracts/target_composer_source_identity.py` (or equivalent typed contract)
- `core/target_contact_authority.py` (structured loader → PRIMARY_EVIDENCE)
- `tests/test_fullcontext_dialogue_presentation_convergence_implementation.py`
- `tests/test_situation_intake_http_offline.py` (start/back/submit/SID/interrupt/PII)
- `tests/test_target_contact_primary_evidence_offline.py`
- `tests/test_target_presentation_channel_mutex_offline.py`
- `tests/test_target_fallback_phone_offline.py`
- Validator: structured `contact:` required; **forbid** duplicate contact facts in MD

### UPDATE (expected)

- `contracts/turn_frame.py` — `marketing_scenarios` + `contacts` in `AspectKind`
- `contracts/answer_plan.py` — `contacts` aspect
- `core/turn_frame_from_raw.py` / planner prompt — `marketing_scenarios` + `contacts` sanitization
- `core/target_composer_executor.py` — parse strict JSON sidecar; live backend contract
- `core/target_runtime_llm_backends.py` — live Composer JSON response
- `core/target_presentation_turn_projection.py` — **delete** `derive_marketing_scenarios` after cutover
- `core/target_response_verifier.py` — validate sidecar refs; pass through
- `core/target_fullcontext_content_package.py` — propagate Composer primary for content-only
- `core/target_verified_response_pipeline.py` — prefer Composer sidecar over evidence inference
- `core/target_presentation_decision.py` — channel mutex; situation priority fix
- `core/target_presentation_turn_projection.py` — `time`, `result_reliability` projection
- `core/target_runtime_widget.py` — fallback phone injection; plain attribution on all error paths
- `ux_builder.py` — align/remove post-widget truncation; `internal_error_response` attribution
- `clients/demo/clinic_policies.yaml` — structured `contact` block (demo)
- `clients/_template/clinic_policies.yaml` — template schema
- Multi-turn regression tests (see audit table)

**KEEP:** `consultation_value` mechanism, AC1–AC3, A9 authority, bone_graft demo data,
frozen artifacts, Composer/Verifier medical policy.

## Acceptance matrix (implementation)

| # | Criterion |
|---|---|
| 1 | Generic pain FAQ + valid source → answer + source-based UI |
| 1b | Generic FAQ + valid answer + missing/invalid source → answer only, warning, no follow-up/video/situation |
| 2 | FAQ follow-up from `suggest_h3` on validated primary |
| 3 | FAQ video + follow-up occupy two secondary slots |
| 4 | Video shown → next unseen follow-ups available |
| 5 | Existing follow-up → situation does not displace it |
| 6 | One follow-up + free slot → situation may show |
| 7 | Choice menu contains no price-detail |
| 8 | Price-detail contains no content secondary |
| 9 | Direct phone / address / hours / WhatsApp → PRIMARY_EVIDENCE |
| 10 | Marketing `time` scenario (0–2) via TurnFrame |
| 11 | Marketing `result_reliability` scenario (0–2) via TurnFrame |
| 12 | Exact-service `consultation_value` preserved |
| 13 | Generic FAQ without neighbor `consultation_value` |
| 14 | Technical fallback → fixed text + canonical phone only |
| 15 | Verifier block → fixed text + canonical phone only |
| 16 | Internal error → `attribution_kind=plain` |
| 17 | Situation start / back / submit HTTP offline |
| 18 | No-repeat cadence (video, followups, situation) |
| 19 | `/ask` and `/ask/stream` parity |
| 20 | AC1–AC3, typed UI, explicit service price lookup, pricebook — no regression |

## Tests (governance PRE-CODE)

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-dlg-gov-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_fullcontext_dialogue_presentation_convergence_governance.py `
  tests/test_fullcontext_presentation_parity_governance.py `
  tests/test_final_client_pack_data_convergence_b_governance.py `
  tests/test_final_scope_widget_e2e_closeout_governance.py -q
git diff --check
```

## Tests (implementation COMPLETION — future)

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-dlg-impl-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_fullcontext_dialogue_presentation_convergence_governance.py `
  tests/test_fullcontext_dialogue_presentation_convergence_implementation.py `
  tests/test_situation_intake_http_offline.py `
  tests/test_target_contact_primary_evidence_offline.py `
  tests/test_target_presentation_channel_mutex_offline.py `
  tests/test_target_fallback_phone_offline.py `
  tests/test_fullcontext_presentation_parity_implementation.py `
  tests/test_vague_doctor_followup.py `
  tests/test_s62_correction_offline.py `
  tests/test_c2c_session_migration_offline.py `
  tests/test_ui_source_policy.py -q
git diff --check
```

## STOP conditions

1. Governance requires product code in same commit
2. Need file outside governance allowlist
3. Must edit frozen acceptance artifacts for green governance
4. Retriever / legacy policy restore / second pipeline introduced
5. Composer / Verifier medical policy change required
6. LIVE / LLM / prompt tuning required for governance green
7. Implementation artifact before PRE-CODE ✅
8. Contact facts duplicated in MD instead of `clinic_policies.yaml` only
9. Channel mutex solved by post-hoc widget truncation only
10. Marketing scenarios inferred from aspects/emotion instead of `TurnFrame.marketing_scenarios`
11. Contact routing via regex instead of typed `contacts` aspect

## STOP

Governance PRE-CODE PASS does **not** authorize implementation.
**STOP after PRE-CODE ✅** — request separate owner GO before Phase 2.

## Governance completion record

| Field | Value |
|-------|-------|
| Baseline HEAD | `7c716df` |
| Governance HEAD (Phase 1) | pending |
| PRE-CODE | pending |
| Product change | **none** |
| LIVE / LLM | **none** |

## Governance correction — contacts, Composer JSON, marketing_scenarios (@ post-`6eb6cee`)

**Mode:** docs/governance/tests only · **NO product code**

### Binding clarifications

1. **Contacts** — only `clinic_policies.yaml` `contact:`; no phone/address/hours/WhatsApp duplication in MD.
2. **Contact routing** — typed `contacts` aspect from Turn Planner; no `policy.contacts_intent` regex on target path.
3. **PRIMARY_EVIDENCE** — `kind=clinic_contact` (not `commercial_fact`).
4. **Composer** — strict JSON `{ answer, source_identity }`; `primary_content_ref ∈ used_content_refs` when present; invented refs never used; generic FAQ: missing/invalid source → answer + warning, no UI (not whole-response block); live backend update required.
5. **Marketing** — canonical `TurnFrame.marketing_scenarios` (0–2) from planner same call; direct questions ≠ scenarios; remove `derive_marketing_scenarios` heuristics after cutover.

**STOP after correction PRE-CODE ✅** — implementation still requires separate owner GO.

## Governance correction — source identity fail-open for generic answer (@ post-`f91fc04`)

**Mode:** docs/governance/tests only · **NO product code**

### Binding clarifications

For generic FAQ/info/comparison:

- valid answer + valid source identity → answer + source-based UI;
- valid answer + missing/invalid source identity → answer shown, follow-up/video/situation suppressed, warning logged;
- invented refs never used;
- do **not** block entire answer solely because of source-identity sidecar.

Fail-closed (blocking) only for: missing/unparseable answer; exact clinic/commercial claims without PRIMARY_EVIDENCE; contacts without validated `clinic_contact` evidence; existing Verifier blocking decisions.

### Allowlist (this correction commit)

- `docs/evidence/presentation/FULLCONTEXT_DIALOGUE_PRESENTATION_CONVERGENCE_SEAM_AUDIT.md`
- `TASK.md`
- `docs/ARCH_TARGET_DESIGN.md`
- `tests/test_fullcontext_dialogue_presentation_convergence_governance.py`

**STOP after correction PRE-CODE ✅** — implementation still requires separate owner GO.

## Implementation completion record

| Field | Value |
|-------|-------|
| Baseline HEAD | `204da81` |
| Implementation HEAD | `84b2741` |
| Governance HEAD | `18e4d47` |
| PRE-CODE | 11/11 ✅ |
| COMPLETION (focused) | 106/106 ✅ |
| COMPLETION (full diff `204da81..18e4d47`) | 24/24 ✅ |
| Product change | gaps H–N implemented |
| LIVE / LLM | **none** |

### Post-push verification verdict (@ `18e4d47`)

| Check | Result |
|-------|--------|
| `HEAD` == `origin/codex/stage-a` | ✅ |
| COMPLETION checker full diff `204da81..18e4d47` | ✅ 24/24 |
| source identity / contact authority / TurnFrame / UI mutex / situation / fallback | ✅ per governance |
| Wide safe-offline (corrected command) | ❌ 6 pre-existing failures (`bone_graft` pack consistency) |
| Frozen pins | ✅ unchanged |
| `import app` | ✅ |
| collect-only `tests/` | ✅ |

Wide failures identical on `204da81` and `18e4d47` — **not** H–N regression. Routed to
`DEMO_BONE_GRAFT_PACK_CONSISTENCY`.

---

# TASK — DEMO_BONE_GRAFT_PACK_CONSISTENCY (governance)

**Status:** governance checkpoint only · **NO PRODUCT CHANGE / NO LIVE / NO LLM**

**Baseline:** `codex/stage-a` @ `18e4d47` (`FULLCONTEXT_DIALOGUE_PRESENTATION_CONVERGENCE` complete)

**Authority:** seam audit
`docs/evidence/client_pack/DEMO_BONE_GRAFT_PACK_CONSISTENCY_SEAM_AUDIT.md`.

## Goal

Закрыть шесть pre-existing wide safe-offline failures после добавления first-class `bone_graft`
в demo client pack — без выдуманных цен, units, promotions или doctor credentials.

## Owner decisions (binding)

1. **Doctor linkage:** `bone_graft` → `doctors__doctor__orlov` + `doctors__doctor__volkov`
   (authored surgical/implant competence; peer to `sinus_lift`). **Not** kuznetsov.
2. **`no_public_price`:** честный approved text; **no** fictitious `billing_unit` or `UNIT_LABELS` entry.
3. **Marketing:** facts applicability in `facts.json` is correct; **no** bone_graft-specific promotion required.
4. **Legacy fixture:** `tests/fixtures/demo_legacy_marketing.yaml` — historical; **not** active authority;
   remove byte-hash active pin; do not mechanical hash-update.
5. **`UNIT_LABELS`:** test-only legacy map — scope to numeric-price offers only; no new product service dictionary.
6. **`sinus_lift` exact prices** (42000 / 68000): must not regress.

## Confirmed failures (read-only audit @ `18e4d47`)

| Test | Classification |
|------|----------------|
| `test_demo_doctor_catalog` | actual demo-data gap |
| `test_demo_doctor_template` | actual demo-data gap |
| `test_demo_target_service_catalog` | actual demo-data gap |
| `test_demo_target_price_offers` | architectural hardcode / stale test |
| `test_demo_target_marketing_policy` | historical fixture / stale test |
| `test_demo_target_marketing_migration_audit` | stale test coupling |

## Allowlist (governance commit only)

| File | Action |
|------|--------|
| `TASK.md` | UPDATE — this checkpoint |
| `docs/evidence/client_pack/DEMO_BONE_GRAFT_PACK_CONSISTENCY_SEAM_AUDIT.md` | CREATE |
| `tests/test_demo_bone_graft_pack_consistency_governance.py` | CREATE — PRE-CODE checker |

**Forbidden in governance commit:** product/data changes, LIVE/LLM, frozen pin edits, Verifier/A9 changes.

## Allowlist (implementation — blocked until PRE-CODE ✅ + owner GO)

| File | Action |
|------|--------|
| `clients/demo/doctor_catalog.json` | UPDATE — add `bone_graft` to orlov + volkov |
| `tests/test_demo_target_price_offers.py` | UPDATE — numeric-only `UNIT_LABELS` scope |
| `tests/test_demo_target_marketing_policy.py` | UPDATE — drop legacy hash active pin |
| `tests/test_demo_target_marketing_migration_audit.py` | UPDATE — facts↔promo without legacy superset lock |
| `tests/fixtures/demo_legacy_marketing.yaml` | DELETE or historical isolate |
| `tests/test_demo_bone_graft_pack_consistency_implementation.py` | CREATE — COMPLETION checker |

## Owner sign-off table

| Decision | Proposed | Status |
|----------|----------|--------|
| `bone_graft` → orlov | yes (MD: костная пластика) | **APPROVED** |
| `bone_graft` → volkov | yes (surgical implantologist) | **APPROVED** |
| `bone_graft` → kuznetsov | **no** | **APPROVED** |
| No bone_graft-specific promotion | yes | **APPROVED** |
| Remove legacy marketing hash pin | yes | **APPROVED** |
| `UNIT_LABELS` numeric-only | yes | **APPROVED** |

## Acceptance matrix (implementation)

| # | Criterion |
|---|-----------|
| 1 | «Кто делает костную пластику?» → orlov + volkov |
| 2 | `no_public_price` без dummy numeric unit |
| 3 | «Сколько стоит костная пластика?» → approved no-public-price text |
| 4 | `sinus_lift` exact prices unchanged (42000 / 68000) |
| 5 | No invented bone_graft promotion |
| 6 | Marketing facts do not leak across services |
| 7 | No legacy/hash mirror in active client pack tests |
| 8 | `validate_client_pack` demo + `_template` green |
| 9 | Prior COMPLETION `test_fullcontext_dialogue_presentation_convergence_*` green |
| 10 | Corrected wide safe-offline: 0 failures |
| 11 | collect-only `tests/` green |
| 12 | frozen pins byte-identical |
| 13 | `import app` green |
| 14 | `git diff --check` clean |

## Tests (governance PRE-CODE)

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-bone-graft-gov-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_demo_bone_graft_pack_consistency_governance.py `
  tests/test_fullcontext_dialogue_presentation_convergence_governance.py `
  tests/test_fullcontext_dialogue_presentation_convergence_implementation.py -q
git diff --check
```

## Wide safe-offline command (corrected — implementation COMPLETION)

Removed missing turn-plan protocol guard test (file absent from repo). All 26 paths verified @ `18e4d47`.

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-bone-graft-wide-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_final_client_pack_data_convergence_b_governance.py `
  tests/test_final_client_pack_data_convergence_governance.py `
  tests/test_final_client_pack_data_convergence_reader_cutover.py `
  tests/test_final_client_pack_data_convergence_sparse_pack.py `
  tests/test_validate_client_pack.py `
  tests/test_client_pack_template_scaffold.py `
  tests/test_turn_planner_llm.py `
  tests/test_turn_planner_wiring.py `
  tests/test_catalog_match.py `
  tests/test_follow_up_rewrite.py `
  tests/test_dialog_focus_baseline.py `
  tests/test_dialog_focus_contract.py `
  tests/test_demo_doctor_catalog.py `
  tests/test_demo_doctor_template.py `
  tests/test_demo_target_service_catalog.py `
  tests/test_demo_target_price_offers.py `
  tests/test_demo_target_marketing_policy.py `
  tests/test_demo_target_marketing_migration_audit.py `
  tests/test_response_schema_loader.py `
  tests/test_target_scope_aware_selection_offline.py `
  tests/test_final_price_and_service_coverage_implementation.py `
  tests/test_final_price_scope_coverage_nav_implementation.py `
  tests/test_final_explicit_service_price_lookup_boundary_implementation.py `
  tests/test_c2_import_firewall_offline.py `
  tests/test_price_ref_routing.py `
  tests/test_content_linter.py -q
python -m pytest --collect-only -q
```

## STOP conditions

- Owner rejects doctor mapping without authored alternative.
- Fix requires fictitious price unit, promotion, or doctor credentials.
- Verifier/A9/AC1–AC3 or frozen pin change required.
- File outside implementation allowlist.
- Mechanical legacy hash update as sole fix.

## STOP

Governance PRE-CODE PASS does **not** authorize implementation.
**STOP after governance commit + push** — await owner GO.

## Implementation completion record

| Field | Value |
|-------|-------|
| Governance HEAD | `525c18e` |
| Implementation HEAD | `9104212` |
| Owner GO | ✅ Phase 2 approved |
| PRE-CODE (governance) | 10/10 ✅ |
| COMPLETION (focused) | 44/44 ✅ |
| COMPLETION (full diff `525c18e..9104212`) | 44/44 ✅ |
| Wide safe-offline (corrected) | 263/263 ✅ |
| collect-only `tests/` | 2772 ✅ |
| `validate_client_pack` demo + `_template` | ✅ |
| `import app` | ✅ |
| frozen pins | ✅ unchanged |
| `git diff --check` | ✅ clean |
| LIVE / LLM | **none** |

### Post-push verification (@ `9104212`)

| Check | Result |
|-------|--------|
| `HEAD` == `origin/codex/stage-a` | _(after push)_ |
| Working tree clean | _(after push)_ |

### Files changed (implementation `525c18e..9104212`)

| File | Change |
|------|--------|
| `clients/demo/doctor_catalog.json` | `bone_graft` → orlov + volkov |
| `clients/demo/md/doctors__doctor__orlov.md` | `services` frontmatter + `bone_graft` |
| `clients/demo/md/doctors__doctor__volkov.md` | `services` frontmatter + `bone_graft` |
| `tests/test_demo_target_price_offers.py` | `UNIT_LABELS` numeric-only scope |
| `tests/test_demo_target_marketing_policy.py` | drop legacy hash pin; digest 36 files |
| `tests/test_demo_target_marketing_migration_audit.py` | facts superset parity |
| `tests/test_demo_doctor_catalog.py` | `_EXPECTED_CATALOG` snapshot sync |
| `docs/evidence/client_pack/fixtures/demo_legacy_marketing.yaml` | historical isolate (moved) |
| `tests/test_demo_bone_graft_pack_consistency_implementation.py` | CREATE COMPLETION checker |

