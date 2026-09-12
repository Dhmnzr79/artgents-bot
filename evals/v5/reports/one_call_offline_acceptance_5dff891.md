# ONE-CALL-OFFLINE-ACCEPTANCE-1

Checkpoint: `5dff891b0ba9049704eb321aac895a2d7ffc268d`

Branch: `codex/one-call-cached-fullcontext-baseline`

Date: 2026-09-03 (final C3 assertion fix)

## 1. Pre-flight

| Check | Result |
| --- | --- |
| Branch | `codex/one-call-cached-fullcontext-baseline` |
| HEAD | `5dff891b0ba9049704eb321aac895a2d7ffc268d` |
| Staged | empty |
| Allowlist edits | `tests/test_response_plan_dialogue_acceptance.py`, `evals/v5/reports/one_call_offline_acceptance_5dff891.md` only |

Allowlist SHA-256 after this pass:

| File | SHA-256 |
| --- | --- |
| `tests/test_response_plan_dialogue_acceptance.py` | `80787AB0AD1CA4703E726F850D9613C245C1B66C8B21A0703869FC606025499E` |
| `evals/v5/reports/one_call_offline_acceptance_5dff891.md` | (this file) |

## 2. Pipeline under test

`ResponsePlanSessionStore.read` → `begin_bound_session_turn` → `execute_bound_session_turn` (RecordingBackend) → parser/adapter → selection/materialization → resolver/renderer → `prepare_bound_session_turn` → `commit_session_update` → `read`.

Recording backend substitutes model JSON only. Not tested: live NLU, HTTP/SSE cutover, provider/network.

## 3. C3 — final assertions (`test_c3_end_to_end_price_with_nonempty_required_conditions`)

Data: REAL demo bundle + **SYNTHETIC** `OfferConditionEvidence(complete, non-empty conditions)` on `all_on_4.jaw.implantium` and `all_on_4.jaw.impro`. Condition texts are test-owned, not clinic metadata.

Added/strengthened checks in this pass:

| Area | Assertion |
| --- | --- |
| **Render order** | Using renderer-aligned condition strings (`_condition_display_texts`): full price block ends before **each** of the two conditions; **each** condition ends before `patient_text`. No extra ordering requirement between the two conditions. |
| **SQLite memory** | `accumulated_before = runner.read()` before the turn; after commit `accumulated_after = runner.read().state.accumulated_shown_ids` (not `prepared.proposed_state` alone). Non-empty finalized `price_offer_ids` and `required_offer_condition_ids`; `accumulated_after == prior ∪ finalized` for both groups. |
| **Frozen price rows** | `offer_rows` contains exactly one row per expected offer ID; each row matches bundle `TargetFixedPrice`: `amount`, `currency`, `billing_unit`. |
| **Preserved** | Non-empty condition entries linked to offer IDs; no `ServiceOptionsBlock`; full recording pipeline unchanged. |

## 4. Other acceptance scenarios (unchanged this pass)

Stale expiry, accumulated memory (A/D), C1 warranty topic, C2 requested+promo overlap, A–H matrix — see prior rows; all remain **25/25 PASS** after this fix.

## 5. Command results (this pass)

Environment before pytest:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:OPENAI_API_KEY='sk-offline-test-key-not-for-live'
```

Commands executed from repo root (no ellipsis):

```powershell
python -m pytest -q -p no:cacheprovider tests/test_response_plan_dialogue_acceptance.py
python -m pytest -q -p no:cacheprovider tests/test_response_plan_composer_contract.py tests/test_response_plan_composer_parser.py tests/test_response_plan_composer_input.py tests/test_response_plan_composer_executor.py tests/test_response_plan_post_composer.py tests/test_response_plan_materialization_integration.py tests/test_response_plan_session_integration.py
```

**This pass:**

| Command | Result |
| --- | --- |
| `tests/test_response_plan_dialogue_acceptance.py` | **25 passed**, 3 warnings |
| Fixed adjacent regression set (7 files above) | **259 passed**, 3 warnings |

**Previous passes (not re-run here):**

| Command | Result (historical) |
| --- | --- |
| Adjacent regression (correction pass) | 262 passed — count differed; current fixed set yields **259 passed** |
| `tests/test_demo_target_service_catalog.py` | 3 failed — **not re-run in this pass** |

Catalog suite and full-repo pytest were not executed.

## 6. Data origin

| Layer | Label |
| --- | --- |
| Demo bundle / FullContext | REAL_CATALOG (on disk unchanged) |
| Injected condition evidence (C3, A, B, …) | SYNTHETIC |
| In-memory display policies (C1, D synthetic) | SYNTHETIC_POLICY_FIXTURE |
| `_terminal_authorities_for()` | SYNTHETIC terminal text/phones |

REAL_CATALOG inputs + SYNTHETIC authorities/evidence where noted. C3 green does **not** confirm clinic-authored price conditions.

## 7. Non-allowlist WIP (comparable check)

Algorithm: SHA-256 of each path in saved manifest `%TEMP%\offline-acceptance-pre-20260903-132058\non-allowlist-pre.txt` (86 paths), UTF-8 file bytes, hash in manifest compared uppercase.

| When | missing | changed |
| --- | --- | --- |
| Before this pass | 0 | 0 |
| After this pass | 0 | 0 |

Logs (`logs/app.jsonl`) may append pytest INFO lines; not counted as source/doc WIP changes. New untracked files outside the 86-path manifest are not proven absent by this check alone.

## 8. Catalog readiness (not re-evaluated here)

Previous run: **NOT PASS** — `test_real_target_catalog_is_strict_complete_s1_wire_data`, `test_family_roles_and_selection_match_normative_inventory`, `test_content_refs_and_doctor_service_links_are_complete` (service `braces`: normative inventory drift + missing `content_ref`).

## 9. Runtime defects

None from C3 final assertions; all targeted tests green without weakening expectations.

## 10. Status summary

| Area | Status |
| --- | --- |
| Offline pipeline acceptance | **PASS** (25/25) |
| Adjacent regression (this pass) | **PASS** (259/259) |
| Real catalog / data readiness | **NOT PASS** (prior catalog run; not re-run) |
| Real model NLU | **NOT TESTED** |
| HTTP/SSE cutover | **NOT TESTED** |
