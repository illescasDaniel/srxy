# Decisions

_Log of significant technical, structural, or dependency choices. Newest first._

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
