# FINAL_PROVIDER_PROMPT_CACHE_PREWARM (PERF-3) — seam audit

**Дата:** 2026-07-29
**Baseline:** `codex/stage-a` @ `897cdb7`
**Режим:** governance / docs / tests only · **NO product implementation / NO provider calls / NO LIVE /
NO LLM / NO Composer/Verifier prompt change / NO answer-cache / NO streaming text / NO Boundary changes /
NO Ingress+Planner merge / NO client data/frozen artifacts / NO TSC-C / NO TSC-D**
**Owner GO:** Phase 1 governance only; implementation blocked until PRE-CODE ✅ + separate owner GO, and
even after implementation lands, first real activation against the provider requires its own separate
LIVE/LLM owner permission (see §8) — the same two-gate pattern already used elsewhere in this codebase
for other live-provider milestones.

## Governing principle (binding, restated)

**Do not implement prewarm until it is proven that the warming request produces the exact same cache
key/prefix that a real later Composer or Verifier call would use.** This audit's job in Phase 1 is to
prove — from code, not from a live experiment — that a prewarm call CAN be built to send byte-identical
leading bytes to what production Composer/Verifier calls send. It is **not** this phase's job to prove the
provider actually returns a cache hit for that prefix (that requires a live measurement, which this phase
forbids) — that empirical proof is deferred to Phase 2's own cold/warm instrumentation, itself gated behind
a separate LIVE/LLM permission before ever running for real (§8, §9).

## 1. Producer/consumer map

```text
Composer:
  core/target_composer_executor.py: _invocation() [389]
    → TargetComposerInvocation(system_policy=TARGET_COMPOSER_SYSTEM_POLICY [388],
                                cached_full_context=cached_full_context.corpus_text,
                                response_directives_json=..., primary_evidence_json=...,
                                governed_action_context_json=..., user_message=...)
  core/target_runtime_llm_backends.py: TargetRuntimeLiveComposerBackend.generate() [72-97]
    → build_composer_sdk_messages(invocation)  [core/target_runtime_llm_messages.py:43-60]
    → chat_completions_create(model=target_fullcontext_composer_model(), messages=[...], timeout=20s)
    → log_llm_usage(..., call_type="target_fullcontext_runtime_composer")  [backends.py:91,103]

Semantic Verifier:
  core/target_response_verifier.py: _semantic_invocation() [594-625]
    → TargetSemanticVerifierInvocation(system_policy=TARGET_SEMANTIC_VERIFIER_SYSTEM_POLICY [37-44],
                                        cached_full_context=cached_full_context.corpus_text, ...)
  core/target_runtime_llm_backends.py: TargetRuntimeLiveSemanticBackend.assess() [120-169]
    → build_verifier_sdk_messages(invocation)  [core/target_runtime_llm_messages.py:63-77]
    → chat_completions_create(model=target_fullcontext_verifier_model(), messages=[...], timeout=20s)
    → log_llm_usage(..., call_type="target_fullcontext_runtime_verifier")  [backends.py:139,162]

Static corpus source (shared by both):
  core/target_cached_full_context.py: build_target_cached_full_context(md_root) [79-104]
    → TargetCachedFullContext(corpus_text, document_count, document_paths, sha256)  [contracts/target_cached_full_context.py:8-15]
  core/target_runtime_client_context.py: load_target_runtime_client_context(client_id) [154-163]
    → process-level cache: _CONTEXT_CACHE: dict[str, TargetRuntimeClientContext] = {}  [line 37]
    → built ONCE per client_id per process (lazy, on first use), never rebuilt unless
      clear_target_runtime_client_context_cache() is called — and that helper is called
      ONLY from tests/evals (11 files), never from application/route code [target_runtime_client_context.py:166-170]

Provider client (shared singleton, both stages):
  llm.py:33-37 — chat_client = OpenAI(**_chat_client_kwargs); client = chat_client
    (constructed once at module import — object construction only, NOT a network call)
  llm.py:60-63 — chat_completions_create(*, model, **kwargs) wraps chat_client.chat.completions.create(...)
  Provider: OpenAI-compatible SDK pointed at DashScope/Qwen (config.py:11-18); models are plain
    env-configurable strings (config.py:26-28, `QWEN_PLUS_MODEL = "qwen3.7-plus"`), not aliases
    documented anywhere in this repo as pinned-vs-rolling (§18 unknown, flagged not invented).

Usage/observability (shared, reused, not re-implemented — see §9):
  logging_setup.py:272-288 — log_llm_usage(logger, resp, *, call_type: str, model: str | None = None,
    extra_details: dict | None = None) — reads usage.prompt_tokens_details.cached_tokens via
    _cached_tokens_from_usage_obj() [logging_setup.py:238-248], includes it in the emitted `llm_usage`
    event only when not None.
```

