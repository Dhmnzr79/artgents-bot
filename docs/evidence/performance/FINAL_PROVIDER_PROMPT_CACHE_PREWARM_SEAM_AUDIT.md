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

## Governance correction (this revision, @ `552c2ce` → correction)

The initial revision of this audit selected **B + C** for Phase 2 (owner-controlled CLI *and* an
automatic async startup hook wired into `app.py`, gated by a runtime env flag). The owner correctly
narrowed this: Phase 2 now covers **only Option B** — a manual, owner-controlled CLI. Option C (automatic
startup prewarm) is **deferred** to a separate future milestone, to be considered only after the CLI's
own measured results (real `cached_tokens`/duration evidence, not just "the call fired") justify the
larger engineering surface (`app.py` changes, reloader guard, runtime flag, background thread). This
revision also:

1. Corrects cache-locality terminology throughout (§8) — the provider's prompt cache lives at
   DashScope/Qwen, not inside this process; a Flask process restart does not, by itself, necessarily
   cold the cache (the cache is not process state).
2. Softens the "byte-identical" claim to what can actually be proven and controlled: **identical
   message/token prefix** — i.e., the same Python message-list content, built via the same functions, up
   to the dynamic boundary. This audit does not claim wire-byte HTTP-request identity, since the SDK's
   own request serialization is not something this codebase controls or inspects.
3. Redesigns the fingerprint (§5) to include an explicit, directly-verifiable **static-prefix hash** (a
   hash of the actual assembled static prefix text itself), in addition to the corpus hash and version
   markers.
4. Replaces the in-process budget counter (only meaningful for a long-running server process) with a
   **file-based exclusive attempt ledger** (§7, §10) — correct for a CLI that runs as a fresh, short-lived
   process each invocation, with no shared memory between runs.
5. Narrows the Phase 2 implementation allowlist (§13) to remove `app.py` and any startup/runtime-flag
   component entirely — nothing in Phase 2 touches the running application.

No other section's core finding changed: prefix identity (in the corrected, honest sense above) is still
provable from code (§2-§7); Composer and Verifier are still proven-separate namespaces (§3); the TTL and
actual cache-hit behavior are still unknown and not guessed (§8).

## Governance correction (second revision) — separating cache identity from attempt lifecycle

The prior revision's duplicate-run protection had a real design flaw: it used a **permanent** O_EXCL
marker keyed by `(client_id, role, fingerprint)`. Since the fingerprint does not change when the
provider's cache simply goes cold (TTL expiry is invisible locally — §6), that design would have
**permanently blocked every future legitimate re-warm** of an unchanged fingerprint, forever, even
after the provider's actual cache had long since expired. This revision fixes it by separating two
concepts that were wrongly conflated into one key:

1. **Cache identity** — `(client_id, model, role, static_prefix_hash, fingerprint)` (§5) — describes
   *what content* would be warmed. It is descriptive/audit data. **It is never used as a lookup key that
   blocks or permits an attempt.**
2. **Owner-authorized live attempt** — a separate, explicit, immutable **`attempt_id`**, supplied by the
   operator only in the future `--live` mode (never in dry-run). Each CLI invocation that reaches
   `--live` is exactly one attempt, gets exactly one run-level marker, keyed by `attempt_id` — not by
   fingerprint, not by role. A fresh attempt_id always gets a fresh marker path; nothing about a
   previously-warmed fingerprint ever blocks it. What IS forbidden is reusing the **same** `attempt_id`
   value twice (§7) — that is a bug/replay guard, not a content-based cache-warming throttle.

This means re-warming an unchanged fingerprint after an unknown TTL has expired is fully supported by
design: it simply requires a new owner GO and a new `attempt_id` — never blocked by the fingerprint
itself, and never requiring any `--force`/reclaim/delete override (none exists).

## Governing principle (binding, restated)

**Do not implement prewarm until it is proven that the warming request produces the same message/token
prefix that a real later Composer or Verifier call would use.** This audit's job in Phase 1 is to prove —
from code, not from a live experiment — that a prewarm call CAN be built to send the identical leading
message content that production Composer/Verifier calls send, by reusing the exact same message-builder
functions rather than a parallel implementation. It is **not** this phase's job to prove the provider
actually returns a cache hit for that prefix (that requires a live measurement, which this phase forbids)
— that empirical proof is deferred to the CLI's own live mode, itself gated behind a separate LIVE/LLM
permission before ever running for real (§8, §9).

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
    → built ONCE per client_id per process (lazy, on first use). This is a LOCAL, in-process
      memoization of file-read work — it has nothing to do with the PROVIDER's own prompt cache
      (§8); do not conflate the two.

