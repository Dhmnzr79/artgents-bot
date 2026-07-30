# PERF-4 — development-time live provider calls — forensic audit

**Дата аудита:** 2026-07-30
**Метод:** read-only. No test re-run, no server start, no widget request. Evidence is exclusively the
existing local structured log `logs/demo-app.jsonl` (JSONL, `logger.info(..., extra={"extra_data": ...})`
via `logging_setup.emit_bot_event`/`log_json`), read and aggregated offline.

## Verdict

**A real, live provider call occurred — not merely a risk.** During PERF-4 Phase 2 implementation and
debugging earlier today (2026-07-30), the speculative Ingress/Planner fork mechanism made numerous
genuine HTTP round-trips to the real DashScope-compatible provider, before the safe-by-default
(`PLANNER_SPECULATION_CAPACITY=0`) fix and the five test corrections were in place. This corrects and
supersedes the "NO LIVE confirmation" statement in TASK.md's PERF-4 Phase 2 completion record, which was
**incorrect** — see the correction applied to TASK.md alongside this audit.

## Evidence (counts, from `logs/demo-app.jsonl`, scoped to `ts` prefix `2026-07-30`)

| Signal | Count | First | Last |
|---|---|---|---|
| `bot_event`/`llm_usage`, `call_type=turn_planner_plan` (Planner role) | **104** | 09:58:44.921Z | 11:52:34.104Z |
| `bot_event`/`llm_usage`, `call_type=ingress_classify` (Ingress role) | **126** | 09:58:41.146Z | 12:05:09.159Z |
| **Total confirmed real provider HTTP round-trips today** | **230** | 09:58:41.146Z | 12:05:09.159Z |

Each of the 230 rows carries genuine, internally-consistent `prompt_tokens`/`completion_tokens`/
`total_tokens`/`cached_tokens`/`estimated_usd` values (not placeholders) — the unambiguous signature of a
real completed provider response, not a stub or a preflight check that stopped before transport.

### Requested / observed model (role-scoped; no mismatch recorded)

| Role | Model | Notes |
|---|---|---|
| Planner (`turn_planner_plan`) | `qwen3.7-plus` | 100% of the 104 rows; no `model_mismatch`/drift event recorded for this role today |
| Ingress (`ingress_classify`) | `qwen3.6-flash` | 100% of the 126 rows; no `model_mismatch`/drift event recorded for this role today |

No `requested_model != observed_model` divergence appears in the log for either role today — every
recorded `model` field is the one configured/expected value.

### Aggregate cost and token exposure (Planner role; Ingress role does not log `total_tokens`)

- Planner (`turn_planner_plan`): **249,761 total tokens**, **≈$0.094** estimated cost across 104 calls.
- Ingress (`ingress_classify`): **≈$0.042** estimated cost across 126 calls (per-call token breakdown not
  captured by that log line's schema).
- **Combined estimated cost today: ≈$0.137.**

### PERF-4 speculation-lifecycle counters (same log, same day — cross-reference, not separate evidence)

| Event | Count |
|---|---|
| `planner_speculation_submitted` | 211 |
| `planner_speculation_published` | 64 |
| `planner_speculation_discarded` | 57 |
| `planner_parallel_overload_sequential` | 66 |
| `planner_compute_exception` | 9 |
| `turn_planner_failed` (pre-existing Planner fallback path) | 16 |
| `ingress_classify_failed` (pre-existing Ingress fallback path) | 1 |

These 211 `planner_speculation_submitted` events confirm the speculative fork itself fired repeatedly
during development (both from the author's own deliberate, faked test scenarios in this session and,
before the fixes landed, from the unintended leak into pre-existing tests that left `classify_ingress`
unmocked) — consistent with, and the direct mechanism behind, the 104 real `turn_planner_plan` calls
above. The 104/126 real-usage counts are the authoritative "did a network request actually happen"
evidence; the submitted/published/discarded counters are corroborating context, not a separate claim.

## What is explicitly NOT in this audit (by design, per instruction)

No prompt text, answer/completion content, `sid`, contact values, or secrets are reproduced here or were
read from response bodies beyond `.model`/`.usage` (the same discipline `core/planner_compute_executor.py`
and `core/turn_planner_llm.py` already apply at the source — this audit adds no new read of response
content, it only aggregates already-anonymized usage metadata that was already logged).

## Scope note

Two `turn_planner_plan` rows from 2026-07-28 (unrelated to today's PERF-4 activation work — from earlier,
separate sessions) also exist in the log but are outside this audit's scope and are not counted above.
Postgres event forwarding (`pg_sink`) may hold a mirror of the same `bot_event` rows if enabled for the
`demo` client pack; this audit did not query any Postgres store — the JSONL log above is sufficient,
authoritative evidence for the verdict and was the only artifact read.

## Immutable record

This file is committed as append-only evidence and must not be edited to change the counts above; a
follow-up correction, if ever needed, must be a new dated section appended below, never an edit to the
numbers already recorded.
