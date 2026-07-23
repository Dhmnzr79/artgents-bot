# S62 Target FullContext HTTP Live Runtime — Post-Live Audit

**Captured:** 2026-07-23 · **Live baseline:** `c00fa4d` · **Artifact commit:** `0a43da1` · **Status:** `S62_NOT_PASSED` (diagnostic evidence only)

Machine-readable pins: [`evals/v5/artifacts/s62_target_runtime_post_live_audit_manifest.json`](../evals/v5/artifacts/s62_target_runtime_post_live_audit_manifest.json)

Supplementary stdout (ingress/planner evidence): [`evals/v5/artifacts/s62_live_stdout_capture.txt`](../evals/v5/artifacts/s62_live_stdout_capture.txt)

---

## Owner ruling (binding)

1. **S62 is NOT PASSED** — diagnostic evidence only; frozen `AUTOMATED_PASS` in committed result is **incorrect** (harness/scorer bug).
2. **Do not retroactively rewrite** frozen live artifacts (`raw`, `result`, `manifest`, `attempt`, `ledger`, `manual_review`, `audit.log`).
3. **Corrected provider totals:** 18 actual LLM calls (stdout + `llm_usage`); committed target ledger = 10 (incomplete).
4. **RERUN_BLOCKED** without new owner approval.
5. **Preflight zero-call marker reclaim** accepted only for the documented preflight incident (`c00fa4d` harness fix); not precedent after ≥1 provider call.

---

## SHA-256 pins (frozen live artifacts — immutable)

| Artifact | Path | SHA-256 |
|----------|------|---------|
| Raw | `evals/v5/artifacts/s62_target_runtime_live_raw.json` | `1091fff43615e9a9adb43bf492dabb46009636eed23d92eac95d8a6073b2a428` |
| Result | `evals/v5/artifacts/s62_target_runtime_live_result.json` | `1091fff43615e9a9adb43bf492dabb46009636eed23d92eac95d8a6073b2a428` |
| Manifest | `evals/v5/artifacts/s62_target_runtime_live_manifest.json` | `4643a99ccb768d5863f96c286c30f8b76ee352c837064d14a7bc2e13a831f1e3` |
| Attempt marker | `evals/v5/artifacts/s62_target_runtime_live_attempt.json` | `2570338b15cba9b4caf5b71c0c873c9ecb1fa8dcbca64014148665184ecfe657` |
| Call ledger | `evals/v5/artifacts/s62_target_runtime_live_call_ledger.jsonl` | `fd71c6460b4f8658dab85a2ec1c847d5ff7c2f29ab9a2d82886bf2ba98cf97a2` |
| Manual review seed | `evals/v5/artifacts/s62_target_runtime_live_manual_review.json` | `9983da4ee2dcf0f9c35d4f40815a599607c87daf13846880c548052d9c885741` |
| Harness audit log | `evals/v5/artifacts/s62_target_runtime_live_audit.log` | `e6a2d1e5bdc1cfe20e20dfe5d7f23c644103a97ab1eda8132346fc9616e82e02` |
| **Stdout capture** | `evals/v5/artifacts/s62_live_stdout_capture.txt` | `3CA6A7EBB971FEDAFD5A3507442A49BE660CB56B96BD862CB11528C9D15D7AFC` |

Frozen turns spec hash: `f3b41f7b250f7ab72111cdce72b2346e0e54c299a0b72276a9848c281b205c55`

---

## Corrected provider accounting

| Role | Actual (stdout / `llm_usage`) | Committed ledger | Delta |
|------|--------------------------------|------------------|-------|
| ingress | 4 | 0 | ledger gap |
| planner | 4 | 0 | ledger gap |
| medical_boundary | 4 | 4 | match |
| composer | 3 | 3 | match |
| semantic_verifier | 3 | 3 | match |
| **Total** | **18** | **10** | **8 missing** |

Retries: **0** · legacy hits: **0** · budget ≤20: **PASS**

Turn 3 skipped composer/verifier (terminal defer after boundary).

---

## Frozen harness verdict (incorrect — do not edit)

Committed `s62_target_runtime_live_result.json` records:

- `automated_verdict`: `AUTOMATED_PASS` ← **wrong** (scorer ignored failed gates)
- `final_verdict`: `PENDING_MANUAL_REVIEW`
- `followup_ref_pass`: `false`

**Corrected post-audit ruling:** technical/final **FAIL** (`S62_NOT_PASSED`).

---

## Causal taxonomy

| ID | Finding | Class |
|----|---------|-------|
| C1 | Harness audit wrapper missed ingress/planner transport frames | harness bug |
| C2 | Scorer emitted `AUTOMATED_PASS` despite `followup_ref_pass=false` | harness bug |
| C3 | Turn 3 doctors: planner had `service_id=all_on_4`, shadow frame lost continuity → `terminal_defer` | product/runtime bug |
| C4 | Turn 1: `cta_key=plan` in meta but widget `cta=null` (`cta_action` missing) | product/widget bug |
| C5 | Turn 1: no price quick reply displayed (UI limit policy); follow-up ref test used fallback text | expectation/spec + UI policy |
| C6 | Turn 2: `UnicodeEncodeError` logging ₽ on Windows cp1251 (HTTP 200, answer captured) | environment/logging |
| C7 | Preflight abort before first provider call (wrong legacy guard module path) | harness preflight incident |

---

## Preflight incident (zero-call reclaim)

| Field | Value |
|-------|-------|
| Commit before fix | `9a6bc2a` |
| Error | `ModuleNotFoundError: orchestration.routing_after_resolver` |
| Marker | created with `started_provider_calls=0` |
| Fix | `c00fa4d` legacy guard paths + zero-call reclaim |
| Live attempt | second run with `--owner-override-attempt-marker` |

Not precedent for rerun after ≥1 provider call.

---

## Manual review (audit seed — frozen files unchanged)

| Turn | Endpoint | Manual technical | Notes |
|------|----------|------------------|-------|
| 1 | `/ask` All-on-4 info | answer **PASS**, CTA **FAIL** | price-followup expectation too narrow; UI showed MD refs only |
| 2 | `/ask` price (fallback text) | answer **PASS**, session price **PASS** | actual ref-click not exercised |
| 3 | `/ask` doctors | **FAIL** | unexpected `target_fullcontext_terminal_defer` |
| 4 | `/ask/stream` lupus | answer **PASS** (S59 policy), SSE **PASS** | materialized medical handoff |
| **Overall** | | **FAIL** | `S62_NOT_PASSED` |

---

## Acceptance failures (owner)

- `followup_ref_pass=false` (harness gate; Turn 1 had no price QR — corrected criterion in Phase B)
- Turn 3 doctors → terminal defer instead of catalog materialization
- CTA key selected, widget CTA absent
- Ledger incomplete (10 vs 18)
- Frozen `AUTOMATED_PASS` erroneous

---

## Governance

- NO authority / NO A9 / NO legacy fallback introduced
- Frozen S47/S50/S53/S55/S58 artifacts untouched
- `TARGET_FULLCONTEXT_DEV` default OFF unchanged
- **RERUN_BLOCKED**
