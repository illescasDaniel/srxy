---
name: gui-search-isolation
description: (1) Always run GUI search in the existing search subprocess. (2) Gate worker allow_process_pool on search_uses_subprocess(args) so light searches stay…
type: decision
date: 2026-08-30
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** Searching `$HOME` for common queries froze the GUI (and briefly the whole machine after a bad subprocess+pool experiment). py-spy showed in-process QThread scoring holding the GIL (~60% samples); NDJSON probes showed model flushes were cheap while status/ListView work and event-loop lag were not.
- **Decision:** (1) Always run GUI search in the existing search **subprocess**. (2) Gate worker `allow_process_pool` on `search_uses_subprocess(args)` so light searches stay single-process. (3) Stream-append results during search, sort once on finish; coalesce list/status updates; lighten results delegates (`reuseItems`, fixed height, shared context menu). (4) Animate activity via a separate `activitySpinner` property; use an indeterminate `ProgressBar` until a file total is known.
- **Rationale:** Isolates GIL from Qt without a free-threaded interpreter; avoids process-pool fork storms on large trees; keeps progressive UX without mid-list index storms.
