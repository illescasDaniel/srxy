# Development

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync --extra semantic
./scripts/quality/checks.sh --fix
./scripts/quality/checks.sh              # day-to-day (skips heaviest tests)
./scripts/quality/checks.sh --full       # before release
./scripts/quality/checks.sh --full+cpu   # release + forced-CPU transcribe matrix
```

`uv sync` creates `.venv`, installs the project editable, and pulls the default **`dev`** dependency group (pytest, ruff, taskipy, …). Add `--extra windows` on Windows for Explorer tags. Upload tooling: `uv sync --group uploader`.

On **Windows** with an NVIDIA GPU, install CUDA PyTorch in `.venv` before relying on GPU features ([installation.md → Windows](installation.md#windows)).

Run tasks without activating the venv:

```bash
uv run task checks
uv run task cli -- "registry" ./src
uv run pytest -m integration
uv run python scripts/bench_file_search.py
```

## Quality gate

Without `--fix`, verify steps (Ruff, ShellCheck/shfmt, basedpyright, pip-audit, build, pytest) run **in parallel**; pytest xdist workers are capped to half of `nproc` to leave CPU for the other steps. With `--fix`, steps stay **sequential** so autofix writers finish before later checks.

| Command | pytest |
|---------|--------|
| `checks.sh` | Integration + TUI/GUI; excludes `integration_full` and `transcribe_device_matrix`. Runs with `-n auto --dist=loadgroup` (half `nproc` when parallel verify), `--testmon-forceselect --ff`, no coverage |
| `checks.sh --full` | Full local suite; parallel verify; no testmon, with coverage |
| `checks.sh --full+cpu` | `--full` + `--integration-test-cpu` |
| `CI=true checks.sh` | `unit` marker only, excluding `semantic` and `transcribe`. Parallel verify + `-n` half `nproc`; no testmon, no coverage. `--fix`, `--full`, `--full+cpu` ignored |

`--fix` = Ruff + shell autofix, then remaining steps sequentially; ignored in CI.

## Fixtures

Dev-only under `tests/fixtures/` (not in wheel). See [`tests/fixtures/README.md`](../tests/fixtures/README.md).

| Path | Used by |
|------|---------|
| `corpus/` | In-memory semantic eval — `magic_search` / `search` |
| `file_search/` | `magic_file_search` integration; override `SRXY_FILE_SEARCH_FIXTURES` |

## pytest

Requires the `[semantic]` extra (`uv sync --extra semantic`); `SRXY_SEMANTIC=1` set in `tests/integration/conftest.py`.

Default local gate pytest uses **pytest-xdist** (`-n auto --dist=loadgroup`): unit/cli fan out across workers; TUI, GUI, and integration each share one worker via `xdist_group`. **pytest-testmon** (`--testmon-forceselect`) plus `--ff` select/reorder by recent changes on the day-to-day gate only — disabled for `--full` / `--full+cpu` and CI. Coverage runs only on `--full` / `--full+cpu`. The `.testmondata` DB is local and gitignored; the first run builds it.

```bash
uv run pytest -m unit -n auto
uv run pytest -m integration
uv run pytest -m integration_full
uv run pytest --integration-test-cpu
```

Gate mapping: default `checks.sh` ≈ `pytest -m "not integration_full and not transcribe_device_matrix" -n auto --dist=loadgroup --testmon-forceselect --ff`; `--full` ≈ `pytest tests/ -n auto --dist=loadgroup --cov=src`.

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
