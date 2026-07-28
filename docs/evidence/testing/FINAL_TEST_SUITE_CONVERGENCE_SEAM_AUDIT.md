# FINAL_TEST_SUITE_CONVERGENCE — seam audit (Phase 1)

**Milestone:** `FINAL_TEST_SUITE_CONVERGENCE`  
**Governance baseline:** `codex/stage-a` @ `1980ab7`  
**Evidence baseline:** `16d6ea5` (pre-tomography) vs `1980ab7` (current)  
**Authority:** `drafts/EXACT_WIDE_TWO_HEAD_DELTA_AUDIT.md`, `drafts/wide_two_head_delta_classification.json`  
**Inventory:** `docs/evidence/testing/final_test_failure_inventory.json` (185/185)

**NO LIVE / NO LLM / NO network / NO product changes in Phase 1.**

---

## Executive summary

| Metric | Value |
|--------|------:|
| Current failures @ `1980ab7` | 185 |
| Pre-existing `FAIL_BOTH` | 178 |
| New from tomography diff (`PASS_BASELINE_FAIL_CURRENT`) | 5 |
| Proven product regressions | **0** |
| Pack-drift guards (mutable) | 4 (+1 compact `FAIL_BOTH`) |
| Rate-limit wide pollution | 16 nodeids (3 proven isolated-green) |
| Historical/frozen inventory | 87 |
| Live owner-gated | 10 |

Owner objective: two new clinics require a test ecosystem where safe-offline is green,
historical contracts are green in their own layer, aggregate `pytest tests/ -q` has zero
unexplained failures, and live/network tests never run without owner GO.

**Target suites:** `current_safe_offline`, `historical_frozen_contracts`, `live_owner_gated`
(see `docs/TEST_SUITE_ARCHITECTURE.md`).

---

## Normative rules (binding)

1. **No assert weakening** — convergence by correct expectation, isolation, or historical repair.
2. **No automatic hash bumps** — frozen artifacts immutable; mutable demo guards may update.
3. **No skip/xfail/catalog hiding** — documented live skips only after TSC-D.
4. **Delete orphan** only with proof: product target gone + coverage elsewhere or requirement retired.
5. **Historical tests** validate frozen artifact version, not accidental current-runtime coupling.
6. **Shared state isolated** — rate buckets, sessions, caches, contextvars, DB paths, env.
7. **Product rate limiter unchanged** — fix tests, not `RATE_LIMIT_MAX_PER_IP`.
8. **Phase 1 = governance only** — no implementation.

---

## Phase 1 seam audit checklist

- [x] Exact dual-head wide pytest delta exists in `drafts/`
- [x] Machine-readable inventory 185/185
- [x] Three-suite target architecture documented
- [x] Mutable vs frozen guard separation explicit
- [x] Rate-limit producer and isolation proposal documented
- [x] Four implementation checkpoints with allowlists
- [x] PRE-CODE governance checker
- [x] No product/test assertion/hash changes in Phase 1

---

## 1. Mutable demo-pack guards

### Corpus 54→55

| nodeid | baseline | current | action |
|--------|----------|---------|--------|
| `test_demo_corpus_document_count_and_doctors_inclusion` | PASS | FAIL | UPDATE_ASSERTION |
| `test_pipeline_accepts_prebuilt_context_without_calling_builder` | PASS | FAIL | UPDATE_ASSERTION |
| `test_exact_cta_sources_expose_unresolved_legacy_key` | PASS | FAIL | UPDATE_ASSERTION |

**Cause:** `clients/demo/md/diagnostics__service__tomography.md` (+55th doc).  
**Checkpoint:** TSC-A.  
**Forbidden:** frozen eval hash edits.

### Tomography `content_ref`

| nodeid | cause | action |
|--------|-------|--------|
| `test_real_target_catalog_is_strict_complete_s1_wire_data` | extra `content_ref` field | UPDATE_ASSERTION |

**File:** `clients/demo/target_response/service_catalog.json`.  
**Not frozen:** mutable S1 wire schema guard for current demo pack.

### Compact catalog 638→661

| HEAD | `test_current_demo_compact_reference_and_catalog_drift_guard` |
|------|---------------------------------------------------------------|
| `16d6ea5` | FAIL `661 == 638` |
| `1980ab7` | FAIL `661 == 638` |

**Verdict:** pre-existing `FAIL_BOTH`; update guard in TSC-A, not tomography regression.

### Demo hash cascade (17 `FAIL_BOTH`)

`test_demo_target_*` failures: composer candidate text / pipeline sidecars drift with FullContext
hash change. **Mutable** demo golden — update assertions in TSC-A, separate from frozen eval pins.

