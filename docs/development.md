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

Without `--fix`, light verify steps (Ruff, ShellCheck/shfmt, basedpyright, pip-audit, build) run **in parallel** on Unix, then pytest runs **alone** (safe parallel pass, then serial heavy). On Windows (`checks-win.ps1`), light steps run **sequentially**, then the same pytest split. With `--fix` / `-Fix`, steps stay **sequential** so autofix writers finish before later checks. Only one gate runs at a time (`.srxy-quality-gate.lock` in the repo root).

| Command | pytest |
|---------|--------|
| `checks.sh` / `checks-win.ps1` | Safe parallel: `unit and not semantic and not transcribe and not gui and not tui and not integration` (`-n` = `min(4, nproc)`, `--testmon-forceselect --ff`). Then serial heavy: `(semantic or transcribe or gui or tui or integration) and not integration_full and not transcribe_device_matrix` (`-n 0`, `QT_QPA_PLATFORM=offscreen`). No coverage |
| `checks.sh --full` / `checks-win.ps1 -Full` | Same two-pass split; heavy marker also includes `integration_full` / `transcribe_device_matrix`; no testmon; coverage on both passes (`--cov-append` on serial) |
| `checks.sh --full+cpu` / `checks-win.ps1 -FullCpu` | `--full` + `--integration-test-cpu` on the serial heavy pass |
| `CI=true checks.sh` / `CI=true checks-win.ps1` | Single parallel pass: `(unit or gui) and not integration and not semantic and not transcribe`. Linux CI sets `QT_QPA_PLATFORM=offscreen`. Light steps parallel then pytest; no testmon, no coverage, no serial follow-up. On GitHub Actions, `--fix`/`--full`/`--full+cpu` (and Windows `-Fix`/`-Full`/`-FullCpu`) are ignored. Locally, `checks-win.ps1 -Full` clears a leftover `CI=true` so the heavy suite still runs |

`--fix` = Ruff + shell autofix, then remaining steps sequentially; ignored in CI.

## Fixtures

Dev-only under `tests/fixtures/` (not in wheel). See [`tests/fixtures/README.md`](../tests/fixtures/README.md).

| Path | Used by |
|------|---------|
| `corpus/` | In-memory semantic eval — `magic_search` / `search` |
| `file_search/` | `magic_file_search` integration; override `SRXY_FILE_SEARCH_FIXTURES` |

## pytest

Requires the `[semantic]` extra (`uv sync --extra semantic`); `SRXY_SEMANTIC=1` set in `tests/integration/conftest.py`.

Default local gate pytest uses two passes so torch/whisper/Qt do not share xdist workers:

1. **Safe parallel** — `unit and not semantic and not transcribe and not gui and not tui and not integration` with `-n` = `min(4, nproc)` (override via `LIB_PYTEST_WORKERS`) and `--dist=loadgroup`.
2. **Serial heavy** — `semantic` / `transcribe` / `gui` / `tui` / `integration` (plus `integration_full` / `transcribe_device_matrix` on `--full`) with `-n 0` and `QT_QPA_PLATFORM=offscreen`.

**pytest-testmon** (`--testmon-forceselect`) plus `--ff` select/reorder by recent changes on the day-to-day **safe** pass only — disabled for `--full` / `--full+cpu` and CI. Coverage runs only on `--full` / `--full+cpu` (serial pass appends). The `.testmondata` DB is local and gitignored; the first run builds it.

**Anti-hang:** pytest output is always streamed live (never buffered until EOF). `pytest-timeout` defaults to 60s per test (`timeout_method=thread`). Integration tests under `tests/integration/` get a 300s timeout, and semantic model warmup runs in `pytest_sessionstart` so cold scipy/sentence-transformers imports are not charged to the first test. [`scripts/quality/pytest.sh`](../scripts/quality/pytest.sh) wraps runs with a wall-clock and no-output stall watchdog (override via `LIB_PYTEST_WALL_SECONDS` / `LIB_PYTEST_STALL_SECONDS`); stalls exit 124 with a process tree dump.

```bash
uv run pytest -m unit -n auto
uv run pytest -m integration
uv run pytest -m integration_full
uv run pytest --integration-test-cpu
```

Gate mapping: default `checks.sh` ≈ parallel safe unit subset then serial `QT_QPA_PLATFORM=offscreen pytest -m "(semantic or transcribe or gui or tui or integration) and not integration_full and not transcribe_device_matrix" -n 0`; `--full` ≈ same split with full heavy markers + coverage.

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
