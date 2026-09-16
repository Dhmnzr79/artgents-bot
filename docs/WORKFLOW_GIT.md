# Git and workspace workflow

## Permanent folder

- `C:\Cursor Projects\artgents-bot` — the single active checkout. Keep `main` clean; develop on a task branch here.
- Old registered worktrees are historical state. Leave them untouched until a separate verified cleanup.

Use one active task and one editor window for this folder.

## Start a task

From the clean standalone clone:

```powershell
cd "C:\Cursor Projects\artgents-bot"
git fetch --prune origin
git switch main
git pull --ff-only
git switch -c codex/<task> origin/main
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
only copy as uncommitted files in the folder. Never switch tasks with a dirty checkout.

## Finish after merge

From a clean task checkout:

```powershell
git fetch --prune origin
git switch main
git pull --ff-only
git branch -d codex/<task>
```

Delete the remote topic branch after merge, or enable GitHub's automatic head-branch deletion.
Never remove an old registered worktree manually. Verify its patch, untracked files, and `.env`
before any separately authorized cleanup with `git worktree remove`.

## Daily five-line check

```powershell
git rev-parse --show-toplevel
git branch --show-current
git status --short --branch
git fetch --prune origin
git rev-list --left-right --count HEAD...origin/main
```

If the path or branch is not the current task, stop before editing.
