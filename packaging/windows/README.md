# Windows offline installers

Two offline artifacts, built independently (neither overwrites the other):

| Artifact | Build | Smoke | UI |
|----------|-------|-------|----|
| `dist/srxy-<version>-installer-<installer_version>-x86_64.exe(.zip)` | [`build-offline.ps1`](build-offline.ps1) | [`smoke-offline.ps1`](smoke-offline.ps1) | **Inno Setup** native wizard (headless Python engine underneath) |
| `dist/srxy-<version>-installer-<installer_version>-pyside-x86_64.zip` | [`build-offline-pyside.ps1`](build-offline-pyside.ps1) | [`smoke-offline-pyside.ps1`](smoke-offline-pyside.ps1) | **PySide6** full wizard — same QML wizard as the macOS `.app` / Linux AppImage offline installers |

The Inno path remains the primary/shipped Windows installer for now (see [Windows installer migration](../../memory/activeContext.md)). The PySide wrapper is an additional, parity-focused build for eventual use as the payload behind an NSIS-based single-file installer (a separate follow-up — **not** implemented here); today it ships as a zip of a portable payload folder (extract, run `SrxyInstaller.exe`).

## Inno Setup wizard

| Piece | Role |
|-------|------|
| [`srxy-offline.iss`](srxy-offline.iss) | Inno Setup wizard (mode, privacy, components, PATH, ARP) |
| [`build-offline.ps1`](build-offline.ps1) | Stage bootstrap + wheel, compile with ISCC, zip artifact |
| [`smoke-offline.ps1`](smoke-offline.ps1) | Headless CLI smoke, or silent run of a built `.exe` |

## Prerequisites

