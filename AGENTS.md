# Agent instructions

## Quality gate

After writing or changing code, run the quality gate until it passes cleanly.

**Unix / macOS / WSL (preferred where bash works):**

1. **Autofix** — run `./scripts/quality/checks.sh --quiet --fix` and address any remaining issues it reports.
2. **Verify** — run `./scripts/quality/checks.sh --quiet` (no `--fix`) and confirm a clean pass.
3. **Repeat** — if either step fails, fix the reported problems (rerun `--fix` for Ruff/shell issues; fix ty, pip-audit, and pytest failures in code) and go back to step 1 until both commands succeed.

**Windows (native PowerShell — use when bash/`flock`/CRLF breaks `checks.sh`):**

1. **Autofix** — `powershell -ExecutionPolicy Bypass -File ./scripts/quality/checks-win.ps1 -Fix -Quiet` (or `uv run task checks-win-fix-quiet`)
2. **Verify** — `powershell -ExecutionPolicy Bypass -File ./scripts/quality/checks-win.ps1 -Quiet` (or `uv run task checks-win-quiet`)

`checks-win.ps1` mirrors the bash gate (same steps, buckets, lock file). Light verify steps and pytest buckets run **concurrently** on both platforms. ShellCheck/shfmt are skipped with a warning when those tools are not on PATH. Both gates apply a wall-clock watchdog to pytest (exit 124 on timeout); bash also has a stall (no-output) watchdog.

