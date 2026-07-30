# FINAL_PARALLEL_INGRESS_PLANNER_LATENCY (PERF-4) — seam audit

**Дата:** 2026-07-30
**Baseline:** `codex/stage-a` @ `61cd93e`
**Режим:** Phase 1 — governance / read-only seam audit / docs / tests only · **NO product
implementation / NO merging Ingress+Planner / NO prompt/model/schema changes / NO removing
Ingress / NO Composer/Verifier/Boundary changes / NO scoped FullContext implementation / NO
streaming text / NO answer-cache/prewarm loops / NO client data/frozen artifacts / NO TSC-C /
NO TSC-D / NO LIVE / NO LLM / NO provider calls**
**Owner GO:** Phase 1 governance only; product implementation (a parallel Ingress/Planner
coordinator) is blocked until PRE-CODE ✅ + a separate, later owner GO — the same two-gate
pattern already used for PERF-3.

## 0. Real-request measurement that motivated this milestone

The most recent real turn ("Что такое костная пластика?") measured: total 18.2s — Ingress
3.4s, Planner 3.8s, Boundary 1.3s, Composer 7.8s, Verifier 1.8s, Composer/Verifier
`cached_tokens=0`. Ingress and Planner run **sequentially** today even though both only need
the same original question — the user waits ≈ 3.4+3.8 = 7.2s before Boundary even starts.
PERF-3's live prewarm attempt did not produce a cache hit on this real request (see §15,
Checkpoint A) — a prompt-cache win is not currently available, so this milestone looks at
**wall-clock overlap** of two independent understanding-layer calls instead.

## 1. Is Ingress really independent of Planner? (question the owner asked to settle first)

**Yes, in the sense that matters for concurrency — but with one asymmetry that decides the
whole design (§4).** Both read the same original question text and both are separate LLM
contracts with independent prompts/models/schemas (never merged — see §12 for why merging is
explicitly rejected). Neither reads the other's output:

- `classify_ingress` (`ingress_gate.py`) takes `(question, client_id, sid)` and returns an
  `IngressRouteResult`. It has no parameter for a Planner result and never imports anything
  from `orchestration/planner_turn.py` or `core/turn_planner_llm.py`.
- `plan_turn_attempt` (`core/turn_planner_llm.py`) takes `(q, sid, client_id)` and returns a
  `PlannerAttempt`. It has no parameter for an Ingress result and never imports anything from
  `ingress_gate.py`.

The one asymmetry: **Ingress's LLM path touches `request.ctx` internally; Planner's compute
does not.** `_call_ingress_llm` (`ingress_gate.py:417-496`) calls
`core.turn_timing.set_flag(...)` and `core.turn_timing.timed_stage("ingress_ms",
accumulate=True)` for its own full-retry accounting (the lite→full catalog retry, §6). Both
write into `request.ctx` via `turn_timing._bucket()`. `plan_turn_attempt` (`core/
turn_planner_llm.py:211-303`) has **no `from flask import request` at all** — it only reads
`build_compact_service_catalog(client_id)`, `allowed_brand_filters(client_id)`,
`load_client_topic_taxonomy(client_id)` (config/catalog reads), `recent_dialog_history(sid)`
(a session **read**, not a write), makes the one LLM call, and writes structured logs
(`log_json`/`log_llm_usage`/`log_llm_error` — confirmed request-context-optional, §7). This is
why the selected design (§4) moves only Planner's compute off the request thread and leaves
Ingress exactly where it is today.

## 2. Full call chain today (sequential, confirmed by reading the code)

`app.py:_orchestrate_ask_turn` (`app.py:304-336`):

1. `run_pre_resolver_turn(...)` (`orchestration/pre_resolver_turn.py`) — client/reset/rate/
   noise, **then, only if `q and not ingress_skip`**, `classify_ingress(...)` synchronously
   (`pre_resolver_turn.py:131-163`), then `handle_flows(...)`, anti-spam burst/soft-redirect
   checks, ref-click handling — returns either an `AskOrchestrationResult` (early exit — no
   Planner ever runs) or an `AskTurnContext` (continue).
2. If an `AskTurnContext` came back: `try_run_typed_ui_planner_turn(...)` (typed UI clicks —
   independent of free-text Planner, confirmed it never calls `run_planner_turn`/
   `plan_turn_attempt`/`publish_planner_attempt_frame`). If it returns non-`None`, **Planner is
   skipped entirely** (`app.py:322-329`).
