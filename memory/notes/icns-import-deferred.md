---
name: icns-import-deferred
description: Import write_icns_from_png lazily inside _write_macos_app, right before use (which is already sys.platform != "darwin"-guarded and wrapped in a…
type: decision
date: 2026-08-29
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** develop `61855d4` (macOS Mach-O launcher / Tahoe restamp merge) added a module-level `from srxy.resources.icons.icns import write_icns_from_png` in `install.py`. `icns.py` imports Pillow. The Windows offline installer's relocatable wizard venv installs `srxy` with `--no-deps` (only `PySide6` is installed explicitly), so Pillow isn't present — the venv-relocation import smoke test (`from srxy.adapters.inbound.installer.install import InstallOptions`) failed with `ModuleNotFoundError: No module named 'PIL'`, breaking `build-offline.ps1` (Windows Installer CI, `build-offline` job).
- **Decision:** Import `write_icns_from_png` lazily inside `_write_macos_app`, right before use (which is already `sys.platform != "darwin"`-guarded and wrapped in a best-effort `try/except`), instead of at module top level.
- **Rationale:** `write_icns_from_png` is macOS-only functionality; deferring the import keeps `install.py` importable without Pillow on platforms/venvs that don't need it, restoring Windows Installer CI without touching shared packaging behavior on macOS/Linux.
