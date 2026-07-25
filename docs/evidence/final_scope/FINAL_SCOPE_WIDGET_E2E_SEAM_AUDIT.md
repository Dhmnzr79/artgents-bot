# FINAL scope/widget E2E — seam audit (read-only)

**Date:** 2026-07-25  
**Baseline:** `70a96c1` (A9R3 implementation complete)  
**Scope:** governance + offline pre-live checkpoint · **NO LIVE / NO LLM**

**Owner sequence:** one FINAL live E2E → on PASS remove `A9_PATIENT_SCOPE_AUTHORITY` kill-switch → unconditional A9 authority.

---

## Target chain (live E2E)

```
HTTP /ask | /ask/stream
  → pre_resolver (AC1 UI scope/stage)
  → planner (Plus, A9_PATIENT_SCOPE_AUTHORITY=1)
  → TurnFrame.patient_scope
  → project_patient_scope_from_turn_frame
  → merge_effective_scope_axes
  → EffectiveScope (reported_context stripped)
  → AC2 scope-aware selection
  → AC3 response stage + widget payload
  → session persist (extent/jaw/stage after materialized only)
```

**Reuses:** S63 HTTP harness stack (`contract` / `harness` / `provider_audit` / `run_*.py`), attempt marker, call ledger, exclusive artifacts. **No parallel pipeline.**

---

## Authority env (live only — set before import)

| Env | Value |
|-----|-------|
| `A9_PATIENT_SCOPE_AUTHORITY` | `1` |
| `TURN_PLANNER_LLM_MODEL` | `qwen3.7-plus` |
| ingress | `qwen3.6-flash` |
| boundary/composer/verifier | `qwen3.7-plus` |

Product default remains `A9_PATIENT_SCOPE_AUTHORITY=0` until post-E2E closeout.

---

## Frozen turn matrix

`evals/v5/demo/final_scope_widget_e2e_turns.json`  
**Blob hash:** `f4eecf7532481a288d1db6a6ee107dd147117dae44afc991451836dd3589434f`

| # | SID | Endpoint | Action | Expected |
|---|-----|----------|--------|----------|
| 1 | A | `/ask` | «Сколько стоит имплантация?» | broad overview; 3 scope buttons; no payment stages |
| 2 | A | `/ask` | click «Вся челюсть» | scoped exact offers; scope buttons gone; session `full_arch` |
| 3 | A | `/ask` | «Нет, речь об одном зубе» | A9 correction → session `one_tooth` |
| 4 | B (fresh) | `/ask/stream` | «Сколько стоит имплантация всей челюсти?» | A9 `full_arch`; scoped; no scope nav |
| 5 | C (fresh) | `/ask` | «Сколько стоит протезирование?» | broad prosthetics + 3 scope buttons |
| 6 | C | `/ask` | click «Один зуб» | stage clarification when required |
| 7 | C | `/ask` | click «Имплант установлен» | scoped prosthetics offers; no repeat scope/stage nav |
| 8 | D (fresh) | `/ask/stream` | «Имплант уже установлен, сколько будет коронка?» | A9 `stage=implant_placed`; prosthetics scoped |

---

## Provider call budget (minimal by role)

Assumption: **one provider call per role per HTTP turn** (S63 invariant); ref-only turns may skip ingress.

| Role | Turns using role | Budget |
|------|------------------|--------|
| ingress | 5 text turns (1,3,4,5,8) | **5** |
| planner | all 8 | **8** |
| medical_boundary | all 8 | **8** |
| composer | all 8 | **8** |
| semantic_verifier | all 8 | **8** |
| **Total** | | **37** |

**Contract hard stop:** `MAX_PROVIDER_CALLS = 40` (3-call buffer). Per-role cap **8**. `RETRY_COUNT_MAX = 0`.

**Hard stop triggers:** `ProviderRoleViolationError` on budget exceed; duplicate role in same turn; ledger imbalance.

---

## Automated gates (live)

| Gate | Threshold |
|------|-----------|
| HTTP turns | 8/8 status 200 |
| Route | `target_fullcontext_*`; no legacy/w1 |
| Materialized | 8/8 |
| legacy_hits | 0 |
| fullcontext_build_count | 1 |
| turn automated gates | 8/8 PASS |
| planner model observed | all `qwen3.7-plus` |
| provider total | ≤ 40 |
| ledger | complete + balanced |
| retries | 0 |

**Manual review (mandatory):** all user-visible answers, CTA, follow-up dedup, pricebook fidelity, marketing ≤1 fact, attribution.

---

## Post-E2E closeout (separate owner GO — not this checkpoint)

1. Remove `A9_PATIENT_SCOPE_AUTHORITY` flag and conditional branch  
2. A9 authority unconditional in `resolve_effective_scope` / runtime  
3. Update `docs/FLAGS_AND_STATUS.md`, tests  
4. **No permanent kill-switch**

---

## STOP

Governance + offline pre-live complete. **No live run in this checkpoint.**
