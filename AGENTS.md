# Agent instructions

## Quality gate

After writing or changing code, run the quality gate until it passes cleanly.

1. **Autofix** — run `./scripts/quality/checks.sh --fix` and address any remaining issues it reports.
2. **Verify** — run `./scripts/quality/checks.sh` (no `--fix`) and confirm a clean pass.
3. **Repeat** — if either step fails, fix the reported problems (rerun `--fix` for Ruff/shell issues; fix basedpyright, pip-audit, and pytest failures in code) and go back to step 1 until both commands succeed.

Use the project venv with dev dependencies installed (`pip install -e ".[dev,semantic]"`).

The gate runs, in order: Ruff (lint + format) → ShellCheck/shfmt → basedpyright → pip-audit → build → pytest.

Locally, pytest runs integration and TUI tests (excluding `integration_full` unless you pass `--full`). File-search fixtures live at `tests/fixtures/file_search/`; semantic corpus JSON at `tests/fixtures/corpus/`. Override the search tree with `SRXY_FILE_SEARCH_FIXTURES` if needed. CI runs unit tests only (`CI=true`).

`--fix` autofixes Ruff and shell scripts only; basedpyright and test failures must be fixed manually. `--fix`, `--full`, and `--full+cpu` are ignored when `CI=true`.

Before a release, run `./scripts/quality/checks.sh --full` (and `--full+cpu` when validating CUDA/CPU transcribe parity). Full details: [docs/development.md](docs/development.md).

## Typing

Do not annotate functions that return `None` with `-> None`. Omit the return type instead.
