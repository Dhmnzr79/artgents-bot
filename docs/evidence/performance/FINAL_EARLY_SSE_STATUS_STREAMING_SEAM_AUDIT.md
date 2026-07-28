# FINAL_EARLY_SSE_STATUS_STREAMING (PERF-1) — seam audit

**Дата:** 2026-07-28
**Baseline:** `codex/stage-a` @ `228ee28`
**Режим:** governance / docs / tests only · **NO product implementation / NO Composer token streaming /
NO text_delta / NO answer/route/prompt change / NO LLM-call-count change / NO Boundary bypass / NO
Verifier change / NO prewarm/cache / NO Ingress+Planner merge / NO UX redesign / NO LIVE / NO LLM / NO
E2E / NO frozen artifacts / NO TSC-C / NO TSC-D**
**Owner GO:** Phase 1 governance only; implementation blocked until PRE-CODE ✅ + separate owner GO

## Preflight

| Check | Result |
|---|---|
| Branch `codex/stage-a` | ✅ |
| `HEAD` == `origin/codex/stage-a` @ `228ee28` | ✅ |
| Working tree clean at governance start | ✅ |

## Goal

Make `/ask/stream`'s SSE connection and its **first server event** appear **before** orchestration
finishes, using honest status derived from the pipeline's real state (ideally PERF-0's existing
`stage_start`/`stage_end`/`stage_skipped` marks), without streaming Composer tokens, without a second
timing system, and without changing `/ask`, routes, answers, or LLM call count.

## Why `/ask/stream` answers late today (confirmed @ `228ee28`)

`app.py:502` `ask_stream()` calls `orch_r = _orchestrate_ask_turn(data)` **synchronously** at line 521 —
this one call runs the entire chain (`run_pre_resolver_turn` → `try_run_typed_ui_planner_turn` /
`run_planner_turn` → `orchestrate_target_fullcontext_turn` → `run_target_fullcontext_runtime_turn`,
i.e. Ingress → Planner → Boundary → Composer → Verifier → widget) to completion **before**
`_dispatch_orchestration_sse` / `_sse_service_reply` are even called. `_sse_service_reply`
(`app.py:433`) then builds the **entire** `out` payload via `finalize_ask` — still before the SSE
generator (`_gen()`, `app.py:473`) is defined. Only after all of that does `app.response_class(_gen(), ...)`
get constructed and returned; Flask/Werkzeug does not send **any** HTTP response bytes to the client
until this view function returns. The generator itself then yields `typing` → `ui` → `done` with no real
gap (PERF-0 seam audit Finding 2, still true). **Net: today's `time_to_first_server_event` ≈
`total_ms`** — there is no separate "early" signal at all.

## Chain under audit (unchanged from PERF-0)

```text
Ingress → Turn Planner → Medical Boundary → Composer → Semantic Verifier → Runtime/presentation/widget
```

## PERF-0 marks available to reuse (no new tracking system)

`core/turn_timing.py` already provides, per request (`request.ctx["turn_timing"]`):

- `stage_start(name)` / `stage_end(name, status, llm_used, reason)` — called at exactly six seams:
  `ingress` (`orchestration/pre_resolver_turn.py`), `planner` (`orchestration/planner_turn.py`,
  skipped via `orchestration/typed_ui_planner_turn.py`), `boundary`, `composer`,
  `verifier_deterministic`, `verifier_semantic` (all four in `core/target_runtime_turn.py` +
  `core/target_composer_executor.py` + `core/target_response_verifier.py`).
- `stage_skipped(name, reason)` — explicit label for bypassed stages (structured `clinic_contact` /
  `service_availability`, `typed_ui`, `terminal_before_composer`, `deterministic_block`).
- Point marks: `verified_answer_ready`, `first_meaningful_text`, `widget_payload_ready`,
  `first_server_event`, `request_complete`, `orchestrate_done`.

**PERF-1 must drive its status text from these same calls (or from a thin notification hook added at
the exact same call sites), not from a second parallel classifier.** This is the binding design
constraint from the milestone brief and from PERF-0's own Rule 6 ("не создавай параллельную систему
логирования").

## Client readiness (confirmed, no client blocker)

