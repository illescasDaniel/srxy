# Agent instructions

## Quality gate

After writing or changing code, run the quality gate until it passes cleanly.

1. **Autofix** — run `./scripts/quality/checks.sh --fix` and address any remaining issues it reports.
2. **Verify** — run `./scripts/quality/checks.sh` (no `--fix`) and confirm a clean pass.
3. **Repeat** — if either step fails, fix the reported problems (rerun `--fix` for Ruff/shell issues; fix basedpyright, pip-audit, and pytest failures in code) and go back to step 1 until both commands succeed.

Use the project env with `uv sync --extra semantic` (default `dev` dependency group).

The gate runs, in order: Ruff (lint + format) → ShellCheck/shfmt → basedpyright → pip-audit → build → pytest.

Locally, pytest runs integration and TUI tests (excluding `integration_full` unless you pass `--full`) with `-n auto --dist=loadgroup`. Day-to-day local runs also use `--testmon-forceselect --ff` (change-aware; `.testmondata` is gitignored). Coverage is enabled only for `--full` / `--full+cpu`. File-search fixtures live at `tests/fixtures/file_search/`; semantic corpus JSON at `tests/fixtures/corpus/`. Override the search tree with `SRXY_FILE_SEARCH_FIXTURES` if needed. CI runs `unit` tests only in parallel, excluding `semantic` and `transcribe` markers (`CI=true`); no testmon, no coverage.

`--fix` autofixes Ruff and shell scripts only; basedpyright and test failures must be fixed manually. `--fix`, `--full`, and `--full+cpu` are ignored when `CI=true`.

Before a release, run `./scripts/quality/checks.sh --full` (and `--full+cpu` when validating CUDA/CPU transcribe parity). Full details: [docs/development.md](docs/development.md).

## TUI changes

When adding or changing TUI widgets, layout, or visible labels, add snapshot tests under [`tests/tui/`](tests/tui/) using `assert_svg_snapshot` from [`tests/tui/helpers.py`](tests/tui/helpers.py). Snapshots live in [`tests/tui/snapshots/`](tests/tui/snapshots/) as `*.snap.txt` files (visible SVG text).

Regenerate after intentional UI changes:

```bash
UPDATE_TUI_SNAPSHOTS=1 uv run pytest tests/tui/test_query_builder_display.py
```

## GUI changes

When adding or changing GUI QML layout or visible labels, add or update text-tree snapshot tests under [`tests/gui/`](tests/gui/). Refresh with `UPDATE_GUI_SNAPSHOTS=1 QT_QPA_PLATFORM=offscreen uv run pytest tests/gui/test_gui_snapshots.py`.

Run the full local gate (`./scripts/quality/checks.sh`) so integration, TUI, and GUI tests execute; CI (`CI=true`) runs `unit` tests excluding `semantic` and `transcribe`.

## Typing

Do not annotate functions that return `None` with `-> None`. Omit the return type instead.
