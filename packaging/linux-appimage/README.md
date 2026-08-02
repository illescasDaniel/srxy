# Linux AppImage installer

Builds `dist/srxy-installer-<version>-x86_64.AppImage` — an install/uninstall wizard only (not the runtime app).

```bash
./packaging/linux-appimage/build.sh
# or: task build-appimage
```

Uses current [appimagetool](https://github.com/AppImage/appimagetool) with the [type2-runtime](https://github.com/AppImage/type2-runtime) (no host `libfuse2`).

App icon assets live in [`src/srxy/resources/icons/`](../../src/srxy/resources/icons/) and are used for the AppImage, window chrome, and the installed `.desktop` entry.

The AppImage embeds Python + PySide6 for the wizard. It does **not** embed NVIDIA/CUDA, Hugging Face models, Tesseract, or ffmpeg — those are downloaded into `~/Applications/srxy` (or a chosen prefix) after the user acknowledges [docs/privacy.md](../../docs/privacy.md).

macOS / Windows installers are planned separately; shared logic lives under `src/srxy/adapters/inbound/installer/` and `SRXY_HOME` path resolution.
