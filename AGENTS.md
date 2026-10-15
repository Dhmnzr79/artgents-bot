# Repository working agreement

This file is the permanent workflow contract for Codex, Cursor, and human contributors.
Task-specific acceptance criteria belong in the current task or PR, not here.

## Deployment reality — non-negotiable

**A demo bot is deployed on a VPS (owner confirmed 2026-10-13).** Real
production-user traffic and migration requirements have not been placed in scope.
The local `/ask` and `/ask/stream` remain the development/test checkout, distinct
from the deployed demo.

- Preserve explicitly agreed tenant, lead/privacy, price/UI and transport boundaries.
  Local runtime changes must follow the current authorized task; no implied legacy
  compatibility, dual-run, per-request fallback or user-data migration is required.
- Do not merge or deploy without explicit owner authority. A topic-branch push is
  not a VPS deployment. Documentation/test cleanup does not modify the deployed bot.
- Reports must distinguish local checks, GitHub build/deploy evidence and actual
  deployed dialogue verification. Do not infer production-user guarantees from demo.

## Workspace model

- One active task equals one `codex/<slug>` branch in the permanent repository folder and one editor window.
- Keep `main` clean and read-only for development; switch to the task branch in the same folder before editing.
- Create every task from a freshly fetched `origin/main`.
- Never switch a dirty checkout to another task. Preserve old registered worktrees until separately verified and removed with `git worktree remove`.

## Mandatory preflight

At the start of a task or substantive stage, before editing, report:

- absolute repository path and Git top level;
- branch, HEAD, `origin/main`, and merge base;
- concise status including untracked files;
- explicit task baseline and exact file allowlist;
- any pre-existing or foreign WIP.

Stop if the folder, branch, baseline, or task do not match.
Within the same stage, do not repeat the full preflight for every message or
small edit. Recheck it if the checkout, scope, baseline or foreign WIP changes.

## Editing and Git safety

- Preserve all work outside the declared allowlist.
- If a necessary edit falls outside the allowlist, explain it before staging.
- Never use `git add .` or `git add -A`; stage exact paths only.
- Before commit, inspect staged names, stat, diff, and `diff --check`.
- Never commit secrets, `.env`, provider payloads containing private data, local databases, or raw patient conversations.
- Do not merge, deploy, make live provider calls, or perform destructive cleanup without explicit authority.
- A paused task must have a named checkpoint commit pushed to its remote branch.

## Verification

### Verification cadence — stages, not individual edits

- A stage is a coherent deliverable: one substantive change or a batch of related
  small edits. A user message, file save, wording correction or CSS adjustment
  does not by itself start a new stage or require another review.
- For small text/content edits, typo fixes, labels and cosmetic CSS adjustments
  that do not change runtime logic, data contracts, references or protection
  mechanisms, read the affected text/diff and finish the edit. Do not launch
  Checker, test suites, browser runs, repository-wide audits or protected-file
  hash scans after each such edit. Do not create a separate task-card section,
  evidence report or checkpoint just to record a micro-edit. Record related
  changes together when the stage is complete.
- Batch simple edits and run only relevant checks once at the end of the block,
  when those checks can detect a plausible error. For prose-only changes, reading
  the final text/diff is normally enough. Check syntax, schema or references when
  the edit affects them. Do not add tests that merely repeat the edited wording.
- Use targeted offline tests for substantive code/behavior changes at meaningful
  checkpoints. Run one independent Checker for a completed substantive stage
  involving runtime logic, architecture, contracts, tenant isolation,
  lead/privacy, prices, transport or a broad cross-file restructuring. A batch
  of simple content/cosmetic edits does not automatically require Checker;
  use it when the owner requests review or the scope introduces a concrete
  integration risk. Never spawn a reviewer solely because another small edit
  has been made.
- After checks pass, repeat only checks affected by a new change or an unresolved
  finding. Do not rerun a full review or CI for punctuation or other unrelated
  cosmetic corrections. Required release/merge checks and protections remain
  in force. Judge scope by what the change affects, not by its character count.
- Apply this cadence to the checkpoint/review instructions below and in
  `docs/WORKFLOW_CHECKER.md`; those instructions do not require review per edit.

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
- Before a substantive implementation stage, state in the existing card/report whether the change
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

- For substantive implementation stages, run the smallest targeted offline tests
  that cover the change at meaningful checkpoints, following the cadence above.
- Run one independent Checker review for a completed stage that requires it
  under the cadence above, not for each individual edit or user message.
- After a REJECT, run a focused recheck of the findings; do not restart a full review unless scope changed materially.
- Run the repository CI set before merge, not after every small edit.
- Compare failures with a clean baseline before labeling them regressions.
- Live/provider tests require explicit owner approval and a hard call budget.

## Audit change-map discipline

- Follow the owner-approved change map and its current task, in sequence.
  For D2 the canonical map is `docs/tasks/DEMO_D2_DELIVERY_ROADMAP.md`,
  section "Текущая очередь — owner GO 2026-10-13: документация и тесты";
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

For a substantive stage, report the branch, commit, changed files, tests, known baseline failures, provider calls,
staging state, push/PR state, and remaining foreign WIP. A report is evidence to verify,
not permission to merge or deploy.
For a micro-edit, give a short confirmation of what changed; do not repeat the
full technical report or create additional reporting files for it.

See `docs/WORKFLOW_GIT.md` for commands and `docs/WORKFLOW_CHECKER.md` for review rules.
