# Agent instructions

## Quality gate

After writing or changing code, run the quality gate until it passes cleanly.

**Unix / macOS / WSL (preferred where bash works):**

1. **Autofix** — run `./scripts/quality/checks.sh --fix` and address any remaining issues it reports.
2. **Verify** — run `./scripts/quality/checks.sh` (no `--fix`) and confirm a clean pass.
3. **Repeat** — if either step fails, fix the reported problems (rerun `--fix` for Ruff/shell issues; fix basedpyright, pip-audit, and pytest failures in code) and go back to step 1 until both commands succeed.

**Windows (native PowerShell — use when bash/`flock`/CRLF breaks `checks.sh`):**

1. **Autofix** — `powershell -ExecutionPolicy Bypass -File ./scripts/quality/checks-win.ps1 -Fix` (or `uv run task checks-win-fix`)
2. **Verify** — `powershell -ExecutionPolicy Bypass -File ./scripts/quality/checks-win.ps1` (or `uv run task checks-win`)

`checks-win.ps1` mirrors the bash gate (same steps, markers, lock file). Light verify steps run **sequentially** on Windows (bash still parallelizes them). ShellCheck/shfmt are skipped with a warning when those tools are not on PATH. Pytest stall/wall watchdogs from `pytest.sh` are not ported; `pytest-timeout` still applies.

Use the project env with `uv sync --extra semantic` (default `dev` dependency group); on Windows also `--extra windows`.

The gate runs, in order: Ruff (lint + format) → ShellCheck/shfmt → basedpyright → pip-audit → build → pytest.

Locally, pytest runs in two passes: a **safe parallel** pass (`unit and not semantic and not transcribe and not gui and not tui and not integration and not ocr`, workers capped at `min(4, nproc)` unless `LIB_PYTEST_WORKERS` is set) then a **serial heavy** pass (`-n 0`, `QT_QPA_PLATFORM=offscreen`) for `semantic` / `transcribe` / `gui` / `tui` / `integration` / `ocr` (plus `integration_full` / `transcribe_device_matrix` on `--full`). Day-to-day local runs also use `--testmon-forceselect --ff` on the safe pass only (change-aware; `.testmondata` is gitignored). Coverage is enabled only for `--full` / `--full+cpu` (serial pass uses `--cov-append`). File-search fixtures live at `tests/fixtures/file_search/`; semantic corpus JSON at `tests/fixtures/corpus/`. Override the search tree with `SRXY_FILE_SEARCH_FIXTURES` if needed. CI runs a single parallel pass: `(unit or gui) and not integration and not semantic and not transcribe` (`CI=true`); no testmon, no coverage, no serial follow-up. OCR orientation tests stay in the CI parallel pass (they carry a 300s timeout).

Local verify (no `--fix`) runs light steps (Ruff, shell, basedpyright, pip-audit, build) **in parallel**, then **pytest alone** (safe parallel + serial heavy). CI skips the serial follow-up (`CI=true`).

The gate takes an exclusive flock on `.srxy-quality-gate.lock` (repo root). A second overlapping `checks.sh` exits immediately with an error instead of spawning another pytest tree.

`--fix` autofixes Ruff and shell scripts only; basedpyright and test failures must be fixed manually. `--fix`, `--full`, and `--full+cpu` are ignored when `GITHUB_ACTIONS=true`. On Windows, `checks-win.ps1 -Full` still runs the heavy suite even if a leftover local `CI=true` is set.

Before a release, run `./scripts/quality/checks.sh --full` (and `--full+cpu` when validating CUDA/CPU transcribe parity). Full details: [docs/development.md](docs/development.md).

### Running the gate (agent pitfalls)

- Pytest streams live under the gate (including `CI=true`). After `[6/6] pytest` you should see a `pytest: starting (workers=…)` banner and then `[gwN] PASSED` lines. A long blank gap means a real stall — the stall/wall watchdog will kill the run (exit 124) instead of hanging forever.
- Override limits with `LIB_PYTEST_WALL_SECONDS` / `LIB_PYTEST_STALL_SECONDS` if needed.
- **Do not** pipe the gate through `tail` (or anything that only prints on EOF). Prefer running `./scripts/quality/checks.sh` / `--fix` directly, or `tee` a log **without** truncating live output. With `| tee … | tail -N`, a healthy but long verify looks hung because nothing appears until the process exits.
- If the gate refuses to start because of the lock file, another gate is still running — stop leftover `checks.sh` / `checks-win.ps1` / pytest processes for this repo, then retry. Do not start a second gate in parallel.
- If verify seems stuck despite the lock: inspect the process tree and the full log. A clean re-run usually finishes in tens of seconds under `CI=true`.
- Optional when GPU contention is noisy: `CUDA_VISIBLE_DEVICES="" ./scripts/quality/checks.sh` (or the same for `CI=true` local mimic runs). On Windows PowerShell: `$env:CUDA_VISIBLE_DEVICES = ''; $env:CI = 'true'; .\scripts\quality\checks-win.ps1`.

## TUI changes

