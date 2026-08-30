---
name: copy-venv-to-worktree-srxy
description: >-
  Copy the .venv from the primary srxy checkout into the current linked
  worktree so developers and agents avoid re-downloading multi-GB CUDA
  packages. Use when the user invokes /copy-venv-to-worktree-srxy, asks to
  copy or set up the venv in this worktree, or when a worktree is freshly
  created and needs the venv bootstrapped quickly.
disable-model-invocation: true
---
# Copy Venv to Worktree (srxy)

Use only when the user explicitly invokes `/copy-venv-to-worktree-srxy` or
asks to copy / set up the `.venv` in the current worktree.

## Goal

Copy the fully-installed `.venv` from the primary checkout into this worktree,
then run a fast `uv sync` whose only job is to re-stamp the activation-script
paths for the new location. No packages are re-downloaded.

## Steps

### Windows

1. Run the helper script from the worktree root:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .cursor/skills/copy-venv-to-worktree-srxy/scripts/copy-venv-win.ps1
   ```

   Add `-Force` if the worktree already has a `.venv` that you want to
   replace:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .cursor/skills/copy-venv-to-worktree-srxy/scripts/copy-venv-win.ps1 -Force
   ```

2. The script:
   - Auto-detects the primary checkout from `git worktree list`.
   - Guards against running in the primary itself.
   - Uses `robocopy` to mirror `.venv`.
   - Runs `uv run task sync-win` (NVIDIA GPU detected) or
     `uv sync --extra semantic --extra windows` (no GPU) to fix paths.
   - Prints source path, destination path, and torch version/CUDA check.

3. Verify the result reported by the script:
   - torch version contains `+cu` and `cuda=True` on an NVIDIA machine, or
   - `cpu` / `cuda=False` on non-GPU machines — both are correct.

### Unix / macOS

1. Run the helper script from the worktree root:

   ```bash
   bash .cursor/skills/copy-venv-to-worktree-srxy/scripts/copy-venv.sh
   ```

   Add `--force` if the worktree already has a `.venv` that you want to
   replace:

   ```bash
   bash .cursor/skills/copy-venv-to-worktree-srxy/scripts/copy-venv.sh --force
   ```

2. The script:
   - Auto-detects the primary checkout from `git worktree list`.
   - Guards against running in the primary itself.
   - Uses `rsync` to mirror `.venv`.
   - Runs `uv sync --extra semantic` to fix activation-script paths.
   - Prints source path, destination path, and torch version/CUDA check.

3. Verify the result reported by the script:
   - torch version and `cuda=True`/`False` as appropriate for this machine.

## Edge cases

| Situation | What the script does |
|-----------|----------------------|
| Running inside the primary checkout | Exits 0 with a clear message — nothing to copy from. |
| Destination already has `.venv` | Warns and exits unless `--force` / `-Force` is passed. |
| Source `.venv` is missing | Instructs the user to sync the primary checkout first (`uv sync --extra semantic` on Unix; `uv run task sync-win` on Windows), then retry. |
| Primary checkout not found in worktree list | Aborts with a diagnostic message. |
| `rsync` missing (Unix) | Aborts and asks to install `rsync`. |
