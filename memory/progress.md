# Progress

_Last updated: 2026-09-12_

## v1.7.0 — shipped 2026-09-11

Shipped on `main` @ `2c64f08` (PR #44 develop→main). Tag/release: https://github.com/illescasDaniel/srxy/releases/tag/v1.7.0

User-facing notes live on the GitHub Release (not duplicated here). Installers (Windows offline zip, macOS offline/online DMG, Linux AppImage) attached to that release; CI tag jobs green.

### Open (post-1.7.0)

- [ ] Optional: Authenticode signing for Windows fat `SrxyInstaller.exe` (SmartScreen).
- [x] Sync #49 hotfix (Windows Property Store subprocess isolation) from `main` @ `182649f` onto `develop` — ported `windows_metadata.py` / `windows_metadata_worker.py` / `tests/unit/test_windows_metadata.py` verbatim via a dedicated sync PR (avoids dirty full main→develop merge from squash history, same pattern as #47/#48). Daniel OK'd this sync; Tech Lead authorized merge.

## Next train — v1.8.0

Active work lives on `feature/1.8.0` (and its topic branches). Track Open items there / Trello 1.8.0 — do not dump 1.8.0 Done into this file until that train ships.

## Docs — README GUI screenshot (2026-09-11)

- [x] Regenerated `docs/images/gui-linux.png` via `./scripts/docs/export_gui_screenshot.sh`.
- [x] Fixed script for `SrxyControls` import path + theme context props.
- [x] Fixed missing Search / flat Options/Filters: headless Material fills often omit from `grabWindow`; script prefers a real display, falls back to software RHI, and composites button faces from QML props when chrome is missing.
- [ ] Optional: regenerate on a real Linux display (no composite); regenerate `gui-macos.png` / `gui-windows.png` on those hosts; commit when Daniel asks.

- [x] **Manual QA (user):** Windows Inno installer — disk-space label updates with components/tessdata; cancel during CUDA torch; uninstall extras checkboxes; English installer → English GUI on first launch. Confirmed by user 2026-09-01.
- [x] **Manual QA (user):** OCR search on a folder with a multi-page PDF + other files — confirm progress bar never jumps to 100% then back while OCR status is active. Confirmed by user 2026-09-01.
- [x] **Manual QA (user):** OCR/content search on a mixed folder (images + txt) — confirm txt hits appear while status shows `OCR ·` / `CLIP ·` for media. Confirmed by user 2026-09-01.
- [x] **Manual QA (user):** OCR/content search on a small folder — confirm `progressCount` `1/2`… and status `OCR · file` (not stuck on Searching…). Confirmed by user 2026-09-01.
- [x] **Manual QA (user):** Settings menu shortcuts + All Settings dialog — download all / reset cache / reset preferences; confirm busy guard during search/download. Confirmed by user 2026-09-01.
- [x] **Manual QA (user):** GUI persist — check Persist on Options/Filters, OK, quit, relaunch; Reset draft; unpersist clears `settings.json` payload; Filters live validation greys OK on bad input. Confirmed by user 2026-09-01.
- [x] **Manual QA (user):** Reset All Settings with Persist on — options/filters snap to factory defaults immediately; quit leaves `settings.json` absent. Confirmed by user 2026-09-01.

### Open

#### v1.7.0 (still on `develop` / PR #35)

- [ ] **Windows installer migration — PySide offline wrapper:** parity with macOS `.app` / Linux AppImage offline wizard (PR #35).
- [ ] **Check macOS installer:** Verify macOS installer build/signing/install path still works.

#### v1.8.0 (`feature/1.8.0`)

- [x] **Search by folder name — QA nits addressed (2026-09-06):** (1) `test_file_search.py` gained a symmetric search-level case: with `include_subdirectories=False`, a top-level folder still matches as a directory result while a deeper one does not (walker-level guarantee was already covered directly in `test_file_walker_directories.py`; this exercises it through the full search API). (2) Closed a JSON `"type"` TOCTOU — `FileSearchResult` gained `is_dir: bool = False`, captured once by `_search_single_file` when the hit is produced (reusing the `is_directory` check it already computes) instead of `format_json_result` re-`stat`-ing `path.is_dir()` at format time. Threaded through the worker subprocess round-trip (`file_result_to_dict`/`file_result_from_dict`) so heavy GUI/TUI searches keep the correct type across the subprocess boundary. `docs/api-reference.md` regenerated. Gate passed clean.
- [x] **Search by folder name (CLI/TUI/GUI):** Folders whose name matches the query now surface as true directory results (same `FileSearchResult`/scoring pipeline as files), not just files inside matching folders. `FileWalkerPort.iter_files`/`collect_files` gained `include_directories` (one combined `os.walk` pass, no duplicate tree walk); gated by the existing **File names** / `search_names` toggle only — no new option surface. Directories never participate in content/OCR/transcribe/CLIP matching (`_search_single_file` forces `search_contents=False` for `path.is_dir()`); respects `include_subdirectories`, hidden/noise filters, and `match_skipped_names` the same way files do. CLI JSON gained an additive `"type": "file"|"directory"` field; CLI `--names`/`--names-only` help text and `tui.hint.file_names` / `gui.help.search_names` (en/es) mention folder names. Tests: new `tests/unit/test_file_walker_directories.py` (10 cases), 12 new cases in `tests/unit/test_file_search.py` (folder-as-result, content-only exclusion, root excluded, nested + `include_subdirectories`, hidden/noise, fuzzy ranking parity vs. filenames), CLI (`tests/cli/test_cli.py`: flat + JSON `type` + content-only exclusion), TUI (`tests/tui/test_file_search_tui.py`: real-engine names-only hit + content-only exclusion; regenerated 4 snapshot files for the changed hint copy), GUI (`tests/gui/test_gui_flows.py`: click-driven names-only folder hit + selection/preview path, content-only exclusion). Docs: `docs/cli.md` (Scope section), `docs/gui.md`, `docs/tui.md`. Design rationale in `memory/decisions.md` (2026-09-06). Branch `cursor/search-by-folder-name-b203`; PR → `feature/1.8.0`.
- [ ] **Unlimited OCR (semantic):** When `[semantic]` deps are installed, download/use [`baidu/Unlimited-OCR`](https://huggingface.co/baidu/Unlimited-OCR); else keep Tesseract. Benchmarks (quality+speed), unit + integration tests. Draft PR #38 → `feature/1.8.0`; Daniel GPU QA before undraft.
- [ ] **Media preview panel:** Improve content preview to show **images**, **video**, and **audio** (not only text). Draft PR #39 → `feature/1.8.0`; Team Lead LGTM; Daniel visual smoke before undraft.
- [ ] **Search by folder name:** Match folder/directory names in search across **GUI**, **TUI**, and **CLI**. Topic branch off `feature/1.8.0`; unit + GUI/TUI/CLI tests required. Team Lead marks PR ready-for-review when OK.
- [ ] **Windows installer migration — NSIS:** Replace Inno Setup outer shell with NSIS (permissive license for commercial distribution).

## Bugs / sub-tasks discovered

- [x] Preview file open spam (`DirectWrite: CreateFontFaceFromHDC` for `8514oem`/`Fixedsys`, then `OpenType support missing` for Tahoma/Arial/… scripts) — preview HTML used bare `font-family:monospace`, which Windows Qt resolves as TypeWriter bitmap fonts DirectWrite cannot load. Fixed via `preview_font_family()` (Consolas / Menlo / monospace) in `gui/preview.py`, matching QML; unit tests added. `checks-win-quiet` PASSED. Applied from worktree `r9oj`.
- [x] Search aborts or noisy failures on PermissionError (errno 13) for inaccessible files/folders under large trees (e.g. home). Fixed: skip + warn via existing ⚠ skipped-files UI; prune unlistable dirs during walk; parent prune after denied file when folder is not listable.
- [x] `AccentButton` binding loop on `foreground` at GUI launch — `foreground` read `control.palette.*` while assigning `palette.buttonText`. Fixed via sibling `SystemPalette` for face/disabled colours; `checks-win-quiet` PASSED.
- [x] Search button stays dark (non-accent) after cancel — `_on_search_thread_finished` always set `_last_snapshot`, clearing `stale`; Search binds `accent: controller.stale`. Not Windows-only. Fixed: commit baseline only on successful finish; clear baseline on cancel/error. Gate passed.
- [x] macOS Search button misaligned / label off-centre + black OK text — forced matchHeight clipped native 32px bevel; WCAG onAccent black for `#308cc6`. Fixed: Windows-only stretch; darwin white onAccent; `palette.buttonText` binding. Gate passed.
- [x] Options/filters dialog OK button black text (Windows accent `#0078d4` → black via `contrast_text_on` max-contrast rule). Fixed by preferring white at AA 4.5:1; regression test added; gate passed.
- [x] QML results ListView warning (`DelegateModel::cancel: index out range`) — `ResultsModel.clear()`/`replace_results()` now use row-based `beginRemoveRows`/`endRemoveRows` (+ `beginInsertRows`) instead of a full `beginResetModel()`, so the delegate model cancels in-flight items with valid indices. Added `tests/unit/test_gui_models.py` (deterministic signal assertions: rows removed/inserted, never `modelReset`) + a GUI regression test in `test_gui_qml_load.py` (drives two search cycles through loaded QML, asserts no `DelegateModel`/`index out range` warning). Gate passed.
- [x] Qt engine-destruction warning (`in the process of being created`) — root cause was teardown order: `QQmlEngine` was destroyed (via interpreter shutdown) while the `QQuickWindow` was still alive, so pending async delegate incubations kept `inProgressCreations > 0`. Fixed by destroying root windows before the engine in `gui/app.py` and `installer/app.py` (then flushing `DeferredDelete`); added a regression assertion in `test_gui_qml_load.py`. Gate passed.
- [x] Host-portal registration warning (`Failed to register with host portal … Connection already associated with an application ID`) — Qt 6.11 deferred `org.freedesktop.host.portal.Registry.Register` because `desktopFileName()` was empty at `QGuiApplication` init; a later `follow_system_color_scheme()` portal read claimed the connection first. Fixed by setting identity via static setters before construction (`apply_app_identity`).
- [x] Dialog OK buttons dark in dark mode — `DialogButtonBox` (FluentWinUI3) forces `highlighted` off on child buttons, so `AccentButton`'s `fillColor`/`foreground` fell back to `palette.button` (5.8%-alpha white → dark). Fixed by decoupling accent state into an explicit `accent` bool (default true) in `AccentButton.qml`; Search button toggles `accent` for the stale state; added `optionsOkButton`/`filtersOkButton` objectNames + a regression test asserting accent fill/foreground. Gate passed.
- [x] GUI freezes every few hundred ms on heavy progressive search — in-process QThread scoring held the GIL; status spinner/`statusChanged` and mid-list inserts amplified ListView lag. Fixed via subprocess isolation + stream-append + coalescing; process pools disabled for light worker searches (fork storm).
- [x] Frozen (non-animating) activity spinner after status coalesce — glyph now lives on `activitySpinner`; status body stays coalesced. Progress bar indeterminate until scan total exists.
- [x] Linux/Material: black Search label + black magnifier glyph next to a white dialog OK label — Material ignores `palette.buttonText` and paints `primaryHighlightedTextColor`, while the Search button hand-tinted its own `contentItem` from the WCAG `foreground`. Fixed by letting the style's `IconLabel` paint label and icon (`defaultIconColor`), pinning `palette.brightText` for Fusion/Basic, and gating `icon.color` to macOS only.
- [x] Latent packaging bug: `Main.qml` imported `Qt5Compat.GraphicalEffects`, but both the macOS and Linux AppImage prune scripts delete that QML module — removed with the `ColorOverlay` tint.
