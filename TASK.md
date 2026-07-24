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
| A9R governance HEAD | pending |
| A9R matrix blob | `36d137112007a3fb0a96ad0759aa111af6115a35` |
| PRE-CODE | ✅ |
| COMPLETION | N/A (governance only) |

**STOP after governance PRE-CODE ✅. No A9R1 work without separate owner GO.**
