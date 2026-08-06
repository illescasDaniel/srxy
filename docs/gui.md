# Graphical UI

On a graphical session, **srxy opens a PySide6 + QML window by default**.

```bash
srxy "registry" ./src
srxy --tui          # Textual TUI instead
srxy --cli "q" .    # plain CLI
```

## Layout

Named sections top to bottom:

| Section | Purpose |
|---------|---------|
| **Where to search** | Browse + path field; live validation with a warning icon when the path is missing or not a directory |
| **What to search** | Query field with mode selector on the right (Simple / Multi-term / Advanced); preview shown for Multi-term and Advanced only |
| **How to search** | Options and Filters buttons (stacked) open popup dialogs; Options uses the same sections as the TUI (Where / How / Which files); each control has an **(i)** info button |
| **Search** | Wider Search button (enabled only when path + query are usable); warning icon when the query is invalid; system highlight tint when settings are stale |
| **Search Results** | Column tables (Results \| Matches + Preview) with zebra rows; inactive until the first search; Matches pane hidden for name-only hits |
| **Search progress** | Progress bar, percentage, `current/total` file count, animated status spinner during OCR/transcribe/semantic work, Cancel; inactive until the first search |

Power-ups that need optional deps or a GPU (CUDA/MPS) are grayed out when unavailable; **(i)** stays clickable and explains how to fix (install `srxy[semantic]`, Tesseract, ffmpeg, GPU PyTorch). Missing **AI model caches** do not gray out — Search prompts to download with confirm + progress dialogs (same idea as the TUI).

Tesseract and ffmpeg are system binaries: the GUI does not install them; info text points at package managers and official sites.

## Query modes

| Mode | Use for |
|------|---------|
| **Simple** | One literal search term (`|` / `&` / `()` are not operators; path separators are ignored) |
| **Multi-term** | Literal term rows joined with AND/OR (same as the TUI builder) |
| **Advanced** | Raw `|` / `&` / `()` boolean syntax |

## Snapshots

GUI text-tree snapshots live under `tests/gui/snapshots/`. Refresh:

```bash
UPDATE_GUI_SNAPSHOTS=1 QT_QPA_PLATFORM=offscreen pytest tests/gui/test_gui_snapshots.py
```

Regenerate the README screenshot: `./scripts/docs/export_gui_screenshot.sh`
