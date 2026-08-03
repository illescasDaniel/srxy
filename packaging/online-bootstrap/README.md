# Online bootstrap (Go)

Slim AppImage entrypoint that downloads uv / managed Python / srxy from PyPI, then hands off to the Python localhost installer.

Build and packaging notes: [`../linux-appimage/README.md`](../linux-appimage/README.md). End-user guide: [`../../docs/installers.md`](../../docs/installers.md).

```bash
go test ./...
# or via the packaging contract tests:
uv run pytest tests/unit/test_linux_appimage_packaging.py
```
