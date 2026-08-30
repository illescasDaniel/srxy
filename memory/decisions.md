# Decisions

_Log of significant technical, structural, or dependency choices. Newest first._

## 2026-08-30 — Search progress bar is file-scan only (not OCR page / transcribe segment %)

- **Context:** Searching Pictures with OCR, the progress bar could jump to 100% while status still showed `OCR · …`, then drop to ~95%. Document OCR (and transcribe) emit determinate activity with `current/total` for pages/segments; the GUI also fed those ratios into the same progress bar used for files completed / files listed.
- **Decision:** `SearchActivityEvent` updates status/spinner only. The determinate search progress bar and `progressCount` come solely from `SearchProgressEvent` (and terminal finished/cancel). Page/segment percent remains visible in the status line via `format_activity_status_body` (`100% OCR · scan.pdf`).
- **Rationale:** Mixing two independent ratios on one bar guarantees non-monotonic jumps whenever an in-file counter finishes ahead of the outer file counter.

## 2026-08-30 — Heavy-mode search: light files inline, OCR/transcribe/CLIP in thread pool

- **Context:** With OCR (or transcribe/CLIP) on, every discovered file — including plain `.txt` — went into the same `ThreadPoolExecutor`. FIFO queueing meant text scoring sat behind in-flight OCR workers, so progress looked frozen on the image being OCRed even though fast files were waiting.
- **Decision:** (1) Classify paths with `ocr_candidate_path` / `transcribe_candidate_path` (TextExtractorPort) plus existing `is_image_path`. (2) When `_use_threads`, score light files synchronously on the walking thread; submit only heavy candidates to the pool. (3) Non-blocking drain of completed heavy futures between light files; blocking drain at `pending_limit` and after listing. Documents stay inline even with OCR (embedded text is usually cheap; scanned-page OCR is a known follow-up).
- **Rationale:** Keeps streaming results/progress for text while heavy media runs in parallel; avoids GIL thrashing from putting pure-text matching on the same thread pool as OCR.
## 2026-08-30 — GUI Settings dialog via JSON snapshot property

- **Context:** Need a Settings menu for clearing/re-downloading AI models and clearing the encrypted results cache, with per-kind rows and live size/status.
- **Decision:** (1) Top menu **Settings** has shortcut Actions (**Download All Models**, **Reset Cache**, **Reset All Settings**) plus **All Settings…** for the full dialog. (2) `SearchController.settingsJson` holds a refreshed snapshot (`models[]` + `cache` + `preferences` + `busy`); QML parses it and binds rows. (3) Clears / resets / download-all go through a Yes/No confirm; re-downloads reuse `_DownloadWorker` / progress UI with `_settings_redownload` skipping the search-time download confirm and chaining kinds for `all`. (4) **Reset All Settings** deletes `settings.json` via `reset_settings()` and re-applies system language without rewriting the file. (5) Helpers live in `application/disk_usage.py` + `application/settings_maintenance.py` over existing `model_store` / `cache` / `settings` APIs.
- **Rationale:** Common maintenance stays one click away; the full dialog covers per-model detail. Avoids duplicating download UX; keeps OCR/vendor wipe out of scope until dedicated clear APIs exist.

## 2026-08-30 — Concurrent search activity fan-in + early `0/N` progress

- **Context:** OCR searches on small folders (e.g. 2 files in Downloads) left the GUI stuck on “Searching…” with no `1/2` counts and no `OCR · filename` labels. Sticky `activity.searching` blocked `status.scanning`; `_catch_up_progress` skipped `completed == 0`; heavy GUI/TUI searches use a thread pool that omitted `on_activity` to avoid overlapping labels.
- **Decision:** (1) Emit `on_progress(completed, listed)` whenever listing finishes and `listed > 0` (including `0/N`). (2) Add `concurrent_activity_fan_in` so each worker thread owns one activity slot; clear removes that slot only; downstream sees the latest remaining label. Pass the fan-in into thread-pool `_submit_file`. (3) GUI/TUI treat generic Searching as yielding to `Scanning current/total`; specific ops (`OCR ·`, `CLIP ·`, …) still own the status line.
- **Rationale:** Keeps thread-pool speed for heavy modes while restoring determinate file counts and per-file operation text during the long OCR wait.

## 2026-08-30 — AccentButton icons follow the style's label colour, not our WCAG `foreground`

- **Context:** On Linux/Material the Options dialog OK button drew white text while the Search button drew a black label *and* a black magnifier glyph. Material/Fluent/Universal compute their own highlighted label colour (`Material.primaryHighlightedTextColor`) and ignore `palette.buttonText`, so our WCAG `contrast_text_on(#3daee9) == #000000` only reached the Search button — which replaced its `contentItem` with a hand-tinted `Row { ColorOverlay; Text }`.
- **Decision:** (1) Drop the Search button's custom `contentItem`/`ColorOverlay` (and the now-unused `Qt5Compat.GraphicalEffects` import in `Main.qml`); use plain `text` + `icon.source` so the style's own `IconLabel` paints both. (2) `AccentButton` also pins `palette.brightText: foreground`, because Fusion/Basic tint icons from `brightText` while drawing the label from `buttonText`. (3) `icon.color` is assigned **only** on macOS, via `Binding { when: Qt.platform.os === "osx" }` — Aqua predates `defaultIconColor`, but on every other style the role must stay *unresolved*: `QQuickIconLabel` falls back to `defaultIconColor` only when `icon.color` was never set, so even `"transparent"` strands the glyph untinted.
- **Rationale:** Matching the style beats out-computing it — the OK button was already the style's own colour, so the only way for Search to agree was to stop overriding. Reading the painted colour back (`contentItem.color`) was tried and rejected: `QQuickIconLabel::color` is non-bindable, so the value froze at creation. Also removes a latent packaging bug — both `packaging/macos/prune-pyside.sh` and `packaging/linux-appimage/prune_pyside.sh` already delete the `Qt5Compat` QML module that `Main.qml` imported. Regression test asserts the Search label, its `QQuickIconImage` tint, and the dialog OK label are all the same colour.
## 2026-08-30 — `[semantic]` is GPU-only; drop `semantic-gpu` name and CPU semantic

