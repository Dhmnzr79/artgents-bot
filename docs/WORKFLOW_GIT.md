# Git and workspace workflow

## Permanent folder

- `C:\Cursor Projects\artgents-bot-active` — the single active checkout for development and local bot/widget runs. Keep `main` clean; develop on a task branch here.
- `C:\Cursor Projects\artgents-bot` is the former checkout with preserved local WIP. Do not run the bot from it or clean it up as part of normal tasks.
- Old registered worktrees are historical state. Leave them untouched until a separate verified cleanup.

Use one active task and one editor window for this folder.

## Start a task

From the clean standalone clone:

```powershell
cd "C:\Cursor Projects\artgents-bot-active"
git fetch --prune origin
git switch main
git pull --ff-only
git switch -c codex/<task> origin/main
git status --short --branch
```

Open this same folder in Cursor for the active task. Use the single local launcher
below for bot/widget runs; it checks the Git root, uses this folder's `.venv`,
and refuses a second process on port 9001. Do not reuse the old checkout's
environment or local `data/` implicitly.

## Local demo bot and widget

In PowerShell, run the one launcher by its full path, even if the terminal
currently points at another folder:

```powershell
& "C:\Cursor Projects\artgents-bot-active\scripts\start_local_widget.ps1"
```

The launcher prints the folder, branch, and commit before starting. If port
9001 is already occupied, it stops with an error instead of opening another
bot. Identify the existing process before opening the widget. When the
launcher starts successfully, open
`http://127.0.0.1:9001/static/widget-test.html`. Stop the foreground
process with Ctrl+C. This is a local test run, not a
production deployment. The local `.env`, `.venv`, logs and runtime data must
never be committed. Do not launch the old checkout or an old worktree to test
current D2 behavior.

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
