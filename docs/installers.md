# Desktop installers

Optional desktop installers for people who prefer a wizard over `uv tool install` / PyPI. **Linux AppImages are available now.** Windows and macOS installers are in progress.

PyPI / `uv tool install` remain the primary install paths on every platform. Privacy / third-party downloads: [privacy.md](privacy.md).

## Linux (supported)

Two separate AppImages (do not mix them up):

| Artifact name pattern | Role |
|-----------------------|------|
| `srxy-*-installer-<installer_version>-x86_64.AppImage` | **Offline wizard** — full PySide UI; install / update / reinstall / uninstall |
| `srxy-*-installer-online-<installer_version>-x86_64.AppImage` | **Online one-click** — slim Go bootstrap + localhost browser page; install from PyPI |

Download from [GitHub Releases](https://github.com/illescasDaniel/srxy/releases), make executable, and run (type2 static runtime — no host `libfuse2`). Default prefix: `~/Applications/srxy`.

### Offline wizard

- Choose **Install or update**, **Reinstall**, or **Uninstall**.
- Acknowledge the privacy notice, then optionally vendor Tesseract / ffmpeg / semantic extras and prefetch models.
- Optional PATH block in your shell rc (`# >>> srxy PATH >>>`).

### Online one-click

- Opens your default browser to a preparing page, then the install UI on `127.0.0.1` only.
- First launch may download pinned `uv`, managed Python, and the srxy installer package into `~/.cache/srxy/online-bootstrap/` (needs network).
- Always vendors uv / tesseract / ffmpeg and adds PATH; smarter-search packages only when a GPU/MPS is detected. Model weights are **not** prefetched.
- No reinstall/uninstall UI — use the offline wizard or remove the prefix manually. Closing the browser tab stops the process.

Step-by-step install notes: [installation.md § Linux AppImage installers](installation.md#linux-appimage-installers-optional).

## Windows and macOS (coming soon)

Desktop installers for Windows and macOS are planned. Until then, use [Installation](installation.md) (`uv tool install` / pipx) on those platforms.

## Build from source

| Artifact | Build | Smoke |
|----------|-------|-------|
| Offline | `./packaging/linux-appimage/build.sh` | `./packaging/linux-appimage/smoke-appimage.sh` |
| Online | `./packaging/linux-appimage/build-online.sh` | `./packaging/linux-appimage/smoke-appimage-online.sh` |

Packaging details (AppDir layout, UPX, checksums, CI): [`packaging/linux-appimage/README.md`](../packaging/linux-appimage/README.md). Bootstrap sources: [`packaging/online-bootstrap/`](../packaging/online-bootstrap/). Compatibility pins: [`packaging/installer_meta.toml`](../packaging/installer_meta.toml).

```bash
uv run python -m srxy.adapters.inbound.installer          # offline wizard (dev)
uv run python -m srxy.adapters.inbound.installer_online   # online UI without AppImage
```