---

## 2. Rate-limit pollution

### Producer

```
orchestration/route_guards.py
  _IP_RATE_BUCKETS: dict[str, deque]  # module-global, threaded
  check_rate_limit(ip) → False when len(q) >= RATE_LIMIT_MAX_PER_IP (40)
```

HTTP tests share `127.0.0.1`. Bypass exists (`E2E_USE_TEST_CLIENT=1`) but **must not** be used in wide suite.

### Harness entry

`tests/test_final_fullcontext_dialogue_runtime_convergence_harness.py::orchestrate_via_app`
→ Flask TestClient POST `/ask` or `/ask/stream`.

### Affected nodeids (16)

All classified `FIX_TEST_ISOLATION`, checkpoint TSC-A.  
Isolated reruns **PASS** for: `test_unknown_ref_returns_clarify`, `test_scenario_09_ask_parity`,
`test_scenario_10_ask_stream_parity`.

### Proposed centralized fix (Phase 2)

Create `tests/conftest.py`:

```python
@pytest.fixture(autouse=True)
def _reset_rate_limit_buckets():
    from orchestration import route_guards
    with route_guards._IP_RATE_LOCK:
        route_guards._IP_RATE_BUCKETS.clear()
    yield
    with route_guards._IP_RATE_LOCK:
        route_guards._IP_RATE_BUCKETS.clear()
```

Scope autouse to HTTP harness modules if global autouse too broad.  
Retain dedicated test proving real 429 when bucket full in **isolated** module.

---

## 3. Frozen / shadow / preservation (87 inventory entries)

Delta audit coarse bucket: 76 `frozen_eval_historical` in `FAIL_BOTH`.  
Inventory precise count: **87** `historical_frozen_contracts` (includes A9R2 frozen diagnostic,
native contract spec, topic shadow — all `FAIL_BOTH`).

### Dominant root cause

```
ValidationError: TurnFrame / TurnFrameMeta
field_meta.marketing_scenarios — Field required
```

Frozen `raw_turn_plan` JSON in `evals/v5/**` predates `marketing_scenarios` metadata.
Tests call `TurnFrame.model_validate(frozen_raw)` directly → historical contract wired to
**current** schema without versioned loader.

### Per-family summary

| Family | count | repair approach |
|--------|------:|-----------------|
| `patient_scope_shadow_eval_contract` | 21 | versioned frame loader or shim in harness only |
| `fullcontext_quality_eval_harness` | 15 | replay through frozen-case adapter |
| `preservation_eval_contract` | 14 | keep payload contract; decouple from live TurnFrame |
| `patient_scope_shadow_eval_v2_contract` | 9 | same |
| `a9r2_scorer_correction_offline` | 6 | frozen diagnostic recompute uses versioned loader |
| `fullcontext_response_eval_harness` | 6 | harness adapter |
| `fullcontext_verifier_replay_harness` | 6 | harness adapter |
| `a9r2b_metric_correction_offline` | 5 | frozen metric on versioned projection |
| others | 11 | per-file in inventory |

**Checkpoint:** TSC-C.  
**Forbidden:** editing frozen JSONL/matrices/hashes; skip/xfail; runtime behavior change.

---

## 4. Active branch drift (TSC-B, 50 failures)

| Category | count | action |
|----------|------:|--------|
| Pipeline signature / import firewall | 15 | UPDATE_ASSERTION |
| Planner/TurnFrame contracts | 7 | UPDATE_ASSERTION |
| S61/S65/S69 HTTP (non-429) | 3 | UPDATE_ASSERTION / 1 PRODUCT_BUG_FUTURE |
| Loader/guard negative paths | 9 | UPDATE_ASSERTION |
| AC3 / explicit price | 4 | UPDATE_ASSERTION |
| S56 missing-base | 4 | UPDATE_ASSERTION |
| Scope widget offline | 2 | UPDATE_ASSERTION |
| Other (md_chunks, mass_composer, c2c, …) | 6 | UPDATE_ASSERTION |

### Notable single cases

- `test_invalid_pack_fail_closed` — `TargetRuntimeClientContextError` surface; verify expected
  exception type (PRODUCT_BUG_FUTURE if product wrong).
- `test_build_rejects_empty_corpus` — raises `full_context_corpus_empty`; test expectation may
  need error-code alignment (UPDATE_ASSERTION).

---

## 5. Live owner-gated (TSC-D, 10 failures)

