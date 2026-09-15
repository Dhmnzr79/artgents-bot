# Git and workspace workflow

## Permanent folders

- `C:\Cursor Projects\artgents-bot` — standalone clean clone on `main`; do not develop here.
- `C:\Cursor Projects\artgents-bot-<task>` — one temporary worktree per active task.
- `C:\Cursor Projects\artgents-workspace-recovery-YYYY-MM-DD` — local recovery only; never commit.

Open exactly one task folder in each Cursor window and Codex task.

## Start a task

From the clean standalone clone:

```powershell
cd "C:\Cursor Projects\artgents-bot"
git fetch --prune origin
git switch main
git pull --ff-only
git worktree add -b codex/<task> "C:\Cursor Projects\artgents-bot-<task>" origin/main
cd "C:\Cursor Projects\artgents-bot-<task>"
git status --short --branch
```

Then open only `artgents-bot-<task>` in Cursor.

## Checkpoint and push

Stage exact paths, never the whole tree:

```powershell
git add -- path/to/file1 path/to/file2
git diff --cached --name-status
git diff --cached --stat
git diff --cached --check
git commit -m "type(scope): concise checkpoint"
git push -u origin codex/<task>
```

Create one PR for the task. Add later checkpoint commits to the same branch and PR.
Merge only after the task is complete, Checker passes, CI is green, and the owner approves.

## Pause safely

If useful work must pause, make a clearly named WIP checkpoint and push it. Do not leave the
only copy as uncommitted files in a folder. Never mix a second task into that worktree.

## Finish after merge

From the standalone clone:

```powershell
git fetch --prune origin
git switch main
git pull --ff-only
git worktree remove "C:\Cursor Projects\artgents-bot-<task>"
git branch -d codex/<task>
```

Delete the remote topic branch after merge, or enable GitHub's automatic head-branch deletion.
Never remove a dirty worktree with `--force` until its patch, untracked files, and `.env` have
been backed up and verified.

## Daily five-line check

```powershell
git rev-parse --show-toplevel
git branch --show-current
git status --short --branch
git fetch --prune origin
git rev-list --left-right --count HEAD...origin/main
```

If the path or branch is not the current task, stop before editing.