3. Only if `typed_outcome is None`: `run_planner_turn(...)` (`orchestration/planner_turn.py`)
   — `plan_turn_attempt` (the LLM call), then `publish_planner_attempt_frame`, `request.ctx`
   writes, `record_decision_frame_ctx(None)`, `enqueue_resolver_trace(...)`.
4. `orchestrate_target_fullcontext_turn(...)` — Boundary/Composer/Verifier (unchanged, out of
   scope for this milestone).

**The discard surface is bigger than "Ingress route ≠ normal."** Every one of these, which all
happen strictly after the point Ingress resolves (or is skipped) and strictly before
`run_planner_turn` actually executes, currently means Planner (and its cost) never happens
today, and must equally discard any *speculatively started* Planner compute in the parallel
design:

| # | Discard trigger | Where |
|---|---|---|
| 1 | `ingress_res.route != "normal"` | `pre_resolver_turn.py:150-163` |
| 2 | `handle_flows(...)` returns a flow_result (active lead flow) | `pre_resolver_turn.py:179-193` |
| 3 | Anti-spam message burst → soft redirect | `pre_resolver_turn.py:198-218` |
| 4 | Anti-spam no-intent → soft redirect | `pre_resolver_turn.py:219-238` |
| 5 | Unknown ref → clarify payload (three sub-cases: scope ref, stage ref, generic followup) | `pre_resolver_turn.py:269-339` |
| 6 | Empty `q` after all of the above | `pre_resolver_turn.py:343-354` |
| 7 | `try_run_typed_ui_planner_turn` returns non-`None` | `app.py:317-322` |

Note that trigger 5 (ref-click) structurally **cannot** co-occur with a speculatively-started
Planner under the recommended fork point (§4): `ref` being set forces `ingress_skip=True`
(`pre_resolver_turn.py:125-130`), and the fork point only fires inside the `q and not
ingress_skip` branch — so ref-driven typed-UI turns never start a speculative Planner call in
the first place. Triggers 2/3/4/6/7 remain real discard paths that a speculatively-started
Planner call must tolerate (§9, §13).

## 3. `run_planner_turn`'s own compute/publish boundary (confirmed line-by-line)

`orchestration/planner_turn.py:61-101`:

```
turn_timing.stage_start("planner")                       # request.ctx write
attempt = plan_turn_attempt(q, sid, client_id)            # <-- THE COMPUTE: one LLM call,
                                                           #     zero request.ctx/Flask reads
turn_timing.stage_end("planner", status="completed")      # request.ctx write
publish_planner_attempt_frame(attempt=attempt)            # request.ctx write (runtime frame)
status = get_runtime_turn_frame_status()
request.ctx["turn_planner_used"] = ...                    # request.ctx write
request.ctx["resolver_used"] = False                      # request.ctx write
request.ctx["safety_net_used"] = False                    # request.ctx write
... 
request.ctx["effective_intent"] = str(intent)             # request.ctx write
record_decision_frame_ctx(None)                           # request.ctx write (route_intent/...)
enqueue_resolver_trace(decision=None, ...)                # DURABLE side effect (pg_sink)
```

`publish_planner_attempt_frame` (`core/runtime_turn_frame.py:33-36,98-120`) reads/writes via a
`_ctx()` helper that is **literally `request.ctx`** — i.e. the live Flask request context of
the thread that is handling this HTTP request. `record_decision_frame_ctx`
(`core/metadata_first_observability.py:168-182`) does the same. `enqueue_resolver_trace` — the
concrete callable passed in is `app.py:_enqueue_v5_resolver_trace` (`app.py:62-89`), which reads
`request.ctx.get("request_id"/"sid"/"client_id")` and calls `pg_sink.enqueue_v5_turn_trace(...)`
— a **durable** write (the V5 shadow-eval trace sink), swallowed on exception. This is the
exact kind of durable/request-context side effect the owner's brief said must never fire before
Ingress has resolved the turn as `normal` and no discard trigger (§2) has fired.

**Compute = `plan_turn_attempt(q, sid, client_id)` alone.** Everything else in
`run_planner_turn` is publish, is request.ctx-bound, and must run in the main orchestration
thread, exactly once, only on the path that reaches this call site today.

## 4. Selected concurrency variant

