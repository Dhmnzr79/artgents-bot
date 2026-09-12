# FINAL_RESPONSE_LATENCY_OBSERVABILITY (PERF-0) — seam audit

**Дата:** 2026-07-28
**Baseline:** `codex/stage-a` @ `d381bc9`
**Режим:** governance / docs / tests only · **NO product code / NO product instrumentation / NO real streaming / NO Boundary bypass / NO Verifier context change / NO provider prewarm / NO answer cache / NO UX redesign / NO LIVE / NO LLM / NO E2E / NO frozen artifact changes / NO TSC-C / NO TSC-D / NO Ingress+Planner merge**
**Owner GO:** Phase 1 governance only; implementation blocked until PRE-CODE ✅ + separate owner GO

## Preflight

| Check | Result |
|---|---|
| Branch `codex/stage-a` | ✅ |
| `HEAD` == `origin/codex/stage-a` @ `d381bc9` | ✅ |
| Working tree clean at governance start | ✅ |

## Defect / motivation (confirmed offline @ `d381bc9`)

**Turn:** «Я боюсь боли» observed end-to-end at ~12–15s. `/ask/stream` does **not** carry a real answer
during Composer generation: `orchestrate_target_fullcontext_turn` (Ingress → Planner → Boundary →
Composer → Verifier → widget) runs to completion **before** the SSE generator (`_gen()`) is entered.
There is currently no instrumentation that isolates which of the six stages consumes the time — only
one end-to-end mark exists. PERF-0 adds measurement only; it changes no answer, route, LLM-call count,
or UI behavior.

## Chain under audit

```text
Ingress → Turn Planner → Medical Boundary → Composer → Semantic Verifier → Runtime/presentation/widget
```

## Master seam table (@ `d381bc9`)

| # | Stage | Producer (exact call site) | LLM? | Existing timing | Existing usage/cache logging |
|---|---|---|---|---|---|
| A | Ingress | `orchestration/pre_resolver_turn.py:131` `classify_ingress(q, ...)` → `ingress_gate.py:433` `_call_ingress_llm` | Conditional (see gate B) | **None** | `log_llm_usage(call_type="ingress_classify")` at `ingress_gate.py:444`; `log_llm_error` at `:527` |
| B | Ingress deterministic short-circuits | `ingress_gate.py:520` `_ingress_deterministic_normal`; `:516` `match_clinic_policy_key`; `:509/:513` skip/short | No | **None** | N/A (no LLM call made) |
| C | Turn Planner (LLM) | `orchestration/planner_turn.py:70` `plan_turn_attempt` → `core/turn_planner_llm.py:244` `_planner_chat_completions_create` | Yes | **None** | `log_llm_usage(call_type="turn_planner_plan")` at `turn_planner_llm.py:255` |
| D | Turn Planner (typed UI, deterministic) | `orchestration/typed_ui_planner_turn.py:49` `try_run_typed_ui_planner_turn` | No — skips Planner LLM entirely when a governed UI scope/stage click is on ctx | **None** | N/A |
| E | Medical Boundary | `core/target_runtime_turn.py:308` `execute_target_medical_boundary_classification` → `core/target_runtime_llm_backends.py:187` `TargetRuntimeLiveMedicalBoundaryBackend.classify` | Yes | **None** | `log_llm_usage(call_type="target_fullcontext_runtime_boundary")` at `target_runtime_llm_backends.py:198` |
| F | Structured-capability bypass (Boundary+Composer+Verifier all skipped) | `core/target_runtime_turn.py:196-305` — `structured_capability.kind in {"clinic_contact","service_availability"}` | No | **None** | N/A |
| G | Composer | `core/target_composer_executor.py:422` `generate(invocation)` → `core/target_runtime_llm_backends.py:80` `TargetRuntimeLiveComposerBackend.generate` | Yes (never `stream=True` today) | **None** | `log_llm_usage(call_type="target_fullcontext_runtime_composer")` at `target_runtime_llm_backends.py:88` |
| H | Semantic Verifier — deterministic pre-checks | `core/target_response_verifier.py:713-752` (numeric-claim grounding, `must_preserve_exact` facts, clinic-contact scalar match) | No | **None** | N/A — can `_error(...)` and block **before** any LLM call |
| I | Semantic Verifier — LLM assessment | `core/target_response_verifier.py:761` `assess(invocation)` → `core/target_runtime_llm_backends.py:128` `TargetRuntimeLiveSemanticBackend.assess` | Yes | **None** | `log_llm_usage(call_type="target_fullcontext_runtime_verifier")` at `target_runtime_llm_backends.py:136` |
| J | Verifier — semantic blocking (post-LLM) | `core/target_response_verifier.py:768-773` `_blocking_issues` → `_error("target_verifier_semantic_rejected", ...)` | N/A (after I) | **None** | N/A |
| K | Runtime/presentation/widget finalization | `core/target_runtime_widget.py` `widget_payload_from_runtime_result` / `materialize_verified_widget_payload` / terminal / error builders | No | **None** | N/A |
| L | Orchestration total (existing) | `app.py:364` (`/ask`) and `app.py:511` (`/ask/stream`) `mark("orchestrate_done")` right after `_orchestrate_ask_turn()` returns | — | **Only mark that exists today**; fires **after** stages A–K have all completed | — |
| M | Turn-complete emission | `orchestration/finalize_turn.py:58` `finalize_ask` → `emit_bot_event(..., "turn_complete", details={..., **summary_for_turn_complete()})` | — | Emits `total_ms` (from `turn_t0_monotonic`) + `orchestrate_done_since_start_ms` | Aggregates nothing per-stage; per-call usage lives in separate `llm_usage` events (A/C/E/G/I), not joined to `turn_complete` |
| N | SSE dispatch | `app.py:428-465` `_sse_service_reply` | — | **None** — `finalize_ask` (row M) already ran **before** `_gen()` is defined; the generator then yields `typing` → `ui` → `done` back-to-back with no gap | — |
| O | Client (widget) | `static/widget/api.js`, `static/widget/widget.js` | — | **None** — no `performance.now()`/`Date.now()` anywhere in either file | — |

