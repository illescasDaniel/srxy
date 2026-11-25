---
name: srxy-app-embeds-interpreter
description: Hardlink/copy the venv Python into Srxy.app/Contents/MacOS/SrxyPython and have the bundle Mach-O launcher exec that binary with PYTHONPATH → venv…
type: decision
date: 2026-09-10
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** After pinning PySide and exporting `QT_QUICK_CONTROLS_STYLE=macOS`, the installed GUI still looked like older macOS vs `uv run`. The `.app` entrypoint was a shell script that `exec`’d `prefix/.venv/bin/python` (uv CPython outside the bundle). AppKit then treated the process as that interpreter’s bundle, so Qt’s macOS NativeStyle used a compatibility / non-app chrome path. Separately: Filters lacked ScrollView; info `ToolButton` hover was a heavy slab; help `MessageDialog` parented to the main window appeared under Popup.Native Options/Filters sheets.
- **Decision:** Hardlink/copy the venv Python into `Srxy.app/Contents/MacOS/SrxyPython` and have the bundle Mach-O launcher exec that binary with `PYTHONPATH` → venv site-packages; Info.plist gains `NSHighResolutionCapable`, `LSSupportsAutomaticGraphicsSwitching`, and `LSEnvironment.QT_QUICK_CONTROLS_STYLE=macOS` (never `UIDesignRequiresCompatibility`). Filters get ScrollView + bounded height; info hover uses a light pill on macOS; native alerts use a QWindow-compatible parent (see Mach-O / parentWindow decision above); remove the style stdout line.
- **Rationale:** `NSBundle.mainBundle` follows the running Mach-O path; keeping the interpreter inside the `.app` is the standard fix for script-launched Python GUIs.
