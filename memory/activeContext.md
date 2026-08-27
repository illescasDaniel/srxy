# Active Context

_Last updated: 2026-08-20_

## Branch

- `feature/fixes_1.6.6` — fixes and improvements for v1.6.6.
- Ahead of `origin/feature/fixes_1.6.6` by 1 commit: `d54c86c` (row-based `ResultsModel` mutations + v1.6.6 bump). Not pushed.
- Working tree clean.

## Done this session (committed + pushed)

### Agent-verbosity quality gate (`--quiet` / `-Quiet`) — `b40975c`

- AI-agent runs of the quality gate were burning tokens on pytest's `-v` output (~1 line per test) plus heavy-pass model noise. Added an opt-in quiet flag to both gates (`checks.sh --quiet`, `checks-win.ps1 -Quiet`) that exports `LIB_GATE_QUIET=true`.
- `pytest.sh` / `checks-win.ps1` append `-q --no-header -ra --tb=short -p agent_progress`; new plugin `scripts/quality/internal/agent_progress.py` prints sparse `[gate] N/total (ok=.. fail=..)` lines (nodeid-set totals — xdist workers each report the full collection). Heavy pass uses `LIB_PYTEST_PROGRESS_INTERVAL=1` + `HF_HUB_DISABLE_PROGRESS_BARS`/`TRANSFORMERS_VERBOSITY=error`/`TOKENIZERS_PARALLELISM=false`/`TQDM_DISABLE=1`.
- `checks.sh` `gate_finish_step` now suppresses passing light-step logs on the verify path (loads status first; cats only on failure or non-quiet). `-p no:cacheprovider` dropped — it removes pytest's `--ff` option.
- Day-to-day Taskipy tasks (`checks`/`checks-fix`/`checks-win`/`checks-win-fix`) remain **verbose**; dedicated `*-quiet` tasks added for all gate modes on both platforms (`checks-quiet`, `checks-fix-quiet`, `checks-full-quiet`, `checks-full-cpu-quiet`, `checks-win-quiet`, `checks-win-fix-quiet`, `checks-win-full-quiet`, `checks-win-full-cpu-quiet`). `AGENTS.md` instructs agents to always use the quiet variants. `--full`/`--full+cpu`/CI stay verbose.
- Verified: `uv run task checks` (verbose) and `uv run task checks-quiet` (quiet) both PASSED (122 heavy tests, ~4.9 min each).

### Host-portal registration warning — `ce6d367`

- GUI/installer logged `qt.qpa.services: Failed to register with host portal … Connection already associated with an application ID` on Linux (Qt 6.11 + KDE/Wayland). Root cause: identity was set *after* `QGuiApplication` construction, so `desktopFileName()` was empty at init and Qt deferred `org.freedesktop.host.portal.Registry.Register` to a queued callback — by then `follow_system_color_scheme()` (inside `apply_qt_quick_theme`) had already made a portal colour-scheme read that claimed the connection.
- Fix: `app_icon.py` gains `apply_app_identity(name)` (static `setApplicationName` / `setOrganizationName` / `setDesktopFileName`); `apply_desktop_file_name` is now static-only (`name`). Both `gui/app.py` (`run_gui`) and `installer/app.py` (`run_installer`) call `apply_app_identity(...)` **before** `QGuiApplication` is constructed.
- Unit tests updated: `test_app_icon.py` (static signature + `apply_app_identity` cases), `test_gui_app.py` (patch `apply_app_identity`, drop now-unused `FakeApp` name/org setters).

### Linux native folder picker — `2b9e722`

- The GUI/installer "Browse" button (`FolderDialog`) rendered the Qt Quick non-native dialog on Linux because Qt's auto-selected KDE/GNOME platform theme provides no native folder dialog.
- Added `prefer_native_file_dialogs()` to `gui/qt_theme.py`: on Linux it `setdefault`s `QT_QPA_PLATFORMTHEME=xdgdesktopportal`, which routes file/folder dialogs through `org.freedesktop.portal.FileChooser` → the native KDE picker. Called in `gui/app.py` (`run_gui`) and `installer/app.py` (`run_installer`) before `QGuiApplication` is constructed.
- macOS/Windows untouched (their dialogs are already native). User-set `QT_QPA_PLATFORMTHEME` preserved via `setdefault`.
- Unit tests: `test_qt_theme.py` (linux sets portal theme; preset env preserved; win32/darwin untouched); `test_gui_app.py` now mocks the helper.