## Findings

### 1. Exactly one timing datum exists today, and it is post-hoc

`core/turn_timing.py` provides a generic `mark`/`record_ms`/`timed_stage` bucket keyed on
`request.ctx["turn_timing"]`, plus `summary_for_turn_complete()` which turns marks into
`{mark}_since_start_ms` and computes `total_ms`. In product code, exactly **one** mark is ever
set: `orchestrate_done` (row L), written immediately after the entire six-stage chain has already
returned. No stage in A–K currently calls `mark(...)` or `timed_stage(...)`. This means
`turn_timing` today answers "how long did the whole turn take", not "which stage was slow" — the
central PERF-0 gap.

### 2. `/ask/stream` does not stream the turn — it streams the *response envelope* after the fact

`_sse_service_reply` (`app.py:428`) computes `out = finalize_ask(payload, ...)` — i.e. the entire
turn including Composer and Verifier — **before** defining the SSE generator `_gen()`. The
generator then yields `event: typing` → `event: ui` → `event: done` with no real gap between them.
The `phase` ("searching" vs "writing") passed to the first SSE event is chosen from the **final**
route (`_sse_typing_phase`, `app.py:405`), not from real-time stage progress. This confirms the
milestone context precisely: today there is no `time_to_first_server_event` distinct from
`total_ms`, and no `time_to_first_composer_token` is possible because the Composer backend is
never called with `stream=True` (row G) — per Rule 4 of the milestone, this metric must be recorded
as `not_available`/`null`, not fabricated from the full response.

### 3. `verifier_turn` is a dead metric slot

`orchestration/finalize_turn.py:27` (`verifier_trace_flat`) and the `turn_complete` /
`bot_reply_completed` event builders read `request.ctx.get("verifier_turn")` (lines 136, 173), but
**no code anywhere in the repository writes `request.ctx["verifier_turn"]`.** This is an existing
consumer with no producer — a latent no-op today. PERF-0 should not silently "fix" this by
attaching new data to an unused key without governance sign-off; the seam is flagged here for the
implementation phase to decide whether to reuse or retire it.

### 4. Two independent "total duration" computations already exist and can drift

- `orchestration/finalize_turn.py:140-143` computes `lat_ms` from
  `request.ctx.get("turn_t0_monotonic")` directly, inline in `finalize_ask`.
- `core/turn_timing.py:87-89` (`summary_for_turn_complete`) computes `total_ms` from the **same**
  `turn_t0_monotonic`, but at a different call point inside the same function.

Both end up in the same `turn_complete` event (`latency_ms` and `total_ms` side by side) and will
normally agree to within a few ms, but they are two independently computed fields from one clock
read. This is a pre-existing double-count risk pattern the implementation phase must not repeat
when adding new stage marks — see Finding 6.

### 5. Structured/deterministic paths that bypass one or more LLM calls entirely

These are not bugs; they are correct fast paths, and PERF-0 must represent them as **explicitly
skipped**, never as `0ms` or missing:

