# Active Context

_Last updated: 2026-08-18_

## Branch

- `feature/fixes_1.6.6` — fixes and improvements for v1.6.6.
- 5 commits ahead of `origin/feature/fixes_1.6.6` (`e5b844e` memory bank tracked, `95f499e` merge of `feature/preview-highlight-find`, `965f1c3` preview feature, `35adda3` memory, `b4cd2d1` button GUI improvements).
- Working tree is **not clean** — uncommitted changes pending (see "Current uncommitted work").

## Done this session: memory bank now tracked in git

- `memory/` is no longer gitignored; tracked as per-branch state (commit `e5b844e`).
- `decisions.md` append-only (`.gitattributes` `merge=union`); `progress.md`/`activeContext.md` reset at branch start (section 4 of `.cursor/rules/agent-memory.mdc` + `memory/README.md`).
- Root `README.md` links to `memory/README.md` under Development.

## Current focus

Polishing and fixing the Windows-first GUI/installer release for v1.6.6.

### Active blocker: `DelegateModel::cancel: index out range` still reproduces

The user still sees `DelegateModel::cancel: index out range 6 0` / `10 1` while running searches, even with the uncommitted `_clear_selection()` fix present. Root cause is now pinned down:

- The warning is `QQmlDelegateModel::cancel(index)` logging `index` vs `d->m_compositor.count(group)` — i.e. it is asked to cancel a delegate at a stale row `index` when the delegate compositor only holds `count` items. So `6 0` = cancel row 6 with 0 delegates; `10 1` = cancel row 10 with 1 delegate.
- Trigger: `ResultsModel.clear()` / `replace_results()` both do a full `beginResetModel()`/`endResetModel()`. The reset invalidates rows while the `resultsView` delegate model still has in-flight (async-incubated) delegates, and `resultsView.currentIndex` is bound to `controller.selectedResult` (QML binding re-evaluates **asynchronously**), so it lags the synchronous reset.
- `_clear_selection()` sets `selectedResult = -1` and emits `selectedResultChanged` before the reset, but that only clears the Python property — it cannot synchronously drive the QML `currentIndex` binding, and it does nothing for the reset's own in-flight delegate cancellation.
- The existing unit test `test_given_previous_selection_when_beginning_new_search_then_selection_is_cleared` only asserts the Python `selectedResult == -1`, so it cannot catch the QML-side race.

Candidate fixes to evaluate next (not yet chosen):

1. **Stop full-reset**: rewrite `ResultsModel.clear()` / `replace_results()` to use `beginRemoveRows`/`endRemoveRows` (+ `beginInsertRows` for replace) instead of `beginResetModel`/`endResetModel`, so the delegate model cancels in-flight items with valid indices.
2. **QML synchronous clear**: connect to `controller.resultsModel.modelAboutToBeReset` in `Main.qml` and set `resultsView.currentIndex = -1` there (must preserve the `selectedResult` binding via a `Binding` element or a `Connections.onSelectedResultChanged` re-sync).
3. **Defer the reset** in Python (`QTimer.singleShot(0, ...)`) so the `currentIndex` binding settles first — less deterministic, last resort.

### Recently merged: preview highlighting / find / context menus

`feature/preview-highlight-find` was merged into `feature/fixes_1.6.6` (merge commit `95f499e`; feature commit `965f1c3`). Quality gate passed clean (`checks-win.ps1 -Fix`: ruff/basedpyright/pip-audit/build/pytest all pass; only shell skipped — no shellcheck/shfmt on PATH).

- Theme-aware preview syntax highlighting (`PreviewPalette` light/dark in `gui/preview.py`).
- Ctrl+F in-preview find bar (`Main.qml`) + controller find slots.
- Preview right-click menu + "Open containing folder" on the results list.
- Jump-to-line on match click (`LineNumberRole`).
- `reveal_path` on `DesktopPort` (os/gui/tui adapters).
- en/es i18n strings.

### Fixed this session: Qt engine-destruction warning

The GUI/installer logged `There are still "1" items in the process of being created at engine destruction.` on exit. Root cause: `QQmlEnginePrivate::~QQmlEnginePrivate` warns when `inProgressCreations > 0`, and the engine was being destroyed (implicitly, at interpreter shutdown) while the `QQuickWindow` root was still alive — so pending async ListView delegate incubations were never cancelled. Fix: in `gui/app.py` (`run_gui`) and `installer/app.py` (`run_installer`), after `app.exec()` destroy the root windows first (`root.deleteLater()`), then `engine.deleteLater()`, then flush `QEvent.Type.DeferredDelete` via `sendPostedEvents` + `processEvents()`. Deleting the window cascades to the `QQmlDelegateModel`/`Loader` incubators, which `clear()` and decrement `inProgressCreations` before the engine destructor runs. Regression coverage: `tests/gui/test_gui_qml_load.py` now captures the message and asserts teardown is clean; `tests/unit/test_gui_app.py` fakes updated for the new teardown calls. Full quality gate passed (exit 0; shell step skipped).

### Fixed this session: preview highlighting cutoff

Removed the undocumented plain fallback in `src/srxy/adapters/inbound/gui/preview.py` that dropped syntax highlighting for previews over 16 KB (`_PLAIN_PREVIEW_BYTES`) or 500 lines. All text previews now get syntax colors; content is still capped at 64 KB / 2000 lines. Added `tests/unit/test_gui_preview.py::test_given_long_python_file_when_formatting_then_still_highlights`. Full quality gate passed (exit 0; shell step skipped — no shellcheck/shfmt on PATH). Not yet committed.

### Branch theme (vs `main`)

