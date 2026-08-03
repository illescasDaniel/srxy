# Agent instructions

## Quality gate

After writing or changing code, run the quality gate until it passes cleanly.

1. **Autofix** — run `./scripts/quality/checks.sh --fix` and address any remaining issues it reports.
2. **Verify** — run `./scripts/quality/checks.sh` (no `--fix`) and confirm a clean pass.
3. **Repeat** — if either step fails, fix the reported problems (rerun `--fix` for Ruff/shell issues; fix basedpyright, pip-audit, and pytest failures in code) and go back to step 1 until both commands succeed.

Use the project env with `uv sync --extra semantic` (default `dev` dependency group).

The gate runs, in order: Ruff (lint + format) → ShellCheck/shfmt → basedpyright → pip-audit → build → pytest.

Locally, pytest runs integration and TUI tests (excluding `integration_full` unless you pass `--full`) with `-n auto --dist=loadgroup`. Day-to-day local runs also use `--testmon-forceselect --ff` (change-aware; `.testmondata` is gitignored). Coverage is enabled only for `--full` / `--full+cpu`. File-search fixtures live at `tests/fixtures/file_search/`; semantic corpus JSON at `tests/fixtures/corpus/`. Override the search tree with `SRXY_FILE_SEARCH_FIXTURES` if needed. CI runs `unit` tests only in parallel, excluding `semantic` and `transcribe` markers (`CI=true`); no testmon, no coverage.

Local verify (no `--fix`) runs light steps (Ruff, shell, basedpyright, pip-audit, build) **in parallel**, then **pytest alone** with `-n` = `nproc`. Locally, `integration and gui` tests are excluded from that pytest pass and then run **serially** (`-n 0`, `QT_QPA_PLATFORM=offscreen`) so PySide6 + torch/CUDA do not kill xdist workers. CI skips that serial follow-up (`CI=true`).

The gate takes an exclusive flock on `.srxy-quality-gate.lock` (repo root). A second overlapping `checks.sh` exits immediately with an error instead of spawning another pytest tree.

`--fix` autofixes Ruff and shell scripts only; basedpyright and test failures must be fixed manually. `--fix`, `--full`, and `--full+cpu` are ignored when `CI=true`.

Before a release, run `./scripts/quality/checks.sh --full` (and `--full+cpu` when validating CUDA/CPU transcribe parity). Full details: [docs/development.md](docs/development.md).

### Running the gate (agent pitfalls)

- Pytest streams live under the gate (including `CI=true`). After `[6/6] pytest` you should see a `pytest: starting (workers=…)` banner and then `[gwN] PASSED` lines. A long blank gap means a real stall — the stall/wall watchdog will kill the run (exit 124) instead of hanging forever.
- Override limits with `LIB_PYTEST_WALL_SECONDS` / `LIB_PYTEST_STALL_SECONDS` if needed.
- **Do not** pipe the gate through `tail` (or anything that only prints on EOF). Prefer running `./scripts/quality/checks.sh` / `--fix` directly, or `tee` a log **without** truncating live output. With `| tee … | tail -N`, a healthy but long verify looks hung because nothing appears until the process exits.
- If the gate refuses to start because of the lock file, another gate is still running — stop leftover `checks.sh` / pytest processes for this repo, then retry. Do not start a second gate in parallel.
- If verify seems stuck despite the lock: inspect the process tree and the full log. A clean re-run usually finishes in tens of seconds under `CI=true`.
- Optional when GPU contention is noisy: `CUDA_VISIBLE_DEVICES="" ./scripts/quality/checks.sh` (or the same for `CI=true` local mimic runs).

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