Provider client (shared singleton, both stages):
  llm.py:33-37 — chat_client = OpenAI(**_chat_client_kwargs); client = chat_client
    (constructed once at module import — object construction only, NOT a network call)
  llm.py:60-63 — chat_completions_create(*, model, **kwargs) wraps chat_client.chat.completions.create(...)
  Provider: OpenAI-compatible SDK pointed at DashScope/Qwen (config.py:11-18); models are plain
    env-configurable strings (config.py:26-28, `QWEN_PLUS_MODEL = "qwen3.7-plus"`), not aliases
    documented anywhere in this repo as pinned-vs-rolling (§8 unknown, flagged not invented).

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
text. Combined with the system policy: **~106,000 characters (~26,500 tokens)** of stable static-prefix
message content per client_id, versus an estimated **1–5 KB** of dynamic per-turn tail — the static
prefix dominates total prompt size by roughly 20–100×, which is exactly the size profile prefix-caching
economics are built for, IF the provider genuinely reuses the cached prefix across calls (unconfirmed
without a live measurement, §8).

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
      + corpus_text                                          ← same corpus_text object/content
    DYNAMIC tail: RESPONSE_SPEC_JSON / PRIMARY_EVIDENCE_JSON / CANDIDATE_TEXT (per-turn).
```

**Confirmed empirically, not assumed: Composer and Verifier do NOT share a reusable cache prefix,
despite sharing identical `corpus_text` content.** Both message arrays diverge starting at `message[0]`
(different system policy text) and diverge again at the very start of `message[1]` (`"Compose the
patient-facing answer..."` vs `"Assess the candidate answer..."`, plus Composer's extra
`"Return strict JSON only: ..."` block that appears *before* `CACHED_FULL_CONTEXT:` and Verifier does not
have). Any provider prefix-matching necessarily matches from the *start* of the request; since the very
first characters differ, a prewarm of Composer's prefix cannot produce a cache hit for Verifier's later
call, or vice versa — **two independent namespaces are required, confirmed as a proven fact for this
codebase, not merely a cautious default.**

## 4. Static/dynamic boundary (summary table)

| Content | Composer | Verifier | Static? |
|---|---|---|---|
| System policy text | `TARGET_COMPOSER_SYSTEM_POLICY` | `TARGET_SEMANTIC_VERIFIER_SYSTEM_POLICY` | Static, but role-specific (no shared text) |
| User-message preamble | `"Compose the patient-facing answer..."` + `"Return strict JSON only:..."` | `"Assess the candidate answer..."` | Static, role-specific |
| `CACHED_FULL_CONTEXT:\n` + corpus_text | same corpus content | same corpus content | Static, per-`client_id`, stable until the underlying `.md` files change |
| Everything after corpus_text | directives/action/evidence/user_message | spec/evidence/candidate_text | Dynamic, per-turn |
| Model string | `target_fullcontext_composer_model()` | `target_fullcontext_verifier_model()` | Static per process/env, role-specific |

**No PII, session state, or user text of any kind appears anywhere in the static portion** — confirmed by
construction (`corpus_text` is pure file content; the preambles are fixed literals) — satisfying rule 5
trivially for the prewarm design, provided the CLI only ever sends the static portion plus a fixed,
non-PII placeholder for the dynamic tail's required template fields (§7).

## 5. Cache-key / fingerprint design (local bookkeeping only — not sent to the provider)

**Important distinction:** the fingerprint below is a *local* construct the CLI uses to decide "have I
already warmed this exact prefix, should I attempt it again." It is never transmitted to the provider —
the provider's own cache matching (whatever it actually is; unconfirmed, §8) is presumably based on the
bytes of the request it actually receives, independent of any local bookkeeping concept.

No existing single fingerprint covers "everything that determines this static prefix's content." What
already exists: `TargetCachedFullContext.sha256` (`contracts/target_cached_full_context.py:15`) — SHA-256
of `corpus_text` only — and `TargetRuntimeClientContext.cache_key` (`core/target_runtime_client_context.py:73-75`,
`f"{self.client_id}:{self.cached_full_context.sha256}"`) — the closest existing precedent, but it doesn't
cover the system policy text, the template wording, or the model string. **Nothing in this codebase
versions `TARGET_COMPOSER_SYSTEM_POLICY`, `TARGET_SEMANTIC_VERIFIER_SYSTEM_POLICY`, or the message
templates** (confirmed by grep for `POLICY_VERSION`/`policy_version` — no matches).

**Designed fingerprint (Phase 2, not built in this governance phase) — governance correction: now
includes an explicit, directly-verifiable static-prefix hash, not just component hashes:**

```text
static_prefix_text =                    # the ACTUAL assembled static prefix, built by calling the
    system_policy_text                  # real build_*_sdk_messages() function and slicing its output
    + preamble_template_text            # up to (not including) the dynamic tail -- never hand-assembled
    + corpus_text                       # separately from what production code would build

static_prefix_hash = sha256(static_prefix_text)   # the PRIMARY, directly-verifiable proof: if two
                                                    # fingerprints share this hash, the actual prefix
                                                    # content sent is guaranteed identical

TargetPromptCacheFingerprint = sha256(
    client_id
    + "|" + role                          # "composer" | "verifier" — literal, never a third value
    + "|" + model                         # the exact model string passed to chat_completions_create
    + "|" + static_prefix_hash            # PRIMARY proof of prefix identity (above)
    + "|" + corpus_sha256                 # TargetCachedFullContext.sha256 -- kept for readable,
                                           # independently-checkable invalidation granularity even
                                           # though it's already subsumed by static_prefix_hash
    + "|" + str(PROMPT_TEMPLATE_VERSION)        # small manually-bumped int, human-readable version
                                                  # marker (mirrors BOT_EVENTS_SCHEMA_VERSION,
                                                  # logging_setup.py:27) -- auditability, even though
                                                  # static_prefix_hash already catches wording changes
    + "|" + str(MESSAGE_SERIALIZATION_VERSION)  # separate small manually-bumped int -- catches
                                           # STRUCTURAL changes (field order, message count, role
                                           # list) that hashing the assembled TEXT alone would not
                                           # catch if the assembly *code* changes without the
                                           # resulting *text* changing
)
```