`static/widget/api.js` `streamAsk()` already reads the SSE body via `res.body.getReader()` +
`TextDecoder` in a `while (true) { await reader.read(); ... }` loop — a true incremental streaming
reader, **not** the buffering `EventSource` API. It already dispatches on `event: <name>` and silently
ignores any event name it doesn't recognize in its `if/else if` chain (no `else` branch, no throw). This
means: (a) the client can already render bytes as they arrive — no client-side blocker to early SSE
delivery; (b) a **new** SSE event name introduced in Phase 2 (e.g. `event: status`) is automatically
backward-compatible — old client builds that don't know about it simply skip it, satisfying acceptance
row 16 without any compatibility shim.

## Runtime/session/context seams that constrain the mechanism

1. **Flask request context is thread-local (contextvar-based).** `request.ctx` (a plain dict) is read
   and written pervasively — by grep, dozens of call sites across `orchestration/*.py` and
   `core/target_runtime_*.py` — including every PERF-0 stage mark, `_bind_chat_ctx`, effective-scope
   publishing, and UI-action binding. None of this is safe to access from a different OS thread unless
   that thread pushes its **own** request context first.
2. **`session.py` client-pack binding is thread-local, not request-scoped.** `_tls = threading.local()`
   (`session.py:27`); `bind_session_client(client_id)` sets `_tls.client_id`, consumed by
   `_session_pack_id()` to pick the per-client SQLite file. `bind_client_id` (called once, on the
   request-handling thread, via `_bind_chat_ctx`) is what sets this today. **A worker thread that never
   calls `bind_session_client` itself will silently fall back to the `"demo"` pack** (`_session_pack_id`'s
   `or "demo"`) — a real correctness hazard, not a hypothetical one, for any non-demo client.
3. **Session writes happen exactly once per turn today**, inside `finalize_ask` (`mem_add_user`/
   `mem_add_bot`) and inside `run_target_fullcontext_runtime_turn` (`write_target_runtime_session_after_materialized`).
   Whichever mechanism PERF-1 picks, the actual orchestration call must still happen **exactly once**;
   no retry-on-disconnect, no duplicate invocation.
2. **No existing cancellation primitive for outbound LLM HTTP calls.** `llm.py`'s `chat_completions_create`
   is a plain blocking call (`openai` SDK). There is no way to safely abort it mid-flight from another
   thread without risking a corrupt/partial provider-side call. Any design must treat "client
   disconnected" as **stop relaying to the socket**, never as "cancel the in-flight turn".
3. **Precedent for background work already exists in this codebase**: `pg_sink.py` runs a singleton
   background thread draining a bounded `queue.Queue` (`_QUEUE_MAX`, drop-with-warning on overflow) for
   async Postgres writes. This establishes queue+thread as an accepted pattern here — but it is a
   **long-lived shared worker** (fire-and-forget producer), structurally different from what PERF-1
   needs (a **per-turn** worker whose result the request must wait for before closing the stream).
4. **Dev-only deployment** (`app.run(host="0.0.0.0", port=PORT, debug=False)`, no `threaded=` override,
   no Procfile/gunicorn found). Per-request background threads work regardless of the dev server's own
   connection-concurrency mode; LLM calls are I/O-bound and release the GIL while blocked, so a
   generator thread can keep servicing the socket while a worker thread blocks on network I/O.

## Mechanism comparison (A/B/C/D)

### A — Run orchestration inside the SSE generator, single thread

