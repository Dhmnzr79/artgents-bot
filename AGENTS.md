# Repository working agreement

This file is the permanent workflow contract for Codex, Cursor, and human contributors.
Task-specific acceptance criteria belong in the current task or PR, not here.

## Deployment reality — non-negotiable

**This repository has no production bot and no production users.** The current
local `/ask` and `/ask/stream` route is a disposable baseline for comparison,
not a production-compatibility target.

- A task may replace or break the local normal-dialogue runtime when that is
  necessary for the agreed result. Preserve only explicitly named external
  contracts, tenant data, and lead/privacy boundaries.
- Do **not** assume production migration, user-data compatibility, dual-run,
  per-request fallback, release rollback, or protection of the current local
  semantic route unless the owner explicitly says that a production deployment
  exists and places it in scope.
- Reports must distinguish a local baseline from a deployed, user-facing bot.
  Never cite the existence of the local route as a reason to defer a clean
  semantic replacement.

## Workspace model

- One active task equals one `codex/<slug>` branch in the permanent repository folder and one editor window.
- Keep `main` clean and read-only for development; switch to the task branch in the same folder before editing.
- Create every task from a freshly fetched `origin/main`.
- Never switch a dirty checkout to another task. Preserve old registered worktrees until separately verified and removed with `git worktree remove`.

## Mandatory preflight

Before editing, report:

- absolute repository path and Git top level;
- branch, HEAD, `origin/main`, and merge base;
- concise status including untracked files;
- explicit task baseline and exact file allowlist;
- any pre-existing or foreign WIP.

Stop if the folder, branch, baseline, or task do not match.

## Editing and Git safety

- Preserve all work outside the declared allowlist.
- If a necessary edit falls outside the allowlist, explain it before staging.
- Never use `git add .` or `git add -A`; stage exact paths only.
- Before commit, inspect staged names, stat, diff, and `diff --check`.
- Never commit secrets, `.env`, provider payloads containing private data, local databases, or raw patient conversations.
- Do not merge, deploy, make live provider calls, or perform destructive cleanup without explicit authority.
- A paused task must have a named checkpoint commit pushed to its remote branch.

## Verification

- During implementation, run the smallest targeted offline tests that cover the change.
- Run one independent Checker review when a coherent checkpoint is ready.
- After a REJECT, run a focused recheck of the findings; do not restart a full review unless scope changed materially.
- Run the repository CI set before merge, not after every small edit.
- Compare failures with a clean baseline before labeling them regressions.
- Live/provider tests require explicit owner approval and a hard call budget.

## Completion report

Report the branch, commit, changed files, tests, known baseline failures, provider calls,
staging state, push/PR state, and remaining foreign WIP. A report is evidence to verify,
not permission to merge or deploy.

See `docs/WORKFLOW_GIT.md` for commands and `docs/WORKFLOW_CHECKER.md` for review rules.