`static_prefix_hash` is the primary, self-updating proof (if the policy prose, preamble wording, or
corpus content changes for any reason, this hash changes automatically, with no developer action
required). The two explicit version ints exist for human auditability and for the one class of change
content-hashing cannot catch on its own (restructuring the assembly code without changing the resulting
text) — an explicit escape hatch, not an assumption.

**Governance correction (second revision) — fingerprint is cache identity, not an attempt-lifecycle
key.** This fingerprint (and its `static_prefix_hash`/`corpus_sha256` components) is recorded *inside* a
live attempt's marker for audit/description purposes (§7) — it is never used as the marker's file path
or as any kind of lookup key that permits or blocks a CLI run. That role belongs exclusively to the
separate, explicit `attempt_id` described in §7. Conflating the two was the exact flaw this correction
fixes: keying duplicate-run protection off a content fingerprint would permanently block all future
re-warms of unchanged content, even long after an unknown provider TTL had expired.

## 6. Invalidation table — cold/miss triggers (corrected terminology)

The provider's cache is **provider-side state** (at DashScope/Qwen), not something this process owns or
controls. A Flask process restart does **not**, by itself, necessarily make the provider's cache cold —
the provider may still recognize a previously-seen prefix regardless of which local process sends it
again. Cache miss/cold state can genuinely occur from:

| Trigger | Local fingerprint changes? | Mechanism |
|---|---|---|
| Provider-side cache TTL expiry (duration unknown, §8) | No — fingerprint stays the same | Not detectable locally at all; only a live measurement (`cached_tokens`) reveals this |
| Provider-side cache cleared/changed by the vendor | No — fingerprint stays the same | Same as above — genuinely invisible to this codebase |
| `TARGET_FULLCONTEXT_COMPOSER_MODEL` / `_VERIFIER_MODEL` env var changed | Yes | `model` string differs |
| `TARGET_COMPOSER_SYSTEM_POLICY` / `TARGET_SEMANTIC_VERIFIER_SYSTEM_POLICY` text edited | Yes | `static_prefix_hash` differs (and `PROMPT_TEMPLATE_VERSION` should be bumped manually for auditability) |
| `_COMPOSER_USER_TEMPLATE` / `_VERIFIER_USER_TEMPLATE` preamble wording edited | Yes | `static_prefix_hash` differs |
| `clients/{id}/md/*.md` content edited | Yes | `static_prefix_hash` AND `corpus_sha256` both differ |
| Message-list structure changed (field order, message count, role list) without template text changing | **Only if a developer manually bumps `MESSAGE_SERIALIZATION_VERSION`** | explicit int; a required manual step, not automatic |
| `client_id` changes | Yes | different fingerprint entirely — separate namespace by construction |
| Composer vs Verifier | Always different | `role` literal differs; §3 proves no shared prefix regardless |
| Process restart with unchanged files | **No local change** — but whether the PROVIDER still has it warm is unknown (see TTL row above) | fingerprint is deterministic over content, not over process identity — this is intentional, and it does NOT imply the provider is still warm |

**Key correction:** a locally-unchanged fingerprint does not prove the provider cache is still warm (TTL
is unknown) — it only proves the CLI would send the identical prefix content if run again. Warmth itself
can only be confirmed by an actual live measurement's `cached_tokens` result.

## 7. What the CLI actually sends and records

