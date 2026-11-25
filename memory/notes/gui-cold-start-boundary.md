---
name: gui-cold-start-boundary
description: (1) Shared light modules under application/ (search_defaults, skipped_file_warnings, search_messages, startup_timing); GUI/TUI/deps_preflight no longer…
type: decision
date: 2026-08-29
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** GUI launch was ~1.0–1.1s to `Main.qml` (offscreen Windows), dominated by eager CLI/search imports (OCR/semantic/transcribe/cache/rapidfuzz) before first paint. FluentWinUI3 stays; SrxyLauncher is installer-only; splash deferred.
- **Decision:** (1) Shared light modules under `application/` (`search_defaults`, `skipped_file_warnings`, `search_messages`, `startup_timing`); GUI/TUI/deps_preflight no longer import `adapters.inbound.cli` for helpers. (2) CLI/`search_runner`/capability/bootstrap adapters use function-local imports for heavy outbound stacks; `cryptography.fernet` deferred inside cache encrypt/decrypt. (3) `SearchController` starts with `default_capabilities()` + `_capabilities_probing`, then `QTimer.singleShot(0, refreshCapabilities)`. (4) Opt-in `SRXY_STARTUP_TIMING=1` (+ `SRXY_STARTUP_EXIT=1` for benchmark quit after QML).
- **Rationale:** Measured wins — `cli_imported` ~0.30s → ~0.10s; `qml_loaded` ~1.06s → ~0.73–0.92s depending on env warmth. Keeps first paint free of OCR/transcribe/search_files/cryptography/rapidfuzz. Regression: `tests/unit/test_gui_startup_imports.py`. Gate: `checks-win-quiet` PASSED.
