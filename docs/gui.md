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
| **Where to search** | Browse + path field; live validation with a warning icon when the path is missing or not a directory; a folder can also be dragged from the OS file manager and dropped anywhere on this row (dashed highlight + "Drop folder here" while dragging) |
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

## Query modes

| Mode | Use for |
|------|---------|
| **Simple** | One literal search term (`|` / `&` / `()` are not operators; path separators are ignored) |
| **Multi-term** | Literal term rows joined with AND/OR (same as the TUI builder) |
| **Advanced** | Raw `|` / `&` / `()` boolean syntax |

## Drag-and-drop path field

The **Where to search** row is a `DropArea` (`objectName: pathDropArea`) accepting `text/uri-list`:

- Dragging a folder over it shows a dashed accent border, a translucent fill, and a "Drop folder here" label; the **Browse** button dims while a drag is in progress.
- Dropping resolves the first local `file://` URI via `resolve_dropped_folder_path()` in [`controller.py`](../src/srxy/adapters/inbound/gui/controller.py) and assigns it to `controller.path`, going through the same normalization (`_normalize_browsed_path`, percent-decoding) and validation (`pathIssue`) as the Browse dialog and manual typing.
- **Directories** update the path and clear any warning; **files** update the path but surface the existing "Not a directory" warning (same affordance as typing a file path).
- **Multiple dropped items**: only the first local URI is used; the rest are ignored (a multi-selection drag is not a multi-root search).
- **Non-local URIs** (`http://`, `ftp://`, UNC/network-share hosts) are ignored outright — the path field is left unchanged.
- Dropping never starts a search; it only updates `path`/`pathIssue`, same as editing `pathField` by hand.

Covered by unit tests for the URI→path helper (`resolve_dropped_folder_path`, `handleDroppedPathUrls`) in [`tests/gui/test_gui_controller.py`](../tests/gui/test_gui_controller.py) and a full-window flow test in [`tests/gui/test_gui_flows.py`](../tests/gui/test_gui_flows.py) that drives `Main.qml`'s bindings end-to-end (offscreen QML cannot synthesize real OS drag events, so tests call the same `handleDroppedPathUrls` entry point the `DropArea.onDropped` handler calls).

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
