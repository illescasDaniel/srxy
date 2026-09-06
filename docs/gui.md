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
| **How to search** | Options and Filters buttons (stacked) open popup dialogs; Options uses the same sections as the TUI (Where / How / Which files); each control has an **(i)** info button. Each dialog ends with an opt-in **Persist … after srxy exits** checkbox and a **Reset** button (factory defaults in the draft; OK still required). When Persist is on, values are written to `settings.json` on quit and restored on the next GUI launch. |
| **Search** | Wider Search button (enabled only when path + query are usable); warning icon when the query is invalid; system highlight tint when settings are stale |
| **Search Results** | Column tables (Results \| Matches + Preview) with zebra rows; inactive until the first search; Matches pane hidden for name-only hits |
| **Search progress** | Progress bar (indeterminate until the file total is known, then 0–100%), percentage, `current/total` file count, animated status spinner during OCR/transcribe/semantic work, Cancel; inactive until the first search |

Power-ups that need optional deps or a GPU (CUDA/MPS) are grayed out when unavailable; **(i)** stays clickable and explains how to fix (install `srxy[semantic]`, Tesseract, ffmpeg, GPU PyTorch). Missing **AI model caches** do not gray out — Search prompts to download with confirm + progress dialogs (same idea as the TUI).

Tesseract and ffmpeg are system binaries: the GUI does not install them; info text points at package managers and official sites.

## Search responsiveness (progressive results)

Heavy searches (large trees, many hits) must not stall the Qt event loop:

| Rule | Why |
|------|-----|
| GUI search always runs in a **subprocess** | Scoring on a QThread holds the GIL and freezes the UI even when Python handlers are fast |
| Light (name/content) worker searches use **no process pool** | `allow_process_pool=True` over `$HOME` can fork `cpu_count` interpreters and thrash the whole machine |
| Progressive hits **stream-append** then **sort on finish** | Mid-list score inserts reshuffle every row index and stall the ListView |
| Result flushes coalesce (~1s after the first hit) | Limits ListView layout cost while still showing early matches |
| Activity **status body** is coalesced; the braille **spinner** is a separate property | Rewriting the full status string every 100ms used to cost tens–hundreds of ms per tick under load |
| Progress bar is **indeterminate** until a file total exists | Walk/search overlap means `%` is meaningless before `current/total` is known |

Dev helper: `scripts/dev/profile-gui-freeze.sh` (needs ptrace/`sudo`) dumps stacks and a speedscope/flamegraph for live freezes.

## Startup splash

Cold start is still dominated by importing PySide6, applying the Qt Quick theme, and loading `Main.qml`. A small **splash window** (`Splash.qml`, `Qt.SplashScreen`) appears after Qt is ready and before the main window, so users see branding sooner than the full UI — typically a few hundred milliseconds earlier, not an instant native splash.

It shows the app name, version, author (from package metadata / `branding.AUTHOR`), a busy indicator, and a short status line updated while translations, services, the search controller, and `Main.qml` load.

**Limits:** the splash cannot appear before `QGuiApplication` and theme setup. For Start Menu / `Srxy.exe` launches, anything earlier would need a native splash in the C# launcher (installer-only path), which this Python GUI path does not use.

### Disable or remove

| Goal | How |
|------|-----|
| **Turn off at runtime** | Set `SRXY_NO_SPLASH=1` (or `true` / `yes` / `on`). `run_gui` skips `Splash.qml` and shows Main when ready. |
| **Benchmark without splash** | Same env, optionally with `SRXY_STARTUP_TIMING=1` and `SRXY_STARTUP_EXIT=1` (quit after `qml_loaded`; see [development.md](development.md)). |
| **Remove the feature** | Delete or stop loading `src/srxy/adapters/inbound/gui/qml/Splash.qml` and `splash.py`; in `app.py`, drop the `splash_enabled` / `SplashBridge` path and keep a single `engine.load(Main.qml)` with `visible: true` (or reveal Main immediately). Drop splash assertions in `tests/gui/test_gui_qml_load.py` and `tests/unit/test_gui_splash.py`. |

## Content preview

The **Preview** pane (right side of Search Results) renders differently depending on the selected file's detected content type (Magika + extension heuristics — the same `resolve_content_route()` routing search uses):

| Content kind | Preview |
|--------------|---------|
| Text / code / markdown / JSON | Syntax-highlighted plain text, line-number gutter, in-file Find (Ctrl+F, F3 / Shift+F3) |
| **Image** (`.jpg`, `.png`, `.webp`, `.gif`, `.bmp`, `.heic`/`.heif`, camera RAW, `.svg`, …) | Scaled-to-fit image. Non-SVG formats are decoded once via Pillow (same path as OCR/semantic image search — handles HEIC and RAW without relying on Qt's native image plugins) and capped to 2048px on the long edge; SVG renders natively via Qt Svg. |
| **Audio** (`.mp3`, `.flac`, `.ogg`, `.wav`, `.m4a`, `.aac`, …) | `QtMultimedia` player: play/pause, seek slider, elapsed/duration, mute |
| **Video** (`.mp4`, `.mov`, `.webm`, `.mkv`, `.avi`, …) | Same player controls plus an embedded video surface (`VideoOutput`) |

Detected type mismatches still show in the header (e.g. `OGG · named .txt`) regardless of preview mode. Binary files Magika cannot classify as a known media/document kind still fall back to the previous "(Binary file — showing matches only)" placeholder, with matched lines (if any) surfaced in the Matches pane above.

Only the **main app** (`srxy`) ships the full PySide6 wheel with `QtMultimedia` — the separate `srxy-installer` wizard's PySide6 payload is pruned to a Quick/Controls/Dialogs-only subset (see `packaging/*/prune-pyside*.sh`) and does not need this module.

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

## Click-driven flow tests

Pilot-style helpers live in [`tests/gui/helpers.py`](../tests/gui/helpers.py) (`load_main`, `click`, `set_text`, dialog open/OK). End-to-end flows (path → query → options/filters → Search → results/progress) are in [`tests/gui/test_gui_flows.py`](../tests/gui/test_gui_flows.py). They run in the **gui** quality-gate bucket (`QT_QPA_PLATFORM=offscreen`). Prefer typing into `pathField` over clicking Browse (native `FolderDialog` is hostile offscreen).

Regenerate the README screenshot for the host OS (writes `docs/images/gui-macos.png`, `gui-linux.png`, or `gui-windows.png`):

```bash
./scripts/docs/export_gui_screenshot.sh
```