- **Context:** Offering a lighter CPU `[semantic]` alongside `[semantic-gpu]` encouraged installs that are too slow for real use, and the dual extras confused docs/`sync-dev`.
- **Decision:** (1) Keep one optional extra named `[semantic]` whose deps are the former `semantic-gpu` stack (sentence-transformers, faster-whisper, rawpy, explicit torch/torchaudio/torchvision, cublas markers). (2) Delete the old CPU-leaning semantic set and the `semantic-gpu` alias. (3) `sync.py` adds `--extra semantic` only for Linux/Windows NVIDIA or macOS Apple Silicon (MPS); no GPU / CUDA skip → no semantic extra. (4) README/install docs: GPU rows use `srxy[semantic]`; remove “Fast CPU, no GPU”; no-GPU users get core-only.
- **Rationale:** Semantic search without a GPU is a poor default; one extra name matches user intent and keeps Windows CUDA via `[tool.uv.sources]` on checkout sync.

## 2026-08-30 — `pywin32` is a core Windows dependency (no `[windows]` extra)

- **Context:** Install docs, installer specs, CI, and `sync-dev` all had to remember `--extra windows` / `srxy[…,windows]` just to get Explorer tag support.
- **Decision:** (1) Add `pywin32>=312; platform_system == 'Windows'` to core `[project] dependencies`. (2) Drop the `[windows]` extra entirely (no empty stub). (3) Stop appending `[windows]` in `sync.py`, installer `package_extras_for_host`, CI, and docs; bump privacy notice to v7 (pywin32 listed under core).
- **Rationale:** Platform markers install pywin32 only on Windows; end-user and agent commands drop a whole extra dimension.

## 2026-08-30 — Linux `semantic-gpu` only with NVIDIA; CI stays semantic-free

- **Context:** First cut of `sync-dev` always used `--extra semantic-gpu` on Linux. CI never needed torch extras for `core+gui+tui`.
- **Decision:** (1) Linux matches Windows: `semantic-gpu` only when NVIDIA is detected (same skip envs). No GPU → `--extra semantic`. (2) Document that GitHub Actions keeps `uv sync --frozen` (no `[semantic]` / `[semantic-gpu]`); CI does not run the heavy suite.
- **Rationale:** Avoid multi-GiB CUDA wheels on CPU-only Linux laptops; CI stays lean and already omitted semantic extras.

## 2026-08-30 — Platform-aware `sync` / `sync-dev` / `sync-uploader` tasks

- **Context:** Agents and docs kept repeating OS-specific `uv sync --extra …` recipes (`semantic-gpu` on GPU Linux/Windows, `semantic` on macOS / CPU-only). Easy to get wrong; Windows especially thrashes CPU↔CUDA torch without `semantic-gpu`.
- **Decision:** (1) Add `scripts/dev/sync.py` (plus Unix `sync.sh` / Windows `sync.ps1`) that picks extras per platform and mode. (2) Taskipy: `sync` = runtime (`--no-default-groups`), `sync-dev` = default for agents/devs, `sync-uploader` = dev + `uploader`; keep `sync-win` as a `sync-dev` alias. (3) Document in README, AGENTS.md, development.md, installation.md; point copy-venv / gate missing-venv messages at `sync-dev`. (4) Do not extend `[tool.uv.sources]` to Linux — PyPI Linux torch is already CUDA; Windows keeps the pytorch-cu130 sources marker.
- **Rationale:** One command per intent; fewer multi-GiB mistakes; shorter docs; copy-venv and gates stay aligned with the same extras.

## 2026-08-30 — copy-venv rewrites shebangs / editable `.pth` (uv sync is not enough)

