# Linux AppImage installer

Builds `dist/srxy-<srxy-version>-installer-<installer-version>-x86_64.AppImage` — an install/uninstall wizard only (not the runtime app). The installer segment is `installer_version` from [`packaging/installer_meta.toml`](../installer_meta.toml).

```bash
./packaging/linux-appimage/build.sh
# or: task build-appimage
./packaging/linux-appimage/smoke-appimage.sh
```

Uses pinned [appimagetool 1.9.1](https://github.com/AppImage/appimagetool/releases/tag/1.9.1) with the [type2-runtime](https://github.com/AppImage/type2-runtime) (no host `libfuse2`). The build script verifies the tool's SHA-256 before packing.

## Relocatable Python

The AppDir installs a uv-managed CPython under `AppDir/usr/python` (`UV_PYTHON_PREFERENCE=only-managed`, `--install-dir`), then creates a **relocatable** venv with `--link-mode copy`. After the venv is created, the build asserts that `usr/venv/bin/python` resolves inside the AppDir — never into `~/.local/share/uv/python` on the build host. `smoke-appimage.sh` re-checks `--help` / `--version` with an isolated `HOME` and a minimal `PATH` so a host uv Python cannot mask a broken AppImage.

## Slim wizard venv

The AppImage venv is **wizard-only**: `PySide6` plus `uv pip install --no-deps` of srxy. It does **not** pull the full search-stack dependency tree (wordfreq, pillow-heif, textual, …). Prefix installs still use the bundled wheel under `usr/share/srxy/` (full package + PyPI prefer-newer via `resolve_srxy_install_spec()`).

After install, [`prune_pyside.sh`](prune_pyside.sh) deletes unused Qt modules (WebEngine, 3D, Charts, Multimedia, designer/qmlls, …) while keeping the Quick / Controls / Dialogs / FolderDialog stack the wizard needs. The build then smoke-tests installer imports and a tiny offscreen QML load. Packing uses squashfs **zstd** at compression level **19** (`--mksquashfs-opt`). Build logs print AppDir and AppImage sizes (`du -sh`).

## Vendor checksums

Installer downloads (uv, tesseract, tessdata, ffmpeg) are HTTPS-only and require a pinned SHA-256 unless `SRXY_INSTALLER_ALLOW_UNVERIFIED=1` (dev only). Refresh digests after changing catalog URLs:

```bash
./packaging/linux-appimage/refresh_checksums.sh
./packaging/linux-appimage/refresh_checksums.sh --check   # print only
./packaging/linux-appimage/refresh_checksums.sh uv ffmpeg # subset
```

## CI

[`.github/workflows/appimage.yml`](../../.github/workflows/appimage.yml) builds and smokes the AppImage on PRs/main (artifacts retained a few days) and attaches the AppImage + `SHA256SUMS` to GitHub Releases on `v*` tags.

## Icons and meta

App icons live in [`src/srxy/resources/icons/`](../../src/srxy/resources/icons/). The installed app uses `srxy-*.png`; the AppImage / installer wizard uses `srxy-installer-*.png` (same artwork with a gears badge). Regenerate installer icons after changing the base set:

```bash
task generate-installer-icons
# or: uv run python scripts/generate_installer_icons.py
```

The AppImage embeds that icon as `.DirIcon` / `srxy-installer.png` for file managers. Showing it in the browser still needs a working AppImage thumbnailer on the host (e.g. KDE `appimagethumbnail` via `kio-extras` + `libappimage`). Without that, desktops fall back to the generic AppImage MIME icon — packaging cannot override that.

Installer compatibility is declared in [`packaging/installer_meta.toml`](../installer_meta.toml) (`installer_version`, `min_srxy_version`). Edit that file when the AppImage needs a newer minimum srxy, then rebuild. The installer prefers PyPI only when the latest release is newer than the bundled wheel/source, meets `min_srxy_version`, and lists PySide6 in `requires_dist`.

The AppImage embeds Python + PySide6 for the wizard. It does **not** embed NVIDIA/CUDA, Hugging Face models, Tesseract, or ffmpeg — those are downloaded into `~/Applications/srxy` (or a chosen prefix) after the user acknowledges [docs/privacy.md](../../docs/privacy.md).

macOS / Windows installers are planned separately; shared logic lives under `src/srxy/adapters/inbound/installer/` and `SRXY_HOME` path resolution.

The prefix launcher writes runtime output to `{SRXY_HOME}/logs/srxy.log` when started from the desktop menu (see [docs/privacy.md](../../docs/privacy.md)).