### Native-first `AccentButton` — `41df699`

- `AccentButton` no longer replaces the native `background`/`contentItem` (which dropped Material ripple/elevation, Fluent hover/press, per-style radius/size). It is now a plain `Button` with `highlighted: control.accent` and no custom chrome.
- Read the Qt 6.11 source to settle why dialog OK buttons lost their accent: `QQuickDialogButtonBoxPrivate::updateLayout()` calls `setHighlighted(button == defaultButton)` on every child each layout pass — so a QML `highlighted` binding is clobbered inside a box and `buttonRole: AcceptRole` alone does NOT highlight.
- Fix: set `DialogButtonBox.defaultButton` on the primary dialog buttons — `optionsOkButton`, `filtersOkButton` (GUI), `updateYesButton` (update dialog) — in addition to `AcceptRole`. Search/installer Launch are not in a box, so `highlighted: accent` applies directly.
- FluentWinUI3 paints its highlighted fill from `palette.accent` (not `palette.button`/custom background), so added `qt_theme._apply_button_accent_palette` to pin `QPalette.Accent` to the resolved button accent (called in `apply_qt_quick_theme`).
- `foreground` is retained only for the Search button's custom icon+text `contentItem`.
- Tests: `test_gui_qml_load.py` accent regression now asserts `highlighted is True` + `foreground == onAccent`; `test_qt_theme.py` added `_apply_button_accent_palette` coverage.
- Full quality gate passed clean (ruff/shell/basedpyright/pip-audit/build/pytest all pass; 0 errors).

## Done this session: fixed host-portal registration warning

- GUI/installer logged `qt.qpa.services: Failed to register with host portal … Connection already associated with an application ID` on Linux (Qt 6.11 + KDE/Wayland). Root cause: identity was set *after* `QGuiApplication` construction, so `desktopFileName()` was empty at init and Qt deferred `org.freedesktop.host.portal.Registry.Register` to a queued callback — by then `follow_system_color_scheme()` (inside `apply_qt_quick_theme`) had already made a portal colour-scheme read that claimed the connection.
- Fix: `app_icon.py` gains `apply_app_identity(name)` (static `setApplicationName` / `setOrganizationName` / `setDesktopFileName`); `apply_desktop_file_name` is now static-only (`name`). Both `gui/app.py` (`run_gui`) and `installer/app.py` (`run_installer`) call `apply_app_identity(...)` **before** `QGuiApplication` is constructed.
- Unit tests updated: `test_app_icon.py` (static signature + `apply_app_identity` cases), `test_gui_app.py` (patch `apply_app_identity`, drop now-unused `FakeApp` name/org setters). Committed (`ce6d367`).

## Done this session: Linux native folder picker for the "Browse" button

- The GUI/installer "Browse" button (`FolderDialog`) rendered the Qt Quick non-native dialog on Linux because Qt's auto-selected KDE/GNOME platform theme provides no native folder dialog.
- Added `prefer_native_file_dialogs()` to `gui/qt_theme.py`: on Linux it `setdefault`s `QT_QPA_PLATFORMTHEME=xdgdesktopportal`, which routes file/folder dialogs through `org.freedesktop.portal.FileChooser` → the native KDE picker. Called in `gui/app.py` (`run_gui`) and `installer/app.py` (`run_installer`) before `QGuiApplication` is constructed.
- macOS/Windows untouched (their dialogs are already native). User-set `QT_QPA_PLATFORMTHEME` preserved via `setdefault`.
- Unit tests: `test_qt_theme.py` (linux sets portal theme; preset env preserved; win32/darwin untouched); `test_gui_app.py` now mocks the helper.
- Quality gate passed.

## Done this session: memory bank now tracked in git

- `memory/` is no longer gitignored; tracked as per-branch state (commit `e5b844e`).
- `decisions.md` append-only (`.gitattributes` `merge=union`); `progress.md`/`activeContext.md` reset at branch start (section 4 of `.cursor/rules/agent-memory.mdc` + `memory/README.md`).
- Root `README.md` links to `memory/README.md` under Development.

## Current focus

macOS Search button + accent OK text — done (user-verified + tests + gate). Uncommitted; ready to commit when asked.

