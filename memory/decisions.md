# Decisions

_Log of significant technical, structural, or dependency choices. Newest first._

## 2026-08-20 — `ResultsModel` mutates rows, never full-resets

- **Context:** Searches logged `DelegateModel::cancel: index out range 6 0` / `10 1`. `ResultsModel.clear()` and `replace_results()` did a full `beginResetModel()`/`endResetModel()`, invalidating rows while the `resultsView` ListView's async `currentIndex` binding and in-flight (async-incubated) delegates were stale. `QQmlDelegateModel::cancel(index)` was then asked to cancel a delegate at a row index beyond the delegate compositor's count. `_clear_selection()` (Python-side) cannot synchronously drive the QML `currentIndex` binding, so it did not silence the warning.
- **Decision:** Rewrote `ResultsModel.clear()` to use `beginRemoveRows(_EMPTY_INDEX, 0, N-1)`/`endRemoveRows()` (skipped when empty) and `replace_results()` to emit a remove-all + insert-all pair, never `modelReset`. `MatchesModel` full resets were left unchanged (no async `currentIndex` binding on that view).
- **Rationale:** Row-level mutations let the QML delegate model cancel in-flight incubations with valid indices, avoiding the stale-index warning. The change preserves the row contract (order, limit) exactly. Added `tests/unit/test_gui_models.py` (deterministic signal assertions: `rowsRemoved`/`rowsInserted`, never `modelReset`, incl. empty-model no-op cases) and a GUI regression test in `test_gui_qml_load.py` (two search cycles through loaded QML; asserts no `DelegateModel`/`index out range` message). Unit tests were verified to fail against the old full-reset code. Fallback options (QML `modelAboutToBeReset` → `currentIndex = -1`, deferred reset) were not needed.

## 2026-08-19 — Taskipy gate tasks: non-quiet by default, dedicated `*-quiet` variants

- **Context:** The first iteration made the day-to-day Taskipy tasks (`checks`/`checks-fix`/`checks-win`/`checks-win-fix`) default to `--quiet`. The user preferred humans keep the verbose default and agents opt into quiet explicitly.
- **Decision:** Reverted `checks`/`checks-fix`/`checks-win`/`checks-win-fix` to plain (verbose) commands. Added explicit `*-quiet` variants for every gate mode on both platforms: `checks-quiet`, `checks-fix-quiet`, `checks-full-quiet`, `checks-full-cpu-quiet`, `checks-win-quiet`, `checks-win-fix-quiet`, `checks-win-full-quiet`, `checks-win-full-cpu-quiet`. `AGENTS.md` instructs AI agents to always use the quiet variants (direct `--quiet`/`-Quiet` flags or `*-quiet` tasks); the release line points agents at `checks-full-quiet` / `checks-full-cpu-quiet`.
- **Rationale:** Keeps the human-facing day-to-day commands unchanged (no silent behavior change) while giving agents an explicit, discoverable low-token path. Verified with `uv run task checks` (verbose, PASSED) and `uv run task checks-quiet` (quiet, PASSED).

## 2026-08-19 — Agent-verbosity `--quiet` flag for the quality gate

- **Context:** AI agents running `checks.sh` consume tens of thousands of tokens just reading the gate's stdout: pytest's `-v` addopts print one line per test (~880+ tests), and the serial heavy pass (semantic/transcribe/gui/tui/integration/ocr) reruns everything every time, streaming model/progress noise. The gate must keep streaming live output (the stall watchdog depends on it), so truncation (`tail`) was ruled out.
- **Decision:** Add opt-in `--quiet` (`checks.sh`) / `-Quiet` (`checks-win.ps1`) that exports `LIB_GATE_QUIET=true`. Pytest runs with `-q --no-header -ra --tb=short -p agent_progress` (sparse `[gate] N/total (ok=.. fail=..)` lines from the new `scripts/quality/internal/agent_progress.py` plugin; totals use nodeid sets because xdist workers each report the full collection). The heavy pass additionally gets `LIB_PYTEST_PROGRESS_INTERVAL=1` and `HF_HUB_DISABLE_PROGRESS_BARS=1`/`TRANSFORMERS_VERBOSITY=error`/`TOKENIZERS_PARALLELISM=false`/`TQDM_DISABLE=1`. On the parallel-verify path, passing light-step logs are no longer replayed (`gate_finish_step` loads the status first and cats the log only on failure or non-quiet). Taskipy task naming was later revised — see the "Taskipy gate tasks: non-quiet by default, dedicated `*-quiet` variants" entry above. `-p no:cacheprovider` was dropped because disabling the cacheprovider also removes pytest's `--ff` (fail-first) option, which the local gate passes.
- **Rationale:** Keeps the human-facing verbose default while slashing agent token cost; failures still show full short tracebacks + `-ra` summary; progress lines keep the stall watchdog satisfied during slow heavy tests. Verified with `uv run task checks` and `uv run task checks-fix` (both PASSED, 122 heavy tests).

