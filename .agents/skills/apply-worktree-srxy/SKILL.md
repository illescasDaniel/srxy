---
name: apply-worktree-srxy
description: Apply an srxy linked worktree branch to its primary checkout when asked to merge or bring worktree changes back into the main workspace.
---

# Apply Worktree (srxy)

Land the worktree's changes on the primary checkout's current branch. Keep the worktree for separate cleanup; push only when explicitly authorized.

1. Inspect `git rev-parse --show-toplevel`, `git rev-parse --absolute-git-dir`, `git rev-parse --path-format=absolute --git-common-dir`, `git worktree list --porcelain`, and status in both checkouts. Identify the primary checkout through Git metadata (its Git directory is the common directory), never an IDE path. Confirm both checkouts share that common directory and identify the destination branch. If current checkout is primary, there is no linked worktree to apply. If detached, identify the intended source commit first.
2. Review staged/unstaged diffs, relevant untracked files, and recent history. Preserve unrelated work. Make a dirty destination safe without discarding or automatically stashing the user's edits before merging.
3. Commit relevant dirty source changes **only with current authorization to commit**. Pending review or instructions to leave work uncommitted take precedence over skill invocation. Without commit authorization, prepare the reviewable diff and explain that this commit-then-merge workflow cannot proceed yet; do not substitute copying dirty files into the destination. Stage explicit relevant paths only and follow repository commit conventions.
4. Run commands with an explicit primary-checkout working directory, for example `git -C <primary> merge <source-branch>`. Prefer fast-forward; otherwise use a normal merge commit within current authorization. Do not assume the primary branch is named `main`. If the source tip is already an ancestor and there is no new source commit, report nothing to apply.
5. Resolve conflicts by composing both sides' intentional changes rather than blindly choosing ours/theirs. Preserve prior decision entries and reconcile current-state memory only through the orchestrator's memory protocol. If contradictory changes cannot safely compose, report the ambiguity and stop for direction; do not silently discard either side or abort an existing user merge.
6. Run the required destination quality gate until clean: `uv run task checks -- --quiet --fix`, then `uv run task checks -- --quiet` (use `--all` for shared code as repository rules require). Fix failures caused by the apply and repeat. Use `uv run task sync-dev` if environment setup is needed. Follow `AGENTS.md` for environment/sandbox requirements.
7. Commit relevant gate/conflict fixes only within current commit authorization. Report source/destination branches, resulting SHA(s), gate results, and uncommitted work or blockers. If the session remains attached to the source, state that commands ran explicitly in the destination; do not claim the session moved.

Never force-push, change Git configuration, bypass hooks, delete the worktree, or delete branches as part of applying changes. Applying changes never overrides an explicit no-commit/no-push instruction.
