# Windows offline installer

Fat self-extracting PySide6/QML wizard — same installer UI as the macOS offline
`.app` and Linux offline AppImage (`srxy.adapters.inbound.installer.app.run_installer`)
around the shared headless engine.

| Artifact | Build | Smoke |
|----------|-------|-------|
| `dist/srxy-<version>-installer-<installer_version>-x86_64.zip` | [`build-offline.ps1`](build-offline.ps1) | [`smoke-offline.ps1`](smoke-offline.ps1) |

Unzipping yields a single `SrxyInstaller.exe` that embeds `python\` + `venv\` + `share\`
and extracts them on first launch.

## Prerequisites

- Windows x64
- [uv](https://docs.astral.sh/uv/)
- `csc.exe` (.NET Framework 4.x developer tools — also used to build the app launcher/icon)

## Build

```powershell
# from repo root
.\packaging\windows\build-offline.ps1
# or: uv run task build-windows-installer-offline
.\packaging\windows\smoke-offline.ps1
# or: uv run task smoke-windows-installer-offline
# optional: .\packaging\windows\smoke-offline.ps1 -InstallerExe .\dist\windows-pyside-installer-stage\SrxyInstaller.exe
```

Optional: `-OutDir dist`, `-PythonVersion 3.12`.

After unzipping the distribution zip:

```
SrxyInstaller.exe    fat SFX: embedded zip of python\ + venv\ + share\ + SRXYISFX trailer
```

On first launch the stub extracts under `%LOCALAPPDATA%\srxy\is\<sha16>\p\`
(cached for later runs), sets `SRXY_INSTALLER_PAYLOAD`, and execs
`venv\Scripts\pythonw.exe -m srxy.adapters.inbound.installer`. The embedded tree is:

```
python\             relocatable managed CPython 3.12 (base interpreter for venv\)
venv\                wizard-only venv: PySide6 + srxy --no-deps (pruned, no full search stack)
share\srxy\          srxy.whl / srxy-<version>-*.whl (full wheel for prefix installs)
share\srxy\installer_meta.toml
share\srxy\windows\  prebuilt Srxy.exe (app launcher) + srxy.ico, reused at prefix-install time
```

Default prefix: `%LOCALAPPDATA%\Programs\srxy` (per-user, no admin). Start Menu /
desktop shortcuts target `bin\Srxy.exe`; `bin\srxy.cmd` remains for PATH/CLI.

Payload resolution uses the shared contract
(`SRXY_INSTALLER_PAYLOAD` → `payload/share/srxy/...`; see
`srxy.adapters.inbound.installer.package_spec.resolve_bundled_or_local_spec` and
`srxy.adapters.inbound.installer.meta.load_installer_meta`).

Optional components (Tesseract, ffmpeg, semantic, models) are **not** embedded — the
headless engine downloads them after privacy acknowledgment (same policy as
Linux/macOS offline installers).

Build steps: install managed CPython, create a `--relocatable --link-mode copy` venv,
install `PySide6>=6.6` then `srxy --no-deps`, verify the venv still imports after a
copy to an unrelated path, prune unused Qt
([`prune-pyside.ps1`](prune-pyside.ps1) — Windows PySide6 layout: `Qt6*.dll` under
`site-packages\PySide6\`, no nested `Qt\lib\`), compile the SFX stub, append
`payload-embed.zip` + trailer.

Setup types in the wizard: **Recommended (GPU)** (Tesseract + ffmpeg + semantic),
**Recommended (no GPU)** (Tesseract + ffmpeg), **Simple** (app only), **Complete**
(also prefetches AI models), **Custom**. NVIDIA detection via `nvidia-smi` (override
with `SRXY_FORCE_GPU` / `SRXY_FORCE_NO_GPU`). When semantic is selected and an NVIDIA
GPU is present, the engine reinstalls CUDA PyTorch (`cu130`, fallback `cu126`) into
the prefix `.venv`.

Signing / SmartScreen: unsigned builds may warn; Authenticode is a follow-up.
Online Windows installer is out of scope for this packaging tree.

CI: [`windows-installer.yml`](../../.github/workflows/windows-installer.yml) builds,
smokes, and on tags attaches the zip to GitHub Releases.

## Engine progress protocol

The headless CLI (`python -m srxy.adapters.inbound.installer`) prints tab-separated
lines for progress UIs / scripts:

| Line | Meaning |
|------|---------|
| `STATUS\t<message>` | Current phase text |
| `TASK\t<index>\t<total>\t<label>` | Install phase N of M |
| `PROGRESS\t<done>\t<total>\t<label>` | Byte progress for a download (`total>1`), or `1\t1` when a phase finishes |
| `OK\tinstall\|reinstall\|uninstall` | Success |
| `ERROR\t<message>` | Failure (non-zero exit) |