| Path | What it skips |
|---|---|
| `/reset`, empty q, rate-limited, obvious-noise, anti-spam burst/soft-redirect (`orchestration/pre_resolver_turn.py`) | Entire chain A–K; short-circuits before Ingress even runs |
| Ingress `policy_key` match / `_ingress_deterministic_normal` (row B) | Ingress LLM call (row A) |
| `ref`-click with `is_ui_scope_ref` / `is_ui_stage_ref` → typed UI TurnFrame (row D) | Turn Planner LLM call (row C) |
| `structured_capability.kind in {"clinic_contact","service_availability"}` (row F) | Medical Boundary (E), Composer (G), Verifier (H/I/J) — all three |
| Verifier deterministic pre-check failure (row H) | Verifier LLM call (row I) — blocked before ever reaching the backend |
| Ingress non-`normal` route, lead/flow handling (`flow_handlers.handle_flows`) | Turn Planner, Boundary, Composer, Verifier entirely |

### 6. Two plausible instrumentation seams per LLM stage — pick one to avoid double-counting

Each LLM stage has two candidate wrap points:

- the **provider-neutral orchestration boundary** (e.g. `execute_target_composer` calling
  `generate(invocation)` at `core/target_composer_executor.py:422`; `verify_target_composed_response`
  calling `assess(invocation)` at `core/target_response_verifier.py:761`) — this is also what fake
  backends in tests implement, so timing here stays structurally comparable between offline tests
  and live runs (near-zero for fakes, real latency for `TargetRuntimeLive*Backend`);
- the **live backend / network boundary** (`core/target_runtime_llm_backends.py`), which is where
  `log_llm_usage`/cache/model/`call_type` data is already captured today (rows A, C, E, G, I).

If a future implementation marks stage duration at **both** layers (e.g. wraps
`execute_target_composer` *and* wraps `TargetRuntimeLiveComposerBackend.generate` separately), the
two spans nest and any `accumulate=True` usage would double-count the same LLM round trip. PERF-0's
implementation allowlist (below) exists to force a single documented seam per stage — the
orchestration boundary for `mark`/`timed_stage` (stage start/end), joined by `request_id` to the
existing `llm_usage` event (model/cache/tokens) emitted from the backend layer for the same call.

### 7. Error / terminal / fallback / verifier-blocked turns already reach `finalize_ask`

Any exception in the target pipeline is caught in `core/target_runtime_turn.py` and converted to
`materialize_target_error_payload(...)`, which still returns as `AskOrchestrationResult(kind="service_reply", ...)`.
That means `finalize_ask` (row M) — and therefore whatever total-duration accounting it does — still
runs for boundary failures, composer failures, and verifier blocks (both deterministic row H and
semantic row J). `emit_target_pipeline_failure_from_exception` (`core/target_pipeline_observability.py:62`)
additionally emits a separate `target_pipeline_failure` event with `stage`/`code`/`value`, but **without**
`summary_for_turn_complete()` — i.e. today's error path gets total latency but not a per-stage
breakdown, same gap as the happy path (Finding 1). Two orchestration outcomes never reach
`finalize_ask` at all: `kind="unknown_client"` and `kind="reset_session"` (`app.py:331-334`) — these
are pre-turn/administrative responses, not part of the six-stage chain, and are out of scope for the
acceptance matrix below.

### 8. Client (widget) has zero timing instrumentation today

Neither `static/widget/api.js` nor `static/widget/widget.js` calls `performance.now()` or
`Date.now()` anywhere. `time_to_first_local_status` (the widget-only metric named in the milestone)
is not measured client-side at all today — there is no scaffold to extend. The SSE parser in
`api.js` (`event: typing` / `event: text_delta` handling, lines ~98-101) does not timestamp receipt
of any event.

### 9. `/ask` vs `/ask/stream` parity

Both entrypoints call the same `_orchestrate_ask_turn(data)` (`app.py:294`) and set
`request.ctx["turn_t0_monotonic"]` at handler entry (`app.py:352`, `:499`) and
`mark("orchestrate_done")` right after (`app.py:364`, `:511`). `/ask` dispatches to `_service_reply`
→ `finalize_ask` → `safe_jsonify`. `/ask/stream` dispatches to `_sse_service_reply`, which calls the
**same** `finalize_ask` before building its generator (row N). Today the two paths are already
timing-comparable at the total-duration level (Requirement 8 in the milestone); the gap is that
neither path has stage-level breakdown, and only `/ask/stream` has an (currently unused) opportunity
to emit early SSE events before the turn is fully computed.

## Existing vs. missing metrics (against the milestone's required list)