### Done this session (uncommitted): macOS button alignment + OK text

- `AccentButton.qml`: `palette.buttonText: control.foreground`.
- `Main.qml`: Search stretch-to-field / padding / `AlignTop` only on Windows (`Binding` + `restoreMode`); macOS/Linux native size + `AlignVCenter`; warning ToolButtons same alignment gate.
- `qt_theme.py`: darwin `SrxyTheme.onAccent` always white (Aqua; `#308cc6` WCAG would pick black).
- Tests: platform-aware layout assert (`test_gui_query_layout.py`); OK `palette.buttonText == onAccent` (`test_gui_qml_load.py`); darwin onAccent unit test (`test_qt_theme.py`).
- Gate: `checks.sh --quiet --fix` + `checks.sh --quiet` PASSED (123 heavy tests).

### Next steps

1. Commit when asked (macOS button fix + tests + memory).
2. Remaining Final QA: Windows dark mode / Linux Material / installers.

### Done this session: native-first `AccentButton` (committed, `41df699`)

- `AccentButton` no longer replaces the native `background`/`contentItem` (which dropped Material ripple/elevation, Fluent hover/press, per-style radius/size). It is now a plain `Button` with `highlighted: control.accent` and no custom chrome.
- Read the Qt 6.11 source to settle why dialog OK buttons lost their accent: `QQuickDialogButtonBoxPrivate::updateLayout()` calls `setHighlighted(button == defaultButton)` on every child each layout pass — so a QML `highlighted` binding is clobbered inside a box and `buttonRole: AcceptRole` alone does NOT highlight.
- Fix: set `DialogButtonBox.defaultButton` on the primary dialog buttons — `optionsOkButton`, `filtersOkButton` (GUI), `updateYesButton` (update dialog) — in addition to `AcceptRole`. Search/installer Launch are not in a box, so `highlighted: accent` applies directly.
- FluentWinUI3 paints its highlighted fill from `palette.accent` (not `palette.button`/custom background), so added `qt_theme._apply_button_accent_palette` to pin `QPalette.Accent` to the resolved button accent (called in `apply_qt_quick_theme`).
- `foreground` is retained only for the Search button's custom icon+text `contentItem`.
- Tests: `test_gui_qml_load.py` accent regression now asserts `highlighted is True` + `foreground == onAccent`; `test_qt_theme.py` added `_apply_button_accent_palette` coverage.
- Full quality gate passed clean (ruff/shell/basedpyright/pip-audit/build/pytest all pass; 0 errors).

### Active blocker: `DelegateModel::cancel: index out range` — FIXED

Fixed by option 1 (stop full-reset). `ResultsModel.clear()` and `replace_results()` in `models.py` now emit row-level `beginRemoveRows`/`endRemoveRows` (+ `beginInsertRows`) instead of `beginResetModel`/`endResetModel`, so the QML delegate model cancels in-flight incubations with valid indices.

- Root cause (kept for reference): the warning is `QQmlDelegateModel::cancel(index)` logging `index` vs `d->m_compositor.count(group)` — asked to cancel a delegate at a stale row `index` when the compositor holds `count` items. `6 0` = cancel row 6 with 0 delegates. The full reset invalidated rows while `resultsView.currentIndex` (async binding, `Main.qml`) and in-flight async-incubated delegates were stale.
- `_clear_selection()` in `controller.py` remains (clears `selectedResult`, matches, preview before the model mutation).
- Regression coverage: `tests/unit/test_gui_models.py` (new, deterministic — asserts `clear()` emits `rowsRemoved` (0,N-1) and never `modelReset`; `replace_results()` emits remove+insert pairs; empty-model no-op cases) and `tests/gui/test_gui_qml_load.py::test_given_results_when_running_a_new_search_then_no_delegate_model_warning` (loads Main.qml, feeds `SearchFinishedEvent` results, re-runs `_begin_search`, asserts no `DelegateModel`/`index out range` captured). Both verified: unit tests fail against the old full-reset code; GUI suite passes serially (offscreen).
- Fallback options 2 (QML `modelAboutToBeReset` → `currentIndex = -1`) and 3 (deferred reset) were not needed.
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

