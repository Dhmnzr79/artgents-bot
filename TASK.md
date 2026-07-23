# TASK — S63 delta target FullContext live runtime test (offline prep)

**Baseline:** `codex/stage-a` / `0214ea7` · **NO LIVE / NO LLM on this step**

## Goal

Prepare isolated S63 harness + offline tests for a **3-turn delta live runtime test** validating S62 Checkpoint B fixes only (CTA widget, follow-up ref click, doctors session hydration). Do **not** repeat full S62 (4 turns / medical stream).

## Future S63 artifact paths (exclusive; created only on live run)

| Artifact | Path |
|----------|------|
| Raw | `evals/v5/artifacts/s63_target_runtime_live_raw.json` |
| Result | `evals/v5/artifacts/s63_target_runtime_live_result.json` |
| Manifest | `evals/v5/artifacts/s63_target_runtime_live_manifest.json` |
| Manual review | `evals/v5/artifacts/s63_target_runtime_live_manual_review.json` |
| Attempt marker | `evals/v5/artifacts/s63_target_runtime_live_attempt.json` |
| Call ledger | `evals/v5/artifacts/s63_target_runtime_live_call_ledger.jsonl` |
| Audit log | `evals/v5/artifacts/s63_target_runtime_live_audit.log` |

Frozen turns spec: `evals/v5/demo/s63_target_runtime_live_turns.json` (hash-pinned in contract).

## S62 pin guard (must pass in every S63 test module setup)

Byte-identical check of all frozen S62 live artifacts (SHA-256 from post-live audit `396a226`):

| File | SHA-256 |
|------|---------|
| `s62_target_runtime_live_raw.json` | `1091fff43615e9a9adb43bf492dabb46009636eed23d92eac95d8a6073b2a428` |
| `s62_target_runtime_live_result.json` | `1091fff43615e9a9adb43bf492dabb46009636eed23d92eac95d8a6073b2a428` |
| `s62_target_runtime_live_manifest.json` | `4643a99ccb768d5863f96c286c30f8b76ee352c837064d14a7bc2e13a831f1e3` |
| `s62_target_runtime_live_attempt.json` | `2570338b15cba9b4caf5b71c0c873c9ecb1fa8dcbca64014148665184ecfe657` |
| `s62_target_runtime_live_call_ledger.jsonl` | `fd71c6460b4f8658dab85a2ec1c847d5ff7c2f29ab9a2d82886bf2ba98cf97a2` |
| `s62_target_runtime_live_manual_review.json` | `9983da4ee2dcf0f9c35d4f40815a599607c87daf13846880c548052d9c885741` |
| `s62_target_runtime_live_audit.log` | `e6a2d1e5bdc1cfe20e20dfe5d7f23c644103a97ab1eda8132346fc9616e82e02` |

Implemented as `assert_frozen_s62_live_artifacts_unchanged()` in `s63_target_runtime_live_contract.py`. S62 turns hash (`s62_target_runtime_live_turns.json`) is **not** mutated.

## Frozen turns spec (authoritative JSON)

```json
{
  "schema_version": 1,
  "suite_id": "s63_target_runtime_live",
  "client_id": "demo",
  "turns": [
    {
      "turn": 1,
      "turn_id": "s63_turn_01_all_on_4_info",
      "endpoint": "/ask",
      "request": { "q": "Что такое All-on-4?" }
    },
    {
      "turn": 2,
      "turn_id": "s63_turn_02_followup_ref",
      "endpoint": "/ask",
      "request_kind": "followup_ref_from_turn_1",
      "fallback_request": { "q": "Кому подходит All-on-4?" }
    },
    {
      "turn": 3,
      "turn_id": "s63_turn_03_doctors",
      "endpoint": "/ask",
      "request": { "q": "А кто делает?" }
    }
  ]
}
```

Turn 2: harness picks first visible `quick_replies` entry from Turn 1; sends `{ "q": "", "ref": "<picked.ref>" }`. `fallback_request` used only if Turn 1 had no visible follow-up (→ gate fail).

## Future live turns (summary)

| Turn | Endpoint | Request | Expected |
|------|----------|---------|----------|
| 1 | `/ask` | `Что такое All-on-4?` (new sid) | materialized; authored CTA; ≥1 follow-up button |
| 2 | `/ask` | ref of displayed Turn-1 follow-up | target nav restores label; materialized; no legacy |
| 3 | `/ask` | `А кто делает?` (same sid) | session hydration → `all_on_4`; materialized doctors; no defer |

