# Windows offline installer (Inno Setup)

Builds `dist/srxy-<version>-installer-<installer_version>-x86_64.exe` locally, plus a
max-compressed `*.exe.zip` sibling. CI/release artifacts publish the **zip** (and
checksums), not the bare exe.

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

## Engine progress protocol

The headless CLI (`python -m srxy.adapters.inbound.installer`) prints tab-separated lines for the Inno wizard:

| Line | Meaning |
|------|---------|
| `STATUS\t<message>` | Current phase text |
| `TASK\t<index>\t<total>\t<label>` | Install phase N of M |
| `PROGRESS\t<done>\t<total>\t<label>` | Byte progress for a download (`total>1`), or `1\t1` when a phase finishes |
| `OK\tinstall\|reinstall\|uninstall` | Success |
| `ERROR\t<message>` | Failure (non-zero exit) |
