# PERF-3 — FINAL_PROVIDER_PROMPT_CACHE_PREWARM — live attempt audit

**Дата:** 2026-07-30
**Baseline:** `codex/stage-a` @ `f8db2e0` (pre-authorization) → `64fd54c` (pre-live authorization commit)
**Owner GO:** exact-attempt LIVE/LLM GO, `attempt_id = perf3-demo-2026-07-30-01`, `client_id = demo`,
Composer/Verifier model `qwen3.7-plus`, Composer calls ≤1, Verifier calls ≤1, total provider calls ≤2,
retry=0. Ran exactly once, per owner instruction; no retry, no new attempt_id, no repeated `--live` call.

## Preflight (all matched before running live)

- Branch `codex/stage-a`, expected HEAD `f8db2e0`, HEAD == `origin/codex/stage-a`, working tree clean,
  `.prewarm_ledger/attempts/perf3-demo-2026-07-30-01.json` absent — all confirmed before any change.
- Dry-run (`python scripts/prewarm_prompt_cache.py --client-id demo`) made 0 provider calls, 0 artifacts,
  and produced the fingerprints used below.
- Composer fingerprint: `aeb519f43eb9b4eb9cb4f2dfdf2c48cd34ead754b2edd0225857b5aa084980d4`
- Verifier fingerprint: `44999fefb2810dcf4dfb6ae6d7cbc1a69159cda1c9cd99a21b9853bfeb99d41a`
- Re-ran the same dry-run after the gate-change commit: identical fingerprints (code change did not
  alter message construction).

## Pre-live authorization commit

`64fd54c` — replaced `LIVE_ACTIVATION_AUTHORIZED` (blanket bool) with `LIVE_AUTHORIZED_ATTEMPT_ID: str |
None`, set to the single exact string `perf3-demo-2026-07-30-01` for this attempt only. `run_live` gates
on `request.attempt_id == LIVE_AUTHORIZED_ATTEMPT_ID`; any other attempt_id remains `LIVE_OUTCOME_BLOCKED`
before any marker write or provider call. Added three offline tests: gate closed (`None`) blocks every
attempt_id; a non-matching attempt_id is blocked even while a different one is authorized; the exact
authorized attempt_id passes the gate (proven with a fake transport, no network). No runtime, prompt, or
client-data files touched. Pushed to `origin/codex/stage-a` before the live call.

## Live command (ran exactly once)

```
python scripts/prewarm_prompt_cache.py --client-id demo --live \
  --attempt-id perf3-demo-2026-07-30-01 \
  --expected-composer-model qwen3.7-plus --expected-verifier-model qwen3.7-plus \
  --expected-composer-fingerprint aeb519f43eb9b4eb9cb4f2dfdf2c48cd34ead754b2edd0225857b5aa084980d4 \
  --expected-verifier-fingerprint 44999fefb2810dcf4dfb6ae6d7cbc1a69159cda1c9cd99a21b9853bfeb99d41a
```

Exit code: `0`.

## Attempt marker / ledger (`.prewarm_ledger/attempts/perf3-demo-2026-07-30-01.json`)

| Field | Composer | Verifier |
|---|---|---|
| requested_model | qwen3.7-plus | qwen3.7-plus |
| configured_model | qwen3.7-plus | qwen3.7-plus |
| observed_model | qwen3.7-plus | qwen3.7-plus |
| status | completed | completed |
| duration_ms | 5194.666 | 2550.791 |
| prompt_tokens | 32256 | 32035 |
| completion_tokens | 16 | 4 |
| total_tokens | 32272 | 32039 |
| cached_tokens | 0 | 0 |

Attempt-level: `attempt_id=perf3-demo-2026-07-30-01`, `client_id=demo`, `budget=2`, `retry=0`,
`status=completed`, `calls_started=2`, `calls_completed=2`, `started_at=2026-07-30T09:38:33.573765+00:00`,
`completed_at=2026-07-30T09:38:41.489094+00:00`. Composer and Verifier fingerprints recorded in the
marker match the dry-run fingerprints above exactly. No corpus text, no answer/response content, no
session id, no PII present in the marker (verified by reading the marker file directly — response
`.choices` content was never read by the prewarm code, only `.model`/`.usage`, per
`test_marker_content_has_no_corpus_or_pii` and the `_FakeResponse.choices` trap in the offline suite).

## What this attempt does and does not prove

Both calls completed successfully with the exact requested/configured/observed model on both roles, and
both stayed within budget (2/2, retry=0, no mismatch, no abort). This proves the CLI wiring, model-pin
and fingerprint preflight, ledger, and provider transport work end-to-end against the real provider.

`cached_tokens=0` on both calls is **expected, not a failure**: this was the first-ever warm call for
this exact fingerprint under this attempt — there was nothing previously cached to hit. This attempt
therefore does **not** by itself prove the prompt-cache prewarm delivers any latency/cost benefit. That
can only be measured by a **subsequent, separate, real user request** through the widget hitting the same
Composer/Verifier static prefix and observing non-zero `cached_tokens` and/or reduced duration relative
to this baseline — not part of this attempt, not run as part of this owner GO (no `/ask`, no widget call
was made here).

## Verdict

**`LIVE_ATTEMPT_COMPLETED_PENDING_REAL_REQUEST_MEASUREMENT`**

Not `LIVE_ATTEMPT_FAILED` (both calls completed, exit 0). Not `MODEL_MISMATCH` (requested == configured ==
observed on both roles). Not `PREFLIGHT_ABORT` (preflight passed; the run proceeded to the provider).
PERF-3 is **not** declared successful by this attempt alone — actual benefit is pending the next real
Composer/Verifier request's `cached_tokens`/duration, compared against this attempt's baseline
(`prompt_tokens` 32256/32035, `cached_tokens` 0/0, `duration_ms` 5194.666/2550.791).

## Closeout

Immediately after this audit is committed, the gate is closed: `LIVE_AUTHORIZED_ATTEMPT_ID = None`. A
new offline test proves that replaying the exact same `attempt_id` (`perf3-demo-2026-07-30-01`) is
blocked once the gate is closed, and that the on-disk marker for this attempt_id makes any future
attempt with the same id fail with `PrewarmAttemptReuseError` before any new provider call, on this
machine or after a fresh checkout elsewhere (the marker file is committed as immutable evidence).
