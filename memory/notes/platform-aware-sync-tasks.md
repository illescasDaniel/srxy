---
name: platform-aware-sync-tasks
description: (1) Add scripts/dev/sync.py (plus Unix sync.sh / Windows sync.ps1) that picks extras per platform and mode. (2) Taskipy: sync = runtime…
type: decision
date: 2026-08-30
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** Agents and docs kept repeating OS-specific `uv sync --extra …` recipes (`semantic-gpu` on GPU Linux/Windows, `semantic` on macOS / CPU-only). Easy to get wrong; Windows especially thrashes CPU↔CUDA torch without `semantic-gpu`.
- **Decision:** (1) Add `scripts/dev/sync.py` (plus Unix `sync.sh` / Windows `sync.ps1`) that picks extras per platform and mode. (2) Taskipy: `sync` = runtime (`--no-default-groups`), `sync-dev` = default for agents/devs, `sync-uploader` = dev + `uploader`; keep `sync-win` as a `sync-dev` alias. (3) Document in README, AGENTS.md, development.md, installation.md; point copy-venv / gate missing-venv messages at `sync-dev`. (4) Do not extend `[tool.uv.sources]` to Linux — PyPI Linux torch is already CUDA; Windows keeps the pytorch-cu130 sources marker.
- **Rationale:** One command per intent; fewer multi-GiB mistakes; shorter docs; copy-venv and gates stay aligned with the same extras.