## 2. Exact current Composer message prefix

Two messages, built by `build_composer_sdk_messages` (`core/target_runtime_llm_messages.py:43-60`):

```text
[0] role=system, content = TARGET_COMPOSER_SYSTEM_POLICY   (core/target_composer_executor.py:37-47)
    — literal string constant, 3,611 characters, no .format()/interpolation applied anywhere.

[1] role=user, content = _COMPOSER_USER_TEMPLATE.format(...)  (core/target_runtime_llm_messages.py:10-20)
    STATIC leading segment (identical for every user/turn/session of this client_id, in this exact order):
      "Compose the patient-facing answer using the inputs below.\n\n"
      "Return strict JSON only: {\"answer\":\"<text>\",\"source_identity\":{\"primary_content_ref\":"
      "\"<md or null>\",\"used_content_refs\":[\"<md filenames>\"]}}\n\n"
      "CACHED_FULL_CONTEXT:\n"
      + corpus_text                                          ← ends the static prefix
    DYNAMIC tail (begins immediately after corpus_text, varies per turn):
      "\n\nRESPONSE_DIRECTIVES_JSON:\n{response_directives_json}\n\n"
      "GOVERNED_ACTION_CONTEXT_JSON:\n{governed_action_context_json}\n\n"
      "PRIMARY_EVIDENCE_JSON:\n{primary_evidence_json}\n\n"
      "USER_MESSAGE:\n{user_message}"
```

`corpus_text` itself (`core/target_cached_full_context.py:79-104`) is built deterministically: every `*.md`
under `md_root`, sorted by canonical relative POSIX path, each wrapped
`---BEGIN DOC:{path}---\n{content}\n---END DOC:{path}---`, joined with `"\n"` — no session state, user
identity, or date/time interpolated. For `clients/demo/md/` (55 files): **~102,489 characters** of corpus
text. Combined with the system policy: **~106,000 characters (~26,500 tokens)** of byte-stable static
prefix per client_id, versus an estimated **1–5 KB** of dynamic per-turn tail — the static prefix
dominates total prompt size by roughly 20–100×, which is exactly the size profile prefix-caching
economics are built for, IF the prefix is truly reused byte-for-byte across calls.

## 3. Exact current Semantic Verifier message prefix — and why it needs its own namespace

Two messages, built by `build_verifier_sdk_messages` (`core/target_runtime_llm_messages.py:63-77`):

```text
[0] role=system, content = TARGET_SEMANTIC_VERIFIER_SYSTEM_POLICY  (core/target_response_verifier.py:37-44)
    — a completely separate string constant from Composer's; different subject matter
    (issue-classification rules: unsupported_clinic_claim / personal_medical_conclusion /
    material_external_medical_claim / minor_external_detail), different JSON output shape.

[1] role=user, content = _VERIFIER_USER_TEMPLATE.format(...)  (core/target_runtime_llm_messages.py:22-32)
    STATIC leading segment:
      "Assess the candidate answer using the inputs below.\n\n"
      "CACHED_FULL_CONTEXT:\n"
      + corpus_text                                          ← same corpus_text object, byte-identical
    DYNAMIC tail: RESPONSE_SPEC_JSON / PRIMARY_EVIDENCE_JSON / CANDIDATE_TEXT (per-turn).
```

**Confirmed empirically, not assumed: Composer and Verifier do NOT share a reusable cache prefix,
despite sharing byte-identical `corpus_text`.** Both message arrays diverge starting at `message[0]`
(different system policy text) and diverge again at the very start of `message[1]` (`"Compose the
patient-facing answer..."` vs `"Assess the candidate answer..."`, plus Composer's extra
`"Return strict JSON only: ..."` block that appears *before* `CACHED_FULL_CONTEXT:` and Verifier does not
have). Provider prefix-caching matches from the *start* of the request; since the very first bytes differ,
a prewarm of Composer's prefix cannot produce a cache hit for Verifier's later call, or vice versa — **two
independent namespaces are required, confirming rule 13 as a proven fact for this codebase, not merely a
cautious default.**

## 4. Static/dynamic boundary (summary table)

| Content | Composer | Verifier | Static? |
|---|---|---|---|
| System policy text | `TARGET_COMPOSER_SYSTEM_POLICY` | `TARGET_SEMANTIC_VERIFIER_SYSTEM_POLICY` | Static, but role-specific (no shared text) |
| User-message preamble | `"Compose the patient-facing answer..."` + `"Return strict JSON only:..."` | `"Assess the candidate answer..."` | Static, role-specific |
| `CACHED_FULL_CONTEXT:\n` + corpus_text | same corpus object | same corpus object | Static, per-`client_id`, process-lifetime-stable |
| Everything after corpus_text | directives/action/evidence/user_message | spec/evidence/candidate_text | Dynamic, per-turn |
| Model string | `target_fullcontext_composer_model()` | `target_fullcontext_verifier_model()` | Static per process/env, role-specific |

