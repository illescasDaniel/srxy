---
name: copy-venv-rewrites-paths
description: (1) Add rewrite_venv_paths.py and run it after copy in copy-venv.sh / copy-venv-win.ps1. (2) Rewrite text shebangs, activate scripts, .pth, and…
type: decision
date: 2026-08-30
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** After rsync/robocopy of `.venv` into a worktree, console-script shebangs (`#!/primary/.venv/bin/python`), `srxy.pth`, and `direct_url.json` still point at the primary checkout. The quality gate prefers direct `.venv/bin/*` / `Scripts\*.exe` (`lib_uv_run` / `Get-VenvExe`), so worktree pytest executed **primary** Python and loaded **primary** `srxy`. `uv sync` does not rewrite those entry points ([astral-sh/uv#18196](https://github.com/astral-sh/uv/issues/18196)).
- **Decision:** (1) Add `rewrite_venv_paths.py` and run it after copy in `copy-venv.sh` / `copy-venv-win.ps1`. (2) Rewrite text shebangs, activate scripts, `*.pth`, and `direct_url.json`; on Windows also update trampoline `UV_PYTHON_PATH` PE resources when they embed the old venv python. (3) Follow with `uv sync --offline --reinstall-package srxy` (plus existing extras / `sync-win` on GPU Windows). (4) Fail the script if pytest shebang / `srxy.__file__` still reference the primary tree.
- **Rationale:** Avoids multi-GiB re-downloads while making worktree tools and editable imports land on the worktree tree. Native binaries (`ruff`) and uv-managed `python` symlinks/trampolines are left alone.
