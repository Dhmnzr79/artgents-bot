# Local admin workspace — 2026-11-10

Owner authorized first draft of admin navigation, dialogues, errors and metrics.
Baseline: origin/main 514ce61ef7ba8e07e18a829c92d43fc0b40e931d.
Branch: codex/admin-workspace. Clean checkout; existing stashes are out of scope.
Classification: admin usability / diagnostic bug fixes, not bot architecture simplification.
Allowlist: admin_dashboard/{app.py,repository.py,templates/index.html,static/dashboard.js,static/dashboard.css}; tests/test_d2_admin_dashboard.py; tests/js/admin_workspace.mjs; this document.
No bot runtime changes, DB writes/migrations, provider calls, commit/push or VPS deployment.
Acceptance: split dialogue workspace, section navigation, search/date/error filters, activity ordering, previous/next, preserved selection; tenant-safe read-only summaries and partial failure evidence; linked errors/leads; coherent periods and missing-data labels; responsive layout and safe text rendering.
Verification: targeted admin offline tests, JS syntax/behaviour check, local browser inspection, independent Checker per AGENTS.md.

## Completed first draft

Removed the overlapping two-column card grid and below-list dialogue viewer.
Added four sections, split list/thread workspace, safe first-question previews, question/action counts, activity ordering, question/ID search, activity-period and technical-problem filters, previous/next loaded dialogue, explicit loading/selection, preserved navigation on refresh, mobile list/thread view, linked leads and technical events, partial failure evidence on saved turns, readable bold text without HTML execution.
Statistics distinguish lifetime storage counts from period telemetry; model-call tokens/costs remain provider snapshots; cache percentage uses known split input tokens; average completed-request time is distinct from model latency. Missing price data is informational, not a technical failure.
No changes to bot behaviour, prompts, provider configuration, prices, KB, data schema or stored conversations. Admin remains read-only with existing authentication, tenant validation, no-store headers and privacy projection.

Verification:
- Independent Checker: PASS; 37 targeted offline tests (dashboard, tenant/access, schema).
- node tests/js/admin_workspace.mjs: PASS (stale tenant/search/thread responses, safe formatting, refresh navigation and turn cursor).
- node --check dashboard.js and git diff --check: PASS.
- Local browser: desktop list/thread, next dialogue, statistics, 390px mobile list/thread, refresh preserving selected dialogue.
- Initial test invocation could not create sandbox's default temporary directory; rerun using workspace --basetemp succeeded. No baseline test failures identified; existing datetime.utcnow warnings remain.
- One new test initially used an obsolete fake-provider envelope; corrected to actual current text+action fixture; passed. Production runtime untouched.
- Live provider calls: 0. VPS/deploy/CI runs: 0. Local admin alone restarted to load Python and cached HTML changes.

Known draft limits:
- Activity-sorted OFFSET paging can skip a moved session if new activity changes ordering between page loads; refresh the list for a consistent current view.
- Previous/next traverses loaded filtered results; load more to extend the queue.
- Error-to-turn lookup is capped at ten pages; older turns can be loaded manually. A request failing before public publication has no saved answer to show.
- Old telemetry lacks diagnostic reasons; panel explicitly says so. Read-only price-card details remain formatted saved text, not interactive copies of the widget.
- Search covers privacy-filtered user questions and session hashes, not assistant answers. Dates are browser local; period boundaries explicitly UTC.

Git: codex/admin-workspace; HEAD/baseline 514ce61ef7ba8e07e18a829c92d43fc0b40e931d. No new commit, staging, push or PR. Changed files are the five allowlisted admin files, tests/test_d2_admin_dashboard.py, tests/js/admin_workspace.mjs and this card. Foreign stashes untouched.

## Release authorization
Owner explicitly approved VPS deployment after the light-theme logo correction (2026-11-10). Final scope additionally includes static/logo-light.svg; existing logo geometry and blue fill preserved. Subsequent visual polish adds semantic KPI accents, SVG icons, cost/cache summary and dark/light palettes; calculations and bot code remain unchanged. Theme preference alone is stored in localStorage, never dialogue data.
Release uses the existing CI → publish → manual deploy workflow, retaining named volumes. Shared image deployment recreates bot/admin containers; bot source/config/KB unchanged from 514ce61. No migration or data replacement.