**No PII, session state, or user text of any kind appears anywhere in the static portion** — confirmed by
construction (`corpus_text` is pure file content; the preambles are fixed literals) — satisfying rule 5
trivially for the prewarm design, provided the prewarm implementation only ever sends the static portion
plus a fixed, non-PII placeholder for the dynamic tail's required template fields (§7).

## 5. Cache-key / fingerprint design (local bookkeeping only — not sent to the provider)

**Important distinction:** the fingerprint below is a *local* construct our own code uses to decide "have I
already warmed this exact prefix recently, should I bother sending it again." It is never transmitted to
the provider — the provider's own cache matching (whatever it is; unconfirmed, §8) is presumably purely
byte-content-based on the request it actually receives.

No existing single fingerprint covers "everything that determines this static prefix's bytes." What
already exists: `TargetCachedFullContext.sha256` (`contracts/target_cached_full_context.py:15`) — SHA-256
of `corpus_text` only — and `TargetRuntimeClientContext.cache_key` (`core/target_runtime_client_context.py:73-75`,
`f"{self.client_id}:{self.cached_full_context.sha256}"`) — the closest existing precedent, but it doesn't
cover the system policy text, the template wording, or the model string. **Nothing in this codebase
versions `TARGET_COMPOSER_SYSTEM_POLICY`, `TARGET_SEMANTIC_VERIFIER_SYSTEM_POLICY`, or the message
templates** (confirmed by grep for `POLICY_VERSION`/`policy_version` — no matches).

**Designed fingerprint (Phase 2, not built in this governance phase):**

```text
TargetPromptCacheFingerprint = sha256(
    client_id
    + "|" + role                          # "composer" | "verifier" — literal, never a third value
    + "|" + model                         # the exact model string passed to chat_completions_create
    + "|" + corpus_sha256                 # TargetCachedFullContext.sha256 — already exists, reused verbatim
    + "|" + sha256(system_policy_text)    # hash of the LIVE string constant at prewarm time — self-updating;
                                           # if the policy text changes for ANY reason, this changes too,
                                           # without needing a developer to remember to bump a version int
    + "|" + sha256(preamble_template_text)  # same self-updating principle for the static preamble text
    + "|" + str(MESSAGE_SERIALIZATION_VERSION)  # a small manually-bumped int (mirrors the existing
                                           # BOT_EVENTS_SCHEMA_VERSION pattern, logging_setup.py:27) —
                                           # catches STRUCTURAL changes (field order, message count,
                                           # role list) that content-hashing the template STRING alone
                                           # would not catch if the assembly *code* changes without the
                                           # template *text* changing
)
```

Hashing the live string content (rather than requiring a manually-maintained policy version) means the
fingerprint is self-invalidating for the two most likely real-world change vectors (editing the policy
prose, editing the corpus) without relying on developer discipline to remember a version bump — while the
explicit `MESSAGE_SERIALIZATION_VERSION` int is the deliberate, rule-18-compliant escape hatch for the one
class of change that content-hashing cannot catch on its own (restructuring the assembly code itself).

## 6. Invalidation table

| Component change | Fingerprint changes? | Mechanism |
|---|---|---|
| `clients/{id}/md/*.md` content edited | Yes | `corpus_sha256` changes |
| `TARGET_COMPOSER_SYSTEM_POLICY` text edited | Yes (Composer only) | `sha256(system_policy_text)` changes |
| `TARGET_SEMANTIC_VERIFIER_SYSTEM_POLICY` text edited | Yes (Verifier only) | same, role-scoped |
| `_COMPOSER_USER_TEMPLATE` / `_VERIFIER_USER_TEMPLATE` preamble wording edited | Yes | `sha256(preamble_template_text)` changes |
| Message-list structure changed (field order, message count, role list) without template text changing | **Only if a developer manually bumps `MESSAGE_SERIALIZATION_VERSION`** | explicit int; documented as a required manual step in the Phase 2 allowlist, not automatic |
| `TARGET_FULLCONTEXT_COMPOSER_MODEL` / `_VERIFIER_MODEL` env var changed | Yes | `model` string changes |
| `client_id` changes | Yes | different fingerprint entirely — separate namespace by construction |
| Composer vs Verifier | Always different | `role` literal differs; §3 proves no shared prefix regardless |
| Process restart with unchanged files | **No** | fingerprint is deterministic over content, not over process identity — this is intentional, not a gap |

