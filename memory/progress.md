# Progress

_Last updated: 2026-08-27_

## v1.6.6 — fixes and improvements

### Done

- [x] Windows GUI (PR #28) — FluentWinUI3 theme, fallback Universal → Windows.
- [x] Shared `AccentButton` + button GUI improvements.
- [x] Windows offline Inno Setup installer + download-based tessdata packs.
- [x] macOS installer/signing path hardening + icon regen.
- [x] OCR orientation fixtures + orientation-aware OCR text.
- [x] GPU availability + installer (catalog/vendor/path-setup) refactors.
- [x] en/es i18n updates.
- [x] Test expansion (theme, installer, OCR orientation, tessdata, search worker, GUI snapshots).
- [x] Preview theme-aware highlighting, in-preview find, context menus, reveal_path (merged `feature/preview-highlight-find` → `feature/fixes_1.6.6`, `95f499e`).
- [x] Preview syntax highlighting applies to all file sizes (removed the 16 KB / 500-line plain fallback in `gui/preview.py`; added regression test).
- [x] Preview header file-path elision: long file names in the preview panel now elide with `...` (right) and show the full path on hover (`ToolTip`); metadata `score · matched` stays visible. Added `previewFilePath` property + unit test. Gate passed.
- [x] Dialog OK buttons render dark in dark mode — `AccentButton` relied on the standard `highlighted` property, which `DialogButtonBox` clobbers on its child buttons (FluentWinUI3 delegate drives it from `buttonRole`). Replaced with an explicit `accent` bool; Search button now toggles `accent` instead of `highlighted`. Regression test asserts OK buttons render accent fill/foreground. Gate passed.
- [x] Linux "Browse" button now opens the native folder picker — `prefer_native_file_dialogs()` sets `QT_QPA_PLATFORMTHEME=xdgdesktopportal` on Linux before `QGuiApplication` (gui + installer), routing `FolderDialog` through the desktop portal. macOS/Windows untouched. Unit tests added; gate passed; committed (`2b9e722`).
- [x] Host-portal registration warning gone — set Qt app identity (name/org/desktop file name) via static setters **before** `QGuiApplication` construction (`apply_app_identity` in `app_icon.py`), so Qt registers with `org.freedesktop.host.portal.Registry` at init time instead of after a portal colour-scheme read (which logged `Connection already associated with an application ID`).
- [x] Agent-verbosity quality gate — `--quiet` (Unix) / `-Quiet` (Windows) on `checks.sh`/`checks-win.ps1`: pytest collapses to sparse `[gate] N/total` progress lines (new `scripts/quality/internal/agent_progress.py` plugin), passing light-step logs are suppressed on the verify path, and the heavy pass silences HF/transformers/tqdm noise. Failures still print short tracebacks + `-ra` summary; `--full`/CI unchanged. Day-to-day Taskipy tasks stay verbose; dedicated `*-quiet` tasks (`checks-quiet`/`checks-fix-quiet`/`checks-full-quiet`/`checks-full-cpu-quiet`/`checks-win-quiet`/`checks-win-fix-quiet`/`checks-win-full-quiet`/`checks-win-full-cpu-quiet`) exist for agents, and `AGENTS.md` instructs agents to always use them. Verified: `uv run task checks` (verbose) and `uv run task checks-quiet` (quiet) both PASSED.
- [x] Native-first `AccentButton` — dropped the custom `Rectangle`/`Text` background+contentItem (and hardcoded 80x32 size) in favour of native chrome recoloured via `highlighted`. Qt 6.11 `DialogButtonBox` calls `setHighlighted(button == defaultButton)` on all children every layout pass, so dialog OK/Yes buttons now set `DialogButtonBox.defaultButton` (plus `AcceptRole`) instead of relying on a `highlighted` binding. `qt_theme.py` pins `QPalette.Accent` to the button accent so FluentWinUI3's highlighted fill matches `SrxyTheme.accent`. Regression test now asserts `highlighted`/`foreground`. Gate passed.
- [x] QML results ListView warning (`DelegateModel::cancel: index out range`) — `ResultsModel.clear()`/`replace_results()` now use row-based `beginRemoveRows`/`endRemoveRows` (+ `beginInsertRows`) instead of a full `beginResetModel()`, so the delegate model cancels in-flight items with valid indices. Added `tests/unit/test_gui_models.py` (deterministic signal assertions: rows removed/inserted, never `modelReset`) + a GUI regression test in `test_gui_qml_load.py` (drives two search cycles through loaded QML, asserts no `DelegateModel`/`index out range` warning). Gate passed.
- [x] Version bump `1.6.5` → `1.6.6` — `pyproject.toml` `1.6.6`, `min_srxy_version` `1.6.6` in both `installer_meta.toml` copies, `uv.lock` regenerated, tests synced (`test_updates_path_i18n.py` assertion → `1.6.6`; `test_installer_online.py` mocked PyPI responses → `1.6.6`).
- [x] Full quality gate before release — `checks-fix-quiet` PASSED (ruff/shell/basedpyright/pip-audit/build/pytest all clean, 123 heavy tests in ~4:44; first `checks-quiet` run flagged only a Ruff format issue in the new test file, fixed). Clean cache-free unit pass: 791 passed, 2 skipped.
- [x] macOS Search button alignment + accent label color — Search stretch-to-field only on Windows; macOS/Linux native size + `AlignVCenter`. `AccentButton` sets `palette.buttonText: foreground`; darwin `SrxyTheme.onAccent` always white (Aqua). Tests: platform-aware layout assert, OK `palette.buttonText == onAccent`, darwin onAccent unit test. Gate passed (`checks-quiet`).
- [x] Linux Material pinkish window background — Qt 6.11 M3 default surface `#fffbfe`; Linux now sets `QT_QUICK_CONTROLS_MATERIAL_BACKGROUND` to `#ffffff` (light) / `#303030` (dark) from the active colour scheme after `follow_system_color_scheme`. Unit tests added.

### Open

- [ ] Final QA — Windows dark mode (incl. `SplitView` grips), Linux Material light/dark (background fix applied; visual confirm), Windows/macOS installers (macOS Search/OK visual QA done).

## Bugs / sub-tasks discovered

- [x] macOS Search button misaligned / label off-centre + black OK text — forced matchHeight clipped native 32px bevel; WCAG onAccent black for `#308cc6`. Fixed: Windows-only stretch; darwin white onAccent; `palette.buttonText` binding. Gate passed.
- [x] Options/filters dialog OK button black text (Windows accent `#0078d4` → black via `contrast_text_on` max-contrast rule). Fixed by preferring white at AA 4.5:1; regression test added; gate passed.
- [x] QML results ListView warning (`DelegateModel::cancel: index out range`) — `ResultsModel.clear()`/`replace_results()` now use row-based `beginRemoveRows`/`endRemoveRows` (+ `beginInsertRows`) instead of a full `beginResetModel()`, so the delegate model cancels in-flight items with valid indices. Added `tests/unit/test_gui_models.py` (deterministic signal assertions: rows removed/inserted, never `modelReset`) + a GUI regression test in `test_gui_qml_load.py` (drives two search cycles through loaded QML, asserts no `DelegateModel`/`index out range` warning). Gate passed.
- [x] Qt engine-destruction warning (`in the process of being created`) — root cause was teardown order: `QQmlEngine` was destroyed (via interpreter shutdown) while the `QQuickWindow` was still alive, so pending async delegate incubations kept `inProgressCreations > 0`. Fixed by destroying root windows before the engine in `gui/app.py` and `installer/app.py` (then flushing `DeferredDelete`); added a regression assertion in `test_gui_qml_load.py`. Gate passed.
- [x] Host-portal registration warning (`Failed to register with host portal … Connection already associated with an application ID`) — Qt 6.11 deferred `org.freedesktop.host.portal.Registry.Register` because `desktopFileName()` was empty at `QGuiApplication` init; a later `follow_system_color_scheme()` portal read claimed the connection first. Fixed by setting identity via static setters before construction (`apply_app_identity`).
- [x] Dialog OK buttons dark in dark mode — `DialogButtonBox` (FluentWinUI3) forces `highlighted` off on child buttons, so `AccentButton`'s `fillColor`/`foreground` fell back to `palette.button` (5.8%-alpha white → dark). Fixed by decoupling accent state into an explicit `accent` bool (default true) in `AccentButton.qml`; Search button toggles `accent` for the stale state; added `optionsOkButton`/`filtersOkButton` objectNames + a regression test asserting accent fill/foreground. Gate passed.
