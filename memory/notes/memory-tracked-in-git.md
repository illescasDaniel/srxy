---
name: memory-tracked-in-git
description: Track memory/ in git as per-branch state. decisions.md stays append-only (never cleaned); progress.md and activeContext.md are reset at branch start…
type: decision
date: 2026-08-18
status: superseded
supersedes: adopt-gitignored-memory-bank
superseded_by: memory-layout-memory-1
source:
---
- **Context:** The earlier entry gitignored `memory/` to keep agent scratch out of the repo. But worktrees don't share ignored files: each new `git worktree add` got zero context and memory fragmented across worktrees.
- **Decision:** Track `memory/` in git as per-branch state. `decisions.md` stays append-only (never cleaned); `progress.md` and `activeContext.md` are reset at branch start. `memory/decisions.md` gets `merge=union` in `.gitattributes`.
- **Rationale:** Per-branch tracked memory follows the branch automatically in worktrees and new clones; the clean-at-start ritual keeps `progress.md`/`activeContext.md` relevant. Add `.cursor/rules/agent-memory.mdc` section 4 + human-oriented `memory/README.md`.