## 7. What a prewarm call would actually send

Reusing `build_composer_sdk_messages`/`build_verifier_sdk_messages` **verbatim, unmodified** (never
hand-rolling a parallel prefix string) is the only way to *guarantee* byte-identical bytes to what a real
Composer/Verifier call sends — this is the core of "proving the same cache key/prefix," per the governing
principle. Since provider prefix-caching (whatever the actual provider mechanism is) matches from the
*start* of the request, the dynamic tail's exact content does not need to be real: a prewarm call can
supply a fixed, static, non-PII placeholder for `response_directives_json`/`primary_evidence_json`/
`governed_action_context_json`/`user_message` (e.g., empty JSON objects and an empty string) built through
the *same* `TargetComposerInvocation`/`TargetSemanticVerifierInvocation` dataclasses and the *same*
`build_*_sdk_messages` functions — never inventing a second message-assembly code path. This automatically
satisfies rule 5 (no user text/SID/session/PII/phone — the placeholder is a fixed constant, never derived
from any real request) and rule 6 (only the static approved prefix is meaningfully "warmed"; the
placeholder tail is not content anyone cares about caching).

## 8. What the provider actually caches, and what remains genuinely unknown

`cached_tokens` (`usage.prompt_tokens_details.cached_tokens`, read at `logging_setup.py:238-248`) has
already been observed in real production usage logs for this exact message shape, per the owner's own
brief — **without any deliberate prewarm mechanism existing today.** This is strong evidence the
DashScope/Qwen-compatible endpoint already performs *some* form of automatic, implicit prefix caching for
repeated identical prompt prefixes across ordinary consecutive real turns. `core/target_cached_full_context.py`'s
own docstring (lines 17-18) already anticipated this exact gate: *"This module prepares a deterministic
provider prompt prefix candidate. Provider-side prompt caching is a separate future live integration gate
and is **not** implemented here."*

**What this audit can prove from code alone (Phase 1, no live calls):** that a prewarm call built via §7
sends byte-identical leading bytes to a real later call, for a provably-static prefix (§2-§4), scoped to
correct per-role/per-client namespaces (§3, §5).

**What this audit explicitly cannot prove without a live measurement, and does not invent an answer for
(rule 18):**
- The provider's cache TTL — undocumented anywhere in this repo or in any comment/config found. Could be
  seconds, minutes, or longer. Treated as **unknown**, not assumed short or long.
- Whether the provider's implicit caching applies uniformly to *any* two calls sharing a prefix regardless
  of time gap between them (as opposed to only very-close-in-time calls, e.g. within one demo session)
  — unconfirmed.
- Whether the exact model string configured (`"qwen3.7-plus"`) is a stable pinned snapshot or could be
  silently re-aliased by the provider over time — no in-repo documentation either way (a sibling agent's
  finding, not guessed here).
- Whether a deliberate prewarm call, sent from a context with no subsequent real user activity for some
  time, would still be warm by the time real traffic arrives — this is precisely what Phase 2's own
  cold-vs-warm duration/`cached_tokens` comparison is designed to measure empirically, under a **separate,
  explicit LIVE/LLM owner permission**, matching this codebase's own established pattern (e.g. the A9 and
  S66 milestones in `docs/STRANGLER_ROADMAP.md` both gate their first live run behind a distinct owner
  decision even after implementation is otherwise complete).

## 9. Deployment / reloader / multi-worker audit

- **Deployment today is single-process:** `Dockerfile:10` and `start.sh` both run `gunicorn -w 1 -b
  0.0.0.0:8000 app:app` — `start.sh`'s own comment states this is deliberate ("SQLite session storage is
  single-writer oriented. Keep one worker to avoid cross-worker session inconsistencies"). No `Procfile`,
  no `--threads`, no `workers=` overrides found anywhere.
- **`debug=False` today, no reloader:** `app.py:922`, the only live `app.run(` call, passes `debug=False`.
  Flask's dev reloader (which would double-fire startup code via a reloader child process) is **not**
  active in the current deployment.
- **No `WERKZEUG_RUN_MAIN` guard exists anywhere in this repo** (confirmed by grep) — there is no existing
  precedent to copy, because the codebase has never needed one. A Phase 2 prewarm step must add its own
  guard defensively (e.g. `if os.environ.get("WERKZEUG_RUN_MAIN") in (None, "true"):`-style check) in case
  `debug=True` is ever enabled later, even though it is not required for today's actual deployment shape.
