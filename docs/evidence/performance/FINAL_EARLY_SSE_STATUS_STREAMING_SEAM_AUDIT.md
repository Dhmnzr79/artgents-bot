# FINAL_EARLY_SSE_STATUS_STREAMING (PERF-1) — seam audit

**Дата:** 2026-07-28 (governance correction @ `254d859`)
**Baseline:** `codex/stage-a` @ `228ee28`
**Режим:** governance / docs / tests only · **NO product implementation / NO Composer token streaming /
NO text_delta / NO answer/route/prompt change / NO LLM-call-count change / NO Boundary bypass / NO
Verifier change / NO prewarm/cache / NO Ingress+Planner merge / NO UX redesign / NO LIVE / NO LLM / NO
E2E / NO frozen artifacts / NO TSC-C / NO TSC-D**
**Owner GO:** Phase 1 governance only; implementation blocked until PRE-CODE ✅ + separate owner GO

## Governance correction (this revision, @ `254d859`)

The initial revision of this audit named `app.test_request_context()` as the worker thread's Flask
context mechanism. The owner correctly rejected this: `test_request_context()` is a **testing utility**
(name, semantics, and internal `EnvironBuilder`-fabricated environ all signal "for tests"), not a
production-safe primitive, and it does not by itself address who owns `request.ctx` concurrently. This
revision replaces that design with a corrected worker-execution-context design (new section below),
strengthens disconnect/cleanup/overload normative rules, and corrects the `pg_sink.py` precedent framing
(fire-and-forget logging is not equivalent proof of safety for session-write-dependent orchestration).
No other section's conclusions changed: the chosen outer mechanism is still **B**.

## Preflight

| Check | Result |
|---|---|
| Branch `codex/stage-a` | ✅ |
| `HEAD` == `origin/codex/stage-a` @ `228ee28` (original) / `254d859` (correction baseline) | ✅ |
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
3. **Precedent for background work already exists in this codebase, but it is not sufficient proof of
   safety on its own.** `pg_sink.py` runs a singleton background thread draining a bounded `queue.Queue`
   (`_QUEUE_MAX`, drop-with-warning on overflow) for async Postgres writes. This shows queue+thread is an
   architecturally familiar shape here — **that is all it shows.** `pg_sink`'s worker never touches
   `flask.request`, never needs a request context, never does a SQLite session write, and does not care
   whether the original HTTP request is still alive (fire-and-forget logging of already-serialized
   dicts). PERF-1's worker is materially different on every one of those axes: it performs a real
   session write, depends on `request.ctx` resolving correctly for unmodified pipeline code, and its
   caller (the SSE generator) must wait for its result before closing the stream. `pg_sink.py` is cited
   here only as evidence that background threads are not a foreign concept in this codebase — it is
   **not** cited as evidence that PERF-1's specific context-propagation and session-binding problems are
   already solved. Those are solved by the dedicated design in "Worker execution context" below,
   independent of `pg_sink.py`.
4. **A real, already-in-product precedent for cross-thread state without sharing `request.ctx` exists:**
   `core/target_composer_action_context.py` uses module-level `contextvars.ContextVar` (not
   `request.ctx`) with a strict `bind_...() -> tokens` / `reset_...(tokens)` pair, called from
   `core/target_runtime_turn.py` as `tokens = bind_pending_ui_actions_for_composer(...)` /
   `finally: reset_pending_ui_actions_for_composer(tokens)`. This is the exact discipline (explicit
   bind, paired `finally` reset, `ContextVar` rather than a shared dict) the corrected worker-context
   design below generalizes for `client_id`, session binding, and the status event sink — it is a
   reuse of an existing in-repo pattern, not a new one invented for PERF-1.
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
- **Flask context:** worker thread must **not** touch the live `request` proxy, and must **not** use
  `app.test_request_context()` (testing utility, rejected — see "Worker execution context" below for the
  corrected, production-safe mechanism).
- **contextvars:** the worker's context is self-contained; nothing crosses the thread boundary except
  plain data (`sid`, `client_id`, `q`, `data` dict, `request_id`, `nav_ref`) captured **before** the
  thread starts, plus explicit `contextvars.ContextVar` binds performed **by the worker itself** at
  start and reset in `finally` — see "Worker execution context" below.
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

## Worker execution context: production-safe design (governance correction)

Mechanism B's remaining open question is *how the worker thread gets a working `flask.request.ctx`
without sharing the live one or using test tooling*. Three named options, compared:

### Rejected outright — `app.test_request_context()`