- **Windows GUI** — FluentWinUI3 style engine (`qt_theme.py`), fallback Universal → Windows; `SplitView` results pane falls back to Fusion until Fluent styles it.
- **Primary CTAs** — shared `AccentButton` (SrxyControls) for WCAG black/white contrast.
- **Windows installer** — Inno Setup offline installer (`packaging/windows/`), download-based tessdata language packs (third-party binary policy).
- **macOS** — installer/signing path hardening + squircle icon regen.
- **OCR** — orientation fixtures + orientation-aware OCR text.
- **Refactors** — GPU availability, install paths, installer catalog/vendor/path-setup, search worker.
- **i18n** — en/es string updates.
- **Tests/docs** — large test expansion (theme, installer, OCR orientation, tessdata, search worker), docs + screenshots.

### Current uncommitted work (not yet committed)

A batch of uncommitted edits on top of `95f499e` fixes QML preview/selection warnings and refactors the preview header:

- `controller.py` — new `previewFilePath` property; new `_clear_selection()` called before results-model clear/replace (first attempt at the `DelegateModel::cancel: index out range` warning — insufficient, see "Active blocker"); preview header now shows only `score · matched` (path moved to `previewFilePath`).
- `preview.py` — removed the large-payload plain-preview fallback (`_PLAIN_PREVIEW_BYTES`); preview always renders the numbered/syntax-coloured HTML layout.
- `qt_theme.py` — `contrast_text_on` now prefers white when it clears AA 4.5:1 (options/filters OK button black-text fix; see "Recently fixed").
- `qml/Main.qml` — preview header/path split to match `previewFilePath`; the path label elides with `Text.ElideRight` (no wrap) and shows a hover `ToolTip` with the full path, while `score · matched` stays visible alongside.
- `tests/unit/test_gui_controller.py`, `tests/unit/test_gui_preview.py`, `tests/unit/test_qt_theme.py` — updated for the above.
- `app.py` (gui) + `installer/app.py` — teardown now destroys root windows before the engine and flushes `DeferredDelete` (fixes the engine-destruction warning).
- `tests/gui/test_gui_qml_load.py` — now also asserts no `in the process of being created` warning during teardown, plus a regression test that the options/filters OK buttons render accent fill/foreground.
- `tests/unit/test_gui_app.py` — fakes extended for the new teardown calls.
- `shared/qml/SrxyControls/AccentButton.qml` — decoupled accent fill from the standard `highlighted` property (a new `accent` bool) because `DialogButtonBox` clobbers `highlighted` on child buttons.
- `qml/Main.qml` — Search button now toggles `accent` (was `highlighted`) for the stale state; `optionsOkButton` / `filtersOkButton` objectNames added.
- `.cursor/rules/agent-memory.mdc` — rewritten (memory file roles + update triggers + hand-off protocol).

### Recently fixed: dialog OK buttons dark in dark mode

`AccentButton` chose accent vs. secondary fill by reading the standard `highlighted` property, which `DialogButtonBox` (FluentWinUI3) forcibly overrides on its child buttons. In dark mode the OK/Yes buttons fell back to `palette.button` (5.8%-alpha white → dark). Fixed by giving `AccentButton` an explicit `accent` bool (default true) and pointing the Search button's dynamic stale toggle at `accent`. Added `optionsOkButton` / `filtersOkButton` objectNames and a regression test asserting the buttons render `fillColor == accent` / `foreground == onAccent`. Quality gate passed (only shell step skipped — no shellcheck/shfmt on PATH). Uncommitted.

### Recently fixed: options OK button black text

`contrast_text_on` in `qt_theme.py` used a pure "max contrast wins" rule; for the Windows accent `#0078d4` that picks black (4.637 vs 4.529), so the options/filters dialog OK button (`AccentButton`) showed black text while Cancel stayed white. Fixed to prefer white whenever white still clears AA 4.5:1, falling back to max-contrast otherwise. Added `test_given_windows_accent_fill_when_contrast_text_then_returns_white`. Quality gate passed (only shell step skipped — no shellcheck/shfmt on PATH). Uncommitted.

### Key files touched

- `src/srxy/adapters/inbound/gui/qt_theme.py` (new) — theme/style selection; `contrast_text_on` now prefers white at AA 4.5:1.
- `src/srxy/adapters/inbound/gui/qml/Main.qml`, `controller.py`, `app.py`, `app_icon.py`.
- `src/srxy/adapters/inbound/shared/qml/SrxyControls/AccentButton.qml` (new).
- `src/srxy/adapters/inbound/installer/*` — catalog, vendor, path_setup, tessdata_langs, privacy, install/uninstall, qml.
- `packaging/windows/*` (new) — Inno Setup offline installer + smoke script.
- `src/srxy/adapters/outbound/ocr/ocr_text.py` — orientation handling.
- `pyproject.toml` — still `1.6.5`.

## Next steps

1. **Resolve the `DelegateModel::cancel: index out range` warning** (pick one of the candidate fixes above; likely avoid the full model reset in `ResultsModel.clear()`/`replace_results()`), add/adjust a test that exercises the model reset, then run the GUI test suite and quality gate (user will signal when the other process is done).
2. Finish/verify the uncommitted preview/selection work (the engine-destruction warning is now fixed and its repro script removed), then commit it.
3. Bump `pyproject.toml` version to `1.6.6` (and any installer meta referencing it).
4. Push the unpushed commits.
5. Final QA: visually check Windows dark mode (incl. results `SplitView` grips), macOS native controls, Linux Material light/dark, and the Windows/macOS installers.
6. Run the full local quality gate before release: `uv run task checks-full` (Windows: `uv run task checks-win-full`).
