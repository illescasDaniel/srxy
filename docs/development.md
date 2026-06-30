# Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,semantic]"
./scripts/quality/checks.sh --fix
./scripts/quality/checks.sh              # day-to-day (skips heaviest tests)
./scripts/quality/checks.sh --full       # before release
./scripts/quality/checks.sh --full+cpu   # release + forced-CPU transcribe matrix
```

## Quality gate

Order: Ruff → ShellCheck/shfmt → basedpyright → pip-audit → build → pytest.

| Command | pytest |
|---------|--------|
| `checks.sh` | Integration + TUI; excludes `integration_full` and `transcribe_device_matrix` |
| `checks.sh --full` | Full local suite |
| `checks.sh --full+cpu` | `--full` + `--integration-test-cpu` |
| `CI=true checks.sh` | `unit` marker only, excluding `semantic` and `transcribe` tests. `--fix`, `--full`, `--full+cpu` ignored |

`--fix` = Ruff + shell only; ignored in CI.

## Fixtures

Dev-only under `tests/fixtures/` (not in wheel). See [`tests/fixtures/README.md`](../tests/fixtures/README.md).

| Path | Used by |
|------|---------|
| `corpus/` | In-memory semantic eval — `magic_search` / `search` |
| `file_search/` | `magic_file_search` integration; override `SRXY_FILE_SEARCH_FIXTURES` |

## pytest

Requires `pip install -e ".[semantic]"`; `SRXY_SEMANTIC=1` set in `tests/integration/conftest.py`.

```bash
pytest -m integration
pytest -m integration_full
pytest --integration-test-cpu
```

Gate mapping: default `checks.sh` ≈ `pytest -m "not integration_full and not transcribe_device_matrix"`; `--full` ≈ `pytest tests/`.

Platform tag tests: `pytest -m linux_xattr`, `macos_finder`, `windows_tags` (`srxy[windows]`).

### TUI snapshots

New or changed TUI elements need snapshot coverage in `tests/tui/` (`assert_svg_snapshot`). Refresh: `UPDATE_TUI_SNAPSHOTS=1 pytest tests/tui/…`. See [AGENTS.md](../AGENTS.md).