| Variant | Verdict |
|---|---|
| **A** — Ingress in a future, Planner stays in the current thread | **Rejected.** Ingress's LLM path (`_call_ingress_llm`) itself touches `request.ctx` (`set_flag`/`timed_stage` for full-retry accounting, §1/§6) — moving *it* off the request thread would need the same context-independence work §5 gives Planner for free, for no extra latency benefit over moving Planner instead. Larger surface change for the same `max(ingress, planner)` win. |
| **B** — Both in a bounded executor, publish in the main thread | **Rejected.** Same reason as A for the Ingress half; doubles the context-independence surface (both calls would need it) versus moving only the one call (Planner) that already needs none. |
| **C** — Split Planner into pure compute + publish; parallelize only compute | **Selected.** `plan_turn_attempt` already has zero `request.ctx`/Flask dependency (§1, §3) — nothing to refactor there. Ingress stays exactly as it is today, in the main thread, unchanged. Minimal surface: one new fork point, one new join point, zero changes to Ingress, zero changes to Composer/Verifier/Boundary, zero prompt/model/schema changes. |
| **D** — Stay sequential if side effects can't be safely separated | Not needed — §3 shows the split is clean. Kept as the **documented overload/failure fallback** (§9), not the primary design. |

**Selected: C.** Concretely: at the exact point `run_pre_resolver_turn` is about to call
`classify_ingress(...)` for the slow (LLM) path only (§6 — never for a deterministic-rule
hit), submit `plan_turn_attempt(q, sid, client_id)` to a small, dedicated, bounded executor
(§8) and keep going with `classify_ingress(...)` synchronously exactly as today. The resulting
`Future[PlannerAttempt]` (or, under admission overload, `None` — §9) travels through
`AskTurnContext` down to `_orchestrate_ask_turn`. `run_planner_turn` gains an optional
pre-computed-future parameter: if present, it blocks on `future.result(timeout=...)` instead of
calling `plan_turn_attempt` itself, then runs the **exact same, unmodified** publish logic
(`turn_timing.stage_end`, `publish_planner_attempt_frame`, the `request.ctx` writes,
`record_decision_frame_ctx`, `enqueue_resolver_trace`) it runs today. Every discard trigger in
§2's table simply never reaches that call site — the future, if one was started, is dropped
unread; nothing is cancelled (Python's `ThreadPoolExecutor` futures cannot be force-cancelled
once running — §13), the background call is left to finish and its result is garbage-collected
unread, unpublished.

## 5. Why the fork point does not need PERF-1's full independent-RequestContext machinery

PERF-1 (`core/target_sse_worker_context.py`) backgrounds an **entire turn** (Boundary, Composer,
Verifier, session writes, everything) and correctly gives that background thread its own,
fully independent Flask `RequestContext` (`app.request_context(minimal_environ)`, pushed/popped
in `finally`, plus `ContextVar` binding for `client_id` and the status sink) — because the
backgrounded code (`_orchestrate_ask_turn` itself) reads/writes `request.ctx` extensively.
Planner's compute (`plan_turn_attempt`) is narrower: it reads no Flask state at all (§1). It
therefore needs **none** of that machinery — a plain function submitted to a plain
`ThreadPoolExecutor` is sufficient for correctness. What it *does* need, and what PERF-1's
pattern is still the right precedent for, is **log correlation** (§7): without it, the
speculative Planner's own log lines (`turn_planner_llm`, `turn_planner_failed`, the
`llm_usage` `bot_event` for the planner call) lose `request_id` correlation, because
`logging_setup.request_context_defaults()` only pulls `request_id` from a real/bound
`request.ctx`, and a plain worker thread has none at all (not even an independent one). Phase 2
should bind a lightweight `request_id` (and `sid`/`client_id`, already passed as explicit args
to `plan_turn_attempt` and already threaded into its own `log_json`/`log_llm_error` calls) —
either via a small `ContextVar` bound only around the compute call, mirroring
`target_sse_worker_context`'s existing bind/reset-in-`finally` shape, or by extending
`plan_turn_attempt`'s explicit logging call sites to accept a request_id override. This is a
correctness-adjacent observability gap, not a safety hazard — flag it in the Phase 2 allowlist,
don't silently ignore it.

## 6. Where exactly to fork (why "before every `classify_ingress` call" is wrong — Rule 4)