## 2026-08-19 — AccentButton is native-first (highlighted via `defaultButton`), no custom background

- **Context:** `AccentButton` replaced the native button `background`/`contentItem` with a plain `Rectangle`+`Text`, losing Material ripple/elevation, Fluent hover/press states, per-style corner radius, and per-style size (hardcoded 80x32, faked pressed state via `opacity: 0.85`). The prior "explicit `accent` bool + custom fill" workaround existed because `DialogButtonBox` appeared to clobber `highlighted`.
- **Decision:** `AccentButton` is now a plain `Button` with `highlighted: control.accent` and no custom `background`/`contentItem`, so every style renders its native chrome and its own accent. Reading the Qt 6.11 source confirmed `QQuickDialogButtonBoxPrivate::updateLayout()` calls `setHighlighted(button == defaultButton)` on every child each layout pass — so a QML `highlighted` binding is unreliable inside a box, and `buttonRole: AcceptRole` alone does NOT highlight. The fix is `DialogButtonBox.defaultButton` on the primary dialog button (`optionsOkButton`, `filtersOkButton`, `updateYesButton`), which is what actually keeps it highlighted. FluentWinUI3 paints its highlighted fill from `palette.accent` (not `palette.button`/a custom background), so `qt_theme._apply_button_accent_palette` pins `QPalette.Accent` to the resolved button accent.
- **Rationale:** `highlighted` is the native accent on every style in play (Material `Material.accent`, Universal `Universal.accent`, Fluent `palette.accent`, Fusion `palette.highlight`, macOS/Windows native default button), so a custom background is unnecessary and harmful. `foreground` is retained only for the Search button's custom icon+text `contentItem`. Supersedes the 2026-08-18 "`accent` bool, not `highlighted`" entry below.

## 2026-08-19 — Set Qt app identity before QGuiApplication construction (host portal registration)

- **Context:** On Linux the GUI logged `qt.qpa.services: Failed to register with host portal QDBusError("org.freedesktop.portal.Error.Failed", "Could not register app ID: Connection already associated with an application ID")` at startup. Qt 6.10+/6.11 `QDesktopUnixServices` registers the app with the xdg-desktop-portal host-app registry (`org.freedesktop.host.portal.Registry.Register`) using `QGuiApplication::desktopFileName()`; the portal requires `Register` to run before any other portal call, and only once. Because identity was set *after* `QGuiApplication` was constructed, `desktopFileName()` was empty at init so Qt deferred registration to a queued callback; by then `follow_system_color_scheme()` (inside `apply_qt_quick_theme`) had already made a portal colour-scheme read, so the connection was already associated and `Register` failed.
- **Decision:** Add `apply_app_identity(name)` to `app_icon.py` that sets `QGuiApplication.setApplicationName(name)`, `QGuiApplication.setOrganizationName("srxy")`, and `apply_desktop_file_name(name)` via the **static** setters, and call it in `gui/app.py` (`run_gui`) and `installer/app.py` (`run_installer`) **before** `QGuiApplication` is constructed. `apply_desktop_file_name` becomes static-only (`name` arg, no app instance).
- **Rationale:** Qt reads these at init time and registers with the portal immediately, before any other portal method call, so the `Connection already associated` warning disappears. The `.desktop`-file guard (`desktop_file_available`) is preserved so `uv run`/PyPI runs without a desktop entry still skip registration gracefully.

## 2026-08-19 — Native file/folder dialogs on Linux via xdgdesktopportal platform theme

