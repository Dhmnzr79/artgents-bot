# Admin call counts — 2026-11-10

Type: admin observability bug fix / missing statistics, not bot architecture simplification.
Owner requested counts of answers using one/two model calls, plus per-turn evidence.
Baseline: e6db5995b3cbc3214b03dfe8bf2f12bf86851333; branch codex/admin-call-counts.
Allowlist: admin_dashboard/repository.py, admin_dashboard/static/dashboard.js,
tests/test_d2_admin_dashboard.py, this file. Clean initial checkout; no foreign WIP.

Read existing telemetry only. Exact event attempt joins separate failed requests and
replays from completed attempts. Completed-at timestamp defines the period; calls
crossing its start are included. Tenant, session and request identity must match.
Display 0/1/2/>2 observed calls and the two-call percentage of completed attempts
(including interface actions). Per saved turn, use latest completed attempt, never
replay or failed-attempt calls. Missing request telemetry is unknown, not zero.
No phase field exists: counts cannot prove architectural second-stage usage or SDK
internal retries. Zero recorded provider events can also mean incomplete telemetry.
Explain these limits in UI. No bot changes, schema migration, data writes, model
calls, commit/push/merge or VPS deployment in this stage.

Verification: targeted admin, tenant and schema offline tests; JS workspace regression
and syntax checks; independent Checker. No live model calls.

Completed: added readonly aggregation and per-turn metrics, no existing runtime
decision paths removed or changed. 38 admin/tenant/schema offline tests PASS;
JS workspace regressions, syntax and diff whitespace checks PASS. Independent
Checker PASS; corrected minor wording to avoid implying all failed attempts
preceded success. Existing datetime.utcnow warnings only. Local admin restarted,
live local costs endpoint returns new breakdown. No provider calls or VPS changes.
Changes remain unstaged/uncommitted; no push/PR; no foreign WIP.

## Owner extension: current knowledge size

Admin-only observability addition, not architecture simplification. Same baseline
and branch; earlier call-count WIP preserved. Newly observed untracked data/ is
runtime data, outside allowlist and untouched. Additional allowlist:
admin_dashboard/knowledge_stats.py, admin_dashboard/app.py,
admin_dashboard/templates/index.html, tests/test_admin_knowledge_stats.py;
dashboard.js and this card remain in scope.

Show current document/service/offer counts, source pack bytes and ordinary first
request system + tools characters using the actual prompt builder, without invoking
the provider or reading dialogues. Refresh recomputes current pack; no persistent
cache or database mutation. Show broad heuristic 2–4 chars/token explicitly, not an
exact tokenizer or billing amount. Exclude user/history/API envelope/second tool
result and distinguish current configuration from period metrics. Existing auth,
tenant allowlist and no-store guards protect new endpoint. No changes to bot or VPS.

Extension evidence: 41 targeted offline tests PASS, JS workspace regressions and
syntax/diff checks PASS, independent Checker PASS. Existing datetime.utcnow
warnings only. Local admin restarted; /api/knowledge demo returns 61 documents,
23 services, 33 offers, 122163 system characters + 3023 tool characters. No paid
calls, schema/data changes, commit/push or deployment. All WIP remains unstaged.

## Owner checkpoint: 2026-11-10

Owner authorized commit and topic-branch push of this completed stage and recording
the optimization direction. Cosmetic follow-up adds dashboard.css to the allowlist:
knowledge breakdown is a table, four cards share a desktop row with responsive
stacking. Syntax and whitespace checks passed; no new runtime behavior after
the completed Checker review. Earlier uncommitted/no-push statements describe
the preceding stage, not this authorized checkpoint. Runtime data/ stays excluded.
The optimization discussion is recorded in BOT_OPTIMIZATION_DIRECTION_20261110.md;
it does not implement or deploy changes to the bot.
