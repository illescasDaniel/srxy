---
name: macos-dialog-footer-and-quick-style
description: Opaque macOS SrxyDialogFooter with 16px side padding; Filters width 560 on Darwin; Unix launcher exports QT_QUICK_CONTROLS_STYLE=macOS; clear…
type: decision
date: 2026-09-10
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** Native Filters sheets looked good but OK sat flush to the right edge, the Cancel/OK strip was transparent (form content visible underneath), and Filters felt cramped. Installed `Srxy.app` could still look “old” vs `uv run` because Finder launches omit style env, QML disk caches linger, and pip floated PySide to 6.11.2 while offline/`uv run` stay on 6.11.1.
- **Decision:** Opaque macOS `SrxyDialogFooter` with 16px side padding; Filters width 560 on Darwin; Unix launcher exports `QT_QUICK_CONTROLS_STYLE=macOS`; clear `~/Library/Caches/{srxy,Python}/qmlcache` on `write_launcher`; after Darwin package install pin `PySide6==6.11.1`; ship `scripts/macos/repair-prefix-gui.sh` for existing prefixes.
- **Rationale:** Footer is laid out full-bleed (Dialog padding does not inset it); env+pin+cache removes the three installed-vs-dev skews we can control without requiring a full offline rebuild.