- **Context:** The GUI/installer "Browse" button uses Qt Quick's `FolderDialog`. On macOS and Windows that dialog is native, but on Linux Qt only renders a native dialog when the platform theme provides one — the KDE/GNOME themes Qt auto-selects do not, so the "Browse" button showed the Qt Quick (non-native) fallback instead of KDE's native folder picker.
- **Decision:** Add `prefer_native_file_dialogs()` in `qt_theme.py` that sets `QT_QPA_PLATFORMTHEME=xdgdesktopportal` (via `os.environ.setdefault`, Linux only), and call it in `gui/app.py` / `installer/app.py` **before** `QGuiApplication` is constructed. The `xdgdesktopportal` platform theme is bundled with PySide6 and serves file dialogs through `org.freedesktop.portal.FileChooser`, which opens the desktop's native picker.
- **Rationale:** Standard freedesktop route, no new dependencies, no bundled binaries; a user-set `QT_QPA_PLATFORMTHEME` is preserved. macOS/Windows are untouched (their dialogs are already native). Fails gracefully to the non-native dialog if the portal is unavailable.

## 2026-08-18 — AccentButton uses an `accent` bool, not `highlighted`

- **Context:** In dark mode the Search Options / Filters OK buttons (and update "Yes") rendered dark instead of accent-filled. `AccentButton` chose accent vs. secondary fill by reading the standard `highlighted` property, but `DialogButtonBox` (FluentWinUI3, and Material/Fusion/Universal alike) forcibly overrides `highlighted` on its child buttons from its own delegate, so the `highlighted: true` set inside `AccentButton` was silently dropped and `fillColor`/`foreground` fell back to `palette.button` (5.8%-alpha white in Fluent dark mode). `buttonRole: AcceptRole` and overriding `DialogButtonBox.delegate` did not restore it.
- **Decision:** Give `AccentButton` its own `property bool accent: true` and drive `fillColor`/`foreground` off that; the Search button's dynamic stale toggle now binds `accent` instead of `highlighted`.
- **Rationale:** `highlighted` is a container-managed property (`Container`/`DialogButtonBox` re-assign it), so it cannot be trusted to express "is the primary CTA". A dedicated `accent` flag is unambiguous and immune to `DialogButtonBox`. Added `optionsOkButton`/`filtersOkButton` objectNames plus a regression test asserting the OK buttons render `fillColor == accent` / `foreground == onAccent`.

## 2026-08-18 — Track the memory bank in git (reverses gitignore decision)

- **Context:** The earlier entry gitignored `memory/` to keep agent scratch out of the repo. But worktrees don't share ignored files: each new `git worktree add` got zero context and memory fragmented across worktrees.
- **Decision:** Track `memory/` in git as per-branch state. `decisions.md` stays append-only (never cleaned); `progress.md` and `activeContext.md` are reset at branch start. `memory/decisions.md` gets `merge=union` in `.gitattributes`.
- **Rationale:** Per-branch tracked memory follows the branch automatically in worktrees and new clones; the clean-at-start ritual keeps `progress.md`/`activeContext.md` relevant. Add `.cursor/rules/agent-memory.mdc` section 4 + human-oriented `memory/README.md`.

## 2026-08-18 — QML teardown order: destroy windows before the engine

- **Context:** GUI and installer exit logged `There are still "1" items in the process of being created at engine destruction.`. `QQmlEnginePrivate::~QQmlEnginePrivate` warns when `inProgressCreations > 0`; at interpreter shutdown the `QQmlApplicationEngine` was destroyed while its `QQuickWindow` (and its async `QQmlDelegateModel`/`Loader` incubators) were still alive.
- **Decision:** After `app.exec()` returns, destroy root windows first (`root.deleteLater()`), then `engine.deleteLater()`, then flush `QEvent.Type.DeferredDelete` with `sendPostedEvents` + `processEvents()` — in both `gui/app.py` and `installer/app.py`.
- **Rationale:** Deleting the window cascades into the delegate model/loader, whose incubator destructors `clear()` and decrement `inProgressCreations` before the engine destructor runs, so the warning is avoided. This is the standard Qt teardown order; deleting the engine first leaves stale PySide wrappers (verified `RuntimeError` in a repro) and the pending-incubator warning.

## 2026-08-18 — Preview syntax highlighting applies to all file sizes

