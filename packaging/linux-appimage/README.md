# Linux AppImage installers

Two separate artifacts (do not overwrite each other):

| Artifact | Build | Smoke | UI |
|----------|-------|-------|----|
| `dist/srxy-<srxy-version>-installer-<installer-version>-x86_64.AppImage` | [`build.sh`](build.sh) | [`smoke-appimage.sh`](smoke-appimage.sh) | PySide6 full wizard (bundled wheel) |
| `dist/srxy-<srxy-version>-installer-online-<installer-version>-x86_64.AppImage` | [`build-online.sh`](build-online.sh) | [`smoke-appimage-online.sh`](smoke-appimage-online.sh) | Go bootstrap + browser UI (PyPI) |

The installer segment is `installer_version` from [`packaging/installer_meta.toml`](../installer_meta.toml).

```bash
./packaging/linux-appimage/build.sh
# or: task build-appimage
./packaging/linux-appimage/smoke-appimage.sh

./packaging/linux-appimage/build-online.sh
# or: task build-appimage-online
./packaging/linux-appimage/smoke-appimage-online.sh
```

Uses pinned [appimagetool 1.9.1](https://github.com/AppImage/appimagetool/releases/tag/1.9.1) with the [type2-runtime](https://github.com/AppImage/type2-runtime) (no host `libfuse2`). The build scripts verify the tool's SHA-256 before packing.

## Relocatable Python

Each AppDir installs a uv-managed CPython under `AppDir/usr/python` (`UV_PYTHON_PREFERENCE=only-managed`, `--install-dir`), then creates a **relocatable** venv with `--link-mode copy`. After the venv is created, the build **rewrites** `usr/venv/bin/python*` to relative symlinks (and a relative `pyvenv.cfg` `home`) and asserts the symlink target is relative — never an absolute build-host path. (`readlink -f` alone is not enough: absolute links still resolve on CI while the build tree exists, then break for users.) Smoke scripts re-check `--help` / `--version` with an isolated `HOME` and a minimal `PATH` so a host uv Python cannot mask a broken AppImage.

## Offline wizard (PySide)

The offline AppImage venv is **wizard-only**: `PySide6` plus `uv pip install --no-deps` of srxy. It does **not** pull the full search-stack dependency tree (wordfreq, pillow-heif, textual, …). Prefix installs still use the bundled wheel under `usr/share/srxy/` (full package + PyPI prefer-newer via `resolve_srxy_install_spec()`).

After install, [`prune_pyside.sh`](prune_pyside.sh) deletes unused Qt modules (WebEngine, 3D, Charts, Multimedia, designer/qmlls, …) while keeping the Quick / Controls / Dialogs / FolderDialog stack the wizard needs. The build then smoke-tests installer imports and a tiny offscreen QML load. Packing uses squashfs **zstd** at compression level **19**. Build logs print AppDir and AppImage sizes (`du -sh`). Optional model prefetch remains available in this wizard.

## Online one-click (Go bootstrap + localhost browser UI)

The online AppImage embeds a small **Go** bootstrap binary (UPX-compressed at build time) and meta (no CPython, no uv, **no** bundled wheel). On first launch it opens your browser to a preparing page, downloads pinned `uv` + managed Python into `~/.cache/srxy/online-bootstrap/`, installs `srxy>=<build>,<next_major>` from PyPI (`--no-deps`) into a cache venv, then hands off to the Python localhost installer (`installer_online`). Later launches reuse the cache (uv upgrades within the major bound when a newer 1.x exists). The *prefix* install still uses `resolve_pypi_install_spec()`. Auto options: PATH, tesseract, ffmpeg; semantic packages only when GPU/MPS is present; `prefetch_models=False`. Checksums are written to `SHA256SUMS-online` so they do not overwrite the offline `SHA256SUMS`.

Building requires **Go** and **xz** (to unpack pinned UPX). Set `SRXY_ONLINE_SKIP_UPX=1` to skip UPX on the online bootstrap. The offline AppImage may also UPX pruned Qt `.so` files after `prune_pyside.sh`; set `SRXY_OFFLINE_SKIP_UPX=1` to skip that pass. Override the bootstrap package with `SRXY_ONLINE_BOOTSTRAP_SPEC` for local testing. Bootstrap sources live under [`packaging/online-bootstrap/`](../online-bootstrap/).

## Vendor checksums

Installer downloads (uv, tesseract, tessdata, ffmpeg) are HTTPS-only and require a pinned SHA-256 unless `SRXY_INSTALLER_ALLOW_UNVERIFIED=1` (dev only). Refresh digests after changing catalog URLs:

```bash
./packaging/linux-appimage/refresh_checksums.sh
./packaging/linux-appimage/refresh_checksums.sh --check   # print only
./packaging/linux-appimage/refresh_checksums.sh uv ffmpeg # subset
```

## CI

[`.github/workflows/appimage.yml`](../../.github/workflows/appimage.yml) builds and smokes **both** AppImages on PRs/main (separate artifacts) and attaches both AppImages + checksum files to GitHub Releases on `v*` tags.

## Icons and meta

App icons live in [`src/srxy/resources/icons/`](../../src/srxy/resources/icons/) (packaged; may be compressed). The uncompressed original is [`assets/icons/srxy.png`](../../assets/icons/srxy.png). The installed app uses `srxy-*.png`; installer AppImages use `srxy-installer-*.png` (same artwork with a gears badge). Regenerate packaged icons after changing the original:

```bash
task generate-installer-icons
# or: uv run python scripts/generate_installer_icons.py
task generate-macos-icons
```

The AppImage embeds that icon as `.DirIcon` for file managers. Showing it in the browser still needs a working AppImage thumbnailer on the host (e.g. KDE `appimagethumbnail` via `kio-extras` + `libappimage`). Without that, desktops fall back to the generic AppImage MIME icon — packaging cannot override that.

Installer compatibility is declared in [`packaging/installer_meta.toml`](../installer_meta.toml) (`installer_version`, `min_srxy_version`). Edit that file when either AppImage needs a newer minimum srxy, then rebuild.

The offline AppImage embeds Python + PySide6 for the wizard and a wheel for optional offline prefix installs. The online AppImage embeds a Go bootstrap + meta only (downloads uv, Python, and srxy from PyPI on first run). Neither embeds NVIDIA/CUDA, Hugging Face models, Tesseract, or ffmpeg — those are downloaded into `~/Applications/srxy` (or a chosen prefix) after the user acknowledges [docs/privacy.md](../../docs/privacy.md).

macOS / Windows installers are planned separately; shared install logic lives under `src/srxy/adapters/inbound/installer/` (online UI under `installer_online/`) and `SRXY_HOME` path resolution.

The prefix launcher writes runtime output to `{SRXY_HOME}/logs/srxy.log` when started from the desktop menu (see [docs/privacy.md](../../docs/privacy.md)).