When adding or changing TUI widgets, layout, or visible labels, add snapshot tests under [`tests/tui/`](tests/tui/) using `assert_svg_snapshot` from [`tests/tui/helpers.py`](tests/tui/helpers.py). Snapshots live in [`tests/tui/snapshots/`](tests/tui/snapshots/) as `*.snap.txt` files (visible SVG text).

Regenerate after intentional UI changes:

```bash
UPDATE_TUI_SNAPSHOTS=1 uv run pytest tests/tui/test_query_builder_display.py
```

## GUI changes

When adding or changing GUI QML layout or visible labels, add or update text-tree snapshot tests under [`tests/gui/`](tests/gui/). Refresh with `UPDATE_GUI_SNAPSHOTS=1 QT_QPA_PLATFORM=offscreen uv run pytest tests/gui/test_gui_snapshots.py`.

Run the full local gate (`./scripts/quality/checks.sh`) so integration, TUI, and GUI tests execute; CI (`CI=true`) runs `unit` tests excluding `semantic` and `transcribe`.

### Qt Quick Controls theming (platform pitfalls)

Theme/style selection lives in [`src/srxy/adapters/inbound/gui/qt_theme.py`](src/srxy/adapters/inbound/gui/qt_theme.py) (`apply_qt_quick_theme`), shared by the main GUI and installer. Keep platform style choice in Python, not in shared QML.

Current intent:

- **Windows:** `Universal` (WinUI-like), fallback `Windows`. Follow OS light/dark.
- **macOS:** `macOS` (native Aqua). Follow OS light/dark.
- **Linux / other:** `Material` (Dense variant for desktop), fallback `Fusion`. Follow OS light/dark. Also set `QT_QUICK_CONTROLS_MATERIAL_ACCENT` from the XDG Desktop Portal `accent-color` (session-bus CLI), else `QPalette` Highlight if it looks like a real tint, else Material `"Blue"`.

Hard-won lessons — do not regress these:

1. **Do not `import QtQuick.Controls.Universal` / `Material` (or set `Universal.theme` / `Material.theme`) in shared QML** (`gui/qml/Main.qml`, `installer/qml/Main.qml`). Those imports force that chrome even when Python selected `macOS`, breaking native macOS controls. Style-specific attached properties belong only in platform-private QML, or better: avoid them.
2. **Windows Universal and Linux Material default to Light** even when the OS is dark. `QStyleHints.setColorScheme(...)` alone is not enough. Set `QT_QUICK_CONTROLS_UNIVERSAL_THEME=System` (Windows) or `QT_QUICK_CONTROLS_MATERIAL_THEME=System` (Linux) in Python **before** `QQuickStyle.setStyle(...)` / before the QML engine loads. That is the supported equivalent of `*.theme: *.System` without a QML style import. On Linux also set `QT_QUICK_CONTROLS_MATERIAL_VARIANT=Dense` — Normal is touch-sized and overflows fixed window heights. Set `QT_QUICK_CONTROLS_MATERIAL_ACCENT` the same way (portal / palette / `"Blue"`) so Material does not keep Qt’s default pink accent.
3. **`hints.colorScheme` is a method in PySide6** — call `hints.colorScheme()`, do not pass the unbound method into `setColorScheme` (that TypeError crashes GUI launch).
4. **Plain `Windows` Quick style looks dated** and its dark-mode mix with a dark window palette is often illegible. Prefer `Universal` + system theme on Windows; do not “fix light” as the long-term fix unless Universal is unavailable.
5. **macOS packaging prunes Universal/Material frameworks** (`packaging/macos/prune-pyside.sh`). Relying on those QML imports in shipped macOS builds is fragile even beyond the style-forcing issue. Linux AppImage pruning keeps Material (needed at runtime).
6. **Installer/GUI footers:** Material page chrome (and tall StackLayout implicit heights) can push in-content nav rows below the window. Keep wizard actions in `ApplicationWindow.footer` (see installer `Main.qml`) and give fill-height StackLayouts `Layout.preferredHeight: 0` so they only take leftover space.
7. When changing themes, **restart the app fully** (no hot-reload assumptions) and visually check Windows dark mode, Linux Material light/dark, and macOS native controls before considering the change done.

## Typing

Do not annotate functions that return `None` with `-> None`. Omit the return type instead.

## Task command verification

When you add or modify any Taskipy task or the script it runs, execute that exact task command before reporting completion.

- If the task is interactive/long-running, run a deterministic smoke variant (`--help`, `--version`, or equivalent non-interactive flag) plus one realistic invocation path that reaches the changed code.
- Include the exact command(s) and outcome in your final update.

## Third-party binary policy

Do not bundle third-party runtime binaries (for example tesseract, ffmpeg, CUDA, or similar) inside installer app artifacts, the git repository, or project GitHub Releases.

- Keep third-party components as opt-in downloads from pinned upstream HTTPS sources at install/runtime.
- Do not host rebuilt/repackaged third-party runtime binaries under srxy release tags.
- If a change would embed third-party runtime binaries into an installer artifact, the repo, or our releases, stop and use a download-based approach instead.
