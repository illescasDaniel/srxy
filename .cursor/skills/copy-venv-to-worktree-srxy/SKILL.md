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
rewrite console-script shebangs / editable `.pth` / `direct_url.json` (and on
Windows, trampoline `UV_PYTHON_PATH`) so tools run against the **worktree**
tree — then run a cheap offline `uv sync --reinstall-package srxy`. No
packages are re-downloaded.

`uv sync` alone does **not** fix shebangs after a copy
(https://github.com/astral-sh/uv/issues/18196). Without the rewrite, the
quality gate's direct `.venv/bin/pytest` (or `Scripts\pytest.exe`) still
executes the primary checkout's interpreter and loads primary `srxy`.

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
   - Runs `rewrite_venv_paths.py` (shebangs / `.pth` / `direct_url` /
     trampoline `UV_PYTHON_PATH`).
   - Runs `python scripts/dev/sync.py --dev --offline --reinstall-package srxy`
     (platform extras + CUDA ensure on NVIDIA). If offline fails (e.g. primary
     was synced without `semantic`), retries the same command online.
   - Verifies `srxy.__file__` is under the worktree `src/`, pytest runs, and
     prints torch version/CUDA check.

3. Verify the result reported by the script:
   - `srxy.__file__` under this worktree's `src/`
   - torch version contains `+cu` and `cuda=True` on an NVIDIA machine, or
     `cpu` / `cuda=False` on non-GPU machines — both are correct.

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
   - Runs `rewrite_venv_paths.py` (shebangs / `.pth` / `direct_url`).
   - Runs `scripts/dev/sync.py --dev --offline --reinstall-package srxy`
     (NVIDIA / Apple Silicon → `--extra semantic`; else core+dev only).
     Retries online if offline fails.
   - Verifies pytest shebang points at this worktree's `.venv`,
     `srxy.__file__` is under worktree `src/`, and prints torch check.

3. Verify the result reported by the script:
   - pytest shebang under this worktree's `.venv/bin/python`
   - `srxy.__file__` under this worktree's `src/`
   - torch version and `cuda=True`/`False` as appropriate for this machine.

## Edge cases

| Situation | What the script does |
|-----------|----------------------|
| Running inside the primary checkout | Exits 0 with a clear message — nothing to copy from. |
| Destination already has `.venv` | Warns and exits unless `--force` / `-Force` is passed. |
| Source `.venv` is missing | Instructs the user to sync the primary checkout first (`uv run task sync-dev`), then retry. |
| Primary checkout not found in worktree list | Aborts with a diagnostic message. |
| `rsync` missing (Unix) | Aborts and asks to install `rsync`. |
| Shebang / `srxy.__file__` still point at primary after rewrite | Exits non-zero — do not treat the copy as successful. |
