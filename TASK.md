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
| **A9R3** | `resolve_effective_scope` authority wiring after quality gates | owner GO |
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
| Live HEAD | |
| `automated_verdict` | `AUTOMATED_FAIL` |
| `final_verdict` | `FAIL` (manual review 17/17) |
| `provider_model_verified` | true (`qwen3.7-plus` × 17) |
| `true_composite_exact_turn_rate` | 0.882 (15/17) |
| Material FP | 1 |
| Rerun | blocked |