## Live budget (future run only — not executed here)

| Role | Max |
|------|-----|
| ingress | 3 |
| planner | 3 |
| medical_boundary | 3 |
| composer | 3 |
| semantic_verifier | 3 |
| **total** | **15** |
| retry | 0 |

Models: ingress/planner `qwen3.6-flash`; boundary/composer/verifier `qwen3.7-plus`.

## Automated gates (harness)

1. All 3 turns via target path.
2. No legacy/RAG/chunk handlers.
3. All 3 materialized + verified route.
4. Turn 1 authored CTA present when key selected.
5. Turn 1 shows target follow-up.
6. Turn 2 uses displayed ref.
7. Turn 2 target navigation (no legacy).
8. Turn 3 doctors materialized for All-on-4.
9. Session continuity (`last_service_id=all_on_4` before Turn 3).
10. FullContext built once.
11. Provider ledger complete (all 5 roles; start/complete paired).
12. Total calls ≤15, retry=0.
13. Provider/pipeline/transport errors = 0.
14. No terminal/defer/error routes on mandatory turns.
15. Any mandatory gate fail → `AUTOMATED_FAIL`; `AUTOMATED_PASS` → `PENDING_MANUAL_REVIEW` only.

## `tests/test_s63_correction_offline.py` scope

S63-only delta coverage with fake/recording backends. **Do not modify** `tests/test_s62_correction_offline.py`.

| Test area | What S63 adds beyond S62 |
|-----------|--------------------------|
| CTA / unknown key | import-level smoke via `build_target_runtime_widget_cta` (regression pin) |
| Follow-up pick + HTTP ref | 3-turn sid flow: Turn 1 seeds followups → Turn 2 ref click → Turn 3 doctors |
| Session hydration | Turn 3 doctors materialized after Turn 1–2 session carries `all_on_4` |
| Fresh doctors question | no fabricated `service_id` (unit, not in 3-turn live spec) |
| Harness gates | `_evaluate_summary` fails on missing CTA/doctors/follow-up |
| Provider audit | 5-role ledger, call-16 hard stop (budget 15) |
| S62 immutability | `assert_frozen_s62_live_artifacts_unchanged()` |

## Allowlist

| File | Change |
|------|--------|
| `TASK.md` | S63 governance |
| `evals/v5/demo/s63_target_runtime_live_turns.json` | frozen 3-turn spec |
| `evals/v5/s63_target_runtime_live_contract.py` | S63 contract + S62 pin guard |
| `evals/v5/s63_target_runtime_live_provider_audit.py` | provider audit (15-call budget) |
| `evals/v5/s63_target_runtime_live_harness.py` | HTTP harness + gates |
| `evals/v5/run_s63_target_runtime_live.py` | CLI (`--dry-run` / `--live`; no live here) |
| `tests/test_s63_target_runtime_live_harness.py` | harness contract/audit/gates tests |
| `tests/test_s63_correction_offline.py` | 3-turn HTTP delta + product regression pins |
| `docs/STRANGLER_ROADMAP.md` | S63 prep note |

**Forbidden:** live/LLM, `TARGET_FULLCONTEXT_DEV` default flip, authority switch, A9, legacy fallback, frozen S62 artifact edits, product changes outside harness/tests.

## Commands

```powershell
$bt = Join-Path $env:TEMP ("s63_pytest_" + [guid]::NewGuid().ToString("n"))
python -m pytest -p no:cacheprovider --basetemp $bt `
  tests/test_s63_target_runtime_live_harness.py `
  tests/test_s63_correction_offline.py `
  -q

python evals/v5/run_s63_target_runtime_live.py --dry-run
```

## Acceptance (COMPLETION)

- [ ] PRE-CODE ✅
- [ ] Targeted pytest green (both test modules)
- [ ] `run_s63_target_runtime_live.py --dry-run` exits 0
- [ ] S62 frozen artifacts byte-identical (pin guard in tests)
- [ ] No live/LLM/network calls
- [ ] Allowlist-only diff
- [ ] COMPLETION checker ✅

## Checker

| Checkpoint | When |
|---|---|
| PRE-CODE | before implementation |
| COMPLETION | after pytest green |
