# Progress

_Last updated: 2026-08-18_

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

### Open

- [ ] Commit the uncommitted batch (preview fallback/header, selection, theme, memory rule), then push the 4 ahead commits.
- [ ] Bump `pyproject.toml` version `1.6.5` → `1.6.6` (and installer meta).
- [ ] Final QA — Windows dark mode (incl. `SplitView` grips), macOS native, Linux Material light/dark, Windows/macOS installers.
- [ ] Full quality gate before release (`checks-full` / `checks-win-full`).

## Bugs / sub-tasks discovered

- [x] Options/filters dialog OK button black text (Windows accent `#0078d4` → black via `contrast_text_on` max-contrast rule). Fixed by preferring white at AA 4.5:1; regression test added; gate passed.
- [ ] QML results ListView warning (`DelegateModel::cancel: index out range`) — **still reproduces** during searches (observed `6 0` / `10 1`) despite the uncommitted `_clear_selection()` in `controller.py`. Root cause: `ResultsModel.clear()`/`replace_results()` do a full `beginResetModel()` while the `resultsView` `currentIndex` binding (async) and in-flight delegates are stale. Fix pending — likely stop the full reset (use remove/insert rows) or clear `currentIndex` in QML on `modelAboutToBeReset`.
- [x] Qt engine-destruction warning (`in the process of being created`) — root cause was teardown order: `QQmlEngine` was destroyed (via interpreter shutdown) while the `QQuickWindow` was still alive, so pending async delegate incubations kept `inProgressCreations > 0`. Fixed by destroying root windows before the engine in `gui/app.py` and `installer/app.py` (then flushing `DeferredDelete`); added a regression assertion in `test_gui_qml_load.py`. Gate passed.
