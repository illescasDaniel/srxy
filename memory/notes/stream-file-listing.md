---
name: stream-file-listing
description: Search paths as FileWalkerPort.iter_files yields them. Threads/processes use a bounded in-flight future set; process pool still waits until 50 paths (or…
type: decision
date: 2026-08-29
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** On large roots (e.g. home), `_execute_file_search` fully materialized `list[Path]` under “Listing files…” before any matching, so users waited with no results.
- **Decision:** Search paths as `FileWalkerPort.iter_files` yields them. Threads/processes use a bounded in-flight future set; process pool still waits until 50 paths (or walk end under 50 → sequential). When semantic image is active, encode the CLIP query before the walk. Activity is “Searching…” (no exclusive listing gate). Determinate `on_progress(completed, total)` only after the walk finishes (catch-up + remaining completions); UIs already treat unknown totals as indeterminate.
- **Rationale:** Time-to-first-result shrinks on huge trees without parallelizing `os.walk` itself; progress stays compatible with existing GUI/TUI/CLI bars; process-pool startup heuristic is preserved.
