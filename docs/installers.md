# Desktop installers

Optional desktop installers for people who prefer a wizard over `uv tool install` / PyPI. Linux AppImages, macOS installer wrappers, and a Windows offline Inno Setup installer are available.

Download free builds from [GitHub Releases](https://github.com/illescasDaniel/srxy/releases/latest), or [buy the installers](https://www.daniel-ir.eu/shop/p/srxy) from the official site (includes a **signed** macOS build). PyPI / `uv tool install` remain the primary install paths on every platform. Privacy / third-party downloads: [privacy.md](privacy.md).

## Linux (supported)

Two separate AppImages (do not mix them up):

| Artifact name pattern | Role |
|-----------------------|------|
| `srxy-*-installer-<installer_version>-x86_64.AppImage.xz` | **Offline wizard** — full PySide UI; install / update / reinstall / uninstall |
| `srxy-*-installer-online-<installer_version>-x86_64.AppImage.xz` | **Online one-click** — slim Go bootstrap + localhost browser page; install from PyPI |

Download from [GitHub Releases](https://github.com/illescasDaniel/srxy/releases/latest), decompress (`xz -d …`), make executable, and run (type2 static runtime — no host `libfuse2`). Default prefix: `~/Applications/srxy`.

### Offline wizard

- Choose **Install or update**, **Reinstall**, or **Uninstall**.
- Acknowledge the privacy notice, then optionally vendor Tesseract / ffmpeg / semantic extras and prefetch models. When Tesseract is selected, the next page is languages for text in images (English + orientation detection always included; OS preferred languages pre-selected) — same idea as the Windows offline installer.
- Optional PATH block in your shell rc (`# >>> srxy PATH >>>`).

### Online one-click

- Opens your default browser to a preparing page, then the install UI on `127.0.0.1` only.
- First launch may download pinned `uv`, managed Python, and the srxy installer package into `~/.cache/srxy/online-bootstrap/` (needs network).
- Always vendors uv / tesseract / ffmpeg and adds PATH; smarter-search packages only when a GPU/MPS is detected. Model weights are **not** prefetched. OCR languages are chosen automatically: English + orientation detection + every mapped browser/system language.
- No reinstall/uninstall UI — use the offline wizard or remove the prefix manually. Closing the browser tab stops the process.

<img src="images/installer-online.png" alt="srxy online web installer" width="400" />

Regenerate README / docs screenshots: `./scripts/docs/export_installer_screenshot.sh` (offline wizard) and `./scripts/docs/export_installer_online_screenshot.sh` (online UI).

Step-by-step install notes: [installation.md § Linux AppImage installers](installation.md#linux-appimage-installers-optional).

## macOS (supported)

Two macOS DMG installers (same naming shape as Linux AppImages):

| Artifact name pattern | Role |
|-----------------------|------|
| `srxy-*-installer-<installer_version>-<arch>.dmg` | **Offline wizard** — PySide UI in `Srxy <ver> - Installer <n>.app` inside the DMG |
| `srxy-*-installer-online-<installer_version>-<arch>.dmg` | **Online one-click** — Go bootstrap `Srxy <ver> - Installer Online <n>.app` + localhost browser UI |

1. Download the `.dmg` from [GitHub Releases](https://github.com/illescasDaniel/srxy/releases/latest).
2. Open the DMG and double-click the installer (the volume background reminds you).
3. Both installers target `~/Applications/srxy` by default.

GitHub Release DMGs are currently **unsigned** (Gatekeeper may warn or block on first open). A **signed** macOS installer is available from the [official shop](https://www.daniel-ir.eu/shop/p/srxy).

Notes:

- The online macOS wrapper installs srxy from PyPI and adds PATH in your shell rc.
- On Apple Silicon and Intel Macs, optional installer toggles can vendor ffmpeg (martin-riedl static build, latest release resolved at install time) and tesseract (Homebrew core bottles from `ghcr.io`, digests resolved at install time and relocated; Homebrew itself is not required).
- No admin rights are required for the default `~/Applications` prefix.
- First **Launch** after install can take several seconds while Qt libraries load cold; later opens from Finder are normal.

## Windows (supported)

Offline Inno Setup installer (x86_64):

| Artifact name pattern | Role |
|-----------------------|------|
| `srxy-*-installer-<installer_version>-x86_64.exe.zip` | **Offline wizard** — native Inno UI (zip of the setup `.exe`); headless Python engine; install / update / reinstall / uninstall |

Download from [GitHub Releases](https://github.com/illescasDaniel/srxy/releases/latest) and run. Default prefix: `%LOCALAPPDATA%\Programs\srxy` (per-user; no admin required).

### Offline wizard

- Choose **Install or update**, **Reinstall**, or **Uninstall**.
- Acknowledge the privacy notice, then pick a setup type:
  - **Recommended (GPU)** — Tesseract, ffmpeg, and smarter-search packages (no model prefetch)
  - **Recommended (no GPU)** — Tesseract and ffmpeg only
  - **Simple** — app only (not recommended)
  - **Complete** — recommended GPU set plus AI model download
  - **Custom** — pick components yourself
- The wizard probes for an NVIDIA GPU (`nvidia-smi`) and pre-selects the matching recommended type.
- Optional **Add to PATH** (user `PATH` via the registry).
- Start Menu shortcut is created; desktop shortcut is optional.
- Builds are currently **unsigned** (SmartScreen may warn on first run).

Until you prefer the wizard, [Installation](installation.md) (`uv tool install` / pipx) remains supported on Windows.

Packaging details: [`packaging/windows/README.md`](../packaging/windows/README.md).

## Build from source

| Artifact | Build | Smoke |
|----------|-------|-------|
| Offline | `./packaging/linux-appimage/build.sh` | `./packaging/linux-appimage/smoke-appimage.sh` |
| Online | `./packaging/linux-appimage/build-online.sh` | `./packaging/linux-appimage/smoke-appimage-online.sh` |
| macOS Offline | `./packaging/macos/build-offline.sh` | `./packaging/macos/smoke-offline.sh` |
| macOS Online | `./packaging/macos/build-online.sh` | `./packaging/macos/smoke-online.sh` |
| Windows Offline | `./packaging/windows/build-offline.ps1` | `./packaging/windows/smoke-offline.ps1` |

Packaging details (AppDir layout, UPX, checksums, CI): [`packaging/linux-appimage/README.md`](../packaging/linux-appimage/README.md). Bootstrap sources: [`packaging/online-bootstrap/`](../packaging/online-bootstrap/). Compatibility pins: [`packaging/installer_meta.toml`](../packaging/installer_meta.toml).

```bash
uv run python -m srxy.adapters.inbound.installer          # offline wizard (dev)
uv run python -m srxy.adapters.inbound.installer_online   # online UI without AppImage
```
