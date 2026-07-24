# TASK — AC1 Canonical scope + typed UI action + session persistence

**Product baseline:** `codex/stage-a` @ `eedbd66` · **W1b PARKED** · **NO LIVE / NO LLM / NO A9 product read**

**Authority:** Architecture Convergence Audit (2026-07-24); канон: `docs/ARCHITECTURE_CONVERGENCE.md`.

## Goal

Ввести **постоянный** product contract для patient scope до service-selection wiring:

1. **`EffectiveScope`** — merge explicit current `UiScopeAction` + fresh session `patient_facts` (same topic).
2. **`UiScopeAction`** — UI click передаёт canonical `extent` (`one_tooth|few_teeth|full_arch`), **не** label для повторного угадывания planner.
3. **Session `patient_facts`** — persist extent/jaw/stage между ходами; topic change clears stale carry; new `UiScopeAction` replaces prior session extent.

**Не в scope AC1:** W1b restore, `service_catalog.selection` runtime wiring, `ResponseStage`, marketing runtime, A9 product read/authority, free-text scope correction, live E2E.

## W1b parked (do not touch)

Snapshot: `docs/artifacts/w1b_wip_checkpoint_2026-07-24/` (`MANIFEST.txt`, `checksums.sha256`, `RESTORE.md`).
Restore W1b only by explicit owner decision.

## Baseline and tree state

**До governance commit (этот checkpoint):**

- **Product tree** соответствует `eedbd66` (нет W1b product diff).
- **Dirty diff** — только governance: `TASK.md`, docs sync, `docs/artifacts/w1b_wip_checkpoint_2026-07-24/**`.

**После governance commit:**

- `HEAD` = governance commit поверх `eedbd66`; working tree **clean**; branch synced с `origin/codex/stage-a`.

**AC1 implementation preflight** (не этот commit):

- `HEAD` = governance commit (не `eedbd66`).
- Product tree clean; W1b artifact checksums match `checksums.sha256`.

## Process (mandatory)

1. **Governance checkpoint (this commit):** TASK + docs + W1b artifact only → push → **PRE-CODE checker ✅** → STOP.
2. **AC1 implementation** (later): verify governance `HEAD`, read docs → contract unit tests → HTTP smoke → **COMPLETION checker ✅** → product commit → STOP.

No product code before PRE-CODE ✅.

## Forbidden

- Restore/continue W1b WIP without owner approval
- Live/LLM; A9 matrix/harness rerun; **any product import/read of `TurnFrame.patient_scope`**
- Free-text scope correction parser (regex/second classifier) in AC1
- `family_price_groups` as applicability authority
- Per-MD routing, RAG, second situation classifier
- `ResponseStage` or service-selection wiring in AC1
- Weakening Verifier or frozen artifacts
- Files outside allowlist without governance correction

## Allowlist

### New (AC1 implementation only)

| File |
|------|
| `contracts/effective_scope.py` |
| `contracts/ui_scope_action.py` |
| `core/target_effective_scope.py` |
| `core/target_ui_scope_action.py` |
| `tests/test_effective_scope_contract.py` |
| `tests/test_ui_scope_action_contract.py` |
| `tests/test_session_patient_facts_offline.py` |
| `tests/test_ui_scope_click_http_offline.py` |

### Modify (AC1 implementation only)

| File |
|------|
| `orchestration/pre_resolver_turn.py` |
| `core/target_runtime_turn_frame_hydration.py` |
| `core/target_runtime_session.py` |
| `core/target_runtime_turn.py` |
| `core/target_runtime_followup_nav.py` |
| `tests/test_s61_correction_target_runtime.py` (only if neighbor asserts remain valid; no free-text scope cases) |

### Governance commit (this checkpoint only)

| File |
|------|
| `TASK.md` |
| `docs/ARCHITECTURE_CONVERGENCE.md` |
| `docs/ARCH_TARGET_DESIGN.md` |
| `docs/PRICE_SERVICE_ARCHITECTURE.md` |
| `docs/STRANGLER_ROADMAP.md` |
| `docs/CURRENT_ARCHITECTURE.md` |
| `docs/artifacts/w1b_wip_checkpoint_2026-07-24/**` |

## EffectiveScope priority — AC1 product (normative)

1. explicit current `UiScopeAction` (replaces prior session extent for this turn)
2. fresh session `patient_facts` (same topic, not stale after topic change)
3. all-unknown

**Future (docs only, not AC1 code):** current-turn A9 `patient_scope` may slot between (1) and (2) after separate authority decision.

Scope must **not** select treatment, protocol, or `service_id`. Product path must **not** read `TurnFrame.patient_scope`.

## Acceptance (offline, AC1 implementation)

1. Typed ref `target:ui_scope/{topic}/{extent}` hydrates `UiScopeAction` **before** planner; planner label is not the sole scope source.
2. Session stores and restores `extent` across price continuation (same topic); extent question not repeated when session fact is fresh.
3. New `UiScopeAction` with different `extent` replaces prior session extent (explicit UI correction only).
4. Topic change clears carried extent.
5. HTTP `/ask` + `/ask/stream`: ref-only click with empty `q` uses typed path (smoke tests).
6. **A9 firewall:** product dispatch/session/effective-scope code do not import or read `TurnFrame.patient_scope`; AST or equivalent test proves firewall.
7. W1b artifact byte-identical to `checksums.sha256`.

Free-text correction («нет, несколько зубов») — **out of scope**; defer to post-A9 authority checkpoint.

## Tests (focused, AC1 implementation)

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$bt = Join-Path $env:TEMP ("demo-bot-ac1-" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_effective_scope_contract.py `
  tests/test_ui_scope_action_contract.py `
  tests/test_session_patient_facts_offline.py `
  tests/test_ui_scope_click_http_offline.py `
  -q
```

## STOP conditions

1. AC1 requires reading `TurnFrame.patient_scope` in product path or A9 authority
2. AC1 requires free-text scope correction or second classifier
3. Requires W1b product merge in same diff
4. Requires `service_catalog.selection`, `ResponseStage`, or marketing runtime wiring
5. PRE-CODE or COMPLETION checker ❌ without fix path

## Completion record

| Field | Value |
|-------|-------|
| W1b park checkpoint | 2026-07-24 |
| W1b artifact | `docs/artifacts/w1b_wip_checkpoint_2026-07-24/` |
| Governance HEAD | `bbeef20` |
| PRE-CODE | ✅ |
| COMPLETION | ✅ |
| AC1 product HEAD | (this commit) |

**STOP after AC1 COMPLETION ✅. AC2 starts only after separate owner go.**