Reusing `build_composer_sdk_messages`/`build_verifier_sdk_messages` **verbatim, unmodified** (never
hand-rolling a parallel prefix string) is the only way to guarantee the CLI's prewarm call carries the
identical message/token content that a real Composer/Verifier call would send, up to the dynamic
boundary — this is the core of "proving the same prefix," per the governing principle, stated honestly:
this is message-content identity, not a claim about HTTP wire-level byte identity (the SDK's own request
serialization is outside this codebase's control or inspection, per the governance correction).

Since any provider-side prefix matching would necessarily match from the *start* of the request, the
dynamic tail's exact content does not need to be real: the CLI supplies a fixed, static, non-PII
placeholder for `response_directives_json`/`primary_evidence_json`/`governed_action_context_json`/
`user_message` (e.g., empty JSON objects and an empty string) built through the *same*
`TargetComposerInvocation`/`TargetSemanticVerifierInvocation` dataclasses and the *same*
`build_*_sdk_messages` functions — never inventing a second message-assembly code path. This automatically
satisfies rule 5 (no user text/SID/session/PII/phone — the placeholder is a fixed constant, never derived
from any real request) and rule 6 (only the static approved prefix is meaningfully "warmed"; the
placeholder tail is not content anyone cares about caching).

**Dry-run mode (default, zero provider calls, zero artifacts):** loads the real client pack via the
existing `load_target_runtime_client_context(client_id)`, builds the real Composer/Verifier messages via
the real `build_*_sdk_messages` functions, computes the fingerprint for each role (§5), and prints
**only**: `client_id`, `role`, `model`, `static_prefix_hash`, `corpus_sha256`, prefix length (characters)
and an estimated token count, the composite fingerprint per role, and the planned budget (Composer ≤1,
Verifier ≤1, total ≤2). It never prints `corpus_text` itself, any synthetic answer, contact information,
or any other client-pack content — only hashes and small scalar metadata. **Dry-run never creates an
attempt marker, never writes to the ledger, and never requires an `attempt_id` at all** — it is pure
read/compute/print.

**Live mode (`--live`, explicit, separate future owner LIVE/LLM permission required) — attempt
lifecycle (governance correction, second revision):**

1. **`attempt_id` is a required, explicit CLI argument in `--live` mode only** (never auto-generated by
   the script, never required or accepted in dry-run) — this ties every live activation to a specific,
   operator-supplied value that is part of the deliberate owner-authorization act itself, not something
   the tool invents on the operator's behalf.
2. Before any marker write or provider call, the CLI performs a **preflight check**: the freshly-computed
   fingerprints (Composer and Verifier) are compared against operator-supplied expected model/fingerprint
   values; any mismatch aborts immediately, before anything is written or called.
3. On a matching preflight, the CLI creates **exactly one run-level attempt marker for the whole
   invocation**, at a path keyed **by `attempt_id` alone** (e.g.
   `.prewarm_ledger/attempts/{attempt_id}.json`) — via exclusive-create/`O_EXCL` semantics, **before the
   first provider call**. This is the file that both proves the attempt happened and prevents that exact
   `attempt_id` from ever being used again (reuse is a hard error at this exact step, before any provider
   call). Fingerprint/role/client_id are **not** part of this path — a different `attempt_id` with an
   unchanged fingerprint creates a brand-new marker without friction, which is precisely what makes a
   legitimate re-warm after an unknown TTL expiry possible (§6).
4. The marker records, at creation and updated as the attempt proceeds: `attempt_id`, `client_id`,
   requested/configured `model`, `composer_fingerprint`, `verifier_fingerprint`, `planned_roles` (e.g.
   `["composer", "verifier"]`), `budget` (fixed at 2), `retry` (fixed at 0), `status`
   (`"started"` → `"completed"` | `"aborted"` | `"failed"`), `started_at`/`completed_at` timestamps, and
   running `calls_started`/`calls_completed` counters.
5. **Composer and Verifier calls are both recorded in this same single marker/ledger file for the
   attempt** — one shared ledger per attempt, not two separate per-role files. Each call increments
   `calls_started` immediately before the provider call and `calls_completed` immediately after a
   successful response.
6. On the first unexpected provider/model mismatch or provider error for either role, the CLI **aborts
   the remainder of the attempt**: `status` is set to `"aborted"`/`"failed"`, `completed_at` is recorded,
   and the other planned role (if not yet attempted) is never called. `retry=0` throughout — no call is
   ever repeated within an attempt.
7. **Once created, an attempt marker is permanently consumed — successful, aborted, failed, or crashed
   (process killed mid-run, marker left in `"started"` forever) all count as consumed.** There is no
   `--force` flag, no marker-delete tooling, no reclaim mechanism anywhere in the CLI or its supporting
   module. A crashed or partial attempt is never auto-resumed or retried by the same `attempt_id` — the
   operator must obtain a new owner GO and a new `attempt_id` to try again, exactly like any other
   re-warm.
8. **The attempt marker proves only the fact and final state of that one specific, owner-authorized run
   — it does not mean, and must never be read as meaning, that the provider's prompt cache is still
   warm.** Warmth itself is only ever confirmed by an actual `cached_tokens` value in a live measurement
   (§8), never inferred from a marker's mere existence or `"completed"` status.

**Warm response handling (rule 8):** the provider's actual response content (the composed answer text /
verifier issues JSON) is **discarded** immediately after the usage object is read — never written to
session, never shown to any user, never persisted anywhere as answer text. Only anonymized
usage/result metadata is recorded in the marker/ledger (the fields listed in step 4 above, plus
`cached_tokens` if the provider reports it, per call). This is not an answer-cache and never becomes
one.

## 8. What the provider actually caches, and what remains genuinely unknown

**Corrected terminology:** the cache being discussed is **provider-side state at DashScope/Qwen**, not
anything local to this Flask process. `_CONTEXT_CACHE` (§1) is a separate, unrelated, purely local
memoization of file-read work — conflating the two would be a real design error, which this correction
exists partly to prevent.

