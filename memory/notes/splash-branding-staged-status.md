---
name: splash-branding-staged-status
description: Add authors to pyproject.toml + AUTHOR in branding.py. New SplashBridge QObject exposes appName / author / version / status; run_gui updates status…
type: decision
date: 2026-08-29
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** Splash only showed icon + name + BusyIndicator. Author was not in `pyproject.toml` (only LICENSE). Users wanted name, author, version, and Loading / progress copy.
- **Decision:** Add `authors` to `pyproject.toml` + `AUTHOR` in `branding.py`. New `SplashBridge` QObject exposes `appName` / `author` / `version` / `status`; `run_gui` updates status between translations → services → controller → Main.qml. App window icon applied after first splash paint.
- **Rationale:** Metadata-driven author/version stay in sync with packaging; staged status reuses the existing splash window without a second UI path. Further “instant splash” options (native pixmap / pre-Qt child process) deferred — see activeContext notes.
