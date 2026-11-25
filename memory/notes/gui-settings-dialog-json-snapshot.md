---
name: gui-settings-dialog-json-snapshot
description: (1) Top menu Settings has shortcut Actions (Download All Models, Reset Cache, Reset All Settings) plus All Settings… for the full dialog. (2)…
type: decision
date: 2026-08-30
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** Need a Settings menu for clearing/re-downloading AI models and clearing the encrypted results cache, with per-kind rows and live size/status.
- **Decision:** (1) Top menu **Settings** has shortcut Actions (**Download All Models**, **Reset Cache**, **Reset All Settings**) plus **All Settings…** for the full dialog. (2) `SearchController.settingsJson` holds a refreshed snapshot (`models[]` + `cache` + `preferences` + `busy`); QML parses it and binds rows. (3) Clears / resets / download-all go through a Yes/No confirm; re-downloads reuse `_DownloadWorker` / progress UI with `_settings_redownload` skipping the search-time download confirm and chaining kinds for `all`. (4) **Reset All Settings** deletes `settings.json` via `reset_settings()`, re-applies system language without rewriting the file, and restores factory search options/filters (clears persist flags) so the live session matches the missing file. (5) Helpers live in `application/disk_usage.py` + `application/settings_maintenance.py` over existing `model_store` / `cache` / `settings` APIs.
- **Rationale:** Common maintenance stays one click away; the full dialog covers per-model detail. Avoids duplicating download UX; keeps OCR/vendor wipe out of scope until dedicated clear APIs exist.