`cached_tokens` (`usage.prompt_tokens_details.cached_tokens`, read at `logging_setup.py:238-248`) has
already been observed in real production usage logs for this exact message shape, per the owner's own
brief — **without any deliberate prewarm mechanism existing today.** This is strong evidence the
DashScope/Qwen-compatible endpoint already performs *some* form of automatic, implicit prefix caching for
repeated identical prompt prefixes across ordinary consecutive real turns. `core/target_cached_full_context.py`'s
own docstring (lines 17-18) already anticipated this exact gate: *"This module prepares a deterministic
provider prompt prefix candidate. Provider-side prompt caching is a separate future live integration gate
and is **not** implemented here."*

**What this audit can prove from code alone (Phase 1, no live calls):** that a CLI prewarm call built via
§7 sends message-content-identical leading segments to a real later call, for a provably-static prefix
(§2-§4), scoped to correct per-role/per-client namespaces (§3, §5).

**What this audit explicitly cannot prove without a live measurement, and does not invent an answer for:**
- The provider's cache TTL — undocumented anywhere in this repo or in any comment/config found. Could be
  seconds, minutes, or longer. Treated as **unknown**, not assumed short or long.
- Whether the provider's implicit caching applies uniformly to *any* two calls sharing a prefix regardless
  of time gap between them (as opposed to only very-close-in-time calls) — unconfirmed.
- Whether the exact model string configured (`"qwen3.7-plus"`) is a stable pinned snapshot or could be
  silently re-aliased by the provider over time — no in-repo documentation either way.
- What specifically causes the provider's cache to invalidate on its side (§6's TTL/vendor-side-clear
  rows) — genuinely invisible from this codebase; only a live measurement (`cached_tokens`) reveals
  whether a given call was a hit.
- Whether a deliberate prewarm call, sent from a context with no subsequent real user activity for some
  time, would still be warm by the time real traffic arrives — this is precisely what the CLI's own live
  mode is designed to measure empirically, under a **separate, explicit LIVE/LLM owner permission**,
  matching this codebase's own established pattern (e.g. the A9 and S66 milestones in
  `docs/STRANGLER_ROADMAP.md` both gate their first live run behind a distinct owner decision even after
  implementation is otherwise complete).

## 9. Deployment / reloader / multi-worker — status: not in scope for this milestone

**Governance correction: this entire concern class is deferred along with Option C.** Since Phase 2 now
builds only a standalone CLI script (never wired into `app.py`, never started by the application process),
none of the following affect this milestone's implementation:

- Flask's dev reloader (`debug=True`/`WERKZEUG_RUN_MAIN`) — not applicable; the CLI is invoked directly by
  an operator, not by Flask's app-boot sequence.
- Multi-worker gunicorn deployment — not applicable; the CLI runs as its own independent process,
  regardless of how many `gunicorn` workers the application itself uses.
- Import-time safety — trivially satisfied; the CLI script is never imported by `app.py`, `tests/conftest.py`,
  or any other application/test import graph, so it cannot fire as a side effect of `import app` or `pytest`
  collection.

These findings remain documented here for completeness and to inform a **future, separate Option-C
milestone** (automatic startup prewarm), which — if ever undertaken — would need to design for: today's
`gunicorn -w 1` single-worker deployment (`Dockerfile:10`, `start.sh`, deliberately single-writer per its
own comment about SQLite sessions), the absence of any existing `WERKZEUG_RUN_MAIN` guard precedent in
this repo, and `app.py:190-196`'s `_startup_check()` as the explicit anti-pattern to avoid copying
(module-scope, unconditional, would double-fire under any future reloader scenario). None of this is
built, wired, or exercised in this milestone.

**What does carry over from this section into the current CLI-only scope:**
- **`log_llm_usage` reuse** (`logging_setup.py:272-288`) — the CLI must mint its own new `call_type` value
  (e.g. `"target_fullcontext_prewarm_composer"` / `"_verifier"`) distinct from the ~15 existing values, so
  downstream usage dashboards don't misattribute prewarm cost to real turn stages.
- **`core/turn_timing.py`'s `_bucket()`** (lines 21-30) silently returns a throwaway dict outside an
  active Flask request context — irrelevant to a standalone CLI anyway, which has no Flask request
  context at all. The CLI logs its own timing directly via `log_llm_usage`, never touching PERF-0's
  request-scoped stage machinery — satisfying rule 16 (prewarm creates no PERF-1 user-facing status) as a
  direct, structural consequence.
- **`client_id` is a small, fixed, allowlisted set** (`config.py:152-158`, `ALLOWED_CLIENTS`, defaulting
  to `{"demo"}`) — the CLI takes `client_id` as an explicit required argument, validated against this same
  set.

## 10. Cost / call budget

