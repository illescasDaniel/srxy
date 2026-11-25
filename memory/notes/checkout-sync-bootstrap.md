---
name: checkout-sync-bootstrap
description: (1) Drop sync / sync-win Taskipy tasks; keep sync-dev / sync-uploader as thin wrappers that never prune the group they run from. (2) Pruning syncs…
type: decision
date: 2026-09-01
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** `uv run task sync` (runtime-only, `--no-default-groups`) runs through Taskipy from `.venv`, which loads dev-only deps like `psutil`. Windows refuses to unlink the loaded `.pyd` (os error 5); on Unix the dev group would be ripped out mid-run.
- **Decision:** (1) Drop `sync` / `sync-win` Taskipy tasks; keep `sync-dev` / `sync-uploader` as thin wrappers that never prune the group they run from. (2) Pruning syncs (`--no-default-groups`, `--only-group`) must use `uv run --no-project python scripts/dev/sync.py` so the script runs on a standalone interpreter. (3) `sync.py` detects `running_inside_project_venv()` and refuses pruning unless `--force`.
- **Rationale:** Taskipy cannot orchestrate its own uninstall; `--no-project` is the uv-supported escape hatch.