| Required metric | Status @ `d381bc9` |
|---|---|
| request/turn start | **Exists** — `request.ctx["turn_t0_monotonic"]` (`app.py:352`, `:499`) |
| `time_to_first_local_status` | **Missing** — no client-side timing at all (Finding 8) |
| `time_to_first_server_event` | **Missing** — no mark at SSE generator entry/first yield (Finding 2) |
| Ingress start/complete/duration | **Missing** — no marks; only `log_json("ingress_gate", ...)` outcome log (`pre_resolver_turn.py:132`), no duration |
| Planner start/complete/duration | **Missing** — no marks; usage-only via `log_llm_usage` |
| Boundary start/complete/duration or skipped | **Missing** — no marks; structured-capability bypass (row F) not currently flagged as "boundary skipped" anywhere |
| Composer start | **Missing** |
| `time_to_first_composer_token` | **Not available today** — Composer never called with `stream=True` (row G); must be recorded `not_available`/`null` per Rule 4, not derived from full response |
| Composer complete/duration | **Missing** |
| Verifier start/complete/duration or skipped | **Missing** — no distinction today between deterministic block (row H, no LLM reached) and semantic block (row J, after LLM) |
| verified answer ready | **Missing** as an explicit mark (implicit: return of `verify_target_composed_response`) |
| presentation/widget payload ready | **Missing** as an explicit mark (implicit: return of `widget_payload_from_runtime_result`) |
| `time_to_first_meaningful_text` | **Missing** — no concept of "meaningful text" is marked anywhere; would need explicit definition tied to prebuffer release in `core/stream_answer_text.py` (unwired — see below) |
| HTTP/SSE complete | **Missing** — no mark after generator finishes yielding |
| total turn duration | **Exists** — `total_ms` (`turn_timing.py:87-89`) **and** separately `latency_ms` (`finalize_turn.py:141-143`) — two fields, one source (Finding 4) |
| cache hit/miss + cached token count per LLM call | **Exists** — `log_llm_usage`/`log_llm_stream_usage` already read `prompt_tokens_details.cached_tokens` (`logging_setup.py:238-269`) at all four current LLM call sites (Ingress, Planner, Boundary, Composer, Verifier — rows A, C, E, G, I) |
| model + call_type per LLM call | **Exists** — same `log_llm_usage` calls already pass `call_type` and `model` |

**Net:** cache/token/model observability is already solid (reuse, do not duplicate). Everything
stage-shaped (start/end/duration/skipped) is absent. This is exactly what PERF-0 implementation
should add, using the existing `turn_timing` mechanism rather than a parallel logging system (Rule 6).

## Note on `core/stream_answer_text.py`

`StreamTextAccumulator` / `prebuffer_ready` already exist and implement lead-buffered display-text
release, but are **not wired** into `/ask/stream` today (confirmed: `app.py` never imports
`core.stream_answer_text`). This module is pre-existing, unrelated-to-PERF-0 scaffolding for a future
real-streaming milestone. PERF-0 does not wire it, use it, or change it — noted only so the
implementation phase does not mistake "unused module already exists" for "streaming already works."

## Implementation allowlist (Phase 2 — blocked until owner GO)

Instrumentation-only; must not change payload content, routes, LLM call count, or session state.

| File | Action |
|---|---|
| `core/turn_timing.py` | UPDATE — extend mark/duration vocabulary only (e.g. stage names), no behavior change to existing consumers |
| `orchestration/pre_resolver_turn.py` | UPDATE — mark Ingress start/end around `classify_ingress`; mark deterministic-skip reason |
| `ingress_gate.py` | UPDATE — mark around `_call_ingress_llm` only (not the deterministic paths) |
| `orchestration/planner_turn.py` | UPDATE — mark Planner start/end around `plan_turn_attempt` |
| `orchestration/typed_ui_planner_turn.py` | UPDATE — mark Planner "skipped: typed_ui" |
| `core/target_runtime_turn.py` | UPDATE — mark Boundary start/end around `execute_target_medical_boundary_classification`; mark "boundary skipped: structured_capability" for rows F |
| `core/target_composer_executor.py` | UPDATE — mark Composer start/end around `generate(invocation)` call (single seam, per Finding 6) |
| `core/target_response_verifier.py` | UPDATE — mark Verifier start; mark "verifier blocked: deterministic" (row H) vs mark around `assess(invocation)` + "verifier blocked: semantic" (row J) — **no change to verification logic or prompts** |
| `core/target_runtime_widget.py` | UPDATE — mark "widget payload ready" |
| `app.py` | UPDATE — mark SSE generator entry / first-yield / generator-complete for `/ask/stream`; keep `/ask` and `/ask/stream` marks comparable |
| `orchestration/finalize_turn.py` | UPDATE — join per-stage marks into `turn_complete`/`target_pipeline_failure` details; resolve the `latency_ms`/`total_ms` duplication (Finding 4) into one documented field, not a third field |
| `static/widget/api.js` | UPDATE — add `performance.now()` capture at SSE event receipt (`typing`, `text_delta`, `ui`, `done`) |
| `static/widget/widget.js` | UPDATE — add `time_to_first_local_status` capture at first UI-visible typing indicator |
| `tests/test_final_response_latency_observability_implementation.py` | CREATE — acceptance matrix below |

