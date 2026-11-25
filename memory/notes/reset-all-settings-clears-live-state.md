---
name: reset-all-settings-clears-live-state
description: (1) resetPreferences restores factory SearchOptions() / default_search_filters(), clears both persist flags, reapplies args, refreshes stale. (2)…
type: decision
date: 2026-08-30
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** Reset All Settings deleted `settings.json` but left `_options` / `_filters` / persist flags in the controller. The dialogs still showed the old ticks, and `shutdown` → `_write_persisted_search_prefs` recreated the file.
- **Decision:** (1) `resetPreferences` restores factory `SearchOptions()` / `default_search_filters()`, clears both persist flags, reapplies args, refreshes stale. (2) `_write_persisted_search_prefs` no-ops when both persist flags are off and the settings file is absent (so quit after reset does not recreate it).
- **Rationale:** Removing the settings file must mean a clean slate for search prefs in the same session, not only on the next launch.
