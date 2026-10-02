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

### Architecture simplification — mandatory acceptance

- Fix the general mechanism, never a particular phrase or message sequence.
  Explain the class of requests covered. Do not invent product behavior,
  offer-selection policy, missing-data semantics or context carry rules.
  Show unresolved behavior with an example before implementing it.
- New scenario branches, semantic heuristics, fallback, model calls, control
  fields, parallel memory or one layer repairing another layer's decision
  require separate agreement. First examine removal of the original cause.
  Established tenant, price, UI authenticity, medical and lead/privacy
  protections are requirements, not inherently unwanted complexity.
- For D2 architecture questions consult Astra; its advice does not authorize
  product or responsibility changes. Stop only dependent work when a new owner
  decision is needed; discuss it in ordinary chat. Within agreed boundaries,
  perform routine technical work independently.

- For D2, use the single responsibility table in
  `docs/tasks/DEMO_D2_TARGET_CONTRACT.md` §3. Apply it to every changed path;
  do not copy the table into task cards or ask the owner to approve it again.
- Before implementation, state in the existing card/report whether the change
  is architecture simplification, a bug fix, or documentation only. For
  simplification, give a concrete **before → after → removed dependency**,
  name the sole decision owner, and identify the old reachable decision paths
  to remove. A bug fix need not remove a decision; do not call it simplification.
- A narrower card or passing scenario cannot replace the agreed architecture
  objective. Stop before edits that change agreed responsibility, product
  behavior, or scope; discuss the conflict with examples in ordinary chat,
  not a popup. Routine choices within the agreed scheme need no new approval.
- Independent Checker and any Cursor review must trace the actual call path
  and verify both removal of the claimed dependency and complete dialogue
  behavior, including adverse model outputs. Hiding the dependency behind a
  new condition, prompt instruction, retry, or another layer is not removal.
- Missing architectural evidence or a contradictory changed path blocks PASS.
  Follow `docs/WORKFLOW_CHECKER.md`; no extra document or approval round is
  required. Unrelated existing debt remains explicitly scoped, not silently
  declared fixed. Report bug-fix success separately from architecture success.

- During implementation, run the smallest targeted offline tests that cover the change.
- Run one independent Checker review when a coherent checkpoint is ready.
- After a REJECT, run a focused recheck of the findings; do not restart a full review unless scope changed materially.
- Run the repository CI set before merge, not after every small edit.
- Compare failures with a clean baseline before labeling them regressions.
- Live/provider tests require explicit owner approval and a hard call budget.

## Audit change-map discipline

- Follow the owner-approved change map and its current task, in sequence.
  For D2 the canonical map is `docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md`,
  section "Актуальный порядок после независимого аудита — 2026-10-02";
  the nearest task is `docs/tasks/DEMO_D2_INTERFACE_TASK.md`.
  Audit findings are proposals, not automatic implementation authority.
- Do not independently change product behavior, architecture, agreed limits
  or task scope. Routine technical choices within the approved boundaries
  remain the implementer's responsibility.
- Do not add fields, states, handlers, scenario branches, layers or model
  calls absent from the approved map/task without separate owner agreement.
  Updating the task yourself does not authorize such an addition.
- A replacement must remove the old reachable structure. Do not retain
  parallel mechanisms, transitional converters or a new-to-old contract
  adapter without explicit agreement. Fix the general mechanism, never
  conditions for a particular user phrase or question sequence.
- Before deviating, explain the concrete cause, smallest alternative and
  consequences in ordinary chat. Stop dependent changes until agreed;
  continue independent work already authorized. No new approval document
  or popup is required.
- After each stage report what was removed, what was added and why, whether
  behavior changed, evidence and remaining risks. Separate offline evidence
  from live model/widget evidence. Simplification means fewer decisions,
  duplicates and dependencies while preserving agreed quality/protections;
  extra prompt instructions alone do not qualify.

## Completion report

Report the branch, commit, changed files, tests, known baseline failures, provider calls,
staging state, push/PR state, and remaining foreign WIP. A report is evidence to verify,
not permission to merge or deploy.

See `docs/WORKFLOW_GIT.md` for commands and `docs/WORKFLOW_CHECKER.md` for review rules.
