---
name: gui-opt-in-persist-options-filters
description: (1) Extend existing settings.json (settings_path(): $SRXY_HOME/settings.json or ~/.config/srxy/settings.json) with persist_options / persist_filters flags…
type: decision
date: 2026-08-30
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** Search options and filters were session-only; users wanted an explicit way to keep them across exits without always writing prefs. Installer prefix vs PyPI/dev needed a single storage story.
- **Decision:** (1) Extend existing `settings.json` (`settings_path()`: `$SRXY_HOME/settings.json` or `~/.config/srxy/settings.json`) with `persist_options` / `persist_filters` flags plus `options` / `filters` payloads — no separate `app-preferences.json`. (2) GUI-only: checkbox + Reset at the bottom of each dialog; persist flag committed on OK; payloads written in `controller.shutdown` (`aboutToQuit`). Unpersist clears that payload. (3) Shared load/save helpers in `application/settings.py` for a future TUI wire-up.
- **Rationale:** Reuses the language settings path rules users already have; write-on-exit matches the checkbox wording; Reset only edits the dialog draft so OK remains the confirm step.