Per attempt (one `attempt_id`, one CLI `--live` invocation), for one `client_id`: **at most one Composer
warm call and at most one Verifier warm call — total maximum 2 provider calls**, recorded in that
attempt's own marker (§7). Budget is scoped to the attempt, not to the fingerprint — a later attempt
(new `attempt_id`, new owner GO) for the same fingerprint gets its own fresh 2-call budget; nothing
about a prior attempt's consumed budget carries over or accumulates. `retry=0` (§11). If the live
preflight check (fingerprint/model mismatch) fails, or if the first call's result is an unexpected
provider/model mismatch, the CLI **aborts immediately** — it does not proceed to attempt the second
(Verifier, if Composer ran first) call in the same attempt. This is small, bounded, operator-visible, and
cheap relative to the ~26,500-token static prefix's one-time cost.

## 11. Failure semantics (fail-open for the CLI itself; binding)

A CLI prewarm attempt failing (timeout, provider error, malformed response, preflight mismatch,
`attempt_id` already used) must never retry (`retry=0`, matching the existing
`call_count > 1: raise ..._retry_forbidden` single-attempt discipline already used by Composer/Verifier/
Boundary live backends at `core/target_runtime_llm_backends.py:73-78,121-126,180-185` — the same idiom,
not a new one) and must **abort the remainder of that attempt** on the first unexpected provider/model
mismatch rather than attempting further calls. A crashed process mid-attempt leaves the marker
permanently in its last-written, non-`"completed"` status — this counts as consumed, exactly like a
clean abort; there is no difference in outcome between "cleanly aborted" and "crashed," both burn that
`attempt_id` forever, and neither is auto-resumable. Since the CLI is entirely separate from the running
application, "fail-open" here means: a failed, aborted, or crashed CLI run has **zero effect** on the
bot's ability to serve real traffic — the bot continues exactly as it does today whether or not the CLI
was ever run, or whether it succeeded, failed, or crashed. Nothing in the application depends on the CLI
having run.

## 12. Options comparison (A–E)

### A. Explicit provider cache API — **RULED OUT, not supported**

No explicit prompt-cache pre-registration API exists in the OpenAI-compatible SDK this codebase uses
against its DashScope/Qwen endpoint (§1, confirmed by repo-wide search for `cache_control`/`prompt_cache`/
`ttl` near any LLM call site — zero matches on the actual request/response path). Only implicit,
content-based caching (if any) is a candidate. Not carried forward — there is nothing to call explicitly.

### B. Owner-controlled prewarm CLI before demo/deploy — **SELECTED, sole Phase 2 scope**

- **Guarantees identical reusable prefix content:** yes, if built via §7 (reuses production
  message-builder functions verbatim).
- **Cost:** identical per-call cost to a real Composer/Verifier call (full static prefix tokens), at most
  2 calls per invocation (§10).
- **Latency:** irrelevant to the user — runs before traffic, as a standalone script, never inside the
  request path.
- **TTL risk:** the CLI-to-first-real-request gap is operator-controlled (run it right before the demo
  starts), which is the *best* case for an unknown, possibly-short TTL (§8).
- **Duplicate calls under reloader/multiworker:** not applicable at all (§9) — a standalone script
  process, never part of the running app. Duplicate/replay protection within a single attempt is the
  `attempt_id`-keyed marker (§7), scoped to that one owner-authorized run, never to the fingerprint.
- **Failure behavior:** trivially fail-open for the application (§11) — a failed warm-up script just means
  the first real request is cold, exactly like today.
- **Multi-client scaling:** run once per `client_id` in `ALLOWED_CLIENTS`, operator-driven — scales
  linearly and explicitly, no automatic fan-out risk.
- **Observability:** logs via `log_llm_usage` with its own `call_type`.
- **Complexity/risk:** **lowest** of any automated-benefit option — a new standalone script analogous to
  the existing `scripts/validate_client_pack.py`, zero changes to `app.py`, zero interaction with
  reloader/multi-worker/import-time concerns by construction.
- **Downside:** requires a human to remember to run it; provides no protection for unattended/automatic
  first-time traffic. Accepted as the correct trade-off for this milestone — see Option C below.

### C. Async startup prewarm after readiness — **DEFERRED to a separate future milestone, not in Phase 2**

Automatic, no manual step, fires on every process start. Real engineering surface (`app.py` changes,
`WERKZEUG_RUN_MAIN` guard, a new runtime env flag, a background thread, reloader/multi-worker design —
§9) is materially larger than B's, and its value is currently unproven — the CLI (B) has not yet been run
even once to confirm real `cached_tokens`/duration benefit. Building C now would mean adding that
complexity to `app.py` before there is any measured evidence it helps. **Deferred, not rejected:** if the
CLI's own live measurements (a future, separately-permitted step) show real, repeatable benefit, a
follow-up milestone can design C properly, informed by that evidence, with its own governance audit. Not
part of this milestone's implementation allowlist in any form — no `app.py` change, no config flag, no
background hook.

### D. Lazy background prewarm after first request — **not selected**

Real incremental value is the weakest of the automated candidates. The owner's own brief states
`cached_tokens` has *already* been observed in production logs **without any deliberate prewarm
mechanism** — meaning ordinary consecutive real turns already appear to implicitly warm the cache for each
other today, at zero extra engineering cost. Option D only fires *after* a first real request has already
occurred — at which point whatever implicit turn-to-turn caching already exists has already had its
chance to start warming things up on its own. D would benefit only turns 2+ of a freshly-cold process for
a client with zero prior traffic — a narrower and already-partially-covered case than the "cold moment
right before a demo" that B directly targets.

