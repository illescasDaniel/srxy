---
name: gui-recent-searches-one-list
description: (1) One recent_searches list in settings.json (newest first, cap 20 via RECENT_SEARCHES_CAP); the "last session" for the launch banner is simply…
type: decision
date: 2026-09-07
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** Trello scope lock for "GUI: recent searches + restore last path/query session": persist last **successful** search context (path, query text, query mode) only, cap ~20, launch Restore/Dismiss banner (never auto-search), query-field chevron popover with Restore / Restore & Search / Clear all, Reset preferences also clears history.
- **Decision:** (1) One `recent_searches` list in `settings.json` (newest first, cap 20 via `RECENT_SEARCHES_CAP`); the "last session" for the launch banner is simply `recent_searches[0]` — no separate storage key. (2) `RecentSearchEntry` carries `path`, `query_mode`, `simple_query`, `advanced_query`, `term_rows_json` (raw multi-term rows JSON so a restore can rebuild the query-builder UI exactly), `display` (precomputed human-readable query text for the banner/popover), `timestamp`. Deliberately no filters/options fields. (3) `save_recent_search` de-dupes an exact repeat (same path/mode/query) by moving it to the front rather than padding the list. (4) Controller records only on a non-cancelled `SearchFinishedEvent` (`_search_completed_ok` path), mirroring the existing "stale" baseline logic — a cancelled or failed run must not count as the last successful search. (5) `resetPreferences()` clears the in-memory recent list too (the settings.json file is already gone via `reset_settings()`, but the live QML-bound list must also drop so the banner/popover do not show stale data until next launch).
- **Rationale:** Single source of truth avoids drift between "last session" and "recent list" round-tripping; storing raw multi-term rows JSON (not just a formatted display string) is required for Restore to actually repopulate the query-builder UI, not just show text.
