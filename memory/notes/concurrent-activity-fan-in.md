---
name: concurrent-activity-fan-in
description: (1) Emit on_progress(completed, listed) whenever listing finishes and listed > 0 (including 0/N). (2) Add concurrent_activity_fan_in so each worker thread…
type: decision
date: 2026-08-30
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** OCR searches on small folders (e.g. 2 files in Downloads) left the GUI stuck on “Searching…” with no `1/2` counts and no `OCR · filename` labels. Sticky `activity.searching` blocked `status.scanning`; `_catch_up_progress` skipped `completed == 0`; heavy GUI/TUI searches use a thread pool that omitted `on_activity` to avoid overlapping labels.
- **Decision:** (1) Emit `on_progress(completed, listed)` whenever listing finishes and `listed > 0` (including `0/N`). (2) Add `concurrent_activity_fan_in` so each worker thread owns one activity slot; clear removes that slot only; downstream sees the latest remaining label. Pass the fan-in into thread-pool `_submit_file`. (3) GUI/TUI treat generic Searching as yielding to `Scanning current/total`; specific ops (`OCR ·`, `CLIP ·`, …) still own the status line.
- **Rationale:** Keeps thread-pool speed for heavy modes while restoring determinate file counts and per-file operation text during the long OCR wait.
