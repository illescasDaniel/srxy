---
name: memory-layout-memory-1
description: Project memory now uses the memory-1 layout (NOW.md, MEMORY.md, one-fact notes) instead of memory-bank files
type: decision
date: 2026-11-25
status: current
supersedes: memory-tracked-in-git
superseded_by:
source:
---

Project memory now follows the `memory-1` skill: `memory/NOW.md` for current state, `memory/MEMORY.md` as the index, one dated fact per file under `memory/notes/`, and `memory/LATER.md` for open items. The old `memory-bank` files (`activeContext.md`, `progress.md`, `decisions.md`, `README.md`) were split into notes and moved to `memory/archive/`.

**Why:** one fact per note is greppable and merges cleanly, while `NOW.md` stays small enough to read at every session start. The old append-only `decisions.md` had grown to 526 lines and `activeContext.md` mixed status with durable facts.

**Rejected:** keeping the three-file memory-bank layout (status and decisions drift together, and merges conflict on the same two files).

**How to apply:** read `NOW.md` then `MEMORY.md` at session start; write durable decisions, preferences, incidents and gotchas as notes; update `NOW.md` at the end of any session with work. Keep `memory/` tracked in git so it follows the branch.