| Module | tests | CI role |
|--------|------:|---------|
| `test_final_scope_widget_e2e_*_live_harness` | 8 | marker/prepare/fake-provider |
| `test_fullcontext_quality_eval_live_wiring` | 1 | mocked live wiring |
| `test_s66_default_authority_live_harness` | 2 | authority proof + marker |

**Action:** KEEP_AS_IS in Phase 2; wire markers so default CI runs dry-run only.

---

## 6. Test discovery

| Check | Result |
|-------|--------|
| `pytest tests/` | 3189 collected ✓ |
| `pytest docs/artifacts/` | 2 collection errors (WIP untracked tests) |
| Policy | `testpaths = ["tests"]`; exclude `docs/artifacts` |

No active product tests hidden; stray artifact tests are orphan debris.

---

## Implementation checkpoints

### TSC-A — mutable pack guards + isolation (38 failures)

**Allowlist (tests + harness):**

- `tests/conftest.py` (CREATE)
- `tests/test_turn_planner_llm.py`
- `tests/test_target_cached_full_context.py`
- `tests/test_demo_target_*.py` (mutable guards only)
- `tests/test_demo_target_marketing_migration_audit.py`
- `tests/test_demo_target_service_catalog.py`
- HTTP harness modules listed in inventory TSC-A entries
- `tests/test_final_fullcontext_dialogue_runtime_convergence_harness.py` (fixture hook only)

**Delete-list:** none.

**Acceptance:**

```powershell
python -m pytest tests/test_turn_planner_llm.py tests/test_target_cached_full_context.py tests/test_demo_target_service_catalog.py -q
python -m pytest tests/test_final_tomography_existing_scan_content_routing_implementation.py tests/test_s61_correction_target_runtime.py tests/test_s65_authority_switch_offline.py -q
```

All TSC-A nodeids green in full `pytest tests/ -q` without rate-limit bypass.

**STOP:** if frozen pin/hash update required.

---

### TSC-B — active current-runtime stale tests (50 failures)

**Allowlist:** inventory entries with `checkpoint=TSC-B` (see JSON `files` arrays).

**Delete-list:** none in Phase 2 without orphan proof.

**Acceptance:** TSC-B nodeids green; no frozen artifact edits.

**Focused:**

```powershell
python -m pytest tests/test_planner_attempt_contract.py tests/test_target_cached_full_context.py tests/test_c2d_loader_canonical_offline.py -q
```

---

### TSC-C — historical/frozen contract repair (87 failures)

**Allowlist:**

- `tests/test_patient_scope_shadow_eval_*.py`
- `tests/test_preservation_eval_contract.py`
- `tests/test_fullcontext_*_eval*.py` (offline harness)
- `tests/test_a9r2*_*.py` (frozen diagnostic)
- `evals/v5/*_loader*.py` or harness shims (CREATE as needed)

**Forbidden:** mutating frozen artifact bytes under `evals/v5/`, `docs/evidence/`.

**Acceptance:**

```powershell
python -m pytest tests/test_patient_scope_shadow_eval_contract.py tests/test_preservation_eval_contract.py -q
```

Historical suite green independently of mutable demo hash updates.

---

### TSC-D — CI, markers, aggregate closeout

**Allowlist:**

- `pyproject.toml` or `pytest.ini` (testpaths, markers)
- `.github/workflows/ci.yml` (proposed commands — document in TASK first)
- `docs/TEST_SUITE_ARCHITECTURE.md`, `docs/FLAGS_AND_STATUS.md`
- live harness marker tests

**Acceptance:**

```powershell
python -m pytest tests/ -q   # 0 failed
```

Documented skips only for owner-gated live actions.

---

## Forbidden solutions (Phase 2)

- Global `E2E_USE_TEST_CLIENT=1` in wide suite
- Weakening `RATE_LIMIT_MAX_PER_IP`
- Auto-resnapshot frozen eval hashes
- `skip` / `xfail` / `--ignore` on active `tests/**`
- Product code changes to satisfy stale historical contracts
- Deleting frozen eval without owner archival decision

---

## Phase 1 deliverables map

| File | Status |
|------|--------|
| `docs/evidence/testing/FINAL_TEST_SUITE_CONVERGENCE_SEAM_AUDIT.md` | this document |
| `docs/evidence/testing/final_test_failure_inventory.json` | 185 entries |
| `docs/TEST_SUITE_ARCHITECTURE.md` | three-suite target |
| `tests/test_final_test_suite_convergence_governance.py` | PRE-CODE |
| `TASK.md` | governance section |

## STOP (Phase 1)

After governance commit + PRE-CODE PASS + push — **stop**. TSC-A implementation forbidden
until separate owner GO.