The generator function itself calls `run_pre_resolver_turn` → `try_run_typed_ui_planner_turn`/
`run_planner_turn` → `orchestrate_target_fullcontext_turn`, with a `yield status(...)` inserted **between**
these three top-level calls (mirroring `_orchestrate_ask_turn`'s existing structure). Same thread
throughout, same live `request.ctx`, zero context-transfer risk.

- **Can it emit events during a blocking LLM call?** Only *between* top-level calls, not *during* one.
  Since `orchestrate_target_fullcontext_turn` internally bundles Boundary + Composer + Verifier + widget
  as one opaque call from the SSE view's perspective, this gives at most **3 coarse checkpoints**
  (before pre-resolver, before planner, before the target call) — it cannot honestly say "Boundary done,
  Composer started" without either (a) restructuring the pipeline's call chain into `yield from`-chained
  generators at every one of ~6 stack frames (`run_target_fullcontext_runtime_turn` →
  `run_target_offline_boundary_enforced_fullcontext_response` →
  `run_target_offline_turn_frame_bound_response` → `run_target_offline_verified_response_pipeline` →
  `execute_target_composer` / `verify_target_composed_response`), which **breaks the return-value
  contract** every existing caller and PERF-0 test depends on (`run_target_fullcontext_runtime_turn`
  today returns a `TargetRuntimeTurnOutcome`; dozens of tests call it directly and assert on the return
  value) — or (b) accept 3-phase coarseness.
- **Flask context:** trivially safe — same thread, same context, nothing to transfer.
- **contextvars:** none needed.
- **Session/DB:** trivially safe — single call path, same as today.
- **Disconnect cleanup:** trivial — generator just stops; no background work outlives the request.
- **Complexity/risk:** **lowest**. But: coarse-grained status cannot honestly satisfy "status исходят
  из реального состояния pipeline" at PERF-0's actual stage granularity, and cannot cleanly avoid a
  false status for a *skipped* stage that lives inside the opaque `orchestrate_target_fullcontext_turn`
  call (e.g. distinguishing "Boundary skipped because clinic_contact" from "Boundary ran" is invisible
  at this call boundary) without duplicating stage-skip logic at the SSE-view level — which **is** a
  second, cruder classification system, the exact thing the milestone forbids.

### B — Background worker thread + bounded status queue + guaranteed-delivery result

The SSE view starts a **per-turn** daemon worker thread that runs the *unmodified* `_orchestrate_ask_turn`
call. Before starting it, the view explicitly re-binds what the worker needs (constructs its own
`app.test_request_context()`-equivalent seeded with `sid`/`client_id`/`request_id`, and calls
`bind_client_id`/`bind_session_client` again on that thread — exactly the same calls the main thread
already makes, just repeated deliberately, not shared). PERF-0's `stage_start`/`stage_end`/
`stage_skipped` call sites gain a thin, optional notification hook (reusing the exact same call sites,
not a new classifier) that pushes a status event onto a **bounded** `queue.Queue` (`put_nowait`,
drop-oldest-or-drop-new on overflow — status is best-effort/coalescable). The final `AskOrchestrationResult`
is delivered through a **separate, guaranteed** channel (e.g. the worker thread's return value captured
via a plain `threading.Event` + result slot, or `concurrent.futures.ThreadPoolExecutor.submit` returning
a `Future`) — never through the lossy bounded queue, so a full status queue can never drop the actual
answer. The main thread's generator loop: `while not done: drain queue (non-blocking, short poll) → yield
any status events → check if future is resolved → when resolved, yield `ui` + `done` once and stop`.

- **Can it emit events during a blocking LLM call?** **Yes** — this is the only option that can, because
  the notification hook fires from *whatever* stack depth `stage_start`/`stage_end` already lives at,
  independent of how deep that is, and the *main* thread is free to poll-and-yield while the *worker*
  thread is parked in a blocking network call (GIL is released during I/O wait).
- **Flask context:** worker thread must **not** touch the live `request` proxy at all — it constructs
  its **own** fresh request context (the same `app.test_request_context()` pattern already used
  throughout this repo's own test suite for exactly this reason) seeded with only the plain values it
  needs. This is the documented-safe Flask pattern for background work, not a workaround.
- **contextvars:** the worker's fresh context is self-contained; nothing crosses the thread boundary
  except plain data (`sid`, `client_id`, `q`, `data` dict, `request_id`) captured **before** the thread
  starts.
- **Session/DB:** orchestration still runs exactly once, on the worker thread; `bind_session_client`
  must be called explicitly on that thread (documented requirement, not optional) or session writes
  silently target the wrong SQLite file for non-demo clients — this is the one real, must-not-skip
  correctness rule for Phase 2.
- **Disconnect cleanup:** client disconnect only stops the **main** thread from relaying further status
  to a closed socket (detected when a `yield` raises, or by checking the WSGI environ before each yield);
  it must **not** attempt to cancel the worker (no safe cancellation primitive exists for the in-flight
  LLM call, per seam finding above) — the worker finishes its single write normally, in the background,
  as a daemon thread, and is never restarted or duplicated. No second turn, no re-invocation.
- **Complexity/risk:** **medium** — real, but bounded and precedented (`pg_sink.py` already uses
  queue+thread in this codebase); every risk above has one specific, named mitigation, not a vague
  "be careful".

### C — Callback/event sink without a dedicated worker thread

Register a callback in `request.ctx` that `stage_start`/`stage_skipped` invoke synchronously (reusing
the exact call sites, same as B). Without a second thread, nothing can flush bytes to the socket while
the *same* thread is blocked inside a deep call several stack frames below the SSE generator — a `yield`
can only suspend execution at the frame that contains the `yield` statement itself; Python generators
cannot "yield out of" a plain function several calls deep unless every intermediate frame is also a
generator using `yield from` (i.e., collapses into Option A's generator-chain variant, with the same
call-contract-breaking cost) or unless the callback hands off to a second thread (i.e., collapses into
Option B). **C is not independently viable at fine granularity** — it is either A wearing a different
name (coarse, safe, ~3 phases) or B in disguise (fine-grained, needs a thread). Documented here for
completeness, not carried forward as a distinct target.

### D — Other minimal variant considered and rejected

`asyncio`/`async def` view functions: would require the WSGI app and every blocking call in the chain
(`requests`/`openai` SDK calls, `sqlite3`) to be async-compatible, or wrapped in `run_in_executor` —
functionally equivalent to Option B (a background thread pool) but with a much larger blast radius
(Flask's sync app object, every synchronous call site, the whole test suite's synchronous fixtures) for
no additional capability over B. Rejected as strictly more invasive than B for the same result.

## Chosen target mechanism: **B — background worker thread + bounded status queue + guaranteed result**

Selected because it is the only option that can honestly derive status from PERF-0's **actual**
per-stage marks (Ingress/Planner/Boundary/Composer/verifier_deterministic/verifier_semantic — including
correct skip semantics for structured `clinic_contact`/`service_availability` and `typed_ui`) without
inventing a second, cruder classification layer, and without breaking the return-value contract that
`run_target_fullcontext_runtime_turn` and its callers (including all PERF-0 tests) rely on today. Its
real risks (context propagation, thread-local session binding, bounded-queue drops, disconnect handling)
each have one concrete, named, already-idiomatic-to-this-codebase mitigation — not a workaround.

## Normative behavior (binding for Phase 2 implementation)

1. `/ask` is untouched — it keeps calling `_orchestrate_ask_turn` synchronously, on the request thread,
   exactly as today.
2. `/ask/stream` starts a **per-turn** daemon worker thread that runs the **unmodified**
   `_orchestrate_ask_turn(data)` inside its own freshly-constructed request context (seeded with
   `sid`/`client_id`/`request_id`/`data`), and calls `bind_client_id`/`bind_session_client` on that
   thread before touching session state.
3. The worker's `AskOrchestrationResult` is delivered through a guaranteed channel (never the bounded
   status queue).
4. PERF-0's `stage_start`/`stage_end`/`stage_skipped` gain an optional notification hook at the same
   call sites; the hook pushes onto a **bounded** `queue.Queue` owned by the request, best-effort
   (`put_nowait`, drop-on-full with a counted warning, mirroring `pg_sink.py`'s existing drop policy).
5. Status text is derived from stage name + status via one small, fixed mapping table (e.g. `ingress`/
   `planner` running → "Проверяю вопрос"; `boundary`/`composer` running → "Ищу информацию в материалах
   клиники"; `verifier_*` running → "Готовлю ответ") — never from `reason`, `q`, or any free text.
   **Skipped stages never produce a status event** (`stage_skipped` must not enqueue).
6. No duplicate consecutive status text is sent (coalesce identical adjacent phrases).
7. The generator polls the queue with a short bounded timeout, yields any pending status, checks
   whether the worker's result is ready; once ready, yields exactly one `event: ui` (byte-identical
   payload shape to `/ask`'s JSON body) then exactly one `event: done`, then returns.
8. On client disconnect (detected before/at a yield), the generator stops yielding and returns; the
   worker thread is **not** cancelled and completes its single write normally in the background.
9. On any exception inside the worker (including the existing `TargetResponseVerificationError` /
   generic pipeline-failure paths already handled by `materialize_target_error_payload`), the worker
   still produces a normal `AskOrchestrationResult` (error payload) through the **same** guaranteed
   result channel — the generator's `ui`/`done` sequence is identical to the happy path; only the
   payload content differs (already true today).
10. `time_to_first_server_event` in PERF-0's trace must be re-anchored to the actual first `yield` in
    the generator (today it is a same-instant proxy mark next to `request_complete`); `request_complete`
    stays anchored to the real end of the generator.

## Acceptance matrix (Phase 2 implementation — minimum coverage)

| # | Scenario | Expected |
|---|---|---|
| 1 | Fake Planner takes >300ms | first SSE status event arrives before Planner completes |
| 2 | Any normal turn | measurable pause between first status and final `ui` in test (not back-to-back) |
| 3 | Generic FullContext | statuses appear in a valid order (checking → searching → composing subset), no invalid transitions |
| 4 | Structured contacts (`clinic_contact`) | no Boundary/Composer/Verifier status shown (they are `skipped`, not silently "running") |
| 5 | Structured service availability | same short-path guarantee as #4 |
| 6 | Typed UI click (governed ref) | no Planner status shown (`stage_skipped("planner", reason="typed_ui")` must not enqueue) |
| 7 | Terminal / fallback | stream still ends with exactly one `ui` + one `done` |
| 8 | Pipeline exception | stream still ends with exactly one `ui` (error payload) + one `done`, no hang |
| 9 | `/ask` vs `/ask/stream` | identical `ui` payload content for the same fixture |
| 10 | Any turn | exactly one `done`, and it is the last event |
| 11 | Any turn | exactly one session write (no duplicate `mem_add_user`/`mem_add_bot`/`write_target_runtime_session_after_materialized`) |
| 12 | Simulated client disconnect mid-stream | no second orchestration call, no duplicate session write, worker thread completes and exits cleanly (no leak) |
| 13 | Any status event | no question text, answer text, or PII in `data:` payload |
| 14 | Any turn | PERF-0's `stages`/marks in the logged `turn_complete` trace still present and correct |
| 15 | Any turn | LLM call count identical to `/ask` for the same fixture (no extra classification call for status text) |
| 16 | Old client build (no `event: status` handling) | still receives and renders `ui`/`done` correctly, ignoring unknown event names |

## Implementation allowlist (Phase 2 — blocked until owner GO)

| File | Action |
|---|---|
| `app.py` | UPDATE — `/ask/stream` gains the worker-thread + queue + generator loop; `/ask` untouched |
| `core/turn_timing.py` | UPDATE — optional notification hook at `stage_start`/`stage_end`/`stage_skipped` (bounded queue push), additive only |
| `orchestration/pre_resolver_turn.py` | UPDATE only if the worker-thread request-context seeding needs a narrow hook here (no stage logic change) |
| `session.py` | **KEEP unchanged** — reuse existing `bind_client_id`/`bind_session_client`, call them explicitly from the worker thread |
| `static/widget/api.js` | UPDATE — recognize new `event: status` (additive, backward compatible; old builds ignore it) |
| `static/widget/widget.js` | UPDATE — render status phrase text (additive; no change to existing `typing`/`ui`/`done` handling) |
| `tests/test_final_early_sse_status_streaming_implementation.py` | CREATE — acceptance matrix above |

**KEEP unchanged:** `/ask` route and behavior; Composer/Boundary/Verifier policy, prompts, and call
count; routing/threshold logic; session write call sites and count; widget payload content/CTA/buttons;
`core/stream_answer_text.py` (still untouched, unwired — unrelated to status streaming).

## PRE-CODE checker

`tests/test_final_early_sse_status_streaming_governance.py` — asserts this seam audit exists and covers
the required sections (mechanism comparison A/B/C/D, chosen mechanism B, normative behavior, seam
findings on Flask context / thread-local session binding / cancellation), asserts `TASK.md` has the
PERF-1 governance section with baseline `228ee28`, asserts `docs/FLAGS_AND_STATUS.md` and
`docs/STRANGLER_ROADMAP.md` reference the milestone, and asserts the forbidden-in-Phase-1 list is
documented verbatim.

## Forbidden in governance commit (Phase 1)

- Product implementation of any kind (no worker thread, no queue, no generator restructuring committed
  in this phase)
- Composer token streaming / `text_delta`
- Any change to answers, routes, or prompts
- Any change to LLM call count
- Boundary bypass
- Verifier changes
- Provider prewarm / answer cache
- Ingress + Planner merge
- UX redesign
- LIVE / LLM / E2E eval runs
- Frozen artifact / hash changes
- TSC-C / TSC-D
- Fixing unrelated pre-existing test debt

## Test commands (governance)

```powershell
python -m pytest tests/test_final_early_sse_status_streaming_governance.py -q
git diff --check
```

## STOP

After PRE-CODE ✅ — **STOP**. Implementation only after a separate owner GO.
