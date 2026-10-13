# Test suite architecture (target)

**Milestone:** `FINAL_TEST_SUITE_CONVERGENCE` · **Governance @ `1980ab7`**

Owner objective: before onboarding two new clinic packs, the test ecosystem must be legible,
honest, and green in layers — without hiding real bugs behind stale reds or suite pollution.

## Three explicit suites

### A. `current_safe_offline`

**Purpose:** protect the **current** dental demo product path.

**Includes:**

- client-pack validation (`validate_client_pack`, lint scripts);
- cached FullContext build/load;
- Planner / TurnFrame / dispatch;
- AC1–AC3 scope, prices, explicit lookup;
- contacts, availability, FAQ, presentation, lead/situation intake;
- `/ask` and `/ask/stream` via TestClient with fakes at provider boundary;
- mutable demo-pack drift guards (corpus count, catalog fields, compact bytes).

**Excludes:** network provider calls, frozen historical matrices, owner-gated live markers.

**Target command (post-convergence):**

```powershell
python -m pytest tests/ -m "current_safe_offline" -q
```

(Phase 2: introduce marker; Phase 1 documents intent only.)

### B. `historical_frozen_contracts`

**Purpose:** byte/hash integrity and versioned harness contracts for **past** measurement artifacts.

**Includes:**

- `evals/v5/**` frozen matrices, JSONL captures, diagnostic recomputes;
- shadow eval v1/v2 contracts;
- preservation eval payloads;
- fullcontext quality/response/verifier replay harnesses bound to frozen turns.

**Rule:** a historical test validates **its artifact version**, not accidental compatibility
with today's `TurnFrame` / runtime unless explicitly bridged through a versioned loader.

**Target command:**

```powershell
python -m pytest tests/ -m "historical_frozen_contracts" -q
```

### C. `live_owner_gated`

**Purpose:** dry-run / preflight / exclusive-marker wiring only in ordinary CI.

**Includes:**

- `test_prepare_live_run_creates_exclusive_marker` family;
- `fullcontext_quality_eval_live_wiring` mocked path;
- S66 default-authority live harness entrypoints.

**Rule:** real provider/network execution **only** after explicit owner GO and outside default CI.

**Target command (CI):**

```powershell
python -m pytest tests/ -m "live_owner_gated" -q
```

## Aggregate target

```powershell
python -m pytest tests/ -q
```

→ **0 failed**; only documented skips for real live actions awaiting owner GO.

Current measured state @ `1980ab7`: **185 failed**, **2993 passed**, **11 skipped** (3189 collected).
Source: `drafts/EXACT_WIDE_TWO_HEAD_DELTA_AUDIT.md`.

## Pytest discovery policy (normative)

| Rule | Detail |
|------|--------|
| **Collect root** | `tests/` only for product CI and wide aggregate |
| **Exclude** | `docs/artifacts/**` test debris (WIP checkpoints); not part of `pytest tests/` today but must stay excluded via `testpaths` / `norecursedirs` in Phase 2 |
| **No catalog hiding** | Do not exclude active `tests/**` modules to fake green |
| **No new skip/xfail** | Convergence via fix/isolation/repair/delete-with-proof only |

Verified @ governance: `pytest tests/` → 3189 collected; `pytest docs/artifacts` errors (not in aggregate).

## Shared-state isolation (mandatory)

Wide-suite pollution root cause @ `1980ab7`:

| State | Producer | Symptom |
|-------|----------|---------|
| `_IP_RATE_BUCKETS` | `orchestration/route_guards.py` `check_rate_limit` | HTTP 429 on `127.0.0.1` after ~40 requests in-process |
| HTTP harness | `orchestrate_via_app` in `test_final_fullcontext_dialogue_runtime_convergence_harness.py` | 16 nodeids red only in full suite |

**Phase 2 fix (TSC-A):** centralized `tests/conftest.py` autouse fixture:

- reset `_IP_RATE_BUCKETS` before/after each HTTP-harness module or test;
- optional per-test fresh TestClient session;
- **forbidden:** global `E2E_USE_TEST_CLIENT=1` in wide suite;
- **forbidden:** weakening `RATE_LIMIT_MAX_PER_IP`.

Dedicated tests for real 429 behavior remain explicit and isolated.

## Mutable vs frozen guards

| Guard type | Example | Suite | Action |
|------------|---------|-------|--------|
| **Mutable demo pack** | corpus `54→55`, `content_ref`, compact `638→661` | A | `UPDATE_ASSERTION` when pack legitimately changes |
| **Frozen pin** | `FROZEN_TURNS_HASH`, retry4 live JSONL | B | `FIX_HISTORICAL_CONTRACT`; never auto-bump hash |
| **Demo hash cascade** | `test_demo_target_*` composer text | A | update golden derived from current pack, not frozen eval |

## Implementation checkpoints (Phase 2+)

| ID | Scope | Failures |
|----|-------|----------|
| **TSC-A** | Mutable pack guards + rate-limit/session isolation | 38 |
| **TSC-B** | Active current-runtime stale tests | 50 |
| **TSC-C** | Historical/frozen contract repair | 87 |
| **TSC-D** | Markers, discovery, CI commands, aggregate closeout | 10 live + wiring |

Details: `docs/evidence/testing/FINAL_TEST_SUITE_CONVERGENCE_SEAM_AUDIT.md`, `TASK.md`.

## What protects the bot today

**Actually guards current bot behavior (green when fixed):**

- `test_final_*_implementation.py` milestone matrices (tomography, availability, price-only, etc.);
- `test_target_*` offline pipeline units;
- client pack lint/validate scripts in CI;
- ingress/booking/medical hard-stop tests (mostly already green).

**Historical measurement (must not block reading current bot health):**

- 87 inventory entries in `historical_frozen_contracts` — mostly frozen TurnFrame replay without versioned loader.

**Orphan candidates (none deleted in Phase 1):**

- `docs/artifacts/**/untracked/tests/*` — not collected; delete/archive in TSC-D hygiene.