- **Import-time safety:** `app.py:190-196` calls `_startup_check()` **unconditionally at module scope**
  (not inside `if __name__ == "__main__":`) — this is the one existing precedent for "runs on every
  import," and it is explicitly **not** the pattern a prewarm step should follow, since it does file I/O
  only (`core/startup_check.py:13-56`, no LLM/network call) and would double-fire under any future reloader
  scenario just like everything else at module scope. No module-level LLM call exists anywhere in this
  codebase today (confirmed by grep for top-level `chat_completions_create`/classifier calls, and for any
  `OpenAI(`/client construction outside `llm.py:36`, which only constructs the SDK object — no network
  call). **A Phase 2 prewarm entry point must be the first thing in this codebase to do real LLM I/O near
  startup, and must NOT mimic `_startup_check()`'s unconditional-module-scope pattern** — it must run only
  from inside `if __name__ == "__main__":` (or an equivalent real-server-boot hook), in a background
  thread, after the app is otherwise ready, gated by an explicit default-OFF env flag.
- **Tests/CI never trigger real LLM calls today** via any global switch — there is no `OFFLINE_ONLY`/
  `NO_LLM`/`LIVE=0` gate; instead, tests simply don't import/exercise the code paths that reach
  `chat_completions_create` (mostly `*_offline.py` naming convention, or per-test monkeypatching). This
  means a Phase 2 prewarm entry point's safety for tests/CI depends entirely on it **never being reachable
  from any import path `pytest`/`tests/conftest.py` naturally walks** — not on any existing gate catching it
  if it were.
- **`log_llm_usage` reuse:** signature confirmed at `logging_setup.py:272-288`. ~15 distinct `call_type`
  values already in use across the codebase (`target_fullcontext_runtime_composer`,
  `target_fullcontext_runtime_verifier`, etc.) — a Phase 2 prewarm call must mint its own new value
  (e.g. `"target_fullcontext_prewarm_composer"` / `"_verifier"`) rather than reuse any existing one, so
  downstream usage dashboards don't misattribute prewarm cost to real turn stages.
- **`core/turn_timing.py`'s `_bucket()`** (lines 21-30) silently returns a throwaway dict outside an active
  Flask request context — so `stage_start`/`stage_end` calls from a background prewarm thread would be
  harmless no-ops, but also pointless (never surfaced anywhere). A Phase 2 prewarm module should log its
  own timing directly via `log_llm_usage`/`emit_bot_event`, not attempt to reuse PERF-0's request-scoped
  stage-tracking machinery — satisfying rule 16 (prewarm creates no PERF-1 user-facing status) as a direct
  consequence of never touching a Flask request context at all.
- **Existing budget/lock precedent to mirror:** `orchestration/route_guards.py:32-69` (`check_rate_limit`
  — module-level `threading.Lock` + `dict`/`deque`, env-driven bypass) and
  `evals/v5/s62_target_runtime_live_provider_audit.py` (`MAX_PROVIDER_CALLS = 20` hard cap wrapping
  `llm.chat_completions_create`, plus an exclusive marker-file pattern to prevent duplicate concurrent live
  runs) are both directly reusable *styles* for a Phase 2 prewarm hard budget — a small module-level
  counter/lock, capped at "at most one attempt per (client_id, role, fingerprint) per process," is the
  natural fit given today's single-process deployment, with the marker-file style available as a
  future-proofing option if multi-worker deployment is ever introduced.
- **`client_id` is a small, fixed, allowlisted set** (`config.py:152-158`, `ALLOWED_CLIENTS`, defaulting to
  `{"demo"}` — only `clients/demo/` and `clients/_template/` exist on disk today) — confirming a hard
  per-client budget is trivially boundable, not an open-ended surface.

## 10. Cost / call budget

Given `ALLOWED_CLIENTS` defaults to one client (`demo`) and there are exactly two roles (Composer,
Verifier), a full prewarm sweep is at most **2 calls per process start** (one per role, for the one
configured client) under the "at most one attempt per (client_id, role, fingerprint) per process" budget
in §9 — small, bounded, and cheap relative to the ~26,500-token static prefix's one-time cost. Re-warming
the *same* fingerprint repeatedly within a process is never done (§9 budget), since TTL is unknown (§8) and
resending an already-recently-sent identical prefix has no evidence of providing additional benefit.

## 11. Failure semantics (fail-open, binding)

A prewarm call failing (timeout, provider error, malformed response, budget exhausted) must never raise
into the request path, never block `app.run()`/readiness, and never retry (retry=0, matching the existing
`call_count > 1: raise ..._retry_forbidden` single-attempt discipline already used by Composer/Verifier/
Boundary live backends at `core/target_runtime_llm_backends.py:73-78,121-126,180-185` — the same idiom, not
a new one). The bot continues serving real traffic without cache exactly as it does today if prewarm never
ran at all — prewarm is purely additive, never load-bearing for correctness.

