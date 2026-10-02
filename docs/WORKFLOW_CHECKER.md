# Checker contract

Checker is an independent, read-only review of one completed checkpoint.

## Inputs

The task must state the baseline, exact allowlist, acceptance criteria, intended tests, and
known foreign WIP. Read this repository agreement first. For D2, follow the source
priority in `docs/tasks/DEMO_D2_EXECUTION_LOCK.md` §6; a task card cannot weaken
the agreed architecture objective. Historical reports are context, not authority.

## Review

Checker must:

1. Confirm repository path, branch, HEAD, baseline, staging state, and untracked files.
2. Review the checkpoint diff and its reachable callers/callees needed to verify
   the claim, while identifying out-of-scope edits and preserving foreign WIP.
3. Read changed tests before production code and reject weakened, skipped, or dishonest tests.
4. Check product invariants and security boundaries named in the task.
5. Run only proportional offline tests requested for the checkpoint.
6. Confirm live/provider call count and inspect staged paths if staging is part of the request.
7. Separate pre-existing baseline failures from checkpoint regressions.

Checker must not edit, format, stage, commit, push, merge, deploy, or make provider calls.

## Architecture evidence — applies to Checker and Cursor

### Mandatory change-map check

Apply AGENTS.md "Audit change-map discipline". For D2 compare the actual diff
with the dated current map in DEMO_D2_DELIVERY_ROADMAP.md and its current task;
read their paths under docs/tasks/. A finding or an executor's edit to the
task is not owner approval. Check the agreed sequence and scope.

REJECT an unapproved change to behavior, architecture or constraints; an
unplanned field/state/handler/scenario branch/layer/model call; retained
parallel mechanisms or a transitional new-to-old adapter; or a phrase-specific
patch presented as the general solution. A documented owner-approved exception
must name its scope; it does not authorize further departures.

For each claimed replacement identify the deleted structure and verify that
its decision is not reachable elsewhere. Require the stage report to list
removals, additions with their agreed reason, behavior changes, checks and
risks. Distinguish offline, live-model and widget evidence. A larger prompt,
passing fixtures or fewer lines alone do not demonstrate simplification.
Apply this check in the existing review, without adding another review round.

Check the current Roadmap section and its approved product decisions, not
historical GO/Draft text. Reject invented product behavior or phrase-specific
fixes presented as general simplification. Verify the request class covered,
preserved medical/price protections, and that any added scenario/control field,
heuristic, fallback, model call or parallel memory was explicitly agreed.

For D2 use the sole responsibility table in
`docs/tasks/DEMO_D2_TARGET_CONTRACT.md` §3 (repository-relative). Do not request a new architecture document,
an unrelated refactor, or renewed approval for the already agreed scheme.

The existing card/report must distinguish simplification, bug fix, and
documentation. For simplification, review **before → after → removed dependency**:

- Trace the former and resulting reachable decision paths from the real entry.
  Identify the sole owner with file/line evidence; check that the same decision
  is not repeated elsewhere. A condition, retry, or prompt covering the old
  dependency is not its removal. Fewer files/lines alone are not evidence.
- Check complete dialogues through the affected real endpoints, including
  adverse/absent suitable model decisions where the model remains involved.
  A validated button must not undergo model task classification again. A model
  used for explanation receives the determined task; server repair of a second
  route/kind decision is not removal. Tenant, privacy, revision and ownership failures must still be
  rejected. If the model is removed from that action, verify it is not called.
- Assertions must identify the intended task, offers/scope and next-turn context
  relevant to the change; HTTP success or presence of any price is insufficient.
  Offline behavior proves the tested inputs, not live-model quality.
- For a bug fix, verify its behavior and responsibility boundaries; deletion
  of a decision is not required. For documentation, check links and consistency
  without running bot/provider tests. Do not label either as implemented
  architectural simplification without runtime evidence.

For SIM-2 reject mandatory splitting of ordinary connected explanations into
separate operations or a larger replacement control envelope without agreement.
For SIM-2/3 require a jointly specified completed-result/projection boundary,
service-bound extent and explicit removed context transfers, not a new summary,
fact extractor or parallel memory. For SIM-4 apply the later owner decision
D2-114/T3/C03: code-owned financial blocks use approved tenant data; unrestricted
useful prose remains published with explicitly accepted residual financial risk.
Do not require the superseded D2-108 all-answer guarantee or introduce a semantic
verifier, sanitizer, second call, prose truncation/refusal or template replacement
to obtain PASS. Verify real removals and the SIM-0-approved selection policy;
changing a prompt or acceptance document alone is not runtime simplification.
Existing review signals are observation only; detecting all mistakes is not promised.
The future admin review queue is an idea, not authorized implementation. Each SIM must prove
its affected dialogues and architectural claim before closure; REC-5 integrates
those proofs, not postpones them.

Missing before/after/removal evidence for claimed simplification, a retained or
relocated claimed dependency, and a changed path that violates the agreed
responsibility table are blocking P1 findings. FUTURE SCOPE cannot excuse these
within the claimed change. Unrelated baseline debt outside that change is
reported separately and does not require completing future stages.

## Verdict

Return exactly one verdict:

- `PASS` — no blocking checkpoint finding remains.
- `REJECT` — list concrete P0/P1 blockers with file and evidence.

P2 observations are non-blocking unless the task explicitly elevates them. After a correction,
recheck only the rejected findings and any materially changed scope.

The report must include branch/HEAD/baseline, reviewed allowlist, findings, test results,
provider calls, staging state, and foreign WIP.
For simplification, include the sole owner and removed dependency with code and
dialogue evidence, plus limits of that evidence. For other change kinds, state
that no implemented simplification is being certified. A narrow PASS does not
certify the architecture of the whole bot.
