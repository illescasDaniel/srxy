# Desktop installers

Optional desktop installers for people who prefer a wizard over `uv tool install` / PyPI. Linux AppImages and macOS installer wrappers are available now.

PyPI / `uv tool install` remain the primary install paths on every platform. Privacy / third-party downloads: [privacy.md](privacy.md).

## Linux (supported)

Two separate AppImages (do not mix them up):

| Artifact name pattern | Role |
|-----------------------|------|
| `srxy-*-installer-<installer_version>-x86_64.AppImage.xz` | **Offline wizard** — full PySide UI; install / update / reinstall / uninstall |
| `srxy-*-installer-online-<installer_version>-x86_64.AppImage.xz` | **Online one-click** — slim Go bootstrap + localhost browser page; install from PyPI |

Download from [GitHub Releases](https://github.com/illescasDaniel/srxy/releases/latest), decompress (`xz -d …`), make executable, and run (type2 static runtime — no host `libfuse2`). Default prefix: `~/Applications/srxy`.

### Offline wizard

- Choose **Install or update**, **Reinstall**, or **Uninstall**.
- Acknowledge the privacy notice, then optionally vendor Tesseract / ffmpeg / semantic extras and prefetch models.
- Optional PATH block in your shell rc (`# >>> srxy PATH >>>`).

### Online one-click

- Opens your default browser to a preparing page, then the install UI on `127.0.0.1` only.
- First launch may download pinned `uv`, managed Python, and the srxy installer package into `~/.cache/srxy/online-bootstrap/` (needs network).
- Always vendors uv / tesseract / ffmpeg and adds PATH; smarter-search packages only when a GPU/MPS is detected. Model weights are **not** prefetched.
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

Notes:

- The online macOS wrapper installs srxy from PyPI and adds PATH in your shell rc.
- On Apple Silicon, optional installer toggles can vendor ffmpeg (martin-riedl static build) and tesseract (pinned Homebrew core bottles from `ghcr.io`, relocated at install time; Homebrew itself is not required).
- On Intel Macs, the installer pins and vendors `uv`; third-party tesseract/ffmpeg vendor downloads remain unavailable.
- No admin rights are required for the default `~/Applications` prefix.
- First **Launch** after install can take several seconds while Qt libraries load cold; later opens from Finder are normal.

## Windows (coming soon)

A dedicated Windows installer is still planned. Until then, use [Installation](installation.md) (`uv tool install` / pipx) on Windows.

## Build from source

| Artifact | Build | Smoke |
|----------|-------|-------|
| Offline | `./packaging/linux-appimage/build.sh` | `./packaging/linux-appimage/smoke-appimage.sh` |
| Online | `./packaging/linux-appimage/build-online.sh` | `./packaging/linux-appimage/smoke-appimage-online.sh` |
| macOS Offline | `./packaging/macos/build-offline.sh` | `./packaging/macos/smoke-offline.sh` |
| macOS Online | `./packaging/macos/build-online.sh` | `./packaging/macos/smoke-online.sh` |

Packaging details (AppDir layout, UPX, checksums, CI): [`packaging/linux-appimage/README.md`](../packaging/linux-appimage/README.md). Bootstrap sources: [`packaging/online-bootstrap/`](../packaging/online-bootstrap/). Compatibility pins: [`packaging/installer_meta.toml`](../packaging/installer_meta.toml).

```bash
uv run python -m srxy.adapters.inbound.installer          # offline wizard (dev)
uv run python -m srxy.adapters.inbound.installer_online   # online UI without AppImage
```