## 12. Options comparison (A–E)

### A. Explicit provider cache API — **RULED OUT, not supported**

No explicit prompt-cache pre-registration API exists in the OpenAI-compatible SDK this codebase uses
against its DashScope/Qwen endpoint (§1, confirmed by repo-wide search for `cache_control`/`prompt_cache`/
`ttl` near any LLM call site — zero matches on the actual request/response path). Only implicit,
content-based caching (if any) is a candidate. Not carried forward — there is nothing to call explicitly.

### B. Owner-controlled prewarm CLI before demo/deploy

- **Guarantees exact reusable prefix:** yes, if built via §7 (reuses production message-builder functions
  verbatim).
- **Cost:** identical per-call cost to a real Composer/Verifier call (full static prefix tokens), run at
  most twice per demo/deploy (Composer + Verifier).
- **Latency:** irrelevant to the user — runs before traffic, as a standalone script.
- **TTL risk:** the CLI-to-first-real-request gap is operator-controlled (run it right before the demo
  starts), which is the *best* case for an unknown, possibly-short TTL (§8).
- **Duplicate calls under reloader/multiworker:** not applicable — a standalone script process, not part of
  the running app; no import-time or worker-boot interaction at all.
- **Failure behavior:** trivially fail-open — a failed warm-up script just means the first real request is
  cold, exactly like today; the operator sees the failure directly and can decide whether to retry manually
  (still retry=0 *within* the script itself, per rule 12).
- **Multi-client scaling:** run once per `client_id` in `ALLOWED_CLIENTS`, operator-driven — scales linearly
  and explicitly, no automatic fan-out risk.
- **Observability:** logs via `log_llm_usage` with its own `call_type`, same as any other mechanism.
- **Complexity/risk:** **lowest** of the automated-benefit options — a new standalone script analogous to
  the existing `scripts/validate_client_pack.py`, no changes to `app.py`'s startup sequence at all, zero
  interaction with reloader/multi-worker/import-time concerns by construction.
- **Downside:** requires a human to remember to run it; provides no protection for unattended/automatic
  first-time traffic (e.g. a process restart at 3am with no operator present).

### C. Async startup prewarm after readiness (not at import)

- **Guarantees exact reusable prefix:** yes, same §7 mechanism.
- **Cost:** same per-call cost as B, but fires automatically on every process start (today: once per
  `gunicorn -w 1` boot) rather than requiring a manual trigger.
- **Latency:** must run in a background thread, strictly after `app.run()`/worker-boot, never blocking
  readiness or the first real request (rule 3) — the same "fire-and-forget background thread" shape PERF-1
  already established and shipped for `/ask/stream`'s worker (`app.py`'s `_sse_worker_executor`), a direct,
  precedented pattern to reuse rather than invent.
- **TTL risk:** the startup-to-first-traffic gap is *not* operator-controlled — could be seconds (traffic
  right after boot) or much longer (idle process) — genuinely unknown whether warmth survives, given §8's
  undocumented TTL. Real risk of wasted prewarm cost if the gap exceeds an unknown TTL.
- **Duplicate calls under reloader/multiworker:** would require the `WERKZEUG_RUN_MAIN` guard (§9, not yet
  needed for today's `debug=False` deployment but required defensively per the binding rules) and the
  per-fingerprint dedup budget (§9/§10); with today's single-worker deployment, the realistic risk is low,
  but the design must not silently assume single-worker forever.
- **Failure behavior:** must be explicitly wrapped fail-open (rule 4) — cannot be allowed to delay or crash
  `app.run()`.
- **Multi-client scaling:** automatic sweep over `ALLOWED_CLIENTS` × 2 roles at every boot — bounded (§10)
  but happens unconditionally every restart, including restarts where no demo/traffic is imminent.
- **Observability:** same `log_llm_usage` reuse.
- **Complexity/risk:** **medium** — touches `app.py`'s startup sequence (a new guarded call site, not
  module-scope), needs the reloader guard, the budget, and fail-open wrapping all correctly composed; more
  moving parts than B, but each part is precedented elsewhere in this codebase (§9).

### D. Lazy background prewarm after first request

- **Guarantees exact reusable prefix:** yes, same §7 mechanism, triggered from within an already-correctly
  guarded Flask request lifecycle (sidesteps import-time/reloader/multi-worker concerns almost entirely,
  since it never fires outside a real request context).
