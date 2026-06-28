# Agent instructions

## Quality gate

After writing or changing code, run the quality gate until it passes cleanly.

1. **Autofix** — run `./scripts/quality/checks.sh --fix` and address any remaining issues it reports.
2. **Verify** — run `./scripts/quality/checks.sh` (no `--fix`) and confirm a clean pass.
3. **Repeat** — if either step fails, fix the reported problems (rerun `--fix` for Ruff/shell issues; fix basedpyright, pip-audit, and pytest failures in code) and go back to step 1 until both commands succeed.

Use the project venv with dev dependencies installed (`pip install -e ".[dev,semantic]"`).

The gate runs, in order: Ruff (lint + format) → ShellCheck/shfmt → basedpyright → pip-audit → build → pytest.

Locally, pytest runs the **full suite** including integration, QA (`tests/integration/qa/`), and TUI tests. QA tests use the committed corpus at `tests/fixtures/qa_corpus/` (dev-only, not installed with the package). Override with `SRXY_QA_CORPUS` if needed. CI runs unit tests only (`CI=true`).

`--fix` autofixes Ruff and shell scripts only; basedpyright and test failures must be fixed manually. `--fix` is ignored when `CI=true`.

## Typing

Do not annotate functions that return `None` with `-> None`. Omit the return type instead.
