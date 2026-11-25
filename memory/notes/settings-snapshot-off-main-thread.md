---
name: settings-snapshot-off-main-thread
description: (1) stdlib threading.Thread + QMetaObject.invokeMethod(..., QueuedConnection) to apply JSON on the GUI thread. (2) Memoize per-kind sizes in one snapshot…
type: decision
date: 2026-09-01
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** `build_settings_snapshot` blocked the GUI ~5s (model size walks + torch device probe). Initial QThread worker crashed on Windows pytest (torch/numpy import from QThread → access violation).
- **Decision:** (1) stdlib `threading.Thread` + `QMetaObject.invokeMethod(..., QueuedConnection)` to apply JSON on the GUI thread. (2) Memoize per-kind sizes in one snapshot call so the `all` row reuses cache. (3) Remove torch from snapshot path; static transcribe label + lazy import only for pending downloads.
- **Rationale:** Keeps dialog instant without fighting Qt thread affinity for heavy Python imports.