- **Context:** File-content preview fell back to unhighlighted "plain" rendering once content exceeded `_PLAIN_PREVIEW_BYTES` (16 KB) or 500 lines. An 18 KB Python file (`caffe2/.../dataio_test.py`) lost keyword coloring while a 4 KB sibling (`coverage.py`) kept it, which looked like a bug.
- **Decision:** Remove the 16 KB / 500-line plain fallback entirely; always run the lightweight per-line tokenizer since preview payloads are already capped at `PREVIEW_MAX_BYTES` (64 KB) / `PREVIEW_MAX_LINES` (2000).
- **Rationale:** The tokenizer takes ~0.03 s for a max-size (50 KB / 2000-line) preview and emits ~280 KB of HTML, which QML RichText handles fine; the 16 KB cutoff was arbitrary and produced inconsistent highlighting.

## 2026-08-18 — AccentButton text: prefer white when it clears AA 4.5:1

- **Context:** Options dialog OK button (shared `AccentButton`) rendered black text on Windows, unlike Cancel. `contrast_text_on` picked the strictly higher-contrast colour, and for the Windows accent `#0078d4` black wins by a hair (4.637 vs 4.529), producing illegible-looking black-on-blue text.
- **Decision:** Prefer white text on dark/saturated fills whenever white still clears the WCAG AA 4.5:1 threshold, then fall back to the higher-contrast colour.
- **Rationale:** White-on-colour is the CTA convention; the pure max-contrast rule regressed mid-tone accents. Keeps light accents (`#3daee9`, `#90caf9`, `#ffeb3b`) black and dark accents (`#1565c0`) white. Added a regression test for `#0078d4` → white.

## 2026-08-18 — Preview highlighting/find/context menus (merged to `feature/fixes_1.6.6`)

- **Context:** File-content preview used hardcoded hex syntax colours (not theme-aware), had no in-preview find, and no copy/open/folder actions.
- **Decision:** Keep the in-house HTML highlighter but drive colours from a `PreviewPalette` with light/dark variants; add a Ctrl+F find bar that renders match spans as HTML overlays on top of the existing preview; add a right-click menu (copy/select-all/find/open file/open folder) plus "Open containing folder" on the results list; extend `DesktopPort` with `reveal_path` (os/gui/tui adapters); expose match line numbers via `LineNumberRole` to jump the preview on click.
- **Rationale:** No Pygments/tree-sitter dependency; reuses the existing line-oriented matching; theme-awareness follows the OS light/dark already handled in `qt_theme.py`.

## 2026-08-18 — Adopt a gitignored agent memory bank

- **Context:** Needed persistent cross-session context for an agent working across the v1.6.6 branch.
- **Decision:** Add `memory/` (gitignored) with `activeContext.md`, `progress.md`, `decisions.md`, plus an always-on rule at `.cursor/rules/agent-memory.mdc`.
- **Rationale:** Keeps agent scratch memory out of the repo while `docs/` stays the canonical committed reference.

## Windows GUI style → FluentWinUI3

- **Context:** Plain `Windows` Quick style looked dated and mixed poorly with dark mode.
- **Decision:** Use FluentWinUI3 on Windows, fallback Universal → Windows; follow OS light/dark. Results-pane `SplitView` falls back to Fusion until Fluent styles that control.
- **Rationale:** Native WinUI-like appearance with a safe fallback chain; documented hard-won pitfalls in `AGENTS.md`.

## Primary CTAs → shared `AccentButton`

- **Context:** Primary actions were `Button { highlighted: true }` with hand-picked label colours.
- **Decision:** Use shared `AccentButton` from the `SrxyControls` module, painting the system accent fill and WCAG black/white `foreground` from `srxyTheme`.
- **Rationale:** Consistent, accessible primary CTAs across GUI and installer.

## Qt theme selection lives in Python, not shared QML

- **Context:** Style imports in shared QML forced a single chrome and broke native macOS controls.
- **Decision:** Keep platform style choice in `src/srxy/adapters/inbound/gui/qt_theme.py` (`apply_qt_quick_theme`); never `import QtQuick.Controls.<Style>` in shared QML.
- **Rationale:** macOS needs native Aqua; Linux uses Material (Dense); Windows uses FluentWinUI3. Platform-specific attached properties belong only in platform-private QML, or avoided.

## Windows tessdata language packs → opt-in download

- **Context:** Windows OCR language data for the installer.
- **Decision:** Ship language packs as opt-in downloads from pinned upstream HTTPS sources; no bundled third-party runtime binaries.
- **Rationale:** Third-party binary policy (`AGENTS.md`) — keep tesseract/ffmpeg/CUDA etc. out of installer artifacts, the repo, and Releases.
