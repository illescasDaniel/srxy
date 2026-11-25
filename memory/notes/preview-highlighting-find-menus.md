---
name: preview-highlighting-find-menus
description: Keep the in-house HTML highlighter but drive colours from a PreviewPalette with light/dark variants; add a Ctrl+F find bar that renders match spans as…
type: decision
date: 2026-08-18
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** File-content preview used hardcoded hex syntax colours (not theme-aware), had no in-preview find, and no copy/open/folder actions.
- **Decision:** Keep the in-house HTML highlighter but drive colours from a `PreviewPalette` with light/dark variants; add a Ctrl+F find bar that renders match spans as HTML overlays on top of the existing preview; add a right-click menu (copy/select-all/find/open file/open folder) plus "Open containing folder" on the results list; extend `DesktopPort` with `reveal_path` (os/gui/tui adapters); expose match line numbers via `LineNumberRole` to jump the preview on click.
- **Rationale:** No Pygments/tree-sitter dependency; reuses the existing line-oriented matching; theme-awareness follows the OS light/dark already handled in `qt_theme.py`.