- **Context:** After rsync/robocopy of `.venv` into a worktree, console-script shebangs (`#!/primary/.venv/bin/python`), `srxy.pth`, and `direct_url.json` still point at the primary checkout. The quality gate prefers direct `.venv/bin/*` / `Scripts\*.exe` (`lib_uv_run` / `Get-VenvExe`), so worktree pytest executed **primary** Python and loaded **primary** `srxy`. `uv sync` does not rewrite those entry points ([astral-sh/uv#18196](https://github.com/astral-sh/uv/issues/18196)).
- **Decision:** (1) Add `rewrite_venv_paths.py` and run it after copy in `copy-venv.sh` / `copy-venv-win.ps1`. (2) Rewrite text shebangs, activate scripts, `*.pth`, and `direct_url.json`; on Windows also update trampoline `UV_PYTHON_PATH` PE resources when they embed the old venv python. (3) Follow with `uv sync --offline --reinstall-package srxy` (plus existing extras / `sync-win` on GPU Windows). (4) Fail the script if pytest shebang / `srxy.__file__` still reference the primary tree.
- **Rationale:** Avoids multi-GiB re-downloads while making worktree tools and editable imports land on the worktree tree. Native binaries (`ruff`) and uv-managed `python` symlinks/trampolines are left alone.
## 2026-08-30 — GUI search isolation + progressive ListView updates

- **Context:** Searching `$HOME` for common queries froze the GUI (and briefly the whole machine after a bad subprocess+pool experiment). py-spy showed in-process QThread scoring holding the GIL (~60% samples); NDJSON probes showed model flushes were cheap while status/ListView work and event-loop lag were not.
- **Decision:** (1) Always run GUI search in the existing search **subprocess**. (2) Gate worker `allow_process_pool` on `search_uses_subprocess(args)` so light searches stay single-process. (3) Stream-append results during search, sort once on finish; coalesce list/status updates; lighten results delegates (`reuseItems`, fixed height, shared context menu). (4) Animate activity via a separate `activitySpinner` property; use an indeterminate `ProgressBar` until a file total is known.
- **Rationale:** Isolates GIL from Qt without a free-threaded interpreter; avoids process-pool fork storms on large trees; keeps progressive UX without mid-list index storms.

## 2026-08-30 — Content routing via Magika + NUL gate (not path heuristics)

- **Context:** Content search and preview were mis-handling extensionless Minecraft `assets/objects` hashes and wrong-extension files (e.g. mp4 named `.txt`, text named `.mp4`, lying `.pdf`). Basename/hash skips and suffix-only routing were rejected.
- **Decision:** Add `magika` and `content_kind.resolve_content_route`: (1) NUL sample ⇒ never treat as UTF-8 body text even if Magika says `is_text`; (2) trust known media/doc suffixes when parse/metadata works; (3) escalate to Magika for extensionless, parse failure, or text/media mismatch; (4) `DocumentExtractError` on doc parse failure so callers can re-route. Wire through `line_sources`, `document_text`, `media_metadata`, and preview payloads.
- **Rationale:** Content typing matches real bytes; Magika beats libmagic packaging pain. NUL-first avoids Magika false-positive text on tiny binary samples.

## 2026-08-30 — Preview owns QTextDocument content; avoid dead QML/shiboken docs

- **Context:** Rapid GUI selection left preview on “Loading…” with `RuntimeError: libshiboken: Internal C++ object (QTextDocument) already deleted` in `_apply_preview_document` / `_refresh_preview_line_height`.
- **Decision:** Store `QQuickTextDocument`, re-resolve live `QTextDocument` via `textDocument()` + `shiboken6.isValid`, apply content with `setPlainText` (Python-owned), drop QML `text: controller.previewText` binding, always `previewChanged.emit()` after display updates, and estimate line height with a fixed constant (no `documentLayout()`/`defaultFont()` under shiboken).
- **Rationale:** QML TextArea can replace the C++ document while a worker result still holds a stale pointer; writing through the live Quick document and not dual-binding text stops the lifetime crash and stuck Loading.

## 2026-08-30 — Quality gate type checker: basedpyright → ty

- **Context:** basedpyright was slow in the day-to-day gate; Astral's `ty` is far faster and already in the Astral toolchain with Ruff/uv.
- **Decision:** Replace `basedpyright` with `ty` in the `dev` group; Unix `scripts/quality/ty.sh` and Windows `checks-win.ps1` both run `ty check --output-format github`. Config lives under `[tool.ty]` with rule/override parity for the old basedpyright relaxations (unknown/attribute noise, optional semantic/windows imports). Scope remains `src` + `tests` (scripts/packaging/examples excluded).
- **Rationale:** Same gate surface on both platforms, much lower type-check wall time; github annotation format plugs into existing `gate_emit.py` counting.

## 2026-08-30 — `semantic-gpu` extra + uv sources for Windows CUDA torch

- **Context:** `sync-win` always ran bare `uv sync --extra semantic` then `ensure-windows-cuda-torch.ps1`. Because the lockfile only had CPU PyPI torch, every sync uninstalled `+cu130` torch/torchvision/torchaudio and reinstalled CPU torch, then the ensure script re-downloaded CUDA wheels (~minutes / multi-GiB first time, still a full reinstall when already correct).
- **Decision:** (1) Add optional extra `semantic-gpu` = `srxy[semantic]` + explicit `torch`/`torchaudio`/`torchvision`. (2) `[tool.uv.index]` `pytorch-cu130` (`explicit = true`) + `[tool.uv.sources]` for those three packages with `marker = "sys_platform == 'win32'"`. (3) `sync-win.ps1` chooses `--extra semantic-gpu` when NVIDIA is present, else `--extra semantic`; keep ensure script as safety net. (4) Regenerate `uv.lock` so Windows resolves `2.13.0+cu130` etc.
- **Rationale:** Lockfile-owned CUDA wheels make `uv sync` a no-op when already installed (`Checked N packages`). Sources are Windows-only so macOS/Linux/CI keep PyPI. Windows-without-GPU may get the larger CUDA wheel if they use `semantic-gpu` or if transitive torch is resolved via sources for `semantic` — accepted (CUDA builds still run on CPU). Installer path unchanged (still post-pip ensure via `cuda_torch.py`).

## 2026-08-29 — Windows installer installs CUDA PyTorch after semantic

- **Context:** Desktop/offline Windows installs used `uv pip install 'srxy[semantic,windows]'`, which resolves CPU-only torch from PyPI. GPU-recommended installs then ran CLIP/semantic on CPU despite NVIDIA detection for the setup type.
- **Decision:** Add `installer/cuda_torch.py` and a `cuda_torch` install phase (after package) when semantic is selected on Windows and `has_nvidia_gpu()` is true. Reinstall torch/torchvision/torchaudio from the PyTorch `cu130` index (`cu126` fallback). Dev checkouts keep `scripts/dev/ensure-windows-cuda-torch.ps1` / `sync-win`; the installer uses the Python helper (no PowerShell dependency for end users).
- **Rationale:** Same root cause as the agent/dev venv trap; end users cannot be expected to run a manual `uv pip` after Setup.

## 2026-08-29 — Windows: CUDA torch must be re-applied after every uv sync

- **Context:** On Windows, `uv sync --extra semantic` installs PyPI's CPU-only `torch…+cpu`. A later `uv sync` also **uninstalls** a previously installed CUDA wheel (`+cu130`) and restores CPU torch. Agents/gates then hit `warning: no GPU found; CLIP image semantic search will use CPU` despite an RTX GPU, making heavy tests far slower.
- **Decision:** (1) Add `scripts/dev/ensure-windows-cuda-torch.ps1` + `sync-win` task/cmd that sync then reinstall torch/torchvision/torchaudio from `https://download.pytorch.org/whl/cu130`. (2) `checks-win.ps1` runs the ensure script when the `heavy` bucket is selected (skipped in GitHub Actions / `SRXY_SKIP_CUDA_TORCH=1`). (3) Document in `AGENTS.md`, `docs/development.md`, `docs/installation.md`, and `apply-worktree-srxy`.
- **Rationale:** Cannot pin CUDA torch in the lockfile for all platforms without forcing multi-GiB CUDA wheels onto CI/macOS/CPU-only machines. Post-sync ensure is the durable Windows GPU workflow.

## 2026-08-29 — Quality gate: path buckets + auto-scope + Windows parallel light steps

- **Context:** Day-to-day `checks` was slow on Windows: every pytest process imported PySide6 via pytest-qt; the "safe" pass still collected Qt/Textual `unit` files; the heavy serial pass (~123 tests / ~4:44) had no change-awareness; Windows light steps ran sequentially and pytest stdout was piped per-line through PowerShell.
- **Decision:** (1) Path-based pytest buckets (`core`/`gui`/`tui`/`heavy`) as separate processes, longest-job-first, overlapping light steps. (2) Auto-scope from `git diff`/`status` with `--scope`/`--gui`/`--tui`/`--all` overrides; `--full` ⇒ all. (3) Move Qt/Textual/real-backend tests under `tests/gui|tui|integration`; shared isolation in `tests/isolation.py` (not root conftest). (4) `-p no:pytest-qt` everywhere except `gui`; per-bucket testmon via `TESTMON_DATAFILE`; `.gate-cache` for pip-audit/build. (5) Windows: parallel light steps via `Start-Process` (not `Start-Job`), inherited pytest stdout, targeted shell-script walk, direct `.venv\Scripts` exes, wall watchdog, `checks-win.cmd` prefers `pwsh`.
- **Rationale:** Marker deselection happens after import, so only path selection removes Qt/torch cost from workers. Process-level buckets avoid the historical xdist shared-state mess while still overlapping wall clock. Auto-scope keeps the default correct rather than merely fast.
## 2026-08-29 — Ship as 1.7.0 (skip 1.6.6 patch)

- **Context:** Branch `feature/fixes_1.6.6` accumulated Fluent/Material/macOS UI work, AccentButton, preview find/highlight, installers, search streaming, and permission-denied skips — more than a patch relative to 1.6.5.
- **Decision:** Bump `project.version` and both `min_srxy_version` values to **1.7.0** instead of releasing 1.6.6. Document the full bump checklist in `docs/development.md` (**Bumping the release version**). Leave `installer_version` at `16` (installer capability stamp unchanged by this renumber alone).
- **Rationale:** Semver minor for user-visible UI/feature scope; online installers should require ≥1.7.0 once that release is on PyPI.

## 2026-08-29 — Preview RichText uses concrete monospace faces, not CSS `monospace`

- **Context:** Opening some file previews on Windows logged `DirectWrite: CreateFontFaceFromHDC() failed` for `8514oem` / `Fixedsys` (`styleHint=5` TypeWriter), then cascades of `OpenType support missing` while Qt probed Tahoma/Arial/CJK/emoji fallbacks. Preview HTML forced `font-family:monospace` while QML already set Consolas/Menlo on the `TextArea`.
- **Decision:** Emit platform-specific faces from `preview_font_family()` in preview HTML (Windows `Consolas`, macOS `Menlo`, else `monospace`), matching QML. Do not suppress `qt.qpa.fonts` / `qt.text.font.db`, and do not switch to FreeType/`nodirectwrite`.
- **Rationale:** Bare CSS `monospace` on Windows maps to legacy bitmap fonts DirectWrite cannot load; naming a real TrueType face stops that cascade. Log filtering would hide real font issues; FreeType would change global text rendering.

## 2026-08-29 — Permission denied (Error 13) → skip + warn, prune unlistable dirs

- **Context:** Searching large trees (e.g. home) could hit `PermissionError` / errno 13 on files or folders and abort the whole search instead of continuing.
- **Decision:** Treat access-denied as `SkippedFile(reason="permission_denied")`. Walker records unlistable dirs via `os.walk(onerror=…)`. Per-file search catches access-denied and, if the parent directory is not listable, marks that prefix so later paths under it are not opened. Warnings reuse the existing skipped-files ⚠ UI via `format_skipped_file_warning`. Always pass `skipped_files` from `execute_search` (including names-only) so permission skips are retained.
- **Rationale:** Matches size/OCR skip UX; avoids wasting work on known-denied subtrees without parallelizing the walk or changing QML.

## 2026-08-29 — Splash shows branding + staged status

- **Context:** Splash only showed icon + name + BusyIndicator. Author was not in `pyproject.toml` (only LICENSE). Users wanted name, author, version, and Loading / progress copy.
- **Decision:** Add `authors` to `pyproject.toml` + `AUTHOR` in `branding.py`. New `SplashBridge` QObject exposes `appName` / `author` / `version` / `status`; `run_gui` updates status between translations → services → controller → Main.qml. App window icon applied after first splash paint.
- **Rationale:** Metadata-driven author/version stay in sync with packaging; staged status reuses the existing splash window without a second UI path. Further “instant splash” options (native pixmap / pre-Qt child process) deferred — see activeContext notes.

## 2026-08-29 — GUI splash + deferred Main reveal

- **Context:** After import-graph wins, remaining cold-start cost is mostly PySide6 + large `Main.qml`. Users still see a blank gap before the main window. FluentWinUI3 stays; no widgets `QSplashScreen` (app is `QGuiApplication`).
- **Decision:** (1) Tiny `Splash.qml` `Window` with `Qt.SplashScreen` loaded first; `processEvents` so it can paint. (2) Defer `SearchController` / `build_app_services` / i18n until after splash. (3) `Main.qml` starts `visible: false`; Python `_reveal_main` shows it and closes the splash. (4) `QQuickWindow.setDefaultAlphaBuffer(False)` before any Quick window. (5) `SRXY_NO_SPLASH=1` opt-out.
- **Rationale:** Improves perceived launch without changing Fluent chrome; keeps splash out of the widget stack; tests that load Main set `visible: true` themselves.

## 2026-08-29 — AccentButton foreground uses SystemPalette, not control.palette

- **Context:** Launching the GUI logged `QML AccentButton: Binding loop detected for property "foreground"` (Search button). `AccentButton` bound `palette.buttonText: control.foreground` while `foreground` read `control.palette.placeholderText` / `control.palette.button` (disabled / non-accent paths). Any write to a palette role dirties the whole group and re-triggers those reads.
- **Decision:** Resolve disabled and non-accent face colours from a sibling `SystemPalette` (`refPalette`) that we never write to; keep writing `palette.buttonText` from `foreground` for macOS/Fusion IconLabels.
- **Rationale:** Breaks the read/write cycle on the same palette object without dropping the `buttonText` override that fixes black labels on Aqua. Existing GUI load test already asserts no binding-loop warnings.
## 2026-08-29 — GUI cold-start: application-layer boundary + deferred probe

- **Context:** GUI launch was ~1.0–1.1s to `Main.qml` (offscreen Windows), dominated by eager CLI/search imports (OCR/semantic/transcribe/cache/rapidfuzz) before first paint. FluentWinUI3 stays; SrxyLauncher is installer-only; splash deferred.
- **Decision:** (1) Shared light modules under `application/` (`search_defaults`, `skipped_file_warnings`, `search_messages`, `startup_timing`); GUI/TUI/deps_preflight no longer import `adapters.inbound.cli` for helpers. (2) CLI/`search_runner`/capability/bootstrap adapters use function-local imports for heavy outbound stacks; `cryptography.fernet` deferred inside cache encrypt/decrypt. (3) `SearchController` starts with `default_capabilities()` + `_capabilities_probing`, then `QTimer.singleShot(0, refreshCapabilities)`. (4) Opt-in `SRXY_STARTUP_TIMING=1` (+ `SRXY_STARTUP_EXIT=1` for benchmark quit after QML).
- **Rationale:** Measured wins — `cli_imported` ~0.30s → ~0.10s; `qml_loaded` ~1.06s → ~0.73–0.92s depending on env warmth. Keeps first paint free of OCR/transcribe/search_files/cryptography/rapidfuzz. Regression: `tests/unit/test_gui_startup_imports.py`. Gate: `checks-win-quiet` PASSED.

## 2026-08-29 — Stream file listing into search (overlap walk + match)

- **Context:** On large roots (e.g. home), `_execute_file_search` fully materialized `list[Path]` under “Listing files…” before any matching, so users waited with no results.
- **Decision:** Search paths as `FileWalkerPort.iter_files` yields them. Threads/processes use a bounded in-flight future set; process pool still waits until 50 paths (or walk end under 50 → sequential). When semantic image is active, encode the CLIP query before the walk. Activity is “Searching…” (no exclusive listing gate). Determinate `on_progress(completed, total)` only after the walk finishes (catch-up + remaining completions); UIs already treat unknown totals as indeterminate.
- **Rationale:** Time-to-first-result shrinks on huge trees without parallelizing `os.walk` itself; progress stays compatible with existing GUI/TUI/CLI bars; process-pool startup heuristic is preserved.

## 2026-08-29 — Search stale baseline only after successful finish

- **Context:** After Cancel, the GUI Search button dropped its accent and looked dark (Fluent secondary). Search binds `accent: controller.stale`. `_on_search_thread_finished` always set `_last_snapshot = _snapshot()`, so cancel cleared `stale` even though `_begin_search` had wiped results. Same on every platform; most visible in Windows dark mode.
- **Decision:** Commit `_last_snapshot` only when a non-cancelled `SearchFinishedEvent` set `_search_completed_ok`. On cancel/error, clear `_last_snapshot` so `stale` stays true and Search stays accented (including cancelled re-runs of an identical prior query).
- **Rationale:** Accent means “settings differ from last successful search”; a cancelled/failed run must not establish that baseline. Unit + QML regression tests cover cancel and success-then-cancel.

## 2026-08-27 — Linux Material background: flat `#ffffff` / `#303030` from colour scheme

- **Context:** Qt 6.11 Material’s default light surface is M3 tonal `#fffbfe` (pinkish white); dark is `#1c1b1f` (purple-grey). Accent was already overridden (portal / palette / Blue) but `ApplicationWindow` and Panes paint `Material.backgroundColor`, so the window still looked pink. A fixed `QT_QUICK_CONTROLS_MATERIAL_BACKGROUND=#ffffff` would lock dark mode to white (env is a single colour, not theme-aware).
- **Decision:** On Linux, after `follow_system_color_scheme`, `setdefault` `QT_QUICK_CONTROLS_MATERIAL_BACKGROUND` to `#ffffff` (light) or `#303030` (classic MD2 dark) from `QStyleHints.colorScheme` / window-palette lightness. User-set env is preserved. Shared QML stays free of Material imports.
- **Rationale:** Neutralises the pink cast on all Material surfaces (window + panes) while still following System light/dark at startup. Env is resolved once (mid-session OS theme toggles still need an app restart for the background role).

## 2026-08-27 — macOS accent labels force white; Search stretch only on Windows

- **Context:** On macOS the Search button looked misaligned (forced to TextField height ~24px while the native Aqua button is 32px), and accent OK/Search/Launch labels were black on the blue bevel. Qt's macOS `DefaultButton` IconLabel always paints `palette.buttonText` (black by default) even when `highlighted`. Our WCAG `contrast_text_on` also picked black for the system Highlight `#308cc6` (white ratio ≈3.69 < 4.5 AA). Dropping to "native-only" buttons does not fix the black label — the IconLabel still draws black over the native blue chrome.
- **Decision:** (1) `AccentButton` sets `palette.buttonText: control.foreground` so macOS/Fusion labels follow `onAccent`. (2) `SrxyTheme` on darwin always uses white `onAccent` (Aqua convention), bypassing WCAG for that platform. (3) Search-button stretch-to-field / forced padding / `AlignTop` is gated to Windows via `Binding { when }` + `restoreMode`; macOS/Linux keep native size and `AlignVCenter`.
- **Rationale:** Matches Aqua default-button look (white on blue) without custom chrome; Windows Fluent stretch-to-field look is preserved. Regression: platform-aware layout test, OK-button `palette.buttonText == onAccent`, darwin `onAccent` unit test. Gate passed.

## 2026-08-20 — `ResultsModel` mutates rows, never full-resets

- **Context:** Searches logged `DelegateModel::cancel: index out range 6 0` / `10 1`. `ResultsModel.clear()` and `replace_results()` did a full `beginResetModel()`/`endResetModel()`, invalidating rows while the `resultsView` ListView's async `currentIndex` binding and in-flight (async-incubated) delegates were stale. `QQmlDelegateModel::cancel(index)` was then asked to cancel a delegate at a row index beyond the delegate compositor's count. `_clear_selection()` (Python-side) cannot synchronously drive the QML `currentIndex` binding, so it did not silence the warning.
- **Decision:** Rewrote `ResultsModel.clear()` to use `beginRemoveRows(_EMPTY_INDEX, 0, N-1)`/`endRemoveRows()` (skipped when empty) and `replace_results()` to emit a remove-all + insert-all pair, never `modelReset`. `MatchesModel` full resets were left unchanged (no async `currentIndex` binding on that view).
- **Rationale:** Row-level mutations let the QML delegate model cancel in-flight incubations with valid indices, avoiding the stale-index warning. The change preserves the row contract (order, limit) exactly. Added `tests/unit/test_gui_models.py` (deterministic signal assertions: `rowsRemoved`/`rowsInserted`, never `modelReset`, incl. empty-model no-op cases) and a GUI regression test in `test_gui_qml_load.py` (two search cycles through loaded QML; asserts no `DelegateModel`/`index out range` message). Unit tests were verified to fail against the old full-reset code. Fallback options (QML `modelAboutToBeReset` → `currentIndex = -1`, deferred reset) were not needed.

## 2026-08-19 — Taskipy gate tasks: non-quiet by default, dedicated `*-quiet` variants

- **Context:** The first iteration made the day-to-day Taskipy tasks (`checks`/`checks-fix`/`checks-win`/`checks-win-fix`) default to `--quiet`. The user preferred humans keep the verbose default and agents opt into quiet explicitly.
- **Decision:** Reverted `checks`/`checks-fix`/`checks-win`/`checks-win-fix` to plain (verbose) commands. Added explicit `*-quiet` variants for every gate mode on both platforms: `checks-quiet`, `checks-fix-quiet`, `checks-full-quiet`, `checks-full-cpu-quiet`, `checks-win-quiet`, `checks-win-fix-quiet`, `checks-win-full-quiet`, `checks-win-full-cpu-quiet`. `AGENTS.md` instructs AI agents to always use the quiet variants (direct `--quiet`/`-Quiet` flags or `*-quiet` tasks); the release line points agents at `checks-full-quiet` / `checks-full-cpu-quiet`.
- **Rationale:** Keeps the human-facing day-to-day commands unchanged (no silent behavior change) while giving agents an explicit, discoverable low-token path. Verified with `uv run task checks` (verbose, PASSED) and `uv run task checks-quiet` (quiet, PASSED).

## 2026-08-19 — Agent-verbosity `--quiet` flag for the quality gate

- **Context:** AI agents running `checks.sh` consume tens of thousands of tokens just reading the gate's stdout: pytest's `-v` addopts print one line per test (~880+ tests), and the serial heavy pass (semantic/transcribe/gui/tui/integration/ocr) reruns everything every time, streaming model/progress noise. The gate must keep streaming live output (the stall watchdog depends on it), so truncation (`tail`) was ruled out.
- **Decision:** Add opt-in `--quiet` (`checks.sh`) / `-Quiet` (`checks-win.ps1`) that exports `LIB_GATE_QUIET=true`. Pytest runs with `-q --no-header -ra --tb=short -p agent_progress` (sparse `[gate] N/total (ok=.. fail=..)` lines from the new `scripts/quality/internal/agent_progress.py` plugin; totals use nodeid sets because xdist workers each report the full collection). The heavy pass additionally gets `LIB_PYTEST_PROGRESS_INTERVAL=1` and `HF_HUB_DISABLE_PROGRESS_BARS=1`/`TRANSFORMERS_VERBOSITY=error`/`TOKENIZERS_PARALLELISM=false`/`TQDM_DISABLE=1`. On the parallel-verify path, passing light-step logs are no longer replayed (`gate_finish_step` loads the status first and cats the log only on failure or non-quiet). Taskipy task naming was later revised — see the "Taskipy gate tasks: non-quiet by default, dedicated `*-quiet` variants" entry above. `-p no:cacheprovider` was dropped because disabling the cacheprovider also removes pytest's `--ff` (fail-first) option, which the local gate passes.
- **Rationale:** Keeps the human-facing verbose default while slashing agent token cost; failures still show full short tracebacks + `-ra` summary; progress lines keep the stall watchdog satisfied during slow heavy tests. Verified with `uv run task checks` and `uv run task checks-fix` (both PASSED, 122 heavy tests).

## 2026-08-19 — AccentButton is native-first (highlighted via `defaultButton`), no custom background

- **Context:** `AccentButton` replaced the native button `background`/`contentItem` with a plain `Rectangle`+`Text`, losing Material ripple/elevation, Fluent hover/press states, per-style corner radius, and per-style size (hardcoded 80x32, faked pressed state via `opacity: 0.85`). The prior "explicit `accent` bool + custom fill" workaround existed because `DialogButtonBox` appeared to clobber `highlighted`.
- **Decision:** `AccentButton` is now a plain `Button` with `highlighted: control.accent` and no custom `background`/`contentItem`, so every style renders its native chrome and its own accent. Reading the Qt 6.11 source confirmed `QQuickDialogButtonBoxPrivate::updateLayout()` calls `setHighlighted(button == defaultButton)` on every child each layout pass — so a QML `highlighted` binding is unreliable inside a box, and `buttonRole: AcceptRole` alone does NOT highlight. The fix is `DialogButtonBox.defaultButton` on the primary dialog button (`optionsOkButton`, `filtersOkButton`, `updateYesButton`), which is what actually keeps it highlighted. FluentWinUI3 paints its highlighted fill from `palette.accent` (not `palette.button`/a custom background), so `qt_theme._apply_button_accent_palette` pins `QPalette.Accent` to the resolved button accent.
- **Rationale:** `highlighted` is the native accent on every style in play (Material `Material.accent`, Universal `Universal.accent`, Fluent `palette.accent`, Fusion `palette.highlight`, macOS/Windows native default button), so a custom background is unnecessary and harmful. `foreground` is retained only for the Search button's custom icon+text `contentItem`. Supersedes the 2026-08-18 "`accent` bool, not `highlighted`" entry below.

## 2026-08-19 — Set Qt app identity before QGuiApplication construction (host portal registration)

- **Context:** On Linux the GUI logged `qt.qpa.services: Failed to register with host portal QDBusError("org.freedesktop.portal.Error.Failed", "Could not register app ID: Connection already associated with an application ID")` at startup. Qt 6.10+/6.11 `QDesktopUnixServices` registers the app with the xdg-desktop-portal host-app registry (`org.freedesktop.host.portal.Registry.Register`) using `QGuiApplication::desktopFileName()`; the portal requires `Register` to run before any other portal call, and only once. Because identity was set *after* `QGuiApplication` was constructed, `desktopFileName()` was empty at init so Qt deferred registration to a queued callback; by then `follow_system_color_scheme()` (inside `apply_qt_quick_theme`) had already made a portal colour-scheme read, so the connection was already associated and `Register` failed.
- **Decision:** Add `apply_app_identity(name)` to `app_icon.py` that sets `QGuiApplication.setApplicationName(name)`, `QGuiApplication.setOrganizationName("srxy")`, and `apply_desktop_file_name(name)` via the **static** setters, and call it in `gui/app.py` (`run_gui`) and `installer/app.py` (`run_installer`) **before** `QGuiApplication` is constructed. `apply_desktop_file_name` becomes static-only (`name` arg, no app instance).
- **Rationale:** Qt reads these at init time and registers with the portal immediately, before any other portal method call, so the `Connection already associated` warning disappears. The `.desktop`-file guard (`desktop_file_available`) is preserved so `uv run`/PyPI runs without a desktop entry still skip registration gracefully.

## 2026-08-19 — Native file/folder dialogs on Linux via xdgdesktopportal platform theme

- **Context:** The GUI/installer "Browse" button uses Qt Quick's `FolderDialog`. On macOS and Windows that dialog is native, but on Linux Qt only renders a native dialog when the platform theme provides one — the KDE/GNOME themes Qt auto-selects do not, so the "Browse" button showed the Qt Quick (non-native) fallback instead of KDE's native folder picker.
- **Decision:** Add `prefer_native_file_dialogs()` in `qt_theme.py` that sets `QT_QPA_PLATFORMTHEME=xdgdesktopportal` (via `os.environ.setdefault`, Linux only), and call it in `gui/app.py` / `installer/app.py` **before** `QGuiApplication` is constructed. The `xdgdesktopportal` platform theme is bundled with PySide6 and serves file dialogs through `org.freedesktop.portal.FileChooser`, which opens the desktop's native picker.
- **Rationale:** Standard freedesktop route, no new dependencies, no bundled binaries; a user-set `QT_QPA_PLATFORMTHEME` is preserved. macOS/Windows are untouched (their dialogs are already native). Fails gracefully to the non-native dialog if the portal is unavailable.

## 2026-08-18 — AccentButton uses an `accent` bool, not `highlighted`

- **Context:** In dark mode the Search Options / Filters OK buttons (and update "Yes") rendered dark instead of accent-filled. `AccentButton` chose accent vs. secondary fill by reading the standard `highlighted` property, but `DialogButtonBox` (FluentWinUI3, and Material/Fusion/Universal alike) forcibly overrides `highlighted` on its child buttons from its own delegate, so the `highlighted: true` set inside `AccentButton` was silently dropped and `fillColor`/`foreground` fell back to `palette.button` (5.8%-alpha white in Fluent dark mode). `buttonRole: AcceptRole` and overriding `DialogButtonBox.delegate` did not restore it.
- **Decision:** Give `AccentButton` its own `property bool accent: true` and drive `fillColor`/`foreground` off that; the Search button's dynamic stale toggle now binds `accent` instead of `highlighted`.
- **Rationale:** `highlighted` is a container-managed property (`Container`/`DialogButtonBox` re-assign it), so it cannot be trusted to express "is the primary CTA". A dedicated `accent` flag is unambiguous and immune to `DialogButtonBox`. Added `optionsOkButton`/`filtersOkButton` objectNames plus a regression test asserting the OK buttons render `fillColor == accent` / `foreground == onAccent`.

## 2026-08-18 — Track the memory bank in git (reverses gitignore decision)

- **Context:** The earlier entry gitignored `memory/` to keep agent scratch out of the repo. But worktrees don't share ignored files: each new `git worktree add` got zero context and memory fragmented across worktrees.
- **Decision:** Track `memory/` in git as per-branch state. `decisions.md` stays append-only (never cleaned); `progress.md` and `activeContext.md` are reset at branch start. `memory/decisions.md` gets `merge=union` in `.gitattributes`.
- **Rationale:** Per-branch tracked memory follows the branch automatically in worktrees and new clones; the clean-at-start ritual keeps `progress.md`/`activeContext.md` relevant. Add `.cursor/rules/agent-memory.mdc` section 4 + human-oriented `memory/README.md`.

## 2026-08-18 — QML teardown order: destroy windows before the engine

- **Context:** GUI and installer exit logged `There are still "1" items in the process of being created at engine destruction.`. `QQmlEnginePrivate::~QQmlEnginePrivate` warns when `inProgressCreations > 0`; at interpreter shutdown the `QQmlApplicationEngine` was destroyed while its `QQuickWindow` (and its async `QQmlDelegateModel`/`Loader` incubators) were still alive.
- **Decision:** After `app.exec()` returns, destroy root windows first (`root.deleteLater()`), then `engine.deleteLater()`, then flush `QEvent.Type.DeferredDelete` with `sendPostedEvents` + `processEvents()` — in both `gui/app.py` and `installer/app.py`.
- **Rationale:** Deleting the window cascades into the delegate model/loader, whose incubator destructors `clear()` and decrement `inProgressCreations` before the engine destructor runs, so the warning is avoided. This is the standard Qt teardown order; deleting the engine first leaves stale PySide wrappers (verified `RuntimeError` in a repro) and the pending-incubator warning.

## 2026-08-18 — Preview syntax highlighting applies to all file sizes

- **Context:** File-content preview fell back to unhighlighted "plain" rendering once content exceeded `_PLAIN_PREVIEW_BYTES` (16 KB) or 500 lines. An 18 KB Python file (`caffe2/.../dataio_test.py`) lost keyword coloring while a 4 KB sibling (`coverage.py`) kept it, which looked like a bug.
- **Decision:** Remove the 16 KB / 500-line plain fallback entirely; always run the lightweight per-line tokenizer since preview payloads are already capped at `PREVIEW_MAX_BYTES` (64 KB) / `PREVIEW_MAX_LINES` (2000).
- **Rationale:** The tokenizer takes ~0.03 s for a max-size (50 KB / 2000-line) preview and emits ~280 KB of HTML, which QML RichText handles fine; the 16 KB cutoff was arbitrary and produced inconsistent highlighting.

## 2026-08-18 — AccentButton text: prefer white when it clears AA 4.5:1

- **Context:** Options dialog OK button (shared `AccentButton`) rendered black text on Windows, unlike Cancel. `contrast_text_on` picked the strictly higher-contrast colour, and for the Windows accent `#0078d4` black wins by a hair (4.637 vs 4.529), producing illegible-looking black-on-blue text.
- **Decision:** Prefer white text on dark/saturated fills whenever white still clears the WCAG AA 4.5:1 threshold, then fall back to the higher-contrast colour.
- **Rationale:** White-on-colour is the CTA convention; the pure max-contrast rule regressed mid-tone accents. Keeps light accents (`#3daee9`, `#90caf9`, `#ffeb3b`) black and dark accents (`#1565c0`) white. Added a regression test for `#0078d4` → white.

## 2026-08-18 — Preview highlighting/find/context menus (merged to `feature/fixes_1.6.6`)

- **Context:** File-content preview used hardcoded hex syntax colours (not theme-aware), had no in-preview find, and no copy/open/folder actions.
- **Decision:** Keep the in-house HTML highlighter but drive colours from a `PreviewPalette` with light/dark variants; add a Ctrl+F find bar that renders match spans as HTML overlays on top of the existing preview; add a right-click menu (copy/select-all/find/open file/open folder) plus "Open containing folder" on the results list; extend `DesktopPort` with `reveal_path` (os/gui/tui adapters); expose match line numbers via `LineNumberRole` to jump the preview on click.
- **Rationale:** No Pygments/tree-sitter dependency; reuses the existing line-oriented matching; theme-awareness follows the OS light/dark already handled in `qt_theme.py`.

## 2026-08-18 — Adopt a gitignored agent memory bank

- **Context:** Needed persistent cross-session context for an agent working across the v1.6.6 branch.
- **Decision:** Add `memory/` (gitignored) with `activeContext.md`, `progress.md`, `decisions.md`, plus an always-on rule at `.cursor/rules/agent-memory.mdc`.
- **Rationale:** Keeps agent scratch memory out of the repo while `docs/` stays the canonical committed reference.

## Windows GUI style → FluentWinUI3

- **Context:** Plain `Windows` Quick style looked dated and mixed poorly with dark mode.
- **Decision:** Use FluentWinUI3 on Windows, fallback Universal → Windows; follow OS light/dark. Results-pane `SplitView` falls back to Fusion until Fluent styles that control.
- **Rationale:** Native WinUI-like appearance with a safe fallback chain; documented hard-won pitfalls in `AGENTS.md`.

## Primary CTAs → shared `AccentButton`

- **Context:** Primary actions were `Button { highlighted: true }` with hand-picked label colours.
- **Decision:** Use shared `AccentButton` from the `SrxyControls` module, painting the system accent fill and WCAG black/white `foreground` from `srxyTheme`.
- **Rationale:** Consistent, accessible primary CTAs across GUI and installer.

## Qt theme selection lives in Python, not shared QML

- **Context:** Style imports in shared QML forced a single chrome and broke native macOS controls.
- **Decision:** Keep platform style choice in `src/srxy/adapters/inbound/gui/qt_theme.py` (`apply_qt_quick_theme`); never `import QtQuick.Controls.<Style>` in shared QML.
- **Rationale:** macOS needs native Aqua; Linux uses Material (Dense); Windows uses FluentWinUI3. Platform-specific attached properties belong only in platform-private QML, or avoided.

## Windows tessdata language packs → opt-in download

- **Context:** Windows OCR language data for the installer.
- **Decision:** Ship language packs as opt-in downloads from pinned upstream HTTPS sources; no bundled third-party runtime binaries.
- **Rationale:** Third-party binary policy (`AGENTS.md`) — keep tesseract/ffmpeg/CUDA etc. out of installer artifacts, the repo, and Releases.
