---
name: parallel-file-count-probe
description: Start a daemon counting thread with identical walker args (no duplicate skip warnings). Use probe_total as progress denominator until listing_done; emit…
type: decision
date: 2026-09-01
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** `_execute_file_search` consumes `iter_files` lazily; once OCR pending hits the limit, the walk blocks on `_drain_done`. `listing_done` and the `(0, N)` emission were gated behind the full walk — minutes for large image folders.
- **Decision:** Start a daemon counting thread with identical walker args (no duplicate skip warnings). Use `probe_total` as progress denominator until `listing_done`; emit `(0, N)` when probe finishes. Join probe in `finally`.
- **Rationale:** One extra cheap directory walk buys immediate UI feedback without changing OCR parallelism.
