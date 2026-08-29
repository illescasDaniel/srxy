# Development

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync --extra semantic
./scripts/quality/checks.sh --fix
./scripts/quality/checks.sh              # day-to-day (skips heaviest tests)
./scripts/quality/checks.sh --full       # before release
./scripts/quality/checks.sh --full+cpu   # release + forced-CPU transcribe matrix
```

On **Windows**, use the PowerShell gate instead of `checks.sh` (bash/`flock` often fail under Git Bash or WSL mounts):

```powershell
uv sync --extra semantic --extra windows
powershell -ExecutionPolicy Bypass -File .\scripts\quality\checks-win.ps1 -Fix
powershell -ExecutionPolicy Bypass -File .\scripts\quality\checks-win.ps1
# or: uv run task checks-win-fix / uv run task checks-win
```

`uv sync` creates `.venv`, installs the project editable, and pulls the default **`dev`** dependency group (pytest, ruff, taskipy, …). Add `--extra windows` on Windows for Explorer tags. Upload tooling: `uv sync --group uploader`.

On **Windows** with an NVIDIA GPU, install CUDA PyTorch in `.venv` before relying on GPU features ([installation.md → Windows](installation.md#windows)).

When bumping AppImage installer compatibility, edit [`packaging/installer_meta.toml`](../packaging/installer_meta.toml) (`installer_version`, `min_srxy_version`) and rebuild the AppImage. Keep a copy in sync under `src/srxy/adapters/inbound/installer/installer_meta.toml` for packaged installs. End-user guide: [installers.md](installers.md). Packaging details: [`packaging/linux-appimage/README.md`](../packaging/linux-appimage/README.md).

Run tasks without activating the venv:

```bash
uv run task checks
uv run task cli -- "registry" ./src
uv run task gui-bare            # GUI from gitignored .venv-bare (core-only; no AI extras)
uv run task gui-bare -- --recreate
uv run pytest -m integration
uv run python scripts/bench_file_search.py
```

## Quality gate

Without `--fix`, light verify steps (Ruff, ShellCheck/shfmt, basedpyright, pip-audit, build) run **in parallel** and **overlap** pytest buckets on both Unix and Windows. With `--fix` / `-Fix`, steps stay **sequential** so autofix writers finish before later checks. Only one gate runs at a time (`.srxy-quality-gate.lock` in the repo root).

Pytest is split into path-based **buckets** (not a single marker expression):

| Bucket | Paths | Runtime |
|--------|-------|---------|
| `core` | `tests/unit`, `tests/cli` | xdist (`-n` up to 8), `-p no:pytest-qt` |
| `gui` | `tests/gui` | `-n 0`, offscreen Qt, pytest-qt enabled |
| `tui` | `tests/tui` | `-n 0`, `-p no:pytest-qt` |
| `heavy` | `tests/integration` | `-n 0`, models/GPU, `-p no:pytest-qt` |

Default scope is **auto** (from `git diff` / `git status`): `core` always; GUI/TUI/heavy only when matching paths changed. Ambiguous paths or no git → all buckets. Override with `--scope=…` / `--gui` / `--tui` / `--cli` / `--all` (Windows: `-Scope`, `-Gui`, `-Tui`, `-Cli`, `-All`).

| Command | Behaviour |
|---------|-----------|
| `checks.sh` / `checks-win.ps1` | Auto-scope buckets; per-bucket testmon + `--ff`; no coverage; `.gate-cache` may skip pip-audit/build |
| `checks.sh --full` / `checks-win.ps1 -Full` | All buckets; heavy includes `integration_full` / `transcribe_device_matrix`; no testmon; coverage; no step cache |
| `checks.sh --full+cpu` / `checks-win.ps1 -FullCpu` | `--full` + `--integration-test-cpu` on heavy |
| `CI=true checks.sh` / `CI=true checks-win.ps1` | `core+gui+tui` (no heavy); no testmon; no coverage; no step cache. On GitHub Actions, `--fix`/`--full` are ignored. Locally, `checks-win.ps1 -Full` clears a leftover `CI=true` so heavy still runs |

`--fix` = Ruff + shell autofix, then remaining steps sequentially; ignored in CI. `--timings` / `-Timings` appends `--durations=25` and prints per-step seconds. `--no-cache` / `-NoCache` forces pip-audit and the wheel build.

### Windows notes

- Prefer `pwsh` when available; Taskipy still falls back to `powershell`.
- Light steps use `Start-Process` (not `Start-Job`) for parallelism.
- **Windows Defender:** excluding the repo, `.venv`, the uv cache (`%LOCALAPPDATA%\uv`), and `%TEMP%` often cuts import-heavy Python wall time by 30–50%. Add exclusions via Windows Security → Virus & threat protection → Exclusions.

## Fixtures

Dev-only under `tests/fixtures/` (not in wheel). See [`tests/fixtures/README.md`](../tests/fixtures/README.md).

| Path | Used by |
|------|---------|
| `corpus/` | In-memory semantic eval — `magic_search` / `search` |
| `file_search/` | `magic_file_search` integration; override `SRXY_FILE_SEARCH_FIXTURES` |

## pytest

Requires the `[semantic]` extra (`uv sync --extra semantic`); `SRXY_SEMANTIC=1` set in `tests/integration/conftest.py`.

Default local gate pytest uses concurrent **buckets** so torch/whisper/Qt do not share xdist workers with unit tests:

1. **core** — `tests/unit` + `tests/cli` with `-n` up to 8 (override via `LIB_PYTEST_WORKERS`) and `--dist=loadgroup`; pytest-qt disabled.
2. **gui** / **tui** / **heavy** — path-scoped, `-n 0`, started longest-job-first and overlapped with light steps. Serialize with `LIB_GATE_BUCKET_CONCURRENCY=1`.

**pytest-testmon** (`--testmon-forceselect`) plus `--ff` select/reorder by recent changes per bucket (`.testmondata-core` etc. via `TESTMON_DATAFILE`) on day-to-day only — disabled for `--full` / `--full+cpu` and CI. Coverage runs only on `--full` / `--full+cpu`. The testmon DBs are local and gitignored; the first run builds them.

**Anti-hang:** pytest output is always streamed live (never buffered until EOF). `pytest-timeout` defaults to 60s per test (`timeout_method=thread`). Integration and OCR tests get a 300s timeout, and semantic model warmup runs in `pytest_sessionstart` so cold scipy/sentence-transformers imports are not charged to the first test. [`scripts/quality/pytest.sh`](../scripts/quality/pytest.sh) and `checks-win.ps1` wrap runs with a wall-clock watchdog (override via `LIB_PYTEST_WALL_SECONDS`); bash also has a no-output stall watchdog (`LIB_PYTEST_STALL_SECONDS`). Stalls/timeouts exit 124.

```bash
uv run pytest tests/unit tests/cli -n auto -p no:pytest-qt
uv run pytest tests/integration
uv run pytest tests/integration -m integration_full
uv run pytest --integration-test-cpu
```

Platform tag tests: `pytest -m linux_xattr`, `macos_finder`, `windows_tags` (`srxy[windows]`).

### TUI snapshots

New or changed TUI elements need snapshot coverage in `tests/tui/` (`assert_svg_snapshot`). Refresh: `UPDATE_TUI_SNAPSHOTS=1 uv run pytest tests/tui/…`. See [AGENTS.md](../AGENTS.md).

### GUI snapshots

GUI chrome text-tree snapshots live in `tests/gui/snapshots/`. Refresh: `UPDATE_GUI_SNAPSHOTS=1 QT_QPA_PLATFORM=offscreen uv run pytest tests/gui/test_gui_snapshots.py`. See [docs/gui.md](gui.md) and [docs/architecture.md](architecture.md).

### Public API reference

[`docs/api-reference.md`](api-reference.md) is generated from `srxy.__all__`. After changing public exports or their signatures/docstrings:

```bash
uv run python scripts/docs/export_public_api.py
```

## Performance benchmarks

`scripts/bench_file_search.py` measures `magic_file_search` across several scenarios (text, documents, OCR, synthetic large/small sets):

```bash
uv run python scripts/bench_file_search.py                 # warm cache
uv run python scripts/bench_file_search.py --cold          # cold cache (re-runs OCR/parsing)
uv run python scripts/bench_file_search.py --iters 5       # more iterations for stable σ
```

Results and design rationale for the parallel execution strategy (thread pool vs process pool) are documented in [docs/multi-process-benchmark.md](multi-process-benchmark.md).