A naive fork point ("start Planner's compute right before calling `classify_ingress`,
unconditionally, whenever `q and not ingress_skip`") would violate the owner's Rule 4
("Deterministic ingress short-circuit не запускает speculative Planner"): `classify_ingress`
(`ingress_gate.py:499-549`) checks, **before ever calling the LLM**, in order: `skip` (forced
normal), message length < 2 (forced normal), `match_clinic_policy_key` (rule hit →
`not_offered_policy`), `_ingress_deterministic_normal` (rule hit → normal, content-prior-
experience/tooth-loss). All three are in-process, no network, sub-millisecond. If Planner's
compute is forked *before* these checks, a policy-rule hit or a deterministic-normal hit would
still pay for a full Planner LLM call with zero latency benefit (there is no slow Ingress call
to overlap with) — pure waste, and the exact thing Rule 4 forbids.

The correct seam: fork Planner's compute **only at the point `classify_ingress` is actually
about to call `_call_ingress_llm`** — i.e. after its own existing deterministic checks have
already run and found nothing. This reuses `classify_ingress`'s own existing rule-matching
functions (`match_clinic_policy_key`, `_ingress_deterministic_normal`) as the gating signal —
it is **not** a second router, because it calls the same functions `classify_ingress` already
calls, from the one place that already calls them, and does not reimplement or duplicate any
routing decision. Two shapes are available for Phase 2 to choose between (governance does not
pick one — that's an implementation-time call, both keep the "no second router" property):

- (a) `classify_ingress` gains an optional hook parameter invoked exactly at the point it is
  about to call `_call_ingress_llm`, letting the caller start Planner's compute at that instant; or
- (b) `run_pre_resolver_turn` calls the same two deterministic pre-check functions itself
  (imported, not reimplemented) immediately before its existing `classify_ingress(...)` call,
  forks Planner's compute only if both return no decision, then calls `classify_ingress(...)`
  unchanged (which harmlessly re-runs the same two sub-millisecond checks internally).

## 7. Logging thread-safety (confirmed safe to call from a worker thread)

`logging_setup.log_json` / `emit_bot_event` / `log_llm_usage` all funnel through Python's
standard `logging` module (`logger.info(...)`, `logger.exception(...)`), which is documented
thread-safe (its `Handler.emit` is internally lock-protected) — concurrent Ingress-thread and
Planner-worker-thread log calls will not corrupt the JSONL log file or interleave partial
lines. `request_context_defaults()` (`logging_setup.py:153-171`) guards with
`has_request_context()` inside a `try/except`, so calling any of these logging helpers from a
plain worker thread with **no** Flask context at all is safe — it degrades to omitting
`request_id`/`sid`/`client_id`/`path` from that specific log line (§5's observability gap),
never raises.

## 8. Provider/backend concurrency

`llm.py` builds **one module-level `chat_client = OpenAI(**_chat_client_kwargs)`**, already
shared across the whole running Flask process today. Any production WSGI deployment already
relies on this client tolerating concurrent `.chat.completions.create()` calls from multiple
threads handling multiple simultaneous HTTP requests — that is the existing, already-accepted
assumption this app runs on. Two concurrent calls *for the same turn* (Ingress + Planner) place
no new demand on the client beyond what already happens across two different simultaneous
requests today; the OpenAI SDK's `httpx`-based transport pools connections and is built for
concurrent use. `INGRESS_CLASSIFY_MODEL` (`QWEN_FLASH_MODEL` by default) and
`TURN_PLANNER_LLM_MODEL` (`QWEN_PLUS_MODEL` by default) are **different models** — so the two
concurrent calls for one turn land on separate provider-side model deployments/rate-limit
buckets in the common case, reducing contention further versus two calls to the same model.
Retry count is unchanged either way (`retry=0` semantics for both calls stay exactly as they
are today — Rule 15); timeout is unchanged (`LLM_REQUEST_TIMEOUT_SEC` for Planner,
`_LLM_TIMEOUT`/`LLM_REQUEST_TIMEOUT_SEC` for Ingress, both already independent per-call
timeouts today). Model provenance (`requested`/`configured`/`observed`) is unaffected — neither
call's model selection depends on the other's timing.

## 9. Bounded concurrency, admission, and the overload fallback (Rules 9, 10)

PERF-1 already established, and this milestone should reuse the *pattern* (not the *instance*
— §10) of: a small `ThreadPoolExecutor` **plus** a non-blocking `threading.Semaphore` used as
explicit admission control (`app.py:441-451`, `_sse_worker_admission.acquire(blocking=False)`)
— never relying on a thread pool's own (effectively unbounded) internal work queue as the
admission gate. Applied here: a dedicated, small, bounded executor for Planner-compute
submissions; if admission is refused (pool at capacity), `run_pre_resolver_turn` does **not**
fork anything — it falls straight through to calling `classify_ingress(...)` and, later,
`run_planner_turn` calls `plan_turn_attempt` itself, synchronously, exactly as it does today
(Variant D as the overload fallback, never a user-visible error — Rule 10).

## 10. The nested-executor deadlock hazard (Rule 11) — the most important hazard in this audit

`_orchestrate_ask_turn` (which would contain the new fork/join code) is **already** invoked
*from inside* a PERF-1 SSE worker thread when the request came in via `/ask/stream`
(`app.py:_run_sse_worker_turn` → `_orchestrate_ask_turn`, running on one of
`_sse_worker_executor`'s `_SSE_WORKER_CAPACITY` (default 8) threads). If the new
Planner-compute executor were the **same pool object** as `_sse_worker_executor`, then under
load — all 8 SSE workers busy, each one independently reaching the fork point and submitting a
nested Planner-compute task to that same, already-exhausted pool — every worker thread would
block waiting for a free worker slot that can never open up (all slots are themselves blocked
waiting on their own nested submission). This is a genuine deadlock, not a theoretical one:
`ThreadPoolExecutor.submit(...).result()` from *inside* one of that same pool's own worker
threads, at full capacity, hangs forever. **The Planner-compute executor must be a separate,
independently-bounded pool, never `_sse_worker_executor` itself**, and must never be submitted
to from inside its own worker threads either. A synchronous request via `/ask` (main Flask
request thread) and a streamed request via `/ask/stream` (one of the 8 SSE worker threads) both
end up calling the same fork/join code — as long as the Planner-compute pool is its own,
separate object with its own bounded admission + synchronous fallback (§9), both call sites are
safe: each outer thread (main or SSE-worker) submits at most one inner task and blocks on it
with the existing LLM timeout as an upper bound, never on the outer pool's own capacity.

## 11. PERF-0 / PERF-1 timing semantics under overlap (Rules 18, 19)

`turn_timing.stage_start`/`stage_end` (`core/turn_timing.py:59-110`) record **absolute**
`time.monotonic()` timestamps per stage (`{name}_start`, `{name}_end`) and compute each stage's
own `duration_ms` as its own `end - start` — this is correct and unaffected by other stages
overlapping in wall-clock time; it was never a shared/global clock. What changes under the
parallel design is: **`stage_start("planner")`/`stage_end("planner", ...)` must be called from
the main thread, at the moment of fork/join, not from inside the worker thread** — both
because `_bucket()` needs `request.ctx` (unavailable in a plain worker thread, §1) and because
`stage_start` calls `_notify_status_sink` (`core/turn_timing.py:65-85`), which reads a
`ContextVar` (`core.target_sse_worker_context.current_status_sink`) that is **not**
automatically inherited by a freshly spawned `ThreadPoolExecutor` thread (Python `ContextVar`s
only propagate via `contextvars.copy_context()`/`asyncio`, never to a plain new `Thread`). If
`stage_start("planner")` were called from inside the worker thread, PERF-1's SSE status hook
would silently stop firing for the planner stage under `/ask/stream` — **keeping
`stage_start`/`stage_end` calls in the main thread, at fork-time and join-time respectively,
avoids this entirely** without needing to propagate the `ContextVar` into the worker at all.
`summary_for_turn_complete`'s `{key}_since_start_ms` fields (`turn_timing.py:139-174`), which
some historical eval contracts may read, continue to reflect real wall-clock offsets from
`turn_t0_monotonic` — overlapping `ingress_start`..`ingress_end` and `planner_start`..
`planner_end` spans are an honest, correct representation of what actually happened
concurrently, not a bug to paper over. PERF-1's own status-phrase table
(`app.py:_SSE_STAGE_STATUS_PHRASES`) already maps both `"ingress"` and `"planner"` to the same
user-visible phrase ("Проверяю вопрос") — so even if both stages' start events fire close
together in wall-clock time under the parallel design, the emitted status text does not
flap between two different phrases (Rule 18 satisfied by an existing design choice, not a new
one).

## 12. Why this is not a merge and not a workaround

Ingress and Planner remain **two separate contracts** end-to-end: separate system prompts,
separate models (`INGRESS_CLASSIFY_MODEL` vs `TURN_PLANNER_LLM_MODEL`), separate response
schemas (`IngressRouteResult` vs `PlannerAttempt`/`TurnFrame`), separate call sites, separate
failure/fallback semantics (§13), separate log event names. Nothing about Rule 1 ("Ingress и
Planner остаются двумя независимыми contracts") is touched — no shared prompt, no combined
schema, no single call answering both questions. What changes is purely *when in wall-clock
time* Planner's independent compute is allowed to start relative to Ingress's independent
compute — a scheduling change, not a semantic merge. It is also not a workaround/hack in the
sense of papering over a slow call: it does not change what either call computes, does not
skip either call for an accepted normal turn (Rule 16 — still exactly 2 LLM calls for the
understanding layer), and does not touch Composer/Verifier/Boundary at all.

## 13. Failure / fallback semantics (Rule 7) and cancellation (Rule 14)

Today: Ingress backend failure → `classify_ingress` catches the exception and returns a
`fallback` route=`normal`, confidence 0 (`ingress_gate.py:524-545`) — **unchanged** by this
design, since Ingress's call site and implementation are untouched. Planner backend failure →
`plan_turn_attempt` catches the exception and returns `PlannerAttempt(frame=None,
status="not_available")` via `_not_available_attempt()` (`core/turn_planner_llm.py:260-262`) —
**unchanged in kind**; under the parallel design this exception is caught **inside the worker
thread** (the `try/except` is already inside `plan_turn_attempt` itself, so it never propagates
out of the future — `future.result()` on the main thread receives the already-degraded
`PlannerAttempt`, never raises). Both-fail: independent, unrelated to each other, each already
degrades on its own (no new combined-failure state to invent). Timeout: each call already has
its own independent timeout today (`LLM_REQUEST_TIMEOUT_SEC` / `_LLM_TIMEOUT`) — the join point
should bound `future.result(timeout=...)` to (at most) the same existing Planner timeout so a
hung Planner compute cannot indefinitely block the main thread past what a synchronous
`plan_turn_attempt` call would already have bounded it to today.

**Cancellation (Rule 14):** Python's `concurrent.futures.ThreadPoolExecutor` cannot forcibly
cancel a future that has already started running — `future.cancel()` only succeeds before the
worker has picked it up. This design never relies on cancellation for correctness: a discarded
future (§2, §4) is simply never read (`.result()` never called on it on that code path) — its
underlying call runs to completion in the background and is garbage-collected once done; it is
never retried, and its result is never published twice, because "publish" only ever happens
once, at the one call site in `run_planner_turn`, on the one code path that reaches it.

## 14. Session / durable-write count (Rule 20)

`enqueue_resolver_trace` (the durable, shadow-eval trace write) is called exactly once per
turn today, only inside `run_planner_turn`, only on the path that reaches it. Under the
parallel design this does not change — it remains part of the publish step (§3, §4), called
from the main thread, exactly once, only when Planner's result is actually published. No new
session write is introduced by forking the compute; the compute itself (`plan_turn_attempt`)
performs no session writes (only a `recent_dialog_history(sid)` **read** — confirmed, §1).

## 15. Checkpoint A — PERF-3 measurement outcome (owner-requested capture)

Per the owner's PERF-3 post-live audit
(`docs/evidence/performance/PERF3_PROMPT_CACHE_PREWARM_LIVE_ATTEMPT_AUDIT.md`) and TASK.md's
PERF-3 completion record:

- The single authorized live prewarm attempt (`perf3-demo-2026-07-30-01`) completed: 2/2 calls,
  both models matched exactly, `cached_tokens=0` on both (expected — first-ever warm of that
  exact fingerprint, nothing previously cached to hit).
- The **subsequent real production-style request** referenced in §0 above (the "костная
  пластика" turn) shows Composer and Verifier `cached_tokens=0` as well — **the practical
  cache-hit benefit PERF-3 was built to test has not been demonstrated on a real turn.**
- Automatic startup prewarm (Option C, from the PERF-3 seam audit) **remains deferred and is
  not recommended** by this milestone either — nothing in this audit changes that
  recommendation; this milestone's latency target (Ingress/Planner overlap) is independent of
  prompt-cache warmth.
- The PERF-3 CLI (`scripts/prewarm_prompt_cache.py`) and its immutable evidence
  (`.prewarm_ledger/attempts/perf3-demo-2026-07-30-01.json`,
  `docs/evidence/performance/PERF3_PROMPT_CACHE_PREWARM_LIVE_ATTEMPT_AUDIT.md`) are **not**
  removed or modified by this milestone. No new prewarm loop, automatic or manual, is started
  by this milestone.

### Observability gap noted, not fixed in Phase 1

PERF-3's offline fake-provider tests (`tests/test_final_provider_prompt_cache_prewarm_
implementation.py`) write real `bot_event`/`llm_usage` log rows into the **shared**
`logs/demo-app.jsonl` (via the real `logging_setup.log_llm_usage`/`emit_bot_event` — only the
provider transport is faked, the logging path is not). This means the shared log file mixes
real production-style events with test-fixture events, with no field distinguishing them. This
audit does **not** fix that in Phase 1 (out of allowlist — no product/test-infra changes here).
It is classified as **test-log-isolation debt**, to be added to a **future** implementation
allowlist only if a concrete harm is demonstrated (e.g. an eval or dashboard query counting
fixture-generated `llm_usage` rows as real traffic) — not spontaneously "fixed" as a drive-by
in this or the PERF-4 milestone.

## 16. Speculative-Planner cost/frequency estimate (Rule 17 — from existing anonymized logs, no LIVE)

Counted offline from the existing local `logs/demo-app.jsonl` (+ rotated `.1`/`.5`) —
dev/test-fixture traffic (local Windows dev box, mostly synthetic eval runs; see
[[local-dev-test-data]] — not real customer PII, and not necessarily representative of
production reject-rate mix):

```
total ingress_gate events logged: 1373
  route=normal:               1372  (99.93%)
  route=service_not_offered:     1  (0.07%)
```

Within this sample, a naive "fork before `classify_ingress`, unconditionally" design would
waste a Planner call on ≈0.07% of turns purely from Ingress rejects in this fixture set — but
§6 already rules that design out on separate (Rule 4) grounds regardless of how small this
number is. Under the **selected** fork point (§6 — only after Ingress's own deterministic
pre-checks find nothing, i.e. only immediately before the real LLM call), the residual waste
is: (a) the small residual reject rate among turns that *do* reach the LLM ingress path
specifically (a subset of the 0.07%, likely smaller — deterministic rejects are excluded by
construction), plus (b) the discard triggers 2/3/4/6/7 in §2's table (lead-flow/anti-spam/
empty-q/typed-UI), which are not separately instrumented in the current logs and cannot be
sized from this sample alone. **Recommendation for the owner:** treat the speculative-Planner
waste rate as small-but-not-precisely-known from this fixture set, and have Phase 2's
implementation add a dedicated, cheap counter (e.g. a `bot_event` at the discard point) so the
real waste rate can be measured directly on live traffic after rollout, rather than estimating
it once and trusting the estimate indefinitely.

## 17. Implementation allowlist (Phase 2 — NOT started in this Phase 1 milestone)

| Path | Change |
|---|---|
| `orchestration/pre_resolver_turn.py` | Fork `plan_turn_attempt` compute at the seam in §6, thread the future through `AskTurnContext` |
| `orchestration/context.py` (`AskTurnContext`) | Add an optional field carrying the in-flight future (or `None` under overload/skip) |
| `orchestration/planner_turn.py` (`run_planner_turn`) | Accept an optional pre-computed future; `future.result(timeout=...)` instead of calling `plan_turn_attempt` when present; publish logic unchanged |
| A new small module (name TBD in Phase 2, e.g. `core/planner_compute_executor.py`) | The dedicated, separately-bounded `ThreadPoolExecutor` + non-blocking admission `Semaphore` (§9, §10) — never `_sse_worker_executor` |
| `core/turn_planner_llm.py` / `plan_turn_attempt`'s logging call sites | Thread an explicit `request_id` (or a small bind/reset `ContextVar`, §5) through so speculative-compute log lines stay correlated |
| Explicitly NOT in this allowlist | `ingress_gate.py` (no change — Ingress stays exactly as-is); `core/target_sse_worker_context.py` / `_sse_worker_executor` (no reuse, no modification); Composer/Verifier/Boundary; any prompt/model/schema; `app.py` route handlers beyond wiring the new future through unchanged call sites |

## 18. Acceptance matrix (Phase 2 — governance defines it now, does not implement it)

| # | Scenario |
|---|---|
| 1 | Delayed Ingress 3s + delayed Planner 4s → understanding-layer wall time ≈4s (`max`), not ≈7s (`sum`) |
| 2 | Ingress completes before Planner — join waits only on Planner's remaining time |
| 3 | Planner completes before Ingress — join waits only on Ingress's remaining time |
| 4 | Deterministic-rule Ingress hit (policy_key match) → no speculative Planner call fired |
| 5 | Deterministic-rule Ingress hit (`_ingress_deterministic_normal`) → no speculative Planner call fired |
| 6 | LLM-path Ingress, route=normal → Planner published exactly once |
| 7 | LLM-path Ingress, route≠normal (reject) → Planner result discarded, never published |
| 8 | Rejected request does not call `publish_planner_attempt_frame` |
| 9 | Rejected request does not call `enqueue_resolver_trace` |
| 10 | Rejected request does not write session/durable state from the discarded Planner result |
| 11 | Ingress backend failure (LLM path) → existing fallback route=normal, confidence 0 unchanged |
| 12 | Planner backend failure → existing `not_available`/`PlannerAttempt(frame=None)` unchanged, caught inside the worker, never raises out of the future |
| 13 | Both Ingress and Planner fail independently → each degrades on its own, no new combined-failure state |
| 14 | Ingress LLM call times out → existing per-call timeout semantics unchanged |
| 15 | Planner LLM call times out → `future.result(timeout=...)` bounded by the existing Planner timeout, never blocks past it |
| 16 | Planner-compute executor at capacity → synchronous fallback (Variant D), `plan_turn_attempt` called inline exactly as today, no user-visible error |
| 17 | Planner-compute executor capacity is explicit and bounded (admission `Semaphore`, not the pool's internal queue) |
| 18 | No nested-submit deadlock: Planner-compute executor is a separate pool object from `_sse_worker_executor`, verified by identity, not just by behavior |
| 19 | `/ask` (main request thread) reaching the fork/join code behaves identically to `/ask/stream` (SSE worker thread) reaching it |
| 20 | Typed UI scope/stage ref clicks unchanged (ref click ⇒ `ingress_skip=True` ⇒ no speculative Planner fork at all) |
| 21 | Contacts / service-availability / lead / situation / reset paths unchanged (none of them reach the fork point differently than today) |
| 22 | Ordinary FAQ (no ref, no lead context) — accepted normal turn, 2 LLM calls, unchanged outputs |
| 23 | Exact service price question — accepted normal turn, unchanged outputs |
| 24 | Medical/uncertain question still passes through Boundary after the (now-overlapped) understanding layer, unchanged Boundary behavior |
| 25 | `/ask` and `/ask/stream` produce the same final `ui` payload for the same input |
| 26 | PERF-0 stage marks: `ingress_start`/`ingress_end` and `planner_start`/`planner_end` may overlap in wall-clock time; each stage's own `duration_ms` is still individually correct (§11) |
| 27 | PERF-1 SSE status sequence stays stable — no flapping between two different phrases from overlapping stage_start calls (§11 — both stages already share one phrase) |
| 28 | Provider call count for an accepted normal turn's understanding layer stays exactly 2 (1 Ingress + 1 Planner) — Rule 16 |
| 29 | Speculative-Planner cost is counted (a dedicated discard-path counter/event) for rejected/discarded turns, not silently absorbed |
| 30 | Offline tests exercise all of the above with **zero** real network/provider calls (fakes/stubs only) |
| 31 | No two threads ever read or write the same `request.ctx` dict — the worker thread touches nothing Flask-shaped at all |
| 32 | Publish (`publish_planner_attempt_frame` + the `request.ctx` writes + `enqueue_resolver_trace`) happens exactly once per accepted, non-discarded turn — never zero, never twice |

## 19. PRE-CODE summary

- Governance-only Phase 1: this seam audit, `TASK.md` normative design, one new governance
  checker, and minimal doc syncs (`docs/FLAGS_AND_STATUS.md`, `docs/STRANGLER_ROADMAP.md`). No
  product code changed.
- No merging of Ingress and Planner (§12) — two contracts, two prompts, two models, two
  schemas, unchanged.
- No prompt/model/schema changes anywhere.
- No side-effectful `run_planner_turn` moved into a child thread wholesale — only the pure
  `plan_turn_attempt` compute (§3, §4).
- Compute-before-publish design confirmed clean by direct code reading, not assumed (§1, §3).
- Bounded concurrency via a dedicated, separately-bounded executor + explicit non-blocking
  admission semaphore (§9), reusing PERF-1's *pattern*, never PERF-1's *instance* (§10).
- Sequential overload fallback (Variant D) is the documented degrade path, not an afterthought
  (§9).
- No `request.ctx` sharing between threads at any point (§1, §5, §11).
- Ingress reject discards Planner; so does every other pre-Planner short-circuit in the current
  sequential flow (§2's full table, not just Ingress reject).
- No publish/session/durable side effects occur before Ingress has resolved the turn as normal
  and no discard trigger has fired (§3, §4, §14).
- PERF-0 overlap semantics addressed directly: per-stage durations stay correct under overlap;
  wall-time summaries must use `max`-style reasoning, not naive summation (§11).
- PERF-1 integration addressed directly: separate executor (§10), `ContextVar` propagation
  hazard identified and avoided by keeping `stage_start`/`stage_end` in the main thread (§11).
- Exact Phase 2 implementation allowlist enumerated (§17) — narrow, five items, explicit
  exclusions.
- The product parallel coordinator does not exist yet — nothing in `orchestration/`, `core/`,
  or `app.py` has been modified by this milestone.
