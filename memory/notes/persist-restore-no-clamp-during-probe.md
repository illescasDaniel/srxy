---
name: persist-restore-no-clamp-during-probe
description: (1) While _capabilities_probing, clamp only OCR; leave semantic / semantic_image / transcribe until the real probe. (2) Write prefs on dialog OK as well…
type: decision
date: 2026-08-30
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** User checked Similar meaning + Persist, OK, quit, relaunched — option was gone. `default_capabilities()` always has `semantic_enabled=False` (GPU probe deferred); init clamped persisted ticks away before `refreshCapabilities()`. Separately, write-only-on-exit meant a failed silent `save_settings` (e.g. root-owned `~/.config/srxy`) left no payload.
- **Decision:** (1) While `_capabilities_probing`, clamp only OCR; leave semantic / semantic_image / transcribe until the real probe. (2) Write prefs on dialog OK as well as shutdown. (3) `save_settings` / `save_persisted_search_prefs` return bool; emit `errorOccurred` when write fails.
- **Rationale:** Probe deferral is for startup speed; it must not erase user intent. OK-time write matches “I confirmed Persist”; surfacing permission errors beats silent no-ops.