Rejected by the owner and confirmed on inspection: its name, its internal use of
`werkzeug.test.EnvironBuilder` to fabricate a fake environ, and its purpose (documented Flask testing
helper) all signal "for tests," not "production background execution." Using it in product code is
misleading to future readers even where it happens to work. **Not carried forward.**

### Option 1 — `flask.copy_current_request_context`

A real, non-test Flask API for propagating a request context into a callback invoked from another
thread. On inspection of its mechanics: `RequestContext.copy()` (which it calls internally) constructs a
new `RequestContext` but passes `request=self.request` — **the same underlying `Request` object
instance**, and therefore the same `request.ctx` dict object, is shared by reference between the
original context and the copy. This directly reintroduces the exact hazard the owner flagged in point 6
("generator and worker must not simultaneously mutate one `request.ctx`") — copying the context does
**not** give the worker an independent `request.ctx`, it gives it a second handle onto the *same* dict.
**Rejected as the sole mechanism** for this reason, though the underlying idea (a real, non-test Flask
API) is correct and informs Option 2.

### Option 2 — a separate, production request context

Flask's actual production entry point for constructing a `RequestContext` is `Flask.request_context(environ)`
— the exact method `wsgi_app()` itself calls for every real incoming HTTP request; there is nothing
test-flavored about the method itself. The gap is only that it needs a WSGI-shaped `environ` dict, which
normally comes from a live socket. **Chosen approach:** the worker constructs a minimal, hand-built
`environ` dict directly (a plain dict literal with only the small set of keys `werkzeug.wrappers.Request`
actually requires to construct — `REQUEST_METHOD`, `SERVER_NAME`, `SERVER_PORT`, `SCRIPT_NAME`,
`PATH_INFO`, `wsgi.input`, `wsgi.errors`, `wsgi.version`, `wsgi.url_scheme`, `wsgi.multithread`,
`wsgi.multiprocess`, `wsgi.run_once`) — **no `werkzeug.test`/`EnvironBuilder` import, no fabricated
request semantics beyond what's structurally required to construct a `Request` object.** This gives the
worker a genuinely **independent** `RequestContext` (a brand-new `request.ctx` dict, never shared with
the live one), pushed via `app.request_context(environ)` and popped in `finally` — satisfying every
unmodified pipeline call site that does `from flask import request; request.ctx...` without rewriting
any of them, and without sharing mutable state with the generator thread (resolves point 6).

### Option 3 — explicit immutable execution context, no Flask request dependency

Carry every cross-cutting value (`client_id`, `sid`, `request_id`, turn-timing event sink) through
`contextvars.ContextVar` instead of `request.ctx`, generalizing the **already-shipped** in-product
pattern in `core/target_composer_action_context.py` (`ContextVar` + `bind_...() -> tokens` /
`reset_...(tokens)` in `finally`, invoked today from `core/target_runtime_turn.py` around Composer
action binding). This is the cleanest option **for values that matter operationally**, but on its own it
does not solve `flask.request` resolution — dozens of existing call sites (every PERF-0 stage mark,
effective-scope publishing, UI-action reads) still do `from flask import request; request.ctx...` and
would raise `RuntimeError: Working outside of request context` with no `RequestContext` active at all.
Fully removing that dependency would mean rewriting every one of those call sites to read from
`ContextVar`s instead of `request.ctx` — a real, large, invasive refactor, explicitly **not** minimal for
the current architecture and explicitly out of scope (no product code this phase; not "minimal" even in
Phase 2).

### Chosen combination: Option 2 (Flask-proxy compatibility shell) + Option 3's discipline (operational state)

The worker thread pushes an **independent** `RequestContext` via `app.request_context(environ)` with a
hand-built minimal environ (Option 2) purely so unmodified pipeline code's `request.ctx` reads/writes
keep working without touching those call sites. Populating that fresh `request.ctx` and everything that
actually matters for correctness — `client_id`, `sid` binding, the status-event sink — happens through
explicit `contextvars.ContextVar` bind/reset pairs **generalizing** `core/target_composer_action_context.py`'s
existing pattern (new `ContextVar`s for `client_id` and the status sink; `session.py`'s
`bind_session_client` called explicitly, matching its existing thread-local contract). Both halves are
bound at worker start and reset in a single `finally` block — never left dangling on any exit path
(normal return, exception, or disconnect-triggered early generator exit).

This satisfies every point in the governance correction:

- **(1)** No `test_request_context()` anywhere.
- **(2)** All three named options compared, with concrete reasons, not just named and dismissed.
- **(3)** Minimal for current architecture: reuses an existing in-product `ContextVar` pattern instead of
  inventing a new state-passing mechanism; does not rewrite the dozens of existing `request.ctx` call
  sites.