Removed the undocumented plain fallback in `src/srxy/adapters/inbound/gui/preview.py` that dropped syntax highlighting for previews over 16 KB (`_PLAIN_PREVIEW_BYTES`) or 500 lines. All text previews now get syntax colors; content is still capped at 64 KB / 2000 lines. Added `tests/unit/test_gui_preview.py::test_given_long_python_file_when_formatting_then_still_highlights`. Full quality gate passed (exit 0; shell step skipped — no shellcheck/shfmt on PATH). Committed in `a2c2387`.

### Branch theme (vs `main`)

- **Windows GUI** — FluentWinUI3 style engine (`qt_theme.py`), fallback Universal → Windows; `SplitView` results pane falls back to Fusion until Fluent styles it.
- **Primary CTAs** — shared `AccentButton` (SrxyControls) for WCAG black/white contrast.
- **Windows installer** — Inno Setup offline installer (`packaging/windows/`), download-based tessdata language packs (third-party binary policy).
- **macOS** — installer/signing path hardening + squircle icon regen.
- **OCR** — orientation fixtures + orientation-aware OCR text.
- **Refactors** — GPU availability, install paths, installer catalog/vendor/path-setup, search worker.
- **i18n** — en/es string updates.
- **Tests/docs** — large test expansion (theme, installer, OCR orientation, tessdata, search worker), docs + screenshots.

### Current uncommitted work

None — committed in `d54c86c` (row-based `ResultsModel` + v1.6.6 bump + memory). Working tree clean; 1 commit ahead of origin.

### Recently fixed: dialog OK buttons dark in dark mode

`AccentButton` chose accent vs. secondary fill by reading the standard `highlighted` property, which `DialogButtonBox` (FluentWinUI3) forcibly overrides on its child buttons. In dark mode the OK/Yes buttons fell back to `palette.button` (5.8%-alpha white → dark). Fixed by giving `AccentButton` an explicit `accent` bool (default true) and pointing the Search button's dynamic stale toggle at `accent`. Added `optionsOkButton` / `filtersOkButton` objectNames and a regression test asserting the buttons render `fillColor == accent` / `foreground == onAccent`. Quality gate passed (only shell step skipped — no shellcheck/shfmt on PATH). Committed in `a2c2387` (then reworked to native-first `highlighted`+`defaultButton` in `41df699`).

### Recently fixed: options OK button black text

`contrast_text_on` in `qt_theme.py` used a pure "max contrast wins" rule; for the Windows accent `#0078d4` that picks black (4.637 vs 4.529), so the options/filters dialog OK button (`AccentButton`) showed black text while Cancel stayed white. Fixed to prefer white whenever white still clears AA 4.5:1, falling back to max-contrast otherwise. Added `test_given_windows_accent_fill_when_contrast_text_then_returns_white`. Quality gate passed (only shell step skipped — no shellcheck/shfmt on PATH). Committed in `a2c2387`.

### Key files touched

- `src/srxy/adapters/inbound/gui/qt_theme.py` (new) — theme/style selection; `contrast_text_on` now prefers white at AA 4.5:1.
- `src/srxy/adapters/inbound/gui/qml/Main.qml`, `controller.py`, `app.py`, `app_icon.py`.
- `src/srxy/adapters/inbound/shared/qml/SrxyControls/AccentButton.qml` (new).
- `src/srxy/adapters/inbound/installer/*` — catalog, vendor, path_setup, tessdata_langs, privacy, install/uninstall, qml.
- `packaging/windows/*` (new) — Inno Setup offline installer + smoke script.
- `src/srxy/adapters/outbound/ocr/ocr_text.py` — orientation handling.
- `pyproject.toml` — bumped to `1.6.6` (version bump done).

## Next steps

1. **Resolved: `DelegateModel::cancel: index out range` warning** — row-based `ResultsModel` mutations + deterministic unit tests + GUI regression test.
2. **Resolved: version bump 1.6.5 → 1.6.6** — `pyproject.toml`, both `installer_meta.toml` `min_srxy_version`, `uv.lock` regenerated, tests synced.
3. **Resolved: quality gate** — `checks-fix-quiet` PASSED (all 6 steps clean); cache-free unit pass 791 passed / 2 skipped.
4. **Committed** `d54c86c` (row-based `ResultsModel` + v1.6.6 bump + memory). Not yet pushed.
5. Final QA: visually check Windows dark mode (incl. results `SplitView` grips), macOS native controls, Linux Material light/dark, and the Windows/macOS installers; push when ready.
