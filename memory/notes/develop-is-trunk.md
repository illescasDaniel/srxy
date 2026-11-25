---
name: develop-is-trunk
description: Treat develop as the active integration branch for new work; keep memory/activeContext.md / progress.md oriented to develop rather than the old feature…
type: decision
date: 2026-08-30
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** Feature work previously lived on `feature/fixes_1.6.6` and related worktrees. Development continues on `develop`.
- **Decision:** Treat `develop` as the active integration branch for new work; keep `memory/activeContext.md` / `progress.md` oriented to `develop` rather than the old feature branch name.
- **Rationale:** Avoid agents writing memory against a branch that is no longer where ongoing work lands.