- Windows x64
- [uv](https://docs.astral.sh/uv/)
- [Inno Setup 7](https://jrsoftware.org/isdl.php) preferred (6.2+ also works for `ExecAndLogOutput`). `ISCC.exe` on `PATH` or under Program Files.

## Build

```powershell
# from repo root
.\packaging\windows\build-offline.ps1
# or: uv run task build-windows-installer-offline
```

Optional: `-IsccPath 'C:\Path\To\ISCC.exe'`, `-OutDir dist`, `-PythonVersion 3.12`.

The payload under `dist/windows-installer-stage/payload/` contains:

- `python/` — relocatable CPython with the installer package in `Lib\site-packages` (`--no-deps`, no PySide)
- `share/srxy/*.whl` — full wheel for the prefix install (includes GUI deps when installed into the target venv)

Optional components (Tesseract, ffmpeg, semantic, models) are **not** embedded; the headless engine downloads them after privacy acknowledgment (same policy as Linux/macOS offline installers).

## Smoke

```powershell
# Headless engine only (uses the checkout via uv run)
.\packaging\windows\smoke-offline.ps1

# Built installer (silent, core components only)
.\packaging\windows\smoke-offline.ps1 -InstallerExe .\dist\srxy-*-installer-*-x86_64.exe
```

## Notes

- Default prefix: `%LOCALAPPDATA%\Programs\srxy` (per-user, no admin).
- Start Menu / desktop shortcuts target `bin\Srxy.exe` (icon embedded); `bin\srxy.cmd` remains for PATH/CLI.
- Privacy pages ship English and Spanish UTF-8 notices (BOM) and follow the installer language choice.
- Custom wizard pages, components, and tasks use Inno `[CustomMessages]` so Spanish/English stay consistent with the built-in chrome.
- Setup types: **Recommended (GPU)** (Tesseract + ffmpeg + semantic), **Recommended (no GPU)** (Tesseract + ffmpeg), **Simple** (app only), **Complete** (also prefetches AI models), **Custom**. The wizard detects NVIDIA GPUs via `nvidia-smi` (including `{sysnative}` so 32-bit Setup can see it under WOW64) and pre-selects the matching recommended type (override with env `SRXY_FORCE_GPU` / `SRXY_FORCE_NO_GPU`). When semantic is selected and an NVIDIA GPU is present, the install engine reinstalls CUDA PyTorch (`cu130`, fallback `cu126`) into the prefix `.venv` after the semantic package (PyPI ships CPU-only torch on Windows). Inno Setup 7 builds a **64-bit** Setup (`SetupArchitecture=x64`). Silent installs default to the CPU recommended type unless you pass `/TYPE=recommendedgpu` (or another type).
- Interactive installs stream the headless engine’s stdout into the progress page via Inno `ExecAndLogOutput` (`STATUS` / `PROGRESS` / `TASK` lines) and tee the same lines to `{app}\logs\installer-engine.log`. Requires Inno Setup 6.2+ (CI uses 7.0.2).
- Windows Tesseract is downloaded as the UB-Mannheim NSIS setup, then **extracted** with a pinned 7-Zip helper (no UAC / no running the setup EXE).
- Signing / SmartScreen: unsigned builds may warn (same class of issue as unsigned macOS DMGs). Authenticode is a follow-up.
- Online Windows installer is out of scope for this packaging tree.

## PySide wizard (offline)

Builds `dist/srxy-<version>-installer-<installer_version>-pyside-x86_64.zip`, a zipped
portable payload folder — parity with the macOS offline `.app` and Linux offline
AppImage, which both wrap the same PySide6/QML wizard
(`srxy.adapters.inbound.installer.app.run_installer`) around the same headless engine.

```powershell
.\packaging\windows\build-offline-pyside.ps1
# or: uv run task build-windows-installer-offline-pyside
.\packaging\windows\smoke-offline-pyside.ps1
# or: uv run task smoke-windows-installer-offline-pyside
```

Prerequisites: `uv`, and `csc.exe` (.NET Framework 4.x developer tools — same requirement
`build-offline.ps1` already has for the app launcher/icon build).

Extracted, the zip contains:

```
python\             relocatable managed CPython 3.12 (base interpreter for venv\)
venv\                wizard-only venv: PySide6 + srxy --no-deps (pruned, no full search stack)
share\srxy\          srxy.whl / srxy-<version>-*.whl (full wheel for prefix installs)
share\srxy\installer_meta.toml
share\srxy\windows\  prebuilt Srxy.exe (app launcher) + srxy.ico, reused at prefix-install time
SrxyInstaller.exe    launcher: sets SRXY_INSTALLER_PAYLOAD, execs venv\Scripts\pythonw.exe -m srxy.adapters.inbound.installer
```

Same payload-resolution contract the Inno bootstrap already uses
(`SRXY_INSTALLER_PAYLOAD` → `payload/share/srxy/...`; see
`srxy.adapters.inbound.installer.package_spec.resolve_bundled_or_local_spec` and
`srxy.adapters.inbound.installer.meta.load_installer_meta`), so the shared engine finds
the bundled wheel, `installer_meta.toml`, and prebuilt app launcher without any
Windows-specific engine changes.

Optional components (Tesseract, ffmpeg, semantic, models) are **not** embedded — same
policy as every other offline installer; the headless engine downloads them after
privacy acknowledgment.

Build steps mirror macOS/Linux offline builds: install a managed CPython, create a
`--relocatable --link-mode copy` venv, install `PySide6>=6.6` then `srxy --no-deps`,
verify the venv still imports after being copied to an unrelated path (the same
relocation-bug class those builds guard against), then prune unused Qt payload
([`prune-pyside.ps1`](prune-pyside.ps1) — Windows PySide6 wheel layout: `Qt6*.dll`
sit directly under `site-packages\PySide6\`, not a nested `Qt\lib\` like macOS/Linux;
`qml\` / `plugins\` / `translations\` / `metatypes\` have no `Qt\` prefix either).

CI job: `build-offline-pyside` in
[`.github/workflows/windows-installer.yml`](../../.github/workflows/windows-installer.yml)
(uploads the zip as a build artifact on every PR/push; not yet attached to GitHub
Releases — that follows once the NSIS single-file wrapper lands).

**What still needs a real Windows host to verify:** the actual `.ps1` execution
(managed Python/`uv venv`/`csc.exe` toolchain, PySide6 DLL loading, on-screen wizard
rendering, FluentWinUI3 theming). This repo's cloud agent environment cannot run
PowerShell/Windows builds, so verification here is limited to: script-content contract
tests (`tests/unit/test_windows_pyside_packaging.py`), reuse of the already-tested
cross-platform install engine (`install.py`, `path_setup.py`, `controller.py`, shared
QML wizard), and the CI job above running on `windows-latest`.

## Engine progress protocol

The headless CLI (`python -m srxy.adapters.inbound.installer`) prints tab-separated lines for the Inno wizard:

| Line | Meaning |
|------|---------|
| `STATUS\t<message>` | Current phase text |
| `TASK\t<index>\t<total>\t<label>` | Install phase N of M |
| `PROGRESS\t<done>\t<total>\t<label>` | Byte progress for a download (`total>1`), or `1\t1` when a phase finishes |
| `OK\tinstall\|reinstall\|uninstall` | Success |
| `ERROR\t<message>` | Failure (non-zero exit) |
