---
name: gate-parallel-progress-and-ctrl-c
description: Keep pytest buckets parallel. pytest.sh polls running buckets: emit [gate] pytest[bucket]: still running (Ns) every LIB_PYTEST_PROGRESS_INTERVAL (default…
type: decision
date: 2026-09-11
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** `uv run task checks --full` looked frozen after printing bucket args (parallel buckets wrote to temp logs with no live progress). Ctrl+C in `checks.py` raised `KeyboardInterrupt` in Python instead of stopping the bash gate tree.
- **Decision:** Keep pytest buckets **parallel**. `pytest.sh` polls running buckets: emit `[gate] pytest[bucket]: still running (Ns)` every `LIB_PYTEST_PROGRESS_INTERVAL` (default 25s); in quiet mode also tail `[gate]` lines from per-bucket logs (with `LIB_GATE_BUCKET_NAME` prefix in `agent_progress`). `checks.sh` overlaps pytest with light steps via `tee`. `checks.py` uses `Popen(start_new_session=True)` + SIGINT/SIGTERM → `killpg`, exit 130. **Do not** serialize buckets for verbose mode.
- **Rationale:** Speed from overlap; liveness from periodic progress without dumping full verbose interleave. Taskipy: pass flags after `--` (`uv run task checks -- --fix --full`).
