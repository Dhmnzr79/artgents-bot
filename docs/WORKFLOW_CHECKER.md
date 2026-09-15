# Checker contract

Checker is an independent, read-only review of one completed checkpoint.

## Inputs

The task must state the baseline, exact allowlist, acceptance criteria, intended tests, and
known foreign WIP. Source priority is: current task, this repository agreement, then explicitly
named current architecture documents. Historical reports are context, not authority.

## Review

Checker must:

1. Confirm repository path, branch, HEAD, baseline, staging state, and untracked files.
2. Review only the checkpoint diff while identifying out-of-scope edits and foreign WIP.
3. Read changed tests before production code and reject weakened, skipped, or dishonest tests.
4. Check product invariants and security boundaries named in the task.
5. Run only proportional offline tests requested for the checkpoint.
6. Confirm live/provider call count and inspect staged paths if staging is part of the request.
7. Separate pre-existing baseline failures from checkpoint regressions.

Checker must not edit, format, stage, commit, push, merge, deploy, or make provider calls.

## Verdict

Return exactly one verdict:

- `PASS` — no blocking checkpoint finding remains.
- `REJECT` — list concrete P0/P1 blockers with file and evidence.

P2 observations are non-blocking unless the task explicitly elevates them. After a correction,
recheck only the rejected findings and any materially changed scope.

The report must include branch/HEAD/baseline, reviewed allowlist, findings, test results,
provider calls, staging state, and foreign WIP.
