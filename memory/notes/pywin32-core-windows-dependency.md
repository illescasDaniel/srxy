---
name: pywin32-core-windows-dependency
description: (1) Add pywin32>=312; platform_system == 'Windows' to core [project] dependencies. (2) Drop the [windows] extra entirely (no empty stub). (3) Stop…
type: decision
date: 2026-08-30
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** Install docs, installer specs, CI, and `sync-dev` all had to remember `--extra windows` / `srxy[…,windows]` just to get Explorer tag support.
- **Decision:** (1) Add `pywin32>=312; platform_system == 'Windows'` to core `[project] dependencies`. (2) Drop the `[windows]` extra entirely (no empty stub). (3) Stop appending `[windows]` in `sync.py`, installer `package_extras_for_host`, CI, and docs; bump privacy notice to v7 (pywin32 listed under core).
- **Rationale:** Platform markers install pywin32 only on Windows; end-user and agent commands drop a whole extra dimension.
