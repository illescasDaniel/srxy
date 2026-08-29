---
name: apply-worktree-srxy
description: >-
  Bring changes from the current isolated Git worktree into the main checkout,
  run the repo quality gate, and commit. Use when the user invokes
  /apply-worktree-srxy or asks to apply/merge the worktree back into the main
  workspace (srxy project).
disable-model-invocation: true
---
# Apply Worktree (srxy)

Use only when the user explicitly invokes `/apply-worktree-srxy` (or clearly asks to apply this worktree into the main checkout).

## Goal

Commit any pending work on this worktree branch first, then merge that branch into the **main checkout** (parent branch), verify with the project quality gate, and commit any remaining parent-side fixes. Do **not** delete the worktree (that is `/delete-worktree-srxy`). Do **not** push unless the user asks.

## Steps

1. **Confirm context**
   - Run `git rev-parse --show-toplevel`, `git status -sb`, `git worktree list`.
   - If the current repo is not a linked worktree (only one entry in `git worktree list`), stop and say there is nothing to apply.
   - Main checkout = the worktree list entry that is **not** under `~/.cursor/worktrees/` (normally the first / primary path).
   - Note the worktree’s current branch and the main checkout’s current branch (the parent branch to land on).

2. **Commit worktree changes first (required if dirty)**
   - If the worktree has staged, unstaged, or untracked files that belong to the task, **commit them on the worktree branch before merging**.
   - Follow the user’s git safety rules and commit style: review `git status` / `git diff` / recent `git log`; stage relevant paths only (never secrets); no `--no-verify`, no amend unless the usual amend conditions are met, no force-push, no git config changes, no `-i`.
   - Use a HEREDOC (or PowerShell here-string) for the message body; focus on why.
   - If the worktree is already clean, skip this step.
   - Do **not** skip ahead to copying dirty files into main — the apply path is commit-then-merge.

3. **Merge the worktree branch into main**
   - From the main checkout, merge the worktree branch (`git -C <main> merge <worktree-branch>`). Prefer a fast-forward when possible; otherwise create a merge commit.
   - If there is nothing to merge (worktree branch tip is already an ancestor of the parent tip and step 2 made no commit), say so and stop unless the gate/commit steps still need to run for an incomplete prior apply.
   - **On conflict: resolve automatically.** Do not stop for the user to fix conflicts.
     - Inspect each conflicted file; keep **both** sides’ intentional changes whenever they compose (feature work from the worktree **plus** newer parent-branch fixes).
     - Prefer the worktree’s version only for files that are purely the feature under apply; prefer parent for unrelated parent-only fixes when a hunk cannot compose.
     - For `memory/activeContext.md` / `memory/progress.md`, rewrite to reflect the applied feature on the parent branch (not a raw conflict dump). Append to `memory/decisions.md` (never delete prior entries).
     - After resolving, `git add` the conflicted paths and continue the merge (`git commit` if merge is in progress and needs a merge commit).
     - Only abort the merge and ask the user if a conflict is truly ambiguous after inspection (e.g. contradictory edits to the same logic with no safe composition).

4. **Switch to the main checkout**
   - Call `move_agent_to_root` on the main checkout path before gate/commit so commands run there.

5. **Quality gate (required)**
   - Run the **project’s** quality gate from the main checkout until it passes cleanly.
   - Prefer repo docs / `AGENTS.md` / Taskipy tasks. Typical patterns:
     - Windows: before the gate, ensure the venv has CUDA torch when an NVIDIA GPU is present (`uv run task sync-win`, which uses `--extra semantic-gpu` + `ensure-windows-cuda-torch.ps1`). Prefer that over bare `uv sync --extra semantic`. Verify with `.\.venv\Scripts\python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available())"` (`+cu*` and `True`). Then: `uv run task checks-win-fix-quiet` then `uv run task checks-win-quiet` (or the repo’s documented equivalent).
     - Unix/macOS: `./scripts/quality/checks.sh --quiet --fix` then `./scripts/quality/checks.sh --quiet`.
   - If the gate fails, fix issues in the **main checkout** and re-run until clean. Do not finish with a red gate.
   - If you see `warning: no GPU found; … will use CPU` despite a real NVIDIA GPU, stop and fix the venv (run `sync-win` / ensure script) before continuing — do not treat that as a normal gate message.

6. **Commit on the parent branch (if needed)**
   - If the merge already created a merge/ff commit and the tree is clean after the gate, that satisfies this step (report that SHA).
   - If the gate (or conflict resolution) left parent-only fixes uncommitted, stage those files and create a proper commit on the main checkout’s current branch using the repo’s commit style.
   - Same git safety rules as step 2.

7. **Hand off**
   - Report the worktree commit SHA(s) (if any), the parent merge/commit SHA(s), branch name, and that the gate passed.
   - Reminder: use `/delete-worktree-srxy` separately when they want the isolated checkout removed.

## Rules

- Always commit dirty worktree work on the worktree branch **before** merging into the parent. Never apply uncommitted worktree diffs straight onto main as a substitute for that commit.
- Never skip the quality gate after a successful merge (unless there was truly nothing to apply).
- Never leave a merge half-finished because of conflicts you can resolve — resolve them and continue.
- Never force-push. Never delete the worktree from this skill.
- Never update git config.
- Do not use `-i` git flags.
- If main and worktree point at unrelated repos, abort.