- **(4)** Immutable snapshot (`request_id`, `client_id`, `sid`, parsed `data`, `nav_ref`) captured on the
  **generator's** thread before the worker starts; the worker never reads the live `request` proxy.
- **(5)** Worker explicitly binds and `finally`-clears: the `client_id` `ContextVar`, `session.py`'s
  `bind_session_client` thread-local, and the turn-timing/event-sink `ContextVar` — three distinct,
  named bind/reset pairs, not one bundled blob.
- **(6)** Generator and worker never share one `request.ctx` object — each has its own, independently
  constructed dict (this is precisely what rules out Option 1's `copy_current_request_context`).

## Bounded worker capacity (no unlimited thread-per-request)

A bounded pool (e.g. `concurrent.futures.ThreadPoolExecutor(max_workers=N)`, `N` config-driven, small)
or a counting `threading.Semaphore(N)` gates how many concurrent PERF-1 workers may run. **Overload
behavior:** when capacity is exhausted, `/ask/stream` degrades to **today's synchronous behavior** for
that request (compute the full turn on the request-handling thread, exactly as it does now, then emit
`typing` → `ui` → `done` back-to-back) rather than queueing indefinitely or rejecting the request. This
guarantees `/ask/stream` never behaves worse than it does today, even under load; it only sometimes loses
the early-status benefit.

## Guaranteed delivery of the terminal result (queue cannot lose it)

The bounded status queue is explicitly **best-effort and lossy by design** (status is informational and
coalescable — losing one intermediate "Ищу информацию..." update is harmless). The final result is
**never** put on that queue. It is delivered through a separate, non-lossy channel — a
`concurrent.futures.Future` (or equivalent single-assignment primitive) that the generator polls
alongside its short, non-blocking queue drains, or blocks on with a bounded timeout once no more status
is expected. A single, unambiguous **terminal sentinel** (the future resolving, not a queue item) is what
tells the generator loop to stop draining status and emit `ui` + `done` — this cannot be dropped by queue
overflow because it never enters the queue.

## Normative behavior (binding for Phase 2 implementation)

1. `/ask` is untouched — it keeps calling `_orchestrate_ask_turn` synchronously, on the request thread,
   exactly as today.
2. `/ask/stream` starts a **per-turn** daemon worker thread (subject to the bounded-capacity gate below)
   that runs the **unmodified** `_orchestrate_ask_turn(data)`. Before starting it, the request-handling
   thread captures an **immutable snapshot** (`request_id`, `client_id`, `sid`, parsed `data`, `nav_ref`)
   — plain values only, no Flask proxy, no shared dict. The worker never touches the live `request`.
3. The worker pushes its **own independent** `RequestContext` via `app.request_context(environ)` with a
   hand-built minimal environ (no `test_request_context`, no `werkzeug.test`/`EnvironBuilder`) — see
   "Worker execution context" above — and explicitly binds three `ContextVar`/thread-local pairs from the
   immutable snapshot: `client_id` `ContextVar`, `session.py`'s `bind_session_client` thread-local, and
   the status-event-sink `ContextVar`. All three are reset in one `finally` block that runs on every exit
   path (normal return, exception, or early generator exit on disconnect).
4. The worker's `AskOrchestrationResult` is delivered through a guaranteed, non-lossy channel (a
   `Future`/single-assignment result) — **never** the bounded status queue (see "Guaranteed delivery"
   above).
5. PERF-0's `stage_start`/`stage_end`/`stage_skipped` gain an optional notification hook at the same
   call sites; the hook pushes onto a **bounded** `queue.Queue` owned by the request, best-effort
   (`put_nowait`, drop-on-full with a counted warning). This queue is explicitly lossy for status and
   explicitly never carries the terminal result.
