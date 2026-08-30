# Active Context

_Last updated: 2026-08-30_

## Branch

- `feature/fixes_1.6.6` — version target **1.7.0** (worktree `cursor/3ae3cdde`).

## Current focus

Just finished: **copy-venv shebang / editable-path rewrite** so a copied worktree `.venv` no longer runs primary-checkout interpreters or imports.

## Touched files

- `.cursor/skills/copy-venv-to-worktree-srxy/scripts/rewrite_venv_paths.py` — new: rewrite shebangs / `.pth` / `direct_url.json` + Windows `UV_PYTHON_PATH`
- `.cursor/skills/copy-venv-to-worktree-srxy/scripts/copy-venv.sh` — call rewriter; `--offline --reinstall-package srxy`; verify shebang + `srxy.__file__`
- `.cursor/skills/copy-venv-to-worktree-srxy/scripts/copy-venv-win.ps1` — same + trampoline path verify
- `.cursor/skills/copy-venv-to-worktree-srxy/SKILL.md` — document that `uv sync` alone does not fix shebangs
- `tests/unit/test_copy_venv_rewrite.py` — given/when/then coverage for the rewriter
- `memory/decisions.md`, `memory/activeContext.md`, `memory/progress.md`

## Verified

- Unit tests for rewriter: 2 passed
- `shellcheck` + `shfmt` clean on `copy-venv.sh`
- Core pytest: 673 passed, 1 skipped (after `uv sync --extra semantic` in this worktree)
- `checks.sh --quiet --fix` light steps clean (earlier all-bucket run failed core only for missing semantic packages before sync)

## Next steps

1. Commit copy-venv shebang rewrite (+ prior Unix copy-venv / shellcheck fixes if still uncommitted on parent) when ready.
2. Optional: `/copy-venv-to-worktree-srxy --force` in this worktree to replace the thin sync-created `.venv` with a primary mirror + rewrite.
3. User: manual Windows (and other) installer verification for 1.7.0.
4. `/delete-worktree-srxy` for applied worktrees when ready.