### E. Do not implement, if cache semantics cannot be proven — **not chosen**

Not chosen outright, because the specific thing the governing principle demands proof of — **prefix
content identity** — is provable from code today (§2-§7), by disciplined reuse of the exact production
message-builder functions rather than a parallel implementation. What remains unprovable without a live
call (TTL, actual hit behavior, model-alias stability — §8) is explicitly not claimed as proven anywhere
in this audit, and the CLI's live mode requires a separate LIVE/LLM permission before those unknowns are
ever tested for real. E would be the right call only if prefix identity itself could not be guaranteed —
it can be, via reuse discipline, so E is not selected.

## Selected: **B only — owner-controlled CLI, offline-first, two-gate rollout**

- **B (owner-controlled CLI)** is the entire Phase 2 scope. Standalone script, zero interaction with
  `app.py`, zero runtime flag, zero background worker, zero startup-sequence change.
- **C (async startup prewarm) is explicitly deferred** to a separate future milestone, contingent on the
  CLI's own measured live results — not built, wired, or flagged in any form in this milestone.
- **D is not selected** (weak incremental value given already-observed implicit caching); **A is ruled
  out** (unsupported); **E is not chosen** (prefix-content identity is provable).
- **Two-gate rollout (binding):** Phase 2 implementation (the CLI itself, fully exercisable offline via
  dry-run, default action with no `--live` flag) requires owner GO same as any implementation phase.
  **First real (`--live`) activation against the actual provider requires a SEPARATE, explicit owner
  LIVE/LLM permission**, on top of that — matching this codebase's existing pattern for other
  live-provider milestones (A9, S66 in `docs/STRANGLER_ROADMAP.md`).

## 13. Implementation allowlist (Phase 2 — blocked until owner GO; LIVE activation blocked further)

| File | Action |
|---|---|
| `contracts/target_prompt_cache_fingerprint.py` | CREATE — `TargetPromptCacheFingerprint` frozen dataclass (§5) — cache identity only, never used as a lookup/lifecycle key |
| `contracts/target_prompt_cache_attempt.py` | CREATE — `TargetPromptCacheAttempt` frozen dataclass: `attempt_id`, `client_id`, `model`, `composer_fingerprint`, `verifier_fingerprint`, `planned_roles`, `budget` (fixed 2), `retry` (fixed 0), `status`, `started_at`, `completed_at`, `calls_started`, `calls_completed` (§7) |
| `core/target_prompt_cache_prewarm.py` | CREATE — fingerprint computation (pure, including `static_prefix_hash`), dry-run message assembly (reusing `build_composer_sdk_messages`/`build_verifier_sdk_messages` verbatim), the `attempt_id`-keyed exclusive marker mechanism (create-before-first-call, one shared ledger per attempt, no force/reclaim/delete), the live `chat_completions_create` call path (only exercised when the CLI passes `--live`), fail-open/abort-on-mismatch wrapping, `log_llm_usage` call with a new `call_type` |
| `scripts/prewarm_prompt_cache.py` | CREATE — the CLI entry point itself: argument parsing (`client_id`, `--live`, required `--attempt-id` in live mode only, expected model/fingerprint for preflight), dry-run vs. live dispatch, calls into `core/target_prompt_cache_prewarm.py` |
| `tests/test_final_provider_prompt_cache_prewarm_implementation.py` | CREATE — acceptance matrix (§14) |

**Explicitly NOT in this allowlist (governance correction):** `app.py` (no changes of any kind); any
startup/runtime-flag module; `static/widget/*` (no widget involvement); any orchestration/runtime-turn
file (no request-path integration); any background-worker/thread-pool component.

**KEEP unchanged:** `logging_setup.py` (`log_llm_usage` reused, not duplicated); `core/turn_timing.py`
(irrelevant to a standalone CLI); `core/target_composer_executor.py`, `core/target_response_verifier.py`,
`core/target_runtime_llm_messages.py` (reused verbatim, never forked/edited); `app.py`,
`core/startup_check.py` (untouched — no automatic prewarm in this milestone); `/ask`/`/ask/stream` route
parity; LLM call count for every real user turn.

## 14. Acceptance matrix (Phase 2 implementation — minimum coverage, 32 scenarios)