6. Status text is derived from stage name + status via one small, fixed mapping table (e.g. `ingress`/
   `planner` running → "Проверяю вопрос"; `boundary`/`composer` running → "Ищу информацию в материалах
   клиники"; `verifier_*` running → "Готовлю ответ") — never from `reason`, `q`, or any free text.
   **Skipped stages never produce a status event** (`stage_skipped` must not enqueue).
7. No duplicate consecutive status text is sent (coalesce identical adjacent phrases).
8. The generator polls the queue with a short bounded timeout, yields any pending status, checks
   whether the worker's result future is resolved; once resolved, yields exactly one `event: ui`
   (byte-identical payload shape to `/ask`'s JSON body) then exactly one `event: done`, then returns.
   The generator never writes to the worker's `request.ctx`, and the worker never writes to the
   generator's — each owns an independent context (resolves owner point 6).
9. On client disconnect (detected before/at a yield), the generator stops yielding and returns; the
   worker thread is **not** cancelled — there is no safe way to abort an in-flight blocking LLM call —
   and completes its single write normally in the background, then runs its `finally` cleanup exactly
   once. No second turn is started; no retry; no duplicate session write.
10. On any exception inside the worker (including the existing `TargetResponseVerificationError` /
    generic pipeline-failure paths already handled by `materialize_target_error_payload`), the worker
    still produces a normal `AskOrchestrationResult` (error payload) through the **same** guaranteed
    result channel, and its `finally` cleanup still runs — the generator's `ui`/`done` sequence is
    identical to the happy path; only the payload content differs (already true today).
11. Bounded worker capacity: a small, config-driven `N` gates concurrent PERF-1 workers; on exhaustion,
    `/ask/stream` falls back to computing the turn synchronously (today's behavior) for that request —
    never unbounded thread creation, never an indefinite queue.
12. `time_to_first_server_event` in PERF-0's trace must be re-anchored to the actual first `yield` in
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
| 17 | Worker completes normally | `client_id` `ContextVar`, `session.py` thread-local, and event-sink `ContextVar` are all reset (verifiable — not left dangling for the next task on that thread) |
| 18 | Worker raises before completing | same three bindings are still reset (`finally` ran) |
| 19 | Concurrent requests beyond bounded worker capacity `N` | the `N+1`th `/ask/stream` request falls back to synchronous computation (today's behavior), not an unbounded new thread and not a rejected request |
| 20 | Status queue artificially full | terminal `ui`/`done` still delivered (via the guaranteed channel, never dropped by queue overflow) |
| 21 | Generator and worker inspected mid-flight | each holds a distinct `request.ctx` object (`is not`), never the same dict instance |

## Implementation allowlist (Phase 2 — blocked until owner GO)

| File | Action |
|---|---|
| `app.py` | UPDATE — `/ask/stream` gains the bounded-capacity worker-thread + queue + generator loop; `/ask` untouched |
| `core/turn_timing.py` | UPDATE — optional notification hook at `stage_start`/`stage_end`/`stage_skipped` (bounded queue push), additive only |
| `core/target_sse_worker_context.py` | CREATE — new module generalizing `core/target_composer_action_context.py`'s `ContextVar` bind/reset pattern for `client_id` and the status-event sink; owns the worker's `app.request_context(environ)` push/pop and the minimal hand-built environ construction |
| `session.py` | **KEEP unchanged** — reuse existing `bind_client_id`/`bind_session_client`; called explicitly by the new worker-context module, not modified itself |
| `static/widget/api.js` | UPDATE — recognize new `event: status` (additive, backward compatible; old builds ignore it) |
| `static/widget/widget.js` | UPDATE — render status phrase text (additive; no change to existing `typing`/`ui`/`done` handling) |
| `tests/test_final_early_sse_status_streaming_implementation.py` | CREATE — acceptance matrix above |

**KEEP unchanged:** `/ask` route and behavior; Composer/Boundary/Verifier policy, prompts, and call
count; routing/threshold logic; session write call sites and count; widget payload content/CTA/buttons;
`core/stream_answer_text.py` (still untouched, unwired — unrelated to status streaming);
`core/target_composer_action_context.py` (pattern reused/generalized, file itself not modified).
**Forbidden mechanism:** `app.test_request_context()` and `flask.copy_current_request_context` — both
rejected in this audit (testing utility; shared-`request.ctx` hazard, respectively).

## PRE-CODE checker

`tests/test_final_early_sse_status_streaming_governance.py` — asserts this seam audit exists and covers
the required sections (mechanism comparison A/B/C/D, chosen mechanism B, the corrected worker-execution-
context comparison — `copy_current_request_context` / production `request_context()` / explicit
`contextvars` — with `test_request_context()` explicitly rejected, bounded worker capacity, guaranteed
terminal-result delivery, normative behavior, seam findings on Flask context / thread-local session
binding / cancellation / the corrected `pg_sink.py` framing), asserts `TASK.md` has the PERF-1 governance
section with baseline `228ee28`, asserts `docs/FLAGS_AND_STATUS.md` and `docs/STRANGLER_ROADMAP.md`
reference the milestone, and asserts the forbidden-in-Phase-1 list is documented verbatim.

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
