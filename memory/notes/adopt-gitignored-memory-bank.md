---
name: adopt-gitignored-memory-bank
description: Add memory/ (gitignored) with activeContext.md, progress.md, decisions.md, plus an always-on rule at .cursor/rules/agent-memory.mdc.
type: decision
date: 2026-08-18
status: superseded
supersedes: 
superseded_by: memory-tracked-in-git
source:
---
- **Context:** Needed persistent cross-session context for an agent working across the v1.6.6 branch.
- **Decision:** Add `memory/` (gitignored) with `activeContext.md`, `progress.md`, `decisions.md`, plus an always-on rule at `.cursor/rules/agent-memory.mdc`.
- **Rationale:** Keeps agent scratch memory out of the repo while `docs/` stays the canonical committed reference.
