---
name: delete-worktree-srxy
description: Clean up an srxy isolated Git worktree when the user asks to delete, remove, or archive its checkout after work is finished.
---

# Delete Worktree (srxy)

Remove or archive only the requested isolated checkout. Do not merge its changes or record worktree cleanup in tracked memory.

1. Inspect `git worktree list --porcelain`, target status (including untracked files), and Git/common-directory metadata. Identify the primary checkout through Git metadata, never IDE path names. Never remove the primary checkout. Check unique commits as well as uncommitted work.
2. Inspect Codex app attachments with `list_artifacts` when available. For a managed Codex worktree, use `archive_worktree` with its exact artifact identity instead of Git removal. Archiving preserves local changes, unpushed commits, and non-ignored untracked files in a recoverable snapshot; preserve needed ignored files separately first. If the app refuses archival, report the reason rather than bypassing its protection through Git.
3. For an unmanaged checkout, run commands from a surviving checkout with an explicit working directory. Use `git worktree remove <target>` only when clean and unique work is preserved. A deletion request does not authorize discarding unsaved files or unique commits. If preservation or disposition is unclear, leave it intact and report what needs a decision. Never add `--force` merely because this skill was invoked.
4. Delete a temporary branch only when branch cleanup is authorized, it is no longer checked out, and `git branch -d <branch>` succeeds. Never use `-D` or delete long-lived branches (`main`, `master`, `develop`, release branches, or ongoing feature branches). Keep branches of unclear purpose or ownership.
5. Verify Git worktree registration and, for managed worktrees, the artifact lifecycle result. Report archive/removal, branch disposition, preserved work, and leftover directories. Do not claim the chat workspace moved just because commands ran elsewhere.

If file locks prevent removal but an unmanaged worktree is already unregistered, a leftover locked folder is acceptable: report it and stop. Do not kill IDE processes, close handles, loop on deletion retries, or forcibly delete directories. Use `git worktree prune` only for a confirmed stale registration after checking other worktrees. Never force-push or change Git configuration.