| # | Scenario | Expected |
|---|---|---|
| 1 | First cold request (no prior CLI run) | Application behavior identical to today — no dependency on the CLI ever having run |
| 2 | Dry-run mode | Zero provider calls, zero artifacts (no marker/ledger file, no `attempt_id` required); loads the real client pack; builds real Composer/Verifier messages via the existing builders; prints only hashes/model/role/prefix length/token estimate/fingerprint/planned budget |
| 3 | Dry-run output content | Never prints `corpus_text`, any synthetic answer, contact info, or other client-pack content — hashes and scalar metadata only |
| 4 | Live mode without `--live` | Never calls the provider — `--live` is required, not a default |
| 5 | Live mode missing `client_id` | Refused before any provider call — `client_id` is a required argument |
| 6 | Live mode missing `--attempt-id` | Refused before any marker write or provider call — `attempt_id` is a required argument in `--live` mode only, never auto-generated |
| 7 | Live mode preflight — expected model/fingerprint mismatch | Aborts before any attempt-marker write or provider call |
| 8 | Attempt marker creation | Created via exclusive-create/`O_EXCL`, keyed by `attempt_id` alone (not client_id/role/fingerprint), before the first provider call |
| 9 | Attempt marker required fields | Records `attempt_id`, `client_id`, `model`, `composer_fingerprint`, `verifier_fingerprint`, `planned_roles`, `budget=2`, `retry=0`, `status`, `started_at`/`completed_at`, `calls_started`/`calls_completed` |
| 10 | Composer warm call | Exactly one, via `build_composer_sdk_messages` verbatim |
| 11 | Verifier warm call | Exactly one, via `build_verifier_sdk_messages` verbatim |
| 12 | One shared ledger per attempt | Composer's and Verifier's call records both land in the same attempt marker/ledger file — never two separate per-role files |
| 13 | Total call budget | Never more than 2 provider calls in one attempt (1 Composer + 1 Verifier) |
| 14 | `retry=0` | Exactly one attempt per provider call, no internal retry loop |
| 15 | Abort after unexpected provider/model mismatch | The remaining planned call (e.g. Verifier, if Composer's result was unexpected) is not attempted; `status` becomes `"aborted"`/`"failed"` |
| 16 | Reusing the same `attempt_id` | Forbidden — a second attempt with an already-used `attempt_id` fails at the marker-creation step, before any provider call |
| 17 | New `attempt_id` for an unchanged fingerprint (simulated TTL-expiry re-warm) | Succeeds without friction — the unchanged fingerprint never blocks a fresh, differently-`attempt_id`'d attempt; this is the core fix this correction verifies |
| 18 | Crash/partial attempt (process killed mid-attempt, simulated) | Marker remains in its last-written, non-`"completed"` status forever; that `attempt_id` is permanently consumed; no auto-resume |
| 19 | No `--force`/reclaim/delete mechanism | Confirmed absent anywhere in the CLI or its supporting module — no code path exists to reopen, delete, or override a consumed marker |
| 20 | Warm response content discarded | Provider's actual answer/issues content is never written to session, never shown to any user, never persisted as answer text |
| 21 | Marker/ledger persists only anonymized metadata | The fields in row 9, plus `cached_tokens` (if present) per call — no corpus/answer content |
| 22 | Fingerprint recorded for audit only | `composer_fingerprint`/`verifier_fingerprint` appear inside the marker as descriptive data; the marker's file path/key is `attempt_id` alone, never the fingerprint |
| 23 | Composer/Verifier namespaces proven distinct | Same `client_id`, same corpus — Composer and Verifier fingerprints differ (§3, §5) |
| 24 | Two `client_id`s produce distinct fingerprints | No cross-client reuse assumed |
| 25 | Message/token prefix identity (offline proof) | The CLI's assembled static prefix equals what a real Composer/Verifier call would build, up to the dynamic boundary — verified by direct comparison in a test, not claimed as HTTP wire-byte identity |
| 26 | Tests/CI run | Zero real provider calls anywhere, zero marker/ledger artifacts created — dry-run path and any test invocation of the CLI module never reach `chat_completions_create` |
| 27 | No PII/session in CLI payload, logs, or marker | Dynamic-tail fields are fixed non-PII placeholders (§7), never derived from any real request/session/SID/phone |
| 28 | `cached_tokens` sourced from provider usage (live-gated) | Read via the existing `_cached_tokens_from_usage_obj`/`log_llm_usage` path (`logging_setup.py:238-248,272-288`) — no second usage-parsing implementation |
| 29 | Automatic startup prewarm not exercised | No `app.py` change, no config flag, no background hook exists anywhere in this milestone's diff |
| 30 | Client-pack validation unchanged | `scripts/validate_client_pack.py`'s behavior/output is unaffected by any prewarm code (no shared state, no import coupling) |
| 31 | Stale fingerprint never considered warm | A fingerprint computed before a tracked component changed is never treated as still-valid after the change — no grace period, no partial match |
| 32 | Attempt marker does not imply provider warmth | A `"completed"` marker proves only that its specific authorized attempt ran and finished — it is never read anywhere as evidence the provider's cache is still warm; only a live `cached_tokens` measurement proves that |

## STOP

After PRE-CODE ✅ — **STOP**. Phase 2 implementation (the CLI, offline-first) only after a separate owner
GO, and even then, first real `--live` activation against the provider requires a further separate owner
LIVE/LLM permission (§8, §12).

## Test commands (governance)

```powershell
python -m pytest tests/test_final_provider_prompt_cache_prewarm_governance.py -q
python -m pytest tests/test_final_response_latency_observability_governance.py tests/test_final_early_sse_status_streaming_governance.py tests/test_final_safe_medical_boundary_bypass_governance.py -q
git diff --check
```
