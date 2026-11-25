---
name: permission-denied-skip-and-warn
description: Treat access-denied as SkippedFile(reason="permission_denied"). Walker records unlistable dirs via os.walk(onerror=…). Per-file search catches…
type: decision
date: 2026-08-29
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** Searching large trees (e.g. home) could hit `PermissionError` / errno 13 on files or folders and abort the whole search instead of continuing.
- **Decision:** Treat access-denied as `SkippedFile(reason="permission_denied")`. Walker records unlistable dirs via `os.walk(onerror=…)`. Per-file search catches access-denied and, if the parent directory is not listable, marks that prefix so later paths under it are not opened. Warnings reuse the existing skipped-files ⚠ UI via `format_skipped_file_warning`. Always pass `skipped_files` from `execute_search` (including names-only) so permission skips are retained.
- **Rationale:** Matches size/OCR skip UX; avoids wasting work on known-denied subtrees without parallelizing the walk or changing QML.
