# Linux AppImage installer

Builds `dist/srxy-installer-<version>-x86_64.AppImage` — an install/uninstall wizard only (not the runtime app).

```bash
./packaging/linux-appimage/build.sh
# or: task build-appimage
```

Uses current [appimagetool](https://github.com/AppImage/appimagetool) with the [type2-runtime](https://github.com/AppImage/type2-runtime) (no host `libfuse2`).

App icon assets live in [`src/srxy/resources/icons/`](../../src/srxy/resources/icons/) and are used for the AppImage, window chrome, and the installed `.desktop` entry.

Installer compatibility is declared in [`packaging/installer_meta.toml`](../installer_meta.toml) (`installer_version`, `min_srxy_version`). Edit that file when the AppImage needs a newer minimum srxy, then rebuild. The installer prefers PyPI only when the latest release is newer than the bundled wheel/source, meets `min_srxy_version`, and lists PySide6 in `requires_dist`.

The AppImage embeds Python + PySide6 for the wizard. It does **not** embed NVIDIA/CUDA, Hugging Face models, Tesseract, or ffmpeg — those are downloaded into `~/Applications/srxy` (or a chosen prefix) after the user acknowledges [docs/privacy.md](../../docs/privacy.md).

macOS / Windows installers are planned separately; shared logic lives under `src/srxy/adapters/inbound/installer/` and `SRXY_HOME` path resolution.
