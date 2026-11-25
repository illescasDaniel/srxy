---
name: search-stale-baseline
description: Commit _last_snapshot only when a non-cancelled SearchFinishedEvent set _search_completed_ok. On cancel/error, clear _last_snapshot so stale stays true…
type: decision
date: 2026-08-29
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** After Cancel, the GUI Search button dropped its accent and looked dark (Fluent secondary). Search binds `accent: controller.stale`. `_on_search_thread_finished` always set `_last_snapshot = _snapshot()`, so cancel cleared `stale` even though `_begin_search` had wiped results. Same on every platform; most visible in Windows dark mode.
- **Decision:** Commit `_last_snapshot` only when a non-cancelled `SearchFinishedEvent` set `_search_completed_ok`. On cancel/error, clear `_last_snapshot` so `stale` stays true and Search stays accented (including cancelled re-runs of an identical prior query).
- **Rationale:** Accent means “settings differ from last successful search”; a cancelled/failed run must not establish that baseline. Unit + QML regression tests cover cancel and success-then-cancel.