- **Real incremental value is the weakest of the four candidates.** The owner's own brief states
  `cached_tokens` has *already* been observed in production logs **without any deliberate prewarm
  mechanism** — meaning ordinary consecutive real turns already appear to implicitly warm the cache for
  each other today, at zero extra engineering cost. Option D only fires *after* a first real request has
  already occurred — at which point whatever implicit turn-to-turn caching already exists has already had
  its chance to start warming things up on its own. D would benefit only turns 2+ of a **freshly-cold**
  process for a client that had zero prior traffic — a narrower and already-partially-covered case than B
  or C, which both target the higher-value "cold moment right after boot, including the very first
  request" gap that D structurally cannot help with (D's trigger *is* that first request).
- **Cost/latency/failure/scaling/observability:** all comparable to C, minus the reloader/import-time risk
  surface (a real advantage), but at the cost of the value gap above.
- **Complexity/risk:** low-medium — simplest trigger point of the three automated options, but the
  narrowest justified benefit.

### E. Do not implement, if cache semantics cannot be proven

Not chosen outright, because the specific thing the governing principle demands proof of — **prefix
identity** — is provable from code today (§2-§7), by disciplined reuse of the exact production
message-builder functions rather than a parallel implementation. What remains unprovable without a live
call (TTL, actual hit behavior, model-alias stability — §8) is explicitly not claimed as proven anywhere in
this audit, and Phase 2's own rollout is designed to require a separate LIVE/LLM permission before those
unknowns are ever tested for real. E would be the right call only if prefix identity itself could not be
guaranteed — it can be, via reuse discipline, so E is not selected.

## Selected: **B + C, implementation permitted in Phase 2, default OFF, two-gate rollout**

- **B (owner-controlled CLI)** is the lowest-risk, immediately-useful mechanism — build it first, as a
  standalone script with zero interaction with `app.py`'s startup path, directly analogous to
  `scripts/validate_client_pack.py`. Solves the highest-value case (warm the cache deliberately right
  before an important demo) with the least engineering risk.
- **C (async startup prewarm)** is the automated complement — same underlying prewarm function B calls,
  wired into `app.py` behind a new, explicit, default-**OFF** env flag (e.g.
  `PROMPT_CACHE_PREWARM_ENABLED`), a `WERKZEUG_RUN_MAIN` guard, and the fail-open/budget/retry=0 rules from
  §9-§11. Default-OFF means Phase 2 landing this code changes nothing about current runtime behavior until
  an operator explicitly opts in — a second, independent gate beyond PRE-CODE/owner-GO-for-implementation.