Use the project env with **`uv run task sync-dev`**. That task is platform-aware ([docs/development.md](docs/development.md#sync)):

| OS | What `sync-dev` does |
|----|----------------------|
| Linux + NVIDIA | `uv sync --extra semantic`. `SRXY_SKIP_CUDA_TORCH=1` or empty `CUDA_VISIBLE_DEVICES` → no semantic extra |
| Linux (no GPU) | `uv sync` (dev group only; no semantic) |
| macOS Apple Silicon | `uv sync --extra semantic` (MPS) |
| macOS Intel | `uv sync` (no semantic) |
| Windows + NVIDIA | `uv sync --extra semantic`, then `ensure-windows-cuda-torch.ps1` |
| Windows (no GPU) | `uv sync` (no semantic) |

Variants: `uv run task sync` (runtime extras, **no** pytest/ruff), `uv run task sync-uploader` (dev + twine). `sync-win` is an alias of `sync-dev`. `[semantic]` is GPU-only (NVIDIA / Apple Silicon MPS). CI uses `uv sync --frozen` without semantic extras (no heavy suite). `pywin32` is a core Windows dependency (no `[windows]` extra).

**Windows + NVIDIA GPU (required for fast heavy/semantic tests):** `sync-dev` pulls CUDA PyTorch (`+cu130`) from the lockfile via `[tool.uv.sources]`. Before a heavy gate, confirm:

```powershell
.\.venv\Scripts\python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

Expect `+cu130` (or `+cu126`) and `True`. `+cpu` / `False` with an RTX GPU present means the venv is wrong — re-run `uv run task sync-dev` (see [docs/development.md](docs/development.md) and [docs/installation.md](docs/installation.md#windows)). `checks-win.ps1` auto-runs the ensure script when the `heavy` bucket is selected (skipped in GitHub Actions / when `SRXY_SKIP_CUDA_TORCH=1`).

The gate runs, in order: Ruff (lint + format) → ShellCheck/shfmt → ty → pip-audit → build → pytest buckets. Without `--fix`, light steps and pytest **overlap**.

### Pytest buckets and auto-scope

Day-to-day default is **auto-scope** from `git diff` / `git status`:

| Bucket | Paths | How it runs |
|--------|-------|-------------|
| `core` | `tests/unit`, `tests/cli` | xdist (`-n` up to 8), `-p no:pytest-qt` |
| `gui` | `tests/gui` | `-n 0`, `QT_QPA_PLATFORM=offscreen`, pytest-qt on |
| `tui` | `tests/tui` | `-n 0`, `-p no:pytest-qt` |
| `heavy` | `tests/integration` | `-n 0`, models/GPU, `-p no:pytest-qt` |

- `core` always runs. Touching `inbound/gui/` / `shared/qml/` / `installer/` → `gui`; `inbound/tui/` → `tui`; semantic/transcribe/ocr/models/fixtures → `heavy`. Ambiguous paths (`pyproject.toml`, `tests/conftest.py`, `scripts/quality/`, …) or no git → all buckets.
- Override with `--scope=core,gui` / `--gui` / `--tui` / `--cli` / `--all` (Windows: `-Scope`, `-Gui`, `-Tui`, `-Cli`, `-All`). `--full` implies `--all` and adds `integration_full` / `transcribe_device_matrix` plus coverage.
- Per-bucket testmon (`.testmondata-core` etc.) + `--ff` on day-to-day only (not CI / not `--full`).
- `pip-audit` / wheel build skip via `.gate-cache/` when inputs are unchanged (force with `--no-cache`).
- Prefer scoped tasks when you know the surface: `checks-gui-quiet`, `checks-tui-quiet`, `checks-core-quiet`, `checks-win-gui-quiet`, …
- Use `--all` / `checks-all-quiet` before a commit that touches shared code, and `--full` / `checks-full-quiet` before release.

CI (`CI=true`) selects `core+gui+tui` (no heavy). File-search fixtures live at `tests/fixtures/file_search/`; semantic corpus JSON at `tests/fixtures/corpus/`. Override the search tree with `SRXY_FILE_SEARCH_FIXTURES` if needed.

The gate takes an exclusive flock on `.srxy-quality-gate.lock` (repo root). A second overlapping `checks.sh` exits immediately with an error instead of spawning another pytest tree.

`--fix` autofixes Ruff and shell scripts only; ty and test failures must be fixed manually. `--fix`, `--full`, and `--full+cpu` are ignored when `GITHUB_ACTIONS=true`. On Windows, `checks-win.ps1 -Full` still runs the heavy suite even if a leftover local `CI=true` is set.

`--quiet` (Unix) / `-Quiet` (Windows) is the agent-verbosity mode: passing light-step logs are suppressed and pytest collapses to sparse `[gate] N/total` progress lines, showing failures in full (`-ra --tb=short`). Omit the flag for the full human-facing output. **AI agents must always use the quiet variants** (`--quiet` / `-Quiet`, or the `*-quiet` Taskipy tasks). The non-quiet `checks` / `checks-fix` / `checks-win` / `checks-win-fix` tasks and plain `checks.sh` / `checks-win.ps1` are for humans.

Before a release, run `./scripts/quality/checks.sh --full` (and `--full+cpu` when validating CUDA/CPU transcribe parity); agents should run the quiet equivalents `checks-full-quiet` / `checks-full-cpu-quiet`. Full details: [docs/development.md](docs/development.md).

### Running the gate (agent pitfalls)

- Pytest streams live under the gate (including `CI=true`). After the pytest step you should see `pytest buckets: …` and then `[gate] N/total` progress lines (`--quiet`) or per-test lines. A long blank gap means a real stall — the wall/stall watchdog will kill the run (exit 124) instead of hanging forever.
- Override limits with `LIB_PYTEST_WALL_SECONDS` / `LIB_PYTEST_STALL_SECONDS` if needed. Serialize buckets with `LIB_GATE_BUCKET_CONCURRENCY=1` when debugging flakiness.
- **Do not** pipe the gate through `tail` (or anything that only prints on EOF). Prefer running `./scripts/quality/checks.sh` / `--quiet` directly, or `tee` a log **without** truncating live output. With `| tee … | tail -N`, a healthy but long verify looks hung because nothing appears until the process exits.
- If the gate refuses to start because of the lock file, another gate is still running — stop leftover `checks.sh` / `checks-win.ps1` / pytest processes for this repo, then retry. Do not start a second gate in parallel.
- If verify seems stuck despite the lock: inspect the process tree and the full log. A clean scoped re-run usually finishes in tens of seconds under `CI=true`.
- Optional when GPU contention is noisy: `CUDA_VISIBLE_DEVICES="" ./scripts/quality/checks.sh` (or the same for `CI=true` local mimic runs). On Windows PowerShell: `$env:CUDA_VISIBLE_DEVICES = ''; $env:CI = 'true'; .\scripts\quality\checks-win.ps1`.
- Run the gate **outside the sandbox** (`required_permissions: ["all"]`). The sandbox blocks writes to per-user dirs (`~/.cache/srxy/cache.db`, `~/.local/share/srxy`, `~/.config/srxy/settings.json`) and blocks Hugging Face network checks, so an in-sandbox run fails with `sqlite3.OperationalError: attempt to write a readonly database` and Hugging Face `403` — both environmental, not code bugs. If the light steps pass and pytest only shows those, re-run outside the sandbox. To stay sandboxed (narrow repro only), redirect the writable dirs into the workspace first: `export SRXY_CACHE_DIR="$PWD/.sandbox/cache" XDG_CACHE_HOME="$PWD/.sandbox/cache" XDG_DATA_HOME="$PWD/.sandbox/data" XDG_CONFIG_HOME="$PWD/.sandbox/config" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1`, then run `./scripts/quality/checks.sh`.

## TUI changes

When adding or changing TUI widgets, layout, or visible labels, add snapshot tests under [`tests/tui/`](tests/tui/) using `assert_svg_snapshot` from [`tests/tui/helpers.py`](tests/tui/helpers.py). Snapshots live in [`tests/tui/snapshots/`](tests/tui/snapshots/) as `*.snap.txt` files (visible SVG text).

Regenerate after intentional UI changes:

```bash
UPDATE_TUI_SNAPSHOTS=1 uv run pytest tests/tui/test_query_builder_display.py
```

## GUI changes

When adding or changing GUI QML layout or visible labels, add or update text-tree snapshot tests under [`tests/gui/`](tests/gui/). Refresh with `UPDATE_GUI_SNAPSHOTS=1 QT_QPA_PLATFORM=offscreen uv run pytest tests/gui/test_gui_snapshots.py`.

Run the full local gate (`./scripts/quality/checks.sh`) so integration, TUI, and GUI tests execute; CI (`CI=true`) runs `unit` tests excluding `semantic` and `transcribe`.

### Primary / accent CTAs

Primary actions (Search, dialog OK/Yes, installer Launch, and similar) must use shared [`AccentButton`](src/srxy/adapters/inbound/shared/qml/SrxyControls/AccentButton.qml) from the `SrxyControls` module — not `Button { highlighted: true }` with hand-picked label colours. `AccentButton` paints the system accent fill and feeds the WCAG black/white `foreground` from the `srxyTheme` context property (set in GUI/installer `app.py` after `apply_qt_quick_theme`) into `palette.buttonText` / `palette.brightText`, which is all the styles that honour those roles need.

Do **not** give an `AccentButton` a custom `contentItem`, and do not set `icon.color` on one. Material, FluentWinUI3, and Universal compute their own highlighted label colour and ignore `palette.buttonText`, so hand-tinting to `foreground` puts a black Search label and glyph next to a white dialog OK label. Use plain `text` + `icon.source` and let the style's `IconLabel` paint both: it tints icons from `defaultIconColor`, which every style except Fusion/Basic (covered by `palette.brightText`) sets to its own label colour. Note that `icon.color` must stay *unassigned* — even writing `"transparent"` resolves the role and strands the glyph untinted.

Ordinary secondary actions stay plain `Button` / `ToolButton`.

### Qt Quick Controls theming (platform pitfalls)

Theme/style selection lives in [`src/srxy/adapters/inbound/gui/qt_theme.py`](src/srxy/adapters/inbound/gui/qt_theme.py) (`apply_qt_quick_theme`), shared by the main GUI and installer. Keep platform style choice in Python, not in shared QML.

Current intent:

- **Windows:** `FluentWinUI3` (WinUI-like), fallback `Universal` then `Windows`. Follow OS light/dark. Theme experiment: Fluent’s unsupported controls (notably `SplitView` in the GUI results pane) fall back to Fusion until Qt styles them.
- **macOS:** `macOS` (native Aqua). Follow OS light/dark.
- **Linux / other:** `Material` (Dense variant for desktop), fallback `Fusion`. Follow OS light/dark. Also set `QT_QUICK_CONTROLS_MATERIAL_ACCENT` from the XDG Desktop Portal `accent-color` (session-bus CLI), else `QPalette` Highlight if it looks like a real tint, else Material `"Blue"`.

Hard-won lessons — do not regress these:

1. **Do not `import QtQuick.Controls.FluentWinUI3` / `Universal` / `Material` (or set `Universal.theme` / `Material.theme`) in shared QML** (`gui/qml/Main.qml`, `installer/qml/Main.qml`). Those imports force that chrome even when Python selected `macOS`, breaking native macOS controls. Style-specific attached properties belong only in platform-private QML, or better: avoid them.
2. **Windows Universal and Linux Material default to Light** even when the OS is dark. `QStyleHints.setColorScheme(...)` alone is not enough. Set `QT_QUICK_CONTROLS_UNIVERSAL_THEME=System` (Windows, for the Universal fallback) or `QT_QUICK_CONTROLS_MATERIAL_THEME=System` (Linux) in Python **before** `QQuickStyle.setStyle(...)` / before the QML engine loads. That is the supported equivalent of `*.theme: *.System` without a QML style import. FluentWinUI3 has no `*_THEME` env and follows the OS/palette via `follow_system_color_scheme`. On Linux also set `QT_QUICK_CONTROLS_MATERIAL_VARIANT=Dense` — Normal is touch-sized and overflows fixed window heights. Set `QT_QUICK_CONTROLS_MATERIAL_ACCENT` the same way (portal / palette / `"Blue"`) so Material does not keep Qt’s default pink accent. Qt 6.11 Material’s default surface is M3 tonal `#fffbfe` (pinkish white) / `#1c1b1f` (purple-grey dark) — set `QT_QUICK_CONTROLS_MATERIAL_BACKGROUND` to `#ffffff` (light) or `#303030` (dark) from the active colour scheme **after** `follow_system_color_scheme` (a fixed `#ffffff` locks dark mode to white; env is resolved once at startup).
3. **`hints.colorScheme` is a method in PySide6** — call `hints.colorScheme()`, do not pass the unbound method into `setColorScheme` (that TypeError crashes GUI launch).
4. **Plain `Windows` Quick style looks dated** and its dark-mode mix with a dark window palette is often illegible. Prefer `FluentWinUI3`, then `Universal` + system theme on Windows; do not “fix light” as the long-term fix unless both are unavailable. Keep the Fluent→Fusion `SplitView` mismatch in mind until Fluent supports that control.
5. **macOS packaging prunes Universal/Material frameworks** (`packaging/macos/prune-pyside.sh`). Relying on those QML imports in shipped macOS builds is fragile even beyond the style-forcing issue. Linux AppImage pruning keeps Material (needed at runtime).
6. **Installer/GUI footers:** Material page chrome (and tall StackLayout implicit heights) can push in-content nav rows below the window. Keep wizard actions in `ApplicationWindow.footer` (see installer `Main.qml`) and give fill-height StackLayouts `Layout.preferredHeight: 0` so they only take leftover space.
7. When changing themes, **restart the app fully** (no hot-reload assumptions) and visually check Windows dark mode (including results `SplitView` grips), Linux Material light/dark, and macOS native controls before considering the change done.

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
