# D2 local full audit — demo-only diagnostic checkpoint

Date: 2026-09-26. Status: offline-reviewed checkpoint; local activation pending. Owner explicitly requested complete
local demo traces, including test personal data. This is diagnostic evidence, not
permission for a live provider call, merge, deployment, or deletion of old logs.

## Baseline and scope

- Active folder and Git root: `C:\Cursor Projects\artgents-bot-active`.
- Branch: `codex/d2-stage1-contract`; baseline: `bc7616999ed9fa2a9a3f74a3e7bdc8b47ba0e171` (REC-2 checkpoint).
- `origin/main` and merge base at preflight: `141ce91fb1731cd990fcf8391550150016c73e7f`.
- Tracked worktree/staging clean before this checkpoint; foreign untracked `data/` stays untouched.
- Historical reference only: `C:\Cursor Projects\artgents-bot` at `b8b28d3`, including `core/d2_full_audit.py`. Do not restore its dialogue/HTTP runtime.

Write allowlist:

```text
app.py
core/d2_http_adapter.py
core/d2_live_provider.py
core/d2_dialogue.py
core/d2_diagnostics.py
core/d2_full_audit.py                   # new
tests/test_d2_full_audit.py             # new
docs/tasks/DEMO_D2_FULL_AUDIT_TASK.md   # new
docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md
docs/tasks/DEMO_D2_CHECKPOINT_LEDGER.md
```

`data/`, tenant packs, SQLite, parser, materializer, store/schema, widget, launcher,
`.env`, `.venv` and existing app logs are read-only. No semantic route, state,
frozen answer, UI or lead-effect changes. Existing REC-1 safe diagnostics remain.

## Contract

`D2_FULL_AUDIT_LOG=1` enables one local JSONL transcript under `BOT_LOG_DIR`
(`logs/d2_full_audit.jsonl` by default). It is off without the explicit flag and
always off for `APP_ENV=prod|production`. It is not served by the dashboard and
`logs/` is Git-ignored. It records complete demo input, including name/phone/lead
turns, exact prompt and provider output when a provider runs, parsed/effective
envelope, selected UI action, source/frozen response, state transition, commit,
effect, replay, HTTP JSON/SSE result and error/disconnect. One attempt ID links
events with REC-1. No second model/parser/materializer/store operation is allowed.

Credential-looking keys and bearer tokens are redacted, but **patient/test
personal data is intentionally not redacted**. Never pass headers, cookies,
environment or transport credentials to this logger. Writer/serialization failure
must not change a bot answer, exception, state, effect or replay. The transcript
is local debug data, not an application/analytics event. No raw transcript is
committed or pushed.

Before any production use: disable the flag, verify it stays off, and separately
remove or protect prior local transcript files and their copies/backups. Merely
disabling the flag does not erase previously recorded personal data.

## Offline acceptance

- JSON and SSE ordinary content, exact price/mixed answer and typed widget click:
  one linked trace has ingress, model messages/raw, parsed/effective envelope,
  frozen response/UI, commit, and exact public payload.
- Pre-provider lead turn with synthetic name/phone has full ingress/response and
  state/effect evidence, with no fabricated model call.
- Replay returns the same saved answer with no new provider call; failure before
  commit, failure after commit/framing, and SSE disconnect retain honest events.
- Disabled and prod modes write no full transcript. Credentials are scrubbed;
  synthetic personal data remains visible only in the opt-in transcript, not in
  the existing safe diagnostic/app channel.
- Broken transcript writer cannot alter success, error identity, rollback,
  commit/effect count or SSE close behavior. Concurrent attempts do not mix.

Use fake provider, temporary DB/log/tenant copies and no network. Run focused
offline tests plus existing HTTP/SSE, lead, replay and no-legacy regressions.
Independent Checker and Cursor must review the implementation before claiming
the checkpoint complete. Historical REC-2 PASS does not apply to this change.

Post-review evidence: `tests/test_d2_full_audit.py` 15 passed. A related offline
regression run (before the final credential vocabulary extension) had 71 passed;
the added token/body/effect targeted checks passed separately (3 passed).
Independent focused Checker PASS and owner-supplied Cursor read-only PASS were
reported separately after the diff review. Neither review authorizes live calls,
merge, deploy, or automatic activation of this opt-in logger.
