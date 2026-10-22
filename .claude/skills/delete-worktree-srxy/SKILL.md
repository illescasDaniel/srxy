---
name: delete-worktree-srxy
description: >-
  Remove the current isolated Git worktree and clean up its branch when finished.
  Use when the user invokes /delete-worktree-srxy or asks to delete/remove the
  agent worktree checkout (srxy project).
disable-model-invocation: true
---

# Delete Worktree (srxy)

Use only when the user explicitly invokes `/delete-worktree-srxy` (or clearly asks to delete this worktree).

## Goal

Unregister the isolated checkout from git and drop its generated `cursor/...` branch after work is finished or applied. Does **not** apply changes (that is `/apply-worktree-srxy`).

## Expected lock (do not escalate)

The **same Cursor agent tab** that ran in the worktree often still has that folder as an open workspace root or has files/terminals open under it. On Windows this commonly yields:

- `error: failed to delete '…/.cursor/worktrees/…': Permission denied`
- `Remove-Item` / “used by another process”

That is **normal**. Success for this skill is:

1. The worktree no longer appears in `git worktree list`, and  
2. The generated `cursor/…` branch is deleted when appropriate.

An empty or nearly empty leftover directory under `~/.cursor/worktrees/…` is **OK**. Report it briefly and stop. Do **not**:

- Kill Cursor/IDE processes, force-close handles, or run handle/Sysinternals tools  
- Loop on `Remove-Item` / `rm -rf` retries  
- Ask the user to restart the IDE unless they want the folder gone for disk cleanup  

## Steps

1. **Confirm context**
   - `git rev-parse --show-toplevel`, `git worktree list`, current branch.
   - Identify the worktree path to remove (under `~/.cursor/worktrees/`).
   - Abort if the target is the primary checkout (not under `~/.cursor/worktrees/`).

2. **Move out of the worktree**
   - Call `move_agent_to_root` on the main checkout path **before** removing anything (so the agent is not left inside a deleted root).

3. **Remove the worktree registration**
   - From the main checkout: `git worktree remove <worktree-path>` (use `--force` if the worktree still has leftover dirty files and the user asked to delete).
   - If git reports permission denied on deleting the directory but the worktree disappears from `git worktree list`, treat registration as done. Run `git worktree prune` once if needed.
   - Do not keep retrying filesystem deletes when the folder is locked by this Cursor tab.

4. **Optional branch cleanup**
   - If the worktree used a generated `cursor/...` branch, delete it with `git branch -d` / `-D` from the main checkout.
   - Do not delete `main` / `master` / the user's long-lived feature branch (e.g. `feature/fixes_1.6.6`).

5. **Report**
   - State that the worktree is unregistered, whether the `cursor/…` branch was deleted, and that the agent root is the main checkout.
   - If a leftover empty/locked folder remains, say so in one line — that is acceptable.

## Rules

- Never delete the primary (non-`.cursor/worktrees`) checkout.
- Never force-push. Never update git config.
- Do not apply/merge changes as part of this skill.
- Do not fight OS file locks from the open agent tab.
