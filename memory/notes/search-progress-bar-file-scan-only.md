---
name: search-progress-bar-file-scan-only
description: SearchActivityEvent updates status/spinner only. The determinate search progress bar and progressCount come solely from SearchProgressEvent (and terminal…
type: decision
date: 2026-08-30
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** Searching Pictures with OCR, the progress bar could jump to 100% while status still showed `OCR · …`, then drop to ~95%. Document OCR (and transcribe) emit determinate activity with `current/total` for pages/segments; the GUI also fed those ratios into the same progress bar used for files completed / files listed.
- **Decision:** `SearchActivityEvent` updates status/spinner only. The determinate search progress bar and `progressCount` come solely from `SearchProgressEvent` (and terminal finished/cancel). Page/segment percent remains visible in the status line via `format_activity_status_body` (`100% OCR · scan.pdf`).
- **Rationale:** Mixing two independent ratios on one bar guarantees non-monotonic jumps whenever an in-file counter finishes ahead of the outer file counter.
