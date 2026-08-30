# Memory bank

Per-branch project state used as an AI agent memory bank. The folder is **tracked in git**: each worktree or checkout carries its branch's version, so context follows the branch instead of staying trapped on one machine or worktree.

## Files

| File | Role |
|------|------|
| `progress.md` | Macro checklist — what is done, what is pending, open bugs. |
| `activeContext.md` | Session scratchpad — current focus, blockers, touched files, immediate next steps. |
| `decisions.md` | Technical log — significant technical, structural, or dependency decisions and their rationale (newest first, append-only). |

## Starting a new feature branch

`progress.md` and `activeContext.md` describe the *current* branch and go stale fast, so reset them when starting a new branch (worktree or checkout). `decisions.md` is a permanent log — never clean it.

- New branch: give `progress.md` a fresh section for the feature/version, clear the Done list, and carry forward only Open items still relevant to the new branch.
- `activeContext.md`: rewrite with the branch name, the new feature as current focus, no blockers, and only relevant next steps carried over.
- You can do this manually or just ask the AI agent — it knows the exact steps from `.cursor/rules/agent-memory.mdc` and will commit the initialization with the branch's first commit.