- **D is not selected** — real value is too thin given already-observed implicit turn-to-turn caching (see
  comparison above); not worth its own engineering surface as a *separate* mechanism. (Nothing prevents D's
  natural effect from continuing to happen on its own, since it isn't a deliberate mechanism at all —
  ordinary real traffic already does this implicitly, per the owner's own observation.)
- **A is ruled out** (unsupported), **E is not chosen** (prefix-identity is provable).
- **Both B and C must reuse the identical `build_composer_sdk_messages`/`build_verifier_sdk_messages` +
  fingerprint (§5) + budget (§9-§10) machinery** — implemented once, in one Phase 2 module, called by both
  the CLI entry point and the async startup hook, never duplicated.
- **First real (LIVE) activation of either B or C against the actual provider requires a separate,
  explicit owner LIVE/LLM permission**, on top of the Phase 2 implementation GO — matching this codebase's
  existing two-gate pattern for other live-provider milestones (A9, S66 in `docs/STRANGLER_ROADMAP.md`).
  Phase 2 implementation itself must remain fully exercisable offline (dry-run mode computing fingerprints
  and deciding "would I call the provider now" without actually calling it — §"Acceptance matrix" rows
  15-16).

## 13. Implementation allowlist (Phase 2 — blocked until owner GO, and LIVE activation blocked further)

| File | Action |
|---|---|
| `contracts/target_prompt_cache_fingerprint.py` | CREATE — `TargetPromptCacheFingerprint` frozen dataclass (§5) |
| `core/target_prompt_cache_prewarm.py` | CREATE — fingerprint computation (pure), budget/dedup gate, the actual `chat_completions_create` prewarm call (reusing `build_composer_sdk_messages`/`build_verifier_sdk_messages` verbatim), fail-open wrapping, `log_llm_usage` call with a new `call_type` |
| `scripts/prewarm_prompt_cache.py` | CREATE — standalone owner-controlled CLI (Option B), thin wrapper calling `core/target_prompt_cache_prewarm.py` |
| `app.py` | UPDATE — Option C's guarded async startup hook, inside `if __name__ == "__main__":`, behind `PROMPT_CACHE_PREWARM_ENABLED` (default off) and a `WERKZEUG_RUN_MAIN` guard; **no changes to `/ask`/`/ask/stream` request handling** |
| `logging_setup.py` | **KEEP unchanged** — reuse existing `log_llm_usage`, no second usage logger (rule 15) |
| `core/turn_timing.py` | **KEEP unchanged** — prewarm does not use PERF-0's request-scoped stage machinery (§9) |
| `core/target_composer_executor.py`, `core/target_response_verifier.py`, `core/target_runtime_llm_messages.py` | **KEEP unchanged** — prewarm reuses these modules' existing functions, never forks or edits them (rule 9: no prompt changes for artificial cache hits) |
| `tests/test_final_provider_prompt_cache_prewarm_implementation.py` | CREATE — acceptance matrix (§14) |

## 14. Acceptance matrix (Phase 2 implementation — minimum coverage, 24 scenarios)

| # | Scenario | Expected |
|---|---|---|
| 1 | First cold request (no prior prewarm) | Behavior identical to today — no dependency on prewarm ever having run |
| 2 | Warm cache hit (after a successful prewarm, real LIVE-gated test only) | Measurable `cached_tokens` > 0 and/or reduced stage duration vs. cold baseline |
| 3 | Cache miss after corpus change | Fingerprint differs (`corpus_sha256` changed) — treated as a fresh, un-warmed fingerprint |
| 4 | Miss after prompt/template change | Fingerprint differs (`sha256(system_policy_text)` or `sha256(preamble_template_text)` changed) |
| 5 | Miss after model change | Fingerprint differs (`model` string changed) |
| 6 | Composer/Verifier namespaces separated | Same client_id, same corpus — Composer and Verifier fingerprints are provably different (§3, §5) |
| 7 | Two `client_id`s separated | Distinct fingerprints, distinct budget counters, no cross-client reuse assumed |
| 8 | Repeated prewarm of the same fingerprint | No duplicate provider call — budget/dedup gate blocks it (§9-§10) |
| 9 | Dev reloader simulated (`WERKZEUG_RUN_MAIN` unset then set) | Prewarm fires at most once across the simulated parent+child pair |
| 10 | Multi-worker simulated (two independent processes) | Each process's own budget counter is independent (documented limitation — no cross-process dedup without a future marker-file mechanism; not silently assumed safe) |
| 11 | Provider failure (simulated exception from the LLM call) | Fail-open — no exception propagates past the prewarm call site, app continues normally |
| 12 | Timeout (simulated) | Fail-open, same as row 11 |
| 13 | `retry=0` | Exactly one attempt per prewarm call, no internal retry loop |
| 14 | Hard call budget exceeded | Further prewarm attempts for that budget scope are refused, not queued |
| 15 | Tests/CI run | Zero real provider calls anywhere in the test suite (prewarm entry points never reachable from `pytest`'s import graph) |
| 16 | Dry-run mode | Fingerprint computed and a "would call provider" decision logged, with zero actual `chat_completions_create` invocations |
| 17 | No PII/session in prewarm payload | Dynamic-tail fields are fixed non-PII placeholders (§7), never derived from `request`/session/SID/phone |
| 18 | No answer persistence | Prewarm's provider response is never written to session, never surfaced to any user, never treated as a real answer (rule 7-8) |
| 19 | User-turn LLM count unchanged | A real `/ask`/`/ask/stream` turn's LLM call count is identical whether or not prewarm ran (rule 17) |
| 20 | PERF-0 cold vs. warm duration comparison | Composer/Verifier stage `duration_ms` compared between a cold-fingerprint turn and a warm-fingerprint turn (LIVE-gated real measurement, not simulated) |
| 21 | `cached_tokens` sourced from provider usage | Read via the existing `_cached_tokens_from_usage_obj`/`log_llm_usage` path (`logging_setup.py:238-248,272-288`) — no second usage-parsing implementation |
| 22 | PERF-1 status sequence unchanged | `/ask/stream`'s `event: status` sequence for a real user turn is unaffected by prewarm having run or not (rule 16 — prewarm never touches `core/turn_timing.py`'s request-scoped sink) |
| 23 | Client-pack validation unchanged | `scripts/validate_client_pack.py`'s behavior/output is unaffected by any prewarm code (no shared state, no import coupling) |
| 24 | Stale fingerprint not considered warm | A fingerprint computed before a tracked component changed is never treated as still-valid after the change — no grace period, no partial match |

## STOP

After PRE-CODE ✅ — **STOP**. Phase 2 implementation only after a separate owner GO, and even then, first
real LIVE activation against the provider requires a further separate owner LIVE/LLM permission (§8, §12).

## Test commands (governance)

```powershell
python -m pytest tests/test_final_provider_prompt_cache_prewarm_governance.py -q
python -m pytest tests/test_final_response_latency_observability_governance.py tests/test_final_early_sse_status_streaming_governance.py tests/test_final_safe_medical_boundary_bypass_governance.py -q
git diff --check
```