**KEEP unchanged:** Verifier policy/prompts, Boundary policy/prompts, Composer policy/prompts, all
routing/threshold logic, LLM call count per turn, session writes, widget payload content/CTA/buttons,
`core/stream_answer_text.py` (untouched, unwired).

## Acceptance matrix (implementation — minimum coverage)

| # | Scenario | Stages expected | Expected trace shape |
|---|---|---|---|
| 1 | FAQ (generic FullContext, no service match) | Ingress → Planner → Boundary(none) → Composer → Verifier → widget | full stage breakdown, all durations present |
| 2 | Price lookup | Ingress(deterministic or LLM) → Planner → Boundary → Composer → Verifier → widget | full breakdown; Ingress may show `skipped` |
| 3 | Contacts (`structured_capability.kind="clinic_contact"`) | Ingress → Planner → widget | Boundary/Composer/Verifier marked **skipped**, not `0ms`/missing |
| 4 | Service availability (`structured_capability.kind="service_availability"`) | Ingress → Planner → widget | Boundary/Composer/Verifier marked **skipped** |
| 5 | Generic FullContext (no structured capability, no service) | full chain | full breakdown |
| 6 | Medical concern → `medical_handoff` | Ingress → Planner → Boundary(medical_handoff) → Composer → Verifier → widget | Boundary duration present; Composer still runs (medical_handoff still composes grounded answer per Composer policy rule 7) |
| 7 | Terminal / fallback (e.g. Boundary terminal enforcement) | Ingress → Planner → Boundary → **terminal**, Composer/Verifier skipped | trace still completes; Composer/Verifier marked **skipped**, `total_ms` present |
| 8 | Verifier blocked — deterministic (ungrounded numeric claim) | full chain through Composer, Verifier stops at row H | Verifier LLM call marked **not reached**; error payload; `turn_complete`/`target_pipeline_failure` both carry a completed trace |
| 9 | Verifier blocked — semantic (LLM rejects) | full chain through Verifier LLM call (row I), blocked at row J | Verifier LLM call duration present; trace completed |
| 10 | `/ask` | same stage trace as equivalent `/ask/stream` scenario | comparable field names/values between the two entrypoints |
| 11 | `/ask/stream` | as above, plus `time_to_first_server_event` | SSE-specific fields present; JSON-only fields (`/ask`) absent or null, not fabricated |

All eleven rows must additionally confirm: identical `answer` text, identical routing decision,
identical LLM call count, and identical session writes versus the pre-PERF-0 baseline for the same
fixture — i.e., a parity diff, not just a presence check.

## PRE-CODE checker

`tests/test_final_response_latency_observability_governance.py` — asserts this seam audit exists and
covers the required stages/findings, asserts `TASK.md` has the PERF-0 governance section with baseline
`d381bc9`, asserts `docs/FLAGS_AND_STATUS.md` and `docs/STRANGLER_ROADMAP.md` reference the milestone,
and asserts the forbidden-in-Phase-1 list is documented verbatim (no real streaming, no Boundary
bypass, no Verifier context change, no provider prewarm, no answer cache, no Ingress+Planner merge).

## Forbidden in governance commit (Phase 1)

- Product instrumentation code changes (no `mark(...)`/`timed_stage(...)` added to `core/`,
  `orchestration/`, `app.py`, or `static/widget/*.js` in this commit)
- Pipeline optimization of any kind
- Real token/text streaming
- Any change to LLM call count
- Medical Boundary bypass changes
- Semantic Verifier context/policy/prompt changes
- Provider prewarm
- Answer cache
- UX redesign
- LIVE / LLM / E2E eval runs
- Frozen artifact / hash changes
- TSC-C / TSC-D
- Merging Ingress + Planner

## Test commands (governance)

```powershell
python -m pytest tests/test_final_response_latency_observability_governance.py -q
git diff --check
```

## STOP

After PRE-CODE ✅ — **STOP**. Implementation only after a separate owner GO.
