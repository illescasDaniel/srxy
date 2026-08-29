# Active Context

_Last updated: 2026-08-29_

## Branch

- `cursor/d34ce3c1` — GUI cold-start (merged `feature/fixes_1.6.6`).

## Current focus

Merged parent `feature/fixes_1.6.6` (Search-after-cancel accent + AccentButton binding-loop fix). Cold-start import work restored; quality gate next, then commit, then splash / QML startup experiments.

## Done this session

- Faster GUI launch: timing hook, deferred `probe_capabilities`, application-layer shared helpers (GUI no longer imports CLI), slim CLI/`search_runner`/matcher/cache imports.
- Offscreen timings (median-ish): baseline `qml_loaded` ~1.06s → after fixes ~0.73–0.92s; `cli_imported` ~0.30s → ~0.10s.
- Merged `feature/fixes_1.6.6` into this worktree (fast-forward + stash pop).

## Next steps

1. Run `checks-win-quiet`; fix any breakage from the merge.
2. Commit cold-start work.
3. Splash screen + PySide6/QML startup improvements.
4. Remaining Final QA: Windows/macOS installers; then release.

## Key files touched

- `src/srxy/application/search_defaults.py`, `skipped_file_warnings.py`, `search_messages.py`, `startup_timing.py` — new light shared layer
- `src/srxy/adapters/inbound/cli/cli.py`, `gui/controller.py`, `gui/app.py`, `gui/capabilities.py` — slim imports + deferred probe
- `src/srxy/bootstrap` adapters (`text_extractor`, `image_similarity`, `content_cache`, `cache.py`, matching registry/fuzzy/phonetic)
- `tests/unit/test_gui_startup_imports.py` — import-graph regression
