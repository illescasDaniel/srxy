---
name: copy-venv-to-worktree-srxy
description: Bootstrap an srxy linked worktree environment by reusing the primary checkout's installed .venv when asked to copy or set up the worktree venv.
---

# Copy Venv to Worktree (srxy)

Reuse existing repository helpers; do not duplicate scripts. They copy `.venv`, rewrite shebangs/editable paths (plus Windows trampoline `UV_PYTHON_PATH`), then reinstall editable srxy through platform-aware sync. Copying alone or plain `uv sync` does not reliably repair console-script paths.

## Preflight

- Identify destination and primary checkout using `git rev-parse --show-toplevel`, `git worktree list --porcelain`, and Git/common-directory metadata. Confirm the same repository and distinct roots. In the primary, report nothing to copy.
- Inspect the helper before execution. Existing helpers select the first `git worktree list` path outside the user's `.cursor/worktrees` and split paths at whitespace. Run only when that selection matches the actual primary checkout and worktree paths contain no spaces. Otherwise use `uv run task sync-dev` in the destination; do not execute against the wrong source or edit helpers as part of this skill.
- Confirm source `.venv` exists; otherwise sync the primary first. Replace an existing destination environment only when authorized: helper `--force` / `-Force` deletes it first.
- Helpers try offline reinstall, then **automatically retry online on failure**. Invoke them only when network fallback is allowed by current instructions and environment permissions. For offline-only requests, do not invoke them: use an explicitly offline path such as `uv run --offline --no-project python scripts/dev/sync.py --offline`, reporting missing cached packages instead of downloading. Do not promise helper execution never downloads.

## Run from the destination checkout

Resolve these maintained helper paths from the destination repository root, not this skill directory. The `.cursor/skills` location does not require Cursor when preflight conditions hold.

Unix / macOS (requires `rsync`):

```bash
bash .cursor/skills/copy-venv-to-worktree-srxy/scripts/copy-venv.sh
```

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .cursor/skills/copy-venv-to-worktree-srxy/scripts/copy-venv-win.ps1
```

Add `--force` or `-Force` only for authorized replacement; do not delete files manually to bypass the guard.

## Verify

Require successful helper exit and `srxy.__file__` under destination `src/`. On Unix check the reported pytest shebang points into destination `.venv`; on Windows check destination `pytest.exe` succeeds. Review torch output against actual hardware: NVIDIA requires the project's CUDA build and `cuda=True`; CPU-only machines need no semantic extra; Apple Silicon uses MPS. Missing torch in core-only environments does not itself prove copy failure. Follow `AGENTS.md` for environment repair. Report source, destination, verification, and online fallback if used.
